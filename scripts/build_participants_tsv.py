#!/usr/bin/env python3
"""Build a participants.tsv for BIDS-remapped LEMON data.

The GWDG LEMON download sometimes remaps subject IDs (e.g. sub-032301)
while the .vhdr files internally still reference the original IDs
(e.g. sub-010002).  This script reads each .vhdr, extracts the original
ID from the DataFile= reference, looks it up in the META CSV, and writes
a participants.tsv keyed by the directory (BIDS) ID.

Usage:
    python scripts/build_participants_tsv.py /path/to/EEG_Raw_BIDS_ID

Requires the META CSV to be in the same directory (or parent directory).
"""

import csv
import sys
from pathlib import Path


META_CSV_NAME = "META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"


def load_meta_csv(meta_path):
    """Load the META CSV into a dict keyed by subject ID."""
    participants = {}
    with meta_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            sid = row.get("ID", "").strip()
            if not sid:
                continue
            raw_age = row.get("Age", "").strip()
            raw_gender = row.get("Gender_ 1=female_2=male", "").strip()
            sex = "F" if raw_gender == "1" else "M" if raw_gender == "2" else raw_gender
            participants[sid] = {"age": raw_age, "sex": sex}
    return participants


def extract_original_id(vhdr_path):
    """Get the original subject ID from a .vhdr's DataFile= reference."""
    try:
        for line in vhdr_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DataFile="):
                ref = line.split("=", 1)[1].strip()
                return Path(ref).stem
    except Exception:
        pass
    return None


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} /path/to/EEG_Raw_BIDS_ID", file=sys.stderr)
        sys.exit(1)

    data_dir = Path(sys.argv[1])

    # Find META CSV
    meta_path = None
    for candidate in (data_dir / META_CSV_NAME, data_dir.parent / META_CSV_NAME):
        if candidate.exists():
            meta_path = candidate
            break

    if not meta_path:
        print(f"ERROR: Could not find {META_CSV_NAME} in {data_dir} or {data_dir.parent}",
              file=sys.stderr)
        sys.exit(1)

    meta = load_meta_csv(meta_path)
    print(f"Loaded {len(meta)} subjects from {meta_path.name}", file=sys.stderr)

    # Find all .vhdr files
    vhdr_files = sorted(
        set(data_dir.glob("sub-*/eeg/*.vhdr"))
        | set(data_dir.glob("sub-*/RSEEG/*.vhdr"))
        | set(data_dir.glob("sub-*/ses-*/eeg/*.vhdr"))
    )

    # Build mapping: directory ID → original ID → demographics
    output = data_dir / "participants.tsv"
    matched = 0
    unmatched = 0
    seen = set()

    with output.open("w", newline="") as fh:
        fh.write("participant_id\tage\tsex\toriginal_id\n")
        for vhdr_path in vhdr_files:
            # Extract directory-level subject ID
            dir_id = None
            for part in vhdr_path.parts:
                if part.startswith("sub-"):
                    dir_id = part
            if not dir_id or dir_id in seen:
                continue
            seen.add(dir_id)

            original_id = extract_original_id(vhdr_path) or dir_id
            info = meta.get(dir_id) or meta.get(original_id) or {}

            age = info.get("age", "n/a")
            sex = info.get("sex", "n/a")

            if info:
                matched += 1
            else:
                unmatched += 1

            fh.write(f"{dir_id}\t{age}\t{sex}\t{original_id}\n")

    print(f"Wrote {output}", file=sys.stderr)
    print(f"  {matched} matched, {unmatched} unmatched", file=sys.stderr)

    if unmatched:
        print(f"\nWARNING: {unmatched} subjects had no demographics match.", file=sys.stderr)


if __name__ == "__main__":
    main()
