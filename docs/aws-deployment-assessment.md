# AWS Deployment Assessment — Norm Recomputation

**Status**: Draft assessment to inform the implementation PR.
**Scope**: Offload normative recomputation (`scripts/build_norms.py`) to elastic cloud compute so local dev machines stop being the bottleneck on iteration speed.
**Non-scope**: Public reproducibility pipeline; release-grade provenance; CI-triggered runs; new datasets.

## TL;DR

Use **AWS Batch on EC2 Spot array jobs**, one array element per subject-range slice, with per-subject checkpoints synced to S3 after each subject completes. A single on-demand merge job stitches slices at the end. Expected cost: **~$0.60 per LEMON recompute, ~$1 per Dortmund recompute, ~$1/mo idle storage.** Total cloud spend at weekly recompute cadence: under $10/mo.

The pipeline's existing `--subject-range` slicing (`build_norms.py`) and order-independent aggregation (`normative.py`) are exactly the shape Batch array jobs consume. No pipeline science changes; only a thin `--checkpoint-sync` flag, a submission CLI, a Dockerfile, and a Terraform module.

## Pipeline assessment

### Recompute entrypoint

`scripts/build_norms.py` drives the full recompute. Key facts:

- **CLI dispatch**: `ProcessPoolExecutor` with N workers (`--jobs`). Each worker runs `_process_one_subject()` end-to-end for one `(subject_id, condition)` pair.
- **Subject slicing**: `--subject-range START:END` already exists. `scripts/distribute.py` uses it to split work across SSH-mounted machines. It is the natural work-distribution primitive.
- **Merge mode**: `build_norms.py --merge --merge-dir ...` reads multiple `subjects/` directories and aggregates. Already in place.

### Checkpoint granularity

After each subject completes, `_save_subject_result()` writes:

- `subjects/{subject_id}_{condition}.json` — flattened metrics dict (one file per condition per subject).
- `subjects/{subject_id}_{condition}_psd.npz` — PSD arrays (optional, with `--save-psd`).

On startup, `load_checkpoints()` scans the directory and skips subjects with existing checkpoints. **Resume is clean at subject boundaries.** A killed worker only loses the subject currently in flight. This is exactly the interruption model spot instances need.

No checkpointing within a subject (ICA → spectral → DICS → connectivity is all-or-nothing for one subject). That's fine: one subject is ~75–150 seconds, well under any spot interruption warning window.

### Aggregation determinism

`open_normative/normative.py` builds per-cell lists across subjects, then computes per-cell statistics:

- `np.mean(arr)`, `np.std(arr, ddof=1)`, `np.percentile(arr, p)` — all order-independent over float64.
- Log-transform, Shapiro-Wilk, outlier flags — applied per cell, not across cells.

**Aggregation is order-independent.** Slices can be merged in any sequence, from any number of machines, and the result is identical. This is the critical property for the reproducibility gate.

### Resource profile per subject

From `build_norms.py`'s own documentation and empirical behavior:

- **Memory**: ~2 GB/worker for 19-channel, ~3 GB/worker for 37-channel.
- **CPU**: Fully CPU-bound. PICARD ICA, scipy FFT, mne-connectivity, DICS beamformer — all CPU.
- **GPU**: None used, none needed.
- **Wall time**: ~75–150 seconds per (subject, condition) on modern CPU, scaling with recording length and whether `--source` is enabled.

### Data volumes (corrected)

Only the resting-state EO/EC blocks each pipeline needs are downloaded, not full recordings. Real sizes:

| Dataset | Subjects | Source | Total size |
|---|---|---|---|
| LEMON | ~220 | GWDG FTP (Germany) | ~10–20 GB |
| Dortmund | ~608 | OpenNeuro `s3://openneuro.org/ds005385` (us-east-1) | ~24 GB |
| HBN (future) | ~2800 | AWS Open Data | TBD |

Storage cost at this scale is negligible (< $2/mo for both datasets in S3 Standard).

### Non-determinism risks

Known fixed seeds: ICA (`random_state=42`), RANSAC bad-channel detection (`random_state=42`).

Known un-pinned: **specparam fitting** uses scipy's default minimize; no seed control. Re-running the same subject can produce sub-machine-precision differences (~1e-6) in periodic power estimates.

**Mitigation**: Pin specparam's RNG before the reproducibility gate test. One-line change in `parameters.py`. Without it, the gate will fail on numerical noise.

## Cloud compute decision

### Chosen: AWS Batch on EC2 Spot (array jobs)

