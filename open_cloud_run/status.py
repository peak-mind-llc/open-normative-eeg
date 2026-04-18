"""Describe run status by resolving run_id → job IDs via the manifest."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Config
from .manifest import Manifest, read_manifest


@dataclass
class JobStatus:
    job_id: str
    status: str
    reason: str | None
    # For array parents: breakdown of child status counts
    array_summary: dict[str, int] | None = None


@dataclass
class RunStatus:
    run_id: str
    manifest: Manifest
    array: JobStatus | None
    merge: JobStatus | None


def _describe(batch_client, job_ids: list[str]) -> list[dict]:
    if not job_ids:
        return []
    return batch_client.describe_jobs(jobs=job_ids).get("jobs", [])


def _to_status(job: dict) -> JobStatus:
    ap = (job.get("arrayProperties") or {}).get("statusSummary") or {}
    summary = {k: int(v) for k, v in ap.items() if v}
    return JobStatus(
        job_id=job["jobId"],
        status=job.get("status", "UNKNOWN"),
        reason=job.get("statusReason"),
        array_summary=summary or None,
    )


def get_status(
    cfg: Config,
    run_id: str,
    *,
    batch_client=None,
    s3_client=None,
) -> RunStatus | None:
    """Return a RunStatus for the given run_id, or None if no manifest exists.

    Does not raise for jobs that have aged out of the Batch retention
    window — those show up as ``None`` in the returned status.
    """
    manifest = read_manifest(cfg, run_id, s3_client=s3_client)
    if manifest is None:
        return None
    if batch_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        batch_client = session.client("batch")
    ids = [j for j in (manifest.array_job_id, manifest.merge_job_id) if j]
    jobs = _describe(batch_client, ids)
    by_id: dict[str, dict] = {j["jobId"]: j for j in jobs}
    array = _to_status(by_id[manifest.array_job_id]) if manifest.array_job_id and manifest.array_job_id in by_id else None
    merge = _to_status(by_id[manifest.merge_job_id]) if manifest.merge_job_id and manifest.merge_job_id in by_id else None
    return RunStatus(run_id=run_id, manifest=manifest, array=array, merge=merge)


def format_status(status: RunStatus) -> str:
    """Human-readable multi-line string."""
    lines = []
    m = status.manifest
    lines.append(f"run_id          : {status.run_id}")
    lines.append(f"submitted_at    : {m.submitted_at}")
    lines.append(f"image           : {m.image}")
    lines.append(f"units           : {m.n_units}  slices={m.slices} × per_slice={m.per_slice}")
    if m.git_sha:
        lines.append(f"git_sha         : {m.git_sha}")
    for label, js in (("array", status.array), ("merge", status.merge)):
        if js is None:
            if (label == "array" and not m.array_job_id) or (label == "merge" and not m.merge_job_id):
                continue
            lines.append(f"{label:15s} : (job aged out of Batch retention)")
            continue
        extra = ""
        if js.array_summary:
            extra = "  [" + " ".join(f"{k}={v}" for k, v in js.array_summary.items()) + "]"
        if js.reason and js.status == "FAILED":
            extra += f"  reason={js.reason!r}"
        lines.append(f"{label:15s} : {js.status}{extra}")
    return "\n".join(lines)
