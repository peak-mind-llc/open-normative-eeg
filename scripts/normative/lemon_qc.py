#!/usr/bin/env python3
"""QC sweep for LEMON raw EEG data.

Loads each subject's raw BrainVision file and produces a QC report
covering basic integrity, channel issues, signal quality, condition
markers, and reference channel status.

Usage:
    python scripts/normative/lemon_qc.py ~/Data/EEG/lemon/EEG_Raw_BIDS_ID

    # Test with 3 subjects:
    python scripts/normative/lemon_qc.py ~/Data/EEG/lemon/EEG_Raw_BIDS_ID \
        --output ./test_qc --max-subjects 3

    # Parallel processing:
    python scripts/normative/lemon_qc.py ~/Data/EEG/lemon/EEG_Raw_BIDS_ID \
        --output ./lemon_qc_output --workers 4
"""

import argparse
import json
import logging
import multiprocessing
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import mne
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_SFREQ = 2500
EXPECTED_N_CHANNELS = 62
EXPECTED_CHANNELS = [
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "FC5", "FC1", "FC2", "FC6",
    "T7", "C3", "Cz", "C4", "T8",
    "VEOG",
    "CP5", "CP1", "CP2", "CP6", "AFz",
    "P7", "P3", "Pz", "P4", "P8",
    "PO9", "O1", "Oz", "O2", "PO10",
    "AF7", "AF3", "AF4", "AF8",
    "F5", "F1", "F2", "F6",
    "FT7", "FC3", "FC4", "FT8",
    "C5", "C1", "C2", "C6",
    "TP7", "CP3", "CPz", "CP4", "TP8",
    "P5", "P1", "P2", "P6",
    "PO7", "PO3", "POz", "PO4", "PO8",
]
NON_EEG_CHANNELS = {"VEOG"}
REFERENCE_CHANNEL = "FCz"

# Marker codes in LEMON (recorded in Germany)
MARKER_EO = "S200"
MARKER_EC = "S210"
LINE_FREQ = 50  # Hz — European mains frequency

