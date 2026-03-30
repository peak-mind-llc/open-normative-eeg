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
8. **Spectral analysis** — PSD (Welch), 11 frequency bands, aperiodic/1/f fitting (specparam), specparam-corrected band power, asymmetry
9. **Connectivity** — dwPLI, coherence, imaginary coherence across 10 hub regions, graph metrics, theta-gamma PAC

## Specparam-Corrected Z-Scores

Traditional QEEG z-scores are computed on raw band power, which conflates two distinct phenomena:

- **Periodic (oscillatory) activity** — actual brain rhythms (alpha peaks, theta, etc.)
- **Aperiodic (1/f) activity** — the broadband background noise floor

A subject could have abnormal z-scores simply because their aperiodic slope differs from the norm, not because their oscillatory activity is abnormal. This package computes z-scores **both ways**:

| Metric | Description | Use case |
|--------|-------------|----------|
| `absolute_power` | Traditional band power (includes 1/f) | Backward-compatible with legacy QEEG |
| `corrected_absolute_power` | Periodic-only power (1/f removed via specparam) | More specific to oscillatory activity |
| `relative_power` | Traditional relative power | Standard QEEG metric |
| `corrected_relative_power` | Periodic-only relative power | Oscillation-specific relative comparison |

The corrected metrics use [specparam](https://specparam-tools.github.io/) (formerly FOOOF) to fit and subtract the aperiodic component in log-power space before computing band power. This isolates oscillatory peaks from the 1/f background, giving clinically more meaningful z-scores.

## Supported Datasets

| Dataset | Subjects | Ages | Channels | Status |
|---------|----------|------|----------|--------|
| LEMON | ~220 | 20–77 | 62 (BrainVision) | Implemented |
| HBN | ~2500 | 5–21 | 128 (EGI) | Implemented |
| MIPDB | ~126 | 6–44 | 128 (EGI) | Implemented |

## Installation

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[datasets,dev]"
```

Requires Python 3.10+. The install pulls in MNE, specparam, python-picard, asrpy, mne-icalabel, mne-connectivity, onnxruntime, and other dependencies.

## Building Normative Databases

The build script processes any supported dataset through the pipeline, checkpoints after each subject (so you can resume if interrupted), and outputs normative distributions as JSON and CSV.

### CLI options

```
python scripts/build_norms.py --help

  data_dir                  Path to dataset (BIDS-like layout)
  --output, -o              Output directory (default: ./norms_output)
  --dataset, -d             Dataset: lemon, hbn, mipdb (default: lemon)
  --condition               eo, ec, or both (default: both)
  --max-subjects N          Limit to N subjects (0 = all)
  --skip-connectivity       Skip connectivity (faster, spectral-only norms)
  --age-bins 20 30 40 ...   Custom age bin edges (default: decade bins)
```

### Output

```
norms_output/
  subjects/          # Per-subject checkpoint JSONs (for resume)
  norms.json         # Normative distributions (machine-readable)
  norms.csv          # Same as above (spreadsheet-friendly)
  subjects.csv       # Per-subject metrics (for rebinning)
  errors.log         # Any processing failures
  run_config.json    # Exact parameters used (reproducibility)
```

---

### LEMON (~220 subjects, ages 20-77, 62-channel BrainVision)

**Reference:** Babayan et al. (2019). A mind-brain-body dataset of MRI, EEG, and cognition. *Scientific Data*, 6, 180308. [doi:10.1038/sdata.2018.308](https://doi.org/10.1038/sdata.2018.308)

#### 1. Download LEMON EEG data

The data is hosted at `https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON/`. The FTP directory contains many subdirectories — here's what's in there and what you actually need:

```
MPI-Leipzig_Mind-Brain-Body-LEMON/
├── Behavioural_Data_MPILMBB_LEMON/          ← demographics file is here
│   ├── META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv  ← NEED THIS
│   ├── Emotion/
│   ├── Personality/
│   ├── Cognitive/
│   └── ... (other behavioral data — not needed)
│
├── EEG_MPILMBB_LEMON/
│   ├── EEG_Raw_BIDS_ID/                     ← raw EEG recordings are here
│   │   ├── sub-010002/RSEEG/                ← NEED THESE
│   │   │   ├── sub-010002_task-rest_EO_eeg.vhdr
│   │   │   ├── sub-010002_task-rest_EO_eeg.vmrk
│   │   │   ├── sub-010002_task-rest_EO_eeg.eeg
│   │   │   ├── sub-010002_task-rest_EC_eeg.vhdr
│   │   │   ├── sub-010002_task-rest_EC_eeg.vmrk
│   │   │   └── sub-010002_task-rest_EC_eeg.eeg
│   │   ├── sub-010004/RSEEG/
│   │   └── ... (~220 subjects)
│   │
│   ├── EEG_Preprocessed_BIDS_ID/            ← preprocessed data (not needed — we run our own pipeline)
│   └── EEG_MPILMBB_LEMON_README.pdf
│
├── MRI_MPILMBB_LEMON/                       ← MRI data (not needed)
├── INDI_retro_LEMON/                         ← retrospective data (not needed)
└── ... (other modalities — not needed)
```

**You only need to download two things:**

1. **EEG recordings** — the entire `EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID/` directory. This is the raw BrainVision data (~220 subjects, each with Eyes Open and Eyes Closed `.vhdr`/`.vmrk`/`.eeg` files). Each subject folder contains a `RSEEG/` subdirectory with the resting-state files.

2. **Demographics file** — the single file `META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv` from inside `Behavioural_Data_MPILMBB_LEMON/`. This CSV contains subject ID, age (as 5-year bins like `20-25`), and gender (`1`=female, `2`=male). **The EEG download does NOT include a `participants.tsv`** — without this META CSV, subjects will have `age=NaN` and won't be assigned to age bins.

You can skip everything else (MRI, preprocessed EEG, personality questionnaires, etc.).

**Alternative demographics source:** If you have the OpenNeuro version ([ds000221](https://openneuro.org/datasets/ds000221)), its `participants.tsv` is also supported (download it from `https://github.com/OpenNeuroDatasets/ds000221/blob/master/participants.tsv`).

#### 2. Organize the data directory

Place the META CSV at the root of your data directory (next to the `sub-*/` folders). **No renaming is needed** — the loader supports both the original `RSEEG/` subdirectory names and the BIDS-standard `eeg/` names.

```bash
# Copy the demographics CSV into the EEG data directory
cp /path/to/Behavioural_Data_MPILMBB_LEMON/META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv /path/to/EEG_Raw_BIDS_ID/
```

Your directory should look like this (works as-is from the FTP download):
```
lemon/
  META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv
  sub-010002/RSEEG/sub-010002.vhdr       ← single-file format (auto-split by markers)
  sub-010002/RSEEG/sub-010002.vmrk
  sub-010002/RSEEG/sub-010002.eeg
  sub-010004/RSEEG/...
  ...
```

The loader handles **both** LEMON file formats automatically:
- **Single-file recordings** (e.g. `sub-010002.vhdr`) — the loader reads the `S210` (Eyes Open) and `S200` (Eyes Closed) markers from the recording and splits the data into separate EO and EC segments.
- **Separate EO/EC files** (e.g. `sub-010002_task-rest_EO_eeg.vhdr`) — detected from the filename.

Both `RSEEG/` and `eeg/` subdirectory names are supported. No renaming needed.

The loader auto-detects the META CSV and parses age (5-year range bins like `20-25`, converted to midpoint `22.5`), sex (`1`=female, `2`=male), and subject IDs (`sub-XXXXXX`).

The 62-channel 10-10 names (T7, T8, P7, P8, etc.) are automatically mapped to the standard 19-channel 10-20 montage by name matching.

#### 3. Build norms

```bash
source .venv/bin/activate

# Fast test: 5 subjects, spectral only
python scripts/build_norms.py /path/to/lemon \
    -o ./test_output \
    --max-subjects 5 \
    --skip-connectivity

# Eyes-open only, full pipeline
python scripts/build_norms.py /path/to/lemon -o ./norms_output --condition eo

# Both conditions, full pipeline
python scripts/build_norms.py /path/to/lemon -o ./norms_output
```

#### 4. QC sweep (recommended before building norms)

Run a quality check across all subjects before the full pipeline:

```bash
# Quick test with 5 subjects
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc --max-subjects 5

# Full sweep, 4 parallel workers
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc -j 4
```

This produces:
- `summary.md` — overview table with ready/review/exclude counts
- `ready.txt` / `excluded.txt` — subject lists for downstream use
- `subjects/*.json` — per-subject QC details (flat channels, railing, artifact %, marker presence, etc.)

The script is resumable — re-run it and it will skip already-completed subjects.

---

### HBN (~2500 subjects, ages 5-21, 128-channel EGI)

**Reference:** Alexander et al. (2017). An open resource for transdiagnostic research in pediatric mental health and learning disorders. *Scientific Data*, 4, 170181. [doi:10.1038/sdata.2017.181](https://doi.org/10.1038/sdata.2017.181)

#### 1. Get access to HBN data

HBN requires a Data Use Agreement:

1. Visit [the HBN site](http://fcon_1000.projects.nitrc.org/indi/cmi_healthy_brain_network/).
2. Register for data access through the LORIS portal.
3. Download the EEG resting-state recordings (`.mff` format, 128-channel EGI HydroCel Geodesic Sensor Net).

#### 2. Organize into BIDS-like layout

The loader expects this structure:

```
hbn/
  participants.tsv              # participant_id, age, sex
  sub-NDARXXXX/eeg/
    sub-NDARXXXX_task-restEO_eeg.mff/
    sub-NDARXXXX_task-restEC_eeg.mff/
  ...
```

You may need to create `participants.tsv` from HBN's phenotypic data files. The TSV should have columns: `participant_id`, `age`, `sex`.

The 128 EGI channels (E1-E128) are automatically mapped to the 19-channel 10-20 montage using spatial nearest-neighbor matching based on electrode positions.

#### 3. Build norms

```bash
# Use pediatric age bins (3-year bins from 5-21)
python scripts/build_norms.py /path/to/hbn -o ./hbn_norms \
    --dataset hbn \
    --age-bins 5 8 11 14 17 22
```

---

### MIPDB (~126 subjects, ages 6-44, 128-channel EGI)

**Reference:** Langer et al. (2017). A resource for assessing information processing in the developing brain using EEG and eye tracking. *Scientific Data*, 4, 170040. [doi:10.1038/sdata.2017.40](https://doi.org/10.1038/sdata.2017.40)

#### 1. Download MIPDB data

1. Visit [the MIPDB site](http://fcon_1000.projects.nitrc.org/indi/cmi_eeg/).
2. Download the EEG resting-state data (`.raw` or `.mff` format, 128-channel EGI).

#### 2. Organize into BIDS-like layout

The loader expects this structure:

```
mipdb/
  participants.tsv              # participant_id, age, sex
  sub-XXXX/eeg/
    sub-XXXX_task-restEO_eeg.raw
    sub-XXXX_task-restEC_eeg.raw
  ...
```

You may need to create `participants.tsv` from MIPDB's demographic data. The 128-channel EGI mapping works the same way as HBN (spatial nearest-neighbor).

#### 3. Build norms

```bash
# Age bins spanning 6-44 range
python scripts/build_norms.py /path/to/mipdb -o ./mipdb_norms \
    --dataset mipdb \
    --age-bins 6 12 18 25 35 45
```

## Visualize Normative Database

Generate an HTML report with topographic head maps, band power heatmaps, coverage tables, and distribution quality flags:

```bash
python scripts/visualize_norms.py norms_output/norms.json -o report.html
```

Open `report.html` in a browser. The report includes:
- **Topographic maps** of mean power per band and age bin (uncorrected and corrected)
- **Corrected vs uncorrected comparison** side-by-side topomaps
- **Band power heatmaps** (channels x bands matrix per age bin)
- **Coverage table** showing sample sizes per age bin, with low-n warnings
- **Distribution quality** flags for non-normality and sparse cells

All images are embedded in the HTML — no external files needed.

## Python API

### Process a single recording

```python
from open_normative.channels import load_and_standardize
from open_normative.pipeline import process_resting

raw = load_and_standardize("path/to/recording.vhdr")
result = process_resting(raw, condition="eo")
print(result.to_nested_dict())
```

### Compare a clinical recording against norms

```python
from open_normative.compare import compare_to_norms
from open_normative.io import read_norms_json

norms = read_norms_json("norms_output/norms.json")
results = compare_to_norms(
    metrics=clinical_result.to_nested_dict(),
    norms=norms,
    age=42,
    condition="eo",
)

for r in results:
    if abs(r.z_score or 0) > 2.0:
        print(f"{r.channel} {r.band} {r.metric}: z={r.z_score:.2f}")

# Compare corrected (specparam) z-scores vs uncorrected
for r in results:
    if r.metric == "corrected_absolute_power" and abs(r.z_score or 0) > 2.0:
        print(f"[corrected] {r.channel} {r.band}: z={r.z_score:.2f}")
```

## Normative Output Format

Each normative cell stores:
- **Parametric stats**: mean, SD (and log-transformed mean/SD for power metrics)
- **Non-parametric stats**: percentiles at 1, 5, 10, 25, 50, 75, 90, 95, 99
- **Quality indicators**: sample size (n), Shapiro-Wilk normality p-value
- **Age bins**: Decade bins by default, configurable
- **Dual metrics**: Both uncorrected and specparam-corrected band power for each cell

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
