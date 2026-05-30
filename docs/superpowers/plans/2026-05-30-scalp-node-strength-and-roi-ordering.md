# Scalp node strength + ROI/BA ordering metadata — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two consumer-facing gaps from issue #28 in the v0.3.0 norms bundle: (a) move per-electrode node-strength cells out of `scalp_power.npz` into their own `scalp_node_strength.npz` category with renamed metric names (`dwpli`/`coh`), and (b) publish the canonical source ROI/BA ordering and labels in `npz/metadata.json` so CW (and any consumer) can construct `_src_conn_{A}_{B}` keys without guessing.

**Architecture:** All changes ride inside `open_normative.io.write_norms_npz`. The category-routing logic gains an explicit metric-name override that takes precedence over the channel-prefix rules and renames the metric at write time. The top-level `meta` dict gains three optional keys (`roi_order`, `roi_labels`, `ba_order`) populated from `open_normative.source` constants. No changes to the build pipeline, `compare.py`, or the format_version (additive within v3).

**Tech Stack:** Python 3.10, numpy, dataclasses, pytest. Shared venv at `/Users/jcroall/git/open-normative-eeg/.venv` (activate before running anything).

**Spec:** `docs/superpowers/specs/2026-05-30-scalp-node-strength-and-roi-ordering-design.md`

**Test command (run from worktree root):**
```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```

Current baseline (as of branch creation): 206 tests passing.

---

## File map

**Modified:**
- `open_normative/source.py` — add `BA_ORDER` module-level constant.
- `open_normative/io.py` — add `_METRIC_CATEGORY_OVERRIDES`; refactor `_categorize_channel(channel) → _categorize_cell(channel, metric) → (category, new_metric)`; rename metrics at write time inside `write_norms_npz`; emit `roi_order`/`roi_labels`/`ba_order` in `metadata.json`.

**Created:**
- `tests/test_npz_node_strength_routing.py` — round-trip + invariants for the new category.
- `tests/test_npz_roi_order_metadata.py` — `metadata.json` keys present iff the corresponding cells exist.

**Extended:**
- `tests/test_npz_sex_roundtrip.py` — assert `unique_metrics` for `scalp_node_strength` is `["coh", "dwpli"]` after the rename.

---

## Cell shape reference (for test fixtures)

`NormCell` constructor takes (in order): `bin, condition, channel, band, metric, n, mean, sd, log_mean, log_sd, log_transformed, normality_p, percentiles` (and defaulted disclosure fields). See `tests/test_npz_sex_roundtrip.py::_make_cell` for the canonical helper pattern — most new tests can copy that and override fields.

---

### Task 1: Add `BA_ORDER` constant to `open_normative/source.py`

**Files:**
- Modify: `open_normative/source.py` (insert after the existing `_BA_TO_DK = _build_ba_to_dk()` line around line 189)
- Test: covered by Task 3's tests (no standalone test for a one-line constant)

This is a one-line addition so subsequent tasks have a stable importable symbol. BA pair keys in the bundle already use this exact alphabetical order (`source.py:1388,1401`), so publishing it in `metadata.json` is documentation/discovery rather than a fix — but exporting the constant lets us reference one source of truth instead of recomputing `sorted(_BA_TO_DK.keys())` in `io.py` and the tests.

- [ ] **Step 1: Verify current state**

```bash
grep -n "_BA_TO_DK = _build_ba_to_dk\|^BA_ORDER" open_normative/source.py
```
Expected: one line for `_BA_TO_DK = _build_ba_to_dk()`, none for `BA_ORDER`.

- [ ] **Step 2: Add the constant**

In `open_normative/source.py`, immediately after the line `_BA_TO_DK = _build_ba_to_dk()` (currently line 189), add:

```python

# Canonical alphabetical ordering of Brodmann area short names — matches the
# order BA pair keys are constructed in the bundle (source.py:1388,1401 use
# sorted(_BA_TO_DK.keys()) and sorted(ba_to_dk_idx.keys()) respectively).
# Published in npz/metadata.json so consumers can discover the BA vocabulary
# without scanning every cell's channel name.
BA_ORDER: list[str] = sorted(_BA_TO_DK.keys())
```

- [ ] **Step 3: Smoke import**

```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python -c "from open_normative.source import BA_ORDER; print(len(BA_ORDER), BA_ORDER[:5])"
```
Expected: prints a length (likely > 30) and the first five entries starting with `BA1`.

- [ ] **Step 4: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 206 passed, 0 failures.

- [ ] **Step 5: Commit**

