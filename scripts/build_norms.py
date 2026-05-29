#!/usr/bin/env python3
"""Build normative distributions from a public EEG dataset.

Usage:
    python scripts/build_norms.py /path/to/lemon --output ./norms_output

    # Test with 5 subjects first:
    python scripts/build_norms.py /path/to/lemon --output ./test_output --max-subjects 5

    # Eyes-open only, skip connectivity (fast):
    python scripts/build_norms.py /path/to/lemon --output ./test_output \
        --condition eo --skip-connectivity --max-subjects 10

    # Merge multiple datasets (no processing, just combine existing checkpoints):
    python scripts/build_norms.py --merge \
        --merge-dir ./lemon_norms/subjects \
        --merge-dir ./dortmund_norms/subjects \
        --output ./merged_norms
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import traceback
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats

from open_normative.datasets import DATASETS
from open_normative.io import write_norms_csv, write_norms_json, write_norms_npz, write_subjects_csv
from open_normative.normative import build_normative, _PERCENTILE_POINTS
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.pipeline import process_resting


def _process_one_subject(
    filepath: str,
    subject_id: str,
    age: float,
    sex: str,
    condition: str,
    n_channels: int,
    params: dict | None,
    skip_connectivity: bool,
    source: bool = False,
    ba_connectivity: bool = False,
    dk_connectivity: bool = False,
    dk_corrected_power: bool = False,
    marker_condition: str | None = None,
) -> dict:
    """Worker function for parallel subject processing.

    Loads raw data, standardizes channels, and runs the full pipeline.
    Designed to be called from ProcessPoolExecutor (must be top-level
    and all arguments must be picklable).

    Returns the subject_data dict ready for checkpointing.
    Raises RuntimeError on failure (never FloatingPointError or other
    errors that could kill the worker process).
    """
    try:
        import mne
        import numpy as np
        from open_normative.channels import pick_standard_channels

        np.seterr(all="warn")

        filepath = Path(filepath)
        ext = filepath.suffix.lower()

        # Load raw data
        loaders = {
            ".vhdr": mne.io.read_raw_brainvision,
            ".edf": mne.io.read_raw_edf,
            ".set": mne.io.read_raw_eeglab,
            ".fif": mne.io.read_raw_fif,
            ".mff": mne.io.read_raw_egi,
        }
        raw = loaders[ext](str(filepath), preload=True, verbose=False)
        raw.pick("eeg")

        # Handle single-file recordings with marker-based condition splitting
        if marker_condition is not None:
            from open_normative.datasets.lemon import _split_by_markers
            splits = _split_by_markers(raw)
            if marker_condition in splits:
                raw = splits[marker_condition]
            else:
                raise ValueError(
                    f"Condition {marker_condition} not found in markers "
                    f"for {filepath}"
                )

        raw = pick_standard_channels(raw, n_channels=n_channels)

        result = process_resting(
            raw,
            condition=condition,
            params=params,
            skip_connectivity=skip_connectivity,
            source=source,
            ba_connectivity=ba_connectivity,
            dk_connectivity=dk_connectivity,
            dk_corrected_power=dk_corrected_power,
        )

        return {
            "subject_id": subject_id,
            "age": age,
            "sex": sex,
            "condition": condition,
            "metrics": result.to_nested_dict(),
            "_spectral": result.spectral,
        }
    except BaseException as exc:
        # Convert any error (including FloatingPointError, which can kill
        # the ProcessPoolExecutor) into a RuntimeError so the pool survives.
        raise RuntimeError(
            f"{subject_id} ({condition}): {type(exc).__name__}: {exc}"
        ) from None


def _save_subject_result(
    subject_data: dict,
    subjects_dir: Path,
    psd_dir: Path | None,
    subjects_for_norms: list,
) -> list[Path]:
    """Checkpoint a processed subject and optionally save PSD data.

    Returns the list of files written, in output-dir-relative form suitable
    for mirroring to remote storage.
    """
    spectral = subject_data.pop("_spectral", None)
    written: list[Path] = []

    json_path = save_checkpoint(
        subjects_dir, subject_data["subject_id"],
        subject_data["condition"], subject_data,
    )
    written.append(json_path)

    if psd_dir is not None and spectral is not None:
        psds = spectral.get("psds")
        freqs = spectral.get("freqs")
        ch_names = spectral.get("ch_names", [])
        if psds is not None and freqs is not None:
            psd_path = save_psd_checkpoint(
                psd_dir, subject_data["subject_id"],
                subject_data["condition"], freqs, psds, ch_names,
            )
            written.append(psd_path)

    subjects_for_norms.append(subject_data)
    return written


_S3_WARN_EMITTED = False


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    """Split ``s3://bucket/prefix/...`` into (bucket, prefix)."""
    if not uri.startswith("s3://"):
        raise ValueError(f"--checkpoint-sync requires an s3:// URI, got: {uri!r}")
    rest = uri[len("s3://"):]
    if "/" in rest:
        bucket, prefix = rest.split("/", 1)
    else:
        bucket, prefix = rest, ""
    if not bucket:
        raise ValueError(f"--checkpoint-sync URI missing bucket: {uri!r}")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return bucket, prefix


def _sync_checkpoint_files(
    files: list[Path],
    output_dir: Path,
    bucket: str,
    prefix: str,
    logger: logging.Logger,
) -> None:
    """Upload the given checkpoint files to ``s3://bucket/prefix/<relpath>``.

    Failures are logged but do not raise: the local checkpoint is still on
    disk, and a subsequent container retry will re-sync it.
    """
    global _S3_WARN_EMITTED
    try:
        import boto3
    except ImportError:
        if not _S3_WARN_EMITTED:
            logger.warning(
                "--checkpoint-sync requested but boto3 is not installed; "
                "install with `pip install 'open-normative-eeg[aws]'` or "
                "`pip install boto3`. Continuing without remote sync."
            )
            _S3_WARN_EMITTED = True
        return

    client = boto3.client("s3")
    for path in files:
        try:
            key = prefix + str(path.relative_to(output_dir))
        except ValueError:
            logger.warning(
                f"checkpoint-sync: {path} not under output dir {output_dir}; skipping"
            )
            continue
        try:
            client.upload_file(str(path), bucket, key)
        except Exception as exc:
            logger.warning(
                f"checkpoint-sync: failed to upload {path} to s3://{bucket}/{key}: "
                f"{type(exc).__name__}: {exc}"
            )


