# Release & Rebuild Process — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One script (`scripts/release.py`) runs the whole release process (rebuild norms on AWS → assemble the cw_payload → verify), and a tag-triggered CI workflow runs it with `--publish` to drop versioned, hash-verified artifacts that downstream apps read via `release.json`.

**Architecture:** Testable core logic lives in a package module `open_normative/release.py` (version bump, params hash, manifest assembly, the verify gate, S3 publish, `latest.json`). `scripts/release.py` is a thin CLI that sequences the phases and shells out to the existing `scripts/cloud_recompute.py` CLI for the AWS rebuild/download. CI (`.github/workflows/release.yml`) is a thin wrapper that runs the same CLI.

**Tech Stack:** Python 3.10, NumPy, boto3 (+ `moto` for tests), tomllib/regex for version files, `subprocess` to drive `cloud_recompute.py`, GitHub Actions with AWS OIDC.

**Spec:** `docs/superpowers/specs/2026-05-26-release-and-rebuild-process-design.md`

---

## File Structure

- **Create `open_normative/release.py`** — pure, testable functions: `normalize_version`, `bump_version`, `pipeline_params_sha256`, `sha256_file`, `build_release_manifest`, `write_release_json`, `verify_payload`, `publish_to_s3`, `update_latest_json`. No argparse, no subprocess — easy to unit-test.
- **Create `scripts/release.py`** — CLI. Parses `version`, `--publish`, `--dry-run`, `--datasets`; sequences validate→bump→rebuild→assemble→verify→publish; drives `cloud_recompute.py` via subprocess for the rebuild/download.
- **Create `.github/workflows/release.yml`** — tag-triggered (`v*`) wrapper running `scripts/release.py <tag> --publish`.
- **Create `docs/RELEASE.md`** — runbook + consumer contract.
- **Create `CHANGELOG.md`** — Keep-a-Changelog.
- **Create `tests/test_release.py`** — unit tests for `open_normative/release.py` (S3 mocked via `moto`).