```bash
git add open_normative/source.py
git commit -m "feat(source): export BA_ORDER as the canonical BA short-name ordering

Same value the bundle uses today when constructing _src_ba_conn_* pair keys
(sorted(_BA_TO_DK.keys())) — promoting it to a module-level constant lets
io.py and tests reference one source of truth.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Route `*_node_strength` cells to `scalp_node_strength.npz` with metric rename

**Files:**
- Modify: `open_normative/io.py` (lines 130–185 for the routing helper; lines 181–185 + 269–277 inside `write_norms_npz`)
- Create: `tests/test_npz_node_strength_routing.py`
- Modify: `tests/test_npz_sex_roundtrip.py` (one new assertion)

- [ ] **Step 1: Write failing tests**

Create `tests/test_npz_node_strength_routing.py`:

```python
"""Per-electrode node-strength cells route to scalp_node_strength.npz with
the metric renamed from dwpli_node_strength/coh_node_strength to dwpli/coh."""

import json
from pathlib import Path

from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import NormCell


def _cell(channel: str, metric: str, **overrides) -> NormCell:
    base = dict(
        bin="20-29", condition="ec", channel=channel,
        band="Alpha", metric=metric,
        n=10, mean=1.0, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={}, sex="pooled",
    )
    base.update(overrides)
    return NormCell(**base)


