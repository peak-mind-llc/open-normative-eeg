# Coherence Workstation — Normative Comparison View

## Implementation Spec for Claude Code

This document, along with `norms.json` and optionally `norms_psd.npz`, provides
everything needed to build the Normative Comparison page in Coherence Workstation.

---

## 1. Data Files

### 1.1 norms.json — Band-Power & Connectivity Norms

A flat JSON array of normative cells. Each cell is one
`(age_bin, condition, channel, band, metric)` combination.

```jsonc
[
  {
    "bin": "20-29",           // age range (inclusive both ends)
    "condition": "eo",        // "eo" or "ec"
    "channel": "Fz",          // electrode name, OR synthetic: "_hub_F_mid", "_graph"
    "band": "Alpha",          // "Delta","Theta","Alpha","Beta","HighBeta","Gamma"
    "metric": "absolute_power",
    "n": 47,                  // subjects in this cell
    "mean": 12.34,            // arithmetic mean (raw space)
    "sd": 5.67,               // arithmetic SD (raw space)
    "log_mean": 1.05,         // mean of ln(value) — only for log-transformed metrics
    "log_sd": 0.43,           // SD of ln(value) — only for log-transformed metrics
    "log_transformed": true,  // whether this metric uses log-space z-scores
    "normality_p": 0.23,      // Shapiro-Wilk p-value (null = insufficient data)
    "percentiles": {           // stored percentile boundaries (raw space)
      "1": 2.1, "5": 3.4, "10": 4.2, "25": 6.8,
      "50": 11.5, "75": 16.7, "90": 22.1, "95": 26.3, "99": 35.0
    }
  },
  // ... thousands more cells
]
```

**Channel types in the file:**

| Channel pattern | Meaning | Example metrics |
|---|---|---|
| `Fp1`, `Fz`, etc. (19 standard) | Electrode-level | `absolute_power`, `relative_power`, `corrected_absolute_power`, `dwpli_node_strength` |
| `_hub_F_mid`, `_hub_T_L`, etc. | Hub-to-hub connectivity | `dwpli_hub_F_R`, `dwpli_hub_P_mid`, ... |
| `_graph` | Whole-brain graph metrics | `global_efficiency`, `char_path_length` |

**Metric names and z-score rules:**

| Metric | Log-transform? | Appears on channels | Description |
|---|---|---|---|
| `absolute_power` | **Yes** (use `log_mean`/`log_sd`) | 19 electrodes | µV²/Hz band power |
| `relative_power` | No (use `mean`/`sd`) | 19 electrodes | fraction of total power |
| `corrected_absolute_power` | **Yes** | 19 electrodes | periodic-only (specparam) |
| `corrected_relative_power` | No | 19 electrodes | periodic-only relative |
| `Theta/Beta` | **Yes** | 19 electrodes | ratio |
| `Theta/Beta1` | **Yes** | 19 electrodes | ratio (Beta1 = 13-20 Hz) |
| `Delta/HighBeta` | **Yes** | 19 electrodes | ratio |
| `Alpha/HighBeta` | **Yes** | 19 electrodes | ratio |
| `dwpli_node_strength` | No | 19 electrodes | mean dwPLI to all other channels |
| `dwpli_hub_{target}` | No | `_hub_*` channels | pairwise hub dwPLI |
| `global_efficiency` | No | `_graph` | graph metric |
| `char_path_length` | No | `_graph` | graph metric |

### 1.2 norms_psd.npz — Full PSD Curves (for Spectral Overlay)

NumPy compressed archive. Load with `np.load("norms_psd.npz")`.

| Key | Shape | Dtype | Description |
|---|---|---|---|
| `freqs` | `(n_freqs,)` | float64 | frequency vector in Hz (e.g. 0.5 to 50 Hz) |
| `bins` | `(n_bins,)` | str | age bin labels, e.g. `["20-29", "30-39", ...]` |
| `conditions` | `(n_conds,)` | str | `["ec", "eo"]` |
| `ch_names` | `(19,)` | str | channel names in order |
| `mean` | `(n_bins, n_conds, 19, n_freqs)` | float64 | mean log10(µV²/Hz) PSD |
| `sd` | `(n_bins, n_conds, 19, n_freqs)` | float64 | SD of log10(µV²/Hz) PSD |
| `n` | `(n_bins, n_conds)` | int | subject count per cell |

**Usage:** To draw the normative band for channel `ch` in age bin `bi`, condition `ci`:
```
mean_curve = mean[bi, ci, ch_idx, :]
upper_1sd = mean_curve + sd[bi, ci, ch_idx, :]
lower_1sd = mean_curve - sd[bi, ci, ch_idx, :]
upper_2sd = mean_curve + 2 * sd[bi, ci, ch_idx, :]
lower_2sd = mean_curve - 2 * sd[bi, ci, ch_idx, :]
```

