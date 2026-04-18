# open_cloud_run — generic AWS Batch array-job SDK

A small, opinion-light framework for running per-unit work on AWS Batch. It handles enumeration, slicing, submission, observability, and output sync. **Everything experiment-specific stays in your code.**

The framework never imports EEG libraries, dataset loaders, or analysis helpers. It knows about: array jobs, S3, environment variables, shell commands. Whatever your "unit of work" is — a subject, a session, a hyperparameter combo, a filename — the framework doesn't care. Your enumeration prints strings; your driver reads a string; you're done.

This SDK is shipped from the `open-normative-eeg` repo as a sibling package (`open_cloud_run/`). It's installable standalone via `pip install -e ".[cloud-run]"` and reusable across research projects.

---

## Contents

1. [The three contracts](#the-three-contracts)
2. [Quick start](#quick-start)
3. [A worked example: hyperparameter sweep](#a-worked-example-hyperparameter-sweep)
4. [CLI reference](#cli-reference)
5. [Python API reference](#python-api-reference)
6. [How runs are persisted](#how-runs-are-persisted)
7. [What the framework does NOT assume](#what-the-framework-does-not-assume)
8. [Container setup for your experiment](#container-setup-for-your-experiment)
9. [Picking this up in a new session](#picking-this-up-in-a-new-session)

---

## The three contracts

Three small contracts define the framework's entire surface area. Everything else is experiment-level.

### The enumerator contract

A shell command you run on your laptop. Prints one work unit ID per line to stdout.

- **Exit 0** on success, nonzero means enumeration failed and the framework aborts submission.
- **Blank lines** and lines starting with `#` are ignored.
- **Unit IDs are arbitrary strings.** `sub-001`, `sub-001|ses-2`, `seed=42|k=25`, `dataset=lemon:subject=sub-010002`. Your experiment's convention, your choice.
- Runs on your laptop. Cheap. Allowed to fail; no cloud resources committed yet.

### The driver contract

A shell command invoked once per unit inside the container. Before invoking the driver the framework sets these environment variables:

| Variable | What it is |
|---|---|
| `UNIT` | The unit ID string from the enumerator. The driver parses it however makes sense for its experiment. |
| `OUT_DIR` | An absolute path (under `/work/out/<UNIT>/`) the driver should write outputs into. Pre-created for you. |
| `RUN_ID` | The cloud run identifier. Rarely used by drivers; available for logging / provenance. |
| `BUCKET` | The S3 bucket for this run. Useful if the driver wants to do its own mid-unit uploads. |
| `SLICE_INDEX` | Which array element this is. Rarely used. |

The driver must:

1. **Exit 0 on success, nonzero on failure.** That's the only "is this unit done" signal the framework reads.
2. **Write outputs under `$OUT_DIR`.** Any files, any format. The framework syncs `$OUT_DIR` wholesale to `s3://$BUCKET/runs/$RUN_ID/out/$UNIT/` at slice end.
3. **Be idempotent per unit.** On Spot preemption, the container restarts and replays the slice. Typical idempotency check (3 lines):

   ```python
   expected = Path(os.environ["OUT_DIR"]) / "result.json"
   if expected.exists():
       sys.exit(99)   # convention: exit 99 = "already done, skip"
   ```

   Exit 99 is logged as "skipped" instead of "ok"; any other nonzero exit is a failure.

4. **Not know it's on Batch.** No framework imports. The driver runs identically on your laptop if you set `UNIT` and `OUT_DIR` manually.

The driver is **not** expected to:

- Talk to S3 (unless it wants to).
- Handle spot retries or array sharding.
- Know about other drivers.
- Follow any specific output schema. Drop a JSON, a pickle, an `.npz`, an image — whatever the experiment needs.

### The merge contract (optional)

If your experiment has an aggregation step, provide a merge command. It runs in a separate on-demand container after all array elements succeed.

Environment variables:

| Variable | What it is |
|---|---|
| `INPUTS_DIR` | Local path containing all per-unit `$OUT_DIR`s from the run, synced down from S3. |
| `MERGE_OUT` | Local path to write aggregated outputs; synced up to `s3://$BUCKET/runs/$RUN_ID/out_merged/`. |
| `RUN_ID`, `BUCKET` | Same as the array mode. |

Same exit code and stdout semantics as the driver. Omit `--merge` on submission and the merge step is simply skipped.

---

## Quick start

```bash
# Install (from the open-normative-eeg repo)
pip install -e '.[cloud-run]'

# Confirm CLI is on path
open-cloud-run --help

# Or as a module
python -m open_cloud_run --help
```

You need an `aws-config.yaml` pointing at your S3 bucket, Batch queue, and JDs. Terraform from `infra/aws/` generates these values.

Minimum `aws-config.yaml`:

```yaml
aws:
  region: us-east-1
  profile: my-profile           # or null to use env/default
storage:
  bucket: my-runs-bucket
  runs_prefix: runs/
compute:
  batch_job_queue: norm-recompute-queue
  batch_job_definition: generic-jd
  batch_merge_job_definition: generic-jd    # same JD, different MODE env
  image: ghcr.io/my-org/my-experiment:latest
slicing:
  default_slices: 10
  min_units_per_slice: 2
```

Submit a run:

```bash
open-cloud-run submit \
  --name my-experiment \
  --enumerate "python scripts/enumerate.py" \
  --driver    "python scripts/driver.py" \
  --merge     "python scripts/merge.py"     # optional
```

Track / retrieve:

```bash
open-cloud-run list
open-cloud-run status my-experiment-20260418T153000Z
open-cloud-run logs   my-experiment-20260418T153000Z --follow
open-cloud-run download my-experiment-20260418T153000Z
```

---

## A worked example: hyperparameter sweep

Say you want to sweep LEiDA k ∈ {15, 20, 25, 30, 50} across 50 subjects = 250 units. No existing framework code is modified. The entire experiment is ~65 lines of code.

**`scripts/sweep_enumerate.py`** (~20 lines):

```python
#!/usr/bin/env python3
"""Enumerate (subject, k) pairs for the LEiDA k-sweep."""
SUBJECTS = [f"sub-{i:03d}" for i in range(50)]
K_VALUES = [15, 20, 25, 30, 50]

for k in K_VALUES:
    for s in SUBJECTS:
        print(f"{s}|k={k}")
```

**`scripts/sweep_driver.py`** (~40 lines):

```python
#!/usr/bin/env python3
"""Run LEiDA on one (subject, k) pair. Reads UNIT + OUT_DIR env vars."""
import os, sys, json
from pathlib import Path
from my_lab.leida import compute_leida_landscape   # your research code

unit = os.environ["UNIT"]
out_dir = Path(os.environ["OUT_DIR"])

# Parse unit — your convention
subject, k_str = unit.split("|")
k = int(k_str.split("=")[1])

# Idempotency
result_path = out_dir / "result.json"
if result_path.exists():
    sys.exit(99)

# Do the work
result = compute_leida_landscape(subject=subject, k_clusters=k)
out_dir.mkdir(parents=True, exist_ok=True)
result_path.write_text(json.dumps(result))
```

**`scripts/sweep_merge.py`** (~15 lines, optional):

```python
#!/usr/bin/env python3
"""Aggregate per-unit results into a sweep summary."""
import os, json
from pathlib import Path

inputs = Path(os.environ["INPUTS_DIR"])
merge_out = Path(os.environ["MERGE_OUT"])
merge_out.mkdir(parents=True, exist_ok=True)

rows = []
for unit_dir in sorted(inputs.iterdir()):
    if not unit_dir.is_dir():
        continue
    p = unit_dir / "result.json"
    if p.exists():
        rows.append({"unit": unit_dir.name, **json.loads(p.read_text())})

(merge_out / "sweep.json").write_text(json.dumps(rows))
```

**Submit:**

```bash
open-cloud-run submit \
  --name leida-k-sweep \
  --enumerate "python scripts/sweep_enumerate.py" \
  --driver    "python scripts/sweep_driver.py" \
  --merge     "python scripts/sweep_merge.py" \
  --slices 25
```

Adds up to 250 units ÷ 25 slices = 10 units per container. With ~2 min/unit, each container runs for 20 min. Parallel across 25 containers → ~20 min wall time.

That's the whole experiment. No framework modifications. The sweep scripts don't import from the framework. They would run identically on a laptop with `UNIT=sub-001|k=25 OUT_DIR=/tmp/out python scripts/sweep_driver.py`.

---

## CLI reference

All subcommands take `--config PATH` (defaults to `./aws-config.yaml`).

### `submit`

```
--enumerate CMD       Shell command printing one unit per stdout line  [required]
--driver CMD          Shell command run per unit inside the container  [required]
--merge CMD           Optional shell command run after all units succeed
--image URI           Container image; overrides config compute.image
--outputs PATH        Driver's OUT_DIR inside container (default: /work/out)
--slices N            Number of array elements (default from config)
--per-slice N         Units per slice (overrides --slices math)
--name PREFIX         Run-id prefix (recommended: your experiment name)
--tag KEY=VALUE       Extra tag (repeatable)
--enumerate-cwd DIR   Directory the enumerator runs in
--dry-run             Print what would be submitted and exit
```

Output: the generated `run_id`, array + merge job IDs, and the S3 output URI.

### `status [run_id]`

With a `run_id`: prints array/merge status with array child counts.

Without: shows the N most recent runs (`--limit`, default 5).

### `logs run_id [--follow]`

Tails CloudWatch logs, merging events from the array parent, all array children, and the merge job. `--log-group` overrides the default.

### `download run_id [--output DIR] [--include-subjects]`

Runs `aws s3 sync` on the run's `out/` prefix. `--include-subjects` also syncs per-unit outputs (useful when the merged `out_merged/` is a summary and per-unit provenance matters).

### `list [--limit N] [--json]`

Lists recent runs from the bucket, most recent first.

---

## Python API reference

Library surface is small:

```python
from open_cloud_run import (
    Config,            # Config.load(path) → Config
    Manifest,          # submission manifest, roundtrips to/from JSON
    submit_run,        # submit an array + optional merge
    get_status,        # run status via manifest + batch describe
    format_status,     # pretty-print a RunStatus
    get_logs,          # tail CloudWatch
    download_outputs,  # aws s3 sync wrapper
    list_runs,         # list runs in a bucket
    enumerate_units,   # run a shell command and parse stdout
)
```

`submit_run` is the main entry point:

```python
cfg = Config.load("aws-config.yaml")
run = submit_run(
    cfg,
    enumerate_cmd="python scripts/enumerate.py",
    driver_cmd="python scripts/driver.py",
    merge_cmd="python scripts/merge.py",          # optional
    image="ghcr.io/my-org/exp:latest",            # or None to use cfg.default_image
    slices=10,
    per_slice=None,
    run_id_prefix="my-experiment",
    tags={"pi": "james"},
)
# run.run_id, run.array_job_id, run.merge_job_id, run.outputs_s3_uri
```

Takes a `batch_client` kwarg for injecting a fake in tests (see `tests/test_open_cloud_run.py`).

---

## How runs are persisted

Each run has exactly two S3 artifacts written at submission time:

1. **Submission manifest**: `s3://$BUCKET/$runs_prefix<run_id>/_submission.json`
   — JSON with run_id, timestamp, image, enumerate/driver/merge commands, array+merge job IDs, slice shape, git SHA (if available), and tags. The `status/logs/download/list` subcommands read this to find the jobs.

2. **Per-slice manifests**: `s3://$BUCKET/$runs_prefix<run_id>/slices/<N>/manifest.txt`
   — plain text, one unit per line, for array element N. The container pulls its own manifest at startup.

During/after the run:

- **Per-unit outputs**: `s3://$BUCKET/$runs_prefix<run_id>/out/<UNIT>/...`
- **Merged outputs** (if merge ran): `s3://$BUCKET/$runs_prefix<run_id>/out_merged/...`

S3 is the source of truth for every run; there's no database or control-plane service to maintain.

---

## What the framework does NOT assume

Explicit list so your next experiment doesn't fight hidden defaults:

- **Not** that a unit is a subject. Could be `(subject, session, seed)`, a seed-only unit for a reproducibility sweep, or a filename glob.
- **Not** that outputs are JSON. Any file shape is fine; the framework treats `$OUT_DIR` as opaque.
- **Not** a specific folder layout inside `$OUT_DIR`. One file, many files, subdirectories — all fine.
- **Not** that the driver calls back into the framework. It doesn't. No `--checkpoint-sync` required; the framework does slice-end sync for you.
- **Not** that there's a merge step. Omit `--merge` and it's skipped entirely.
- **Not** a particular Python version, base image, or dependency set. The container image is yours. The framework only requires the aws CLI inside the container (so the entrypoint can `aws s3 sync`).
- **Not** bit-identical reproducibility. The entrypoint sets `OMP_NUM_THREADS=1` etc. by default, which helps for many numeric pipelines. Override with `BLAS_THREADS=N` env if your workload needs threads.

---

## Container setup for your experiment

Two options for your experiment's Docker image.

### Option A: use the framework entrypoint (recommended)

Copy (or vendor) the framework's `entrypoint.sh`, place in your image, and set it as `ENTRYPOINT`. Your `Dockerfile`:

```dockerfile
FROM python:3.10-slim-bookworm

# system deps for your experiment
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# AWS CLI v2 (framework entrypoint uses it)
RUN ARCH=$(dpkg --print-architecture) \
 && case "$ARCH" in amd64) A=x86_64 ;; arm64) A=aarch64 ;; esac \
 && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${A}.zip" -o /tmp/aws.zip \
 && unzip -q /tmp/aws.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/aws.zip

WORKDIR /app

# your deps
COPY requirements-pinned.txt .
RUN pip install -r requirements-pinned.txt

# your code
COPY . /app

# vendored framework entrypoint
COPY vendored/open_cloud_run/container/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

Vendoring is trivially small; we don't distribute a base image on purpose.

### Option B: roll your own entrypoint

If you want more control (e.g. GPU setup, specific FUSE mounts, different BLAS handling), write your own entrypoint. The contract you need to honor:

- On `MODE=array`, read `s3://$BUCKET/$RUNS_PREFIX$RUN_ID/slices/$AWS_BATCH_JOB_ARRAY_INDEX/manifest.txt`; loop each non-empty line; for each set `UNIT`, create `$OUT_DIR/$UNIT/`, run `$DRIVER_CMD`; at end sync `$OUT_DIR/` to `s3://$BUCKET/$RUNS_PREFIX$RUN_ID/out/`.
- On `MODE=merge`, sync `out/` down, run `$MERGE_CMD` with `INPUTS_DIR` + `MERGE_OUT` set, sync `$MERGE_OUT` to `out_merged/`.

The bundled entrypoint is ~120 lines; read it as the reference.

### Batch job definition

A single job definition works for both array and merge modes if you define it generically (no hardcoded command). Terraform:

```hcl
resource "aws_batch_job_definition" "generic" {
  name                  = "generic-jd"
  type                  = "container"
  platform_capabilities = ["EC2"]

  retry_strategy {
    attempts = 5
    evaluate_on_exit { on_status_reason = "Host EC2*" action = "RETRY" }
    evaluate_on_exit { on_reason        = "*"         action = "EXIT"  }
  }

  container_properties = jsonencode({
    image      = var.default_image   # overridden per-submission
    vcpus      = 8
    memory     = 14336
    jobRoleArn = aws_iam_role.job.arn
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.jobs.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "generic"
      }
    }
  })
  timeout { attempt_duration_seconds = 7200 }
}
```

---

## Picking this up in a new session

If you (or a future Claude session) are adopting this framework for a new experiment:

1. **Read this doc and the driver contract first**, then skim `tests/test_open_cloud_run.py` to see the invariants.
2. **Check the infra exists**: `terraform output` in `infra/aws/` of `open-normative-eeg`. You should see a bucket, a queue, a generic JD. Reuse them.
3. **Write three scripts** in your experiment's repo: `enumerate.py`, `driver.py`, optionally `merge.py`. Each is a standalone executable that reads env vars and exits with a status code. No framework imports.
4. **Build your image** following Option A or B above. Publish to GHCR via a GitHub Action (copy the workflow from `open-normative-eeg/.github/workflows/publish-image.yml`).
5. **Write a minimal `aws-config.yaml`** pointing at the shared infra + your image.
6. **Smoke test with 2 units** and `--follow`. Confirm outputs land.
7. **Add a per-experiment README** describing the unit ID format and what's in `out/`.

### Things that will bite you (so future-you doesn't repeat today's bugs)

- **Array jobs need size ≥ 2.** If the enumerator produces 1 unit, Batch refuses. The framework catches this and raises `ValueError`.
- **GHCR packages default to private.** Flip to public (or add pull creds to Batch) after first publish.
- **BLAS threads are pinned by default.** If your workload genuinely needs multi-threaded linalg and you've accepted the cross-machine reproducibility cost, set `BLAS_THREADS=<N>` as a containerOverrides env var on submission.
- **`containerOverrides.command` does NOT replace ENTRYPOINT.** We rely on this — the framework's entrypoint stays in control, and the driver runs inside it via env vars.
- **Merge runs on the same compute environment** unless you create a separate merge JD pointing at an on-demand env. For small merges the shared spot env is fine; for long merges, consider separating.

---

## Pointers

- `open_cloud_run/` — the package.
- `tests/test_open_cloud_run.py` — unit tests with moto-backed S3. Read these for usage patterns.
- `open_cloud_run/container/entrypoint.sh` — the generic container entrypoint. Vendor into your image.
- `infra/aws/` — shared Terraform; the bucket, queue, JDs this SDK submits against.
- `docs/aws-deployment.md` — the production runbook for the norm-recompute use-case. A useful end-to-end example.
- `docs/adapting-for-new-experiments.md` — earlier sketch, superseded by this document. Keep only as historical reference.