def test_node_strength_cells_land_in_scalp_node_strength_category(tmp_path: Path):
    cells = [
        _cell("Fz", "absolute_power"),
        _cell("Fz", "dwpli_node_strength"),
        _cell("Fz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    files = sorted(p.name for p in (tmp_path / "npz").glob("*.npz"))
    assert "scalp_node_strength.npz" in files
    assert "scalp_power.npz" in files


def test_node_strength_metric_renamed_to_dwpli_or_coh(tmp_path: Path):
    cells = [
        _cell("Fz", "dwpli_node_strength", mean=2.0),
        _cell("Cz", "coh_node_strength", mean=3.0),
    ]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    by_channel = {c.channel: c for c in loaded}
    # Metric is renamed; mean value round-trips so we know the right row is
    # tagged with the right channel.
    assert by_channel["Fz"].metric == "dwpli"
    assert by_channel["Fz"].mean == 2.0
    assert by_channel["Cz"].metric == "coh"
    assert by_channel["Cz"].mean == 3.0


def test_scalp_power_no_longer_contains_node_strength_rows(tmp_path: Path):
    cells = [
        _cell("Fz", "absolute_power"),
        _cell("Fz", "dwpli_node_strength"),
        _cell("Fz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    metrics_in_scalp_power = {
        c.metric for c in loaded
        if c.channel == "Fz" and c.metric in {"absolute_power", "dwpli", "coh", "dwpli_node_strength", "coh_node_strength"}
    }
    # absolute_power stays; renamed metrics live under the new category.
    assert "absolute_power" in metrics_in_scalp_power
    # No row anywhere still carries the old long form.
    assert "dwpli_node_strength" not in metrics_in_scalp_power
    assert "coh_node_strength" not in metrics_in_scalp_power


def test_metadata_unique_metrics_for_node_strength_is_clean(tmp_path: Path):
    cells = [
        _cell("Fz", "dwpli_node_strength"),
        _cell("Cz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    cat = meta["categories"]["scalp_node_strength"]
    assert sorted(cat["unique_metrics"]) == ["coh", "dwpli"]
```

- [ ] **Step 2: Run tests to verify failure**

```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python -m pytest tests/test_npz_node_strength_routing.py -v
```
Expected: all four tests FAIL — `scalp_node_strength.npz` does not exist; cells with `dwpli_node_strength` land in `scalp_power.npz` with the original metric name.

- [ ] **Step 3: Add `_METRIC_CATEGORY_OVERRIDES` and refactor the helper**

In `open_normative/io.py`, replace the block from `_CATEGORY_RULES = [` through the end of `_categorize_channel` (currently lines 130–147) with:

```python
# Channel prefix → category mapping
_CATEGORY_RULES = [
    ("_pair_", "scalp_connectivity"),
    ("_src_ba_conn_", "source_ba_connectivity"),
    ("_src_dk_", "source_dk"),          # both dk power and dk connectivity
    ("_src_conn_", "source_roi_connectivity"),
    ("_src_net_", "source_network"),
    ("_src_ba_", "source_ba_power"),     # after _src_ba_conn_ check
    ("_graph", "graph_metrics"),
]

# Metric-name overrides that take precedence over the channel-prefix rules.
# Maps the cell's `metric` to (target_category, renamed_metric) — the cell
# is routed to target_category with metric replaced by renamed_metric at
# write time. The category name conveys "node strength" so the metric drops
# its `_node_strength` suffix, matching scalp_connectivity.npz convention
# where the metric is just "dwpli"/"coh".
_METRIC_CATEGORY_OVERRIDES: dict[str, tuple[str, str]] = {
    "dwpli_node_strength": ("scalp_node_strength", "dwpli"),
    "coh_node_strength":   ("scalp_node_strength", "coh"),
}


def _categorize_cell(channel: str, metric: str) -> tuple[str, str]:
    """Map a (channel, metric) pair to (category, stored_metric).

    Metric-name overrides win first (e.g. node-strength routes to its own
    category with a renamed metric). Otherwise fall through to the channel-
    prefix rules and keep the original metric.
    """
    override = _METRIC_CATEGORY_OVERRIDES.get(metric)
    if override is not None:
        return override
    for prefix, category in _CATEGORY_RULES:
        if channel.startswith(prefix):
            return category, metric
    return "scalp_power", metric
```

(Delete the old `_categorize_channel` function — it's replaced.)

- [ ] **Step 4: Update `write_norms_npz` to use the new helper and apply the rename**

In `open_normative/io.py:write_norms_npz`, replace the grouping block (currently lines 181–185, around the `for cell in cells:` loop) with:

```python
    # Group cells by category. Routing may rename a cell's metric (e.g.
    # node-strength → scalp_node_strength.npz with metric "dwpli"/"coh"), so
    # we substitute the renamed copy via dataclasses.replace before grouping.
    by_category: dict[str, list[NormCell]] = defaultdict(list)
    for cell in cells:
        category, stored_metric = _categorize_cell(cell.channel, cell.metric)
        if stored_metric != cell.metric:
            cell = dataclasses.replace(cell, metric=stored_metric)
        by_category[category].append(cell)
```

(The `dataclasses` module is already imported at the top of `io.py`.)

- [ ] **Step 5: Extend test_npz_sex_roundtrip with a unique_metrics assertion**

Append to `tests/test_npz_sex_roundtrip.py`:

```python
def test_scalp_node_strength_unique_metrics_in_metadata(tmp_path: Path):
    """When node-strength cells are written, their unique_metrics is the
    short form (dwpli/coh) — confirms the rename made it through to the
    category manifest."""
    cells = [
        NormCell(
            bin="20-29", condition="ec", channel="Fz",
            band="Alpha", metric="dwpli_node_strength",
            n=10, mean=1.0, sd=0.5,
            log_mean=None, log_sd=None, log_transformed=False,
            normality_p=None, percentiles={}, sex="pooled",
        ),
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["categories"]["scalp_node_strength"]["unique_metrics"] == ["dwpli"]
```

(`NormCell`, `json`, `Path`, and `write_norms_npz` are already imported at the top of `test_npz_sex_roundtrip.py`.)

- [ ] **Step 6: Run tests to verify pass**

```bash
python -m pytest tests/test_npz_node_strength_routing.py tests/test_npz_sex_roundtrip.py -v
```
Expected: all 4 new routing tests PASS, plus all existing `test_npz_sex_roundtrip.py` tests PASS plus the 1 new assertion.

- [ ] **Step 7: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 211 passed (206 prior + 4 new routing + 1 new sex-roundtrip extension), 0 failures.

- [ ] **Step 8: Commit**

```bash
git add open_normative/io.py tests/test_npz_node_strength_routing.py tests/test_npz_sex_roundtrip.py
git commit -m "feat(io): route node-strength cells to scalp_node_strength.npz with metric rename

The pipeline already produces per-electrode node strength cells with metric
dwpli_node_strength / coh_node_strength, but the NPZ writer routed them by
channel prefix only — they fell through to scalp_power.npz. CW expects them
at npz/scalp_node_strength.npz with metric dwpli/coh (no _node_strength
suffix, matching scalp_connectivity.npz convention).

Add _METRIC_CATEGORY_OVERRIDES dict and refactor _categorize_channel to
_categorize_cell(channel, metric) → (category, stored_metric). Override
maps {dwpli,coh}_node_strength to (scalp_node_strength, {dwpli,coh}); the
rename happens at write time via dataclasses.replace before grouping. No
new computation; same cells, different file with a tidier metric name.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Emit `roi_order` / `roi_labels` / `ba_order` in `metadata.json`

**Files:**
- Modify: `open_normative/io.py:write_norms_npz` (the `meta` dict construction at lines 279–288)
- Create: `tests/test_npz_roi_order_metadata.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_npz_roi_order_metadata.py`:

```python
"""metadata.json includes canonical roi_order / roi_labels / ba_order when
the bundle contains source connectivity cells; the keys are absent when
those categories are empty."""

import json
from pathlib import Path

from open_normative.io import write_norms_npz
from open_normative.normative import NormCell
from open_normative.source import BA_ORDER, ROI_DEFINITIONS, ROI_NAMES


def _cell(channel: str, **overrides) -> NormCell:
    base = dict(
        bin="20-29", condition="ec", channel=channel,
        band="Alpha", metric="source_dwpli",
        n=10, mean=1.0, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={}, sex="pooled",
    )
    base.update(overrides)
    return NormCell(**base)


def test_roi_order_present_when_src_conn_cells_exist(tmp_path: Path):
    cells = [
        _cell("_src_conn_DLPFC_L_ACC"),
        _cell("Fz", metric="absolute_power"),  # unrelated, must not affect roi_order
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["roi_order"] == ROI_NAMES


def test_roi_labels_present_and_match_definitions(tmp_path: Path):
    cells = [_cell("_src_conn_DLPFC_L_ACC")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_labels" in meta
    # Sample a few — full map must equal the ROI_DEFINITIONS labels.
    expected = {k: v["label"] for k, v in ROI_DEFINITIONS.items()}
    assert meta["roi_labels"] == expected


def test_ba_order_present_when_src_ba_conn_cells_exist(tmp_path: Path):
    cells = [_cell("_src_ba_conn_BA1-lh_BA4-lh", metric="source_dwpli")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["ba_order"] == BA_ORDER


def test_roi_and_ba_keys_absent_when_no_source_cells(tmp_path: Path):
    """A scalp-only bundle must not emit ROI/BA ordering metadata."""
    cells = [
        _cell("Fz", metric="absolute_power"),
        _cell("Cz", metric="dwpli_node_strength"),  # routed to scalp_node_strength
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_order" not in meta
    assert "roi_labels" not in meta
    assert "ba_order" not in meta


def test_src_conn_cells_only_emit_roi_keys_not_ba(tmp_path: Path):
    """Bundle with ROI cells but no BA cells gets roi_order/roi_labels but
    not ba_order."""
    cells = [_cell("_src_conn_DLPFC_L_ACC")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_order" in meta
    assert "roi_labels" in meta
    assert "ba_order" not in meta
```

- [ ] **Step 2: Run tests to verify failure**

```bash
source /Users/jcroall/git/open-normative-eeg/.venv/bin/activate
python -m pytest tests/test_npz_roi_order_metadata.py -v
```
Expected: all five tests FAIL — `roi_order` / `roi_labels` / `ba_order` keys are not in `metadata.json`.

- [ ] **Step 3: Augment the `meta` dict in `write_norms_npz`**

In `open_normative/io.py:write_norms_npz`, replace the `meta = { ... }` construction (currently lines 280–286) with:

```python
    # Write metadata index. ROI/BA ordering keys are only emitted when the
    # corresponding source-connectivity categories are present, so consumers
    # can detect "this bundle has source data, here's how to walk its pair
    # keys" without scanning every channel name.
    has_roi_conn = any(
        c.channel.startswith("_src_conn_") for c in cells
    )
    has_ba_conn = any(
        c.channel.startswith("_src_ba_conn_") for c in cells
    )

    meta = {
        "format_version": 3,
        "total_cells": len(cells),
        "categories": file_manifest,
        "age_bins": sorted(set(c.bin for c in cells)),
        "conditions": sorted(set(c.condition for c in cells)),
    }
    if has_roi_conn:
        # Lazy import: open_normative.source is heavy (MNE / forward model
        # loaders). io.py is imported by code paths that don't need it.
        from open_normative.source import ROI_DEFINITIONS, ROI_NAMES
        meta["roi_order"] = list(ROI_NAMES)
        meta["roi_labels"] = {k: v["label"] for k, v in ROI_DEFINITIONS.items()}
    if has_ba_conn:
        from open_normative.source import BA_ORDER
        meta["ba_order"] = list(BA_ORDER)
```

The two `any(...)` scans walk the cells list once each (O(n)); fine at write time. The lazy import avoids forcing `open_normative.source` (and its MNE dependencies) on consumers of `open_normative.io` that don't write source-aware bundles.

- [ ] **Step 4: Run tests to verify pass**

```bash
python -m pytest tests/test_npz_roi_order_metadata.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Full baseline still green**

```bash
python -m pytest tests/ --ignore=tests/test_pipeline.py --ignore=tests/test_preprocessing.py -q
```
Expected: 216 passed (211 from Task 2 + 5 new), 0 failures.

- [ ] **Step 6: Commit**

```bash
git add open_normative/io.py tests/test_npz_roi_order_metadata.py
git commit -m "feat(io): publish canonical roi_order / roi_labels / ba_order in metadata.json

Bundle builds _src_conn_{A}_{B} pair keys with A precedes B in
ROI_DEFINITIONS insertion order (DLPFC_L, DLPFC_R, mPFC, ACC, ...) — not
alphabetical. CW's lookup uses sorted([a, b]) and silently misses pairs
where the canonical order disagrees (e.g. _src_conn_DLPFC_L_ACC in the
bundle vs _src_conn_ACC_DLPFC_L in CW).

Publish the canonical ordering — and the human-readable labels — in
npz/metadata.json so consumers can construct keys correctly without
guessing. ba_order is also emitted (alphabetical, matching the bundle's
existing BA pair construction) for documentation / discovery.

Keys are only emitted when corresponding cells exist (no roi_order on
a scalp-only bundle, no ba_order without _src_ba_conn_* cells), so
metadata.json stays tight.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Update CHANGELOG entry for the v3 bundle additions

**Files:**
- Modify: `CHANGELOG.md` (the `[Unreleased]` section if it has been reopened post-v0.3.0; otherwise add a new `[Unreleased]` block and let the next release.sh run move it).

This is doc-only and falls under the same v3 bundle additions. Catching it in CHANGELOG saves a sticky-note for the release moment.

- [ ] **Step 1: Inspect current CHANGELOG state**

```bash
head -25 CHANGELOG.md
```
Expected: there is either an empty `## [Unreleased]` block (if release.sh has not yet rolled to v0.3.0) or a populated `## [0.3.0] - 2026-05-29` block with v3 contents. (If the v0.3.0 release was cut, the next release that ships this enhancement will be v0.3.1 or v0.4.0 — `scripts/release.sh` will move whatever lands under `[Unreleased]` to a new dated header at tag time.)

- [ ] **Step 2: Add entries under `[Unreleased]`**

In `CHANGELOG.md`, immediately under the `## [Unreleased]` header, add:

```markdown
### Added
- New `npz/scalp_node_strength.npz` category. Per-electrode node-strength
  cells (formerly mixed into `scalp_power.npz` under metric names
  `dwpli_node_strength` / `coh_node_strength`) now live in their own file
  with metric names `dwpli` / `coh`, matching `scalp_connectivity.npz`
  convention.
- `npz/metadata.json` publishes `roi_order` and `roi_labels` when source
  ROI connectivity cells are present, and `ba_order` when BA connectivity
  cells are present. Consumers should construct `_src_conn_{A}_{B}` keys
  with A preceding B in `roi_order` rather than calling `sorted()`.

### Changed
- `scalp_power.npz` no longer contains node-strength rows (moved to
  `scalp_node_strength.npz`). Consumers reading `dwpli_node_strength` /
  `coh_node_strength` from `scalp_power.npz` will see no such metric;
  switch the lookup to `scalp_node_strength.npz` with metric `dwpli` /
  `coh`.
```

(If a `[Unreleased]` block does not exist yet — meaning v0.3.0 was already cut and the section was rolled — add one at the top above the most recent dated header.)

- [ ] **Step 3: No automated test**

CHANGELOG is documentation; verify by reading the rendered diff.

```bash
git diff CHANGELOG.md
```
Expected: the new entries appear under `[Unreleased]` and the document otherwise is unchanged.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note scalp_node_strength category + ROI/BA ordering metadata

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## What's deliberately NOT in this plan

- **No changes to `build_norms.py`** — node strength is already produced upstream; nothing to compute differently.
- **No changes to `compare.py`** — z-scoring against `dwpli_node_strength`/`coh_node_strength` keeps working because `compare_to_norms` looks up `(channel, band, metric)` against the loaded NormCells, and the loaded cells now carry the renamed metric. Patient metrics dicts from CW use the new short metric names per the migration notes in the spec.
- **No format_version bump** — additive within v3.
- **No CW-side code changes** — those land in the consumer repo per the spec's "Migration notes for CW" section.
- **No `_src_roi_*` category** for per-ROI source-level node strength — out of scope (separate enhancement; see Finding 4 in the spec).
- **No PROVENANCE.md generator update** — the existing generator emits the cohort sex breakdown and PSD spectrum note; the new bundle additions are visible from `npz/metadata.json` itself. A one-line addition to `PROVENANCE.md` can ride in a future docs PR.