def setup_logging(output_dir: Path) -> logging.Logger:
    """Configure logging to both console and error log file."""
    logger = logging.getLogger("build_norms")
    logger.setLevel(logging.INFO)

    # Console: INFO and above
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    # File: WARNING and above (errors and tracebacks)
    error_log = output_dir / "errors.log"
    file_handler = logging.FileHandler(error_log)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )
    logger.addHandler(file_handler)

    return logger


def save_checkpoint(subjects_dir: Path, subject_id: str, condition: str, metrics: dict) -> Path:
    """Save a single subject's metrics as a checkpoint JSON. Returns the path written."""
    fname = f"{subject_id}_{condition}.json"
    fpath = subjects_dir / fname
    with open(fpath, "w") as f:
        json.dump(metrics, f)
    return fpath


def save_psd_checkpoint(psd_dir: Path, subject_id: str, condition: str,
                        freqs: np.ndarray, psds: np.ndarray, ch_names: list) -> Path:
    """Save a single subject's full PSD array as an .npz checkpoint. Returns the path written."""
    fname = f"{subject_id}_{condition}_psd.npz"
    fpath = psd_dir / fname
    np.savez_compressed(
        fpath,
        freqs=freqs,
        psds=psds,  # shape (n_channels, n_freqs), V²/Hz
        ch_names=np.array(ch_names),
    )
    return fpath


def load_psd_checkpoint(fpath: Path) -> dict:
    """Load a PSD checkpoint .npz file."""
    data = np.load(fpath, allow_pickle=False)
    return {
        "freqs": data["freqs"],
        "psds": data["psds"],
        "ch_names": list(data["ch_names"]),
    }


def load_checkpoints(subjects_dir: Path) -> dict[str, dict]:
    """Load all existing checkpoint files. Returns {subject_id_condition: metrics_dict}."""
    checkpoints = {}
    if not subjects_dir.exists():
        return checkpoints
    for fpath in subjects_dir.glob("*.json"):
        key = fpath.stem  # e.g., "sub-010002_eo"
        try:
            with open(fpath) as f:
                checkpoints[key] = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logging.getLogger(__name__).warning(
                f"Skipping corrupt checkpoint {fpath.name}: {exc}"
            )
    return checkpoints


def save_run_config(output_dir: Path, args: argparse.Namespace):
    """Save the parameters used for this run."""
    config = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "data_dir": str(args.data_dir),
        "output": str(args.output),
        "condition": args.condition,
        "channels": args.channels,
        "max_subjects": args.max_subjects,
        "skip_connectivity": args.skip_connectivity,
        "save_psd": args.save_psd,
        "age_bins": args.age_bins,
        "pipeline_params": PIPELINE_PARAMS,
    }
    with open(output_dir / "run_config.json", "w") as f:
        json.dump(config, f, indent=2, default=str)


# Unit-sanity bounds for a per-subject alpha-band (8–13 Hz) PSD median, in
# V²/Hz. Clean EEG sits ~1e-14..1e-11 (observed LEMON/Dortmund/SRM range
# 2.6e-14..9.5e-9); values far outside betray a unit error — e.g. a dataset
# stored in µV²/Hz but treated as V²/Hz inflates power by ~1e12. See the SRM
# blank-EDF-units bug (2026-05): its alpha median read ~1e0 before the fix.
_PSD_ALPHA_UNIT_MIN = 1e-16
_PSD_ALPHA_UNIT_MAX = 1e-7


_PSD_SEX_ORDER = ["pooled", "F", "M"]
_PSD_N_SEX = len(_PSD_SEX_ORDER)


