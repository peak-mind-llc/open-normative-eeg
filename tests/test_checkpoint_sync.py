"""Tests for the --checkpoint-sync S3 upload path in scripts/build_norms.py.

Covers URI parsing, per-subject upload of JSON (+ optional PSD), path-to-key
mapping relative to the output dir, and non-fatal failure handling.
"""
import importlib.util
import logging
from pathlib import Path

import numpy as np
import pytest

try:
    import boto3
    from moto import mock_aws
except ImportError:
    pytest.skip("boto3/moto not installed; install with [aws]+[dev]", allow_module_level=True)


_SPEC = importlib.util.spec_from_file_location(
    "build_norms", Path(__file__).resolve().parent.parent / "scripts" / "build_norms.py"
)
bn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bn)


class TestParseS3Uri:
    def test_bucket_and_prefix(self):
        assert bn._parse_s3_uri("s3://my-bucket/runs/abc/") == ("my-bucket", "runs/abc/")

    def test_prefix_normalized_to_trailing_slash(self):
        assert bn._parse_s3_uri("s3://my-bucket/runs/abc") == ("my-bucket", "runs/abc/")

    def test_bucket_only(self):
        assert bn._parse_s3_uri("s3://my-bucket") == ("my-bucket", "")

    def test_rejects_non_s3_scheme(self):
        with pytest.raises(ValueError, match="s3://"):
            bn._parse_s3_uri("http://example.com/x")

    def test_rejects_empty_bucket(self):
        with pytest.raises(ValueError, match="missing bucket"):
            bn._parse_s3_uri("s3:///prefix")


@mock_aws
def test_sync_uploads_files_under_output_dir(tmp_path, caplog):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    output_dir = tmp_path / "out"
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True)
    psd_dir = output_dir / "psd_checkpoints"
    psd_dir.mkdir()

    json_path = subjects_dir / "sub-01_ec.json"
    json_path.write_text('{"subject_id": "sub-01"}')
    psd_path = psd_dir / "sub-01_ec_psd.npz"
    np.savez_compressed(psd_path, freqs=np.array([1.0]))

    logger = logging.getLogger("test_sync")
    bn._sync_checkpoint_files(
        [json_path, psd_path], output_dir, "test-bucket", "runs/abc/", logger,
    )

    resp = s3.list_objects_v2(Bucket="test-bucket")
    keys = sorted(obj["Key"] for obj in resp.get("Contents", []))
    assert keys == [
        "runs/abc/psd_checkpoints/sub-01_ec_psd.npz",
        "runs/abc/subjects/sub-01_ec.json",
    ]


@mock_aws
def test_sync_empty_prefix_still_uploads(tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="my-bucket")
    out = tmp_path / "o"
    (out / "subjects").mkdir(parents=True)
    p = out / "subjects" / "x.json"
    p.write_text("{}")

    bn._sync_checkpoint_files([p], out, "my-bucket", "", logging.getLogger("t"))

    obj = s3.get_object(Bucket="my-bucket", Key="subjects/x.json")
    assert obj["Body"].read() == b"{}"


@mock_aws
def test_sync_skips_paths_outside_output_dir(tmp_path, caplog):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="my-bucket")
    out = tmp_path / "o"
    out.mkdir()
    foreign = tmp_path / "elsewhere.json"
    foreign.write_text("{}")

    with caplog.at_level(logging.WARNING):
        bn._sync_checkpoint_files([foreign], out, "my-bucket", "", logging.getLogger("t"))

    assert "not under output dir" in caplog.text
    assert s3.list_objects_v2(Bucket="my-bucket").get("KeyCount", 0) == 0


def test_sync_warns_when_boto3_missing(tmp_path, monkeypatch, caplog):
    # Simulate boto3 absence by poisoning the module import.
    monkeypatch.setitem(__import__("sys").modules, "boto3", None)
    bn._S3_WARN_EMITTED = False  # reset module-level flag

    out = tmp_path / "o"
    (out / "s").mkdir(parents=True)
    p = out / "s" / "x.json"
    p.write_text("{}")

    with caplog.at_level(logging.WARNING):
        bn._sync_checkpoint_files([p], out, "my-bucket", "", logging.getLogger("t"))

    assert "boto3 is not installed" in caplog.text


@mock_aws
def test_sync_logs_failure_without_raising(tmp_path, caplog):
    # Bucket does not exist -> upload should fail, but be swallowed as a warning.
    out = tmp_path / "o"
    (out / "s").mkdir(parents=True)
    p = out / "s" / "x.json"
    p.write_text("{}")

    with caplog.at_level(logging.WARNING):
        bn._sync_checkpoint_files([p], out, "nonexistent-bucket", "", logging.getLogger("t"))

    assert "failed to upload" in caplog.text
