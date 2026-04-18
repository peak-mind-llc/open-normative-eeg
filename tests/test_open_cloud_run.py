"""Unit tests for open_cloud_run.

Covers config loading, enumeration parsing, slicing math, manifest
round-trip, and a moto-backed submit → read-back.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

try:
    import boto3
    from moto import mock_aws
except ImportError:
    pytest.skip("boto3/moto not installed; install [aws] + [dev]", allow_module_level=True)

from open_cloud_run import (
    Config,
    Manifest,
    enumerate_units,
    read_manifest,
    write_manifest,
    list_runs,
)
from open_cloud_run.enumerate import slice_units
from open_cloud_run.submit import make_run_id, submit_run


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    y = tmp_path / "aws-config.yaml"
    y.write_text(
        """
aws:
  profile: null
  region: us-east-1
storage:
  bucket: test-bucket
  runs_prefix: runs/
  mirrors_prefix: mirrors/
compute:
  batch_job_queue: test-queue
  batch_job_definition: test-jd
  batch_merge_job_definition: test-merge-jd
  image: ghcr.io/example/img:latest
  workers_per_slice: 4
slicing:
  default_slices: 5
  min_units_per_slice: 2
"""
    )
    return Config.load(y)


# ─── Config ──────────────────────────────────────────────────────────────

class TestConfig:
    def test_loads_full_schema(self, cfg: Config):
        assert cfg.bucket == "test-bucket"
        assert cfg.region == "us-east-1"
        assert cfg.runs_prefix == "runs/"
        assert cfg.merge_jd == "test-merge-jd"
        assert cfg.workers_per_slice == 4
        assert cfg.default_slices == 5

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            Config.load(tmp_path / "nope.yaml")

    def test_missing_required_key_exits(self, tmp_path: Path):
        y = tmp_path / "bad.yaml"
        y.write_text("aws:\n  region: us-east-1\nstorage:\n  bucket: b\n")
        with pytest.raises(SystemExit):
            Config.load(y)

    def test_s3_uri_helpers(self, cfg: Config):
        assert cfg.runs_s3_uri("r1") == "s3://test-bucket/runs/r1/"
        assert cfg.out_s3_uri("r1") == "s3://test-bucket/runs/r1/out/"


# ─── Enumeration ─────────────────────────────────────────────────────────

class TestEnumerate:
    def test_stdout_lines_become_units(self, tmp_path: Path):
        # A tiny shell command producing three units.
        units = enumerate_units("printf 'sub-001\\nsub-002\\nsub-003\\n'")
        assert units == ["sub-001", "sub-002", "sub-003"]

    def test_blank_and_comment_lines_skipped(self):
        units = enumerate_units(
            "printf 'sub-001\\n\\n# a comment\\nsub-002\\n'"
        )
        assert units == ["sub-001", "sub-002"]

    def test_nonzero_exit_raises(self):
        with pytest.raises(RuntimeError, match="exited"):
            enumerate_units("printf 'x\\n'; exit 1")


class TestSlicing:
    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            slice_units([], None, None, 5, 1)

    def test_per_slice_override(self):
        units = [f"u{i}" for i in range(10)]
        slices, per = slice_units(units, None, 3, 5, 1)
        assert per == 3
        # ceil(10/3) = 4 slices
        assert len(slices) == 4
        assert sum(len(s) for s in slices) == 10
        assert slices[0] == ["u0", "u1", "u2"]
        assert slices[-1] == ["u9"]

    def test_default_slice_count(self):
        units = [f"u{i}" for i in range(10)]
        slices, per = slice_units(units, None, None, 5, 1)
        assert len(slices) == 5
        assert per == 2

    def test_min_per_slice_caps_slice_count(self):
        # 10 units with min_per_slice=4 means at most 2 slices.
        units = [f"u{i}" for i in range(10)]
        slices, per = slice_units(units, 10, None, 5, 4)
        assert len(slices) == 2
        assert per == 5


# ─── Manifest round-trip ─────────────────────────────────────────────────

class TestManifestLocal:
    def test_round_trip(self):
        m = Manifest.new(
            run_id="r-1",
            image="ghcr.io/x/y:latest",
            enumerate_cmd="echo a",
            driver_cmd="echo b",
            merge_cmd=None,
            outputs_dir="/work/out",
            slices=3,
            per_slice=4,
            n_units=10,
            region="us-east-1",
            git_sha="abc123",
            tags={"k": "v"},
        )
        m.array_job_id = "aid"
        blob = m.to_json()
        m2 = Manifest.from_json(blob)
        assert m2.run_id == m.run_id
        assert m2.array_job_id == "aid"
        assert m2.tags == {"k": "v"}

    def test_unknown_fields_are_ignored(self):
        blob = json.dumps({
            "run_id": "r",
            "submitted_at": "now",
            "image": "img",
            "enumerate_cmd": "e",
            "driver_cmd": "d",
            "merge_cmd": None,
            "outputs_dir": "/w",
            "slices": 1,
            "per_slice": 1,
            "n_units": 1,
            "future_field_we_dont_know_about": 42,
        })
        m = Manifest.from_json(blob)
        assert m.run_id == "r"


# ─── Submit + list, moto-backed ──────────────────────────────────────────

class _FakeBatch:
    """Just enough of the boto3 batch client for submit_run to exercise."""
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self._next_id = 0

    def submit_job(self, **kwargs):
        self._next_id += 1
        jid = f"fake-job-{self._next_id}"
        self.calls.append(("submit_job", kwargs))
        return {"jobId": jid}


@mock_aws
def test_submit_writes_manifests_and_submits_jobs(cfg, tmp_path):
    boto3.client("s3", region_name=cfg.region).create_bucket(Bucket=cfg.bucket)
    batch = _FakeBatch()

    units = [f"u{i}" for i in range(8)]
    run = submit_run(
        cfg,
        enumerate_cmd="unused",
        driver_cmd="python driver.py",
        merge_cmd="python merge.py",
        image="ghcr.io/x/y:tag",
        slices=4,
        units_override=units,
        batch_client=batch,
    )

    # Slice manifests uploaded.
    s3 = boto3.client("s3", region_name=cfg.region)
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=cfg.bucket)["Contents"]]
    assert any(k.startswith(f"runs/{run.run_id}/slices/0/") for k in keys)
    assert any(k.startswith(f"runs/{run.run_id}/slices/3/") for k in keys)
    # Submission manifest uploaded.
    assert f"runs/{run.run_id}/_submission.json" in keys

    # Batch got two submit_job calls (array + merge).
    assert len(batch.calls) == 2
    (arr_name, arr_kwargs), (mrg_name, mrg_kwargs) = batch.calls
    assert arr_kwargs["arrayProperties"]["size"] == 4
    # MODE env var is set on the array JD override.
    env = {e["name"]: e["value"] for e in arr_kwargs["containerOverrides"]["environment"]}
    assert env["MODE"] == "array"
    assert env["BUCKET"] == "test-bucket"
    assert env["DRIVER_CMD"] == "python driver.py"
    # Merge job depends on array.
    assert mrg_kwargs["dependsOn"] == [{"jobId": run.array_job_id, "type": "SEQUENTIAL"}]
    merge_env = {e["name"]: e["value"] for e in mrg_kwargs["containerOverrides"]["environment"]}
    assert merge_env["MODE"] == "merge"
    assert merge_env["MERGE_CMD"] == "python merge.py"


@mock_aws
def test_submit_requires_array_size_at_least_two(cfg):
    boto3.client("s3", region_name=cfg.region).create_bucket(Bucket=cfg.bucket)
    batch = _FakeBatch()
    with pytest.raises(ValueError, match="size >= 2"):
        submit_run(
            cfg,
            enumerate_cmd="unused",
            driver_cmd="python driver.py",
            image="img:latest",
            slices=1,
            per_slice=10,
            units_override=["u0"],
            batch_client=batch,
        )


@mock_aws
def test_list_runs_reads_manifests(cfg):
    boto3.client("s3", region_name=cfg.region).create_bucket(Bucket=cfg.bucket)
    batch = _FakeBatch()
    # Submit two runs so we have two prefixes.
    run1 = submit_run(
        cfg, enumerate_cmd="u", driver_cmd="d",
        image="img:latest", slices=2, per_slice=1,
        units_override=["u0", "u1"], batch_client=batch,
    )
    run2 = submit_run(
        cfg, enumerate_cmd="u", driver_cmd="d",
        image="img:latest", slices=2, per_slice=1,
        units_override=["u0", "u1"], batch_client=batch,
    )
    rows = list_runs(cfg, limit=10)
    ids = [r["run_id"] for r in rows]
    # Most recent first; the two run_ids are timestamped so later wins.
    assert set(ids) == {run1.run_id, run2.run_id}
    # Manifests were read successfully.
    assert rows[0]["image"] == "img:latest"
    assert rows[0]["slices"] == 2


@mock_aws
def test_read_manifest_missing_returns_none(cfg):
    boto3.client("s3", region_name=cfg.region).create_bucket(Bucket=cfg.bucket)
    assert read_manifest(cfg, "nonexistent-run") is None


def test_make_run_id_prefixed():
    rid = make_run_id("p300-sweep")
    assert rid.startswith("p300-sweep-")
    assert rid.endswith("Z")
    assert len(rid) > len("p300-sweep-")


def test_make_run_id_no_prefix():
    rid = make_run_id(None)
    assert rid.endswith("Z")
    assert len(rid) == len("YYYYmmddTHHMMSSZ")
