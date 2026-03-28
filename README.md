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
