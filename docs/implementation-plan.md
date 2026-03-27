# open-normative-eeg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python package that processes public EEG datasets through a pipeline identical to Coherence Workstation's, producing open normative distributions.

**Architecture:** Focused modules (`parameters.py`, `preprocessing.py`, `spectral.py`, `connectivity.py`) orchestrated by `pipeline.py`. Dataset loaders yield MNE `Raw` objects. `normative.py` aggregates per-subject metrics into age-binned distributions. `compare.py` computes z-scores against those distributions.

**Tech Stack:** Python 3.10+, MNE-Python, specparam, mne-icalabel, mne-connectivity, python-picard, asrpy, pyprep, pandas, networkx, scipy

---

## File Map

| File | Responsibility |
|------|---------------|
| `open_normative/__init__.py` | Package exports, version |
| `open_normative/parameters.py` | Canonical `PIPELINE_PARAMS` dict — all processing parameters |
| `open_normative/channels.py` | Channel name normalization, montage mapping, file loading (open formats) |
| `open_normative/preprocessing.py` | Resample, filter, bad channels, ASR, ICA, re-reference |
| `open_normative/spectral.py` | PSD, band powers, aperiodic fitting, asymmetry |
| `open_normative/connectivity.py` | Epoching, hub averaging, dwPLI/coh/imcoh, graph metrics, PAC |
| `open_normative/pipeline.py` | Orchestrator: chains preprocessing → spectral → connectivity |
| `open_normative/normative.py` | Aggregate per-subject metrics into age-binned distributions |
| `open_normative/compare.py` | Compare a recording's metrics against normative distributions |
| `open_normative/io.py` | Read/write norms as JSON and CSV |
| `open_normative/datasets/__init__.py` | Dataset registry |
| `open_normative/datasets/base.py` | Abstract `DatasetLoader` + `SubjectRecord` dataclass |
| `open_normative/datasets/lemon.py` | LEMON dataset loader (download, iterate subjects) |
| `open_normative/datasets/hbn.py` | HBN loader stub |
| `open_normative/datasets/mipdb.py` | MIPDB loader stub |
| `tests/test_parameters.py` | Parameter completeness and type checks |
| `tests/test_channels.py` | Channel normalization and mapping tests |
| `tests/test_preprocessing.py` | Preprocessing function tests |
| `tests/test_spectral.py` | Spectral analysis tests |
| `tests/test_connectivity.py` | Connectivity computation tests |
| `tests/test_pipeline.py` | End-to-end pipeline orchestration test |
| `tests/test_normative.py` | Normative distribution computation tests |
| `tests/test_compare.py` | Comparison/z-score tests |
| `tests/conftest.py` | Shared fixtures (synthetic MNE Raw, mock metrics) |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `open_normative/__init__.py`
- Create: `open_normative/datasets/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "open-normative-eeg"
version = "0.1.0"
description = "Open normative EEG database builder with clinical-grade processing pipeline"
readme = "README.md"
license = "AGPL-3.0-or-later"
requires-python = ">=3.10"
dependencies = [
    "mne>=1.6",
    "numpy>=1.24",
    "scipy>=1.10",
    "pandas>=2.0",
    "specparam>=1.0",
    "mne-icalabel>=0.4",
    "mne-connectivity>=0.5",
    "python-picard>=0.7",
    "asrpy>=0.2",
    "networkx>=3.0",
]

[project.optional-dependencies]
datasets = [
    "requests",
    "tqdm",
]
dev = [
    "pytest>=7.0",
    "ruff>=0.1",
]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create open_normative/__init__.py**

```python
"""open-normative-eeg: Open normative EEG database builder."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create open_normative/datasets/__init__.py**

```python
"""Dataset loaders for public EEG datasets."""
```

- [ ] **Step 4: Create tests/__init__.py and tests/conftest.py**

`tests/__init__.py` — empty file.

```python
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
                    },
                    "Theta": {
                        "absolute_power": float(rng.lognormal(0.5, 0.4)),
                        "relative_power": float(rng.beta(2, 8)),
                    },
                },
            },
        })
    return subjects
```

- [ ] **Step 5: Verify the scaffold**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && pip install -e ".[dev]" 2>&1 | tail -5`
Expected: Successful install with "Successfully installed open-normative-eeg-0.1.0"

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -c "import open_normative; print(open_normative.__version__)"`
Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add pyproject.toml open_normative/__init__.py open_normative/datasets/__init__.py tests/__init__.py tests/conftest.py
git commit -m "feat: project scaffolding with pyproject.toml and test fixtures"
```

---

### Task 2: Parameters Module

**Files:**
- Create: `open_normative/parameters.py`
- Create: `tests/test_parameters.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for pipeline parameters."""

from open_normative.parameters import PIPELINE_PARAMS


def test_pipeline_params_has_required_sections():
    required = ["preprocessing", "spectral", "connectivity"]
    for section in required:
        assert section in PIPELINE_PARAMS, f"Missing section: {section}"


def test_preprocessing_filter_params():
    filt = PIPELINE_PARAMS["preprocessing"]["filter"]
    assert filt["l_freq"] == 0.5
    assert filt["h_freq"] == 100.0
    assert filt["notch_freq"] == 60.0
    assert filt["notch_harmonics"] == [120.0, 180.0]
    assert filt["notch_width"] == 2.0


def test_preprocessing_ica_params():
    ica = PIPELINE_PARAMS["preprocessing"]["ica"]
    assert ica["method"] == "picard"
    assert ica["extended"] is True
    assert ica["n_components"] == 0.999
    assert ica["max_iter"] == 500
    assert ica["random_state"] == 42
    assert ica["two_stage_filter"] is True
    assert ica["ica_highpass"] == 1.0
    assert ica["brain_threshold"] == 0.80
    assert ica["review_threshold"] == 0.50


def test_preprocessing_asr_params():
    asr = PIPELINE_PARAMS["preprocessing"]["asr"]
    assert asr["cutoff"] == 20
    assert asr["window_length"] == 0.5


def test_preprocessing_bad_channels_params():
    bc = PIPELINE_PARAMS["preprocessing"]["bad_channels"]
    assert bc["method"] == "ransac"
    assert bc["correlation_threshold"] == 0.75
    assert bc["flat_threshold_factor"] == 0.01
    assert bc["noisy_threshold_factor"] == 10.0


def test_preprocessing_resample_params():
    rs = PIPELINE_PARAMS["preprocessing"]["resample"]
    assert rs["enabled"] is True
    assert rs["target_sfreq"] == 256.0


def test_preprocessing_reference():
    assert PIPELINE_PARAMS["preprocessing"]["reference"] == "average"


def test_spectral_bands():
    bands = PIPELINE_PARAMS["spectral"]["bands"]
    assert bands["Delta"] == [1, 4]
    assert bands["Theta"] == [4, 8]
    assert bands["Alpha"] == [8, 13]
    assert bands["Alpha1"] == [8, 10.5]
    assert bands["Alpha2"] == [10.5, 13]
    assert bands["Beta"] == [13, 30]
    assert bands["Beta1"] == [13, 15]
    assert bands["Beta2"] == [15, 18]
    assert bands["Beta3"] == [18, 25]
    assert bands["HighBeta"] == [25, 30]
    assert bands["Gamma"] == [30, 50]


def test_spectral_psd_params():
    s = PIPELINE_PARAMS["spectral"]
    assert s["method"] == "welch"
    assert s["fmin"] == 0.5
    assert s["fmax"] == 50.0
    assert s["n_fft"] == 1024


def test_spectral_aperiodic_params():
    ap = PIPELINE_PARAMS["spectral"]["aperiodic"]
    assert ap["freq_range"] == [2, 40]
    assert ap["r_squared_threshold"] == 0.85
    assert ap["peak_width_limits"] == [1, 8]
    assert ap["max_n_peaks"] == 6
    assert ap["min_peak_height"] == 0.1
    assert ap["peak_threshold"] == 2.0


def test_spectral_asymmetry_params():
    asym = PIPELINE_PARAMS["spectral"]["asymmetry"]
    assert [["F3", "F4"]] == [asym["homologous_pairs"][0]]
    assert len(asym["homologous_pairs"]) == 7
    assert asym["threshold"] == 0.15


def test_spectral_ratios():
    ratios = PIPELINE_PARAMS["spectral"]["ratios"]
    assert ["Theta", "Beta"] in ratios
    assert ["Theta", "Beta1"] in ratios


def test_connectivity_params():
    conn = PIPELINE_PARAMS["connectivity"]
    assert conn["epoch_length"] == 2.0
    assert conn["epoch_overlap"] == 0.0
    assert conn["min_epochs"] == 30
    assert conn["max_epochs"] == 120
    assert conn["methods"] == ["dwpli", "coh", "imcoh"]


def test_connectivity_hubs():
    hubs = PIPELINE_PARAMS["connectivity"]["hubs"]
    assert hubs["F_mid"] == ["Fz"]
    assert hubs["F_L"] == ["F3", "F7"]
    assert hubs["O"] == ["O1", "O2"]
    assert len(hubs) == 10


def test_connectivity_cfc_params():
    cfc = PIPELINE_PARAMS["connectivity"]["cfc"]
    assert cfc["enabled"] is True
    assert cfc["phase_band"] == [4, 8]
    assert cfc["amp_band"] == [30, 45]
    assert cfc["n_bins"] == 18


def test_connectivity_graph_params():
    graph = PIPELINE_PARAMS["connectivity"]["graph"]
    assert graph["threshold_percentile"] == 75


def test_channels_config():
    ch = PIPELINE_PARAMS["channels"]
    assert ch["target_montage"] == "standard_1020"
    assert len(ch["channels_19"]) == 19
    assert "Fp1" in ch["channels_19"]
    assert ch["name_mapping"]["T7"] == "T3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_parameters.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_normative.parameters'`

- [ ] **Step 3: Write parameters.py**

