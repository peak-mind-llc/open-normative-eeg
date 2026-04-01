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
9. **GSF correction** — Global Scale Factor removes non-neural variance (skull thickness, amplifier gain)
10. **IAF detection** — Individual Alpha Frequency via peak detection and center-of-gravity (Corcoran et al. 2018)
11. **Connectivity** — dwPLI, coherence, imaginary coherence across 10 hub regions, graph metrics, theta-gamma PAC

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

## Statistical Transparency

Most normative EEG databases are black boxes. This one shows its work.

| Feature | What it does | Why it matters |
|---------|-------------|----------------|
| **FDR correction** | Benjamini-Hochberg across all tests | 19ch x 11 bands = 209 tests. At p=0.05, ~10 false positives expected. FDR tells you which findings are real. |
| **SE(z)** | Standard error of each z-score | A z=2.3 from N=200 is precise. A z=2.3 from N=8 is not. SE quantifies this. |
| **Prediction intervals** | Where a *new* healthy person would fall | CI tells you where the population mean is. PI tells you "is this value normal?" — the actual clinical question. |
| **Cohen's d + severity labels** | Effect size with calibrated language | "Moderately atypical" is more useful than "z=1.7". Six tiers from "Within typical limits" to "Extremely atypical". |
| **Global pattern detection** | Flags when 60%+ channels deviate same direction | 15 elevated channels is one global pattern (medication? arousal?), not 15 independent findings. |
| **Spatial cluster detection** | BFS on channel adjacency graph | Finds localized clusters like "elevated Theta at T3-T5-O1 (left temporal-occipital)". |
| **Metric disagreements** | Compares total vs periodic-only power | When they disagree, the deviation is in the 1/f slope, not oscillatory activity. Clinically different. |
| **GSF correction** | Global Scale Factor removes non-neural variance | Skull thickness and amplifier gain account for ~42% of power variance. Critical for multi-dataset norms. |
| **IAF detection** | Individual Alpha Frequency (peak + center-of-gravity) | Fixed 8-13 Hz boundaries mischaracterize anyone with alpha at 8 Hz. IAF flags when this is happening. |

## Supported Datasets

| Dataset | Subjects | Ages | Channels | Format | License | Status |
|---------|----------|------|----------|--------|---------|--------|
| LEMON | ~220 | 20–77 | 62 (BrainVision) | .vhdr | CC0 (public domain) | Implemented |
| Dortmund | ~486 | 20–70 | 64 (BrainProducts) | .edf | CC BY 4.0 | Implemented |
| HBN | ~2500 | 5–21 | 128 (EGI) | .mff | CC-BY-SA 4.0 | Loader implemented, not yet run |
| MIPDB | ~126 | 6–44 | 128 (EGI) | .raw | CC-BY-NC-SA | Loader implemented, not yet run |

Combined coverage: ages 5 through 77 with no gaps. ~3,300+ subjects from four independent datasets.

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
  --dataset, -d             Dataset: lemon, dortmund, hbn, mipdb (default: lemon)
  --condition               eo, ec, or both (default: both)
  --max-subjects N          Limit to N subjects (0 = all)
  --skip-connectivity       Skip connectivity (faster, spectral-only norms)
  --age-bins 20 30 40 ...   Custom age bin edges (default: decade bins)
  --qc-dir PATH             QC output directory — only process QC-passed subjects
  --save-psd                Save aggregated PSD curves (norms_psd.npz)
  --merge                   Merge mode: combine existing checkpoint dirs
  --merge-dir PATH          (with --merge) checkpoint directory to include (repeatable)
```

Line frequency (50/60 Hz) is auto-detected from the dataset loader — no manual flag needed.

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

#### 3. QC sweep (recommended before building norms)

Run a quality check across all subjects before the full pipeline. This catches
data integrity issues (corrupt files, wrong sampling rate, missing channels,
excessive artifact, missing condition markers) so you don't waste time
processing bad data.

```bash
source .venv/bin/activate

# Quick test with 5 subjects
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc --max-subjects 5

