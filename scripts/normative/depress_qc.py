#!/usr/bin/env python3
"""QC sweep for Depression EEG dataset (ds003478).

Loads each subject's raw EEGLAB .set file and produces a QC report
covering BIDS structure, recording parameters, channel name normalization,
healthy control filtering (BDI), signal quality, EO/EC event parsing,
duration validation, and demographics.

The Depression study recorded 64-channel resting EEG with alternating
1-minute eyes-open and eyes-closed blocks within a single run.
Recording system: Neuroscan Synamps2, 500 Hz, referenced between Cz/CPz.
Location: University of Arizona (USA, 60 Hz mains).

Healthy controls: BDI <= 13, excluding sub-038 (invalid, all NaN).

Usage:
    # Quick test with 3 subjects
    python scripts/normative/depress_qc.py ~/Data/EEG/Depression \\
        -o ./depress_qc --max-subjects 3

    # Full QC sweep, 4 parallel workers
    python scripts/normative/depress_qc.py ~/Data/EEG/Depression \\
        -o ./depress_qc -w 4
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import multiprocessing
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import mne
import numpy as np

from open_normative.channels import _CHANNELS_19, _NAME_MAP, normalize_channel_names
from open_normative.datasets.depress import (
    _DEPRESS_CAP_FIXES,
    _EXCLUDED_SUBJECTS,
    _MAX_BDI_HEALTHY,
    _normalize_depress_channels,
    parse_events_tsv,
    segment_eo_ec,
    _find_events_tsv,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_SFREQ = 500.0
EXPECTED_N_EEG_CHANNELS = 64
EXPECTED_N_EOG_CHANNELS = 2  # HEOG, VEOG
EXPECTED_TOTAL_CHANNELS = 66
LINE_FREQ = 60.0  # USA mains

# Non-EEG channel patterns
NON_EEG_PATTERNS = {"VEOG", "HEOG", "ECG", "EMG", "EOG", "BIP", "AUX",
                     "GSR", "RESP", "TEMP", "STATUS", "TRIGGER", "STI"}

# Duration thresholds (full run ~500s = 8.4 min)
MIN_DURATION_S = 300.0        # 5 min minimum
EXPECTED_DURATION_S = 500.0   # ~8.4 min expected
MAX_DURATION_S = 700.0        # ~11.7 min max

# Per-condition duration thresholds (expect ~4 x 60s = 240s each)
MIN_CONDITION_DURATION_S = 100.0
EXPECTED_CONDITION_DURATION_S = 240.0

# Signal quality thresholds
FLAT_VARIANCE_UV2 = 0.1
RAILED_AMPLITUDE_UV = 1000.0
RAILED_FRACTION = 0.10
NOISE_SD_THRESHOLD = 3.0
MEDIAN_AMP_WARN_UV = 200.0
ARTIFACT_EPOCH_SEC = 1.0
ARTIFACT_CHAN_FRACTION = 0.50
ARTIFACT_AMP_UV = 200.0
ARTIFACT_PCT_WARN = 20.0
ARTIFACT_PCT_FAIL = 50.0

# BDI score bins for distribution analysis
BDI_BINS = [(0, 5), (6, 10), (11, 13), (14, 19), (20, 28), (29, 63)]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging to both console and error log file."""
    log = logging.getLogger("depress_qc")
    log.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)

    error_log = output_dir / "qc_errors.log"
    file_handler = logging.FileHandler(error_log)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    log.addHandler(file_handler)

    return log


logger = logging.getLogger("depress_qc")


# ---------------------------------------------------------------------------
# Channel mapping
# ---------------------------------------------------------------------------

def build_channel_mapping(ch_names: list[str]) -> dict:
    """Build mapping from 64-channel Neuroscan layout to 19-channel 10-20.

    The Depression dataset uses UPPERCASE names (FP1, CZ, etc.) which
    must first be normalized to standard case.

    Returns dict with mapping_1020, present_19, missing_19, additional_1010.
    """
    # Apply Depression-specific capitalization fixes first
    fixed_names = [_DEPRESS_CAP_FIXES.get(ch, ch) for ch in ch_names]
    # Then apply global normalization
    normalized = normalize_channel_names(fixed_names)
    norm_to_orig = dict(zip(normalized, ch_names))

    mapping = {}
    present = []
    missing = []

    for target in _CHANNELS_19:
        if target in norm_to_orig:
            mapping[target] = norm_to_orig[target]
            present.append(target)
        else:
            missing.append(target)

    mapped_originals = set(mapping.values())
    additional = [ch for ch in ch_names if ch not in mapped_originals
                  and not any(p in ch.upper() for p in NON_EEG_PATTERNS)]

    return {
        "mapping_1020": mapping,
        "present_19": present,
        "missing_19": missing,
        "additional_1010": sorted(additional),
        "normalization_applied": {
            orig: _DEPRESS_CAP_FIXES.get(orig, orig)
            for orig in ch_names
            if orig in _DEPRESS_CAP_FIXES and _DEPRESS_CAP_FIXES[orig] != orig
        },
    }


# ---------------------------------------------------------------------------
# Participants parsing
# ---------------------------------------------------------------------------

