# Adapting the AWS Batch Framework for New Experiments

The infrastructure we built for normative recomputation is a generic
"split CPU-bound work into array jobs on EC2 Spot, checkpoint per unit
to S3, track via S3 manifests" framework. Normative recompute is one
instance. ERP analyses, TMS-EEG pipelines, and any other per-subject
driver script fits the same mould.

This guide is how to onboard a new experiment onto the shared infra
**without refactoring the framework itself**. A full abstraction layer
can come later if you run three or more experiments and the copy-paste
gets annoying; until then, forking is faster than generalizing.

## What you reuse as-is

| Resource | Shared across experiments |
|---|---|
| Terraform module (`infra/aws/`) | Same bucket, compute env, queue, IAM, log group, budget. |
| S3 bucket | Each experiment lives under a separate prefix (e.g. `runs/p300/...`). |
| Batch compute environment + queue | Capacity-optimized Spot, scales to zero. |
| `_submission.json` manifest convention | Status/logs/download subcommands work across experiments. |
| BLAS thread pinning / reproducibility story | Applies to any numeric Python work. |
| GH Actions image publish pattern | One workflow per experiment, publishing to GHCR. |

## What you duplicate (and tailor)

For each new experiment:

1. **A driver script** that processes one unit of work (one subject, one session, one condition — whatever the natural unit is for that experiment).
2. **A container image** with the experiment's Python dependencies pinned.
3. **An entrypoint script** that maps `AWS_BATCH_JOB_ARRAY_INDEX` to the range of units the container should process.
4. **An orchestrator CLI** that enumerates units, slices, submits jobs, writes a manifest.
5. **A Batch job definition** pointing at the experiment's image.

Each is ~50-200 lines of code, almost all of it structurally identical to what's in `scripts/build_norms.py`, `scripts/batch_entrypoint.sh`, `scripts/cloud_recompute.py`, and `infra/aws/main.tf`.

## Step-by-step: adding a new experiment

### 1. Make your driver script resumable

Most experiment drivers already have three things:

- `enumerate_units()` — returns the list of work units (subject IDs, session IDs, etc.).
- `process_one(unit_id)` — runs the analysis for one unit.
- Some aggregation / reporting step.

You need to add one flag and one hook.

**Add a `--unit-range START:END` flag.** The container entrypoint will pass it. In the normative pipeline this is `--subject-range` in `scripts/build_norms.py:492-498`:

```python
parser.add_argument(
    "--unit-range",
    type=str,
    default=None,
    help="Process units[START:END). 0-based, exclusive end.",
)
```

**Add a `--checkpoint-sync s3://bucket/prefix/` flag.** After each unit completes, upload its output file(s) to S3. Copy the pattern from `scripts/build_norms.py:166-207` — it's a tiny boto3 helper that logs warnings on failure but never crashes the pool.

**Guarantee resume**: on startup, scan the local output directory (or pull prior checkpoints from S3 first) and skip any unit whose output already exists. The existing `load_checkpoints()` pattern in `build_norms.py:222-236` is drop-in reusable.

### 2. Write a Dockerfile

Fork `Dockerfile` from the root of this repo. Typical changes:

- Swap `requirements-pinned.txt` for your experiment's pinned deps.
- Swap the `COPY open_normative /app/open_normative` / `COPY scripts /app/scripts` lines for your experiment's package layout.
- Keep the BLAS thread pinning ENV vars — they apply to any numeric Python.
- Point `ENTRYPOINT` at your experiment's entrypoint script (see next step).

### 3. Write the entrypoint script

Fork `scripts/batch_entrypoint.sh`. The `MODE=array|merge` switch and the env var contract are reusable; swap the actual Python invocation.

Minimal example for a per-subject ERP pipeline:

```bash
#!/usr/bin/env bash
set -euo pipefail
MODE="${MODE:-array}"
: "${BUCKET:?}"; : "${RUN_ID:?}"

case "$MODE" in
  array)
    : "${PER_SLICE:?}"; : "${AWS_BATCH_JOB_ARRAY_INDEX:?}"
    START=$((AWS_BATCH_JOB_ARRAY_INDEX * PER_SLICE))
    END=$(((AWS_BATCH_JOB_ARRAY_INDEX + 1) * PER_SLICE))

    # Resume any prior checkpoints
    aws s3 sync "s3://${BUCKET}/runs/${RUN_ID}/units/" /work/units/ --no-progress || true

    # Pull only the units this slice needs — each ~40MB for ERP data
    # (see PR E in open-normative-eeg for the full per-subject-sync pattern)
    for i in $(seq $START $((END - 1))); do
        # look up unit id from a manifest file written by the orchestrator
        UNIT=$(sed -n "$((i + 1))p" /work/manifest.txt)
        aws s3 sync "s3://${DATA_SOURCE}/${UNIT}" /work/data/${UNIT} --no-progress
    done

    python /app/drivers/analyze.py /work/data \
        --unit-range "${START}:${END}" \
        --output /work \
        --checkpoint-sync "s3://${BUCKET}/runs/${RUN_ID}/"
    ;;
  merge)
    aws s3 sync "s3://${BUCKET}/runs/${RUN_ID}/units/" /work/units/ --no-progress
    python /app/drivers/combine.py /work/units /work/out
    aws s3 sync /work/out/ "s3://${BUCKET}/runs/${RUN_ID}/out/" --no-progress
    ;;
  *)
    echo "Unknown MODE=${MODE}" >&2; exit 1 ;;
esac
```

