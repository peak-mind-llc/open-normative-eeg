# Norms bundle minor fixes — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two v2 bundle gaps flagged in `coherence-workstation/.claude/worktrees/fix+minor-fixes/bug-report-open-normative-2026-05-28.md` — add sex stratification (pooled, F, M) to every normative cell, and add a sex-stratified frequency-resolved PSD slab inside the v2 directory so the bundle is self-sufficient.

**Architecture:** Add `sex` as a field on `NormCell` (default `"pooled"`) and a parallel array in every NPZ category (format_version 2 → 3). Each subject contributes to a pooled cell plus their own-sex cell when sex is "F" or "M". `compare_to_norms`/`compare_and_report` gain an optional `sex` parameter that falls back to pooled per-metric when the requested variant is absent, reporting which variant was used via `resolved_sex` per result and `resolved_sex_summary` in the report metadata. Frequency-resolved PSD already exists at the bundle root as `norms_psd.npz`; it gets a sex axis and moves to `output_dir/npz/psd_spectrum.npz` as a slab-layout v2 category.

**Tech Stack:** Python 3.10, numpy, scipy, MNE-Python, pytest, dataclasses. Shared venv at `/Users/jcroall/git/open-normative-eeg/.venv` (activate before running anything).

**Spec:** `docs/superpowers/specs/2026-05-28-norms-bundle-minor-fixes-design.md`

**Test command (run from worktree root):**
```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```

---

## File map

**Modified:**
- `open_normative/normative.py` — `NormCell` gains `sex` field; `build_normative()` fans subjects to pooled + own-sex.
- `open_normative/io.py` — `write_norms_npz`/`read_norms_npz` carry `sex` array; `write_norms_csv` adds column; JSON reader back-compat.
- `open_normative/compare.py` — `ComparisonResult` gains `resolved_sex`; `compare_to_norms`/`compare_and_report` gain `sex` kwarg; `ComparisonReport.metadata` gains `resolved_sex_summary`.
- `scripts/build_norms.py` — `build_normative_psd` adds sex axis and writes to `npz/psd_spectrum.npz`, registers in `metadata.json`.

**Created:**
- `tests/test_sex_stratification.py` — `build_normative` fans cells correctly.
- `tests/test_npz_sex_roundtrip.py` — `sex` survives NPZ write→read; v2 NPZ defaults to `"pooled"`.
- `tests/test_compare_sex.py` — `sex=` kwarg flows through `compare_to_norms` / `compare_and_report` with fallback semantics.
- `tests/test_psd_slab.py` — `build_normative_psd` emits sex-stratified slab at the right path; `metadata.json` lists `psd_spectrum`.

**Extended:**
- `tests/test_psd_percentiles.py` — existing PSD tests carry through the new sex axis.

---

## Field-order constraint

Python dataclasses require defaulted fields after non-defaulted ones. `NormCell` currently has non-defaulted fields through `percentiles`, then `ci_lower`/`ci_upper`/etc with defaults. The new `sex` field has a default (`"pooled"`), so it must go after the other defaulted fields (at the end of the dataclass). The conceptual "key field" positioning the spec described is not enforceable in the dataclass — serialization (JSON/CSV/NPZ) and lookups all key by name, so the position is cosmetic only.

---

### Task 1: Add `sex` field to `NormCell` and round-trip through JSON

**Files:**
- Modify: `open_normative/normative.py` (dataclass definition at lines 88-138)
- Modify: `open_normative/io.py:read_norms_json` (lines 44-63)
- Test: `tests/test_sex_stratification.py` (new)

- [ ] **Step 1: Write the failing test for NormCell.sex default and JSON round-trip**

Create `tests/test_sex_stratification.py`:

```python
"""Sex stratification tests — NormCell carries sex; build_normative fans to pooled + F + M."""

from pathlib import Path

import pytest

from open_normative.io import read_norms_json, write_norms_json
from open_normative.normative import NormCell, build_normative


def _make_cell(**overrides) -> NormCell:
    """Build a NormCell with sensible defaults for testing."""
    base = dict(
        bin="20-29",
        condition="ec",
        channel="Fz",
        band="Alpha",
        metric="absolute_power",
        n=10,
        mean=1.0,
        sd=0.5,
        log_mean=None,
        log_sd=None,
        log_transformed=False,
        normality_p=None,
        percentiles={},
    )
    base.update(overrides)
    return NormCell(**base)


def test_normcell_sex_defaults_to_pooled():
    cell = _make_cell()
    assert cell.sex == "pooled"


def test_normcell_sex_roundtrips_through_json(tmp_path: Path):
    cells = [_make_cell(sex="F"), _make_cell(sex="M"), _make_cell(sex="pooled")]
    path = tmp_path / "norms.json"
    write_norms_json(cells, path)
    loaded = read_norms_json(path)
    assert [c.sex for c in loaded] == ["F", "M", "pooled"]


def test_normcell_legacy_json_without_sex_field_reads_as_pooled(tmp_path: Path):
    """Old bundles have no `sex` field in JSON — must deserialize as 'pooled'."""
    import json
    legacy = [{
        "bin": "20-29", "condition": "ec", "channel": "Fz",
        "band": "Alpha", "metric": "absolute_power",
        "n": 10, "mean": 1.0, "sd": 0.5,
        "log_mean": None, "log_sd": None, "log_transformed": False,
        "normality_p": None, "percentiles": {},
        # Note: no 'sex' field
    }]
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy))
    loaded = read_norms_json(path)
    assert len(loaded) == 1
    assert loaded[0].sex == "pooled"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_sex_stratification.py -v
```
Expected: All three tests FAIL — `NormCell.__init__() got an unexpected keyword argument 'sex'` (or AttributeError on `cell.sex`).

- [ ] **Step 3: Add `sex` field to NormCell**

In `open_normative/normative.py`, after the `transform_normalized` line (line 138), add:

```python
    # NOTE: `sex` is conceptually a key field (alongside bin/condition/channel/band/
    # metric) but Python dataclass rules require defaulted fields after non-defaulted
    # ones, so it lives at the end. Lookups and serialization go by name, so the
    # position is cosmetic only. Legal values: "pooled", "F", "M".
    sex: str = "pooled"
```

- [ ] **Step 4: Add JSON back-compat for old bundles**

In `open_normative/io.py:read_norms_json` (around line 58), inside the loop that builds items, add a setdefault for `sex` alongside the existing setdefaults:

```python
    for item in data:
        # Backward compat: add defaults for fields added after v1.0.
        item.setdefault("ci_lower", None)
        item.setdefault("ci_upper", None)
        item.setdefault("pi_lower", None)
        item.setdefault("pi_upper", None)
        item.setdefault("sex", "pooled")  # added 2026-05; older bundles are pooled-only
        cells.append(NormCell(**item))
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_sex_stratification.py -v
```
Expected: All three tests PASS.

- [ ] **Step 6: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 182 passed (179 baseline + 3 new), 0 failures.

- [ ] **Step 7: Commit**

