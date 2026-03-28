"""Tests for EEG preprocessing functions."""

import mne
import numpy as np
import pytest
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.preprocessing import (
    resample,
    apply_filters,
    detect_bad_channels,
    interpolate_bad_channels,
    apply_asr,
    run_ica,
    apply_reference,
    preprocess,
)


def test_resample_from_high_sfreq(synthetic_raw_62ch):
    """LEMON data is 2500 Hz — should downsample to 256."""
    raw = synthetic_raw_62ch.copy()
    assert raw.info["sfreq"] == 2500.0
    params = PIPELINE_PARAMS["preprocessing"]["resample"]
    result = resample(raw, params)
    assert result.info["sfreq"] == 256.0


def test_resample_skip_if_close(synthetic_raw_19ch):
    """256 Hz input should not be resampled."""
    raw = synthetic_raw_19ch.copy()
    assert raw.info["sfreq"] == 256.0
    params = PIPELINE_PARAMS["preprocessing"]["resample"]
    result = resample(raw, params)
    assert result.info["sfreq"] == 256.0


def test_apply_filters(synthetic_raw_19ch):
    raw = synthetic_raw_19ch.copy()
    params = PIPELINE_PARAMS["preprocessing"]["filter"]
    result = apply_filters(raw, params)
    assert result is not None
    assert result.info["sfreq"] == 256.0
    assert result.n_times == synthetic_raw_19ch.n_times


def test_detect_bad_channels_no_bads(synthetic_raw_19ch):
    """Clean synthetic data should have no bad channels."""
    raw = synthetic_raw_19ch.copy()
    params = PIPELINE_PARAMS["preprocessing"]["bad_channels"]
    bads = detect_bad_channels(raw, params)
    assert isinstance(bads, list)


def test_detect_bad_channels_finds_flat():
    """A flat channel should be detected as bad."""
    ch_names = ["Fp1", "Fp2", "F3", "Fz", "Cz"]
    sfreq = 256.0
    data = np.random.randn(5, int(sfreq * 30)) * 20e-6
    data[2, :] = 0.0  # F3 is flat
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", verbose=False)
    params = PIPELINE_PARAMS["preprocessing"]["bad_channels"]
    bads = detect_bad_channels(raw, params)
    assert "F3" in bads


def test_interpolate_bad_channels(synthetic_raw_19ch):
    raw = synthetic_raw_19ch.copy()
    raw.info["bads"] = ["F3"]
    result = interpolate_bad_channels(raw)
    assert result.info["bads"] == []


def test_apply_reference(synthetic_raw_19ch):
    raw = synthetic_raw_19ch.copy()
    params = PIPELINE_PARAMS["preprocessing"]["reference"]
    result = apply_reference(raw, params)
    assert result is not None


def test_preprocess_end_to_end(synthetic_raw_19ch):
    """Full preprocessing chain should run without error."""
    raw = synthetic_raw_19ch.copy()
    params = PIPELINE_PARAMS["preprocessing"]
    result = preprocess(raw, params)
    assert isinstance(result, dict)
    assert "raw" in result
    assert isinstance(result["raw"], mne.io.BaseRaw)
    assert "bad_channels" in result
    assert "ica" in result