Plot subject PSD as `log10(psd_uV2Hz)` on the same y-axis.

---

## 2. Subject Data Requirements

CW already computes these from a resting-state recording. The Normative Comparison
view consumes the same metrics dict that CW uses internally.

**Required subject data structure** (nested dict):
```jsonc
{
  "Fz": {
    "Alpha": {
      "absolute_power": 8.7,
      "relative_power": 0.32,
      "corrected_absolute_power": 5.1,
      "dwpli_node_strength": 0.15
    },
    "Theta": { ... },
    // ... all 6 bands
  },
  // ... all 19 channels
  "_hub_F_mid": {
    "Alpha": {
      "dwpli_hub_F_L": 0.12,
      "dwpli_hub_F_R": 0.08,
      // ... to all other 9 hubs
    }
  },
  // ... all 10 _hub_ channels
  "_graph": {
    "Alpha": {
      "global_efficiency": 0.45,
      "char_path_length": 2.3
    }
  }
}
```

**Also needed for spectral overlay:**
- Subject's full PSD array: `(19, n_freqs)` in µV²/Hz
- Corresponding frequency vector: `(n_freqs,)` in Hz
- These are already available from `compute_psd()` in the pipeline

**Subject metadata:**
- `age` (years) — determines which normative bin to use
- `condition` — `"eo"` or `"ec"`

---

## 3. Z-Score Computation Algorithm

For each `(channel, band, metric)` in the subject's data:

```
1. Find the NormCell where:
   cell.channel == channel AND
   cell.band == band AND
   cell.metric == metric AND
   cell.condition == subject_condition AND
   cell.bin contains subject_age (e.g., age 34 → bin "30-39")

2. Compute z-score:
   IF metric is log-transformed (cell.log_transformed == true):
       z = (ln(subject_value) - cell.log_mean) / cell.log_sd
   ELSE:
       z = (subject_value - cell.mean) / cell.sd

3. Interpolate percentile from cell.percentiles (linear between stored points)
```

**Log-transformed metrics:** `absolute_power`, `corrected_absolute_power`,
`Theta/Beta`, `Theta/Beta1`, `Delta/HighBeta`, `Alpha/HighBeta`

**NOTE:** `log_mean` and `log_sd` in norms.json use natural log (`ln`), not `log10`.
The subject value must also be `ln()`-transformed before computing the z-score.

---

## 4. View Layout

### 4.0 Page Structure

The Normative Comparison view is a dedicated full-page view (not embedded in
existing views). It has a header bar and four scrollable sections.

