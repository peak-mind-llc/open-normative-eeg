# Norms bundle minor fixes — design spec

**Date:** 2026-05-28
**Worktree:** `.claude/worktrees/fix+norms-minor-fixes-2026-05-28`
**Source bug report:** `coherence-workstation/.claude/worktrees/fix+minor-fixes/bug-report-open-normative-2026-05-28.md`
**Bundle baseline:** `merged-lemon-dortmund-37ch-v2-20260524T102747Z` (`format_version: 2`)

## Problem

The v2 normative bundle has two gaps that block the Coherence Workstation app from going "v2-only":

**Gap 1 — Freq-resolved PSD data lives outside v2.**
The per-frequency normative spectrum (used for the gray-ribbon overlay behind a patient's PSD plot) ships as `norms_psd.npz` at the root of the bundle, separate from the eight category files under `npz/`. `PROVENANCE.md` labels it "superseded," but it isn't — the v2 directory has no freq-resolved category to replace it. Consumers have to load both v1 and v2 files; the v2 bundle is not self-sufficient.

**Gap 2 — No sex stratification.**
Every normative cell is computed by pooling F and M subjects together. LEMON and Dortmund both record sex per subject and the dataset loaders normalize it to `"F"`/`"M"`, but the stratification was never carried through `build_normative`. Clinical practice expects sex-matched normative comparisons (alpha amplitudes and frontal asymmetry baselines differ by sex). The UI also can't honestly say "sex bin = F" in its pane header because no such bin exists.

Both gaps must close in a single bundle regeneration so the consumer can drop the v1 file and CW's normative pane can label its match honestly.

## Decisions

The following design choices were made during brainstorming. The spec assumes them.

| Decision | Choice | Why |
|---|---|---|
| Freq-resolved PSD storage layout | Multi-dimensional slab (`mean[bin, cond, sex, channel, freq]`) | ~5 MB vs ~150 MB for flat parallel-array; matches the consumer's natural slice pattern; PSD is already log-space so v2's per-cell `log_mean`/`log_sd`/`log_transformed`/`band`/`metric` fields would be no-ops |
| Sex stratification scope | F, M, pooled for every category (including PSD slab) | Bug report acceptance criterion; CW spectral ribbon overlay also wants sex-matched |
| Sex axis representation | `sex` field on `NormCell` (uniform parallel array in NPZ) | Treats sex analogously to age (another filter axis); single schema bump; avoids tripling file count or inventing a differential encoding |
| Sex min-n behavior | Ship every cell regardless of n; expose `n` per cell | Consumer (CW) already reads and displays `n`; pushes trust decision to caller; simpler writer |
| "Other"/empty sex handling | Contributes to pooled only; no `"Other"` cell shipped | LEMON+Dortmund are effectively binary; an `"Other"` category would have n≈0 and add noise to the schema |
| compare API when requested sex variant missing | Silent fallback to pooled; report `resolved_sex` per result | Avoids holes in the patient report; visible via `resolved_sex_summary` in the report metadata |
| Format version | NPZ `format_version` bumps `2 → 3` | Version-3 readers parse the new `sex` array; version-2 bundles read with default `sex="pooled"` |

## Architecture

### Files touched

| File | Change |
|---|---|
| `open_normative/normative.py` | `NormCell` gains `sex: str = "pooled"`. `build_normative()` accumulator key gains a sex slot; each subject contributes to `("pooled", ...)` plus `(subject["sex"], ...)` when sex is `"F"`/`"M"`. |
| `open_normative/io.py` | `write_norms_npz` adds `sex` U10 parallel array per category and writes `format_version: 3`. `read_norms_npz` reads it; defaults to `"pooled"` for older bundles. `write_norms_csv` inserts a `sex` column after `bin`. |
| `open_normative/compare.py` | `compare_to_norms` and `compare_and_report` gain `sex: Optional[str] = None`. Norm index keyed by `(channel, band, metric, sex)`. When `sex="F"`/`"M"`, prefer the matching variant; fall back to `"pooled"` if absent. Each `ComparisonResult` carries `resolved_sex`. `ComparisonReport.metadata` carries `resolved_sex_summary`. |
| `scripts/build_norms.py` | `build_normative_psd` adds a sex axis to every output array; writes to `output_dir/npz/psd_spectrum.npz`; registers in `metadata.json` with `"layout": "slab"`. Legacy root `norms_psd.npz` still written for one bundle cycle (the v3 LEMON+Dortmund regeneration that lands this spec; removed in the regeneration after that) as a back-compat shim. |
| `PROVENANCE.md` (in bundle) | Adds sex breakdown table per age bin; notes PSD freq-resolved category at `npz/psd_spectrum.npz`; marks root `norms_psd.npz` deprecated with removal target. |
| `tests/test_sex_stratification.py` (new) | Verifies pooled/F/M cell triples; verifies pooled equals union of all subjects (incl. Other); verifies Other/empty contributes only to pooled. |
| `tests/test_npz_sex_roundtrip.py` (new) | Sex round-trips through write/read; version-2 NPZ reads back with default `"pooled"`. |
| `tests/test_compare_sex.py` (new) | `sex="F"` uses F when present, falls back to pooled when not; `resolved_sex` reported correctly; `sex=None` matches today's behavior. |
| `tests/test_psd_percentiles.py` (extended) | PSD slab carries new sex axis; pooled equals current-behavior baseline when synthetic data is single-sex. |

### Data flow (after changes)

```
[per-subject pipeline output]
  metrics dict, age, sex, condition
        │
        ▼
build_normative(subjects)
  accumulator key: (bin, sex, cond, channel, band, metric)
  each subject fans out:
    → ("pooled", ...)                              always
    → (subject["sex"], ...)                        if sex ∈ {"F", "M"}
        │
        ▼
[NormCell list — ~3× as many as before]
        │
        ├──> write_norms_json   (full fidelity, adds `sex` field per cell)
        ├──> write_norms_csv    (adds `sex` column)
        └──> write_norms_npz    (adds `sex` parallel array per category)
                                 format_version: 3

[per-subject PSD checkpoints]
  freqs, log10(psds), ch_names, age, sex, condition
        │
        ▼
build_normative_psd(...)
  grouped by (bin, cond, sex)
  each subject fans into "pooled" + own sex bucket
        │
        ▼
output_dir/npz/psd_spectrum.npz
  shape (n_bins, n_conds, 3, n_channels, n_freqs)
  metadata.json["categories"]["psd_spectrum"] = {layout: "slab", ...}
```

### Consumer-side flow (after changes)

```
CW: load_normative_bundle(format_version=3)
  reads sex axis from every category and from psd_spectrum
        │
        ▼
CW: compare_and_report(patient_metrics, age, condition, sex="F")
        │
        ▼
open_normative.compare.compare_to_norms
  for each (channel, band, metric):
    F variant exists?  → use it,      resolved_sex="F"
    else               → use pooled,  resolved_sex="pooled"
        │
        ▼
ComparisonReport
  metadata.resolved_sex_summary = {"F": 1247, "pooled": 12}
  CW pane header: "age 30–39 · sex F · EO (1247 F / 12 pooled)"
```

## Specifications

### `NormCell.sex` field

- Type: `str`
- Default: `"pooled"`
- Legal values: `"pooled"`, `"F"`, `"M"`
- Position: inserted after `bin` in the dataclass field order for natural grouping with the other key fields
- Back-compat: JSON files without a `sex` field deserialize to `sex="pooled"` (handled in `read_norms_json` with `item.setdefault("sex", "pooled")`)

### NPZ schema, format_version 3

Every category NPZ (`scalp_power.npz`, `scalp_connectivity.npz`, etc.) gains a `sex` array:

```
sex: (n_cells,) U10
```

All other arrays are unchanged. `metadata.json` per-category info gains `unique_sexes: ["F", "M", "pooled"]`. Top-level `metadata.json` carries `format_version: 3`.

`read_norms_npz` checks for the `sex` array in each file; when absent (older bundle), defaults all cells to `sex="pooled"`.

### PSD slab schema (`npz/psd_spectrum.npz`)

```
freqs              (n_freqs,)                                  float64
bins               (n_bins,)                                   U20
conditions         (n_conds,)                                  U10
sexes              (3,)                                        U10   # ["pooled", "F", "M"]
channels           (n_channels,)                               U20
mean               (n_bins, n_conds, 3, n_channels, n_freqs)   float32  # log10(µV²/Hz)
sd                 (n_bins, n_conds, 3, n_channels, n_freqs)   float32
n                  (n_bins, n_conds, 3)                        int32
percentile_points  (13,)                                       float64
percentiles        (n_bins, n_conds, 3, n_channels, n_freqs, 13) float32
normality_p        (n_bins, n_conds, 3, n_channels, n_freqs)   float32
psd_format_version scalar                                      int      # 3
```

`metadata.json["categories"]["psd_spectrum"]`:
```json
{
  "file": "psd_spectrum.npz",
  "layout": "slab",
  "n_freqs": 199,
  "n_channels": 37,
  "unique_sexes": ["F", "M", "pooled"],
  "size_bytes": <int>
}
```

The `"layout": "slab"` sentinel lets the consumer's category-dispatch table branch from the default flat parallel-array reader. All other categories carry `"layout": "flat"` (implicit, omitted for back-compat with the v2 reader).

Note: `unique_sexes` in `metadata.json` lists which variants exist in alphabetical order, consistent with how `unique_bands` and `unique_metrics` are emitted today. The slab's actual `sexes` axis array uses a meaningful order — `["pooled", "F", "M"]` — and that order is the canonical axis index. Consumers slicing the slab should index by looking up the position in the in-file `sexes` array, not by assuming alphabetical order.

### `compare_to_norms` and `compare_and_report` signatures

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
) -> list[ComparisonResult]: ...

