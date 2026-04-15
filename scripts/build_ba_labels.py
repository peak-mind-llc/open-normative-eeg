#!/usr/bin/env python3
"""Build Brodmann Area labels on fsaverage surface for BA-to-BA connectivity.

One-time offline script. Maps LORETA voxel BA assignments to fsaverage surface
vertices via nearest-neighbor (KD-tree), then creates mne.Label objects per BA.

Usage:
    python scripts/build_ba_labels.py            # builds both 19ch and 37ch
    python scripts/build_ba_labels.py --channels 37
"""

from __future__ import annotations

import argparse
import csv
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import mne
import numpy as np
from scipy.spatial import cKDTree

DATA_DIR = Path(__file__).resolve().parent.parent / "open_normative" / "data"
SOURCE_DIR = DATA_DIR / "source"

MAX_DISTANCE_MM = 15.0  # max distance from vertex to voxel for assignment
MIN_VERTICES = 10       # minimum vertices for a BA to be included


def _load_ba_voxels() -> tuple[np.ndarray, list[str]]:
    """Load MNI coordinates and BA labels from the LORETA CSV.

    Returns
    -------
    coords : ndarray of shape (2394, 3)
        MNI coordinates in mm.
    ba_labels : list[str]
        BA label per voxel (e.g. "Brodmann area 20").
    """
    csv_path = DATA_DIR / "LORETA-Talairach-BAs.csv"
    coords = []
    ba_labels = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            coords.append([float(row[0]), float(row[1]), float(row[2])])
            ba_labels.append(row[7] if len(row) > 7 else "")
    return np.array(coords, dtype=np.float64), ba_labels


def _sanitize_ba_name(name: str) -> str:
    """Convert 'Brodmann area 20' → 'BA20', keep others as-is."""
    if name.startswith("Brodmann area "):
        return "BA" + name.replace("Brodmann area ", "")
    return name.replace(" ", "_")


def build_ba_labels(n_channels: int) -> tuple[list, list[str]]:
    """Build BA labels for a given channel configuration.

    Parameters
    ----------
    n_channels : int
        19 or 37.

    Returns
    -------
    labels : list[mne.Label]
        One Label per BA, ordered by ba_names.
    ba_names : list[str]
        Sanitized BA name per label (e.g. "BA20").
    """
    src_path = SOURCE_DIR / f"src_{n_channels}ch.fif"
    if not src_path.exists():
        print(f"ERROR: source space not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    src = mne.read_source_spaces(str(src_path), verbose=False)

    # Collect all surface vertex positions in MNI (meters → mm)
    # fsaverage surface coords are in MNI space
    vertex_coords = []  # (x, y, z) in mm
    vertex_hemi = []    # 0 = lh, 1 = rh
    vertex_idx = []     # vertex index within hemisphere
    for hi, hemi in enumerate(src):
        rr_mm = hemi["rr"] * 1000.0  # meters → mm
        for vi in range(len(rr_mm)):
            vertex_coords.append(rr_mm[vi])
            vertex_hemi.append(hi)
            vertex_idx.append(vi)

    vertex_coords = np.array(vertex_coords)
    n_vertices = len(vertex_coords)
    print(f"  {n_channels}ch: {n_vertices} surface vertices across 2 hemispheres")

    # Load LORETA voxel positions and BA assignments
    voxel_coords, voxel_bas = _load_ba_voxels()
    print(f"  {len(voxel_coords)} LORETA voxels loaded")

    # Build KD-tree on LORETA voxels, query for each surface vertex
    tree = cKDTree(voxel_coords)
    distances, indices = tree.query(vertex_coords)

    # Group vertices by BA
    ba_vertices = defaultdict(lambda: {"lh": [], "rh": []})
    n_assigned = 0
    for i in range(n_vertices):
        if distances[i] > MAX_DISTANCE_MM:
            continue
        ba_raw = voxel_bas[indices[i]]
        if not ba_raw:
            continue
        hemi_key = "lh" if vertex_hemi[i] == 0 else "rh"
        ba_vertices[ba_raw][hemi_key].append(vertex_idx[i])
        n_assigned += 1

    print(f"  {n_assigned}/{n_vertices} vertices assigned to a BA "
          f"(within {MAX_DISTANCE_MM}mm)")

    # Create mne.Label objects, filter by minimum vertex count
    labels = []
    ba_names = []

    for ba_raw in sorted(ba_vertices.keys()):
        verts = ba_vertices[ba_raw]
        lh_verts = np.array(sorted(verts["lh"]), dtype=int)
        rh_verts = np.array(sorted(verts["rh"]), dtype=int)
        total = len(lh_verts) + len(rh_verts)

        if total < MIN_VERTICES:
            san = _sanitize_ba_name(ba_raw)
            print(f"  SKIP {san}: only {total} vertices (< {MIN_VERTICES})")
            continue

        san_name = _sanitize_ba_name(ba_raw)

        # Create per-hemisphere labels and combine
        lh_label = rh_label = None
        if len(lh_verts) > 0:
            lh_label = mne.Label(
                lh_verts, hemi="lh", name=f"{san_name}-lh",
                subject="fsaverage",
            )
        if len(rh_verts) > 0:
            rh_label = mne.Label(
                rh_verts, hemi="rh", name=f"{san_name}-rh",
                subject="fsaverage",
            )

        if lh_label is not None and rh_label is not None:
            label = lh_label + rh_label
        elif lh_label is not None:
            label = lh_label
        else:
            label = rh_label

        labels.append(label)
        ba_names.append(san_name)
        print(f"  {san_name}: {total} vertices "
              f"(lh={len(lh_verts)}, rh={len(rh_verts)})")

    print(f"  Total: {len(labels)} BAs with >= {MIN_VERTICES} vertices")
    return labels, ba_names


def main():
    parser = argparse.ArgumentParser(
        description="Build Brodmann Area surface labels for BA-to-BA connectivity.",
    )
    parser.add_argument(
        "--channels", type=int, choices=[19, 37], default=None,
        help="Channel count (default: build both 19 and 37).",
    )
    args = parser.parse_args()

    channel_counts = [args.channels] if args.channels else [19, 37]

    for n_ch in channel_counts:
        print(f"\nBuilding BA labels for {n_ch}-channel configuration...")
        labels, ba_names = build_ba_labels(n_ch)

        out_path = SOURCE_DIR / f"ba_labels_{n_ch}ch.pkl"
        with open(out_path, "wb") as f:
            pickle.dump({"labels": labels, "ba_names": ba_names}, f,
                        protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  Saved: {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