# Full sweep, 4 parallel workers
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc -j 4
```

This produces:
- `summary.md` — overview table with ready/review/exclude verdicts and reasons
- `ready.txt` / `excluded.txt` — subject lists for downstream use
- `subjects/*.json` — per-subject QC details (flat channels, railing, artifact %, marker presence, etc.)

**What it checks:**

| Category | Checks |
|----------|--------|
| Integrity | Sampling rate (2500 Hz), channel count (62), duration (3-20 min) |
| Channels | Missing/unexpected names, flat (var < 0.1 µV), railed (>500 µV), 50 Hz line noise |
| Signal | Amplitude distribution, artifact % (>200 µV), DC offset |
| Markers | S210 (EO) / S200 (EC) presence and duration (>1 min each) |
| Reference | FCz absent (was online reference) |

The script is resumable — re-run it and it will skip already-completed subjects.

#### 4. Build norms

Use `--qc-dir` to only process QC-passed subjects:

```bash
# Build norms using only QC-passed subjects (recommended)
python scripts/build_norms.py /path/to/lemon \
    -o ./norms_output \
    --qc-dir ./lemon_qc

# Quick test: 5 subjects, spectral only, with QC filter
python scripts/build_norms.py /path/to/lemon \
    -o ./test_output \
    --max-subjects 5 \
    --skip-connectivity \
    --qc-dir ./lemon_qc

# Without QC filter (processes all subjects)
python scripts/build_norms.py /path/to/lemon -o ./norms_output

# Eyes-open only
python scripts/build_norms.py /path/to/lemon -o ./norms_output --condition eo
```

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

### Dortmund Vital Study (~486 subjects, ages 20-70, 64-channel BrainProducts EDF)

**Reference:** Getzmann, S., Gajewski, P.D., Schneider, D. & Wascher, E. (2024). Resting-state EEG data before and after cognitive activity across the adult lifespan and a 5-year follow-up. *Scientific Data*, 11:988. [doi:10.1038/s41597-024-03814-8](https://doi.org/10.1038/s41597-024-03814-8)

**License:** CC BY 4.0 (open, commercial OK, attribution required)

#### 1. Download Dortmund data

```bash
# OpenNeuro CLI
pip install openneuro-py
openneuro download --dataset ds005385 ~/datasets/dortmund/

# Or via AWS S3 (no credentials needed)
aws s3 sync s3://openneuro.org/ds005385 ~/datasets/dortmund/ --no-sign-request
```

#### 2. QC sweep

```bash
python scripts/normative/dortmund_qc.py ~/datasets/dortmund/ -o ./dortmund_qc -w 4
```

**Important:** This is a European dataset. The loader automatically applies 50 Hz notch filtering (not 60 Hz). The QC script checks for 50 Hz line noise.

The Dortmund study recorded EEG in four blocks: pre-task EO, pre-task EC, [2 hours cognitive tasks], post-task EO, post-task EC. Only **pre-task** data is used for normative purposes. Post-task data is contaminated by cognitive fatigue.

#### 3. Build norms

```bash
python scripts/build_norms.py ~/datasets/dortmund/ \
    -o ./dortmund_norms \
    --dataset dortmund \
    --qc-dir ./dortmund_qc \
    --save-psd
```

---

### Merging Multiple Datasets

Combine normative data from multiple datasets into a single database. Each dataset is processed independently (preserving checkpoint/resume), then merged:

```bash
# Step 1: Process each dataset separately
python scripts/build_norms.py ~/datasets/lemon/ -o ./norms_lemon --dataset lemon --qc-dir ./lemon_qc --save-psd
python scripts/build_norms.py ~/datasets/dortmund/ -o ./norms_dortmund --dataset dortmund --qc-dir ./dortmund_qc --save-psd

# Step 2: Merge
python scripts/build_norms.py --merge \
    --merge-dir ./norms_lemon/subjects \
    --merge-dir ./norms_dortmund/subjects \
    --output ./norms_combined
```

The merged database recomputes all normative statistics (mean, SD, percentiles, CI, PI) from the combined subject pool. GSF correction normalizes amplifier gain differences between datasets.

---

## Compare a Recording Against Norms

Process a single clinical EEG file and compare it against the normative database:

```bash
# Quick comparison (spectral only, text summary)
python scripts/compare_recording.py recording.edf norms_combined/norms.json \
    --age 35 --condition eo --skip-connectivity

# Full comparison with JSON report
python scripts/compare_recording.py recording.edf norms_combined/norms.json \
    --age 35 --condition eo --output report.json

# European recording (50 Hz line noise)
python scripts/compare_recording.py recording.edf norms.json \
    --age 42 --condition ec --line-freq 50
```

Supports `.edf`, `.vhdr` (BrainVision), `.set` (EEGLAB), `.mff` (EGI). Any channel count is standardized to 19-channel 10-20 automatically.

The text summary includes:
- FDR-corrected significant findings with severity labels
- Global pattern alerts (non-focal deviations)
- Metric disagreements (aperiodic vs oscillatory)
- Spatial clusters of adjacent deviant channels
- SE(z) precision for each z-score
- Prediction interval status (is the value within the normal range?)

---

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
from open_normative.compare import compare_and_report
from open_normative.io import read_norms_json

norms = read_norms_json("norms_output/norms.json")

# Full comparison report with statistical transparency
report = compare_and_report(
    metrics=clinical_result.to_nested_dict(),
    norms=norms,
    age=42,
    condition="eo",
)

# Text summary with FDR counts, patterns, severity labels
print(report.summary_text())

# JSON for frontend consumption
import json
json.dump(report.to_dict(), open("report.json", "w"), indent=2)

# Programmatic access
for er in report.results:
    if er.base.fdr_significant:
        print(
            f"{er.base.channel} {er.base.band} {er.base.metric}: "
            f"z={er.base.z_score:+.2f} ± {er.se_z:.2f} (SE), "
            f"{er.severity_label}, Cohen's d={er.cohen_d_label}"
        )

# Pattern-level insights
for gp in report.global_patterns:
    print(gp["interpretation"])
for md in report.metric_disagreements:
    print(md["interpretation"])
```

## Normative Output Format

Each normative cell stores:
- **Parametric stats**: mean, SD (and log-transformed mean/SD for power metrics)
- **Non-parametric stats**: percentiles at 1, 5, 10, 25, 50, 75, 90, 95, 99
- **Confidence interval**: 95% CI for the population mean
- **Prediction interval**: 95% PI for where a new individual would fall
- **Quality indicators**: sample size (n), Shapiro-Wilk normality p-value
- **Age bins**: Decade bins by default, configurable
- **Dual metrics**: Both uncorrected and specparam-corrected band power
- **GSF-corrected power**: Global Scale Factor normalized band power
- **IAF**: Individual Alpha Frequency (peak and center-of-gravity) per channel and global
- **Connectivity norms**: dwPLI, coherence, graph metrics, PAC
- **Asymmetry norms**: Hemispheric laterality indices for homologous pairs

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
