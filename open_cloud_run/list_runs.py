"""List runs under the bucket's runs_prefix."""
from __future__ import annotations

from .config import Config
from .manifest import read_manifest


def list_runs(cfg: Config, *, limit: int = 20, s3_client=None) -> list[dict]:
    """Return a list of dicts describing runs, most recent first.

    Each dict has at least ``run_id`` and possibly ``submitted_at``,
    ``dataset``, ``slices``, etc (when a manifest is readable).
    """
    if s3_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        s3_client = session.client("s3")

    paginator = s3_client.get_paginator("list_objects_v2")
    run_ids: list[str] = []
    for page in paginator.paginate(Bucket=cfg.bucket, Prefix=cfg.runs_prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes") or []:
            p = cp["Prefix"]
            if p.endswith("/"):
                rid = p[len(cfg.runs_prefix):].rstrip("/")
                if rid:
                    run_ids.append(rid)
    # Most recent first: run IDs end with a UTC timestamp so reverse-lex works.
    run_ids.sort(reverse=True)
    run_ids = run_ids[:limit]

    results: list[dict] = []
    for rid in run_ids:
        m = read_manifest(cfg, rid, s3_client=s3_client)
        row: dict[str, object] = {"run_id": rid}
        if m is not None:
            row.update({
                "submitted_at": m.submitted_at,
                "image": m.image,
                "slices": m.slices,
                "per_slice": m.per_slice,
                "n_units": m.n_units,
                "git_sha": m.git_sha,
            })
        else:
            row["manifest"] = None
        results.append(row)
    return results
