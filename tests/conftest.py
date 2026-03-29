"""Shared test fixtures for open-normative-eeg."""

import numpy as np
import mne
import pytest


@pytest.fixture
def synthetic_raw_19ch():
    """Create a synthetic 19-channel EEG Raw object for testing.

    256 Hz, 60 seconds, standard 10-20 montage with realistic-ish EEG:
    1/f noise + 10 Hz alpha at posterior channels.
    """
    ch_names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T3", "C3", "Cz", "C4", "T4",
        "T5", "P3", "Pz", "P4", "T6",
        "O1", "O2",
    ]
    sfreq = 256.0
    n_channels = len(ch_names)
    duration = 60.0
    n_samples = int(sfreq * duration)
    rng = np.random.RandomState(42)

    # 1/f noise base
    data = np.zeros((n_channels, n_samples))
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sfreq)
    freqs[0] = 1.0  # avoid division by zero
    for i in range(n_channels):
        spectrum = rng.randn(len(freqs)) + 1j * rng.randn(len(freqs))
        spectrum *= 1.0 / np.sqrt(freqs)  # 1/f
        data[i] = np.fft.irfft(spectrum, n=n_samples)

    # Add 10 Hz alpha to posterior channels (O1, O2, P3, P4, Pz)
    t = np.arange(n_samples) / sfreq
    alpha = 5e-6 * np.sin(2 * np.pi * 10 * t)
    for ch in ["O1", "O2", "P3", "P4", "Pz"]:
        data[ch_names.index(ch)] += alpha

    # Scale to realistic EEG amplitudes (microvolts → volts for MNE)
    data = data / np.std(data) * 20e-6

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", verbose=False)
    return raw


@pytest.fixture
def synthetic_raw_62ch():
    """Create a synthetic 62-channel BrainVision-like Raw (simulates LEMON).

    Uses 10-10 naming convention with channels that include the 19 standard
    10-20 channels plus extended positions.
    """
    ch_names_10_10 = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "FC5", "FC1", "FC2", "FC6",
        "T7", "C3", "Cz", "C4", "T8",
        "CP5", "CP1", "CP2", "CP6",
        "P7", "P3", "Pz", "P4", "P8",
        "PO9", "O1", "Oz", "O2", "PO10",
        "AF7", "AF3", "AF4", "AF8",
        "F5", "F1", "F2", "F6",
        "FT7", "FC3", "FC4", "FT8",
        "C5", "C1", "C2", "C6",
        "TP7", "CP3", "CPz", "CP4", "TP8",
        "P5", "P1", "P2", "P6",
        "PO7", "PO3", "POz", "PO4", "PO8",
        "Fpz", "Iz",
    ]
    sfreq = 2500.0  # LEMON native rate
    n_channels = len(ch_names_10_10)
    duration = 60.0
    n_samples = int(sfreq * duration)
    rng = np.random.RandomState(123)

    data = rng.randn(n_channels, n_samples) * 20e-6

    info = mne.create_info(ch_names=ch_names_10_10, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    montage = mne.channels.make_standard_montage("standard_1020")
    raw.set_montage(montage, on_missing="ignore", verbose=False)
    return raw


@pytest.fixture
def mock_band_power():
    """Mock band power dict matching compute_band_power output shape."""
    n_ch = 19
    rng = np.random.RandomState(99)
    bands = {
        "Delta": {"absolute": rng.rand(n_ch) * 100, "relative": None},
        "Theta": {"absolute": rng.rand(n_ch) * 50, "relative": None},
        "Alpha": {"absolute": rng.rand(n_ch) * 80, "relative": None},
        "Beta": {"absolute": rng.rand(n_ch) * 30, "relative": None},
        "Beta1": {"absolute": rng.rand(n_ch) * 10, "relative": None},
        "HighBeta": {"absolute": rng.rand(n_ch) * 5, "relative": None},
        "Gamma": {"absolute": rng.rand(n_ch) * 3, "relative": None},
    }
    total = sum(b["absolute"] for b in bands.values())
    for b in bands.values():
        b["relative"] = b["absolute"] / total
    return bands


@pytest.fixture
def mock_subject_metrics():
    """Mock per-subject metrics for normative distribution tests."""
    rng = np.random.RandomState(77)
    subjects = []
    for i in range(50):
        age = rng.randint(20, 70)
        subjects.append({
            "subject_id": f"sub-{i:03d}",
            "age": age,
            "sex": rng.choice(["M", "F"]),
            "condition": "eo",
            "metrics": {
                "Fz": {
                    "Alpha": {
                        "absolute_power": float(rng.lognormal(1.0, 0.5)),
                        "relative_power": float(rng.beta(2, 5)),
                        "corrected_absolute_power": float(rng.lognormal(0.5, 0.5)),
                        "corrected_relative_power": float(rng.beta(2, 5)),
                    },
                    "Theta": {
                        "absolute_power": float(rng.lognormal(0.5, 0.4)),
                        "relative_power": float(rng.beta(2, 8)),
                        "corrected_absolute_power": float(rng.lognormal(0.2, 0.4)),
                        "corrected_relative_power": float(rng.beta(2, 8)),
                    },
                },
            },
        })
    return subjects
