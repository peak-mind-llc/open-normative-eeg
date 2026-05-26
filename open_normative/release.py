"""Core logic for cutting a versioned norms release.

Pure, testable functions used by scripts/release.py (CLI) and the
tag-triggered CI workflow. No argparse, no subprocess here.
"""
from __future__ import annotations

import datetime as _dt
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
            if float(np.nanmax(pct[valid])) > 6.0:
                problems.append(
                    "norms_psd.npz: percentile magnitude implausibly high "
                    "(>1e6 µV²/Hz — unit error?)"
                )

    if not (payload_dir / "npz" / "metadata.json").exists():
        problems.append("npz/metadata.json missing (band-level split not generated)")

    return problems


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
    # release.json first (clients validate the other files against it), then the
    # payload files (_iter_payload_files excludes release.json to avoid a dup).
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
