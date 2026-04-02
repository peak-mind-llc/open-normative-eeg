# Validation Report: LEMON + Dortmund

Generated: 2026-04-02 01:25 UTC

---

## Executive Summary

**11 PASS, 2 FAIL, 0 SKIP** out of 13 checks.

| Check | Result |
|-------|--------|
| Split-half (core spectral) r > 0.90 | FAIL |
| Split-half (all metrics) r > 0.90 | FAIL |
| EC > EO alpha | PASS |
| IAF declines with age | PASS |
| alpha_posterior_dominance | PASS |
| eo_ec_alpha | PASS |
| aperiodic_exponent_range | PASS |
| aperiodic_age_flattening | PASS |
| iaf_range | PASS |
| theta_beta_ratio_range | PASS |
| relative_power_sums | PASS |
| gsf_consistency | PASS |
| Cross-dataset r > 0.90 | PASS |

---

## Internal Consistency

### Cell Quality

- **Total normative cells:** 37,536
- **Total subject-condition records:** 971
- **Sample size per cell:** min=8, median=88, max=121
- **Thin cells (N < 10):** 6
- **Non-normal cells (Shapiro-Wilk p < 0.01):** 18409

| Age Bin | Min N | Median N | Max N | Status |
|---------|-------|----------|-------|--------|
| 20-29 | 96 | 109 | 109 | OK |
| 30-39 | 73 | 88 | 89 | OK |
| 40-49 | 69 | 87 | 88 | OK |
| 50-59 | 97 | 121 | 121 | OK |
| 60-69 | 52 | 67 | 68 | OK |
| 70-79 | 8 | 12 | 12 | Thin |

### Split-Half Reliability

Performed 10 random 50/50 splits. For each split, built normative tables from each half and correlated the cell means.

- **Overall mean r:** 0.8477
- **Overall range:** 0.7958 to 0.8728
- **All splits r > 0.95:** No
- **All splits r > 0.90:** No

**Core spectral metrics only** (relative power, corrected power, GSF power, aperiodic):
- **Core mean r:** 0.9008
- **Core all r > 0.90:** No

| Metric | Mean r | Min r | Status |
|--------|--------|-------|--------|
| absolute_power | 0.050 | -0.024 | LOW |
| aperiodic_exponent | 0.839 | 0.768 | OK |
| aperiodic_offset | 0.882 | 0.851 | OK |
| asymmetry_index | 0.239 | 0.093 | LOW |
| char_path_length | 0.950 | 0.929 | OK |
| coh_hub_C_mid | 0.995 | 0.993 | OK |
| coh_hub_F_L | 0.995 | 0.993 | OK |
| coh_hub_F_R | 0.992 | 0.988 | OK |
| coh_hub_F_mid | nan | nan | OK |
| coh_hub_O | 0.989 | 0.984 | OK |
| coh_hub_P_L | 0.985 | 0.980 | OK |
| coh_hub_P_R | 0.991 | 0.988 | OK |
| coh_hub_P_mid | 0.988 | 0.983 | OK |
| coh_hub_T_L | 0.986 | 0.976 | OK |
| coh_hub_T_R | 0.995 | 0.990 | OK |
| coh_node_strength | 0.986 | 0.982 | OK |
| corrected_absolute_power | 0.918 | 0.829 | OK |
| corrected_relative_power | 0.974 | 0.954 | OK |
| dwpli_hub_C_mid | 0.945 | 0.899 | OK |
| dwpli_hub_F_L | 0.945 | 0.899 | OK |
| dwpli_hub_F_R | 0.926 | 0.884 | OK |
| dwpli_hub_F_mid | nan | nan | OK |
| dwpli_hub_O | 0.915 | 0.828 | OK |
| dwpli_hub_P_L | 0.921 | 0.875 | OK |
| dwpli_hub_P_R | 0.947 | 0.931 | OK |
| dwpli_hub_P_mid | 0.937 | 0.900 | OK |
| dwpli_hub_T_L | 0.951 | 0.929 | OK |
| dwpli_hub_T_R | 0.954 | 0.926 | OK |
| dwpli_node_strength | 0.942 | 0.902 | OK |
| global_efficiency | 0.300 | 0.170 | LOW |
| gsf | 0.641 | 0.391 | LOW |
| gsf_absolute_power | 0.768 | 0.699 | LOW |
| gsf_relative_power | 0.963 | 0.935 | OK |
| iaf_cog | 0.620 | 0.305 | LOW |
| iaf_peak | 0.558 | 0.356 | LOW |
| imcoh_hub_C_mid | 0.964 | 0.941 | OK |
| imcoh_hub_F_L | 0.964 | 0.941 | OK |
| imcoh_hub_F_R | 0.949 | 0.923 | OK |
| imcoh_hub_F_mid | nan | nan | OK |
| imcoh_hub_O | 0.950 | 0.909 | OK |
| imcoh_hub_P_L | 0.942 | 0.914 | OK |
| imcoh_hub_P_R | 0.961 | 0.949 | OK |
| imcoh_hub_P_mid | 0.955 | 0.935 | OK |
| imcoh_hub_T_L | 0.960 | 0.940 | OK |
| imcoh_hub_T_R | 0.965 | 0.939 | OK |
| pac_mi | 0.303 | -0.076 | LOW |
| relative_power | 0.963 | 0.935 | OK |
| value | 0.937 | 0.887 | OK |