```bash
git add open_normative/normative.py open_normative/io.py tests/test_sex_stratification.py
git commit -m "feat(normative): add NormCell.sex field with JSON round-trip + back-compat

NormCell gains \`sex: str = 'pooled'\` (legal: 'pooled', 'F', 'M').
read_norms_json defaults missing sex to 'pooled' so v2-format bundles read.
Default position at end of dataclass (forced by Python defaulted-field rules).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `build_normative()` fans each subject to pooled + own-sex cells

**Files:**
- Modify: `open_normative/normative.py:build_normative` (lines 248-322)
- Modify: `open_normative/normative.py:_compute_cell` (lines 141-245) — accept and pass through `sex`
- Test: `tests/test_sex_stratification.py` (append)

- [ ] **Step 1: Write failing tests for fan-out semantics**

Append to `tests/test_sex_stratification.py`:

```python
def _subject(subject_id, age, sex, value, condition="ec"):
    """Tiny subject record for build_normative."""
    return {
        "subject_id": subject_id,
        "age": age,
        "sex": sex,
        "condition": condition,
        "metrics": {"Fz": {"Alpha": {"absolute_power": value}}},
    }


def test_build_normative_fans_to_three_sex_variants():
    """Mixed-sex dataset produces a pooled cell + an F cell + an M cell per tuple."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "F", 1.1),
        _subject("s03", 25, "F", 1.2),
        _subject("s04", 25, "M", 2.0),
        _subject("s05", 25, "M", 2.1),
        _subject("s06", 25, "M", 2.2),
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    assert set(by_sex) == {"pooled", "F", "M"}
    assert by_sex["pooled"].n == 6
    assert by_sex["F"].n == 3
    assert by_sex["M"].n == 3
    # Pooled mean is the mean of all 6 values; F mean is the mean of 3.
    assert by_sex["pooled"].mean == pytest.approx((1.0 + 1.1 + 1.2 + 2.0 + 2.1 + 2.2) / 6)
    assert by_sex["F"].mean == pytest.approx((1.0 + 1.1 + 1.2) / 3)
    assert by_sex["M"].mean == pytest.approx((2.0 + 2.1 + 2.2) / 3)


def test_build_normative_other_sex_contributes_to_pooled_only():
    """Subjects with empty/unrecognised sex are pooled-only — no own-sex cell shipped."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "M", 2.0),
        _subject("s03", 25, "", 3.0),      # unknown
        _subject("s04", 25, "Other", 4.0),  # explicit other
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    # Only pooled / F / M variants exist — no "Other" or "" cell.
    assert set(by_sex) == {"pooled", "F", "M"}
    # Pooled n includes all 4 subjects (including Other and unknown).
    assert by_sex["pooled"].n == 4
    assert by_sex["F"].n == 1
    assert by_sex["M"].n == 1
    # Pooled mean averages all 4 raw values.
    assert by_sex["pooled"].mean == pytest.approx((1.0 + 2.0 + 3.0 + 4.0) / 4)


