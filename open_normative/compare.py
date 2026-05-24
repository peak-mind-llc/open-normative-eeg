"""Normative comparison: z-scores, percentile ranks, and clinical reports.

Given a clinical subject's metrics and a normative database, computes
z-scores (using log-transformation when appropriate), interpolated
percentile ranks, and enriched clinical comparison reports with
statistical transparency features.
"""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.stats import norm as _norm_dist

from open_normative.normative import NormCell, _is_log_transform


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
        robust_z: Percentile-derived z-score (inverse-normal of the empirical
            percentile rank). Makes no Gaussian assumption, so it diverges from
            z_score exactly when the distribution is non-normal.
        normality_p: Scoring-space Shapiro p-value of the matched cell.
        parametric_z_unreliable: True when normality_p < alpha — the parametric
            z (and its ±2/±3 cutoffs) over- or under-flag in the tails.
        z_discrepancy: |z_score - robust_z|.
        z_discrepancy_flag: True when z_discrepancy exceeds the threshold.
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
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    p_value: Optional[float] = None
    fdr_significant: Optional[bool] = None
    fdr_threshold: Optional[float] = None
    robust_z: Optional[float] = None
    normality_p: Optional[float] = None
    parametric_z_unreliable: bool = False
    z_discrepancy: Optional[float] = None
    z_discrepancy_flag: bool = False


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


def apply_fdr_correction(
    results: list[ComparisonResult],
    alpha: float = 0.05,
) -> list[ComparisonResult]:
    """Apply Benjamini-Hochberg FDR correction to comparison results.

    Computes two-tailed p-values from z-scores, applies the BH procedure,
    and sets p_value, fdr_significant, and fdr_threshold on each result.

    Args:
        results: List of ComparisonResult with z_scores computed.
        alpha: FDR significance level (default 0.05).

    Returns:
        The same list, modified in place, with FDR fields populated.
    """
    # Collect results with valid z-scores
    valid = [(i, r) for i, r in enumerate(results) if r.z_score is not None]
    if not valid:
        return results

    # Compute two-tailed p-values
    for idx, r in valid:
        r.p_value = float(2.0 * (1.0 - _norm_dist.cdf(abs(r.z_score))))

    # Sort by p-value for BH procedure
    p_sorted = sorted(valid, key=lambda x: x[1].p_value)
    m = len(p_sorted)

    # Find the largest k where p(k) <= alpha * k / m
    max_k = -1
    for k, (idx, r) in enumerate(p_sorted):
        threshold = alpha * (k + 1) / m
        r.fdr_threshold = float(threshold)
        if r.p_value <= threshold:
            max_k = k

    # All tests up to max_k are significant
    for k, (idx, r) in enumerate(p_sorted):
        r.fdr_significant = k <= max_k if max_k >= 0 else False

    return results


