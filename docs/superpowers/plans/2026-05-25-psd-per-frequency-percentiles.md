# Per-frequency percentiles in `norms_psd.npz` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add additive `percentile_points`, `percentiles`, `normality_p`, and `psd_format_version=2` arrays to `norms_psd.npz` so the Coherence Workstation can render distribution-honest spectrum ribbons instead of Gaussian mean ± σ.

**Architecture:** One additive change to `build_normative_psd()` in `scripts/build_norms.py`, computed from the per-subject `stacked` array that function already builds for mean/sd. Reuse `_PERCENTILE_POINTS` from `open_normative.normative`. Then regenerate the merged bundle and refresh `cw_payload_v2/`.

**Tech Stack:** Python, NumPy (`np.nanpercentile`), SciPy (`stats.shapiro`), pytest.

**Spec:** `docs/superpowers/specs/2026-05-25-psd-per-frequency-percentiles-design.md`

---

## File Structure

- **Modify:** `scripts/build_norms.py`
  - Imports (lines ~24–38): add `import warnings`, `from scipy import stats`, and `_PERCENTILE_POINTS` to the `open_normative.normative` import.
  - `build_normative_psd()` (lines 319–448): add the three arrays to the aggregation loop and the `np.savez_compressed` call.
- **Create:** `tests/test_psd_percentiles.py` — unit test fabricating synthetic PSD checkpoints and asserting the spec self-checks.
- **Data (not git-tracked):** regenerate `norms_output_all_merged/norms_psd.npz`, copy to `cw_payload_v2/norms_psd.npz`, update `cw_payload_v2/MANIFEST.txt`.

---

## Task 1: Add per-frequency percentiles + normality to `build_normative_psd`

**Files:**
- Test: `tests/test_psd_percentiles.py` (create)
- Modify: `scripts/build_norms.py` (imports ~24–38; `build_normative_psd` 412–445)

- [ ] **Step 1: Write the failing test**

Create `tests/test_psd_percentiles.py`:

```python
"""Tests for per-frequency percentiles in norms_psd.npz (psd_format_version 2)."""
import importlib.util
import logging
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "build_norms", Path(__file__).resolve().parent.parent / "scripts" / "build_norms.py"
)
bn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bn)

_PCT = [0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99, 99.5]
_CH = ["Cz", "Pz"]
_FREQS = np.array([2.0, 4.0, 8.0, 16.0, 32.0])
_TRUE_MEAN = np.array([1.0, 0.8, 0.5, 0.0, -0.5])  # per-freq log10(µV²/Hz)
_TRUE_SD = 0.4


def _write_psd_checkpoint(psd_dir, subject_id, condition, log10_uv2):
    """log10_uv2: (n_ch, n_freq). Stored as V²/Hz, since the writer multiplies by 1e12."""
    uv2 = 10.0 ** log10_uv2          # µV²/Hz
    v2 = uv2 * 1e-12                 # → V²/Hz
    bn.save_psd_checkpoint(psd_dir, subject_id, condition, _FREQS, v2.astype(np.float64), _CH)


def _build(tmp_path, seed, n_full=400):
    rng = np.random.default_rng(seed)
    psd_dir = tmp_path / "psd_checkpoints"
    psd_dir.mkdir()
    subjects = []
    # bin "20-29": n_full near-normal subjects in log space
    for i in range(n_full):
        vals = _TRUE_MEAN[None, :] + rng.normal(0.0, _TRUE_SD, size=(len(_CH), len(_FREQS)))
        sid = f"sub-{i:04d}"
        _write_psd_checkpoint(psd_dir, sid, "ec", vals)
        subjects.append({"subject_id": sid, "condition": "ec", "age": 25})
    # bin "30-39": a single subject (n=1) → percentiles + normality must be NaN
    _write_psd_checkpoint(psd_dir, "sub-9000", "ec",
                          _TRUE_MEAN[None, :] + np.zeros((len(_CH), len(_FREQS))))
    subjects.append({"subject_id": "sub-9000", "condition": "ec", "age": 35})
    out = tmp_path / "norms_psd.npz"
    bn.build_normative_psd(psd_dir, subjects, [20, 30, 40], out, logging.getLogger("test"))
    return np.load(out, allow_pickle=False)


def test_new_arrays_present_and_shaped(tmp_path):
    d = _build(tmp_path, 0)
    for k in ["freqs", "bins", "conditions", "ch_names", "mean", "sd", "n",
              "percentile_points", "percentiles", "normality_p", "psd_format_version"]:
        assert k in d.files, f"missing {k}"
    assert int(d["psd_format_version"]) == 2
    np.testing.assert_allclose(d["percentile_points"], _PCT)
    n_bins, n_cond, n_ch, n_freq = d["mean"].shape
    assert d["percentiles"].shape == (n_bins, n_cond, n_ch, n_freq, 13)
    assert d["percentiles"].dtype == np.float32
    assert d["normality_p"].shape == (n_bins, n_cond, n_ch, n_freq)
    assert d["normality_p"].dtype == np.float32


def test_p50_matches_mean(tmp_path):
    d = _build(tmp_path, 1)
    p50 = d["percentiles"][0, 0, :, :, 6]
    np.testing.assert_allclose(p50, d["mean"][0, 0], atol=0.1)


def test_monotonic_along_points(tmp_path):
    d = _build(tmp_path, 2)
    diffs = np.diff(d["percentiles"][0, 0], axis=-1)  # (n_ch, n_freq, 12)
    assert np.all(diffs >= -1e-6)


def test_tails_bracket_two_sigma(tmp_path):
    d = _build(tmp_path, 3)
    mean, sd = d["mean"][0, 0], d["sd"][0, 0]
    p2_5 = d["percentiles"][0, 0, :, :, 2]
    p97_5 = d["percentiles"][0, 0, :, :, 10]
    assert np.all((p2_5 > mean - 2.5 * sd) & (p2_5 < mean - 1.4 * sd))
    assert np.all((p97_5 < mean + 2.5 * sd) & (p97_5 > mean + 1.4 * sd))


def test_nan_where_insufficient_n(tmp_path):
    d = _build(tmp_path, 4)
    assert int(d["n"][1, 0]) == 1                       # bin "30-39"
    assert np.all(np.isnan(d["percentiles"][1, 0]))     # n < 2
    assert np.all(np.isnan(d["normality_p"][1, 0]))     # n < 3


def test_existing_arrays_unchanged(tmp_path):
    d = _build(tmp_path, 5)
    assert d["mean"].dtype == np.float64
    assert d["sd"].dtype == np.float64
    assert list(d["ch_names"]) == _CH
    assert int(d["n"][0, 0]) == 400
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_psd_percentiles.py -v`
Expected: FAIL — `test_new_arrays_present_and_shaped` errors with `missing percentile_points` (the writer doesn't emit the new keys yet).

- [ ] **Step 3: Add the imports**

In `scripts/build_norms.py`, after `import traceback` (line 29) add:

```python
import warnings
```

After `from concurrent.futures import ThreadPoolExecutor, as_completed` block / with the other third-party imports (near line 34, after `import numpy as np`) add:

```python
from scipy import stats
```

Change line 38 from:

```python
from open_normative.normative import build_normative
```

to:

```python
from open_normative.normative import build_normative, _PERCENTILE_POINTS
```

- [ ] **Step 4: Implement the percentile + normality computation**

In `build_normative_psd`, replace the aggregation block (currently lines 412–445, from `# Aggregate` through the `np.savez_compressed(...)` call) with:

```python
    # Aggregate
    n_points = len(_PERCENTILE_POINTS)
    mean_arr = np.full((n_bins, n_conds, n_chs, n_freqs), np.nan)
    sd_arr = np.full((n_bins, n_conds, n_chs, n_freqs), np.nan)
    n_arr = np.zeros((n_bins, n_conds), dtype=int)
    # Distribution-honest additions (psd_format_version 2): per-frequency
    # percentiles + Shapiro-Wilk normality, computed from the same per-subject
    # stack used for mean/sd. float32 keeps `percentiles` (~46 MB) compact.
    pct_arr = np.full((n_bins, n_conds, n_chs, n_freqs, n_points), np.nan, dtype=np.float32)
    normality_arr = np.full((n_bins, n_conds, n_chs, n_freqs), np.nan, dtype=np.float32)

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

        # Per-frequency percentiles (need >=2 subjects). Reuse the band-level
        # _PERCENTILE_POINTS; nanpercentile over the subject axis → (points,
        # n_ch, n_freq), then move points to the last axis to match the
        # documented (..., n_freq, n_points) layout.
        if len(entries) >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                pct = np.nanpercentile(stacked, _PERCENTILE_POINTS, axis=0)
            pct_arr[bi, ci] = np.moveaxis(pct, 0, -1).astype(np.float32)

        # Shapiro-Wilk per (channel, freq) on the log (scoring) space, mirroring
        # the band-level normality_p. NaN if <3 valid samples or zero variance.
        if len(entries) >= 3:
            for chi in range(n_chs):
                for fi in range(n_freqs):
                    col = stacked[:, chi, fi]
                    col = col[~np.isnan(col)]
                    if col.size >= 3 and np.std(col, ddof=1) > 0:
                        try:
                            normality_arr[bi, ci, chi, fi] = float(stats.shapiro(col).pvalue)
                        except Exception:
                            pass  # leave NaN

    np.savez_compressed(
        output_path,
        freqs=ref_freqs,
        bins=np.array(bin_labels),
        conditions=np.array(all_conditions),
        ch_names=np.array(all_ch_names),
        mean=mean_arr,
        sd=sd_arr,
        n=n_arr,
        percentile_points=np.array(_PERCENTILE_POINTS, dtype=np.float64),
        percentiles=pct_arr,
        normality_p=normality_arr,
        psd_format_version=2,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_psd_percentiles.py -v`
Expected: PASS (6 passed).

- [ ] **Step 6: Run the regression suite**

Run: `python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q`
Expected: all previously-passing tests still pass (no regressions).

- [ ] **Step 7: Commit**

```bash
git add tests/test_psd_percentiles.py scripts/build_norms.py
git commit -m "feat(psd-norms): per-frequency percentiles + normality in norms_psd.npz

Adds percentile_points, percentiles (float32, log10 space), normality_p,
and psd_format_version=2 to build_normative_psd, computed from the
per-subject stack already used for mean/sd. Reuses _PERCENTILE_POINTS.
Purely additive; consumers branch on psd_format_version.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Regenerate the merged bundle and refresh `cw_payload_v2/`

**Files:** data only (not git-tracked): `norms_output_all_merged/norms_psd.npz`, `cw_payload_v2/norms_psd.npz`, `cw_payload_v2/MANIFEST.txt`

- [ ] **Step 1: Regenerate via the fixed merge**

Run (from repo root):

```bash
python scripts/build_norms.py --merge \
  --merge-dir norms_merge_in/lemon/subjects \
  --merge-dir norms_merge_in/dortmund/subjects \
  --merge-dir norms_merge_in/srm/subjects \
  --output norms_output_all_merged
```
Expected: log ends with "Saved normative PSD to norms_output_all_merged/norms_psd.npz" and a "Subjects per cell" line.

- [ ] **Step 2: Verify the regenerated bundle (real-data self-checks)**

Run:

```bash
python - <<'PY'
import numpy as np
d = np.load("norms_output_all_merged/norms_psd.npz", allow_pickle=False)
assert int(d["psd_format_version"]) == 2
for k in ["percentile_points", "percentiles", "normality_p"]:
    assert k in d.files, k
np.testing.assert_allclose(d["percentile_points"],
    [0.5,1,2.5,5,10,25,50,75,90,95,97.5,99,99.5])
pct, mean, sd, n = d["percentiles"], d["mean"], d["sd"], d["n"]
print("shapes:", pct.shape, "dtype:", pct.dtype)
# only check well-populated cells
valid = ~np.isnan(pct[..., 6])
p50 = pct[..., 6][valid]; mu = mean[valid]
print("max |p50-mean|:", float(np.nanmax(np.abs(p50 - mu))))
diffs = np.diff(pct, axis=-1)
print("monotonic:", bool(np.all((diffs >= -1e-5) | np.isnan(diffs))))
import os
print("size MB:", round(os.path.getsize("norms_output_all_merged/norms_psd.npz")/1e6, 1))
print("n per (bin,cond):", n.tolist())
PY
```
Expected: `psd_format_version==2`, monotonic `True`, `max |p50-mean|` small (≲ 0.1 in log units), and a printed size.

- [ ] **Step 3: Refresh the CW payload**

```bash
cp norms_output_all_merged/norms_psd.npz cw_payload_v2/norms_psd.npz
```

Then append a note to `cw_payload_v2/MANIFEST.txt` recording the version bump and new size — read the file first, then add a line such as:
`norms_psd.npz — psd_format_version 2 (adds percentile_points, percentiles, normality_p); <SIZE> MB; regenerated 2026-05-25`.

- [ ] **Step 4: Report**

Summarize: new file size, `n` per bin/condition (confirming the 836c5ab PSD recovery), and that `cw_payload_v2/norms_psd.npz` is refreshed. No git commit — these are untracked data artifacts.

---

## Self-Review

**Spec coverage:**
- `percentile_points` (13, float64) — Task 1 Step 4 savez ✓
- `percentiles` (…, 13, float32, log10 space, NaN where n<2) — Task 1 Step 4 (`len(entries) >= 2` gate) ✓; tested in `test_*_shaped`, `test_nan_where_insufficient_n` ✓
- `normality_p` (float32, NaN where n<3) — Task 1 Step 4 (`len(entries) >= 3` + per-col guard) ✓; tested ✓
- `psd_format_version=2` — Task 1 Step 4 ✓; tested ✓
- Reuse `_PERCENTILE_POINTS` / no second impl — Task 1 Step 3 import + `np.nanpercentile` ✓
- Self-checks (p50≈mean, monotonic, tails bracket ±2σ) — Task 1 Steps 1/5 + Task 2 Step 2 ✓
- Regeneration + cw_payload refresh — Task 2 ✓
- Back-compat additive (existing keys unchanged) — `test_existing_arrays_unchanged` ✓

**Placeholder scan:** none — all code and commands are concrete (the only fill-in is `<SIZE>` in the MANIFEST note, derived from Step 2 output).

**Type consistency:** `build_normative_psd`, `save_psd_checkpoint`, `_PERCENTILE_POINTS`, and array names (`pct_arr`, `normality_arr`) are consistent across tasks and match the source signatures verified in the spec.