def test_build_normative_single_sex_dataset_omits_other_sex_cell():
    """All-F dataset: pooled and F cells ship; the M cell is genuinely absent."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "F", 1.1),
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    assert set(by_sex) == {"pooled", "F"}
    assert by_sex["pooled"].n == 2
    assert by_sex["F"].n == 2
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_sex_stratification.py -v
```
Expected: Three new tests FAIL — `build_normative` currently emits one cell per tuple (no sex fan-out), so `set(by_sex)` will be a single-element set or every cell will have `sex == "pooled"`.

- [ ] **Step 3: Update `_compute_cell` to accept `sex`**

In `open_normative/normative.py:_compute_cell` (around line 141), add `sex: str` as a parameter (after `metric`) and pass it through to the `NormCell(...)` constructor at the end:

```python
def _compute_cell(
    values: list[float],
    bin_label: str,
    condition: str,
    channel: str,
    band: str,
    metric: str,
    sex: str,                     # NEW
) -> NormCell:
```

And in the `return NormCell(...)` call at the end (around lines 224-244), add `sex=sex` to the kwargs (anywhere in the call is fine since the field has a default).

- [ ] **Step 4: Update `build_normative` to fan-out by sex**

Replace the accumulator + emit loops in `open_normative/normative.py:build_normative` (lines ~278-322) with:

```python
    # Accumulate values: key = (bin, sex, condition, channel, band, metric).
    # Each subject contributes to ("pooled", ...) always, plus
    # (subject.sex, ...) when sex is "F" or "M". Subjects with empty / "Other" /
    # unrecognised sex contribute only to pooled — no own-sex cell ships.
    accumulator: dict[tuple, list[float]] = {}

    for subject in subjects:
        age = subject["age"]
        cond = subject["condition"]
        if cond not in all_conditions:
            continue

        bin_label = _assign_bin(age, age_bins)
        if bin_label is None:
            continue

        raw_sex = str(subject.get("sex", "") or "").strip().upper()
        subject_sex = raw_sex if raw_sex in {"F", "M"} else None

        metrics = subject.get("metrics", {})
        for channel, band_dict in metrics.items():
            for band, metric_dict in band_dict.items():
                for metric_name, value in metric_dict.items():
                    if value is None or (
                        isinstance(value, float) and np.isnan(value)
                    ):
                        continue
                    if not isinstance(value, (int, float)):
                        continue

                    pooled_key = (bin_label, "pooled", cond, channel, band, metric_name)
                    accumulator.setdefault(pooled_key, []).append(float(value))
                    if subject_sex is not None:
                        sex_key = (bin_label, subject_sex, cond, channel, band, metric_name)
                        accumulator.setdefault(sex_key, []).append(float(value))

    # Build NormCell for each collected key.
    cells = []
    for (bin_label, sex, cond, channel, band, metric_name), values in sorted(
        accumulator.items()
    ):
        cell = _compute_cell(
            values=values,
            bin_label=bin_label,
            condition=cond,
            channel=channel,
            band=band,
            metric=metric_name,
            sex=sex,
        )
        cells.append(cell)

    return cells
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_sex_stratification.py -v
```
Expected: All 6 tests PASS.

- [ ] **Step 6: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 185 passed, 0 failures. If any existing test fails, it likely constructs a `NormCell` directly and indexes the cell list expecting one cell per tuple — that's an indication the test needs to filter by `sex == "pooled"`. Fix in place.

- [ ] **Step 7: Commit**

```bash
git add open_normative/normative.py tests/test_sex_stratification.py
git commit -m "feat(normative): fan each subject to pooled + own-sex cells in build_normative

Accumulator key gains a sex slot. Each subject contributes to (\"pooled\", ...)
always, and to (subject.sex, ...) when sex normalizes to \"F\" or \"M\".
Subjects with empty / Other / unrecognised sex contribute only to pooled —
no own-sex cell ships when there's no clear sex to bin them under.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: NPZ writer adds `sex` array; format_version bumps to 3

**Files:**
- Modify: `open_normative/io.py:write_norms_npz` (lines 148-285)
- Test: `tests/test_npz_sex_roundtrip.py` (new)

- [ ] **Step 1: Write failing test for NPZ round-trip including sex**

Create `tests/test_npz_sex_roundtrip.py`:

```python
"""NPZ format_version 3 round-trip: sex array written, read back, defaults to 'pooled'."""

import json
from pathlib import Path

import numpy as np

from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import NormCell


def _make_cell(sex: str, mean: float = 1.0) -> NormCell:
    return NormCell(
        bin="20-29", condition="ec", channel="Fz",
        band="Alpha", metric="absolute_power",
        n=10, mean=mean, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={},
        sex=sex,
    )


def test_npz_sex_roundtrip(tmp_path: Path):
    cells = [_make_cell("pooled", 1.0), _make_cell("F", 1.5), _make_cell("M", 0.5)]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    by_sex = {c.sex: c.mean for c in loaded}
    assert by_sex == {"pooled": 1.0, "F": 1.5, "M": 0.5}


def test_npz_metadata_lists_format_version_3_and_unique_sexes(tmp_path: Path):
    cells = [_make_cell("pooled"), _make_cell("F"), _make_cell("M")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["format_version"] == 3
    cat = meta["categories"]["scalp_power"]
    assert sorted(cat["unique_sexes"]) == ["F", "M", "pooled"]


def test_npz_legacy_v2_without_sex_array_reads_as_pooled(tmp_path: Path):
    """Hand-write a v2 NPZ (no 'sex' array) and verify it reads back with sex='pooled'."""
    npz_dir = tmp_path / "npz"
    npz_dir.mkdir()

    # Minimal v2-style NPZ with all required arrays except 'sex'.
    np.savez_compressed(
        npz_dir / "scalp_power.npz",
        bins=np.array(["20-29"], dtype="U20"),
        conditions=np.array(["ec"], dtype="U10"),
        channels=np.array(["Fz"], dtype="U80"),
        bands=np.array(["Alpha"], dtype="U64"),
        metrics=np.array(["absolute_power"], dtype="U40"),
        mean=np.array([1.0], dtype=np.float64),
        sd=np.array([0.5], dtype=np.float64),
        n=np.array([10], dtype=np.int32),
        log_mean=np.array([np.nan], dtype=np.float64),
        log_sd=np.array([np.nan], dtype=np.float64),
        log_transformed=np.array([False], dtype=bool),
        skewness=np.array([np.nan], dtype=np.float64),
        kurtosis=np.array([np.nan], dtype=np.float64),
        normality_p=np.array([np.nan], dtype=np.float64),
        transform_normalized=np.array([np.nan], dtype=np.float64),
        percentile_points=np.array([50.0], dtype=np.float64),
        percentiles=np.full((1, 1), np.nan, dtype=np.float64),
    )
    meta = {
        "format_version": 2,
        "total_cells": 1,
        "categories": {"scalp_power": {"file": "scalp_power.npz", "n_cells": 1}},
        "age_bins": ["20-29"],
        "conditions": ["ec"],
    }
    (npz_dir / "metadata.json").write_text(json.dumps(meta))

    loaded = read_norms_npz(npz_dir)
    assert len(loaded) == 1
    assert loaded[0].sex == "pooled"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_npz_sex_roundtrip.py -v
```
Expected: First two tests FAIL (NPZ doesn't write a `sex` array; format_version is 2; `unique_sexes` missing). Third test PASSES already (`read_norms_npz` doesn't fail on missing `sex` — but the cell's `sex` will be `"pooled"` only if `NormCell`'s default applies; verify this is the case before declaring it passing).

- [ ] **Step 3: Add `sex` array to `write_norms_npz`**

In `open_normative/io.py:write_norms_npz` (around line 195, after the `metrics` array), add:

```python
        sexes = np.array([c.sex for c in cat_cells], dtype="U10")
```

In the `np.savez_compressed(...)` call (around lines 244-263), add `sex=sexes,` alongside the other named arrays:

```python
        np.savez_compressed(
            out_path,
            bins=bins,
            conditions=conditions,
            channels=channels,
            bands=bands,
            metrics=metrics,
            sex=sexes,                # NEW
            mean=means,
            sd=sds,
            # ... rest unchanged
        )
```

In the `file_manifest[category]` dict (around lines 265-272), add `unique_sexes`:

```python
        file_manifest[category] = {
            "file": f"{category}.npz",
            "n_cells": n,
            "unique_channels": int(len(set(channels))),
            "unique_bands": sorted(set(bands.tolist())),
            "unique_metrics": sorted(set(metrics.tolist())),
            "unique_sexes": sorted(set(sexes.tolist())),   # NEW
            "size_bytes": out_path.stat().st_size,
        }
```

In the top-level `meta` dict (around lines 275-281), bump the version:

```python
    meta = {
        "format_version": 3,    # was 2
        "total_cells": len(cells),
        "categories": file_manifest,
        "age_bins": sorted(set(c.bin for c in cells)),
        "conditions": sorted(set(c.condition for c in cells)),
    }
```

- [ ] **Step 4: Update `read_norms_npz` to read `sex` with back-compat**

In `open_normative/io.py:read_norms_npz` (around line 329), add `sex` reading alongside the other arrays with a back-compat fallback:

```python
        bins = d["bins"]; conditions = d["conditions"]; channels = d["channels"]
        bands = d["bands"]; metrics = d["metrics"]; ns = d["n"]
        means = d["mean"]; sds = d["sd"]
        log_means = d["log_mean"]; log_sds = d["log_sd"]; log_tf = d["log_transformed"]
        # Back-compat: v2 NPZs have no 'sex' array. Default every cell to 'pooled'.
        sexes = d["sex"] if "sex" in d.files else None
```

In the row loop (around line 355, where `NormCell(...)` is constructed), pass `sex`:

```python
            cells.append(NormCell(
                bin=str(bins[i]),
                # ... existing fields ...
                sex=str(sexes[i]) if sexes is not None else "pooled",  # NEW
            ))
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_npz_sex_roundtrip.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 6: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 188 passed, 0 failures.

- [ ] **Step 7: Commit**

```bash
git add open_normative/io.py tests/test_npz_sex_roundtrip.py
git commit -m "feat(io): NPZ writer/reader carry sex array; format_version 2 -> 3

write_norms_npz emits a 'sex' U10 parallel array per category, lists
'unique_sexes' in metadata, and bumps format_version to 3.
read_norms_npz defaults missing 'sex' arrays to 'pooled' so existing
v2 bundles continue to read.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: CSV writer adds `sex` column

**Files:**
- Modify: `open_normative/io.py:write_norms_csv` (lines 71-121)
- Test: `tests/test_sex_stratification.py` (append)

- [ ] **Step 1: Write failing test**

Append to `tests/test_sex_stratification.py`:

```python
def test_csv_writer_includes_sex_column(tmp_path: Path):
    import csv
    from open_normative.io import write_norms_csv

    cells = [
        _make_cell(),  # default sex='pooled'
    ]
    cells[0] = NormCell(
        bin="20-29", condition="ec", channel="Fz", band="Alpha",
        metric="absolute_power", n=10, mean=1.0, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={}, sex="F",
    )
    path = tmp_path / "norms.csv"
    write_norms_csv(cells, path)

    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert "sex" in rows[0]
    assert rows[0]["sex"] == "F"
```

- [ ] **Step 2: Run test to verify failure**

```bash
python -m pytest tests/test_sex_stratification.py::test_csv_writer_includes_sex_column -v
```
Expected: KeyError or assertion fails — `sex` not in CSV columns.

- [ ] **Step 3: Add `sex` to CSV columns**

In `open_normative/io.py:write_norms_csv`, modify `base_fields` (around line 86) to include `sex` right after `bin`:

```python
    base_fields = [
        "bin", "sex", "condition", "channel", "band", "metric",
        "n", "mean", "sd", "log_mean", "log_sd", "log_transformed",
        "normality_p", "ci_lower", "ci_upper", "pi_lower", "pi_upper",
        "skewness", "kurtosis", "transform_normalized",
    ]
```

In the row dict (around line 98), add `"sex": cell.sex,` after `"bin"`:

```python
            row = {
                "bin": cell.bin,
                "sex": cell.sex,                # NEW
                "condition": cell.condition,
                # ... rest unchanged
            }
```

- [ ] **Step 4: Run test to verify pass**

```bash
python -m pytest tests/test_sex_stratification.py::test_csv_writer_includes_sex_column -v
```
Expected: PASS.

- [ ] **Step 5: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 189 passed, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add open_normative/io.py tests/test_sex_stratification.py
git commit -m "feat(io): write_norms_csv adds sex column after bin

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add `resolved_sex` to `ComparisonResult`

**Files:**
- Modify: `open_normative/compare.py:ComparisonResult` (lines 23-70)
- Test: `tests/test_compare_sex.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_compare_sex.py`:

```python
"""compare_to_norms and compare_and_report carry sex through with fallback."""

import pytest

from open_normative.compare import compare_to_norms, compare_and_report
from open_normative.normative import NormCell


def _norm(sex: str, mean: float = 1.0, sd: float = 0.5, channel: str = "Fz",
          band: str = "Alpha", metric: str = "absolute_power") -> NormCell:
    return NormCell(
        bin="20-29", condition="ec", channel=channel,
        band=band, metric=metric,
        n=100, mean=mean, sd=sd,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={},
        sex=sex,
    )


def test_comparison_result_has_resolved_sex_field():
    norms = [_norm("pooled", mean=1.0)]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.5}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec")
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"
```

- [ ] **Step 2: Run test to verify failure**

```bash
python -m pytest tests/test_compare_sex.py -v
```
Expected: AttributeError on `resolved_sex`.

- [ ] **Step 3: Add `resolved_sex` to ComparisonResult**

In `open_normative/compare.py`, add to the `ComparisonResult` dataclass (after `z_discrepancy_flag` at line 70):

```python
    z_discrepancy_flag: bool = False
    resolved_sex: str = "pooled"     # NEW — "pooled", "F", or "M"
```

Update the docstring (lines 25-48) to mention the new field:

```python
    """Comparison of one clinical metric against the normative distribution.

    Fields:
        ...
        z_discrepancy_flag: True when z_discrepancy exceeds the threshold.
        resolved_sex: Which sex variant of the normative cell was actually used
            ("pooled", "F", or "M"). When the caller passes sex="F" but no F
            cell exists for this tuple, compare_to_norms falls back to pooled
            and reports resolved_sex="pooled" so the consumer can label honestly.
    """
```

- [ ] **Step 4: Wire `resolved_sex` through compare_to_norms (default path)**

In `open_normative/compare.py:compare_to_norms`, in the loop that constructs each `ComparisonResult` (search for `results.append(ComparisonResult(`), pass `resolved_sex=cell.sex` to the constructor. (When the sex= kwarg lands in the next task, this becomes the actual resolution; for now it just echoes the cell's sex.)

- [ ] **Step 5: Run test to verify pass**

```bash
python -m pytest tests/test_compare_sex.py::test_comparison_result_has_resolved_sex_field -v
```
Expected: PASS.

- [ ] **Step 6: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 190 passed.

- [ ] **Step 7: Commit**

```bash
git add open_normative/compare.py tests/test_compare_sex.py
git commit -m "feat(compare): ComparisonResult carries resolved_sex (echoes cell.sex)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `compare_to_norms` gains `sex=` kwarg with fallback semantics

**Files:**
- Modify: `open_normative/compare.py:compare_to_norms` (lines 187-323)
- Test: `tests/test_compare_sex.py` (append)

- [ ] **Step 1: Write failing tests for fallback semantics**

Append to `tests/test_compare_sex.py`:

```python
def test_sex_none_matches_only_pooled():
    """sex=None matches pooled cell, ignores F/M cells even when present."""
    norms = [
        _norm("pooled", mean=1.0),
        _norm("F", mean=10.0),    # very different mean — would be obvious if used
        _norm("M", mean=-10.0),
    ]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex=None)
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"
    # value 1.0 vs pooled mean 1.0 -> z near 0; vs F mean 10.0 -> very negative z
    assert abs(results[0].z_score) < 0.5


def test_sex_f_uses_f_cell_when_present():
    norms = [
        _norm("pooled", mean=1.0),
        _norm("F", mean=2.0, sd=0.5),
    ]
    metrics = {"Fz": {"Alpha": {"absolute_power": 2.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    assert len(results) == 1
    assert results[0].resolved_sex == "F"
    # value 2.0 vs F mean 2.0 -> z near 0
    assert abs(results[0].z_score) < 0.1


def test_sex_f_falls_back_to_pooled_when_no_f_cell():
    """If sex='F' requested but no F cell exists for this tuple, fall back to pooled."""
    norms = [_norm("pooled", mean=1.0)]   # only pooled, no F
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    assert len(results) == 1
    assert results[0].resolved_sex == "pooled"


def test_sex_fallback_is_per_metric():
    """When some tuples have F and some don't, fallback happens per-tuple."""
    norms = [
        _norm("pooled", mean=1.0, channel="Fz"),
        _norm("F", mean=2.0, channel="Fz"),       # F exists for Fz
        _norm("pooled", mean=3.0, channel="Cz"),  # only pooled for Cz
    ]
    metrics = {
        "Fz": {"Alpha": {"absolute_power": 2.0}},
        "Cz": {"Alpha": {"absolute_power": 3.0}},
    }
    results = compare_to_norms(metrics, norms, age=25, condition="ec", sex="F")
    by_channel = {r.channel: r.resolved_sex for r in results}
    assert by_channel == {"Fz": "F", "Cz": "pooled"}


