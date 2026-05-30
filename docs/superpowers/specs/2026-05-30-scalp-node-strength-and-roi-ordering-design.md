# Scalp node strength category + source ROI/BA ordering metadata — design spec

**Date:** 2026-05-30
**Source issue:** [#28](https://github.com/peak-mind-llc/open-normative-eeg/issues/28) — "Connectivity norms for CW Network Normative: add scalp_node_strength category + align source ROI pair keys"
**Reporter:** Coherence Workstation team (James Croall)
**Bundle target:** Lands in the same v0.3.0 regen as the sex-stratification work; no second regen needed.

## Problem

Two gaps block CW's Network Normative phase from consuming the bundle without workarounds:

**Gap 1 — `scalp_node_strength` cells exist but in the wrong file.** The build pipeline already computes per-electrode node strength per `(band, method)` and writes cells with `metric ∈ {"dwpli_node_strength", "coh_node_strength"}` to the NormCell list. The NPZ writer routes by channel prefix; `"Fz"` has no prefix, so these cells fall through to `scalp_power.npz`. CW's `extract_metrics §6a/§6b` looks specifically for the file `npz/scalp_node_strength.npz` and reports zero per-electrode node-strength norm cells.

**Gap 2 — Source ROI pair keys use a non-alphabetical canonical order that the consumer doesn't know about.** `open_normative.source.ROI_NAMES` is an `OrderedDict` of `["DLPFC_L", "DLPFC_R", "mPFC", "ACC", "INS_L", "INS_R", ...]`. Cell keys are constructed as `_src_conn_{ROI_NAMES[i]}_{ROI_NAMES[j]}` with `i < j` in that insertion order — so the bundle has `_src_conn_DLPFC_L_ACC`. CW (`plugins/ins/normative/service.py:734`) does `a, b = sorted([roi_a, roi_b])` and looks up `_src_conn_ACC_DLPFC_L`. The cell is in the bundle; CW just can't find it.

Both gaps must close in the v0.3.0 regen so CW's Network Normative phase ships with real per-node z-scores and source-pair coverage in the same release that introduces sex stratification.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Metric naming inside `scalp_node_strength.npz` | Short form (`dwpli`, `coh`) | Matches `scalp_connectivity.npz` convention where the category name implies the kind. Rename happens at write time: strip the `_node_strength` suffix when routing into the new category. |
| Routing mechanism | Explicit metric→category override dict (`_METRIC_CATEGORY_OVERRIDES`) | Two lines, self-documents, no risk of accidentally catching future `_node_strength`-suffixed metrics we haven't designed for. |
| Duplication for back-compat | None — move cells entirely | v3 is already a hard break for old consumers; duplication creates schema-drift risk for negligible benefit. |
| ROI vocabulary translation | None needed | Cross-checked against `plugins/ins/normative/service.py:734-740` — vocabulary matches (`DLPFC_L`, `ACC`, ..., `source_dwpli`/`source_coh`/`source_imcoh`); only the ordering diverges. |
| ROI/BA order discovery | Publish in `npz/metadata.json` as `roi_order` / `ba_order` lists | Single source of truth; consumers stop calling `sorted()` and construct keys in the published order. |
| Human-readable ROI labels | Publish in `npz/metadata.json` as `roi_labels` map | Zero cost (read from existing `ROI_DEFINITIONS[k]["label"]`); helps UI labelling. |
| Bundle format_version | No further bump — stays at v3 (the sex-stratification bump) | New category and new metadata keys are additive within v3; consumers reading older v3 bundles see no `scalp_node_strength` category and no `roi_order` key, both of which are documented as optional. |

## Cross-check findings (CW source)

Verified against `~/git/coherence-workstation/plugins/ins/normative/service.py` (issue-cited file):

| Aspect | Bundle today | CW today | Status |
|---|---|---|---|
| ROI pair key construction | `_src_conn_{ROI_NAMES[i]}_{ROI_NAMES[j]}`, i<j in insertion order | `_src_conn_{sorted([a,b])[0]}_{sorted([a,b])[1]}`, alphabetical | **Mismatch** — fixed by publishing `roi_order` (this spec) |
| ROI label vocabulary | `DLPFC_L`, `DLPFC_R`, `mPFC`, `ACC`, ... from `ROI_DEFINITIONS` | Reads `roi_names` from upstream `source_connectivity` stage (`service.py:716`); issue lists same names | **Match** (high confidence; not in scope to verify the CW upstream emitter) |
| Source connectivity metric names | `source_dwpli`, `source_coh`, `source_imcoh` | `source_dwpli`, `source_coh`, `source_imcoh` | **Match** |
| Per-electrode node strength location | `scalp_power.npz` (default fallthrough) | Reads `scalp_node_strength.npz`; reports zero cells | **Mismatch** — fixed by routing into new category (this spec) |
| Per-ROI source-level node strength | Not shipped; bundle has `_src_conn_{ROI}` only for `corrected_dics_power` | Expects `_src_roi_{ROI}` with `source_{method}` metric (`service.py:744-754`); currently derives node strength from the matrix itself | **Mismatch, OUT OF SCOPE** — file as a separate enhancement |

## Architecture

### Files touched

| File | Change |
|---|---|
| `open_normative/io.py` | Add `_METRIC_CATEGORY_OVERRIDES` dict. Rename `_categorize_channel(channel) → _categorize_cell(channel, metric)`; check the override first, then the existing channel-prefix rules. In `write_norms_npz`, when routing into `scalp_node_strength`, strip the `_node_strength` suffix from the cell's metric so the stored metric is `"dwpli"` / `"coh"`. Augment the top-level `meta` dict with `roi_order`, `roi_labels`, `ba_order` keys when the corresponding source categories are present. |
| `open_normative/source.py` | Add module-level `BA_ORDER = sorted(_BA_TO_DK.keys())` (e.g. `["BA1", "BA10", "BA11", ..., "BA9"]`) so the order is importable. BA pairs in the bundle are already alphabetical (`source.py:1388,1401`), so publishing `ba_order` is documentation/discovery — consumers using `sorted()` already land on the right pair key. No `BA_LABELS` map; the BA short name IS the canonical string (`"BA1"`, etc.) — no human-readable form to publish. |
| `tests/test_npz_node_strength_routing.py` (new) | Round-trip: create cells with `metric="dwpli_node_strength"`/`"coh_node_strength"`, verify they land in `scalp_node_strength.npz` with `metric="dwpli"`/`"coh"`, and that no such metrics remain in `scalp_power.npz`. |
| `tests/test_npz_roi_order_metadata.py` (new) | Build a tiny norms list including `_src_conn_*` and `_src_ba_conn_*` cells. Verify `metadata.json` includes `roi_order`, `roi_labels`, `ba_order` with the expected lists; verify that when no such cells exist, the keys are absent. |
| `tests/test_npz_sex_roundtrip.py` (extend) | Add an assertion that the per-category `unique_metrics` listed in `metadata.json` for `scalp_node_strength` is `["coh", "dwpli"]` after the rename. |

### Data flow

```
Today (v2/v3-without-this-spec):
  pipeline → subject metrics dict
    "Fz": {"Alpha": {"absolute_power": ..., "dwpli_node_strength": ...}}
        │
  build_normative
        │
  list[NormCell]:
    NormCell(channel="Fz", band="Alpha", metric="dwpli_node_strength", ...)
        │
  write_norms_npz
    _categorize_channel("Fz") → "scalp_power"          ← cell lands HERE today
        │
  npz/scalp_power.npz contains both absolute_power AND dwpli_node_strength rows.


This spec:
  (pipeline, build_normative unchanged)
        │
  write_norms_npz
    _categorize_cell("Fz", "dwpli_node_strength")
      → metric in _METRIC_CATEGORY_OVERRIDES → "scalp_node_strength"
    write row with metric renamed "dwpli_node_strength" → "dwpli"
        │
  npz/scalp_node_strength.npz contains:
    (bin, sex, condition, channel="Fz", band="Alpha", metric="dwpli", n, mean, sd, ...)
  npz/scalp_power.npz now contains ONLY power metrics.
  npz/metadata.json["categories"]["scalp_node_strength"] auto-listed.
  npz/metadata.json gains:
    roi_order:  [...]
    roi_labels: {...}
    ba_order:   [...]   (when applicable)
```

## Specifications

### `_METRIC_CATEGORY_OVERRIDES` (open_normative/io.py)

```python
# Metrics that route to a non-default category regardless of channel prefix.
# Checked BEFORE the channel-prefix rules in _CATEGORY_RULES.
# When a cell routes here, the metric is renamed at write time per the value's
# (category, new_metric) tuple — the category name already implies "node strength".
_METRIC_CATEGORY_OVERRIDES: dict[str, tuple[str, str]] = {
    "dwpli_node_strength": ("scalp_node_strength", "dwpli"),
    "coh_node_strength":   ("scalp_node_strength", "coh"),
}
```

### `_categorize_cell(channel, metric)`

Replaces today's `_categorize_channel(channel)`:

1. If `metric in _METRIC_CATEGORY_OVERRIDES`, return `(category, new_metric)` from the dict.
2. Else, walk `_CATEGORY_RULES` by channel prefix; on match return `(category, metric)` (no rename).
3. Else return `("scalp_power", metric)`.

Returning `(category, metric)` instead of just `category` is the minimal-blast-radius way to thread the rename through `write_norms_npz`.

### `npz/metadata.json` additions

Three new top-level keys, all optional (omitted when no relevant cells exist):

```jsonc
{
  "format_version": 3,                       // unchanged
  "total_cells": <int>,                      // unchanged
  "categories": { ... },                     // unchanged; auto-includes scalp_node_strength
  "age_bins": [ ... ],                       // unchanged
  "conditions": [ ... ],                     // unchanged

  // NEW — present when any _src_conn_* cells exist
  "roi_order": ["DLPFC_L", "DLPFC_R", "mPFC", "ACC", "INS_L", "INS_R", ...],
  "roi_labels": {
    "DLPFC_L": "Left DLPFC",
    "DLPFC_R": "Right DLPFC",
    "mPFC":    "Medial PFC",
    "ACC":     "Anterior Cingulate",
    "INS_L":   "Left Insula",
    "INS_R":   "Right Insula",
    ...
  },

  // NEW — present when any _src_ba_conn_* cells exist.
  // Alphabetical. BA pair keys (per hemisphere) already use this order in the
  // bundle, so consumers can sorted() and still land on the right key; this
  // entry is documentation / discovery rather than a fix.
  "ba_order": ["BA1", "BA10", "BA11", ..., "BA9"]
}
```

`roi_order` is the canonical order for pair-key construction: for any two ROI keys A and B, the pair cell is keyed `_src_conn_{A}_{B}` where A precedes B in `roi_order`. Consumers replace `sorted([a, b])` with a lookup against this list.

`roi_labels` is documentation-only; no consumer is required to read it.

### Schema invariant

After this change:
- `scalp_power.npz` contains zero rows with metric ending in `_node_strength`.
- `scalp_node_strength.npz` contains zero rows where `metric` is anything other than `"dwpli"` or `"coh"`.
- For every `_src_conn_{A}_{B}` cell in the bundle, both A and B appear in `roi_order`, and A's index in `roi_order` is strictly less than B's.

These are checked in the new tests.

## Testing strategy

### New test files

- **`tests/test_npz_node_strength_routing.py`**
  - Construct mixed cells: `absolute_power`, `dwpli_node_strength`, `coh_node_strength`, all on channel `"Fz"`.
  - `write_norms_npz` → `read_norms_npz`.
  - Assert: `scalp_node_strength.npz` has the two node-strength rows with `metric="dwpli"`/`"coh"` (renamed).
  - Assert: `scalp_power.npz` has the `absolute_power` row, and no row with `metric` ending in `_node_strength`.
  - Assert: round-tripped NormCells preserve the renamed metric (consumer sees the new names).

- **`tests/test_npz_roi_order_metadata.py`**
  - Build a small norms list including `_src_conn_DLPFC_L_ACC`, `_src_ba_conn_BA1_BA4-lh`, and `_src_dk_*` cells.
  - `write_norms_npz`.
  - Assert: `metadata.json` includes `roi_order == open_normative.source.ROI_NAMES`.
  - Assert: `metadata.json["roi_labels"]["DLPFC_L"] == "Left DLPFC"`.
  - Assert: `metadata.json["ba_order"]` is present and matches `open_normative.source.BA_ORDER` (alphabetical, so e.g. `["BA1", "BA10", "BA11", ..., "BA9"]`).
  - Assert: for every `_src_conn_*` cell, the embedded ROIs appear in `roi_order` and the first index < second index.
  - Build a second norms list with NO source cells; assert `roi_order` / `roi_labels` / `ba_order` are absent from `metadata.json`.

### Extension

- **`tests/test_npz_sex_roundtrip.py`** — when `scalp_node_strength` is one of the written categories, its per-category `metadata.json["categories"]["scalp_node_strength"]["unique_metrics"]` is `["coh", "dwpli"]` (sorted, no `_node_strength` suffix).

### Smoke check before regen

After implementation, run the existing end-to-end synthetic smoke test (`tests/test_end_to_end_smoke.py`) extended to include connectivity metrics, and verify the new category appears with the expected metric names. Only then trigger the production regen.

## Migration notes for CW

CW needs three small consumer-side changes to pick up these gains:

1. **`_load_norms_npz`** — add `scalp_node_strength` to the category-file list. Read with `metric="dwpli"`/`"coh"` (not `"dwpli_node_strength"` etc.). The §6a/§6b branches in `extract_metrics` map cleanly: they were looking up `dwpli_node_strength`/`coh_node_strength` against `scalp_power.npz`; switch to looking up `dwpli`/`coh` against `scalp_node_strength.npz`.

2. **Source ROI pair lookup** — replace `a, b = sorted([roi_a, roi_b])` at `service.py:734` with a lookup against `metadata.json["roi_order"]`. Pseudocode:
   ```python
   roi_order = metadata.get("roi_order", [])
   def ordered_pair(a, b):
       if not roi_order:
           return tuple(sorted([a, b]))  # fallback for legacy bundles
       ia, ib = roi_order.index(a), roi_order.index(b)
       return (a, b) if ia < ib else (b, a)
   ```
   Same fix for `_src_ba_conn_*` pairs using `ba_order`.

3. **No vocabulary mapping required.** Names match between sides.

## Backward compatibility

- **Old library + new bundle.** Old `read_norms_npz` doesn't know about the new `scalp_node_strength` category, but `metadata.json["categories"]` is iterated dynamically — the file will simply be read and its cells loaded with `metric="dwpli"`/`"coh"`. Old callers that explicitly look for `metric="dwpli_node_strength"` on `scalp_power.npz` will miss them (broken — same hard break as the v3 sex axis).

- **New library + old bundle.** Old bundles have no `scalp_node_strength.npz` and no `roi_order` / `roi_labels` / `ba_order` in `metadata.json`. The new library handles both gracefully: absent category is just not loaded; consumers fall back to alphabetical sort with a log warning.

- **`PROVENANCE.md`** — gains a one-line note under the v3 schema section: "Per-electrode node-strength cells live at `npz/scalp_node_strength.npz` (metrics `dwpli`/`coh`). Source ROI/BA pair-key canonical order is published as `roi_order` / `ba_order` in `npz/metadata.json`."

## Out of scope

- **Per-ROI source-level node strength** (`_src_roi_*` cells expected by CW `service.py:744-754`). CW currently derives these from the matrix at consumption time. If we want them precomputed, file a follow-up enhancement.
- **Recomputing node strength** — the pipeline already emits it. No work in `build_norms.py` or `connectivity.py`.
- **Vocabulary translation tables** — vocab matches; not needed.
- **Bumping bundle format_version beyond 3** — new category and new metadata keys are additive within v3.
- **CW-side code changes** — see "Migration notes for CW" above; those land in the consumer repo.
