#!/usr/bin/env python3
"""Generate an HTML report from a normative EEG database.

Produces topographic head maps, band power heatmaps, coverage tables,
and distribution quality flags — all in a single self-contained HTML file.

Usage:
    python scripts/visualize_norms.py norms_output/norms.json -o report.html
"""

import argparse
import base64
import dataclasses
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.colors as mcolors  # noqa: E402
import mne  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from open_normative.io import read_norms_json  # noqa: E402
from open_normative.parameters import PIPELINE_PARAMS  # noqa: E402

CHANNELS_19 = PIPELINE_PARAMS["channels"]["channels_19"]
ALL_BANDS = list(PIPELINE_PARAMS["spectral"]["bands"].keys())
MAIN_BANDS = ["Delta", "Theta", "Alpha", "Beta", "HighBeta", "Gamma"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def cells_to_dataframe(cells):
    """Convert NormCell list to a flat DataFrame."""
    rows = []
    for cell in cells:
        d = dataclasses.asdict(cell)
        pcts = d.pop("percentiles", {})
        for p, v in pcts.items():
            d[f"p{p}"] = v
        rows.append(d)
    return pd.DataFrame(rows)


def get_topo_array(df, band, condition, age_bin, metric, stat="mean"):
    """Return a 19-element array of values ordered by CHANNELS_19."""
    mask = (
        (df["band"] == band)
        & (df["condition"] == condition)
        & (df["bin"] == age_bin)
        & (df["metric"] == metric)
    )
    subset = df.loc[mask].set_index("channel")
    values = np.full(len(CHANNELS_19), np.nan)
    for i, ch in enumerate(CHANNELS_19):
        if ch in subset.index:
            values[i] = subset.loc[ch, stat]
    return values


# ---------------------------------------------------------------------------
# MNE info for topomaps
# ---------------------------------------------------------------------------

def make_topo_info():
    """Create an MNE Info with the standard 19-channel 10-20 montage."""
    info = mne.create_info(ch_names=CHANNELS_19, sfreq=256, ch_types="eeg")
    montage = mne.channels.make_standard_montage("standard_1020")
    info.set_montage(montage, on_missing="ignore")
    return info


# ---------------------------------------------------------------------------
# Figure rendering
# ---------------------------------------------------------------------------

def fig_to_base64(fig, dpi=100):
    """Render a figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def render_topo_grid(df, info, condition, metric, dpi=100):
    """Render topographic maps: rows=age bins, cols=main bands."""
    age_bins = sorted(df["bin"].unique(), key=lambda b: int(b.split("-")[0]))
    bands = [b for b in MAIN_BANDS if b in df["band"].unique()]

    if not age_bins or not bands:
        return ""

    n_rows = len(age_bins)
    n_cols = len(bands)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(2.5 * n_cols, 2.5 * n_rows))
    if n_rows == 1:
        axes = axes[np.newaxis, :]
    if n_cols == 1:
        axes = axes[:, np.newaxis]

    for i, age_bin in enumerate(age_bins):
        for j, band in enumerate(bands):
            ax = axes[i, j]
            values = get_topo_array(df, band, condition, age_bin, metric)
            if np.all(np.isnan(values)):
                ax.set_visible(False)
                continue
            mne.viz.plot_topomap(
                values, info, axes=ax, show=False, contours=0,
                cmap="RdYlBu_r", sensors=True, names=None,
            )
            if i == 0:
                ax.set_title(band, fontsize=10, fontweight="bold")
            if j == 0:
                ax.set_ylabel(age_bin, fontsize=9, rotation=0, labelpad=50,
                              va="center")

    fig.suptitle(f"{metric} — {condition.upper()}", fontsize=13, y=1.02)
    fig.tight_layout()
    return fig_to_base64(fig, dpi)


def render_corrected_comparison(df, info, condition, age_bin, dpi=100):
    """Side-by-side topomaps: uncorrected vs corrected absolute power."""
    bands = [b for b in MAIN_BANDS if b in df["band"].unique()]
    has_corrected = "corrected_absolute_power" in df["metric"].values

    if not bands or not has_corrected:
        return ""

    n_rows = len(bands)
    fig, axes = plt.subplots(n_rows, 2, figsize=(6, 2.2 * n_rows))
    if n_rows == 1:
        axes = axes[np.newaxis, :]

    for i, band in enumerate(bands):
        uncorr = get_topo_array(df, band, condition, age_bin, "absolute_power")
        corr = get_topo_array(df, band, condition, age_bin, "corrected_absolute_power")

        # Shared color scale per row
        all_vals = np.concatenate([uncorr[np.isfinite(uncorr)],
                                   corr[np.isfinite(corr)]])
        if len(all_vals) == 0:
            axes[i, 0].set_visible(False)
            axes[i, 1].set_visible(False)
            continue
        vmin, vmax = np.nanmin(all_vals), np.nanmax(all_vals)
        if vmin == vmax:
            vmax = vmin + 1e-12

        for j, (vals, label) in enumerate([(uncorr, "Uncorrected"),
                                            (corr, "Corrected")]):
            ax = axes[i, j]
            if np.all(np.isnan(vals)):
                ax.set_visible(False)
                continue
            mne.viz.plot_topomap(
                vals, info, axes=ax, show=False, contours=0,
                cmap="RdYlBu_r", vlim=(vmin, vmax), sensors=True,
            )
            if i == 0:
                ax.set_title(label, fontsize=10, fontweight="bold")
            if j == 0:
                ax.set_ylabel(band, fontsize=9, rotation=0, labelpad=45,
                              va="center")

    fig.suptitle(f"Corrected vs Uncorrected — {condition.upper()} / {age_bin}",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    return fig_to_base64(fig, dpi)


def render_power_heatmap(df, condition, age_bin, metric="absolute_power",
                         dpi=100):
    """Channels x Bands heatmap of mean power."""
    mask = (
        (df["condition"] == condition)
        & (df["bin"] == age_bin)
        & (df["metric"] == metric)
    )
    subset = df.loc[mask]
    if subset.empty:
        return ""

    bands = [b for b in ALL_BANDS if b in subset["band"].unique()]
    matrix = np.full((len(CHANNELS_19), len(bands)), np.nan)
    for i, ch in enumerate(CHANNELS_19):
        for j, band in enumerate(bands):
            row = subset[(subset["channel"] == ch) & (subset["band"] == band)]
            if not row.empty:
                matrix[i, j] = row.iloc[0]["mean"]

    fig, ax = plt.subplots(figsize=(max(8, len(bands) * 0.9), 8))
    im = ax.imshow(matrix, aspect="auto", cmap="viridis",
                   interpolation="nearest")
    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels(bands, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(CHANNELS_19)))
    ax.set_yticklabels(CHANNELS_19, fontsize=8)
    ax.set_title(f"{metric} — {condition.upper()} / {age_bin}", fontsize=11)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Mean")

    # Annotate cells with values
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            if np.isfinite(val):
                # Use scientific notation for very small/large values
                if abs(val) < 0.01 or abs(val) > 1000:
                    txt = f"{val:.1e}"
                else:
                    txt = f"{val:.2f}"
                ax.text(j, i, txt, ha="center", va="center", fontsize=5,
                        color="white" if val > np.nanmedian(matrix) else "black")

    fig.tight_layout()
    return fig_to_base64(fig, dpi)


# ---------------------------------------------------------------------------
# Coverage table
# ---------------------------------------------------------------------------

def render_coverage_table(df):
    """HTML table showing sample sizes per age bin and condition."""
    # Get n for a reference metric (first available)
    ref_metric = df["metric"].iloc[0] if not df.empty else "absolute_power"
    ref_band = "Alpha"
    ref_ch = "Fz"

    mask = (
        (df["metric"] == ref_metric)
        & (df["band"] == ref_band)
        & (df["channel"] == ref_ch)
    )
    subset = df.loc[mask]

    conditions = sorted(df["condition"].unique())
    age_bins = sorted(df["bin"].unique(), key=lambda b: int(b.split("-")[0]))

    rows_html = ""
    for age_bin in age_bins:
        cells = f"<td><strong>{age_bin}</strong></td>"
        for cond in conditions:
            row = subset[(subset["bin"] == age_bin) & (subset["condition"] == cond)]
            n = int(row.iloc[0]["n"]) if not row.empty else 0
            css = ' class="flag-low-n"' if 0 < n < 10 else ""
            cells += f"<td{css}>{n}</td>"
        rows_html += f"<tr>{cells}</tr>\n"

    header = "<th>Age Bin</th>" + "".join(f"<th>{c.upper()}</th>" for c in conditions)
    return f"""
    <table>
    <thead><tr>{header}</tr></thead>
    <tbody>{rows_html}</tbody>
    </table>
    <p class="meta">Cells highlighted yellow have n &lt; 10 (low confidence).</p>
    """


# ---------------------------------------------------------------------------
# Distribution quality
# ---------------------------------------------------------------------------

def render_quality_flags(df, condition, n_threshold=10, normality_alpha=0.05):
    """HTML section flagging low-n and non-normal distributions."""
    cond_df = df[df["condition"] == condition]
    parts = []

    # Low-n cells
    low_n = cond_df[(cond_df["n"] > 0) & (cond_df["n"] < n_threshold)]
    if not low_n.empty:
        summary = (
            low_n.groupby(["bin", "band", "metric"])["channel"]
            .apply(lambda x: ", ".join(sorted(x)))
            .reset_index()
        )
        rows = ""
        for _, r in summary.iterrows():
            rows += (f'<tr class="flag-low-n"><td>{r["bin"]}</td>'
                     f'<td>{r["band"]}</td><td>{r["metric"]}</td>'
                     f'<td>{r["channel"]}</td></tr>\n')
        parts.append(f"""
        <h4>Low Sample Size (n &lt; {n_threshold})</h4>
        <table>
        <thead><tr><th>Age Bin</th><th>Band</th><th>Metric</th><th>Channels</th></tr></thead>
        <tbody>{rows}</tbody>
        </table>
        """)
    else:
        parts.append(f"<p>No cells with n &lt; {n_threshold}.</p>")

    # Non-normal distributions
    non_normal = cond_df[
        (cond_df["normality_p"].notna())
        & (cond_df["normality_p"] < normality_alpha)
        & (cond_df["metric"] == "absolute_power")
    ]
    total_testable = cond_df[
        (cond_df["normality_p"].notna())
        & (cond_df["metric"] == "absolute_power")
    ].shape[0]
    pct = (len(non_normal) / total_testable * 100) if total_testable > 0 else 0
    parts.append(
        f"<h4>Normality (absolute_power, Shapiro-Wilk)</h4>"
        f"<p>{len(non_normal)} / {total_testable} cells reject normality "
        f"at p &lt; {normality_alpha} ({pct:.0f}%). "
        f"This is expected for absolute power — use log-transformed z-scores.</p>"
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Database statistics
# ---------------------------------------------------------------------------

def render_database_stats(df, norms_path, subjects_csv=None):
    """Render a comprehensive database statistics section."""
    conditions = sorted(df["condition"].unique())
    age_bins = sorted(df["bin"].unique(), key=lambda b: int(b.split("-")[0]))
    metrics = sorted(df["metric"].unique())
    bands = sorted(df["band"].unique())
    channels = sorted(df["channel"].unique())

    # Get sample sizes from a reference cell (Alpha / Fz / absolute_power)
    ref = df[(df["band"] == "Alpha") & (df["channel"] == "Fz") & (df["metric"] == "absolute_power")]
    total_n = int(ref["n"].sum()) if not ref.empty else 0
    n_per_bin = {}
    for _, row in ref.iterrows():
        key = f"{row['condition'].upper()} / {row['bin']}"
        n_per_bin[key] = int(row["n"])

    min_n = int(df[df["n"] > 0]["n"].min()) if not df.empty else 0
    max_n = int(df["n"].max()) if not df.empty else 0
    median_n = int(df[df["n"] > 0]["n"].median()) if not df.empty else 0

    # Load subjects.csv if available for demographics
    subjects_data = _load_subjects_csv(norms_path, subjects_csv)
    demo_html = _render_demographics(subjects_data) if subjects_data else ""

    # Age × sex distribution chart
    age_sex_img = _render_age_sex_chart(subjects_data) if subjects_data else ""

    # Normality summary across all cells
    testable = df[df["normality_p"].notna()]
    n_normal = len(testable[testable["normality_p"] >= 0.05])
    n_non_normal = len(testable[testable["normality_p"] < 0.05])
    pct_normal = (n_normal / len(testable) * 100) if len(testable) > 0 else 0

    # Log-transformed metrics
    log_metrics = sorted(df[df["log_transformed"] == True]["metric"].unique())  # noqa: E712

    # Pipeline params
    params_html = _render_pipeline_params()

    html = f"""
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{total_n:,}</div>
        <div class="stat-label">Total Subject-Conditions</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(age_bins)}</div>
        <div class="stat-label">Age Bins</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(conditions)}</div>
        <div class="stat-label">Conditions</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(channels)}</div>
        <div class="stat-label">Channels</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(bands)}</div>
        <div class="stat-label">Frequency Bands</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(metrics)}</div>
        <div class="stat-label">Metrics</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{len(df):,}</div>
        <div class="stat-label">Normative Cells</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{median_n}</div>
        <div class="stat-label">Median n per Cell</div>
      </div>
    </div>

    <h3>Sample Size by Condition and Age</h3>
    {_render_n_table(df, conditions, age_bins)}

    <h3>Metrics</h3>
    <table>
    <thead><tr><th>Metric</th><th>Description</th><th>Log-Transformed</th></tr></thead>
    <tbody>
    <tr><td>absolute_power</td><td>Traditional band power (µV²)</td><td>{"Yes" if "absolute_power" in log_metrics else "No"}</td></tr>
    <tr><td>relative_power</td><td>Band power / total power</td><td>{"Yes" if "relative_power" in log_metrics else "No"}</td></tr>
    <tr><td>corrected_absolute_power</td><td>Periodic-only power after aperiodic removal (specparam)</td><td>{"Yes" if "corrected_absolute_power" in log_metrics else "No"}</td></tr>
    <tr><td>corrected_relative_power</td><td>Corrected band / total corrected power</td><td>{"Yes" if "corrected_relative_power" in log_metrics else "No"}</td></tr>
    <tr><td>value</td><td>Band ratios (Theta/Beta, Delta/HighBeta, etc.)</td><td>{"Yes" if "value" in log_metrics else "No"}</td></tr>
    </tbody></table>

    <h3>Frequency Bands</h3>
    {_render_bands_table()}

    <h3>Distribution Quality</h3>
    <table>
    <thead><tr><th>Statistic</th><th>Value</th></tr></thead>
    <tbody>
    <tr><td>Min n per cell</td><td>{min_n}</td></tr>
    <tr><td>Max n per cell</td><td>{max_n}</td></tr>
    <tr><td>Median n per cell</td><td>{median_n}</td></tr>
    <tr><td>Cells passing Shapiro-Wilk (p ≥ 0.05)</td><td>{n_normal:,} / {len(testable):,} ({pct_normal:.0f}%)</td></tr>
    <tr><td>Cells with n ≥ 20</td><td>{len(df[df['n'] >= 20]):,} / {len(df):,} ({len(df[df['n'] >= 20]) / max(len(df), 1) * 100:.0f}%)</td></tr>
    </tbody></table>

    {demo_html}
    {age_sex_img}

    <h3>Channels</h3>
    <p>Standard 19-channel 10-20 clinical montage:</p>
    <p style="font-family: monospace; font-size: 0.95em;">{' &nbsp; '.join(CHANNELS_19)}</p>

    <details>
    <summary><strong>Pipeline Parameters</strong> (click to expand)</summary>
    {params_html}
    </details>
    """
    return html


def _load_subjects_csv(norms_path, subjects_csv=None):
    """Try to load subjects.csv from the same directory as norms.json."""
    if subjects_csv:
        p = Path(subjects_csv)
    else:
        p = Path(norms_path).parent / "subjects.csv"
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _render_demographics(subjects_df):
    """Render demographics summary from subjects.csv."""
    if subjects_df is None or subjects_df.empty:
        return ""

    n_total = len(subjects_df)
    # Unique subjects (may have both EO and EC rows)
    if "subject_id" in subjects_df.columns:
        n_unique = subjects_df["subject_id"].nunique()
    else:
        n_unique = n_total

    parts = [f"<h3>Subject Demographics</h3>"]
    parts.append(f"<p><strong>{n_unique}</strong> unique subjects, "
                 f"<strong>{n_total}</strong> total recordings (EO + EC)</p>")

    if "age" in subjects_df.columns:
        ages = subjects_df["age"].dropna()
        if len(ages) > 0:
            parts.append("<table>")
            parts.append("<thead><tr><th>Stat</th><th>Age</th></tr></thead><tbody>")
            parts.append(f"<tr><td>Mean</td><td>{ages.mean():.1f}</td></tr>")
            parts.append(f"<tr><td>SD</td><td>{ages.std():.1f}</td></tr>")
            parts.append(f"<tr><td>Min</td><td>{ages.min():.1f}</td></tr>")
            parts.append(f"<tr><td>Max</td><td>{ages.max():.1f}</td></tr>")
            parts.append(f"<tr><td>Median</td><td>{ages.median():.1f}</td></tr>")
            parts.append("</tbody></table>")

    if "sex" in subjects_df.columns:
        sex_counts = subjects_df.drop_duplicates(subset=["subject_id"] if "subject_id" in subjects_df.columns else None)["sex"].value_counts()
        parts.append("<p><strong>Sex distribution:</strong> ")
        parts.append(", ".join(f"{k}: {v}" for k, v in sex_counts.items()))
        parts.append("</p>")

    return "\n".join(parts)


def _render_age_sex_chart(subjects_df):
    """Render age × sex histogram."""
    if subjects_df is None or "age" not in subjects_df.columns:
        return ""

    # Deduplicate to unique subjects
    if "subject_id" in subjects_df.columns:
        sdf = subjects_df.drop_duplicates(subset=["subject_id"])
    else:
        sdf = subjects_df

    ages = sdf["age"].dropna()
    if len(ages) < 3:
        return ""

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Age histogram
    ax = axes[0]
    ax.hist(ages, bins=20, color="#3498db", edgecolor="white", alpha=0.85)
    ax.set_xlabel("Age")
    ax.set_ylabel("Count")
    ax.set_title("Age Distribution")

    # Age × sex
    ax = axes[1]
    if "sex" in sdf.columns:
        for sex, color, label in [("M", "#3498db", "Male"), ("F", "#e74c3c", "Female")]:
            mask = sdf["sex"] == sex
            sex_ages = sdf.loc[mask, "age"].dropna()
            if len(sex_ages) > 0:
                ax.hist(sex_ages, bins=20, alpha=0.6, color=color, edgecolor="white", label=label)
        ax.legend()
        ax.set_xlabel("Age")
        ax.set_ylabel("Count")
        ax.set_title("Age × Sex Distribution")
    else:
        ax.set_visible(False)

    fig.tight_layout()
    b64 = fig_to_base64(fig)
    return f'<img src="data:image/png;base64,{b64}">'


def _render_n_table(df, conditions, age_bins):
    """Detailed sample size table with min/max/median n."""
    ref_metric = "absolute_power"
    ref_band = "Alpha"
    ref_ch = "Fz"

    mask = (
        (df["metric"] == ref_metric)
        & (df["band"] == ref_band)
        & (df["channel"] == ref_ch)
    )
    subset = df.loc[mask]

    header = "<th>Age Bin</th>"
    for cond in conditions:
        header += f"<th>{cond.upper()} (n)</th>"
    header += "<th>Total</th>"

    rows = ""
    grand_total = 0
    for age_bin in age_bins:
        cells = f"<td><strong>{age_bin}</strong></td>"
        row_total = 0
        for cond in conditions:
            row = subset[(subset["bin"] == age_bin) & (subset["condition"] == cond)]
            n = int(row.iloc[0]["n"]) if not row.empty else 0
            css = ' class="flag-low-n"' if 0 < n < 10 else ""
            cells += f"<td{css}>{n}</td>"
            row_total += n
        cells += f"<td><strong>{row_total}</strong></td>"
        rows += f"<tr>{cells}</tr>\n"
        grand_total += row_total

    # Total row
    total_cells = "<td><strong>Total</strong></td>"
    for cond in conditions:
        cond_n = int(subset[subset["condition"] == cond]["n"].sum())
        total_cells += f"<td><strong>{cond_n}</strong></td>"
    total_cells += f"<td><strong>{grand_total}</strong></td>"
    rows += f"<tr style='border-top: 2px solid #333'>{total_cells}</tr>"

    return f"""
    <table>
    <thead><tr>{header}</tr></thead>
    <tbody>{rows}</tbody>
    </table>
    <p class="meta">Cells highlighted yellow have n &lt; 10.</p>
    """


def _render_bands_table():
    """Render frequency bands from pipeline parameters."""
    bands = PIPELINE_PARAMS["spectral"]["bands"]
    rows = ""
    for name, (lo, hi) in bands.items():
        rows += f"<tr><td>{name}</td><td>{lo}</td><td>{hi}</td></tr>\n"
    return f"""
    <table>
    <thead><tr><th>Band</th><th>Low (Hz)</th><th>High (Hz)</th></tr></thead>
    <tbody>{rows}</tbody>
    </table>
    """


def _render_pipeline_params():
    """Render full pipeline parameters as formatted JSON."""
    params_json = json.dumps(PIPELINE_PARAMS, indent=2, default=str)
    return f'<pre style="background:#f4f4f4; padding:12px; border-radius:4px; font-size:0.8em; max-height:400px; overflow:auto;">{params_json}</pre>'


def render_transparency(df, norms_path):
    """Render a transparency and limitations section.

    Addresses critiques of black-box normative databases by being explicit
    about sample sizes, empty bins, methodology, and known limitations.
    """
    conditions = sorted(df["condition"].unique())
    age_bins = sorted(df["bin"].unique(), key=lambda b: int(b.split("-")[0]))

    # Find empty or sparse bins
    ref = df[(df["band"] == "Alpha") & (df["channel"] == "Fz") & (df["metric"] == "absolute_power")]
    warnings = []

    # Check for missing age ranges (gaps between bins)
    if age_bins:
        bin_starts = [int(b.split("-")[0]) for b in age_bins]
        bin_ends = [int(b.split("-")[1]) for b in age_bins]
        full_range = list(range(bin_starts[0], bin_ends[-1] + 1, bin_ends[0] - bin_starts[0] + 1))
        missing_decades = [f"{d}-{d+9}" for d in full_range if d not in bin_starts]
        if missing_decades:
            warnings.append(
                f'<div class="warning-box"><strong>Missing age ranges:</strong> '
                f'No subjects in age bins: {", ".join(missing_decades)}. '
                f'Z-scores cannot be computed for these ages. Consider adding data '
                f'from other datasets (HBN for ages 5-21, MIPDB for ages 6-44).</div>'
            )

    # Check for low-n bins
    low_bins = []
    for _, row in ref.iterrows():
        if 0 < row["n"] < 20:
            low_bins.append(f"{row['condition'].upper()}/{row['bin']} (n={int(row['n'])})")
    if low_bins:
        warnings.append(
            f'<div class="warning-box"><strong>Low sample size bins:</strong> '
            f'{", ".join(low_bins)}. '
            f'Z-scores from bins with n &lt; 20 have wide confidence intervals '
            f'and should be interpreted with caution.</div>'
        )

    # Check for unbalanced conditions
    for cond in conditions:
        cond_ref = ref[ref["condition"] == cond]
        if not cond_ref.empty:
            ns = cond_ref["n"].values
            if len(ns) > 1 and max(ns) > 5 * min(ns[ns > 0]) if any(ns > 0) else False:
                warnings.append(
                    f'<div class="warning-box"><strong>Unbalanced age bins ({cond.upper()}):</strong> '
                    f'Sample sizes range from {int(min(ns[ns > 0]))} to {int(max(ns))}. '
                    f'Bins with fewer subjects will have less reliable norms.</div>'
                )

    # Compute normality rejection rate by metric
    normality_rows = ""
    for metric in sorted(df["metric"].unique()):
        mdf = df[(df["metric"] == metric) & (df["normality_p"].notna())]
        if mdf.empty:
            continue
        n_reject = len(mdf[mdf["normality_p"] < 0.05])
        pct = n_reject / len(mdf) * 100
        normality_rows += f"<tr><td>{metric}</td><td>{n_reject}/{len(mdf)}</td><td>{pct:.0f}%</td></tr>\n"

    warnings_html = "\n".join(warnings) if warnings else '<p style="color: #27ae60;">No critical warnings.</p>'

    # Load run_config.json if available for provenance
    config_path = Path(norms_path).parent / "run_config.json"
    provenance = ""
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
            provenance = f"""
            <h3>Provenance</h3>
            <table>
            <tbody>
            <tr><td>Dataset</td><td>{config.get('dataset', 'unknown')}</td></tr>
            <tr><td>Data directory</td><td><code>{config.get('data_dir', 'unknown')}</code></td></tr>
            <tr><td>Build timestamp</td><td>{config.get('timestamp', 'unknown')}</td></tr>
            <tr><td>Conditions</td><td>{config.get('condition', 'unknown')}</td></tr>
            <tr><td>Max subjects</td><td>{config.get('max_subjects', 'all') or 'all'}</td></tr>
            <tr><td>Connectivity</td><td>{'Skipped' if config.get('skip_connectivity') else 'Included'}</td></tr>
            <tr><td>Age bins</td><td>{config.get('age_bins', 'unknown')}</td></tr>
            </tbody></table>
            """
        except Exception:
            pass

    html = f"""
    <p>This section provides full transparency into the normative database.
    Unlike commercial black-box qEEG systems, every parameter, sample size,
    and limitation is documented here.</p>

    <h3>Warnings</h3>
    {warnings_html}

    <h3>What This Database Is</h3>
    <ul>
    <li>An <strong>open-source</strong> normative reference built from publicly available EEG datasets</li>
    <li>Fully auditable — every processing step, parameter, and statistical choice is visible</li>
    <li>Dual z-scores: traditional band power <strong>and</strong> specparam-corrected (periodic-only) power</li>
    <li>Age-binned by decade — z-scores compare a subject against same-age peers</li>
    <li>Log-transformed where appropriate to handle right-skewed power distributions</li>
    </ul>

    <h3>What This Database Is NOT</h3>
    <ul>
    <li>Not a clinical diagnostic tool on its own — z-scores are one input among many</li>
    <li>Not a replacement for clinical judgment</li>
    <li>Not demographically matched to all populations — dataset-specific biases exist</li>
    <li>Bins with small n (&lt; 20) should be interpreted as preliminary</li>
    </ul>

    <h3>Normality of Distributions (Shapiro-Wilk)</h3>
    <p>Z-scores assume approximately Gaussian distributions. Cells that reject
    normality (p &lt; 0.05) may produce less reliable z-scores. Log-transformation
    is applied to right-skewed metrics to improve normality.</p>
    <table>
    <thead><tr><th>Metric</th><th>Reject Normality</th><th>% Non-Normal</th></tr></thead>
    <tbody>{normality_rows}</tbody>
    </table>

    {provenance}
    """
    return html


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Normative EEG Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1400px; margin: 0 auto; padding: 20px;
         background: #fafafa; color: #333; }}
  h1 {{ border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
  h2 {{ color: #2c3e50; margin-top: 40px; }}
  h3 {{ color: #34495e; }}
  .section {{ background: #fff; border-radius: 8px; padding: 20px;
             margin: 20px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  table {{ border-collapse: collapse; margin: 10px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 12px; text-align: center; }}
  th {{ background: #2c3e50; color: white; }}
  tr:nth-child(even) {{ background: #f8f9fa; }}
  .flag-low-n {{ background: #fff3cd; }}
  .flag-non-normal {{ background: #f8d7da; }}
  img {{ max-width: 100%; height: auto; }}
  .meta {{ color: #666; font-size: 0.9em; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                 gap: 12px; margin: 16px 0; }}
  .stat-card {{ background: #2c3e50; color: white; border-radius: 8px;
               padding: 16px; text-align: center; }}
  .stat-value {{ font-size: 1.8em; font-weight: bold; }}
  .stat-label {{ font-size: 0.85em; opacity: 0.85; margin-top: 4px; }}
  .warning-box {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px;
                  padding: 12px 16px; margin: 12px 0; }}
  .warning-box strong {{ color: #856404; }}
  details summary {{ cursor: pointer; font-size: 1.05em; margin: 12px 0; }}
  .tab-container {{ display: flex; flex-wrap: wrap; gap: 4px; margin: 10px 0; }}
  .tab-btn {{ padding: 4px 14px; border: 1px solid #ccc; border-radius: 4px;
             cursor: pointer; background: #f0f0f0; font-size: 0.85em; }}
  .tab-btn.active {{ background: #2c3e50; color: white; border-color: #2c3e50; }}
  .tab-content {{ display: none; width: 100%; }}
  .tab-content.active {{ display: block; }}
</style>
</head>
<body>
<h1>Normative EEG Database Report</h1>
<p class="meta">Generated: {timestamp}<br>
Source: {source_file}<br>
Total cells: {total_cells:,} | Conditions: {conditions} | Age bins: {age_bins}</p>

{sections}

<script>
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const group = btn.dataset.group;
    const target = btn.dataset.target;
    document.querySelectorAll('.tab-btn[data-group="' + group + '"]')
      .forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content[data-group="' + group + '"]')
      .forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(target).classList.add('active');
  }});
}});
</script>
</body>
</html>
"""


