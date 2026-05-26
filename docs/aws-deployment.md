# AWS Batch Deployment — Runbook

How to run a normative recompute on AWS Batch instead of a local machine.
Background and design rationale live in `aws-deployment-assessment.md`;
this file is a task-oriented operations guide.

## Why this exists at all

A full recompute with source analysis enabled is ~4–6 hours sequential on
a modern laptop. That's slow enough to kill iteration — every parameter
tweak, new dataset, or pipeline change means starting over and waiting out
a half-day. The cloud path gets the same run done in **~35 minutes for
about $2** on LEMON, using Spot instances that are ~30% of on-demand price.

The full "why cloud, why spot, and when to stay local" discussion lives
in the [README's "Running on AWS Batch" section](../README.md#running-on-aws-batch).
This file assumes you've decided to run in the cloud and just want to know
how.

## Prerequisites

- An AWS account with `AdministratorAccess` (or equivalent) for your IAM user.
- MFA on the IAM user you use for the CLI.
- Billing alerts configured (recommended `$25/mo`).
- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5.
- [Docker](https://docs.docker.com/get-docker/) or [OrbStack](https://orbstack.dev/), only if you want to build custom images locally. The default config pulls from GHCR.
- A clone of this repo with Python 3.10+ installed locally (needed to enumerate subjects before submission).

## One-time account setup

1. `aws configure --profile peak-mind` (or use SSO) — standard credential chain.
2. Set the profile for this project:
   ```bash
   cd open-normative-eeg
   cat > .envrc <<'EOF'
   export AWS_PROFILE=peak-mind
   export AWS_REGION=us-east-2
   EOF
   direnv allow .
   ```
3. Confirm: `aws sts get-caller-identity` should print your account ID and the IAM user ARN.

## One-time infra setup (`terraform apply`)

```bash
cd infra/aws
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set a globally-unique bucket_name.

terraform init
terraform plan         # review what will be created
terraform apply        # takes ~2 minutes
```

When apply finishes:

```bash
terraform output aws_config_yaml_snippet
```

Copy the printed YAML block into `../../aws-config.yaml` (create from
`aws-config.example.yaml` if it doesn't exist). `aws-config.yaml` is
gitignored — never commit it.

## Daily use

The CLI is subcommand-based. Five commands: `submit`, `status`, `logs`, `download`, `list`.

```bash
# LEMON, 37ch, full source analysis, 20 parallel slices
python scripts/cloud_recompute.py submit \
    --dataset lemon --channels 37 \
    --source --ba-connectivity --dk-connectivity --save-psd \
    --slices 20 --follow

# Check status at any time — reads the _submission.json manifest in S3
python scripts/cloud_recompute.py status <run_id>
python scripts/cloud_recompute.py status              # most recent runs
python scripts/cloud_recompute.py list                # all runs in the bucket

# Logs — array children + merge, dedup'd across attempts
python scripts/cloud_recompute.py logs <run_id>           # last ~100 events
python scripts/cloud_recompute.py logs <run_id> --follow  # stream live

# Download merged results locally
python scripts/cloud_recompute.py download <run_id>       # ./norm_out/ by default
```

What happens:

1. `cloud_recompute.py` enumerates subjects locally (no raw data read), sizes the array, and submits one Batch array job + one merge job (depends on the array).
2. Each array element pulls the container image, resumes any prior checkpoints from S3, processes its subject-range slice, and streams per-subject JSON/PSD back to `s3://<bucket>/runs/<run_id>/subjects/`.
3. When all array elements succeed, the merge job runs `build_norms.py --merge`, writes `norms.json`, `norms.csv`, `subjects.csv`, and `npz/*.npz` to `s3://<bucket>/runs/<run_id>/out/`.
4. `--follow` tails job status until the merge finishes.

Download results:

```bash
aws s3 sync s3://<bucket>/runs/<run_id>/out/ ./norms_output_<run_id>/
```

## Costs and timing to expect

Observed on real runs (us-east-1, m*i.2xlarge spot, 28 GB container memory, 2 workers/container, full source pipeline with `--source --ba-connectivity --dk-connectivity --save-psd`):

| Run | Array wall time | Merge wall time | Total | Cost |
|---|---|---|---|---|
| LEMON (215 subj × 2 conditions, 37ch, full source) | ~35 min | ~42 min | **~78 min** | **~$2.00** |
| Dortmund (608 subj × 2 conditions, 37ch, full source) | ~40–50 min (projected) | ~90 min (projected — merge scales nonlinearly with subject count) | ~135 min | **~$4–5** (projected) |
| Scalp-only (no `--source`) | ~3–5× faster | ~10× faster | dominated by array | ~50% less |
| Idle steady state (S3 bucket + CloudWatch log group) | — | — | — | ~$1–2 / month |

**Why is merge so long?** The merge job walks every normative cell (channel × band × metric × age-bin × condition ≈ 150,000 cells for the full source pipeline) and runs Shapiro-Wilk + CI + prediction intervals + percentiles on the N subjects in each cell. Per-cell cost is ~linear in N but the cell count is fixed, so for LEMON's N=215 it's 42 min of single-threaded scipy.stats. If this becomes the bottleneck for larger datasets we'd want to parallelize the merge, or drop CI/PI computation for non-headline cells.

**Per-run breakdown** (LEMON, 31 slices):

| Component | Share | Notes |
|---|---|---|
| 31 × m*i.2xlarge spot × ~35 min | ~$1.75 | The dominant line item |
| 1 × merge (m*i.2xlarge, ~10 min) | ~$0.05 | Single-instance; runs when array completes |
| EBS (200 GB gp3 × 31 × ~1 hr) | ~$0.07 | Required: 63 GB LEMON sync + work files |
| S3 storage (outputs + mirrors) | < $0.01/run, ~$1.50/mo idle | Bucket grows by ~700 MB per retained run |
| CloudWatch Logs | < $0.01 | 30-day retention |

At weekly cadence: **~$8–10/mo**. The `monthly_budget_usd` alert fires at 80% of your threshold.

### Ways to trade cost for time

- **Default (spot, full source, 31 slices):** ~35 min, ~$2. Sensible default.
- **Spot off (change compute env to `type = "EC2"`):** ~20–25 min, ~$6. Buys predictability; worth it only when you're waiting on a result for a deadline.
- **Scalp-only (drop `--source --ba-connectivity --dk-connectivity`):** ~10 min, ~$0.50. Good for quick iteration on preprocessing changes that don't touch source analysis.
- **More parallelism (bump AWS vCPU quota beyond 256):** can bring LEMON under 20 min total. Current 256 vCPU quota caps us at 32 concurrent slices × 8 vCPU; a bump to 512 vCPU would let us halve the per-slice subject count. Bottleneck moves from "wait for containers" to "wait for spot provisioning" (~3–5 min unavoidable).
- **Skip selective sync (set `DATA_MIRROR` empty, use loader downloads):** usually slower, not recommended for LEMON. Listed here only so you know the sync is optional.

## Adding a new dataset

A new dataset is a **code change**, not a config change. Add a loader in `open_normative/datasets/<name>.py` (subclass `BaseLoader`, implement `iter_subject_files()` + `load()`), register it in `DATASETS`, and it becomes available via `--dataset <name>`.

The container image needs a rebuild to include the new loader. GH Actions
publishes on every main-branch push that touches pipeline code.

## Where the raw data has to live for `submit` to work

`cloud_recompute.py submit` enumerates subjects at submit time so it can
size the array job and write per-slice manifests. It does *not* read EEG
content — only filenames and `participants.tsv`. There are two supported
ways to satisfy that:

### Option A — local mirror (`--data-dir` or default `~/Data/EEG/<DATASET>/`)

The legacy path. Use this when:

- The dataset isn't on a public AWS bucket (currently: **LEMON only**, hosted at GWDG in Germany).
- You already keep a local copy and want submit to pick it up.

```bash
# LEMON — must exist locally before submit
python scripts/lemon_download.py ~/Data/EEG/LEMON
python scripts/cloud_recompute.py submit --dataset lemon --channels 37 ...

# Any OpenNeuro dataset, with explicit local copy
python scripts/dortmund_download.py ~/Data/EEG/DORTMUND
python scripts/cloud_recompute.py submit --dataset dortmund --channels 37 \
    --data-dir ~/Data/EEG/DORTMUND ...
```

The cloud containers still stream from S3 at run time (via the
auto-defaulted `--data-mirror`); the local copy is only used by submit.

### Option B — auto-stage from OpenNeuro (no local data)

Default for OpenNeuro datasets (`dortmund`, `srm`, `trt`, `depress`)
when `--data-dir` is omitted. Submit lists `s3://openneuro.org/dsXXXXXX/`,
downloads `participants.tsv` + `dataset_description.json`, and creates
empty placeholder files matching the BIDS layout in a temp dir. The
loader's existing filename-glob enumeration walks those stubs to compute
the slice manifest. Cleanup is automatic on process exit.

```bash
# Zero local data needed — everything lives in S3
python scripts/cloud_recompute.py submit --dataset srm --channels 37 \
    --source --ba-connectivity --dk-connectivity --save-psd --slices 8
```

What you'll see at the top of the output:

```
staged 153 EEG path stubs from s3://openneuro.org/ds003775/ (no local data download needed)
```

The unsigned S3 listing finishes in a few seconds for any of these
datasets (a few thousand keys at most). Containers still pull real EEG
content from `s3://openneuro.org/dsXXXXXX/` at run time exactly as in
Option A.

**HBN is not in this auto-list** — its data is split across 11 release
subdirectories on `s3://fcp-indi/data/Projects/HBN/BIDS_EEG/cmi_bids_R{1..11}/`
and you have to point `--data-mirror` at one release at a time. That
case still requires a local copy of that release's BIDS root for
submit-time enumeration (Option A).

## Lessons from the initial deployment

- **Don't attach a custom `service_role` to the Batch compute environment.** AWS Batch now uses the `AWSServiceRoleForBatch` service-linked role automatically; passing a custom service role produces `ecs:DescribeClusters` denials and leaves the compute env in `INVALID`. The Terraform module in this repo already omits it.
- **`aws_batch_compute_environment.compute_resources.instance_type` is a list but uses the singular key.** Don't use `instance_types` (plural) — the provider rejects it.
- **Array jobs require `size >= 2`.** Smallest smoke test is `--slices 2 --per-slice 1`.
- **ENTRYPOINT can't be replaced via `containerOverrides.command` in Batch.** Submit-time commands become args to the entrypoint, not a replacement. Use a `MODE=array|merge` env var in the entrypoint to branch.
- **GHCR packages default to private.** After the first publish, flip the package to Public (GitHub org → Packages → package → Package settings → Change visibility) or Batch can't pull. If your org disables public packages, enable them under **org Settings → Packages**.
- **Check the bucket's actual region.** `aws s3 ls` lists all buckets globally, but each bucket has a specific region. Terraform's S3 resource errors with `BucketAlreadyOwnedByYou` when your provider region differs from the bucket's region. `aws s3api get-bucket-location --bucket <name>` shows the truth (`null` means us-east-1).
- **For LEMON, mirror once to your S3 bucket**: LEMON is on GWDG FTP (Germany), not AWS. For Dortmund, HBN, MIPDB — stream directly from `s3://openneuro.org` or `s3://fcp-indi` (IAM already grants the reads). Keep your runs in us-east-1 where these source buckets live to avoid cross-region egress.

## Troubleshooting

### `aws sts get-caller-identity` fails

Run `aws sso login --profile <name>` (for SSO) or verify `AWS_PROFILE` and
`~/.aws/credentials`.

### Terraform apply fails on `aws_batch_compute_environment`

The default VPC may be missing (unusual — check the AWS console → VPC). If
so, create a default VPC from the console or pass custom `subnets` into the
module.

### Jobs stuck in `RUNNABLE` forever

- Check the compute environment state (`aws batch describe-compute-environments`).
  If `INVALID`, the details field tells you why (common: an instance type in
  `instance_types` not available in your region).
- Spot capacity may be exhausted. Try adding `m6i.2xlarge` / `m5.2xlarge` to
  `instance_types` in terraform.tfvars and re-apply.

### Image pull failure in job logs

The default image (`ghcr.io/peak-mind-llc/open-normative-eeg:latest`) must be
**public** on GHCR. If you forked:

1. Push to your fork triggers `.github/workflows/publish-image.yml` on merge
   to `main` — that publishes to `ghcr.io/<your-user-or-org>/open-normative-eeg`.
2. In GitHub → your org/user → Packages → open-normative-eeg → Package
   settings → Change visibility → Public.
3. Update `compute.image` in `aws-config.yaml` to your image URI.

### Dortmund run is slower / more expensive than expected

You probably ran in `us-east-2` (or elsewhere) while OpenNeuro lives in
`us-east-1`. `cloud_recompute.py` warns on this by default. Options:
(a) re-apply Terraform with `region = "us-east-1"`, or
(b) mirror Dortmund to your own bucket once, then run without cross-region egress.

### Spot preemptions are high

- Accept it — the retry strategy handles it at ~2 min rework per interruption.
- Or, switch the compute env to on-demand by changing
  `aws_batch_compute_environment.spot.compute_resources.type` from `"SPOT"`
  to `"EC2"` and re-applying. Costs ~3× more; worth it only for time-sensitive runs.

## Tearing down

```bash
# Delete bucket contents first (Terraform won't force-delete a non-empty bucket).
aws s3 rm s3://<your-bucket>/ --recursive

cd infra/aws
terraform destroy
```

The GHCR image, Terraform state file, and `aws-config.yaml` stay on your
laptop — remove manually if you want a clean slate.

## Reproducibility gate

Per-machine determinism is guaranteed by seeded RNGs + BLAS thread pinning
(see `open_normative/parameters.py` docstring and the Dockerfile ENV). Cloud
output should match local output bit-for-bit on the same machine type. If
drift appears, verify:

1. Docker image SHA matches locally (`docker pull ...@sha256:...`) and in CloudWatch.
2. No new unseeded RNG introduced in the pipeline (`tests/test_determinism.py` guards specparam).
3. The compute environment is restricted to a single instance family
   (mix of AVX2 / AVX512 CPUs can produce sub-ULP drift).
