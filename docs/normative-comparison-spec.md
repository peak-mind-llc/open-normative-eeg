# Normative Comparison View — Design Spec

## Overview

A dedicated view in Coherence Workstation (CW) that compares an individual subject's resting-state EEG against age-matched normative distributions. Shows the same metrics already displayed elsewhere in CW (absolute power, relative power, ratios, connectivity) but z-scored against the normative database.

The emphasis is **structural**: this is its own screen, not embedded in existing power or network views.

## Requirements

### Minimum Input
- **Birthday** — converted to age in years, mapped to normative age bin
- **Sex** (M/F) — stored for future sex-stratified norms; currently used combined
- **19-channel resting EEG** — standard 10-20 montage (Fp1, Fp2, F7, F3, Fz, F4, F8, T3, C3, Cz, C4, T4, T5, P3, Pz, P4, T6, O1, O2)
- **Condition** — EO and/or EC (compared against same-condition norms)

### Normative Database
- Loaded from `norms.json` (output of `build_norms.py`)
- Each NormCell: bin, condition, channel, band, metric, n, mean, sd, log_mean, log_sd, percentiles
- Right-skewed metrics (absolute_power, corrected_absolute_power, ratios) use log-space z-scores
- Symmetric metrics (relative_power) use raw z-scores

### Edge Cases
- Age outside all bins → show warning: "Subject age (X) is outside the normative range (Y–Z). Comparison may not be valid."
- Age bin with n < 10 → show warning: "Low reference sample (n=X) for this age bin. Interpret with caution."
- Missing channel → skip that channel, show as grey/hatched on topomaps

---

## View Layout

### Header Bar
```
Normative Comparison    [EO ▼] [EC]     Age: 34 (bin: 30-39)    Sex: M    Reference: n=47
```
- Condition toggle (EO/EC) — switches all panels
- Age and bin displayed prominently
- Reference n shown (from the normative cells)

### Section 1: Spectral Overlay (the differentiator)

**19-channel small multiples arranged in head-map layout:**
```
          Fp1    Fp2
     F7   F3  Fz  F4   F8
     T3   C3  Cz  C4   T4
     T5   P3  Pz  P4   T6
          O1        O2
```

Each panel shows:
- **X-axis:** Frequency (1–50 Hz, log or linear scale toggle)
- **Y-axis:** Power spectral density (log10 µV²/Hz)
- **Subject PSD:** Solid colored line
- **Normative mean:** Dashed black line
- **±1 SD band:** Medium shading (e.g., light blue)
- **±2 SD band:** Light shading (e.g., lighter blue)
- **Band boundaries:** Subtle vertical lines at delta|theta|alpha|beta|highbeta|gamma edges
- **Click to enlarge:** Clicking a panel opens a full-size view with axis labels, percentile bands (5th/25th/75th/95th), and the option to overlay the aperiodic fit

**Why this matters:** A z-score of -2.1 for alpha at Pz tells you *how much*, but the spectral overlay tells you *why*. Is it a reduced alpha peak? A shifted peak frequency? A steep aperiodic slope suppressing the alpha band? The spectral curve reveals the mechanism.

**Enlarged single-channel view (on click) also shows:**
- Aperiodic (1/f) fit line (from specparam) — subject vs normative
- Periodic-only component (full PSD minus aperiodic) — subject vs normative
- This reveals whether deviations are oscillatory or aperiodic in nature

### Section 2: Z-Score Topographic Maps

**Grid layout — rows = metrics, columns = bands:**

```
                 Delta  Theta  Alpha  Beta  HighBeta  Gamma
Absolute Power    [topo] [topo] [topo] [topo] [topo]  [topo]
Relative Power    [topo] [topo] [topo] [topo] [topo]  [topo]
Corrected Power   [topo] [topo] [topo] [topo] [topo]  [topo]
```

Each topomap:
- 19-channel interpolated head map
- Color scale: blue (-3) → white (0) → red (+3) — diverging colormap
- Z-score value labeled on each electrode position
- Significance markers: |z| > 2.0 gets a bold outline or asterisk

**Additional row for ratios (no topomaps — bar charts or single-row heatmaps):**
```
Theta/Beta         [19-channel bar chart, z-scored]
Delta/HighBeta     [19-channel bar chart, z-scored]
Alpha/HighBeta     [19-channel bar chart, z-scored]
Theta/Beta1        [19-channel bar chart, z-scored]
```

Same ratios shown elsewhere in CW, just z-scored.

### Section 3: Connectivity Comparison (three-panel)

Three side-by-side head maps per frequency band:

```
         Subject              Normative Mean         Z-Score Comparison
    [head map with         [head map with          [head map with
     hub connections,       hub connections,        hub connections,
     raw dwPLI values]      mean dwPLI values]      z-scored colors]
```

**Left panel (Subject):** Hub connectivity head map with line width/opacity proportional to the subject's dwPLI values. Uses warm colormap (YlOrRd). Raw values.

**Center panel (Normative):** Same layout but showing the normative mean dwPLI values for this age bin. Gives the clinician a visual reference for "what's normal."

**Right panel (Z-Score):** Hub connectivity with lines colored by z-score. Diverging colormap: blue (hypoconnected) → grey (normal) → red (hyperconnected). Line width proportional to |z-score|. Only connections with |z| > 1.0 shown to reduce clutter.

**Tabs across bands:** Delta | Theta | Alpha | Beta | HighBeta | Gamma

**Below the head maps:** Graph metrics comparison:
- Global efficiency: subject value marked on normative distribution (mini histogram or box plot)
- Characteristic path length: same
- Hub strength per region: bar chart with normative ±1SD range shaded

