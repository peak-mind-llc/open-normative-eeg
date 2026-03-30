#!/usr/bin/env python3
"""QC sweep for HBN EEG data — run before the normative pipeline.

Loads each subject's EEG (EEGLAB .set format in BIDS layout, or
legacy 128-channel EGI .mff/.raw) and checks integrity, channel
quality, signal quality (pediatric thresholds), condition markers,
reference channel, and phenotypic data (CBCL filtering).

HBN BIDS EEG structure:
- Files are .set (EEGLAB format) with .fdt companion data files.
- Resting state is a SINGLE file ``sub-*_task-RestingState_eeg.set``
  containing BOTH eyes-open and eyes-closed blocks (5x20s EO + 5x40s EC).
- EO/EC transitions are encoded in ``sub-*_task-RestingState_events.tsv``.
- Other tasks: SurroundSupp, ContrastChange, SequenceLearning,
  SymbolSearch, Video*.

Usage:
    # Quick test with 5 subjects
    python scripts/hbn_qc.py ~/Data/EEG/HBN -o ./hbn_qc --max-subjects 5

    # Full QC sweep, 4 parallel workers
    python scripts/hbn_qc.py ~/Data/EEG/HBN -o ./hbn_qc -j 4

    # Resume an interrupted run
    python scripts/hbn_qc.py ~/Data/EEG/HBN -o ./hbn_qc
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import mne
import numpy as np

from open_normative.channels import _CHANNELS_19

logger = logging.getLogger("hbn_qc")

# ── Constants ────────────────────────────────────────────────────────────────

EXPECTED_SFREQ = 500.0
EXPECTED_N_CHANNELS = 128
MIN_DURATION_S = 60.0
MAX_DURATION_S = 1200.0
FLAT_VAR_THRESHOLD = 0.1       # uV^2
RAIL_AMP_THRESHOLD = 500.0     # uV
RAIL_FRACTION = 0.10
LINE_NOISE_FREQ = 60.0         # US mains
LINE_NOISE_SD = 3.0
DC_OFFSET_THRESHOLD = 40.0     # uV
ARTIFACT_AMP = 300.0           # uV — pediatric (vs 200 for adults)
ARTIFACT_CHAN_FRAC = 0.50
ARTIFACT_REJECT_PCT = 60.0     # flag if >60% contaminated
MIN_USABLE_REST_S = 120.0      # 2 min usable after artifact removal
MIN_CONDITION_S = 60.0
CBCL_THRESHOLDS = [60, 63, 70]

AGE_BINS = [(5, 7), (8, 10), (11, 13), (14, 16), (17, 21)]


# ── EGI mapping ──────────────────────────────────────────────────────────────

def compute_egi_mapping():
    """Compute EGI 128-ch to 10-20 19-ch spatial mapping.

    Returns dict mapping each 10-20 channel to its nearest EGI electrode
    with distance in mm.
    """
    egi_montage = mne.channels.make_standard_montage("GSN-HydroCel-128")
    target_montage = mne.channels.make_standard_montage("standard_1020")
    egi_pos = egi_montage.get_positions()["ch_pos"]
    target_pos = target_montage.get_positions()["ch_pos"]

    mapping = {}
    used = set()
    for tch in _CHANNELS_19:
        if tch not in target_pos:
            continue
        t = np.array(target_pos[tch])
        best_ch, best_dist = None, np.inf
        for ech, epos in egi_pos.items():
            if ech in used:
                continue
            d = np.linalg.norm(t - np.array(epos))
            if d < best_dist:
                best_dist, best_ch = d, ech
        if best_ch is not None:
            used.add(best_ch)
            mapping[tch] = {
                "egi_channel": best_ch,
                "distance_mm": round(best_dist * 1000, 2),
            }
    return mapping


def compute_face_neck_channels():
    """Identify EGI face/neck channels from montage z-coordinates."""
    montage = mne.channels.make_standard_montage("GSN-HydroCel-128")
    pos = montage.get_positions()["ch_pos"]
    zvals = [p[2] for p in pos.values()]
    z_min, z_max = min(zvals), max(zvals)
    z_range = z_max - z_min
    threshold = np.median(zvals) - 0.4 * z_range
    return sorted(ch for ch, p in pos.items() if p[2] < threshold)


# ── Check functions ──────────────────────────────────────────────────────────

def check_integrity(raw, eeg_path):
    """Basic integrity: sampling rate, channel count, duration, paradigm."""
    sfreq = raw.info["sfreq"]
    n_ch = len(raw.ch_names)
    duration = raw.times[-1]

    # Parse paradigm from BIDS filename (HBN EEG protocol)
    paradigm = "unknown"
    name = Path(eeg_path).name.upper()
    for tag in ("RESTINGSTATE", "RESTEO", "RESTEC", "REST",
                "SURROUNDSUP", "CONTRASTCHANGE", "SEQUENCELEARNING",
                "SYMBOLSEARCH", "SURROUND",
                "SEQUENCE", "CONTRAST", "VIDEO"):
        if tag in name:
            paradigm = tag.lower()
            break

    return {
        "sfreq": sfreq,
        "sfreq_ok": abs(sfreq - EXPECTED_SFREQ) < 2,
        "n_channels": n_ch,
        "n_channels_ok": n_ch >= 100,
        "duration_s": round(duration, 1),
        "duration_ok": MIN_DURATION_S <= duration <= MAX_DURATION_S,
        "paradigm": paradigm,
    }


def check_channels(raw, face_neck_chs):
    """Channel-level checks: flat, railed, line noise, face/neck."""
    data = raw.get_data() * 1e6  # V -> uV

    var = np.var(data, axis=1)
    flat = [raw.ch_names[i] for i in range(len(raw.ch_names))
            if var[i] < FLAT_VAR_THRESHOLD]

    railed_frac = np.mean(np.abs(data) > RAIL_AMP_THRESHOLD, axis=1)
    railed = [raw.ch_names[i] for i in range(len(raw.ch_names))
              if railed_frac[i] > RAIL_FRACTION]

    line_noise = []
    try:
        psds, freqs = mne.time_frequency.psd_array_welch(
            data / 1e6, sfreq=raw.info["sfreq"],
            fmin=LINE_NOISE_FREQ - 1, fmax=LINE_NOISE_FREQ + 1,
            n_fft=int(raw.info["sfreq"] * 2), verbose=False,
        )
        idx = np.argmin(np.abs(freqs - LINE_NOISE_FREQ))
        noise_power = psds[:, idx]
        if len(noise_power) > 1 and np.std(noise_power) > 0:
            z = (noise_power - np.mean(noise_power)) / np.std(noise_power)
            line_noise = [raw.ch_names[i] for i in range(len(z))
                          if z[i] > LINE_NOISE_SD]
    except Exception:
        pass

    present_fn = [ch for ch in raw.ch_names if ch in set(face_neck_chs)]
    return {
        "flat_channels": flat,
        "railed_channels": railed,
        "line_noise_channels": line_noise,
        "n_face_neck": len(present_fn),
        "face_neck_channels": present_fn,
    }


def check_signal_quality(raw):
    """Signal quality with pediatric 300 uV artifact threshold."""
    data = raw.get_data() * 1e6
    n_ch, n_samples = data.shape
    sfreq = raw.info["sfreq"]

    amp_mean = float(np.mean(np.abs(data)))
    amp_std = float(np.std(data))
    amp_max = float(np.max(np.abs(data)))

    window = int(sfreq)
    n_windows = n_samples // window
    artifact_count = 0
    for w in range(n_windows):
        seg = data[:, w * window:(w + 1) * window]
        max_per_ch = np.max(np.abs(seg), axis=1)
        if np.mean(max_per_ch > ARTIFACT_AMP) > ARTIFACT_CHAN_FRAC:
            artifact_count += 1
    artifact_pct = round(100.0 * artifact_count / max(n_windows, 1), 1)

    usable_s = round((n_windows - artifact_count) / max(sfreq / window, 1), 1)

    dc = np.mean(data, axis=1)
    dc_channels = [raw.ch_names[i] for i in range(n_ch)
                   if abs(dc[i]) > DC_OFFSET_THRESHOLD]

    return {
        "amplitude_mean_uv": round(amp_mean, 1),
        "amplitude_std_uv": round(amp_std, 1),
        "amplitude_max_uv": round(amp_max, 1),
        "artifact_pct": artifact_pct,
        "usable_duration_s": usable_s,
        "usable_ok": usable_s >= MIN_USABLE_REST_S,
        "dc_offset_channels": dc_channels,
    }


def _parse_events_tsv(eeg_path):
    """Read the BIDS ``_events.tsv`` companion for an EEG file.

    Parameters
    ----------
    eeg_path : str or Path
        Path to the ``.set`` (or ``.mff`` / ``.raw``) EEG file.

    Returns
    -------
    list[dict]
        Each dict has ``onset`` (float, seconds), ``duration`` (float),
        and ``trial_type`` (str).  Returns an empty list when no events
        file is found or it cannot be parsed.
    """
    eeg_path = Path(eeg_path)
    # BIDS convention: replace modality suffix + extension with _events.tsv
    # e.g. sub-X_task-RestingState_eeg.set -> sub-X_task-RestingState_events.tsv
    stem = eeg_path.name
    for suffix in ("_eeg.set", "_eeg.fdt", "_eeg.mff", "_eeg.raw",
                    ".set", ".fdt", ".mff", ".raw"):
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
                trial_type = row.get("trial_type",
                                     row.get("value",
                                             row.get("description", ""))).strip()
                events.append({
                    "onset": onset,
                    "duration": duration,
                    "trial_type": trial_type,
                })
    except Exception:
        pass
    return events


def check_markers(raw, eeg_path):
    """Identify resting-state condition and parse event markers.

    For BIDS HBN data the resting file contains interleaved EO/EC blocks.
    We first try to parse the companion ``_events.tsv``; if unavailable we
    fall back to raw annotations.
    """
    name = Path(eeg_path).name.upper()
    condition = None
    if "EC" in name and "EO" not in name and "RESTINGSTATE" not in name:
        condition = "ec"
    elif "EO" in name and "EC" not in name and "RESTINGSTATE" not in name:
        condition = "eo"
    elif "RESTINGSTATE" in name or "REST" in name:
        condition = "eo+ec"  # combined resting

    # ── Try BIDS events.tsv first ──
    bids_events = _parse_events_tsv(eeg_path)
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

    has_events_tsv = len(bids_events) > 0

    # ── Fall back to raw annotations ──
    ann_count = len(raw.annotations)
    descs = [a["description"] for a in raw.annotations] if ann_count else []
    unique_events = sorted(set(descs))

    if not has_events_tsv and ann_count > 0:
        # Try to extract EO/EC durations from annotations
        for ann in raw.annotations:
            desc = ann["description"].lower().strip()
            dur = float(ann["duration"]) if ann["duration"] else 0.0
            if desc in eo_keywords:
                eo_duration += dur
            elif desc in ec_keywords:
                ec_duration += dur

    is_resting = condition is not None
    eo_ok = eo_duration >= MIN_CONDITION_S
    ec_ok = ec_duration >= MIN_CONDITION_S

    return {
        "condition_from_filename": condition,
        "has_events_tsv": has_events_tsv,
        "n_bids_events": len(bids_events),
        "eo_duration_s": round(eo_duration, 1),
        "ec_duration_s": round(ec_duration, 1),
        "eo_duration_ok": eo_ok,
        "ec_duration_ok": ec_ok,
        "annotation_count": ann_count,
        "unique_events": unique_events[:20],  # cap for JSON size
        "is_resting": is_resting,
    }


def check_reference(raw):
    """Check if Cz was online reference (should be flat or absent)."""
    cz_names = {"Cz", "E129", "VREF"}
    found = None
    for ch in raw.ch_names:
        if ch in cz_names:
            found = ch
            break

    if found is None:
        return {"cz_present": False, "cz_variance": None,
                "cz_is_reference": True}  # absent = was reference

    idx = raw.ch_names.index(found)
    data = raw.get_data(picks=[idx]) * 1e6
    variance = float(np.var(data))
    return {
        "cz_present": True,
        "cz_channel_name": found,
        "cz_variance": round(variance, 4),
        "cz_is_reference": variance < FLAT_VAR_THRESHOLD,
    }


# ── Phenotypic data ─────────────────────────────────────────────────────────

def load_cbcl(phenotypic_dir):
    """Scan phenotypic dir for CBCL data, return {subject_id: {cbcl_total_t}}."""
    if phenotypic_dir is None or not Path(phenotypic_dir).exists():
        logger.warning("No phenotypic directory found — CBCL filtering unavailable")
        return {}

    cbcl_files = list(Path(phenotypic_dir).glob("*[Cc][Bb][Cc][Ll]*"))
    if not cbcl_files:
        # Try broader search
        cbcl_files = [f for f in Path(phenotypic_dir).glob("*.csv")
                      if "cbcl" in f.name.lower()]
    if not cbcl_files:
        logger.warning("No CBCL files found in %s", phenotypic_dir)
        return {}

    logger.info("Found %d CBCL file(s): %s", len(cbcl_files),
                [f.name for f in cbcl_files])

    id_cols = ["participant_id", "EID", "Identifiers", "subjectkey", "Subject",
               "participant"]
    score_cols = ["CBCL_Total_T", "Total_Problems_T",
                  "CBCL_Total_Problems_T_Score", "CBCL_Total_Prob_T",
                  "Total_T", "cbcl_total_t"]

    result = {}
    for cbcl_file in cbcl_files:
        try:
            with cbcl_file.open(newline="", encoding="utf-8") as fh:
                # Skip comment lines starting with #
                lines = [l for l in fh if not l.startswith("#")]
            if not lines:
                continue
            import io
            reader = csv.DictReader(io.StringIO("".join(lines)))
            headers = reader.fieldnames or []

            id_col = next((c for c in id_cols if c in headers), None)
            score_col = next((c for c in score_cols if c in headers), None)

            if id_col is None or score_col is None:
                logger.debug("CBCL file %s: no matching columns (has: %s)",
                             cbcl_file.name, headers[:10])
                continue

            for row in reader:
                sid = row.get(id_col, "").strip()
                if not sid:
                    continue
                if not sid.startswith("sub-"):
                    sid = f"sub-{sid}"
                try:
                    score = float(row[score_col])
                    result[sid] = {"cbcl_total_t": score,
                                   "cbcl_source": cbcl_file.name}
                except (ValueError, TypeError):
                    pass

            logger.info("Loaded %d CBCL scores from %s", len(result),
                        cbcl_file.name)
        except Exception as e:
            logger.warning("Error reading %s: %s", cbcl_file.name, e)

    return result


def load_participants(data_dir):
    """Parse participants.tsv for demographics and commercial use flag.

    HBN distributes most data under CC-BY-4.0 (commercial OK), but a
    subset is CC-BY-NC-SA (no commercial use).  The "Commercial_Use"
    column in the metadata file indicates this ("Yes"/"No").  We also
    check participants.tsv in case the column lives there.
    """
    tsv = Path(data_dir) / "participants.tsv"
    if not tsv.exists():
        logger.warning("participants.tsv not found at %s", tsv)
        return {}

    participants = {}
    with tsv.open(newline="", encoding="utf-8") as fh:
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
            raw_sex = row.get("sex", row.get("gender", "")).strip().upper()
            sex = "M" if raw_sex.startswith("M") else (
                "F" if raw_sex.startswith("F") else raw_sex)
            # Commercial use flag (CC-BY-4.0 vs CC-BY-NC-SA)
            commercial = row.get("Commercial_Use",
                                 row.get("commercial_use", "")).strip()
            participants[sid] = {
                "age": age,
                "sex": sex,
                "commercial_use": commercial.upper() != "NO",
            }

    # If Commercial_Use wasn't in participants.tsv, try separate metadata file
    has_flag = any(row.get("Commercial_Use") or row.get("commercial_use")
                   for row in [{}])  # placeholder — detected from header presence
    # Try loading from phenotypic metadata files if all are default True
    all_true = all(p["commercial_use"] for p in participants.values())
    if all_true and len(participants) > 0:
        _load_commercial_use_flags(data_dir, participants)

    no_commercial = sum(1 for p in participants.values()
                        if not p["commercial_use"])
    if no_commercial:
        logger.info("%d subjects flagged as no commercial use", no_commercial)

    return participants


def _load_commercial_use_flags(data_dir, participants):
    """Try to find Commercial_Use flags from metadata/phenotypic files."""
    search_dirs = [
        Path(data_dir),
        Path(data_dir) / "phenotypic",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.csv")) + sorted(d.glob("*.tsv")):
            try:
                delim = "\t" if f.suffix == ".tsv" else ","
                with f.open(newline="", encoding="utf-8") as fh:
                    lines = [l for l in fh if not l.startswith("#")]
                if not lines:
                    continue
                import io
                reader = csv.DictReader(io.StringIO("".join(lines)),
                                        delimiter=delim)
                headers = reader.fieldnames or []
                cu_col = next((c for c in headers
                               if c.lower() == "commercial_use"), None)
                id_col = next((c for c in headers
                               if c.lower() in ("participant_id", "eid",
                                                 "subjectkey", "subject")),
                              None)
                if cu_col is None or id_col is None:
                    continue

                logger.info("Loading Commercial_Use from %s", f.name)
                count = 0
                for row in reader:
                    sid = row.get(id_col, "").strip()
                    if not sid.startswith("sub-"):
                        sid = f"sub-{sid}"
                    if sid in participants:
                        val = row.get(cu_col, "").strip()
                        participants[sid]["commercial_use"] = val.upper() != "NO"
                        count += 1
                if count:
                    logger.info("Updated commercial use flags for %d subjects",
                                count)
                    return  # done, found the file
            except Exception:
                continue


# ── Verdict ──────────────────────────────────────────────────────────────────

def compute_verdict(integrity, channels, signal, markers, reference):
    """Combine checks into verdict: ready / review / exclude."""
    reasons = []

    # Exclude conditions
    if not integrity["sfreq_ok"]:
        reasons.append(f"sfreq={integrity['sfreq']} (expected ~{EXPECTED_SFREQ})")
    if integrity["n_channels"] < 64:
        reasons.append(f"only {integrity['n_channels']} channels")
    if integrity["duration_s"] < 30:
        reasons.append(f"duration={integrity['duration_s']}s (<30s)")
    if signal["artifact_pct"] > ARTIFACT_REJECT_PCT:
        reasons.append(f"artifact={signal['artifact_pct']}% (>{ARTIFACT_REJECT_PCT}%)")

    if reasons:
        return "exclude", reasons

    # Review conditions
    if not integrity["n_channels_ok"]:
        reasons.append(f"{integrity['n_channels']} channels (expected >={EXPECTED_N_CHANNELS})")
    if not integrity["duration_ok"]:
        reasons.append(f"duration={integrity['duration_s']}s")
    if len(channels["flat_channels"]) > 5:
        reasons.append(f"{len(channels['flat_channels'])} flat channels")
    if len(channels["railed_channels"]) > 5:
        reasons.append(f"{len(channels['railed_channels'])} railed channels")
    if len(channels["line_noise_channels"]) > 5:
        reasons.append(f"{len(channels['line_noise_channels'])} line-noise channels")
    if signal["artifact_pct"] > 30:
        reasons.append(f"artifact={signal['artifact_pct']}%")
    if not signal["usable_ok"]:
        reasons.append(f"usable={signal['usable_duration_s']}s (<{MIN_USABLE_REST_S}s)")
    if not reference.get("cz_is_reference", True):
        reasons.append("Cz not confirmed as reference")
    if not markers["is_resting"]:
        reasons.append("not a resting-state recording")

    if reasons:
        return "review", reasons

    return "ready", []


# ── Per-subject runner ───────────────────────────────────────────────────────

def qc_one_subject(subject_id, eeg_files, face_neck_chs):
    """Run all QC checks on one HBN subject."""
    result = {
        "subject_id": subject_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "paradigms": [],
    }

    # Find resting file first; fall back to first file
    resting_file = None
    for p in eeg_files:
        name = Path(p).name.upper()
        if any(t in name for t in ("RESTINGSTATE", "REST", "EO", "EC")):
            resting_file = p
            break
    if resting_file is None:
        resting_file = eeg_files[0]

    # Record all paradigms (HBN EEG protocol)
    for p in eeg_files:
        name = Path(p).name.upper()
        for tag in ("RESTINGSTATE", "RESTEO", "RESTEC", "REST",
                    "SURROUNDSUP", "CONTRASTCHANGE", "SEQUENCELEARNING",
                    "SYMBOLSEARCH", "SURROUND",
                    "SEQUENCE", "CONTRAST", "VIDEO"):
            if tag in name:
                result["paradigms"].append(tag.lower())
                break
        else:
            result["paradigms"].append("unknown")

    # QC the resting file — try EEGLAB (.set) first, then EGI (.mff/.raw)
    try:
        ext = Path(resting_file).suffix.lower()
        if ext == ".set":
            raw = mne.io.read_raw_eeglab(str(resting_file), preload=True,
                                         verbose=False)
        elif ext == ".mff":
            raw = mne.io.read_raw_egi(str(resting_file), preload=True,
                                      verbose=False)
        else:
            # .raw or other — try EGI reader
            raw = mne.io.read_raw_egi(str(resting_file), preload=True,
                                      verbose=False)
        raw.pick("eeg")
    except Exception as e:
        result.update({
            "verdict": "exclude",
            "reasons": [f"load error: {e}"],
            "eeg_path": str(resting_file),
            "integrity": {}, "channels": {}, "signal_quality": {},
            "markers": {}, "reference": {},
        })
        return result

    integrity = check_integrity(raw, resting_file)
    channels_result = check_channels(raw, face_neck_chs)
    signal = check_signal_quality(raw)
    markers = check_markers(raw, resting_file)
    reference = check_reference(raw)
    verdict, reasons = compute_verdict(integrity, channels_result, signal,
                                       markers, reference)

    result.update({
        "verdict": verdict,
        "reasons": reasons,
        "eeg_path": str(resting_file),
        "integrity": integrity,
        "channels": channels_result,
        "signal_quality": signal,
        "markers": markers,
        "reference": reference,
    })
    return result


# ── File discovery & resume ──────────────────────────────────────────────────

def discover_subjects(data_dir):
    """Find all EEG files grouped by subject.

    Looks for BIDS EEGLAB ``.set`` files first (the standard HBN BIDS
    layout), then falls back to legacy EGI ``.mff`` / ``.raw`` files.
    Companion ``.fdt`` files are noted but not returned as separate
    entries (MNE loads them automatically via the ``.set``).
    """
    data_root = Path(data_dir)
    eeg_files = sorted(
        list(data_root.glob("sub-*/eeg/*.set"))
        + list(data_root.glob("sub-*/eeg/*.mff"))
        + list(data_root.glob("sub-*/eeg/*.raw"))
    )
    # De-duplicate: if a .set file exists for a task, skip .mff/.raw
    # for the same stem
    seen_stems: set[str] = set()
    filtered: list[Path] = []
    for p in eeg_files:
        stem = p.stem  # e.g. sub-X_task-RestingState_eeg
        if p.suffix == ".set":
            seen_stems.add(stem)
            filtered.append(p)
        elif stem not in seen_stems:
            filtered.append(p)

    subjects: dict[str, list[Path]] = {}
    for p in filtered:
        for part in p.parts:
            if part.startswith("sub-"):
                subjects.setdefault(part, []).append(p)
                break
    return sorted(subjects.items())


def load_existing(output_dir):
    """Load already-completed QC results."""
    results_dir = output_dir / "subjects"
    existing = {}
    if not results_dir.exists():
        return existing
    for f in results_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            existing[data["subject_id"]] = data
        except Exception:
            pass
    return existing


# ── Summary ──────────────────────────────────────────────────────────────────

def _age_bin(age):
    """Return age bin label or None."""
    for lo, hi in AGE_BINS:
        if lo <= age <= hi:
            return f"{lo}-{hi}"
    return None


def generate_summary(output_dir, results, cbcl_data, participants):
    """Write summary.md, ready.txt, excluded.txt, normative_eligible.txt."""
    ready = [r for r in results if r["verdict"] == "ready"]
    review = [r for r in results if r["verdict"] == "review"]
    exclude = [r for r in results if r["verdict"] == "exclude"]

    reason_counts = {}
    for r in results:
        for reason in r.get("reasons", []):
            key = reason.split("=")[0].split(":")[0].strip()
            reason_counts[key] = reason_counts.get(key, 0) + 1

    lines = [
        "# HBN EEG QC Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Total subjects:** {len(results)}",
        "",
        "## Summary",
        "",
        "| Verdict | Count |",
        "|---------|-------|",
        f"| Ready   | {len(ready)} |",
        f"| Review  | {len(review)} |",
        f"| Exclude | {len(exclude)} |",
        "",
    ]

    if reason_counts:
        lines += ["## Issue Frequency", "",
                   "| Issue | Count |", "|-------|-------|"]
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    if exclude:
        lines += ["## Excluded Subjects", "",
                   "| Subject | Reasons |", "|---------|---------|"]
        for r in sorted(exclude, key=lambda x: x["subject_id"]):
            reasons = "; ".join(r.get("reasons", []))
            lines.append(f"| {r['subject_id']} | {reasons} |")
        lines.append("")

    if review:
        lines += ["## Subjects Needing Review", "",
                   "| Subject | Reasons |", "|---------|---------|"]
        for r in sorted(review, key=lambda x: x["subject_id"]):
            reasons = "; ".join(r.get("reasons", []))
            lines.append(f"| {r['subject_id']} | {reasons} |")
        lines.append("")

    # Channel issues
    flat_all, railed_all, noise_all = {}, {}, {}
    for r in results:
        ch = r.get("channels", {})
        for c in ch.get("flat_channels", []):
            flat_all[c] = flat_all.get(c, 0) + 1
        for c in ch.get("railed_channels", []):
            railed_all[c] = railed_all.get(c, 0) + 1
        for c in ch.get("line_noise_channels", []):
            noise_all[c] = noise_all.get(c, 0) + 1

    if flat_all or railed_all or noise_all:
        lines += ["## Channel Issues Across Subjects", "",
                   "| Channel | Flat | Railed | Line Noise |",
                   "|---------|------|--------|------------|"]
        all_ch = sorted(set(flat_all) | set(railed_all) | set(noise_all))
        for ch in all_ch:
            lines.append(f"| {ch} | {flat_all.get(ch, 0)} | "
                         f"{railed_all.get(ch, 0)} | {noise_all.get(ch, 0)} |")
        lines.append("")

    # ── Normative eligibility by CBCL threshold ──
    ready_ids = {r["subject_id"] for r in ready}
    lines += ["## Normative Eligibility (CBCL Filtering)", "",
              "HBN is community-referred — most participants have psychiatric "
              "concerns. Subjects must pass QC AND have CBCL Total Problems "
              "T-score below threshold to be normative-eligible.", ""]

    lines += ["| CBCL Threshold | Eligible | Excluded | No CBCL Data |",
              "|----------------|----------|----------|--------------|"]
    best_threshold_eligible = {}
    for thresh in CBCL_THRESHOLDS:
        eligible, excluded_cbcl, no_data = 0, 0, 0
        eligible_ids = set()
        for sid in ready_ids:
            cbcl = cbcl_data.get(sid)
            if cbcl is None:
                no_data += 1
                eligible_ids.add(sid)  # keep if no CBCL data
            elif cbcl["cbcl_total_t"] < thresh:
                eligible += 1
                eligible_ids.add(sid)
            else:
                excluded_cbcl += 1
        lines.append(f"| T < {thresh} | {eligible} | {excluded_cbcl} | {no_data} |")
        best_threshold_eligible[thresh] = eligible_ids
    lines.append("")

    # ── Commercial use licensing ──
    commercial_yes = sum(1 for sid in ready_ids
                         if participants.get(sid, {}).get("commercial_use", True))
    commercial_no = sum(1 for sid in ready_ids
                        if not participants.get(sid, {}).get("commercial_use", True))
    if commercial_no:
        lines += [
            "## Commercial Use Licensing", "",
            "HBN data is mostly CC-BY-4.0 (commercial OK), but a subset is "
            "CC-BY-NC-SA (no commercial use). Among QC-ready subjects:", "",
            f"- **Commercial use allowed:** {commercial_yes}",
            f"- **No commercial use:** {commercial_no}",
            "",
        ]

    # ── Age x sex distribution ──
    lines += ["## Age x Sex Distribution (QC-Ready Subjects)", ""]
    age_sex = {}
    for sid in ready_ids:
        info = participants.get(sid, {})
        age = info.get("age", float("nan"))
        sex = info.get("sex", "?")
        ab = _age_bin(age)
        if ab:
            age_sex.setdefault(ab, {"M": 0, "F": 0, "?": 0})
            age_sex[ab][sex if sex in ("M", "F") else "?"] += 1

    if age_sex:
        lines += ["| Age Bin | Male | Female | Unknown | Total |",
                   "|---------|------|--------|---------|-------|"]
        for ab_label in [f"{lo}-{hi}" for lo, hi in AGE_BINS]:
            counts = age_sex.get(ab_label, {"M": 0, "F": 0, "?": 0})
            total = counts["M"] + counts["F"] + counts["?"]
            lines.append(f"| {ab_label} | {counts['M']} | {counts['F']} | "
                         f"{counts['?']} | {total} |")
        lines.append("")

    # Write files
    (output_dir / "summary.md").write_text("\n".join(lines))

    (output_dir / "ready.txt").write_text(
        "\n".join(sorted(ready_ids)) + "\n" if ready_ids else ""
    )
    (output_dir / "excluded.txt").write_text(
        "\n".join(r["subject_id"] for r in sorted(
            exclude, key=lambda x: x["subject_id"])) + "\n"
        if exclude else ""
    )

    # Normative eligible at default threshold (60)
    ne = best_threshold_eligible.get(60, set())
    (output_dir / "normative_eligible.txt").write_text(
        "\n".join(sorted(ne)) + "\n" if ne else ""
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

def setup_logging(output_dir):
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    fh = logging.FileHandler(output_dir / "qc_errors.log")
    fh.setLevel(logging.WARNING)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)


def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for HBN EEG data (128-ch EGI, pediatric)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("data_dir", type=Path, help="Path to HBN data root")
    parser.add_argument("--output", "-o", type=Path, default=Path("./hbn_qc_output"))
    parser.add_argument("--max-subjects", type=int, default=0, help="Limit (0=all)")
    parser.add_argument("--jobs", "-j", type=int, default=1, help="Parallel workers")
    parser.add_argument("--line-freq", type=float, default=LINE_NOISE_FREQ,
                        help=f"Mains frequency Hz (default: {LINE_NOISE_FREQ})")
    parser.add_argument("--phenotypic-dir", type=Path, default=None,
                        help="Override phenotypic data path (default: data_dir/phenotypic)")
    args = parser.parse_args()

    subjects_dir = args.output / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(args.output)

    # Compute EGI mapping once and save
    logger.info("Computing EGI-to-10-20 channel mapping...")
    egi_mapping = compute_egi_mapping()
    mapping_path = args.output / "egi_to_1020_mapping.json"
    mapping_path.write_text(json.dumps(egi_mapping, indent=2))
    logger.info("Saved EGI mapping to %s", mapping_path)
    flagged = [ch for ch, m in egi_mapping.items() if m["distance_mm"] > 10]
    if flagged:
        logger.warning("Channels with mapping distance >10mm: %s", flagged)

    # Compute face/neck channels once
    face_neck_chs = compute_face_neck_channels()
    logger.info("Identified %d face/neck channels: %s", len(face_neck_chs),
                face_neck_chs)

    # Load phenotypic data
    pheno_dir = args.phenotypic_dir or args.data_dir / "phenotypic"
    cbcl_data = load_cbcl(pheno_dir)
    if cbcl_data:
        logger.info("Loaded CBCL scores for %d subjects", len(cbcl_data))

    participants = load_participants(args.data_dir)
    logger.info("Loaded demographics for %d subjects", len(participants))

    # Discover and filter
    all_subjects = discover_subjects(args.data_dir)
    logger.info("Found %d subjects in %s", len(all_subjects), args.data_dir)

    existing = load_existing(args.output)
    if existing:
        logger.info("Resuming: %d already completed", len(existing))

    todo = [(sid, paths) for sid, paths in all_subjects if sid not in existing]
    if args.max_subjects > 0:
        todo = todo[:args.max_subjects]
    logger.info("Will QC %d subjects (%d jobs)", len(todo), args.jobs)

    # Process
    new_results = []
    start = time.time()

    if args.jobs <= 1:
        for i, (sid, paths) in enumerate(todo):
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info("[%d/%d] %s (%d files, %.1f subj/min)",
                        i + 1, len(todo), sid, len(paths), rate * 60)
            result = qc_one_subject(sid, paths, face_neck_chs)
            (subjects_dir / f"{sid}.json").write_text(
                json.dumps(result, indent=2))
            new_results.append(result)
            logger.info("  -> %s%s", result["verdict"],
                        f" ({', '.join(result['reasons'])})"
                        if result["reasons"] else "")
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(qc_one_subject, sid, paths, face_neck_chs): sid
                for sid, paths in todo
            }
            for i, future in enumerate(as_completed(futures)):
                sid = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {
                        "subject_id": sid, "verdict": "exclude",
                        "reasons": [f"worker error: {e}"],
                        "paradigms": [],
                        "integrity": {}, "channels": {},
                        "signal_quality": {}, "markers": {},
                        "reference": {},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                (subjects_dir / f"{sid}.json").write_text(
                    json.dumps(result, indent=2))
                new_results.append(result)
                logger.info("[%d/%d] %s -> %s", i + 1, len(todo), sid,
                            result["verdict"])

    elapsed = time.time() - start
    logger.info("\nQC complete: %d subjects in %.1f min", len(todo),
                elapsed / 60)

    # Combine and summarize
    all_results = list(existing.values()) + new_results
    generate_summary(args.output, all_results, cbcl_data, participants)

    ready = sum(1 for r in all_results if r["verdict"] == "ready")
    review = sum(1 for r in all_results if r["verdict"] == "review")
    exclude = sum(1 for r in all_results if r["verdict"] == "exclude")
    logger.info("Results: %d ready, %d review, %d exclude", ready, review,
                exclude)
    logger.info("Report: %s", args.output / "summary.md")


if __name__ == "__main__":
    main()
