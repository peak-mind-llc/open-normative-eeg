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

# cloud_recompute is a script, not a package module — load it by path.
# Register in sys.modules BEFORE exec so dataclass introspection (Config) works
# under Python 3.10's importlib (cls.__module__ would otherwise be None).
_CR_SPEC = importlib.util.spec_from_file_location(
    "cloud_recompute", REPO_ROOT / "scripts" / "cloud_recompute.py"
)
cloud_recompute = importlib.util.module_from_spec(_CR_SPEC)
sys.modules["cloud_recompute"] = cloud_recompute
_CR_SPEC.loader.exec_module(cloud_recompute)

DATASETS_DEFAULT = ["lemon", "dortmund"]
CHANNELS = 37
IMAGE_REPO = "ghcr.io/peak-mind-llc/open-normative-eeg"
SUBMIT_FLAGS = ["--channels", str(CHANNELS), "--condition", "both",
                "--source", "--ba-connectivity", "--dk-connectivity", "--save-psd"]


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def rebuild_dataset(version: str, ds: str, cfg, force: bool = False) -> str:
    """Submit a per-dataset cloud run (idempotent) and return its run_id.

    Idempotent by run_id: if a submission manifest for this version+dataset
    already exists, reuse it (skip resubmission) unless force=True. The manifest
    is written at submit time, so a previously-failed run is reused too — pass
    --force-rebuild to resubmit from scratch.
    """
    v = rel.normalize_version(version)
    run_id = f"release-v{v}-{ds}-{CHANNELS}ch"
    existing = cloud_recompute._read_submission_manifest(cfg, run_id)
    if force or existing is None:
        _run([sys.executable, "scripts/cloud_recompute.py", "submit",
              "--dataset", ds, "--run-id", run_id, *SUBMIT_FLAGS, "--follow"])
    else:
        print(f"reusing existing run {run_id} "
              f"(submitted {existing.get('submitted_at', '?')}); "
              f"pass --force-rebuild to redo")
    return run_id


def download_run(run_id: str, dest: Path, cfg) -> None:
    """Sync a run's per-subject checkpoints into dest/subjects + dest/psd_checkpoints.

    The local cross-dataset merge needs the per-subject JSON + PSD checkpoints,
    which live at runs/<run_id>/subjects/ and runs/<run_id>/psd_checkpoints/ on S3
    (batch_entrypoint.sh writes them there via --checkpoint-sync; the per-dataset
    merged norms go to runs/<run_id>/out/). cloud_recompute's `download` subcommand
    only fetches out/, so sync these two prefixes directly.
    """
    base = f"s3://{cfg.bucket}/{cfg.runs_prefix}{run_id}"
    for sub in ("subjects", "psd_checkpoints"):
        (dest / sub).mkdir(parents=True, exist_ok=True)
        cmd = ["aws", "s3", "sync", f"{base}/{sub}/", str(dest / sub),
               "--region", cfg.region, "--no-progress"]
        if cfg.profile:
            cmd += ["--profile", cfg.profile]
        _run(cmd)


def merge_local(src_dirs: list[Path], merged_dir: Path) -> None:
    """Cross-dataset merge runs LOCALLY via build_norms --merge."""
    cmd = [sys.executable, "scripts/build_norms.py", "--merge"]
    for d in src_dirs:
        cmd += ["--merge-dir", str(d / "subjects")]
    cmd += ["--output", str(merged_dir)]
    _run(cmd)


def assemble(*, merged_dir: Path, payload_dir: Path) -> None:
    """Build the cw_payload from a merged-norms output directory.

    build_norms --merge already writes both norms_psd.npz and the npz/ band-level
    split into merged_dir, so we just copy them into the payload — no regeneration.
    """
    payload_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(merged_dir / "norms_psd.npz", payload_dir / "norms_psd.npz")
    npz_dst = payload_dir / "npz"
    if npz_dst.exists():
        shutil.rmtree(npz_dst)
    shutil.copytree(merged_dir / "npz", npz_dst)


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cut a versioned norms release.")
    ap.add_argument("version", help="Release version, e.g. v0.2.0")
    ap.add_argument("--datasets", default=",".join(DATASETS_DEFAULT),
                    help="Comma-separated datasets (default: lemon,dortmund)")
    ap.add_argument("--publish", action="store_true", help="Upload artifacts to S3 + GitHub")
    ap.add_argument("--dry-run", action="store_true", help="Validate/verify; log publish, no writes")
    ap.add_argument("--force-rebuild", action="store_true",
                    help="Resubmit cloud runs even if a manifest for this version exists.")
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
        run_id = rebuild_dataset(v, ds, cfg, force=args.force_rebuild)
        dataset_run_ids[ds] = run_id
        dest = merge_in / ds
        download_run(run_id, dest, cfg)
        src_dirs.append(dest)

    # cross-dataset merge runs LOCALLY (no cloud cross-dataset merge exists)
    merged_dir = REPO_ROOT / "dist" / "merged" / f"v{v}"
    merge_local(src_dirs, merged_dir)

    # 4. assemble payload from the merged output
    dist = REPO_ROOT / "dist" / "releases" / f"v{v}"
    assemble(merged_dir=merged_dir, payload_dir=dist)

    sha = _git_sha()
    ci_run = os.environ.get("GITHUB_RUN_ID")
    if ci_run:
        builder = f"ci:{ci_run}"
        ci_run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                      f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{ci_run}")
    else:
        builder = f"local:{os.environ.get('USER', 'unknown')}"
        ci_run_url = None
    manifest = rel.build_release_manifest(
        version=v, payload_dir=dist,
        datasets=[{"name": d, "channels": CHANNELS,
                   "run_id": dataset_run_ids[d], "source": "cloud run"}
                  for d in datasets],
        merge_run_id="local",   # cross-dataset merge runs locally, not in the cloud
        # image tag matches publish-image.yml (docker metadata-action: 7-char short sha)
        code={"git_sha": sha, "git_tag": f"v{v}", "image": f"{IMAGE_REPO}:{sha[:7]}"},
        format_versions={"norms_npz": 3, "psd": 3},
        s3_base=f"s3://{cfg.bucket}/releases/v{v}/",
        builder=builder,
        ci_run_url=ci_run_url,
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
