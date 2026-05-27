#!/usr/bin/env python3
"""Orchestrator for normative recomputes on AWS Batch.

Subcommands:
    submit      Submit a new array+merge recompute run
    status      Show array+merge status for a run (or all recent runs)
    logs        Tail CloudWatch logs for a run
    download    Sync run outputs to a local directory
    list        List recent runs in the S3 bucket

Example:
    python scripts/cloud_recompute.py submit \\
        --dataset lemon --channels 37 --source \\
        --slices 20 --follow

    python scripts/cloud_recompute.py status lemon-37ch-20260418T143459Z
    python scripts/cloud_recompute.py logs   lemon-37ch-20260418T143459Z --follow
    python scripts/cloud_recompute.py download lemon-37ch-20260418T143459Z

Reads aws-config.yaml for account-specific settings. Credentials come
from the standard AWS SDK chain. See docs/aws-deployment.md.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# OpenNeuro datasets that can be streamed directly from s3://openneuro.org
# (us-east-1 public bucket). The job role policy in infra/aws/main.tf grants
# read access. HBN is intentionally absent: it's split across 11 release
# subdirectories on s3://fcp-indi/, so it needs a dedicated --data-mirror
# pointing at one release at a time.
_OPENNEURO_DATASETS = {
    "dortmund": "ds005385",
    "srm":      "ds003775",
    "trt":      "ds004148",
    "depress":  "ds003478",
}


# ─── Config ──────────────────────────────────────────────────────────────

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
    if not path.exists():
        sys.exit(
            f"Config not found: {path}\n"
            f"Copy aws-config.example.yaml to aws-config.yaml and edit."
        )
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


def _require_boto3():
    try:
        import boto3  # noqa: F401
    except ImportError:
        sys.exit("boto3 is required: pip install 'open-normative-eeg[aws]'")


def _session(cfg: Config):
    import boto3
    return boto3.Session(profile_name=cfg.profile, region_name=cfg.region)


# ─── Helpers shared across subcommands ───────────────────────────────────

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


def _resolve_run_id(args) -> str:
    """Use an explicit --run-id if given, else an auto timestamped id."""
    return getattr(args, "run_id", None) or _make_run_id(args.dataset, args.channels)


def _job_name(run_id: str, suffix: str) -> str:
    """AWS Batch job names allow only [A-Za-z0-9_-] (<=128 chars). run_ids may
    contain other chars — e.g. a release version like v0.2.0 has dots — so
    sanitize for the job name while leaving run_id (the S3 prefix) untouched."""
    return re.sub(r"[^A-Za-z0-9_-]", "-", f"{run_id}-{suffix}")[:128]


def _stage_openneuro_layout(ds_id: str, dest_dir: Path) -> int:
    """Materialize a stub BIDS layout from s3://openneuro.org/<ds_id>/.

    Downloads metadata files (participants.tsv, dataset_description.json)
    with real content, and creates empty placeholder files for every EEG
    file under sub-*/. The dataset loaders' iter_subject_files() only
    needs filename enumeration + participants.tsv to compute slice
    manifests, so the empty stubs are sufficient for submit-time work.
    The actual EEG content is streamed to the Batch containers from
    s3://openneuro.org/<ds_id>/ at run time via DATA_MIRROR.

    Returns the number of stub EEG files created.
    """
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config as BotoConfig

    s3 = boto3.client(
        "s3", region_name="us-east-1",
        config=BotoConfig(signature_version=UNSIGNED),
    )
    bucket = "openneuro.org"

    dest_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("participants.tsv", "dataset_description.json"):
        try:
            s3.download_file(bucket, f"{ds_id}/{fname}", str(dest_dir / fname))
        except Exception:
            pass  # not all datasets ship every metadata file

    eeg_exts = (".edf", ".set", ".vhdr", ".bdf", ".fif")
    n = 0
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{ds_id}/sub-"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(eeg_exts):
                continue
            rel = key[len(f"{ds_id}/"):]
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            n += 1
    return n


def _enumerate_eligible_subjects(
    dataset: str, data_dir: Path, channels: int, condition: str,
) -> list[tuple[str, str]]:
    """Return ordered list of (subject_id, condition) records.

    Matches build_norms.py iteration order so slice N here corresponds to
    slice N there. Both conditions of a subject count as separate entries
    (same as build_norms.py's eligible_idx stride).
    """
    from open_normative.datasets import DATASETS
    loader = DATASETS[dataset]()
    loader.n_channels = channels
    conditions = {"eo", "ec"} if condition == "both" else {condition}
    out: list[tuple[str, str]] = []
    for record in loader.iter_subject_files(data_dir):
        if record.condition in conditions:
            out.append((record.subject_id, record.condition))
    return out


def _write_slice_manifests(
    cfg: Config, run_id: str,
    eligible: list[tuple[str, str]], slices: int, per_slice: int,
) -> None:
    """Upload one plaintext manifest per slice to S3.

    Key: runs/<run_id>/slices/<i>.txt, one subject_id per line (deduped,
    order preserved). The container's entrypoint reads this to drive a
    selective aws s3 sync — each slice pulls ~per_slice/total of the mirror
    instead of the full dataset, which is the difference between a 9-min
    and a 30-second data-sync phase on LEMON.
    """
    import boto3
    s3 = _session(cfg).client("s3")
    for i in range(slices):
        start = i * per_slice
        end = min((i + 1) * per_slice, len(eligible))
        ids = [sid for sid, _ in eligible[start:end]]
        # Dedupe while preserving first-seen order (eo+ec map to same dir).
        seen: set[str] = set()
        unique: list[str] = []
        for sid in ids:
            if sid not in seen:
                seen.add(sid)
                unique.append(sid)
        body = ("\n".join(unique) + "\n").encode("utf-8")
        key = f"{cfg.runs_prefix}{run_id}/slices/{i}.txt"
        s3.put_object(
            Bucket=cfg.bucket, Key=key, Body=body, ContentType="text/plain",
        )


def _compute_slicing(
    total: int,
    requested_slices: int | None,
    requested_per_slice: int | None,
    cfg: Config,
) -> tuple[int, int]:
    """Return (num_slices, per_slice)."""
    if total <= 0:
        sys.exit("No eligible subjects found. Check --dataset and data-dir.")
    if requested_per_slice is not None:
        per_slice = max(1, requested_per_slice)
        slices = requested_slices or 1
        return slices, per_slice
    slices = requested_slices or cfg.default_slices
    max_sensible = max(1, total // max(cfg.min_subjects_per_slice, 1))
    slices = min(slices, max_sensible)
    slices = max(slices, 1)
    per_slice = (total + slices - 1) // slices
    # Shrink slice count so the tail slice is non-empty. With per_slice=14
    # and total=430 we want 31 slices (last one has 10 subjects), not 32
    # (where the 32nd would cover 434..447 = zero real subjects and fail).
    slices = (total + per_slice - 1) // per_slice
    return slices, per_slice


def _region_safety_warning(cfg: Config, dataset: str, force: bool) -> None:
    if dataset in _OPENNEURO_DATASETS and cfg.region != "us-east-1":
        msg = (
            f"⚠  {dataset} raw data lives in s3://openneuro.org (us-east-1). "
            f"Running jobs in {cfg.region} will incur cross-region egress "
            f"(~$0.02/GB). "
        )
        if force:
            print(msg + "Proceeding because --confirm-cross-region was passed.", file=sys.stderr)
        else:
            sys.exit(
                msg + "Re-run with --confirm-cross-region to accept, or "
                f"apply the Terraform module with region=us-east-1."
            )


def _array_env(
    bucket: str, run_id: str, dataset: str, channels: int, condition: str,
    per_slice: int, workers: int, source_flags: str, data_mirror: str | None,
) -> list[dict[str, str]]:
    pairs = {
        "MODE": "array",
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


def _merge_env(bucket: str, run_id: str) -> list[dict[str, str]]:
    return [
        {"name": "MODE", "value": "merge"},
        {"name": "BUCKET", "value": bucket},
        {"name": "RUN_ID", "value": run_id},
    ]


def _submission_key(cfg: Config, run_id: str) -> str:
    return f"{cfg.runs_prefix}{run_id}/_submission.json"


def _write_submission_manifest(cfg: Config, run_id: str, manifest: dict) -> None:
    import boto3
    s3 = _session(cfg).client("s3")
    s3.put_object(
        Bucket=cfg.bucket,
        Key=_submission_key(cfg, run_id),
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _read_submission_manifest(cfg: Config, run_id: str) -> dict | None:
    s3 = _session(cfg).client("s3")
    try:
        resp = s3.get_object(Bucket=cfg.bucket, Key=_submission_key(cfg, run_id))
    except s3.exceptions.NoSuchKey:
        return None
    except Exception as exc:
        if "NoSuchKey" in str(exc) or "404" in str(exc):
            return None
        raise
    return json.loads(resp["Body"].read())


def _describe(batch, job_ids: list[str]) -> list[dict]:
    if not job_ids:
        return []
    return batch.describe_jobs(jobs=job_ids).get("jobs", [])


def _wait_terminal(batch, job_id: str, label: str) -> str:
    from botocore.exceptions import BotoCoreError, ClientError

    last = None
    transient_fails = 0
    while True:
        try:
            jobs = _describe(batch, [job_id])
            transient_fails = 0
        except (BotoCoreError, ClientError) as exc:
            # Transient network/DNS/throttle blip (e.g. laptop sleep or wifi drop
            # during a long --follow). The job keeps running on AWS, so keep polling
            # rather than killing the run; give up only after many failures in a row.
            transient_fails += 1
            if transient_fails > 40:
                raise
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {label}: transient AWS error "
                  f"({type(exc).__name__}); retry {transient_fails}...", file=sys.stderr)
            time.sleep(15)
            continue
        if not jobs:
            print(f"[{label}] describe_jobs empty for {job_id}; retrying...", file=sys.stderr)
            time.sleep(10)
            continue
        st = jobs[0].get("status")
        if st != last:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {label}: {st}")
            last = st
        if st in ("SUCCEEDED", "FAILED"):
            if st == "FAILED":
                print(
                    f"[{label}] failure reason: {jobs[0].get('statusReason', 'unknown')}",
                    file=sys.stderr,
                )
            return st
        time.sleep(15)


# ─── submit ──────────────────────────────────────────────────────────────

def cmd_submit(args) -> int:
    cfg = _load_config(args.config)
    _region_safety_warning(cfg, args.dataset, args.confirm_cross_region)

    # Resolve where to enumerate subjects from. Three paths:
    #  (A) --data-dir explicit  → use it (legacy local-mirror workflow).
    #  (B) OpenNeuro dataset, no --data-dir → stage a stub BIDS layout from
    #      s3://openneuro.org/<ds_id>/ in a temp dir (zero local data needed).
    #  (C) Non-OpenNeuro (LEMON), no --data-dir → fall back to ~/Data/EEG/<DS>/.
    _stage_ctx = None  # holds the TemporaryDirectory until function returns
    if args.data_dir is not None:
        data_dir = args.data_dir
    elif args.dataset in _OPENNEURO_DATASETS:
        ds_id = _OPENNEURO_DATASETS[args.dataset]
        _stage_ctx = tempfile.TemporaryDirectory(prefix=f"open-norm-{args.dataset}-")
        data_dir = Path(_stage_ctx.name)
        n_stubs = _stage_openneuro_layout(ds_id, data_dir)
        print(
            f"staged {n_stubs} EEG path stubs from s3://openneuro.org/{ds_id}/ "
            f"(no local data download needed)",
            file=sys.stderr,
        )
    else:
        data_dir = Path.home() / "Data" / "EEG" / args.dataset.upper()

    if not data_dir.exists():
        sys.exit(
            f"Data dir not found: {data_dir}\n"
            f"Slice sizing reads the local dataset to enumerate subjects.\n"
            f"Pass --data-dir if your local copy lives elsewhere."
        )
    eligible = _enumerate_eligible_subjects(
        args.dataset, data_dir, args.channels, args.condition,
    )
    total = len(eligible)
    slices, per_slice = _compute_slicing(total, args.slices, args.per_slice, cfg)

    run_id = _resolve_run_id(args)
    git_sha = _git_sha()

    parts = []
    if args.source:              parts.append("--source")
    if args.ba_connectivity:     parts.append("--ba-connectivity")
    if args.dk_connectivity:     parts.append("--dk-connectivity")
    if args.skip_connectivity:   parts.append("--skip-connectivity")
    if args.save_psd:            parts.append("--save-psd")
    source_flags = " ".join(parts)

    data_mirror = args.data_mirror
    if data_mirror is None:
        if args.dataset == "lemon":
            # LEMON has no public S3 mirror — pulled into our bucket once,
            # then read by every container.
            data_mirror = f"s3://{cfg.bucket}/{cfg.mirrors_prefix}lemon/"
        elif args.dataset in _OPENNEURO_DATASETS:
            # Stream straight from OpenNeuro's public bucket (us-east-1).
            # Job role grants s3:GetObject + s3:ListBucket on openneuro.org.
            data_mirror = f"s3://openneuro.org/{_OPENNEURO_DATASETS[args.dataset]}/"

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

    session = _session(cfg)
    batch = session.client("batch")

    queues = batch.describe_job_queues(jobQueues=[cfg.job_queue]).get("jobQueues", [])
    if not queues or queues[0].get("state") != "ENABLED":
        sys.exit(f"Job queue {cfg.job_queue!r} not found or not ENABLED. Apply Terraform first.")

    # Write per-slice subject manifests so each container selectively syncs
    # only its own ~per_slice/total of the mirror instead of the whole thing.
    _write_slice_manifests(cfg, run_id, eligible, slices, per_slice)
    print(f"wrote {slices} slice manifest(s) to s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/slices/")

    array_resp = batch.submit_job(
        jobName=_job_name(run_id, "array"),
        jobQueue=cfg.job_queue,
        jobDefinition=cfg.array_jd,
        arrayProperties={"size": slices},
        containerOverrides={
            "environment": _array_env(
                cfg.bucket, run_id, args.dataset, args.channels, args.condition,
                per_slice, cfg.workers_per_slice, source_flags, data_mirror,
            ),
        },
        tags={"run_id": run_id, "git_sha": git_sha, "role": "array"},
    )
    array_id = array_resp["jobId"]
    print(f"submitted array job : {array_id}")

    merge_resp = batch.submit_job(
        jobName=_job_name(run_id, "merge"),
        jobQueue=cfg.job_queue,
        jobDefinition=cfg.merge_jd,
        dependsOn=[{"jobId": array_id, "type": "SEQUENTIAL"}],
        containerOverrides={"environment": _merge_env(cfg.bucket, run_id)},
        tags={"run_id": run_id, "git_sha": git_sha, "role": "merge"},
    )
    merge_id = merge_resp["jobId"]
    print(f"submitted merge job : {merge_id}")

    manifest = {
        "run_id": run_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "region": cfg.region,
        "dataset": args.dataset,
        "channels": args.channels,
        "condition": args.condition,
        "slices": slices,
        "per_slice": per_slice,
        "source_flags": source_flags,
        "data_mirror": data_mirror,
        "array_job_id": array_id,
        "merge_job_id": merge_id,
    }
    _write_submission_manifest(cfg, run_id, manifest)
    print(f"manifest        : s3://{cfg.bucket}/{_submission_key(cfg, run_id)}")

    print(
        f"\nCheck status:\n"
        f"  python scripts/cloud_recompute.py status {run_id}\n"
        f"  python scripts/cloud_recompute.py logs   {run_id} --follow\n"
        f"Outputs will appear at:\n"
        f"  s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/out/"
    )

    if args.follow:
        if _wait_terminal(batch, array_id, "array") != "SUCCEEDED":
            return 1
        if _wait_terminal(batch, merge_id, "merge") != "SUCCEEDED":
            return 1
        print(f"\n✓ Run complete: s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/out/")

    return 0


# ─── status ──────────────────────────────────────────────────────────────

def _print_run_status(cfg: Config, batch, manifest: dict) -> None:
    run_id = manifest["run_id"]
    array_id = manifest.get("array_job_id")
    merge_id = manifest.get("merge_job_id")
    submitted = manifest.get("submitted_at", "?")

    jobs = _describe(batch, [j for j in [array_id, merge_id] if j])
    by_id = {j["jobId"]: j for j in jobs}

    print(f"run_id          : {run_id}")
    print(f"submitted_at    : {submitted}")
    print(f"dataset         : {manifest.get('dataset')}  channels={manifest.get('channels')}  "
          f"condition={manifest.get('condition')}")
    print(f"slices          : {manifest.get('slices')} × per_slice={manifest.get('per_slice')}")
    for role, jid in [("array", array_id), ("merge", merge_id)]:
        if not jid:
            continue
        j = by_id.get(jid)
        if not j:
            print(f"{role:15s} : {jid} (not found in Batch — may have aged out)")
            continue
        status = j.get("status")
        extra = ""
        ap = j.get("arrayProperties") or {}
        summary = ap.get("statusSummary") or {}
        if summary:
            extra = " [" + " ".join(f"{k}={v}" for k, v in summary.items() if v) + "]"
        reason = j.get("statusReason")
        if reason and status in ("FAILED",):
            extra += f"  reason={reason!r}"
        print(f"{role:15s} : {status}{extra}")
    out_uri = f"s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/out/"
    print(f"outputs         : {out_uri}")


def cmd_status(args) -> int:
    cfg = _load_config(args.config)
    session = _session(cfg)
    batch = session.client("batch")

    if args.run_id:
        manifest = _read_submission_manifest(cfg, args.run_id)
        if manifest is None:
            sys.exit(f"No submission manifest found for run_id={args.run_id!r}")
        _print_run_status(cfg, batch, manifest)
        return 0

    runs = _list_runs(cfg, limit=args.limit)
    if not runs:
        print("(no runs found)")
        return 0
    for i, run_id in enumerate(runs):
        if i:
            print("─" * 60)
        manifest = _read_submission_manifest(cfg, run_id)
        if manifest is None:
            print(f"{run_id}  (no manifest)")
            continue
        _print_run_status(cfg, batch, manifest)
    return 0


# ─── logs ────────────────────────────────────────────────────────────────

def cmd_logs(args) -> int:
    cfg = _load_config(args.config)
    manifest = _read_submission_manifest(cfg, args.run_id)
    if manifest is None:
        sys.exit(f"No submission manifest found for run_id={args.run_id!r}")

    session = _session(cfg)
    batch = session.client("batch")
    logs = session.client("logs")

    log_group = "/aws/batch/norm-recompute"
    job_ids = [manifest.get(k) for k in ("array_job_id", "merge_job_id") if manifest.get(k)]
    jobs = _describe(batch, job_ids)

    # Collect log stream names across parent + array children.
    streams: list[str] = []
    for j in jobs:
        attempts = j.get("attempts") or []
        for att in attempts:
            ls = (att.get("container") or {}).get("logStreamName")
            if ls:
                streams.append(ls)
        # For array parents, also list child streams
        ap = j.get("arrayProperties") or {}
        if ap.get("size"):
            children = batch.list_jobs(arrayJobId=j["jobId"]).get("jobSummaryList", [])
            for c in children:
                cj = _describe(batch, [c["jobId"]])
                if not cj:
                    continue
                for att in cj[0].get("attempts") or []:
                    ls = (att.get("container") or {}).get("logStreamName")
                    if ls:
                        streams.append(ls)

    streams = list(dict.fromkeys(streams))  # dedupe preserving order
    if not streams:
        print("(no log streams yet — job may still be provisioning)", file=sys.stderr)
        return 0
    print(f"log group: {log_group}")
    print(f"streams  : {len(streams)}")
    for s in streams:
        print(f"  - {s}")
    print()

    # Print the last N events per stream, optionally follow.
    kwargs = {
        "logGroupName": log_group,
        "logStreamNames": streams,
        "limit": 100 if not args.follow else 10000,
    }
    paginator = logs.get_paginator("filter_log_events")
    seen_ids: set[str] = set()
    while True:
        for page in paginator.paginate(**kwargs):
            for ev in page.get("events", []):
                if ev["eventId"] in seen_ids:
                    continue
                seen_ids.add(ev["eventId"])
                ts = datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc).strftime("%H:%M:%S")
                print(f"[{ts}] {ev['message'].rstrip()}")
        if not args.follow:
            break
        # On follow: wait a bit, then re-query with the latest timestamp
        time.sleep(5)
        kwargs["startTime"] = int(time.time() * 1000) - 30_000
    return 0


# ─── download ────────────────────────────────────────────────────────────

def cmd_download(args) -> int:
    cfg = _load_config(args.config)
    out_uri = f"s3://{cfg.bucket}/{cfg.runs_prefix}{args.run_id}/out/"
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    print(f"syncing {out_uri} → {dest}")
    rc = subprocess.call([
        "aws", "s3", "sync", out_uri, str(dest),
        "--region", cfg.region,
        "--profile", cfg.profile or "default",
        "--no-progress",
    ])
    if rc != 0:
        return rc
    print("\nFiles:")
    for p in sorted(dest.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(dest)}  ({p.stat().st_size:,} bytes)")
    return 0


# ─── list ────────────────────────────────────────────────────────────────

def _list_runs(cfg: Config, limit: int = 20) -> list[str]:
    s3 = _session(cfg).client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    prefixes: list[str] = []
    for page in paginator.paginate(Bucket=cfg.bucket, Prefix=cfg.runs_prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []) or []:
            p = cp["Prefix"]
            run_id = p[len(cfg.runs_prefix):].rstrip("/")
            if run_id:
                prefixes.append(run_id)
    # Most recent first (run IDs sort lexicographically because timestamp is in ISO form).
    prefixes.sort(reverse=True)
    return prefixes[:limit]


def cmd_list(args) -> int:
    cfg = _load_config(args.config)
    runs = _list_runs(cfg, limit=args.limit)
    if not runs:
        print("(no runs in bucket)")
        return 0
    for run_id in runs:
        manifest = _read_submission_manifest(cfg, run_id)
        if manifest is None:
            print(f"{run_id}  (no manifest)")
        else:
            print(f"{run_id}  {manifest.get('dataset')}  {manifest.get('channels')}ch  "
                  f"{manifest.get('condition')}  "
                  f"slices={manifest.get('slices')}  "
                  f"submitted={manifest.get('submitted_at', '?')[:19]}")
    return 0


# ─── CLI ─────────────────────────────────────────────────────────────────

def _add_common(p):
    p.add_argument("--config", type=Path, default=REPO_ROOT / "aws-config.yaml",
                   help="Path to aws-config.yaml (default: repo root)")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="cloud_recompute",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # submit
    p_sub = sub.add_parser("submit", help="Submit a new recompute run")
    _add_common(p_sub)
    p_sub.add_argument("--dataset", required=True, help="Dataset key (lemon, dortmund, ...)")
    p_sub.add_argument("--data-dir", type=Path, default=None,
                       help="Local data dir for enumerating subjects. If omitted: "
                            "OpenNeuro datasets (dortmund/srm/trt/depress) auto-stage "
                            "filename-only stubs from s3://openneuro.org/dsXXXXXX/ in "
                            "a temp dir; everything else falls back to ~/Data/EEG/<DATASET>.")
    p_sub.add_argument("--channels", type=int, choices=[19, 37], default=19)
    p_sub.add_argument("--condition", choices=["eo", "ec", "both"], default="both")
    p_sub.add_argument("--source", action="store_true")
    p_sub.add_argument("--ba-connectivity", action="store_true")
    p_sub.add_argument("--dk-connectivity", action="store_true")
    p_sub.add_argument("--skip-connectivity", action="store_true")
    p_sub.add_argument("--save-psd", action="store_true")
    p_sub.add_argument("--slices", type=int, default=None,
                       help="Number of array elements. Default from aws-config.yaml.")
    p_sub.add_argument("--per-slice", type=int, default=None,
                       help="Explicit subjects-per-slice. Overrides slice-size math.")
    p_sub.add_argument("--data-mirror", default=None,
                       help="Override the s3:// URI for raw data. Auto-defaults: "
                            "LEMON → mirrors_prefix in your bucket; "
                            "dortmund/srm/trt/depress → s3://openneuro.org/dsXXXXXX/. "
                            "Required for HBN (point at one release, e.g. "
                            "s3://fcp-indi/data/Projects/HBN/BIDS_EEG/cmi_bids_R1/).")
    p_sub.add_argument("--confirm-cross-region", action="store_true")
    p_sub.add_argument("--follow", action="store_true",
                       help="Tail job status until the merge job terminates.")
    p_sub.add_argument("--dry-run", action="store_true")
    p_sub.add_argument("--run-id", default=None,
                       help="Explicit run id (default: <dataset>-<channels>ch-<timestamp>). "
                            "Used by the release orchestrator for idempotent named runs.")

    # status
    p_st = sub.add_parser("status", help="Show job status for a run (or recent runs)")
    _add_common(p_st)
    p_st.add_argument("run_id", nargs="?",
                      help="If omitted, shows the most recent N runs (see --limit).")
    p_st.add_argument("--limit", type=int, default=5,
                      help="When no run_id is given, how many recent runs to show (default: 5).")

    # logs
    p_lg = sub.add_parser("logs", help="Tail CloudWatch logs for a run")
    _add_common(p_lg)
    p_lg.add_argument("run_id")
    p_lg.add_argument("--follow", action="store_true", help="Stream new events until Ctrl-C.")

    # download
    p_dl = sub.add_parser("download", help="Sync run outputs locally")
    _add_common(p_dl)
    p_dl.add_argument("run_id")
    p_dl.add_argument("--output", type=Path, default=Path("./norm_out"),
                      help="Local directory to sync into (default: ./norm_out).")

    # list
    p_ls = sub.add_parser("list", help="List recent runs in the bucket")
    _add_common(p_ls)
    p_ls.add_argument("--limit", type=int, default=20)

    args = ap.parse_args()

    _require_boto3()

    if args.cmd == "submit":   return cmd_submit(args)
    if args.cmd == "status":   return cmd_status(args)
    if args.cmd == "logs":     return cmd_logs(args)
    if args.cmd == "download": return cmd_download(args)
    if args.cmd == "list":     return cmd_list(args)
    ap.error(f"unknown subcommand: {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())
