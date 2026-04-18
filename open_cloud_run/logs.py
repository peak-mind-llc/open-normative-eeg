"""CloudWatch log tailing for a run.

Gathers every log stream across the array parent, its array children,
and the merge job; dedupes events by ID; optionally follows indefinitely.

The log group is configurable via the batch job definition's
logConfiguration. In this project's Terraform module that's
``/aws/batch/norm-recompute``. The SDK accepts it as an argument rather
than hardcoding a value.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Iterable

from .config import Config
from .manifest import read_manifest


DEFAULT_LOG_GROUP = "/aws/batch/norm-recompute"


def _collect_streams(batch_client, job_ids: Iterable[str]) -> list[str]:
    streams: list[str] = []
    for jid in job_ids:
        if not jid:
            continue
        jobs = batch_client.describe_jobs(jobs=[jid]).get("jobs", [])
        if not jobs:
            continue
        job = jobs[0]
        for attempt in job.get("attempts") or []:
            s = (attempt.get("container") or {}).get("logStreamName")
            if s:
                streams.append(s)
        # array parent: fan out to children
        if (job.get("arrayProperties") or {}).get("size"):
            child_listing = batch_client.list_jobs(arrayJobId=jid).get("jobSummaryList", [])
            child_ids = [c["jobId"] for c in child_listing]
            if child_ids:
                # Batch describe_jobs accepts up to 100 IDs at a time.
                for i in range(0, len(child_ids), 100):
                    chunk = child_ids[i:i + 100]
                    for cj in batch_client.describe_jobs(jobs=chunk).get("jobs", []):
                        for attempt in cj.get("attempts") or []:
                            s = (attempt.get("container") or {}).get("logStreamName")
                            if s:
                                streams.append(s)
    # dedupe preserving order
    return list(dict.fromkeys(streams))


def get_logs(
    cfg: Config,
    run_id: str,
    *,
    log_group: str = DEFAULT_LOG_GROUP,
    follow: bool = False,
    batch_client=None,
    logs_client=None,
    out=sys.stdout,
) -> int:
    """Print logs for a run. Returns an exit code (0 on clean finish,
    non-zero if streams cannot be located).

    In follow mode this loops until SIGINT or until the process is
    killed externally. The loop retries stream collection every
    ``follow`` iteration so streams that appear after the first query
    (e.g. new array children starting) are picked up.
    """
    manifest = read_manifest(cfg, run_id)
    if manifest is None:
        print(f"No submission manifest found for run_id={run_id!r}", file=sys.stderr)
        return 1

    if batch_client is None or logs_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        batch_client = batch_client or session.client("batch")
        logs_client = logs_client or session.client("logs")

    job_ids = [j for j in (manifest.array_job_id, manifest.merge_job_id) if j]
    seen: set[str] = set()

    def _print_streams(streams: list[str]) -> None:
        if not streams:
            return
        paginator = logs_client.get_paginator("filter_log_events")
        for page in paginator.paginate(
            logGroupName=log_group,
            logStreamNames=streams,
            limit=10000,
        ):
            for ev in page.get("events", []):
                if ev["eventId"] in seen:
                    continue
                seen.add(ev["eventId"])
                ts = datetime.fromtimestamp(ev["timestamp"] / 1000, tz=timezone.utc).strftime("%H:%M:%S")
                out.write(f"[{ts}] {ev['message'].rstrip()}\n")

    streams = _collect_streams(batch_client, job_ids)
    if not streams:
        print("(no log streams yet — job may still be provisioning)", file=sys.stderr)
        if not follow:
            return 0

    _print_streams(streams)
    out.flush()

    if not follow:
        return 0

    try:
        while True:
            time.sleep(5)
            streams = _collect_streams(batch_client, job_ids)
            if streams:
                _print_streams(streams)
                out.flush()
    except KeyboardInterrupt:
        return 0
