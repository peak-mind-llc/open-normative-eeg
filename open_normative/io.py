"""I/O utilities for normative database files.

Supports JSON (round-trip with full NormCell fidelity), CSV
(flat format for analysis in R/Python/Excel), and NPZ
(compact binary split by category for fast product loading).
"""

from __future__ import annotations

import csv
import dataclasses
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Optional, Union

import numpy as np
from scipy.stats import norm as _norm_dist

from open_normative.normative import NormCell, _PERCENTILE_POINTS


PathLike = Union[str, Path]


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def write_norms_json(cells: list[NormCell], filepath: PathLike) -> None:
    """Write a list of NormCell objects to a JSON file.

    Args:
        cells: List of NormCell objects.
        filepath: Destination file path.
    """
    data = [dataclasses.asdict(cell) for cell in cells]
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def read_norms_json(filepath: PathLike) -> list[NormCell]:
    """Read NormCell objects back from a JSON file written by write_norms_json.

    Args:
        filepath: Source file path.

    Returns:
        List of NormCell objects.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    cells = []
    for item in data:
        # Backward compat: add defaults for fields added after v1.0.
        item.setdefault("ci_lower", None)
        item.setdefault("ci_upper", None)
        item.setdefault("pi_lower", None)
        item.setdefault("pi_upper", None)
        cells.append(NormCell(**item))
    return cells


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------


def write_norms_csv(cells: list[NormCell], filepath: PathLike) -> None:
    """Write normative cells to a flat CSV file.

    Percentile columns are named p1, p5, p10, p25, p50, p75, p90, p95, p99.

    Args:
        cells: List of NormCell objects.
        filepath: Destination file path.
    """
    if not cells:
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            fh.write("")
        return

    pct_cols = [f"p{p}" for p in _PERCENTILE_POINTS]
    base_fields = [
        "bin", "condition", "channel", "band", "metric",
        "n", "mean", "sd", "log_mean", "log_sd", "log_transformed",
        "normality_p", "ci_lower", "ci_upper", "pi_lower", "pi_upper",
        "skewness", "kurtosis", "transform_normalized",
    ]
    fieldnames = base_fields + pct_cols

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for cell in cells:
            row = {
                "bin": cell.bin,
                "condition": cell.condition,
                "channel": cell.channel,
                "band": cell.band,
                "metric": cell.metric,
                "n": cell.n,
                "mean": cell.mean,
                "sd": cell.sd,
                "log_mean": cell.log_mean,
                "log_sd": cell.log_sd,
                "log_transformed": cell.log_transformed,
                "normality_p": cell.normality_p,
                "ci_lower": cell.ci_lower,
                "ci_upper": cell.ci_upper,
                "pi_lower": cell.pi_lower,
                "pi_upper": cell.pi_upper,
                "skewness": cell.skewness,
                "kurtosis": cell.kurtosis,
                "transform_normalized": cell.transform_normalized,
            }
            for p in _PERCENTILE_POINTS:
                row[f"p{p}"] = cell.percentiles.get(str(p))
            writer.writerow(row)


# ---------------------------------------------------------------------------
# NPZ I/O — split by category for fast product loading
# ---------------------------------------------------------------------------

# Channel prefix → category mapping
_CATEGORY_RULES = [
    ("_pair_", "scalp_connectivity"),
    ("_src_ba_conn_", "source_ba_connectivity"),
    ("_src_dk_", "source_dk"),          # both dk power and dk connectivity
    ("_src_conn_", "source_roi_connectivity"),
    ("_src_net_", "source_network"),
    ("_src_ba_", "source_ba_power"),     # after _src_ba_conn_ check
    ("_graph", "graph_metrics"),
]


def _categorize_channel(channel: str) -> str:
    """Map a channel name to its NPZ category."""
    for prefix, category in _CATEGORY_RULES:
        if channel.startswith(prefix):
            return category
    return "scalp_power"


def write_norms_npz(cells: list[NormCell], output_dir: PathLike) -> dict:
    """Write normative cells as split NPZ files for fast product loading.

    Creates one .npz file per category under output_dir/npz/:
        scalp_power.npz          — 37ch electrode power metrics
        scalp_connectivity.npz   — 666 electrode pair connectivity
        source_ba_power.npz      — Brodmann area source power
        source_ba_connectivity.npz — BA-to-BA connectivity
        source_roi_connectivity.npz — 18 merged ROI connectivity
        source_dk.npz            — DK parcel power + connectivity
        source_network.npz       — network-level connectivity
        graph_metrics.npz        — global efficiency, char path length
        metadata.json            — index of all files + dimensions

    Each NPZ contains:
        bins, conditions, channels, bands, metrics: label arrays
        mean, sd, n: float arrays aligned with labels
        log_mean, log_sd: float arrays (NaN where not log-transformed)
        log_transformed: bool array
        skewness, kurtosis: raw-distribution shape (NaN where n < 3)
        normality_p: Shapiro p-value of the scoring space (NaN where n < 3)
        transform_normalized: tri-state float (NaN/1.0/0.0)
        percentile_points: 1D array of percentile points (e.g. [0.5, 1, ...])
        percentiles: (n_cells, n_points) matrix aligned with percentile_points

    Returns dict of {category: n_cells} for logging.
    """
    output_dir = Path(output_dir)
    npz_dir = output_dir / "npz"
    npz_dir.mkdir(parents=True, exist_ok=True)

    # Group cells by category
    by_category: dict[str, list[NormCell]] = defaultdict(list)
    for cell in cells:
        cat = _categorize_channel(cell.channel)
        by_category[cat].append(cell)

    file_manifest = {}
    for category, cat_cells in sorted(by_category.items()):
        n = len(cat_cells)

        # Build parallel arrays. Bands need U64 to fit ratio names like
        # "(Delta+Theta)/(Alpha+Beta)" and "corrected_Alpha/HighBeta" — U20
        # silently truncated them to ambiguous prefixes.
        bins = np.array([c.bin for c in cat_cells], dtype="U20")
        conditions = np.array([c.condition for c in cat_cells], dtype="U10")
        channels = np.array([c.channel for c in cat_cells], dtype="U80")
        bands = np.array([c.band for c in cat_cells], dtype="U64")
        metrics = np.array([c.metric for c in cat_cells], dtype="U40")
        means = np.array([c.mean for c in cat_cells], dtype=np.float64)
        sds = np.array([c.sd for c in cat_cells], dtype=np.float64)
        ns = np.array([c.n for c in cat_cells], dtype=np.int32)
        log_means = np.array(
            [c.log_mean if c.log_mean is not None else np.nan for c in cat_cells],
            dtype=np.float64,
        )
        log_sds = np.array(
            [c.log_sd if c.log_sd is not None else np.nan for c in cat_cells],
            dtype=np.float64,
        )
        log_transformed = np.array(
            [c.log_transformed for c in cat_cells], dtype=bool,
        )

        # Disclosure arrays (Wood et al. 2024): raw skewness/kurtosis, the
        # scoring-space normality p-value, and a tri-state transform_normalized
        # flag (NaN=unknown, 1.0=True, 0.0=False). NaN encodes "not computed".
        def _nan(x):
            return float(x) if x is not None else np.nan

        skewness = np.array([_nan(c.skewness) for c in cat_cells], dtype=np.float64)
        kurtosis = np.array([_nan(c.kurtosis) for c in cat_cells], dtype=np.float64)
        normality_p = np.array(
            [_nan(c.normality_p) for c in cat_cells], dtype=np.float64
        )
        transform_normalized = np.array(
            [np.nan if c.transform_normalized is None
             else (1.0 if c.transform_normalized else 0.0)
             for c in cat_cells],
            dtype=np.float64,
        )

        # Percentiles as a (n_cells, n_points) matrix aligned with
        # percentile_points, so the product can derive a robust (percentile-
        # based) z-score. NaN where a cell had too few subjects.
        percentile_points = np.array(_PERCENTILE_POINTS, dtype=np.float64)
        percentiles = np.full(
            (n, len(_PERCENTILE_POINTS)), np.nan, dtype=np.float64
        )
        for i, c in enumerate(cat_cells):
            for j, p in enumerate(_PERCENTILE_POINTS):
                v = c.percentiles.get(str(p))
                if v is not None:
                    percentiles[i, j] = float(v)

        out_path = npz_dir / f"{category}.npz"
        np.savez_compressed(
            out_path,
            bins=bins,
            conditions=conditions,
            channels=channels,
            bands=bands,
            metrics=metrics,
            mean=means,
            sd=sds,
            n=ns,
            log_mean=log_means,
            log_sd=log_sds,
            log_transformed=log_transformed,
            skewness=skewness,
            kurtosis=kurtosis,
            normality_p=normality_p,
            transform_normalized=transform_normalized,
            percentile_points=percentile_points,
            percentiles=percentiles,
        )

        file_manifest[category] = {
            "file": f"{category}.npz",
            "n_cells": n,
            "unique_channels": int(len(set(channels))),
            "unique_bands": sorted(set(bands.tolist())),
            "unique_metrics": sorted(set(metrics.tolist())),
            "size_bytes": out_path.stat().st_size,
        }

    # Write metadata index
    meta = {
        "format_version": 2,
        "total_cells": len(cells),
        "categories": file_manifest,
        "age_bins": sorted(set(c.bin for c in cells)),
        "conditions": sorted(set(c.condition for c in cells)),
    }
    with open(npz_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    return {cat: info["n_cells"] for cat, info in file_manifest.items()}


def _pct_key(p: float) -> str:
    """Format a percentile point as its NormCell.percentiles dict key.

    Matches normative._compute_cell: integer points become "50", fractional
    points become "0.5"/"99.5".
    """
    return str(int(p)) if float(p).is_integer() else str(p)


def _npz_opt(x) -> Optional[float]:
    """NaN in an NPZ float array encodes 'not computed' → None."""
    x = float(x)
    return None if math.isnan(x) else x


def read_norms_npz(npz_dir: PathLike) -> list[NormCell]:
    """Read NormCell objects back from a split NPZ directory.

    Canonical reader for the product/consumers — handles both format_version 1
    (no disclosure arrays) and 2. Note that NPZ never stored CI/PI, so those
    fields come back as None; use norms.json for full fidelity.

    Args:
        npz_dir: Path to the `npz/` directory (contains metadata.json).

    Returns:
        List of NormCell objects across all category files.
    """
    npz_dir = Path(npz_dir)
    meta = json.loads((npz_dir / "metadata.json").read_text())

    cells: list[NormCell] = []
    for _category, info in meta.get("categories", {}).items():
        fpath = npz_dir / info["file"]
        if not fpath.exists():
            continue
        d = np.load(fpath, allow_pickle=False)
        n_cells = len(d["mean"])
        has_disclosure = "skewness" in d.files
        points = d["percentile_points"] if "percentile_points" in d.files else None
        pct_matrix = d["percentiles"] if "percentiles" in d.files else None

        for i in range(n_cells):
            percentiles: dict = {}
            if points is not None and pct_matrix is not None:
                for j in range(len(points)):
                    v = pct_matrix[i, j]
                    if not math.isnan(v):
                        percentiles[_pct_key(float(points[j]))] = float(v)

            transform_normalized = None
            if has_disclosure:
                tn = float(d["transform_normalized"][i])
                transform_normalized = None if math.isnan(tn) else bool(tn >= 0.5)

            cells.append(NormCell(
                bin=str(d["bins"][i]),
                condition=str(d["conditions"][i]),
                channel=str(d["channels"][i]),
                band=str(d["bands"][i]),
                metric=str(d["metrics"][i]),
                n=int(d["n"][i]),
                mean=float(d["mean"][i]),
                sd=float(d["sd"][i]),
                log_mean=_npz_opt(d["log_mean"][i]),
                log_sd=_npz_opt(d["log_sd"][i]),
                log_transformed=bool(d["log_transformed"][i]),
                normality_p=_npz_opt(d["normality_p"][i]) if has_disclosure else None,
                percentiles=percentiles,
                skewness=_npz_opt(d["skewness"][i]) if has_disclosure else None,
                kurtosis=_npz_opt(d["kurtosis"][i]) if has_disclosure else None,
                transform_normalized=transform_normalized,
            ))
    return cells


def robust_z_from_percentiles(
    value: float,
    points,
    row,
    n: int,
    tail_min_n: int = 200,
) -> Optional[float]:
    """Percentile-derived robust z-score — the reference for product parity.

    Mirrors open_normative.compare.compare_to_norms exactly: interpolate the
    value's percentile rank from the stored percentile points, gate the tail
    points (p0.5/p99.5) behind a minimum n, then take the inverse-normal CDF.

    Args:
        value: Patient value.
        points: Percentile points (e.g. NPZ percentile_points).
        row: Percentile values aligned with points (NaN where unavailable).
        n: Cell sample size (drives tail gating).
        tail_min_n: Below this n, clamp the rank to [1, 99].

    Returns:
        Robust z-score, or None if no usable percentiles.
    """
    from open_normative.compare import _interpolate_percentile

    pct: dict = {}
    for p, v in zip(points, row):
        if v is None:
            continue
        fv = float(v)
        if math.isnan(fv):
            continue
        pct[_pct_key(float(p))] = fv
    if not pct:
        return None

    rank = _interpolate_percentile(value, pct)
    if rank is None:
        return None
    lo, hi = (1.0, 99.0) if n < tail_min_n else (0.5, 99.5)
    rank = min(max(rank, lo), hi)
    return float(_norm_dist.ppf(rank / 100.0))


def write_subjects_csv(subjects: list[dict], filepath: PathLike) -> None:
    """Write per-subject metrics to a flat CSV file.

    Flattens the nested metrics dict to columns named
    "<channel>.<band>.<metric>".

    Args:
        subjects: List of subject dicts as produced by pipeline/normative workflow.
            Each dict should have: subject_id, age, sex, condition, metrics.
        filepath: Destination file path.
    """
    if not subjects:
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            fh.write("")
        return

    # Collect all metric keys across all subjects.
    metric_keys: list[str] = []
    seen: set[str] = set()
    for subject in subjects:
        for channel, band_dict in subject.get("metrics", {}).items():
            for band, metric_dict in band_dict.items():
                for metric_name in metric_dict:
                    key = f"{channel}.{band}.{metric_name}"
                    if key not in seen:
                        metric_keys.append(key)
                        seen.add(key)

    meta_fields = ["subject_id", "age", "sex", "condition"]
    fieldnames = meta_fields + sorted(metric_keys)

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for subject in subjects:
            row: dict = {
                "subject_id": subject.get("subject_id", ""),
                "age": subject.get("age", ""),
                "sex": subject.get("sex", ""),
                "condition": subject.get("condition", ""),
            }
            for channel, band_dict in subject.get("metrics", {}).items():
                for band, metric_dict in band_dict.items():
                    for metric_name, value in metric_dict.items():
                        row[f"{channel}.{band}.{metric_name}"] = value
            writer.writerow(row)