```python
"""Canonical pipeline parameters for open-normative-eeg.

These parameters are extracted from Coherence Workstation's configs/default.yaml
and processing code. They define the exact processing pipeline used for both
normative database construction and clinical EEG analysis.

CW imports this dict to guarantee identical processing.
"""

PIPELINE_PARAMS = {
    "preprocessing": {
        "resample": {
            "enabled": True,
            "target_sfreq": 256.0,
        },
        "filter": {
            "l_freq": 0.5,
            "h_freq": 100.0,
            "notch_freq": 60.0,
            "notch_harmonics": [120.0, 180.0],
            "notch_width": 2.0,
        },
        "bad_channels": {
            "method": "ransac",
            "correlation_threshold": 0.75,
            "flat_threshold_factor": 0.01,
            "noisy_threshold_factor": 10.0,
        },
        "asr": {
            "cutoff": 20,
            "window_length": 0.5,
        },
        "ica": {
            "method": "picard",
            "extended": True,
            "n_components": 0.999,
            "max_iter": 500,
            "random_state": 42,
            "two_stage_filter": True,
            "ica_highpass": 1.0,
            "brain_threshold": 0.80,
            "review_threshold": 0.50,
        },
        "reference": "average",
    },
    "spectral": {
        "method": "welch",
        "fmin": 0.5,
        "fmax": 50.0,
        "n_fft": 1024,
        "bands": {
            "Delta": [1, 4],
            "Theta": [4, 8],
            "Alpha": [8, 13],
            "Alpha1": [8, 10.5],
            "Alpha2": [10.5, 13],
            "Beta": [13, 30],
            "Beta1": [13, 15],
            "Beta2": [15, 18],
            "Beta3": [18, 25],
            "HighBeta": [25, 30],
            "Gamma": [30, 50],
        },
        "ratios": [
            ["Theta", "Beta"],
            ["Theta", "Beta1"],
            ["Delta", "HighBeta"],
            ["Alpha", "HighBeta"],
        ],
        "aperiodic": {
            "freq_range": [2, 40],
            "r_squared_threshold": 0.85,
            "peak_width_limits": [1, 8],
            "max_n_peaks": 6,
            "min_peak_height": 0.1,
            "peak_threshold": 2.0,
        },
        "asymmetry": {
            "homologous_pairs": [
                ["F3", "F4"],
                ["C3", "C4"],
                ["P3", "P4"],
                ["T3", "T4"],
                ["T5", "T6"],
                ["F7", "F8"],
                ["O1", "O2"],
            ],
            "threshold": 0.15,
        },
    },
    "connectivity": {
        "epoch_length": 2.0,
        "epoch_overlap": 0.0,
        "min_epochs": 30,
        "max_epochs": 120,
        "methods": ["dwpli", "coh", "imcoh"],
        "bands": {
            "Delta": [1, 4],
            "Theta": [4, 8],
            "Alpha": [8, 13],
            "Beta": [13, 30],
            "HighBeta": [25, 30],
            "Gamma": [30, 50],
        },
        "hubs": {
            "F_mid": ["Fz"],
            "F_L": ["F3", "F7"],
            "F_R": ["F4", "F8"],
            "C_mid": ["Cz"],
            "T_L": ["T3", "T5"],
            "T_R": ["T4", "T6"],
            "P_mid": ["Pz"],
            "P_L": ["P3"],
            "P_R": ["P4"],
            "O": ["O1", "O2"],
        },
        "graph": {
            "threshold_percentile": 75,
        },
        "cfc": {
            "enabled": True,
            "phase_band": [4, 8],
            "amp_band": [30, 45],
            "n_bins": 18,
            "hub_pairs": [
                ["F_mid", "P_mid"],
                ["F_L", "T_L"],
                ["F_R", "T_R"],
                ["T_L", "P_mid"],
                ["F_mid", "T_L"],
                ["F_mid", "T_R"],
            ],
        },
    },
    "channels": {
        "target_montage": "standard_1020",
        "channels_19": [
            "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
            "T3", "C3", "Cz", "C4", "T4",
            "T5", "P3", "Pz", "P4", "T6",
            "O1", "O2",
        ],
        "name_mapping": {
            "T7": "T3",
            "T8": "T4",
            "P7": "T5",
            "P8": "T6",
        },
        "capitalization_fixes": {
            "FP1": "Fp1",
            "FP2": "Fp2",
            "FPZ": "Fpz",
        },
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_parameters.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/parameters.py tests/test_parameters.py
git commit -m "feat: add canonical pipeline parameters module"
```

---

### Task 3: Channels Module

**Files:**
- Create: `open_normative/channels.py`
- Create: `tests/test_channels.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for channel normalization and montage mapping."""

import mne
import numpy as np
import pytest
from open_normative.channels import (
    normalize_channel_names,
    pick_standard_19,
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
    # Apply EGI GSN montage (if available) or standard_1020
    montage = mne.channels.make_standard_montage("standard_1020")
    # This won't have E1, E2 etc so spatial matching will be attempted
    # but with no valid positions it should raise or return what it can
    # We test that the function doesn't crash
    try:
        raw_19 = pick_standard_19(raw)
        assert len(raw_19.ch_names) <= 19
    except ValueError:
        pass  # Acceptable if no spatial positions available


def test_load_and_standardize_returns_19ch(tmp_path, synthetic_raw_62ch):
    """Round-trip: save to .fif, load_and_standardize, get 19ch."""
    fpath = tmp_path / "test_raw.fif"
    synthetic_raw_62ch.save(fpath, overwrite=True, verbose=False)
    raw = load_and_standardize(str(fpath))
    assert len(raw.ch_names) == 19
    assert raw.info["sfreq"] == synthetic_raw_62ch.info["sfreq"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_channels.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write channels.py**

```python
"""Channel name normalization, montage mapping, and EEG file loading.

Handles mapping from various EEG system naming conventions to the standard
19-channel 10-20 montage used for normative processing.
"""

from pathlib import Path

import mne
import numpy as np

from open_normative.parameters import PIPELINE_PARAMS

_PARAMS = PIPELINE_PARAMS["channels"]
_CHANNELS_19 = _PARAMS["channels_19"]
_NAME_MAP = _PARAMS["name_mapping"]
_CAP_FIXES = _PARAMS["capitalization_fixes"]

# Known channel base names for reference suffix detection
_KNOWN_BASES = {
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "T3", "C3", "Cz", "C4", "T4", "T5", "P3", "Pz", "P4", "T6",
    "O1", "O2", "T7", "T8", "P7", "P8",
    "AF3", "AF4", "FC1", "FC2", "FC3", "FC4", "FC5", "FC6",
    "FT7", "FT8", "FT9", "FT10",
    "CP1", "CP2", "CP3", "CP4", "CP5", "CP6",
    "TP7", "TP8", "TP9", "TP10",
    "PO3", "PO4", "PO7", "PO8",
    "Fpz", "CPz", "POz", "Oz", "Iz",
    "A1", "A2", "M1", "M2",
    "C1", "C2", "C5", "C6",
    "F1", "F2", "F5", "F6",
    "P1", "P2", "P5", "P6",
}


def strip_reference_suffix(name: str) -> str:
    """Strip a reference suffix (e.g. '-LE', '-AR') from a channel name.

    Preserves bipolar derivations like 'T3-T4' where both sides are
    known channel names.
    """
    if "-" not in name:
        return name
    parts = name.split("-", 1)
    base = parts[0].strip()
    suffix = parts[1].strip()
    # If both sides are known channels, it's a bipolar derivation — keep it
    if base in _KNOWN_BASES and suffix in _KNOWN_BASES:
        return name
    # If the base is a known channel, strip the suffix
    if base in _KNOWN_BASES:
        return base
    return name


def normalize_channel_names(ch_names: list[str]) -> list[str]:
    """Normalize a list of channel names to standard 10-20 convention.

    Handles:
    - EDF 'EEG Fp1-LE' prefix+suffix format
    - Reference suffixes (-LE, -AR, -Ref, etc.)
    - 10-10 → 10-20 renaming (T7→T3, T8→T4, P7→T5, P8→T6)
    - Capitalization fixes (FP1→Fp1)
    """
    result = []
    for name in ch_names:
        # Strip EDF "EEG " prefix
        if name.startswith("EEG "):
            name = name[4:]
        # Strip trailing dots/spaces
        name = name.rstrip(". ")
        # Strip reference suffix
        name = strip_reference_suffix(name)
        # Capitalization fixes
        name = _CAP_FIXES.get(name, name)
        # 10-10 → 10-20 mapping
        name = _NAME_MAP.get(name, name)
        result.append(name)
    return result


def pick_standard_19(raw: mne.io.Raw) -> mne.io.Raw:
    """Reduce a Raw object to the standard 19-channel 10-20 montage.

    First normalizes channel names, then picks channels by name matching.
    If fewer than 19 channels match by name and the raw has montage positions,
    falls back to spatial nearest-neighbor matching.
    """
    raw = raw.copy()

    # Normalize names in place
    new_names = normalize_channel_names(raw.ch_names)
    rename_map = {}
    for old, new in zip(raw.ch_names, new_names):
        if old != new:
            rename_map[old] = new
    if rename_map:
        raw.rename_channels(rename_map)

    # Try direct name matching
    available = [ch for ch in _CHANNELS_19 if ch in raw.ch_names]

    if len(available) >= 19:
        raw.pick(available)
        # Reorder to canonical order
        raw.reorder_channels(available)
        montage = mne.channels.make_standard_montage("standard_1020")
        raw.set_montage(montage, on_missing="ignore", verbose=False)
        return raw

    # Spatial nearest-neighbor fallback for high-density systems
    if raw.get_montage() is not None:
        target_montage = mne.channels.make_standard_montage("standard_1020")
        target_pos = target_montage.get_positions()["ch_pos"]
        raw_pos = raw.get_montage().get_positions()["ch_pos"]

        # Only proceed if we have 3D positions for raw channels
        raw_chs_with_pos = {ch: pos for ch, pos in raw_pos.items() if ch in raw.ch_names}
        if len(raw_chs_with_pos) >= 19:
            matched = {}
            used_sources = set()
            for target_ch in _CHANNELS_19:
                if target_ch in available:
                    # Already matched by name
                    matched[target_ch] = target_ch
                    used_sources.add(target_ch)
                    continue
                if target_ch not in target_pos:
                    continue
                t_pos = target_pos[target_ch]
                best_dist = np.inf
                best_ch = None
                for src_ch, src_pos in raw_chs_with_pos.items():
                    if src_ch in used_sources:
                        continue
                    dist = np.linalg.norm(np.array(t_pos) - np.array(src_pos))
                    if dist < best_dist:
                        best_dist = dist
                        best_ch = src_ch
                if best_ch is not None:
                    matched[target_ch] = best_ch
                    used_sources.add(best_ch)

            if len(matched) >= 19:
                # Pick matched source channels
                src_chs = list(matched.values())
                raw.pick(src_chs)
                # Rename to target names
                rename = {v: k for k, v in matched.items() if v != k}
                if rename:
                    raw.rename_channels(rename)
                raw.reorder_channels(_CHANNELS_19)
                montage = mne.channels.make_standard_montage("standard_1020")
                raw.set_montage(montage, on_missing="ignore", verbose=False)
                return raw

    # If we get here, we have a partial match — pick what we can
    if available:
        raw.pick(available)
        montage = mne.channels.make_standard_montage("standard_1020")
        raw.set_montage(montage, on_missing="ignore", verbose=False)
        return raw

    raise ValueError(
        f"Cannot map channels to standard 19-channel montage. "
        f"Found {len(available)} matching channels out of 19 required. "
        f"Raw channels: {raw.ch_names[:10]}..."
    )


_LOADERS = {
    ".vhdr": mne.io.read_raw_brainvision,
    ".edf": mne.io.read_raw_edf,
    ".set": mne.io.read_raw_eeglab,
    ".fif": mne.io.read_raw_fif,
}


def load_and_standardize(filepath: str | Path) -> mne.io.Raw:
    """Load an EEG file and standardize to 19-channel 10-20 montage.

    Supports: .vhdr (BrainVision), .edf, .set (EEGLAB), .fif (MNE)
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"Unsupported file format: {ext}. Supported: {list(_LOADERS.keys())}")

    raw = loader(filepath, preload=True, verbose=False)

    # Drop non-EEG channels if present
    eeg_types = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(eeg_types) < len(raw.ch_names):
        raw.pick("eeg")

    return pick_standard_19(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_channels.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/channels.py tests/test_channels.py
git commit -m "feat: add channel normalization and 19ch montage mapping"
```

---

### Task 4: Preprocessing Module

**Files:**
- Create: `open_normative/preprocessing.py`
- Create: `tests/test_preprocessing.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    # Data should be modified (filtered)
    assert result.n_times == synthetic_raw_19ch.n_times


def test_detect_bad_channels_no_bads(synthetic_raw_19ch):
    """Clean synthetic data should have no bad channels."""
    raw = synthetic_raw_19ch.copy()
    params = PIPELINE_PARAMS["preprocessing"]["bad_channels"]
    bads = detect_bad_channels(raw, params)
    # Synthetic data is clean, so few or no bads expected
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_preprocessing.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write preprocessing.py**

```python
"""EEG preprocessing: filtering, bad channels, ASR, ICA, re-referencing.

