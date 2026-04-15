#!/usr/bin/env python3
"""QC sweep for Test-Retest EEG data (OpenNeuro ds004148).

Loads each subject's raw BrainVision files and produces a QC report
covering BIDS structure, recording parameters, channel mapping,
signal quality, duration verification, and demographics.

The TRT study recorded EEG in multiple sessions and tasks:
  - 3 sessions (session1, session2, session3)
  - 5 tasks including eyesclosed and eyesopen (~5 min each)

For normative purposes, only session 1 eyesclosed and eyesopen are used.

Usage:
    # Quick test with 3 subjects
    python scripts/normative/trt_qc.py ~/Data/EEG/TRT/ \\
        -o ./trt_qc --max-subjects 3

    # Full QC sweep, 4 parallel workers
    python scripts/normative/trt_qc.py ~/Data/EEG/TRT/ \\
        -o ./trt_qc -w 4
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_SFREQ = 500.0
EXPECTED_N_CHANNELS = 64
REFERENCE_CHANNEL = "FCz"
LINE_FREQ = 50.0  # China mains

# Non-EEG channel patterns
NON_EEG_PATTERNS = {"VEOG", "HEOG", "ECG", "EMG", "EOG", "BIP", "AUX",
                     "GSR", "RESP", "TEMP", "STATUS", "TRIGGER", "STI"}

# Duration thresholds (~5 min = 300 s expected per task)
MIN_DURATION_S = 180.0        # 3 min — fail below this
EXPECTED_DURATION_S = 300.0   # 5 min expected
MAX_DURATION_S = 420.0        # 7 min — warn above this

# Signal quality thresholds
FLAT_VARIANCE_UV2 = 0.1       # uV^2 — below this, channel is flat
RAILED_AMPLITUDE_UV = 1000.0  # uV — above this on demeaned data
RAILED_FRACTION = 0.10        # >10% of samples railed -> flag
NOISE_SD_THRESHOLD = 3.0      # 50 Hz power > 3 SD above mean -> flag
MEDIAN_AMP_WARN_UV = 200.0    # overall median amplitude warning
ARTIFACT_EPOCH_SEC = 1.0      # epoch length for gross artifact check
ARTIFACT_CHAN_FRACTION = 0.50  # >50% channels exceed threshold -> artifact
ARTIFACT_AMP_UV = 200.0       # uV per-channel threshold for artifacts
ARTIFACT_PCT_WARN = 20.0      # % — warn above this
ARTIFACT_PCT_FAIL = 50.0      # % — fail above this
DC_OFFSET_WARN_UV = 100.0     # uV — warn if |offset| exceeds this

# Age bins (narrow range: 18-28)
AGE_BINS = [(18, 20), (21, 23), (24, 26), (27, 28)]
THIN_BIN_THRESHOLD = 5  # flag bins with fewer than this

# Reverse name map: 10-20 name -> 10-10 source name
_REVERSE_NAME_MAP = {v: k for k, v in _NAME_MAP.items()}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging to both console and error log file."""
    log = logging.getLogger("trt_qc")
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


logger = logging.getLogger("trt_qc")


# ---------------------------------------------------------------------------
# Channel mapping: 64-channel 10-10 -> 19-channel 10-20
# ---------------------------------------------------------------------------

def build_channel_mapping(ch_names: list[str]) -> dict:
    """Build mapping from 64-channel 10-10 layout to 19-channel 10-20 subset.

    Returns dict with:
        mapping_1020: {10-20 target: 10-10 source name found in data}
        present_19: list of 10-20 channels successfully mapped
        missing_19: list of 10-20 channels NOT found
        additional_1010: list of channels not in the 19-channel subset
    """
    normalized = normalize_channel_names(ch_names)
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

    # Additional channels not part of the 19-channel set
    mapped_originals = set(mapping.values())
    additional = [ch for ch in ch_names if ch not in mapped_originals
                  and not any(p in ch.upper() for p in NON_EEG_PATTERNS)]

    return {
        "mapping_1020": mapping,
        "present_19": present,
        "missing_19": missing,
        "additional_1010": sorted(additional),
    }


# ---------------------------------------------------------------------------
# BIDS discovery and participants parsing
# ---------------------------------------------------------------------------

