#!/usr/bin/env python3
"""QC sweep for LEMON EEG data — run before the normative pipeline.

Loads each subject's raw EEG file and checks basic integrity, channel
quality, signal quality, and condition markers.  Produces per-subject
JSON files, a summary markdown report, and ready/excluded subject lists.

Usage:
    # Quick test with 5 subjects
    python scripts/lemon_qc.py ~/Data/EEG/LEMON/EEG_Raw_BIDS_ID \
        -o ./lemon_qc_output --max-subjects 5

    # Full QC sweep, 4 parallel workers
    python scripts/lemon_qc.py ~/Data/EEG/LEMON/EEG_Raw_BIDS_ID \
        -o ./lemon_qc_output -j 4

    # Resume an interrupted run (skips already-completed subjects)
    python scripts/lemon_qc.py ~/Data/EEG/LEMON/EEG_Raw_BIDS_ID \
        -o ./lemon_qc_output
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import mne
import numpy as np


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""

    def default(self, obj):
        if isinstance(obj, (np.bool_, np.integer)):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

from open_normative.datasets.lemon import _fix_vhdr_refs, _EO_MARKER, _EC_MARKER

logger = logging.getLogger("lemon_qc")

# ── Constants ────────────────────────────────────────────────────────────────

EXPECTED_SFREQ = 2500.0
EXPECTED_N_CHANNELS = 62
MIN_DURATION_S = 180.0      # 3 minutes
MAX_DURATION_S = 1200.0     # 20 minutes
FLAT_VAR_THRESHOLD = 0.1    # µV² — channels with variance below this are "flat"
RAIL_AMP_THRESHOLD = 500.0  # µV — absolute amplitude threshold for railing
RAIL_FRACTION = 0.10        # fraction of samples above rail threshold to flag
LINE_NOISE_FREQ = 50.0      # Hz — LEMON was recorded in Germany (50 Hz mains)
LINE_NOISE_SD = 3.0         # flag channels with line noise power > 3 SD above mean
ARTIFACT_AMP = 200.0        # µV — amplitude threshold for gross artifact detection
ARTIFACT_CHAN_FRAC = 0.50    # fraction of channels that must exceed threshold
DC_OFFSET_THRESHOLD = 40.0  # µV — flag channels with |mean| > this
MIN_CONDITION_S = 60.0      # seconds — minimum condition duration to be valid

# Expected 62 EEG channels in the LEMON dataset (10-10 montage).
# FCz was the online reference and should NOT appear as a data channel.
EXPECTED_CHANNELS = {
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "FC5", "FC1", "FC2", "FC6",
    "T7", "C3", "Cz", "C4", "T8",
    "CP5", "CP1", "CP2", "CP6",
    "P7", "P3", "Pz", "P4", "P8",
    "PO9", "O1", "Oz", "O2", "PO10",
    "AF7", "AF3", "AF4", "AF8",
    "F5", "F1", "F2", "F6",
    "FT7", "FC3", "FC4", "FT8",
    "C5", "C1", "C2", "C6",
    "TP7", "CP3", "CPz", "CP4", "TP8",
    "P5", "P1", "P2", "P6",
    "PO7", "PO3", "POz", "PO4", "PO8",
    "Fpz",
}


# ── Check functions ──────────────────────────────────────────────────────────

def check_integrity(raw, vhdr_path):
    """Basic integrity checks: sampling rate, channel count, duration."""
    sfreq = raw.info["sfreq"]
    n_ch = len(raw.ch_names)
    duration = raw.times[-1]

    return {
        "sfreq": sfreq,
        "sfreq_ok": sfreq == EXPECTED_SFREQ,
        "n_channels": n_ch,
        "n_channels_ok": n_ch == EXPECTED_N_CHANNELS,
        "duration_s": round(duration, 1),
        "duration_ok": MIN_DURATION_S <= duration <= MAX_DURATION_S,
    }


def check_channels(raw):
    """Channel-level checks: missing, flat, railed, line noise, FCz."""
    ch_set = set(raw.ch_names)
    missing = sorted(EXPECTED_CHANNELS - ch_set)
    unexpected = sorted(ch_set - EXPECTED_CHANNELS)
    fcz_present = "FCz" in ch_set

    # Get data in µV
    data = raw.get_data() * 1e6  # V → µV

    # Flat channels: variance < threshold
    var = np.var(data, axis=1)
    flat = [raw.ch_names[i] for i in range(len(raw.ch_names)) if var[i] < FLAT_VAR_THRESHOLD]

    # Railed channels: |amplitude| > threshold for > RAIL_FRACTION of samples
    n_samples = data.shape[1]
    railed_frac = np.mean(np.abs(data) > RAIL_AMP_THRESHOLD, axis=1)
    railed = [raw.ch_names[i] for i in range(len(raw.ch_names)) if railed_frac[i] > RAIL_FRACTION]

    # Line noise: 50 Hz power per channel, flag > 3 SD above mean
    line_noise = []
    try:
        psds, freqs = mne.time_frequency.psd_array_welch(
            data / 1e6,  # back to V for MNE
            sfreq=raw.info["sfreq"],
            fmin=LINE_NOISE_FREQ - 1,
            fmax=LINE_NOISE_FREQ + 1,
            n_fft=int(raw.info["sfreq"] * 2),
            verbose=False,
        )
        # Find the bin closest to the line noise frequency
        idx = np.argmin(np.abs(freqs - LINE_NOISE_FREQ))
        noise_power = psds[:, idx]
        if len(noise_power) > 1 and np.std(noise_power) > 0:
            z = (noise_power - np.mean(noise_power)) / np.std(noise_power)
            line_noise = [raw.ch_names[i] for i in range(len(z)) if z[i] > LINE_NOISE_SD]
    except Exception:
        pass

    return {
        "missing_channels": missing,
        "unexpected_channels": unexpected,
        "flat_channels": flat,
        "railed_channels": railed,
        "line_noise_channels": line_noise,
        "fcz_present": fcz_present,
    }


def check_signal_quality(raw):
    """Signal-level checks: amplitude stats, artifact %, DC offset."""
    data = raw.get_data() * 1e6  # µV
    n_ch, n_samples = data.shape
    sfreq = raw.info["sfreq"]

    # Amplitude stats
    amp_mean = float(np.mean(np.abs(data)))
    amp_std = float(np.std(data))
    amp_max = float(np.max(np.abs(data)))

    # Artifact percentage: 1-second windows where >50% of channels exceed 200 µV
    window = int(sfreq)
    n_windows = n_samples // window
    artifact_count = 0
    for w in range(n_windows):
        segment = data[:, w * window : (w + 1) * window]
        max_per_ch = np.max(np.abs(segment), axis=1)
        if np.mean(max_per_ch > ARTIFACT_AMP) > ARTIFACT_CHAN_FRAC:
            artifact_count += 1
    artifact_pct = round(100.0 * artifact_count / max(n_windows, 1), 1)

    # DC offset per channel
    dc = np.mean(data, axis=1)
    dc_channels = [raw.ch_names[i] for i in range(n_ch) if abs(dc[i]) > DC_OFFSET_THRESHOLD]

    return {
        "amplitude_mean_uv": round(amp_mean, 1),
        "amplitude_std_uv": round(amp_std, 1),
        "amplitude_max_uv": round(amp_max, 1),
        "artifact_pct": artifact_pct,
        "dc_offset_channels": dc_channels,
        "mean_dc_offset_uv": round(float(np.mean(np.abs(dc))), 2),
    }


def check_markers(raw):
    """Condition marker checks: S210 (EO) and S200 (EC) presence and duration."""
    eo_onsets = []
    ec_onsets = []
    for ann in raw.annotations:
        desc = ann["description"].strip()
        if desc == _EO_MARKER:
            eo_onsets.append(ann["onset"])
        elif desc == _EC_MARKER:
            ec_onsets.append(ann["onset"])

    def _condition_duration(onsets):
        if len(onsets) < 2:
            return 0.0
        s = sorted(onsets)
        epoch_dur = float(np.median(np.diff(s)))
        return s[-1] - s[0] + epoch_dur

    eo_dur = _condition_duration(eo_onsets)
    ec_dur = _condition_duration(ec_onsets)

    return {
        "eo_marker_count": len(eo_onsets),
        "ec_marker_count": len(ec_onsets),
        "eo_duration_s": round(eo_dur, 1),
        "ec_duration_s": round(ec_dur, 1),
        "eo_ok": eo_dur >= MIN_CONDITION_S,
        "ec_ok": ec_dur >= MIN_CONDITION_S,
    }


# ── Verdict ──────────────────────────────────────────────────────────────────

def compute_verdict(integrity, channels, signal, markers):
    """Combine all checks into a verdict: ready / review / exclude."""
    reasons = []

    # Exclude conditions
    if not integrity["sfreq_ok"]:
        reasons.append(f"sfreq={integrity['sfreq']} (expected {EXPECTED_SFREQ})")
    if integrity["n_channels"] < 50:
        reasons.append(f"only {integrity['n_channels']} channels")
    if integrity["duration_s"] < 60:
        reasons.append(f"duration={integrity['duration_s']}s (<1 min)")
    if signal["artifact_pct"] > 50:
        reasons.append(f"artifact={signal['artifact_pct']}% (>50%)")
    if markers["eo_marker_count"] == 0 and markers["ec_marker_count"] == 0:
        reasons.append("no EO or EC markers")

    if reasons:
        return "exclude", reasons

    # Review conditions
    if not integrity["duration_ok"]:
        reasons.append(f"duration={integrity['duration_s']}s (outside {MIN_DURATION_S}-{MAX_DURATION_S}s)")
    if not integrity["n_channels_ok"]:
        reasons.append(f"{integrity['n_channels']} channels (expected {EXPECTED_N_CHANNELS})")
    if len(channels["flat_channels"]) > 5:
        reasons.append(f"{len(channels['flat_channels'])} flat channels")
    if len(channels["railed_channels"]) > 5:
        reasons.append(f"{len(channels['railed_channels'])} railed channels")
    if len(channels["line_noise_channels"]) > 5:
        reasons.append(f"{len(channels['line_noise_channels'])} line-noise channels")
    if signal["artifact_pct"] > 20:
        reasons.append(f"artifact={signal['artifact_pct']}%")
    if not markers["eo_ok"]:
        reasons.append(f"EO duration={markers['eo_duration_s']}s (<{MIN_CONDITION_S}s)")
    if not markers["ec_ok"]:
        reasons.append(f"EC duration={markers['ec_duration_s']}s (<{MIN_CONDITION_S}s)")
    if channels["fcz_present"]:
        reasons.append("FCz present (expected to be reference)")

    if reasons:
        return "review", reasons

    return "ready", []


# ── Per-subject runner ───────────────────────────────────────────────────────

def qc_one_subject(subject_id, vhdr_path):
    """Run all QC checks on a single subject. Returns a result dict."""
    result = {
        "subject_id": subject_id,
        "vhdr_path": str(vhdr_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        load_path = _fix_vhdr_refs(vhdr_path)
        raw = mne.io.read_raw_brainvision(str(load_path), preload=True, verbose=False)
    except Exception as e:
        result.update({
            "verdict": "exclude",
            "reasons": [f"load error: {e}"],
            "integrity": {}, "channels": {}, "signal_quality": {}, "markers": {},
        })
        return result

    # Markers first (uses annotations, independent of channel picking)
    markers = check_markers(raw)

    # Pick EEG only for remaining checks
    raw.pick("eeg")

    integrity = check_integrity(raw, vhdr_path)
    channels = check_channels(raw)
    signal = check_signal_quality(raw)
    verdict, reasons = compute_verdict(integrity, channels, signal, markers)

    result.update({
        "verdict": verdict,
        "reasons": reasons,
        "integrity": integrity,
        "channels": channels,
        "signal_quality": signal,
        "markers": markers,
    })
    return result


# ── File discovery ───────────────────────────────────────────────────────────

def discover_subjects(data_dir):
    """Find all .vhdr files and return (subject_id, vhdr_path) pairs."""
    vhdr_files = sorted(
        set(data_dir.glob("sub-*/eeg/*.vhdr"))
        | set(data_dir.glob("sub-*/RSEEG/*.vhdr"))
        | set(data_dir.glob("sub-*/ses-*/eeg/*.vhdr"))
    )
    subjects = []
    seen = set()
    for vhdr_path in vhdr_files:
        subject_id = None
        for part in vhdr_path.parts:
            if part.startswith("sub-"):
                subject_id = part
        if subject_id and subject_id not in seen:
            seen.add(subject_id)
            subjects.append((subject_id, vhdr_path))
    return subjects


# ── Resume support ───────────────────────────────────────────────────────────

def load_existing(output_dir):
    """Load already-completed QC results. Returns {subject_id: result_dict}."""
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


# ── Summary generation ───────────────────────────────────────────────────────

def generate_summary(output_dir, results):
    """Write summary.md, ready.txt, and excluded.txt."""
    ready = [r for r in results if r["verdict"] == "ready"]
    review = [r for r in results if r["verdict"] == "review"]
    exclude = [r for r in results if r["verdict"] == "exclude"]

    # Reason frequency
    reason_counts = {}
    for r in results:
        for reason in r.get("reasons", []):
            # Normalize reason to category
            key = reason.split("=")[0].split(":")[0].strip()
            reason_counts[key] = reason_counts.get(key, 0) + 1

    lines = [
        "# LEMON EEG QC Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Total subjects:** {len(results)}",
        "",
        "## Summary",
        "",
        f"| Verdict | Count |",
        f"|---------|-------|",
        f"| Ready   | {len(ready)} |",
        f"| Review  | {len(review)} |",
        f"| Exclude | {len(exclude)} |",
        "",
    ]

    if reason_counts:
        lines += [
            "## Issue Frequency",
            "",
            "| Issue | Count |",
            "|-------|-------|",
        ]
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    if exclude:
        lines += [
            "## Excluded Subjects",
            "",
            "| Subject | Reasons |",
            "|---------|---------|",
        ]
        for r in sorted(exclude, key=lambda x: x["subject_id"]):
            reasons = "; ".join(r.get("reasons", []))
            lines.append(f"| {r['subject_id']} | {reasons} |")
        lines.append("")

    if review:
        lines += [
            "## Subjects Needing Review",
            "",
            "| Subject | Reasons |",
            "|---------|---------|",
        ]
        for r in sorted(review, key=lambda x: x["subject_id"]):
            reasons = "; ".join(r.get("reasons", []))
            lines.append(f"| {r['subject_id']} | {reasons} |")
        lines.append("")

    # Channel issue details for review/exclude subjects
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
        lines += [
            "## Channel Issues Across Subjects",
            "",
            "| Channel | Flat | Railed | Line Noise |",
            "|---------|------|--------|------------|",
        ]
        all_ch = sorted(set(flat_all) | set(railed_all) | set(noise_all))
        for ch in all_ch:
            lines.append(
                f"| {ch} | {flat_all.get(ch, 0)} | "
                f"{railed_all.get(ch, 0)} | {noise_all.get(ch, 0)} |"
            )
        lines.append("")

    (output_dir / "summary.md").write_text("\n".join(lines))

    # Subject lists
    (output_dir / "ready.txt").write_text(
        "\n".join(r["subject_id"] for r in sorted(ready, key=lambda x: x["subject_id"])) + "\n"
    )
    (output_dir / "excluded.txt").write_text(
        "\n".join(r["subject_id"] for r in sorted(exclude, key=lambda x: x["subject_id"])) + "\n"
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

def setup_logging(output_dir):
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)
    error_log = output_dir / "qc_errors.log"
    fh = logging.FileHandler(error_log)
    fh.setLevel(logging.WARNING)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)


def main():
    parser = argparse.ArgumentParser(
        description="QC sweep for LEMON EEG data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("data_dir", type=Path, help="Path to LEMON data root")
    parser.add_argument("--output", "-o", type=Path, default=Path("./lemon_qc_output"))
    parser.add_argument("--max-subjects", type=int, default=0, help="Limit (0=all)")
    parser.add_argument("--jobs", "-j", type=int, default=1, help="Parallel workers")
    parser.add_argument(
        "--line-freq", type=float, default=LINE_NOISE_FREQ,
        help=f"Mains frequency in Hz (default: {LINE_NOISE_FREQ} for Europe)",
    )
    args = parser.parse_args()

    subjects_dir = args.output / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(args.output)

    # Discover and filter
    all_subjects = discover_subjects(args.data_dir)
    logger.info("Found %d subjects in %s", len(all_subjects), args.data_dir)

    existing = load_existing(args.output)
    if existing:
        logger.info("Resuming: %d already completed", len(existing))

    todo = [(sid, p) for sid, p in all_subjects if sid not in existing]
    if args.max_subjects > 0:
        todo = todo[: args.max_subjects]
    logger.info("Will QC %d subjects (%d jobs)", len(todo), args.jobs)

    # Process
    new_results = []
    start = time.time()

    if args.jobs <= 1:
        for i, (sid, vhdr) in enumerate(todo):
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info("[%d/%d] %s (%.1f subj/min)", i + 1, len(todo), sid, rate * 60)
            result = qc_one_subject(sid, vhdr)
            # Save checkpoint
            (subjects_dir / f"{sid}.json").write_text(json.dumps(result, indent=2, cls=_NumpyEncoder))
            new_results.append(result)
            logger.info("  → %s%s", result["verdict"],
                         f" ({', '.join(result['reasons'])})" if result["reasons"] else "")
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(qc_one_subject, sid, vhdr): sid
                for sid, vhdr in todo
            }
            for i, future in enumerate(as_completed(futures)):
                sid = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {
                        "subject_id": sid, "verdict": "exclude",
                        "reasons": [f"worker error: {e}"],
                        "integrity": {}, "channels": {}, "signal_quality": {}, "markers": {},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                (subjects_dir / f"{sid}.json").write_text(json.dumps(result, indent=2, cls=_NumpyEncoder))
                new_results.append(result)
                logger.info("[%d/%d] %s → %s", i + 1, len(todo), sid, result["verdict"])

    elapsed = time.time() - start
    logger.info("\nQC complete: %d subjects in %.1f min", len(todo), elapsed / 60)

    # Combine all results for summary
    all_results = list(existing.values()) + new_results
    generate_summary(args.output, all_results)

    ready = sum(1 for r in all_results if r["verdict"] == "ready")
    review = sum(1 for r in all_results if r["verdict"] == "review")
    exclude = sum(1 for r in all_results if r["verdict"] == "exclude")
    logger.info("Results: %d ready, %d review, %d exclude", ready, review, exclude)
    logger.info("Report: %s", args.output / "summary.md")


if __name__ == "__main__":
    main()