def compare_to_norms(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
    apply_fdr: bool = True,
    fdr_alpha: float = 0.05,
    robust_config: Optional[dict] = None,
) -> list[ComparisonResult]:
    """Compare clinical metrics against a normative database.

    Matches the subject's age to an age bin, filters norms by condition,
    and for each matching (channel, band, metric) cell computes a z-score
    and interpolated percentile rank.

    Log-transformation is applied to metrics flagged by _is_log_transform()
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
    if robust_config is None:
        from open_normative.parameters import REPORT_PARAMS
        robust_config = REPORT_PARAMS.get("robust_z", {})
    normality_alpha = robust_config.get("normality_alpha", 0.05)
    discrepancy_threshold = robust_config.get("discrepancy_threshold", 1.0)
    tail_min_n = robust_config.get("tail_percentile_min_n", 200)

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
                    _is_log_transform(metric_name, band)
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

                # Percentile-derived robust z — inverse-normal of the empirical
                # rank. Tail points (p0.5/p99.5) need large n to be stable; below
                # the gate, clamp the rank to [1, 99] so the robust z doesn't
                # over-reach into tails the sample can't actually resolve.
                robust_z: Optional[float] = None
                if pct_rank is not None:
                    lo, hi = (1.0, 99.0) if cell.n < tail_min_n else (0.5, 99.5)
                    clamped = min(max(pct_rank, lo), hi)
                    robust_z = float(_norm_dist.ppf(clamped / 100.0))

                normality_p = getattr(cell, "normality_p", None)
                parametric_unreliable = (
                    normality_p is not None and normality_p < normality_alpha
                )
                z_discrepancy: Optional[float] = None
                z_discrepancy_flag = False
                if z_score is not None and robust_z is not None:
                    z_discrepancy = abs(z_score - robust_z)
                    z_discrepancy_flag = z_discrepancy > discrepancy_threshold

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
                        ci_lower=getattr(cell, "ci_lower", None),
                        ci_upper=getattr(cell, "ci_upper", None),
                        robust_z=robust_z,
                        normality_p=normality_p,
                        parametric_z_unreliable=parametric_unreliable,
                        z_discrepancy=z_discrepancy,
                        z_discrepancy_flag=z_discrepancy_flag,
                    )
                )

    if apply_fdr:
        apply_fdr_correction(results, alpha=fdr_alpha)

    return results


# ---------------------------------------------------------------------------
# Enrichment: SE(z), Cohen's d, severity labels
# ---------------------------------------------------------------------------


def compute_se_z(z: float, n: int) -> Optional[float]:
    """Standard error of a z-score given normative sample size.

    SE_z = sqrt(1/n + z²/(2n)) — quantifies how much the z-score itself
    would vary if the normative database were re-sampled.

    Args:
        z: The z-score.
        n: Normative sample size.

    Returns:
        Standard error, or None if n < 2.
    """
    if n < 2:
        return None
    return float(math.sqrt(1.0 / n + (z * z) / (2.0 * n)))


def compute_cohen_d(value: float, mean: float, sd: float) -> Optional[float]:
    """Cohen's d effect size (same as z-score for raw-space metrics).

    Args:
        value: Clinical value.
        mean: Normative mean.
        sd: Normative SD.

    Returns:
        Cohen's d, or None if sd is 0.
    """
    if sd <= 0:
        return None
    return float((value - mean) / sd)


def classify_cohen_d(
    d: float,
    thresholds: Optional[dict] = None,
) -> str:
    """Classify Cohen's d magnitude into interpretive labels.

    Args:
        d: Cohen's d value (sign is ignored).
        thresholds: Dict with "small", "medium", "large" float thresholds.
            Defaults to 0.2 / 0.5 / 0.8.

    Returns:
        One of "negligible", "small", "medium", "large".
    """
    if thresholds is None:
        thresholds = {"small": 0.2, "medium": 0.5, "large": 0.8}
    ad = abs(d)
    if ad >= thresholds["large"]:
        return "large"
    if ad >= thresholds["medium"]:
        return "medium"
    if ad >= thresholds["small"]:
        return "small"
    return "negligible"


def assign_severity_label(
    z: float,
    thresholds: Optional[list[float]] = None,
    labels: Optional[list[str]] = None,
) -> str:
    """Map a z-score to a clinical severity tier.

    Uses absolute value of z against ordered thresholds. Labels list
    must have one more element than thresholds (the below-first label).

    Args:
        z: Z-score value.
        thresholds: Ascending list of |z| thresholds. Default: [0.5, 1.0, 1.5, 2.0, 3.0].
        labels: Labels for each tier. Default: Within typical → Extremely atypical.

    Returns:
        Severity label string.
    """
    if thresholds is None:
        thresholds = [0.5, 1.0, 1.5, 2.0, 3.0]
    if labels is None:
        labels = [
            "Within typical limits",
            "Mildly atypical",
            "Moderately atypical",
            "Notably atypical",
            "Markedly atypical",
            "Extremely atypical",
        ]
    idx = bisect.bisect_right(thresholds, abs(z))
    return labels[min(idx, len(labels) - 1)]


# ---------------------------------------------------------------------------
# Enriched result and pattern detection
# ---------------------------------------------------------------------------


@dataclass
class EnrichedResult:
    """A ComparisonResult enriched with derived clinical statistics."""

    base: ComparisonResult
    se_z: Optional[float] = None
    cohen_d: Optional[float] = None
    cohen_d_label: str = "negligible"
    severity_label: str = "Within typical limits"
    pi_lower: Optional[float] = None
    pi_upper: Optional[float] = None
    within_prediction_interval: Optional[bool] = None
    log_transformed: bool = False
    normality_p: Optional[float] = None


@dataclass
class DeviationCluster:
    """A group of spatially adjacent channels with same-direction deviations."""

    channels: list[str]
    band: str
    metric: str
    direction: str  # "elevated" or "reduced"
    mean_z: float
    max_z: float


def detect_global_patterns(
    results: list[EnrichedResult],
    channels: list[str],
    fraction_threshold: float = 0.6,
    z_threshold: float = 1.5,
) -> list[dict]:
    """Detect global (non-focal) patterns across channels.

    For each (band, metric), if >= fraction_threshold of channels deviate
    in the same direction with |z| > z_threshold, flag as global pattern.

    Returns:
        List of dicts with band, metric, direction, fraction, channel_count,
        total_channels, interpretation.
    """
    channels_set = set(channels)
    # Group results by (band, metric)
    groups: dict[tuple[str, str], list[EnrichedResult]] = defaultdict(list)
    for er in results:
        if er.base.channel in channels_set:
            groups[(er.base.band, er.base.metric)].append(er)

    patterns = []
    for (band, metric), group in groups.items():
        if not group:
            continue
        pos = [er for er in group if er.base.z_score is not None and er.base.z_score > z_threshold]
        neg = [er for er in group if er.base.z_score is not None and er.base.z_score < -z_threshold]
        total = len(group)

        for direction, deviant in [("elevated", pos), ("reduced", neg)]:
            frac = len(deviant) / total if total > 0 else 0
            if frac >= fraction_threshold:
                patterns.append({
                    "band": band,
                    "metric": metric,
                    "direction": direction,
                    "fraction": round(frac, 2),
                    "channel_count": len(deviant),
                    "total_channels": total,
                    "interpretation": (
                        f"Global {direction} in {band} {metric} across "
                        f"{len(deviant)}/{total} channels ({frac:.0%}) suggests "
                        f"a non-focal process."
                    ),
                })
    return patterns


def detect_deviation_clusters(
    results: list[EnrichedResult],
    adjacency: dict[str, list[str]],
    z_threshold: float = 1.5,
) -> list[DeviationCluster]:
    """Find spatially connected clusters of same-direction deviations.

    Uses BFS on the 19-channel adjacency graph to find connected components
    of channels where |z| > z_threshold and z has the same sign.

    Returns:
        List of DeviationCluster objects (only clusters with 2+ channels).
    """
    # Group results by (band, metric)
    groups: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for er in results:
        if er.base.z_score is not None and er.base.channel in adjacency:
            groups[(er.base.band, er.base.metric)][er.base.channel] = er.base.z_score

    clusters = []
    for (band, metric), ch_z in groups.items():
        for direction, sign_check in [("elevated", lambda z: z > z_threshold),
                                       ("reduced", lambda z: z < -z_threshold)]:
            deviant = {ch for ch, z in ch_z.items() if sign_check(z)}
            visited: set[str] = set()

            for start_ch in deviant:
                if start_ch in visited:
                    continue
                # BFS
                component = []
                queue = [start_ch]
                while queue:
                    ch = queue.pop(0)
                    if ch in visited:
                        continue
                    visited.add(ch)
                    if ch in deviant:
                        component.append(ch)
                        for neighbor in adjacency.get(ch, []):
                            if neighbor not in visited and neighbor in deviant:
                                queue.append(neighbor)

                if len(component) >= 2:
                    z_vals = [abs(ch_z[c]) for c in component]
                    clusters.append(DeviationCluster(
                        channels=sorted(component),
                        band=band,
                        metric=metric,
                        direction=direction,
                        mean_z=round(float(np.mean(z_vals)), 2),
                        max_z=round(float(np.max(z_vals)), 2),
                    ))
    return clusters


def detect_metric_disagreements(
    results: list[EnrichedResult],
    z_threshold: float = 1.5,
) -> list[dict]:
    """Detect disagreements between absolute_power and corrected_absolute_power.

    When total and periodic-only power z-scores have opposite signs and at
    least one exceeds the threshold, the deviation is in the aperiodic (1/f)
    component rather than oscillatory activity.

    Returns:
        List of dicts with channel, band, absolute_z, corrected_z, interpretation.
    """
    # Index results by (channel, band, metric)
    idx: dict[tuple[str, str, str], float] = {}
    for er in results:
        if er.base.z_score is not None:
            idx[(er.base.channel, er.base.band, er.base.metric)] = er.base.z_score

    disagreements = []
    seen: set[tuple[str, str]] = set()
    for (ch, band, metric), z in idx.items():
        if metric != "absolute_power":
            continue
        corr_z = idx.get((ch, band, "corrected_absolute_power"))
        if corr_z is None:
            continue
        key = (ch, band)
        if key in seen:
            continue

        # Check for sign disagreement with at least one exceeding threshold
        if z * corr_z < 0 and (abs(z) > z_threshold or abs(corr_z) > z_threshold):
            seen.add(key)
            disagreements.append({
                "channel": ch,
                "band": band,
                "absolute_z": round(z, 2),
                "corrected_z": round(corr_z, 2),
                "interpretation": (
                    f"Total power {'elevated' if z > 0 else 'reduced'} (z={z:.1f}) "
                    f"but periodic-only power {'elevated' if corr_z > 0 else 'reduced'} "
                    f"(z={corr_z:.1f}) at {ch} {band} — the deviation is in the "
                    f"aperiodic (1/f) component, not oscillatory activity."
                ),
            })
    return disagreements


# ---------------------------------------------------------------------------
# ComparisonReport
# ---------------------------------------------------------------------------


@dataclass
class ComparisonReport:
    """Full clinical comparison report with statistical transparency."""

    results: list[EnrichedResult]
    total_tests: int
    fdr_significant_count: int
    fdr_alpha: float
    expected_false_positives_uncorrected: float
    global_patterns: list[dict]
    deviation_clusters: list[DeviationCluster]
    metric_disagreements: list[dict]
    age: float
    condition: str
    age_bin: str
    age_interpolated: bool

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict for CW frontend consumption."""
        return {
            "metadata": {
                "age": self.age,
                "condition": self.condition,
                "age_bin": self.age_bin,
                "age_interpolated": self.age_interpolated,
                "total_tests": self.total_tests,
                "fdr_significant_count": self.fdr_significant_count,
                "fdr_alpha": self.fdr_alpha,
                "expected_false_positives_uncorrected": round(
                    self.expected_false_positives_uncorrected, 1
                ),
            },
            "results": [
                {
                    "channel": er.base.channel,
                    "band": er.base.band,
                    "metric": er.base.metric,
                    "value": er.base.value,
                    "z_score": er.base.z_score,
                    "se_z": er.se_z,
                    "p_value": er.base.p_value,
                    "fdr_significant": er.base.fdr_significant,
                    "cohen_d": er.cohen_d,
                    "cohen_d_label": er.cohen_d_label,
                    "severity_label": er.severity_label,
                    "percentile_rank": er.base.percentile_rank,
                    "robust_z": er.base.robust_z,
                    "parametric_z_unreliable": er.base.parametric_z_unreliable,
                    "z_discrepancy": er.base.z_discrepancy,
                    "z_discrepancy_flag": er.base.z_discrepancy_flag,
                    "norm_mean": er.base.norm_mean,
                    "norm_sd": er.base.norm_sd,
                    "norm_n": er.base.norm_n,
                    "ci_lower": er.base.ci_lower,
                    "ci_upper": er.base.ci_upper,
                    "pi_lower": er.pi_lower,
                    "pi_upper": er.pi_upper,
                    "within_prediction_interval": er.within_prediction_interval,
                    "log_transformed": er.log_transformed,
                    "normality_p": er.normality_p,
                    "low_confidence": er.base.low_confidence,
                }
                for er in self.results
            ],
            "patterns": {
                "global_patterns": self.global_patterns,
                "deviation_clusters": [
                    {
                        "channels": dc.channels,
                        "band": dc.band,
                        "metric": dc.metric,
                        "direction": dc.direction,
                        "mean_z": dc.mean_z,
                        "max_z": dc.max_z,
                    }
                    for dc in self.deviation_clusters
                ],
                "metric_disagreements": self.metric_disagreements,
            },
        }

    def summary_text(self) -> str:
        """Plain-text clinical summary."""
        lines = [
            f"Comparison Report — Age {self.age}, Condition: {self.condition.upper()}, "
            f"Bin: {self.age_bin}",
            f"{self.total_tests} tests performed. "
            f"{self.fdr_significant_count} significant after FDR correction "
            f"(alpha={self.fdr_alpha}).",
            f"Without correction, ~{self.expected_false_positives_uncorrected:.1f} "
            f"false positives expected at p<{self.fdr_alpha}.",
            "",
        ]

        if self.global_patterns:
            lines.append("GLOBAL PATTERNS:")
            for gp in self.global_patterns:
                lines.append(f"  - {gp['interpretation']}")
            lines.append("")

        sig = [er for er in self.results if er.base.fdr_significant]
        if sig:
            sig.sort(key=lambda er: abs(er.base.z_score or 0), reverse=True)
            lines.append(f"NOTABLE FINDINGS (FDR-corrected, {len(sig)} significant):")
            for er in sig:
                direction = "elevated" if (er.base.z_score or 0) > 0 else "reduced"
                se_str = f" ± {er.se_z:.2f}" if er.se_z else ""
                pi_str = ""
                if er.pi_lower is not None and er.pi_upper is not None:
                    inside = "WITHIN" if er.within_prediction_interval else "OUTSIDE"
                    pi_str = (
                        f"  Prediction interval: [{er.pi_lower:.1f}, {er.pi_upper:.1f}] "
                        f"— patient value {inside} PI"
                    )
                lines.append(
                    f"  {er.base.channel} {er.base.band} {er.base.metric}: "
                    f"z={er.base.z_score:+.2f}{se_str} ({direction}), "
                    f"Cohen's d={er.cohen_d_label}, "
                    f"Severity: {er.severity_label}"
                )
                if er.base.parametric_z_unreliable and er.base.robust_z is not None:
                    lines.append(
                        f"    ⚠ distribution non-normal (Shapiro p="
                        f"{er.normality_p:.3g}); σ-based z may over-flag — "
                        f"robust z={er.base.robust_z:+.2f}"
                    )
                if pi_str:
                    lines.append(pi_str)
            lines.append("")

        if self.metric_disagreements:
            lines.append("METRIC DISAGREEMENTS:")
            for md in self.metric_disagreements:
                lines.append(f"  - {md['interpretation']}")
            lines.append("")

        if self.deviation_clusters:
            lines.append("SPATIAL CLUSTERS:")
            for dc in self.deviation_clusters:
                lines.append(
                    f"  - {dc.direction.title()} {dc.band} {dc.metric} at "
                    f"{', '.join(dc.channels)} (mean |z|={dc.mean_z}, max={dc.max_z})"
                )

        return "\n".join(lines)