def load_participants(data_dir: Path) -> dict[str, dict]:
    """Parse participants.tsv for age, sex.

    TRT uses lowercase m/f for sex — normalized to M/F.
    Returns {subject_id: {"age": float, "sex": str}}.
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

            raw_age = row.get("age", "").strip()
            try:
                age = float(raw_age)
            except (ValueError, TypeError):
                age = float("nan")

            # Normalize lowercase m/f to M/F
            raw_sex = row.get("sex", "").strip().upper()
            if raw_sex.startswith("M"):
                sex = "M"
            elif raw_sex.startswith("F"):
                sex = "F"
            else:
                sex = raw_sex

            participants[sid] = {"age": age, "sex": sex}

    return participants


def _parse_bids_entities(filepath: Path) -> dict[str, str]:
    """Extract BIDS entities from a filename.

    E.g. 'sub-01_ses-session1_task-eyesclosed_eeg.vhdr'
    -> {'sub': '01', 'ses': 'session1', 'task': 'eyesclosed'}
    """
    stem = filepath.stem
    # Remove modality suffix like '_eeg'
    if "_eeg" in stem:
        stem = stem[:stem.rfind("_eeg")]

    entities = {}
    for part in stem.split("_"):
        if "-" in part:
            key, val = part.split("-", 1)
            entities[key] = val
    return entities


def discover_subjects(data_dir: Path) -> list[dict]:
    """Discover all subjects in session 1 with eyesclosed/eyesopen files.

    Returns list of dicts:
    {
        "subject_id": str,
        "ec_file": Path or None,
        "eo_file": Path or None,
    }
    """
    # Find all .vhdr files in session 1
    vhdr_files = sorted(
        list(data_dir.glob("sub-*/ses-session1/eeg/*.vhdr"))
    )

    # Group by subject
    subject_files: dict[str, dict] = {}
    for f in vhdr_files:
        entities = _parse_bids_entities(f)
        sub = entities.get("sub", "")
        task = entities.get("task", "")
        subject_id = f"sub-{sub}"

        if subject_id not in subject_files:
            subject_files[subject_id] = {
                "subject_id": subject_id,
                "ec_file": None,
                "eo_file": None,
            }

        if task == "eyesclosed":
            subject_files[subject_id]["ec_file"] = f
        elif task == "eyesopen":
            subject_files[subject_id]["eo_file"] = f

    return sorted(subject_files.values(), key=lambda s: s["subject_id"])


def discover_tasks(data_dir: Path) -> dict[str, int]:
    """Scan all .vhdr files to discover unique BIDS task labels.

    Returns {task_name: count}.
    """
    vhdr_files = list(data_dir.glob("sub-*/ses-*/eeg/*.vhdr"))
    task_counts: dict[str, int] = {}
    for f in vhdr_files:
        entities = _parse_bids_entities(f)
        task = entities.get("task", "unknown")
        task_counts[task] = task_counts.get(task, 0) + 1
    return task_counts


# ---------------------------------------------------------------------------
# Checkpointing (resumability)
# ---------------------------------------------------------------------------

def load_existing_qc(subjects_dir: Path) -> set[str]:
    """Return set of subject_ids that already have QC results."""
    done = set()
    if not subjects_dir.exists():
        return done
    for fpath in subjects_dir.glob("*_qc.json"):
        subject_id = fpath.stem.replace("_qc", "")
        done.add(subject_id)
    return done


def save_subject_qc(subjects_dir: Path, result: dict):
    """Save a single subject's QC result as a checkpoint JSON."""
    fname = f"{result['subject_id']}_qc.json"
    with open(subjects_dir / fname, "w") as f:
        json.dump(result, f, indent=2)


def load_all_results(subjects_dir: Path) -> list[dict]:
    """Load all QC result JSONs from the subjects directory."""
    results = []
    if not subjects_dir.exists():
        return results
    for fpath in sorted(subjects_dir.glob("*_qc.json")):
        with open(fpath) as f:
            results.append(json.load(f))
    return results


# ---------------------------------------------------------------------------
# EEG file loading
# ---------------------------------------------------------------------------

def _load_eeg(filepath: Path):
    """Load a BrainVision EEG file. Returns mne.io.Raw."""
    return mne.io.read_raw_brainvision(str(filepath), preload=True, verbose=False)


