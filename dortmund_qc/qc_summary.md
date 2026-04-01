# Dortmund Vital Study EEG — QC Report

**Generated:** 2026-04-01 13:22 UTC
**Total subjects:** 608

## Summary

| Verdict | Count |
|---------|-------|
| Pass    | 0 |
| Warn    | 491 |
| Fail    | 117 |
| **Normative-eligible** | **491** |

## BIDS Task Discovery

- **EyesClosed**: 1632 files (runs: none, acqs: post, pre)
- **EyesOpen**: 1632 files (runs: none, acqs: post, pre)

## Session Inventory

- Session 1 only: 400
- Session 1 + Session 2: 208
- **Session 2 subjects are flagged for longitudinal analysis only**

## Issue Frequency

| Issue | Count |
|-------|-------|
| [EO] large DC offset (>100.0 uV) | 608 |
| [EC] large DC offset (>100.0 uV) | 608 |
| [EC] railed channels (>500.0 uV >10%) | 515 |
| [EO] excessive 50 Hz noise | 436 |
| [EO] railed channels (>500.0 uV >10%) | 418 |
| [EC] excessive 50 Hz noise | 416 |
| [EC] gross artifact | 190 |
| [EO] gross artifact | 139 |
| [EC] median amplitude | 51 |
| [EO] median amplitude | 44 |
| [EC] duration | 1 |

## Channel Issues Across Subjects

| Channel | Flat | Railed | 50 Hz Noise |
|---------|------|--------|-------------|
| AF3 | 0 | 148 | 113 |
| AF4 | 0 | 159 | 60 |
| AF7 | 0 | 211 | 67 |
| AF8 | 0 | 236 | 43 |
| C1 | 0 | 99 | 2 |
| C2 | 0 | 106 | 5 |
| C3 | 0 | 85 | 2 |
| C4 | 0 | 79 | 3 |
| C5 | 0 | 101 | 8 |
| C6 | 0 | 89 | 5 |
| CP1 | 0 | 98 | 2 |
| CP2 | 0 | 87 | 7 |
| CP3 | 0 | 83 | 1 |
| CP4 | 0 | 90 | 0 |
| CP5 | 0 | 138 | 36 |
| CP6 | 0 | 96 | 1 |
| CPz | 0 | 91 | 0 |
| Cz | 0 | 105 | 9 |
| F1 | 0 | 98 | 2 |
| F2 | 0 | 113 | 1 |
| F3 | 0 | 141 | 7 |
| F4 | 0 | 137 | 4 |
| F5 | 0 | 206 | 19 |
| F6 | 0 | 144 | 8 |
| F7 | 0 | 160 | 41 |
| F8 | 0 | 162 | 16 |
| FC1 | 0 | 97 | 3 |
| FC2 | 0 | 117 | 5 |
| FC3 | 0 | 119 | 24 |
| FC4 | 0 | 93 | 2 |
| FC5 | 0 | 96 | 25 |
| FC6 | 0 | 85 | 27 |
| FT10 | 0 | 208 | 9 |
| FT7 | 0 | 134 | 21 |
| FT8 | 0 | 158 | 37 |
| FT9 | 0 | 186 | 6 |
| Fp1 | 0 | 182 | 66 |
| Fp2 | 0 | 200 | 25 |
| Fz | 0 | 75 | 75 |
| O1 | 0 | 136 | 9 |
| O2 | 0 | 122 | 6 |
| Oz | 0 | 147 | 2 |
| P1 | 0 | 95 | 0 |
| P2 | 0 | 86 | 0 |
| P3 | 0 | 98 | 0 |
| P4 | 0 | 92 | 1 |
| P5 | 0 | 113 | 1 |
| P6 | 0 | 112 | 7 |
| P7 | 0 | 124 | 3 |
| P8 | 0 | 125 | 2 |
| PO10 | 0 | 152 | 57 |
| PO3 | 0 | 123 | 4 |
| PO4 | 0 | 121 | 3 |
| PO7 | 0 | 132 | 4 |
| PO8 | 0 | 124 | 8 |
| PO9 | 0 | 137 | 41 |
| POz | 0 | 122 | 1 |
| Pz | 0 | 111 | 0 |
| T7 | 0 | 134 | 72 |
| T8 | 0 | 140 | 70 |
| TP10 | 0 | 202 | 42 |
| TP7 | 0 | 136 | 21 |
| TP8 | 0 | 123 | 10 |
| TP9 | 0 | 204 | 65 |

## Age x Sex Distribution (Normative-Eligible Subjects)

| Age Bin | Male | Female | Unknown | Total | Thin? |
|---------|------|--------|---------|-------|-------|
| 20-24 | 9 | 37 | 0 | 46 |  |
| 25-29 | 20 | 45 | 0 | 65 |  |
| 30-34 | 22 | 31 | 0 | 53 |  |
| 35-39 | 17 | 20 | 0 | 37 |  |
| 40-44 | 11 | 24 | 0 | 35 |  |
| 45-49 | 18 | 36 | 0 | 54 |  |
| 50-54 | 20 | 48 | 0 | 68 |  |
| 55-59 | 21 | 32 | 0 | 53 |  |
| 60-64 | 14 | 24 | 0 | 38 |  |
| 65-70 | 22 | 20 | 0 | 42 |  |

### Decade Bins

| Age Bin | Male | Female | Total | Thin? |
|---------|------|--------|-------|-------|
| 20-29 | 29 | 82 | 111 |  |
| 30-39 | 39 | 51 | 90 |  |
| 40-49 | 29 | 60 | 89 |  |
| 50-59 | 41 | 80 | 121 |  |
| 60-70 | 36 | 44 | 80 |  |

## Excluded Subjects