### 4.1 Header Bar

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Normative Comparison    [EO ▼] [EC]    Age: 34 (bin: 30-39)   n = 47   │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Condition toggle** (EO/EC) — switches all panels instantly
- **Age and bin** — computed from birthday
- **n** — subject count from the matched normative bin (from any cell's `n` field)
- Warning banner if age is outside all bins or n < 10

### 4.2 Section 1: Spectral Overlay

**19 small-multiple PSD plots arranged in 10-20 head layout:**

```
            Fp1      Fp2
      F7    F3   Fz   F4    F8
      T3    C3   Cz   C4    T4
      T5    P3   Pz   P4    T6
            O1        O2
```

**Grid coordinates** (col, row) for CSS grid or absolute positioning:

| Channel | Col | Row |
|---------|-----|-----|
| Fp1 | 2 | 0 |
| Fp2 | 4 | 0 |
| F7 | 0 | 1 |
| F3 | 1 | 1 |
| Fz | 3 | 1 |
| F4 | 4 | 1 |
| F8 | 5 | 1 |
| T3 | 0 | 2 |
| C3 | 1 | 2 |
| Cz | 3 | 2 |
| C4 | 4 | 2 |
| T4 | 5 | 2 |
| T5 | 0 | 3 |
| P3 | 2 | 3 |
| Pz | 3 | 3 |
| P4 | 4 | 3 |
| T6 | 5 | 3 |
| O1 | 2 | 4 |
| O2 | 4 | 4 |

Each mini-plot contains:
- **X-axis:** 1–50 Hz
- **Y-axis:** log10(µV²/Hz)
- **Subject PSD:** solid colored line (e.g., black or dark blue)
- **Normative mean:** dashed line
- **±1 SD:** medium shaded band (e.g., light blue, 20% opacity)
- **±2 SD:** lighter shaded band (e.g., 10% opacity)
- **Band boundaries:** subtle vertical lines at 1|4|8|13|25|30|50

**Click-to-enlarge:** clicking a channel opens a modal/detail view with full axis
labels, legend, and percentile bands (5th/25th/75th/95th).

**Data source:** `norms_psd.npz` for normative curves. Subject PSD from CW pipeline.

### 4.3 Section 2: Z-Score Topographic Maps

**Grid layout — rows = metric groups, columns = frequency bands:**

```
                    Delta   Theta   Alpha   Beta   HighBeta   Gamma
Absolute Power       [topo]  [topo]  [topo]  [topo]  [topo]   [topo]
Relative Power       [topo]  [topo]  [topo]  [topo]  [topo]   [topo]
Corrected Power      [topo]  [topo]  [topo]  [topo]  [topo]   [topo]
```

Each topomap:
- 19-channel interpolated head outline with nose at top
- **Color scale:** diverging — blue (−3) → white (0) → red (+3)
- Clamp display range at [−3, +3] but allow tooltip to show true value
- Z-score value label at each electrode position (small text, e.g. "−2.1")
- **Bold outline or marker** on electrodes where |z| ≥ 2.0

**Ratio z-scores** (below the topomap grid):

```
Theta/Beta           [19-channel topomap or horizontal bar chart]
Delta/HighBeta       [19-channel topomap or horizontal bar chart]
Alpha/HighBeta       [19-channel topomap or horizontal bar chart]
Theta/Beta1          [19-channel topomap or horizontal bar chart]
```

Use the same diverging color scale. Each channel gets one z-score value.
These are the same ratios shown elsewhere in CW.

### 4.4 Section 3: Connectivity — Three-Panel Head Maps

For each frequency band (tabs: Delta | Theta | Alpha | Beta | HighBeta | Gamma):

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    Subject       │  │    Normative     │  │    Z-Score       │
│                  │  │                  │  │                  │
│  [head outline   │  │  [head outline   │  │  [head outline   │
│   with hub       │  │   with hub       │  │   with hub       │
│   connections]   │  │   connections]   │  │   connections]   │
│                  │  │                  │  │                  │
│  Raw dwPLI       │  │  Mean dwPLI      │  │  Z-scored        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**10 regional hubs** and their 2D head positions (azimuthal equidistant projection,
unit circle with nose at top):

| Hub | Channels averaged | X | Y |
|---|---|---|---|
| F_mid | Fz | 0.00 | 0.36 |
| F_L | F3, F7 | −0.35 | 0.30 |
| F_R | F4, F8 | 0.35 | 0.30 |
| C_mid | Cz | 0.00 | 0.00 |
| T_L | T3, T5 | −0.55 | −0.05 |
| T_R | T4, T6 | 0.55 | −0.05 |
| P_mid | Pz | 0.00 | −0.36 |
| P_L | P3 | −0.25 | −0.30 |
| P_R | P4 | 0.25 | −0.30 |
| O | O1, O2 | 0.00 | −0.55 |

**Left panel (Subject raw):**
- Draw head circle, nose, ear markers
- Draw hub nodes as circles (all same size)
- Draw lines between all hub pairs where dwPLI > 0.05
- Line width proportional to dwPLI value (range 0–0.5 → 1–6px)
- Line color: warm sequential (YlOrRd or similar)

**Center panel (Normative mean):**
- Same layout, same visual encoding
- Uses the normative mean dwPLI values from norms.json
- Subject's dwPLI: from their metrics dict under `_hub_*` channels
- Normative dwPLI: from norms cells where channel starts with `_hub_`

**Right panel (Z-Score):**
- Lines colored by z-score: blue (hypo, z < −1) → grey (|z| < 1) → red (hyper, z > 1)
- Line width proportional to |z-score| (range 0–3 → 1–6px)
- Only show connections where |z| > 1.0 to reduce clutter
- Hub nodes colored by their total node_strength z-score

**Extracting hub-to-hub data:**

From norms.json, for a given band (e.g., "Alpha"):
```
For hub_i "F_mid", find cell where:
  channel == "_hub_F_mid"
  band == "Alpha"
  metric == "dwpli_hub_F_R"   (for the F_mid → F_R connection)

This gives you the normative mean/sd for that hub pair.
```

From subject metrics dict:
```
subject_dwpli = metrics["_hub_F_mid"]["Alpha"]["dwpli_hub_F_R"]
```

The 10 hubs form a 10×10 matrix. Only the off-diagonal entries exist (45 unique pairs).

### 4.5 Section 4: Flagged Deviations Table

Summary table sorted by |z-score| descending. Default filter: |z| ≥ 2.0 (adjustable).

| Column | Source |
|---|---|
| Channel | cell channel name |
| Band | cell band name |
| Metric | cell metric name |
| Value | subject's raw value |
| Z-Score | computed z-score (color: blue if negative, red if positive) |
| Percentile | interpolated from cell percentiles |

---

## 5. Frequency Bands

These are the canonical bands used throughout:

| Band | Range (Hz) |
|---|---|
| Delta | 1–4 |
| Theta | 4–8 |
| Alpha | 8–13 |
| Beta | 13–30 |
| HighBeta | 25–30 |
| Gamma | 30–50 |

Note: HighBeta overlaps with Beta (it's a sub-band). Both are shown independently.

---

## 6. The 19-Channel Montage

Standard 10-20 system, always in this order:

```
Fp1 Fp2 F7 F3 Fz F4 F8 T3 C3 Cz C4 T4 T5 P3 Pz P4 T6 O1 O2
```

2D electrode positions for topographic mapping (unit head circle, nose at top):

| Ch | X | Y |
|---|---|---|
| Fp1 | −0.15 | 0.70 |
| Fp2 | 0.15 | 0.70 |
| F7 | −0.55 | 0.40 |
| F3 | −0.25 | 0.40 |
| Fz | 0.00 | 0.40 |
| F4 | 0.25 | 0.40 |
| F8 | 0.55 | 0.40 |
| T3 | −0.70 | 0.00 |
| C3 | −0.30 | 0.00 |
| Cz | 0.00 | 0.00 |
| C4 | 0.30 | 0.00 |
| T4 | 0.70 | 0.00 |
| T5 | −0.55 | −0.40 |
| P3 | −0.25 | −0.40 |
| Pz | 0.00 | −0.40 |
| P4 | 0.25 | −0.40 |
| T6 | 0.55 | −0.40 |
| O1 | −0.15 | −0.70 |
| O2 | 0.15 | −0.70 |

For topographic interpolation: use biharmonic spline or any standard EEG topomap
interpolation method across these 19 points within the unit head circle.

---

## 7. Color Scales

| Use case | Type | Range | Colors |
|---|---|---|---|
| Z-score topomaps | Diverging | −3 to +3 | Blue → White → Red (e.g., RdBu_r) |
| Subject/Norm dwPLI | Sequential | 0 to max | YlOrRd or Viridis |
| Z-score connectivity | Diverging | −3 to +3 | Blue → Grey → Red |
| Spectral overlay shading | Opacity | ±1 SD / ±2 SD | Same hue, 20%/10% opacity |

---

## 8. Edge Cases & Warnings

| Condition | Behavior |
|---|---|
| Age outside all bins | Show banner: "Subject age (X) outside normative range (Y–Z)." Disable z-scores. |
| Bin with n < 10 | Show banner: "Low reference sample (n=X). Interpret with caution." |
| Missing channel in subject data | Show as grey/hatched on topomaps, skip in table |
| log-transform metric but value ≤ 0 | Skip z-score for that cell, show as "N/A" |
| No norms_psd.npz | Hide or disable spectral overlay section |
| No `_hub_*` cells in norms.json | Hide or disable connectivity section |

---

## 9. Loading norms.json — Practical Index

For fast lookup, build an in-memory index on load:

```
index = {}
for cell in norms_json:
    key = (cell.bin, cell.condition, cell.channel, cell.band, cell.metric)
    index[key] = cell
```

Then to look up: `index[(age_bin, condition, "Fz", "Alpha", "absolute_power")]`

The file is typically 5–20 MB. Parse once on app startup or when norms file is selected.

---

## 10. Is This Enough?

**Yes — norms.json + norms_psd.npz + this spec is sufficient** for Claude Code to
build the Normative Comparison view, provided the session also has access to:

1. **The CW codebase** — to understand the existing component library, routing,
   state management, chart rendering approach, and how existing views (power maps,
   spectral plots) are implemented.

2. **A sample norms.json** — even a small one (e.g., from `--max-subjects 5`) so
   Claude Code can inspect the actual data shape and validate its parsing.

3. **This spec** — copy into the CW repo as `docs/normative-comparison-spec.md`
   or paste into the prompt.

**What Claude Code does NOT need from this repo:**
- The Python processing pipeline (that's for building norms, not consuming them)
- The `compare.py` module (the z-score algorithm is simple enough to reimplement
  in whatever language CW uses — see Section 3 above)

**Recommended prompt for the CW session:**
> Read `docs/normative-comparison-spec.md` and `sample_norms.json`.
> Add a new "Normative Comparison" page/view to CW.
> Phase 1: Z-score topomaps + flagged deviations table.
> Phase 2: Spectral overlay (requires norms_psd.npz).
> Phase 3: Three-panel connectivity head maps.