### Eyes-Open vs Eyes-Closed Alpha (Berger Effect)

Eyes-closed alpha relative_power should exceed eyes-open

- **Cells tested:** 114
- **Correct (EC > EO):** 114 (100%)
- **Violations:** 0
- **Result:** PASS

### IAF Age Trend

IAF should decline with age (negative correlation expected)
- **Result:** PASS

**EO:** r = -0.432 (p = 0.3928) PASS

| Bin | Mean IAF (Hz) | SD | N |
|-----|---------------|-----|---|
| 20-29 | 10.3 | 1.1 | 108 |
| 30-39 | 10.6 | 0.9 | 88 |
| 40-49 | 10.6 | 1.2 | 87 |
| 50-59 | 10.5 | 1.2 | 119 |
| 60-69 | 10.4 | 1.2 | 68 |
| 70-79 | 10.1 | 1.1 | 12 |

**EC:** r = -0.814 (p = 0.0489) PASS

| Bin | Mean IAF (Hz) | SD | N |
|-----|---------------|-----|---|
| 20-29 | 10.3 | 0.9 | 109 |
| 30-39 | 10.5 | 0.9 | 89 |
| 40-49 | 10.3 | 0.9 | 87 |
| 50-59 | 10.2 | 1.1 | 121 |
| 60-69 | 10.0 | 1.0 | 67 |
| 70-79 | 9.3 | 0.7 | 12 |

---

## Literature Reference Checks

Each check verifies that the normative database is consistent with well-established EEG findings from the published literature. These are directional and magnitude checks, not exact-number comparisons.

### Summary

| Check | Result |
|-------|--------|
| alpha_posterior_dominance | PASS |
| eo_ec_alpha | PASS |
| aperiodic_exponent_range | PASS |
| aperiodic_age_flattening | PASS |
| iaf_range | PASS |
| theta_beta_ratio_range | PASS |
| relative_power_sums | PASS |
| gsf_consistency | PASS |

### Alpha posterior dominance

Alpha power should be higher at posterior (O1,O2,Pz,P3,P4) than anterior (Fp1,Fp2,Fz,F3,F4) sites

- **Reference:** Niedermeyer & da Silva (2005); Klimesch (1999)
- **Result:** PASS
- **Cells:** 12/12 correct

### Berger effect (EC > EO alpha)

Eyes-closed alpha power should exceed eyes-open at all sites. Expected ratio 1.5-4x at posterior sites.

- **Reference:** Berger (1929); Barry et al. (2007, 2009)
- **Result:** PASS
- **Cells:** 114/114 correct
- **Median EC/EO ratio:** 1.86

### Aperiodic exponent range

Mean aperiodic exponent should be 0.5-3.0 for healthy adults (typical: 1.0-2.0)

- **Reference:** Donoghue et al. (2020); Voytek et al. (2015)
- **Result:** PASS
- **Cells:** 228/228 correct

### Aperiodic exponent flattens with age

1/f exponent should decrease (flatten) with age at Pz

- **Reference:** Voytek et al. (2015); Craiu et al. (2025): ~-0.003/year
- **Result:** PASS
- **EC:** r = -0.945 (p = 0.0044)
- **EO:** r = -0.948 (p = 0.0039)

### IAF in expected range (8-13 Hz)

Mean IAF should be 8-13 Hz, peaking ~10 Hz in young adults, declining with age

- **Reference:** Klimesch (1999); Craiu et al. (2025): -0.015 Hz/year
- **Result:** PASS
- **Cells:** 12/12 correct

