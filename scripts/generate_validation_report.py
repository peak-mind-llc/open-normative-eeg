#!/usr/bin/env python3
"""Generate a human-readable validation report from validation JSONs.

Reads the output of validate_internal.py, validate_literature.py, and
optionally validate_cross_dataset.py, and produces a comprehensive
markdown report suitable for inclusion in publications or documentation.

Usage:
    # Single dataset
    python scripts/generate_validation_report.py \
        --internal dortmund_internal.json \
        --literature dortmund_literature.json \
        --output validation_report.md

    # With cross-dataset comparison
    python scripts/generate_validation_report.py \
        --internal dortmund_internal.json \
        --literature dortmund_literature.json \
        --cross-dataset cross_dataset.json \
        --label "LEMON + Dortmund Combined" \
        --output validation_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def section_internal(data: dict) -> list[str]:
    """Generate internal consistency section."""
    lines = [
        "## Internal Consistency",
        "",
    ]

    # Cell quality
    cq = data.get("cell_quality", {})
    if cq:
        lines += [
            "### Cell Quality",
            "",
            f"- **Total normative cells:** {cq.get('total_cells', '?'):,}",
            f"- **Total subject-condition records:** {cq.get('total_subjects', '?'):,}",
            f"- **Sample size per cell:** min={cq.get('min_n', '?')}, "
            f"median={cq.get('median_n', '?')}, max={cq.get('max_n', '?')}",
            f"- **Thin cells (N < 10):** {cq.get('n_thin_cells_lt10', '?')}",
            f"- **Non-normal cells (Shapiro-Wilk p < 0.01):** {cq.get('n_non_normal_cells_p001', '?')}",
            "",
            "| Age Bin | Min N | Median N | Max N | Status |",
            "|---------|-------|----------|-------|--------|",
        ]
        for age_bin, info in sorted(cq.get("by_bin", {}).items()):
            status = "Thin" if info.get("thin") else "OK"
            lines.append(
                f"| {age_bin} | {info['min_n']} | {info['median_n']} | "
                f"{info['max_n']} | {status} |"
            )
        lines.append("")

    # Split-half reliability
    sh = data.get("split_half_reliability", {})
    if sh and "error" not in sh:
        lines += [
            "### Split-Half Reliability",
            "",
            f"Performed {sh.get('n_splits', '?')} random 50/50 splits. "
            f"For each split, built normative tables from each half and "
            f"correlated the cell means.",
            "",
            f"- **Overall mean r:** {sh.get('mean_r', '?')}",
            f"- **Overall range:** {sh.get('min_r', '?')} to {sh.get('max_r', '?')}",
            f"- **All splits r > 0.95:** {'Yes' if sh.get('all_above_095') else 'No'}",
            f"- **All splits r > 0.90:** {'Yes' if sh.get('all_above_090') else 'No'}",
        ]
        if sh.get("core_spectral_mean_r") is not None:
            lines += [
                "",
                f"**Core spectral metrics only** (relative power, corrected power, "
                f"GSF power, aperiodic):",
                f"- **Core mean r:** {sh['core_spectral_mean_r']}",
                f"- **Core all r > 0.90:** "
                f"{'Yes' if sh.get('core_spectral_all_above_090') else 'No'}",
            ]
        lines.append("")

        # Per-metric table
        pm = sh.get("per_metric", {})
        if pm:
            lines += [
                "| Metric | Mean r | Min r | Status |",
                "|--------|--------|-------|--------|",
            ]
            for metric in sorted(pm.keys()):
                info = pm[metric]
                lines.append(
                    f"| {metric} | {info['mean_r']:.3f} | {info['min_r']:.3f} | "
                    f"{info['flag'].upper()} |"
                )
            lines.append("")

    # EO vs EC alpha
    eoec = data.get("eo_ec_alpha", {})
    if eoec:
        lines += [
            "### Eyes-Open vs Eyes-Closed Alpha (Berger Effect)",
            "",
            f"{eoec.get('description', '')}",
            "",
            f"- **Cells tested:** {eoec.get('n_cells_tested', '?')}",
            f"- **Correct (EC > EO):** {eoec.get('n_correct', '?')} "
            f"({(eoec.get('pass_rate', 0) or 0) * 100:.0f}%)",
            f"- **Violations:** {eoec.get('n_violations', '?')}",
            f"- **Result:** {'PASS' if eoec.get('pass') else 'FAIL'}",
            "",
        ]
        violations = eoec.get("violations", [])
        if violations:
            lines += [
                "| Bin | Channel | EC Mean | EO Mean |",
                "|-----|---------|---------|---------|",
            ]
            for v in violations[:10]:
                lines.append(
                    f"| {v['bin']} | {v['channel']} | {v['ec_mean']:.4f} | {v['eo_mean']:.4f} |"
                )
            lines.append("")

    # IAF age trend
    iaf = data.get("iaf_age_trend", {})
    if iaf:
        lines += [
            "### IAF Age Trend",
            "",
            f"{iaf.get('description', '')}",
            f"- **Result:** {'PASS' if iaf.get('pass') else 'FAIL' if iaf.get('pass') is False else 'SKIP'}",
            "",
        ]
        for cond, v in iaf.get("by_condition", {}).items():
            lines += [
                f"**{cond.upper()}:** r = {v['correlation_r']:.3f} "
                f"(p = {v['correlation_p']:.4f}) "
                f"{'PASS' if v.get('negative_trend') else 'FAIL'}",
                "",
                "| Bin | Mean IAF (Hz) | SD | N |",
                "|-----|---------------|-----|---|",
            ]
            for b, m, s, n in zip(v["bins"], v["iaf_means"], v["iaf_sds"], v["ns"]):
                lines.append(f"| {b} | {m:.1f} | {s:.1f} | {n} |")
            lines.append("")

    return lines


def section_literature(data: dict) -> list[str]:
    """Generate literature validation section."""
    lines = [
        "## Literature Reference Checks",
        "",
        "Each check verifies that the normative database is consistent with "
        "well-established EEG findings from the published literature. These "
        "are directional and magnitude checks, not exact-number comparisons.",
        "",
    ]

    summary = data.get("summary", [])
    if summary:
        lines += [
            "### Summary",
            "",
            "| Check | Result |",
            "|-------|--------|",
        ]
        for s in summary:
            lines.append(f"| {s['check']} | {s['status']} |")
        lines.append("")

    # Detail for each check
    for key, check_data in data.items():
        if key == "summary" or not isinstance(check_data, dict):
            continue
        if "check" not in check_data and "description" not in check_data:
            continue

        name = check_data.get("check", key)
        desc = check_data.get("description", "")
        ref = check_data.get("reference", "")
        passed = check_data.get("pass")
        status = "PASS" if passed else ("FAIL" if passed is False else "SKIP")

        lines += [
            f"### {name}",
            "",
            f"{desc}",
            "",
            f"- **Reference:** {ref}",
            f"- **Result:** {status}",
        ]

        if "n_tested" in check_data:
            n_ok = check_data.get("n_correct", check_data.get("n_in_range", "?"))
            lines.append(f"- **Cells:** {n_ok}/{check_data['n_tested']} correct")

        if check_data.get("median_ec_eo_ratio"):
            lines.append(f"- **Median EC/EO ratio:** {check_data['median_ec_eo_ratio']}")

        if check_data.get("by_condition"):
            for cond, v in check_data["by_condition"].items():
                if "correlation_r" in v:
                    lines.append(
                        f"- **{cond.upper()}:** r = {v['correlation_r']:.3f} "
                        f"(p = {v['correlation_p']:.4f})"
                    )
                if "gsf_means" in v:
                    lines.append(f"- **GSF means:** {v['gsf_means']}")
                    lines.append(f"- **CV:** {v.get('cv', '?')}")

        if check_data.get("results"):
            results = check_data["results"]
            if isinstance(results[0], dict) and "mean_iaf" in results[0]:
                lines += [
                    "",
                    "| Bin | Condition | Mean IAF | SD | N |",
                    "|-----|-----------|----------|-----|---|",
                ]
                for r in results:
                    lines.append(
                        f"| {r['bin']} | {r['condition']} | {r['mean_iaf']:.1f} | "
                        f"{r['sd']:.1f} | {r['n']} |"
                    )

        lines.append("")

    return lines


def section_cross_dataset(data: dict) -> list[str]:
    """Generate cross-dataset comparison section."""
    lines = [
        "## Cross-Dataset Agreement",
        "",
        f"Comparing **{data.get('label_a', 'A')}** ({data.get('n_subjects_a', '?')} subjects) "
        f"vs **{data.get('label_b', 'B')}** ({data.get('n_subjects_b', '?')} subjects) "
        f"in overlapping age bins.",
        "",
    ]

    gc = data.get("global_correlation", {})
    if gc:
        lines += [
            f"- **Global correlation of normative means:** r = {gc.get('r', '?')} "
            f"(p = {gc.get('p', '?'):.2e}) -- {gc.get('interpretation', '')}",
            f"- **Overlapping bins:** {data.get('overlapping_bins', [])}",
            f"- **Common cells:** {data.get('n_common_cells', '?'):,}",
            "",
        ]

    # Per-bin table
    per_bin = data.get("per_bin", {})
    if per_bin:
        lines += [
            "### Agreement by Age Bin",
            "",
            "| Bin | r | Mean |d| | N (A) | N (B) |",
            "|-----|---|---------|-------|-------|",
        ]
        for age_bin, info in sorted(per_bin.items()):
            lines.append(
                f"| {age_bin} | {info.get('correlation_r', '?'):.3f} | "
                f"{info.get('mean_abs_cohen_d', '?'):.3f} | "
                f"{info.get('n_a', '?')} | {info.get('n_b', '?')} |"
            )
        lines.append("")

    # Per-metric table
    per_metric = data.get("per_metric", {})
    if per_metric:
        lines += [
            "### Agreement by Metric",
            "",
            "| Metric | r | Mean |d| | Max |d| | Agreement |",
            "|--------|---|---------|---------|-----------|",
        ]
        for metric, info in sorted(per_metric.items()):
            lines.append(
                f"| {metric} | {(info.get('correlation_r') or 0):.3f} | "
                f"{(info.get('mean_abs_cohen_d') or 0):.3f} | "
                f"{(info.get('max_abs_cohen_d') or 0):.3f} | "
                f"{info.get('agreement', '?')} |"
            )
        lines.append("")

    # Top disagreements
    top = data.get("top_disagreements", [])
    if top:
        lines += [
            "### Largest Disagreements",
            "",
            "| Bin | Cond | Channel | Band | Metric | d | A mean | B mean |",
            "|-----|------|---------|------|--------|---|--------|--------|",
        ]
        for d in top[:10]:
            lines.append(
                f"| {d['bin']} | {d['condition']} | {d['channel']} | "
                f"{d['band']} | {d['metric']} | {d['cohen_d']:.2f} | "
                f"{d['mean_a']:.3f} | {d['mean_b']:.3f} |"
            )
        lines.append("")

    return lines


def main():
    parser = argparse.ArgumentParser(
        description="Generate a human-readable validation report from validation JSONs",
    )
    parser.add_argument(
        "--internal",
        type=Path,
        default=None,
        help="Path to internal validation JSON (from validate_internal.py)",
    )
    parser.add_argument(
        "--literature",
        type=Path,
        default=None,
        help="Path to literature validation JSON (from validate_literature.py)",
    )
    parser.add_argument(
        "--cross-dataset",
        type=Path,
        default=None,
        help="Path to cross-dataset JSON (from validate_cross_dataset.py)",
    )
    parser.add_argument(
        "--label",
        default="Normative Database",
        help="Label for this database (e.g., 'Dortmund', 'LEMON + Dortmund Combined')",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output markdown file",
    )

    args = parser.parse_args()

    if not any([args.internal, args.literature, args.cross_dataset]):
        print("Error: provide at least one validation JSON (--internal, --literature, --cross-dataset)")
        sys.exit(1)

    lines = [
        f"# Validation Report: {args.label}",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
    ]

    # Executive summary
    all_checks = []

    if args.internal and args.internal.exists():
        internal = load_json(args.internal)
        sh = internal.get("split_half_reliability", {})
        eoec = internal.get("eo_ec_alpha", {})
        iaf = internal.get("iaf_age_trend", {})
        cq = internal.get("cell_quality", {})

        all_checks.append(("Split-half (core spectral) r > 0.90",
                          sh.get("core_spectral_all_above_090")))
        all_checks.append(("Split-half (all metrics) r > 0.90",
                          sh.get("all_above_090")))
        all_checks.append(("EC > EO alpha", eoec.get("pass")))
        all_checks.append(("IAF declines with age", iaf.get("pass")))

    if args.literature and args.literature.exists():
        literature = load_json(args.literature)
        for s in literature.get("summary", []):
            all_checks.append((s["check"], s["status"] == "PASS"))

    if args.cross_dataset and args.cross_dataset.exists():
        cross = load_json(args.cross_dataset)
        gc = cross.get("global_correlation", {})
        all_checks.append((f"Cross-dataset r > 0.90",
                          gc.get("r", 0) > 0.90 if gc else None))

    if all_checks:
        n_pass = sum(1 for _, v in all_checks if v is True)
        n_fail = sum(1 for _, v in all_checks if v is False)
        n_skip = sum(1 for _, v in all_checks if v is None)

        lines += [
            "## Executive Summary",
            "",
            f"**{n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP** out of {len(all_checks)} checks.",
            "",
            "| Check | Result |",
            "|-------|--------|",
        ]
        for name, passed in all_checks:
            status = "PASS" if passed is True else ("FAIL" if passed is False else "SKIP")
            lines.append(f"| {name} | {status} |")
        lines += ["", "---", ""]

    # Detailed sections
    if args.internal and args.internal.exists():
        lines += section_internal(internal)
        lines += ["---", ""]

    if args.literature and args.literature.exists():
        lines += section_literature(literature)
        lines += ["---", ""]

    if args.cross_dataset and args.cross_dataset.exists():
        lines += section_cross_dataset(cross)
        lines += ["---", ""]

    # Footer
    lines += [
        "## Methodology",
        "",
        "This report was generated by `open-normative-eeg` validation scripts.",
        "All checks are automated and reproducible. Source code and methodology",
        "are open source at https://github.com/peak-mind-llc/open-normative-eeg.",
        "",
        "### References",
        "",
        "- Barry et al. (2007, 2009) -- EO vs EC alpha differences",
        "- Corcoran et al. (2018) -- IAF estimation methods",
        "- Craiu et al. (2025) -- Aperiodic normative characterization",
        "- Donoghue et al. (2020) -- specparam / FOOOF",
        "- Klimesch (1999) -- Alpha oscillation frequency",
        "- Niedermeyer & da Silva (2005) -- EEG fundamentals",
        "- Voytek et al. (2015) -- Aperiodic slope and aging",
        "",
    ]

    with open(args.output, "w") as f:
        f.write("\n".join(lines))

    print(f"Validation report written to {args.output}")
    print(f"  {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")


if __name__ == "__main__":
    main()
