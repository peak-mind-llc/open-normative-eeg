"""Tests for the release orchestrator core (open_normative/release.py)."""
import json
import hashlib
import importlib.util as _ilu
from pathlib import Path

import numpy as np
import pytest

from open_normative import release as rel


def test_normalize_version_strips_v_and_validates():
    assert rel.normalize_version("v0.2.0") == "0.2.0"
    assert rel.normalize_version("0.2.0") == "0.2.0"
    with pytest.raises(ValueError):
        rel.normalize_version("0.2")        # not X.Y.Z
    with pytest.raises(ValueError):
        rel.normalize_version("v1.2.x")     # non-numeric


def test_bump_version_rewrites_both_files(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "open-normative-eeg"\nversion = "0.1.0"\n'
    )
    pkg = tmp_path / "open_normative"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""pkg."""\n__version__ = "0.1.0"\n')

    rel.bump_version("0.2.0", tmp_path)

    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text()
    assert '__version__ = "0.2.0"' in (pkg / "__init__.py").read_text()
    assert 'name = "open-normative-eeg"' in (tmp_path / "pyproject.toml").read_text()


def test_pipeline_params_sha256_is_stable_and_hex():
    h1 = rel.pipeline_params_sha256()
    h2 = rel.pipeline_params_sha256()
    assert h1 == h2
    assert len(h1) == 64 and int(h1, 16) >= 0


def _make_payload(tmp_path):
    payload = tmp_path / "payload"
    (payload / "npz").mkdir(parents=True)
    (payload / "norms_psd.npz").write_bytes(b"PSD-BYTES")
    (payload / "npz" / "scalp_power.npz").write_bytes(b"SCALP-BYTES")
    (payload / "MANIFEST.txt").write_text("manifest")
    return payload


def test_sha256_file_matches_hashlib(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    assert rel.sha256_file(f) == hashlib.sha256(b"hello").hexdigest()


def test_build_release_manifest_lists_every_file(tmp_path):
    payload = _make_payload(tmp_path)
    manifest = rel.build_release_manifest(
        version="0.2.0",
        payload_dir=payload,
        datasets=[{"name": "lemon", "source": "s3://b/mirrors/lemon",
                   "channels": 37, "run_id": "release-v0.2.0-lemon-37ch", "n_subjects": 176}],
        merge_run_id="release-v0.2.0-merged-37ch",
        code={"git_sha": "abc123", "git_tag": "v0.2.0", "image": "ghcr.io/x@sha256:..."},
        format_versions={"norms_npz": 2, "psd": 2},
        s3_base="s3://b/releases/v0.2.0/",
        builder="local:test",
    )
    paths = {a["path"] for a in manifest["artifacts"]}
    assert paths == {"norms_psd.npz", "npz/scalp_power.npz", "MANIFEST.txt"}
    psd = next(a for a in manifest["artifacts"] if a["path"] == "norms_psd.npz")
    assert psd["sha256"] == hashlib.sha256(b"PSD-BYTES").hexdigest()
    assert psd["bytes"] == len(b"PSD-BYTES")
    assert manifest["version"] == "v0.2.0"
    assert manifest["pipeline_params_sha256"] == rel.pipeline_params_sha256()
    assert manifest["datasets"][0]["name"] == "lemon"


def test_write_release_json_roundtrips(tmp_path):
    payload = _make_payload(tmp_path)
    manifest = rel.build_release_manifest(
        version="0.2.0", payload_dir=payload, datasets=[], merge_run_id="m",
        code={"git_sha": "x", "git_tag": "v0.2.0", "image": None},
        format_versions={"norms_npz": 2, "psd": 2}, s3_base="s3://b/releases/v0.2.0/",
        builder="local:test",
    )
    rel.write_release_json(manifest, payload)
    loaded = json.loads((payload / "release.json").read_text())
    assert loaded["version"] == "v0.2.0"
    assert all(a["path"] != "release.json" for a in loaded["artifacts"])


def _write_norms_psd(path, *, version=2, p97_5=2.0, p50_offset=0.0, with_npz_meta=True):
    """Write a minimal norms_psd.npz. percentiles in log10(µV²/Hz)."""
    n_bins, n_cond, n_ch, n_freq, n_pts = 1, 1, 2, 3, 13
    points = [0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99, 99.5]
    mean = np.full((n_bins, n_cond, n_ch, n_freq), 0.5)
    pct = np.zeros((n_bins, n_cond, n_ch, n_freq, n_pts))
    for k in range(n_pts):
        pct[..., k] = -1.0 + (p97_5 + 1.0) * (k / (n_pts - 1))
    pct[..., 6] = mean + p50_offset
    pct.sort(axis=-1)  # guarantee monotonic
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(mean=mean, sd=np.full_like(mean, 0.3),
                  percentiles=pct.astype(np.float32),
                  percentile_points=np.array(points),
                  n=np.full((n_bins, n_cond), 100))
    if version is not None:
        kwargs["psd_format_version"] = version
    np.savez_compressed(path, **kwargs)


def test_verify_passes_clean_payload(tmp_path):
    payload = tmp_path / "p"
    _write_norms_psd(payload / "norms_psd.npz", version=2, p97_5=2.0)
    (payload / "npz").mkdir(parents=True, exist_ok=True)
    (payload / "npz" / "metadata.json").write_text('{"format_version": 2}')
    assert rel.verify_payload(payload) == []


def test_verify_flags_missing_version(tmp_path):
    payload = tmp_path / "p"
    _write_norms_psd(payload / "norms_psd.npz", version=None, p97_5=2.0)
    (payload / "npz").mkdir(parents=True, exist_ok=True)
    (payload / "npz" / "metadata.json").write_text("{}")
    problems = rel.verify_payload(payload)
    assert any("psd_format_version" in p for p in problems)


def test_verify_flags_inflated_magnitude(tmp_path):
    payload = tmp_path / "p"
    _write_norms_psd(payload / "norms_psd.npz", version=2, p97_5=13.0)
    (payload / "npz").mkdir(parents=True, exist_ok=True)
    (payload / "npz" / "metadata.json").write_text("{}")
    problems = rel.verify_payload(payload)
    assert any("magnitude" in p for p in problems)


def test_verify_flags_missing_band_metadata(tmp_path):
    payload = tmp_path / "p"
    _write_norms_psd(payload / "norms_psd.npz", version=2, p97_5=2.0)
    problems = rel.verify_payload(payload)
    assert any("metadata.json" in p for p in problems)


try:
    import boto3
    from moto import mock_aws
except ImportError:
    boto3 = None
    mock_aws = None

needs_aws = pytest.mark.skipif(boto3 is None, reason="boto3/moto not installed")


@needs_aws
@mock_aws
def test_publish_uploads_and_writes_latest(tmp_path):
    payload = _make_payload(tmp_path)
    manifest = rel.build_release_manifest(
        version="0.2.0", payload_dir=payload, datasets=[], merge_run_id="m",
        code={"git_sha": "x", "git_tag": "v0.2.0", "image": None},
        format_versions={"norms_npz": 2, "psd": 2}, s3_base="s3://bbb/releases/v0.2.0/",
        builder="local:test",
    )
    rel.write_release_json(manifest, payload)

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bbb")

    rel.publish_to_s3(s3, "bbb", "0.2.0", payload, manifest)

    keys = {o["Key"] for o in s3.list_objects_v2(Bucket="bbb").get("Contents", [])}
    assert "releases/v0.2.0/norms_psd.npz" in keys
    assert "releases/v0.2.0/npz/scalp_power.npz" in keys
    assert "releases/v0.2.0/release.json" in keys

    rel.update_latest_json(s3, "bbb", "0.2.0", manifest)
    latest = json.loads(
        s3.get_object(Bucket="bbb", Key="releases/latest.json")["Body"].read()
    )
    assert latest["latest"] == "v0.2.0"
    assert latest["release_json"] == "s3://bbb/releases/v0.2.0/release.json"


@needs_aws
@mock_aws
def test_publish_refuses_to_overwrite_existing_version(tmp_path):
    payload = _make_payload(tmp_path)
    manifest = rel.build_release_manifest(
        version="0.2.0", payload_dir=payload, datasets=[], merge_run_id="m",
        code={"git_sha": "x", "git_tag": "v0.2.0", "image": None},
        format_versions={"norms_npz": 2, "psd": 2}, s3_base="s3://bbb/releases/v0.2.0/",
        builder="local:test",
    )
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="bbb")
    s3.put_object(Bucket="bbb", Key="releases/v0.2.0/sentinel", Body=b"x")
    with pytest.raises(FileExistsError):
        rel.publish_to_s3(s3, "bbb", "0.2.0", payload, manifest)


import argparse as _argparse
import sys as _sys

_CR_SPEC = _ilu.spec_from_file_location(
    "cloud_recompute_t", Path(__file__).resolve().parent.parent / "scripts" / "cloud_recompute.py"
)
cr = _ilu.module_from_spec(_CR_SPEC)
_sys.modules["cloud_recompute_t"] = cr
_CR_SPEC.loader.exec_module(cr)


def test_resolve_run_id_honors_explicit():
    args = _argparse.Namespace(run_id="release-v0.2.0-lemon-37ch", dataset="lemon", channels=37)
    assert cr._resolve_run_id(args) == "release-v0.2.0-lemon-37ch"


def test_resolve_run_id_falls_back_to_timestamped():
    args = _argparse.Namespace(run_id=None, dataset="lemon", channels=37)
    assert cr._resolve_run_id(args).startswith("lemon-37ch-")


_REL_CLI = _ilu.spec_from_file_location(
    "release_cli", Path(__file__).resolve().parent.parent / "scripts" / "release.py"
)
relcli = _ilu.module_from_spec(_REL_CLI)
import sys as _sys
_sys.modules["release_cli"] = relcli
_REL_CLI.loader.exec_module(relcli)


def test_cli_assemble_generates_npz_split(tmp_path, monkeypatch):
    """assemble() must regenerate the npz/ band-level split from norms.json."""
    merged = tmp_path / "merged"
    merged.mkdir()
    _write_norms_psd(merged / "norms_psd.npz", version=2, p97_5=2.0)
    (merged / "norms.json").write_text("[]")

    called = {}

    def fake_write_npz(cells, output_dir):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "metadata.json").write_text('{"format_version": 2}')
        called["dir"] = str(output_dir)
        return {}

    monkeypatch.setattr(relcli, "write_norms_npz", fake_write_npz)
    monkeypatch.setattr(relcli, "read_norms_json", lambda p: [])

    payload = tmp_path / "payload"
    relcli.assemble(merged_dir=merged, payload_dir=payload)

    assert (payload / "norms_psd.npz").exists()
    assert (payload / "npz" / "metadata.json").exists()
    assert called["dir"].endswith("npz")
