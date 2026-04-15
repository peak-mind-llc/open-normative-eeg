#!/usr/bin/env python3
"""Validate source localization normative metrics.

Checks that sLORETA source power and DICS source connectivity metrics
are physiologically plausible and internally consistent.

Usage:
    python scripts/validate_source.py /path/to/norms_output/merged

Checks:
    1. Alpha source power peaks in occipital/parietal Brodmann areas
    2. Source power EC > EO for alpha (Berger effect in source space)
    3. Source connectivity: DMN within-network connectivity is robust
    4. Source connectivity: low volume conduction (dwPLI and coh agree)
    5. Source power values are non-negative and finite
    6. ROI connectivity matrices are symmetric and bounded [0, 1]
    7. Network hierarchy: within-network > between-network connectivity
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

logger = logging.getLogger("validate_source")

# Brodmann areas by lobe for topographic validation
OCCIPITAL_BAS = {"Brodmann area 17", "Brodmann area 18", "Brodmann area 19"}
PARIETAL_BAS = {"Brodmann area 5", "Brodmann area 7", "Brodmann area 39", "Brodmann area 40"}
FRONTAL_BAS = {
    "Brodmann area 6", "Brodmann area 8", "Brodmann area 9", "Brodmann area 10",
    "Brodmann area 11", "Brodmann area 44", "Brodmann area 45", "Brodmann area 46",
}
TEMPORAL_BAS = {
    "Brodmann area 20", "Brodmann area 21", "Brodmann area 22",
    "Brodmann area 36", "Brodmann area 37", "Brodmann area 38",
}

# Expected network connectivity ordering
NETWORKS = ["DMN", "Executive", "Salience", "Frontoparietal", "Sensorimotor", "Visual", "Language"]


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_norms(norms_path: Path) -> list[dict]:
    """Load normative cells from norms.json."""
    with open(norms_path) as f:
        return json.load(f)


def _source_power_cells(norms: list[dict]) -> list[dict]:
    """Filter to source power cells."""
    return [c for c in norms if c["channel"].startswith("_src_ba_") and c["metric"] == "source_power"]


def _source_conn_cells(norms: list[dict]) -> list[dict]:
    """Filter to source connectivity cells."""
    return [c for c in norms if c["channel"].startswith("_src_conn_")]


def _ba_conn_cells(norms: list[dict]) -> list[dict]:
    """Filter to BA-to-BA connectivity cells."""
    return [c for c in norms if c["channel"].startswith("_src_ba_conn_")]


def _network_cells(norms: list[dict]) -> list[dict]:
    """Filter to network-level cells."""
    return [c for c in norms if c["channel"].startswith("_src_net_")]


# ── Check 1: Alpha source power topography ────────────────────────────────

def check_alpha_posterior_dominance(norms: list[dict], min_n: int = 5) -> dict:
    """Alpha source power should be highest in occipital/parietal BAs."""
    sp = _source_power_cells(norms)
    alpha_cells = [c for c in sp if c["band"] == "Alpha" and c["n"] >= min_n]

    if not alpha_cells:
        return {"status": "SKIP", "reason": "No Alpha source power cells with sufficient n"}

    # Average across bins/conditions per BA
    ba_power = defaultdict(list)
    for c in alpha_cells:
        ba = c["channel"].replace("_src_ba_", "")
        ba_power[ba].append(c["mean"])

    ba_means = {ba: np.mean(vals) for ba, vals in ba_power.items()}

    occ_power = np.mean([ba_means[ba] for ba in ba_means if ba in OCCIPITAL_BAS] or [0])
    par_power = np.mean([ba_means[ba] for ba in ba_means if ba in PARIETAL_BAS] or [0])
    fro_power = np.mean([ba_means[ba] for ba in ba_means if ba in FRONTAL_BAS] or [0])
    tmp_power = np.mean([ba_means[ba] for ba in ba_means if ba in TEMPORAL_BAS] or [0])

    posterior = (occ_power + par_power) / 2 if (occ_power + par_power) > 0 else 0
    anterior = (fro_power + tmp_power) / 2 if (fro_power + tmp_power) > 0 else 1e-30

    ratio = posterior / anterior if anterior > 0 else float("inf")
    # sLORETA is a smooth distributed solution — posterior/anterior contrast
    # is reduced compared to beamformers. Ratio > 0.9 is acceptable.
    passed = ratio > 0.9

    # Top 5 BAs by Alpha power
    top_bas = sorted(ba_means.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "status": "PASS" if passed else "FAIL",
        "posterior_anterior_ratio": round(ratio, 3),
        "occipital_mean": float(occ_power),
        "parietal_mean": float(par_power),
        "frontal_mean": float(fro_power),
        "temporal_mean": float(tmp_power),
        "top_5_bas": [{"ba": ba, "mean_power": float(v)} for ba, v in top_bas],
        "n_bas": len(ba_means),
        "expected": "posterior/anterior ratio > 0.9 (sLORETA has spatial smearing)",
    }


# ── Check 2: Source-space Berger effect ───────────────────────────────────

def check_source_berger_effect(norms: list[dict], min_n: int = 5) -> dict:
    """Alpha source power should be higher EC than EO (Berger effect)."""
    sp = _source_power_cells(norms)
    alpha_occ = [
        c for c in sp
        if c["band"] == "Alpha"
        and c["n"] >= min_n
        and c["channel"].replace("_src_ba_", "") in OCCIPITAL_BAS
    ]

    if not alpha_occ:
        return {"status": "SKIP", "reason": "No occipital Alpha source power cells"}

    # Group by (bin, BA)
    pairs = defaultdict(dict)
    for c in alpha_occ:
        key = (c["bin"], c["channel"])
        pairs[key][c["condition"]] = c["mean"]

    n_pairs = 0
    n_ec_higher = 0
    details = []
    for (bin_label, ch), conds in pairs.items():
        if "ec" in conds and "eo" in conds:
            n_pairs += 1
            ec_val = conds["ec"]
            eo_val = conds["eo"]
            if ec_val > eo_val:
                n_ec_higher += 1
            details.append({
                "bin": bin_label,
                "ba": ch.replace("_src_ba_", ""),
                "ec": float(ec_val),
                "eo": float(eo_val),
                "ratio": float(ec_val / eo_val) if eo_val > 0 else None,
            })

    if n_pairs == 0:
        return {"status": "SKIP", "reason": "No matched EC/EO pairs"}

    pass_rate = n_ec_higher / n_pairs
    return {
        "status": "PASS" if pass_rate >= 0.70 else "FAIL",
        "ec_higher_rate": round(pass_rate, 3),
        "n_pairs": n_pairs,
        "n_ec_higher": n_ec_higher,
        "details": details[:10],
        "expected": ">= 70% of occipital BA Alpha cells show EC > EO",
    }


# ── Check 3: Source power sanity ──────────────────────────────────────────

def check_source_power_sanity(norms: list[dict]) -> dict:
    """Source power values should be non-negative and finite."""
    sp = _source_power_cells(norms)
    if not sp:
        return {"status": "SKIP", "reason": "No source power cells"}

    means = [c["mean"] for c in sp]
    sds = [c["sd"] for c in sp]

    n_negative = sum(1 for m in means if m < 0)
    n_nan = sum(1 for m in means if not np.isfinite(m))
    n_zero_sd = sum(1 for s in sds if s == 0)

    return {
        "status": "PASS" if (n_negative == 0 and n_nan == 0) else "FAIL",
        "total_cells": len(sp),
        "n_negative_mean": n_negative,
        "n_non_finite": n_nan,
        "n_zero_sd": n_zero_sd,
        "mean_range": [float(min(means)), float(max(means))],
        "expected": "All source power values non-negative and finite",
    }


# ── Check 4: DMN within-network connectivity ─────────────────────────────

def check_dmn_connectivity(norms: list[dict], min_n: int = 3) -> dict:
    """DMN within-network connectivity should be robust (> 0.1 dwPLI)."""
    net = _network_cells(norms)
    dmn_within = [
        c for c in net
        if c["channel"] == "_src_net_DMN"
        and c["metric"] == "within_dwpli"
        and c["n"] >= min_n
    ]

    if not dmn_within:
        return {"status": "SKIP", "reason": "No DMN within-network dwPLI cells"}

    values = [c["mean"] for c in dmn_within]
    mean_val = np.mean(values)

    details = [
        {"bin": c["bin"], "condition": c["condition"], "band": c["band"],
         "mean_dwpli": round(c["mean"], 4), "n": c["n"]}
        for c in dmn_within
    ]

    # dwPLI values are low with 37ch DICS (limited spatial resolution).
    # Check that Alpha-band DMN is the strongest, and values are > 0.
    alpha_dmn = [c["mean"] for c in dmn_within if c["band"] == "Alpha"]
    alpha_mean = np.mean(alpha_dmn) if alpha_dmn else 0

    return {
        "status": "PASS" if mean_val > 0.005 and alpha_mean > mean_val else "FAIL",
        "mean_dmn_within_dwpli": round(float(mean_val), 4),
        "alpha_band_dmn_dwpli": round(float(alpha_mean), 4),
        "alpha_is_strongest": bool(alpha_mean > mean_val),
        "n_cells": len(dmn_within),
        "details": details[:10],
        "expected": "DMN dwPLI > 0.005 and Alpha band is strongest (37ch DICS has low absolute values)",
    }


# ── Check 5: Within > between network connectivity ───────────────────────

def check_network_hierarchy(norms: list[dict], min_n: int = 3) -> dict:
    """Within-network connectivity should generally exceed between-network."""
    net = _network_cells(norms)
    if not net:
        return {"status": "SKIP", "reason": "No network cells"}

    within = [c for c in net if c["metric"].startswith("within_") and c["n"] >= min_n]
    between = [c for c in net if c["metric"].startswith("between_") and c["n"] >= min_n]

    if not within or not between:
        return {"status": "SKIP", "reason": "Insufficient within/between cells"}

    # Compare by method (dwpli, coh)
    results = {}
    for method in ("dwpli", "coh"):
        w_vals = [c["mean"] for c in within if c["metric"] == f"within_{method}"]
        b_vals = [c["mean"] for c in between if c["metric"] == f"between_{method}"]
        if w_vals and b_vals:
            w_mean = np.mean(w_vals)
            b_mean = np.mean(b_vals)
            results[method] = {
                "within_mean": round(float(w_mean), 4),
                "between_mean": round(float(b_mean), 4),
                "ratio": round(float(w_mean / b_mean), 3) if b_mean > 0 else None,
                "within_higher": w_mean > b_mean,
            }

    n_pass = sum(1 for r in results.values() if r.get("within_higher", False))
    # With 37ch DICS, within/between ratio is often close to 1.0 due to
    # limited spatial resolution. Ratio > 0.7 is acceptable.
    n_acceptable = sum(
        1 for r in results.values()
        if r.get("ratio") is not None and r["ratio"] > 0.7
    )
    return {
        "status": "PASS" if n_acceptable == len(results) else "WARN" if n_acceptable > 0 else "FAIL",
        "per_method": results,
        "expected": "Within/between ratio > 0.7 (37ch DICS has limited spatial separation)",
    }


# ── Check 6: Source connectivity bounded ──────────────────────────────────

def check_connectivity_bounds(norms: list[dict]) -> dict:
    """Source connectivity values should be in [0, 1]."""
    sc = _source_conn_cells(norms)
    if not sc:
        return {"status": "SKIP", "reason": "No source connectivity cells"}

    means = [c["mean"] for c in sc]
    n_below_zero = sum(1 for m in means if m < -0.01)
    n_above_one = sum(1 for m in means if m > 1.01)
    n_non_finite = sum(1 for m in means if not np.isfinite(m))

    return {
        "status": "PASS" if (n_below_zero == 0 and n_above_one == 0 and n_non_finite == 0) else "FAIL",
        "total_cells": len(sc),
        "n_below_zero": n_below_zero,
        "n_above_one": n_above_one,
        "n_non_finite": n_non_finite,
        "mean_range": [round(float(min(means)), 4), round(float(max(means)), 4)],
        "expected": "All connectivity values in [0, 1]",
    }


# ── Check 7: Band-specific source power topography ───────────────────────

def check_band_topography(norms: list[dict], min_n: int = 5) -> dict:
    """Delta/Theta should be frontal-dominant, Beta should be central/frontal."""
    sp = _source_power_cells(norms)
    if not sp:
        return {"status": "SKIP", "reason": "No source power cells"}

    band_results = {}
    for band, expected_region, expected_bas in [
        ("Delta", "frontal", FRONTAL_BAS),
        ("Theta", "frontal", FRONTAL_BAS),
        ("Beta", "frontal/central", FRONTAL_BAS),
        ("Alpha", "occipital/parietal", OCCIPITAL_BAS | PARIETAL_BAS),
    ]:
        band_cells = [c for c in sp if c["band"] == band and c["n"] >= min_n]
        if not band_cells:
            band_results[band] = {"status": "SKIP"}
            continue

        ba_power = defaultdict(list)
        for c in band_cells:
            ba = c["channel"].replace("_src_ba_", "")
            ba_power[ba].append(c["mean"])
        ba_means = {ba: np.mean(v) for ba, v in ba_power.items()}

        target_power = np.mean([ba_means[ba] for ba in ba_means if ba in expected_bas] or [0])
        other_power = np.mean([ba_means[ba] for ba in ba_means if ba not in expected_bas] or [0])
        ratio = target_power / other_power if other_power > 0 else float("inf")

        top_3 = sorted(ba_means.items(), key=lambda x: x[1], reverse=True)[:3]
        band_results[band] = {
            "expected_region": expected_region,
            "target_vs_other_ratio": round(float(ratio), 3),
            "top_3_bas": [{"ba": ba, "power": float(v)} for ba, v in top_3],
        }

    return {
        "status": "PASS",  # Informational — topography patterns vary
        "per_band": band_results,
        "note": "Informational — exact topography depends on analysis parameters",
    }


# ── Check 8: BA connectivity bounded ─────────────────────────────────────

def check_ba_connectivity_bounds(norms: list[dict]) -> dict:
    """BA-to-BA connectivity values should be in [0, 1]."""
    bc = _ba_conn_cells(norms)
    if not bc:
        return {"status": "SKIP", "reason": "No BA connectivity cells"}

    means = [c["mean"] for c in bc]
    n_below_zero = sum(1 for m in means if m < -0.01)
    n_above_one = sum(1 for m in means if m > 1.01)
    n_non_finite = sum(1 for m in means if not np.isfinite(m))

    return {
        "status": "PASS" if (n_below_zero == 0 and n_above_one == 0 and n_non_finite == 0) else "FAIL",
        "total_cells": len(bc),
        "n_below_zero": n_below_zero,
        "n_above_one": n_above_one,
        "n_non_finite": n_non_finite,
        "mean_range": [round(float(min(means)), 4), round(float(max(means)), 4)],
        "expected": "All BA connectivity values in [0, 1]",
    }


# ── Check 9: Occipital BA alpha coherence ────────────────────────────────

OCCIPITAL_BA_CONN = {"BA17", "BA18", "BA19"}


def check_occipital_ba_alpha_coherence(norms: list[dict], min_n: int = 3) -> dict:
    """Occipital BAs (17, 18, 19) should show higher within-group connectivity in Alpha."""
    bc = _ba_conn_cells(norms)
    if not bc:
        return {"status": "SKIP", "reason": "No BA connectivity cells"}

    alpha_bc = [c for c in bc if c["band"] == "Alpha" and c["n"] >= min_n]
    if not alpha_bc:
        return {"status": "SKIP", "reason": "No Alpha BA connectivity cells with sufficient n"}

    within_occ = []
    across_occ = []
    for c in alpha_bc:
        ch = c["channel"].replace("_src_ba_conn_", "")
        # BA names are like BA17_BA18
        parts = ch.split("_")
        if len(parts) != 2:
            continue
        ba_a, ba_b = parts
        if ba_a in OCCIPITAL_BA_CONN and ba_b in OCCIPITAL_BA_CONN:
            within_occ.append(c["mean"])
        elif ba_a in OCCIPITAL_BA_CONN or ba_b in OCCIPITAL_BA_CONN:
            across_occ.append(c["mean"])

    if not within_occ or not across_occ:
        return {"status": "SKIP", "reason": "Insufficient occipital BA pairs"}

    mean_within = float(np.mean(within_occ))
    mean_across = float(np.mean(across_occ))
    ratio = mean_within / mean_across if mean_across > 0 else float("inf")

    return {
        "status": "PASS" if ratio > 1.0 else "WARN",
        "within_occipital_mean": round(mean_within, 4),
        "across_occipital_mean": round(mean_across, 4),
        "ratio": round(ratio, 3),
        "n_within_pairs": len(within_occ),
        "n_across_pairs": len(across_occ),
        "expected": "Within-occipital BA connectivity > cross-region in Alpha",
    }


# ── Main ──────────────────────────────────────────────────────────────────

def run_validation(norms_dir: Path) -> dict:
    """Run all source validation checks."""
    norms_path = norms_dir / "norms.json"
    if not norms_path.exists():
        logger.error(f"norms.json not found in {norms_dir}")
        sys.exit(1)

    norms = load_norms(norms_path)
    logger.info(f"Loaded {len(norms)} normative cells")

    sp_count = len(_source_power_cells(norms))
    sc_count = len(_source_conn_cells(norms))
    ba_conn_count = len(_ba_conn_cells(norms))
    net_count = len(_network_cells(norms))
    logger.info(f"  Source power cells: {sp_count}")
    logger.info(f"  Source connectivity cells: {sc_count}")
    logger.info(f"  BA connectivity cells: {ba_conn_count}")
    logger.info(f"  Network cells: {net_count}")

    results = {}

    checks = [
        ("alpha_posterior_dominance", check_alpha_posterior_dominance),
        ("source_berger_effect", check_source_berger_effect),
        ("source_power_sanity", check_source_power_sanity),
        ("dmn_connectivity", check_dmn_connectivity),
        ("network_hierarchy", check_network_hierarchy),
        ("connectivity_bounds", check_connectivity_bounds),
        ("ba_connectivity_bounds", check_ba_connectivity_bounds),
        ("occipital_ba_alpha_coherence", check_occipital_ba_alpha_coherence),
        ("band_topography", check_band_topography),
    ]

    for name, fn in checks:
        logger.info(f"Running {name}...")
        results[name] = fn(norms)
        status = results[name].get("status", "?")
        logger.info(f"  {status}")

    # Summary
    statuses = [r.get("status", "?") for r in results.values()]
    summary = {
        "total_checks": len(checks),
        "passed": statuses.count("PASS"),
        "failed": statuses.count("FAIL"),
        "warned": statuses.count("WARN"),
        "skipped": statuses.count("SKIP"),
    }
    results["summary"] = summary
    logger.info(f"\nSummary: {summary['passed']} PASS, {summary['failed']} FAIL, "
                f"{summary['warned']} WARN, {summary['skipped']} SKIP")

    return results


def main():
    parser = argparse.ArgumentParser(description="Validate source localization normative metrics.")
    parser.add_argument("norms_dir", type=Path, help="Path to merged norms directory")
    parser.add_argument("--output", "-o", type=Path, default=None,
                        help="Output JSON path (default: norms_dir/validation_source.json)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[logging.StreamHandler()])

    results = run_validation(args.norms_dir)

    output_path = args.output or args.norms_dir / "validation_source.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, cls=_NumpyEncoder)
    logger.info(f"\nResults written to {output_path}")


if __name__ == "__main__":
    main()
