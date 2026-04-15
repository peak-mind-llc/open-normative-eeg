#!/usr/bin/env python3
"""Download SRM Resting-state EEG dataset from OpenNeuro (ds003775).

111 healthy adults ages 17-71, 64-channel BioSemi ActiveTwo, EDF format.
Eyes-closed resting state, 4 minutes. CC0 license.

Data layout on S3:
    s3://openneuro.org/ds003775/
        participants.tsv
        sub-001/ses-t1/eeg/sub-001_ses-t1_task-resteyesc_eeg.edf
        sub-001/ses-t1/eeg/sub-001_ses-t1_task-resteyesc_eeg.json
        sub-001/ses-t1/eeg/sub-001_ses-t1_task-resteyesc_channels.tsv
        ...

Usage:
    python scripts/srm_download.py ~/Data/EEG/SRM

    # Dry run
    python scripts/srm_download.py ~/Data/EEG/SRM --dry-run

    # First 10 subjects
    python scripts/srm_download.py ~/Data/EEG/SRM --max-subjects 10

Reference: Hatlestad-Hall et al. (2020). European Journal of Neuroscience.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("srm_download")

S3_BUCKET = "s3://openneuro.org/ds003775"


def run_aws(args, dry_run=False, capture=False):
    """Run an AWS CLI command with --no-sign-request."""
    cmd = ["aws", "s3"] + args + ["--no-sign-request"]
    if dry_run:
        logger.info("  [dry-run] %s", " ".join(cmd))
        return ""
    try:
        result = subprocess.run(
            cmd, capture_output=capture, text=True, check=True,
        )
        return result.stdout if capture else ""
    except subprocess.CalledProcessError as e:
        logger.error("AWS CLI failed: %s\nstderr: %s", " ".join(cmd), e.stderr)
        raise
    except FileNotFoundError:
        logger.error(
            "AWS CLI not found. Install it:\n"
            "  pip install awscli\n"
            "  # or: brew install awscli"
        )
        sys.exit(1)


def list_subjects():
    """List subject directories on S3."""
    logger.info("Listing subjects on S3...")
    output = run_aws(["ls", f"{S3_BUCKET}/"], capture=True)
    subjects = []
    for line in output.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        dirname = parts[-1].rstrip("/")
        if dirname.startswith("sub-"):
            subjects.append(dirname)
    return sorted(subjects)


def download_participants(dest_dir, dry_run=False):
    """Download participants.tsv."""
    dest = dest_dir / "participants.tsv"
    if dest.exists() and not dry_run:
        logger.info("participants.tsv already exists, skipping")
        return dest
    logger.info("Downloading participants.tsv...")
    run_aws(["cp", f"{S3_BUCKET}/participants.tsv", str(dest)], dry_run=dry_run)
    return dest


def download_subject(dest_dir, sid, dry_run=False, max_retries=3):
    """Download session t1 EEG data for one subject."""
    local_eeg = dest_dir / sid / "ses-t1" / "eeg"

    # Check if already downloaded
    if local_eeg.exists() and any(local_eeg.glob("*.edf")):
        return "skipped"

    s3_src = f"{S3_BUCKET}/{sid}/ses-t1/eeg/"
    local_dest = str(local_eeg) + "/"
    local_eeg.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            run_aws(["sync", s3_src, local_dest], dry_run=dry_run)
            if dry_run or any(local_eeg.glob("*.edf")):
                return "downloaded"
        except Exception as e:
            wait = 2 ** (attempt + 1)
            logger.warning("  Retry %d/%d after %ds: %s", attempt + 1, max_retries, wait, e)
            time.sleep(wait)

    return "error"


def download_subjects(dest_dir, subjects, dry_run=False, parallel=8):
    """Download EEG data for all subjects using parallel threads."""
    total = len(subjects)
    downloaded = 0
    skipped = 0
    errors = 0
    start = time.time()
    completed = 0

    logger.info("Downloading with %d parallel threads", parallel)

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        futures = {
            pool.submit(download_subject, dest_dir, sid, dry_run): sid
            for sid in subjects
        }
        for future in as_completed(futures):
            sid = futures[future]
            completed += 1
            try:
                result = future.result()
            except Exception as e:
                result = "error"
                logger.error("  %s: exception: %s", sid, e)

            if result == "skipped":
                skipped += 1
            elif result == "downloaded":
                downloaded += 1
                elapsed = time.time() - start
                rate = downloaded / max(elapsed, 1) * 60
                logger.info(
                    "[%d/%d] %s done (%.1f subj/min)",
                    completed, total, sid, rate,
                )
            elif result == "error":
                errors += 1
                logger.error("[%d/%d] %s FAILED", completed, total, sid)

    elapsed = time.time() - start
    logger.info(
        "\nDownload complete: %d downloaded, %d skipped, "
        "%d errors, %.1f min total",
        downloaded, skipped, errors, elapsed / 60,
    )
    return downloaded, skipped, errors


def save_manifest(dest_dir, subjects):
    """Save a download manifest."""
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "ds003775",
        "dataset_name": "SRM Resting-state EEG",
        "n_subjects": len(subjects),
        "subjects": subjects,
        "s3_source": S3_BUCKET,
    }
    path = dest_dir / "download_manifest.json"
    with path.open("w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest saved to %s", path)


def main():
    parser = argparse.ArgumentParser(
        description="Download SRM Resting-state EEG data from OpenNeuro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("dest_dir", type=Path, help="Destination directory")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-subjects", type=int, default=0,
                        help="Limit subjects (0=all)")
    parser.add_argument("-j", "--parallel", type=int, default=8,
                        help="Parallel downloads (default: 8)")
    args = parser.parse_args()

    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    dest_dir = args.dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    download_participants(dest_dir, dry_run=args.dry_run)

    subjects = list_subjects()
    logger.info("Found %d subjects on S3", len(subjects))

    if args.max_subjects > 0:
        subjects = subjects[: args.max_subjects]

    if not subjects:
        logger.error("No subjects found.")
        sys.exit(1)

    # ~31 MB per subject (EDF)
    est_gb = len(subjects) * 31 / 1024
    logger.info(
        "\nDownload plan:\n"
        "  Dataset: SRM Resting-state EEG (ds003775)\n"
        "  Subjects: %d\n"
        "  Estimated size: ~%.1f GB\n"
        "  Destination: %s",
        len(subjects), est_gb, dest_dir,
    )

    if not args.dry_run:
        try:
            response = input("\nProceed? [Y/n] ").strip().lower()
            if response and response != "y":
                logger.info("Aborted.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            logger.info("\nAborted.")
            sys.exit(0)

    downloaded, skipped, errors = download_subjects(
        dest_dir, subjects, dry_run=args.dry_run, parallel=args.parallel,
    )

    save_manifest(dest_dir, subjects)

    if errors:
        logger.warning("%d subjects failed. Re-run to retry.", errors)


if __name__ == "__main__":
    main()
