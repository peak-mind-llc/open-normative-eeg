# Normative EEG Project Status

*Last updated: 2026-04-04*

## Overview

Extracting the normative EEG processing pipeline from Coherence Workstation (CW) into a standalone open-source package. The pipeline computes z-scores both with and without specparam correction (separating periodic oscillatory activity from aperiodic 1/f background). The pipeline must be parameter-identical to CW — `PIPELINE_PARAMS` in `parameters.py` is the single canonical config dict that CW imports directly.

## Core Library Status

| Module | Status | Notes |
|--------|--------|-------|
| `parameters.py` | ✅ Done | Single `PIPELINE_PARAMS` dict, CW-importable. 19ch + 37ch montages. |
| `pipeline.py` | ✅ Done | `process_resting()` orchestrates full pipeline incl. source |
| `preprocessing.py` | ✅ Done | Filtering, ASR, ICA (blocked by asrpy numpy 2.x bug in tests) |
| `spectral.py` | ✅ Done | PSD, band power (uncorrected + specparam-corrected), ratios |
| `connectivity.py` | ✅ Done | dwPLI, coherence, graph metrics |
| `channels.py` | ✅ Done | Name normalization, 19/37ch support, 128ch EGI spatial mapping |
| `source.py` | ✅ Done | sLORETA source power + DICS beamformer source connectivity |
| `normative.py` | ✅ Done | `build_normative()` creates age-binned NormCell distributions |
| `compare.py` | ✅ Done | Z-score comparison against norms, auto-detects 19/37ch |
| `datasets/lemon.py` | ✅ Done | LEMON loader with all quirks handled, `iter_subject_files()` |
| `datasets/dortmund.py` | ✅ Done | Dortmund Vital Study loader, `iter_subject_files()` |
| `datasets/hbn.py` | ✅ Done | HBN loader (128ch EGI, .mff/.raw) |
| `datasets/mipdb.py` | ✅ Done | MIPDB loader (same pattern as HBN) |

## Scripts Status

| Script | Status | Purpose |
|--------|--------|---------|
| `build_norms.py` | ✅ Done | Build norms. `--channels 19\|37`, `-j N`, `--source`, `--subject-range` |
| `distribute.py` | ✅ Done | Distributed processing across machines via SSH. `setup`, `run`, `status`, `merge` |
| `validate_source.py` | ✅ Done | 7 checks for sLORETA/DICS source metrics |
| `validate_internal.py` | ✅ Done | Split-half reliability, Berger effect, IAF trend. Auto-detects 19/37ch |
| `validate_literature.py` | ✅ Done | 8 literature reference checks. Auto-detects 19/37ch |
| `validate_cross_dataset.py` | ✅ Done | Cross-dataset agreement (pairwise) |
| `lemon_qc.py` | ✅ Done | LEMON QC sweep (integrity, channels, signal, markers) |
| `build_participants_tsv.py` | ✅ Done | Map BIDS-remapped LEMON IDs to META CSV demographics |
| `visualize_norms.py` | ✅ Done | HTML report with topographic head maps |
| `hbn_download.py` | ✅ Done | S3 download manager with release filtering |
| `hbn_qc.py` | ❌ Not started | HBN-specific QC (see below) |

## Dataset Status

### LEMON (~215 subjects, ages 20-78, 62ch BrainVision)

**Status: Full 37ch + source normative build complete (2026-04-03)**

- **211 subject records** (107 EO, 104 EC), 103,580 normative cells, 71 metric types
- **37 sensor channels** + 264 source/hub/graph/network synthetic channels
- **sLORETA source power** across ~40 Brodmann areas per band
- **DICS source connectivity** across 18 Desikan-Killiany ROIs, 7 networks
- **Sensor connectivity**: dwPLI, coherence, imaginary coherence, graph metrics, PAC
- Processed distributed across 3 machines (dev-mac-1, dev-linux-1, dev-linux-2) via NFS

**Validation results (37ch + source):**
- Source validation: 7/7 PASS
- Literature validation: 8/8 PASS
- Internal: EC > EO alpha 185/185 (100%), split-half r=0.81 (below 0.90, expected with LEMON-only sample)

**Output:** `/Volumes/dev/Data/EEG/norms_output/merged/` (Mac) = `/mnt/dev/Data/EEG/norms_output/merged/` (Linux)

