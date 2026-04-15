#!/usr/bin/env python3
"""Download Dortmund Vital Study EEG data from OpenNeuro (ds005385).

608 healthy adults ages 20-70, 64-channel BrainProducts actiCHamp, BIDS format.
CC BY 4.0 license.

Data layout on S3:
    s3://openneuro.org/ds005385/
        participants.tsv
        sub-001/ses-1/eeg/sub-001_ses-1_task-EyesOpen_acq-pre_eeg.vhdr
        sub-001/ses-1/eeg/sub-001_ses-1_task-EyesClosed_acq-pre_eeg.vhdr
        ...

Usage:
    # Download all subjects
    python scripts/dortmund_download.py ~/Data/EEG/Dortmund

    # Dry run — show what would be downloaded
    python scripts/dortmund_download.py ~/Data/EEG/Dortmund --dry-run

    # Download first 10 subjects (for testing)
    python scripts/dortmund_download.py ~/Data/EEG/Dortmund --max-subjects 10

    # Resume interrupted download (already-downloaded subjects are skipped)
    python scripts/dortmund_download.py ~/Data/EEG/Dortmund

Reference: Getzmann et al. (2024). Scientific Data, 11:988.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("dortmund_download")

S3_BUCKET = "s3://openneuro.org/ds005385"


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


def list_subjects(dry_run=False):
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


def download_subjects(dest_dir, subjects, dry_run=False, max_retries=3):
    """Download EEG data for subjects.

    Only downloads session 1 EEG files (.vhdr, .vmrk, .eeg, .json, .tsv)
    to minimize download size. Skips already-downloaded subjects.
    """
    total = len(subjects)
    downloaded = 0
    skipped = 0
    errors = 0
    start = time.time()

    for i, sid in enumerate(subjects):
        # Check for existing session-1 EEG data
        eeg_dir = dest_dir / sid / "ses-1" / "eeg"
        if eeg_dir.exists() and any(eeg_dir.glob("*.vhdr")):
            skipped += 1
            continue

        elapsed = time.time() - start
        rate = (downloaded + 1) / max(elapsed, 1) * 60
        logger.info(
            "[%d/%d] Downloading %s (%.0f subj/min, %d skipped)",
            i + 1, total, sid, rate, skipped,
        )

        # Sync session 1 EEG directory
        s3_src = f"{S3_BUCKET}/{sid}/ses-1/eeg/"
        local_dest = str(eeg_dir) + "/"
        eeg_dir.mkdir(parents=True, exist_ok=True)

        success = False
        for attempt in range(max_retries):
            try:
                run_aws(["sync", s3_src, local_dest], dry_run=dry_run)
                success = True
                break
            except Exception as e:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "  Retry %d/%d after %ds: %s",
                    attempt + 1, max_retries, wait, e,
                )
                time.sleep(wait)

        if success:
            downloaded += 1
        else:
            errors += 1
            logger.error("  FAILED after %d attempts: %s", max_retries, sid)

    elapsed = time.time() - start
    logger.info(
        "\nDownload complete: %d downloaded, %d skipped (already present), "
        "%d errors, %.1f min total",
        downloaded, skipped, errors, elapsed / 60,
    )
    return downloaded, skipped, errors


def save_manifest(dest_dir, subjects):
    """Save a manifest of what was downloaded."""
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": "ds005385",
        "dataset_name": "Dortmund Vital Study",
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
        description="Download Dortmund Vital Study EEG data from OpenNeuro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("dest_dir", type=Path, help="Destination directory")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument(
        "--max-subjects", type=int, default=0,
        help="Limit number of subjects (0=all, useful for testing)",
    )
    args = parser.parse_args()

    # Setup logging
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    dest_dir = args.dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download participants.tsv
    download_participants(dest_dir, dry_run=args.dry_run)

    # Step 2: List subjects on S3
    subjects = list_subjects(dry_run=args.dry_run)
    logger.info("Found %d subjects on S3", len(subjects))

    if args.max_subjects > 0:
        subjects = subjects[: args.max_subjects]

    if not subjects:
        logger.error("No subjects found.")
        sys.exit(1)

    # Estimate: ~30-50 MB per subject (64ch BrainVision, 2 conditions)
    est_gb = len(subjects) * 40 / 1024
    logger.info(
        "\nDownload plan:\n"
        "  Dataset: Dortmund Vital Study (ds005385)\n"
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

    # Step 3: Download
    downloaded, skipped, errors = download_subjects(
        dest_dir, subjects, dry_run=args.dry_run,
    )

    # Step 4: Save manifest
    save_manifest(dest_dir, subjects)

    if errors:
        logger.warning("%d subjects failed. Re-run to retry.", errors)


if __name__ == "__main__":
    main()