def _is_eeg_channel(ch_name: str) -> bool:
    """Return True if channel name looks like an EEG channel."""
    return not any(p in ch_name.upper() for p in NON_EEG_PATTERNS)


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_basic_integrity(raw, data_uv) -> tuple[dict, list]:
    """Check sampling rate, channel count, duration, and data scale.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    sfreq = raw.info["sfreq"]
    n_channels = len(raw.ch_names)
    duration_sec = raw.n_times / sfreq
    duration_min = duration_sec / 60.0

    # Sampling rate
    if sfreq != EXPECTED_SFREQ:
        issues.append(("fail", f"sfreq={sfreq}, expected {EXPECTED_SFREQ}"))

    # Channel count
    if n_channels < 50:
        issues.append(("fail", f"n_channels={n_channels}, expected ~{EXPECTED_N_CHANNELS}"))
    elif n_channels != EXPECTED_N_CHANNELS:
        issues.append(("warn", f"n_channels={n_channels}, expected {EXPECTED_N_CHANNELS}"))

    # Duration (~5 min = 300 s expected per task)
    if duration_sec < MIN_DURATION_S:
        issues.append(("fail", f"duration={duration_min:.1f} min, below {MIN_DURATION_S / 60:.0f} min minimum"))
    elif duration_sec > MAX_DURATION_S:
        issues.append(("warn", f"duration={duration_min:.1f} min, above {MAX_DURATION_S / 60:.0f} min expected max"))

    # Data scale check
    data_demeaned = data_uv - np.mean(data_uv, axis=1, keepdims=True)
    median_amp = float(np.median(np.abs(data_demeaned)))
    if median_amp > MEDIAN_AMP_WARN_UV:
        issues.append(("fail", f"median amplitude={median_amp:.1f} uV, exceeds {MEDIAN_AMP_WARN_UV}"))

    metrics = {
        "sfreq": sfreq,
        "n_channels": n_channels,
        "duration_sec": round(duration_sec, 2),
        "duration_min": round(duration_min, 2),
        "median_abs_amplitude_uv": round(median_amp, 2),
    }
    return metrics, issues


def check_channels(raw, data_uv, channel_mapping: dict) -> tuple[dict, list]:
    """Check channel names, flat/railed/noisy channels, and reference.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    ch_names = raw.ch_names

    # 10-20 subset verification
    missing_19 = channel_mapping["missing_19"]
    if missing_19:
        severity = "fail" if len(missing_19) > 3 else "warn"
        issues.append((severity, f"missing 10-20 channels: {', '.join(missing_19)}"))

    # FCz reference check — expect absent (online reference)
    fcz_present = REFERENCE_CHANNEL in set(ch_names)
    fcz_variance = None
    if fcz_present:
        idx = ch_names.index(REFERENCE_CHANNEL)
        fcz_variance = round(float(np.var(data_uv[idx])), 4)
        if fcz_variance < FLAT_VARIANCE_UV2:
            issues.append(("warn", f"{REFERENCE_CHANNEL} present but flat (was online reference)"))
        else:
            issues.append(("fail", f"{REFERENCE_CHANNEL} present with signal — unexpected"))

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
        issues.append(("warn", f"railed channels (>{RAILED_AMPLITUDE_UV} uV >{RAILED_FRACTION * 100:.0f}%): {', '.join(railed)}"))

    # 50 Hz line noise
    noisy = _check_line_noise(raw, eeg_data, eeg_names)
    if noisy:
        issues.append(("warn", f"excessive {LINE_FREQ:.0f} Hz noise: {', '.join(noisy)}"))

    metrics = {
        "n_eeg_channels": len(eeg_idx),
        "present_19": channel_mapping["present_19"],
        "missing_19": missing_19,
        "additional_1010": channel_mapping["additional_1010"],
        "fcz_present": fcz_present,
        "fcz_variance_uv2": fcz_variance,
        "flat_channels": flat,
        "railed_channels": railed,
        "noisy_50hz_channels": noisy,
    }
    return metrics, issues


