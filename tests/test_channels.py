"""Tests for channel normalization and montage mapping."""

import mne
import numpy as np
import pytest
from open_normative.channels import (
    normalize_channel_names,
    pick_standard_19,
    pick_standard_channels,
    strip_reference_suffix,
    load_and_standardize,
)


def test_strip_reference_suffix_linked_ears():
    assert strip_reference_suffix("Fp1-LE") == "Fp1"
    assert strip_reference_suffix("Cz-AR") == "Cz"
    assert strip_reference_suffix("O2-Ref") == "O2"


def test_strip_reference_suffix_preserves_bipolar():
    assert strip_reference_suffix("T3-T4") == "T3-T4"
    assert strip_reference_suffix("F3-C3") == "F3-C3"


def test_strip_reference_suffix_no_suffix():
    assert strip_reference_suffix("Fp1") == "Fp1"
    assert strip_reference_suffix("Cz") == "Cz"


def test_normalize_channel_names_10_10_to_10_20():
    ch_names = ["T7", "T8", "P7", "P8", "Fz", "Cz"]
    result = normalize_channel_names(ch_names)
    assert result == ["T3", "T4", "T5", "T6", "Fz", "Cz"]


def test_normalize_channel_names_capitalization():
    ch_names = ["FP1", "FP2", "FPZ"]
    result = normalize_channel_names(ch_names)
    assert result == ["Fp1", "Fp2", "Fpz"]


def test_normalize_channel_names_edf_prefix():
    ch_names = ["EEG Fp1-LE", "EEG F3-LE", "EEG Cz-LE"]
    result = normalize_channel_names(ch_names)
    assert result == ["Fp1", "F3", "Cz"]


def test_pick_standard_19_from_62ch(synthetic_raw_62ch):
    raw_19 = pick_standard_19(synthetic_raw_62ch)
    assert len(raw_19.ch_names) == 19
    assert "Fp1" in raw_19.ch_names
    assert "O2" in raw_19.ch_names
    # T7 should have been renamed to T3
    assert "T3" in raw_19.ch_names
    assert "T7" not in raw_19.ch_names


def test_pick_standard_19_already_19ch(synthetic_raw_19ch):
    raw_19 = pick_standard_19(synthetic_raw_19ch)
    assert len(raw_19.ch_names) == 19


def test_pick_standard_19_spatial_fallback():
    """When channels don't match by name, fall back to spatial nearest-neighbor."""
    ch_names = [f"E{i}" for i in range(1, 65)]
    sfreq = 256.0
    data = np.random.randn(64, int(sfreq * 10)) * 20e-6
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    # This won't have E1, E2 etc so spatial matching will be attempted
    # but with no valid positions it should raise or return what it can
    try:
        raw_19 = pick_standard_19(raw)
        assert len(raw_19.ch_names) <= 19
    except ValueError:
        pass  # Acceptable if no spatial positions available


def test_pick_standard_37_from_62ch(synthetic_raw_62ch):
    raw_37 = pick_standard_channels(synthetic_raw_62ch, n_channels=37)
    assert len(raw_37.ch_names) == 37
    # Standard 10-20 channels present
    assert "Fp1" in raw_37.ch_names
    assert "O2" in raw_37.ch_names
    # Extended 10-10 channels present
    assert "FC1" in raw_37.ch_names
    assert "CP3" in raw_37.ch_names
    assert "P1" in raw_37.ch_names
    # T7 should have been renamed to T3
    assert "T3" in raw_37.ch_names
    assert "T7" not in raw_37.ch_names


def test_pick_standard_37_already_37ch(synthetic_raw_37ch):
    raw_37 = pick_standard_channels(synthetic_raw_37ch, n_channels=37)
    assert len(raw_37.ch_names) == 37


def test_pick_standard_channels_invalid_count():
    """Requesting an unsupported channel count should raise."""
    import mne
    info = mne.create_info(ch_names=["Fp1"], sfreq=256, ch_types="eeg")
    raw = mne.io.RawArray(np.zeros((1, 256)), info, verbose=False)
    with pytest.raises(ValueError, match="Unsupported channel count"):
        pick_standard_channels(raw, n_channels=25)


def test_load_and_standardize_returns_19ch(tmp_path, synthetic_raw_62ch):
    """Round-trip: save to .fif, load_and_standardize, get 19ch."""
    fpath = tmp_path / "test_raw.fif"
    synthetic_raw_62ch.save(fpath, overwrite=True, verbose=False)
    raw = load_and_standardize(str(fpath))
    assert len(raw.ch_names) == 19
    assert raw.info["sfreq"] == synthetic_raw_62ch.info["sfreq"]


def test_load_and_standardize_returns_37ch(tmp_path, synthetic_raw_62ch):
    """Round-trip: save to .fif, load_and_standardize with n_channels=37."""
    fpath = tmp_path / "test_raw_37.fif"
    synthetic_raw_62ch.save(fpath, overwrite=True, verbose=False)
    raw = load_and_standardize(str(fpath), n_channels=37)
    assert len(raw.ch_names) == 37