# Thresholds
FLAT_VARIANCE_UV2 = 0.1        # µV² — below this, channel is flat
RAILED_AMPLITUDE_UV = 500      # µV — above this, channel may be railed
RAILED_FRACTION = 0.10         # >10% of samples railed → flag
NOISE_SD_THRESHOLD = 3.0       # 50 Hz power > 3 SD above mean → flag
MEDIAN_AMP_WARN_UV = 200       # µV — overall median amplitude warning
ARTIFACT_EPOCH_SEC = 1.0       # epoch length for gross artifact check
ARTIFACT_CHAN_FRACTION = 0.50   # >50% of channels exceed threshold → artifact
ARTIFACT_AMP_UV = 200          # µV — per-channel threshold for artifacts
ARTIFACT_PCT_WARN = 20.0       # % — warn above this
ARTIFACT_PCT_FAIL = 50.0       # % — fail above this
DC_OFFSET_WARN_UV = 100        # µV — warn if |offset| exceeds this
DURATION_MIN_FAIL = 3.0        # minutes — fail below this
DURATION_MAX_FAIL = 20.0       # minutes — fail above this
DURATION_MIN_WARN = 14.0       # minutes — warn below this
DURATION_MAX_WARN = 18.0       # minutes — warn above this
MARKER_MIN_FAIL = 4            # fewer than this → fail
MARKER_EXPECTED = 8            # expected number of each marker type


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging to both console and error log file."""
    logger = logging.getLogger("lemon_qc")
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


# ---------------------------------------------------------------------------
# Subject discovery
# ---------------------------------------------------------------------------

def discover_subjects(data_dir: Path) -> list[tuple[str, Path]]:
    """Return sorted list of (subject_id, vhdr_path) tuples."""
    subjects = []
    for vhdr_path in sorted(data_dir.glob("sub-*/RSEEG/sub-*.vhdr")):
        subject_id = vhdr_path.parent.parent.name  # sub-XXXXXX
        subjects.append((subject_id, vhdr_path))
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
        # filename is {subject_id}_qc.json
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
# Check functions
# ---------------------------------------------------------------------------

def check_basic_integrity(raw, data_uv):
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
    if n_channels != EXPECTED_N_CHANNELS:
        issues.append(("fail", f"n_channels={n_channels}, expected {EXPECTED_N_CHANNELS}"))

    # Duration
    if duration_min < DURATION_MIN_FAIL or duration_min > DURATION_MAX_FAIL:
        issues.append(("fail", f"duration={duration_min:.1f} min, outside [{DURATION_MIN_FAIL}, {DURATION_MAX_FAIL}]"))
    elif duration_min < DURATION_MIN_WARN or duration_min > DURATION_MAX_WARN:
        issues.append(("warn", f"duration={duration_min:.1f} min, outside [{DURATION_MIN_WARN}, {DURATION_MAX_WARN}]"))

    # Data scale — check median absolute amplitude makes sense for µV
    median_amp = float(np.median(np.abs(data_uv)))

    metrics = {
        "sfreq": sfreq,
        "n_channels": n_channels,
        "duration_sec": round(duration_sec, 2),
        "duration_min": round(duration_min, 2),
        "median_abs_amplitude_uv": round(median_amp, 2),
    }
    return metrics, issues


def check_channels(raw, data_uv):
    """Check channel names, flat/railed/noisy channels, and reference.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    ch_names = raw.ch_names
    expected_set = set(EXPECTED_CHANNELS)
    present_set = set(ch_names)

    missing = sorted(expected_set - present_set)
    unexpected = sorted(present_set - expected_set)

    if missing:
        severity = "fail" if len(missing) > 5 else "warn"
        issues.append((severity, f"missing channels: {', '.join(missing)}"))
    if unexpected:
        issues.append(("warn", f"unexpected channels: {', '.join(unexpected)}"))

    # FCz reference check
    fcz_present = REFERENCE_CHANNEL in present_set
    if fcz_present:
        issues.append(("fail", f"{REFERENCE_CHANNEL} present — unexpected (was online reference)"))

    # Per-channel variance (µV²)
    variances = np.var(data_uv, axis=1)
    ch_variances = {ch: round(float(v), 4) for ch, v in zip(ch_names, variances)}

    # Flat channels
    flat = [ch for ch, v in zip(ch_names, variances)
            if v < FLAT_VARIANCE_UV2 and ch not in NON_EEG_CHANNELS]
    if flat:
        issues.append(("warn", f"flat channels (var<{FLAT_VARIANCE_UV2} µV²): {', '.join(flat)}"))

    # Railed channels
    railed = []
    for i, ch in enumerate(ch_names):
        if ch in NON_EEG_CHANNELS:
            continue
        frac = float(np.mean(np.abs(data_uv[i]) > RAILED_AMPLITUDE_UV))
        if frac > RAILED_FRACTION:
            railed.append(ch)
    if railed:
        issues.append(("warn", f"railed channels (>{RAILED_AMPLITUDE_UV} µV for >{RAILED_FRACTION*100:.0f}%): {', '.join(railed)}"))

    # 50 Hz line noise check — use short FFT segments
    noisy_50hz = _check_line_noise(raw, data_uv, ch_names)
    if noisy_50hz:
        issues.append(("warn", f"excessive {LINE_FREQ} Hz noise: {', '.join(noisy_50hz)}"))

    metrics = {
        "expected_present": len(expected_set & present_set),
        "expected_total": len(expected_set),
        "missing_channels": missing,
        "unexpected_channels": unexpected,
        "fcz_present": fcz_present,
        "flat_channels": flat,
        "railed_channels": railed,
        "noisy_50hz_channels": noisy_50hz,
        "channel_variances_uv2": ch_variances,
    }
    return metrics, issues


