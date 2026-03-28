"""Tests for pipeline orchestrator."""

import pytest
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.pipeline import process_resting, MetricsResult


def test_process_resting_returns_metrics_result(synthetic_raw_19ch):
    result = process_resting(synthetic_raw_19ch, condition="eo")
    assert isinstance(result, MetricsResult)
    assert result.condition == "eo"
    assert result.spectral is not None
    assert result.connectivity is not None
    assert result.preprocessing is not None


def test_process_resting_skip_connectivity(synthetic_raw_19ch):
    result = process_resting(
        synthetic_raw_19ch, condition="eo", skip_connectivity=True
    )
    assert result.spectral is not None
    assert result.connectivity is None


def test_metrics_result_to_flat_dict(synthetic_raw_19ch):
    result = process_resting(
        synthetic_raw_19ch, condition="eo", skip_connectivity=True
    )
    flat = result.to_flat_dict()
    assert isinstance(flat, dict)
    assert any("Fz" in key for key in flat)
    assert any("Alpha" in key for key in flat)


def test_metrics_result_to_nested_dict(synthetic_raw_19ch):
    result = process_resting(
        synthetic_raw_19ch, condition="eo", skip_connectivity=True
    )
    nested = result.to_nested_dict()
    assert isinstance(nested, dict)
    assert "Fz" in nested
    assert "Alpha" in nested["Fz"]
    assert "absolute_power" in nested["Fz"]["Alpha"]
    assert "relative_power" in nested["Fz"]["Alpha"]
