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


def rebuild_dataset(version: str, ds: str, cfg) -> str:
    """Submit a per-dataset cloud run (idempotent) and return its run_id."""
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
    """Cross-dataset merge runs LOCALLY via build_norms --merge."""
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
        ci_run_url=(f"{os.environ.get('GITHUB_SERVER_URL')}/{os.environ.get('GITHUB_REPOSITORY')}"
                    f"/actions/runs/{os.environ.get('GITHUB_RUN_ID')}")
                   if os.environ.get("CI") else None,
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
