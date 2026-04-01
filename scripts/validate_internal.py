#!/usr/bin/env python3
"""Internal consistency validation for a normative database.

Loads subject checkpoints, performs split-half reliability analysis,
checks known physiological effects (EO vs EC alpha, IAF age decline),
and reports on normative cell quality.

Usage:
    python scripts/validate_internal.py ./norms_output/subjects \
        --output ./validation_report.json

    # Use specific age bins
    python scripts/validate_internal.py ./norms_output/subjects \
        --age-bins 20 30 40 50 60 70 80
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_normative.normative import build_normative, _DEFAULT_AGE_BINS

logger = logging.getLogger("validate_internal")


def load_subjects(subjects_dir: Path) -> list[dict]:
    """Load all subject checkpoint JSONs."""
    subjects = []
    for fpath in sorted(subjects_dir.glob("*.json")):
        with open(fpath) as f:
            subjects.append(json.load(f))
    return subjects


def split_half_reliability(
    subjects: list[dict],
    age_bins: list[int],
    n_splits: int = 10,
    seed: int = 42,
) -> dict:
    """Compute split-half reliability across multiple random splits.

    For each split:
    1. Randomly divide subjects into two halves
    2. Build normative tables for each half
    3. Correlate the means across all matching cells

    Returns:
        Dict with per-split correlations, mean/min/max r, and
        per-metric breakdown.
    """
    rng = random.Random(seed)
    split_results = []

    for split_i in range(n_splits):
        shuffled = list(subjects)
        rng.shuffle(shuffled)
        mid = len(shuffled) // 2
        half_a = shuffled[:mid]
        half_b = shuffled[mid:]

        norms_a = build_normative(half_a, age_bins=age_bins)
        norms_b = build_normative(half_b, age_bins=age_bins)

        # Index by (bin, condition, channel, band, metric)
        idx_a = {
            (c.bin, c.condition, c.channel, c.band, c.metric): c.mean
            for c in norms_a if c.n >= 3
        }
        idx_b = {
            (c.bin, c.condition, c.channel, c.band, c.metric): c.mean
            for c in norms_b if c.n >= 3
        }

        # Find matching keys
        common = set(idx_a.keys()) & set(idx_b.keys())
        if len(common) < 10:
            logger.warning("Split %d: only %d common cells, skipping", split_i, len(common))
            continue

        vals_a = [idx_a[k] for k in common]
        vals_b = [idx_b[k] for k in common]

        r, p = stats.pearsonr(vals_a, vals_b)

        # Per-metric breakdown
        metric_rs = {}
        metrics_seen = set(k[4] for k in common)
        for metric in metrics_seen:
            metric_keys = [k for k in common if k[4] == metric]
            if len(metric_keys) < 5:
                continue
            ma = [idx_a[k] for k in metric_keys]
            mb = [idx_b[k] for k in metric_keys]
            mr, _ = stats.pearsonr(ma, mb)
            metric_rs[metric] = round(float(mr), 4)

        split_results.append({
            "split": split_i,
            "n_common_cells": len(common),
            "r": round(float(r), 4),
            "p": float(p),
            "n_half_a": len(half_a),
            "n_half_b": len(half_b),
            "per_metric": metric_rs,
        })

    if not split_results:
        return {"error": "No valid splits produced"}

    rs = [s["r"] for s in split_results]
    # Aggregate per-metric across splits
    all_metrics = set()
    for s in split_results:
        all_metrics.update(s["per_metric"].keys())

    metric_summary = {}
    for metric in sorted(all_metrics):
        m_rs = [s["per_metric"].get(metric) for s in split_results if metric in s["per_metric"]]
        if m_rs:
            metric_summary[metric] = {
                "mean_r": round(float(np.mean(m_rs)), 4),
                "min_r": round(float(np.min(m_rs)), 4),
                "flag": "LOW" if float(np.mean(m_rs)) < 0.80 else "ok",
            }

    # Also compute split-half on core spectral metrics only
    # (excluding noisy connectivity/graph/PAC/asymmetry metrics)
    core_metrics = {
        "relative_power", "corrected_absolute_power", "corrected_relative_power",
        "gsf_absolute_power", "gsf_relative_power",
        "aperiodic_exponent", "aperiodic_offset",
    }
    core_rs = []
    for s in split_results:
        core_r_vals = [v for m, v in s["per_metric"].items() if m in core_metrics and v is not None]
        if core_r_vals:
            core_rs.append(float(np.mean(core_r_vals)))

    return {
        "n_splits": len(split_results),
        "mean_r": round(float(np.mean(rs)), 4),
        "min_r": round(float(np.min(rs)), 4),
        "max_r": round(float(np.max(rs)), 4),
        "all_above_095": all(r >= 0.95 for r in rs),
        "all_above_090": all(r >= 0.90 for r in rs),
        "core_spectral_mean_r": round(float(np.mean(core_rs)), 4) if core_rs else None,
        "core_spectral_all_above_090": all(r >= 0.90 for r in core_rs) if core_rs else None,
        "per_metric": metric_summary,
        "splits": split_results,
    }


def check_eo_ec_alpha(subjects: list[dict], age_bins: list[int]) -> dict:
    """Verify that eyes-closed alpha > eyes-open alpha (universal effect).

    Returns per-bin and per-channel results.
    """
    norms = build_normative(subjects, age_bins=age_bins)

    # Index: (bin, channel) -> {eo: mean, ec: mean}
    alpha_by_cell: dict[tuple, dict] = defaultdict(dict)
    for cell in norms:
        if cell.band == "Alpha" and cell.metric == "absolute_power":
            key = (cell.bin, cell.channel)
            alpha_by_cell[key][cell.condition] = cell.mean

    results = []
    violations = []
    for (age_bin, channel), cond_means in sorted(alpha_by_cell.items()):
        eo = cond_means.get("eo")
        ec = cond_means.get("ec")
        if eo is None or ec is None:
            continue
        # Skip cells where either value is near zero (specparam may have
        # zeroed out periodic power, or the value is negligibly small)
        if eo < 1e-6 or ec < 1e-6:
            continue
        correct = ec > eo
        ratio = ec / eo if eo > 0 else None
        entry = {
            "bin": age_bin,
            "channel": channel,
            "ec_mean": round(ec, 4),
            "eo_mean": round(eo, 4),
            "ec_gt_eo": correct,
            "ec_eo_ratio": round(ratio, 2) if ratio else None,
        }
        results.append(entry)
        if not correct:
            violations.append(entry)

    n_total = len(results)
    n_correct = sum(1 for r in results if r["ec_gt_eo"])

    return {
        "description": "Eyes-closed alpha power should exceed eyes-open alpha power",
        "n_cells_tested": n_total,
        "n_correct": n_correct,
        "n_violations": len(violations),
        "pass_rate": round(n_correct / n_total, 3) if n_total > 0 else None,
        "pass": len(violations) == 0,
        "violations": violations,
    }


def check_iaf_age_trend(subjects: list[dict], age_bins: list[int]) -> dict:
    """Check that IAF decreases with age (expected neurophysiological trend).

    Returns correlation between age bin midpoint and mean IAF.
    """
    norms = build_normative(subjects, age_bins=age_bins)

    iaf_cells = [
        c for c in norms
        if c.metric == "iaf_peak" and c.channel == "_subject" and c.n >= 5
    ]

    if len(iaf_cells) < 3:
        return {
            "description": "IAF should decline with age",
            "pass": None,
            "note": f"Only {len(iaf_cells)} age bins with IAF data (need >= 3)",
        }

    # Group by condition
    results_by_cond = {}
    for cond in set(c.condition for c in iaf_cells):
        cond_cells = sorted(
            [c for c in iaf_cells if c.condition == cond],
            key=lambda c: c.bin,
        )
        if len(cond_cells) < 3:
            continue

        # Extract bin midpoints and IAF means
        midpoints = []
        iaf_means = []
        for c in cond_cells:
            lo, hi = c.bin.split("-")
            midpoints.append((int(lo) + int(hi)) / 2.0)
            iaf_means.append(c.mean)

        r, p = stats.pearsonr(midpoints, iaf_means)
        results_by_cond[cond] = {
            "bins": [c.bin for c in cond_cells],
            "iaf_means": [round(c.mean, 2) for c in cond_cells],
            "iaf_sds": [round(c.sd, 2) for c in cond_cells],
            "ns": [c.n for c in cond_cells],
            "correlation_r": round(float(r), 3),
            "correlation_p": round(float(p), 4),
            "negative_trend": r < 0,
        }

    return {
        "description": "IAF should decline with age (negative correlation expected)",
        "pass": all(v["negative_trend"] for v in results_by_cond.values()),
        "by_condition": results_by_cond,
    }


def check_cell_quality(subjects: list[dict], age_bins: list[int]) -> dict:
    """Report on normative cell quality: sample sizes, normality, thin bins."""
    norms = build_normative(subjects, age_bins=age_bins)

    ns = [c.n for c in norms]
    thin_cells = [c for c in norms if c.n < 10]
    non_normal = [c for c in norms if c.normality_p is not None and c.normality_p < 0.01]

    # Bins breakdown
    bin_ns = defaultdict(list)
    for c in norms:
        bin_ns[c.bin].append(c.n)

    bin_summary = {}
    for b in sorted(bin_ns.keys()):
        bin_summary[b] = {
            "n_cells": len(bin_ns[b]),
            "min_n": int(np.min(bin_ns[b])),
            "median_n": int(np.median(bin_ns[b])),
            "max_n": int(np.max(bin_ns[b])),
            "thin": int(np.min(bin_ns[b])) < 10,
        }

    return {
        "total_cells": len(norms),
        "total_subjects": len(subjects),
        "n_thin_cells_lt10": len(thin_cells),
        "n_non_normal_cells_p001": len(non_normal),
        "min_n": int(np.min(ns)) if ns else 0,
        "median_n": int(np.median(ns)) if ns else 0,
        "max_n": int(np.max(ns)) if ns else 0,
        "by_bin": bin_summary,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Internal consistency validation for normative database",
    )
    parser.add_argument(
        "subjects_dir",
        type=Path,
        help="Path to subjects/ checkpoint directory from build_norms.py",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Write validation report as JSON",
    )
    parser.add_argument(
        "--age-bins",
        type=int,
        nargs="+",
        default=_DEFAULT_AGE_BINS,
        help="Age bin edges (default: decade bins 20-80)",
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=10,
        help="Number of random splits for split-half reliability (default: 10)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.subjects_dir.exists():
        logger.error("Subjects directory not found: %s", args.subjects_dir)
        sys.exit(1)

    # Load subjects
    logger.info("Loading subjects from %s ...", args.subjects_dir)
    subjects = load_subjects(args.subjects_dir)
    logger.info("  Loaded %d subject-condition records", len(subjects))

    if not subjects:
        logger.error("No subjects found!")
        sys.exit(1)

    report = {}

    # 1. Cell quality
    logger.info("\n=== Cell Quality ===")
    quality = check_cell_quality(subjects, args.age_bins)
    report["cell_quality"] = quality
    logger.info("  Total cells: %d", quality["total_cells"])
    logger.info("  Total subjects: %d", quality["total_subjects"])
    logger.info("  Min/median/max N per cell: %d / %d / %d",
                quality["min_n"], quality["median_n"], quality["max_n"])
    logger.info("  Thin cells (N<10): %d", quality["n_thin_cells_lt10"])
    for b, bs in quality["by_bin"].items():
        flag = " ** THIN **" if bs["thin"] else ""
        logger.info("    %s: min_n=%d, median_n=%d%s", b, bs["min_n"], bs["median_n"], flag)

    # 2. Split-half reliability
    logger.info("\n=== Split-Half Reliability (%d splits) ===", args.n_splits)
    split_half = split_half_reliability(subjects, args.age_bins, n_splits=args.n_splits)
    report["split_half_reliability"] = split_half
    if "error" not in split_half:
        logger.info("  Mean r: %.4f", split_half["mean_r"])
        logger.info("  Min r:  %.4f", split_half["min_r"])
        logger.info("  Max r:  %.4f", split_half["max_r"])
        logger.info("  All splits r > 0.95: %s", split_half["all_above_095"])
        logger.info("  All splits r > 0.90: %s", split_half["all_above_090"])
        if split_half.get("core_spectral_mean_r") is not None:
            logger.info("  Core spectral metrics mean r: %.4f", split_half["core_spectral_mean_r"])
            logger.info("  Core spectral all r > 0.90: %s", split_half["core_spectral_all_above_090"])
        # Flag weak metrics
        weak = {m: v for m, v in split_half["per_metric"].items() if v["flag"] == "LOW"}
        if weak:
            logger.info("  LOW reliability metrics (mean r < 0.80):")
            for m, v in sorted(weak.items()):
                logger.info("    %s: mean_r=%.3f", m, v["mean_r"])
    else:
        logger.warning("  %s", split_half["error"])

    # 3. EO vs EC alpha
    logger.info("\n=== Eyes-Open vs Eyes-Closed Alpha ===")
    eo_ec = check_eo_ec_alpha(subjects, args.age_bins)
    report["eo_ec_alpha"] = eo_ec
    logger.info("  %s", eo_ec["description"])
    logger.info("  Cells tested: %d", eo_ec["n_cells_tested"])
    logger.info("  Correct (EC > EO): %d (%.0f%%)",
                eo_ec["n_correct"],
                (eo_ec["pass_rate"] or 0) * 100)
    if eo_ec["violations"]:
        logger.warning("  VIOLATIONS:")
        for v in eo_ec["violations"][:5]:
            logger.warning("    %s %s: EC=%.4f, EO=%.4f",
                          v["bin"], v["channel"], v["ec_mean"], v["eo_mean"])

    # 4. IAF age trend
    logger.info("\n=== IAF Age Trend ===")
    iaf_trend = check_iaf_age_trend(subjects, args.age_bins)
    report["iaf_age_trend"] = iaf_trend
    logger.info("  %s", iaf_trend["description"])
    if iaf_trend["pass"] is not None:
        for cond, v in iaf_trend.get("by_condition", {}).items():
            logger.info("  %s: r=%.3f (p=%.4f) %s",
                       cond.upper(), v["correlation_r"], v["correlation_p"],
                       "PASS" if v["negative_trend"] else "** FAIL **")
            for b, m, s, n in zip(v["bins"], v["iaf_means"], v["iaf_sds"], v["ns"]):
                logger.info("    %s: IAF=%.1f +/- %.1f Hz (n=%d)", b, m, s, n)
    else:
        logger.info("  %s", iaf_trend.get("note", ""))

    # Summary
    logger.info("\n=== SUMMARY ===")
    checks = {
        "Split-half r > 0.90 (all metrics)": split_half.get("all_above_090", False),
        "Split-half r > 0.90 (core spectral)": split_half.get("core_spectral_all_above_090", False),
        "EC > EO alpha (non-zero cells)": eo_ec.get("pass", False),
        "IAF declines with age": iaf_trend.get("pass"),
    }
    all_pass = True
    for check, result in checks.items():
        status = "PASS" if result else ("SKIP" if result is None else "** FAIL **")
        if result is False:
            all_pass = False
        logger.info("  %s: %s", status, check)

    logger.info("\n  Overall: %s", "ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED")

    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, cls=_NumpyEncoder)
        logger.info("\nFull report written to %s", args.output)


if __name__ == "__main__":
    main()
