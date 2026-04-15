#!/usr/bin/env python3
"""Build individual Desikan-Killiany parcel labels for full DK connectivity.

Creates dk_labels_{n}ch.pkl with all 68 individual DK parcels (34 per hemi)
from the fsaverage 'aparc' annotation. These are used alongside the existing
18 merged functional ROI labels for expanded connectivity analysis.

Usage:
    python scripts/build_dk_labels.py
    python scripts/build_dk_labels.py --channels 37
"""

from __future__ import annotations

import argparse
import os
import pickle
import sys
from pathlib import Path

import mne

DATA_DIR = Path(__file__).resolve().parent.parent / "open_normative" / "data"
SOURCE_DIR = DATA_DIR / "source"


def build_dk_labels(n_channels: int) -> tuple[list, list[str]]:
    """Build individual DK parcel labels for a given channel config.

    Returns
    -------
    labels : list[mne.Label]
        One Label per DK parcel (68 total: 34 lh + 34 rh).
    dk_names : list[str]
        Parcel name per label (e.g. "superiorfrontal-lh").
    """
    src_path = SOURCE_DIR / f"src_{n_channels}ch.fif"
    if not src_path.exists():
        print(f"ERROR: source space not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    # We need fsaverage's label directory. MNE ships it via fetch_fsaverage.
    fsaverage_dir = str(mne.datasets.fetch_fsaverage(verbose=False))

    # The subjects_dir is the parent of the fsaverage directory
    subjects_dir = os.path.dirname(fsaverage_dir)
    # But fetch_fsaverage returns the path to the fsaverage dir itself,
    # so subjects_dir should be its parent
    if os.path.basename(fsaverage_dir) == "fsaverage":
        subjects_dir = os.path.dirname(fsaverage_dir)
    else:
        subjects_dir = fsaverage_dir

    print(f"  Reading DK parcellation from {fsaverage_dir}")

    labels = mne.read_labels_from_annot(
        "fsaverage", parc="aparc",
        subjects_dir=subjects_dir, verbose=False,
    )

    # Filter out 'unknown' labels
    labels = [l for l in labels if "unknown" not in l.name.lower()]
    labels = sorted(labels, key=lambda l: l.name)

    dk_names = [l.name for l in labels]

    print(f"  {n_channels}ch: {len(labels)} DK parcels")
    for l in labels:
        print(f"    {l.name}: {len(l.vertices)} vertices")

    return labels, dk_names


def main():
    parser = argparse.ArgumentParser(
        description="Build individual DK parcel labels for full connectivity.",
    )
    parser.add_argument(
        "--channels", type=int, choices=[19, 37], default=None,
        help="Channel count (default: build both 19 and 37).",
    )
    args = parser.parse_args()

    channel_counts = [args.channels] if args.channels else [19, 37]

    for n_ch in channel_counts:
        print(f"\nBuilding DK labels for {n_ch}-channel configuration...")
        labels, dk_names = build_dk_labels(n_ch)

        out_path = SOURCE_DIR / f"dk_labels_{n_ch}ch.pkl"
        with open(out_path, "wb") as f:
            pickle.dump({"labels": labels, "dk_names": dk_names}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Saved: {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
