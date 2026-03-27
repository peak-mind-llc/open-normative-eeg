# open-normative-eeg Design Spec

**Date:** 2026-03-27
**Status:** Approved
**Author:** James Croall + Claude

## Purpose

Extract the resting-state EEG processing pipeline from Coherence Workstation into
a standalone open-source package. The pipeline must be parameter-identical to CW's
clinical processing so that normative distributions built with this package are
directly comparable to clinical recordings processed by CW.

The package serves two audiences:

1. **Researchers** who want to build open normative EEG databases from public datasets
2. **Coherence Workstation** which will call into this package's processing functions
   to guarantee pipeline consistency

## Architecture

### Package Structure

```
open-normative-eeg/
├── open_normative/
│   ├── __init__.py
│   ├── parameters.py          # Canonical pipeline config dict
│   ├── pipeline.py            # Orchestrator: load → preprocess → analyze → metrics
│   ├── spectral.py            # PSD, bands, aperiodic fitting
│   ├── connectivity.py        # dwPLI, coherence, graph metrics, PAC
│   ├── preprocessing.py       # Filter, bad channels, ASR, ICA, re-ref
│   ├── channels.py            # Channel normalization, montage mapping
│   ├── normative.py           # Build distributions from processed subjects
│   ├── compare.py             # Compare recording against norms
│   ├── datasets/
│   │   ├── __init__.py
│   │   ├── base.py            # Abstract loader interface
│   │   ├── lemon.py           # LEMON dataset loader
│   │   ├── hbn.py             # HBN loader (stub)
│   │   └── mipdb.py           # MIPDB loader (stub)
│   └── io.py                  # Read/write norms (JSON, CSV)
├── tests/
│   ├── test_pipeline.py
│   ├── test_spectral.py
│   ├── test_connectivity.py
│   ├── test_normative.py
│   └── test_compare.py
├── pyproject.toml
├── README.md
└── LICENSE
```

### Design Principles

- Processing functions take an MNE `Raw` object as input, never a file path.
  File loading is the caller's responsibility (dataset loaders or CW's proprietary
  loaders).
- Every processing function takes an explicit params dict argument. No hidden defaults,
  no global config.
- `parameters.py` exports a single `PIPELINE_PARAMS` dict that is the canonical
  source of truth for all processing parameters.
- Modules are focused: `preprocessing.py` handles signal cleaning,
  `spectral.py` handles frequency-domain analysis, `connectivity.py` handles
  functional connectivity. `pipeline.py` orchestrates them.

## Data Flow

```
Raw EEG file (.vhdr, .edf, .set, .fif)
    ↓  channels.py: load + normalize channel names
    ↓  channels.py: map to 19ch 10-20 (pick or spatial nearest-neighbor)
    ↓  preprocessing.py: resample to 256 Hz
    ↓  preprocessing.py: bandpass 0.5–100 Hz + notch 60 Hz
    ↓  preprocessing.py: bad channel detection (RANSAC) + interpolation
    ↓  preprocessing.py: ASR artifact cleaning (cutoff=20)
    ↓  preprocessing.py: ICA (PICARD extended, ICLabel auto-reject ≥0.80)
    ↓  preprocessing.py: average re-reference
    ↓  spectral.py: PSD (Welch), band powers, relative powers, ratios
    ↓  spectral.py: aperiodic fitting (specparam, 2–40 Hz)
    ↓  spectral.py: asymmetry (laterality indices)
    ↓  connectivity.py: epoch (2s), dwPLI + coherence + imcoh per band
    ↓  connectivity.py: hub aggregation, graph metrics
    ↓  connectivity.py: theta-gamma PAC (optional, expensive)
    ↓
    MetricsResult (dataclass)
```

### Supported File Formats

Open standard formats only:

- `.vhdr` (BrainVision) — LEMON uses this
- `.edf` (European Data Format)
- `.set` (EEGLAB)
- `.fif` (MNE native)

Proprietary formats (`.nfx`, `.eeg`) remain exclusively in CW. The boundary is
clean: CW's proprietary loaders produce an MNE `Raw` object, then hand off to the
shared pipeline functions.

## Pipeline Parameters

All parameters extracted from CW's `configs/default.yaml` and processing code.
These live in `parameters.py` as a single dict.

### Preprocessing

```yaml
resample:
  enabled: true                    # Enabled here (unlike CW default) to normalize
  target_sfreq: 256.0             #   across datasets with different native rates

filter:
  l_freq: 0.5                     # High-pass — preserves full Delta [1-4 Hz]
  h_freq: 100.0                   # Low-pass — preserves Gamma [30-50 Hz]
  notch_freq: 60.0                # Power line (configurable for 50 Hz regions)
  notch_harmonics: [120.0, 180.0]
  notch_width: 2.0                # Hz bandwidth of notch

bad_channels:
  method: ransac
  correlation_threshold: 0.75
  flat_threshold_factor: 0.01     # < 1% of median variance = flat
  noisy_threshold_factor: 10.0    # > 10x median variance = noisy

asr:
  cutoff: 20                      # SD threshold
  window_length: 0.5              # Seconds per analysis window

ica:
  method: picard
  extended: true
  n_components: 0.999             # Variance explained
  max_iter: 500
  random_state: 42
  two_stage_filter: true
  ica_highpass: 1.0               # High-pass for ICA fitting copy
  brain_threshold: 0.80           # ICLabel: keep brain ≥ 0.80
  review_threshold: 0.50          # Auto-reject non-brain ≥ 0.50

reference: average
```