**Why this shape fits:**

1. **Array jobs map 1:1 to subject-range slices.** Each array element receives `AWS_BATCH_JOB_ARRAY_INDEX`, which computes a start/end subject index. The existing `--subject-range` flag takes it from there with zero pipeline changes.
2. **Batch handles spot preemption natively.** A retry strategy with `evaluateOnExit` catches `Host EC2 * terminated` reasons and re-queues. The new container pulls existing checkpoints from S3 and `load_checkpoints()` skips what's done.
3. **Scales to zero.** `minvCpus: 0` on the compute environment means no cost when idle. No always-on control plane.
4. **Per-subject checkpoint granularity survives preemption cleanly.** Worst-case rework on interruption: one subject (~2 min).
5. **No cluster to manage.** Batch owns capacity provisioning; we just submit jobs.

### Alternatives considered and rejected

| Option | Why rejected |
|---|---|
| **SageMaker Processing** | Job model (one container, one input channel) fights spot-interrupt-and-resume over many subjects. Would reimplement the array pattern on top. No clear win over Batch. |
| **ECS Fargate Spot** | No compute-optimized instance shapes ≥8 vCPU; ~2x cost of EC2 Spot for this CPU-bound workload. |
| **Raw EC2 Spot Fleet + custom dispatcher** | Reinvents Batch. Existing `distribute.py` SSH model is too coupled to adapt. |
| **AWS Lambda** | 15-minute timeout kills a single-subject run with `--source`. |
| **Extending `distribute.py` to AWS** | SSH + shared-NFS assumption is too deep in the design. Replacing SSH with EC2 API is a bigger refactor than adding a Batch submission path. |

### Instance fleet

Mixed Spot fleet, ranked by preference:

- `c7i.2xlarge` (8 vCPU, 16 GB) — newest compute-optimized, ~$0.07/hr spot
- `c6i.2xlarge` (8 vCPU, 16 GB) — widely available, ~$0.10/hr spot
- `c5.2xlarge` (8 vCPU, 16 GB) — fallback for spot availability, ~$0.14/hr spot

8 vCPU matches `--jobs 4` at 3 GB/worker with headroom. `SPOT_CAPACITY_OPTIMIZED` allocation picks the cheapest pool with available capacity.

## End-to-end workflow

### One-command submission (local dev machine)

```bash
python scripts/cloud_recompute.py --dataset lemon --channels 37 --source \
    --slices 20 --follow
```

What the submission script does:

1. Generate `run_id` (e.g., `lemon-37ch-2026-04-17T18-22-04`), capture git SHA + CLI args.
2. Enumerate subjects via the dataset loader (`iter_subject_files()` — no raw data loaded).
3. Split subjects into N slices, compute `(start, end)` index ranges.
4. Check S3 for existing checkpoints under `s3://<bucket>/runs/<run_id>/subjects/`; skip slices already complete.
5. Submit Batch array job (boto3 `submit_job` with `arrayProperties.size=N`).
6. Submit a merge job with `dependsOn: [{jobId: <array-id>, type: "N_TO_N"}]`.
7. Tail CloudWatch Logs until completion.

### Per-slice container execution

```bash
# scripts/batch_entrypoint.sh (pseudocode)
SLICE=$AWS_BATCH_JOB_ARRAY_INDEX
START=$(python -c "print($SLICE * $PER_SLICE)")
END=$(python -c "print(($SLICE + 1) * $PER_SLICE)")

# Resume: pull any existing checkpoints
aws s3 sync s3://$BUCKET/runs/$RUN_ID/subjects/ /work/subjects/

# Pull raw data for this slice only (LEMON). Dortmund streams direct.
if [ "$DATASET" = "lemon" ]; then
    aws s3 sync s3://$BUCKET/mirrors/lemon/ /work/data/ \
        --exclude "*" --include "sub-*/*"  # filtered by subject-range in build_norms
fi

# Run pipeline. Only new flag is --checkpoint-sync.
python scripts/build_norms.py /work/data \
    --dataset $DATASET --channels $CHANNELS --source \
    --subject-range $START:$END \
    --output /work \
    --checkpoint-sync s3://$BUCKET/runs/$RUN_ID/ \
    -j 4
```

### Spot interruption handling

EC2 sends a 2-minute termination notice. Batch's retry strategy:

```json
{
  "attempts": 5,
  "evaluateOnExit": [
    {"onStatusReason": "Host EC2*", "action": "RETRY"},
    {"onReason": "*", "action": "EXIT"}
  ]
}
```

