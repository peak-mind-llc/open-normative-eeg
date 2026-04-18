#!/usr/bin/env python3
"""Submit a normative recompute to AWS Batch as an array job + merge job.

Reads aws-config.yaml for account-specific settings (bucket, queue, job
definitions), enumerates subjects via the dataset loader to size the
array, submits both jobs with a merge dependency, and optionally tails
CloudWatch logs until the merge job finishes.

Example:
    python scripts/cloud_recompute.py --dataset lemon --channels 37 \
        --source --ba-connectivity --dk-connectivity --slices 20 --follow

Pipeline changes are not made here; this submission layer only drives
what build_norms.py already does in a container. See docs/aws-deployment.md
for the full runbook.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    """Flattened view of aws-config.yaml."""
    profile: str | None
    region: str
    bucket: str
    runs_prefix: str
    mirrors_prefix: str
    job_queue: str
    array_jd: str
    merge_jd: str
    image: str
    workers_per_slice: int
    default_slices: int
    min_subjects_per_slice: int


def _load_config(path: Path) -> Config:
    import yaml  # deferred so --help works without PyYAML installed
    data = yaml.safe_load(path.read_text())
    try:
        return Config(
            profile=data["aws"].get("profile"),
            region=data["aws"]["region"],
            bucket=data["storage"]["bucket"],
            runs_prefix=data["storage"].get("runs_prefix", "runs/").rstrip("/") + "/",
            mirrors_prefix=data["storage"].get("mirrors_prefix", "mirrors/").rstrip("/") + "/",
            job_queue=data["compute"]["batch_job_queue"],
            array_jd=data["compute"]["batch_job_definition"],
            merge_jd=data["compute"]["batch_merge_job_definition"],
            image=data["compute"].get("image", ""),
            workers_per_slice=int(data["compute"].get("workers_per_slice", 4)),
            default_slices=int(data.get("slicing", {}).get("default_slices", 20)),
            min_subjects_per_slice=int(data.get("slicing", {}).get("min_subjects_per_slice", 5)),
        )
    except KeyError as exc:
        sys.exit(f"aws-config.yaml is missing required key: {exc}")


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True,
        ).strip()
        return out or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _make_run_id(dataset: str, channels: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{dataset}-{channels}ch-{stamp}"


def _count_eligible_subjects(dataset: str, data_dir: Path, channels: int, condition: str) -> int:
    """Enumerate subjects via the loader. Lightweight — no raw data read."""
    from open_normative.datasets import DATASETS
    loader = DATASETS[dataset]()
    loader.n_channels = channels
    conditions = {"eo", "ec"} if condition == "both" else {condition}
    count = 0
    for record in loader.iter_subject_files(data_dir):
        if record.condition in conditions:
            count += 1
    return count


def _compute_slicing(
    total: int,
    requested_slices: int | None,
    requested_per_slice: int | None,
    cfg: Config,
) -> tuple[int, int]:
    """Return (num_slices, per_slice). Per-slice size is ceil(total/slices).

    If ``requested_per_slice`` is set, it caps the total work: num_slices is
    derived as ceil(effective_total / per_slice) where effective_total is
    min(total, requested_slices * requested_per_slice) if slices is also set,
    else requested_per_slice itself (single slice). Useful for smoke tests.
    """
    if total <= 0:
        sys.exit("No eligible subjects found. Check --dataset and data-dir.")
    if requested_per_slice is not None:
        per_slice = max(1, requested_per_slice)
        slices = requested_slices or 1
        return slices, per_slice
    slices = requested_slices or cfg.default_slices
    # Don't over-slice a small dataset.
    max_sensible = max(1, total // max(cfg.min_subjects_per_slice, 1))
    slices = min(slices, max_sensible)
    slices = max(slices, 1)
    per_slice = (total + slices - 1) // slices
    return slices, per_slice


def _region_safety_warning(cfg: Config, dataset: str, force: bool) -> None:
    if dataset == "dortmund" and cfg.region != "us-east-1":
        msg = (
            f"⚠  Dortmund raw data lives in s3://openneuro.org (us-east-1). "
            f"Running jobs in {cfg.region} will incur cross-region egress "
            f"(~$0.02/GB × ~24 GB = ~$0.50 per run). "
        )
        if force:
            print(msg + "Proceeding because --confirm-cross-region was passed.", file=sys.stderr)
        else:
            sys.exit(
                msg + "Re-run with --confirm-cross-region to accept, or "
                f"apply the Terraform module with region=us-east-1."
            )


def _env_overrides(
    bucket: str,
    run_id: str,
    dataset: str,
    channels: int,
    condition: str,
    per_slice: int,
    workers: int,
    source_flags: str,
    data_mirror: str | None,
) -> list[dict[str, str]]:
    pairs = {
        "BUCKET": bucket,
        "RUN_ID": run_id,
        "DATASET": dataset,
        "CHANNELS": str(channels),
        "CONDITION": condition,
        "PER_SLICE": str(per_slice),
        "WORKERS": str(workers),
        "SOURCE_FLAGS": source_flags,
    }
    if data_mirror:
        pairs["DATA_MIRROR"] = data_mirror
    return [{"name": k, "value": v} for k, v in pairs.items()]


def _submit_array(
    batch: Any,
    cfg: Config,
    run_id: str,
    dataset: str,
    channels: int,
    condition: str,
    slices: int,
    per_slice: int,
    source_flags: str,
    data_mirror: str | None,
    git_sha: str,
) -> str:
    resp = batch.submit_job(
        jobName=f"{run_id}-array",
        jobQueue=cfg.job_queue,
        jobDefinition=cfg.array_jd,
        arrayProperties={"size": slices},
        containerOverrides={
            "environment": _env_overrides(
                cfg.bucket, run_id, dataset, channels, condition,
                per_slice, cfg.workers_per_slice, source_flags, data_mirror,
            ),
        },
        tags={"run_id": run_id, "git_sha": git_sha, "role": "array"},
    )
    return resp["jobId"]


def _submit_merge(
    batch: Any,
    cfg: Config,
    run_id: str,
    array_job_id: str,
    git_sha: str,
) -> str:
    run_prefix = f"s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}"
    # Override the container command to bypass batch_entrypoint.sh (which
    # expects AWS_BATCH_JOB_ARRAY_INDEX) and run build_norms.py --merge
    # directly. Syncs inputs and uploads outputs via aws CLI (already in image).
    command = [
        "bash", "-lc",
        "set -euo pipefail; "
        f"mkdir -p /work/subjects /work/out; "
        f"aws s3 sync {run_prefix}/subjects/ /work/subjects/ --no-progress; "
        f"python /app/scripts/build_norms.py --merge --merge-dir /work/subjects --output /work/out; "
        f"aws s3 sync /work/out/ {run_prefix}/out/ --no-progress; "
        f"echo MERGE_DONE",
    ]
    resp = batch.submit_job(
        jobName=f"{run_id}-merge",
        jobQueue=cfg.job_queue,
        jobDefinition=cfg.merge_jd,
        dependsOn=[{"jobId": array_job_id, "type": "SEQUENTIAL"}],
        containerOverrides={"command": command},
        tags={"run_id": run_id, "git_sha": git_sha, "role": "merge"},
    )
    return resp["jobId"]


def _wait_for_job(batch: Any, logs: Any, job_id: str, label: str) -> str:
    """Poll until the job reaches a terminal state; print status transitions. Returns final status."""
    last = None
    while True:
        resp = batch.describe_jobs(jobs=[job_id])
        jobs = resp.get("jobs", [])
        if not jobs:
            print(f"[{label}] describe_jobs returned nothing for {job_id}; waiting...", file=sys.stderr)
            time.sleep(10)
            continue
        job = jobs[0]
        status = job.get("status")
        if status != last:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {label}: {status}")
            last = status
        if status in ("SUCCEEDED", "FAILED"):
            if status == "FAILED":
                print(f"[{label}] failure reason: {job.get('statusReason', 'unknown')}", file=sys.stderr)
            return status
        time.sleep(15)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, default=REPO_ROOT / "aws-config.yaml",
                    help="Path to aws-config.yaml (default: repo root)")
    ap.add_argument("--dataset", required=True, help="Dataset key (lemon, dortmund, ...)")
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="Local data dir for enumerating subjects. Defaults to "
                         "~/Data/EEG/<DATASET>. Used only for slice sizing.")
    ap.add_argument("--channels", type=int, choices=[19, 37], default=19)
    ap.add_argument("--condition", choices=["eo", "ec", "both"], default="both")
    ap.add_argument("--source", action="store_true")
    ap.add_argument("--ba-connectivity", action="store_true")
    ap.add_argument("--dk-connectivity", action="store_true")
    ap.add_argument("--skip-connectivity", action="store_true")
    ap.add_argument("--save-psd", action="store_true")
    ap.add_argument("--slices", type=int, default=None,
                    help=f"Number of array elements. Default from aws-config.yaml.")
    ap.add_argument("--per-slice", type=int, default=None,
                    help="Explicit subjects-per-slice. Overrides slice-size math. "
                         "Useful for smoke tests: --slices 1 --per-slice 2 runs one "
                         "container on 2 subjects total.")
    ap.add_argument("--data-mirror", default=None,
                    help="Optional s3:// URI for staged raw data (LEMON). "
                         "Defaults to s3://<bucket>/mirrors/<dataset>/ if present.")
    ap.add_argument("--confirm-cross-region", action="store_true",
                    help="Acknowledge that a non-us-east-1 region will incur "
                         "cross-region egress for Dortmund (OpenNeuro) reads.")
    ap.add_argument("--follow", action="store_true",
                    help="Tail job status until the merge job terminates.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be submitted and exit.")
    args = ap.parse_args()

    try:
        import boto3  # noqa: F401
    except ImportError:
        sys.exit("boto3 is required: pip install 'open-normative-eeg[aws]'")

    if not args.config.exists():
        sys.exit(
            f"Config not found: {args.config}\n"
            f"Copy aws-config.example.yaml to aws-config.yaml and edit."
        )
    cfg = _load_config(args.config)
    _region_safety_warning(cfg, args.dataset, args.confirm_cross_region)

    data_dir = args.data_dir or Path.home() / "Data" / "EEG" / args.dataset.upper()
    if not data_dir.exists():
        sys.exit(
            f"Data dir not found: {data_dir}\n"
            f"Slice sizing reads the local dataset to enumerate subjects. "
            f"Pass --data-dir if your local copy lives elsewhere."
        )
    total = _count_eligible_subjects(args.dataset, data_dir, args.channels, args.condition)
    slices, per_slice = _compute_slicing(total, args.slices, args.per_slice, cfg)

    run_id = _make_run_id(args.dataset, args.channels)
    git_sha = _git_sha()

    source_flags_parts = []
    if args.source:
        source_flags_parts.append("--source")
    if args.ba_connectivity:
        source_flags_parts.append("--ba-connectivity")
    if args.dk_connectivity:
        source_flags_parts.append("--dk-connectivity")
    if args.skip_connectivity:
        source_flags_parts.append("--skip-connectivity")
    if args.save_psd:
        source_flags_parts.append("--save-psd")
    source_flags = " ".join(source_flags_parts)

    # Default mirror URI when the bucket has a staged copy of the dataset.
    data_mirror = args.data_mirror
    if data_mirror is None and args.dataset == "lemon":
        data_mirror = f"s3://{cfg.bucket}/{cfg.mirrors_prefix}lemon/"

    print(f"run_id          : {run_id}")
    print(f"git_sha         : {git_sha}")
    print(f"subjects total  : {total} ({args.condition})")
    print(f"slices          : {slices}  × per_slice={per_slice}")
    print(f"source flags    : {source_flags or '<none>'}")
    print(f"data mirror     : {data_mirror or '<loader downloads>'}")
    print(f"queue / JDs     : {cfg.job_queue} / {cfg.array_jd} / {cfg.merge_jd}")
    print(f"region          : {cfg.region}")

    if args.dry_run:
        print("(--dry-run; not submitting)")
        return 0

    session = boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
    batch = session.client("batch")
    logs = session.client("logs")

    # Sanity: confirm the job queue and JDs exist and are ENABLED before submitting.
    q = batch.describe_job_queues(jobQueues=[cfg.job_queue]).get("jobQueues", [])
    if not q or q[0].get("state") != "ENABLED":
        sys.exit(f"Job queue {cfg.job_queue!r} not found or not ENABLED. Apply Terraform first.")

    array_id = _submit_array(
        batch, cfg, run_id, args.dataset, args.channels, args.condition,
        slices, per_slice, source_flags, data_mirror, git_sha,
    )
    print(f"submitted array job : {array_id}")

    merge_id = _submit_merge(batch, cfg, run_id, array_id, git_sha)
    print(f"submitted merge job : {merge_id}")

    print(
        f"\nTo view progress:\n"
        f"  aws --profile {cfg.profile or '<default>'} --region {cfg.region} batch describe-jobs --jobs {array_id} {merge_id}\n"
        f"  aws --profile {cfg.profile or '<default>'} --region {cfg.region} logs tail /aws/batch/norm-recompute --follow\n"
        f"Outputs will appear at:\n"
        f"  s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/out/"
    )

    if args.follow:
        status = _wait_for_job(batch, logs, array_id, "array")
        if status != "SUCCEEDED":
            return 1
        status = _wait_for_job(batch, logs, merge_id, "merge")
        if status != "SUCCEEDED":
            return 1
        print(f"\n✓ Run complete: s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/out/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
