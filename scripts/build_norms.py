#!/usr/bin/env python3
"""Build normative distributions from a public EEG dataset.

Usage:
    python scripts/build_norms.py /path/to/lemon --output ./norms_output

    # Test with 5 subjects first:
    python scripts/build_norms.py /path/to/lemon --output ./test_output --max-subjects 5

    # Eyes-open only, skip connectivity (fast):
    python scripts/build_norms.py /path/to/lemon --output ./test_output \
        --condition eo --skip-connectivity --max-subjects 10
"""

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

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
        "age_bins": args.age_bins,
        "pipeline_params": PIPELINE_PARAMS,
    }
    with open(output_dir / "run_config.json", "w") as f:
        json.dump(config, f, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(
        description="Build normative EEG distributions from a public dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Path to the dataset directory (BIDS layout for LEMON)",
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
    args = parser.parse_args()

    # Setup output directory
    output_dir = args.output
    subjects_dir = output_dir / "subjects"
    subjects_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(output_dir)
    save_run_config(output_dir, args)

    # Load existing checkpoints
    checkpoints = load_checkpoints(subjects_dir)
    if checkpoints:
        logger.info(f"Found {len(checkpoints)} existing checkpoints — will skip those.")

    # Initialize dataset loader
    LoaderClass = DATASETS[args.dataset]
    loader = LoaderClass()

    # Load QC allow-list if provided
    qc_allow = None
    if args.qc_dir:
        ready_path = args.qc_dir / "ready.txt"
        if ready_path.exists():
            qc_allow = set(ready_path.read_text().strip().splitlines())
            logger.info(f"QC filter: {len(qc_allow)} subjects in {ready_path}")
        else:
            logger.warning(f"QC dir provided but {ready_path} not found — processing all subjects")

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
