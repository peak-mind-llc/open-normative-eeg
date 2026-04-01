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
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from open_normative.datasets import DATASETS
from open_normative.io import write_norms_csv, write_norms_json, write_subjects_csv
from open_normative.normative import build_normative
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.pipeline import process_resting


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


def save_checkpoint(subjects_dir: Path, subject_id: str, condition: str, metrics: dict):
    """Save a single subject's metrics as a checkpoint JSON."""
    fname = f"{subject_id}_{condition}.json"
    fpath = subjects_dir / fname
    with open(fpath, "w") as f:
        json.dump(metrics, f)


def save_psd_checkpoint(psd_dir: Path, subject_id: str, condition: str,
                        freqs: np.ndarray, psds: np.ndarray, ch_names: list):
    """Save a single subject's full PSD array as an .npz checkpoint."""
    fname = f"{subject_id}_{condition}_psd.npz"
    np.savez_compressed(
        psd_dir / fname,
        freqs=freqs,
        psds=psds,  # shape (n_channels, n_freqs), V²/Hz
        ch_names=np.array(ch_names),
    )


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
        with open(fpath) as f:
            checkpoints[key] = json.load(f)
    return checkpoints


def save_run_config(output_dir: Path, args: argparse.Namespace):
    """Save the parameters used for this run."""
    config = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "data_dir": str(args.data_dir),
        "output": str(args.output),
        "condition": args.condition,
        "max_subjects": args.max_subjects,
        "skip_connectivity": args.skip_connectivity,
        "save_psd": args.save_psd,
        "age_bins": args.age_bins,
        "pipeline_params": PIPELINE_PARAMS,
    }
    with open(output_dir / "run_config.json", "w") as f:
        json.dump(config, f, indent=2, default=str)


