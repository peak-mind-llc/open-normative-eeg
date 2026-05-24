"""Test-retest reliability, reliable-change, and heteroscedasticity.

Wood et al. (2024, PLoS ONE, Simulation 2) show that when EEG parameter
distributions are fat-tailed, measurement error becomes heteroscedastic — it is
larger out in the tails — so an "abnormal" score (far from the mean) is also the
score most likely to drift on its own at retest. This manufactures apparent
"improvements" that are really regression to the mean, and means a single
test-retest reliability number is misleading for tail observations.

This module quantifies that directly from a test-retest dataset:
  - ICC(2,1)         — two-way random, absolute-agreement, single measurement
  - SEM, MDC95       — standard error of measurement and minimal detectable change
  - Bland-Altman     — bias and 95% limits of agreement
  - heteroscedasticity — does |session2 - session1| grow with the level?

Functions take paired arrays (session-1 vs session-2 values across subjects)
and make no Gaussian assumption beyond the ICC model itself.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
from scipy import stats

_Z95 = 1.959963984540054  # norm.ppf(0.975)


def icc_2_1(x1, x2) -> float:
    """ICC(2,1): two-way random effects, absolute agreement, single rater.

    Args:
        x1, x2: Paired measurements (session 1 and session 2) across subjects.

    Returns:
        The intraclass correlation, or NaN if undefined (n < 2).
    """
    X = np.column_stack([np.asarray(x1, dtype=float), np.asarray(x2, dtype=float)])
    n, k = X.shape
    if n < 2:
        return float("nan")

    grand = X.mean()
    row_means = X.mean(axis=1)
    col_means = X.mean(axis=0)

    ss_total = float(((X - grand) ** 2).sum())
    ss_rows = float(k * ((row_means - grand) ** 2).sum())      # between subjects
    ss_cols = float(n * ((col_means - grand) ** 2).sum())      # between sessions
    ss_err = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_err = ss_err / ((n - 1) * (k - 1))

    denom = ms_rows + (k - 1) * ms_err + (k / n) * (ms_cols - ms_err)
    if denom == 0:
        return float("nan")
    return float((ms_rows - ms_err) / denom)


def sem_from_icc(values, icc: float) -> float:
    """Standard error of measurement: SD_pooled * sqrt(1 - ICC) (Weir 2005)."""
    sd = float(np.std(np.asarray(values, dtype=float), ddof=1))
    if not math.isfinite(icc):
        return float("nan")
    return float(sd * math.sqrt(max(0.0, 1.0 - icc)))


def mdc95(sem: float) -> float:
    """Minimal detectable change at 95% confidence: 1.96 * sqrt(2) * SEM."""
    return float(_Z95 * math.sqrt(2.0) * sem)


def bland_altman(x1, x2) -> dict:
    """Bland-Altman bias and 95% limits of agreement for paired measurements."""
    d = np.asarray(x2, dtype=float) - np.asarray(x1, dtype=float)
    bias = float(np.mean(d))
    sd = float(np.std(d, ddof=1)) if len(d) > 1 else 0.0
    return {
        "bias": bias,
        "sd_diff": sd,
        "loa_lower": float(bias - _Z95 * sd),
        "loa_upper": float(bias + _Z95 * sd),
    }


def heteroscedasticity_slope(x1, x2) -> dict:
    """Quantify whether retest differences grow with the measurement level.

    Regresses |session2 - session1| on the per-subject mean level (the
    Bland-Altman x-axis). A positive, significant slope means the tails carry
    more measurement noise than the centre — the Wood et al. mechanism behind
    spurious "normalization". Also reports the variance ratio of differences in
    the top vs bottom level-tertile.
    """
    x1 = np.asarray(x1, dtype=float)
    x2 = np.asarray(x2, dtype=float)
    level = (x1 + x2) / 2.0
    abs_diff = np.abs(x2 - x1)
    diff = x2 - x1
    n = len(level)

    out = {"slope": float("nan"), "r": float("nan"), "p": float("nan"),
           "tail_center_var_ratio": float("nan")}
    if n >= 3 and float(np.std(level)) > 0:
        reg = stats.linregress(level, abs_diff)
        out["slope"] = float(reg.slope)
        out["r"] = float(reg.rvalue)
        out["p"] = float(reg.pvalue)

    if n >= 6:
        order = np.argsort(level)
        t = n // 3
        low = diff[order[:t]]
        high = diff[order[-t:]]
        var_low = float(np.var(low, ddof=1)) if len(low) > 1 else 0.0
        var_high = float(np.var(high, ddof=1)) if len(high) > 1 else 0.0
        if var_low > 0:
            out["tail_center_var_ratio"] = float(var_high / var_low)
    return out


def paired_reliability(x1, x2) -> dict:
    """Full reliability summary for one metric's paired test-retest values."""
    x1 = np.asarray(x1, dtype=float)
    x2 = np.asarray(x2, dtype=float)
    n = len(x1)
    icc = icc_2_1(x1, x2)
    pooled = np.concatenate([x1, x2])
    sem = sem_from_icc(pooled, icc)
    mdc = mdc95(sem)
    abs_diff = np.abs(x2 - x1)
    frac_exceeding = float(np.mean(abs_diff > mdc)) if (n > 0 and math.isfinite(mdc)) else float("nan")

    ba = bland_altman(x1, x2)
    het = heteroscedasticity_slope(x1, x2)

    return {
        "n": int(n),
        "mean_session1": float(np.mean(x1)),
        "mean_session2": float(np.mean(x2)),
        "icc": icc,
        "sem": sem,
        "mdc95": mdc,
        "frac_exceeding_mdc": frac_exceeding,
        "bias": ba["bias"],
        "sd_diff": ba["sd_diff"],
        "loa_lower": ba["loa_lower"],
        "loa_upper": ba["loa_upper"],
        "ba_slope": het["slope"],
        "ba_slope_p": het["p"],
        "tail_center_var_ratio": het["tail_center_var_ratio"],
    }