| Bin | Condition | Mean IAF | SD | N |
|-----|-----------|----------|-----|---|
| 20-29 | ec | 10.3 | 0.9 | 109 |
| 20-29 | eo | 10.3 | 1.1 | 108 |
| 30-39 | ec | 10.5 | 0.9 | 89 |
| 30-39 | eo | 10.6 | 0.9 | 88 |
| 40-49 | ec | 10.3 | 0.9 | 87 |
| 40-49 | eo | 10.6 | 1.2 | 87 |
| 50-59 | ec | 10.2 | 1.1 | 121 |
| 50-59 | eo | 10.5 | 1.2 | 119 |
| 60-69 | ec | 10.0 | 1.0 | 67 |
| 60-69 | eo | 10.4 | 1.2 | 68 |
| 70-79 | ec | 9.3 | 0.7 | 12 |
| 70-79 | eo | 10.1 | 1.1 | 12 |

### Theta/Beta ratio range

Mean TBR should be 0.1-20.0 (typical healthy adults: 1.5-4.0)

- **Reference:** Arns et al. (2013); Snyder et al. (2015)
- **Result:** PASS
- **Cells:** 228/228 correct

### Relative power sums to ~1.0

Sum of relative power across non-overlapping bands should be ~1.0 (tolerance: 0.85-1.15)

- **Reference:** Basic spectral sanity check
- **Result:** PASS
- **Cells:** 228/228 correct

### GSF consistency across age bins

GSF should be similar across age bins (CV < 10%). Large variation suggests equipment differences.

- **Reference:** GSF reflects amplifier gain and skull thickness, not age-related neural changes
- **Result:** PASS
- **GSF means:** [-12.74, -12.82, -12.84, -12.89, -12.86, -12.88]
- **CV:** 0.004
- **GSF means:** [-12.86, -12.98, -12.99, -12.95, -12.96, -13.04]
- **CV:** 0.004

---

## Cross-Dataset Agreement

Comparing **LEMON** (421 subjects) vs **Dortmund** (971 subjects) in overlapping age bins.

- **Global correlation of normative means:** r = 0.9128 (p = 0.00e+00) -- good
- **Overlapping bins:** ['20-29', '30-39', '50-59', '60-69', '70-79']
- **Common cells:** 31,275

### Agreement by Age Bin

| Bin | r | Mean |d| | N (A) | N (B) |
|-----|---|---------|-------|-------|
| 20-29 | 0.985 | 0.151 | 126 | 109 |
| 30-39 | 0.929 | 0.250 | 12 | 89 |
| 50-59 | 0.916 | 0.313 | 4 | 121 |
| 60-69 | 0.969 | 0.186 | 39 | 67 |
| 70-79 | 0.914 | 0.383 | 22 | 12 |

### Agreement by Metric