def build_comparison_report(
    results: list[ComparisonResult],
    norms: list[NormCell],
    age: float,
    condition: str,
    config: Optional[dict] = None,
    age_interpolated: bool = False,
) -> ComparisonReport:
    """Build an enriched clinical comparison report.

    Takes raw ComparisonResult objects and adds SE(z), Cohen's d, severity
    labels, prediction intervals, global pattern detection, spatial cluster
    detection, and metric disagreement analysis.

    Args:
        results: List of ComparisonResult from compare_to_norms().
        norms: The normative cells used for comparison.
        age: Clinical subject's age.
        condition: Recording condition.
        config: Report config dict. Defaults to REPORT_PARAMS.
        age_interpolated: Whether age interpolation was applied.

    Returns:
        ComparisonReport with full statistical transparency.
    """
    if config is None:
        from open_normative.parameters import REPORT_PARAMS
        config = REPORT_PARAMS

    severity_thresholds = config.get("severity", {}).get(
        "thresholds", [0.5, 1.0, 1.5, 2.0, 3.0]
    )
    severity_labels = config.get("severity", {}).get("labels", [
        "Within typical limits", "Mildly atypical", "Moderately atypical",
        "Notably atypical", "Markedly atypical", "Extremely atypical",
    ])
    cohen_thresholds = config.get("cohen_d", {})

    # Build norm lookup for PI and normality_p
    norm_index: dict[tuple, NormCell] = {}
    for cell in norms:
        if cell.condition == condition and _match_bin(age, cell.bin):
            key = (cell.channel, cell.band, cell.metric)
            if key not in norm_index or cell.n > norm_index[key].n:
                norm_index[key] = cell

    # Determine age bin from results
    age_bin = results[0].bin if results else "unknown"

    # Enrich each result
    enriched: list[EnrichedResult] = []
    for r in results:
        cell = norm_index.get((r.channel, r.band, r.metric))

        se_z = compute_se_z(r.z_score, r.norm_n) if r.z_score is not None else None
        d = compute_cohen_d(r.value, r.norm_mean, r.norm_sd)
        d_label = classify_cohen_d(d, cohen_thresholds) if d is not None else "negligible"
        severity = assign_severity_label(
            r.z_score, severity_thresholds, severity_labels
        ) if r.z_score is not None else severity_labels[0]

        pi_lower = getattr(cell, "pi_lower", None) if cell else None
        pi_upper = getattr(cell, "pi_upper", None) if cell else None
        within_pi = None
        if pi_lower is not None and pi_upper is not None:
            within_pi = pi_lower <= r.value <= pi_upper

        enriched.append(EnrichedResult(
            base=r,
            se_z=se_z,
            cohen_d=d,
            cohen_d_label=d_label,
            severity_label=severity,
            pi_lower=pi_lower,
            pi_upper=pi_upper,
            within_prediction_interval=within_pi,
            log_transformed=getattr(cell, "log_transformed", False) if cell else False,
            normality_p=getattr(cell, "normality_p", None) if cell else None,
        ))

    # FDR summary
    fdr_alpha = config.get("fdr_alpha", 0.05)
    total_tests = len([er for er in enriched if er.base.z_score is not None])
    fdr_sig_count = len([er for er in enriched if er.base.fdr_significant])
    expected_fp = total_tests * fdr_alpha

    # Pattern analysis
    from open_normative.parameters import PIPELINE_PARAMS
    ch_cfg = PIPELINE_PARAMS["channels"]
    # Determine channel set from data: check if any result uses a 37ch channel
    _37ch_extras = set(ch_cfg["channels_37"]) - set(ch_cfg["channels_19"])
    result_channels = {er.base.channel for er in enriched}
    if result_channels & _37ch_extras:
        channels = ch_cfg["channels_37"]
        adjacency = config.get("adjacency_37", config.get("adjacency_19", {}))
    else:
        channels = ch_cfg["channels_19"]
        adjacency = config.get("adjacency_19", {})

    gp_config = config.get("global_pattern", {})
    global_patterns = detect_global_patterns(
        enriched, channels,
        fraction_threshold=gp_config.get("channel_fraction_threshold", 0.6),
        z_threshold=gp_config.get("z_threshold", 1.5),
    )

    clusters = detect_deviation_clusters(
        enriched, adjacency,
        z_threshold=config.get("cluster", {}).get("z_threshold", 1.5),
    )

    disagreements = detect_metric_disagreements(
        enriched,
        z_threshold=config.get("disagreement", {}).get("z_threshold", 1.5),
    )

    return ComparisonReport(
        results=enriched,
        total_tests=total_tests,
        fdr_significant_count=fdr_sig_count,
        fdr_alpha=fdr_alpha,
        expected_false_positives_uncorrected=expected_fp,
        global_patterns=global_patterns,
        deviation_clusters=clusters,
        metric_disagreements=disagreements,
        age=age,
        condition=condition,
        age_bin=age_bin,
        age_interpolated=age_interpolated,
    )


def compare_and_report(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
    config: Optional[dict] = None,
    fdr_alpha: float = 0.05,
) -> ComparisonReport:
    """Convenience: compare_to_norms() + build_comparison_report() in one call.

    Args:
        metrics: Nested dict {channel: {band: {metric: value}}}.
        norms: List of NormCell objects.
        age: Clinical subject's age.
        condition: Recording condition.
        config: Report config dict. Defaults to REPORT_PARAMS.
        fdr_alpha: FDR significance level.

    Returns:
        ComparisonReport with full statistical transparency.
    """
    results = compare_to_norms(
        metrics, norms, age, condition,
        apply_fdr=True, fdr_alpha=fdr_alpha,
    )
    return build_comparison_report(
        results, norms, age, condition,
        config=config,
    )
