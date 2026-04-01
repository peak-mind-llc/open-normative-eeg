#!/usr/bin/env python3
"""Cross-dataset agreement validation.

Compares normative statistics from two independently-processed datasets
in overlapping age ranges. If the pipeline is consistent and the
populations are comparable, the normative means should agree closely.

Usage:
    python scripts/validate_cross_dataset.py \
        --dir-a ./norms_lemon/subjects --label-a LEMON \
        --dir-b ./norms_dortmund/subjects --label-b Dortmund \
        --output ./cross_dataset_report.json

    # Custom age bins
    python scripts/validate_cross_dataset.py \
        --dir-a ./norms_lemon/subjects --label-a LEMON \
        --dir-b ./norms_dortmund/subjects --label-b Dortmund \
        --age-bins 20 30 40 50 60 70 80
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_normative.normative import build_normative, _DEFAULT_AGE_BINS

logger = logging.getLogger("validate_cross_dataset")


def load_subjects(subjects_dir: Path) -> list[dict]:
    """Load all subject checkpoint JSONs from a directory."""
    subjects = []
    for fpath in sorted(subjects_dir.glob("*.json")):
        with open(fpath) as f:
            subjects.append(json.load(f))
    return subjects


def compare_datasets(
    subjects_a: list[dict],
    subjects_b: list[dict],
    label_a: str,
    label_b: str,
    age_bins: list[int],
) -> dict:
    """Compare normative distributions from two datasets.

    For each overlapping (bin, condition, channel, band, metric) cell,
    computes:
    - Correlation of means across all cells
    - Mean absolute difference of means
    - Cohen's d between the two datasets' distributions
    - Per-metric and per-bin breakdown

    Returns:
        Comprehensive comparison report dict.
    """
    norms_a = build_normative(subjects_a, age_bins=age_bins)
    norms_b = build_normative(subjects_b, age_bins=age_bins)

    # Index by key
    idx_a = {}
    for c in norms_a:
        if c.n >= 3:
            idx_a[(c.bin, c.condition, c.channel, c.band, c.metric)] = c
    idx_b = {}
    for c in norms_b:
        if c.n >= 3:
            idx_b[(c.bin, c.condition, c.channel, c.band, c.metric)] = c

    # Find common keys
    common_keys = sorted(set(idx_a.keys()) & set(idx_b.keys()))

    if not common_keys:
        return {
            "error": "No overlapping normative cells found",
            "n_cells_a": len(idx_a),
            "n_cells_b": len(idx_b),
            "bins_a": sorted(set(c.bin for c in norms_a)),
            "bins_b": sorted(set(c.bin for c in norms_b)),
        }

    # Global correlation of means
    means_a = [idx_a[k].mean for k in common_keys]
    means_b = [idx_b[k].mean for k in common_keys]
    global_r, global_p = stats.pearsonr(means_a, means_b)

    # Per-cell comparisons
    cell_diffs = []
    for key in common_keys:
        ca = idx_a[key]
        cb = idx_b[key]

        # Cohen's d between the two cells (pooled SD)
        pooled_sd = np.sqrt(
            ((ca.n - 1) * ca.sd**2 + (cb.n - 1) * cb.sd**2)
            / (ca.n + cb.n - 2)
        ) if (ca.sd > 0 or cb.sd > 0) and (ca.n + cb.n > 2) else None

        d = (ca.mean - cb.mean) / pooled_sd if pooled_sd and pooled_sd > 0 else None

        cell_diffs.append({
            "key": key,
            "bin": key[0],
            "condition": key[1],
            "channel": key[2],
            "band": key[3],
            "metric": key[4],
            "mean_a": round(ca.mean, 4),
            "mean_b": round(cb.mean, 4),
            "sd_a": round(ca.sd, 4),
            "sd_b": round(cb.sd, 4),
            "n_a": ca.n,
            "n_b": cb.n,
            "abs_diff": round(abs(ca.mean - cb.mean), 4),
            "cohen_d": round(float(d), 3) if d is not None else None,
        })

    # Per-metric breakdown
    metric_groups = defaultdict(list)
    for cd in cell_diffs:
        metric_groups[cd["metric"]].append(cd)

    per_metric = {}
    for metric, cells in sorted(metric_groups.items()):
        m_a = [c["mean_a"] for c in cells]
        m_b = [c["mean_b"] for c in cells]
        ds = [c["cohen_d"] for c in cells if c["cohen_d"] is not None]

        r, p = stats.pearsonr(m_a, m_b) if len(m_a) >= 3 else (None, None)
        per_metric[metric] = {
            "n_cells": len(cells),
            "correlation_r": round(float(r), 4) if r is not None else None,
            "mean_abs_cohen_d": round(float(np.mean(np.abs(ds))), 3) if ds else None,
            "max_abs_cohen_d": round(float(np.max(np.abs(ds))), 3) if ds else None,
            "agreement": "good" if r is not None and r > 0.90 else (
                "moderate" if r is not None and r > 0.80 else "poor"
            ),
        }

    # Per-bin breakdown
    bin_groups = defaultdict(list)
    for cd in cell_diffs:
        bin_groups[cd["bin"]].append(cd)

    per_bin = {}
    for age_bin, cells in sorted(bin_groups.items()):
        m_a = [c["mean_a"] for c in cells]
        m_b = [c["mean_b"] for c in cells]
        ds = [c["cohen_d"] for c in cells if c["cohen_d"] is not None]

        r, p = stats.pearsonr(m_a, m_b) if len(m_a) >= 3 else (None, None)
        per_bin[age_bin] = {
            "n_cells": len(cells),
            "n_a": cells[0]["n_a"] if cells else 0,
            "n_b": cells[0]["n_b"] if cells else 0,
            "correlation_r": round(float(r), 4) if r is not None else None,
            "mean_abs_cohen_d": round(float(np.mean(np.abs(ds))), 3) if ds else None,
        }

    # Largest disagreements
    sorted_by_d = sorted(
        [c for c in cell_diffs if c["cohen_d"] is not None],
        key=lambda c: abs(c["cohen_d"]),
        reverse=True,
    )
    top_disagreements = [
        {k: v for k, v in c.items() if k != "key"}
        for c in sorted_by_d[:20]
    ]

    return {
        "label_a": label_a,
        "label_b": label_b,
        "n_subjects_a": len(subjects_a),
        "n_subjects_b": len(subjects_b),
        "n_common_cells": len(common_keys),
        "overlapping_bins": sorted(set(k[0] for k in common_keys)),
        "global_correlation": {
            "r": round(float(global_r), 4),
            "p": float(global_p),
            "interpretation": (
                "excellent" if global_r > 0.95 else
                "good" if global_r > 0.90 else
                "moderate" if global_r > 0.80 else
                "poor"
            ),
        },
        "per_metric": per_metric,
        "per_bin": per_bin,
        "top_disagreements": top_disagreements,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Cross-dataset agreement validation",
    )
    parser.add_argument(
        "--dir-a",
        type=Path,
        required=True,
        help="Path to subjects/ checkpoint directory for dataset A",
    )
    parser.add_argument(
        "--label-a",
        default="Dataset_A",
        help="Label for dataset A (e.g., 'LEMON')",
    )
    parser.add_argument(
        "--dir-b",
        type=Path,
        required=True,
        help="Path to subjects/ checkpoint directory for dataset B",
    )
    parser.add_argument(
        "--label-b",
        default="Dataset_B",
        help="Label for dataset B (e.g., 'Dortmund')",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Write comparison report as JSON",
    )
    parser.add_argument(
        "--age-bins",
        type=int,
        nargs="+",
        default=_DEFAULT_AGE_BINS,
        help="Age bin edges (default: decade bins 20-80)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    for d, label in [(args.dir_a, args.label_a), (args.dir_b, args.label_b)]:
        if not d.exists():
            logger.error("%s directory not found: %s", label, d)
            sys.exit(1)

    # Load subjects
    logger.info("Loading %s from %s ...", args.label_a, args.dir_a)
    subjects_a = load_subjects(args.dir_a)
    logger.info("  %d subject-condition records", len(subjects_a))

    logger.info("Loading %s from %s ...", args.label_b, args.dir_b)
    subjects_b = load_subjects(args.dir_b)
    logger.info("  %d subject-condition records", len(subjects_b))

    # Compare
    logger.info("\nComparing %s vs %s ...", args.label_a, args.label_b)
    report = compare_datasets(
        subjects_a, subjects_b,
        args.label_a, args.label_b,
        args.age_bins,
    )

    if "error" in report:
        logger.error("  %s", report["error"])
        logger.info("  Bins in %s: %s", args.label_a, report.get("bins_a"))
        logger.info("  Bins in %s: %s", args.label_b, report.get("bins_b"))
        sys.exit(1)

    # Print results
    logger.info("\n=== Cross-Dataset Agreement ===")
    logger.info("  %s: %d subjects", args.label_a, report["n_subjects_a"])
    logger.info("  %s: %d subjects", args.label_b, report["n_subjects_b"])
    logger.info("  Overlapping bins: %s", report["overlapping_bins"])
    logger.info("  Common cells: %d", report["n_common_cells"])

    gc = report["global_correlation"]
    logger.info("\n  Global correlation of means: r=%.4f (p=%.2e) — %s",
                gc["r"], gc["p"], gc["interpretation"])

    logger.info("\n  Per-bin agreement:")
    for age_bin, info in report["per_bin"].items():
        r = info["correlation_r"]
        d = info["mean_abs_cohen_d"]
        logger.info("    %s: r=%.3f, mean|d|=%.3f (n_a=%d, n_b=%d)",
                    age_bin, r or 0, d or 0, info["n_a"], info["n_b"])

    logger.info("\n  Per-metric agreement:")
    for metric, info in sorted(report["per_metric"].items()):
        r = info["correlation_r"]
        flag = " ** LOW **" if info["agreement"] == "poor" else ""
        logger.info("    %s: r=%.3f, mean|d|=%.3f%s",
                    metric, r or 0, info["mean_abs_cohen_d"] or 0, flag)

    logger.info("\n  Top 10 largest disagreements (by Cohen's d):")
    for i, d in enumerate(report["top_disagreements"][:10]):
        logger.info("    %d. %s %s %s %s %s: d=%.2f (%s=%.3f, %s=%.3f)",
                    i + 1, d["bin"], d["condition"], d["channel"],
                    d["band"], d["metric"], d["cohen_d"],
                    args.label_a, d["mean_a"],
                    args.label_b, d["mean_b"])

    # Summary
    logger.info("\n=== SUMMARY ===")
    if gc["r"] > 0.90:
        logger.info("  PASS: Global agreement is %s (r=%.3f)", gc["interpretation"], gc["r"])
    else:
        logger.info("  ** CONCERN **: Global agreement is %s (r=%.3f)",
                    gc["interpretation"], gc["r"])

    poor_metrics = [m for m, v in report["per_metric"].items() if v["agreement"] == "poor"]
    if poor_metrics:
        logger.info("  ** POOR agreement metrics: %s", ", ".join(poor_metrics))
    else:
        logger.info("  All metrics have moderate or good agreement")

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("\nFull report written to %s", args.output)


if __name__ == "__main__":
    main()