Preempted tasks re-queue. Fresh container boots, `aws s3 sync` pulls checkpoints already written, `load_checkpoints()` skips completed subjects. Worst-case rework: one subject (~90s) + container boot (~30s) ≈ 2 minutes per interruption.

### Checkpoint sync (the one pipeline change)

Add `--checkpoint-sync s3://bucket/prefix/` to `build_norms.py`. After `_save_subject_result()` writes the local checkpoint files, shell out to `aws s3 cp` for the two files (JSON + optional PSD NPZ). ~1 MB per subject; cost is negligible; the upload is synchronous so a preemption between "file written locally" and "file on S3" loses at most the current subject, same as a local crash.

### Merge

After all array elements succeed, the merge job runs on an **on-demand** `m6i.xlarge` (memory-biased; you don't want the merge itself preempted):

1. `aws s3 sync s3://bucket/runs/<run_id>/subjects/ /work/subjects/`
2. `python scripts/build_norms.py --merge --merge-dir /work/subjects --output /work/out`
3. `aws s3 sync /work/out/ s3://bucket/runs/<run_id>/out/`

Produces the full output set (`norms.json`, `norms.csv`, `subjects.csv`, `norms_psd.npz`, `npz/*.npz`) — identical to what a local run produces.

## Open-source configuration model

The tool must be adoptable by anyone who clones the repo. Per-user values live in a single YAML config; nothing hardcoded to Peak Mind's AWS account.

### Config file: `aws-config.yaml`

`aws-config.example.yaml` is committed and documented. `aws-config.yaml` is gitignored.

```yaml
aws:
  profile: default          # uses standard AWS SDK credential chain
  region: us-east-1         # keep us-east-1 for free OpenNeuro reads

storage:
  bucket: my-norm-recomputes
  runs_prefix: runs/
  mirrors_prefix: mirrors/

compute:
  # Populated by `terraform apply`. Hand-edit only if managing infra separately.
  batch_job_queue: norm-recompute-queue
  batch_job_definition: norm-recompute-jd
  batch_merge_job_definition: norm-recompute-merge-jd

  # Default points at our public image; override for custom builds.
  image: ghcr.io/peak-mind-llc/open-normative-eeg:latest

  instance_types: [c7i.2xlarge, c6i.2xlarge, c5.2xlarge]
  max_vcpus: 256

slicing:
  default_slices: 20
  min_subjects_per_slice: 5

notifications:
  email: null
  monthly_budget_usd: 25
```

### Credentials

Use the standard AWS SDK credential chain only. The config references a profile name; it never contains access keys. Users with AWS SSO, instance roles, or `~/.aws/credentials` all work unchanged.

### Dataset sources

Source URIs for public datasets (OpenNeuro S3 buckets, GWDG FTP) are **properties of the dataset**, not the user. They live in the loaders in `open_normative/datasets/`. Only the *mirror destination* (where a user stages FTP-hosted datasets into their own S3) is user-configurable.

Adding a new public dataset is a code change in the loader, not a config change.

### Infrastructure: Terraform module in `infra/aws/`

One Terraform module provisions everything:

- S3 bucket (with lifecycle rules for old runs)
- ECR repo (optional, only needed for custom images)
- Batch compute environment, job queue, job definitions
- IAM service role, instance role, job role
- CloudWatch log group
- SNS topic + AWS Budgets alert

Onboarding flow:

```
1. git clone && cd open-normative-eeg
2. cp aws-config.example.yaml aws-config.yaml  # edit bucket name, email
3. aws configure sso                             # or existing AWS_PROFILE
4. cd infra/aws && terraform init && terraform apply
5. python scripts/cloud_recompute.py --dataset lemon
```

Teardown is `terraform destroy`. Everything is reversible and version-controlled.

### Public pre-built container image

GitHub Actions publishes `ghcr.io/peak-mind-llc/open-normative-eeg:<git-sha>` on each main-branch commit. New users don't need to build or push an image unless they're modifying pipeline code. This cuts onboarding from "install Docker + ECR setup" to "terraform apply + go."

### Universal vs per-user

| Committed to repo | Per-user (`aws-config.yaml`) |
|---|---|
| Terraform module | AWS profile, region |
| Dockerfile + entrypoint | S3 bucket name |
| `cloud_recompute.py` CLI | Batch resource names (populated by TF) |
| Dataset source URIs (loaders) | Instance types, slice count |
| Pipeline code | Budget threshold, notification email |
| Pinned requirements | Container image override (if custom build) |

## What needs to be built

1. **`--checkpoint-sync s3://...` in `build_norms.py`** (~30 lines). After each `_save_subject_result()`, shell out to `aws s3 cp` for the written files.
2. **`scripts/cloud_recompute.py`** (~200 lines). Load config, compute slices, submit array + merge Batch jobs via boto3, tail CloudWatch logs.
3. **`Dockerfile` + `requirements-pinned.txt` + `scripts/batch_entrypoint.sh`**. Reproducible container build; pinned Python, MNE, specparam versions.
4. **`infra/aws/` Terraform module**. Batch compute env, queue, job definitions, IAM, S3 bucket, SNS, Budgets.
5. **`aws-config.example.yaml`** with every field documented.
6. **`.github/workflows/publish-image.yml`**. GitHub Actions to build and publish container on main pushes.
7. **`docs/aws-deployment.md`** runbook: how to run a recompute, how to add a new dataset, how to tear down, expected cost envelope.
8. **Pin specparam RNG seed** in `parameters.py`. One-line change; required for the reproducibility gate.

**Not built**: changes to pipeline science, new datasets, CI-triggered recompute, public-facing reproducibility pipeline.

## Cost envelope

### Per-recompute (LEMON, 37ch, with `--source`)

- 220 subjects × ~120s × 2 conditions ÷ 4 workers-per-container ≈ 3.7 CPU-hours wall time per container
- 20 containers in parallel → ~15 min wall time
- 20 × `c6i.2xlarge` spot × 0.25 hr × $0.10/hr = **~$0.50**
- Merge: `m6i.xlarge` × 5 min × $0.19/hr = **~$0.02**
- S3 PUTs/GETs + CloudWatch: cents
- **Total: ~$0.60 per LEMON recompute**

### Per-recompute (Dortmund, 37ch, with `--source`)

- 608 subjects × ~120s × 2 conditions ÷ 4 workers ≈ 10 CPU-hours per container
- 30 containers (larger slice count) → ~20 min wall time
- **Total: ~$1.00 per Dortmund recompute**

### Idle / monthly

- S3 Standard for ~50 GB raw + outputs: ~$1–2/mo
- Batch control plane: free
- CloudWatch logs: cents at this volume
- **Steady state: ~$1–2/mo when idle**

### Cadence projection

At weekly recompute of both datasets: ~$8/mo compute + $2/mo storage = **~$10/mo**. Budget alert at $25/mo gives comfortable headroom.

## Reproducibility gate

The ticket requires cloud outputs to match local outputs on a 10-subject LEMON reference subset within a defined tolerance. Plan:

- **Per-subject checkpoints**: expect bit-identical match after pinning specparam RNG. Any drift indicates a numerical issue to investigate before merging.
- **Aggregated normative model**: expect bit-identical match because aggregation is order-independent and operates on the same (bit-identical) per-subject values.
- **Tolerance**: `atol=0` on checkpoint JSONs after RNG pinning. If any field drifts, fail the gate and investigate rather than relaxing tolerance.

The gate is verified by:

1. Local run on a 10-subject subset, archived as `tests/fixtures/reproducibility/lemon-10subj/`.
2. Cloud run with the same inputs and git SHA, outputs diffed field-by-field.
3. Assertion script in `tests/test_cloud_reproducibility.py` (optional manual test, not CI-blocking).

## Open decisions for the PR

1. **LEMON mirror vs direct FTP**: Mirror LEMON once to S3 for reliable, fast access from Batch workers. Alternative is pulling from GWDG FTP on every run — higher risk of rate-limit or transient failure.
2. **Slice size**: 11 subjects (220 ÷ 20) for LEMON feels right. Dortmund at 20 subjects (608 ÷ 30) slightly larger. Tune based on observed spot interruption frequency.
3. **Checkpoint-sync granularity**: sync after every subject (safer) vs every N subjects (cheaper). Default to every subject; revisit if S3 PUT costs show up.
4. **Region lock-in**: submission script warns if `aws.region != us-east-1` and the run includes Dortmund (avoids silent 20x egress cost from cross-region OpenNeuro reads).
5. **Budget alert threshold**: suggest $25/mo; ticket's initial suggestion was $50/mo. $25 is tighter and flags any runaway early.

## Clinical framework note

This is Tier 2 (clinical-supporting). The reproducibility gate keeps it from escalating to Tier 1. If pinning the specparam RNG is insufficient to achieve bit-identical outputs, escalate and file a follow-up for root-cause investigation before merging.
