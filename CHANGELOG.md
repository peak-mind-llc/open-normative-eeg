# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are [semver](https://semver.org/).

## [Unreleased]

### Added
- New `npz/scalp_node_strength.npz` category. Per-electrode node-strength
  cells (formerly mixed into `scalp_power.npz` under metric names
  `dwpli_node_strength` / `coh_node_strength`) now live in their own file
  with metric names `dwpli` / `coh`, matching `scalp_connectivity.npz`
  convention.
- `npz/metadata.json` publishes `roi_order` and `roi_labels` when source
  ROI connectivity cells are present, and `ba_order` when BA connectivity
  cells are present. Consumers should construct `_src_conn_{A}_{B}` keys
  with A preceding B in `roi_order` rather than calling `sorted()`.

### Changed
- `scalp_power.npz` no longer contains node-strength rows (moved to
  `scalp_node_strength.npz`). Consumers reading `dwpli_node_strength` /
  `coh_node_strength` from `scalp_power.npz` will see no such metric;
  switch the lookup to `scalp_node_strength.npz` with metric `dwpli` /
  `coh`.

## [0.3.0] - 2026-05-29

### Added
- `NormCell.sex` field (legal values: "pooled", "F", "M") for sex-stratified
  comparisons. `build_normative()` now fans each subject into a pooled cell
  plus an own-sex cell when sex is F or M.
- `compare_to_norms()` and `compare_and_report()` accept an optional `sex=`
  kwarg with per-metric pooled fallback. Results carry `resolved_sex`; the
  report metadata exposes `resolved_sex_summary`.
- New `npz/psd_spectrum.npz` slab category — frequency-resolved normative
  spectrum, sex-stratified (axis at index 2). Registered in `metadata.json`
  with `"layout": "slab"`.
- `PROVENANCE.md` is now generated at build time with a cohort sex breakdown
  table and PSD freq-resolved category note.

### Changed
- NPZ bundle `format_version` bumped from 2 to 3. Every category gains a
  `sex` parallel array. Older `open_normative` versions reading a v3 bundle
  will silently triple-count cells — consumers must upgrade.
- Legacy root-level `norms_psd.npz` is still written for one bundle cycle
  as a back-compat shim; will be removed in the next regeneration.

## [0.2.0] - 2026-05-26
### Added
- Per-frequency percentiles in `norms_psd.npz` (`psd_format_version: 2`).
- Release process: `scripts/release.py` + tag-triggered CI publishing versioned,
  hash-verified norm bundles to `s3://<bucket>/releases/<version>/` (+ `latest.json`).
- Unit-sanity guard in the norms build.
### Fixed
- SRM EDF unit scaling (`units="uV"`).