def load_participants(data_dir: Path) -> dict[str, dict]:
    """Parse participants.tsv for all subjects (not filtered).

    Returns {subject_id: {age, sex, bdi, stai, scid, hamd, is_healthy}}.
    """
    tsv_path = data_dir / "participants.tsv"
    if not tsv_path.exists():
        logger.warning("No participants.tsv found in %s", data_dir)
        return {}

    participants = {}
    with tsv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            sid = row.get("participant_id", "").strip()
            if not sid:
                continue

            # Age
            raw_age = row.get("age", "").strip()
            try:
                age = float(raw_age)
            except (ValueError, TypeError):
                age = float("nan")

            # Sex: 1=F, 2=M
            raw_sex = row.get("sex", "").strip()
            try:
                sex_code = int(raw_sex)
                sex = "F" if sex_code == 1 else ("M" if sex_code == 2 else "")
            except (ValueError, TypeError):
                sex = ""

            # BDI
            raw_bdi = row.get("BDI", "").strip()
            try:
                bdi = float(raw_bdi)
            except (ValueError, TypeError):
                bdi = float("nan")

            # Additional clinical measures
            info = {"age": age, "sex": sex, "bdi": bdi}
            for field in ("STAI", "SCID", "HamD"):
                raw_val = row.get(field, "").strip()
                try:
                    info[field.lower()] = float(raw_val)
                except (ValueError, TypeError):
                    info[field.lower()] = raw_val

            # Healthy control classification
            is_healthy = (
                sid not in _EXCLUDED_SUBJECTS
                and not math.isnan(bdi)
                and bdi <= _MAX_BDI_HEALTHY
            )
            info["is_healthy"] = is_healthy

            participants[sid] = info

    return participants


# ---------------------------------------------------------------------------
# BIDS discovery
# ---------------------------------------------------------------------------

def discover_subjects(data_dir: Path) -> list[dict]:
    """Discover all subjects and their EEG files.

    Returns list of dicts with subject_id, run-01 set_path, events_path,
    and channels_path.
    """
    subjects = []
    for sub_dir in sorted(data_dir.glob("sub-*")):
        if not sub_dir.is_dir():
            continue
        subject_id = sub_dir.name
        eeg_dir = sub_dir / "eeg"
        if not eeg_dir.exists():
            subjects.append({
                "subject_id": subject_id,
                "set_path": None,
                "events_path": None,
                "channels_path": None,
                "has_run_01": False,
                "has_run_02": False,
            })
            continue

        set_files_r1 = list(eeg_dir.glob("*_task-Rest_run-01_eeg.set"))
        set_files_r2 = list(eeg_dir.glob("*_task-Rest_run-02_eeg.set"))

        set_path = set_files_r1[0] if set_files_r1 else None
        events_path = None
        channels_path = None

        if set_path:
            ep = _find_events_tsv(set_path)
            events_path = ep if ep.exists() else None
            cp = eeg_dir / set_path.name.replace("_eeg.set", "_channels.tsv")
            channels_path = cp if cp.exists() else None

        subjects.append({
            "subject_id": subject_id,
            "set_path": set_path,
            "events_path": events_path,
            "channels_path": channels_path,
            "has_run_01": bool(set_files_r1),
            "has_run_02": bool(set_files_r2),
        })

    return subjects


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------

def load_existing_qc(subjects_dir: Path) -> set[str]:
    """Return set of subject_ids with existing QC results."""
    done = set()
    if not subjects_dir.exists():
        return done
    for fpath in subjects_dir.glob("*_qc.json"):
        subject_id = fpath.stem.replace("_qc", "")
        done.add(subject_id)
    return done


def save_subject_qc(subjects_dir: Path, result: dict):
    """Save a single subject's QC result."""
    fname = f"{result['subject_id']}_qc.json"
    with open(subjects_dir / fname, "w") as f:
        json.dump(result, f, indent=2)


def load_all_results(subjects_dir: Path) -> list[dict]:
    """Load all QC result JSONs."""
    results = []
    if not subjects_dir.exists():
        return results
    for fpath in sorted(subjects_dir.glob("*_qc.json")):
        with open(fpath) as f:
            results.append(json.load(f))
    return results


# ---------------------------------------------------------------------------
# Signal quality checks
# ---------------------------------------------------------------------------

def _is_eeg_channel(ch_name: str) -> bool:
    """Return True if channel name looks like an EEG channel."""
    return not any(p in ch_name.upper() for p in NON_EEG_PATTERNS)


