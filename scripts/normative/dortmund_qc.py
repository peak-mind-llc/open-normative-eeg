#!/usr/bin/env python3
"""QC sweep for Dortmund Vital Study EEG data.

Loads each subject's raw BrainVision files and produces a QC report
covering BIDS structure, recording parameters, channel mapping,
signal quality, condition verification, and age distribution.

The Dortmund study recorded EEG in four resting blocks per session:
  - Pre-task resting EO (3 min)
  - Pre-task resting EC (3 min)
  - [2 hours of cognitive tasks]
  - Post-task resting EO (3 min)
  - Post-task resting EC (3 min)

For normative purposes, only pre-task resting data from session 1 is used.
Post-task data may be contaminated by cognitive fatigue effects.
Session 2 (follow-up) data is flagged for longitudinal analysis only.

Usage:
    # Quick test with 3 subjects
    python scripts/normative/dortmund_qc.py ~/datasets/dortmund/ \\
        -o ./dortmund_qc --max-subjects 3

    # Full QC sweep, 4 parallel workers
    python scripts/normative/dortmund_qc.py ~/datasets/dortmund/ \\
        -o ./dortmund_qc -w 4

    # Skip pre/post spectral comparison
    python scripts/normative/dortmund_qc.py ~/datasets/dortmund/ \\
        -o ./dortmund_qc --skip-pre-post
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import multiprocessing
import random
import re
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

# Recording parameters — accept either 500 or 1000 Hz
ACCEPTED_SFREQS = {500.0, 1000.0}
EXPECTED_N_CHANNELS = 64
REFERENCE_CHANNEL = "FCz"  # Online reference, expected absent from data
LINE_FREQ = 50.0  # European mains — CRITICAL

# Non-EEG channel patterns (discovered channels matching these are excluded
# from signal quality checks)
NON_EEG_PATTERNS = {"VEOG", "HEOG", "ECG", "EMG", "EOG", "BIP", "AUX",
                     "GSR", "RESP", "TEMP"}

# Duration thresholds per condition block (~3 min expected)
MIN_DURATION_S = 120.0        # 2 min — fail below this
EXPECTED_DURATION_S = 180.0   # 3 min expected
MAX_DURATION_S = 300.0        # 5 min — warn above this

# Signal quality thresholds (adult, same as LEMON)
FLAT_VARIANCE_UV2 = 0.1       # uV^2 — below this, channel is flat
RAILED_AMPLITUDE_UV = 500.0   # uV — above this, channel may be railed
RAILED_FRACTION = 0.10        # >10% of samples railed -> flag
NOISE_SD_THRESHOLD = 3.0      # 50 Hz power > 3 SD above mean -> flag
MEDIAN_AMP_WARN_UV = 200.0    # overall median amplitude warning
ARTIFACT_EPOCH_SEC = 1.0      # epoch length for gross artifact check
ARTIFACT_CHAN_FRACTION = 0.50  # >50% channels exceed threshold -> artifact
ARTIFACT_AMP_UV = 200.0       # uV per-channel threshold for artifacts
ARTIFACT_PCT_WARN = 20.0      # % — warn above this
ARTIFACT_PCT_FAIL = 50.0      # % — fail above this
DC_OFFSET_WARN_UV = 100.0     # uV — warn if |offset| exceeds this

# Age bins
AGE_BINS_5Y = [
    (20, 24), (25, 29), (30, 34), (35, 39), (40, 44),
    (45, 49), (50, 54), (55, 59), (60, 64), (65, 70),
]
AGE_BINS_DECADE = [(20, 29), (30, 39), (40, 49), (50, 59), (60, 70)]
THIN_BIN_THRESHOLD = 15  # flag bins with fewer than this

# Pre/post comparison bands
PRE_POST_BANDS = {
    "Delta": [1, 4],
    "Theta": [4, 8],
    "Alpha": [8, 13],
    "Beta": [13, 30],
}
PRE_POST_SAMPLE_SIZE = 20

# Reverse name map: 10-20 name -> 10-10 source name
_REVERSE_NAME_MAP = {v: k for k, v in _NAME_MAP.items()}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging to both console and error log file."""
    logger = logging.getLogger("dortmund_qc")
    logger.setLevel(logging.INFO)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    error_log = output_dir / "qc_errors.log"
    file_handler = logging.FileHandler(error_log)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(file_handler)

    return logger


logger = logging.getLogger("dortmund_qc")


# ---------------------------------------------------------------------------
# Channel mapping: 64-channel 10-10 -> 19-channel 10-20
# ---------------------------------------------------------------------------

def build_channel_mapping(ch_names: list[str]) -> dict:
    """Build mapping from 64-channel 10-10 layout to 19-channel 10-20 subset.

    Dortmund uses standard 10-10 names, so the 19 standard 10-20 channels
    are a direct subset (with T7->T3, T8->T4, P7->T5, P8->T6 renaming).

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
    """Parse participants.tsv for age, sex, handedness.

    Returns {subject_id: {"age": float, "sex": str, "handedness": str}}.
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

            # Age — numeric or range
            raw_age = row.get("age", "").strip()
            try:
                age = float(raw_age)
            except (ValueError, TypeError):
                age = float("nan")

            # Sex
            raw_sex = row.get("sex", row.get("gender", "")).strip().upper()
            if raw_sex.startswith("M"):
                sex = "M"
            elif raw_sex.startswith("F"):
                sex = "F"
            else:
                sex = raw_sex

            # Handedness
            hand = row.get("handedness", row.get("hand", "")).strip()

            participants[sid] = {"age": age, "sex": sex, "handedness": hand}

    return participants


