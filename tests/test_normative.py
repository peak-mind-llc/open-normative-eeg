"""Tests for normative distribution computation."""

import json
import numpy as np
import pytest
from open_normative.normative import build_normative, NormCell, _is_log_transform
from open_normative.io import (
    read_norms_json,
    write_norms_csv,
    write_norms_json,
    write_norms_npz,
)


def test_build_normative_basic(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    assert len(norms) > 0
    assert isinstance(norms[0], NormCell)


def test_norm_cell_has_required_fields(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    cell = norms[0]
    for field in ["bin", "condition", "channel", "band", "metric", "n",
                  "mean", "sd", "log_mean", "log_sd", "log_transformed",
                  "normality_p", "percentiles"]:
        assert hasattr(cell, field)


def test_build_normative_age_bins(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics, age_bins=[20, 40, 60, 80])
    bins_seen = {cell.bin for cell in norms}
    assert len(bins_seen) > 0
    for b in bins_seen:
        assert "-" in b


def test_build_normative_log_transform_absolute_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    abs_power_cells = [c for c in norms if c.metric == "absolute_power"]
    if abs_power_cells:
        cell = abs_power_cells[0]
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_no_log_transform_relative_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    rel_power_cells = [c for c in norms if c.metric == "relative_power"]
    if rel_power_cells:
        cell = rel_power_cells[0]
        assert cell.log_transformed is False


def test_is_log_transform_helper():
    """Ratio bands (containing '/') get log-transformed regardless of metric."""
    # Power metrics by name
    assert _is_log_transform("absolute_power", "Alpha") is True
    assert _is_log_transform("corrected_absolute_power", "Alpha") is True
    assert _is_log_transform("relative_power", "Alpha") is False
    # Ratios — band contains "/"
    assert _is_log_transform("value", "Theta/Beta") is True
    assert _is_log_transform("value", "corrected_Theta/Beta") is True
    assert _is_log_transform("value", "(Delta+Theta)/(Alpha+Beta)") is True
    # Asymmetry pairs (e.g. F3/F4) are stored as channel, not band, so this
    # check is a band-name check; asymmetry's band is e.g. "Alpha".
    assert _is_log_transform("asymmetry_index", "Alpha") is False


def test_build_normative_log_transforms_ratios():
    """Ratio cells (band containing '/') should be log-transformed."""
    rng = np.random.RandomState(42)
    subjects = [
        {
            "subject_id": f"sub-{i:03d}",
            "age": rng.randint(20, 70),
            "sex": "F",
            "condition": "eo",
            "metrics": {
                "Fz": {
                    "Theta/Beta": {
                        "value": float(rng.lognormal(0.0, 0.4)),
                    },
                    "(Delta+Theta)/(Alpha+Beta)": {
                        "value": float(rng.lognormal(0.0, 0.5)),
                    },
                },
            },
        }
        for i in range(40)
    ]
    norms = build_normative(subjects)
    ratio_cells = [c for c in norms if "/" in c.band]
    assert len(ratio_cells) > 0
    for cell in ratio_cells:
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_log_transform_corrected_absolute_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    corr_abs_cells = [c for c in norms if c.metric == "corrected_absolute_power"]
    if corr_abs_cells:
        cell = corr_abs_cells[0]
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_percentiles(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    for cell in norms:
        if cell.n >= 2:
            assert "50" in cell.percentiles
            assert cell.percentiles["50"] is not None


def test_write_and_read_norms_json(tmp_path, mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    fpath = tmp_path / "norms.json"
    write_norms_json(norms, fpath)
    assert fpath.exists()
    loaded = read_norms_json(fpath)
    assert len(loaded) == len(norms)
    assert loaded[0].bin == norms[0].bin


def test_write_norms_csv(tmp_path, mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    fpath = tmp_path / "norms.csv"
    write_norms_csv(norms, fpath)
    assert fpath.exists()
    with open(fpath) as f:
        header = f.readline()
    assert "bin" in header
    assert "mean" in header


def test_write_norms_npz_preserves_long_band_names(tmp_path):
    """Regression: ratio band names like '(Delta+Theta)/(Alpha+Beta)' or
    'corrected_Alpha/HighBeta' must round-trip through NPZ without
    truncation. The bands array dtype must accommodate at least 64 chars
    so future ratio additions don't silently lose data.
    """
    long_bands = [
        "(Delta+Theta)/(Alpha+Beta)",          # 26 chars — was truncated to 20
        "corrected_(Delta+Theta)/(Alpha+Beta)",  # 36 chars
        "corrected_Alpha/HighBeta",             # 24 chars
        "corrected_Theta/Beta1",                # 21 chars
        "Theta/Beta",                           # 10 chars (control)
    ]
    cells = [
        NormCell(
            bin="20-29", condition="eo",
            channel="Fz", band=b, metric="value",
            n=10, mean=1.0, sd=0.1,
            log_mean=None, log_sd=None,
            log_transformed=False,
            normality_p=None, percentiles={},
        )
        for b in long_bands
    ]
    write_norms_npz(cells, tmp_path)

    data = np.load(tmp_path / "npz" / "scalp_power.npz", allow_pickle=False)
    round_tripped = sorted(set(str(b) for b in data["bands"]))
    assert sorted(long_bands) == round_tripped, (
        f"NPZ truncated band names: expected {sorted(long_bands)!r}, "
        f"got {round_tripped!r}"
    )
