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
}


def _is_log_transform(metric: str, band: str) -> bool:
    """Decide whether a (band, metric) cell should be log-transformed.

    Power metrics are flagged by name. Ratio cells are stored with the
    ratio expression as the band (e.g. "Theta/Beta", "corrected_Alpha/Theta",
    "(Delta+Theta)/(Alpha+Beta)") and metric "value" — detect them by the
    presence of "/" in the band name.
    """
    if metric in _LOG_TRANSFORM_METRICS:
        return True
    return "/" in band


def _scoring_space(arr: np.ndarray, metric: str, band: str) -> np.ndarray:
    """Return the values in the space the z-score is computed in.

    Log-transformed metrics are scored in natural-log space, so their
    distribution properties (normality, intervals) must be evaluated there —
    not on the raw, right-skewed values. Non-positive values are dropped for
    log metrics (matching the log-mean/sd computation).
    """
    if _is_log_transform(metric, band):
        return np.log(arr[arr > 0])
    return arr


# Shapiro-Wilk significance level: scoring-space p below this means the
# distribution the z-score uses is not Gaussian, so the parametric z over- or
# under-flags in the tails (Wood et al. 2024).
_NORMALITY_ALPHA = 0.05

# Tail points (0.5/2.5/97.5/99.5) widen the percentile-derived robust-z range
# toward ±2.58σ. They require large n to be stable — consumers gate on n.
_PERCENTILE_POINTS = [0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99, 99.5]

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
        normality_p: Shapiro-Wilk p-value of the SCORING space — log space for
            log-transformed metrics, raw values otherwise (None if n < 3). This
            is the distribution the z-score actually uses, so it governs how
            trustworthy the parametric z is.
        percentiles: Dict of {"0.5": value, "1": ..., ..., "99.5": value}.
        ci_lower/ci_upper: 95% CI for the mean (geometric, in raw units, for
            log metrics).
        pi_lower/pi_upper: 95% prediction interval for a new individual
            (asymmetric in raw units for log metrics).
        skewness: Skewness of the RAW values (Wood et al. disclosure ask).
        kurtosis: Excess (Fisher) kurtosis of the RAW values.
        transform_normalized: Whether the scoring space passes the Shapiro test
            (normality_p >= alpha) — i.e. whether the transform actually
            achieved approximate Gaussianity (None if n < 3).
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
    pi_lower: Optional[float] = None
    pi_upper: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    transform_normalized: Optional[bool] = None
    # NOTE: `sex` is conceptually a key field (alongside bin/condition/channel/band/
    # metric) but Python dataclass rules require defaulted fields after non-defaulted
    # ones, so it lives at the end. Lookups and serialization go by name, so the
    # position is cosmetic only. Legal values: "pooled", "F", "M".
    sex: str = "pooled"