### Section 4: Flagged Deviations

**Summary table of all significant findings, sorted by |z-score| descending:**

```
| Channel | Band     | Metric                  | Value  | Z-Score | Percentile |
|---------|----------|-------------------------|--------|---------|------------|
| Pz      | Alpha    | absolute_power           | 3.21   | -2.8    | 1st        |
| Fz      | Theta    | corrected_absolute_power | 12.45  | +2.4    | 98th       |
| C3-C4   | Alpha    | dwpli_node_strength      | 0.42   | +2.1    | 97th       |
| Fz      | —        | Theta/Beta               | 4.2    | +2.0    | 96th       |
```

- Default threshold: |z| > 2.0 (adjustable)
- Percentile shown alongside z-score (from NormCell percentile data)
- Color-coded: blue for negative, red for positive

---

## Z-Score Computation

### Algorithm

For each (channel, band, metric, condition) combination:

1. Look up the NormCell matching the subject's age bin and condition
2. If the metric is log-transformed (absolute_power, corrected_absolute_power, ratios):
   ```
   z = (log10(subject_value) - log_mean) / log_sd
   ```
3. If the metric is not log-transformed (relative_power):
   ```
   z = (subject_value - mean) / sd
   ```
4. Percentile: interpolate from the NormCell's stored percentiles

### Which metrics to z-score

| Metric | Log-transform | Source |
|--------|---------------|--------|
| absolute_power | Yes | spectral |
| relative_power | No | spectral |
| corrected_absolute_power | Yes | spectral (specparam) |
| corrected_relative_power | No | spectral (specparam) |
| Theta/Beta (and all ratios) | Yes | spectral |
| dwpli_node_strength | No | connectivity |

### Existing Implementation

`open_normative/compare.py` already implements z-score comparison against norms. CW should import and use this module directly rather than reimplementing.

---

## Data Flow

```
CW Recording (19ch, resting)
    │
    ├─ process_resting()  →  MetricsResult
    │     ├─ spectral: band power, ratios, corrected power
    │     └─ connectivity: dwPLI, graph metrics
    │
    ├─ to_nested_dict()   →  {channel: {band: {metric: value}}}
    │
    ├─ compare_to_norms()  →  {channel: {band: {metric: z_score}}}
    │     (from compare.py, using loaded norms.json)
    │
    └─ Render Normative Comparison View
```

CW already runs `process_resting()` — the normative comparison is a post-processing step using the same spectral and connectivity results that are already computed.

---

## Spectral Overlay Data Requirements

To render the spectral overlay, CW needs the **full PSD curve** for each channel, not just band-power summaries. This is already computed during `analyze_spectral()`:
- `spectral_result["psd"]` — full PSD array (n_channels × n_freqs)
- `spectral_result["freqs"]` — frequency vector

For the normative overlay, we need the normative PSD distribution. Two options:

**Option A (recommended):** Store normative PSD statistics during `build_norms.py` — mean and SD of the full PSD curve per channel per age bin. This requires a new output alongside norms.json (e.g., `norms_psd.npz`).

**Option B:** Approximate from band-power norms. Less informative — you lose the frequency-resolution detail that makes the overlay valuable.

**Recommendation:** Option A. Add a `--save-psd` flag to `build_norms.py` that saves the aggregated PSD curves. This is a follow-up task.

---

## Connectivity Z-Score Requirements

For the three-panel connectivity display, CW needs:
- Subject's hub-to-hub dwPLI matrix (from `connectivity_result["hub_connectivity"]["dwpli"]`)
- Normative mean hub-to-hub matrix (from norms: `_hub_*` channel cells)
- Normative SD for each hub pair (from norms: same cells)
- Z-score = (subject - mean) / sd for each hub pair

The hub-to-hub data is now stored in the normative database (as of this branch) under synthetic `_hub_{name}` channels with metrics like `dwpli_hub_{target}`.

---

## Implementation Phases

### Phase 1: Core Z-Score Display
- Z-score topomaps for absolute_power, relative_power, corrected_absolute_power
- Ratio z-scores (bar charts)
- Flagged deviations table
- Uses existing `compare.py` module

### Phase 2: Spectral Overlay
- Full PSD overlay per channel (small multiples in head layout)
- Requires normative PSD storage (`norms_psd.npz`)
- Enlarged single-channel view with aperiodic decomposition

### Phase 3: Connectivity Comparison
- Three-panel hub connectivity head maps (Subject / Normal / Z-Score)
- Graph metrics comparison (global efficiency, path length)
- Hub strength z-scores

### Phase 4: Polish
- PDF/CSV export of the normative report
- Adjustable z-score threshold for flagging
- Sex-stratified norms (when sample sizes permit)
- Confidence indicators (n per cell, normality test results)

---

## Open Questions

1. **Age bin granularity:** Current LEMON bins are by decade (20-29, 30-39, ...). HBN will be finer (2-3 year bins for kids). Should CW handle variable bin widths, or standardize?

2. **Multiple normative databases:** Eventually CW may compare against LEMON norms (adults) and HBN norms (pediatric). Should the UI allow selecting which database, or auto-select based on age?

3. **Sex stratification:** When do we have enough data? Probably need n > 20 per sex × age bin to be meaningful. Track and report.

4. **Real-time vs post-hoc:** Is the normative comparison only available after recording is complete and processed? Or can z-scores update live as data comes in? (Probably post-hoc only for V1.)

5. **Specparam availability:** If specparam fitting fails for a subject (poor R²), corrected metrics won't be available. The view should gracefully degrade to uncorrected-only.
