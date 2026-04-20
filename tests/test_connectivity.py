"""Tests for connectivity analysis functions."""

import mne
import numpy as np
import pytest
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.connectivity import (
    epoch_continuous,
    average_hub_signals,
    compute_connectivity,
    compute_graph_metrics,
    compute_pac,
    analyze_connectivity,
)


def test_epoch_continuous(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    epochs = epoch_continuous(
        synthetic_raw_19ch,
        epoch_length=params["epoch_length"],
        overlap=params["epoch_overlap"],
        min_epochs=params["min_epochs"],
        max_epochs=params["max_epochs"],
    )
    assert epochs is not None
    assert len(epochs) >= params["min_epochs"]
    assert len(epochs) <= params["max_epochs"]


def test_epoch_continuous_too_short():
    """Short recording should return None if fewer than min_epochs."""
    ch_names = ["Fp1", "Fp2", "Fz"]
    sfreq = 256.0
    data = np.random.randn(3, int(sfreq * 5)) * 20e-6
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    epochs = epoch_continuous(raw, epoch_length=2.0, min_epochs=30)
    assert epochs is None


def test_average_hub_signals(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    epochs = epoch_continuous(
        synthetic_raw_19ch,
        epoch_length=params["epoch_length"],
        min_epochs=1,
        max_epochs=0,
    )
    hub_epochs, hub_names, hub_mapping = average_hub_signals(
        epochs, params["hubs"]
    )
    assert len(hub_names) == 10
    assert "F_mid" in hub_names
    assert "O" in hub_names
    assert hub_epochs.get_data().shape[1] == 10


def test_compute_connectivity(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    epochs = epoch_continuous(
        synthetic_raw_19ch,
        epoch_length=params["epoch_length"],
        min_epochs=1,
        max_epochs=30,
    )
    hub_epochs, hub_names, _ = average_hub_signals(epochs, params["hubs"])
    results, vc_flags = compute_connectivity(hub_epochs, hub_names, params)
    assert "dwpli" in results
    assert "coh" in results
    for method in params["methods"]:
        assert len(results[method]) > 0
        for band, matrix in results[method].items():
            assert matrix.shape == (10, 10)
            np.testing.assert_array_equal(np.diag(matrix), 0)
    assert isinstance(vc_flags, list)


def test_compute_graph_metrics(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    epochs = epoch_continuous(
        synthetic_raw_19ch,
        epoch_length=params["epoch_length"],
        min_epochs=1,
        max_epochs=30,
    )
    hub_epochs, hub_names, _ = average_hub_signals(epochs, params["hubs"])
    results, _ = compute_connectivity(hub_epochs, hub_names, params)
    graph = compute_graph_metrics(results["dwpli"], hub_names, params)
    for band in graph:
        assert "strength" in graph[band]
        assert "betweenness" in graph[band]
        assert "clustering" in graph[band]
        assert "global_efficiency" in graph[band]


def test_analyze_connectivity(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    result = analyze_connectivity(synthetic_raw_19ch, params)
    assert "hub_connectivity" in result
    assert "graph_metrics" in result
    assert "hub_names" in result
    assert "electrode_connectivity" in result


def test_compute_pac(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["connectivity"]
    epochs = epoch_continuous(
        synthetic_raw_19ch,
        epoch_length=params["epoch_length"],
        min_epochs=1,
        max_epochs=30,
    )
    hub_epochs, hub_names, _ = average_hub_signals(epochs, params["hubs"])
    pac = compute_pac(hub_epochs, hub_names, params)
    if pac is not None:
        assert "theta_gamma_pac" in pac
        assert "within_hub" in pac["theta_gamma_pac"]
        assert "between_hub" in pac["theta_gamma_pac"]