def _check_line_noise(raw, data_uv, ch_names):
    """Identify channels with excessive 50 Hz power."""
    sfreq = raw.info["sfreq"]
    # Use 10-second segments, up to 6 segments
    seg_len = int(10 * sfreq)
    n_segs = min(6, data_uv.shape[1] // seg_len)
    if n_segs == 0:
        return []

    # EEG channel indices only
    eeg_idx = [i for i, ch in enumerate(ch_names) if ch not in NON_EEG_CHANNELS]
    if not eeg_idx:
        return []

    # Compute average 50 Hz power per EEG channel
    powers_50 = np.zeros(len(eeg_idx))
    freqs = np.fft.rfftfreq(seg_len, d=1.0 / sfreq)
    # Find indices for 49-51 Hz band
    band_mask = (freqs >= LINE_FREQ - 1) & (freqs <= LINE_FREQ + 1)

    for s in range(n_segs):
        start = s * seg_len
        end = start + seg_len
        for j, ch_i in enumerate(eeg_idx):
            spectrum = np.abs(np.fft.rfft(data_uv[ch_i, start:end])) ** 2
            powers_50[j] += np.mean(spectrum[band_mask])

    powers_50 /= n_segs
    mean_p = np.mean(powers_50)
    std_p = np.std(powers_50)

    noisy = []
    if std_p > 0:
        for j, ch_i in enumerate(eeg_idx):
            if (powers_50[j] - mean_p) / std_p > NOISE_SD_THRESHOLD:
                noisy.append(ch_names[ch_i])
    return noisy


def check_signal_quality(raw, data_uv):
    """Check amplitude distribution, gross artifacts, and DC offset.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    ch_names = raw.ch_names
    sfreq = raw.info["sfreq"]

    # Work with EEG channels only
    eeg_idx = [i for i, ch in enumerate(ch_names) if ch not in NON_EEG_CHANNELS]
    eeg_names = [ch_names[i] for i in eeg_idx]
    eeg_data = data_uv[eeg_idx]

    # Per-channel median absolute amplitude
    per_ch_median = {ch: round(float(np.median(np.abs(eeg_data[j]))), 2)
                     for j, ch in enumerate(eeg_names)}
    overall_median = float(np.median(np.abs(eeg_data)))

    if overall_median > MEDIAN_AMP_WARN_UV:
        issues.append(("fail", f"median amplitude={overall_median:.1f} µV, exceeds {MEDIAN_AMP_WARN_UV}"))

    # Gross artifact detection — 1-second epochs
    epoch_samples = int(ARTIFACT_EPOCH_SEC * sfreq)
    n_epochs = eeg_data.shape[1] // epoch_samples
    n_eeg = len(eeg_idx)
    n_artifact_epochs = 0

    for e in range(n_epochs):
        start = e * epoch_samples
        end = start + epoch_samples
        epoch = eeg_data[:, start:end]
        # Count channels where max |amplitude| > threshold
        ch_exceed = np.sum(np.max(np.abs(epoch), axis=1) > ARTIFACT_AMP_UV)
        if ch_exceed > ARTIFACT_CHAN_FRACTION * n_eeg:
            n_artifact_epochs += 1

    artifact_pct = 100.0 * n_artifact_epochs / n_epochs if n_epochs > 0 else 0.0

    if artifact_pct > ARTIFACT_PCT_FAIL:
        issues.append(("fail", f"gross artifact={artifact_pct:.1f}%, exceeds {ARTIFACT_PCT_FAIL}%"))
    elif artifact_pct > ARTIFACT_PCT_WARN:
        issues.append(("warn", f"gross artifact={artifact_pct:.1f}%, exceeds {ARTIFACT_PCT_WARN}%"))

    # DC offset per channel
    dc_offsets = {ch: round(float(np.mean(eeg_data[j])), 2)
                  for j, ch in enumerate(eeg_names)}
    large_offset = [ch for ch, off in dc_offsets.items()
                    if abs(off) > DC_OFFSET_WARN_UV]
    if large_offset:
        issues.append(("warn", f"large DC offset (>{DC_OFFSET_WARN_UV} µV): {', '.join(large_offset)}"))

    metrics = {
        "median_amplitude_uv": round(overall_median, 2),
        "per_channel_median_uv": per_ch_median,
        "gross_artifact_pct": round(artifact_pct, 2),
        "n_artifact_epochs": n_artifact_epochs,
        "n_total_epochs": n_epochs,
        "dc_offsets_uv": dc_offsets,
        "channels_with_large_offset": large_offset,
    }
    return metrics, issues


def check_condition_markers(raw):
    """Check for EO (S200) and EC (S210) markers.

    Returns (metrics_dict, issues_list).
    """
    issues = []
    sfreq = raw.info["sfreq"]

    # Extract annotations
    eo_onsets = []
    ec_onsets = []
    all_markers = []

    for ann in raw.annotations:
        desc = ann["description"]
        onset = float(ann["onset"])
        all_markers.append({"onset": round(onset, 3), "description": desc})
        if MARKER_EO in desc:
            eo_onsets.append(onset)
        elif MARKER_EC in desc:
            ec_onsets.append(onset)

    eo_count = len(eo_onsets)
    ec_count = len(ec_onsets)
    eo_present = eo_count > 0
    ec_present = ec_count > 0

    # Estimate condition durations from marker spans
    eo_duration_sec = _estimate_condition_duration(eo_onsets)
    ec_duration_sec = _estimate_condition_duration(ec_onsets)

    # Check presence and counts
    if not eo_present:
        issues.append(("fail", f"no EO markers ({MARKER_EO}) found"))
    elif eo_count < MARKER_MIN_FAIL:
        issues.append(("fail", f"only {eo_count} EO markers, expected ~{MARKER_EXPECTED}"))
    elif eo_count < MARKER_EXPECTED:
        issues.append(("warn", f"{eo_count} EO markers, expected ~{MARKER_EXPECTED}"))

    if not ec_present:
        issues.append(("fail", f"no EC markers ({MARKER_EC}) found"))
    elif ec_count < MARKER_MIN_FAIL:
        issues.append(("fail", f"only {ec_count} EC markers, expected ~{MARKER_EXPECTED}"))
    elif ec_count < MARKER_EXPECTED:
        issues.append(("warn", f"{ec_count} EC markers, expected ~{MARKER_EXPECTED}"))

    # Check condition duration (each block ~2.5 min total across all blocks)
    if eo_present and eo_duration_sec < 60:
        issues.append(("warn", f"EO total duration={eo_duration_sec:.0f}s, <1 min"))
    if ec_present and ec_duration_sec < 60:
        issues.append(("warn", f"EC total duration={ec_duration_sec:.0f}s, <1 min"))

    metrics = {
        "eo_marker_count": eo_count,
        "ec_marker_count": ec_count,
        "eo_present": eo_present,
        "ec_present": ec_present,
        "eo_duration_sec": round(eo_duration_sec, 1) if eo_present else None,
        "ec_duration_sec": round(ec_duration_sec, 1) if ec_present else None,
        "total_markers": len(all_markers),
    }
    return metrics, issues


def _estimate_condition_duration(onsets):
    """Estimate total duration of a condition from its marker onset times.

    LEMON has ~30 markers per block at 5-second intervals. The condition
    duration is approximated as (last_onset - first_onset) across all
    blocks of that type, but since blocks alternate we sum per-block spans.
    """
    if len(onsets) < 2:
        return 0.0

    # Group into blocks: consecutive markers within 10s of each other
    blocks = []
    block_start = onsets[0]
    prev = onsets[0]
    for t in onsets[1:]:
        if t - prev > 10:  # gap > 10s means new block
            blocks.append((block_start, prev))
            block_start = t
        prev = t
    blocks.append((block_start, prev))

    # Sum block durations (last marker - first marker + ~5s for the final interval)
    total = sum((end - start + 5.0) for start, end in blocks)
    return total


# ---------------------------------------------------------------------------
# Status determination
# ---------------------------------------------------------------------------

def determine_status(issues):
    """Return 'fail', 'warn', or 'pass' based on issue severities."""
    if any(sev == "fail" for sev, _ in issues):
        return "fail"
    if any(sev == "warn" for sev, _ in issues):
        return "warn"
    return "pass"


# ---------------------------------------------------------------------------
# Main QC worker
# ---------------------------------------------------------------------------

def _load_brainvision_patched(vhdr_path: Path):
    """Load a BrainVision file, fixing mismatched internal file references.

    LEMON raw files were renamed from original subject IDs (e.g. sub-010002)
    to BIDS IDs (e.g. sub-032301), but the .vhdr still references the old
    DataFile/MarkerFile names. This creates a temp patched .vhdr if needed.
    """
    stem = vhdr_path.stem
    content = vhdr_path.read_text()

    needs_patch = False
    for line in content.splitlines():
        if line.startswith("DataFile=") and f"{stem}.eeg" not in line:
            needs_patch = True
            break
        if line.startswith("MarkerFile=") and f"{stem}.vmrk" not in line:
            needs_patch = True
            break

    if not needs_patch:
        return mne.io.read_raw_brainvision(str(vhdr_path), preload=True, verbose=False)

    # Patch references to match actual filenames on disk
    patched_lines = []
    for line in content.splitlines():
        if line.startswith("DataFile="):
            patched_lines.append(f"DataFile={stem}.eeg")
        elif line.startswith("MarkerFile="):
            patched_lines.append(f"MarkerFile={stem}.vmrk")
        else:
            patched_lines.append(line)

    # Write patched .vhdr next to original files so relative paths resolve
    tmp_vhdr = vhdr_path.parent / f".{stem}_patched.vhdr"
    try:
        tmp_vhdr.write_text("\n".join(patched_lines))
        raw = mne.io.read_raw_brainvision(str(tmp_vhdr), preload=True, verbose=False)
    finally:
        tmp_vhdr.unlink(missing_ok=True)

    return raw


def qc_one_subject(vhdr_path: Path) -> dict:
    """Run all QC checks on one subject. Returns QC result dict."""
    subject_id = vhdr_path.parent.parent.name
    result = {
        "subject_id": subject_id,
        "source_file": str(vhdr_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "fail",
        "issues": [],
        "integrity": {},
        "channels": {},
        "signal_quality": {},
        "markers": {},
    }

    # Load raw data (with patched references if needed)
    try:
        raw = _load_brainvision_patched(vhdr_path)
    except Exception as exc:
        result["issues"] = [{"severity": "fail", "check": "load", "message": f"load error: {exc}"}]
        return result

    # Convert to µV once
    data_uv = raw.get_data() * 1e6

    all_issues = []

    # 1. Basic integrity
    try:
        metrics, issues = check_basic_integrity(raw, data_uv)
        result["integrity"] = metrics
        all_issues.extend(("integrity", sev, msg) for sev, msg in issues)
    except Exception as exc:
        all_issues.append(("integrity", "fail", f"check error: {exc}"))

    # 2. Channels
    try:
        metrics, issues = check_channels(raw, data_uv)
        result["channels"] = metrics
        all_issues.extend(("channels", sev, msg) for sev, msg in issues)
    except Exception as exc:
        all_issues.append(("channels", "fail", f"check error: {exc}"))

    # 3. Signal quality
    try:
        metrics, issues = check_signal_quality(raw, data_uv)
        result["signal_quality"] = metrics
        all_issues.extend(("signal_quality", sev, msg) for sev, msg in issues)
    except Exception as exc:
        all_issues.append(("signal_quality", "fail", f"check error: {exc}"))

    # 4. Condition markers
    try:
        metrics, issues = check_condition_markers(raw)
        result["markers"] = metrics
        all_issues.extend(("markers", sev, msg) for sev, msg in issues)
    except Exception as exc:
        all_issues.append(("markers", "fail", f"check error: {exc}"))

    # Build issues list and determine status
    result["issues"] = [
        {"severity": sev, "check": check, "message": msg}
        for check, sev, msg in all_issues
    ]
    result["status"] = determine_status([(sev, msg) for _, sev, msg in all_issues])

    return result


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def write_summary(output_dir: Path, results: list[dict]):
    """Write summary markdown, counts JSON, and ready/excluded lists."""
    # Sort by subject_id
    results = sorted(results, key=lambda r: r["subject_id"])

    # --- Summary markdown ---
    lines = ["# LEMON EEG QC Summary\n"]
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
    lines.append(f"Total subjects: {len(results)}\n")

    n_pass = sum(1 for r in results if r["status"] == "pass")
    n_warn = sum(1 for r in results if r["status"] == "warn")
    n_fail = sum(1 for r in results if r["status"] == "fail")
    lines.append(f"- Pass: {n_pass}")
    lines.append(f"- Warn: {n_warn}")
    lines.append(f"- Fail: {n_fail}\n")

    lines.append("| Subject | Status | Issues |")
    lines.append("|---------|--------|--------|")
    for r in results:
        issues_str = "; ".join(
            f"[{i['severity']}] {i['message']}" for i in r["issues"]
        ) if r["issues"] else ""
        # Truncate long issue strings for readability
        if len(issues_str) > 120:
            issues_str = issues_str[:117] + "..."
        lines.append(f"| {r['subject_id']} | {r['status']} | {issues_str} |")

    (output_dir / "qc_summary.md").write_text("\n".join(lines) + "\n")

    # --- Counts JSON ---
    failure_reasons = {}
    warning_reasons = {}
    for r in results:
        for issue in r["issues"]:
            bucket = failure_reasons if issue["severity"] == "fail" else warning_reasons
            key = issue["check"]
            bucket[key] = bucket.get(key, 0) + 1

    counts = {
        "total": len(results),
        "pass": n_pass,
        "warn": n_warn,
        "fail": n_fail,
        "failure_reasons": failure_reasons,
        "warning_reasons": warning_reasons,
    }
    with open(output_dir / "qc_counts.json", "w") as f:
        json.dump(counts, f, indent=2)

    # --- Ready and excluded lists ---
    ready = [r["subject_id"] for r in results if r["status"] in ("pass", "warn")]
    excluded = [
        (r["subject_id"], "; ".join(i["message"] for i in r["issues"] if i["severity"] == "fail"))
        for r in results if r["status"] == "fail"
    ]

    (output_dir / "ready_subjects.txt").write_text("\n".join(ready) + "\n" if ready else "")
    excluded_lines = [f"{sid}\t{reason}" for sid, reason in excluded]
    (output_dir / "excluded_subjects.txt").write_text(
        "\n".join(excluded_lines) + "\n" if excluded_lines else ""
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for LEMON raw EEG data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Path to LEMON EEG_Raw_BIDS_ID directory",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("./lemon_qc_output"),
        help="Output directory (default: ./lemon_qc_output)",
    )
    parser.add_argument(
        "--max-subjects",
        type=int,
        default=0,
        help="Limit to N subjects (0 = all, useful for testing)",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)",
    )
    args = parser.parse_args()

    # Setup
    output_dir = args.output
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(output_dir)

    # Discover subjects
    all_subjects = discover_subjects(args.data_dir)
    logger.info(f"Found {len(all_subjects)} subjects in {args.data_dir}")

    # Resumability — skip already QC'd
    done = load_existing_qc(subjects_dir)
    if done:
        logger.info(f"Found {len(done)} existing QC results — will skip those.")

    if args.max_subjects > 0:
        # Limit total subjects (including already-done)
        remaining = args.max_subjects - len(done)
        todo = [(sid, path) for sid, path in all_subjects if sid not in done]
        todo = todo[:max(0, remaining)]
    else:
        todo = [(sid, path) for sid, path in all_subjects if sid not in done]

    logger.info(f"Will QC {len(todo)} new subjects (workers={args.workers})")

    if not todo:
        logger.info("Nothing to do.")
    else:
        start_time = time.time()
        processed = 0
        errors = 0

        if args.workers > 1:
            # Parallel
            paths = [path for _, path in todo]
            with multiprocessing.Pool(args.workers) as pool:
                for result in pool.imap_unordered(qc_one_subject, paths):
                    save_subject_qc(subjects_dir, result)
                    processed += 1
                    if result["status"] == "fail":
                        errors += 1
                    elapsed = time.time() - start_time
                    rate = processed / (elapsed / 60) if elapsed > 0 else 0
                    logger.info(
                        f"[{processed}/{len(todo)}] {result['subject_id']}: "
                        f"{result['status']} ({rate:.1f} subj/min)"
                    )
        else:
            # Sequential
            for sid, vhdr_path in todo:
                result = qc_one_subject(vhdr_path)
                save_subject_qc(subjects_dir, result)
                processed += 1
                if result["status"] == "fail":
                    errors += 1
                elapsed = time.time() - start_time
                rate = processed / (elapsed / 60) if elapsed > 0 else 0
                logger.info(
                    f"[{processed}/{len(todo)}] {result['subject_id']}: "
                    f"{result['status']} ({rate:.1f} subj/min)"
                )

        elapsed_total = time.time() - start_time
        logger.info(
            f"\nQC complete: {processed} subjects in {elapsed_total / 60:.1f} min, "
            f"{errors} failures"
        )

    # Generate summary from all results (including previously checkpointed)
    all_results = load_all_results(subjects_dir)
    logger.info(f"Writing summary for {len(all_results)} total subjects...")
    write_summary(output_dir, all_results)

    logger.info(f"\nOutput files:")
    logger.info(f"  {output_dir / 'qc_summary.md'}")
    logger.info(f"  {output_dir / 'qc_counts.json'}")
    logger.info(f"  {output_dir / 'ready_subjects.txt'}")
    logger.info(f"  {output_dir / 'excluded_subjects.txt'}")
    logger.info(f"  {subjects_dir}/ (per-subject JSONs)")


if __name__ == "__main__":
    main()