def test_sex_invalid_raises():
    norms = [_norm("pooled")]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    with pytest.raises(ValueError):
        compare_to_norms(metrics, norms, age=25, condition="ec", sex="X")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_compare_sex.py -v
```
Expected: 4 new tests FAIL — `compare_to_norms` doesn't take a `sex` kwarg, the lookup doesn't filter by sex, and the fallback logic doesn't exist.

- [ ] **Step 3: Add `sex` kwarg and fallback logic**

In `open_normative/compare.py:compare_to_norms` (line 187), add the kwarg:

```python
def compare_to_norms(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
    apply_fdr: bool = True,
    fdr_alpha: float = 0.05,
    robust_config: Optional[dict] = None,
    sex: Optional[str] = None,        # NEW
) -> list[ComparisonResult]:
```

After the existing docstring (around line 215), validate the kwarg:

```python
    if sex is not None and sex not in ("F", "M"):
        raise ValueError(f"sex must be None, 'F', or 'M' (got {sex!r})")
    target_sex = sex if sex is not None else "pooled"
```

Replace the norm index construction (lines 222-230) with sex-aware indexing + fallback:

```python
    # Index norms by (channel, band, metric, sex) → cell. For each tuple we
    # also keep a pooled fallback so that when sex='F'/'M' is requested but
    # the variant is absent, we can resolve to pooled per-metric.
    norm_index: dict[tuple, NormCell] = {}
    pooled_index: dict[tuple, NormCell] = {}
    for cell in norms:
        if cell.condition != condition or not _match_bin(age, cell.bin):
            continue
        tup = (cell.channel, cell.band, cell.metric)
        if cell.sex == "pooled":
            if tup not in pooled_index or cell.n > pooled_index[tup].n:
                pooled_index[tup] = cell
        key = (cell.channel, cell.band, cell.metric, cell.sex)
        if key not in norm_index or cell.n > norm_index[key].n:
            norm_index[key] = cell