**Known quirks:**
- GWDG FTP is very slow (~300 KB/s)
- META CSV uses original IDs (sub-010002), directories may use BIDS-remapped IDs (sub-032301)
- Some subjects have no demographics match (6 out of 217 in one download)
- asrpy numpy 2.x bug causes ~10-20% of subjects to fail on ICA (FloatingPointError)
- dev-linux-1 cannot run multiprocessing for source (BrokenProcessPool with Python 3.12 fork)

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

- **Dual montage support**: 19-channel 10-20 and 37-channel 10-10 (`--channels 19|37`)
- **37ch set**: Matched to pre-computed forward model from Coherence Workstation — AF3 AF4 FC3 FC1 FC2 FC4 FT7 FT8 CP3 CP1 CP2 CP4 TP7 TP8 PO3 PO4 P1 P2
- **Source localization**: sLORETA via pre-computed transformation matrices (no fsaverage runtime), DICS beamformer with pre-computed forward models (avoids FreeSurfer EULA)
- **18 DK ROIs**: DLPFC, mPFC, ACC, INS, IFG, STG, IPL, PCUN, PCC, SMC, OCC (L/R) across 7 networks (Executive, DMN, Salience, Language, Frontoparietal, Sensorimotor, Visual)
- **Dual z-scores**: Both uncorrected (raw band power) and corrected (periodic-only after aperiodic removal via specparam/FOOOF)
- **Log-space subtraction**: `periodic_log10 = log10(full_psd) - log10(aperiodic)` for specparam correction
- **Log-transformation**: Right-skewed metrics (absolute_power, corrected_absolute_power, band ratios) — z-scores computed in log-space
- **Spatial nearest-neighbor mapping**: For 128ch EGI → 19/37ch using MNE's GSN-HydroCel-128 montage positions
- **NormCell dataclass**: Stores per-cell normative statistics (bin, condition, channel, band, metric, n, mean, sd, log_mean, log_sd, percentiles, normality_p)
- **Distributed processing**: SSH-based orchestration with YAML config, checkpoint/resume, NFS share for data and results

## Known Issues

- **asrpy + numpy 2.x**: `TypeError: only 0-dimensional arrays can be converted to Python scalars` in asrpy/asr_utils.py. Upstream issue. Causes test_pipeline.py and test_preprocessing.py to fail. Not our bug.
- **specparam**: Only rc versions available on PyPI (2.0.0rc*). No version pin in pyproject.toml.
- **LEMON FTP**: Very slow (~300 KB/s). Use existing downloads when possible.

## Workflow

```bash
# 1. QC sweep (produces ready.txt / excluded.txt)
python scripts/lemon_qc.py /path/to/lemon -o ./lemon_qc -j 4

# 2. Build norms (local, 37ch + source)
python scripts/build_norms.py /path/to/lemon -o ./norms \
    --channels 37 --source -j 2 --qc-dir ./lemon_qc

# 3. Or: distributed across machines
python scripts/distribute.py -c distribute.yaml setup   # one-time env setup
python scripts/distribute.py -c distribute.yaml run      # dispatch jobs
python scripts/distribute.py -c distribute.yaml status   # monitor
python scripts/distribute.py -c distribute.yaml merge    # combine results

# 4. Validate
python scripts/validate_source.py ./norms_output/merged
python scripts/validate_literature.py ./norms_output/merged/subjects
python scripts/validate_internal.py ./norms_output/merged/subjects

# 5. Visualize
python scripts/visualize_norms.py ./norms/norms.json -o ./report.html
```

## Infrastructure

- **NFS share**: `/Volumes/dev` (Mac) = `/mnt/dev` (Linux)
- **Data**: `/Volumes/dev/Data/EEG/EEG/{LEMON,Dortmund}/`
- **Code (NFS)**: `/Volumes/dev/git/open-normative-eeg/open-normative-eeg` (branch: `feature/source-analysis`)
- **Venvs**: `~/.eeg-normative-env` on each machine (local, not NFS)
- **Output**: `/Volumes/dev/Data/EEG/norms_output/`
- **Machines**: dev-mac-1 (M4, 24GB, -j 2), dev-linux-1 (29GB, -j 1 for source), dev-linux-2 (-j 3)

## Development Branch

Active branch: `feature/source-analysis`

## Testing

```bash
# Run passing tests (skip asrpy-dependent ones)
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py

# All tests (2 will fail due to asrpy bug)
python -m pytest tests/
```