def _parse_bids_entities(filepath: Path) -> dict[str, str]:
    """Extract BIDS entities from a filename.

    E.g. 'sub-001_ses-1_task-restEO_run-01_eeg.vhdr'
    -> {'sub': '001', 'ses': '1', 'task': 'restEO', 'run': '01'}
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


def _find_eeg_files(data_dir: Path) -> list[Path]:
    """Find all EEG data files (.edf, .vhdr, .set) in a BIDS tree."""
    files = []
    for ext in ("*.edf", "*.vhdr", "*.set"):
        files.extend(data_dir.glob(f"sub-*/ses-*/eeg/{ext}"))
        files.extend(data_dir.glob(f"sub-*/eeg/{ext}"))
    return sorted(set(files))


def discover_tasks(data_dir: Path) -> dict[str, dict]:
    """Scan all EEG files to discover unique BIDS task, acq, and run labels.

    Returns {task_name: {"count": int, "runs": [...], "acqs": [...]}}.
    Called once at startup for reporting.
    """
    eeg_files = _find_eeg_files(data_dir)

    task_info: dict[str, dict] = {}
    for f in eeg_files:
        entities = _parse_bids_entities(f)
        task = entities.get("task", "unknown")
        run = entities.get("run", "")
        acq = entities.get("acq", "")

        if task not in task_info:
            task_info[task] = {"count": 0, "runs": set(), "acqs": set()}
        task_info[task]["count"] += 1
        if run:
            task_info[task]["runs"].add(run)
        if acq:
            task_info[task]["acqs"].add(acq)

    # Convert sets to sorted lists
    for info in task_info.values():
        info["runs"] = sorted(info["runs"])
        info["acqs"] = sorted(info["acqs"])

    return task_info


def _classify_condition(task: str) -> str | None:
    """Classify a BIDS task label as 'eo' or 'ec', or None if unrecognized."""
    t = task.lower()
    eo_patterns = ["eo", "eyesopen", "eyes_open", "open"]
    ec_patterns = ["ec", "eyesclosed", "eyes_closed", "closed"]

    for pat in eo_patterns:
        if pat in t:
            return "eo"
    for pat in ec_patterns:
        if pat in t:
            return "ec"
    return None


def classify_resting_files(eeg_files: list[Path]) -> dict:
    """Classify EEG files into pre-task and post-task, EO and EC.

    Supports multiple BIDS conventions:
    - task-EyesOpen/task-EyesClosed with acq-pre/acq-post (Dortmund)
    - task-restEO/task-restEC with run-01/run-02
    - 'pre'/'post' in task name

    Returns dict with pre_eo, pre_ec, post_eo, post_ec paths (or None),
    plus classification_method and unclassified file list.
    """
    result = {
        "pre_eo": None, "pre_ec": None,
        "post_eo": None, "post_ec": None,
        "classification_method": "none",
        "all_eeg_files": [str(f) for f in eeg_files],
        "unclassified": [],
    }

    if not eeg_files:
        return result

    # Parse entities for each file
    parsed = []
    for f in eeg_files:
        entities = _parse_bids_entities(f)
        condition = _classify_condition(entities.get("task", ""))
        acq = entities.get("acq", "").lower()
        run = entities.get("run", "")
        task = entities.get("task", "").lower()

        # Determine pre/post timing from acq, task name, or run
        timing = None
        if acq in ("pre", "pretask"):
            timing = "pre"
        elif acq in ("post", "posttask"):
            timing = "post"
        elif "pre" in task:
            timing = "pre"
        elif "post" in task:
            timing = "post"

        parsed.append({
            "path": f, "entities": entities,
            "condition": condition, "timing": timing, "run": run,
        })

    # Group by condition
    eo_files = [p for p in parsed if p["condition"] == "eo"]
    ec_files = [p for p in parsed if p["condition"] == "ec"]
    rest_files = [p for p in parsed if p["condition"] is None]

    # If no EO/EC classification from task names, mark as unclassified
    if not eo_files and not ec_files and rest_files:
        result["unclassified"] = [str(p["path"]) for p in rest_files]
        result["classification_method"] = "unresolved_rest_task"
        return result

    def _assign_pre_post(files: list[dict], condition: str):
        """Assign pre/post from acq entity, task name, or run numbers."""
        if len(files) == 0:
            return

        # Strategy 1: acq-pre / acq-post (Dortmund convention)
        pre_acq = [f for f in files if f["timing"] == "pre"]
        post_acq = [f for f in files if f["timing"] == "post"]

        if pre_acq:
            result[f"pre_{condition}"] = pre_acq[0]["path"]
            if result["classification_method"] == "none":
                result["classification_method"] = "acq_entity"
        if post_acq:
            result[f"post_{condition}"] = post_acq[0]["path"]
            if result["classification_method"] == "none":
                result["classification_method"] = "acq_entity"

        if pre_acq or post_acq:
            return

        # Strategy 2: run numbers (run-01 = pre, run-02 = post)
        files_sorted = sorted(files, key=lambda p: p["run"] or "00")
        if len(files_sorted) >= 2:
            result[f"pre_{condition}"] = files_sorted[0]["path"]
            result[f"post_{condition}"] = files_sorted[1]["path"]
            if result["classification_method"] == "none":
                result["classification_method"] = "run_number"
            return

        # Strategy 3: single file — assume pre-task
        if len(files_sorted) == 1:
            result[f"pre_{condition}"] = files_sorted[0]["path"]
            if result["classification_method"] == "none":
                result["classification_method"] = "single_file_assumed_pre"

    _assign_pre_post(eo_files, "eo")
    _assign_pre_post(ec_files, "ec")

    # Mark remaining unclassified
    classified_paths = {result[k] for k in ("pre_eo", "pre_ec", "post_eo", "post_ec")
                        if result[k] is not None}
    result["unclassified"] = [
        str(p["path"]) for p in parsed
        if p["path"] not in classified_paths and p["condition"] is None
    ]

    return result


def discover_subjects(data_dir: Path) -> list[dict]:
    """Discover all subjects, sessions, and resting-state files.

    Returns list of dicts:
    {
        "subject_id": str,
        "sessions": [str],
        "has_session_2": bool,
        "ses1_files": classify_resting_files result for session 1,
        "ses2_files": classify_resting_files result for session 2 or None,
    }
    """
    # Find all subject directories
    subject_dirs = set()
    for pattern in ["sub-*/ses-*/eeg", "sub-*/eeg"]:
        for eeg_dir in sorted(data_dir.glob(pattern)):
            # Walk up to find subject dir
            for part in eeg_dir.parts:
                if part.startswith("sub-"):
                    subject_dirs.add(data_dir / part)
                    break

    subjects = []
    for sub_dir in sorted(subject_dirs):
        subject_id = sub_dir.name
        info = {"subject_id": subject_id, "sessions": [], "has_session_2": False,
                "ses1_files": None, "ses2_files": None}

        # Check for session directories
        ses_dirs = sorted(sub_dir.glob("ses-*"))
        if ses_dirs:
            for ses_dir in ses_dirs:
                ses_label = ses_dir.name
                info["sessions"].append(ses_label)
                eeg_dir = ses_dir / "eeg"
                if not eeg_dir.exists():
                    continue
                eeg_data_files = sorted(
                    list(eeg_dir.glob("*.edf"))
                    + list(eeg_dir.glob("*.vhdr"))
                    + list(eeg_dir.glob("*.set"))
                )
                classified = classify_resting_files(eeg_data_files)

                # First session found -> ses1, second -> ses2
                if info["ses1_files"] is None:
                    info["ses1_files"] = classified
                else:
                    info["ses2_files"] = classified
                    info["has_session_2"] = True
        else:
            # Sessionless BIDS layout
            eeg_dir = sub_dir / "eeg"
            if eeg_dir.exists():
                eeg_data_files = sorted(
                    list(eeg_dir.glob("*.edf"))
                    + list(eeg_dir.glob("*.vhdr"))
                    + list(eeg_dir.glob("*.set"))
                )
                info["ses1_files"] = classify_resting_files(eeg_data_files)
                info["sessions"].append("")

        subjects.append(info)

    return subjects


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

_EEG_LOADERS = {
    ".vhdr": mne.io.read_raw_brainvision,
    ".edf": mne.io.read_raw_edf,
    ".set": mne.io.read_raw_eeglab,
}


def _load_eeg(filepath: Path):
    """Load an EEG file by extension. Returns mne.io.Raw."""
    ext = filepath.suffix.lower()
    loader = _EEG_LOADERS.get(ext)
    if loader is None:
        raise ValueError(f"Unsupported EEG format: {ext}")
    return loader(str(filepath), preload=True, verbose=False)


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def _is_eeg_channel(ch_name: str) -> bool:
    """Return True if channel name looks like an EEG channel."""
    return not any(p in ch_name.upper() for p in NON_EEG_PATTERNS)


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
    if sfreq not in ACCEPTED_SFREQS:
        issues.append(("fail", f"sfreq={sfreq}, expected one of {sorted(ACCEPTED_SFREQS)}"))

    # Channel count
    if n_channels < 50:
        issues.append(("fail", f"n_channels={n_channels}, expected ~{EXPECTED_N_CHANNELS}"))
    elif n_channels != EXPECTED_N_CHANNELS:
        issues.append(("warn", f"n_channels={n_channels}, expected {EXPECTED_N_CHANNELS}"))

    # Duration (per condition block, ~3 min expected)
    if duration_sec < MIN_DURATION_S:
        issues.append(("fail", f"duration={duration_min:.1f} min, below {MIN_DURATION_S / 60:.0f} min minimum"))
    elif duration_sec > MAX_DURATION_S:
        issues.append(("warn", f"duration={duration_min:.1f} min, above {MAX_DURATION_S / 60:.0f} min expected max"))

    # Data scale check
    median_amp = float(np.median(np.abs(data_uv)))
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

    # FCz reference check — expect absent
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

    # Flat channels
    variances = np.var(eeg_data, axis=1)
    flat = [eeg_names[i] for i in range(len(eeg_names))
            if variances[i] < FLAT_VARIANCE_UV2]
    if flat:
        issues.append(("warn", f"flat channels (var<{FLAT_VARIANCE_UV2} uV^2): {', '.join(flat)}"))

    # Railed channels
    railed = []
    for i, ch in enumerate(eeg_names):
        frac = float(np.mean(np.abs(eeg_data[i]) > RAILED_AMPLITUDE_UV))
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

    # Per-channel median absolute amplitude
    per_ch_median = {ch: round(float(np.median(np.abs(eeg_data[j]))), 2)
                     for j, ch in enumerate(eeg_names)}
    overall_median = float(np.median(np.abs(eeg_data)))

    # Gross artifact detection — 1-second epochs
    epoch_samples = int(ARTIFACT_EPOCH_SEC * sfreq)
    n_epochs = eeg_data.shape[1] // epoch_samples
    n_artifact_epochs = 0

    for e in range(n_epochs):
        start = e * epoch_samples
        end = start + epoch_samples
        epoch = eeg_data[:, start:end]
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
    if large_offset:
        issues.append(("warn", f"large DC offset (>{DC_OFFSET_WARN_UV} uV): {', '.join(large_offset)}"))

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
# Condition verification and events parsing
# ---------------------------------------------------------------------------

def _parse_events_tsv(eeg_path: Path) -> list[dict]:
    """Parse BIDS _events.tsv companion for an EEG file.

    Returns list of {onset, duration, trial_type} dicts.
    """
    eeg_path = Path(eeg_path)
    stem = eeg_path.name
    for suffix in ("_eeg.edf", "_eeg.vhdr", "_eeg.eeg", "_eeg.vmrk",
                    "_eeg.set", ".edf", ".vhdr", ".set"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    events_path = eeg_path.parent / f"{stem}_events.tsv"
    if not events_path.exists():
        return []

    events = []
    try:
        with events_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                try:
                    onset = float(row.get("onset", "nan"))
                    duration = float(row.get("duration", "0") or "0")
                except (ValueError, TypeError):
                    continue
                trial_type = row.get(
                    "trial_type",
                    row.get("value", row.get("description", ""))
                ).strip()
                events.append({
                    "onset": onset,
                    "duration": duration,
                    "trial_type": trial_type,
                })
    except Exception:
        pass
    return events


def check_condition_markers(raw, eeg_path: Path) -> tuple[dict, list]:
    """Check for condition markers in events file and raw annotations.

    Returns (metrics_dict, issues_list).
    """
    issues = []

    # Try BIDS events.tsv first
    bids_events = _parse_events_tsv(eeg_path)
    has_events_tsv = len(bids_events) > 0

    # Collect unique event types
    unique_events = sorted(set(ev["trial_type"] for ev in bids_events)) if bids_events else []

    # Classify events as EO or EC
    eo_keywords = {"eyesopen", "eyes_open", "eyes open", "open", "eo"}
    ec_keywords = {"eyesclosed", "eyes_closed", "eyes closed", "closed", "ec"}

    eo_duration = 0.0
    ec_duration = 0.0
    for ev in bids_events:
        tt = ev["trial_type"].lower().strip()
        if tt in eo_keywords:
            eo_duration += ev["duration"]
        elif tt in ec_keywords:
            ec_duration += ev["duration"]

    # Fall back to raw annotations
    ann_count = len(raw.annotations)
    ann_events = sorted(set(a["description"] for a in raw.annotations)) if ann_count else []

    if not has_events_tsv and ann_count > 0:
        for ann in raw.annotations:
            desc = ann["description"].lower().strip()
            dur = float(ann["duration"]) if ann["duration"] else 0.0
            if desc in eo_keywords:
                eo_duration += dur
            elif desc in ec_keywords:
                ec_duration += dur

    # Condition detected from filename
    entities = _parse_bids_entities(eeg_path)
    condition_from_task = _classify_condition(entities.get("task", ""))

    metrics = {
        "has_events_tsv": has_events_tsv,
        "n_bids_events": len(bids_events),
        "unique_event_types": unique_events[:20],
        "eo_duration_sec": round(eo_duration, 1),
        "ec_duration_sec": round(ec_duration, 1),
        "annotation_count": ann_count,
        "annotation_events": ann_events[:20],
        "condition_from_filename": condition_from_task,
    }
    return metrics, issues


# ---------------------------------------------------------------------------
# Pre-task vs post-task spectral comparison
# ---------------------------------------------------------------------------

def _compute_band_power_simple(raw, bands: dict) -> dict[str, float]:
    """Compute mean absolute band power across EEG channels using Welch PSD.

    Returns {band_name: mean_log10_power_across_channels}.
    Lightweight — used for pre/post QC comparison only.
    """
    # Pick only EEG channels
    raw_eeg = raw.copy().pick("eeg")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="nperseg.*greater than input length")
        spectrum = raw_eeg.compute_psd(
            method="welch", fmin=0.5, fmax=50.0, n_fft=1024, verbose=False,
        )
    psds = spectrum.get_data()  # V^2/Hz
    freqs = spectrum.freqs

    result = {}
    for band_name, (fmin, fmax) in bands.items():
        idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
        if len(idx) == 0:
            result[band_name] = 0.0
            continue
        abs_power = np.trapezoid(psds[:, idx], freqs[idx], axis=1)
        # Mean log10 power across channels (avoid log of zero)
        safe_power = np.where(abs_power > 0, abs_power, 1e-30)
        result[band_name] = float(np.mean(np.log10(safe_power)))

    return result


def _find_alpha_peak(raw) -> float | None:
    """Find alpha peak frequency (8-13 Hz) from mean PSD across channels."""
    raw_eeg = raw.copy().pick("eeg")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="nperseg.*greater than input length")
        spectrum = raw_eeg.compute_psd(
            method="welch", fmin=8.0, fmax=13.0, n_fft=1024, verbose=False,
        )
    psds = spectrum.get_data()
    freqs = spectrum.freqs
    mean_psd = np.mean(psds, axis=0)
    if len(mean_psd) == 0:
        return None
    return float(freqs[np.argmax(mean_psd)])


def compare_pre_post(pre_path: Path, post_path: Path) -> dict | None:
    """Compare spectral metrics between pre-task and post-task files.

    Returns dict with per-band log10 power difference and alpha peak shift,
    or None if either file cannot be loaded.
    """
    try:
        pre_raw = _load_eeg(pre_path)
        post_raw = _load_eeg(post_path)
    except Exception as e:
        logger.warning("Pre/post comparison load error: %s", e)
        return None

    pre_power = _compute_band_power_simple(pre_raw, PRE_POST_BANDS)
    post_power = _compute_band_power_simple(post_raw, PRE_POST_BANDS)

    band_diffs = {}
    for band in PRE_POST_BANDS:
        diff = post_power[band] - pre_power[band]
        band_diffs[band] = {
            "pre_log10": round(pre_power[band], 4),
            "post_log10": round(post_power[band], 4),
            "diff_log10": round(diff, 4),
        }

    # Alpha peak frequency shift
    pre_peak = _find_alpha_peak(pre_raw)
    post_peak = _find_alpha_peak(post_raw)
    alpha_peak_shift = None
    if pre_peak is not None and post_peak is not None:
        alpha_peak_shift = round(post_peak - pre_peak, 2)

    return {
        "band_differences": band_diffs,
        "alpha_peak_pre_hz": pre_peak,
        "alpha_peak_post_hz": post_peak,
        "alpha_peak_shift_hz": alpha_peak_shift,
    }


def run_pre_post_comparison(subjects: list[dict], n_sample: int = 20) -> dict:
    """Run pre/post comparison on a sample of subjects.

    Selects up to n_sample subjects that have both pre and post EO files.
    Returns aggregate summary with per-band statistics and effect sizes.
    """
    # Find eligible subjects (have both pre and post for at least one condition)
    eligible = []
    for sub in subjects:
        ses1 = sub.get("ses1_files")
        if ses1 is None:
            continue
        if ses1.get("pre_eo") and ses1.get("post_eo"):
            eligible.append(("eo", sub))
        elif ses1.get("pre_ec") and ses1.get("post_ec"):
            eligible.append(("ec", sub))

    if not eligible:
        return {"n_subjects": 0, "note": "no subjects with both pre and post files"}

    sample = eligible[:n_sample] if len(eligible) <= n_sample else random.sample(eligible, n_sample)

    comparisons = []
    compared_ids = []
    for condition, sub in sample:
        ses1 = sub["ses1_files"]
        pre_key = f"pre_{condition}"
        post_key = f"post_{condition}"
        result = compare_pre_post(Path(ses1[pre_key]), Path(ses1[post_key]))
        if result is not None:
            result["condition"] = condition
            comparisons.append(result)
            compared_ids.append(sub["subject_id"])

    if not comparisons:
        return {"n_subjects": 0, "note": "all pre/post comparisons failed"}

    # Aggregate per-band statistics
    band_stats = {}
    for band in PRE_POST_BANDS:
        diffs = [c["band_differences"][band]["diff_log10"] for c in comparisons]
        mean_diff = float(np.mean(diffs))
        std_diff = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0.0
        band_stats[band] = {
            "mean_diff_log10": round(mean_diff, 4),
            "std_diff_log10": round(std_diff, 4),
            "cohens_d": round(cohens_d, 3),
        }

    # Alpha peak shift
    peak_shifts = [c["alpha_peak_shift_hz"] for c in comparisons
                   if c["alpha_peak_shift_hz"] is not None]
    mean_peak_shift = round(float(np.mean(peak_shifts)), 2) if peak_shifts else None

    # Narrative findings
    findings = []
    theta_d = band_stats.get("Theta", {}).get("cohens_d", 0)
    alpha_d = band_stats.get("Alpha", {}).get("cohens_d", 0)
    if theta_d > 0.2:
        findings.append(f"Post-task theta increase detected (d={theta_d:.2f}) — consistent with fatigue")
    if alpha_d < -0.2:
        findings.append(f"Post-task alpha decrease detected (d={alpha_d:.2f}) — consistent with fatigue")
    if mean_peak_shift is not None and mean_peak_shift < -0.3:
        findings.append(f"Alpha peak slowing detected ({mean_peak_shift:+.2f} Hz)")
    if not findings:
        findings.append("No strong pre/post differences detected in this sample")

    return {
        "n_subjects": len(comparisons),
        "subjects_compared": compared_ids,
        "band_statistics": band_stats,
        "mean_alpha_peak_shift_hz": mean_peak_shift,
        "fatigue_signatures": findings,
        "per_subject": comparisons,
    }


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
    """Check if a subject is eligible for cross-sectional normative database.

    Requires:
    - Status is 'pass' or 'warn' (not 'fail')
    - Session 1 pre-task EO and EC files both present
    - Valid age and sex demographics
    """
    if result["status"] == "fail":
        return False
    ses1 = result.get("condition_files", {})
    if not ses1.get("pre_eo") or not ses1.get("pre_ec"):
        return False
    demo = participants.get(result["subject_id"], {})
    if math.isnan(demo.get("age", float("nan"))):
        return False
    if demo.get("sex", "") not in ("M", "F"):
        return False
    return True


# ---------------------------------------------------------------------------
# Per-subject QC worker
# ---------------------------------------------------------------------------

def _run_checks_on_file(eeg_path: Path) -> dict:
    """Load a single EEG file and run all signal-level checks.

    Supports .edf (Dortmund), .vhdr (BrainVision), .set (EEGLAB).
    Returns dict with integrity, channels, signal_quality, markers sections.
    """
    result = {
        "source_file": str(eeg_path),
        "integrity": {},
        "channels": {},
        "signal_quality": {},
        "markers": {},
        "issues": [],
    }

    try:
        raw = _load_eeg(eeg_path)
    except Exception as exc:
        result["issues"] = [("fail", f"load error: {exc}")]
        return result

    data_uv = raw.get_data() * 1e6
    all_issues = []

    # Channel mapping (computed once per file)
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

    # 4. Condition markers
    try:
        metrics, issues = check_condition_markers(raw, vhdr_path)
        result["markers"] = metrics
        all_issues.extend(issues)
    except Exception as exc:
        all_issues.append(("fail", f"marker check error: {exc}"))

    result["issues"] = all_issues
    result["channel_mapping"] = ch_mapping
    return result


def qc_one_subject(subject_info: dict) -> dict:
    """Run all QC checks on one Dortmund subject.

    Processes session 1 pre-task files (primary QC target).
    Records existence of session 2 and post-task files as metadata.
    """
    subject_id = subject_info["subject_id"]
    ses1 = subject_info.get("ses1_files") or {}

    result = {
        "subject_id": subject_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "issues": [],
        "session_info": {
            "sessions": subject_info.get("sessions", []),
            "has_session_2": subject_info.get("has_session_2", False),
        },
        "condition_files": {
            "pre_eo": str(ses1.get("pre_eo")) if ses1.get("pre_eo") else None,
            "pre_ec": str(ses1.get("pre_ec")) if ses1.get("pre_ec") else None,
            "post_eo": str(ses1.get("post_eo")) if ses1.get("post_eo") else None,
            "post_ec": str(ses1.get("post_ec")) if ses1.get("post_ec") else None,
            "classification_method": ses1.get("classification_method", "none"),
        },
        "pre_eo": {},
        "pre_ec": {},
    }

    # Check for missing pre-task files
    all_issues = []
    if not ses1.get("pre_eo"):
        all_issues.append(("fail", "no pre-task EO file found"))
    if not ses1.get("pre_ec"):
        all_issues.append(("fail", "no pre-task EC file found"))

    # QC pre-task EO
    channel_mapping = None
    if ses1.get("pre_eo"):
        eo_result = _run_checks_on_file(Path(ses1["pre_eo"]))
        result["pre_eo"] = {
            "integrity": eo_result["integrity"],
            "channels": eo_result["channels"],
            "signal_quality": eo_result["signal_quality"],
            "markers": eo_result["markers"],
        }
        all_issues.extend(
            (sev, f"[EO] {msg}") for sev, msg in eo_result["issues"]
        )
        channel_mapping = eo_result.get("channel_mapping")

    # QC pre-task EC
    if ses1.get("pre_ec"):
        ec_result = _run_checks_on_file(Path(ses1["pre_ec"]))
        result["pre_ec"] = {
            "integrity": ec_result["integrity"],
            "channels": ec_result["channels"],
            "signal_quality": ec_result["signal_quality"],
            "markers": ec_result["markers"],
        }
        all_issues.extend(
            (sev, f"[EC] {msg}") for sev, msg in ec_result["issues"]
        )
        if channel_mapping is None:
            channel_mapping = ec_result.get("channel_mapping")

    # Store channel mapping (from first successfully loaded file)
    if channel_mapping:
        result["channel_mapping"] = {
            "mapping_1020": channel_mapping["mapping_1020"],
            "present_19": channel_mapping["present_19"],
            "missing_19": channel_mapping["missing_19"],
            "additional_1010": channel_mapping["additional_1010"],
        }

    # Build structured issues list and determine status
    result["issues"] = [
        {"severity": sev, "message": msg} for sev, msg in all_issues
    ]
    result["status"] = determine_status(all_issues)

    return result


# ---------------------------------------------------------------------------
# Age distribution
# ---------------------------------------------------------------------------

def _age_bin_5y(age: float) -> str | None:
    """Return 5-year age bin label, or None if outside range."""
    for lo, hi in AGE_BINS_5Y:
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return None


def _age_bin_decade(age: float) -> str | None:
    """Return decade age bin label, or None if outside range."""
    for lo, hi in AGE_BINS_DECADE:
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return None


def compute_age_distribution(participants: dict, subject_ids: set[str]) -> dict:
    """Compute age distribution for a set of subjects.

    Returns dict with 5-year bins and decade bins, each with M/F/total counts.
    """
    bins_5y: dict[str, dict] = {}
    bins_decade: dict[str, dict] = {}

    for sid in sorted(subject_ids):
        demo = participants.get(sid, {})
        age = demo.get("age", float("nan"))
        sex = demo.get("sex", "?")
        if math.isnan(age):
            continue

        label_5y = _age_bin_5y(age)
        if label_5y:
            bins_5y.setdefault(label_5y, {"M": 0, "F": 0, "?": 0, "total": 0})
            bins_5y[label_5y][sex if sex in ("M", "F") else "?"] += 1
            bins_5y[label_5y]["total"] += 1

        label_dec = _age_bin_decade(age)
        if label_dec:
            bins_decade.setdefault(label_dec, {"M": 0, "F": 0, "?": 0, "total": 0})
            bins_decade[label_dec][sex if sex in ("M", "F") else "?"] += 1
            bins_decade[label_dec]["total"] += 1

    # Flag thin bins
    thin_5y = [label for label, counts in bins_5y.items()
               if counts["total"] < THIN_BIN_THRESHOLD]
    thin_decade = [label for label, counts in bins_decade.items()
                   if counts["total"] < THIN_BIN_THRESHOLD]

    return {
        "bins_5y": bins_5y,
        "bins_decade": bins_decade,
        "thin_bins_5y": thin_5y,
        "thin_bins_decade": thin_decade,
        "thin_threshold": THIN_BIN_THRESHOLD,
    }


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def write_outputs(output_dir: Path, results: list[dict],
                  participants: dict, channel_mapping: dict | None,
                  pre_post: dict | None, task_discovery: dict):
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

    # Session 2 subjects
    ses2_ids = sorted(r["subject_id"] for r in results
                      if r.get("session_info", {}).get("has_session_2", False))

    # --- Summary markdown ---
    lines = [
        "# Dortmund Vital Study EEG — QC Report\n",
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
    for task, info in sorted(task_discovery.items()):
        runs = ", ".join(info["runs"]) if info["runs"] else "none"
        acqs = ", ".join(info.get("acqs", [])) if info.get("acqs") else "none"
        lines.append(f"- **{task}**: {info['count']} files (runs: {runs}, acqs: {acqs})")
    lines.append("")

    # Session inventory
    n_ses1_only = sum(1 for r in results
                      if not r.get("session_info", {}).get("has_session_2", False))
    lines += [
        "## Session Inventory\n",
        f"- Session 1 only: {n_ses1_only}",
        f"- Session 1 + Session 2: {len(ses2_ids)}",
        f"- **Session 2 subjects are flagged for longitudinal analysis only**",
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

    # Channel issues aggregate
    flat_all: dict[str, int] = {}
    railed_all: dict[str, int] = {}
    noise_all: dict[str, int] = {}
    for r in results:
        for cond in ("pre_eo", "pre_ec"):
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
    for lo, hi in AGE_BINS_5Y:
        label = f"{lo}-{hi}"
        counts = age_dist["bins_5y"].get(label, {"M": 0, "F": 0, "?": 0, "total": 0})
        thin = "YES" if label in age_dist["thin_bins_5y"] else ""
        lines.append(f"| {label} | {counts['M']} | {counts['F']} | "
                     f"{counts['?']} | {counts['total']} | {thin} |")
    lines.append("")

    lines += ["### Decade Bins\n",
              "| Age Bin | Male | Female | Total | Thin? |",
              "|---------|------|--------|-------|-------|"]
    for lo, hi in AGE_BINS_DECADE:
        label = f"{lo}-{hi}"
        counts = age_dist["bins_decade"].get(label, {"M": 0, "F": 0, "?": 0, "total": 0})
        thin = "YES" if label in age_dist["thin_bins_decade"] else ""
        lines.append(f"| {label} | {counts['M']} | {counts['F']} | "
                     f"{counts['total']} | {thin} |")
    lines.append("")

    if age_dist["thin_bins_5y"]:
        lines.append(f"**Warning:** Thin 5-year bins (<{THIN_BIN_THRESHOLD} subjects): "
                     f"{', '.join(age_dist['thin_bins_5y'])}\n")

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

    # Pre/post comparison
    if pre_post and pre_post.get("n_subjects", 0) > 0:
        lines += ["## Pre-Task vs Post-Task Comparison\n",
                   f"Compared {pre_post['n_subjects']} subjects to validate "
                   "pre-task-only normative decision.\n",
                   "| Band | Mean Diff (log10) | Cohen's d |",
                   "|------|-------------------|-----------|"]
        for band, stats in pre_post.get("band_statistics", {}).items():
            lines.append(f"| {band} | {stats['mean_diff_log10']:+.4f} | "
                         f"{stats['cohens_d']:+.3f} |")
        lines.append("")
        if pre_post.get("mean_alpha_peak_shift_hz") is not None:
            lines.append(f"Mean alpha peak shift: "
                         f"{pre_post['mean_alpha_peak_shift_hz']:+.2f} Hz\n")
        lines += ["**Findings:**"]
        for finding in pre_post.get("fatigue_signatures", []):
            lines.append(f"- {finding}")
        lines.append("")

    # Subject table
    lines += ["## Per-Subject Results\n",
              "| Subject | Status | Session 2 | Pre-EO | Pre-EC | Issues |",
              "|---------|--------|-----------|--------|--------|--------|"]
    for r in results:
        has_s2 = "yes" if r.get("session_info", {}).get("has_session_2") else ""
        pre_eo = "yes" if r.get("condition_files", {}).get("pre_eo") else "MISSING"
        pre_ec = "yes" if r.get("condition_files", {}).get("pre_ec") else "MISSING"
        issues_str = "; ".join(
            f"[{i['severity']}] {i['message']}" for i in r.get("issues", [])
        )
        if len(issues_str) > 80:
            issues_str = issues_str[:77] + "..."
        lines.append(f"| {r['subject_id']} | {r['status']} | {has_s2} | "
                     f"{pre_eo} | {pre_ec} | {issues_str} |")
    lines.append("")

    (output_dir / "qc_summary.md").write_text("\n".join(lines) + "\n")

    # --- Counts JSON ---
    counts = {
        "total": len(results),
        "pass": n_pass,
        "warn": n_warn,
        "fail": n_fail,
        "normative_eligible": len(ready_ids),
        "session_2_subjects": len(ses2_ids),
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
            "source_system": "BrainProducts actiCHamp 64ch",
            "source_naming": "10-10",
            "target_naming": "10-20 (19 channels)",
            "line_frequency_hz": LINE_FREQ,
            "reference_channel": REFERENCE_CHANNEL,
            "mapping": channel_mapping["mapping_1020"],
            "additional_channels": channel_mapping["additional_1010"],
        }
        with open(output_dir / "channel_mapping.json", "w") as f:
            json.dump(mapping_out, f, indent=2)

    # --- Ready / excluded / session2 lists ---
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

    (output_dir / "session2_subjects.txt").write_text(
        "\n".join(ses2_ids) + "\n" if ses2_ids else ""
    )

    # --- Pre/post comparison JSON ---
    if pre_post:
        with open(output_dir / "pre_post_comparison.json", "w") as f:
            json.dump(pre_post, f, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for Dortmund Vital Study EEG data "
                    "(64-ch BrainProducts, ages 20-70, European 50 Hz)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir", type=Path,
        help="Path to Dortmund BIDS data root (e.g. ~/datasets/dortmund/)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=Path("./dortmund_qc_output"),
        help="Output directory (default: ./dortmund_qc_output)",
    )
    parser.add_argument(
        "--max-subjects", type=int, default=0,
        help="Limit to N subjects (0 = all, useful for testing)",
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=1,
        help="Number of parallel workers (default: 1)",
    )
    parser.add_argument(
        "--skip-pre-post", action="store_true",
        help="Skip pre/post task spectral comparison",
    )
    parser.add_argument(
        "--pre-post-sample", type=int, default=PRE_POST_SAMPLE_SIZE,
        help=f"N subjects for pre/post comparison (default: {PRE_POST_SAMPLE_SIZE})",
    )
    parser.add_argument(
        "--line-freq", type=float, default=LINE_FREQ,
        help=f"Mains frequency Hz (default: {LINE_FREQ})",
    )
    args = parser.parse_args()

    # Setup output
    output_dir = args.output
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    log = setup_logging(output_dir)

    log.info("Dortmund Vital Study EEG QC")
    log.info("Data directory: %s", args.data_dir)
    log.info("Line frequency: %.0f Hz", LINE_FREQ)

    # Load demographics
    participants = load_participants(args.data_dir)
    log.info("Loaded demographics for %d subjects", len(participants))

    # Discover BIDS structure
    log.info("Discovering BIDS task structure...")
    task_discovery = discover_tasks(args.data_dir)
    for task, info in sorted(task_discovery.items()):
        runs = ", ".join(info["runs"]) if info["runs"] else "none"
        log.info("  task-%s: %d files (runs: %s)", task, info["count"], runs)

    # Discover subjects
    all_subjects = discover_subjects(args.data_dir)
    log.info("Found %d subjects", len(all_subjects))

    n_ses2 = sum(1 for s in all_subjects if s["has_session_2"])
    log.info("  Session 1 only: %d", len(all_subjects) - n_ses2)
    log.info("  Session 1 + 2:  %d", n_ses2)

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

    # --- Pre/post spectral comparison ---
    pre_post = None
    if not args.skip_pre_post:
        log.info("Running pre/post task spectral comparison (n=%d)...",
                 args.pre_post_sample)
        pre_post = run_pre_post_comparison(all_subjects, args.pre_post_sample)
        log.info("  Compared %d subjects", pre_post["n_subjects"])
        for finding in pre_post.get("fatigue_signatures", []):
            log.info("  %s", finding)

    # --- Extract channel mapping from first successful result ---
    channel_mapping = None
    for r in all_results:
        if "channel_mapping" in r and r["channel_mapping"].get("present_19"):
            channel_mapping = r["channel_mapping"]
            break

    # --- Write all outputs ---
    log.info("Writing output files...")
    write_outputs(output_dir, all_results, participants, channel_mapping,
                  pre_post, task_discovery)

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
    log.info("  %s", output_dir / "session2_subjects.txt")
    if pre_post:
        log.info("  %s", output_dir / "pre_post_comparison.json")
    log.info("  %s/ (per-subject JSONs)", subjects_dir)


if __name__ == "__main__":
    main()