### Spectral Analysis

```yaml
spectral:
  method: welch
  fmin: 0.5
  fmax: 50.0
  n_fft: 1024

  bands:
    Delta: [1, 4]
    Theta: [4, 8]
    Alpha: [8, 13]
    Alpha1: [8, 10.5]
    Alpha2: [10.5, 13]
    Beta: [13, 30]
    Beta1: [13, 15]               # SMR
    Beta2: [15, 18]
    Beta3: [18, 25]
    HighBeta: [25, 30]
    Gamma: [30, 50]

  ratios:
    - [Theta, Beta]               # Theta/Beta ratio
    - [Theta, Beta1]              # Theta/SMR ratio
    - [Delta, HighBeta]
    - [Alpha, HighBeta]

  aperiodic:
    freq_range: [2, 40]
    r_squared_threshold: 0.85
    peak_width_limits: [1, 8]
    max_n_peaks: 6
    min_peak_height: 0.1
    peak_threshold: 2.0

  asymmetry:
    homologous_pairs:
      - [F3, F4]
      - [C3, C4]
      - [P3, P4]
      - [T3, T4]
      - [T5, T6]
      - [F7, F8]
      - [O1, O2]
    threshold: 0.15               # Flag if |LI| > 0.15
```

### Connectivity

```yaml
connectivity:
  epoch_length: 2.0               # Seconds
  epoch_overlap: 0.0
  min_epochs: 30
  max_epochs: 120
  methods: [dwpli, coh, imcoh]

  bands:                          # Main bands only (no sub-bands)
    Delta: [1, 4]
    Theta: [4, 8]
    Alpha: [8, 13]
    Beta: [13, 30]
    HighBeta: [25, 30]
    Gamma: [30, 50]

  hubs:
    F_mid: [Fz]
    F_L: [F3, F7]
    F_R: [F4, F8]
    C_mid: [Cz]
    T_L: [T3, T5]
    T_R: [T4, T6]
    P_mid: [Pz]
    P_L: [P3]
    P_R: [P4]
    O: [O1, O2]

  graph:
    threshold_percentile: 75

  cfc:
    enabled: true
    phase_band: [4, 8]            # Theta
    amp_band: [30, 45]            # Gamma
    n_bins: 18
    hub_pairs:
      - [F_mid, P_mid]
      - [F_L, T_L]
      - [F_R, T_R]
      - [T_L, P_mid]
      - [F_mid, T_L]
      - [F_mid, T_R]
```

### Channel Mapping

```yaml
target_montage: standard_1020

channels_19:
  - Fp1, Fp2, F3, F4, C3, C4, P3, P4, O1, O2
  - F7, F8, T3, T4, T5, T6, Fz, Cz, Pz

name_mapping:                     # 10-10 → 10-20 aliases
  T7: T3
  T8: T4
  P7: T5
  P8: T6

capitalization_fixes:
  FP1: Fp1
  FP2: Fp2
  FPZ: Fpz
```

## Normative Output Format

Combined parametric (B) + non-parametric (C) approach.

### Per-Cell Record

Each cell is one combination of (age_bin × condition × channel × band × metric):

```json
{
  "bin": "20-29",
  "condition": "eo",
  "channel": "Fz",
  "band": "Alpha",
  "metric": "relative_power",
  "n": 34,
  "mean": 0.23,
  "sd": 0.08,
  "log_mean": -1.47,
  "log_sd": 0.35,
  "log_transformed": true,
  "normality_p": 0.42,
  "percentiles": {
    "1": 0.07, "5": 0.11, "10": 0.13, "25": 0.17,
    "50": 0.22, "75": 0.28, "90": 0.34, "95": 0.38, "99": 0.44
  }
}
```

### Transform Rules by Metric Type

| Metric type | log_transformed | Rationale |
|---|---|---|
| Absolute power | true | Right-skewed; log-normal is standard in QEEG |
| Relative power | false | Bounded [0,1], approximately normal |
| Band ratios | true | Ratio distributions are log-normal |
| Aperiodic exponent | false | Approximately normal |
| Connectivity (dwPLI, coh, imcoh) | false | Bounded, approximately normal |
| Asymmetry (laterality index) | false | Symmetric around zero |
| Graph metrics | false | Approximately normal after threshold |

### Age Bins

Default decade bins: `[20, 30, 40, 50, 60, 70, 80]`

