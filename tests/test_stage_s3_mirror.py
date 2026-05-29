"""Tests for _stage_s3_mirror_layout in scripts/cloud_recompute.py.

The release pipeline uses this to enumerate slice manifests for LEMON without
needing the dataset on local disk: metadata files (participants.tsv, META CSV)
are downloaded with real content, EEG files are touched as empty stubs.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

try:
    import boto3
    from moto import mock_aws
except ImportError:
    pytest.skip("boto3/moto not installed; install with [aws]+[dev]", allow_module_level=True)


_SPEC = importlib.util.spec_from_file_location(
    "cloud_recompute",
    Path(__file__).resolve().parent.parent / "scripts" / "cloud_recompute.py",
)
cr = importlib.util.module_from_spec(_SPEC)
# Register BEFORE exec so dataclass introspection (Config) can resolve
# cls.__module__ — Python 3.10 dataclasses else trip with AttributeError.
sys.modules["cloud_recompute"] = cr
_SPEC.loader.exec_module(cr)


def _put(s3, bucket, key, body=b""):
    s3.put_object(Bucket=bucket, Key=key, Body=body)


@mock_aws
def test_stage_s3_mirror_downloads_metadata_and_stubs_eeg(tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="ours")

    # LEMON-shaped layout: participants.tsv + META CSV at the root, then per-
    # subject EEG directories.
    _put(s3, "ours", "mirrors/lemon/participants.tsv",
         b"participant_id\tage\tsex\nsub-010002\t25\tF\n")
    _put(s3, "ours", "mirrors/lemon/META_LEMON.csv", b"id,age,gender\nsub-010002,25,F\n")
    _put(s3, "ours", "mirrors/lemon/dataset_description.json", b'{"Name": "LEMON"}')
    _put(s3, "ours", "mirrors/lemon/sub-010002/RSEEG/sub-010002.vhdr",
         b"BV header content that is large and should NOT be downloaded")
    _put(s3, "ours", "mirrors/lemon/sub-010002/RSEEG/sub-010002.eeg",
         b"binary EEG content that is HUGE and should NOT be downloaded")
    _put(s3, "ours", "mirrors/lemon/sub-010002/RSEEG/sub-010002.vmrk", b"markers")

    session = boto3.Session(region_name="us-east-1")
    n_eeg = cr._stage_s3_mirror_layout(
        session, "ours", "mirrors/lemon/", tmp_path,
    )

    # Three EEG stubs created (vhdr, eeg, vmrk all in the EEG extensions set).
    assert n_eeg == 3

    # Metadata downloaded with real content.
    assert (tmp_path / "participants.tsv").read_bytes().startswith(b"participant_id")
    assert (tmp_path / "META_LEMON.csv").read_bytes().startswith(b"id,age,gender")
    assert (tmp_path / "dataset_description.json").read_bytes().startswith(b'{"Name"')

    # EEG files exist but are empty stubs.
    vhdr = tmp_path / "sub-010002" / "RSEEG" / "sub-010002.vhdr"
    eeg = tmp_path / "sub-010002" / "RSEEG" / "sub-010002.eeg"
    assert vhdr.exists() and vhdr.stat().st_size == 0
    assert eeg.exists() and eeg.stat().st_size == 0


@mock_aws
def test_stage_s3_mirror_handles_empty_prefix(tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="ours")
    session = boto3.Session(region_name="us-east-1")
    n_eeg = cr._stage_s3_mirror_layout(session, "ours", "mirrors/lemon/", tmp_path)
    assert n_eeg == 0


@mock_aws
def test_stage_s3_mirror_normalizes_missing_trailing_slash(tmp_path):
    """Caller may pass prefix without trailing slash; function adds one."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="ours")
    _put(s3, "ours", "mirrors/lemon/sub-01/sub-01.edf", b"x")
    _put(s3, "ours", "mirrors/lemon/participants.tsv", b"id\nsub-01\n")
    session = boto3.Session(region_name="us-east-1")
    n_eeg = cr._stage_s3_mirror_layout(session, "ours", "mirrors/lemon", tmp_path)
    assert n_eeg == 1
    assert (tmp_path / "participants.tsv").read_bytes() == b"id\nsub-01\n"
    assert (tmp_path / "sub-01" / "sub-01.edf").exists()