def _compute_psd_slab(psd_dir: Path, subjects_for_norms: list,
                      age_bins: list, logger) -> dict | None:
    """Aggregate per-subject PSD curves into normative PSD statistics.

    Returns a dict of arrays suitable for ``np.savez_compressed``, or ``None``
    if there are no valid PSD checkpoints to aggregate (preserving the
    early-return behaviour of the previous monolithic function).

    The dict contains:
        freqs: (n_freqs,) frequency vector
        bins: list of bin labels (e.g., "20-29")
        conditions: list of conditions
        sexes: ["pooled", "F", "M"]
        ch_names: list of channel names
        mean: (n_bins, n_conditions, 3, n_channels, n_freqs) log10 PSD mean
        sd: (n_bins, n_conditions, 3, n_channels, n_freqs) log10 PSD SD
        n: (n_bins, n_conditions, 3) subject counts
        percentile_points: (n_points,) percentile values (mirrors _PERCENTILE_POINTS)
        percentiles: (n_bins, n_conditions, 3, n_channels, n_freqs, n_points) float32,
            log10 space; NaN where n < 2
        normality_p: (n_bins, n_conditions, 3, n_channels, n_freqs) float32
            Shapiro-Wilk p of the log space; NaN where n < 3
        psd_format_version: scalar int (3); consumers branch on its presence
    """
    # Build lookup: subject_id → age, condition, sex
    subject_info = {}
    for s in subjects_for_norms:
        key = f"{s['subject_id']}_{s['condition']}"
        subject_info[key] = {
            "age": s["age"],
            "condition": s["condition"],
            "sex": s.get("sex", ""),
        }

    # Load all PSD checkpoints
    psd_files = sorted(psd_dir.glob("*_psd.npz"))
    if not psd_files:
        logger.warning("No PSD checkpoints found — skipping normative PSD build.")
        return None

    logger.info(f"Building normative PSD from {len(psd_files)} PSD checkpoints...")

    # Determine bin labels
    bin_labels = []
    for i in range(len(age_bins) - 1):
        bin_labels.append(f"{age_bins[i]}-{age_bins[i + 1] - 1}")

    def age_to_bin(age):
        for i in range(len(age_bins) - 1):
            if age_bins[i] <= age < age_bins[i + 1]:
                return bin_labels[i]
        return None

    # Collect PSD data grouped by (bin, condition, sex)
    # {(bin_label, condition, sex): [(ch_names, log10_psds), ...]}
    # Each subject is fanned to "pooled" + their own sex bucket (if F or M).
    grouped: dict[tuple, list] = {}
    ref_freqs = None
    suspect_units = []  # (stem, alpha_median) for checkpoints failing the unit check

    for fpath in psd_files:
        stem = fpath.stem.replace("_psd", "")  # e.g., "sub-010002_eo"
        info = subject_info.get(stem)
        if info is None:
            continue

        age_bin = age_to_bin(info["age"])
        if age_bin is None:
            continue

        psd_data = load_psd_checkpoint(fpath)
        freqs = psd_data["freqs"]
        psds = psd_data["psds"]  # (n_ch, n_freqs) in V²/Hz
        ch_names = psd_data["ch_names"]

        # Unit-sanity check on the raw V²/Hz values before the µV² conversion.
        alpha_mask = (freqs >= 8.0) & (freqs <= 13.0)
        if np.any(alpha_mask):
            alpha_med = float(np.nanmedian(psds[:, alpha_mask]))
            if alpha_med > 0 and not (
                _PSD_ALPHA_UNIT_MIN <= alpha_med <= _PSD_ALPHA_UNIT_MAX
            ):
                suspect_units.append((stem, alpha_med))

        if ref_freqs is None:
            ref_freqs = freqs
        elif len(freqs) != len(ref_freqs):
            continue  # skip mismatched frequency resolution

        # Convert to log10(µV²/Hz)
        psds_uv = psds * 1e12  # V²/Hz → µV²/Hz
        psds_uv = np.maximum(psds_uv, 1e-30)  # avoid log(0)
        log10_psds = np.log10(psds_uv)

        # Normalise sex to "F", "M", or None (other/empty → pooled-only).
        raw_sex = str(info.get("sex", "") or "").strip().upper()
        subject_sex = raw_sex if raw_sex in {"F", "M"} else None

        # Fan to pooled + own sex bucket.
        for sex_slot in ("pooled", subject_sex):
            if sex_slot is None:
                continue
            key = (age_bin, info["condition"], sex_slot)
            grouped.setdefault(key, []).append((ch_names, log10_psds))

    if suspect_units:
        examples = ", ".join(f"{s}={v:.2e}" for s, v in suspect_units[:5])
        logger.warning(
            "Unit-sanity: %d/%d PSD checkpoints have an alpha-band median outside "
            "[%.0e, %.0e] V²/Hz — likely a unit mismatch (e.g. µV²/Hz mislabeled "
            "as V²/Hz, ~1e12 inflation). Examples: %s",
            len(suspect_units), len(psd_files),
            _PSD_ALPHA_UNIT_MIN, _PSD_ALPHA_UNIT_MAX, examples,
        )

    if not grouped or ref_freqs is None:
        logger.warning("No valid PSD data to aggregate.")
        return None

    # Get canonical channel list from first entry
    # Use only the "pooled" keys to determine conditions/channels, since pooled
    # always has all subjects.
    all_conditions = sorted({k[1] for k in grouped})
    all_ch_names = list(grouped[next(iter(grouped))][0][0])
    n_freqs = len(ref_freqs)
    n_bins = len(bin_labels)
    n_conds = len(all_conditions)
    n_chs = len(all_ch_names)
    n_sex = _PSD_N_SEX

    # Build index maps
    cond_idx = {c: i for i, c in enumerate(all_conditions)}
    bin_idx = {b: i for i, b in enumerate(bin_labels)}
    ch_idx = {ch: i for i, ch in enumerate(all_ch_names)}
    sex_idx = {s: i for i, s in enumerate(_PSD_SEX_ORDER)}

    # Aggregate — sex axis at index 2.
    n_points = len(_PERCENTILE_POINTS)
    mean_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan)
    sd_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan)
    n_arr = np.zeros((n_bins, n_conds, n_sex), dtype=int)
    # Distribution-honest additions (psd_format_version 3): per-frequency
    # percentiles + Shapiro-Wilk normality, computed from the same per-subject
    # stack used for mean/sd. float32 keeps `percentiles` compact.
    pct_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs, n_points), np.nan, dtype=np.float32)
    normality_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan, dtype=np.float32)

    for (b_label, cond, sex), entries in grouped.items():
        bi = bin_idx.get(b_label)
        ci = cond_idx.get(cond)
        si = sex_idx.get(sex)
        if bi is None or ci is None or si is None:
            continue

        n_arr[bi, ci, si] = len(entries)

        # Stack all subjects' PSDs, aligning by channel name
        stacked = np.full((len(entries), n_chs, n_freqs), np.nan)
        for sub_i, (ch_names, log_psds) in enumerate(entries):
            for chi, ch in enumerate(ch_names):
                target_ci = ch_idx.get(ch)
                if target_ci is not None and chi < log_psds.shape[0]:
                    stacked[sub_i, target_ci, :] = log_psds[chi, :]

        mean_arr[bi, ci, si] = np.nanmean(stacked, axis=0)
        sd_arr[bi, ci, si] = np.nanstd(stacked, axis=0, ddof=1)

        # Per-frequency percentiles (need >=2 subjects). Reuse the band-level
        # _PERCENTILE_POINTS; nanpercentile over the subject axis → (points,
        # n_ch, n_freq), then move points to the last axis to match the
        # documented (..., n_freq, n_points) layout.
        if len(entries) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                pct = np.nanpercentile(stacked, _PERCENTILE_POINTS, axis=0)
            pct_arr[bi, ci, si] = np.moveaxis(pct, 0, -1).astype(np.float32)

        # Shapiro-Wilk per (channel, freq) on the log (scoring) space, mirroring
        # the band-level normality_p. NaN if <3 valid samples or zero variance.
        if len(entries) >= 3:
            for chi in range(n_chs):
                for fi in range(n_freqs):
                    col = stacked[:, chi, fi]
                    col = col[~np.isnan(col)]
                    if col.size >= 3 and np.std(col, ddof=1) > 0:
                        try:
                            normality_arr[bi, ci, si, chi, fi] = float(stats.shapiro(col).pvalue)
                        except Exception:
                            pass  # leave NaN

    logger.info(f"  Shape: {n_bins} bins × {n_conds} conditions × {n_sex} sexes × {n_chs} channels × {n_freqs} freqs")
    logger.info(f"  Subjects per (bin, cond, sex): {n_arr.tolist()}")

    return {
        "freqs": ref_freqs,
        "bins": np.array(bin_labels),
        "conditions": np.array(all_conditions),
        "sexes": np.array(_PSD_SEX_ORDER, dtype="U10"),
        "ch_names": np.array(all_ch_names),
        "mean": mean_arr,
        "sd": sd_arr,
        "n": n_arr,
        "percentile_points": np.array(_PERCENTILE_POINTS, dtype=np.float64),
        "percentiles": pct_arr,
        "normality_p": normality_arr,
        "psd_format_version": 3,
    }


