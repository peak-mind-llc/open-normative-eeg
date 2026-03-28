"""Normative comparison: z-scores and percentile ranks for clinical EEG.

Given a clinical subject's metrics and a normative database, computes
z-scores (using log-transformation when appropriate) and interpolated
percentile ranks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from open_normative.normative import NormCell, _LOG_TRANSFORM_METRICS


@dataclass
class ComparisonResult:
    """Comparison of one clinical metric against the normative distribution.

    Fields:
        channel: EEG channel name.
        band: Frequency band name.
        metric: Metric name.
        value: Raw clinical value.
        z_score: Z-score relative to the matched normative cell.
            Computed in log-space for log-transformed metrics.
        percentile_rank: Interpolated percentile rank (0–100).
        norm_mean: Normative cell mean (raw).
        norm_sd: Normative cell SD (raw).
        norm_n: Number of subjects in the matched normative cell.
        bin: Age bin label of the matched cell.
        low_confidence: True when norm_n < 10.
    """

    channel: str
    band: str
    metric: str
    value: float
    z_score: Optional[float]
    percentile_rank: Optional[float]
    norm_mean: float
    norm_sd: float
    norm_n: int
    bin: str
    low_confidence: bool


def _match_bin(age: int | float, bin_label: str) -> bool:
    """Return True if age falls within a bin label like '20-29'.

    Args:
        age: Subject age.
        bin_label: String of the form "low-high" where both bounds are integers.
            The range is inclusive: age is in [low, high].

    Returns:
        True if age is within the bin, False otherwise.
    """
    try:
        low_str, high_str = bin_label.split("-")
        low = int(low_str)
        high = int(high_str)
        return low <= age <= high
    except (ValueError, AttributeError):
        return False


def _interpolate_percentile(value: float, percentiles: dict) -> Optional[float]:
    """Interpolate the percentile rank of a value using stored percentile points.

    Uses piecewise linear interpolation between adjacent stored percentile
    points. Values below the 1st or above the 99th percentile are clamped.

    Args:
        value: The clinical value to rank.
        percentiles: Dict mapping percentile string keys (e.g. "50") to values.

    Returns:
        Estimated percentile rank from 0 to 100, or None if insufficient data.
    """
    if not percentiles:
        return None

    # Build sorted list of (percentile, boundary_value) pairs.
    points: list[tuple[float, float]] = []
    for k, v in percentiles.items():
        try:
            pct = float(k)
            val = float(v)
            points.append((pct, val))
        except (ValueError, TypeError):
            continue

    if not points:
        return None

    points.sort(key=lambda x: x[1])  # sort by boundary value

    # Handle edge cases: below minimum or above maximum stored value.
    if value <= points[0][1]:
        return points[0][0]
    if value >= points[-1][1]:
        return points[-1][0]

    # Linear interpolation between adjacent points.
    for i in range(len(points) - 1):
        p_lo, v_lo = points[i]
        p_hi, v_hi = points[i + 1]
        if v_lo <= value <= v_hi:
            if v_hi == v_lo:
                return (p_lo + p_hi) / 2.0
            t = (value - v_lo) / (v_hi - v_lo)
            return p_lo + t * (p_hi - p_lo)

    return None


def compare_to_norms(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
) -> list[ComparisonResult]:
    """Compare clinical metrics against a normative database.

    Matches the subject's age to an age bin, filters norms by condition,
    and for each matching (channel, band, metric) cell computes a z-score
    and interpolated percentile rank.

    Log-transformation is applied to metrics in _LOG_TRANSFORM_METRICS
    before computing z-scores (using log_mean / log_sd from the cell).

    Args:
        metrics: Nested dict {channel: {band: {metric: value}}}.
        norms: List of NormCell objects (from build_normative or read_norms_json).
        age: Clinical subject's age.
        condition: Recording condition (e.g. "eo").

    Returns:
        List of ComparisonResult, one per matched (channel, band, metric).
        Cells without a matching age bin or condition are silently skipped.
    """
    # Index norms by (bin, condition, channel, band, metric) for fast lookup.
    norm_index: dict[tuple, NormCell] = {}
    for cell in norms:
        if cell.condition == condition and _match_bin(age, cell.bin):
            key = (cell.channel, cell.band, cell.metric)
            # If multiple bins match (shouldn't happen normally), prefer the
            # one with more subjects.
            if key not in norm_index or cell.n > norm_index[key].n:
                norm_index[key] = cell

    results: list[ComparisonResult] = []

    for channel, band_dict in metrics.items():
        for band, metric_dict in band_dict.items():
            for metric_name, value in metric_dict.items():
                key = (channel, band, metric_name)
                cell = norm_index.get(key)
                if cell is None:
                    continue

                if value is None or (isinstance(value, float) and math.isnan(value)):
                    continue

                raw_value = float(value)

                # Compute z-score.
                z_score: Optional[float] = None
                use_log = (
                    metric_name in _LOG_TRANSFORM_METRICS
                    and cell.log_transformed
                    and cell.log_mean is not None
                    and cell.log_sd is not None
                    and cell.log_sd > 0
                    and raw_value > 0
                )
                if use_log:
                    log_val = math.log(raw_value)
                    z_score = (log_val - cell.log_mean) / cell.log_sd
                elif cell.sd > 0:
                    z_score = (raw_value - cell.mean) / cell.sd
                elif cell.mean != 0:
                    z_score = (raw_value - cell.mean) / abs(cell.mean)
                else:
                    z_score = 0.0

                # Interpolate percentile rank.
                pct_rank = _interpolate_percentile(raw_value, cell.percentiles)

                results.append(
                    ComparisonResult(
                        channel=channel,
                        band=band,
                        metric=metric_name,
                        value=raw_value,
                        z_score=z_score,
                        percentile_rank=pct_rank,
                        norm_mean=cell.mean,
                        norm_sd=cell.sd,
                        norm_n=cell.n,
                        bin=cell.bin,
                        low_confidence=cell.n < 10,
                    )
                )

    return results
