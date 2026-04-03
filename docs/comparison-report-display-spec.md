# Comparison Report Display Spec — Coherence Workstation Frontend

## Overview

This spec describes how the CW frontend should render the `ComparisonReport` JSON output from the open-normative-eeg engine. The goal: surface statistical transparency that no competitor offers, in human-readable form that helps clinicians make better decisions.

The engine computes everything. This doc tells you how to show it.

---

## Layout: Cards Above Tables

The existing normative comparison view (z-score tables, topographic maps, raw data) stays exactly as it is. We add **finding cards** as an interpretation layer ABOVE the tables. Cards are **collapsed by default**.

```
┌──────────────────────────────────────────────────┐
│  REPORT HEADER (always visible)                  │
│  - Statistical integrity badge                   │
│  - Normative sample context                      │
│  - GSF + IAF status                              │
├──────────────────────────────────────────────────┤
│  PATTERN ALERTS (if any detected)                │
│  - Global patterns                               │
│  - Metric disagreements                          │
├──────────────────────────────────────────────────┤
│  FINDING CARDS (collapsed by default)            │
│  ▶ Fz · Alpha Power · z=+2.3 ± 0.2 · FDR sig   │
│  ▶ O1 · Theta Power · z=+2.8 ± 0.3 · FDR sig   │
│  ▶ ... (one per FDR-significant finding)         │
├──────────────────────────────────────────────────┤
│  EXISTING NORMATIVE TABLES (unchanged)           │
│  - Z-score tables                                │
│  - Topographic maps                              │
│  - PSD curves                                    │
│  - Raw data                                      │
├──────────────────────────────────────────────────┤
│  TRANSPARENCY DRAWER (collapsed)                 │
│  - Full methodology details                      │
│  - Complete results table with all columns        │
└──────────────────────────────────────────────────┘
```

---

## Section 1: Report Header

Display prominently at top. Always visible.

### Statistical Integrity Badge
```
114 comparisons performed. 8 survived FDR correction at alpha=0.05.
Without correction, ~5.7 false positives expected by chance.
```

Source fields: `metadata.total_tests`, `metadata.fdr_significant_count`, `metadata.fdr_alpha`, `metadata.expected_false_positives_uncorrected`

### Normative Sample Context
```
Compared against [LEMON + Dortmund] normative database.
Age bin: 30-39 (N varies by metric, see details).
Age interpolation: not applied.
```

### GSF Status
```
Global Scale Factor correction applied. Subject GSF = -11.2 (within typical range).
```

### IAF Status

**Typical range:**
```
Individual Alpha Frequency: 10.3 Hz (typical range).
Fixed band boundaries are appropriate for this subject.
```

**Outside typical range (important clinical alert):**
```
IAF: 7.8 Hz (below typical range).
Fixed alpha band [8-13 Hz] may be mischaracterizing this subject's alpha activity.
Consider IAF-adjusted interpretation.
```

Source fields: `metadata.iaf_peak`, `metadata.iaf_typical_range`

---

## Section 2: Pattern Alerts

Show only when patterns are detected. These should be visually prominent (info/warning cards).

### Global Patterns
```
GLOBAL PATTERN DETECTED
Alpha absolute_power is elevated across 15 of 19 channels (79%).
A global pattern suggests a non-focal process rather than localized brain 
activity differences. Common causes include medication effects, arousal 
state differences, or skull thickness/impedance variation (GSF correction 
was applied to mitigate equipment-related scaling).
```

Source: `patterns.global_patterns[]`

### Metric Disagreements
```
APERIODIC VS. OSCILLATORY DISTINCTION — Fz Alpha
Total power: z = +2.3 (elevated)
Periodic-only power: z = -0.2 (typical)
The elevation in total power is driven by the aperiodic (1/f) spectral 
component, not by alpha oscillatory activity. The 1/f slope reflects 
broad cortical excitability, while alpha oscillations reflect specific 
thalamocortical network activity.
```

Source: `patterns.metric_disagreements[]`

### Spatial Clusters
```
CLUSTER: Left temporal-occipital
Elevated Theta at T3, T5, O1 (mean |z| = 2.1, max = 2.8)
Adjacent channels show a coherent pattern of elevated Theta activity,
suggesting a localized finding in the left posterior region.
```