| Metric | r | Mean |d| | Max |d| | Agreement |
|--------|---|---------|---------|-----------|
| absolute_power | nan | 0.222 | 0.970 | poor |
| aperiodic_exponent | 0.896 | 0.250 | 0.875 | moderate |
| aperiodic_offset | 0.897 | 0.194 | 1.088 | moderate |
| asymmetry_index | 0.223 | 0.227 | 1.302 | poor |
| char_path_length | 0.886 | 0.268 | 1.008 | moderate |
| coh_hub_C_mid | 0.996 | 0.230 | 0.853 | good |
| coh_hub_F_L | 0.996 | 0.230 | 0.853 | good |
| coh_hub_F_R | 0.987 | 0.290 | 0.964 | good |
| coh_hub_F_mid | nan | 0.000 | 0.000 | poor |
| coh_hub_O | 0.990 | 0.214 | 0.694 | good |
| coh_hub_P_L | 0.974 | 0.300 | 0.964 | good |
| coh_hub_P_R | 0.994 | 0.263 | 0.876 | good |
| coh_hub_P_mid | 0.986 | 0.248 | 0.848 | good |
| coh_hub_T_L | 0.976 | 0.313 | 0.971 | good |
| coh_hub_T_R | 0.995 | 0.281 | 0.971 | good |
| coh_node_strength | 0.981 | 0.309 | 1.597 | good |
| corrected_absolute_power | nan | 0.255 | 2.546 | poor |
| corrected_relative_power | 0.954 | 0.297 | 2.092 | good |
| dwpli_hub_C_mid | 0.955 | 0.238 | 0.586 | good |
| dwpli_hub_F_L | 0.955 | 0.238 | 0.586 | good |
| dwpli_hub_F_R | 0.908 | 0.263 | 1.315 | good |
| dwpli_hub_F_mid | nan | 0.000 | 0.000 | poor |
| dwpli_hub_O | 0.910 | 0.250 | 0.925 | good |
| dwpli_hub_P_L | 0.894 | 0.263 | 1.530 | moderate |
| dwpli_hub_P_R | 0.904 | 0.270 | 1.530 | good |
| dwpli_hub_P_mid | 0.907 | 0.271 | 1.315 | good |
| dwpli_hub_T_L | 0.930 | 0.269 | 1.193 | good |
| dwpli_hub_T_R | 0.951 | 0.238 | 1.007 | good |
| dwpli_node_strength | 0.918 | 0.257 | 1.301 | good |
| global_efficiency | 0.156 | 0.271 | 1.445 | poor |
| gsf | 0.553 | 0.316 | 0.553 | poor |
| gsf_absolute_power | 0.871 | 0.223 | 1.865 | moderate |
| gsf_relative_power | 0.941 | 0.263 | 1.884 | good |
| iaf_cog | 0.526 | 0.266 | 1.017 | poor |
| iaf_peak | 0.564 | 0.265 | 1.118 | poor |
| imcoh_hub_C_mid | 0.969 | 0.241 | 0.673 | good |
| imcoh_hub_F_L | 0.969 | 0.241 | 0.673 | good |
| imcoh_hub_F_R | 0.947 | 0.249 | 1.358 | good |
| imcoh_hub_F_mid | nan | 0.000 | 0.000 | poor |
| imcoh_hub_O | 0.953 | 0.239 | 0.774 | good |
| imcoh_hub_P_L | 0.928 | 0.255 | 1.191 | good |
| imcoh_hub_P_R | 0.942 | 0.272 | 1.000 | good |
| imcoh_hub_P_mid | 0.933 | 0.275 | 1.358 | good |
| imcoh_hub_T_L | 0.935 | 0.287 | 1.300 | good |
| imcoh_hub_T_R | 0.953 | 0.261 | 1.300 | good |
| pac_mi | -0.084 | 0.304 | 1.579 | poor |
| relative_power | 0.941 | 0.263 | 1.884 | good |
| value | 0.922 | 0.251 | 1.290 | good |

### Largest Disagreements

| Bin | Cond | Channel | Band | Metric | d | A mean | B mean |
|-----|------|---------|------|--------|---|--------|--------|
| 50-59 | ec | T4 | HighBeta | corrected_absolute_power | 2.55 | 0.000 | 0.000 |
| 50-59 | ec | C3 | HighBeta | corrected_absolute_power | 2.13 | 0.000 | 0.000 |
| 50-59 | ec | C3 | HighBeta | corrected_relative_power | 2.09 | 0.162 | 0.083 |
| 50-59 | ec | P4 | HighBeta | corrected_absolute_power | 1.99 | 0.000 | 0.000 |
| 50-59 | ec | T4 | HighBeta | corrected_relative_power | 1.98 | 0.139 | 0.075 |
| 50-59 | eo | P3 | HighBeta | corrected_relative_power | 1.94 | 0.146 | 0.086 |
| 50-59 | ec | P4 | HighBeta | corrected_relative_power | 1.91 | 0.131 | 0.062 |
| 50-59 | ec | P3 | HighBeta | corrected_absolute_power | 1.90 | 0.000 | 0.000 |
| 50-59 | ec | F8 | HighBeta | corrected_relative_power | 1.89 | 0.126 | 0.074 |
| 50-59 | ec | C3 | HighBeta | gsf_relative_power | 1.88 | 0.082 | 0.037 |

---

## Methodology

This report was generated by `open-normative-eeg` validation scripts.
All checks are automated and reproducible. Source code and methodology
are open source at https://github.com/peak-mind-llc/open-normative-eeg.

### References

- Barry et al. (2007, 2009) -- EO vs EC alpha differences
- Corcoran et al. (2018) -- IAF estimation methods
- Craiu et al. (2025) -- Aperiodic normative characterization
- Donoghue et al. (2020) -- specparam / FOOOF
- Klimesch (1999) -- Alpha oscillation frequency
- Niedermeyer & da Silva (2005) -- EEG fundamentals
- Voytek et al. (2015) -- Aperiodic slope and aging
