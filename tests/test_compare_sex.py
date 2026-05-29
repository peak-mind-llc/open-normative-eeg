"""compare_to_norms and compare_and_report carry sex through with fallback."""

import pytest

from open_normative.compare import compare_to_norms, compare_and_report
from open_normative.normative import NormCell


def _norm(sex: str, mean: float = 1.0, sd: float = 0.5, channel: str = "Fz",
          band: str = "Alpha", metric: str = "absolute_power") -> NormCell:
    return NormCell(
        bin="20-29", condition="ec", channel=channel,
        band=band, metric=metric,
        n=100, mean=mean, sd=sd,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={},
        sex=sex,
    )


def test_comparison_result_has_resolved_sex_field():
    norms = [_norm("pooled", mean=1.0)]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.5}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec")
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"
