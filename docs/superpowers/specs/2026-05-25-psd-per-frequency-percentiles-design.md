# Per-frequency percentiles in `norms_psd.npz`

**Date:** 2026-05-25
**Status:** Approved design → implementation
**Branch:** `feat/psd-per-frequency-percentiles`

## Problem

The band-level norms (per-cell NPZ under `npz/`, `format_version: 2`, commit `a4fb198`)
ship `percentile_points` + a per-cell `percentiles` vector so the Coherence Workstation
(CW) can compute a percentile-derived robust z and render distribution-honest reads
instead of Gaussian ±σ.

The per-frequency PSD norms (`norms_psd.npz`) still carry only `mean`/`sd` in
log10(µV²/Hz). EEG power is fat-tailed per-frequency, so ±σ over/under-states the band
at most frequencies. CW's Spectra pane wants to overlay **percentile ribbons** instead of
mean ± σ. This task gives the PSD bundle the same percentile treatment.

## What exists today

`scripts/build_norms.py::build_normative_psd()` writes `norms_psd.npz` with:

- `freqs` (n_freqs,), `bins` (n_bins,), `conditions` (n_conditions,), `ch_names` (n_channels,)
- `mean` (n_bins, n_conditions, n_channels, n_freqs) — log10(µV²/Hz)
- `sd` (same shape) — log10(µV²/Hz)
- `n` (n_bins, n_conditions)

Crucially, the function already stacks every subject's PSD into
`stacked = (n_subjects, n_channels, n_freqs)` (build_norms.py:426–434) and reduces it via
`np.nanmean`/`np.nanstd`. The full per-frequency distribution is therefore already in hand
at the point where `mean`/`sd` are computed — percentiles need no extra I/O, no second
pass, and no re-run from raw EEG.

## Design

Additive change to **one function** (`build_normative_psd`), plus regeneration of the
merged bundle and refresh of the `cw_payload_v2/` product payload.

### New arrays (existing arrays untouched)

| key | shape | dtype | notes |
|-----|-------|-------|-------|
| `percentile_points` | (13,) | float64 | imported `_PERCENTILE_POINTS` — identical to band-level |
| `percentiles` | (n_bins, n_conditions, n_channels, n_freqs, 13) | **float32** | log10(µV²/Hz) space; NaN where n < 2; ≈ 46 MB at 6×2×37×199×13 |
| `normality_p` | (n_bins, n_conditions, n_channels, n_freqs) | float32 | Shapiro–Wilk p of the log (scoring) space; NaN if n < 3 |
| `psd_format_version` | scalar int | — | `2` — consumers branch on presence |

`percentile_points` = `[0.5, 1, 2.5, 5, 10, 25, 50, 75, 90, 95, 97.5, 99, 99.5]` (index 6 = p50).

### Computation (inside the existing per-(bin,condition) loop)

```python
# stacked: (n_subjects, n_channels, n_freqs), log10(µV²/Hz)
mean_arr[bi, ci] = np.nanmean(stacked, axis=0)
sd_arr[bi, ci]   = np.nanstd(stacked, axis=0, ddof=1)

# percentiles → (n_channels, n_freqs, 13)
if len(entries) >= 2:
    pct = np.nanpercentile(stacked, _PERCENTILE_POINTS, axis=0)   # (13, n_ch, n_freq)
    pct_arr[bi, ci] = np.moveaxis(pct, 0, -1).astype(np.float32)

# normality_p → (n_channels, n_freqs); Shapiro per (ch, freq)
for chi in range(n_chs):
    for fi in range(n_freqs):
        col = stacked[:, chi, fi]
        col = col[~np.isnan(col)]
        if col.size >= 3 and np.std(col, ddof=1) > 0:
            try:
                normality_arr[bi, ci, chi, fi] = float(stats.shapiro(col).pvalue)
            except Exception:
                pass  # stays NaN
```

### Reuse, not reinvent

- Import `_PERCENTILE_POINTS` from `open_normative.normative` (the same list the
  band-level v2 norms use).
- Use `np.nanpercentile` — the nan-aware analog of the band-level inline `np.percentile`.
  `stacked` carries NaN for unaligned channels, which is exactly why `mean`/`sd` already
  use `np.nanmean`/`np.nanstd`.
- `normality_p` mirrors the band-level `stats.shapiro` call and its guard (n ≥ 3, std > 0,
  try/except).

No second percentile implementation is introduced.

### Regeneration & deliverable

Re-run the **fixed** merge (also recovers the silently-dropped PSDs from commit `836c5ab`),
then refresh the CW payload:

```bash
python scripts/build_norms.py --merge \
  --merge-dir norms_merge_in/lemon/subjects \
  --merge-dir norms_merge_in/dortmund/subjects \
  --merge-dir norms_merge_in/srm/subjects \
  --output norms_output_all_merged

cp norms_output_all_merged/norms_psd.npz cw_payload_v2/norms_psd.npz
# update cw_payload_v2/MANIFEST.txt with the new size / version note
```

### Back-compat

Purely additive. An old consumer reading `mean`/`sd` is unaffected. New consumers gate on
`psd_format_version` (or key presence) and fall back to ±σ when the percentile arrays are
absent.

## Verification

Test-first unit test (`tests/test_psd_percentiles.py`) builds a handful of synthetic PSD
checkpoints, runs `build_normative_psd`, and asserts:

1. New keys present with correct shapes/dtypes; existing keys (`mean`/`sd`/`n`/`freqs`/…)
   unchanged.
2. `percentiles[..., 6]` (p50) ≈ `mean` within tolerance for near-normal synthetic cells.
3. `percentiles` monotonic non-decreasing along the last axis.
4. `p2.5`/`p97.5` (indices 2 and 10) roughly bracket `mean ± 2·sd` for near-normal cells.
5. NaN in `percentiles` where n < 2; NaN in `normality_p` where n < 3.
6. `psd_format_version == 2`.

Then confirm the regenerated real bundle passes the same structural/self-checks and report
its new on-disk size.

## Cost

`normality_p` adds ≈ 88k Shapiro calls per bundle (37 ch × 199 freq × 6 bins × 2 cond),
≈ 1–3 min one-time at build. Acceptable for a build step.

## Out of scope

- No change to band-level norms or `io.py` NPZ split.
- No new CLI flags (computation is unconditional inside `build_normative_psd`).
- CW consumer-side rendering of the ribbons (separate product work).