Run tests with: `python -m pytest tests/test_release.py -v` (the repo's venv is `.venv/`; use `.venv/bin/python` if `python` is not on PATH).

---

## Task 1: Version helpers (`normalize_version`, `bump_version`, `pipeline_params_sha256`)

**Files:**
- Create: `open_normative/release.py`
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_release.py`:

```python
"""Tests for the release orchestrator core (open_normative/release.py)."""
import json
import hashlib
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
    # name line untouched
    assert 'name = "open-normative-eeg"' in (tmp_path / "pyproject.toml").read_text()


def test_pipeline_params_sha256_is_stable_and_hex():
    h1 = rel.pipeline_params_sha256()
    h2 = rel.pipeline_params_sha256()
    assert h1 == h2                       # deterministic
    assert len(h1) == 64 and int(h1, 16) >= 0  # 64-char hex
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_normative.release'`.

- [ ] **Step 3: Create `open_normative/release.py` with these functions**

```python
"""Core logic for cutting a versioned norms release.

Pure, testable functions used by scripts/release.py (CLI) and the
tag-triggered CI workflow. No argparse, no subprocess here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def normalize_version(version: str) -> str:
    """Strip a leading 'v' and validate X.Y.Z. Returns the bare numeric version."""
    v = version[1:] if version.startswith("v") else version
    if not _SEMVER_RE.match(v):
        raise ValueError(f"version must be X.Y.Z (got {version!r})")
    return v


def bump_version(version: str, repo_root: Path) -> None:
    """Rewrite the version in pyproject.toml and open_normative/__init__.py."""
    v = normalize_version(version)
    pyproject = repo_root / "pyproject.toml"
    text = pyproject.read_text()
    text, n = re.subn(r'(?m)^version\s*=\s*".*"$', f'version = "{v}"', text)
    if n != 1:
        raise ValueError(f"expected exactly one version line in {pyproject}, found {n}")
    pyproject.write_text(text)

    init = repo_root / "open_normative" / "__init__.py"
    itext = init.read_text()
    itext, n = re.subn(r'(?m)^__version__\s*=\s*".*"$', f'__version__ = "{v}"', itext)
    if n != 1:
        raise ValueError(f"expected exactly one __version__ line in {init}, found {n}")
    init.write_text(itext)


def pipeline_params_sha256() -> str:
    """Stable hash of the canonical PIPELINE_PARAMS dict."""
    from open_normative.parameters import PIPELINE_PARAMS
    blob = json.dumps(PIPELINE_PARAMS, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add open_normative/release.py tests/test_release.py
git commit -m "feat(release): version helpers + pipeline params hash"
```

---

## Task 2: Artifact hashing + manifest (`sha256_file`, `build_release_manifest`, `write_release_json`)

**Files:**
- Modify: `open_normative/release.py`
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_release.py`)**

```python
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
    # release.json itself is NOT listed among artifacts
    assert all(a["path"] != "release.json" for a in loaded["artifacts"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -k "sha256 or manifest or release_json" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'sha256_file'`.

- [ ] **Step 3: Add these functions to `open_normative/release.py`**

```python
import datetime as _dt


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_payload_files(payload_dir: Path):
    """All files under payload_dir except release.json, as (relpath, abspath)."""
    for p in sorted(payload_dir.rglob("*")):
        if p.is_file() and p.name != "release.json":
            yield p.relative_to(payload_dir).as_posix(), p


def build_release_manifest(*, version, payload_dir, datasets, merge_run_id,
                           code, format_versions, s3_base, builder,
                           ci_run_url=None):
    v = normalize_version(version)
    artifacts = [
        {"path": rel_path, "bytes": abs_path.stat().st_size,
         "sha256": sha256_file(abs_path)}
        for rel_path, abs_path in _iter_payload_files(payload_dir)
    ]
    return {
        "version": f"v{v}",
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "builder": builder,
        "ci_run_url": ci_run_url,
        "code": code,
        "datasets": datasets,
        "merge_run_id": merge_run_id,
        "pipeline_params_sha256": pipeline_params_sha256(),
        "format_versions": format_versions,
        "artifacts": artifacts,
        "s3_base": s3_base,
    }


def write_release_json(manifest: dict, payload_dir: Path) -> Path:
    out = payload_dir / "release.json"
    out.write_text(json.dumps(manifest, indent=2))
    return out
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -k "sha256 or manifest or release_json" -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add open_normative/release.py tests/test_release.py
git commit -m "feat(release): release.json manifest assembly + artifact hashing"
```

---

## Task 3: The verify gate (`verify_payload`)

**Files:**
- Modify: `open_normative/release.py`
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_release.py`)**

```python
def _write_norms_psd(path, *, version=2, p97_5=2.0, p50_offset=0.0, with_npz_meta=True):
    """Write a minimal norms_psd.npz. percentiles in log10(µV²/Hz)."""
    n_bins, n_cond, n_ch, n_freq, n_pts = 1, 1, 2, 3, 13
    points = [0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99, 99.5]
    mean = np.full((n_bins, n_cond, n_ch, n_freq), 0.5)
    pct = np.zeros((n_bins, n_cond, n_ch, n_freq, n_pts))
    # monotone ramp from -1 up to p97_5, with p50 (index 6) = mean + offset
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
    # p97.5 ~ 13 in log10 => the SRM-class unit bug
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -k verify -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'verify_payload'`.

- [ ] **Step 3: Add `verify_payload` to `open_normative/release.py`**

```python
def verify_payload(payload_dir: Path) -> list[str]:
    """Return a list of verification problems; empty list == passes.

    Mirrors the manual QC done during the percentile-feature work: percentile
    self-checks, the unit-sanity magnitude bound (catches the SRM µV²/Hz bug),
    format-version presence, and that the band-level npz/ split exists.
    """
    import numpy as np

    problems: list[str] = []
    psd_path = payload_dir / "norms_psd.npz"
    if not psd_path.exists():
        return [f"missing {psd_path.name}"]

    d = np.load(psd_path, allow_pickle=False)
    if "psd_format_version" not in d.files or int(d["psd_format_version"]) != 2:
        problems.append("norms_psd.npz: psd_format_version missing or != 2")
    if "percentiles" not in d.files:
        problems.append("norms_psd.npz: missing percentiles array")
    else:
        pct, mean = d["percentiles"], d["mean"]
        p50 = pct[..., 6]
        valid = ~np.isnan(p50)
        if valid.any():
            med_diff = float(np.nanmedian(np.abs(p50[valid] - mean[valid])))
            if med_diff > 0.25:
                problems.append(
                    f"norms_psd.npz: median |p50-mean| {med_diff:.3f} > 0.25 "
                    "(possible skew/contamination)"
                )
            diffs = np.diff(pct, axis=-1)
            if not bool(np.all((diffs >= -1e-4) | np.isnan(diffs))):
                problems.append("norms_psd.npz: percentiles not monotonic")
            # percentiles are log10(µV²/Hz); a clean alpha p97.5 ~2. >6 (1e6 µV²/Hz)
            # is physiologically impossible and signals a unit error.
            if float(np.nanmax(pct[valid])) > 6.0:
                problems.append(
                    "norms_psd.npz: percentile magnitude implausibly high "
                    "(>1e6 µV²/Hz — unit error?)"
                )

    if not (payload_dir / "npz" / "metadata.json").exists():
        problems.append("npz/metadata.json missing (band-level split not generated)")

    return problems
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -k verify -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add open_normative/release.py tests/test_release.py
git commit -m "feat(release): verify gate (percentile self-checks + unit-magnitude bound)"
```

---

## Task 4: S3 publish (`publish_to_s3`, `update_latest_json`)

**Files:**
- Modify: `open_normative/release.py`
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_release.py`)**

```python
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
        format_versions={"norms_npz": 2, "psd": 2}, s3_base="s3://b/releases/v0.2.0/",
        builder="local:test",
    )
    rel.write_release_json(manifest, payload)

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="b")

    rel.publish_to_s3(s3, "b", "0.2.0", payload, manifest)

    keys = {o["Key"] for o in s3.list_objects_v2(Bucket="b").get("Contents", [])}
    assert "releases/v0.2.0/norms_psd.npz" in keys
    assert "releases/v0.2.0/npz/scalp_power.npz" in keys
    assert "releases/v0.2.0/release.json" in keys

    rel.update_latest_json(s3, "b", "0.2.0", manifest)
    latest = json.loads(
        s3.get_object(Bucket="b", Key="releases/latest.json")["Body"].read()
    )
    assert latest["latest"] == "v0.2.0"
    assert latest["release_json"] == "s3://b/releases/v0.2.0/release.json"


