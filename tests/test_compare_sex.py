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


def test_sex_none_matches_only_pooled():
    """sex=None matches pooled cell, ignores F/M cells even when present."""
    norms = [
        _norm("pooled", mean=1.0),
        _norm("F", mean=10.0),    # very different mean — would be obvious if used
        _norm("M", mean=-10.0),
    ]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex=None)
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"
    # value 1.0 vs pooled mean 1.0 -> z near 0; vs F mean 10.0 -> very negative z
    assert abs(results[0].z_score) < 0.5


def test_sex_f_uses_f_cell_when_present():
    norms = [
        _norm("pooled", mean=1.0),
        _norm("F", mean=2.0, sd=0.5),
    ]
    metrics = {"Fz": {"Alpha": {"absolute_power": 2.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    assert len(results) == 1
    assert results[0].resolved_sex == "F"
    # value 2.0 vs F mean 2.0 -> z near 0
    assert abs(results[0].z_score) < 0.1


def test_sex_f_falls_back_to_pooled_when_no_f_cell():
    """If sex='F' requested but no F cell exists for this tuple, fall back to pooled."""
    norms = [_norm("pooled", mean=1.0)]   # only pooled, no F
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"


def test_sex_fallback_is_per_metric():
    """When some tuples have F and some don't, fallback happens per-tuple."""
    norms = [
        _norm("pooled", mean=1.0, channel="Fz"),
        _norm("F", mean=2.0, channel="Fz"),       # F exists for Fz
        _norm("pooled", mean=3.0, channel="Cz"),  # only pooled for Cz
    ]
    metrics = {
        "Fz": {"Alpha": {"absolute_power": 2.0}},
        "Cz": {"Alpha": {"absolute_power": 3.0}},
    }
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    by_channel = {r.channel: r.resolved_sex for r in results}
    assert by_channel == {"Fz": "F", "Cz": "pooled"}


def test_sex_invalid_raises():
    norms = [_norm("pooled")]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    with pytest.raises(ValueError):
        compare_to_norms(metrics, norms, age=25, condition="ec", sex="X")
