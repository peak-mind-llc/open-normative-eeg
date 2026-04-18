# AWS Batch Deployment — Runbook

How to run a normative recompute on AWS Batch instead of a local machine.
Background and design rationale live in `aws-deployment-assessment.md`;
this file is a task-oriented operations guide.

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

```bash
# LEMON, 37ch, full source analysis, 20 parallel slices
python scripts/cloud_recompute.py \
    --dataset lemon \
    --channels 37 \
    --source --ba-connectivity --dk-connectivity \
    --save-psd \
    --slices 20 \
    --follow
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

## Costs to expect

| Run | Approximate cost |
|---|---|
| LEMON (220 subj, 37ch, source on) | ~$0.60 |
| Dortmund (608 subj, 37ch, source on) | ~$1.00 |
| Idle (bucket + log group only) | ~$1–2 / month |

At weekly cadence: **~$8–10/mo**. The `monthly_budget_usd` alert fires at 80% of your threshold.

## Adding a new dataset

A new dataset is a **code change**, not a config change. Add a loader in `open_normative/datasets/<name>.py` (subclass `BaseLoader`, implement `iter_subject_files()` + `load()`), register it in `DATASETS`, and it becomes available via `--dataset <name>`.

The container image needs a rebuild to include the new loader. GH Actions
publishes on every main-branch push that touches pipeline code.

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
