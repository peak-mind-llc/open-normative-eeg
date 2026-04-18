"""Run the user's enumeration command and collect its output as a unit list.

The enumerator contract (see docs/open-cloud-run.md):
 - Runs on the user's laptop (no Batch awareness).
 - Prints one unit identifier per line to stdout.
 - Blank lines and lines starting with ``#`` are ignored.
 - Exit code 0 means success; nonzero means enumeration failed and
   nothing should be submitted.

A "unit identifier" is any non-empty string. The framework does not
parse it. The driver is responsible for interpreting it (single subject
ID, ``sub-001|ses-2``, ``seed=42|k=25``, etc).
"""
from __future__ import annotations

import shlex
import subprocess
import sys


def enumerate_units(command: str, cwd: str | None = None, timeout: int = 300) -> list[str]:
    """Run the given shell command and return the list of non-empty,
    non-comment stdout lines.

    Stderr is forwarded to the caller's stderr so the user can see any
    diagnostic messages the enumerator wrote.
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Enumeration command timed out after {timeout}s: {command!r}"
        ) from exc

    if proc.stderr:
        sys.stderr.write(proc.stderr)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Enumeration command exited {proc.returncode}: {command!r}"
        )

    units: list[str] = []
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        units.append(line)
    return units


def slice_units(
    units: list[str],
    requested_slices: int | None,
    requested_per_slice: int | None,
    default_slices: int,
    min_per_slice: int,
) -> tuple[list[list[str]], int]:
    """Return (list_of_slices, per_slice_target). Each slice is a list
    of unit strings that one array element will process.

    If ``requested_per_slice`` is set, it overrides the slice-size math;
    the number of slices adapts to ceil(len(units) / per_slice).

    If ``requested_slices`` is set, honor it directly, capped so each
    slice has at least ``min_per_slice`` units.

    Otherwise fall back to ``default_slices``.

    Note that AWS Batch array jobs require size >= 2. This function does
    not enforce that — the caller should inspect ``len(slices)`` and
    decide whether to submit a regular job or an array job.
    """
    n = len(units)
    if n <= 0:
        raise ValueError("Cannot slice an empty unit list")

    if requested_per_slice is not None:
        per_slice = max(1, requested_per_slice)
        n_slices = (n + per_slice - 1) // per_slice
    else:
        n_slices = requested_slices or default_slices
        # Respect the minimum units per slice.
        max_sensible = max(1, n // max(min_per_slice, 1))
        n_slices = min(n_slices, max_sensible)
        n_slices = max(n_slices, 1)
        per_slice = (n + n_slices - 1) // n_slices

    # Actually chunk the list — don't rely on the container to do arithmetic.
    slices: list[list[str]] = []
    for i in range(n_slices):
        start = i * per_slice
        end = min(start + per_slice, n)
        if start >= end:
            break
        slices.append(units[start:end])
    return slices, per_slice