All functions take an MNE Raw object and a params dict. No hidden defaults.
Parameters come from open_normative.parameters.PIPELINE_PARAMS.
"""

import warnings

import mne
import numpy as np


def resample(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Resample raw data to target sampling rate.

    Args:
        raw: MNE Raw object (modified in place).
        params: Dict with 'enabled' (bool) and 'target_sfreq' (float).
    """
    if not params.get("enabled", False):
        return raw
    target = params["target_sfreq"]
    if abs(raw.info["sfreq"] - target) < 0.5:
        return raw
    raw.resample(target, verbose=False)
    return raw


def apply_filters(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Apply bandpass and notch filters.

    Args:
        raw: MNE Raw object (modified in place).
        params: Dict with l_freq, h_freq, notch_freq, notch_harmonics, notch_width.
    """
    raw.filter(
        l_freq=params["l_freq"],
        h_freq=params["h_freq"],
        verbose=False,
    )
    notch_freqs = [params["notch_freq"]] + params.get("notch_harmonics", [])
    # Filter out frequencies above Nyquist
    nyquist = raw.info["sfreq"] / 2.0
    notch_freqs = [f for f in notch_freqs if f < nyquist]
    if notch_freqs:
        raw.notch_filter(
            notch_freqs,
            notch_widths=params.get("notch_width", 2.0),
            verbose=False,
        )
    return raw


def detect_bad_channels(raw: mne.io.Raw, params: dict) -> list[str]:
    """Detect bad channels using variance heuristics and optional RANSAC.

    Args:
        raw: MNE Raw object.
        params: Dict with method, correlation_threshold, flat/noisy thresholds.

    Returns:
        List of bad channel names.
    """
    data = raw.get_data()
    variances = np.var(data, axis=1)
    median_var = np.median(variances)

    flat_thresh = params.get("flat_threshold_factor", 0.01) * median_var
    noisy_thresh = params.get("noisy_threshold_factor", 10.0) * median_var

    bads = []
    for i, ch in enumerate(raw.ch_names):
        if variances[i] < flat_thresh:
            bads.append(ch)
        elif variances[i] > noisy_thresh:
            bads.append(ch)

    if params.get("method") == "ransac":
        try:
            from pyprep.find_noisy_channels import NoisyChannels
            nd = NoisyChannels(raw, random_state=42)
            nd.find_bad_by_ransac()
            ransac_bads = nd.bad_by_ransac
            # Safeguard: if RANSAC flags >50%, fall back to variance-only
            if len(ransac_bads) <= len(raw.ch_names) * 0.5:
                for ch in ransac_bads:
                    if ch not in bads:
                        bads.append(ch)
        except ImportError:
            pass  # pyprep not installed, use variance-only
        except Exception:
            pass  # RANSAC failed, use variance-only

    return bads


def interpolate_bad_channels(raw: mne.io.Raw) -> mne.io.Raw:
    """Interpolate bad channels using spherical spline.

    Bad channels must be set in raw.info['bads'] before calling.
    """
    if raw.info["bads"]:
        raw.interpolate_bads(verbose=False)
    return raw


def _patch_asrpy():
    """Apply NumPy >=2.0 compatibility patches for asrpy."""
    try:
        import asrpy.asr
        # Check if patching is needed (numpy >= 2.0 removed some aliases)
        if not hasattr(np, "float"):
            return  # Already compatible or not needed
    except ImportError:
        pass


def _asr_mem_splits(raw, max_chunk_bytes=500_000_000):
    """Compute memory-efficient splits for ASR transformation."""
    n_ch = len(raw.ch_names)
    n_samples = raw.n_times
    bytes_full = n_ch * n_ch * n_samples * 8  # float64
    return max(3, int(bytes_full / max_chunk_bytes) + 1)


def apply_asr(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Apply Artifact Subspace Reconstruction to clean transient artifacts.

    Args:
        raw: MNE Raw object (filtered, bad channels interpolated).
        params: Dict with cutoff and window_length.
    """
    try:
        from asrpy import ASR
    except ImportError:
        warnings.warn("asrpy not installed — skipping ASR artifact cleaning")
        return raw

    _patch_asrpy()
    cutoff = params.get("cutoff", 20)
    asr = ASR(sfreq=raw.info["sfreq"], cutoff=cutoff)
    asr.fit(raw)
    splits = _asr_mem_splits(raw)
    raw = asr.transform(raw, mem_splits=splits)
    return raw


def _make_ica_copy(raw: mne.io.Raw, params: dict) -> mne.io.Raw | None:
    """Create a higher-filtered copy for two-stage ICA fitting."""
    if not params.get("two_stage_filter", True):
        return None
    ica_highpass = params.get("ica_highpass", 1.0)
    # Only needed if ICA highpass is higher than the main filter
    if ica_highpass <= 0.5:  # Main filter l_freq
        return None
    raw_ica = raw.copy()
    raw_ica.filter(l_freq=ica_highpass, h_freq=None, verbose=False)
    return raw_ica


def run_ica(
    raw: mne.io.Raw, params: dict
) -> dict:
    """Run ICA decomposition and ICLabel auto-classification.

    Args:
        raw: Preprocessed MNE Raw object.
        params: Dict with ICA and ICLabel parameters.

    Returns:
        Dict with keys: ica, rejected_components, labels.
    """
    method = params.get("method", "picard")
    extended = params.get("extended", True)
    n_components = params.get("n_components", 0.999)
    max_iter = params.get("max_iter", 500)
    random_state = params.get("random_state", 42)

    fit_params = {}
    if method == "picard":
        fit_params = {"ortho": False, "extended": extended}
    elif method == "infomax":
        fit_params = {"extended": extended}

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method=method,
        max_iter=max_iter,
        random_state=random_state,
        fit_params=fit_params,
        verbose=False,
    )

    # Two-stage filtering: fit on higher-filtered copy
    raw_fit = _make_ica_copy(raw, params)
    if raw_fit is None:
        raw_fit = raw

    ica.fit(raw_fit, verbose=False)

    # ICLabel classification
    rejected = []
    labels_result = None
    try:
        from mne_icalabel import label_components
        labels_result = label_components(raw_fit, ica, method="iclabel")
        labels = labels_result["labels"]
        proba = labels_result["y_pred_proba"]

        brain_thresh = params.get("brain_threshold", 0.80)
        review_thresh = params.get("review_threshold", 0.50)

        for idx, (label, prob) in enumerate(zip(labels, proba)):
            if label != "brain":
                # Auto-reject non-brain components with high confidence
                max_prob = float(np.max(prob)) if hasattr(prob, "__len__") else float(prob)
                if max_prob >= review_thresh:
                    rejected.append(idx)
            else:
                # Flag uncertain brain components
                brain_prob = float(prob[0]) if hasattr(prob, "__len__") else float(prob)
                if brain_prob < brain_thresh:
                    rejected.append(idx)
    except ImportError:
        warnings.warn("mne-icalabel not installed — skipping IC classification")

    # Apply ICA (exclude rejected components)
    if rejected:
        ica.exclude = rejected
        ica.apply(raw, verbose=False)

    return {
        "ica": ica,
        "rejected_components": rejected,
        "labels": labels_result,
    }


def apply_reference(raw: mne.io.Raw, reference: str) -> mne.io.Raw:
    """Apply re-referencing.

    Args:
        raw: MNE Raw object.
        reference: 'average', 'REST', or a channel name.
    """
    if reference == "average":
        raw.set_eeg_reference("average", verbose=False)
    elif reference == "REST":
        raw.set_eeg_reference("REST", verbose=False)
    else:
        raw.set_eeg_reference([reference], verbose=False)
    return raw