def check_basic_integrity(raw, data_uv) -> tuple[dict, list]:
    """Check sampling rate, channel count, duration, data scale."""
    issues = []
    sfreq = raw.info["sfreq"]
    n_channels = len(raw.ch_names)
    duration_sec = raw.n_times / sfreq
    duration_min = duration_sec / 60.0

    # Sampling rate
    if sfreq != EXPECTED_SFREQ:
        issues.append(("warn", f"sfreq={sfreq}, expected {EXPECTED_SFREQ}"))

    # Channel count (before dropping EOG)
    eeg_count = sum(1 for ch in raw.ch_names if _is_eeg_channel(ch))
    eog_count = n_channels - eeg_count
    if eeg_count < 50:
        issues.append(("fail", f"n_eeg_channels={eeg_count}, expected ~{EXPECTED_N_EEG_CHANNELS}"))
    elif eeg_count != EXPECTED_N_EEG_CHANNELS:
        issues.append(("warn", f"n_eeg_channels={eeg_count}, expected {EXPECTED_N_EEG_CHANNELS}"))

    # Duration (full run)
    if duration_sec < MIN_DURATION_S:
        issues.append(("fail", f"duration={duration_min:.1f} min, below {MIN_DURATION_S / 60:.0f} min"))
    elif duration_sec > MAX_DURATION_S:
        issues.append(("warn", f"duration={duration_min:.1f} min, above {MAX_DURATION_S / 60:.0f} min"))

    # Data scale (demeaned)
    eeg_idx = [i for i, ch in enumerate(raw.ch_names) if _is_eeg_channel(ch)]
    if eeg_idx:
        eeg_data = data_uv[eeg_idx]
        eeg_demeaned = eeg_data - np.mean(eeg_data, axis=1, keepdims=True)
        median_amp = float(np.median(np.abs(eeg_demeaned)))
    else:
        median_amp = float(np.median(np.abs(data_uv)))

    if median_amp > MEDIAN_AMP_WARN_UV:
        issues.append(("fail", f"median amplitude={median_amp:.1f} uV, exceeds {MEDIAN_AMP_WARN_UV}"))

    metrics = {
        "sfreq": sfreq,
        "n_channels_total": n_channels,
        "n_eeg_channels": eeg_count,
        "n_eog_channels": eog_count,
        "duration_sec": round(duration_sec, 2),
        "duration_min": round(duration_min, 2),
        "median_abs_amplitude_uv": round(median_amp, 2),
    }
    return metrics, issues


def check_channels(raw, data_uv, channel_mapping: dict) -> tuple[dict, list]:
    """Check channel names, normalization, flat/railed/noisy channels."""
    issues = []
    ch_names = raw.ch_names

    # Channel name normalization verification
    n_normalized = len(channel_mapping.get("normalization_applied", {}))
    uppercase_remaining = [ch for ch in ch_names if ch.upper() == ch and len(ch) > 1
                           and _is_eeg_channel(ch)]

    # 10-20 subset verification
    missing_19 = channel_mapping["missing_19"]
    if missing_19:
        severity = "fail" if len(missing_19) > 3 else "warn"
        issues.append((severity, f"missing 10-20 channels: {', '.join(missing_19)}"))

    # EEG channels only for quality checks
    eeg_idx = [i for i, ch in enumerate(ch_names) if _is_eeg_channel(ch)]
    eeg_names = [ch_names[i] for i in eeg_idx]
    eeg_data = data_uv[eeg_idx]

    # Demean
    eeg_demeaned = eeg_data - np.mean(eeg_data, axis=1, keepdims=True)

    # Flat channels
    variances = np.var(eeg_data, axis=1)
    flat = [eeg_names[i] for i in range(len(eeg_names))
            if variances[i] < FLAT_VARIANCE_UV2]
    if flat:
        issues.append(("warn", f"flat channels (var<{FLAT_VARIANCE_UV2} uV^2): {', '.join(flat)}"))

    # Railed channels
    railed = []
    for i, ch in enumerate(eeg_names):
        frac = float(np.mean(np.abs(eeg_demeaned[i]) > RAILED_AMPLITUDE_UV))
        if frac > RAILED_FRACTION:
            railed.append(ch)
    if railed:
        issues.append(("warn", f"railed channels: {', '.join(railed)}"))

    # 60 Hz line noise
    noisy = _check_line_noise(raw, eeg_data, eeg_names)
    if noisy:
        issues.append(("warn", f"excessive {LINE_FREQ:.0f} Hz noise: {', '.join(noisy)}"))

    metrics = {
        "n_eeg_channels": len(eeg_idx),
        "present_19": channel_mapping["present_19"],
        "missing_19": missing_19,
        "additional_1010": channel_mapping["additional_1010"],
        "normalization_applied": channel_mapping.get("normalization_applied", {}),
        "n_channels_normalized": n_normalized,
        "uppercase_remaining": uppercase_remaining,
        "flat_channels": flat,
        "railed_channels": railed,
        "noisy_60hz_channels": noisy,
    }
    return metrics, issues


