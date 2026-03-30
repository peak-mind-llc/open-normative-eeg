#!/usr/bin/env python3
"""Download HBN EEG data from the FCP-INDI S3 bucket.

Downloads BIDS-formatted EEG data, participants.tsv, and phenotypic
data from s3://fcp-indi/data/Projects/HBN/.

Usage:
    # Download Release 1 EEG data (~200-300 subjects)
    python scripts/hbn_download.py ~/Data/EEG/HBN --release 1

    # Download all releases
    python scripts/hbn_download.py ~/Data/EEG/HBN --release all

    # Dry run — show what would be downloaded
    python scripts/hbn_download.py ~/Data/EEG/HBN --release 1 --dry-run

    # Resume interrupted download
    python scripts/hbn_download.py ~/Data/EEG/HBN --release 1
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

logger = logging.getLogger("hbn_download")

S3_BASE = "s3://fcp-indi/data/Projects/HBN"
S3_EEG = f"{S3_BASE}/BIDS_EEG"
S3_PHENO = f"{S3_BASE}/phenotypic"

# HBN has 11 releases.  Subjects are organized by release on S3 as
# BIDS_EEG/sub-NDARXXXXXXX/ (flat, not release-partitioned), but the
# participants.tsv lists which release each subject belongs to.
# We download participants.tsv first, then filter by release.
TOTAL_RELEASES = 11


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


def download_participants(dest_dir, dry_run=False):
    """Download participants.tsv from the BIDS_EEG directory."""
    dest = dest_dir / "participants.tsv"
    src = f"{S3_EEG}/participants.tsv"
    if dest.exists() and not dry_run:
        logger.info("participants.tsv already exists, skipping")
        return dest
    logger.info("Downloading participants.tsv...")
    run_aws(["cp", src, str(dest)], dry_run=dry_run)
    return dest


def download_phenotypic(dest_dir, dry_run=False):
    """Download phenotypic/assessment data (CBCL, diagnoses, etc.)."""
    pheno_dir = dest_dir / "phenotypic"
    pheno_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Syncing phenotypic data...")
    run_aws(
        ["sync", S3_PHENO, str(pheno_dir), "--exclude", "*.gz"],
        dry_run=dry_run,
    )
    return pheno_dir


def list_s3_subjects():
    """List all subject directories on S3."""
    logger.info("Listing subjects on S3 (this may take a moment)...")
    output = run_aws(
        ["ls", f"{S3_EEG}/", "--recursive"],
        capture=True,
    )
    # Parse subject IDs from paths like "...BIDS_EEG/sub-NDARXXXXX/..."
    subjects = set()
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) < 4:
            continue
        path = parts[3]
        for segment in path.split("/"):
            if segment.startswith("sub-"):
                subjects.add(segment)
                break
    return sorted(subjects)


def estimate_size(subjects):
    """Rough estimate of download size.

    HBN EEG files are ~50-100 MB per subject (128ch, 500 Hz, multiple tasks).
    """
    per_subject_mb = 75  # rough average
    total_gb = len(subjects) * per_subject_mb / 1024
    return total_gb


def load_release_subjects(participants_path, release):
    """Load participants.tsv and filter by release number.

    Returns set of subject IDs for the requested release(s).
    """
    import csv
    subjects = set()
    if not participants_path.exists():
        return subjects

    with participants_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sid = row.get("participant_id", "").strip()
            if not sid:
                continue
            # Check release column if filtering
            if release != "all":
                rel = row.get("release", row.get("Release", "")).strip()
                try:
                    if int(rel) != int(release):
                        continue
                except (ValueError, TypeError):
                    continue
            subjects.add(sid)
    return subjects


def download_subjects(dest_dir, subjects, dry_run=False, max_retries=3):
    """Download EEG data for a list of subjects."""
    eeg_dir = dest_dir
    total = len(subjects)
    downloaded = 0
    skipped = 0
    errors = 0
    start = time.time()

    for i, sid in enumerate(sorted(subjects)):
        sub_dir = eeg_dir / sid
        eeg_subdir = sub_dir / "eeg"

        # Resume: skip if subject directory already has EEG files
        if eeg_subdir.exists() and any(eeg_subdir.iterdir()):
            skipped += 1
            continue

        elapsed = time.time() - start
        rate = (downloaded + 1) / max(elapsed, 1) * 60
        logger.info(
            "[%d/%d] Downloading %s (%.0f subj/min, %d skipped)",
            i + 1, total, sid, rate, skipped,
        )

        s3_src = f"{S3_EEG}/{sid}/"
        sub_dir.mkdir(parents=True, exist_ok=True)

        success = False
        for attempt in range(max_retries):
            try:
                run_aws(
                    ["sync", s3_src, str(sub_dir), "--exclude", "*.gz"],
                    dry_run=dry_run,
                )
                success = True
                break
            except Exception as e:
                wait = 2 ** (attempt + 1)
                logger.warning("  Retry %d/%d after %ds: %s", attempt + 1, max_retries, wait, e)
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


def save_manifest(dest_dir, subjects, release):
    """Save a manifest of what was downloaded."""
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release": release,
        "n_subjects": len(subjects),
        "subjects": sorted(subjects),
        "s3_source": S3_EEG,
    }
    path = dest_dir / "download_manifest.json"
    with path.open("w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest saved to %s", path)


def main():
    parser = argparse.ArgumentParser(
        description="Download HBN EEG data from S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("dest_dir", type=Path, help="Destination directory")
    parser.add_argument(
        "--release", "-r", default="1",
        help="Release number (1-11) or 'all' (default: 1)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument(
        "--max-subjects", type=int, default=0,
        help="Limit number of subjects (0=all, useful for testing)",
    )
    parser.add_argument(
        "--skip-phenotypic", action="store_true",
        help="Skip downloading phenotypic/assessment data",
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
    participants_path = download_participants(dest_dir, dry_run=args.dry_run)

    # Step 2: Download phenotypic data
    if not args.skip_phenotypic:
        download_phenotypic(dest_dir, dry_run=args.dry_run)

    # Step 3: Determine which subjects to download
    if participants_path.exists():
        subjects = load_release_subjects(participants_path, args.release)
        logger.info(
            "Release %s: %d subjects in participants.tsv",
            args.release, len(subjects),
        )
    else:
        # Fallback: list subjects directly from S3
        logger.info("No participants.tsv — listing subjects from S3...")
        all_subjects = list_s3_subjects()
        subjects = set(all_subjects)
        logger.info("Found %d subjects on S3", len(subjects))

    if args.max_subjects > 0:
        subjects = set(sorted(subjects)[: args.max_subjects])

    if not subjects:
        logger.error("No subjects to download.")
        sys.exit(1)

    # Step 4: Estimate size and confirm
    est_gb = estimate_size(subjects)
    logger.info(
        "\nDownload plan:\n"
        "  Release: %s\n"
        "  Subjects: %d\n"
        "  Estimated size: ~%.1f GB\n"
        "  Destination: %s",
        args.release, len(subjects), est_gb, dest_dir,
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

    # Step 5: Download
    downloaded, skipped, errors = download_subjects(
        dest_dir, subjects, dry_run=args.dry_run,
    )

    # Step 6: Save manifest
    save_manifest(dest_dir, subjects, args.release)

    if errors:
        logger.warning("%d subjects failed to download. Re-run to retry.", errors)


if __name__ == "__main__":
    main()
