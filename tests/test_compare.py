"""Tests for normative comparison."""

import numpy as np
import pytest
from open_normative.normative import NormCell, build_normative
from open_normative.compare import compare_to_norms, ComparisonResult


@pytest.fixture
def sample_norms(mock_subject_metrics):
    return build_normative(mock_subject_metrics)


@pytest.fixture
def clinical_metrics():
    return {
        "Fz": {
            "Alpha": {
                "absolute_power": 50.0,
                "relative_power": 0.35,
            },
            "Theta": {
                "absolute_power": 20.0,
                "relative_power": 0.15,
            },
        },
    }


def test_compare_to_norms_returns_results(sample_norms, clinical_metrics):
    results = compare_to_norms(
        metrics=clinical_metrics, norms=sample_norms, age=35, condition="eo",
    )
    assert len(results) > 0
    assert isinstance(results[0], ComparisonResult)


def test_comparison_result_fields(sample_norms, clinical_metrics):
    results = compare_to_norms(
        metrics=clinical_metrics, norms=sample_norms, age=35, condition="eo",
    )
    r = results[0]
    for field in ["channel", "band", "metric", "value", "z_score",
                  "percentile_rank", "low_confidence"]:
        assert hasattr(r, field)


def test_compare_z_score_direction(sample_norms, clinical_metrics):
    """A very high value should have a positive z-score."""
    clinical_metrics["Fz"]["Alpha"]["absolute_power"] = 1000.0
    results = compare_to_norms(
        metrics=clinical_metrics, norms=sample_norms, age=35, condition="eo",
    )
    alpha_abs = [r for r in results if r.band == "Alpha" and r.metric == "absolute_power"]
    if alpha_abs:
        assert alpha_abs[0].z_score > 0


def test_compare_low_confidence_flag():
    cell = NormCell(
        bin="30-39", condition="eo", channel="Fz", band="Alpha",
        metric="absolute_power", n=5, mean=10.0, sd=2.0,
        log_mean=2.3, log_sd=0.2, log_transformed=True,
        normality_p=0.5,
        percentiles={"1": 5, "5": 6, "10": 7, "25": 8, "50": 10, "75": 12, "90": 13, "95": 14, "99": 15},
    )
    metrics = {"Fz": {"Alpha": {"absolute_power": 12.0}}}
    results = compare_to_norms(metrics=metrics, norms=[cell], age=35, condition="eo")
    assert len(results) == 1
    assert results[0].low_confidence is True


def test_compare_no_matching_bin():
    cell = NormCell(
        bin="20-29", condition="eo", channel="Fz", band="Alpha",
        metric="relative_power", n=30, mean=0.2, sd=0.05,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=0.5, percentiles={"50": 0.2},
    )
    metrics = {"Fz": {"Alpha": {"relative_power": 0.25}}}
    results = compare_to_norms(metrics=metrics, norms=[cell], age=85, condition="eo")
    assert len(results) == 0


def test_compare_corrected_absolute_power():
    """Corrected absolute power should use log-space z-scores."""
    cell = NormCell(
        bin="30-39", condition="eo", channel="Fz", band="Alpha",
        metric="corrected_absolute_power", n=30, mean=5.0, sd=2.0,
        log_mean=1.5, log_sd=0.3, log_transformed=True,
        normality_p=0.5,
        percentiles={"1": 1, "5": 2, "10": 2.5, "25": 3.5, "50": 5, "75": 6.5, "90": 8, "95": 9, "99": 11},
    )
    metrics = {"Fz": {"Alpha": {"corrected_absolute_power": 7.0}}}
    results = compare_to_norms(metrics=metrics, norms=[cell], age=35, condition="eo")
    assert len(results) == 1
    r = results[0]
    assert r.metric == "corrected_absolute_power"
    assert r.z_score is not None
    # z-score should be positive (7.0 > mean of 5.0)
    assert r.z_score > 0