def _check_line_noise(raw, eeg_data, eeg_names) -> list[str]:
    """Identify channels with excessive 60 Hz power."""
    sfreq = raw.info["sfreq"]
    seg_len = int(10 * sfreq)
    n_segs = min(6, eeg_data.shape[1] // seg_len)
    if n_segs == 0:
        return []

    powers_60 = np.zeros(len(eeg_names))
    freqs = np.fft.rfftfreq(seg_len, d=1.0 / sfreq)
    band_mask = (freqs >= LINE_FREQ - 1) & (freqs <= LINE_FREQ + 1)

    for s in range(n_segs):
        start = s * seg_len
        end = start + seg_len
        for j in range(len(eeg_names)):
            spectrum = np.abs(np.fft.rfft(eeg_data[j, start:end])) ** 2
            powers_60[j] += np.mean(spectrum[band_mask])

    powers_60 /= n_segs
    mean_p = np.mean(powers_60)
    std_p = np.std(powers_60)

    noisy = []
    if std_p > 0:
        for j in range(len(eeg_names)):
            if (powers_60[j] - mean_p) / std_p > NOISE_SD_THRESHOLD:
                noisy.append(eeg_names[j])
    return noisy


def check_signal_quality(raw, data_uv) -> tuple[dict, list]:
    """Check amplitude distribution and gross artifacts."""
    issues = []
    ch_names = raw.ch_names
    sfreq = raw.info["sfreq"]

    eeg_idx = [i for i, ch in enumerate(ch_names) if _is_eeg_channel(ch)]
    eeg_names = [ch_names[i] for i in eeg_idx]
    eeg_data = data_uv[eeg_idx]
    n_eeg = len(eeg_idx)

    eeg_demeaned = eeg_data - np.mean(eeg_data, axis=1, keepdims=True)

    # Per-channel median absolute amplitude
    per_ch_median = {ch: round(float(np.median(np.abs(eeg_demeaned[j]))), 2)
                     for j, ch in enumerate(eeg_names)}
    overall_median = float(np.median(np.abs(eeg_demeaned)))

    # Gross artifact detection
    epoch_samples = int(ARTIFACT_EPOCH_SEC * sfreq)
    n_epochs = eeg_demeaned.shape[1] // epoch_samples
    n_artifact_epochs = 0

    for e in range(n_epochs):
        start = e * epoch_samples
        end = start + epoch_samples
        epoch = eeg_demeaned[:, start:end]
        ch_exceed = np.sum(np.max(np.abs(epoch), axis=1) > ARTIFACT_AMP_UV)
        if ch_exceed > ARTIFACT_CHAN_FRACTION * n_eeg:
            n_artifact_epochs += 1

    artifact_pct = 100.0 * n_artifact_epochs / n_epochs if n_epochs > 0 else 0.0

    if artifact_pct > ARTIFACT_PCT_FAIL:
        issues.append(("fail", f"gross artifact={artifact_pct:.1f}%"))
    elif artifact_pct > ARTIFACT_PCT_WARN:
        issues.append(("warn", f"gross artifact={artifact_pct:.1f}%"))

    usable_sec = round((n_epochs - n_artifact_epochs) * ARTIFACT_EPOCH_SEC, 1)

    metrics = {
        "median_amplitude_uv": round(overall_median, 2),
        "per_channel_median_uv": per_ch_median,
        "gross_artifact_pct": round(artifact_pct, 2),
        "n_artifact_epochs": n_artifact_epochs,
        "n_total_epochs": n_epochs,
        "usable_duration_sec": usable_sec,
    }
    return metrics, issues


# ---------------------------------------------------------------------------
# EO/EC event parsing validation
# ---------------------------------------------------------------------------

def check_eo_ec_events(set_path: Path, raw_duration: float) -> tuple[dict, list]:
    """Validate EO/EC event markers from events.tsv.

    Checks:
    - events.tsv exists and is parseable
    - Contains EO and EC markers
    - Segments have reasonable durations
    - Total EO + EC covers most of the recording
    """
    issues = []

    events_path = _find_events_tsv(set_path)
    has_events = events_path.exists()

    if not has_events:
        issues.append(("fail", "no events.tsv found"))
        return {"has_events_tsv": False}, issues

    events = parse_events_tsv(events_path)
    if not events:
        issues.append(("fail", "events.tsv is empty or unparseable"))
        return {"has_events_tsv": True, "n_events": 0}, issues

    # Parse segments
    segments = segment_eo_ec(events, raw_duration)

    n_eo_blocks = len(segments["eo"])
    n_ec_blocks = len(segments["ec"])

    eo_total = sum(end - start for start, end in segments["eo"])
    ec_total = sum(end - start for start, end in segments["ec"])

    # Individual block durations
    eo_durations = [end - start for start, end in segments["eo"]]
    ec_durations = [end - start for start, end in segments["ec"]]

    # Unique event types
    unique_events = sorted(set(ev["trial_type"] for ev in events))

    # Validation
    if n_eo_blocks == 0:
        issues.append(("fail", "no eyes-open blocks found in events"))
    if n_ec_blocks == 0:
        issues.append(("fail", "no eyes-closed blocks found in events"))

    if eo_total < MIN_CONDITION_DURATION_S:
        issues.append(("warn", f"EO total={eo_total:.0f}s, below {MIN_CONDITION_DURATION_S:.0f}s"))
    if ec_total < MIN_CONDITION_DURATION_S:
        issues.append(("warn", f"EC total={ec_total:.0f}s, below {MIN_CONDITION_DURATION_S:.0f}s"))

    # Check coverage
    total_segmented = eo_total + ec_total
    coverage_pct = 100.0 * total_segmented / raw_duration if raw_duration > 0 else 0.0
    if coverage_pct < 50.0:
        issues.append(("warn", f"EO+EC covers only {coverage_pct:.0f}% of recording"))

    metrics = {
        "has_events_tsv": True,
        "n_events": len(events),
        "unique_event_types": unique_events[:20],
        "n_eo_blocks": n_eo_blocks,
        "n_ec_blocks": n_ec_blocks,
        "eo_total_sec": round(eo_total, 1),
        "ec_total_sec": round(ec_total, 1),
        "eo_block_durations_sec": [round(d, 1) for d in eo_durations],
        "ec_block_durations_sec": [round(d, 1) for d in ec_durations],
        "coverage_pct": round(coverage_pct, 1),
    }
    return metrics, issues


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def determine_status(issues: list[tuple[str, str]]) -> str:
    """Return 'fail', 'warn', or 'pass' based on issue severities."""
    if any(sev == "fail" for sev, _ in issues):
        return "fail"
    if any(sev == "warn" for sev, _ in issues):
        return "warn"
    return "pass"


def compute_normative_eligibility(result: dict, participants: dict) -> bool:
    """Check if a subject is eligible for normative database.

    Requires: pass/warn status, valid demographics, healthy control, and
    parseable EO/EC events.
    """
    if result["status"] == "fail":
        return False
    demo = participants.get(result["subject_id"], {})
    if not demo.get("is_healthy", False):
        return False
    if math.isnan(demo.get("age", float("nan"))):
        return False
    if demo.get("sex", "") not in ("M", "F"):
        return False
    # Must have both EO and EC events
    ev = result.get("eo_ec_events", {})
    if ev.get("n_eo_blocks", 0) == 0 or ev.get("n_ec_blocks", 0) == 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Per-subject QC worker
# ---------------------------------------------------------------------------

def qc_one_subject(subject_info: dict) -> dict:
    """Run all QC checks on one Depression subject."""
    subject_id = subject_info["subject_id"]
    set_path = subject_info.get("set_path")

    result = {
        "subject_id": subject_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "issues": [],
        "has_run_01": subject_info.get("has_run_01", False),
        "has_run_02": subject_info.get("has_run_02", False),
        "integrity": {},
        "channels": {},
        "signal_quality": {},
        "eo_ec_events": {},
    }

    all_issues = []

    if not set_path:
        all_issues.append(("fail", "no run-01 .set file found"))
        result["issues"] = [{"severity": s, "message": m} for s, m in all_issues]
        return result

    # Load the recording
    try:
        raw = mne.io.read_raw_eeglab(str(set_path), preload=True, verbose=False)
    except Exception as exc:
        all_issues.append(("fail", f"load error: {exc}"))
        result["issues"] = [{"severity": s, "message": m} for s, m in all_issues]
        return result

    data_uv = raw.get_data() * 1e6

    # Channel mapping (before normalization, to verify uppercase names)
    ch_mapping = build_channel_mapping(raw.ch_names)

    # 1. Basic integrity
    try:
        metrics, issues = check_basic_integrity(raw, data_uv)
        result["integrity"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"integrity check error: {exc}"))

    # 2. Channel checks
    try:
        metrics, issues = check_channels(raw, data_uv, ch_mapping)
        result["channels"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"channel check error: {exc}"))

    # 3. Signal quality (on EEG channels only)
    try:
        metrics, issues = check_signal_quality(raw, data_uv)
        result["signal_quality"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"signal quality error: {exc}"))

    # 4. EO/EC event parsing
    try:
        raw_duration = raw.n_times / raw.info["sfreq"]
        metrics, issues = check_eo_ec_events(Path(set_path), raw_duration)
        result["eo_ec_events"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"event parsing error: {exc}"))

    # Store channel mapping
    result["channel_mapping"] = {
        "mapping_1020": ch_mapping["mapping_1020"],
        "present_19": ch_mapping["present_19"],
        "missing_19": ch_mapping["missing_19"],
        "normalization_applied": ch_mapping.get("normalization_applied", {}),
    }

    # Final status
    result["issues"] = [{"severity": s, "message": m} for s, m in all_issues]
    result["status"] = determine_status(all_issues)

    return result


