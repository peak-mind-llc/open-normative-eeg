#!/usr/bin/env python3
"""Compare a single EEG recording against a normative database.

Loads any EEG file (.edf, .vhdr, .set, .mff), standardizes to
19 channels, runs the full processing pipeline, and compares
against pre-built normative distributions. Outputs a clinical
comparison report with FDR-corrected findings, severity labels,
pattern detection, and full statistical transparency.

Usage:
    # Quick comparison (spectral only, text summary to stdout)
    python scripts/compare_recording.py recording.edf norms.json \
        --age 35 --condition eo --skip-connectivity

    # Full comparison with JSON report output
    python scripts/compare_recording.py recording.edf norms.json \
        --age 35 --condition eo --output report.json

    # European recording (50 Hz line noise)
    python scripts/compare_recording.py recording.edf norms.json \
        --age 42 --condition ec --line-freq 50

    # BrainVision format
    python scripts/compare_recording.py recording.vhdr norms.json \
        --age 28 --condition eo
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from pathlib import Path

import mne

from open_normative.channels import pick_standard_19
from open_normative.compare import compare_and_report
from open_normative.io import read_norms_json
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.pipeline import process_resting

logger = logging.getLogger("compare_recording")

# Supported file formats and their MNE readers
_LOADERS = {
    ".edf": mne.io.read_raw_edf,
    ".bdf": mne.io.read_raw_bdf,
    ".vhdr": mne.io.read_raw_brainvision,
    ".set": mne.io.read_raw_eeglab,
    ".mff": mne.io.read_raw_egi,
    ".raw": mne.io.read_raw_egi,
}


def load_recording(filepath: Path, line_freq: float | None = None) -> mne.io.Raw:
    """Load an EEG recording from any supported format.

    Args:
        filepath: Path to the EEG file.
        line_freq: Line frequency override (stored in raw.info for notch filtering).

    Returns:
        MNE Raw object, preloaded.

    Raises:
        ValueError: If the file format is not supported.
    """
    suffix = filepath.suffix.lower()
    if suffix not in _LOADERS:
        raise ValueError(
            f"Unsupported file format: {suffix}. "
            f"Supported: {', '.join(sorted(_LOADERS.keys()))}"
        )

    reader = _LOADERS[suffix]
    raw = reader(str(filepath), preload=True, verbose=False)

    if line_freq is not None:
        raw.info["line_freq"] = line_freq

    return raw


def main():
    parser = argparse.ArgumentParser(
        description="Compare a single EEG recording against a normative database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "recording",
        type=Path,
        help="Path to EEG recording file (.edf, .vhdr, .set, .mff)",
    )
    parser.add_argument(
        "norms",
        type=Path,
        help="Path to norms.json from build_norms.py",
    )
    parser.add_argument(
        "--age",
        type=float,
        required=True,
        help="Subject age in years (required for age-bin matching)",
    )
    parser.add_argument(
        "--condition",
        choices=["eo", "ec"],
        required=True,
        help="Recording condition: eo (eyes open) or ec (eyes closed)",
    )
    parser.add_argument(
        "--sex",
        choices=["M", "F"],
        default=None,
        help="Subject sex (metadata only, not currently used for comparison)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="Write full ComparisonReport as JSON to this file",
    )
    parser.add_argument(
        "--skip-connectivity",
        action="store_true",
        help="Skip connectivity analysis (faster, spectral-only comparison)",
    )
    parser.add_argument(
        "--line-freq",
        type=float,
        default=None,
        help="Line noise frequency in Hz (default: 60 for US, use 50 for European)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages (still prints summary)",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stderr,
    )
    # Suppress MNE verbosity
    mne.set_log_level("WARNING")

    # Validate inputs
    if not args.recording.exists():
        logger.error("Recording file not found: %s", args.recording)
        sys.exit(1)
    if not args.norms.exists():
        logger.error("Norms file not found: %s", args.norms)
        sys.exit(1)

    start = time.time()

    # Step 1: Load recording
    logger.info("Loading %s ...", args.recording.name)
    try:
        raw = load_recording(args.recording, line_freq=args.line_freq)
    except Exception as e:
        logger.error("Failed to load recording: %s", e)
        sys.exit(1)

    logger.info(
        "  %d channels, %.0f Hz, %.1f seconds",
        len(raw.ch_names), raw.info["sfreq"], raw.times[-1],
    )

    # Step 2: Standardize to 19 channels
    logger.info("Standardizing to 19-channel 10-20 montage ...")
    raw.pick("eeg")
    try:
        raw = pick_standard_19(raw)
    except Exception as e:
        logger.error("Channel standardization failed: %s", e)
        sys.exit(1)

    logger.info("  Channels: %s", ", ".join(raw.ch_names))

    # Step 3: Build params (with optional line freq override)
    params = None
    if args.line_freq is not None:
        params = copy.deepcopy(PIPELINE_PARAMS)
        params["preprocessing"]["filter"]["notch_freq"] = args.line_freq
        params["preprocessing"]["filter"]["notch_harmonics"] = [
            args.line_freq * h for h in (2, 3)
        ]
        logger.info("  Line frequency override: %.0f Hz", args.line_freq)

    # Step 4: Run pipeline
    logger.info("Running processing pipeline ...")
    try:
        result = process_resting(
            raw,
            condition=args.condition,
            params=params,
            skip_connectivity=args.skip_connectivity,
        )
    except Exception as e:
        logger.error("Pipeline processing failed: %s", e)
        sys.exit(1)

    metrics = result.to_nested_dict()
    n_metrics = sum(
        1 for ch in metrics.values()
        for band in ch.values()
        for _ in band.values()
    )
    logger.info("  Computed %d metrics across %d channels", n_metrics, len(metrics))

    # Step 5: Load norms and compare
    logger.info("Loading normative database ...")
    norms = read_norms_json(args.norms)
    logger.info("  %d normative cells loaded", len(norms))

    logger.info("Comparing against norms (age=%.1f, condition=%s) ...", args.age, args.condition)
    report = compare_and_report(
        metrics=metrics,
        norms=norms,
        age=args.age,
        condition=args.condition,
    )

    elapsed = time.time() - start

    # Step 6: Output
    if args.output:
        report_dict = report.to_dict()
        # Add recording metadata
        report_dict["metadata"]["recording_file"] = str(args.recording)
        report_dict["metadata"]["sex"] = args.sex
        report_dict["metadata"]["processing_time_sec"] = round(elapsed, 1)
        report_dict["metadata"]["skip_connectivity"] = args.skip_connectivity

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        logger.info("Full report written to %s", args.output)

    # Always print text summary
    print(report.summary_text())
    print(f"\n--- Processed in {elapsed:.1f} seconds ---")


if __name__ == "__main__":
    main()