Configurable via `normative.py` parameters. Per-subject metrics are always stored
in `subjects.csv` so bins can be recomputed without reprocessing.

### Output Files

- `norms.json` — full structured norms for machine consumption
- `norms.csv` — flat table for human exploration
- `subjects.csv` — per-subject metrics with age, sex, condition (enables rebinning)

### Compare Behavior

`compare.py` takes a clinical recording's metrics and an age:

1. Match age to bin, find matching condition/channel/band/metric cells
2. If `log_transformed`, log-transform the clinical value before z-scoring
3. Compute z-score: `(value - mean) / sd` (or `(log(value) - log_mean) / log_sd`)
4. Compute percentile rank via interpolation against stored percentiles
5. Flag metrics where bin `n < 10` as low-confidence
6. Return structured comparison report

## Dataset Loaders

### Interface (base.py)

```python
@dataclass
class SubjectRecord:
    subject_id: str
    age: float
    sex: str                       # "M" or "F"
    raw: mne.io.Raw               # Loaded, channel-standardized
    condition: str                 # "eo" or "ec"
    metadata: dict                 # Dataset-specific extras

class DatasetLoader(ABC):
    @abstractmethod
    def download(self, dest_dir: Path) -> None: ...

    @abstractmethod
    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]: ...
```

### LEMON (priority — first implementation)

- **Source:** MPI Leipzig, ~220 subjects, ages 20–77
- **Format:** BrainVision (.vhdr), 62 channels (10-10 naming)
- **Conditions:** Eyes open + eyes closed (separate files)
- **Channel mapping:** 62ch 10-10 → 19ch 10-20 via name matching (standard 10-10
  names include all 19 channels from 10-20)
- **Metadata:** Age, sex from participants.tsv (BIDS format)
- **Download:** From public FTP/web endpoint

### HBN (stub)

- 128-channel EGI, ages 5–21, spatial nearest-neighbor mapping

### MIPDB (stub)

- 128-channel EGI, ages 6–44, spatial nearest-neighbor mapping

## CW Integration

### Dependency Setup

CW adds `open-normative-eeg` as a local editable install:

```bash
pip install -e ../open-normative-eeg
```

CW's `pyproject.toml` lists it as a dependency with an optional git fallback:

```toml
dependencies = [
    "open-normative-eeg>=0.1.0",
]
```

No PyPI publication needed. Every environment where CW runs is locally controlled.

### Wrapper Pattern

CW's preprocessing functions delegate to open-normative for signal processing,
wrapping with CW-specific concerns (progress reporting, stage output):

```python
# cw_eeg/preprocess.py (after refactor)
from open_normative.preprocessing import apply_filters as _apply_filters

def apply_filters(raw, cfg):
    emit_progress("Filtering...")
    params = cfg["preprocessing"]["filter"]
    return _apply_filters(raw, params)
```

### What CW Keeps Exclusively

- File loaders for proprietary formats (.nfx, .eeg)
- Progress reporting (`emit_progress()`)
- Stage output writing (`write_stage_output()`)
- ICA review UI
- Clinical interpretation layer (phenotypes, expert notes, AI prompts)
- ERP, ERSP, source localization, HRV, microstates, vigilance
- Server API, report generation

### What Moves to open-normative-eeg

- Filtering (bandpass, notch)
- Bad channel detection (RANSAC) + interpolation
- ASR artifact cleaning
- ICA decomposition + ICLabel auto-classification
- Average re-referencing
- Channel name normalization and montage mapping (open formats only)
- PSD computation, band power extraction, aperiodic fitting
- Asymmetry computation
- Connectivity computation (dwPLI, coherence, imcoh)
- Hub aggregation, graph metrics
- Cross-frequency coupling (theta-gamma PAC)

### Validation

After refactoring CW to call open-normative functions, the test is:
process the same recording through both the old CW path and the new
shared-function path. Outputs must be numerically identical. Any divergence
is a bug.

## Dependencies

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    "mne>=1.6",
    "numpy>=1.24",
    "scipy>=1.10",
    "specparam>=1.0",             # Aperiodic fitting (formerly FOOOF)
    "mne-icalabel>=0.4",          # IC classification
    "mne-connectivity>=0.5",      # Connectivity methods
    "python-picard>=0.7",         # ICA method
    "asrpy>=0.2",                 # Artifact Subspace Reconstruction
    "pyprep>=0.4",                # RANSAC bad channel detection
    "pandas>=2.0",                # Data handling for norms
]

[project.optional-dependencies]
datasets = [
    "requests",                   # Dataset download
    "tqdm",                       # Progress bars
]
dev = [
    "pytest>=7.0",
    "ruff>=0.1",
]
```

## Out of Scope

- Proprietary file format support (.nfx, .eeg)
- ERP / task-evoked analysis
- Source localization (LORETA, DICS, LCMV)
- HRV analysis
- Microstates, vigilance staging
- Phenotype detection
- Clinical interpretation / AI prompts
- Report generation
- Any UI components