# ---------------------------------------------------------------------------
# Demographics and BDI analysis
# ---------------------------------------------------------------------------

def compute_bdi_distribution(participants: dict) -> dict:
    """Compute BDI score distribution across all participants."""
    all_bdi = []
    healthy_bdi = []
    depressed_bdi = []

    for sid, info in sorted(participants.items()):
        bdi = info.get("bdi", float("nan"))
        if math.isnan(bdi):
            continue
        all_bdi.append(bdi)
        if info.get("is_healthy", False):
            healthy_bdi.append(bdi)
        else:
            depressed_bdi.append(bdi)

    # Bin distribution
    bins = {}
    for lo, hi in BDI_BINS:
        label = f"{lo}-{hi}"
        count = sum(1 for b in all_bdi if lo <= b <= hi)
        healthy_count = sum(1 for b in healthy_bdi if lo <= b <= hi)
        bins[label] = {"total": count, "healthy": healthy_count}

    return {
        "n_total": len(all_bdi),
        "n_healthy": len(healthy_bdi),
        "n_depressed": len(depressed_bdi),
        "mean_bdi_all": round(float(np.mean(all_bdi)), 1) if all_bdi else None,
        "mean_bdi_healthy": round(float(np.mean(healthy_bdi)), 1) if healthy_bdi else None,
        "bdi_bins": bins,
        "threshold": _MAX_BDI_HEALTHY,
    }