```

In the per-metric loop (around line 234), change the cell lookup to honor sex with fallback:

```python
    for channel, band_dict in metrics.items():
        for band, metric_dict in band_dict.items():
            for metric_name, value in metric_dict.items():
                tup = (channel, band, metric_name)
                cell = norm_index.get((channel, band, metric_name, target_sex))
                if cell is None and target_sex != "pooled":
                    cell = pooled_index.get(tup)
                if cell is None:
                    continue
                # ... rest of the loop body unchanged
```

(The existing `results.append(ComparisonResult(...))` at the bottom of this loop should already pass `resolved_sex=cell.sex` from Task 5 — verify.)

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/test_compare_sex.py -v
```
Expected: All compare_sex tests PASS.

- [ ] **Step 5: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 195 passed. **If existing comparison tests fail**, they likely construct norm lists with NormCells whose default `sex="pooled"` is incompatible with the new behavior (e.g., they expected a cell to be picked up that no longer matches because they implicitly had sex="" or similar). Inspect and adjust each — most should just work because `NormCell.sex` defaults to `"pooled"` and `sex=None` matches pooled.

- [ ] **Step 6: Commit**

```bash
git add open_normative/compare.py tests/test_compare_sex.py
git commit -m "feat(compare): compare_to_norms gains sex= kwarg with per-metric pooled fallback

sex=None matches pooled only (preserves existing behavior).
sex='F'/'M' prefers the matching variant; when a tuple has no F/M cell,
falls back to pooled and reports resolved_sex='pooled' on that result.
Invalid sex raises ValueError.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `compare_and_report` passes `sex` through; report carries `resolved_sex_summary`

**Files:**
- Modify: `open_normative/compare.py:ComparisonReport` (lines 609-688), `compare_and_report` (lines 888-916)
- Test: `tests/test_compare_sex.py` (append)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_compare_sex.py`:

```python
def test_compare_and_report_passes_sex_through():
    norms = [
        _norm("pooled", mean=1.0, channel="Fz"),
        _norm("F", mean=2.0, channel="Fz"),
    ]
    metrics = {"Fz": {"Alpha": {"absolute_power": 2.0}}}
    report = compare_and_report(metrics, norms, age=25, condition="ec", sex="F")
    # report.results is a list[EnrichedResult]; each wraps a base ComparisonResult
    assert len(report.results) == 1
    assert report.results[0].base.resolved_sex == "F"


def test_report_metadata_has_resolved_sex_summary():
    norms = [
        _norm("pooled", mean=1.0, channel="Fz"),
        _norm("F", mean=2.0, channel="Fz"),
        _norm("pooled", mean=3.0, channel="Cz"),     # only pooled for Cz
    ]
    metrics = {
        "Fz": {"Alpha": {"absolute_power": 2.0}},
        "Cz": {"Alpha": {"absolute_power": 3.0}},
    }
    report = compare_and_report(metrics, norms, age=25, condition="ec", sex="F")
    summary = report.to_dict()["metadata"]["resolved_sex_summary"]
    assert summary == {"F": 1, "pooled": 1}


def test_report_summary_is_empty_when_sex_is_none():
    """sex=None means all results resolve to pooled; summary is just {'pooled': N}."""
    norms = [_norm("pooled", mean=1.0)]
    metrics = {"Fz": {"Alpha": {"absolute_power": 1.0}}}
    report = compare_and_report(metrics, norms, age=25, condition="ec", sex=None)
    summary = report.to_dict()["metadata"]["resolved_sex_summary"]
    assert summary == {"pooled": 1}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python -m pytest tests/test_compare_sex.py -v
```
Expected: 3 new tests FAIL — `compare_and_report` doesn't take `sex` and `to_dict()["metadata"]` has no `resolved_sex_summary`.

- [ ] **Step 3: Update `compare_and_report` signature**

In `open_normative/compare.py:compare_and_report` (line 888), add the kwarg:

```python
def compare_and_report(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
    config: Optional[dict] = None,
    fdr_alpha: float = 0.05,
    sex: Optional[str] = None,        # NEW
) -> ComparisonReport:
```

In the body (around line 909), pass `sex` through:

```python
    results = compare_to_norms(
        metrics, norms, age, condition,
        apply_fdr=True, fdr_alpha=fdr_alpha,
        sex=sex,
    )
```

- [ ] **Step 4: Update `ComparisonReport.to_dict` to emit `resolved_sex_summary`**

In `open_normative/compare.py:ComparisonReport.to_dict` (around line 627), in the `"metadata"` dict, add:

```python
            "metadata": {
                "age": self.age,
                "condition": self.condition,
                "age_bin": self.age_bin,
                "age_interpolated": self.age_interpolated,
                "total_tests": self.total_tests,
                "fdr_significant_count": self.fdr_significant_count,
                "fdr_alpha": self.fdr_alpha,
                "expected_false_positives_uncorrected": round(
                    self.expected_false_positives_uncorrected, 1
                ),
                "resolved_sex_summary": self._sex_summary(),    # NEW
            },
```

Add the helper method below `to_dict`:

```python
    def _sex_summary(self) -> dict:
        """Count how many results resolved to each sex variant."""
        summary: dict[str, int] = {}
        for er in self.results:
            key = er.base.resolved_sex
            summary[key] = summary.get(key, 0) + 1
        return summary
```

- [ ] **Step 5: Run tests to verify pass**

```bash
python -m pytest tests/test_compare_sex.py -v
```
Expected: All compare_sex tests PASS (including the 3 new).

- [ ] **Step 6: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 198 passed.

- [ ] **Step 7: Commit**