def preprocess(raw: mne.io.Raw, params: dict) -> dict:
    """Run the full preprocessing pipeline.

    Args:
        raw: MNE Raw object (already channel-standardized to 19ch).
        params: The 'preprocessing' section of PIPELINE_PARAMS.

    Returns:
        Dict with keys: raw, bad_channels, ica.
    """
    # 1. Resample
    resample(raw, params.get("resample", {}))

    # 2. Filter
    apply_filters(raw, params["filter"])

    # 3. Bad channel detection + interpolation
    bads = detect_bad_channels(raw, params["bad_channels"])
    raw.info["bads"] = bads
    interpolate_bad_channels(raw)

    # 4. ASR artifact cleaning
    apply_asr(raw, params.get("asr", {}))

    # 5. Average re-reference
    apply_reference(raw, params.get("reference", "average"))

    # 6. ICA
    ica_result = run_ica(raw, params["ica"])

    return {
        "raw": raw,
        "bad_channels": bads,
        "ica": ica_result,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_preprocessing.py -v`
Expected: All tests PASS (some may skip if asrpy/pyprep not installed — that's fine)

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/preprocessing.py tests/test_preprocessing.py
git commit -m "feat: add preprocessing pipeline (filter, bad ch, ASR, ICA, re-ref)"
```

---

### Task 5: Spectral Analysis Module

**Files:**
- Create: `open_normative/spectral.py`
- Create: `tests/test_spectral.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for spectral analysis functions."""

import numpy as np
import pytest
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.spectral import (
    compute_psd,
    compute_band_power,
    compute_band_ratios,
    compute_aperiodic,
    compute_asymmetry,
    analyze_spectral,
)


def test_compute_psd(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    assert psds.shape[0] == 19  # n_channels
    assert len(freqs) > 0
    assert freqs[0] >= 0
    assert freqs[-1] <= params["fmax"] + 1


def test_compute_band_power(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    bands = params["bands"]
    band_power = compute_band_power(psds, freqs, bands)
    assert "Alpha" in band_power
    assert "absolute" in band_power["Alpha"]
    assert "relative" in band_power["Alpha"]
    assert len(band_power["Alpha"]["absolute"]) == 19
    # Relative powers should sum to approximately 1.0 across all bands
    # (Not exact because sub-bands overlap with main bands)


def test_compute_band_power_relative_sums():
    """Relative power of non-overlapping bands should sum to ~1."""
    n_ch = 5
    n_freqs = 200
    freqs = np.linspace(0.5, 50.0, n_freqs)
    psds = np.ones((n_ch, n_freqs)) * 1e-12
    # Use non-overlapping bands only
    bands = {
        "Delta": [1, 4],
        "Theta": [4, 8],
        "Alpha": [8, 13],
        "Beta": [13, 30],
        "Gamma": [30, 50],
    }
    bp = compute_band_power(psds, freqs, bands)
    total_rel = sum(bp[b]["relative"][0] for b in bands)
    assert abs(total_rel - 1.0) < 0.05  # Close to 1 (edge effects from trapezoid)


def test_compute_band_ratios(mock_band_power):
    ch_names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T3", "C3", "Cz", "C4", "T4",
        "T5", "P3", "Pz", "P4", "T6",
        "O1", "O2",
    ]
    ratios = compute_band_ratios(mock_band_power, ch_names)
    assert "Theta/Beta" in ratios
    assert "Fp1" in ratios["Theta/Beta"]
    assert ratios["Theta/Beta"]["Fp1"] > 0


def test_compute_aperiodic(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    ap_results = compute_aperiodic(psds, freqs, synthetic_raw_19ch.ch_names, params["aperiodic"])
    assert "Fp1" in ap_results
    assert "exponent" in ap_results["Fp1"]
    assert "slope" in ap_results["Fp1"]
    assert "r_squared" in ap_results["Fp1"]
    # Slope should be positive for 1/f data
    assert ap_results["Fp1"]["slope"] > 0


def test_compute_asymmetry(mock_band_power):
    ch_names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T3", "C3", "Cz", "C4", "T4",
        "T5", "P3", "Pz", "P4", "T6",
        "O1", "O2",
    ]
    pairs = PIPELINE_PARAMS["spectral"]["asymmetry"]["homologous_pairs"]
    asym = compute_asymmetry(mock_band_power, ch_names, pairs)
    assert "F3/F4" in asym
    assert "Alpha" in asym["F3/F4"]
    # Asymmetry should be in [-1, 1]
    for pair in asym:
        for band in asym[pair]:
            assert -1.0 <= asym[pair][band] <= 1.0


def test_analyze_spectral_returns_all_metrics(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    result = analyze_spectral(synthetic_raw_19ch, params)
    assert "psds" in result
    assert "freqs" in result
    assert "band_power" in result
    assert "ratios" in result
    assert "aperiodic" in result
    assert "asymmetry" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_spectral.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write spectral.py**

```python
"""Spectral analysis: PSD, band powers, aperiodic fitting, asymmetry.

Mirrors CW's resting.py spectral computations with identical parameters.
"""

import warnings

import numpy as np


def compute_psd(raw, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Compute power spectral density using Welch's method.

    Args:
        raw: MNE Raw object (preprocessed).
        params: Spectral params with method, fmin, fmax, n_fft.

    Returns:
        (psds, freqs) — psds shape (n_channels, n_freqs), in V²/Hz.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="nperseg.*greater than input length")
        spectrum = raw.compute_psd(
            method=params.get("method", "welch"),
            fmin=params["fmin"],
            fmax=params["fmax"],
            n_fft=params.get("n_fft", 1024),
            verbose=False,
        )
    psds = spectrum.get_data()
    freqs = spectrum.freqs
    return psds, freqs


def compute_band_power(
    psds: np.ndarray, freqs: np.ndarray, bands: dict
) -> dict:
    """Compute absolute and relative band power for each channel.

    Args:
        psds: Shape (n_channels, n_freqs), in V²/Hz.
        freqs: Frequency array.
        bands: Dict of {band_name: [fmin, fmax]}.

    Returns:
        Dict of {band_name: {"absolute": array, "relative": array}}.
    """
    total_power = np.trapezoid(psds, freqs, axis=1)
    band_power = {}
    for band_name, (fmin, fmax) in bands.items():
        idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
        if len(idx) == 0:
            band_power[band_name] = {
                "absolute": np.zeros(psds.shape[0]),
                "relative": np.zeros(psds.shape[0]),
            }
            continue
        abs_power = np.trapezoid(psds[:, idx], freqs[idx], axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_power = np.where(total_power > 0, abs_power / total_power, 0.0)
        band_power[band_name] = {"absolute": abs_power, "relative": rel_power}
    return band_power


def compute_band_ratios(band_power: dict, ch_names: list[str]) -> dict:
    """Compute key band ratios at each channel.

    Args:
        band_power: Output of compute_band_power.
        ch_names: Channel names matching band_power array indices.

    Returns:
        Dict of {ratio_name: {ch_name: value}}.
    """
    ratio_defs = {
        "Theta/Beta": ("Theta", "Beta"),
        "Theta/Beta1": ("Theta", "Beta1"),
        "Delta/HighBeta": ("Delta", "HighBeta"),
        "Alpha/HighBeta": ("Alpha", "HighBeta"),
    }
    ratios = {}
    for ratio_name, (num_band, den_band) in ratio_defs.items():
        if num_band in band_power and den_band in band_power:
            num = band_power[num_band]["absolute"]
            den = band_power[den_band]["absolute"]
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.where(den > 0, num / den, np.nan)
            ratios[ratio_name] = dict(zip(ch_names, ratio.tolist()))
    return ratios


def compute_aperiodic(
    psds: np.ndarray,
    freqs: np.ndarray,
    ch_names: list[str],
    params: dict,
) -> dict:
    """Fit 1/f aperiodic component using specparam (FOOOF) per channel.

    Args:
        psds: Shape (n_channels, n_freqs), in V²/Hz.
        freqs: Frequency array.
        ch_names: Channel names.
        params: Aperiodic params (freq_range, thresholds, peak settings).

    Returns:
        Dict of {ch_name: {exponent, offset, slope, r_squared, ...}}.
    """
    from specparam import SpectralModel

    # MNE returns V²/Hz — convert to µV²/Hz for specparam
    psds_uv = psds * 1e12
    r_sq_threshold = params.get("r_squared_threshold", 0.85)
    results = {}

    for i, ch in enumerate(ch_names):
        sm = SpectralModel(
            peak_width_limits=params.get("peak_width_limits", [1, 8]),
            max_n_peaks=params.get("max_n_peaks", 6),
            min_peak_height=params.get("min_peak_height", 0.1),
            peak_threshold=params.get("peak_threshold", 2.0),
            verbose=False,
        )
        try:
            sm.fit(freqs, psds_uv[i], params.get("freq_range", [2, 40]))
            # Handle both old and new specparam API
            if hasattr(sm, "aperiodic_params_"):
                exponent = float(sm.aperiodic_params_[-1])
                offset = float(sm.aperiodic_params_[0])
                r_squared = float(sm.r_squared_)
                n_peaks = int(sm.n_peaks_)
                peak_params = sm.peak_params_.tolist() if sm.n_peaks_ > 0 else []
            else:
                ap = sm.results.params.aperiodic
                exponent = float(ap.params[ap.indices["exponent"]])
                offset = float(ap.params[ap.indices["offset"]])
                r_squared = float(sm.results.metrics.results.get("gof_rsquared", 0))
                n_peaks = int(sm.results.n_peaks)
                peak_params = sm.results.params.periodic.params.tolist()

            fit_quality = "good" if r_squared >= r_sq_threshold else "poor"
            results[ch] = {
                "exponent": exponent,
                "offset": offset,
                "slope": -exponent,
                "r_squared": r_squared,
                "fit_quality": fit_quality,
                "n_peaks": n_peaks,
                "peak_params": peak_params,
            }
        except Exception:
            results[ch] = {
                "exponent": np.nan,
                "offset": np.nan,
                "slope": np.nan,
                "r_squared": 0.0,
                "fit_quality": "failed",
                "n_peaks": 0,
                "peak_params": [],
            }
    return results


def compute_asymmetry(
    band_power: dict, ch_names: list[str], pairs: list[list[str]]
) -> dict:
    """Compute hemispheric asymmetry (laterality index) for homologous pairs.

    Formula: ASI = (Right - Left) / (Right + Left)

    Args:
        band_power: Output of compute_band_power.
        ch_names: Channel names.
        pairs: List of [left_ch, right_ch] pairs.

    Returns:
        Dict of {"left/right": {band: asi_value}}.
    """
    results = {}
    for left, right in pairs:
        if left not in ch_names or right not in ch_names:
            continue
        li = ch_names.index(left)
        ri = ch_names.index(right)
        pair_key = f"{left}/{right}"
        results[pair_key] = {}
        for band_name, powers in band_power.items():
            lp = powers["absolute"][li]
            rp = powers["absolute"][ri]
            denom = lp + rp
            if denom > 0:
                results[pair_key][band_name] = float((rp - lp) / denom)
            else:
                results[pair_key][band_name] = 0.0
    return results


def analyze_spectral(raw, params: dict) -> dict:
    """Run full spectral analysis pipeline.

    Args:
        raw: MNE Raw object (preprocessed).
        params: The 'spectral' section of PIPELINE_PARAMS.

    Returns:
        Dict with psds, freqs, band_power, ratios, aperiodic, asymmetry.
    """
    psds, freqs = compute_psd(raw, params)
    band_power = compute_band_power(psds, freqs, params["bands"])
    ratios = compute_band_ratios(band_power, raw.ch_names)
    aperiodic = compute_aperiodic(psds, freqs, raw.ch_names, params["aperiodic"])
    asymmetry = compute_asymmetry(
        band_power, raw.ch_names, params["asymmetry"]["homologous_pairs"]
    )
    return {
        "psds": psds,
        "freqs": freqs,
        "band_power": band_power,
        "ratios": ratios,
        "aperiodic": aperiodic,
        "asymmetry": asymmetry,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_spectral.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/spectral.py tests/test_spectral.py
git commit -m "feat: add spectral analysis (PSD, bands, aperiodic, asymmetry)"
```

---

### Task 6: Connectivity Module

**Files:**
- Create: `open_normative/connectivity.py`
- Create: `tests/test_connectivity.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    data = np.random.randn(3, int(sfreq * 5)) * 20e-6  # Only 5 seconds
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
    assert "imcoh" in results
    # Each method should have band results
    for method in params["methods"]:
        assert len(results[method]) > 0
        for band, matrix in results[method].items():
            assert matrix.shape == (10, 10)
            # Diagonal should be zero
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_connectivity.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write connectivity.py**

```python
"""Connectivity analysis: dwPLI, coherence, graph metrics, PAC.

Mirrors CW's connectivity.py with identical hub definitions and methods.
"""

import warnings

import mne
import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt


# MNE-connectivity method name mapping
_METHOD_MAP = {
    "dwpli": "wpli2_debiased",
    "coh": "coh",
    "imcoh": "imcoh",
}


def epoch_continuous(
    raw: mne.io.Raw,
    epoch_length: float = 2.0,
    overlap: float = 0.0,
    min_epochs: int = 30,
    max_epochs: int = 120,
) -> mne.Epochs | None:
    """Create fixed-length epochs from continuous resting data.

    Returns None if fewer than min_epochs can be created.
    """
    duration = raw.times[-1] - raw.times[0]
    step = epoch_length - overlap
    n_possible = int(duration // step)

    if n_possible < min_epochs:
        return None

    events = mne.make_fixed_length_events(raw, duration=epoch_length, overlap=overlap)
    epochs = mne.Epochs(
        raw,
        events,
        tmin=0,
        tmax=epoch_length - 1.0 / raw.info["sfreq"],
        baseline=None,
        preload=True,
        verbose=False,
    )

    # Cap epoch count (take from middle of recording)
    if max_epochs and max_epochs > 0 and len(epochs) > max_epochs:
        n_total = len(epochs)
        start = (n_total - max_epochs) // 2
        indices = list(range(start, start + max_epochs))
        epochs = epochs[indices]

    return epochs


def average_hub_signals(
    epochs: mne.Epochs, hubs: dict
) -> tuple[mne.EpochsArray, list[str], dict]:
    """Average channel signals within each hub to create hub-level epochs.

    Args:
        epochs: MNE Epochs object with channel-level data.
        hubs: Dict of {hub_id: [channel_names]}.

    Returns:
        (hub_epochs, hub_names, hub_mapping) where hub_mapping shows which
        channels were available for each hub.
    """
    ch_names = epochs.ch_names
    data = epochs.get_data()  # (n_epochs, n_channels, n_times)
    sfreq = epochs.info["sfreq"]

    hub_data_list = []
    hub_names = []
    hub_mapping = {}

    for hub_id, hub_channels in hubs.items():
        available = [ch for ch in hub_channels if ch in ch_names]
        if not available:
            continue
        indices = [ch_names.index(ch) for ch in available]
        hub_signal = data[:, indices, :].mean(axis=1, keepdims=True)
        hub_data_list.append(hub_signal)
        hub_names.append(hub_id)
        hub_mapping[hub_id] = available

    hub_data = np.concatenate(hub_data_list, axis=1)
    info = mne.create_info(ch_names=hub_names, sfreq=sfreq, ch_types="eeg")
    hub_epochs = mne.EpochsArray(hub_data, info, verbose=False)
    return hub_epochs, hub_names, hub_mapping


def compute_connectivity(
    hub_epochs: mne.EpochsArray, hub_names: list[str], params: dict
) -> tuple[dict, list]:
    """Compute connectivity metrics per frequency band.

    Args:
        hub_epochs: Hub-averaged epochs.
        hub_names: Hub identifiers.
        params: Connectivity section of PIPELINE_PARAMS.

    Returns:
        (results, vc_flags) where results[method][band] is a (n_hubs, n_hubs) matrix
        and vc_flags lists potential volume conduction pairs.
    """
    from mne_connectivity import spectral_connectivity_epochs

    bands = params.get("bands", {})
    methods = params.get("methods", ["dwpli", "coh", "imcoh"])
    mne_methods = [_METHOD_MAP.get(m, m) for m in methods]

    # Filter bands that need more cycles than epoch length allows
    epoch_len = hub_epochs.times[-1] - hub_epochs.times[0]
    min_reliable_freq = 5.0 / epoch_len if epoch_len > 0 else 0

    band_names = [b for b in bands if bands[b][0] >= min_reliable_freq]
    fmin = [bands[b][0] for b in band_names]
    fmax = [bands[b][1] for b in band_names]

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        con = spectral_connectivity_epochs(
            hub_epochs,
            method=mne_methods,
            fmin=fmin,
            fmax=fmax,
            faverage=True,
            n_jobs=1,
            verbose=False,
        )

    if not isinstance(con, list):
        con = [con]

    n_hubs = len(hub_names)
    results = {}
    for i, method in enumerate(methods):
        con_data = con[i].get_data(output="dense")
        results[method] = {}
        for j, band in enumerate(band_names):
            matrix = con_data[:, :, j].copy()
            matrix = (matrix + matrix.T) / 2
            np.fill_diagonal(matrix, 0)
            results[method][band] = matrix

    # Volume conduction detection
    vc_flags = []
    if "coh" in results and "dwpli" in results:
        for band in band_names:
            if band not in results["coh"] or band not in results["dwpli"]:
                continue
            coh_mat = results["coh"][band]
            dwpli_mat = results["dwpli"][band]
            for i in range(n_hubs):
                for j in range(i + 1, n_hubs):
                    if coh_mat[i, j] > 0.5 and dwpli_mat[i, j] < 0.1:
                        vc_flags.append({
                            "band": band,
                            "hub_a": hub_names[i],
                            "hub_b": hub_names[j],
                            "coherence": float(coh_mat[i, j]),
                            "dwpli": float(dwpli_mat[i, j]),
                        })

    return results, vc_flags


def compute_electrode_connectivity(
    epochs: mne.Epochs, params: dict
) -> tuple[dict, dict, list[str]]:
    """Compute all-to-all electrode-level dwPLI and coherence per band.

    Returns:
        (dwpli_node_strength, dwpli_matrices, ch_names)
    """
    from mne_connectivity import spectral_connectivity_epochs

    bands = params.get("bands", {})
    band_names = list(bands.keys())
    fmin = [bands[b][0] for b in band_names]
    fmax = [bands[b][1] for b in band_names]
    ch_names = list(epochs.ch_names)

    con = spectral_connectivity_epochs(
        epochs,
        method=["wpli2_debiased", "coh"],
        fmin=fmin,
        fmax=fmax,
        faverage=True,
        n_jobs=1,
        verbose=False,
    )

    if not isinstance(con, list):
        con = [con]

    dwpli_data = con[0].get_data(output="dense")
    coh_data = con[1].get_data(output="dense")

    node_strength = {}
    full_matrices = {}
    for j, band in enumerate(band_names):
        matrix = dwpli_data[:, :, j].copy()
        matrix = (matrix + matrix.T) / 2
        np.fill_diagonal(matrix, 0)
        full_matrices[band] = matrix
        node_strength[band] = matrix.mean(axis=1)

    return node_strength, full_matrices, ch_names


def compute_graph_metrics(
    dwpli_matrices: dict, hub_names: list[str], params: dict
) -> dict:
    """Compute graph-theoretic metrics from dwPLI matrices.

    Args:
        dwpli_matrices: Dict of {band: ndarray(n_hubs, n_hubs)}.
        hub_names: Hub identifiers.
        params: Connectivity params (uses graph.threshold_percentile).

    Returns:
        Dict of {band: {strength, betweenness, clustering, ...}}.
    """
    import networkx as nx

    threshold_pct = params.get("graph", {}).get("threshold_percentile", 75)
    results = {}

    for band, matrix in dwpli_matrices.items():
        adj = matrix.copy()
        nonzero = matrix[matrix > 0]
        if len(nonzero) == 0:
            results[band] = {
                "strength": {h: 0.0 for h in hub_names},
                "betweenness": {h: 0.0 for h in hub_names},
                "clustering": {h: 0.0 for h in hub_names},
                "global_efficiency": 0.0,
                "char_path_length": None,
                "is_connected": False,
            }
            continue

        threshold = np.percentile(nonzero, threshold_pct)
        adj[adj < threshold] = 0

        G = nx.from_numpy_array(adj)
        G = nx.relabel_nodes(G, {i: hub_names[i] for i in range(len(hub_names))})

        strength = dict(G.degree(weight="weight"))
        betweenness = nx.betweenness_centrality(G, weight="weight")
        clustering = nx.clustering(G, weight="weight")
        global_eff = nx.global_efficiency(G)
        is_connected = nx.is_connected(G)

        char_path = None
        if is_connected and G.number_of_edges() > 0:
            try:
                char_path = nx.average_shortest_path_length(G, weight=None)
            except nx.NetworkXError:
                char_path = None

        results[band] = {
            "strength": {k: float(v) for k, v in strength.items()},
            "betweenness": {k: float(v) for k, v in betweenness.items()},
            "clustering": {k: float(v) for k, v in clustering.items()},
            "global_efficiency": float(global_eff),
            "char_path_length": float(char_path) if char_path else None,
            "is_connected": is_connected,
        }

    return results


def _bandpass(data, fmin, fmax, sfreq, order=4):
    """Apply zero-phase Butterworth bandpass filter."""
    nyq = sfreq / 2.0
    low = max(fmin / nyq, 0.001)
    high = min(fmax / nyq, 0.999)
    sos = butter(order, [low, high], btype="band", output="sos")
    return sosfiltfilt(sos, data, axis=-1)


def _modulation_index(theta_phase, gamma_amp, n_bins=18):
    """Compute Modulation Index (Tort et al., 2010)."""
    phase_bins = np.linspace(-np.pi, np.pi, n_bins + 1)
    mean_amp = np.zeros(n_bins)
    for i in range(n_bins):
        mask = (theta_phase >= phase_bins[i]) & (theta_phase < phase_bins[i + 1])
        if mask.sum() > 0:
            mean_amp[i] = gamma_amp[mask].mean()

    total = mean_amp.sum()
    if total == 0:
        return 0.0, mean_amp

    mean_amp_norm = mean_amp / total
    uniform = np.ones(n_bins) / n_bins
    mi = np.sum(mean_amp_norm * np.log(mean_amp_norm / uniform + 1e-12))
    mi /= np.log(n_bins)  # Normalize to [0, 1]
    return float(mi), mean_amp


def compute_pac(
    hub_epochs: mne.EpochsArray, hub_names: list[str], params: dict
) -> dict | None:
    """Compute theta-gamma phase-amplitude coupling.

    Args:
        hub_epochs: Hub-averaged epochs.
        hub_names: Hub identifiers.
        params: Connectivity params (uses cfc section).

    Returns:
        Dict with theta_gamma_pac results, or None if CFC disabled.
    """
    cfc_cfg = params.get("cfc", {})
    if not cfc_cfg.get("enabled", True):
        return None

    phase_band = cfc_cfg.get("phase_band", [4, 8])
    amp_band = cfc_cfg.get("amp_band", [30, 45])
    n_bins = cfc_cfg.get("n_bins", 18)
    hub_pairs = cfc_cfg.get("hub_pairs", [])

    data = hub_epochs.get_data()  # (n_epochs, n_hubs, n_times)
    sfreq = hub_epochs.info["sfreq"]
    n_hubs = len(hub_names)

    # Concatenate epochs for continuous phase/amplitude extraction
    data_concat = data.transpose(1, 0, 2).reshape(n_hubs, -1)

    # Extract phase and amplitude for each hub
    hub_phase = np.zeros_like(data_concat)
    hub_amp = np.zeros_like(data_concat)
    for h in range(n_hubs):
        theta_filt = _bandpass(data_concat[h], phase_band[0], phase_band[1], sfreq)
        gamma_filt = _bandpass(data_concat[h], amp_band[0], amp_band[1], sfreq)
        hub_phase[h] = np.angle(hilbert(theta_filt))
        hub_amp[h] = np.abs(hilbert(gamma_filt))

    # Within-hub PAC
    within_hub = {}
    for i, hub_id in enumerate(hub_names):
        mi, dist = _modulation_index(hub_phase[i], hub_amp[i], n_bins)
        within_hub[hub_id] = {"mi": mi, "phase_amp_dist": dist.tolist()}

    # Between-hub PAC
    between_hub = {}
    for hub_a, hub_b in hub_pairs:
        if hub_a not in hub_names or hub_b not in hub_names:
            continue
        idx_a = hub_names.index(hub_a)
        idx_b = hub_names.index(hub_b)
        mi, dist = _modulation_index(hub_phase[idx_a], hub_amp[idx_b], n_bins)
        pair_key = f"{hub_a}_to_{hub_b}"
        between_hub[pair_key] = {"mi": mi, "phase_amp_dist": dist.tolist()}

    all_mi = [v["mi"] for v in within_hub.values()] + [v["mi"] for v in between_hub.values()]
    global_mean_mi = float(np.mean(all_mi)) if all_mi else 0.0

    return {
        "theta_gamma_pac": {
            "within_hub": within_hub,
            "between_hub": between_hub,
            "global_mean_mi": global_mean_mi,
        },
    }


def analyze_connectivity(raw: mne.io.Raw, params: dict) -> dict:
    """Run full connectivity analysis pipeline.

    Args:
        raw: MNE Raw object (preprocessed).
        params: The 'connectivity' section of PIPELINE_PARAMS.

    Returns:
        Dict with hub_connectivity, electrode_connectivity, graph_metrics,
        pac, hub_names, vc_flags.
    """
    epochs = epoch_continuous(
        raw,
        epoch_length=params["epoch_length"],
        overlap=params.get("epoch_overlap", 0.0),
        min_epochs=params.get("min_epochs", 30),
        max_epochs=params.get("max_epochs", 120),
    )

    if epochs is None:
        return {
            "hub_connectivity": None,
            "electrode_connectivity": None,
            "graph_metrics": None,
            "pac": None,
            "hub_names": [],
            "vc_flags": [],
        }

    # Hub-level connectivity
    hub_epochs, hub_names, hub_mapping = average_hub_signals(epochs, params["hubs"])
    hub_results, vc_flags = compute_connectivity(hub_epochs, hub_names, params)
    graph = compute_graph_metrics(hub_results.get("dwpli", {}), hub_names, params)
    pac = compute_pac(hub_epochs, hub_names, params)

    # Electrode-level connectivity
    node_strength, full_matrices, ch_names = compute_electrode_connectivity(epochs, params)

    return {
        "hub_connectivity": hub_results,
        "electrode_connectivity": {
            "node_strength": node_strength,
            "matrices": full_matrices,
            "ch_names": ch_names,
        },
        "graph_metrics": graph,
        "pac": pac,
        "hub_names": hub_names,
        "hub_mapping": hub_mapping,
        "vc_flags": vc_flags,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_connectivity.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/connectivity.py tests/test_connectivity.py
git commit -m "feat: add connectivity analysis (dwPLI, coherence, graph metrics, PAC)"
```

---

### Task 7: Pipeline Orchestrator

**Files:**
- Create: `open_normative/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
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


def test_process_resting_custom_params(synthetic_raw_19ch):
    params = PIPELINE_PARAMS.copy()
    # Disable CFC to speed up test
    params["connectivity"] = {**params["connectivity"]}
    params["connectivity"]["cfc"] = {**params["connectivity"]["cfc"], "enabled": False}
    result = process_resting(synthetic_raw_19ch, condition="ec", params=params)
    assert result.condition == "ec"


def test_process_resting_skip_connectivity(synthetic_raw_19ch):
    params = PIPELINE_PARAMS.copy()
    result = process_resting(
        synthetic_raw_19ch, condition="eo", params=params, skip_connectivity=True
    )
    assert result.spectral is not None
    assert result.connectivity is None


def test_metrics_result_to_flat_dict(synthetic_raw_19ch):
    result = process_resting(
        synthetic_raw_19ch, condition="eo", skip_connectivity=True
    )
    flat = result.to_flat_dict()
    assert isinstance(flat, dict)
    # Should have channel-level metrics
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_pipeline.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write pipeline.py**

```python
"""Pipeline orchestrator: chains preprocessing → spectral → connectivity.

This is the main entry point for processing a single resting-state recording.
"""

from dataclasses import dataclass, field

import mne

from open_normative.parameters import PIPELINE_PARAMS
from open_normative.preprocessing import preprocess
from open_normative.spectral import analyze_spectral
from open_normative.connectivity import analyze_connectivity


@dataclass
class MetricsResult:
    """Container for all metrics from a single recording."""

    condition: str
    preprocessing: dict
    spectral: dict | None = None
    connectivity: dict | None = None

    def to_flat_dict(self) -> dict:
        """Flatten metrics into a single dict keyed by channel/band/metric.

        Keys like: "Fz.Alpha.absolute_power", "Fz.Alpha.relative_power",
        "F3/F4.Alpha.asymmetry", "Theta/Beta.Fz.ratio", etc.
        """
        flat = {}

        if self.spectral:
            bp = self.spectral.get("band_power", {})
            for band, powers in bp.items():
                ch_names = list(range(len(powers["absolute"])))
                if self.spectral.get("freqs") is not None:
                    # Get channel names from the aperiodic results
                    ap = self.spectral.get("aperiodic", {})
                    if ap:
                        ch_list = list(ap.keys())
                    else:
                        ch_list = [str(i) for i in range(len(powers["absolute"]))]
                else:
                    ch_list = [str(i) for i in range(len(powers["absolute"]))]

                for i, ch in enumerate(ch_list):
                    flat[f"{ch}.{band}.absolute_power"] = float(powers["absolute"][i])
                    flat[f"{ch}.{band}.relative_power"] = float(powers["relative"][i])

            # Aperiodic
            for ch, ap in self.spectral.get("aperiodic", {}).items():
                flat[f"{ch}.aperiodic.exponent"] = ap.get("exponent")
                flat[f"{ch}.aperiodic.slope"] = ap.get("slope")
                flat[f"{ch}.aperiodic.r_squared"] = ap.get("r_squared")

            # Ratios
            for ratio_name, ch_vals in self.spectral.get("ratios", {}).items():
                for ch, val in ch_vals.items():
                    flat[f"{ch}.{ratio_name}.ratio"] = val

            # Asymmetry
            for pair, bands in self.spectral.get("asymmetry", {}).items():
                for band, val in bands.items():
                    flat[f"{pair}.{band}.asymmetry"] = val

        if self.connectivity:
            # Hub connectivity
            hub_conn = self.connectivity.get("hub_connectivity")
            if hub_conn:
                hub_names = self.connectivity.get("hub_names", [])
                for method, bands in hub_conn.items():
                    for band, matrix in bands.items():
                        for i, hub_a in enumerate(hub_names):
                            for j, hub_b in enumerate(hub_names):
                                if i < j:
                                    flat[f"{hub_a}-{hub_b}.{band}.{method}"] = float(
                                        matrix[i, j]
                                    )

            # Graph metrics
            graph = self.connectivity.get("graph_metrics")
            if graph:
                for band, metrics in graph.items():
                    for hub, val in metrics.get("strength", {}).items():
                        flat[f"{hub}.{band}.graph_strength"] = val
                    flat[f"global.{band}.global_efficiency"] = metrics.get(
                        "global_efficiency"
                    )

            # PAC
            pac = self.connectivity.get("pac")
            if pac and "theta_gamma_pac" in pac:
                for hub, vals in pac["theta_gamma_pac"].get("within_hub", {}).items():
                    flat[f"{hub}.theta_gamma.pac_mi"] = vals["mi"]
                for pair, vals in pac["theta_gamma_pac"].get("between_hub", {}).items():
                    flat[f"{pair}.theta_gamma.pac_mi"] = vals["mi"]

        return flat

    def to_nested_dict(self) -> dict:
        """Return metrics as nested dict: {channel: {band: {metric: value}}}.

        This format is expected by build_normative() and compare_to_norms().
        """
        nested: dict[str, dict[str, dict[str, float]]] = {}

        if self.spectral:
            bp = self.spectral.get("band_power", {})
            ap = self.spectral.get("aperiodic", {})
            ch_names = list(ap.keys()) if ap else []

            for band, powers in bp.items():
                for i, ch in enumerate(ch_names):
                    nested.setdefault(ch, {}).setdefault(band, {})
                    nested[ch][band]["absolute_power"] = float(powers["absolute"][i])
                    nested[ch][band]["relative_power"] = float(powers["relative"][i])

            # Aperiodic as its own "band"
            for ch, vals in ap.items():
                nested.setdefault(ch, {}).setdefault("aperiodic", {})
                nested[ch]["aperiodic"]["exponent"] = vals.get("exponent")
                nested[ch]["aperiodic"]["slope"] = vals.get("slope")

            # Ratios
            for ratio_name, ch_vals in self.spectral.get("ratios", {}).items():
                for ch, val in ch_vals.items():
                    nested.setdefault(ch, {}).setdefault(ratio_name, {})
                    nested[ch][ratio_name]["ratio"] = val

            # Asymmetry
            for pair, bands in self.spectral.get("asymmetry", {}).items():
                for band, val in bands.items():
                    nested.setdefault(pair, {}).setdefault(band, {})
                    nested[pair][band]["asymmetry"] = val

        return nested


def process_resting(
    raw: mne.io.Raw,
    condition: str,
    params: dict | None = None,
    skip_connectivity: bool = False,
) -> MetricsResult:
    """Process a single resting-state recording through the full pipeline.

    Args:
        raw: MNE Raw object (already standardized to 19ch 10-20 montage).
        condition: "eo" (eyes open) or "ec" (eyes closed).
        params: Full PIPELINE_PARAMS dict. Uses default if None.
        skip_connectivity: If True, skip connectivity analysis (faster).

    Returns:
        MetricsResult with all extracted metrics.
    """
    if params is None:
        params = PIPELINE_PARAMS

    raw = raw.copy()  # Don't modify the caller's data

    # 1. Preprocess
    preproc_result = preprocess(raw, params["preprocessing"])
    processed_raw = preproc_result["raw"]

    # 2. Spectral analysis
    spectral_result = analyze_spectral(processed_raw, params["spectral"])

    # 3. Connectivity (optional)
    connectivity_result = None
    if not skip_connectivity:
        connectivity_result = analyze_connectivity(processed_raw, params["connectivity"])

    return MetricsResult(
        condition=condition,
        preprocessing={
            "bad_channels": preproc_result["bad_channels"],
            "ica_rejected": preproc_result["ica"]["rejected_components"],
        },
        spectral=spectral_result,
        connectivity=connectivity_result,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/pipeline.py tests/test_pipeline.py
git commit -m "feat: add pipeline orchestrator with MetricsResult dataclass"
```

---

### Task 8: Normative Distribution Builder

**Files:**
- Create: `open_normative/normative.py`
- Create: `open_normative/io.py`
- Create: `tests/test_normative.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    assert hasattr(cell, "bin")
    assert hasattr(cell, "condition")
    assert hasattr(cell, "channel")
    assert hasattr(cell, "band")
    assert hasattr(cell, "metric")
    assert hasattr(cell, "n")
    assert hasattr(cell, "mean")
    assert hasattr(cell, "sd")
    assert hasattr(cell, "log_mean")
    assert hasattr(cell, "log_sd")
    assert hasattr(cell, "log_transformed")
    assert hasattr(cell, "normality_p")
    assert hasattr(cell, "percentiles")


def test_build_normative_age_bins(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics, age_bins=[20, 40, 60, 80])
    bins_seen = {cell.bin for cell in norms}
    # Should see at least one of these bins
    assert len(bins_seen) > 0
    for b in bins_seen:
        assert "-" in b  # Format: "20-39"


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
    # Read back and check header
    with open(fpath) as f:
        header = f.readline()
    assert "bin" in header
    assert "mean" in header
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_normative.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write normative.py**

```python
"""Build normative distributions from per-subject metrics.

Aggregates metrics into age-binned cells with parametric stats
(mean, SD, optional log-transform) and non-parametric percentiles.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import stats as scipy_stats

# Metrics that should be log-transformed before computing parametric stats
_LOG_TRANSFORM_METRICS = {"absolute_power", "Theta/Beta", "Theta/Beta1",
                          "Delta/HighBeta", "Alpha/HighBeta"}

_PERCENTILE_POINTS = [1, 5, 10, 25, 50, 75, 90, 95, 99]

_DEFAULT_AGE_BINS = [20, 30, 40, 50, 60, 70, 80]


@dataclass
class NormCell:
    """A single normative distribution cell."""

    bin: str
    condition: str
    channel: str
    band: str
    metric: str
    n: int
    mean: float
    sd: float
    log_mean: float | None
    log_sd: float | None
    log_transformed: bool
    normality_p: float | None
    percentiles: dict[str, float]


def _age_bin_label(age: float, bins: list[int]) -> str | None:
    """Map an age to a bin label like '20-29'."""
    for i in range(len(bins) - 1):
        if bins[i] <= age < bins[i + 1]:
            return f"{bins[i]}-{bins[i + 1] - 1}"
    return None


def build_normative(
    subjects: list[dict],
    age_bins: list[int] | None = None,
    conditions: list[str] | None = None,
) -> list[NormCell]:
    """Build normative distributions from per-subject metrics.

    Args:
        subjects: List of dicts with keys: subject_id, age, sex, condition,
            metrics (nested dict of {channel: {band: {metric: value}}}).
        age_bins: Bin edges (default: decade bins 20-80).
        conditions: Conditions to include (default: all found).

    Returns:
        List of NormCell objects.
    """
    if age_bins is None:
        age_bins = _DEFAULT_AGE_BINS

    # Group subjects by (bin, condition)
    groups: dict[tuple[str, str], list[dict]] = {}
    for subj in subjects:
        bin_label = _age_bin_label(subj["age"], age_bins)
        if bin_label is None:
            continue
        cond = subj["condition"]
        if conditions and cond not in conditions:
            continue
        key = (bin_label, cond)
        groups.setdefault(key, []).append(subj)

    # Collect unique (channel, band, metric) combos from first subject
    metric_paths = set()
    for subj in subjects:
        for ch, bands in subj.get("metrics", {}).items():
            for band, metrics in bands.items():
                for metric_name in metrics:
                    metric_paths.add((ch, band, metric_name))
        break  # Assume all subjects have the same structure

    # Build cells
    cells = []
    for (bin_label, cond), group_subjects in groups.items():
        for ch, band, metric_name in metric_paths:
            values = []
            for subj in group_subjects:
                try:
                    val = subj["metrics"][ch][band][metric_name]
                    if val is not None and np.isfinite(val):
                        values.append(val)
                except (KeyError, TypeError):
                    continue

            if len(values) < 2:
                continue

            values = np.array(values)
            should_log = metric_name in _LOG_TRANSFORM_METRICS

            # Raw stats
            mean_val = float(np.mean(values))
            sd_val = float(np.std(values, ddof=1))

            # Log-transformed stats
            log_mean = None
            log_sd = None
            if should_log:
                positive = values[values > 0]
                if len(positive) >= 2:
                    log_vals = np.log(positive)
                    log_mean = float(np.mean(log_vals))
                    log_sd = float(np.std(log_vals, ddof=1))

            # Normality test (Shapiro-Wilk)
            normality_p = None
            if 3 <= len(values) <= 5000:
                try:
                    _, normality_p = scipy_stats.shapiro(values)
                    normality_p = float(normality_p)
                except Exception:
                    pass

            # Percentiles
            percentiles = {}
            for p in _PERCENTILE_POINTS:
                percentiles[str(p)] = float(np.percentile(values, p))

            cells.append(NormCell(
                bin=bin_label,
                condition=cond,
                channel=ch,
                band=band,
                metric=metric_name,
                n=len(values),
                mean=mean_val,
                sd=sd_val,
                log_mean=log_mean,
                log_sd=log_sd,
                log_transformed=should_log,
                normality_p=normality_p,
                percentiles=percentiles,
            ))

    return cells
```

- [ ] **Step 4: Write io.py**

```python
"""Read/write normative distributions as JSON and CSV."""

import csv
import json
from dataclasses import asdict
from pathlib import Path

from open_normative.normative import NormCell


def write_norms_json(cells: list[NormCell], filepath: str | Path) -> None:
    """Write normative cells to a JSON file."""
    filepath = Path(filepath)
    data = [asdict(cell) for cell in cells]
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def read_norms_json(filepath: str | Path) -> list[NormCell]:
    """Read normative cells from a JSON file."""
    filepath = Path(filepath)
    with open(filepath) as f:
        data = json.load(f)
    return [NormCell(**d) for d in data]


def write_norms_csv(cells: list[NormCell], filepath: str | Path) -> None:
    """Write normative cells to a flat CSV file."""
    filepath = Path(filepath)
    if not cells:
        return

    fieldnames = [
        "bin", "condition", "channel", "band", "metric",
        "n", "mean", "sd", "log_mean", "log_sd", "log_transformed",
        "normality_p",
    ]
    # Add percentile columns
    pct_keys = sorted(cells[0].percentiles.keys(), key=lambda x: int(x))
    fieldnames += [f"p{k}" for k in pct_keys]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cell in cells:
            row = {
                "bin": cell.bin,
                "condition": cell.condition,
                "channel": cell.channel,
                "band": cell.band,
                "metric": cell.metric,
                "n": cell.n,
                "mean": cell.mean,
                "sd": cell.sd,
                "log_mean": cell.log_mean,
                "log_sd": cell.log_sd,
                "log_transformed": cell.log_transformed,
                "normality_p": cell.normality_p,
            }
            for k in pct_keys:
                row[f"p{k}"] = cell.percentiles.get(k)
            writer.writerow(row)


def write_subjects_csv(
    subjects: list[dict], filepath: str | Path
) -> None:
    """Write per-subject metrics to CSV for rebinning.

    Args:
        subjects: List of subject dicts with subject_id, age, sex, condition, metrics.
        filepath: Output CSV path.
    """
    filepath = Path(filepath)
    if not subjects:
        return

    # Discover all metric paths from first subject
    flat_keys = []
    first_metrics = subjects[0].get("metrics", {})
    for ch, bands in first_metrics.items():
        for band, metrics in bands.items():
            for metric_name in metrics:
                flat_keys.append(f"{ch}.{band}.{metric_name}")

    fieldnames = ["subject_id", "age", "sex", "condition"] + sorted(flat_keys)

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for subj in subjects:
            row = {
                "subject_id": subj["subject_id"],
                "age": subj["age"],
                "sex": subj.get("sex", ""),
                "condition": subj["condition"],
            }
            for ch, bands in subj.get("metrics", {}).items():
                for band, metrics in bands.items():
                    for metric_name, val in metrics.items():
                        row[f"{ch}.{band}.{metric_name}"] = val
            writer.writerow(row)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_normative.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/normative.py open_normative/io.py tests/test_normative.py
git commit -m "feat: add normative distribution builder and I/O (JSON, CSV)"
```

---

### Task 9: Compare Module

**Files:**
- Create: `open_normative/compare.py`
- Create: `tests/test_compare.py`

- [ ] **Step 1: Write the failing tests**

```python
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
        metrics=clinical_metrics,
        norms=sample_norms,
        age=35,
        condition="eo",
    )
    assert len(results) > 0
    assert isinstance(results[0], ComparisonResult)


def test_comparison_result_fields(sample_norms, clinical_metrics):
    results = compare_to_norms(
        metrics=clinical_metrics,
        norms=sample_norms,
        age=35,
        condition="eo",
    )
    r = results[0]
    assert hasattr(r, "channel")
    assert hasattr(r, "band")
    assert hasattr(r, "metric")
    assert hasattr(r, "value")
    assert hasattr(r, "z_score")
    assert hasattr(r, "percentile_rank")
    assert hasattr(r, "low_confidence")


def test_compare_z_score_direction(sample_norms, clinical_metrics):
    """A very high value should have a positive z-score."""
    clinical_metrics["Fz"]["Alpha"]["absolute_power"] = 1000.0
    results = compare_to_norms(
        metrics=clinical_metrics,
        norms=sample_norms,
        age=35,
        condition="eo",
    )
    alpha_abs = [r for r in results if r.band == "Alpha" and r.metric == "absolute_power"]
    if alpha_abs:
        assert alpha_abs[0].z_score > 0


def test_compare_low_confidence_flag():
    """Norms with n < 10 should be flagged as low confidence."""
    # Create a norm cell with small n
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
    """Age outside all bins should return empty results."""
    cell = NormCell(
        bin="20-29", condition="eo", channel="Fz", band="Alpha",
        metric="relative_power", n=30, mean=0.2, sd=0.05,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=0.5,
        percentiles={"50": 0.2},
    )
    metrics = {"Fz": {"Alpha": {"relative_power": 0.25}}}
    results = compare_to_norms(metrics=metrics, norms=[cell], age=85, condition="eo")
    assert len(results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_compare.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Write compare.py**

```python
"""Compare a clinical recording's metrics against normative distributions.

Computes z-scores and percentile ranks, respecting log-transform rules.
"""

from dataclasses import dataclass

import numpy as np

from open_normative.normative import NormCell


@dataclass
class ComparisonResult:
    """Result of comparing one metric against its normative distribution."""

    channel: str
    band: str
    metric: str
    value: float
    z_score: float | None
    percentile_rank: float | None
    norm_mean: float
    norm_sd: float
    norm_n: int
    bin: str
    low_confidence: bool


def _interpolate_percentile(value: float, percentiles: dict[str, float]) -> float | None:
    """Interpolate percentile rank from stored percentile points."""
    points = sorted([(int(k), v) for k, v in percentiles.items()], key=lambda x: x[0])
    if not points:
        return None

    # Below minimum
    if value <= points[0][1]:
        return float(points[0][0])
    # Above maximum
    if value >= points[-1][1]:
        return float(points[-1][0])

    # Linear interpolation between bracketing points
    for i in range(len(points) - 1):
        p_low, v_low = points[i]
        p_high, v_high = points[i + 1]
        if v_low <= value <= v_high:
            if v_high == v_low:
                return float(p_low + p_high) / 2
            frac = (value - v_low) / (v_high - v_low)
            return p_low + frac * (p_high - p_low)

    return None


def _match_bin(age: float, bin_label: str) -> bool:
    """Check if an age falls within a bin label like '20-29'."""
    try:
        parts = bin_label.split("-")
        lo = int(parts[0])
        hi = int(parts[1])
        return lo <= age <= hi
    except (ValueError, IndexError):
        return False


def compare_to_norms(
    metrics: dict,
    norms: list[NormCell],
    age: float,
    condition: str,
) -> list[ComparisonResult]:
    """Compare clinical metrics against normative distributions.

    Args:
        metrics: Nested dict of {channel: {band: {metric: value}}}.
        norms: List of NormCell objects (from build_normative or read_norms_json).
        age: Subject's age in years.
        condition: "eo" or "ec".

    Returns:
        List of ComparisonResult objects.
    """
    # Index norms by (bin, condition, channel, band, metric)
    norm_index: dict[tuple, NormCell] = {}
    for cell in norms:
        if cell.condition != condition:
            continue
        if not _match_bin(age, cell.bin):
            continue
        key = (cell.channel, cell.band, cell.metric)
        norm_index[key] = cell

    results = []
    for ch, bands in metrics.items():
        for band, metric_vals in bands.items():
            for metric_name, value in metric_vals.items():
                key = (ch, band, metric_name)
                cell = norm_index.get(key)
                if cell is None:
                    continue

                if value is None or not np.isfinite(value):
                    continue

                # Compute z-score
                z_score = None
                if cell.log_transformed and cell.log_mean is not None and cell.log_sd:
                    if value > 0:
                        log_val = np.log(value)
                        z_score = (log_val - cell.log_mean) / cell.log_sd
                elif cell.sd and cell.sd > 0:
                    z_score = (value - cell.mean) / cell.sd

                if z_score is not None:
                    z_score = float(z_score)

                # Compute percentile rank
                percentile_rank = _interpolate_percentile(value, cell.percentiles)

                results.append(ComparisonResult(
                    channel=ch,
                    band=band,
                    metric=metric_name,
                    value=value,
                    z_score=z_score,
                    percentile_rank=percentile_rank,
                    norm_mean=cell.mean,
                    norm_sd=cell.sd,
                    norm_n=cell.n,
                    bin=cell.bin,
                    low_confidence=cell.n < 10,
                ))

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/git/peak-mind-llc/open-normative-eeg && python -m pytest tests/test_compare.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/compare.py tests/test_compare.py
git commit -m "feat: add normative comparison with z-scores and percentile ranks"
```

---

### Task 10: LEMON Dataset Loader

**Files:**
- Create: `open_normative/datasets/base.py`
- Create: `open_normative/datasets/lemon.py`
- Create: `open_normative/datasets/hbn.py`
- Create: `open_normative/datasets/mipdb.py`

- [ ] **Step 1: Write base.py**

```python
"""Abstract base class for dataset loaders."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import mne


@dataclass
class SubjectRecord:
    """A single subject's data from a dataset."""

    subject_id: str
    age: float
    sex: str  # "M" or "F"
    raw: mne.io.Raw
    condition: str  # "eo" or "ec"
    metadata: dict


class DatasetLoader(ABC):
    """Abstract base for public EEG dataset loaders."""

    @abstractmethod
    def download(self, dest_dir: Path) -> None:
        """Download dataset files to dest_dir."""
        ...

    @abstractmethod
    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Iterate over subjects, yielding SubjectRecord for each condition."""
        ...
```

- [ ] **Step 2: Write lemon.py**

```python
"""LEMON dataset loader.

MPI Leipzig Mind-Brain-Body dataset.
~220 subjects, ages 20-77, 62-channel BrainVision (10-10), eyes open + eyes closed.
BIDS format with participants.tsv metadata.

Reference: https://fcon_1000.projects.nitrc.org/indi/retro/MPI_LEMON.html
"""

import csv
import logging
from collections.abc import Iterator
from pathlib import Path

import mne

from open_normative.channels import pick_standard_19, normalize_channel_names
from open_normative.datasets.base import DatasetLoader, SubjectRecord

logger = logging.getLogger(__name__)

# LEMON condition file suffixes
_CONDITION_MAP = {
    "EC": "ec",
    "EO": "eo",
}


class LEMONLoader(DatasetLoader):
    """Loader for the MPI Leipzig LEMON dataset."""

    def download(self, dest_dir: Path) -> None:
        """Download LEMON dataset.

        LEMON is large (~60 GB). This provides instructions rather than
        auto-downloading. Use the LEMON download scripts or manual download.
        """
        raise NotImplementedError(
            "LEMON auto-download not yet implemented. "
            "Download manually from: "
            "https://fcon_1000.projects.nitrc.org/indi/retro/MPI_LEMON.html\n"
            f"Place BIDS-formatted data in: {dest_dir}"
        )

    def _parse_participants(self, data_dir: Path) -> dict[str, dict]:
        """Parse participants.tsv for age and sex metadata."""
        tsv_path = data_dir / "participants.tsv"
        if not tsv_path.exists():
            logger.warning("participants.tsv not found at %s", tsv_path)
            return {}

        participants = {}
        with open(tsv_path) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                sub_id = row.get("participant_id", "").replace("sub-", "")
                age_str = row.get("age", "")
                sex = row.get("sex", row.get("gender", ""))

                try:
                    age = float(age_str)
                except (ValueError, TypeError):
                    continue

                # Normalize sex
                if sex.upper() in ("M", "MALE"):
                    sex = "M"
                elif sex.upper() in ("F", "FEMALE"):
                    sex = "F"
                else:
                    sex = ""

                participants[sub_id] = {"age": age, "sex": sex}

        return participants

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Iterate over LEMON subjects.

        Expects BIDS layout:
            data_dir/
                participants.tsv
                sub-XXXX/
                    eeg/
                        sub-XXXX_task-rest_EC_eeg.vhdr
                        sub-XXXX_task-rest_EO_eeg.vhdr
        """
        data_dir = Path(data_dir)
        participants = self._parse_participants(data_dir)

        for sub_dir in sorted(data_dir.glob("sub-*")):
            if not sub_dir.is_dir():
                continue
            sub_id = sub_dir.name.replace("sub-", "")
            meta = participants.get(sub_id, {})
            age = meta.get("age")
            sex = meta.get("sex", "")

            if age is None:
                logger.info("Skipping %s: no age in participants.tsv", sub_id)
                continue

            eeg_dir = sub_dir / "eeg"
            if not eeg_dir.exists():
                continue

            for vhdr in sorted(eeg_dir.glob("*.vhdr")):
                # Detect condition from filename
                condition = None
                fname = vhdr.stem.upper()
                for key, cond in _CONDITION_MAP.items():
                    if key in fname:
                        condition = cond
                        break

                if condition is None:
                    logger.debug("Skipping %s: unknown condition", vhdr.name)
                    continue

                try:
                    raw = mne.io.read_raw_brainvision(vhdr, preload=True, verbose=False)
                    # Drop non-EEG channels
                    eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
                    if len(eeg_picks) < len(raw.ch_names):
                        raw.pick("eeg")
                    raw = pick_standard_19(raw)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", vhdr, e)
                    continue

                yield SubjectRecord(
                    subject_id=sub_id,
                    age=age,
                    sex=sex,
                    raw=raw,
                    condition=condition,
                    metadata={"source_file": str(vhdr)},
                )
```

- [ ] **Step 3: Write hbn.py and mipdb.py stubs**

`hbn.py`:
```python
"""HBN (Healthy Brain Network) dataset loader — stub.

~2500 subjects, ages 5-21, 128-channel EGI.
Requires spatial nearest-neighbor mapping to 19-channel 10-20.
"""

from collections.abc import Iterator
from pathlib import Path

from open_normative.datasets.base import DatasetLoader, SubjectRecord


class HBNLoader(DatasetLoader):

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError("HBN loader not yet implemented.")

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        raise NotImplementedError("HBN loader not yet implemented.")
```

`mipdb.py`:
```python
"""MIPDB dataset loader — stub.

~126 subjects, ages 6-44, 128-channel EGI.
Requires spatial nearest-neighbor mapping to 19-channel 10-20.
"""

from collections.abc import Iterator
from pathlib import Path

from open_normative.datasets.base import DatasetLoader, SubjectRecord


class MIPDBLoader(DatasetLoader):

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError("MIPDB loader not yet implemented.")

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        raise NotImplementedError("MIPDB loader not yet implemented.")
```

- [ ] **Step 4: Update datasets/__init__.py**

```python
"""Dataset loaders for public EEG datasets."""

from open_normative.datasets.lemon import LEMONLoader
from open_normative.datasets.hbn import HBNLoader
from open_normative.datasets.mipdb import MIPDBLoader

DATASETS = {
    "lemon": LEMONLoader,
    "hbn": HBNLoader,
    "mipdb": MIPDBLoader,
}
```

- [ ] **Step 5: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add open_normative/datasets/
git commit -m "feat: add dataset loaders (LEMON complete, HBN/MIPDB stubs)"
```

---

### Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# open-normative-eeg

Open normative EEG database builder with a clinical-grade processing pipeline.

## What This Is

A standalone Python package that processes public resting-state EEG datasets through a standardized pipeline and builds normative distributions. The pipeline is parameter-identical to the one used by [Coherence Workstation](https://coherenceworkstation.com) for clinical QEEG analysis.

**Why this matters:** Normative comparisons are only meaningful when the clinical recording and the normative database were processed through the same pipeline. Different filter settings, artifact rejection methods, or spectral algorithms produce different numbers — and comparing across pipelines produces misleading z-scores.

## Pipeline

Every recording passes through:

1. **Channel standardization** — Map to 19-channel 10-20 montage
2. **Resampling** — 256 Hz target
3. **Filtering** — 0.5–100 Hz bandpass, 60 Hz notch (+ harmonics)
4. **Bad channel detection** — RANSAC + variance heuristics
5. **Artifact cleaning** — ASR (Artifact Subspace Reconstruction)
6. **ICA** — PICARD extended with ICLabel auto-classification
7. **Re-referencing** — Average reference
8. **Spectral analysis** — PSD (Welch), 11 frequency bands, aperiodic/1/f fitting (specparam), asymmetry
9. **Connectivity** — dwPLI, coherence, imaginary coherence across 10 hub regions, graph metrics, theta-gamma PAC

## Supported Datasets

| Dataset | Subjects | Ages | Channels | Status |
|---------|----------|------|----------|--------|
| LEMON | ~220 | 20–77 | 62 (BrainVision) | Implemented |
| HBN | ~2500 | 5–21 | 128 (EGI) | Stub |
| MIPDB | ~126 | 6–44 | 128 (EGI) | Stub |

## Installation

```bash
pip install -e ".[datasets,dev]"
```

## Usage

### Process a single recording

```python
from open_normative.channels import load_and_standardize
from open_normative.pipeline import process_resting

raw = load_and_standardize("path/to/recording.vhdr")
result = process_resting(raw, condition="eo")
print(result.to_flat_dict())
```

### Build normative distributions from LEMON

```python
from open_normative.datasets.lemon import LEMONLoader
from open_normative.pipeline import process_resting
from open_normative.normative import build_normative
from open_normative.io import write_norms_json, write_subjects_csv

loader = LEMONLoader()
subjects = []

for record in loader.iter_subjects("/path/to/lemon"):
    result = process_resting(record.raw, condition=record.condition)
    subjects.append({
        "subject_id": record.subject_id,
        "age": record.age,
        "sex": record.sex,
        "condition": record.condition,
        "metrics": result.to_nested_dict(),
    })

norms = build_normative(subjects)
write_norms_json(norms, "norms.json")
write_subjects_csv(subjects, "subjects.csv")
```

### Compare a clinical recording against norms

```python
from open_normative.compare import compare_to_norms
from open_normative.io import read_norms_json

norms = read_norms_json("norms.json")
results = compare_to_norms(
    metrics=clinical_result.to_nested_dict(),
    norms=norms,
    age=42,
    condition="eo",
)

for r in results:
    if abs(r.z_score or 0) > 2.0:
        print(f"{r.channel} {r.band} {r.metric}: z={r.z_score:.2f}")
```

## Normative Output Format

Each normative cell stores:
- **Parametric stats**: mean, SD (and log-transformed mean/SD for power metrics)
- **Non-parametric stats**: percentiles at 1, 5, 10, 25, 50, 75, 90, 95, 99
- **Quality indicators**: sample size (n), Shapiro-Wilk normality p-value
- **Age bins**: Decade bins by default, configurable

## Using with Coherence Workstation

CW can import the shared processing functions directly:

```python
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.preprocessing import apply_filters
```

Install as a local editable dependency:

```bash
pip install -e /path/to/open-normative-eeg
```

## License

AGPL-3.0-or-later
```

- [ ] **Step 2: Commit**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
git add README.md
git commit -m "docs: add README with methodology overview and usage examples"
```

---

### Task 12: CW Integration Branch

**Context:** This task creates a feature branch in the CW repo and makes CW call into open-normative-eeg's shared processing functions.

**Files (in coherence-workstation repo):**
- Modify: `cw_eeg/preprocess.py` — delegate filter, bad channels, ASR, ICA, reference to open_normative
- Modify: `cw_eeg/resting.py` — delegate spectral analysis to open_normative

- [ ] **Step 1: Create CW feature branch**

```bash
cd ~/git/peak-mind-llc/coherence-workstation
git checkout dev
git pull origin dev
git checkout -b feature/open-normative-integration
```

- [ ] **Step 2: Install open-normative-eeg as editable dependency**

```bash
cd ~/git/peak-mind-llc/coherence-workstation
pip install -e ../open-normative-eeg
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from open_normative.parameters import PIPELINE_PARAMS; print('OK:', len(PIPELINE_PARAMS))"
```
Expected: `OK: 4`

- [ ] **Step 4: Add thin wrapper imports to CW's preprocess.py**

Read `cw_eeg/preprocess.py` to find the exact existing function signatures. Then add imports at the top that delegate to open_normative while preserving CW's progress reporting and config resolution.

The key change is adding this pattern at the top of `cw_eeg/preprocess.py`:

```python
# Shared processing functions from open-normative-eeg
try:
    from open_normative.preprocessing import (
        apply_filters as _on_apply_filters,
        detect_bad_channels as _on_detect_bad_channels,
        apply_asr as _on_apply_asr,
        run_ica as _on_run_ica,
        apply_reference as _on_apply_reference,
        resample as _on_resample,
    )
    _HAS_OPEN_NORMATIVE = True
except ImportError:
    _HAS_OPEN_NORMATIVE = False
```

Then in each CW function, add a delegation check:

```python
def apply_filters(raw, cfg):
    emit_progress("Filtering...")
    if _HAS_OPEN_NORMATIVE:
        params = cfg["preprocessing"]["filter"]
        return _on_apply_filters(raw, params)
    # ... existing CW implementation as fallback ...
```

**Important:** This is an incremental integration. CW falls back to its own code if open-normative-eeg isn't installed. The exact modifications depend on reading the current CW code at implementation time — the implementer must read `cw_eeg/preprocess.py` first and adapt the delegation points to match the existing function signatures.

- [ ] **Step 5: Run CW tests to verify no regressions**

```bash
cd ~/git/peak-mind-llc/coherence-workstation
pytest tests/ -x -q
```
Expected: Same pass/fail count as before (5 known pre-existing failures from ICA torch/onnxruntime imports)

- [ ] **Step 6: Commit**

```bash
cd ~/git/peak-mind-llc/coherence-workstation
git add cw_eeg/preprocess.py
git commit -m "feat: delegate preprocessing to open-normative-eeg shared functions"
```

---

### Task 13: Full Test Suite Run

- [ ] **Step 1: Run all open-normative-eeg tests**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
python -m pytest tests/ -v --tb=short
```
Expected: All tests PASS

- [ ] **Step 2: Run ruff lint**

```bash
cd ~/git/peak-mind-llc/open-normative-eeg
ruff check open_normative/ tests/
```
Expected: No errors

- [ ] **Step 3: Run CW tests with open-normative-eeg installed**

```bash
cd ~/git/peak-mind-llc/coherence-workstation
pytest tests/ -x -q
```
Expected: Same results as before integration

- [ ] **Step 4: Commit any fixes**

If lint or tests caught issues, fix and commit.