@needs_aws
@mock_aws
def test_publish_refuses_to_overwrite_existing_version(tmp_path):
    payload = _make_payload(tmp_path)
    manifest = rel.build_release_manifest(
        version="0.2.0", payload_dir=payload, datasets=[], merge_run_id="m",
        code={"git_sha": "x", "git_tag": "v0.2.0", "image": None},
        format_versions={"norms_npz": 2, "psd": 2}, s3_base="s3://b/releases/v0.2.0/",
        builder="local:test",
    )
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="b")
    s3.put_object(Bucket="b", Key="releases/v0.2.0/sentinel", Body=b"x")
    with pytest.raises(FileExistsError):
        rel.publish_to_s3(s3, "b", "0.2.0", payload, manifest)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -k "publish or latest" -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'publish_to_s3'`.

- [ ] **Step 3: Add to `open_normative/release.py`**

```python
def _releases_prefix(version: str) -> str:
    return f"releases/v{normalize_version(version)}/"


def publish_to_s3(s3, bucket: str, version: str, payload_dir: Path,
                  manifest: dict) -> None:
    """Upload the payload to s3://bucket/releases/vX.Y.Z/. Refuses to overwrite."""
    prefix = _releases_prefix(version)
    existing = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
    if existing.get("KeyCount", 0) > 0:
        raise FileExistsError(
            f"s3://{bucket}/{prefix} already exists — releases are immutable; "
            "bump the version instead of overwriting."
        )
    # release.json first so an interrupted upload is detectable, then the rest.
    for rel_path, abs_path in [("release.json", payload_dir / "release.json")] + \
            list(_iter_payload_files(payload_dir)):
        s3.upload_file(str(abs_path), bucket, prefix + rel_path)