```bash
git add open_normative/compare.py tests/test_compare_sex.py
git commit -m "feat(compare): compare_and_report passes sex through; report emits resolved_sex_summary

ComparisonReport.to_dict()['metadata']['resolved_sex_summary'] counts how
many results resolved to each sex variant ('F', 'M', 'pooled'). Consumers
render this in pane headers to label sex-matched coverage honestly.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `build_normative_psd` adds sex axis, writes to `npz/psd_spectrum.npz`

**Files:**
- Modify: `scripts/build_norms.py:build_normative_psd` (lines 330-518) and its caller around line 895
- Test: `tests/test_psd_slab.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/test_psd_slab.py`:

```python
"""build_normative_psd emits a sex-stratified slab at npz/psd_spectrum.npz."""

import json
import logging
from pathlib import Path

import numpy as np
import pytest


def _write_psd_checkpoint(path: Path, freqs, psds, ch_names):
    """Mirror save_psd_checkpoint in scripts/build_norms.py."""
    np.savez_compressed(path, freqs=freqs, psds=psds, ch_names=np.array(ch_names))


def test_psd_slab_has_sex_axis(tmp_path: Path):
    from scripts.build_norms import build_normative_psd

    # Synthetic: 2 F + 2 M subjects, single condition, 4 channels, 5 freqs.
    ch_names = ["Fz", "Cz", "Pz", "Oz"]
    freqs = np.linspace(1, 30, 5)
    # Different mean power per sex so pooled-vs-F-vs-M can be distinguished.
    psd_f = np.full((4, 5), 1e-12)
    psd_m = np.full((4, 5), 1e-10)

    psd_dir = tmp_path / "psd"
    psd_dir.mkdir()
    subjects = []
    for sid, age, sex, psd in [
        ("s01", 25, "F", psd_f),
        ("s02", 27, "F", psd_f),
        ("s03", 26, "M", psd_m),
        ("s04", 28, "M", psd_m),
    ]:
        _write_psd_checkpoint(psd_dir / f"{sid}_ec_psd.npz", freqs, psd, ch_names)
        subjects.append({"subject_id": sid, "age": age, "sex": sex,
                          "condition": "ec"})

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "npz").mkdir()
    build_normative_psd(
        psd_dir, subjects, age_bins=[20, 30, 100],
        output_path=out_dir / "npz" / "psd_spectrum.npz",
        logger=logging.getLogger("test"),
    )

    arr = np.load(out_dir / "npz" / "psd_spectrum.npz")
    # Axis order: (n_bins, n_conds, 3 sex, n_channels, n_freqs)
    assert arr["mean"].shape == (1, 1, 3, 4, 5)
    assert list(arr["sexes"]) == ["pooled", "F", "M"]
    # F slice mean ≈ log10(1e-12 * 1e12) = log10(1.0) = 0
    pooled_idx = list(arr["sexes"]).index("pooled")
    f_idx = list(arr["sexes"]).index("F")
    m_idx = list(arr["sexes"]).index("M")
    assert np.allclose(arr["mean"][0, 0, f_idx, :, :], 0.0, atol=1e-6)
    # M slice mean ≈ log10(1e-10 * 1e12) = log10(100) = 2
    assert np.allclose(arr["mean"][0, 0, m_idx, :, :], 2.0, atol=1e-6)
    # Pooled is the mean of all 4 subjects' log10 PSDs = mean(0, 0, 2, 2) = 1
    assert np.allclose(arr["mean"][0, 0, pooled_idx, :, :], 1.0, atol=1e-6)


def test_metadata_lists_psd_spectrum_category(tmp_path: Path):
    """After build_normative_psd writes the slab, metadata.json gets an entry."""
    # This test sets up the same as above but also asserts the metadata entry.
    # The orchestration that writes metadata.json lives in the build_norms.py
    # main flow — verify the registration helper builds the right manifest entry.
    from scripts.build_norms import register_psd_spectrum_in_metadata
    npz_dir = tmp_path
    # Pre-existing metadata.json (typical for a v2 run that already wrote
    # write_norms_npz output).
    (npz_dir / "metadata.json").write_text(json.dumps({
        "format_version": 3,
        "total_cells": 0,
        "categories": {},
        "age_bins": ["20-29"],
        "conditions": ["ec"],
    }))
    # And a slab file at the expected path.
    slab_path = npz_dir / "psd_spectrum.npz"
    np.savez_compressed(slab_path,
        freqs=np.linspace(1, 30, 5),
        bins=np.array(["20-29"]),
        conditions=np.array(["ec"]),
        sexes=np.array(["pooled", "F", "M"]),
        ch_names=np.array(["Fz"]),
        mean=np.zeros((1, 1, 3, 1, 5)),
    )
    register_psd_spectrum_in_metadata(npz_dir)
    meta = json.loads((npz_dir / "metadata.json").read_text())
    cat = meta["categories"]["psd_spectrum"]
    assert cat["file"] == "psd_spectrum.npz"
    assert cat["layout"] == "slab"
    assert sorted(cat["unique_sexes"]) == ["F", "M", "pooled"]
    assert cat["n_freqs"] == 5
    assert cat["n_channels"] == 1
```

- [ ] **Step 2: Run test to verify failure**

```bash
python -m pytest tests/test_psd_slab.py -v
```
Expected: First test FAILS (`build_normative_psd` doesn't take `output_path` kwarg, doesn't carry sex axis); second FAILS (`register_psd_spectrum_in_metadata` doesn't exist).

- [ ] **Step 3: Add sex axis to `build_normative_psd`**

In `scripts/build_norms.py:build_normative_psd` (line 330), modify the signature to also accept an explicit `output_path` (the current implementation hardcodes the path internally):

```python
def build_normative_psd(psd_dir: Path, subjects_for_norms: list,
                        age_bins: list, output_path: Path, logger):
```

In the grouping logic (around line 379), key by `(bin, condition, sex)` instead of `(bin, condition)` and fan each subject to pooled + own sex:

```python
    # Collect PSD data grouped by (bin, condition, sex). Each subject
    # contributes to ("pooled", ...) and ((F|M), ...) when sex is F/M.
    grouped: dict[tuple, list] = {}
    ref_freqs = None
    suspect_units = []

    for fpath in psd_files:
        stem = fpath.stem.replace("_psd", "")
        info = subject_info.get(stem)
        if info is None:
            continue

        age_bin = age_to_bin(info["age"])
        if age_bin is None:
            continue

        raw_sex = str(info.get("sex", "") or "").strip().upper()
        subject_sex = raw_sex if raw_sex in {"F", "M"} else None

        # ... existing PSD loading + unit check + log10 conversion ...

        for s in ("pooled", subject_sex):
            if s is None:
                continue
            key = (age_bin, info["condition"], s)
            grouped.setdefault(key, []).append((ch_names, log10_psds))
```

Also extend `subject_info` (line 353) to carry sex:

```python
    subject_info = {}
    for s in subjects_for_norms:
        key = f"{s['subject_id']}_{s['condition']}"
        subject_info[key] = {
            "age": s["age"],
            "condition": s["condition"],
            "sex": s.get("sex", ""),
        }