def build_normative_psd(psd_dir: Path, subjects_for_norms: list,
                        age_bins: list, output_path: Path, logger):
    """Aggregate per-subject PSD curves into normative PSD statistics.

    For each (age_bin, condition, channel), computes mean and SD of
    log10(PSD) across subjects. Saves as norms_psd.npz.

    The output contains:
        freqs: (n_freqs,) frequency vector
        bins: list of bin labels (e.g., "20-29")
        conditions: list of conditions
        ch_names: list of 19 channel names
        mean: (n_bins, n_conditions, n_channels, n_freqs) log10 PSD mean
        sd: (n_bins, n_conditions, n_channels, n_freqs) log10 PSD SD
        n: (n_bins, n_conditions) subject counts
    """
    # Build lookup: subject_id → age, condition
    subject_info = {}
    for s in subjects_for_norms:
        key = f"{s['subject_id']}_{s['condition']}"
        subject_info[key] = {"age": s["age"], "condition": s["condition"]}

    # Load all PSD checkpoints
    psd_files = sorted(psd_dir.glob("*_psd.npz"))
    if not psd_files:
        logger.warning("No PSD checkpoints found — skipping normative PSD build.")
        return

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

    # Collect PSD data grouped by (bin, condition)
    # {(bin_label, condition): [(ch_names, log10_psds), ...]}
    grouped = {}
    ref_freqs = None

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

        if ref_freqs is None:
            ref_freqs = freqs
        elif len(freqs) != len(ref_freqs):
            continue  # skip mismatched frequency resolution

        # Convert to log10(µV²/Hz)
        psds_uv = psds * 1e12  # V²/Hz → µV²/Hz
        psds_uv = np.maximum(psds_uv, 1e-30)  # avoid log(0)
        log10_psds = np.log10(psds_uv)

        key = (age_bin, info["condition"])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append((ch_names, log10_psds))

    if not grouped or ref_freqs is None:
        logger.warning("No valid PSD data to aggregate.")
        return

    # Get canonical channel list from first entry
    all_conditions = sorted({k[1] for k in grouped})
    all_ch_names = list(grouped[next(iter(grouped))][0][0])
    n_freqs = len(ref_freqs)
    n_bins = len(bin_labels)
    n_conds = len(all_conditions)
    n_chs = len(all_ch_names)

    # Build index maps
    cond_idx = {c: i for i, c in enumerate(all_conditions)}
    bin_idx = {b: i for i, b in enumerate(bin_labels)}
    ch_idx = {ch: i for i, ch in enumerate(all_ch_names)}

    # Aggregate
    mean_arr = np.full((n_bins, n_conds, n_chs, n_freqs), np.nan)
    sd_arr = np.full((n_bins, n_conds, n_chs, n_freqs), np.nan)
    n_arr = np.zeros((n_bins, n_conds), dtype=int)

    for (b_label, cond), entries in grouped.items():
        bi = bin_idx.get(b_label)
        ci = cond_idx.get(cond)
        if bi is None or ci is None:
            continue

        n_arr[bi, ci] = len(entries)

        # Stack all subjects' PSDs, aligning by channel name
        stacked = np.full((len(entries), n_chs, n_freqs), np.nan)
        for si, (ch_names, log_psds) in enumerate(entries):
            for chi, ch in enumerate(ch_names):
                target_ci = ch_idx.get(ch)
                if target_ci is not None and chi < log_psds.shape[0]:
                    stacked[si, target_ci, :] = log_psds[chi, :]

        mean_arr[bi, ci] = np.nanmean(stacked, axis=0)
        sd_arr[bi, ci] = np.nanstd(stacked, axis=0, ddof=1)

    np.savez_compressed(
        output_path,
        freqs=ref_freqs,
        bins=np.array(bin_labels),
        conditions=np.array(all_conditions),
        ch_names=np.array(all_ch_names),
        mean=mean_arr,
        sd=sd_arr,
        n=n_arr,
    )
    logger.info(f"Saved normative PSD to {output_path}")
    logger.info(f"  Shape: {n_bins} bins × {n_conds} conditions × {n_chs} channels × {n_freqs} freqs")
    logger.info(f"  Subjects per cell: {n_arr.tolist()}")


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
    args = parser.parse_args()

    # ── Merge mode ──────────────────────────────────────────────────────
    if args.merge:
        if not args.merge_dir:
            parser.error("--merge requires at least one --merge-dir")

        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        logger = setup_logging(output_dir)

        logger.info("Merge mode: combining checkpoint directories")

        subjects_for_norms = []
        source_counts = {}
        for merge_path in args.merge_dir:
            if not merge_path.exists():
                logger.warning(f"Merge dir not found: {merge_path}")
                continue
            count = 0
            for fpath in sorted(merge_path.glob("*.json")):
                with open(fpath) as f:
                    data = json.load(f)
                # Tag the source directory for provenance
                data["source_dir"] = str(merge_path)
                subjects_for_norms.append(data)
                count += 1
            source_counts[str(merge_path)] = count
            logger.info(f"  Loaded {count} subjects from {merge_path}")

        if not subjects_for_norms:
            logger.error("No subjects loaded from any merge directory. Exiting.")
            sys.exit(1)

        # Check for duplicate subjects (same person in both datasets)
        seen_ids = {}
        duplicates = []
        for s in subjects_for_norms:
            key = (s["subject_id"], s["condition"])
            if key in seen_ids:
                duplicates.append(key)
            seen_ids[key] = s.get("source_dir", "unknown")
        if duplicates:
            logger.warning(
                f"Found {len(duplicates)} duplicate subject+condition entries. "
                f"First 5: {duplicates[:5]}. Keeping all — ensure datasets "
                f"don't share subjects to avoid violating independence."
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

    # Load existing checkpoints
    checkpoints = load_checkpoints(subjects_dir)
    if checkpoints:
        logger.info(f"Found {len(checkpoints)} existing checkpoints — will skip those.")

    # Initialize dataset loader
    LoaderClass = DATASETS[args.dataset]
    loader = LoaderClass()

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

    # Count and filter subjects
    logger.info(f"Scanning {args.data_dir} for {args.dataset} subjects...")

    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False
        logger.info("Install tqdm for progress bars: pip install tqdm")

    processed = 0
    skipped = 0
    errors = 0
    start_time = time.time()

    # Wrap the iterator
    subject_iter = loader.iter_subjects(args.data_dir)

    subjects_for_norms = []

    # Process subjects
    qc_skipped = 0
    for record in subject_iter:
        # Filter by condition
        if args.condition != "both" and record.condition != args.condition:
            continue

        # Filter by QC allow-list
        if qc_allow is not None and record.subject_id not in qc_allow:
            qc_skipped += 1
            continue

        checkpoint_key = f"{record.subject_id}_{record.condition}"

        # Check if already processed
        if checkpoint_key in checkpoints:
            subjects_for_norms.append(checkpoints[checkpoint_key])
            skipped += 1
            continue

        # Check max subjects limit
        if args.max_subjects > 0 and (processed + skipped) >= args.max_subjects:
            break

        # Process this subject
        elapsed = time.time() - start_time
        rate = (processed + 1) / elapsed if elapsed > 0 else 0
        logger.info(
            f"[{processed + skipped + 1}] Processing {record.subject_id} "
            f"({record.condition}) age={record.age} "
            f"[{rate:.1f} subj/min]"
        )

        try:
            result = process_resting(
                record.raw,
                condition=record.condition,
                params=params_override,
                skip_connectivity=args.skip_connectivity,
            )

            subject_data = {
                "subject_id": record.subject_id,
                "age": record.age,
                "sex": record.sex,
                "condition": record.condition,
                "metrics": result.to_nested_dict(),
            }

            # Checkpoint
            save_checkpoint(subjects_dir, record.subject_id, record.condition, subject_data)

            # Save PSD checkpoint if requested
            if psd_dir is not None and result.spectral is not None:
                psds = result.spectral.get("psds")
                freqs = result.spectral.get("freqs")
                ch_names = result.spectral.get("ch_names", [])
                if psds is not None and freqs is not None:
                    save_psd_checkpoint(
                        psd_dir, record.subject_id, record.condition,
                        freqs, psds, ch_names,
                    )

            subjects_for_norms.append(subject_data)
            processed += 1

        except Exception:
            errors += 1
            tb = traceback.format_exc()
            logger.error(
                f"FAILED: {record.subject_id} ({record.condition})\n{tb}"
            )
            continue

        # Free memory
        del record

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

    # Build normative PSD if requested
    if args.save_psd and psd_dir is not None:
        norms_psd_path = output_dir / "norms_psd.npz"
        build_normative_psd(
            psd_dir, subjects_for_norms, args.age_bins,
            norms_psd_path, logger,
        )

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
