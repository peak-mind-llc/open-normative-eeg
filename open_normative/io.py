"""I/O utilities for normative database files.

Supports JSON (round-trip with full NormCell fidelity) and CSV
(flat format for analysis in R/Python/Excel).
"""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path
from typing import Union

from open_normative.normative import NormCell, _PERCENTILE_POINTS


PathLike = Union[str, Path]


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def write_norms_json(cells: list[NormCell], filepath: PathLike) -> None:
    """Write a list of NormCell objects to a JSON file.

    Args:
        cells: List of NormCell objects.
        filepath: Destination file path.
    """
    data = [dataclasses.asdict(cell) for cell in cells]
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def read_norms_json(filepath: PathLike) -> list[NormCell]:
    """Read NormCell objects back from a JSON file written by write_norms_json.

    Args:
        filepath: Source file path.

    Returns:
        List of NormCell objects.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    cells = []
    for item in data:
        # Backward compat: add defaults for fields added after v1.0.
        item.setdefault("ci_lower", None)
        item.setdefault("ci_upper", None)
        item.setdefault("pi_lower", None)
        item.setdefault("pi_upper", None)
        cells.append(NormCell(**item))
    return cells


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------


def write_norms_csv(cells: list[NormCell], filepath: PathLike) -> None:
    """Write normative cells to a flat CSV file.

    Percentile columns are named p1, p5, p10, p25, p50, p75, p90, p95, p99.

    Args:
        cells: List of NormCell objects.
        filepath: Destination file path.
    """
    if not cells:
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            fh.write("")
        return

    pct_cols = [f"p{p}" for p in _PERCENTILE_POINTS]
    base_fields = [
        "bin", "condition", "channel", "band", "metric",
        "n", "mean", "sd", "log_mean", "log_sd", "log_transformed",
        "normality_p", "ci_lower", "ci_upper", "pi_lower", "pi_upper",
    ]
    fieldnames = base_fields + pct_cols

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for cell in cells:
            row = {
                "bin": cell.bin,
                "condition": cell.condition,
                "channel": cell.channel,
                "band": cell.band,
                "metric": cell.metric,
                "n": cell.n,
                "mean": cell.mean,
                "sd": cell.sd,
                "log_mean": cell.log_mean,
                "log_sd": cell.log_sd,
                "log_transformed": cell.log_transformed,
                "normality_p": cell.normality_p,
                "ci_lower": cell.ci_lower,
                "ci_upper": cell.ci_upper,
                "pi_lower": cell.pi_lower,
                "pi_upper": cell.pi_upper,
            }
            for p in _PERCENTILE_POINTS:
                row[f"p{p}"] = cell.percentiles.get(str(p))
            writer.writerow(row)


def write_subjects_csv(subjects: list[dict], filepath: PathLike) -> None:
    """Write per-subject metrics to a flat CSV file.

    Flattens the nested metrics dict to columns named
    "<channel>.<band>.<metric>".

    Args:
        subjects: List of subject dicts as produced by pipeline/normative workflow.
            Each dict should have: subject_id, age, sex, condition, metrics.
        filepath: Destination file path.
    """
    if not subjects:
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            fh.write("")
        return

    # Collect all metric keys across all subjects.
    metric_keys: list[str] = []
    seen: set[str] = set()
    for subject in subjects:
        for channel, band_dict in subject.get("metrics", {}).items():
            for band, metric_dict in band_dict.items():
                for metric_name in metric_dict:
                    key = f"{channel}.{band}.{metric_name}"
                    if key not in seen:
                        metric_keys.append(key)
                        seen.add(key)

    meta_fields = ["subject_id", "age", "sex", "condition"]
    fieldnames = meta_fields + sorted(metric_keys)

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for subject in subjects:
            row: dict = {
                "subject_id": subject.get("subject_id", ""),
                "age": subject.get("age", ""),
                "sex": subject.get("sex", ""),
                "condition": subject.get("condition", ""),
            }
            for channel, band_dict in subject.get("metrics", {}).items():
                for band, metric_dict in band_dict.items():
                    for metric_name, value in metric_dict.items():
                        row[f"{channel}.{band}.{metric_name}"] = value
            writer.writerow(row)
