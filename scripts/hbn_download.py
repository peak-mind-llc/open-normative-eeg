#!/usr/bin/env python3
"""Download HBN EEG data from the FCP-INDI S3 bucket.

Downloads BIDS-formatted EEG data, participants.tsv, and phenotypic
data from s3://fcp-indi/data/Projects/HBN/.

The BIDS EEG data on S3 is organized into release subdirectories::

    s3://fcp-indi/data/Projects/HBN/BIDS_EEG/
        cmi_bids_R1/    # Release 1 - ~136 subjects
        cmi_bids_R2/    # Release 2 - ~154 subjects
        ...
        cmi_bids_R11/   # Release 11 - ~430 subjects

Each release directory contains participants.tsv and subject folders
with .set (EEGLAB format) EEG files (NOT .mff EGI native)::

    cmi_bids_R1/
        participants.tsv
        sub-NDARXXXXXXX/
            eeg/
                sub-NDARXXXXXXX_task-RestingState_eeg.set
                sub-NDARXXXXXXX_task-RestingState_eeg.json
                sub-NDARXXXXXXX_task-RestingState_channels.tsv
                sub-NDARXXXXXXX_task-RestingState_events.tsv

Usage:
    # Download Release 1 EEG data (~136 subjects)
    python scripts/hbn_download.py ~/Data/EEG/HBN --release 1

    # Download all releases (R1-R11)
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
# BIDS_EEG/cmi_bids_R{n}/sub-NDARXXXXXXX/.  Each release directory
# has its own participants.tsv.  Files are .set (EEGLAB format).
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


def s3_release_prefix(release_num):
    """Return the S3 prefix for a given release number."""
    return f"{S3_EEG}/cmi_bids_R{release_num}"


def download_participants(dest_dir, release, dry_run=False):
    """Download participants.tsv from the release-specific subdirectory.

    For a single release, downloads from cmi_bids_R{release}/participants.tsv.
    For 'all', downloads from each release directory.
    """
    if release == "all":
        releases = range(1, TOTAL_RELEASES + 1)
    else:
        releases = [int(release)]

    paths = []
    for rel in releases:
        release_dir = dest_dir / f"cmi_bids_R{rel}"
        release_dir.mkdir(parents=True, exist_ok=True)
        dest = release_dir / "participants.tsv"
        src = f"{s3_release_prefix(rel)}/participants.tsv"
        if dest.exists() and not dry_run:
            logger.info("participants.tsv for R%d already exists, skipping", rel)
        else:
            logger.info("Downloading participants.tsv for R%d...", rel)
            try:
                run_aws(["cp", src, str(dest)], dry_run=dry_run)
            except Exception:
                logger.warning("Could not download participants.tsv for R%d", rel)
        paths.append(dest)
    return paths


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


def list_s3_subjects(release_num=None):
    """List subject directories on S3 for a given release (or all).

    Parameters
    ----------
    release_num : int or None
        If given, list subjects under cmi_bids_R{release_num}/.
        If None, list across all release directories.
    """
    if release_num is not None:
        prefixes = [f"{s3_release_prefix(release_num)}/"]
    else:
        prefixes = [f"{s3_release_prefix(r)}/" for r in range(1, TOTAL_RELEASES + 1)]

    subjects = set()
    for prefix in prefixes:
        logger.info("Listing subjects at %s ...", prefix)
        try:
            output = run_aws(["ls", prefix], capture=True)
        except Exception:
            logger.warning("Could not list %s", prefix)
            continue
        for line in output.splitlines():
            # `aws s3 ls` on a prefix returns lines like "PRE sub-NDARXXXXX/"
            parts = line.strip().split()
            if not parts:
                continue
            dirname = parts[-1].rstrip("/")
            if dirname.startswith("sub-"):
                subjects.add(dirname)
    return sorted(subjects)


def estimate_size(subjects):
    """Rough estimate of download size.

    HBN EEG .set files are ~50-100 MB per subject (128ch, 500 Hz,
    multiple tasks in EEGLAB .set format).
    """
    per_subject_mb = 75  # rough average
    total_gb = len(subjects) * per_subject_mb / 1024
    return total_gb


def load_release_subjects(dest_dir, release):
    """Determine subjects for a release by listing S3 or parsing participants.tsv.

    For a specific release, lists subject directories from S3 at
    cmi_bids_R{release}/.  Falls back to parsing participants.tsv if
    the S3 listing fails or returns empty.

    For 'all', aggregates across releases 1-11.

    Returns set of (subject_id, release_num) tuples.
    """
    import csv

    if release == "all":
        releases = range(1, TOTAL_RELEASES + 1)
    else:
        releases = [int(release)]

    subjects = set()
    for rel in releases:
        # Primary: list subjects directly from S3
        s3_subjects = list_s3_subjects(release_num=rel)
        if s3_subjects:
            for sid in s3_subjects:
                subjects.add((sid, rel))
            logger.info("R%d: %d subjects found on S3", rel, len(s3_subjects))
            continue

        # Fallback: parse participants.tsv for this release
        participants_path = dest_dir / f"cmi_bids_R{rel}" / "participants.tsv"
        if not participants_path.exists():
            logger.warning("R%d: no subjects found on S3 and no participants.tsv", rel)
            continue

        count = 0
        with participants_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                sid = row.get("participant_id", "").strip()
                if not sid:
                    continue
                subjects.add((sid, rel))
                count += 1
        logger.info("R%d: %d subjects from participants.tsv (S3 listing failed)", rel, count)

    return subjects


def download_subjects(dest_dir, subjects, dry_run=False, max_retries=3):
    """Download EEG data for a list of subjects.

    Parameters
    ----------
    dest_dir : Path
        Local destination root.
    subjects : set of (subject_id, release_num) tuples
        Subjects to download, with their release number so we know
        which S3 prefix to sync from.
    dry_run : bool
    max_retries : int
    """
    total = len(subjects)
    downloaded = 0
    skipped = 0
    errors = 0
    start = time.time()

    for i, (sid, rel) in enumerate(sorted(subjects)):
        sub_dir = dest_dir / sid
        eeg_subdir = sub_dir / "eeg"

        # Resume: skip if subject directory already has EEG files
        if eeg_subdir.exists() and any(eeg_subdir.iterdir()):
            skipped += 1
            continue

        elapsed = time.time() - start
        rate = (downloaded + 1) / max(elapsed, 1) * 60
        logger.info(
            "[%d/%d] Downloading %s (R%d, %.0f subj/min, %d skipped)",
            i + 1, total, sid, rel, rate, skipped,
        )

        s3_src = f"{s3_release_prefix(rel)}/{sid}/"
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


def download_metadata(dest_dir, dry_run=False):
    """Try to download HBN metadata CSV (contains Commercial_Use column, etc.).

    Tries several known paths on S3 and also syncs any top-level CSV
    files from the HBN project directory.
    """
    metadata_dir = dest_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Known candidate paths for the metadata file
    candidates = [
        f"{S3_BASE}/HBN_Metadata.csv",
        f"{S3_BASE}/HBN_R1_Participan_Data_Tables.csv",
        f"{S3_BASE}/HBN_R1_Participant_Data_Tables.csv",
    ]

    for src in candidates:
        fname = src.rsplit("/", 1)[-1]
        dest = metadata_dir / fname
        if dest.exists() and not dry_run:
            logger.info("Metadata file %s already exists, skipping", fname)
            continue
        logger.info("Trying to download %s ...", src)
        try:
            run_aws(["cp", src, str(dest)], dry_run=dry_run)
            logger.info("  Downloaded %s", fname)
        except Exception:
            logger.info("  Not found: %s", src)

    # Also sync any CSVs from the base HBN directory
    logger.info("Syncing top-level CSV files from %s ...", S3_BASE)
    try:
        run_aws(
            [
                "sync", f"{S3_BASE}/", str(metadata_dir),
                "--exclude", "*",
                "--include", "*.csv",
                "--include", "*.CSV",
            ],
            dry_run=dry_run,
        )
    except Exception:
        logger.warning("Could not sync CSV files from %s", S3_BASE)

    return metadata_dir


def save_manifest(dest_dir, subjects, release):
    """Save a manifest of what was downloaded."""
    # subjects is a set of (subject_id, release_num) tuples
    subject_list = sorted(sid for sid, _rel in subjects)
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "release": release,
        "n_subjects": len(subject_list),
        "subjects": subject_list,
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
    parser.add_argument(
        "--skip-metadata", action="store_true",
        help="Skip downloading HBN metadata CSV files",
    )
    args = parser.parse_args()

    # Setup logging
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    dest_dir = args.dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download participants.tsv (per-release)
    download_participants(dest_dir, args.release, dry_run=args.dry_run)

    # Step 2: Download phenotypic data
    if not args.skip_phenotypic:
        download_phenotypic(dest_dir, dry_run=args.dry_run)

    # Step 2b: Download metadata CSV files
    if not args.skip_metadata:
        download_metadata(dest_dir, dry_run=args.dry_run)

    # Step 3: Determine which subjects to download
    subjects = load_release_subjects(dest_dir, args.release)
    logger.info(
        "Release %s: %d subjects found",
        args.release, len(subjects),
    )

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