| Subject | Issues |
|---------|--------|
| sub-004 | [EO] median amplitude=213.4 uV, exceeds 200.0; [EO] gross artifact=67.8%, exceeds 50.0% |
| sub-009 | [EC] median amplitude=202.0 uV, exceeds 200.0; [EC] gross artifact=60.6%, exceeds 50.0% |
| sub-014 | [EC] median amplitude=269.3 uV, exceeds 200.0; [EC] gross artifact=83.1%, exceeds 50.0% |
| sub-015 | [EO] median amplitude=285.0 uV, exceeds 200.0; [EO] gross artifact=72.0%, exceeds 50.0%; [EC] gross artifact=56.5%, e... |
| sub-021 | [EC] gross artifact=50.8%, exceeds 50.0% |
| sub-026 | [EO] median amplitude=888.9 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0%; [EC] median amplitude=460.9... |
| sub-035 | [EO] gross artifact=59.5%, exceeds 50.0%; [EC] median amplitude=235.8 uV, exceeds 200.0; [EC] gross artifact=56.3%, e... |
| sub-043 | [EO] gross artifact=50.3%, exceeds 50.0%; [EC] median amplitude=217.6 uV, exceeds 200.0; [EC] gross artifact=64.3%, e... |
| sub-052 | [EO] median amplitude=387.7 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0%; [EC] gross artifact=55.7%, ... |
| sub-055 | [EO] median amplitude=210.7 uV, exceeds 200.0; [EO] gross artifact=70.9%, exceeds 50.0%; [EC] median amplitude=346.8 ... |
| sub-059 | [EO] median amplitude=331.3 uV, exceeds 200.0; [EO] gross artifact=89.2%, exceeds 50.0%; [EC] median amplitude=345.7 ... |
| sub-066 | [EO] gross artifact=56.3%, exceeds 50.0%; [EC] median amplitude=359.0 uV, exceeds 200.0; [EC] gross artifact=81.8%, e... |
| sub-071 | [EO] gross artifact=53.6%, exceeds 50.0%; [EC] gross artifact=52.5%, exceeds 50.0% |
| sub-077 | [EC] median amplitude=349.9 uV, exceeds 200.0; [EC] gross artifact=80.0%, exceeds 50.0% |
| sub-079 | [EO] gross artifact=56.3%, exceeds 50.0%; [EC] median amplitude=534.0 uV, exceeds 200.0; [EC] gross artifact=84.7%, e... |
| sub-080 | [EC] gross artifact=57.7%, exceeds 50.0% |
| sub-092 | [EC] gross artifact=54.4%, exceeds 50.0% |
| sub-100 | [EC] median amplitude=346.4 uV, exceeds 200.0; [EC] gross artifact=80.3%, exceeds 50.0% |
| sub-105 | [EO] gross artifact=69.2%, exceeds 50.0%; [EC] gross artifact=58.8%, exceeds 50.0% |
| sub-111 | [EC] gross artifact=51.6%, exceeds 50.0% |
| sub-113 | [EC] median amplitude=646.1 uV, exceeds 200.0; [EC] gross artifact=100.0%, exceeds 50.0% |
| sub-118 | [EO] median amplitude=315.5 uV, exceeds 200.0; [EO] gross artifact=74.6%, exceeds 50.0%; [EC] gross artifact=60.5%, e... |
| sub-120 | [EO] median amplitude=201.0 uV, exceeds 200.0; [EO] gross artifact=62.3%, exceeds 50.0%; [EC] gross artifact=51.9%, e... |
| sub-121 | [EO] median amplitude=303.8 uV, exceeds 200.0; [EO] gross artifact=78.0%, exceeds 50.0%; [EC] median amplitude=500.8 ... |
| sub-135 | [EC] median amplitude=333.3 uV, exceeds 200.0; [EC] gross artifact=81.4%, exceeds 50.0% |
| sub-137 | [EO] median amplitude=267.2 uV, exceeds 200.0; [EO] gross artifact=78.5%, exceeds 50.0%; [EC] median amplitude=355.4 ... |
| sub-140 | [EO] gross artifact=53.8%, exceeds 50.0%; [EC] median amplitude=253.8 uV, exceeds 200.0; [EC] gross artifact=74.9%, e... |
| sub-144 | [EO] median amplitude=222.2 uV, exceeds 200.0; [EO] gross artifact=64.7%, exceeds 50.0%; [EC] median amplitude=361.2 ... |
| sub-167 | [EO] gross artifact=59.3%, exceeds 50.0% |
| sub-183 | [EC] gross artifact=59.0%, exceeds 50.0% |
| sub-194 | [EC] median amplitude=235.7 uV, exceeds 200.0; [EC] gross artifact=63.6%, exceeds 50.0% |
| sub-196 | [EO] median amplitude=388.3 uV, exceeds 200.0; [EO] gross artifact=93.5%, exceeds 50.0% |
| sub-203 | [EO] median amplitude=214.1 uV, exceeds 200.0; [EO] gross artifact=62.1%, exceeds 50.0%; [EC] median amplitude=278.6 ... |
| sub-207 | [EC] gross artifact=60.1%, exceeds 50.0% |
| sub-208 | [EC] gross artifact=55.6%, exceeds 50.0% |
| sub-210 | [EO] median amplitude=369.7 uV, exceeds 200.0; [EO] gross artifact=95.6%, exceeds 50.0%; [EC] median amplitude=304.2 ... |
| sub-222 | [EO] median amplitude=421.2 uV, exceeds 200.0; [EO] gross artifact=91.4%, exceeds 50.0%; [EC] median amplitude=247.2 ... |
| sub-230 | [EO] median amplitude=623.9 uV, exceeds 200.0; [EO] gross artifact=89.1%, exceeds 50.0%; [EC] duration=1.0 min, below... |
| sub-235 | [EO] gross artifact=60.1%, exceeds 50.0%; [EC] median amplitude=225.5 uV, exceeds 200.0; [EC] gross artifact=63.2%, e... |
| sub-238 | [EO] median amplitude=269.0 uV, exceeds 200.0; [EO] gross artifact=71.2%, exceeds 50.0%; [EC] median amplitude=207.6 ... |
| sub-247 | [EC] gross artifact=56.3%, exceeds 50.0% |
| sub-253 | [EO] median amplitude=951.1 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0%; [EC] median amplitude=307.7... |
| sub-257 | [EO] median amplitude=247.5 uV, exceeds 200.0; [EO] gross artifact=80.6%, exceeds 50.0%; [EC] gross artifact=51.4%, e... |
| sub-274 | [EC] gross artifact=56.8%, exceeds 50.0% |
| sub-285 | [EC] gross artifact=53.0%, exceeds 50.0% |
| sub-289 | [EO] median amplitude=242.1 uV, exceeds 200.0; [EO] gross artifact=68.1%, exceeds 50.0%; [EC] median amplitude=220.9 ... |
| sub-292 | [EC] median amplitude=201.5 uV, exceeds 200.0; [EC] gross artifact=61.7%, exceeds 50.0% |
| sub-305 | [EC] median amplitude=478.8 uV, exceeds 200.0; [EC] gross artifact=88.0%, exceeds 50.0% |
| sub-312 | [EC] median amplitude=202.2 uV, exceeds 200.0; [EC] gross artifact=59.2%, exceeds 50.0% |
| sub-316 | [EC] gross artifact=51.6%, exceeds 50.0% |
| sub-320 | [EC] median amplitude=250.8 uV, exceeds 200.0; [EC] gross artifact=64.5%, exceeds 50.0% |
| sub-322 | [EO] median amplitude=962.0 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0% |
| sub-323 | [EO] gross artifact=55.6%, exceeds 50.0% |
| sub-324 | [EO] gross artifact=56.8%, exceeds 50.0% |
| sub-330 | [EC] median amplitude=231.2 uV, exceeds 200.0; [EC] gross artifact=67.3%, exceeds 50.0% |
| sub-338 | [EC] gross artifact=56.7%, exceeds 50.0% |
| sub-339 | [EO] median amplitude=273.8 uV, exceeds 200.0; [EO] gross artifact=69.6%, exceeds 50.0%; [EC] median amplitude=296.6 ... |
| sub-342 | [EO] median amplitude=545.9 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0%; [EC] median amplitude=244.7... |
| sub-348 | [EC] gross artifact=53.7%, exceeds 50.0% |
| sub-360 | [EO] median amplitude=252.6 uV, exceeds 200.0; [EO] gross artifact=78.8%, exceeds 50.0% |
| sub-362 | [EO] median amplitude=239.9 uV, exceeds 200.0; [EO] gross artifact=76.5%, exceeds 50.0%; [EC] gross artifact=65.4%, e... |
| sub-365 | [EO] median amplitude=281.7 uV, exceeds 200.0; [EO] gross artifact=82.8%, exceeds 50.0%; [EC] median amplitude=290.8 ... |
| sub-371 | [EO] median amplitude=391.2 uV, exceeds 200.0; [EO] gross artifact=78.4%, exceeds 50.0%; [EC] median amplitude=546.4 ... |
| sub-375 | [EO] median amplitude=314.3 uV, exceeds 200.0; [EO] gross artifact=74.3%, exceeds 50.0%; [EC] gross artifact=60.0%, e... |
| sub-376 | [EC] median amplitude=229.9 uV, exceeds 200.0; [EC] gross artifact=77.7%, exceeds 50.0% |
| sub-378 | [EO] median amplitude=202.8 uV, exceeds 200.0; [EO] gross artifact=63.9%, exceeds 50.0%; [EC] median amplitude=211.3 ... |
| sub-380 | [EO] gross artifact=56.9%, exceeds 50.0% |
| sub-384 | [EO] median amplitude=382.9 uV, exceeds 200.0; [EO] gross artifact=83.3%, exceeds 50.0% |
| sub-386 | [EO] median amplitude=243.2 uV, exceeds 200.0; [EO] gross artifact=66.7%, exceeds 50.0%; [EC] median amplitude=217.4 ... |
| sub-389 | [EC] gross artifact=51.1%, exceeds 50.0% |
| sub-391 | [EO] gross artifact=70.6%, exceeds 50.0%; [EC] median amplitude=221.6 uV, exceeds 200.0; [EC] gross artifact=75.7%, e... |
| sub-404 | [EC] gross artifact=52.4%, exceeds 50.0% |
| sub-409 | [EC] median amplitude=216.3 uV, exceeds 200.0; [EC] gross artifact=67.7%, exceeds 50.0% |
| sub-411 | [EO] median amplitude=348.4 uV, exceeds 200.0; [EO] gross artifact=75.9%, exceeds 50.0%; [EC] median amplitude=568.7 ... |
| sub-412 | [EC] median amplitude=210.3 uV, exceeds 200.0; [EC] gross artifact=59.1%, exceeds 50.0% |
| sub-414 | [EO] gross artifact=51.9%, exceeds 50.0% |
| sub-415 | [EO] median amplitude=887.9 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0% |
| sub-420 | [EC] gross artifact=69.9%, exceeds 50.0% |
| sub-425 | [EC] median amplitude=203.0 uV, exceeds 200.0; [EC] gross artifact=63.8%, exceeds 50.0% |
| sub-429 | [EC] gross artifact=51.9%, exceeds 50.0% |
| sub-433 | [EO] gross artifact=55.1%, exceeds 50.0%; [EC] median amplitude=284.1 uV, exceeds 200.0; [EC] gross artifact=70.1%, e... |
| sub-438 | [EC] gross artifact=67.6%, exceeds 50.0% |
| sub-448 | [EC] gross artifact=61.0%, exceeds 50.0% |
| sub-453 | [EO] gross artifact=63.9%, exceeds 50.0% |
| sub-458 | [EC] gross artifact=57.1%, exceeds 50.0% |
| sub-460 | [EC] gross artifact=57.7%, exceeds 50.0% |
| sub-463 | [EO] median amplitude=282.5 uV, exceeds 200.0; [EO] gross artifact=70.7%, exceeds 50.0%; [EC] median amplitude=476.4 ... |
| sub-465 | [EO] gross artifact=55.8%, exceeds 50.0% |
| sub-472 | [EO] gross artifact=65.3%, exceeds 50.0% |
| sub-473 | [EO] gross artifact=52.5%, exceeds 50.0% |
| sub-474 | [EO] median amplitude=882.6 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0% |
| sub-491 | [EO] median amplitude=248.9 uV, exceeds 200.0; [EO] gross artifact=75.6%, exceeds 50.0%; [EC] gross artifact=75.8%, e... |
| sub-492 | [EO] gross artifact=56.5%, exceeds 50.0% |
| sub-493 | [EC] median amplitude=1779.4 uV, exceeds 200.0; [EC] gross artifact=100.0%, exceeds 50.0% |
| sub-494 | [EC] gross artifact=55.7%, exceeds 50.0% |
| sub-503 | [EO] median amplitude=215.8 uV, exceeds 200.0; [EO] gross artifact=74.3%, exceeds 50.0% |
| sub-505 | [EO] gross artifact=59.8%, exceeds 50.0%; [EC] gross artifact=62.0%, exceeds 50.0% |
| sub-506 | [EC] gross artifact=58.8%, exceeds 50.0% |
| sub-517 | [EO] median amplitude=329.7 uV, exceeds 200.0; [EO] gross artifact=79.5%, exceeds 50.0% |
| sub-518 | [EO] median amplitude=223.7 uV, exceeds 200.0; [EO] gross artifact=74.1%, exceeds 50.0%; [EC] median amplitude=271.6 ... |
| sub-526 | [EO] median amplitude=259.4 uV, exceeds 200.0; [EO] gross artifact=93.2%, exceeds 50.0%; [EC] median amplitude=560.4 ... |
| sub-534 | [EC] gross artifact=61.7%, exceeds 50.0% |
| sub-536 | [EC] gross artifact=59.1%, exceeds 50.0% |
| sub-541 | [EC] gross artifact=57.4%, exceeds 50.0% |
| sub-542 | [EC] gross artifact=53.0%, exceeds 50.0% |
| sub-545 | [EC] gross artifact=68.5%, exceeds 50.0% |
| sub-547 | [EO] median amplitude=313.2 uV, exceeds 200.0; [EO] gross artifact=90.2%, exceeds 50.0% |
| sub-550 | [EC] gross artifact=53.8%, exceeds 50.0% |
| sub-553 | [EC] median amplitude=276.3 uV, exceeds 200.0; [EC] gross artifact=75.3%, exceeds 50.0% |
| sub-554 | [EC] gross artifact=62.0%, exceeds 50.0% |
| sub-557 | [EC] median amplitude=327.2 uV, exceeds 200.0; [EC] gross artifact=82.4%, exceeds 50.0% |
| sub-562 | [EO] median amplitude=310.0 uV, exceeds 200.0; [EO] gross artifact=84.9%, exceeds 50.0% |
| sub-566 | [EO] gross artifact=62.6%, exceeds 50.0%; [EC] gross artifact=68.6%, exceeds 50.0% |
| sub-577 | [EO] median amplitude=482.2 uV, exceeds 200.0; [EO] gross artifact=100.0%, exceeds 50.0% |
| sub-590 | [EO] median amplitude=298.3 uV, exceeds 200.0; [EO] gross artifact=76.0%, exceeds 50.0% |
| sub-598 | [EC] median amplitude=287.0 uV, exceeds 200.0; [EC] gross artifact=71.6%, exceeds 50.0% |
| sub-605 | [EO] gross artifact=66.7%, exceeds 50.0%; [EC] median amplitude=328.8 uV, exceeds 200.0; [EC] gross artifact=73.8%, e... |

