"""Normative distribution builder.

Takes per-subject metric dicts (from process_resting or equivalent),
groups them into age bins × condition cells, and computes descriptive
statistics with optional log-transformation for skewed metrics.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats


# Metrics that are right-skewed and benefit from log-transformation.
_LOG_TRANSFORM_METRICS = {
    "absolute_power",
    "corrected_absolute_power",
    "gsf_absolute_power",
    "Theta/Beta",
    "Theta/Beta1",
    "Delta/HighBeta",
    "Alpha/HighBeta",
}

_PERCENTILE_POINTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]

_DEFAULT_AGE_BINS = [20, 30, 40, 50, 60, 70, 80]


def _bin_label(lower: int, upper: int) -> str:
    """Format a bin label like '20-29'."""
    return f"{lower}-{upper - 1}"


def _assign_bin(age: int | float, bins: list[int]) -> Optional[str]:
    """Return the bin label for an age given sorted bin edges.

    Args:
        age: Subject age.
        bins: Sorted list of bin edge values (e.g. [20, 30, 40, ...]).
              The last value is the exclusive upper bound of the final bin.

    Returns:
        Bin label string like "20-29", or None if age is out of range.
    """
    import math
    if math.isnan(age) or age < bins[0] or age >= bins[-1]:
        return None
    idx = bisect.bisect_right(bins, age) - 1
    return _bin_label(bins[idx], bins[idx + 1])


@dataclass
class NormCell:
    """Statistics for one (bin, condition, channel, band, metric) cell.

    Fields:
        bin: Age bin label, e.g. "20-29".
        condition: Recording condition, e.g. "eo" or "ec".
        channel: Channel name, e.g. "Fz".
        band: Band name, e.g. "Alpha".
        metric: Metric name, e.g. "absolute_power".
        n: Number of subjects in this cell.
        mean: Arithmetic mean of the raw values.
        sd: Standard deviation of the raw values.
        log_mean: Mean of log-transformed values (None if not log-transformed).
        log_sd: SD of log-transformed values (None if not log-transformed).
        log_transformed: Whether log transformation was applied.
        normality_p: Shapiro-Wilk p-value (None if n < 3).
        percentiles: Dict of {"1": value, "5": ..., ..., "99": value}.
    """

    bin: str
    condition: str
    channel: str
    band: str
    metric: str
    n: int
    mean: float
    sd: float
    log_mean: Optional[float]
    log_sd: Optional[float]
    log_transformed: bool
    normality_p: Optional[float]
    percentiles: dict
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None


def _compute_cell(
    values: list[float],
    bin_label: str,
    condition: str,
    channel: str,
    band: str,
    metric: str,
) -> NormCell:
    """Compute statistics for a single norm cell from a list of values."""
    arr = np.array(values, dtype=float)
    n = len(arr)
    mean = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    # Log-transform if applicable.
    log_transformed = metric in _LOG_TRANSFORM_METRICS
    log_mean = None
    log_sd = None
    if log_transformed:
        positive = arr[arr > 0]
        if len(positive) > 0:
            log_arr = np.log(positive)
            log_mean = float(np.mean(log_arr))
            log_sd = float(np.std(log_arr, ddof=1)) if len(log_arr) > 1 else 0.0

    # Shapiro-Wilk normality test (requires n >= 3).
    normality_p = None
    if n >= 3:
        try:
            _, normality_p = stats.shapiro(arr)
            normality_p = float(normality_p)
        except Exception:
            normality_p = None

    # Percentiles.
    percentiles: dict = {}
    if n >= 2:
        for p in _PERCENTILE_POINTS:
            percentiles[str(p)] = float(np.percentile(arr, p))
    elif n == 1:
        for p in _PERCENTILE_POINTS:
            percentiles[str(p)] = mean

    # 95% confidence interval for the mean.
    ci_lower = None
    ci_upper = None
    if n >= 2 and sd > 0:
        se = sd / np.sqrt(n)
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
        ci_lower = float(mean - t_crit * se)
        ci_upper = float(mean + t_crit * se)

    return NormCell(
        bin=bin_label,
        condition=condition,
        channel=channel,
        band=band,
        metric=metric,
        n=n,
        mean=mean,
        sd=sd,
        log_mean=log_mean,
        log_sd=log_sd,
        log_transformed=log_transformed,
        normality_p=normality_p,
        percentiles=percentiles,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
    )


def build_normative(
    subjects: list[dict],
    age_bins: Optional[list[int]] = None,
    conditions: Optional[list[str]] = None,
) -> list[NormCell]:
    """Build a normative database from per-subject metric dicts.

    Each subject dict must have:
        - "age": int or float
        - "condition": str (e.g. "eo")
        - "metrics": nested dict {channel: {band: {metric: value}}}

    Args:
        subjects: List of subject dicts (see above).
        age_bins: Sorted list of bin edge values. Defaults to _DEFAULT_AGE_BINS.
            The last value is the exclusive upper bound of the final bin.
        conditions: Filter to only these conditions. Defaults to all conditions
            found in subjects.

    Returns:
        List of NormCell objects, one per (bin, condition, channel, band, metric).
    """
    if age_bins is None:
        age_bins = _DEFAULT_AGE_BINS

    # Collect all condition values found in data if not filtered.
    all_conditions = {s["condition"] for s in subjects}
    if conditions is not None:
        all_conditions = all_conditions & set(conditions)

    # Accumulate values: key = (bin, condition, channel, band, metric)
    accumulator: dict[tuple, list[float]] = {}

    for subject in subjects:
        age = subject["age"]
        cond = subject["condition"]
        if cond not in all_conditions:
            continue

        bin_label = _assign_bin(age, age_bins)
        if bin_label is None:
            continue

        metrics = subject.get("metrics", {})
        for channel, band_dict in metrics.items():
            for band, metric_dict in band_dict.items():
                for metric_name, value in metric_dict.items():
                    if value is None or (
                        isinstance(value, float) and np.isnan(value)
                    ):
                        continue
                    key = (bin_label, cond, channel, band, metric_name)
                    if key not in accumulator:
                        accumulator[key] = []
                    accumulator[key].append(float(value))

    # Build NormCell for each collected key.
    cells = []
    for (bin_label, cond, channel, band, metric_name), values in sorted(
        accumulator.items()
    ):
        cell = _compute_cell(
            values=values,
            bin_label=bin_label,
            condition=cond,
            channel=channel,
            band=band,
            metric=metric_name,
        )
        cells.append(cell)

    return cells
