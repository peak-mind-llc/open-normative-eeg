"""Tests for source-level analysis utilities.

These cover ratio injection on top of source metrics dicts; full DICS /
sLORETA pipeline tests live in the integration suite.
"""

import math

import pytest

from open_normative.source import add_source_ratios


def _ratio_defs():
    return [
        {"name": "Theta/Beta", "num": ["Theta"], "den": ["Beta"]},
        {"name": "Alpha/Theta", "num": ["Alpha"], "den": ["Theta"]},
        {
            "name": "(Delta+Theta)/(Alpha+Beta)",
            "num": ["Delta", "Theta"],
            "den": ["Alpha", "Beta"],
        },
    ]


def test_source_ratios_at_ba_sloreta():
    """sLORETA BA channels emit raw and corrected ratio bands."""
    metrics = {
        "_src_ba_BA17": {
            "Delta": {"source_power": 1.0, "corrected_source_power": 0.5},
            "Theta": {"source_power": 2.0, "corrected_source_power": 1.0},
            "Alpha": {"source_power": 4.0, "corrected_source_power": 3.0},
            "Beta":  {"source_power": 5.0, "corrected_source_power": 2.0},
        }
    }
    add_source_ratios(metrics, _ratio_defs())
    ch = metrics["_src_ba_BA17"]
    # Raw source_power → bare ratio name
    assert ch["Theta/Beta"]["value"] == pytest.approx(2.0 / 5.0)
    assert ch["Alpha/Theta"]["value"] == pytest.approx(4.0 / 2.0)
    assert ch["(Delta+Theta)/(Alpha+Beta)"]["value"] == pytest.approx(
        (1.0 + 2.0) / (4.0 + 5.0)
    )
    # corrected_source_power → corrected_<name>
    assert ch["corrected_Theta/Beta"]["value"] == pytest.approx(1.0 / 2.0)
    assert ch["corrected_Alpha/Theta"]["value"] == pytest.approx(3.0 / 1.0)


def test_source_ratios_at_dk_corrected_only():
    """DK parcels only have corrected_dics_power → only corrected_<name> bands."""
    metrics = {
        "_src_dk_power_precentral-lh": {
            "Delta": {"corrected_dics_power": 1.0},
            "Theta": {"corrected_dics_power": 2.0},
            "Alpha": {"corrected_dics_power": 4.0},
            "Beta":  {"corrected_dics_power": 8.0},
        }
    }
    add_source_ratios(metrics, _ratio_defs())
    ch = metrics["_src_dk_power_precentral-lh"]
    assert ch["corrected_Theta/Beta"]["value"] == pytest.approx(2.0 / 8.0)
    assert ch["corrected_Alpha/Theta"]["value"] == pytest.approx(4.0 / 2.0)
    # Raw (source_power-based) ratios should NOT be created
    assert "Theta/Beta" not in ch
    assert "Alpha/Theta" not in ch


def test_source_ratios_zero_denominator():
    """Zero/negative/NaN denominator → NaN value, no exception."""
    metrics = {
        "_src_ba_BA17": {
            "Delta": {"corrected_dics_power": 1.0},
            "Theta": {"corrected_dics_power": 2.0},
            "Alpha": {"corrected_dics_power": 0.0},
            "Beta":  {"corrected_dics_power": 0.0},
        }
    }
    add_source_ratios(metrics, [
        {"name": "DTABR", "num": ["Delta", "Theta"], "den": ["Alpha", "Beta"]},
    ])
    val = metrics["_src_ba_BA17"]["corrected_DTABR"]["value"]
    assert math.isnan(val)


def test_source_ratios_skip_when_band_missing():
    """If a required band is absent, the ratio is silently skipped (no crash)."""
    metrics = {
        "_src_ba_BA17": {
            "Theta": {"source_power": 2.0},
            # Beta deliberately missing
        }
    }
    add_source_ratios(metrics, [
        {"name": "Theta/Beta", "num": ["Theta"], "den": ["Beta"]},
    ])
    assert "Theta/Beta" not in metrics["_src_ba_BA17"]


def test_source_ratios_no_op_on_connectivity_only_channels():
    """Connectivity channels (no power_key per band) get no ratio bands."""
    metrics = {
        "_src_conn_DLPFC_mPFC": {
            "Theta": {"source_dwpli": 0.3, "source_coherence": 0.5},
            "Beta":  {"source_dwpli": 0.1, "source_coherence": 0.2},
        }
    }
    add_source_ratios(metrics, _ratio_defs())
    ch = metrics["_src_conn_DLPFC_mPFC"]
    # Original metrics untouched
    assert ch["Theta"]["source_dwpli"] == 0.3
    # No ratio bands injected
    assert "Theta/Beta" not in ch
    assert "corrected_Theta/Beta" not in ch