def _write_psd_slab(arrays: dict, output_path: Path) -> None:
    """Write a PSD slab dict (from ``_compute_psd_slab``) to *output_path*.

    Creates the parent directory if it does not already exist, so callers
    don't have to worry about ordering relative to ``write_norms_npz``.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_path, **arrays)
    logger_name = __name__
    import logging as _logging
    _logging.getLogger(logger_name).debug(f"Saved normative PSD to {output_path}")


def build_normative_psd(psd_dir: Path, subjects_for_norms: list,
                        age_bins: list, output_path: Path, logger):
    """Compute and write the normative PSD slab to *output_path*.

    Convenience wrapper around :func:`_compute_psd_slab` and
    :func:`_write_psd_slab` for callers that only need a single write.
    Returns early (no file written) when there are no valid PSD checkpoints.
    """
    arrays = _compute_psd_slab(psd_dir, subjects_for_norms, age_bins, logger)
    if arrays is None:
        return
    _write_psd_slab(arrays, output_path)
    logger.info(f"Saved normative PSD to {output_path}")


def register_psd_spectrum_in_metadata(npz_dir: Path) -> None:
    """Register npz/psd_spectrum.npz as a v3 slab category in metadata.json.

    The slab is written separately from write_norms_npz (which only handles
    the flat-layout categories), so we patch the metadata after the fact.
    """
    slab_path = npz_dir / "psd_spectrum.npz"
    if not slab_path.exists():
        return
    arr = np.load(slab_path)
    meta_path = npz_dir / "metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {
        "format_version": 3,
        "total_cells": 0,
        "categories": {},
        "age_bins": [],
        "conditions": [],
    }
    meta.setdefault("categories", {})["psd_spectrum"] = {
        "file": "psd_spectrum.npz",
        "layout": "slab",
        "n_freqs": int(arr["mean"].shape[-1]),
        "n_channels": int(arr["mean"].shape[-2]),
        "unique_sexes": sorted(list(map(str, arr["sexes"]))),
        "size_bytes": slab_path.stat().st_size,
    }
    meta_path.write_text(json.dumps(meta, indent=2))


def _run_subject_subprocess(
    fr,
    channels: int,
    skip_connectivity: bool,
    source: bool,
    ba_connectivity: bool,
    dk_connectivity: bool,
    dk_corrected_power: bool,
    subjects_dir: Path,
    psd_dir: Path | None,
    params_override: dict | None,
    subject_timeout: int,
) -> dict:
    """Process one subject in a fresh child Python interpreter.

    Full-process isolation: an OOM-killed worker kills only itself, never
    poisons sibling workers. The parent thread waits on subprocess.run,
    catches non-zero exit cleanly, and the ThreadPoolExecutor never enters
    a broken state.
    """
    spec = {
        "filepath": str(fr.filepath),
        "subject_id": fr.subject_id,
        "age": fr.age,
        "sex": fr.sex,
        "condition": fr.condition,
        "n_channels": channels,
        "skip_connectivity": skip_connectivity,
        "source": source,
        "ba_connectivity": ba_connectivity,
        "dk_connectivity": dk_connectivity,
        "dk_corrected_power": dk_corrected_power,
        "marker_condition": fr.marker_condition,
        "subjects_dir": str(subjects_dir),
        "psd_dir": str(psd_dir) if psd_dir is not None else None,
        "params_override": params_override,
    }
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "--worker-subject", json.dumps(spec)],
        capture_output=True,
        text=True,
        timeout=subject_timeout,
        env=env,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()[-8:]
        raise RuntimeError(
            f"worker exit={completed.returncode}; tail:\n"
            + "\n".join(tail) if tail else f"worker exit={completed.returncode}"
        )
    # Worker wrote the checkpoint JSON; read it back so the parent has the
    # same subject_data it would have received from an in-process call.
    ckpt = subjects_dir / f"{fr.subject_id}_{fr.condition}.json"
    with open(ckpt) as f:
        return json.load(f)


def _worker_subject_main(spec_json: str) -> int:
    """Entry point for ``--worker-subject``: process one subject and exit.

    The spec is a JSON dict matching the kwargs of _process_one_subject
    plus output paths. Runs _process_one_subject + _save_subject_result
    inline; errors print to stderr and exit non-zero. S3 sync of the
    checkpoint is handled by the parent (per-file boto3 upload), not here.
    """
    try:
        spec = json.loads(spec_json)
        subjects_dir = Path(spec["subjects_dir"])
        subjects_dir.mkdir(parents=True, exist_ok=True)
        psd_dir = Path(spec["psd_dir"]) if spec.get("psd_dir") else None
        if psd_dir is not None:
            psd_dir.mkdir(parents=True, exist_ok=True)

        subject_data = _process_one_subject(
            filepath=spec["filepath"],
            subject_id=spec["subject_id"],
            age=spec["age"],
            sex=spec["sex"],
            condition=spec["condition"],
            n_channels=spec["n_channels"],
            params=spec.get("params_override"),
            skip_connectivity=spec["skip_connectivity"],
            source=spec["source"],
            ba_connectivity=spec["ba_connectivity"],
            dk_connectivity=spec["dk_connectivity"],
            dk_corrected_power=spec["dk_corrected_power"],
            marker_condition=spec.get("marker_condition"),
        )
        _save_subject_result(subject_data, subjects_dir, psd_dir, [])
        return 0
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Build normative EEG distributions from a public dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        nargs="?",
        default=None,
        help="Path to the dataset directory (BIDS layout). "
             "Not required when using --merge.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("./norms_output"),
        help="Output directory (default: ./norms_output)",
    )
    parser.add_argument(
        "--dataset", "-d",
        choices=list(DATASETS.keys()),
        default="lemon",
        help="Dataset to process (default: lemon)",
    )
    parser.add_argument(
        "--condition",
        choices=["eo", "ec", "both"],
        default="both",
        help="Which condition(s) to process (default: both)",
    )
    parser.add_argument(
        "--max-subjects",
        type=int,
        default=0,
        help="Limit to N subjects (0 = all, useful for testing)",
    )
    parser.add_argument(
        "--skip-connectivity",
        action="store_true",
        help="Skip connectivity analysis (faster, spectral-only norms)",
    )
    parser.add_argument(
        "--age-bins",
        type=int,
        nargs="+",
        default=[20, 30, 40, 50, 60, 70, 80],
        help="Age bin edges (default: decade bins 20-80)",
    )
    parser.add_argument(
        "--qc-dir",
        type=Path,
        default=None,
        help="Path to QC output directory (from lemon_qc.py). "
             "If provided, only subjects in ready.txt are processed.",
    )
    parser.add_argument(
        "--save-psd",
        action="store_true",
        help="Save aggregated normative PSD curves (mean/SD per channel "
             "per age bin) as norms_psd.npz for spectral overlay display.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge mode: combine existing per-subject checkpoint dirs "
             "into a single normative database. No processing is done.",
    )
    parser.add_argument(
        "--merge-dir",
        type=Path,
        action="append",
        default=[],
        help="Path to a subjects/ checkpoint directory to include in merge. "
             "Can be specified multiple times. Use with --merge.",
    )
    parser.add_argument(
        "--channels",
        type=int,
        choices=[19, 37],
        default=19,
        help="Target channel count: 19 (standard 10-20) or 37 (extended 10-10). "
             "Default: 19. Requires datasets with >= 37 channels for 37.",
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=1,
        help="Number of parallel worker processes (default: 1 = sequential). "
             "Memory: ~2 GB/worker for 19ch, ~3 GB/worker for 37ch.",
    )
    parser.add_argument(
        "--source",
        action="store_true",
        help="Enable source localization (sLORETA power + DICS connectivity). "
             "Adds ~30-60s per subject. Works with both 19 and 37 channels.",
    )
    parser.add_argument(
        "--ba-connectivity",
        action="store_true",
        help="Compute Brodmann Area-to-BA connectivity (requires --source). "
             "Adds ~30 BA-pair metrics per method per band.",
    )
    parser.add_argument(
        "--dk-connectivity",
        action="store_true",
        help="Compute individual DK parcel-to-parcel connectivity (requires --source). "
             "Adds all 68 DK parcels (2,278 pairs) per method per band.",
    )
    parser.add_argument(
        "--dk-corrected-power",
        action="store_true",
        help="(deprecated, no-op) DK corrected power is now always computed "
             "when --dk-connectivity or --ba-connectivity is enabled.",
    )
    parser.add_argument(
        "--subject-range",
        type=str,
        default=None,
        help="Process a slice of subjects by index: START:END (0-based, "
             "exclusive end). E.g. --subject-range 0:100 for first 100. "
             "Useful for distributing work across machines.",
    )
    parser.add_argument(
        "--checkpoint-sync",
        type=str,
        default=None,
        metavar="S3_URI",
        help="After each subject completes, mirror its checkpoint files to "
             "the given s3://bucket/prefix/ location. Paths are preserved "
             "relative to --output (e.g. subjects/sub-01_ec.json). Requires "
             "boto3 and AWS credentials in the standard SDK credential "
             "chain. Upload failures are logged but non-fatal.",
    )
    parser.add_argument(
        "--subject-timeout",
        type=int,
        default=1800,
        help="Per-subject wall-clock timeout in seconds for isolated-subprocess "
             "mode (default: 1800 = 30 min). A runaway subject is SIGTERM'd and "
             "counted as an error; the rest of the slice proceeds.",
    )
    # Hidden: per-subject worker entry point. When set, this invocation
    # processes exactly one subject (spec passed as JSON) and exits.
    # Used internally by the parallel driver for OOM isolation.
    parser.add_argument(
        "--worker-subject",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    # Dispatch to the single-subject worker if this is a child process.
    if args.worker_subject is not None:
        sys.exit(_worker_subject_main(args.worker_subject))


    # --ba-connectivity / --dk-connectivity imply --source
    if (args.ba_connectivity or args.dk_connectivity) and not args.source:
        logging.getLogger(__name__).warning(
            "--ba-connectivity/--dk-connectivity requires --source; enabling --source"
        )
        args.source = True
    # ── Merge mode ──────────────────────────────────────────────────────
    if args.merge:
        if not args.merge_dir:
            parser.error("--merge requires at least one --merge-dir")

        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        logger = setup_logging(output_dir)

        logger.info("Merge mode: combining checkpoint directories")

        # When merging across multiple datasets, prefix each subject_id with
        # the source dataset's name so independent subjects with colliding IDs
        # (e.g. SRM's sub-001 vs Dortmund's sub-001) don't appear as duplicates
        # and can be attributed back to their dataset in subjects.csv. The
        # prefix is the merge_dir's parent directory name (e.g. "lemon" from
        # "norms_merge_in/lemon/subjects/"). Single-merge-dir invocations keep
        # the legacy unprefixed format so the cloud per-run merge job is
        # unaffected.
        multi_source = len(args.merge_dir) > 1
        def _prefix_for(merge_path: Path) -> str:
            if not multi_source:
                return ""
            raw = merge_path.parent.name or merge_path.name
            return re.sub(r"[^A-Za-z0-9]+", "", raw)

        subjects_for_norms = []
        source_counts = {}
        for merge_path in args.merge_dir:
            if not merge_path.exists():
                logger.warning(f"Merge dir not found: {merge_path}")
                continue
            prefix = _prefix_for(merge_path)
            count = 0
            for fpath in sorted(merge_path.glob("*.json")):
                try:
                    with open(fpath) as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning(f"Skipping corrupt file {fpath.name}: {exc}")
                    continue
                if prefix:
                    data["subject_id"] = f"{prefix}_{data['subject_id']}"
                # Tag the source directory for provenance
                data["source_dir"] = str(merge_path)
                subjects_for_norms.append(data)
                count += 1
            source_counts[str(merge_path)] = count
            logger.info(f"  Loaded {count} subjects from {merge_path}")

        if not subjects_for_norms:
            logger.error("No subjects loaded from any merge directory. Exiting.")
            sys.exit(1)

        # Duplicate detection. With multi_source prefixing, cross-dataset ID
        # collisions are namespaced apart, so anything flagged here is a true
        # within-source duplicate and worth investigating.
        seen_ids = {}
        duplicates = []
        for s in subjects_for_norms:
            key = (s["subject_id"], s["condition"])
            if key in seen_ids:
                duplicates.append(key)
            seen_ids[key] = s.get("source_dir", "unknown")
        if duplicates:
            logger.warning(
                f"Found {len(duplicates)} duplicate subject+condition entries "
                f"within a single source. First 5: {duplicates[:5]}."
            )

        logger.info(
            f"\nMerged {len(subjects_for_norms)} subject records "
            f"from {len(source_counts)} sources"
        )

        # Age/sex summary
        ages = [s["age"] for s in subjects_for_norms
                if isinstance(s.get("age"), (int, float)) and s["age"] == s["age"]]
        if ages:
            logger.info(f"  Age range: {min(ages):.0f}-{max(ages):.0f}")
        sexes = {}
        for s in subjects_for_norms:
            sex = s.get("sex", "?")
            sexes[sex] = sexes.get(sex, 0) + 1
        logger.info(f"  Sex distribution: {sexes}")
        conds = {}
        for s in subjects_for_norms:
            c = s.get("condition", "?")
            conds[c] = conds.get(c, 0) + 1
        logger.info(f"  Conditions: {conds}")

        # Build norms
        conditions = None
        if args.condition != "both":
            conditions = [args.condition]

        norms = build_normative(
            subjects_for_norms,
            age_bins=args.age_bins,
            conditions=conditions,
        )

        # Write outputs
        norms_json_path = output_dir / "norms.json"
        norms_csv_path = output_dir / "norms.csv"
        subjects_csv_path = output_dir / "subjects.csv"

        write_norms_json(norms, norms_json_path)
        write_norms_csv(norms, norms_csv_path)
        write_subjects_csv(subjects_for_norms, subjects_csv_path)

        npz_counts = write_norms_npz(norms, output_dir)
        logger.info("NPZ export:")
        for cat, count in sorted(npz_counts.items()):
            logger.info(f"  {cat}: {count} cells")

        # Save merge provenance
        merge_config = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "merge",
            "source_directories": {str(p): source_counts.get(str(p), 0)
                                   for p in args.merge_dir},
            "total_subjects": len(subjects_for_norms),
            "duplicates_found": len(duplicates),
            "age_bins": args.age_bins,
            "condition_filter": args.condition,
            "pipeline_params": PIPELINE_PARAMS,
        }
        with open(output_dir / "merge_config.json", "w") as f:
            json.dump(merge_config, f, indent=2, default=str)

        # Merge PSD checkpoints if available. Carry the same per-source
        # prefix used for subject_ids so build_normative_psd's stem-based
        # lookup (sub-001_ec_psd.npz → "sub-001_ec") matches the prefixed
        # subject_id keys (lemon_sub-001_ec).
        psd_source_dirs: list[tuple[str, Path]] = []
        for merge_path in args.merge_dir:
            psd_candidate = merge_path.parent / "psd_checkpoints"
            if psd_candidate.exists() and list(psd_candidate.glob("*_psd.npz")):
                psd_source_dirs.append((_prefix_for(merge_path), psd_candidate))

        if psd_source_dirs:
            merged_psd_dir = output_dir / "psd_checkpoints"
            merged_psd_dir.mkdir(parents=True, exist_ok=True)

            psd_count = 0
            for prefix, psd_src in psd_source_dirs:
                for npz_file in psd_src.glob("*_psd.npz"):
                    new_name = f"{prefix}_{npz_file.name}" if prefix else npz_file.name
                    dest = merged_psd_dir / new_name
                    if not dest.exists():
                        import shutil
                        shutil.copy2(npz_file, dest)
                        psd_count += 1
            logger.info(f"Merged {psd_count} PSD checkpoints from {len(psd_source_dirs)} sources")

            # Build aggregated normative PSD — compute once, write to both paths.
            # _compute_psd_slab does all the expensive work (Shapiro-Wilk etc.);
            # _write_psd_slab is a cheap np.savez_compressed call.
            slab = _compute_psd_slab(
                merged_psd_dir, subjects_for_norms, args.age_bins, logger,
            )
            if slab is not None:
                _write_psd_slab(slab, output_dir / "norms_psd.npz")          # legacy shim
                _write_psd_slab(slab, output_dir / "npz" / "psd_spectrum.npz")  # v3 home
                logger.info(f"Saved normative PSD to {output_dir / 'norms_psd.npz'} and npz/psd_spectrum.npz")
                register_psd_spectrum_in_metadata(output_dir / "npz")
        else:
            logger.info("No PSD checkpoints found in source directories — skipping normative PSD build.")

        logger.info(f"\nWrote {len(norms)} normative cells to:")
        logger.info(f"  {norms_json_path}")
        logger.info(f"  {norms_csv_path}")
        logger.info(f"  {subjects_csv_path}")
        logger.info(f"  {output_dir / 'merge_config.json'}")

        # Summary stats
        bins_seen = sorted({c.bin for c in norms})
        conditions_seen = sorted({c.condition for c in norms})
        channels_seen = sorted({c.channel for c in norms})
        metrics_seen = sorted({c.metric for c in norms})

        logger.info(f"\nNormative summary:")
        logger.info(f"  Age bins: {bins_seen}")
        logger.info(f"  Conditions: {conditions_seen}")
        logger.info(f"  Channels: {len(channels_seen)}")
        logger.info(f"  Metrics: {metrics_seen}")
        logger.info(f"  Min n per cell: {min(c.n for c in norms)}")
        logger.info(f"  Max n per cell: {max(c.n for c in norms)}")

        for src, cnt in source_counts.items():
            logger.info(f"  {src}: {cnt} subjects")

        return

    # ── Normal (single-dataset) mode ────────────────────────────────────
    if args.data_dir is None:
        parser.error("data_dir is required when not using --merge")

    # Setup output directory
    output_dir = args.output
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    psd_dir = None
    if args.save_psd:
        psd_dir = output_dir / "psd_checkpoints"
        psd_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(output_dir)
    save_run_config(output_dir, args)

    # Validate S3 sync target up front so a typo doesn't fail mid-run.
    sync_target: tuple[str, str] | None = None
    if args.checkpoint_sync:
        sync_target = _parse_s3_uri(args.checkpoint_sync)
        logger.info(
            f"Checkpoint sync: s3://{sync_target[0]}/{sync_target[1]} "
            f"(uploads run after each subject completes)"
        )

    # Load existing checkpoints
    checkpoints = load_checkpoints(subjects_dir)
    if checkpoints:
        logger.info(f"Found {len(checkpoints)} existing checkpoints — will skip those.")

    # Initialize dataset loader
    LoaderClass = DATASETS[args.dataset]
    loader = LoaderClass()
    loader.n_channels = args.channels

    # Apply dataset-specific line frequency (e.g. 50 Hz for European datasets)
    if hasattr(loader, "line_freq") and loader.line_freq != PIPELINE_PARAMS["preprocessing"]["filter"]["notch_freq"]:
        logger.info(
            f"Dataset line frequency: {loader.line_freq} Hz "
            f"(overriding default {PIPELINE_PARAMS['preprocessing']['filter']['notch_freq']} Hz)"
        )
        import copy
        params_override = copy.deepcopy(PIPELINE_PARAMS)
        params_override["preprocessing"]["filter"]["notch_freq"] = loader.line_freq
        # Update harmonics for the new line frequency
        params_override["preprocessing"]["filter"]["notch_harmonics"] = [
            loader.line_freq * h for h in (2, 3)
        ]
    else:
        params_override = None

    # Apply 37-channel overrides if requested
    if args.channels == 37:
        import copy
        if params_override is None:
            params_override = copy.deepcopy(PIPELINE_PARAMS)
        params_override["connectivity"]["hubs"] = params_override["connectivity"]["hubs_37"]
        params_override["spectral"]["asymmetry"]["homologous_pairs"] = (
            params_override["spectral"]["asymmetry"]["homologous_pairs_37"]
        )
        params_override["spectral"]["iaf"]["posterior_channels"] = [
            "O1", "O2", "Pz", "P3", "P4", "PO3", "PO4",
        ]
        logger.info("Using 37-channel montage with extended hubs and asymmetry pairs")

    # Load QC allow-list if provided
    qc_allow = None
    if args.qc_dir:
        # Support both naming conventions from QC scripts
        ready_path = args.qc_dir / "ready.txt"
        if not ready_path.exists():
            ready_path = args.qc_dir / "ready_subjects.txt"
        if ready_path.exists():
            qc_allow = set(ready_path.read_text().strip().splitlines())
            logger.info(f"QC filter: {len(qc_allow)} subjects in {ready_path}")
        else:
            logger.warning(f"QC dir provided but no ready.txt or ready_subjects.txt found — processing all subjects")

    # Scan for work items (lightweight — no raw data loaded)
    logger.info(f"Scanning {args.data_dir} for {args.dataset} subjects...")

    # Parse subject range if provided
    range_start, range_end = 0, None
    if args.subject_range:
        parts = args.subject_range.split(":")
        range_start = int(parts[0])
        range_end = int(parts[1]) if len(parts) > 1 else None
        logger.info(f"Subject range: [{range_start}:{range_end})")

    subjects_for_norms = []
    skipped = 0
    qc_skipped = 0
    eligible_idx = 0  # Index into eligible (post-filter) subjects
    todo = []  # List of SubjectFileRecords to process

    for file_record in loader.iter_subject_files(args.data_dir):
        if args.condition != "both" and file_record.condition != args.condition:
            continue
        if qc_allow is not None and file_record.subject_id not in qc_allow:
            qc_skipped += 1
            continue

        # Apply subject range filter (before checkpoint check)
        if eligible_idx < range_start:
            eligible_idx += 1
            continue
        if range_end is not None and eligible_idx >= range_end:
            eligible_idx += 1
            continue
        eligible_idx += 1

        checkpoint_key = f"{file_record.subject_id}_{file_record.condition}"
        if checkpoint_key in checkpoints:
            subjects_for_norms.append(checkpoints[checkpoint_key])
            skipped += 1
            continue

        if args.max_subjects > 0 and (len(todo) + skipped) >= args.max_subjects:
            break

        todo.append(file_record)

    logger.info(
        f"Found {len(todo)} subjects to process, {skipped} from checkpoint"
        + (f", {qc_skipped} excluded by QC" if qc_skipped else "")
    )

    # Empty-range short-circuit: cloud_recompute.py sizes N slices across the
    # dataset and the tail slice may cover an out-of-range index. That is not
    # a failure — exit 0 so Batch doesn't mark the slice FAILED and block
    # merge via SEQUENTIAL dependsOn.
    if not todo and skipped == 0:
        logger.info("Nothing to do in this subject range; exiting 0.")
        sys.exit(0)

    processed = 0
    errors = 0
    start_time = time.time()

    if args.jobs <= 1:
        # ── Sequential processing ──────────────────────────────────────
        for i, fr in enumerate(todo):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            logger.info(
                f"[{skipped + i + 1}] Processing {fr.subject_id} "
                f"({fr.condition}) age={fr.age} [{rate * 60:.1f} subj/min]"
            )
            try:
                subject_data = _process_one_subject(
                    filepath=str(fr.filepath),
                    subject_id=fr.subject_id,
                    age=fr.age,
                    sex=fr.sex,
                    condition=fr.condition,
                    n_channels=args.channels,
                    params=params_override,
                    skip_connectivity=args.skip_connectivity,
                    source=args.source,
                    ba_connectivity=args.ba_connectivity,
                    dk_connectivity=args.dk_connectivity,
                    dk_corrected_power=args.dk_corrected_power,
                    marker_condition=fr.marker_condition,
                )
                written = _save_subject_result(
                    subject_data, subjects_dir, psd_dir, subjects_for_norms,
                )
                if sync_target is not None:
                    _sync_checkpoint_files(
                        written, output_dir, sync_target[0], sync_target[1], logger,
                    )
                processed += 1
            except Exception:
                errors += 1
                logger.error(
                    f"FAILED: {fr.subject_id} ({fr.condition})\n"
                    + traceback.format_exc()
                )
    else:
        # ── Parallel processing (subprocess-per-subject isolation) ─────
        # Each subject runs in a fresh Python interpreter via subprocess.run.
        # An OOM-killed worker only kills itself; siblings keep processing.
        # ThreadPoolExecutor just supervises the subprocesses — no pickle,
        # no shared interpreter state, no BrokenProcessPool.
        logger.info(
            f"Processing with {args.jobs} isolated-subprocess workers "
            f"(per-subject timeout {args.subject_timeout}s)"
        )
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = {
                pool.submit(
                    _run_subject_subprocess,
                    fr,
                    args.channels,
                    args.skip_connectivity,
                    args.source,
                    args.ba_connectivity,
                    args.dk_connectivity,
                    args.dk_corrected_power,
                    subjects_dir,
                    psd_dir,
                    params_override,
                    args.subject_timeout,
                ): fr
                for fr in todo
            }
            for i, future in enumerate(as_completed(futures)):
                fr = futures[future]
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                try:
                    subject_data = future.result()
                    # Worker already wrote the JSON + PSD. Accumulate here;
                    # the PSD sidecar (if any) is colocated next to the JSON.
                    written = [subjects_dir / f"{fr.subject_id}_{fr.condition}.json"]
                    if psd_dir is not None:
                        psd_path = psd_dir / f"{fr.subject_id}_{fr.condition}_psd.npz"
                        if psd_path.exists():
                            written.append(psd_path)
                    subjects_for_norms.append(subject_data)
                    if sync_target is not None:
                        _sync_checkpoint_files(
                            written, output_dir, sync_target[0], sync_target[1], logger,
                        )
                    processed += 1
                    logger.info(
                        f"[{skipped + i + 1}] Done {fr.subject_id} "
                        f"({fr.condition}) [{rate * 60:.1f} subj/min]"
                    )
                except subprocess.TimeoutExpired:
                    errors += 1
                    logger.error(
                        f"TIMEOUT: {fr.subject_id} ({fr.condition}) "
                        f"exceeded {args.subject_timeout}s"
                    )
                except Exception:
                    errors += 1
                    logger.error(
                        f"FAILED: {fr.subject_id} ({fr.condition})\n"
                        + traceback.format_exc()
                    )

    elapsed_total = time.time() - start_time
    parts = [f"{processed} processed", f"{skipped} resumed from checkpoint", f"{errors} errors"]
    if qc_skipped:
        parts.append(f"{qc_skipped} excluded by QC")
    logger.info(f"\nProcessing complete: {', '.join(parts)}, {elapsed_total / 60:.1f} min total")

    # Build normative distributions
    if not subjects_for_norms:
        logger.error("No subjects to build norms from. Exiting.")
        sys.exit(1)

    logger.info(f"Building normative distributions from {len(subjects_for_norms)} subjects...")

    conditions = None
    if args.condition != "both":
        conditions = [args.condition]

    norms = build_normative(
        subjects_for_norms,
        age_bins=args.age_bins,
        conditions=conditions,
    )

    # Write outputs
    norms_json_path = output_dir / "norms.json"
    norms_csv_path = output_dir / "norms.csv"
    subjects_csv_path = output_dir / "subjects.csv"

    write_norms_json(norms, norms_json_path)
    write_norms_csv(norms, norms_csv_path)
    write_subjects_csv(subjects_for_norms, subjects_csv_path)

    npz_counts = write_norms_npz(norms, output_dir)
    logger.info("NPZ export:")
    for cat, count in sorted(npz_counts.items()):
        logger.info(f"  {cat}: {count} cells")

    # Build normative PSD if requested — compute once, write to both paths.
    # _compute_psd_slab does all the expensive work (Shapiro-Wilk etc.);
    # _write_psd_slab is a cheap np.savez_compressed call.
    if args.save_psd and psd_dir is not None:
        slab = _compute_psd_slab(psd_dir, subjects_for_norms, args.age_bins, logger)
        if slab is not None:
            _write_psd_slab(slab, output_dir / "norms_psd.npz")          # legacy shim
            _write_psd_slab(slab, output_dir / "npz" / "psd_spectrum.npz")  # v3 home
            logger.info(f"Saved normative PSD to {output_dir / 'norms_psd.npz'} and npz/psd_spectrum.npz")
            register_psd_spectrum_in_metadata(output_dir / "npz")

    logger.info(f"Wrote {len(norms)} normative cells to:")
    logger.info(f"  {norms_json_path}")
    logger.info(f"  {norms_csv_path}")
    logger.info(f"  {subjects_csv_path}")

    # Summary stats
    bins_seen = sorted({c.bin for c in norms})
    conditions_seen = sorted({c.condition for c in norms})
    channels_seen = sorted({c.channel for c in norms})
    metrics_seen = sorted({c.metric for c in norms})

    logger.info(f"\nNormative summary:")
    logger.info(f"  Age bins: {bins_seen}")
    logger.info(f"  Conditions: {conditions_seen}")
    logger.info(f"  Channels: {len(channels_seen)}")
    logger.info(f"  Metrics: {metrics_seen}")
    logger.info(f"  Min n per cell: {min(c.n for c in norms)}")
    logger.info(f"  Max n per cell: {max(c.n for c in norms)}")


if __name__ == "__main__":
    main()