def _flatten_metrics(metrics: dict) -> dict:
    """Flatten a nested {channel: {band: {metric: value}}} dict to
    {(channel, band, metric): float}, dropping non-numeric / NaN values."""
    flat: dict[tuple[str, str, str], float] = {}
    for channel, band_dict in metrics.items():
        for band, metric_dict in band_dict.items():
            for metric_name, value in metric_dict.items():
                if not isinstance(value, (int, float)):
                    continue
                if isinstance(value, float) and math.isnan(value):
                    continue
                flat[(channel, band, metric_name)] = float(value)
    return flat


def build_paired_arrays(
    records: list[dict],
    sessions: tuple[str, str] = ("session1", "session2"),
) -> dict[tuple[str, str, str, str], tuple[np.ndarray, np.ndarray]]:
    """Pair two sessions per subject into per-metric arrays.

    Args:
        records: Processed-subject dicts, each with keys subject_id, session,
            condition, and a nested metrics dict.
        sessions: The two session labels to pair (test, retest).

    Returns:
        Dict keyed by (condition, channel, band, metric) → (session1_values,
        session2_values), including only subjects present in BOTH sessions for
        that condition and metric. Arrays are aligned by subject.
    """
    s1, s2 = sessions
    # (subject, condition) -> {session: flat metrics}
    by_subject_cond: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for r in records:
        key = (r["subject_id"], r["condition"])
        by_subject_cond[key][r["session"]] = _flatten_metrics(r.get("metrics", {}))

    pairs: dict[tuple, tuple[list, list]] = defaultdict(lambda: ([], []))
    for (subject, condition), sess in by_subject_cond.items():
        if s1 not in sess or s2 not in sess:
            continue
        common = set(sess[s1]) & set(sess[s2])
        for (channel, band, metric) in common:
            pk = (condition, channel, band, metric)
            pairs[pk][0].append(sess[s1][(channel, band, metric)])
            pairs[pk][1].append(sess[s2][(channel, band, metric)])

    return {
        k: (np.asarray(a, dtype=float), np.asarray(b, dtype=float))
        for k, (a, b) in pairs.items()
    }


def reliability_table(
    paired: dict[tuple, tuple[np.ndarray, np.ndarray]],
    min_n: int = 10,
) -> list[dict]:
    """Compute the per-metric reliability table from paired arrays.

    Args:
        paired: Output of build_paired_arrays.
        min_n: Skip metrics with fewer than this many paired subjects.

    Returns:
        List of row dicts (condition/channel/band/metric + reliability stats),
        sorted by ICC ascending so the least-reliable metrics surface first.
    """
    rows = []
    for (condition, channel, band, metric), (x1, x2) in paired.items():
        if len(x1) < min_n:
            continue
        stats_row = paired_reliability(x1, x2)
        rows.append({
            "condition": condition, "channel": channel,
            "band": band, "metric": metric, **stats_row,
        })
    rows.sort(key=lambda r: (r["icc"] if math.isfinite(r["icc"]) else 1.0))
    return rows


def summarize_reliability(
    rows: list[dict],
    low_icc: float = 0.70,
    alpha: float = 0.05,
) -> dict:
    """Aggregate a reliability table into headline numbers.

    Counts metrics with poor reliability (ICC < low_icc) and metrics showing
    significant heteroscedasticity (positive Bland-Altman slope, p < alpha) —
    the latter being the Wood et al. signature of tail noise that drives
    spurious "normalization".
    """
    if not rows:
        return {"n_metrics": 0, "median_icc": None, "n_low_icc": 0,
                "frac_low_icc": None, "n_heteroscedastic": 0,
                "frac_heteroscedastic": None, "median_frac_exceeding_mdc": None}

    iccs = [r["icc"] for r in rows if math.isfinite(r.get("icc", float("nan")))]
    n_low = sum(1 for r in rows if math.isfinite(r.get("icc", float("nan")))
                and r["icc"] < low_icc)
    n_het = sum(1 for r in rows
                if r.get("ba_slope_p") is not None
                and math.isfinite(r["ba_slope_p"])
                and r["ba_slope_p"] < alpha and r.get("ba_slope", 0) > 0)
    fracs = [r["frac_exceeding_mdc"] for r in rows
             if r.get("frac_exceeding_mdc") is not None
             and math.isfinite(r["frac_exceeding_mdc"])]
    n = len(rows)
    return {
        "n_metrics": n,
        "median_icc": float(np.median(iccs)) if iccs else None,
        "n_low_icc": n_low,
        "frac_low_icc": n_low / n,
        "n_heteroscedastic": n_het,
        "frac_heteroscedastic": n_het / n,
        "median_frac_exceeding_mdc": float(np.median(fracs)) if fracs else None,
    }
