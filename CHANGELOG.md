# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions are [semver](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-05-26
### Added
- Per-frequency percentiles in `norms_psd.npz` (`psd_format_version: 2`).
- Release process: `scripts/release.py` + tag-triggered CI publishing versioned,
  hash-verified norm bundles to `s3://<bucket>/releases/<version>/` (+ `latest.json`).
- Unit-sanity guard in the norms build.
### Fixed
- SRM EDF unit scaling (`units="uV"`).