def _check_line_noise(raw, eeg_data, eeg_names) -> list[str]:
    """Identify channels with excessive 50 Hz power."""
    sfreq = raw.info["sfreq"]
    seg_len = int(10 * sfreq)
    n_segs = min(6, eeg_data.shape[1] // seg_len)
    if n_segs == 0:
        return []

    powers_50 = np.zeros(len(eeg_names))
    freqs = np.fft.rfftfreq(seg_len, d=1.0 / sfreq)
    band_mask = (freqs >= LINE_FREQ - 1) & (freqs <= LINE_FREQ + 1)

    for s in range(n_segs):
        start = s * seg_len
        end = start + seg_len
        for j in range(len(eeg_names)):
            spectrum = np.abs(np.fft.rfft(eeg_data[j, start:end])) ** 2
            powers_50[j] += np.mean(spectrum[band_mask])

    powers_50 /= n_segs
    mean_p = np.mean(powers_50)
    std_p = np.std(powers_50)

    noisy = []
    if std_p > 0:
        for j in range(len(eeg_names)):
            if (powers_50[j] - mean_p) / std_p > NOISE_SD_THRESHOLD:
                noisy.append(eeg_names[j])
    return noisy


def check_signal_quality(raw, data_uv) -> tuple[dict, list]:
    """Check amplitude distribution, gross artifacts, and DC offset.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    ch_names = raw.ch_names
    sfreq = raw.info["sfreq"]

    # EEG channels only
    eeg_idx = [i for i, ch in enumerate(ch_names) if _is_eeg_channel(ch)]
    eeg_names = [ch_names[i] for i in eeg_idx]
    eeg_data = data_uv[eeg_idx]
    n_eeg = len(eeg_idx)

    # Demean
    eeg_demeaned = eeg_data - np.mean(eeg_data, axis=1, keepdims=True)

    # Per-channel median absolute amplitude (demeaned)
    per_ch_median = {ch: round(float(np.median(np.abs(eeg_demeaned[j]))), 2)
                     for j, ch in enumerate(eeg_names)}
    overall_median = float(np.median(np.abs(eeg_demeaned)))

    # Gross artifact detection — 1-second epochs on demeaned data
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
        issues.append(("fail", f"gross artifact={artifact_pct:.1f}%, exceeds {ARTIFACT_PCT_FAIL}%"))
    elif artifact_pct > ARTIFACT_PCT_WARN:
        issues.append(("warn", f"gross artifact={artifact_pct:.1f}%, exceeds {ARTIFACT_PCT_WARN}%"))

    # Usable duration after artifact removal
    usable_sec = round((n_epochs - n_artifact_epochs) * ARTIFACT_EPOCH_SEC, 1)

    # DC offset per channel
    dc_offsets = {ch: round(float(np.mean(eeg_data[j])), 2)
                  for j, ch in enumerate(eeg_names)}
    large_offset = [ch for ch, off in dc_offsets.items()
                    if abs(off) > DC_OFFSET_WARN_UV]

    metrics = {
        "median_amplitude_uv": round(overall_median, 2),
        "per_channel_median_uv": per_ch_median,
        "gross_artifact_pct": round(artifact_pct, 2),
        "n_artifact_epochs": n_artifact_epochs,
        "n_total_epochs": n_epochs,
        "usable_duration_sec": usable_sec,
        "dc_offsets_uv": dc_offsets,
        "channels_with_large_offset": large_offset,
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

    Requires:
    - Status is 'pass' or 'warn' (not 'fail')
    - Both EC and EO files present
    - Valid age and sex demographics
    """
    if result["status"] == "fail":
        return False
    cond = result.get("condition_files", {})
    if not cond.get("ec_file") or not cond.get("eo_file"):
        return False
    demo = participants.get(result["subject_id"], {})
    if math.isnan(demo.get("age", float("nan"))):
        return False
    if demo.get("sex", "") not in ("M", "F"):
        return False
    return True


# ---------------------------------------------------------------------------
# Per-condition QC (runs checks on a single .vhdr file)
# ---------------------------------------------------------------------------

def _run_checks_on_file(eeg_path: Path) -> dict:
    """Load a single BrainVision file and run all signal-level checks.

    Returns dict with integrity, channels, signal_quality sections.
    """
    result = {
        "source_file": str(eeg_path),
        "integrity": {},
        "channels": {},
        "signal_quality": {},
        "issues": [],
    }

    try:
        raw = _load_eeg(eeg_path)
    except Exception as exc:
        result["issues"] = [("fail", f"load error: {exc}")]
        return result

    # Drop non-EEG channels before QC
    non_eeg = [ch for ch in raw.ch_names if not _is_eeg_channel(ch)]
    if non_eeg:
        raw.drop_channels(non_eeg)

    data_uv = raw.get_data() * 1e6
    all_issues = []

    # Channel mapping
    ch_mapping = build_channel_mapping(raw.ch_names)

    # 1. Basic integrity
    try:
        metrics, issues = check_basic_integrity(raw, data_uv)
        result["integrity"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"integrity check error: {exc}"))

    # 2. Channels
    try:
        metrics, issues = check_channels(raw, data_uv, ch_mapping)
        result["channels"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"channel check error: {exc}"))

    # 3. Signal quality
    try:
        metrics, issues = check_signal_quality(raw, data_uv)
        result["signal_quality"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"signal quality check error: {exc}"))

    result["issues"] = all_issues
    result["channel_mapping"] = ch_mapping
    return result


