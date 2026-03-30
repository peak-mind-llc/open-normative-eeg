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
# Connectivity visualization
# ---------------------------------------------------------------------------

CONN_BANDS = ["Delta", "Theta", "Alpha", "Beta", "HighBeta", "Gamma"]

HUB_NAMES = ["F_mid", "F_L", "F_R", "C_mid", "T_L", "T_R",
             "P_mid", "P_L", "P_R", "O"]

HUB_LABELS = ["F\nmid", "F\nL", "F\nR", "C\nmid", "T\nL", "T\nR",
              "P\nmid", "P\nL", "P\nR", "O"]


def render_dwpli_topo(df, info, condition, age_bin, dpi=100):
    """Topographic maps of dwPLI node strength per band."""
    bands = [b for b in CONN_BANDS if b in df["band"].unique()]
    has_dwpli = "dwpli_node_strength" in df["metric"].values
    if not bands or not has_dwpli:
        return ""

    n_cols = len(bands)
    fig, axes = plt.subplots(1, n_cols, figsize=(2.5 * n_cols, 2.8))
    if n_cols == 1:
        axes = [axes]

    for j, band in enumerate(bands):
        ax = axes[j]
        values = get_topo_array(df, band, condition, age_bin,
                                "dwpli_node_strength")
        if np.all(np.isnan(values)):
            ax.set_visible(False)
            continue
        mne.viz.plot_topomap(
            values, info, axes=ax, show=False, contours=0,
            cmap="YlOrRd", sensors=True, names=None,
        )
        ax.set_title(band, fontsize=10, fontweight="bold")

    fig.suptitle(f"dwPLI Node Strength — {condition.upper()} / {age_bin}",
                 fontsize=12, y=1.02)
    fig.tight_layout()
    return fig_to_base64(fig, dpi)


def render_hub_matrix(df, condition, age_bin, method="dwpli", dpi=100):
    """Hub-to-hub connectivity heatmaps per band."""
    bands = [b for b in CONN_BANDS if b in df["band"].unique()]

    # Check if hub data exists
    hub_channels = [ch for ch in df["channel"].unique()
                    if ch.startswith("_hub_")]
    if not hub_channels or not bands:
        return ""

    n_cols = min(len(bands), 3)
    n_rows = (len(bands) + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(4 * n_cols, 3.5 * n_rows),
                             squeeze=False)

    for idx, band in enumerate(bands):
        row, col = divmod(idx, n_cols)
        ax = axes[row][col]

        matrix = np.zeros((len(HUB_NAMES), len(HUB_NAMES)))
        has_data = False
        for i, hub_i in enumerate(HUB_NAMES):
            ch = f"_hub_{hub_i}"
            for j, hub_j in enumerate(HUB_NAMES):
                if i == j:
                    continue
                metric_name = f"{method}_hub_{hub_j}"
                mask = (
                    (df["channel"] == ch)
                    & (df["band"] == band)
                    & (df["condition"] == condition)
                    & (df["bin"] == age_bin)
                    & (df["metric"] == metric_name)
                )
                row_data = df.loc[mask]
                if not row_data.empty:
                    matrix[i, j] = row_data.iloc[0]["mean"]
                    has_data = True

        if not has_data:
            ax.set_visible(False)
            continue

        im = ax.imshow(matrix, cmap="YlOrRd", interpolation="nearest",
                       vmin=0, vmax=max(0.3, np.max(matrix)))
        ax.set_xticks(range(len(HUB_LABELS)))
        ax.set_xticklabels(HUB_LABELS, fontsize=7)
        ax.set_yticks(range(len(HUB_LABELS)))
        ax.set_yticklabels(HUB_LABELS, fontsize=7)
        ax.set_title(band, fontsize=10, fontweight="bold")
        fig.colorbar(im, ax=ax, shrink=0.7)

    # Hide unused axes
    for idx in range(len(bands), n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row][col].set_visible(False)

    fig.suptitle(
        f"Hub-to-Hub {method.upper()} — {condition.upper()} / {age_bin}",
        fontsize=12, y=1.02,
    )
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

    sections = []

    # 1. Coverage
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

    # 6. dwPLI node strength topomaps
    if "dwpli_node_strength" in metrics:
        print("  Rendering dwPLI node strength topomaps...")
        dwpli_topo_items = []
        for cond in conditions:
            for age_bin in age_bins:
                b64 = render_dwpli_topo(df, info, cond, age_bin, dpi)
                if b64:
                    dwpli_topo_items.append((
                        f"{cond.upper()} / {age_bin}",
                        f'<img src="data:image/png;base64,{b64}">'
                    ))
        if dwpli_topo_items:
            sections.append(wrap_section(
                "dwPLI Node Strength (Connectivity)",
                make_tabs("dwpli-topo", dwpli_topo_items),
            ))

    # 7. Hub-to-hub connectivity matrices
    hub_metrics = [m for m in metrics if m.startswith("dwpli_hub_")]
    if hub_metrics:
        print("  Rendering hub-to-hub connectivity matrices...")
        hub_items = []
        for cond in conditions:
            for age_bin in age_bins:
                b64 = render_hub_matrix(df, cond, age_bin, "dwpli", dpi)
                if b64:
                    hub_items.append((
                        f"{cond.upper()} / {age_bin}",
                        f'<img src="data:image/png;base64,{b64}">'
                    ))
        if hub_items:
            sections.append(wrap_section(
                "Hub-to-Hub dwPLI Connectivity",
                make_tabs("hub-matrix", hub_items),
            ))

    # 8. Distribution quality
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
