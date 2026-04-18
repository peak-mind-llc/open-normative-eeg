"""Submit a run: array job + optional merge job.

The run_id is generated here; the caller can pass a prefix (e.g. the
experiment name) that becomes the leading segment. Submission writes:

- One ``slices/<N>/manifest.txt`` per array element into S3.
- One ``_submission.json`` at the run root.
- One Batch array job.
- Optionally one Batch merge job that ``dependsOn`` the array.

No dataset/unit knowledge is baked in. The framework's only inputs
from the caller are (command strings, list of units, image URI, slice
shape).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .enumerate import enumerate_units, slice_units
from .manifest import (
    Manifest,
    write_manifest,
    write_slice_manifests,
    slice_manifest_key,
)


REPO_ROOT_ENVS = ["PWD", "HOME"]  # fallbacks if git fails


@dataclass
class SubmittedRun:
    run_id: str
    array_job_id: str
    merge_job_id: str | None
    slices: int
    per_slice: int
    n_units: int
    outputs_s3_uri: str


def _git_sha(cwd: str | None = None) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd, text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return out or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def make_run_id(prefix: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if prefix:
        return f"{prefix}-{stamp}"
    return stamp


def _array_env(
    cfg: Config,
    run_id: str,
    driver_cmd: str,
    outputs_dir: str,
) -> list[dict[str, str]]:
    """Env vars set on every array element's container.

    The container's entrypoint reads these to know what to do; the
    driver itself also sees them (DRIVER_CMD is interpolated by the
    entrypoint, not passed to the driver)."""
    return [
        {"name": "MODE", "value": "array"},
        {"name": "BUCKET", "value": cfg.bucket},
        {"name": "RUN_ID", "value": run_id},
        {"name": "RUNS_PREFIX", "value": cfg.runs_prefix},
        {"name": "DRIVER_CMD", "value": driver_cmd},
        {"name": "OUT_DIR", "value": outputs_dir},
    ]


def _merge_env(
    cfg: Config,
    run_id: str,
    merge_cmd: str,
    outputs_dir: str,
) -> list[dict[str, str]]:
    return [
        {"name": "MODE", "value": "merge"},
        {"name": "BUCKET", "value": cfg.bucket},
        {"name": "RUN_ID", "value": run_id},
        {"name": "RUNS_PREFIX", "value": cfg.runs_prefix},
        {"name": "MERGE_CMD", "value": merge_cmd},
        {"name": "OUT_DIR", "value": outputs_dir},
    ]


def submit_run(
    cfg: Config,
    *,
    enumerate_cmd: str,
    driver_cmd: str,
    image: str | None = None,
    merge_cmd: str | None = None,
    outputs_dir: str = "/work/out",
    slices: int | None = None,
    per_slice: int | None = None,
    run_id_prefix: str | None = None,
    tags: dict[str, str] | None = None,
    enumerate_cwd: str | None = None,
    units_override: list[str] | None = None,
    batch_client=None,
) -> SubmittedRun:
    """Enumerate work units, slice them, submit to AWS Batch.

    Parameters:
        cfg: loaded Config.
        enumerate_cmd: shell command whose stdout lines are work unit IDs.
            If ``units_override`` is also given, this is recorded in the
            manifest but not actually re-run.
        driver_cmd: shell command executed once per unit inside the
            container. The entrypoint sets $UNIT / $OUT_DIR before
            invoking this command.
        image: container image URI. Defaults to cfg.default_image.
        merge_cmd: optional shell command run after all array elements
            succeed. Runs in an on-demand container (same image).
        outputs_dir: container-local directory the driver writes to.
            Synced to S3 at slice end.
        slices, per_slice: sizing overrides. See slice_units().
        run_id_prefix: naming prefix (e.g. experiment name).
        tags: extra tags attached to the Batch jobs and the manifest.
        enumerate_cwd: directory the enumerate command runs in (defaults
            to current working directory).
        units_override: skip running the enumerator and use this list
            directly. For testing or for callers who already enumerated.
        batch_client: inject a boto3 batch client for tests. Production
            callers leave this None.

    Returns a SubmittedRun describing the two job IDs and the
    outputs S3 URI.

    Raises RuntimeError on enumeration failure, ValueError on empty
    unit list or array size < 2 (Batch requirement).
    """
    if units_override is not None:
        units = list(units_override)
    else:
        units = enumerate_units(enumerate_cmd, cwd=enumerate_cwd)
    if not units:
        raise ValueError("Enumerator produced no units; nothing to submit.")

    slice_lists, per_slice_n = slice_units(
        units,
        requested_slices=slices,
        requested_per_slice=per_slice,
        default_slices=cfg.default_slices,
        min_per_slice=cfg.min_units_per_slice,
    )
    n_slices = len(slice_lists)
    if n_slices < 2:
        raise ValueError(
            f"AWS Batch array jobs require size >= 2, got {n_slices}. "
            f"Either reduce --per-slice (splits more work) or ensure "
            f"the enumerator produces at least 2 units."
        )

    image = image or cfg.default_image
    if not image:
        raise ValueError(
            "No container image specified. Pass image= or set "
            "compute.image in aws-config.yaml."
        )

    # Resolve clients up front. If the caller injected one, use it for both.
    if batch_client is None:
        import boto3
        import boto3.session as _session
        session = _session.Session(profile_name=cfg.profile, region_name=cfg.region)
        batch_client = session.client("batch")
        s3_client = session.client("s3")
    else:
        s3_client = None  # manifest.write_* will build its own

    run_id = make_run_id(run_id_prefix)
    git_sha = _git_sha(cwd=enumerate_cwd)

    # Upload slice manifests first so containers can pull them as soon
    # as they start.
    write_slice_manifests(cfg, run_id, slice_lists, s3_client=s3_client)

    # Array job submission.
    tags = dict(tags or {})
    tags.update({"run_id": run_id, "role": "array"})
    if git_sha:
        tags["git_sha"] = git_sha

    array_resp = batch_client.submit_job(
        jobName=f"{run_id}-array",
        jobQueue=cfg.job_queue,
        jobDefinition=cfg.array_jd,
        arrayProperties={"size": n_slices},
        containerOverrides={
            "image": image,
            "environment": _array_env(cfg, run_id, driver_cmd, outputs_dir),
        },
        tags=tags,
    )
    array_id = array_resp["jobId"]

    merge_id: str | None = None
    if merge_cmd:
        if not cfg.merge_jd:
            raise ValueError(
                "merge_cmd given but cfg.merge_jd (batch_merge_job_definition) "
                "is not set in aws-config.yaml."
            )
        merge_tags = dict(tags)
        merge_tags["role"] = "merge"
        merge_resp = batch_client.submit_job(
            jobName=f"{run_id}-merge",
            jobQueue=cfg.job_queue,
            jobDefinition=cfg.merge_jd,
            dependsOn=[{"jobId": array_id, "type": "SEQUENTIAL"}],
            containerOverrides={
                "image": image,
                "environment": _merge_env(cfg, run_id, merge_cmd, outputs_dir),
            },
            tags=merge_tags,
        )
        merge_id = merge_resp["jobId"]

    manifest = Manifest.new(
        run_id=run_id,
        image=image,
        enumerate_cmd=enumerate_cmd,
        driver_cmd=driver_cmd,
        merge_cmd=merge_cmd,
        outputs_dir=outputs_dir,
        slices=n_slices,
        per_slice=per_slice_n,
        n_units=len(units),
        region=cfg.region,
        git_sha=git_sha,
        tags=tags,
    )
    manifest.array_job_id = array_id
    manifest.merge_job_id = merge_id
    write_manifest(cfg, manifest, s3_client=s3_client)

    return SubmittedRun(
        run_id=run_id,
        array_job_id=array_id,
        merge_job_id=merge_id,
        slices=n_slices,
        per_slice=per_slice_n,
        n_units=len(units),
        outputs_s3_uri=cfg.out_s3_uri(run_id),
    )