def compare_and_report(
    metrics: dict,
    norms: list[NormCell],
    age: int | float,
    condition: str,
    config: Optional[dict] = None,
    fdr_alpha: float = 0.05,
    sex: Optional[str] = None,        # NEW
) -> ComparisonReport: ...
```

Lookup semantics:
- `sex is None` → match `cell.sex == "pooled"` only (preserves current behavior for callers that don't opt in)
- `sex in {"F", "M"}` → prefer matching variant; fall back to `"pooled"` per cell when the variant is absent
- `sex` outside `{None, "F", "M"}` → `ValueError`

### `ComparisonResult.resolved_sex`

```python
@dataclass
class ComparisonResult:
    ...                               # existing fields
    resolved_sex: str = "pooled"      # NEW — "F", "M", or "pooled"
```

Reflects which variant the cell came from for this metric.

### `ComparisonReport.metadata.resolved_sex_summary`

```python
metadata["resolved_sex_summary"]: dict[str, int]
# e.g. {"F": 1247, "pooled": 12}  — counts of results by resolved_sex
```

The consumer renders this in pane headers when the caller passed `sex` explicitly.

### `PROVENANCE.md` additions

Two new sections appended to the bundle's `PROVENANCE.md`:

1. **Sex breakdown** — a table of subject counts per `(age_bin × sex × condition)`. Generated automatically at build time and inserted by the release script.
2. **PSD freq-resolved category** — short paragraph: "The v2 bundle is self-sufficient. Per-frequency normative spectra live at `npz/psd_spectrum.npz` (slab layout, see schema). The legacy root-level `norms_psd.npz` is a back-compat shim and will be removed in the next bundle cycle."

## Testing strategy

### New test files

- `tests/test_sex_stratification.py`
  - Synthetic subjects: 6 F, 6 M, 2 Other → `build_normative` produces three cells per `(bin, cond, ch, band, metric)`: `pooled` (n=14), `F` (n=6), `M` (n=6); no `"Other"` cell ships.
  - Pooled cell's mean equals the mean of all 14 subjects (including Other), confirming Other contributes only to pooled.
  - Single-sex dataset: only pooled + that sex ship; the absent sex's cell is genuinely absent (not n=0).

- `tests/test_npz_sex_roundtrip.py`
  - Write `format_version: 3` NPZ with mixed sexes; read back; cells equal originals.
  - Write a legacy `format_version: 2` NPZ (no `sex` array); read back; all cells default to `sex="pooled"`.
  - Metadata `unique_sexes` is correct per category.

- `tests/test_compare_sex.py`
  - Build norms with mixed sex; call `compare_and_report(sex="F")`; verify every result's `resolved_sex == "F"` when F cell exists.
  - Manually drop F cells for some tuples; verify fallback to pooled with `resolved_sex == "pooled"`.
  - `compare_and_report(sex=None)` matches today's pooled-only behavior identically.
  - `ComparisonReport.metadata["resolved_sex_summary"]` counts match the per-result resolutions.
  - Invalid sex (`sex="X"`) raises `ValueError`.

### Extended tests

- `tests/test_psd_percentiles.py`
  - Existing tests parameterize across the new sex axis (slab has sex axis at index 2).
  - New test: single-sex synthetic data → pooled and that-sex slices are identical; absent sex slice contains NaN/zeros and `n[..., absent_idx] == 0`.

### Smoke test before full regeneration

After implementation, run `build_norms.py` against a small synthetic dataset (~20 subjects, balanced F/M) and verify:
- Cell count is roughly tripled compared to current
- `npz/psd_spectrum.npz` exists with sex axis
- `metadata.json["format_version"] == 3`
- CW dev branch can load the bundle and produce a sex-matched report

Only then regenerate LEMON+Dortmund full bundle.

## Migration notes for CW

The consumer (Coherence Workstation) needs four mechanical changes to ride the new bundle:

1. Loader accepts `format_version: 3`; reads `sex` array from every NPZ category.
2. `_load_norms_psd` reads from `npz/psd_spectrum.npz` instead of root `norms_psd.npz`; slices the new sex axis.
3. `compare_and_report` call site passes the patient's sex from the demographics card.
4. Pane headers render `resolved_sex_summary` ("matched against sex F · n F-cells / n pooled fallbacks").

No new infrastructure on the CW side — pure plumbing.

## Backward compatibility

- `format_version: 2` bundles (currently shipping) continue to read with the updated library. The `sex` array is missing → every cell deserializes with `sex="pooled"`. `compare_to_norms(sex=None)` returns identical results to today.
- `format_version: 3` bundles read with the *old* library would silently ignore the `sex` array and double/triple-count cells (because `(bin, cond, ch, band, metric)` keys would have three matches each). That's a hard break — old library callers must upgrade before consuming a v3 bundle. The bundle's `PROVENANCE.md` will document the minimum library version.
- The legacy root `norms_psd.npz` is written for one more bundle cycle so CW can stagger its loader update. Removal happens in the next regeneration.

## Out of scope

- Higher-order stratification (sex × handedness, sex × ethnicity, etc.) — not requested and there's no upstream demographic to support it consistently.
- A `compare_and_report(sex="auto")` mode that infers strategy from subject demographics — caller can pass `None` for pooled or the actual sex string; an "auto" mode would just push the decision elsewhere.
- Refactoring the existing slab vs. flat layout dichotomy in the NPZ bundle — the dichotomy is intentional (one slab category, eight flat categories) and not worth churning.
- Updating CW itself — that's the consumer's worktree.