def wrap_section(title, content):
    return f'<div class="section"><h2>{title}</h2>\n{content}\n</div>'


def make_tabs(group_id, items):
    """Build tabbed HTML. items is list of (label, html_content)."""
    if not items:
        return "<p>No data available.</p>"
    tabs = '<div class="tab-container">'
    panels = ""
    for i, (label, content) in enumerate(items):
        tid = f"{group_id}-{i}"
        active = " active" if i == 0 else ""
        tabs += (f'<div class="tab-btn{active}" data-group="{group_id}" '
                 f'data-target="{tid}">{label}</div>')
        panels += (f'<div id="{tid}" class="tab-content{active}" '
                   f'data-group="{group_id}">{content}</div>')
    tabs += "</div>"
    return tabs + panels


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(norms_path, output_path, dpi=100):
    """Load norms, render all sections, write HTML."""
    cells = read_norms_json(norms_path)
    if not cells:
        print("No cells found in norms file.", file=sys.stderr)
        sys.exit(1)

    df = cells_to_dataframe(cells)
    info = make_topo_info()

    conditions = sorted(df["condition"].unique())
    age_bins = sorted(df["bin"].unique(), key=lambda b: int(b.split("-")[0]))
    metrics = sorted(df["metric"].unique())

    print(f"Loaded {len(cells):,} cells: {len(conditions)} conditions, "
          f"{len(age_bins)} age bins, {len(metrics)} metrics")

    # Load subjects.csv for demographics
    subjects_csv_path = Path(norms_path).parent / "subjects.csv"

    sections = []

    # 1. Database overview stats
    print("  Rendering database statistics...")
    sections.append(wrap_section(
        "Database Overview", render_database_stats(df, norms_path)
    ))

    # 2. Transparency & limitations
    print("  Rendering transparency section...")
    sections.append(wrap_section(
        "Transparency & Limitations", render_transparency(df, norms_path)
    ))

    # 3. Coverage
    print("  Rendering coverage table...")
    sections.append(wrap_section("Age Bin Coverage", render_coverage_table(df)))

    # 2. Topographic maps (absolute_power)
    print("  Rendering topographic maps...")
    topo_items = []
    for cond in conditions:
        b64 = render_topo_grid(df, info, cond, "absolute_power", dpi)
        if b64:
            topo_items.append((
                cond.upper(),
                f'<img src="data:image/png;base64,{b64}">'
            ))
    if topo_items:
        sections.append(wrap_section(
            "Topographic Maps (Absolute Power)", make_tabs("topo-abs", topo_items)
        ))

    # 3. Topographic maps (corrected_absolute_power)
    if "corrected_absolute_power" in metrics:
        print("  Rendering corrected topographic maps...")
        corr_topo_items = []
        for cond in conditions:
            b64 = render_topo_grid(df, info, cond, "corrected_absolute_power", dpi)
            if b64:
                corr_topo_items.append((
                    cond.upper(),
                    f'<img src="data:image/png;base64,{b64}">'
                ))
        if corr_topo_items:
            sections.append(wrap_section(
                "Topographic Maps (Corrected Absolute Power)",
                make_tabs("topo-corr", corr_topo_items),
            ))

    # 4. Corrected vs uncorrected comparison
    if "corrected_absolute_power" in metrics:
        print("  Rendering corrected vs uncorrected comparison...")
        comp_items = []
        for cond in conditions:
            for age_bin in age_bins:
                b64 = render_corrected_comparison(df, info, cond, age_bin, dpi)
                if b64:
                    comp_items.append((
                        f"{cond.upper()} / {age_bin}",
                        f'<img src="data:image/png;base64,{b64}">'
                    ))
        if comp_items:
            sections.append(wrap_section(
                "Corrected vs Uncorrected Comparison",
                make_tabs("comparison", comp_items),
            ))

    # 5. Band power heatmaps
    print("  Rendering band power heatmaps...")
    heatmap_items = []
    for cond in conditions:
        for age_bin in age_bins:
            b64 = render_power_heatmap(df, cond, age_bin, "absolute_power", dpi)
            if b64:
                heatmap_items.append((
                    f"{cond.upper()} / {age_bin}",
                    f'<img src="data:image/png;base64,{b64}">'
                ))
    if heatmap_items:
        sections.append(wrap_section(
            "Band Power Heatmaps", make_tabs("heatmaps", heatmap_items)
        ))

    # 6. Distribution quality
    print("  Rendering quality flags...")
    quality_items = []
    for cond in conditions:
        html = render_quality_flags(df, cond)
        quality_items.append((cond.upper(), html))
    sections.append(wrap_section(
        "Distribution Quality", make_tabs("quality", quality_items)
    ))

    # Assemble HTML
    html = HTML_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        source_file=norms_path,
        total_cells=len(cells),
        conditions=", ".join(c.upper() for c in conditions),
        age_bins=", ".join(age_bins),
        sections="\n".join(sections),
    )

    Path(output_path).write_text(html, encoding="utf-8")
    size_mb = Path(output_path).stat().st_size / 1024 / 1024
    print(f"Wrote report to {output_path} ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate an HTML report from a normative EEG database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "norms_json",
        type=str,
        help="Path to norms.json (from build_norms.py)",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="report.html",
        help="Output HTML file path (default: report.html)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=100,
        help="Figure resolution in DPI (default: 100)",
    )
    args = parser.parse_args()
    build_report(args.norms_json, args.output, args.dpi)


if __name__ == "__main__":
    main()