```

Add a sex axis to all the output arrays (around line 449). Define the sex order and add an axis at index 2:

```python
    SEX_ORDER = ["pooled", "F", "M"]
    n_sex = 3

    n_arr = np.zeros((n_bins, n_conds, n_sex), dtype=int)
    mean_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan, dtype=np.float32)
    sd_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan, dtype=np.float32)
    pct_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs, n_points), np.nan, dtype=np.float32)
    normality_arr = np.full((n_bins, n_conds, n_sex, n_chs, n_freqs), np.nan, dtype=np.float32)
```

Modify the aggregation loop to iterate over the new sex dimension:

```python
    for (b_label, cond, sex), entries in grouped.items():
        bi = bin_idx.get(b_label)
        ci = cond_idx.get(cond)
        si = SEX_ORDER.index(sex)
        if bi is None or ci is None:
            continue

        n_arr[bi, ci, si] = len(entries)
        # ... existing stacking / mean / sd / percentiles / shapiro logic ...
        # Replace bi, ci indexing with bi, ci, si on the slab arrays.
```

And the final write (line 502):

```python
    np.savez_compressed(
        output_path,
        freqs=ref_freqs,
        bins=np.array(bin_labels),
        conditions=np.array(all_conditions),
        sexes=np.array(SEX_ORDER, dtype="U10"),         # NEW
        ch_names=np.array(all_ch_names),
        mean=mean_arr,
        sd=sd_arr,
        n=n_arr,
        percentile_points=np.array(_PERCENTILE_POINTS, dtype=np.float64),
        percentiles=pct_arr,
        normality_p=normality_arr,
        psd_format_version=3,
    )
