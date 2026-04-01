# Normative EEG Project Status

*Last updated: 2026-03-30*

## Overview

Extracting the normative EEG processing pipeline from Coherence Workstation (CW) into a standalone open-source package. The pipeline computes z-scores both with and without specparam correction (separating periodic oscillatory activity from aperiodic 1/f background). The pipeline must be parameter-identical to CW — `PIPELINE_PARAMS` in `parameters.py` is the single canonical config dict that CW imports directly.

## Core Library Status

| Module | Status | Notes |
|--------|--------|-------|
| `parameters.py` | ✅ Done | Single `PIPELINE_PARAMS` dict, CW-importable |
| `pipeline.py` | ✅ Done | `process_resting()` orchestrates full pipeline |
| `preprocessing.py` | ✅ Done | Filtering, ASR, ICA (blocked by asrpy numpy 2.x bug in tests) |
| `spectral.py` | ✅ Done | PSD, band power (uncorrected + specparam-corrected), ratios |
| `connectivity.py` | ✅ Done | dwPLI, coherence, graph metrics |
| `channels.py` | ✅ Done | Name normalization, 128ch EGI → 19ch spatial mapping |
| `normative.py` | ✅ Done | `build_normative()` creates age-binned NormCell distributions |
| `compare.py` | ✅ Done | Z-score comparison against norms |
| `datasets/lemon.py` | ✅ Done | LEMON loader with all quirks handled |
| `datasets/hbn.py` | ✅ Done | HBN loader (128ch EGI, .mff/.raw) |
| `datasets/mipdb.py` | ✅ Done | MIPDB loader (same pattern as HBN) |

## Scripts Status

| Script | Status | Purpose |
|--------|--------|---------|
| `build_norms.py` | ✅ Done | Build normative distributions, supports `--qc-dir` filtering |
| `lemon_qc.py` | ✅ Done | LEMON QC sweep (integrity, channels, signal, markers) |
| `build_participants_tsv.py` | ✅ Done | Map BIDS-remapped LEMON IDs to META CSV demographics |
| `visualize_norms.py` | ✅ Done | HTML report with topographic head maps |
| `hbn_download.py` | ✅ Done | S3 download manager with release filtering |
| `hbn_qc.py` | ❌ Not started | HBN-specific QC (see below) |

## Dataset Status

### LEMON (~220 subjects, ages 20-77, 62ch BrainVision)

**Status: Ready to build norms**

- Loader handles all known GWDG download quirks:
  - Both `RSEEG/` and `eeg/` subdirectory names
  - Single-file recordings split by S210 (EO) / S200 (EC) markers
  - `.vhdr` files with mismatched internal DataFile/MarkerFile references (BIDS renaming patches only the .vhdr, not .vmrk/.eeg)
  - Merged demographics from META CSV + participants.tsv (both loaded, merged)
- `build_participants_tsv.py` generates a participants.tsv when directory IDs don't match META CSV IDs (extracts original ID from .vhdr DataFile= reference)
- QC script produces ready/excluded lists consumed by `build_norms.py --qc-dir`
- Successfully tested: 5 subjects processed, 1976 normative cells, both EO/EC, all 19 channels, both corrected and uncorrected metrics

**Known quirks:**
- GWDG FTP is very slow (~300 KB/s)
- META CSV uses original IDs (sub-010002), directories may use BIDS-remapped IDs (sub-032301)
- Some subjects have no demographics match (6 out of 217 in one download)

### HBN (~3000 subjects, ages 5-21, 128ch EGI)

**Status: Download manager done, QC script needed**

- Loader implemented: reads .mff/.raw, sets EGI montage, spatial 19ch mapping
- S3 download manager supports release filtering (1-11), resume, dry-run, phenotypic data
- S3 bucket: `s3://fcp-indi/data/Projects/HBN/BIDS_EEG/` (no auth required)

**QC script still needed — requirements:**
- EGI 128→10-20 mapping with spatial distances (save as reusable JSON)
- Pediatric artifact thresholds (300 µV vs 200 µV for adults)
- CBCL phenotypic filtering — **this is critical**: HBN is community-referred, NOT a healthy sample. Most participants have psychiatric concerns (ADHD, anxiety, depression). Without filtering, the "normative" database includes clinical subjects.
- Flag subjects with CBCL Total Problems T-score > 60 (clinical range)
- Report normative-eligible counts at thresholds 60, 63, 70
- Age × sex distribution of clean vs filtered subjects
- Identify which paradigm files exist per subject (resting, oddball, flanker — not all completed all tasks)
- Reference channel: Cz was reference (should be flat/absent)

### MIPDB (~126 subjects, ages 6-44, 128ch EGI)

**Status: Loader done, download/QC not started**

- Same EGI 128ch pattern as HBN
- Smaller dataset, useful for validation

## Key Technical Decisions

- **19-channel 10-20 montage**: Fp1, Fp2, F7, F3, Fz, F4, F8, T3, C3, Cz, C4, T4, T5, P3, Pz, P4, T6, O1, O2
- **Dual z-scores**: Both uncorrected (raw band power) and corrected (periodic-only after aperiodic removal via specparam/FOOOF)
- **Log-space subtraction**: `periodic_log10 = log10(full_psd) - log10(aperiodic)` for specparam correction
- **Log-transformation**: Right-skewed metrics (absolute_power, corrected_absolute_power, band ratios) — z-scores computed in log-space
- **Spatial nearest-neighbor mapping**: For 128ch EGI → 19ch using MNE's GSN-HydroCel-128 montage positions
- **NormCell dataclass**: Stores per-cell normative statistics (bin, condition, channel, band, metric, n, mean, sd, log_mean, log_sd, percentiles, normality_p)

## Known Issues

- **asrpy + numpy 2.x**: `TypeError: only 0-dimensional arrays can be converted to Python scalars` in asrpy/asr_utils.py. Upstream issue. Causes test_pipeline.py and test_preprocessing.py to fail. Not our bug.
- **specparam**: Only rc versions available on PyPI (2.0.0rc*). No version pin in pyproject.toml.
- **LEMON FTP**: Very slow (~300 KB/s). Use existing downloads when possible.

## Workflow

```bash
# 1. QC sweep (produces ready.txt / excluded.txt)
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc -j 4

# 2. Build norms using only QC-passed subjects
python scripts/build_norms.py /path/to/lemon -o ./norms --qc-dir ./lemon_qc

# 3. Visualize results
python scripts/visualize_norms.py ./norms/norms.json -o ./report.html
```

## Development Branch

All work on branch: `claude/extract-eeg-pipeline-18WMH`

## Testing

```bash
# Run passing tests (skip asrpy-dependent ones)
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py

# All tests (2 will fail due to asrpy bug)
python -m pytest tests/
```