def update_latest_json(s3, bucket: str, version: str, manifest: dict) -> None:
    v = normalize_version(version)
    body = json.dumps({
        "latest": f"v{v}",
        "s3_base": f"s3://{bucket}/releases/v{v}/",
        "release_json": f"s3://{bucket}/releases/v{v}/release.json",
        "updated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }, indent=2).encode()
    s3.put_object(Bucket=bucket, Key="releases/latest.json", Body=body)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -k "publish or latest" -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add open_normative/release.py tests/test_release.py
git commit -m "feat(release): immutable S3 publish + latest.json pointer"
```

---

## Task 5: Add `--run-id` to `cloud_recompute submit`

The orchestrator needs deterministic, reusable run ids (`release-vX.Y.Z-<ds>-37ch`) so a rebuild is idempotent. `submit` currently always auto-generates a timestamped id (`scripts/cloud_recompute.py:389`, `run_id = _make_run_id(args.dataset, args.channels)`).

**Files:**
- Modify: `scripts/cloud_recompute.py` (helper after line 124; submit parser ~line 736; `cmd_submit` line 389)
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_release.py`)**

```python
import argparse as _argparse

_CR_SPEC = _ilu.spec_from_file_location(
    "cloud_recompute_t", Path(__file__).resolve().parent.parent / "scripts" / "cloud_recompute.py"
)
cr = _ilu.module_from_spec(_CR_SPEC)
_CR_SPEC.loader.exec_module(cr)


def test_resolve_run_id_honors_explicit():
    args = _argparse.Namespace(run_id="release-v0.2.0-lemon-37ch", dataset="lemon", channels=37)
    assert cr._resolve_run_id(args) == "release-v0.2.0-lemon-37ch"


def test_resolve_run_id_falls_back_to_timestamped():
    args = _argparse.Namespace(run_id=None, dataset="lemon", channels=37)
    assert cr._resolve_run_id(args).startswith("lemon-37ch-")
```

(Note: `_ilu` is `importlib.util`, imported in Task 6's test block; if running this task first, add `import importlib.util as _ilu` at the top of the test file.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -k resolve_run_id -v`
Expected: FAIL — `AttributeError: ... has no attribute '_resolve_run_id'`.

- [ ] **Step 3: Implement in `scripts/cloud_recompute.py`**

Add the helper right after `_make_run_id` (after line 124):

```python
def _resolve_run_id(args) -> str:
    """Use an explicit --run-id if given, else an auto timestamped id."""
    return getattr(args, "run_id", None) or _make_run_id(args.dataset, args.channels)
```

Add to the `submit` parser (with the other `p_sub.add_argument` calls, ~line 736):

```python
    p_sub.add_argument("--run-id", default=None,
                       help="Explicit run id (default: <dataset>-<channels>ch-<timestamp>). "
                            "Used by the release orchestrator for idempotent named runs.")
```

Change line 389 from `run_id = _make_run_id(args.dataset, args.channels)` to:

```python
    run_id = _resolve_run_id(args)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -k resolve_run_id -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/cloud_recompute.py tests/test_release.py
git commit -m "feat(cloud_recompute): optional --run-id on submit for named idempotent runs"
```

---

## Task 6: CLI orchestrator (`scripts/release.py`)

**Files:**
- Create: `scripts/release.py`
- Test: `tests/test_release.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_release.py`)**

```python
import importlib.util as _ilu

_REL_CLI = _ilu.spec_from_file_location(
    "release_cli", Path(__file__).resolve().parent.parent / "scripts" / "release.py"
)
relcli = _ilu.module_from_spec(_REL_CLI)
_REL_CLI.loader.exec_module(relcli)


def test_cli_assemble_generates_npz_split(tmp_path, monkeypatch):
    """assemble() must regenerate the npz/ band-level split from norms.json."""
    merged = tmp_path / "merged"
    merged.mkdir()
    # a norms.json the io layer can read; assemble must turn it into npz/
    _write_norms_psd(merged / "norms_psd.npz", version=2, p97_5=2.0)
    (merged / "norms.json").write_text("[]")  # empty cell list is enough to exercise the call

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_release.py -k cli -v`
Expected: FAIL — `FileNotFoundError`/`ModuleNotFoundError` loading `scripts/release.py`.

- [ ] **Step 3: Create `scripts/release.py`**

```python
#!/usr/bin/env python3
"""Cut a versioned norms release: rebuild → assemble → verify → (publish).

One command runs the whole process. `--publish` (what CI runs on a tag)
uploads the verified artifacts to S3 and writes latest.json.

    python scripts/release.py v0.2.0             # build + test locally
    python scripts/release.py v0.2.0 --publish   # also publish
    python scripts/release.py v0.2.0 --publish --dry-run
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from open_normative import release as rel
from open_normative.io import read_norms_json, write_norms_npz

# cloud_recompute is a script, not a package module — load it by path.
_CR_SPEC = importlib.util.spec_from_file_location(
    "cloud_recompute", REPO_ROOT / "scripts" / "cloud_recompute.py"
)
cloud_recompute = importlib.util.module_from_spec(_CR_SPEC)
_CR_SPEC.loader.exec_module(cloud_recompute)

DATASETS_DEFAULT = ["lemon", "dortmund"]
CHANNELS = 37
IMAGE_REPO = "ghcr.io/peak-mind-llc/open-normative-eeg"


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


SUBMIT_FLAGS = ["--channels", str(CHANNELS), "--condition", "both",
                "--source", "--ba-connectivity", "--dk-connectivity", "--save-psd"]


def rebuild_dataset(version: str, ds: str, cfg) -> str:
    """Submit a per-dataset cloud run (idempotent) and return its run_id.

    cloud_recompute submits ONE dataset per run; there is no cross-dataset cloud
    merge. We name the run release-vX.Y.Z-<ds>-37ch (via the new --run-id from
    Task 5) and skip resubmission if its _submission.json already exists.
    """
    v = rel.normalize_version(version)
    run_id = f"release-v{v}-{ds}-{CHANNELS}ch"
    if cloud_recompute._read_submission_manifest(cfg, run_id) is None:
        _run([sys.executable, "scripts/cloud_recompute.py", "submit",
              "--dataset", ds, "--run-id", run_id, *SUBMIT_FLAGS, "--follow"])
    else:
        print(f"reusing existing run {run_id}")
    return run_id


def download_run(run_id: str, dest: Path) -> None:
    """Sync a run's out/ (subjects/ + psd_checkpoints/ + norms.*) into dest."""
    _run([sys.executable, "scripts/cloud_recompute.py", "download", run_id,
          "--output", str(dest)])


def merge_local(src_dirs: list[Path], merged_dir: Path) -> None:
    """Cross-dataset merge runs LOCALLY via build_norms --merge.

    Each src_dir is a downloaded run's out/ holding subjects/ + psd_checkpoints/.
    Produces norms.json + norms_psd.npz (the npz/ split is regenerated in assemble).
    """
    cmd = [sys.executable, "scripts/build_norms.py", "--merge"]
    for d in src_dirs:
        cmd += ["--merge-dir", str(d / "subjects")]
    cmd += ["--output", str(merged_dir)]
    _run(cmd)


def assemble(*, merged_dir: Path, payload_dir: Path) -> None:
    """Build the cw_payload from a merged-norms output directory.

    The merge produces norms.json + norms_psd.npz but NOT the npz/ split, so we
    regenerate the split here from norms.json via write_norms_npz.
    """
    payload_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(merged_dir / "norms_psd.npz", payload_dir / "norms_psd.npz")
    if (merged_dir / "MANIFEST.txt").exists():
        shutil.copy2(merged_dir / "MANIFEST.txt", payload_dir / "MANIFEST.txt")
    cells = read_norms_json(merged_dir / "norms.json")
    write_norms_npz(cells, payload_dir / "npz")


def _git_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cut a versioned norms release.")
    ap.add_argument("version", help="Release version, e.g. v0.2.0")
    ap.add_argument("--datasets", default=",".join(DATASETS_DEFAULT),
                    help="Comma-separated datasets (default: lemon,dortmund)")
    ap.add_argument("--publish", action="store_true", help="Upload artifacts to S3 + GitHub")
    ap.add_argument("--dry-run", action="store_true", help="Validate/verify; log publish, no writes")
    ap.add_argument("--config", type=Path, default=REPO_ROOT / "aws-config.yaml")
    args = ap.parse_args(argv)

    v = rel.normalize_version(args.version)
    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    cfg = cloud_recompute._load_config(args.config)

    # 1-2. validate + bump
    rel.bump_version(v, REPO_ROOT)

    # 3. rebuild: per-dataset cloud run (idempotent) + download each
    merge_in = REPO_ROOT / "dist" / "merge_in" / f"v{v}"
    dataset_run_ids = {}
    src_dirs = []
    for ds in datasets:
        run_id = rebuild_dataset(v, ds, cfg)
        dataset_run_ids[ds] = run_id
        dest = merge_in / ds
        download_run(run_id, dest)
        src_dirs.append(dest)

    # cross-dataset merge runs LOCALLY (no cloud cross-dataset merge exists)
    merged_dir = REPO_ROOT / "dist" / "merged" / f"v{v}"
    merge_local(src_dirs, merged_dir)

    # 4. assemble payload from the merged output
    dist = REPO_ROOT / "dist" / "releases" / f"v{v}"
    assemble(merged_dir=merged_dir, payload_dir=dist)

    # build manifest + write release.json
    manifest = rel.build_release_manifest(
        version=v, payload_dir=dist,
        datasets=[{"name": d, "channels": CHANNELS,
                   "run_id": dataset_run_ids[d], "source": "cloud run"}
                  for d in datasets],
        merge_run_id="local",   # cross-dataset merge runs locally, not in the cloud
        code={"git_sha": _git_sha(), "git_tag": f"v{v}",
              "image": f"{IMAGE_REPO}:{_git_sha()[:12]}"},
        format_versions={"norms_npz": 2, "psd": 2},
        s3_base=f"s3://{cfg.bucket}/releases/v{v}/",
        builder=("ci:" + os.environ["GITHUB_RUN_ID"]) if os.environ.get("CI") else
                ("local:" + os.environ.get("USER", "unknown")),
        ci_run_url=os.environ.get("GITHUB_SERVER_URL", "") and
                   f"{os.environ.get('GITHUB_SERVER_URL')}/{os.environ.get('GITHUB_REPOSITORY')}"
                   f"/actions/runs/{os.environ.get('GITHUB_RUN_ID')}" or None,
    )
    rel.write_release_json(manifest, dist)

    # 5. verify gate
    problems = rel.verify_payload(dist)
    if problems:
        print("VERIFY FAILED:", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 1
    print(f"verify OK — {dist}")

    # 6. publish
    if args.publish:
        if args.dry_run:
            print(f"[dry-run] would publish {dist} to {manifest['s3_base']} + latest.json")
            return 0
        session = cloud_recompute._session(cfg)
        s3 = session.client("s3")
        rel.publish_to_s3(s3, cfg.bucket, v, dist, manifest)
        rel.update_latest_json(s3, cfg.bucket, v, manifest)
        print(f"published: {manifest['s3_base']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_release.py -k cli -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Run the whole release test module + commit**

Run: `python -m pytest tests/test_release.py -v`
Expected: all pass.

```bash
git add scripts/release.py tests/test_release.py
git commit -m "feat(release): CLI orchestrator (rebuild → assemble → verify → publish)"
```

---

## Task 7: Tag-triggered CI workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Create `.github/workflows/release.yml`**

```yaml
name: release
on:
  push:
    tags: ['v*']

permissions:
  id-token: write   # AWS OIDC
  contents: write   # create the GitHub Release

jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 350   # within GitHub's 6h cap; covers the 2-dataset rebuild
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install
        run: pip install -e '.[aws]'
      - name: Configure AWS (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_RELEASE_ROLE_ARN }}
          aws-region: us-east-1
      - name: Cut release
        run: python scripts/release.py "${GITHUB_REF_NAME}" --publish
      - name: GitHub Release
        run: |
          gh release create "${GITHUB_REF_NAME}" \
            --title "${GITHUB_REF_NAME}" \
            --notes-file <(sed -n "/## \[${GITHUB_REF_NAME#v}\]/,/## \[/p" CHANGELOG.md) \
            "dist/releases/${GITHUB_REF_NAME}/release.json"
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml')); print('yaml OK')"`
Expected: `yaml OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci(release): tag-triggered release workflow (OIDC, runs release.py --publish)"
```

