"""Submission manifest round-trip.

Each run writes two things into S3:

1. ``_submission.json`` at ``runs/<run_id>/`` — a compact record of
   how the run was submitted (commands, image, slice count, job IDs,
   git SHA, timestamp). Read by status/logs/download to resolve a
   run_id into job IDs without needing any other tracking system.

2. ``slices/<N>/manifest.txt`` under the run prefix — one line per
   work unit, for array element N to read at startup.

Keeping these in S3 (not a database) means there's no control-plane
infrastructure to maintain; the bucket is the source of truth.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import Config


@dataclass
class Manifest:
    run_id: str
    submitted_at: str
    image: str
    enumerate_cmd: str
    driver_cmd: str
    merge_cmd: str | None
    outputs_dir: str
    slices: int
    per_slice: int
    n_units: int
    array_job_id: str | None = None
    merge_job_id: str | None = None
    git_sha: str | None = None
    region: str | None = None
    tags: dict[str, str] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        run_id: str,
        image: str,
        enumerate_cmd: str,
        driver_cmd: str,
        merge_cmd: str | None,
        outputs_dir: str,
        slices: int,
        per_slice: int,
        n_units: int,
        region: str | None = None,
        git_sha: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> "Manifest":
        return cls(
            run_id=run_id,
            submitted_at=datetime.now(timezone.utc).isoformat(),
            image=image,
            enumerate_cmd=enumerate_cmd,
            driver_cmd=driver_cmd,
            merge_cmd=merge_cmd,
            outputs_dir=outputs_dir,
            slices=slices,
            per_slice=per_slice,
            n_units=n_units,
            region=region,
            git_sha=git_sha,
            tags=tags or {},
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, blob: str | bytes) -> "Manifest":
        if isinstance(blob, bytes):
            blob = blob.decode("utf-8")
        data: dict[str, Any] = json.loads(blob)
        allowed = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in allowed})


def submission_key(cfg: Config, run_id: str) -> str:
    return f"{cfg.runs_prefix}{run_id}/_submission.json"


def slice_manifest_key(cfg: Config, run_id: str, slice_index: int) -> str:
    return f"{cfg.runs_prefix}{run_id}/slices/{slice_index}/manifest.txt"


def write_manifest(cfg: Config, manifest: Manifest, s3_client=None) -> None:
    if s3_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        s3_client = session.client("s3")
    s3_client.put_object(
        Bucket=cfg.bucket,
        Key=submission_key(cfg, manifest.run_id),
        Body=manifest.to_json().encode("utf-8"),
        ContentType="application/json",
    )


def read_manifest(cfg: Config, run_id: str, s3_client=None) -> Manifest | None:
    if s3_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        s3_client = session.client("s3")
    try:
        resp = s3_client.get_object(Bucket=cfg.bucket, Key=submission_key(cfg, run_id))
    except Exception as exc:
        if "NoSuchKey" in type(exc).__name__ or "NoSuchKey" in str(exc) or "404" in str(exc):
            return None
        raise
    return Manifest.from_json(resp["Body"].read())


def write_slice_manifests(
    cfg: Config,
    run_id: str,
    slice_units: list[list[str]],
    s3_client=None,
) -> list[str]:
    """Upload one manifest per slice. Each element is the list of UNIT
    strings that array element N should process. Returns the S3 keys
    written, in slice order."""
    if s3_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        s3_client = session.client("s3")
    keys: list[str] = []
    for i, units in enumerate(slice_units):
        key = slice_manifest_key(cfg, run_id, i)
        body = "\n".join(units).encode("utf-8")
        s3_client.put_object(
            Bucket=cfg.bucket,
            Key=key,
            Body=body,
            ContentType="text/plain",
        )
        keys.append(key)
    return keys
