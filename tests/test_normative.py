"""Tests for normative distribution computation."""

import json
import numpy as np
import pytest
from open_normative.normative import build_normative, NormCell
from open_normative.io import write_norms_json, write_norms_csv, read_norms_json


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