---

## Task 8: Runbook + CHANGELOG

**Files:**
- Create: `docs/RELEASE.md`
- Create: `CHANGELOG.md`

- [ ] **Step 1: Create `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are [semver](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-05-26
### Added
- Per-frequency percentiles in `norms_psd.npz` (`psd_format_version: 2`).
- Release process: `scripts/release.py` + tag-triggered CI publishing versioned,
  hash-verified norm bundles to `s3://<bucket>/releases/<version>/` (+ `latest.json`).
- Unit-sanity guard in the norms build.
### Fixed
- SRM EDF unit scaling (`units="uV"`).
```

- [ ] **Step 2: Create `docs/RELEASE.md`**

```markdown
# Cutting a release

## TL;DR
```bash
python scripts/release.py v0.2.0          # build + test locally; inspect dist/releases/v0.2.0
git tag v0.2.0 && git push origin v0.2.0  # CI runs release.py --publish and publishes
```

## What happens
1. `release.py` bumps the version, rebuilds norms on AWS (LEMON+Dortmund, 37ch, `--source`),
   downloads the merged output, assembles the cw_payload (incl. regenerating the `npz/`
   split), and runs the **verify gate** (percentile self-checks, unit-magnitude bound,
   format versions, band-level metadata). A failed gate aborts — nothing publishes.