```

- [ ] **Step 4: Add `register_psd_spectrum_in_metadata` helper**

Add a new function to `scripts/build_norms.py` (somewhere near the other write helpers):

```python
def register_psd_spectrum_in_metadata(npz_dir: Path) -> None:
    """Register npz/psd_spectrum.npz as a v3 category in metadata.json.

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
```

- [ ] **Step 5: Wire the call sites**

Find the existing call to `build_normative_psd` in `scripts/build_norms.py` (search around line 895 and around `--merge` path) and update to:
- Pass the new `output_path=output_dir / "npz" / "psd_spectrum.npz"`
- Also keep writing the legacy `output_dir / "norms_psd.npz"` for one cycle (call `build_normative_psd` twice if needed, or split the writer to return arrays and write both files — pick whichever is less invasive)
- Call `register_psd_spectrum_in_metadata(output_dir / "npz")` after `write_norms_npz` so the spectrum category appears in metadata.json

A clean way: split `build_normative_psd` so it returns the aggregated arrays, then have a small writer that takes those arrays + a path. The main flow calls the aggregator once and writes both paths:

```python
slab_arrays = build_normative_psd_arrays(psd_dir, subjects_for_norms, age_bins, logger)
if slab_arrays is not None:
    _write_psd_slab(slab_arrays, output_dir / "norms_psd.npz")          # legacy shim
    _write_psd_slab(slab_arrays, output_dir / "npz" / "psd_spectrum.npz")  # v3 home
    register_psd_spectrum_in_metadata(output_dir / "npz")
```

(Use whichever refactor pattern matches existing style — the goal is "write the same slab to both paths.")

- [ ] **Step 6: Run tests to verify pass**

```bash
python -m pytest tests/test_psd_slab.py -v
```
Expected: PASS.

- [ ] **Step 7: Extend `tests/test_psd_percentiles.py` for the sex axis**

In `tests/test_psd_percentiles.py`, find the existing tests that load `norms_psd.npz` (or the equivalent aggregator output). For each, parameterize/index across the new sex axis at position 2. Example pattern: instead of `arr["mean"][bi, ci]`, the slab is now `arr["mean"][bi, ci, sex_idx]` where `sex_idx` is the position of "pooled" in `arr["sexes"]`. Update each existing assertion to slice the pooled axis when the test setup is single-sex (so the assertions compare against the same values as before).

Run:
```bash
python -m pytest tests/test_psd_percentiles.py -v
```
Expected: All existing tests still pass (now sliced through the pooled sex index).

- [ ] **Step 8: Full baseline green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: ~200 passed.

- [ ] **Step 9: Commit**

```bash
git add scripts/build_norms.py tests/test_psd_slab.py tests/test_psd_percentiles.py
git commit -m "feat(build_norms): PSD slab gains sex axis; writes to npz/psd_spectrum.npz

Per-subject PSD checkpoints are now fanned to (pooled, F, M) and the slab
arrays gain a sex axis at index 2. The slab is written twice for one
bundle cycle: at the legacy path (norms_psd.npz, back-compat shim) and
at the new v3 home (npz/psd_spectrum.npz, registered in metadata.json
with layout='slab').

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Smoke test on synthetic dataset

**Files:**
- Test: `tests/test_end_to_end_smoke.py` (new)

- [ ] **Step 1: Write end-to-end smoke test**

Create `tests/test_end_to_end_smoke.py`:

```python
"""End-to-end smoke test: build a tiny synthetic norm bundle, read it back,
   compare a patient against it with sex='F', verify the report carries the
   expected resolved_sex_summary."""

from pathlib import Path

import pytest

from open_normative.compare import compare_and_report
from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import build_normative


def test_smoke_build_write_read_compare(tmp_path: Path):
    # 6 subjects: 3 F (low alpha values ~1.0-1.2), 3 M (higher values ~2.0-2.2),
    # all in the same age bin and condition.
    subjects = []
    for sid, age, sex, val in [
        ("s01", 25, "F", 1.0), ("s02", 26, "F", 1.1), ("s03", 27, "F", 1.2),
        ("s04", 25, "M", 2.0), ("s05", 26, "M", 2.1), ("s06", 27, "M", 2.2),
    ]:
        subjects.append({"subject_id": sid, "age": age, "sex": sex,
                          "condition": "ec",
                          "metrics": {"Fz": {"Alpha": {"absolute_power": val}}}})

    norms = build_normative(subjects, age_bins=[20, 30, 100])
    write_norms_npz(norms, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    assert len(loaded) == len(norms)

    # Patient: age 25, sex F, value 2.0 (in M range, not F range).
    patient_metrics = {"Fz": {"Alpha": {"absolute_power": 2.0}}}
    report_f = compare_and_report(patient_metrics, loaded, age=25, condition="ec", sex="F")
    report_pooled = compare_and_report(patient_metrics, loaded, age=25, condition="ec", sex=None)

    # F-matched z should be much larger than pooled-matched z because F mean is ~1.1
    # and F sd is small, while pooled mean is ~1.6.
    f_z = report_f.results[0].base.z_score
    pooled_z = report_pooled.results[0].base.z_score
    assert f_z > pooled_z > 0
    # And the F report's metadata reflects F matching.
    assert report_f.to_dict()["metadata"]["resolved_sex_summary"] == {"F": 1}
    assert report_pooled.to_dict()["metadata"]["resolved_sex_summary"] == {"pooled": 1}
```

- [ ] **Step 2: Run test**

```bash
python -m pytest tests/test_end_to_end_smoke.py -v
```
Expected: PASS.

- [ ] **Step 3: Full baseline + commit**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: All tests pass.

```bash
git add tests/test_end_to_end_smoke.py
git commit -m "test(smoke): end-to-end build->write->read->compare with sex='F' fallback

Builds a 6-subject (3F + 3M) synthetic dataset, writes it through
write_norms_npz, reads back via read_norms_npz, and verifies that
compare_and_report(sex='F') returns a larger z than sex=None for a
patient whose value lies in the M range — the F-matched comparison
detects the deviation that the pooled comparison hides.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: PROVENANCE doc — sex breakdown + PSD spectrum note

**Files:**
- Modify: `scripts/release.py` (or wherever `PROVENANCE.md` is generated in the release/distribute flow — find with `grep -rn PROVENANCE scripts/`)
- Reference only: the bundle's `PROVENANCE.md` template

- [ ] **Step 1: Locate PROVENANCE generation**

```bash
grep -rn "PROVENANCE" scripts/ open_normative/ | head -20
```
This will identify the script that writes `PROVENANCE.md`. Likely candidates: `scripts/release.py` or `scripts/distribute.py`.

- [ ] **Step 2: Add a sex breakdown section**

In the identified script's PROVENANCE writer, add a section that builds a markdown table from `subjects_for_norms` showing count of F/M/unknown per age bin per condition. Pseudocode:

```python
from collections import Counter
def _sex_breakdown_table(subjects: list[dict], age_bins: list[int]) -> str:
    counts = Counter()
    for s in subjects:
        bin_label = _assign_bin(s["age"], age_bins)  # imported from open_normative.normative
        if bin_label is None:
            continue
        raw_sex = str(s.get("sex", "") or "").strip().upper()
        sex = raw_sex if raw_sex in {"F", "M"} else "Other/unknown"
        counts[(bin_label, s["condition"], sex)] += 1
    bin_labels = sorted({k[0] for k in counts}, key=lambda x: int(x.split("-")[0]))
    conditions = sorted({k[1] for k in counts})
    lines = ["| Age bin | Condition | F | M | Other/unknown | Total |",
             "|---|---|---|---|---|---|"]
    for b in bin_labels:
        for c in conditions:
            f = counts.get((b, c, "F"), 0)
            m = counts.get((b, c, "M"), 0)
            o = counts.get((b, c, "Other/unknown"), 0)
            lines.append(f"| {b} | {c} | {f} | {m} | {o} | {f+m+o} |")
    return "\n".join(lines)
```

Insert the table into the PROVENANCE markdown under a new `## Cohort sex breakdown` heading. Also add a `## PSD freq-resolved category` paragraph:

```markdown
## PSD freq-resolved category

The v3 bundle is self-sufficient for both band-level and frequency-resolved
queries. Per-frequency normative spectra live at `npz/psd_spectrum.npz`
(slab layout — see the file's schema). The legacy root-level `norms_psd.npz`
is a back-compat shim and will be removed in the next bundle regeneration.

## Cohort sex breakdown

<inserted table>

Subjects with empty or non-F/M sex are reported in "Other/unknown" and
contribute only to the pooled cells — no own-sex stratified cell ships
for them.
```

- [ ] **Step 3: No automated test for the doc writer**

This is a doc-generation change; the test for correctness is reviewing the rendered `PROVENANCE.md` after the smoke regeneration in Task 11. Verify by:
- Running the build on a small synthetic dataset (Task 11)
- Opening the generated `PROVENANCE.md` and confirming the two new sections appear and the table sums match the input cohort

- [ ] **Step 4: Commit**

```bash
git add scripts/release.py   # or wherever PROVENANCE is generated
git commit -m "docs(provenance): add cohort sex breakdown table and PSD spectrum note

PROVENANCE.md gains two sections:
- 'PSD freq-resolved category': documents npz/psd_spectrum.npz and the
  one-cycle back-compat retention of legacy norms_psd.npz.
- 'Cohort sex breakdown': per-bin F/M/Other-unknown counts so consumers
  can see where sex-stratified cells will be thin.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Run a smoke regeneration on a tiny real dataset

**Files:** None modified — verification only.

- [ ] **Step 1: Pick a small dataset for the smoke run**

The smallest available is likely the SRM dataset (~111 subjects) — but for a *real* smoke test we want something even smaller. Look at `open_normative/datasets/` for the smallest. Alternatively, point `--max-subjects 20` at LEMON.

- [ ] **Step 2: Run build_norms.py on the smoke dataset**

```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python scripts/build_norms.py ~/Data/EEG/<smallest_available_dataset> \
    --dataset <dataset_name> --condition both --channels 19 \
    --max-subjects 20 --save-psd \
    --output /tmp/smoke_norms_v3 -j 2 2>&1 | tail -30
```
(Substitute the dataset path the user has locally. Ask before running if uncertain.)

Expected: Build completes without error.

- [ ] **Step 3: Verify the v3 bundle structure**

```bash
ls /tmp/smoke_norms_v3/npz/
cat /tmp/smoke_norms_v3/npz/metadata.json | python -m json.tool | head -30
```
Expected:
- `npz/` contains the usual 8 categories *plus* `psd_spectrum.npz`
- `metadata.json` shows `"format_version": 3`
- `psd_spectrum` category has `"layout": "slab"` and `"unique_sexes": ["F", "M", "pooled"]`
- Every other category's metadata includes `"unique_sexes": [...]`
- The legacy root `norms_psd.npz` still exists alongside the npz/ directory

- [ ] **Step 4: Smoke-test consumer-side load**

```bash
python -c "
from open_normative.io import read_norms_npz
cells = read_norms_npz('/tmp/smoke_norms_v3/npz')
sexes = set(c.sex for c in cells)
print(f'Total cells: {len(cells)}')
print(f'Sex variants: {sorted(sexes)}')
print(f'Cells per variant: {[(s, sum(1 for c in cells if c.sex == s)) for s in sorted(sexes)]}')
"
```
Expected output: `Sex variants: ['F', 'M', 'pooled']` and roughly 3× the cell count of a v2 bundle.

- [ ] **Step 5: Document smoke results inline (in this plan or a follow-up note)**

If the smoke run reveals issues (e.g., one dataset's loader doesn't carry sex, or a cell triple count is wrong), file follow-ups in this plan as new tasks. If it passes, mark the spec as ready for full-bundle regeneration.

- [ ] **Step 6: Commit any fixes**

If the smoke surfaced anything, commit each fix as a separate small commit (one fix per commit). If smoke is clean, no commit needed for this task.

---

## Out of plan scope

These are explicitly NOT part of this plan, per the spec's "Out of scope":

- Higher-order stratification (sex × handedness, etc.).
- A `compare_and_report(sex="auto")` mode.
- Refactoring the slab vs. flat layout dichotomy.
- Updates to the Coherence Workstation consumer code itself.
- Full bundle regeneration (LEMON + Dortmund production run) — gated on a separate decision to ship a new bundle version.
