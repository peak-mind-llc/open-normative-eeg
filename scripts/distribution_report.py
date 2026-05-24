#!/usr/bin/env python3
"""Distribution disclosure report for a normative qEEG database.

Wood et al. (2024, PLoS ONE) show that qEEG z-scores assume Gaussianity that
EEG band power frequently violates, and that *slight* departures (skewness,
kurtosis) inflate tail false positives dramatically. Their recommendation:
qEEG databases should disclose the higher moments of every parameter's
distribution, present QQ-plots, and state whether/which transform was applied.

This script is that disclosure. Given a norms.json (written by build_norms.py),
it reports per-metric skewness and kurtosis, the fraction of cells where the
log transform fails to achieve approximate normality (`transform_normalized`
is False), the scoring-space normality pass-rate, and — optionally — percentile
QQ-plots for the worst offenders.

Usage:
    python scripts/distribution_report.py norms_output/norms.json \
        --output ./distribution_report

    # Also render percentile QQ-plot PNGs for the worst-offending cells
    python scripts/distribution_report.py norms_output/norms.json \
        --output ./distribution_report --figures
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_normative.io import read_norms_json
from open_normative.normative import NormCell

logger = logging.getLogger("distribution_report")


def _median(vals: list[float]):
    return float(np.median(vals)) if vals else None


def _mean(vals: list[float]):
    return float(np.mean(vals)) if vals else None


def summarize_distribution(cells: list[NormCell], alpha: float = 0.05) -> dict:
    """Aggregate the distribution-shape disclosure across all norm cells.

    Args:
        cells: NormCell list (must carry skewness/kurtosis/normality_p/
            transform_normalized — i.e. written by the current build_norms.py).
        alpha: Shapiro significance level; scoring-space p below this is
            "non-normal".

    Returns:
        Dict with "overall" stats, a "by_metric" breakdown, and a ranked
        "worst_cells" list of transform failures.
    """
    moments = [c for c in cells if c.skewness is not None]
    with_norm = [c for c in cells if c.normality_p is not None]
    with_tnorm = [c for c in cells if c.transform_normalized is not None]
    n_transform_failed = sum(
        1 for c in with_tnorm if c.transform_normalized is False
    )

    overall = {
        "total_cells": len(cells),
        "cells_with_moments": len(moments),
        "median_abs_skewness": _median([abs(c.skewness) for c in moments]),
        "median_excess_kurtosis": _median([c.kurtosis for c in moments]),
        "frac_log_transformed": (
            float(np.mean([1.0 if c.log_transformed else 0.0 for c in cells]))
            if cells else None
        ),
        "cells_with_normality": len(with_norm),
        "frac_non_normal": (
            float(np.mean([1.0 if c.normality_p < alpha else 0.0 for c in with_norm]))
            if with_norm else None
        ),
        "n_transform_failed": n_transform_failed,
        "frac_transform_failed": (
            n_transform_failed / len(with_tnorm) if with_tnorm else None
        ),
    }

    by_metric: dict[str, dict] = {}
    groups: dict[str, list[NormCell]] = defaultdict(list)
    for c in cells:
        groups[c.metric].append(c)
    for metric, gcells in groups.items():
        g_mom = [c for c in gcells if c.skewness is not None]
        g_norm = [c for c in gcells if c.normality_p is not None]
        g_tnorm = [c for c in gcells if c.transform_normalized is not None]
        by_metric[metric] = {
            "n_cells": len(gcells),
            "log_transformed": bool(gcells[0].log_transformed),
            "mean_abs_skewness": _mean([abs(c.skewness) for c in g_mom]),
            "mean_excess_kurtosis": _mean([c.kurtosis for c in g_mom]),
            "normality_pass_rate": (
                float(np.mean([1.0 if c.normality_p >= alpha else 0.0 for c in g_norm]))
                if g_norm else None
            ),
            "transform_pass_rate": (
                float(np.mean([1.0 if c.transform_normalized else 0.0 for c in g_tnorm]))
                if g_tnorm else None
            ),
        }

    # Worst offenders: cells where the transform failed to normalize, ranked by
    # most-non-normal (lowest scoring-space p) first.
    failures = [c for c in cells if c.transform_normalized is False]
    failures.sort(key=lambda c: (c.normality_p if c.normality_p is not None else 1.0))
    worst_cells = [
        {
            "bin": c.bin, "condition": c.condition, "channel": c.channel,
            "band": c.band, "metric": c.metric,
            "skewness": c.skewness, "kurtosis": c.kurtosis,
            "normality_p": c.normality_p,
            "transform_normalized": c.transform_normalized,
            "log_transformed": c.log_transformed, "n": c.n,
        }
        for c in failures
    ]

    return {"overall": overall, "by_metric": by_metric, "worst_cells": worst_cells}


def _fmt(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def render_markdown(summary: dict, alpha: float = 0.05, top: int = 25) -> str:
    """Render the disclosure summary as a Markdown report."""
    o = summary["overall"]
    lines = [
        "# Distribution Disclosure Report",
        "",
        "Higher-moment disclosure of the normative qEEG database, following "
        "Wood et al. (2024). The parametric z-score assumes the scoring-space "
        "distribution is Gaussian; this report shows how well that holds.",
        "",
        "## Overall",
        "",
        f"- Total cells: **{o['total_cells']}**",
        f"- Cells with moment estimates (n≥3): {o['cells_with_moments']}",
        f"- Median |skewness| (raw): **{_fmt(o['median_abs_skewness'])}**",
        f"- Median excess kurtosis (raw): **{_fmt(o['median_excess_kurtosis'])}**",
        f"- Fraction log-transformed: {_fmt(o['frac_log_transformed'])}",
        f"- Fraction non-normal in scoring space (Shapiro p < {alpha}): "
        f"**{_fmt(o['frac_non_normal'])}**",
        f"- Cells where the transform FAILED to normalize: "
        f"**{o['n_transform_failed']}** "
        f"({_fmt(o['frac_transform_failed'])} of testable cells)",
        "",
        "> Where `transform_normalized` is False, the σ-based z-score and its "
        "> ±2/±3 cutoffs over- or under-flag in the tails — prefer the "
        "> percentile-derived robust z for those cells.",
        "",
        "## By metric",
        "",
        "| metric | n | log | mean \\|skew\\| | mean kurtosis | "
        "normality pass | transform pass |",
        "|---|---:|:---:|---:|---:|---:|---:|",
    ]
    for metric in sorted(summary["by_metric"]):
        m = summary["by_metric"][metric]
        lines.append(
            f"| {metric} | {m['n_cells']} | "
            f"{'yes' if m['log_transformed'] else 'no'} | "
            f"{_fmt(m['mean_abs_skewness'])} | {_fmt(m['mean_excess_kurtosis'])} | "
            f"{_fmt(m['normality_pass_rate'])} | {_fmt(m['transform_pass_rate'])} |"
        )

    worst = summary["worst_cells"][:top]
    lines += [
        "",
        f"## Worst offenders (transform failures, top {len(worst)})",
        "",
        "| bin | cond | channel | band | metric | skew | kurtosis | "
        "scoring-space p | n |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for w in worst:
        lines.append(
            f"| {w['bin']} | {w['condition']} | {w['channel']} | {w['band']} | "
            f"{w['metric']} | {_fmt(w['skewness'], 2)} | {_fmt(w['kurtosis'], 2)} | "
            f"{_fmt(w['normality_p'], 4)} | {w['n']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_qq_figures(cells: list[NormCell], out_dir: Path, count: int = 12) -> int:
    """Render percentile QQ-plots for the worst-offending cells.

    NormCells store summary percentiles, not raw samples, so this is a
    *percentile* QQ-plot: the stored percentile values (in the scoring space)
    plotted against the standard-normal quantiles at those percentile points. A
    Gaussian scoring space falls on a straight line; fat tails bow away from it.

    Returns the number of figures written (0 if matplotlib is unavailable).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from scipy.stats import norm as _norm
    except Exception:  # pragma: no cover - optional dependency
        logger.warning("matplotlib/scipy unavailable; skipping QQ figures")
        return 0

    failures = [
        c for c in cells
        if c.transform_normalized is False and c.percentiles
    ]
    failures.sort(key=lambda c: (c.normality_p if c.normality_p is not None else 1.0))
    fig_dir = out_dir / "qq"
    fig_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for c in failures[:count]:
        pts = sorted(
            (float(k), float(v)) for k, v in c.percentiles.items()
        )
        if len(pts) < 5:
            continue
        ps = np.array([p for p, _ in pts])
        vals = np.array([v for _, v in pts], dtype=float)
        if c.log_transformed:
            vals = vals[vals > 0]
            ps = ps[: len(vals)]
            vals = np.log(vals)
        theo = _norm.ppf(ps / 100.0)

        fig, ax = plt.subplots(figsize=(4, 4))
        ax.plot(theo, vals, "o-", ms=4)
        # Reference line through the inter-quartile slope.
        if len(vals) >= 2:
            slope = (vals[-1] - vals[0]) / (theo[-1] - theo[0]) if theo[-1] != theo[0] else 1.0
            ax.plot(theo, vals[len(vals) // 2] + slope * (theo - theo[len(theo) // 2]),
                    "--", color="grey", lw=1)
        space = "log" if c.log_transformed else "raw"
        ax.set_title(
            f"{c.channel} {c.band} {c.metric}\n{c.bin} {c.condition} "
            f"(p={_fmt(c.normality_p, 4)}, {space})",
            fontsize=8,
        )
        ax.set_xlabel("Normal quantile")
        ax.set_ylabel(f"Stored percentile value ({space})")
        fig.tight_layout()
        safe = f"{c.bin}_{c.condition}_{c.channel}_{c.band}_{c.metric}".replace("/", "-")
        fig.savefig(fig_dir / f"{safe}.png", dpi=110)
        plt.close(fig)
        written += 1
    return written


def main():
    parser = argparse.ArgumentParser(
        description="Distribution disclosure report for a normative database",
    )
    parser.add_argument("norms_json", type=Path, help="Path to norms.json")
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("./distribution_report"),
        help="Output directory (default: ./distribution_report)",
    )
    parser.add_argument("--alpha", type=float, default=0.05,
                        help="Shapiro significance level (default 0.05)")
    parser.add_argument("--top", type=int, default=25,
                        help="Worst-offender cells to tabulate (default 25)")
    parser.add_argument("--figures", action="store_true",
                        help="Also render percentile QQ-plot PNGs")
    parser.add_argument("--figures-count", type=int, default=12)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.norms_json.exists():
        logger.error("norms.json not found: %s", args.norms_json)
        sys.exit(1)

    logger.info("Loading %s ...", args.norms_json)
    cells = read_norms_json(args.norms_json)
    logger.info("  %d cells", len(cells))

    summary = summarize_distribution(cells, alpha=args.alpha)
    args.output.mkdir(parents=True, exist_ok=True)

    (args.output / "distribution_summary.json").write_text(
        json.dumps(summary, indent=2)
    )
    md = render_markdown(summary, alpha=args.alpha, top=args.top)
    (args.output / "distribution_report.md").write_text(md)

    o = summary["overall"]
    logger.info("  Median |skewness|: %s", _fmt(o["median_abs_skewness"]))
    logger.info("  Median excess kurtosis: %s", _fmt(o["median_excess_kurtosis"]))
    logger.info("  Non-normal fraction (scoring space): %s", _fmt(o["frac_non_normal"]))
    logger.info("  Transform failures: %d (%s)", o["n_transform_failed"],
                _fmt(o["frac_transform_failed"]))

    if args.figures:
        n = write_qq_figures(cells, args.output, count=args.figures_count)
        logger.info("  Wrote %d QQ figures", n)

    logger.info("Report written to %s", args.output / "distribution_report.md")


if __name__ == "__main__":
    main()