2. On a `v*` tag, CI runs the same script with `--publish`, uploading to immutable
   `s3://<bucket>/releases/<version>/` and updating `releases/latest.json`, then creates a
   GitHub Release.

## Consumer contract
Downstream apps read `release.json` (pinned at `releases/<version>/release.json`, or follow
`releases/latest.json`). It lists every artifact with `sha256`; verify hashes before loading.
Releases are **immutable** — to fix a bad release, publish a higher version (CI refuses to
overwrite an existing version prefix) and `latest.json` repoints automatically.

## Prerequisites
- `aws-config.yaml` present (see `aws-config.example.yaml`).
- CI secret `AWS_RELEASE_ROLE_ARN` (OIDC role with S3 + Batch access).
```

- [ ] **Step 3: Commit**

```bash
git add docs/RELEASE.md CHANGELOG.md
git commit -m "docs(release): runbook + CHANGELOG"
```

---

## Self-Review

**1. Spec coverage:**
- One script runs the whole process → Task 6 (`scripts/release.py`). ✓
- Idempotent by run_id → named `--run-id` (Task 5) + `rebuild_dataset()` skips when `_read_submission_manifest` already exists (Task 6). ✓
- Verify gate (percentile self-checks, unit-magnitude, format versions, band metadata) → Task 3. ✓
- `release.json` manifest with per-file sha256 → Task 2. ✓
- Immutable S3 `releases/<v>/` + refuse overwrite + `latest.json` → Task 4. ✓
- Tag-triggered CI with OIDC + GitHub Release → Task 7. ✓
- Consumer contract + runbook + CHANGELOG + semver → Task 8. ✓
- Rebuild uses full `--source` flag set → `SUBMIT_FLAGS` in Task 6. ✓
- `assemble` regenerates the `npz/` split (merge doesn't) → `assemble()` + Task 6 Step 1 test. ✓
- Cross-dataset merge is local (no cloud merge) → `merge_local()` (Task 6). ✓

**2. Cloud interface (verified against the real CLI, 2026-05-26):** `submit` is per-dataset and auto-generates a timestamped run_id (`cmd_submit:389`), waits via `--follow` (not `--wait`), and has no cross-dataset merge — so Task 5 adds `--run-id` and Task 6 does the cross-dataset merge locally via `build_norms --merge`. `download <run_id> --output <dir>` syncs the run's `out/` (which contains `subjects/` + `psd_checkpoints/`), so `merge_local` points `--merge-dir` at `<dir>/subjects`. No remaining guesses.

**3. Placeholder scan:** No TBD/TODO/"similar to". Every code step has complete code.

**4. Type consistency:** `normalize_version` returns bare `X.Y.Z`; manifest/keys use `vX.Y.Z` (`build_release_manifest` prepends `v`). `verify_payload` returns `list[str]` (empty == pass); the CLI treats non-empty as failure. `publish_to_s3(s3, bucket, version, payload_dir, manifest)` matches its test and CLI call. `assemble(*, merged_dir, payload_dir)` and `rebuild_dataset(version, ds, cfg)` / `download_run(run_id, dest)` / `merge_local(src_dirs, merged_dir)` are consistent across Task 6's code and tests. `cloud_recompute._resolve_run_id(args)` (Task 5) is called by `submit` and unit-tested.
