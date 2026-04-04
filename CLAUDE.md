# Open Normative EEG — Claude Code Guide

## Architecture

- `open_normative/` — Core library (parameters, pipeline, preprocessing, spectral, connectivity, channels, normative, compare, source, datasets/)
- `open_normative/data/` — Pre-computed source localization assets (TMs, forward models, ROI labels, Brodmann table)
- `scripts/` — CLI tools (build_norms, distribute, lemon_qc, validate_source, validate_internal, validate_literature, visualize_norms, etc.)
- `tests/` — pytest tests

## Testing

```bash
# Run passing tests (skip asrpy-dependent ones that fail due to upstream numpy 2.x bug)
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py
```

## Key Conventions

- Supports both 19-channel 10-20 and 37-channel 10-10 montages (`--channels 19|37`)
- 37ch set: 19 standard + AF3 AF4 FC3 FC1 FC2 FC4 FT7 FT8 CP3 CP1 CP2 CP4 TP7 TP8 PO3 PO4 P1 P2 (matched to pre-computed forward model)
- Dual z-scores: uncorrected (raw band power) + corrected (periodic-only via specparam)
- Log-space subtraction for specparam: `periodic_log10 = log10(full_psd) - log10(aperiodic)`
- `PIPELINE_PARAMS` in parameters.py is the single canonical config dict
- Scripts use argparse, pathlib, checkpoint/resume pattern, logging to stderr

## Source Localization

- sLORETA source power via pre-computed transformation matrices (no fsaverage runtime dependency)
- DICS beamformer source connectivity with 18 Desikan-Killiany ROIs across 7 networks
- Pre-computed forward assets from Coherence Workstation (avoids FreeSurfer EULA issues)
- Enable with `--source` flag in build_norms.py

## Distributed Processing

- `scripts/distribute.py` — orchestrates build_norms.py across multiple machines via SSH
- Config in `distribute.yaml`: machine names, SSH hosts, NFS paths, worker counts
- Commands: `setup` (create venvs), `run` (dispatch jobs), `status` (check progress), `merge` (combine results)
- NFS share: `/Volumes/dev` (Mac) = `/mnt/dev` (Linux), data at `Data/EEG/EEG/`
- Venvs in home dirs (`~/.eeg-normative-env`), not on NFS (speed)
- For source mode: use `-j 1` on dev-linux-1 (fork issues), `-j 3` on dev-linux-2, `-j 2` on Mac Mini

## Parallelism Notes

- `-j/--jobs` flag for local multiprocessing via ProcessPoolExecutor
- Workers wrap all processing in try/except BaseException to prevent FloatingPointError from killing the pool
- Each worker loads raw data independently (no pickle of Raw objects)
- `iter_subject_files()` on loaders provides lightweight file records for parallel dispatch
