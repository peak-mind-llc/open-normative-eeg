#!/usr/bin/env python3
"""Download LEMON EEG dataset from the GWDG FTP server.

227 healthy adults ages 20-77, 62-channel BrainVision, BIDS format.
Leipzig Study for Mind-Body-Emotion Interactions.

Data layout on FTP:
    https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON/
        EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID/
            sub-032301/eeg/sub-032301.vhdr  (single-file, marker-split EO/EC)
            ...
        Behavioural_Data_MPILMBB_LEMON/
            META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv

Usage:
    # Download all subjects
    python scripts/lemon_download.py ~/Data/EEG/LEMON

    # Download first 10 subjects (for testing)
    python scripts/lemon_download.py ~/Data/EEG/LEMON --max-subjects 10

    # Dry run
    python scripts/lemon_download.py ~/Data/EEG/LEMON --dry-run

    # Resume interrupted download (skips existing subjects)
    python scripts/lemon_download.py ~/Data/EEG/LEMON

Reference: Babayan et al. (2019). Scientific Data, 6, 180308.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

logger = logging.getLogger("lemon_download")

FTP_BASE = "https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON"
EEG_BASE = f"{FTP_BASE}/EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID"
META_BASE = f"{FTP_BASE}/Behavioural_Data_MPILMBB_LEMON"
META_CSV = "META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"


class LinkParser(HTMLParser):
    """Extract href links from an FTP directory listing."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


def list_ftp_dir(url):
    """List entries in an FTP/HTTP directory listing."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lemon-download/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.error("Failed to list %s: %s", url, e)
        return []

    parser = LinkParser()
    parser.feed(html)
    return parser.links


def list_subjects():
    """List subject directories from the LEMON FTP."""
    logger.info("Listing subjects on FTP...")
    links = list_ftp_dir(f"{EEG_BASE}/")

    subjects = []
    for link in links:
        name = link.rstrip("/").split("/")[-1]
        if name.startswith("sub-"):
            subjects.append(name)

    return sorted(set(subjects))


def wget_download_file(url, dest_path, dry_run=False, tries=3):
    """Download a single file using wget with resume support."""
    cmd = [
        "wget", "-q", "--show-progress",
        "-c",  # resume partial downloads
        "-O", str(dest_path),
        f"--tries={tries}",
        "--timeout=120",
        "--waitretry=5",
        url,
    ]
    if dry_run:
        logger.info("  [dry-run] %s", " ".join(cmd))
        return True
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("  wget failed (exit %d) for %s", e.returncode, url)
        return False
    except FileNotFoundError:
        logger.error(
            "wget not found. Install it:\n"
            "  brew install wget      # macOS\n"
            "  apt install wget       # Linux"
        )
        sys.exit(1)


def download_meta(dest_dir, dry_run=False):
    """Download the demographics META CSV."""
    dest = dest_dir / META_CSV
    if dest.exists() and not dry_run:
        logger.info("META CSV already exists, skipping")
        return dest

    logger.info("Downloading demographics META CSV...")
    url = f"{META_BASE}/{META_CSV}"
    wget_download_file(url, dest, dry_run=dry_run)
    return dest


def download_subject(dest_dir, sid, dry_run=False):
    """Download all EEG files for one subject using wget.

    LEMON EEG files are in sub-XXXXXX/RSEEG/ (.vhdr, .vmrk, .eeg).
    wget handles retries, resume, and timeouts natively.
    """
    local_eeg = dest_dir / sid / "RSEEG"

    # Check if already downloaded
    if local_eeg.exists() and any(local_eeg.glob("*.vhdr")):
        return "skipped"

    # List files in RSEEG/ via HTTP directory listing
    sub_eeg_url = f"{EEG_BASE}/{sid}/RSEEG/"
    links = list_ftp_dir(sub_eeg_url)
    eeg_files = [
        link.rstrip("/").split("/")[-1]
        for link in links
        if link.rstrip("/").split("/")[-1].endswith((".vhdr", ".vmrk", ".eeg"))
    ]

    if not eeg_files:
        logger.warning("  No EEG files found for %s", sid)
        return "error"

    # Download each file with wget
    all_ok = True
    for fname in eeg_files:
        dest_path = local_eeg / fname
        if dest_path.exists() and dest_path.stat().st_size > 0:
            continue
        url = f"{sub_eeg_url}{fname}"
        if not wget_download_file(url, dest_path, dry_run=dry_run):
            all_ok = False

    return "downloaded" if all_ok else "error"


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
        "dataset": "LEMON",
        "dataset_name": "Leipzig Study for Mind-Body-Emotion Interactions",
        "n_subjects": len(subjects),
        "subjects": subjects,
        "source": EEG_BASE,
    }
    path = dest_dir / "download_manifest.json"
    with path.open("w") as f:
        json.dump(manifest, f, indent=2)
    logger.info("Manifest saved to %s", path)


def main():
    parser = argparse.ArgumentParser(
        description="Download LEMON EEG data from GWDG FTP",
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
    parser.add_argument(
        "-j", "--parallel", type=int, default=8,
        help="Number of parallel downloads (default: 8)",
    )
    parser.add_argument(
        "--skip-meta", action="store_true",
        help="Skip downloading the demographics META CSV",
    )
    args = parser.parse_args()

    # Setup logging
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    dest_dir = args.dest_dir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Download META CSV
    if not args.skip_meta:
        download_meta(dest_dir, dry_run=args.dry_run)

    # Step 2: List subjects
    subjects = list_subjects()
    logger.info("Found %d subjects on FTP", len(subjects))

    if args.max_subjects > 0:
        subjects = subjects[: args.max_subjects]

    if not subjects:
        logger.error("No subjects found.")
        sys.exit(1)

    # Estimate: ~15-25 MB per subject (62ch BrainVision, single file)
    est_gb = len(subjects) * 20 / 1024
    logger.info(
        "\nDownload plan:\n"
        "  Dataset: LEMON (Leipzig Mind-Brain-Body)\n"
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
        parallel=args.parallel,
    )

    # Step 4: Save manifest
    save_manifest(dest_dir, subjects)

    if errors:
        logger.warning("%d subjects failed. Re-run to retry.", errors)


if __name__ == "__main__":
    main()