Source: `patterns.deviation_clusters[]`

---

## Section 3: Finding Cards

One card per FDR-significant finding. Sort by |z_score| descending (most extreme first).

### Collapsed State (one-line summary strip)

```
▶ Fz · Alpha Power · z=+2.3 ± 0.2 · Moderately atypical · FDR sig
```

Format: `{channel} · {band} {metric} · z={z_score:+.1f} ± {se_z:.1f} · {severity_label} · FDR sig`

Use severity color: green (typical), yellow (mildly), orange (moderately), red (notably+).

### Expanded State (click to open)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Fz · Alpha · Absolute Power                                        │
│  ────────────────────────────────────────────────────────────────    │
│                                                                      │
│  ┌──────────────────┐                                                │
│  │                  │  Value: 48.2 uV^2    z-score: +2.31 +/- 0.21  │
│  │   [CONTEXTUAL    │  Severity: Moderately atypical (elevated)      │
│  │    VISUAL HERE]  │  Effect size: Cohen's d = 2.31 (large)         │
│  │                  │                                                │
│  │   e.g. topomap   │  Reference: mean 22.4, SD 11.2, N=47          │
│  │   with Fz        │  95% CI for reference mean: [19.1, 25.7]      │
│  │   highlighted    │  95% Prediction interval: [0.8, 44.0]         │
│  └──────────────────┘  Patient value is OUTSIDE prediction interval  │
│                                                                      │
│  p = 0.021 · FDR significant · log-transformed                      │
│  Normality: Shapiro-Wilk p = 0.23 (adequate)                        │
│                                                                      │
│  ── Human-Readable Summary ──                                        │
│  "The precision of this z-score is +/-0.21, meaning the true         │
│   deviation is approximately +2.1 to +2.5."                          │
│  "In a healthy reference population, 95% of individuals score        │
│   between 0.8 and 44.0. This patient's value of 48.2 falls          │
│   outside that range."                                               │
│  "This finding remains statistically significant after correcting    │
│   for the 114 simultaneous comparisons performed."                   │
└──────────────────────────────────────────────────────────────────────┘
```

### Contextual Visual (embedded in card)

The visual should match the finding type:

| Finding Type | Visual |
|---|---|
| Band power (any channel) | Topomap of that band's z-scores, finding channel highlighted |
| Connectivity / node strength | Hub connectivity diagram for that band |
| Asymmetry | Left/right comparison bar chart for that pair |
| Aperiodic (offset/exponent) | PSD curve with aperiodic fit overlay |
| IAF | PSD curve with alpha peak and search range marked |

### Human-Readable Translations

Generate these from the data fields:

**SE(z):**
> "The precision of this z-score is +/-{se_z:.2f}, meaning the true deviation is approximately {z-se_z:+.1f} to {z+se_z:+.1f}."

**Prediction interval:**
> "In a healthy reference population, 95% of individuals score between {pi_lower:.1f} and {pi_upper:.1f}. This patient's value of {value:.1f} falls {WITHIN/OUTSIDE} that range."

**FDR:**
> "This finding remains statistically significant after correcting for the {total_tests} simultaneous comparisons performed."

**Low confidence (if applicable):**
> "Caution: This comparison is based on only {norm_n} reference subjects. Z-scores from small samples are less reliable (SE = +/-{se_z:.2f})."

---

## Section 4: Transparency Drawer

Collapsible panel at bottom. Expandable for researchers and experienced clinicians.

### Methodology
```
Normative construction: Built from N subjects across [datasets].
Processed with identical pipeline (open-normative-eeg v0.1).
Statistical methods: Z-scores computed in log-space for right-skewed 
metrics (absolute power, band ratios). FDR correction via 
Benjamini-Hochberg procedure.
```

### Full Results Table

ALL results (not just significant), sortable by any column:

| Channel | Band | Metric | Value | z | SE(z) | p | FDR sig | Cohen's d | Severity | N | Log? | Normality p |
|---------|------|--------|-------|---|-------|---|---------|-----------|----------|---|------|-------------|

### Confidence Color Coding for Table Rows

| Confidence | Color | Criteria |
|---|---|---|
| High | Green background | N >= 30 AND normality_p > 0.05 |
| Moderate | Yellow background | N 10-29 OR normality_p 0.01-0.05 |
| Low | Red background | N < 10 (low_confidence = true) |

---

## Section 5: Design Principles

1. **Cards above tables.** Finding cards sit above the full normative tables as an interpretation layer. The raw z-score tables, topomaps, and all existing views remain unchanged below. Cards are collapsed by default (one-line summary strip) -- click to expand. Tables are never hidden. Cards are additive.

2. **Never show a z-score without its precision.** Always display "z +/- SE" or at minimum show SE on hover/tooltip. A z=2.3 from N=8 is very different from z=2.3 from N=200.

3. **Prediction intervals over confidence intervals.** CI answers "where is the population mean?" -- not the clinical question. PI answers "where would a new healthy person fall?" -- the actual clinical question. Always show PI when available.

4. **Patterns before individual channels.** If 15/19 channels are elevated, show the global pattern alert first. Don't force the clinician to notice the pattern themselves from a table of 114 numbers.

5. **Disagreements are insights, not errors.** When corrected and uncorrected power disagree, that's clinically valuable: it tells you whether the finding is oscillatory or aperiodic. Frame it as useful information.

6. **Color means confidence, not just severity.** Use color to indicate how trustworthy the comparison is (sample size, normality, CI width), not only how extreme the z-score is. A z=3.0 from N=8 should look different from z=3.0 from N=200.

7. **All language is structural, never diagnostic.** "Atypical" not "abnormal." "Elevated" not "pathological." "Suggests" not "indicates." The normative engine measures position relative to a reference. CW contextualizes it.

8. **Progressive disclosure.** Report header -> Collapsed finding cards -> Expanded cards with visuals -> Full normative tables -> Transparency drawer. Each level adds detail without removing what was there before.

---

## JSON API Shape

The `ComparisonReport.to_dict()` output that CW will consume:

```json
{
  "metadata": {
    "age": 35,
    "condition": "eo",
    "age_bin": "30-39",
    "age_interpolated": false,
    "total_tests": 114,
    "fdr_significant_count": 8,
    "fdr_alpha": 0.05,
    "expected_false_positives_uncorrected": 5.7,
    "gsf": -11.2,
    "iaf_peak": 10.3,
    "iaf_typical_range": true
  },
  "results": [
    {
      "channel": "Fz",
      "band": "Alpha",
      "metric": "absolute_power",
      "value": 48.2,
      "z_score": 2.31,
      "se_z": 0.21,
      "p_value": 0.021,
      "fdr_significant": true,
      "cohen_d": 2.31,
      "cohen_d_label": "large",
      "severity_label": "Moderately atypical",
      "percentile_rank": 98.9,
      "norm_mean": 22.4,
      "norm_sd": 11.2,
      "norm_n": 47,
      "ci_lower": 19.1,
      "ci_upper": 25.7,
      "pi_lower": 0.8,
      "pi_upper": 44.0,
      "within_prediction_interval": false,
      "log_transformed": true,
      "normality_p": 0.23,
      "low_confidence": false
    }
  ],
  "patterns": {
    "global_patterns": [
      {
        "band": "Alpha",
        "metric": "absolute_power",
        "direction": "elevated",
        "fraction": 0.79,
        "channel_count": 15,
        "total_channels": 19,
        "interpretation": "Global elevation across 15/19 channels suggests a non-focal process."
      }
    ],
    "deviation_clusters": [
      {
        "channels": ["T3", "T5", "O1"],
        "band": "Theta",
        "metric": "absolute_power",
        "direction": "elevated",
        "mean_z": 2.1,
        "max_z": 2.8
      }
    ],
    "metric_disagreements": [
      {
        "channel": "Fz",
        "band": "Alpha",
        "absolute_z": 2.3,
        "corrected_z": -0.2,
        "interpretation": "Deviation is in the aperiodic component, not oscillatory activity."
      }
    ]
  }
}
```
