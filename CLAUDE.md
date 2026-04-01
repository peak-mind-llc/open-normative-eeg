# Open Normative EEG — Claude Code Guide

## Architecture

- `open_normative/` — Core library (parameters, pipeline, preprocessing, spectral, connectivity, channels, normative, compare, datasets/)
- `scripts/` — CLI tools (build_norms, lemon_qc, hbn_download, visualize_norms, build_participants_tsv)
- `tests/` — pytest tests

## Testing

```bash
# Run passing tests (skip asrpy-dependent ones that fail due to upstream numpy 2.x bug)
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py
```

## Key Conventions

- 19-channel 10-20 montage: Fp1 Fp2 F7 F3 Fz F4 F8 T3 C3 Cz C4 T4 T5 P3 Pz P4 T6 O1 O2
- Dual z-scores: uncorrected (raw band power) + corrected (periodic-only via specparam)
- Log-space subtraction for specparam: `periodic_log10 = log10(full_psd) - log10(aperiodic)`
- `PIPELINE_PARAMS` in parameters.py is the single canonical config dict
- Scripts use argparse, pathlib, checkpoint/resume pattern, logging to stderr
