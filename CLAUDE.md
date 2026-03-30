# Open Normative EEG — Development Guide

## Project Overview

Extracting the normative EEG processing pipeline from Coherence Workstation (CW) into a standalone open-source package. The pipeline must be parameter-identical to CW. Key goal: compute z-scores both with and without specparam correction (separating periodic oscillatory activity from aperiodic 1/f background).

## Architecture

- `open_normative/` — Core library
  - `parameters.py` — Single canonical `PIPELINE_PARAMS` dict that CW imports directly
  - `pipeline.py` — `process_resting()` orchestrates preprocessing → spectral → connectivity
  - `preprocessing.py` — Filtering, ASR, ICA
  - `spectral.py` — PSD, band power (uncorrected + specparam-corrected), ratios
  - `connectivity.py` — dwPLI, coherence, graph metrics
  - `channels.py` — Channel name normalization, 128ch EGI → 19ch spatial mapping
  - `normative.py` — `build_normative()` creates age-binned distributions
  - `compare.py` — Z-score comparison against norms
  - `datasets/` — Dataset loaders (LEMON, HBN, MIPDB)
- `scripts/` — CLI tools for building norms, QC, visualization
- `tests/` — pytest tests

## Key Technical Decisions

- **19-channel 10-20 montage**: Fp1, Fp2, F7, F3, Fz, F4, F8, T3, C3, Cz, C4, T4, T5, P3, Pz, P4, T6, O1, O2
- **Dual z-scores**: Both uncorrected (raw band power) and corrected (periodic-only after aperiodic removal via specparam/FOOOF)
- **Log-space subtraction**: `periodic_log10 = log10(full_psd) - log10(aperiodic)` for specparam correction
- **Log-transformation**: Right-skewed metrics (absolute_power, corrected_absolute_power, band ratios) — z-scores computed in log-space
- **Spatial nearest-neighbor mapping**: For 128ch EGI → 19ch using MNE's GSN-HydroCel-128 montage positions
- **NormCell dataclass**: Stores per-cell normative statistics (bin, condition, channel, band, metric, n, mean, sd, log_mean, log_sd, percentiles, normality_p)

## Dataset Status

### LEMON (~220 subjects, ages 20-77, 62ch BrainVision)
- **Loader**: Fully working. Handles RSEEG/ and eeg/ dirs, single-file S210/S200 marker splitting, .vhdr reference patching, merged demographics (META CSV + participants.tsv)
- **QC script**: `scripts/lemon_qc.py` — checks integrity, channels, signal, markers, produces ready/excluded lists
- **Known quirks**: GWDG FTP download renames .vhdr but not .vmrk/.eeg; DataFile= references inside .vhdr point to original filenames; META CSV uses original IDs, directories may use BIDS-remapped IDs; `scripts/build_participants_tsv.py` generates a mapping file

### HBN (~3000 subjects, ages 5-21, 128ch EGI)
- **Loader**: `datasets/hbn.py` implemented (reads .mff/.raw, EGI montage, spatial 19ch mapping)
- **Download**: `scripts/hbn_download.py` — S3 download manager with release filtering
- **QC script**: NOT YET IMPLEMENTED — needs:
  - EGI 128→10-20 mapping with spatial distances (save as reusable JSON)
  - Pediatric artifact thresholds (300 µV vs 200 µV for adults)
  - CBCL phenotypic filtering (HBN is community-referred, NOT a healthy sample)
  - Flag subjects with CBCL Total Problems T-score > 60 (clinical range)
  - Report normative-eligible counts at thresholds 60, 63, 70
  - Age × sex distribution of clean subjects

### MIPDB (~126 subjects, ages 6-44, 128ch EGI)
- **Loader**: `datasets/mipdb.py` implemented (same pattern as HBN)
- **QC/Download**: Not yet implemented

## Scripts Workflow

```bash
# 1. QC sweep (produces ready.txt / excluded.txt)
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc -j 4

# 2. Build norms using only QC-passed subjects
python scripts/build_norms.py /path/to/lemon -o ./norms --qc-dir ./lemon_qc

# 3. Visualize results
python scripts/visualize_norms.py ./norms/norms.json -o ./report.html
```

## Known Issues

- **asrpy + numpy 2.x incompatibility**: `TypeError: only 0-dimensional arrays can be converted to Python scalars` in asrpy/asr_utils.py. Upstream issue, not our bug. Causes test_pipeline.py and test_preprocessing.py to fail.
- **specparam**: Only rc versions available on PyPI (2.0.0rc*). No version pin in pyproject.toml.
- **LEMON FTP**: Very slow (~300 KB/s). Use existing downloads when possible.

## Development Branch

All work on branch: `claude/extract-eeg-pipeline-18WMH`

## Testing

```bash
# Run all passing tests (skip asrpy-dependent ones)
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py

# All tests (2 will fail due to asrpy bug)
python -m pytest tests/
```