If the experiment has no merge step, drop that branch.

### 4. Fork `cloud_recompute.py`

Copy `scripts/cloud_recompute.py` to the new experiment's repo (or add a sibling like `scripts/cloud_p300.py` in this repo if it's close enough). What needs to change:

| Function | What to adapt |
|---|---|
| `_count_eligible_subjects()` | Replace with your experiment's unit enumeration (dataset loader, database query, CSV scan, etc.). |
| `_array_env()` | Swap the env vars to match your entrypoint (DATASET, CHANNELS etc. → your fields). |
| `_submit_merge()` | Drop this if no merge step. |
| `cmd_submit()` argparse | Remove flags that don't apply (--ba-connectivity, --dk-connectivity, etc.). Add experiment-specific flags. |
| Default `run_id` format | Pick a naming convention (e.g. `p300-20260418T...`). |

Everything else — subcommands `status`, `logs`, `download`, `list`, the `_submission.json` manifest write/read, the subcommand CLI plumbing — works unchanged.

### 5. Add a Batch job definition in Terraform

Add to `infra/aws/main.tf` (or a new `infra/aws/experiments/p300.tf`):

```hcl
resource "aws_batch_job_definition" "p300_array_worker" {
  name                  = "p300-jd"
  type                  = "container"
  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 5
    evaluate_on_exit {
      on_status_reason = "Host EC2*"
      action           = "RETRY"
    }
    evaluate_on_exit { on_reason = "*" action = "EXIT" }
  }

  container_properties = jsonencode({
    image            = var.p300_image   # e.g. ghcr.io/peak-mind-llc/p300-oddball:latest
    vcpus            = 8
    memory           = 14336
    jobRoleArn       = aws_iam_role.job.arn   # reuse the shared job role
    environment      = local.common_container_env   # reuse BLAS pins
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.jobs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "p300-array"
      }
    }
  })
  timeout { attempt_duration_seconds = 7200 }
}
```

Add similar for merge if you have one. Output the JD name so you can paste it into the experiment's own `aws-config.yaml`.

### 6. Set up the GHCR publish workflow

Fork `.github/workflows/publish-image.yml` to the experiment's repo. The only changes are the `images:` tag in the metadata step and the trigger paths.

### 7. Point the orchestrator at the new job definition

Each experiment gets its own `aws-config.yaml` (or one shared file with per-experiment sections). The orchestrator looks up `batch_job_definition` from the config — point it at the new JD.

If you want one shared bucket + one shared config with multiple experiments, add a top-level key:

```yaml
experiments:
  norm:
    batch_job_definition: norm-recompute-jd
    batch_merge_job_definition: norm-recompute-merge-jd
  p300:
    batch_job_definition: p300-jd
    batch_merge_job_definition: null
```

And pass `--experiment p300` on the CLI. At that point you've half-built a generic framework — this is the signal to pull out `open_cloud_run` as a shared package.

## IAM considerations

The shared `norm-recompute-job` role grants:
- `s3:GetObject/PutObject/DeleteObject/ListBucket` on the run bucket
- Public read on OpenNeuro (`openneuro.org`) and AWS Open Data (`fcp-indi`) buckets
- CloudWatch logs write

For most EEG/ERP experiments this is sufficient. If your experiment needs:
- **A different source bucket** (say private lab S3): add a statement to the inline policy.
- **A different log group**: create a new one in Terraform and grant writes.
- **A database** (RDS, DynamoDB): add the relevant actions to the role.

The role is a single point of change — don't fork it per experiment unless scopes really diverge.

## What to definitely **not** duplicate

- **Terraform module** — reuse it. One S3 bucket, one compute env, one queue, one IAM role, one log group, one budget. Splitting these per experiment is a nightmare.
- **Docker base layer** — if two experiments share MNE/scipy/numpy pins, let them share a base image.
- **`_submission.json` schema** — keep every experiment using the same fields (`run_id`, `submitted_at`, `array_job_id`, `merge_job_id`, etc.) so the `status/logs/download/list` subcommands work universally.
- **Run ID format** — stick to `<experiment>-<params>-<ISO8601>` so lexicographic sort gives most-recent-first.

## When to stop forking and build a real framework

Heuristics:
- You're about to onboard your **third** experiment.
- Two existing experiments have drifted — a bug fix to one should apply to the other but doesn't automatically.
- The per-experiment orchestrator is >500 lines AND ~80% of it is copied from another.

At that point, extract an `open_cloud_run` package that takes a `cloud-config.yaml` per experiment and exposes `submit/status/logs/download/list` generically. See the sketch in the architecture section of the chat log or ask for a fresh design.

## Checklist for a new experiment

- [ ] Driver has `--unit-range START:END` and `--checkpoint-sync s3://...` flags, both wired to resume correctly.
- [ ] Dockerfile builds locally; `pip install -r requirements-pinned.txt` is reproducible.
- [ ] Entrypoint's MODE switch works (test with env vars locally: `MODE=array AWS_BATCH_JOB_ARRAY_INDEX=0 BUCKET=... ./entrypoint.sh`).
- [ ] Terraform job definition(s) apply cleanly.
- [ ] GHCR workflow publishes successfully on a dummy push.
- [ ] `cloud_<experiment>.py submit` dry-runs correctly.
- [ ] End-to-end 2-unit smoke test reaches SUCCEEDED.
- [ ] `_submission.json` written so status/logs/download work.
- [ ] Documented in the experiment's README with the same "one-time setup / daily use" sections as this repo.