## Pre-Task vs Post-Task Comparison

Compared 20 subjects to validate pre-task-only normative decision.

| Band | Mean Diff (log10) | Cohen's d |
|------|-------------------|-----------|
| Delta | -0.0137 | -0.012 |
| Theta | +0.0788 | +0.079 |
| Alpha | +0.1044 | +0.120 |
| Beta | +0.0654 | +0.088 |

Mean alpha peak shift: -0.15 Hz

**Findings:**
- No strong pre/post differences detected in this sample

## Per-Subject Results

| Subject | Status | Session 2 | Pre-EO | Pre-EC | Issues |
|---------|--------|-----------|--------|--------|--------|
| sub-001 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8; [warn] [EO] large DC offset... |
| sub-002 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, FC6, CP5, FC4, CP4; [warn]... |
| sub-003 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Oz; [warn] [EO] large DC offset... |
| sub-004 | fail |  | yes | yes | [fail] [EO] median amplitude=213.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-005 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7, AF8, C2; [warn] [EO] large... |
| sub-006 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-007 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP5; [warn] [EO] excessive 50 H... |
| sub-008 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO8; [warn] [EO] excessive 50 H... |
| sub-009 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP2, FC3, POz; [warn] [EO] exce... |
| sub-010 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC4; [warn] [EO] excessive 50 H... |
| sub-011 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1; [warn] [EO] excessive 50 H... |
| sub-012 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF4; [warn] [EO] excessive 50 H... |
| sub-013 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, AF7; [warn] [EO] excessive... |
| sub-014 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, CP5, P7, O1, O2, FT10, TP7,... |
| sub-015 | fail |  | yes | yes | [fail] [EO] median amplitude=285.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-016 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, PO9, PO10; [warn] [EO] exc... |
| sub-017 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, P3; [warn] [EO] large DC of... |
| sub-018 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, PO7; [warn] [EO] excessive... |
| sub-019 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO4; [warn] [EO] excessive 50 H... |
| sub-020 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EO] large DC offset (>100.0 u... |
| sub-021 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, TP10, FT8; [warn] [EO]... |
| sub-022 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, CP4; [warn] [EO] excessive... |
| sub-023 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: O2; [warn] [EO] large DC offset (>100.0 uV... |
| sub-024 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, Fz; [warn] [EO] large DC offset (>100... |
| sub-025 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, FT10; [warn] [EO] excessiv... |
| sub-026 | fail |  | yes | yes | [fail] [EO] median amplitude=888.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-027 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, FC3, PO4; [warn] [EO] exces... |
| sub-028 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, AF7; [warn] [EO] large DC offset (>100... |
| sub-029 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT8; [warn] [EO] large DC offse... |
| sub-030 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] large DC offset (>100.0 u... |
| sub-031 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7; [warn] [EO] excessive 50 H... |
| sub-032 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, F7, Fz, F8, FC5, FC1, FC2, FC6,... |
| sub-033 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, FC1, FT10; [warn] [EO] exce... |
| sub-034 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-035 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, FC2, Pz, P4, PO10, F5, FT10... |
| sub-036 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EO] large DC offset (>100.0 u... |
| sub-037 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, FC4; [warn] [EO] large DC ... |
| sub-038 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, FC6, AF7, AF8, F6, FT8, TP8... |
| sub-039 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, AF3; [warn] [EO] excessive... |
| sub-040 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF7; [warn] [EO] large DC ... |
| sub-041 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P7, P3, FC4; [warn] [EO] excess... |
| sub-042 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, AF7, AF3, AF8, FT10; ... |
| sub-043 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F3, AF7, F5, FC4; [warn] [... |
| sub-044 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [warn] [EO] large DC offset (>10... |
| sub-045 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, T8, AF7; [warn] [EO] e... |
| sub-046 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F8, FC2, T7, C... |
| sub-047 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F6; [warn] [EO] excessive 50 Hz... |
| sub-048 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C2; [warn] [EO] excessive 50 Hz... |
| sub-049 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3; [warn] [EO] excessive 50 Hz... |
| sub-050 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EO] large DC offset (>100.0 u... |
| sub-051 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, C1; [warn] [EO] large DC of... |
| sub-052 | fail | yes | yes | yes | [fail] [EO] median amplitude=387.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-053 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF8; [warn] [EO] large DC offset (>10... |
| sub-054 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz; [warn] [EO] large DC offset... |
| sub-055 | fail |  | yes | yes | [fail] [EO] median amplitude=210.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-056 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C2; [warn] [EO] excessive 50 Hz... |
| sub-057 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1, P3, FT9; [warn] [EO] large... |
| sub-058 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8, CPz; [warn] [EO] excessive... |
| sub-059 | fail | yes | yes | yes | [fail] [EO] median amplitude=331.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-060 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-061 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, T7, TP10, AF4, F5, F2; [war... |
| sub-062 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F8, FC5, FC1, ... |
| sub-063 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC5, FT10, C5; [warn] [EO] larg... |
| sub-064 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8, O2, FT9, PO7; [warn] [EO] e... |
| sub-065 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP6, P8, FT9, TP8, P6; [warn] [... |
| sub-066 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F8, FC5, TP9, CP5... |
| sub-067 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, AF7, CPz; [warn] [EO] exce... |
| sub-068 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7, AF4, F2, C2; [warn] [EO] l... |
| sub-069 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP8; [warn] [EO] large DC offset (>100.0 u... |
| sub-070 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8, FT9; [warn] [EO] large DC o... |
| sub-071 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, CP5, PO9, PO10, AF7, C1, C... |
| sub-072 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C2; [warn] [EO] excessive 50 Hz... |
| sub-073 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT9, FT7; [warn] [EO] excessive... |
| sub-074 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8; [warn] [EO] excessive 50 Hz... |
| sub-075 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, O1, Oz, AF4, AF8, F5, FC4, ... |
| sub-076 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, C2; [warn] [EO] large DC of... |
| sub-077 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO3; [warn] [EO] excessive 50 H... |
| sub-078 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-079 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, Fz, F4, F8, FC5, FC2, T7, C... |
| sub-080 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC6, T8, CP5, CP2, F6, FC4, C1,... |
| sub-081 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F1; [warn] [EO] excessive 50 Hz... |
| sub-082 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, AF7, PO4; [warn] [EO]... |
| sub-083 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, FC1, PO10; [warn] [EO... |
| sub-084 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] excessive 50 ... |
| sub-085 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F4, F8, T7, TP9, ... |
| sub-086 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] excessive 50 ... |
| sub-087 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, PO10; [warn] [EO] large DC offset (>1... |
| sub-088 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-089 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, F4, AF4, AF8, F5, F6, ... |
| sub-090 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-091 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-092 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, AF7, FT7, FT10; [warn] [EO]... |
| sub-093 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz, Oz, C2; [warn] [EO] excessi... |
| sub-094 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-095 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-096 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9, FT9; [warn] [EO] large DC ... |
| sub-097 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, TP10; [warn] [EO] large DC offset (>10... |
| sub-098 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-099 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7; [warn] [EO] large DC offse... |
| sub-100 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9, CPz; [warn] [EO] excessive... |
| sub-101 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-102 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, CP2, F5, FC3, P5; [warn] [... |
| sub-103 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT9; [warn] [EO] excessive 50 H... |
| sub-104 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F3, CP5, Pz, AF3, AF4, F5,... |
| sub-105 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, FC2, Cz, TP10, P7, Pz, P8,... |
| sub-106 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EO] large DC offset (>10... |
| sub-107 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8; [warn] [EO] large DC offset... |
| sub-108 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, P4, P8, O1, Oz, AF7, FC3, C... |
| sub-109 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-110 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, F4, F8, FC1, T7, Cz, T... |
| sub-111 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F4, F8, CP6, AF7, AF4, AF8... |
| sub-112 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C2; [warn] [EO] excessive 50 Hz... |
| sub-113 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F3, F8, P7, P3, P8, P... |
| sub-114 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, CP2, FT9, CPz, PO3; [warn] ... |
| sub-115 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, AF8, TP8; [warn] [EO] exce... |
| sub-116 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3, CP5, F5, F6, FT9, FC3; [war... |
| sub-117 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F8, AF7, AF3, AF4... |
| sub-118 | fail |  | yes | yes | [fail] [EO] median amplitude=315.5 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-119 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, FT9, TP7; [warn] [EO] lar... |
| sub-120 | fail |  | yes | yes | [fail] [EO] median amplitude=201.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-121 | fail |  | yes | yes | [fail] [EO] median amplitude=303.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-122 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP2, FC3; [warn] [EO] large DC offset (>10... |
| sub-123 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] excessive 50 ... |
| sub-124 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-125 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, P2; [warn] [EO] exces... |
| sub-126 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F5, TP7; [warn] [EO] large DC offset (>100... |
| sub-127 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP5, C1; [warn] [EO] excessive ... |
| sub-128 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2; [warn] [EO] excessive 50 H... |
| sub-129 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, P4, O1, FC4, C1, C2, PO3;... |
| sub-130 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C4, CP2, F5; [warn] [EO] excess... |
| sub-131 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P8, F5; [warn] [EO] excessive 5... |
| sub-132 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] large DC offset (>100.0 u... |
| sub-133 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-134 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Cz, AF4, AF8; [warn] [EO] ... |
| sub-135 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F2; [warn] [EO] excessive 50 Hz... |
| sub-136 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] excessive 50 ... |
| sub-137 | fail | yes | yes | yes | [fail] [EO] median amplitude=267.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-138 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F3, Fz, F8, FC5, FC1, FC6,... |
| sub-139 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, TP7; [warn] [EO] large DC offset (>10... |
| sub-140 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP6, P3, PO10, F5, FC4, FT8, C5... |
| sub-141 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, Fz, F4, FC5, FC1, FC2, ... |
| sub-142 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, PO10, FT10, PO8; [warn] [E... |
| sub-143 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-144 | fail |  | yes | yes | [fail] [EO] median amplitude=222.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-145 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, Cz, O1, PO10; [warn] [EO] e... |
| sub-146 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP7; [warn] [EO] excessive 50 H... |
| sub-147 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F8, FC5, FC1, ... |
| sub-148 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] excessive 50 ... |
| sub-149 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP10; [warn] [EO] large DC offset (>100.0 ... |
| sub-150 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7; [warn] [EO] excessive 50 Hz... |
| sub-151 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EO] large DC offset (>100.0 u... |
| sub-152 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, PO10; [warn] [EO] large DC offset (>1... |
| sub-153 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3, P7, C1; [warn] [EO] excessi... |
| sub-154 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, C4, P3, FT7, C2, CP3, CP4,... |
| sub-155 | warn |  | yes | yes | [warn] [EO] gross artifact=27.8%, exceeds 20.0%; [warn] [EO] large DC offset ... |
| sub-156 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Oz; [warn] [EO] excessive 50 Hz... |
| sub-157 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P2; [warn] [EO] large DC offset... |
| sub-158 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-159 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10; [warn] [EO] large DC offset (>1... |
| sub-160 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-161 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1; [warn] [EO] excessive 50 H... |
| sub-162 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz, AF3; [warn] [EO] excessive ... |
| sub-163 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F1, C1, C6, PO7, PO3, PO4; [war... |
| sub-164 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3; [warn] [EO] excessive 50 Hz... |
| sub-165 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7; [warn] [EO] large DC offset (>10... |
| sub-166 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FC5, FT7; [warn] [EO] large DC offset ... |
| sub-167 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, FC5, T7, CP6, TP10, P8, Oz,... |
| sub-168 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, AF8; [warn] [EO] large DC... |
| sub-169 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7; [warn] [EO] large DC offset (>10... |
| sub-170 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, F5; [warn] [EO] large DC offset (>100.... |
| sub-171 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2; [warn] [EO] excessive 50 H... |
| sub-172 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C4, TP10; [warn] [EO] excessive... |
| sub-173 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, TP9, PO10, FC4; [warn] [EO... |
| sub-174 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P4, O2, CP4, P2, P6, PO3, PO4; ... |
| sub-175 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EO] large DC offset (>10... |
| sub-176 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-177 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F4, AF4, F6, FC4; [warn] [... |
| sub-178 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O2, PO4; [warn] [EO] large DC o... |
| sub-179 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, TP8; [warn] [EO] excessiv... |
| sub-180 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3, CP1, TP7, CP3; [warn] [EO] ... |
| sub-181 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-182 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-183 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, FT8; [warn] [EO] excessive... |
| sub-184 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] large DC offs... |
| sub-185 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, O2, F2, F6, POz; [warn] [EO... |
| sub-186 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] excessive 50 ... |
| sub-187 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C4, POz; [warn] [EO] excessive ... |
| sub-188 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP8; [warn] [EO] large DC offse... |
| sub-189 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F1; [warn] [EO] large DC offset... |
| sub-190 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, T8, AF3, AF4, F2, F6; [warn... |
| sub-191 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, Pz, FT8, PO8; [warn] [EO] ... |
| sub-192 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, PO10, F6, FT9, FT8, FT10; [... |
| sub-193 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, FT9; [warn] [EO] excessiv... |
| sub-194 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, C3, CP5, TP10, P7, PO9, PO... |
| sub-195 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, PO4; [warn] [EO] excessive... |
| sub-196 | fail |  | yes | yes | [fail] [EO] median amplitude=388.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-197 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, AF7; [warn] [EO] excessive ... |
| sub-198 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-199 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, P8, TP8; [warn] [EO] exces... |
| sub-200 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, F5; [warn] [EO] excessive 5... |
| sub-201 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-202 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, AF7, AF3; [warn] [EO] exce... |
| sub-203 | fail |  | yes | yes | [fail] [EO] median amplitude=214.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-204 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] large DC offset... |
| sub-205 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT7, C6; [warn] [EO] excessive ... |
| sub-206 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4, C2; [warn] [EO] large DC offset (>100... |
| sub-207 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EO] large DC offset (>100.0 u... |
| sub-208 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, C2, P5, P2; [warn] [EO] la... |
| sub-209 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F4, AF7, AF8, F2; [warn] [... |
| sub-210 | fail | yes | yes | yes | [fail] [EO] median amplitude=369.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-211 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF7; [warn] [EO] excessive... |
| sub-212 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO3; [warn] [EO] excessive 50 H... |
| sub-213 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF7; [warn] [EO] excessive... |
| sub-214 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [warn] [EO] large DC offset (>100.0 u... |
| sub-215 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, AF8; [warn] [EO] large DC ... |
| sub-216 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT9; [warn] [EO] excessive 50 H... |
| sub-217 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] large DC offs... |
| sub-218 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7, FT9; [warn] [EO] excessive... |
| sub-219 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): POz; [warn] [EO] excessive 50 H... |
| sub-220 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT9, FC3; [warn] [EO] excessive... |
| sub-221 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, T7, TP7; [warn] [EO] large... |
| sub-222 | fail | yes | yes | yes | [fail] [EO] median amplitude=421.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-223 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF4; [warn] [EO] large DC offse... |
| sub-224 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-225 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, Pz, AF3, F6, C6; [warn] [EO... |
| sub-226 | warn | yes | yes | yes | [warn] [EO] gross artifact=33.2%, exceeds 20.0%; [warn] [EO] large DC offset ... |
| sub-227 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-228 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-229 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fz, C3, C1; [warn] [EO] excessi... |
| sub-230 | fail | yes | yes | yes | [fail] [EO] median amplitude=623.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-231 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F3, F4, F8, FC5, ... |
| sub-232 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2; [warn] [EO] excessive 50 H... |
| sub-233 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF4; [warn] [EO] excessive 50 H... |
| sub-234 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-235 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, FC1, P4, O1, AF4, AF8, C5,... |
| sub-236 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, TP10, FT10; [warn] [EO] la... |
| sub-237 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F3, FC1, FC6, TP7, PO4; [w... |
| sub-238 | fail | yes | yes | yes | [fail] [EO] median amplitude=269.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-239 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, AF8; [warn] [EO] larg... |
| sub-240 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, F7, F3, F4, F8, FC5, FC1, FC2, ... |
| sub-241 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EO] large DC offset (>10... |
| sub-242 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP5, CP2, P8, P6; [warn] [EO] e... |
| sub-243 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2; [warn] [EO] large DC offse... |
| sub-244 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-245 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] large DC offset (>100.0 u... |
| sub-246 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] large DC offset (>100.0 ... |
| sub-247 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, T7, TP9, TP10, F5, FT9, FT7... |
| sub-248 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EO] large DC offset (>100.0 u... |
| sub-249 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] large DC offset (>100.0 u... |
| sub-250 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, FC2, Oz, F6, FT8, PO7, POz;... |
| sub-251 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-252 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-253 | fail |  | yes | yes | [fail] [EO] median amplitude=951.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-254 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O2; [warn] [EO] excessive 50 Hz... |
| sub-255 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-256 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F8, FC6, C3, Cz, FT10, C1;... |
| sub-257 | fail |  | yes | yes | [fail] [EO] median amplitude=247.5 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-258 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, CP1, O2, AF8, FT7, TP... |
| sub-259 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO8; [warn] [EO] large DC offset (>100.0 u... |
| sub-260 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [warn] [EO] large DC offset (>10... |
| sub-261 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-262 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8, CP6, P4, Oz, O2, FC3, C6, P... |
| sub-263 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-264 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, TP10, P3, PO9, F5, FT9, FT... |
| sub-265 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] large DC offset (>100.0 u... |
| sub-266 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, TP10, AF7; [warn] [EO] exc... |
| sub-267 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F8, T7, T8, TP9, ... |
| sub-268 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fz; [warn] [EO] large DC offset (>100... |
| sub-269 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P4; [warn] [EO] gross artifact=... |
| sub-270 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, TP10, FT9; [warn] [EO] exc... |
| sub-271 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, F8, Oz, PO10, AF7, F5, PO7... |
| sub-272 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, TP9; [warn] [EO] excessive... |
| sub-273 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-274 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EO] large DC offset (>100.0 u... |
| sub-275 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, F4, F8, FC5, FC1, ... |
| sub-276 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] large DC offset (>100.0 ... |
| sub-277 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3, TP9, CP6, TP10, TP8; [warn]... |
| sub-278 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EO] gross artifact=22.7%... |
| sub-279 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-280 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1, P1; [warn] [EO] excessive ... |
| sub-281 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] large DC offs... |
| sub-282 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, F8, FC1, F2, F6, FC3; [warn... |
| sub-283 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F3, Fz, F4, F8, FC5, FC1, ... |
| sub-284 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz; [warn] [EO] excessive 50 Hz... |
| sub-285 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, FC2; [warn] [EO] excessive... |
| sub-286 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F8, TP9, CP1, TP1... |
| sub-287 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1; [warn] [EO] excessive 50 H... |
| sub-288 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP5, FT10, C2; [warn] [EO] exce... |
| sub-289 | fail |  | yes | yes | [fail] [EO] median amplitude=242.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-290 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, TP10; [warn] [EO] excessive... |
| sub-291 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9; [warn] [EO] large DC offse... |
| sub-292 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC5, P3, TP7; [warn] [EO] exces... |
| sub-293 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, AF7, AF8; [warn] [EO] exce... |
| sub-294 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, TP8; [warn] [EO] large DC ... |
| sub-295 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, CP5, F5, P6; [warn] [EO] ex... |
| sub-296 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7; [warn] [EO] large DC offset (>10... |
| sub-297 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, O1; [warn] [EO] gross arti... |
| sub-298 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-299 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-300 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-301 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-302 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, CP5, P6, POz; [warn] [EO] ... |
| sub-303 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9, Oz, PO7; [warn] [EO] exces... |
| sub-304 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-305 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT7, FT10, PO7; [warn] [EO] exc... |
| sub-306 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, FC3; [warn] [EO] large DC offset (>10... |
| sub-307 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Oz; [warn] [EO] excessive 50 Hz... |
| sub-308 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, POz; [warn] [EO] excessive ... |
| sub-309 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P2, PO7; [warn] [EO] excessive ... |
| sub-310 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC5, FC2, CP2, P3, O1, FT7, FC3... |
| sub-311 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EO] large DC offset (>100.0 u... |
| sub-312 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O2, AF4, FT9; [warn] [EO] exces... |
| sub-313 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7, AF8; [warn] [EO] gross artifact=... |
| sub-314 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8, F5, FT7; [warn] [EO] exces... |
| sub-315 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EO] large DC offset (>10... |
| sub-316 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz, TP7, P1; [warn] [EO] excess... |
| sub-317 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO7; [warn] [EO] large DC offset (>100.0 u... |
| sub-318 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T7, Oz, FT10; [warn] [EO] exces... |
| sub-319 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, O2; [warn] [EO] excessive ... |
| sub-320 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, AF4, FT8, CP4, PO8; [warn] ... |
| sub-321 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2; [warn] [EO] excessive 50 H... |
| sub-322 | fail | yes | yes | yes | [fail] [EO] median amplitude=962.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-323 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, FC6, C4, P3, FT10, C2, C6,... |
| sub-324 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F4, F8, T7, C3, T8, O2, AF... |
| sub-325 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, Fz; [warn] [EO] large DC offset (>100.... |
| sub-326 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, TP9, CP5, O1, O2,... |
| sub-327 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1; [warn] [EO] excessive 50 H... |
| sub-328 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO3; [warn] [EO] excessive 50 H... |
| sub-329 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, FT9; [warn] [EO] large DC o... |
| sub-330 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F8, CP5, CP1, AF7... |
| sub-331 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-332 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO4; [warn] [EO] excessive 50 H... |
| sub-333 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1; [warn] [EO] excessive 50 H... |
| sub-334 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5, FT8; [warn] [EO] large DC offset (>10... |
| sub-335 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10, P5, PO7; [warn] [EO] exce... |
| sub-336 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-337 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, F3; [warn] [EO] large DC offset (>100... |
| sub-338 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP6, AF8, F5, FT9, PO7; [warn] ... |
| sub-339 | fail |  | yes | yes | [fail] [EO] median amplitude=273.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-340 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] large DC offse... |
| sub-341 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP7; [warn] [EO] large DC offse... |
| sub-342 | fail |  | yes | yes | [fail] [EO] median amplitude=545.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-343 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] large DC offset (>100.0 u... |
| sub-344 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C4, CP1, P3, CP3, P1; [warn] [E... |
| sub-345 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] excessive 50 ... |
| sub-346 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8, PO3; [warn] [EO] excessive... |
| sub-347 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-348 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-349 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-350 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-351 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1, CP3; [warn] [EO] excessive... |
| sub-352 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] large DC offs... |
| sub-353 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] large DC offse... |
| sub-354 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, CP5, TP10; [warn] [EO] lar... |
| sub-355 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP2; [warn] [EO] excessive 50 H... |
| sub-356 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, CP1, CP2; [warn] [EO] exce... |
| sub-357 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-358 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C1; [warn] [EO] large DC offset... |
| sub-359 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT10; [warn] [EO] large DC offset (>100.0 ... |
| sub-360 | fail |  | yes | yes | [fail] [EO] median amplitude=252.6 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-361 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Oz; [warn] [EO] excessive 50 Hz... |
| sub-362 | fail | yes | yes | yes | [fail] [EO] median amplitude=239.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-363 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8; [warn] [EO] excessive 50 Hz... |
| sub-364 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EO] large DC offset (>100.0 u... |
| sub-365 | fail | yes | yes | yes | [fail] [EO] median amplitude=281.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-366 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: C1; [warn] [EO] large DC offset (>100.0 uV... |
| sub-367 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-368 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P7, AF4, FT10; [warn] [EO] larg... |
| sub-369 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): F7, F3, Fz, F4, F8, FC5, FC2, FC6, T... |
| sub-370 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF4, P6; [warn] [EO] large DC o... |
| sub-371 | fail |  | yes | yes | [fail] [EO] median amplitude=391.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-372 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-373 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-374 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7; [warn] [EO] excessive 50 H... |
| sub-375 | fail |  | yes | yes | [fail] [EO] median amplitude=314.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-376 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, F3, F8, FC2, T7, TP9, ... |
| sub-377 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, FC3; [warn] [EO] large DC o... |
| sub-378 | fail |  | yes | yes | [fail] [EO] median amplitude=202.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-379 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT8, CP3, CP4, PO3; [warn] [EO]... |
| sub-380 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, FC5, FC6, T7, T8, TP9,... |
| sub-381 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, C4, T8, TP10, P3, F5,... |
| sub-382 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1, P2; [warn] [EO] excessive ... |
| sub-383 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-384 | fail |  | yes | yes | [fail] [EO] median amplitude=382.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-385 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-386 | fail |  | yes | yes | [fail] [EO] median amplitude=243.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-387 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, Pz, O1, C2, PO3; [warn] [EO... |
| sub-388 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F8, TP10, PO10, AF8, FT8, ... |
| sub-389 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] gross artifact=25.0%, exc... |
| sub-390 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1; [warn] [EO] excessive 50 H... |
| sub-391 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T7, T8, TP9, CP5, TP10, P3, P4,... |
| sub-392 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, C3, T8, CP5, AF4,... |
| sub-393 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, Fz, F4, F8, FC5, FC1, FC2, ... |
| sub-394 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, TP9, CP1, F2, C2, P6; [war... |
| sub-395 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, F3, F4, F6, FT9; [warn] [EO... |
| sub-396 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, Oz, F5; [warn] [EO] large D... |
| sub-397 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, PO9, CPz; [warn] [EO] exces... |
| sub-398 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-399 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [warn] [EO] large DC offset (>100.0 u... |
| sub-400 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7, AF8, FT7, FC3, FT10; [warn... |
| sub-401 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-402 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8, F6; [warn] [EO] large DC offset (>100... |
| sub-403 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, TP10, P4, AF7, AF3, A... |
| sub-404 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FT10; [warn] [EO] large DC offs... |
| sub-405 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EO] large DC offset (>100.0 u... |
| sub-406 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP8; [warn] [EO] excessive 50 H... |
| sub-407 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7; [warn] [EO] excessive 50 H... |
| sub-408 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, FT8; [warn] [EO] excessive ... |
| sub-409 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, T8, P7, FT7, TP7, TP8; [wa... |
| sub-410 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C5; [warn] [EO] large DC offset... |
| sub-411 | fail | yes | yes | yes | [fail] [EO] median amplitude=348.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-412 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, CP2; [warn] [EO] large DC ... |
| sub-413 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, AF7, TP7; [warn] [EO] exces... |
| sub-414 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, Pz, Oz, FC4, PO3, PO4, PO8;... |
| sub-415 | fail | yes | yes | yes | [fail] [EO] median amplitude=887.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-416 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, PO9, O1, O2, F5, FT8,... |
| sub-417 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF7, P6; [warn] [EO] excessive ... |
| sub-418 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-419 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-420 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, FT9; [warn] [EO] excessive... |
| sub-421 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, TP7; [warn] [EO] large DC offset (>100... |
| sub-422 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P3, P5; [warn] [EO] large DC of... |
| sub-423 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] large DC offset (>100.0 ... |
| sub-424 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-425 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8, TP9, P7, O1, AF8, FT8, TP7,... |
| sub-426 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, AF7, AF8; [warn] [EO] exces... |
| sub-427 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C3; [warn] [EO] excessive 50 Hz... |
| sub-428 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F3, P3, PO10, AF7... |
| sub-429 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, AF7, F5, FT9, FT7, FC3; [w... |
| sub-430 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, CP3; [warn] [EO] large DC ... |
| sub-431 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, T7, FC4, CPz; [warn] [EO] ... |
| sub-432 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, T8, TP9, TP10, FT7, FC4, T... |
| sub-433 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, TP9, Pz, C1, C2, CP3, CPz, ... |
| sub-434 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, TP10, PO9; [warn] [EO] exc... |
| sub-435 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-436 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, F8, FC2, FT8; [warn] [EO] e... |
| sub-437 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fz; [warn] [EO] excessive 50 Hz... |
| sub-438 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P7, O1, Oz, PO10, FT8, PO3, POz... |
| sub-439 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF3; [warn] [EO] excessive... |
| sub-440 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-441 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, FT8, FT10; [warn] [EO] larg... |
| sub-442 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, FC5, TP10, AF8, FT10, PO8; ... |
| sub-443 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, PO9, AF7, AF3, AF4, A... |
| sub-444 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O2, AF3, AF8, FT8, FT10, POz; [... |
| sub-445 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10; [warn] [EO] large DC offset (>1... |
| sub-446 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-447 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, AF3; [warn] [EO] large DC... |
| sub-448 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, F4, T8, TP9, TP10, AF4, F5,... |
| sub-449 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Oz, F5, C5, CPz; [warn] [EO] la... |
| sub-450 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, AF7; [warn] [EO] large DC offset (>10... |
| sub-451 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, AF8; [warn] [EO] excessive ... |
| sub-452 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC2, Cz; [warn] [EO] large DC offset (>100... |
| sub-453 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, CP5, CP2, Pz, FT9, C2, P5, ... |
| sub-454 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF8; [warn] [EO] large DC offset (>10... |
| sub-455 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-456 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, TP9, TP10, P8, PO9, O1, PO1... |
| sub-457 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, C3, P4, F5; [warn] [EO] ex... |
| sub-458 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP2; [warn] [EO] excessive 50 H... |
| sub-459 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, Fz, F4, F8, FC5, FC1, F... |
| sub-460 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] large DC offset (>100.0 u... |
| sub-461 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5, PO7; [warn] [EO] excessive ... |
| sub-462 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-463 | fail | yes | yes | yes | [fail] [EO] median amplitude=282.5 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-464 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, TP9, CP2, TP10, FT10; [warn... |
| sub-465 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, T7, AF8, FT10, TP7; [warn]... |
| sub-466 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] excessive 50 ... |
| sub-467 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7, AF8; [warn] [EO] large DC offset... |
| sub-468 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9; [warn] [EO] excessive 50 H... |
| sub-469 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-470 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, Fz, F4, F8, FC5, FC1, FC2, FC6,... |
| sub-471 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F7, P7, PO9, AF4, AF8, FT9... |
| sub-472 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F4, F8, FC5, FC6,... |
| sub-473 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F7, F3, F4, F8, FC2, ... |
| sub-474 | fail |  | yes | yes | [fail] [EO] median amplitude=882.6 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-475 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10; [warn] [EO] large DC offs... |
| sub-476 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-477 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, Oz; [warn] [EO] excessive... |
| sub-478 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EO] large DC offset (>100... |
| sub-479 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] large DC offset (>100.0 u... |
| sub-480 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-481 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8; [warn] [EO] excessive 50 Hz... |
| sub-482 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] large DC offset (>100.0 u... |
| sub-483 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3; [warn] [EO] large DC offset... |
| sub-484 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C2; [warn] [EO] excessive 50 Hz... |
| sub-485 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3, AF4; [warn] [EO] gross artifact=2... |
| sub-486 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7; [warn] [EO] excessive 50 Hz... |
| sub-487 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-488 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): P3, FC4, CPz; [warn] [EO] exces... |
| sub-489 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, PO9; [warn] [EO] large DC offset (>10... |
| sub-490 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-491 | fail |  | yes | yes | [fail] [EO] median amplitude=248.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-492 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, POz; [fail] [EO] gross art... |
| sub-493 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, AF4, FC3, FT10; [warn] [EO... |
| sub-494 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9, CP1, TP10, P8, PO10, POz; ... |
| sub-495 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9; [warn] [EO] large DC offse... |
| sub-496 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): C1; [warn] [EO] excessive 50 Hz... |
| sub-497 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fz; [warn] [EO] large DC offset (>100... |
| sub-498 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] large DC offset (>100.0 u... |
| sub-499 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Pz, AF4, P6; [warn] [EO] excess... |
| sub-500 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F8, FC5, FC1, ... |
| sub-501 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO10; [warn] [EO] excessive 50 ... |
| sub-502 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5, P6; [warn] [EO] excessive 5... |
| sub-503 | fail | yes | yes | yes | [fail] [EO] median amplitude=215.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-504 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9; [warn] [EO] large DC offse... |
| sub-505 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, F8, FC6, T8, CP2, P8, PO9,... |
| sub-506 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, Fz, F4, FC2, T8, AF7,... |
| sub-507 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp2, F7, F3, F4, F8, FC5, FC1, FC2, ... |
| sub-508 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, F3; [warn] [EO] large DC offset (>100... |
| sub-509 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, FC2; [warn] [EO] large DC o... |
| sub-510 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] large DC offset (>100.0 u... |
| sub-511 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP10, AF3, AF8; [warn] [EO] exc... |
| sub-512 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F3, AF3, F5; [warn] [EO] large DC offset (... |
| sub-513 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-514 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO4; [warn] [EO] excessive 50 H... |
| sub-515 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] large DC offset (>100.0 ... |
| sub-516 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5, AF4; [warn] [EO] large DC offset (>10... |
| sub-517 | fail | yes | yes | yes | [fail] [EO] median amplitude=329.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-518 | fail |  | yes | yes | [fail] [EO] median amplitude=223.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-519 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC5, FC2, C3, TP9, O1, F6, FT10... |
| sub-520 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, CP2, TP10, Pz, AF3, FT9; [... |
| sub-521 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, PO4; [warn] [EO] excessive ... |
| sub-522 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC1, F... |
| sub-523 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1; [warn] [EO] excessive 50 H... |
| sub-524 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, TP10, AF8, FT8, FT10, TP7;... |
| sub-525 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2; [warn] [EO] large DC offset (>100.0 u... |
| sub-526 | fail |  | yes | yes | [fail] [EO] median amplitude=259.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-527 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, O1, Oz; [warn] [EO] large DC offset (... |
| sub-528 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF3; [warn] [EO] large DC offse... |
| sub-529 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Cz, AF8, C5; [warn] [EO] e... |
| sub-530 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-531 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O1; [warn] [EO] excessive 50 Hz... |
| sub-532 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): O1; [warn] [EO] excessive 50 Hz... |
| sub-533 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-534 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP5, CP1, CP2, FT9, CPz, CP4, P... |
| sub-535 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, T7; [warn] [EO] large DC offset (>100... |
| sub-536 | fail | yes | yes | yes | [warn] [EO] gross artifact=34.1%, exceeds 20.0%; [warn] [EO] large DC offset ... |
| sub-537 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC1, F... |
| sub-538 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-539 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): POz; [warn] [EO] excessive 50 H... |
| sub-540 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC3; [warn] [EO] excessive 50 H... |
| sub-541 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): CP1, AF3; [warn] [EO] excessive... |
| sub-542 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F4, F2, FC4, POz; [warn] [EO] e... |
| sub-543 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-544 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, FC5, FC1, ... |
| sub-545 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7, F8, TP9, P7, Pz, P8, O1, Oz... |
| sub-546 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, TP9, FT7, P1; [warn] [EO] e... |
| sub-547 | fail |  | yes | yes | [fail] [EO] median amplitude=313.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-548 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): AF8; [warn] [EO] excessive 50 H... |
| sub-549 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, P3, AF3; [warn] [EO] excess... |
| sub-550 | fail | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, P4, O1, AF7, AF8, POz; [wa... |
| sub-551 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2; [warn] [EO] large DC offse... |
| sub-552 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF7, AF8; [warn] [EO] exce... |
| sub-553 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC1, FC2, FC6, C3, TP10, F1, FT... |
| sub-554 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T7, CP5, CP2, TP10, F5; [warn] ... |
| sub-555 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-556 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] large DC offset (>100.0 ... |
| sub-557 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T7, FT8; [warn] [EO] excessive ... |
| sub-558 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F5; [warn] [EO] excessive 50 Hz... |
| sub-559 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EO] large DC offset (>100.0 uV... |
| sub-560 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] large DC offset (>100.0 uV... |
| sub-561 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] large DC offset (>100.0 u... |
| sub-562 | fail |  | yes | yes | [fail] [EO] median amplitude=310.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-563 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): TP9; [warn] [EO] excessive 50 H... |
| sub-564 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, FT7; [warn] [EO] large DC offset (>10... |
| sub-565 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] large DC offset (>100.0 u... |
| sub-566 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9, O1, Oz, C6, TP8, PO7; [war... |
| sub-567 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, TP7; [warn] [EO] large DC offset (>100... |
| sub-568 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, CP6, FT8; [warn] [EO] exce... |
| sub-569 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC2, TP9, CP5, CP6, F2; [warn] ... |
| sub-570 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] large DC offset (>100.0 uV... |
| sub-571 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FT8; [warn] [EO] large DC offset (>100... |
| sub-572 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EO] large DC offset (>100.0 u... |
| sub-573 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp2, AF4, AF8; [warn] [EO] exce... |
| sub-574 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F7; [warn] [EO] excessive 50 Hz... |
| sub-575 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3; [warn] [EO] excessive 50 Hz... |
| sub-576 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, TP9, P4, AF7, AF3, F5, F1, ... |
| sub-577 | fail |  | yes | yes | [fail] [EO] median amplitude=482.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-578 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F2; [warn] [EO] large DC offset... |
| sub-579 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): T8, CP4; [warn] [EO] excessive ... |
| sub-580 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F3, T7; [warn] [EO] excessive 5... |
| sub-581 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, FT9; [warn] [EO] excessive... |
| sub-582 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3, AF4; [warn] [EO] large DC offset ... |
| sub-583 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): FC6; [warn] [EO] excessive 50 H... |
| sub-584 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-585 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EO] large DC offset (>100.0 u... |
| sub-586 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): POz; [warn] [EO] excessive 50 H... |
| sub-587 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO4; [warn] [EO] excessive 50 H... |
| sub-588 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EO] large DC offset (>10... |
| sub-589 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): PO9; [warn] [EO] large DC offse... |
| sub-590 | fail |  | yes | yes | [fail] [EO] median amplitude=298.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-591 | warn | yes | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-592 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, AF8, TP7, PO3; [warn] [EO] ... |
| sub-593 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EO] large DC offset (>100.... |
| sub-594 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-595 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-596 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-597 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fz; [warn] [EO] excessive 50 Hz... |
| sub-598 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, Fp2, F3, AF7, AF3, FC3, CP... |
| sub-599 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] large DC offset (>100.0 u... |
| sub-600 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-601 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, F3, Fz, F4, F8, FC5, F... |
| sub-602 | warn | yes | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Cz, F1, P2; [warn] [EO] excessi... |
| sub-603 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EO] large DC offset (>100.0 u... |
| sub-604 | warn |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): Fp1, TP9, AF7; [warn] [EO] exce... |
| sub-605 | fail |  | yes | yes | [warn] [EO] railed channels (>500.0 uV >10%): F8, FC5, T7, T8, TP9, CP5, CP1,... |
| sub-606 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8, FT10, C6; [warn] [EO] large DC offset... |
| sub-607 | warn |  | yes | yes | [warn] [EO] large DC offset (>100.0 uV): Fp1, Fp2, F7, Fz, F4, F8, FC5, FC1, ... |
| sub-608 | warn | yes | yes | yes | [warn] [EO] gross artifact=24.6%, exceeds 20.0%; [warn] [EO] large DC offset ... |

