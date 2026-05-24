#!/usr/bin/env python3
"""Test-retest reliability of EEG metrics from the TRT dataset.

Wood et al. (2024, Simulation 2) argue that fat-tailed EEG distributions make
measurement error heteroscedastic, so "abnormal" (tail) scores drift on their
own at retest — producing spurious "normalization" that mimics a treatment
effect. A single reliability number can't capture that. This script processes
two sessions per subject from the TRT dataset (OpenNeuro ds004148) and reports,
per (condition, channel, band, metric):

  - ICC(2,1), SEM, MDC95 (the smallest change distinguishable from noise)
  - the fraction of subjects whose session-to-session change exceeds MDC95
  - Bland-Altman bias / limits of agreement
  - heteroscedasticity (does |Δ| grow with the level? — the Wood mechanism)

Usage:
    python scripts/compute_trt_reliability.py ~/Data/EEG/TRT \
        --output ./trt_reliability --sessions session1 session2 -j 4

    # Include connectivity/source metrics (slower):
    python scripts/compute_trt_reliability.py ~/Data/EEG/TRT \
        --output ./trt_reliability --connectivity --source
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from open_normative.datasets.trt import TRTLoader
from open_normative.reliability import (
    build_paired_arrays,
    reliability_table,
    summarize_reliability,
)

logger = logging.getLogger("compute_trt_reliability")


def _process_recording(
    filepath: str,
    subject_id: str,
    session: str,
    condition: str,
    age: float,
    sex: str,
    n_channels: int,
    skip_connectivity: bool,
    source: bool,
) -> dict:
    """Top-level, picklable worker: load one recording and run the pipeline.

    Any error (incl. FloatingPointError, which can kill a worker process) is
    converted to RuntimeError so the pool survives — matching build_norms.py.
    """
    try:
        import mne
        import numpy as np
        from open_normative.channels import pick_standard_channels
        from open_normative.pipeline import process_resting

        np.seterr(all="warn")
        raw = mne.io.read_raw_brainvision(str(filepath), preload=True, verbose=False)
        raw.pick("eeg")
        raw = pick_standard_channels(raw, n_channels=n_channels)
        result = process_resting(
            raw, condition=condition,
            skip_connectivity=skip_connectivity, source=source,
        )
        return {
            "subject_id": subject_id,
            "session": session,
            "condition": condition,
            "age": age,
            "sex": sex,
            "metrics": result.to_nested_dict(),
        }
    except BaseException as exc:
        raise RuntimeError(
            f"{subject_id}/{session}/{condition}: {type(exc).__name__}: {exc}"
        ) from None


def _render_markdown(rows: list[dict], summary: dict, sessions: tuple) -> str:
    s = summary
    lines = [
        "# Test-Retest Reliability Report",
        "",
        f"Sessions compared: **{sessions[0]}** vs **{sessions[1]}** "
        f"(TRT dataset, OpenNeuro ds004148).",
        "",
        "## Overall",
        "",
        f"- Metrics evaluated: **{s['n_metrics']}**",
        f"- Median ICC(2,1): **{_fmt(s['median_icc'])}**",
        f"- Metrics with poor reliability (ICC < 0.70): "
        f"**{s['n_low_icc']}** ({_fmt(s['frac_low_icc'])})",
        f"- Heteroscedastic metrics (significant positive Bland-Altman slope): "
        f"**{s['n_heteroscedastic']}** ({_fmt(s['frac_heteroscedastic'])})",
        f"- Median fraction of subjects whose change exceeds MDC95: "
        f"{_fmt(s['median_frac_exceeding_mdc'])}",
        "",
        "> Heteroscedastic metrics are where retest noise is larger in the "
        "> tails than at the centre — the mechanism by which an initially "
        "> 'abnormal' value reverts toward the mean and looks like improvement "
        "> (Wood et al. 2024). For those metrics, longitudinal change should be "
        "> judged against MDC95, not a fixed z-cutoff.",
        "",
        "## Least reliable metrics (lowest ICC first)",
        "",
        "| condition | channel | band | metric | n | ICC | SEM | MDC95 | "
        "% > MDC95 | BA slope (p) |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows[:40]:
        lines.append(
            f"| {r['condition']} | {r['channel']} | {r['band']} | {r['metric']} | "
            f"{r['n']} | {_fmt(r['icc'])} | {_fmt(r['sem'])} | {_fmt(r['mdc95'])} | "
            f"{_fmt(r['frac_exceeding_mdc'])} | "
            f"{_fmt(r['ba_slope'], 3)} ({_fmt(r['ba_slope_p'], 3)}) |"
        )
    lines.append("")
    return "\n".join(lines)


def _fmt(x, nd=3):
    return "—" if x is None or (isinstance(x, float) and x != x) else f"{x:.{nd}f}"


def main():
    parser = argparse.ArgumentParser(
        description="Test-retest reliability from the TRT dataset",
    )
    parser.add_argument("data_dir", type=Path, help="TRT dataset root (BIDS)")
    parser.add_argument("--output", "-o", type=Path, default=Path("./trt_reliability"))
    parser.add_argument("--sessions", nargs=2, default=["session1", "session2"],
                        metavar=("TEST", "RETEST"))
    parser.add_argument("--channels", type=int, choices=[19, 37], default=37)
    parser.add_argument("--condition", choices=["ec", "eo", "both"], default="both")
    parser.add_argument("--connectivity", action="store_true",
                        help="Include connectivity metrics (slower)")
    parser.add_argument("--source", action="store_true",
                        help="Include source-level metrics (much slower)")
    parser.add_argument("--min-n", type=int, default=10,
                        help="Minimum paired subjects to report a metric")
    parser.add_argument("--max-subjects", type=int, default=None)
    parser.add_argument("-j", "--jobs", type=int, default=1)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.data_dir.exists():
        logger.error("Data directory not found: %s", args.data_dir)
        sys.exit(1)

    sessions = tuple(args.sessions)
    conditions = {"ec", "eo"} if args.condition == "both" else {args.condition}
    proc_dir = args.output / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)

    # Enumerate work items across both sessions.
    loader = TRTLoader()
    records_in = [
        r for r in loader.iter_subject_files(args.data_dir, sessions=sessions)
        if r.condition in conditions
    ]
    if args.max_subjects is not None:
        keep = sorted({r.subject_id for r in records_in})[: args.max_subjects]
        records_in = [r for r in records_in if r.subject_id in keep]
    logger.info("Found %d recordings across sessions %s", len(records_in), sessions)

    def _ckpt(rec) -> Path:
        ses = rec.metadata.get("session", "?")
        return proc_dir / f"{rec.subject_id}_{ses}_{rec.condition}.json"

    # Process (resume from checkpoints).
    todo = [r for r in records_in if not _ckpt(r).exists()]
    logger.info("%d already processed, %d to do", len(records_in) - len(todo), len(todo))

    def _args_for(rec):
        return (str(rec.filepath), rec.subject_id, rec.metadata.get("session"),
                rec.condition, rec.age, rec.sex, args.channels,
                not args.connectivity, args.source)

    if args.jobs > 1 and todo:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs = {ex.submit(_process_recording, *_args_for(r)): r for r in todo}
            for fut in as_completed(futs):
                rec = futs[fut]
                try:
                    data = fut.result()
                    _ckpt(rec).write_text(json.dumps(data))
                except Exception as exc:
                    logger.warning("  FAILED %s", exc)
    else:
        for rec in todo:
            try:
                data = _process_recording(*_args_for(rec))
                _ckpt(rec).write_text(json.dumps(data))
            except Exception as exc:
                logger.warning("  FAILED %s", exc)

    # Load all processed records.
    records = [json.loads(p.read_text()) for p in sorted(proc_dir.glob("*.json"))]
    logger.info("Loaded %d processed records", len(records))

    paired = build_paired_arrays(records, sessions=sessions)
    rows = reliability_table(paired, min_n=args.min_n)
    summary = summarize_reliability(rows)

    out = {
        "sessions": list(sessions),
        "n_records": len(records),
        "n_metrics": len(rows),
        "summary": summary,
        "rows": rows,
    }
    (args.output / "trt_reliability.json").write_text(json.dumps(out, indent=2))
    (args.output / "trt_reliability_report.md").write_text(
        _render_markdown(rows, summary, sessions)
    )

    logger.info("Metrics evaluated: %d | median ICC: %s | low-ICC: %d | "
                "heteroscedastic: %d",
                summary["n_metrics"], _fmt(summary["median_icc"]),
                summary["n_low_icc"], summary["n_heteroscedastic"])
    logger.info("Report written to %s", args.output / "trt_reliability_report.md")


if __name__ == "__main__":
    main()