def _compute_cell(
    values: list[float],
    bin_label: str,
    condition: str,
    channel: str,
    band: str,
    metric: str,
    sex: str = "pooled",
) -> NormCell:
    """Compute statistics for a single norm cell from a list of values."""
    arr = np.array(values, dtype=float)
    n = len(arr)
    mean = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    # Log-transform if applicable.
    log_transformed = _is_log_transform(metric, band)
    log_mean = None
    log_sd = None
    n_log = 0
    if log_transformed:
        positive = arr[arr > 0]
        n_log = len(positive)
        if n_log > 0:
            log_arr = np.log(positive)
            log_mean = float(np.mean(log_arr))
            log_sd = float(np.std(log_arr, ddof=1)) if n_log > 1 else 0.0

    # Distribution shape of the RAW values — Wood et al. (2024) ask qEEG
    # databases to disclose skewness and kurtosis, since slight departures from
    # Gaussian inflate tail false positives.
    skewness = None
    kurtosis = None
    if n >= 3 and sd > 0:
        skewness = float(stats.skew(arr))
        kurtosis = float(stats.kurtosis(arr, fisher=True))

    # Shapiro-Wilk normality test on the SCORING space (log space for log
    # metrics) — this is the distribution the z-score actually uses, so it is
    # what determines whether the parametric z is trustworthy. transform_
    # normalized flags whether the transform actually achieved Gaussianity.
    normality_p = None
    transform_normalized = None
    scoring = _scoring_space(arr, metric, band)
    if len(scoring) >= 3 and float(np.std(scoring, ddof=1)) > 0:
        try:
            _, p = stats.shapiro(scoring)
            normality_p = float(p)
            transform_normalized = bool(normality_p >= _NORMALITY_ALPHA)
        except Exception:
            normality_p = None
            transform_normalized = None

    # Percentiles.
    percentiles: dict = {}
    if n >= 2:
        for p in _PERCENTILE_POINTS:
            percentiles[str(p)] = float(np.percentile(arr, p))
    elif n == 1:
        for p in _PERCENTILE_POINTS:
            percentiles[str(p)] = mean

    # 95% CI for the mean and 95% prediction interval for a new individual.
    # For log metrics these are computed in log space and exponentiated, giving
    # asymmetric, strictly-positive intervals in raw units (a symmetric raw-
    # space interval is wrong for skewed power — it can even go negative).
    ci_lower = ci_upper = None
    pi_lower = pi_upper = None
    if log_transformed and log_sd is not None and log_sd > 0 and n_log >= 2:
        t_crit = float(stats.t.ppf(0.975, df=n_log - 1))
        se_log = log_sd / np.sqrt(n_log)
        spread = log_sd * np.sqrt(1 + 1 / n_log)
        ci_lower = float(np.exp(log_mean - t_crit * se_log))
        ci_upper = float(np.exp(log_mean + t_crit * se_log))
        pi_lower = float(np.exp(log_mean - t_crit * spread))
        pi_upper = float(np.exp(log_mean + t_crit * spread))
    elif not log_transformed and n >= 2 and sd > 0:
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
        se = sd / np.sqrt(n)
        ci_lower = float(mean - t_crit * se)
        ci_upper = float(mean + t_crit * se)
        pi_lower = float(mean - t_crit * sd * np.sqrt(1 + 1 / n))
        pi_upper = float(mean + t_crit * sd * np.sqrt(1 + 1 / n))

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
        pi_lower=pi_lower,
        pi_upper=pi_upper,
        skewness=skewness,
        kurtosis=kurtosis,
        transform_normalized=transform_normalized,
        sex=sex,
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

    # Accumulate values: key = (bin, sex, condition, channel, band, metric).
    # Each subject contributes to ("pooled", ...) always, plus
    # (subject.sex, ...) when sex is "F" or "M". Subjects with empty / "Other" /
    # unrecognised sex contribute only to pooled — no own-sex cell ships.
    accumulator: dict[tuple, list[float]] = {}

    for subject in subjects:
        age = subject["age"]
        cond = subject["condition"]
        if cond not in all_conditions:
            continue

        bin_label = _assign_bin(age, age_bins)
        if bin_label is None:
            continue

        raw_sex = str(subject.get("sex", "") or "").strip().upper()
        subject_sex = raw_sex if raw_sex in {"F", "M"} else None

        metrics = subject.get("metrics", {})
        for channel, band_dict in metrics.items():
            for band, metric_dict in band_dict.items():
                for metric_name, value in metric_dict.items():
                    if value is None or (
                        isinstance(value, float) and np.isnan(value)
                    ):
                        continue
                    if not isinstance(value, (int, float)):
                        continue

                    pooled_key = (bin_label, "pooled", cond, channel, band, metric_name)
                    accumulator.setdefault(pooled_key, []).append(float(value))
                    if subject_sex is not None:
                        sex_key = (bin_label, subject_sex, cond, channel, band, metric_name)
                        accumulator.setdefault(sex_key, []).append(float(value))

    # Build NormCell for each collected key.
    cells = []
    for (bin_label, sex, cond, channel, band, metric_name), values in sorted(
        accumulator.items()
    ):
        cell = _compute_cell(
            values=values,
            bin_label=bin_label,
            condition=cond,
            channel=channel,
            band=band,
            metric=metric_name,
            sex=sex,
        )
        cells.append(cell)

    return cells