# ---------------------------------------------------------------------------
# Per-subject QC worker
# ---------------------------------------------------------------------------

def qc_one_subject(subject_info: dict) -> dict:
    """Run all QC checks on one TRT subject.

    Processes session 1 eyesclosed and eyesopen files.
    """
    subject_id = subject_info["subject_id"]
    ec_file = subject_info.get("ec_file")
    eo_file = subject_info.get("eo_file")

    result = {
        "subject_id": subject_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "issues": [],
        "condition_files": {
            "ec_file": str(ec_file) if ec_file else None,
            "eo_file": str(eo_file) if eo_file else None,
        },
        "ec": {},
        "eo": {},
    }

    all_issues = []
    channel_mapping = None

    # Check for missing files
    if not ec_file:
        all_issues.append(("fail", "no eyesclosed file found"))
    if not eo_file:
        all_issues.append(("fail", "no eyesopen file found"))

    # QC eyes-closed
    if ec_file:
        ec_path = Path(ec_file) if isinstance(ec_file, str) else ec_file
        ec_result = _run_checks_on_file(ec_path)
        result["ec"] = {
            "integrity": ec_result["integrity"],
            "channels": ec_result["channels"],
            "signal_quality": ec_result["signal_quality"],
        }
        all_issues.extend(
            (sev, f"[EC] {msg}") for sev, msg in ec_result["issues"]
        )
        channel_mapping = ec_result.get("channel_mapping")

    # QC eyes-open
    if eo_file:
        eo_path = Path(eo_file) if isinstance(eo_file, str) else eo_file
        eo_result = _run_checks_on_file(eo_path)
        result["eo"] = {
            "integrity": eo_result["integrity"],
            "channels": eo_result["channels"],
            "signal_quality": eo_result["signal_quality"],
        }
        all_issues.extend(
            (sev, f"[EO] {msg}") for sev, msg in eo_result["issues"]
        )
        if channel_mapping is None:
            channel_mapping = eo_result.get("channel_mapping")

    # Store channel mapping from first successfully loaded file
    if channel_mapping:
        result["channel_mapping"] = {
            "mapping_1020": channel_mapping["mapping_1020"],
            "present_19": channel_mapping["present_19"],
            "missing_19": channel_mapping["missing_19"],
            "additional_1010": channel_mapping["additional_1010"],
        }

    # Build structured issues and determine status
    result["issues"] = [
        {"severity": sev, "message": msg} for sev, msg in all_issues
    ]
    result["status"] = determine_status(all_issues)

    return result


# ---------------------------------------------------------------------------
# Age distribution
# ---------------------------------------------------------------------------