def compute_demographics(participants: dict, eligible_ids: set[str]) -> dict:
    """Compute demographic summary for eligible subjects."""
    ages = []
    sex_counts = {"M": 0, "F": 0, "?": 0}

    for sid in sorted(eligible_ids):
        demo = participants.get(sid, {})
        age = demo.get("age", float("nan"))
        sex = demo.get("sex", "")

        if not math.isnan(age):
            ages.append(age)

        if sex in ("M", "F"):
            sex_counts[sex] += 1
        else:
            sex_counts["?"] += 1

    return {
        "n_eligible": len(eligible_ids),
        "n_with_age": len(ages),
        "age_mean": round(float(np.mean(ages)), 1) if ages else None,
        "age_std": round(float(np.std(ages, ddof=1)), 1) if len(ages) > 1 else None,
        "age_min": round(float(np.min(ages)), 1) if ages else None,
        "age_max": round(float(np.max(ages)), 1) if ages else None,
        "sex_counts": sex_counts,
    }


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def write_outputs(output_dir: Path, results: list[dict],
                  participants: dict, channel_mapping: dict | None):
    """Write all output files."""
    results = sorted(results, key=lambda r: r["subject_id"])

    n_pass = sum(1 for r in results if r["status"] == "pass")
    n_warn = sum(1 for r in results if r["status"] == "warn")
    n_fail = sum(1 for r in results if r["status"] == "fail")

    # Normative eligibility
    ready_ids = set()
    for r in results:
        if compute_normative_eligibility(r, participants):
            ready_ids.add(r["subject_id"])

    # --- Summary markdown ---
    lines = [
        "# Depression EEG (ds003478) -- QC Report\n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Total subjects scanned:** {len(results)}\n",
        "## Summary\n",
        "| Verdict | Count |",
        "|---------|-------|",
        f"| Pass    | {n_pass} |",
        f"| Warn    | {n_warn} |",
        f"| Fail    | {n_fail} |",
        f"| **Normative-eligible** | **{len(ready_ids)}** |",
        "",
    ]

    # Dataset info
    lines += [
        "## Dataset Info\n",
        f"- **Recording system:** Neuroscan Synamps2, 64-channel",
        f"- **Sampling rate:** {EXPECTED_SFREQ} Hz",
        f"- **Line frequency:** {LINE_FREQ} Hz (USA)",
        f"- **Reference:** between Cz and CPz",
        f"- **Format:** EEGLAB .set/.fdt",
        f"- **Healthy control threshold:** BDI <= {_MAX_BDI_HEALTHY}",
        f"- **Excluded subjects:** {', '.join(sorted(_EXCLUDED_SUBJECTS))}",
        "",
    ]

    # BDI distribution
    bdi_dist = compute_bdi_distribution(participants)
    lines += [
        "## BDI Distribution\n",
        f"- Total with BDI: {bdi_dist['n_total']}",
        f"- Healthy (BDI <= {_MAX_BDI_HEALTHY}): {bdi_dist['n_healthy']}",
        f"- Depressed (BDI > {_MAX_BDI_HEALTHY}): {bdi_dist['n_depressed']}",
        f"- Mean BDI (all): {bdi_dist['mean_bdi_all']}",
        f"- Mean BDI (healthy): {bdi_dist['mean_bdi_healthy']}",
        "",
        "| BDI Range | Total | Healthy |",
        "|-----------|-------|---------|",
    ]
    for label, counts in bdi_dist["bdi_bins"].items():
        lines.append(f"| {label} | {counts['total']} | {counts['healthy']} |")
    lines.append("")

    # Demographics of eligible subjects
    demo = compute_demographics(participants, ready_ids)
    lines += [
        "## Demographics (Normative-Eligible)\n",
        f"- N: {demo['n_eligible']}",
        f"- Age: {demo['age_mean']} +/- {demo['age_std']} "
        f"(range {demo['age_min']}-{demo['age_max']})" if demo['age_mean'] else "- Age: N/A",
        f"- Sex: M={demo['sex_counts']['M']}, F={demo['sex_counts']['F']}, "
        f"?={demo['sex_counts']['?']}",
        "",
    ]

    # Issue frequency
    issue_counts: dict[str, int] = {}
    for r in results:
        for issue in r.get("issues", []):
            msg = issue["message"]
            key = msg.split(":")[0].split("=")[0].strip()
            issue_counts[key] = issue_counts.get(key, 0) + 1

    if issue_counts:
        lines += ["## Issue Frequency\n",
                   "| Issue | Count |", "|-------|-------|"]
        for reason, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    # EO/EC event summary
    eo_blocks = []
    ec_blocks = []
    for r in results:
        ev = r.get("eo_ec_events", {})
        eo_blocks.append(ev.get("n_eo_blocks", 0))
        ec_blocks.append(ev.get("n_ec_blocks", 0))

    if eo_blocks:
        lines += [
            "## EO/EC Event Parsing\n",
            f"- Mean EO blocks per subject: {np.mean(eo_blocks):.1f}",
            f"- Mean EC blocks per subject: {np.mean(ec_blocks):.1f}",
            f"- Subjects with no EO events: {sum(1 for n in eo_blocks if n == 0)}",
            f"- Subjects with no EC events: {sum(1 for n in ec_blocks if n == 0)}",
            "",
        ]

    # Channel issues aggregate
    flat_all: dict[str, int] = {}
    railed_all: dict[str, int] = {}
    noise_all: dict[str, int] = {}
    for r in results:
        ch = r.get("channels", {})
        for c in ch.get("flat_channels", []):
            flat_all[c] = flat_all.get(c, 0) + 1
        for c in ch.get("railed_channels", []):
            railed_all[c] = railed_all.get(c, 0) + 1
        for c in ch.get("noisy_60hz_channels", []):
            noise_all[c] = noise_all.get(c, 0) + 1

    if flat_all or railed_all or noise_all:
        lines += ["## Channel Issues Across Subjects\n",
                   "| Channel | Flat | Railed | 60 Hz Noise |",
                   "|---------|------|--------|-------------|"]
        all_ch = sorted(set(flat_all) | set(railed_all) | set(noise_all))
        for ch in all_ch:
            lines.append(f"| {ch} | {flat_all.get(ch, 0)} | "
                         f"{railed_all.get(ch, 0)} | {noise_all.get(ch, 0)} |")
        lines.append("")

    # Channel name normalization report
    if channel_mapping:
        norm = channel_mapping.get("normalization_applied", {})
        if norm:
            lines += ["## Channel Name Normalization\n",
                       "| Original | Normalized |",
                       "|----------|------------|"]
            for orig, fixed in sorted(norm.items()):
                lines.append(f"| {orig} | {fixed} |")
            lines.append("")

    # Excluded subjects
    excluded = [r for r in results if r["status"] == "fail"]
    if excluded:
        lines += ["## Excluded Subjects\n",
                   "| Subject | Issues |", "|---------|--------|"]
        for r in excluded:
            issues_str = "; ".join(i["message"] for i in r["issues"]
                                   if i["severity"] == "fail")
            if len(issues_str) > 120:
                issues_str = issues_str[:117] + "..."
            lines.append(f"| {r['subject_id']} | {issues_str} |")
        lines.append("")

    # Per-subject table
    lines += ["## Per-Subject Results\n",
              "| Subject | Status | Healthy | EO Blocks | EC Blocks | Issues |",
              "|---------|--------|---------|-----------|-----------|--------|"]
    for r in results:
        demo_info = participants.get(r["subject_id"], {})
        healthy = "yes" if demo_info.get("is_healthy") else "no"
        ev = r.get("eo_ec_events", {})
        eo_n = ev.get("n_eo_blocks", "?")
        ec_n = ev.get("n_ec_blocks", "?")
        issues_str = "; ".join(
            f"[{i['severity']}] {i['message']}" for i in r.get("issues", [])
        )
        if len(issues_str) > 80:
            issues_str = issues_str[:77] + "..."
        lines.append(f"| {r['subject_id']} | {r['status']} | {healthy} | "
                     f"{eo_n} | {ec_n} | {issues_str} |")
    lines.append("")

    (output_dir / "qc_summary.md").write_text("\n".join(lines) + "\n")

    # --- JSON report ---
    report = {
        "dataset": "ds003478",
        "dataset_name": "Depression EEG",
        "generated": datetime.now(timezone.utc).isoformat(),
        "total_subjects": len(results),
        "pass": n_pass,
        "warn": n_warn,
        "fail": n_fail,
        "normative_eligible": len(ready_ids),
        "healthy_control_threshold": f"BDI <= {_MAX_BDI_HEALTHY}",
        "excluded_subjects": sorted(_EXCLUDED_SUBJECTS),
        "recording_parameters": {
            "system": "Neuroscan Synamps2",
            "n_channels": EXPECTED_TOTAL_CHANNELS,
            "sfreq": EXPECTED_SFREQ,
            "line_freq": LINE_FREQ,
            "reference": "between Cz and CPz",
            "format": "EEGLAB .set/.fdt",
        },
        "bdi_distribution": bdi_dist,
        "demographics": demo,
        "issue_counts": issue_counts,
        "ready_subjects": sorted(ready_ids),
    }
    with open(output_dir / "qc_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # --- Ready / excluded lists ---
    (output_dir / "ready_subjects.txt").write_text(
        "\n".join(sorted(ready_ids)) + "\n" if ready_ids else ""
    )

    excluded_lines = []
    for r in results:
        if r["status"] == "fail":
            reasons = "; ".join(i["message"] for i in r["issues"]
                                if i["severity"] == "fail")
            excluded_lines.append(f"{r['subject_id']}\t{reasons}")
    (output_dir / "excluded_subjects.txt").write_text(
        "\n".join(excluded_lines) + "\n" if excluded_lines else ""
    )

    # --- Channel mapping JSON ---
    if channel_mapping:
        mapping_out = {
            "source_system": "Neuroscan Synamps2 64ch",
            "source_naming": "UPPERCASE 10-10",
            "target_naming": "10-20 (19 channels)",
            "line_frequency_hz": LINE_FREQ,
            "normalization": channel_mapping.get("normalization_applied", {}),
            "mapping": channel_mapping["mapping_1020"],
        }
        with open(output_dir / "channel_mapping.json", "w") as f:
            json.dump(mapping_out, f, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for Depression EEG data (ds003478) "
                    "(64-ch Neuroscan, ages 18-24, USA 60 Hz)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir", type=Path,
        help="Path to Depression BIDS data root (e.g. ~/Data/EEG/Depression/)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("./depress_qc_output"),
        help="Output directory (default: ./depress_qc_output)",
    )
    parser.add_argument(
        "--max-subjects", type=int, default=0,
        help="Limit to N subjects (0 = all)",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=1,
        help="Number of parallel workers (default: 1)",
    )
    args = parser.parse_args()

    # Setup output
    output_dir = args.output
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    log = setup_logging(output_dir)

    log.info("Depression EEG (ds003478) QC")
    log.info("Data directory: %s", args.data_dir)
    log.info("Line frequency: %.0f Hz", LINE_FREQ)

    # Load demographics
    participants = load_participants(args.data_dir)
    n_healthy = sum(1 for p in participants.values() if p.get("is_healthy"))
    log.info("Loaded %d participants (%d healthy controls)", len(participants), n_healthy)

    # Discover subjects
    all_subjects = discover_subjects(args.data_dir)
    log.info("Found %d subject directories", len(all_subjects))

    n_with_data = sum(1 for s in all_subjects if s["has_run_01"])
    n_with_r2 = sum(1 for s in all_subjects if s["has_run_02"])
    log.info("  With run-01 data: %d", n_with_data)
    log.info("  With run-02 data: %d (not used)", n_with_r2)

    # Resumability
    done = load_existing_qc(subjects_dir)
    if done:
        log.info("Found %d existing QC results -- will skip those", len(done))

    todo = [s for s in all_subjects if s["subject_id"] not in done]
    if args.max_subjects > 0:
        todo = todo[:args.max_subjects]

    log.info("Will QC %d subjects (workers=%d)", len(todo), args.workers)

    # --- Main QC loop ---
    if todo:
        start_time = time.time()
        processed = 0
        errors = 0

        if args.workers > 1:
            with multiprocessing.Pool(args.workers) as pool:
                for result in pool.imap_unordered(qc_one_subject, todo):
                    save_subject_qc(subjects_dir, result)
                    processed += 1
                    if result["status"] == "fail":
                        errors += 1
                    elapsed = time.time() - start_time
                    rate = processed / (elapsed / 60) if elapsed > 0 else 0
                    log.info(
                        "[%d/%d] %s: %s (%.1f subj/min)",
                        processed, len(todo), result["subject_id"],
                        result["status"], rate,
                    )
        else:
            for subject_info in todo:
                result = qc_one_subject(subject_info)
                save_subject_qc(subjects_dir, result)
                processed += 1
                if result["status"] == "fail":
                    errors += 1
                elapsed = time.time() - start_time
                rate = processed / (elapsed / 60) if elapsed > 0 else 0
                log.info(
                    "[%d/%d] %s: %s (%.1f subj/min)",
                    processed, len(todo), result["subject_id"],
                    result["status"], rate,
                )

        elapsed_total = time.time() - start_time
        log.info(
            "\nQC complete: %d subjects in %.1f min, %d failures",
            processed, elapsed_total / 60, errors,
        )

    # --- Load all results ---
    all_results = load_all_results(subjects_dir)
    log.info("Total results: %d", len(all_results))

    # --- Extract channel mapping from first successful result ---
    channel_mapping = None
    for r in all_results:
        if "channel_mapping" in r and r["channel_mapping"].get("present_19"):
            channel_mapping = r["channel_mapping"]
            break

    # --- Write outputs ---
    log.info("Writing output files...")
    write_outputs(output_dir, all_results, participants, channel_mapping)

    # Final summary
    ready_count = sum(1 for r in all_results
                      if compute_normative_eligibility(r, participants))
    log.info("\nResults:")
    log.info("  Pass: %d", sum(1 for r in all_results if r["status"] == "pass"))
    log.info("  Warn: %d", sum(1 for r in all_results if r["status"] == "warn"))
    log.info("  Fail: %d", sum(1 for r in all_results if r["status"] == "fail"))
    log.info("  Normative-eligible: %d", ready_count)
    log.info("\nOutput files:")
    log.info("  %s", output_dir / "qc_summary.md")
    log.info("  %s", output_dir / "qc_report.json")
    log.info("  %s", output_dir / "channel_mapping.json")
    log.info("  %s", output_dir / "ready_subjects.txt")
    log.info("  %s", output_dir / "excluded_subjects.txt")
    log.info("  %s/ (per-subject JSONs)", subjects_dir)


if __name__ == "__main__":
    main()
