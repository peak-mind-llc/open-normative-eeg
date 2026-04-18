"""Sync a run's outputs back to the user's laptop.

Thin wrapper around ``aws s3 sync``. Preferred over a pure-boto3
implementation because aws-cli handles parallelism, retries, and
directory reconstruction natively.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .config import Config


def download_outputs(
    cfg: Config,
    run_id: str,
    dest: Path,
    *,
    include_subjects: bool = False,
) -> int:
    """Sync ``s3://<bucket>/<runs_prefix><run_id>/out/`` into ``dest``.

    If ``include_subjects`` is True, also sync the per-unit output tree
    at ``subjects/`` — useful for experiments where the merged ``out/``
    is only a summary and the full provenance lives per-unit.
    """
    if shutil.which("aws") is None:
        print(
            "This function uses the aws CLI. Install awscli v2 or "
            "use write_manifest/read_manifest/boto3 directly.",
            file=sys.stderr,
        )
        return 1

    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    profile = cfg.profile or "default"
    targets = [("out", dest)]
    if include_subjects:
        targets.append(("subjects", dest / "subjects"))

    rc_total = 0
    for suffix, local_dir in targets:
        s3_uri = f"s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}/{suffix}/"
        local_dir.mkdir(parents=True, exist_ok=True)
        print(f"syncing {s3_uri} → {local_dir}")
        rc = subprocess.call([
            "aws", "s3", "sync", s3_uri, str(local_dir),
            "--region", cfg.region,
            "--profile", profile,
            "--no-progress",
        ])
        if rc != 0:
            rc_total = rc
    return rc_total