def compute_age_distribution(participants: dict, subject_ids: set[str]) -> dict:
    """Compute age distribution for a set of subjects.

    Returns dict with age bins and M/F/total counts.
    """
    bins: dict[str, dict] = {}

    for sid in sorted(subject_ids):
        demo = participants.get(sid, {})
        age = demo.get("age", float("nan"))
        sex = demo.get("sex", "?")
        if math.isnan(age):
            continue

        label = None
        for lo, hi in AGE_BINS:
            if lo <= age <= hi:
                label = f"{lo}-{hi}"
                break
        if label is None:
            continue

        bins.setdefault(label, {"M": 0, "F": 0, "?": 0, "total": 0})
        bins[label][sex if sex in ("M", "F") else "?"] += 1
        bins[label]["total"] += 1

    # Flag thin bins
    thin = [label for label, counts in bins.items()
            if counts["total"] < THIN_BIN_THRESHOLD]

    return {
        "bins": bins,
        "thin_bins": thin,
        "thin_threshold": THIN_BIN_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def write_outputs(output_dir: Path, results: list[dict],
                  participants: dict, channel_mapping: dict | None,
                  task_discovery: dict):
    """Write all output files: summary, counts, lists, age distribution."""
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
        "# Test-Retest EEG (ds004148) — QC Report\n",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Total subjects:** {len(results)}\n",
        "## Summary\n",
        "| Verdict | Count |",
        "|---------|-------|",
        f"| Pass    | {n_pass} |",
        f"| Warn    | {n_warn} |",
        f"| Fail    | {n_fail} |",
        f"| **Normative-eligible** | **{len(ready_ids)}** |",
        "",
    ]

    # BIDS task discovery
    lines += ["## BIDS Task Discovery\n"]
    for task, count in sorted(task_discovery.items()):
        lines.append(f"- **{task}**: {count} files")
    lines.append("")

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

    # Channel issues aggregate
    flat_all: dict[str, int] = {}
    railed_all: dict[str, int] = {}
    noise_all: dict[str, int] = {}
    for r in results:
        for cond in ("ec", "eo"):
            ch = r.get(cond, {}).get("channels", {})
            for c in ch.get("flat_channels", []):
                flat_all[c] = flat_all.get(c, 0) + 1
            for c in ch.get("railed_channels", []):
                railed_all[c] = railed_all.get(c, 0) + 1
            for c in ch.get("noisy_50hz_channels", []):
                noise_all[c] = noise_all.get(c, 0) + 1

    if flat_all or railed_all or noise_all:
        lines += ["## Channel Issues Across Subjects\n",
                   "| Channel | Flat | Railed | 50 Hz Noise |",
                   "|---------|------|--------|-------------|"]
        all_ch = sorted(set(flat_all) | set(railed_all) | set(noise_all))
        for ch in all_ch:
            lines.append(f"| {ch} | {flat_all.get(ch, 0)} | "
                         f"{railed_all.get(ch, 0)} | {noise_all.get(ch, 0)} |")
        lines.append("")

    # Age distribution
    age_dist = compute_age_distribution(participants, ready_ids)

    lines += ["## Age x Sex Distribution (Normative-Eligible Subjects)\n",
              "| Age Bin | Male | Female | Unknown | Total | Thin? |",
              "|---------|------|--------|---------|-------|-------|"]
    for lo, hi in AGE_BINS:
        label = f"{lo}-{hi}"
        counts = age_dist["bins"].get(label, {"M": 0, "F": 0, "?": 0, "total": 0})
        thin = "YES" if label in age_dist["thin_bins"] else ""
        lines.append(f"| {label} | {counts['M']} | {counts['F']} | "
                     f"{counts['?']} | {counts['total']} | {thin} |")
    lines.append("")

    if age_dist["thin_bins"]:
        lines.append(f"**Warning:** Thin bins (<{THIN_BIN_THRESHOLD} subjects): "
                     f"{', '.join(age_dist['thin_bins'])}\n")

    # Demographics summary
    ages = []
    sex_counts = {"M": 0, "F": 0, "?": 0}
    for sid in ready_ids:
        demo = participants.get(sid, {})
        age = demo.get("age", float("nan"))
        sex = demo.get("sex", "?")
        if not math.isnan(age):
            ages.append(age)
        sex_counts[sex if sex in ("M", "F") else "?"] += 1

    if ages:
        lines += [
            "## Demographics Summary (Normative-Eligible)\n",
            f"- Age range: {min(ages):.0f} - {max(ages):.0f}",
            f"- Mean age: {np.mean(ages):.1f} (SD {np.std(ages):.1f})",
            f"- Male: {sex_counts['M']}, Female: {sex_counts['F']}, Unknown: {sex_counts['?']}",
            "",
        ]

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

    # Subject table
    lines += ["## Per-Subject Results\n",
              "| Subject | Status | EC | EO | Issues |",
              "|---------|--------|----|----|--------|"]
    for r in results:
        has_ec = "yes" if r.get("condition_files", {}).get("ec_file") else "MISSING"
        has_eo = "yes" if r.get("condition_files", {}).get("eo_file") else "MISSING"
        issues_str = "; ".join(
            f"[{i['severity']}] {i['message']}" for i in r.get("issues", [])
        )
        if len(issues_str) > 80:
            issues_str = issues_str[:77] + "..."
        lines.append(f"| {r['subject_id']} | {r['status']} | "
                     f"{has_ec} | {has_eo} | {issues_str} |")
    lines.append("")

    (output_dir / "qc_summary.md").write_text("\n".join(lines) + "\n")

    # --- Counts JSON ---
    counts = {
        "total": len(results),
        "pass": n_pass,
        "warn": n_warn,
        "fail": n_fail,
        "normative_eligible": len(ready_ids),
        "issue_counts": issue_counts,
    }
    with open(output_dir / "qc_counts.json", "w") as f:
        json.dump(counts, f, indent=2)

    # --- Age distribution JSON ---
    with open(output_dir / "age_distribution.json", "w") as f:
        json.dump(age_dist, f, indent=2)

    # --- Channel mapping JSON (from first subject with data) ---
    if channel_mapping:
        mapping_out = {
            "source_system": "BrainVision 64ch",
            "source_naming": "10-10",
            "target_naming": "10-20 (19 channels)",
            "line_frequency_hz": LINE_FREQ,
            "reference_channel": REFERENCE_CHANNEL,
            "mapping": channel_mapping["mapping_1020"],
            "additional_channels": channel_mapping["additional_1010"],
        }
        with open(output_dir / "channel_mapping.json", "w") as f:
            json.dump(mapping_out, f, indent=2)

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for Test-Retest EEG data "
                    "(ds004148, 64-ch BrainVision, ages 18-28, 50 Hz China)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir", type=Path,
        help="Path to TRT BIDS data root (e.g. ~/Data/EEG/TRT/)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("./trt_qc_output"),
        help="Output directory (default: ./trt_qc_output)",
    )
    parser.add_argument(
        "--max-subjects", type=int, default=0,
        help="Limit to N subjects (0 = all, useful for testing)",
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

    log.info("Test-Retest EEG (ds004148) QC")
    log.info("Data directory: %s", args.data_dir)
    log.info("Line frequency: %.0f Hz", LINE_FREQ)

    # Load demographics
    participants = load_participants(args.data_dir)
    log.info("Loaded demographics for %d subjects", len(participants))

    # Discover BIDS structure
    log.info("Discovering BIDS task structure...")
    task_discovery = discover_tasks(args.data_dir)
    for task, count in sorted(task_discovery.items()):
        log.info("  task-%s: %d files", task, count)

    # Discover subjects
    all_subjects = discover_subjects(args.data_dir)
    log.info("Found %d subjects in session 1", len(all_subjects))

    n_both = sum(1 for s in all_subjects if s["ec_file"] and s["eo_file"])
    n_ec_only = sum(1 for s in all_subjects if s["ec_file"] and not s["eo_file"])
    n_eo_only = sum(1 for s in all_subjects if not s["ec_file"] and s["eo_file"])
    log.info("  Both EC+EO: %d", n_both)
    log.info("  EC only:    %d", n_ec_only)
    log.info("  EO only:    %d", n_eo_only)

    # Resumability — skip already QC'd
    done = load_existing_qc(subjects_dir)
    if done:
        log.info("Found %d existing QC results — will skip those", len(done))

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

    # --- Load all results (including previously checkpointed) ---
    all_results = load_all_results(subjects_dir)
    log.info("Total results: %d", len(all_results))

    # --- Extract channel mapping from first successful result ---
    channel_mapping = None
    for r in all_results:
        if "channel_mapping" in r and r["channel_mapping"].get("present_19"):
            channel_mapping = r["channel_mapping"]
            break

    # --- Write all outputs ---
    log.info("Writing output files...")
    write_outputs(output_dir, all_results, participants, channel_mapping,
                  task_discovery)

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
    log.info("  %s", output_dir / "qc_counts.json")
    log.info("  %s", output_dir / "age_distribution.json")
    log.info("  %s", output_dir / "channel_mapping.json")
    log.info("  %s", output_dir / "ready_subjects.txt")
    log.info("  %s", output_dir / "excluded_subjects.txt")
    log.info("  %s/ (per-subject JSONs)", subjects_dir)


if __name__ == "__main__":
    main()
