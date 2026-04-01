# Dortmund Vital Study EEG — QC Report

**Generated:** 2026-04-01 13:47 UTC
**Total subjects:** 608

## Summary

| Verdict | Count |
|---------|-------|
| Pass    | 58 |
| Warn    | 433 |
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
| [EO] excessive 50 Hz noise | 436 |
| [EC] excessive 50 Hz noise | 416 |
| [EC] railed channels (>1000.0 uV >10%) | 249 |
| [EC] gross artifact | 190 |
| [EO] gross artifact | 139 |
| [EO] railed channels (>1000.0 uV >10%) | 135 |
| [EC] median amplitude | 51 |
| [EO] median amplitude | 44 |
| [EC] duration | 1 |

## Channel Issues Across Subjects

| Channel | Flat | Railed | 50 Hz Noise |
|---------|------|--------|-------------|
| AF3 | 0 | 51 | 113 |
| AF4 | 0 | 41 | 60 |
| AF7 | 0 | 59 | 67 |
| AF8 | 0 | 67 | 43 |
| C1 | 0 | 20 | 2 |
| C2 | 0 | 22 | 5 |
| C3 | 0 | 18 | 2 |
| C4 | 0 | 25 | 3 |
| C5 | 0 | 26 | 8 |
| C6 | 0 | 24 | 5 |
| CP1 | 0 | 22 | 2 |
| CP2 | 0 | 17 | 7 |
| CP3 | 0 | 22 | 1 |
| CP4 | 0 | 20 | 0 |
| CP5 | 0 | 37 | 36 |
| CP6 | 0 | 25 | 1 |
| CPz | 0 | 24 | 0 |
| Cz | 0 | 30 | 9 |
| F1 | 0 | 17 | 2 |
| F2 | 0 | 33 | 1 |
| F3 | 0 | 38 | 7 |
| F4 | 0 | 46 | 4 |
| F5 | 0 | 69 | 19 |
| F6 | 0 | 42 | 8 |
| F7 | 0 | 45 | 41 |
| F8 | 0 | 47 | 16 |
| FC1 | 0 | 26 | 3 |
| FC2 | 0 | 29 | 5 |
| FC3 | 0 | 40 | 24 |
| FC4 | 0 | 28 | 2 |
| FC5 | 0 | 27 | 25 |
| FC6 | 0 | 25 | 27 |
| FT10 | 0 | 69 | 9 |
| FT7 | 0 | 43 | 21 |
| FT8 | 0 | 46 | 37 |
| FT9 | 0 | 50 | 6 |
| Fp1 | 0 | 49 | 66 |
| Fp2 | 0 | 53 | 25 |
| Fz | 0 | 20 | 75 |
| O1 | 0 | 37 | 9 |
| O2 | 0 | 39 | 6 |
| Oz | 0 | 34 | 2 |
| P1 | 0 | 20 | 0 |
| P2 | 0 | 24 | 0 |
| P3 | 0 | 15 | 0 |
| P4 | 0 | 20 | 1 |
| P5 | 0 | 25 | 1 |
| P6 | 0 | 35 | 7 |
| P7 | 0 | 32 | 3 |
| P8 | 0 | 30 | 2 |
| PO10 | 0 | 35 | 57 |
| PO3 | 0 | 32 | 4 |
| PO4 | 0 | 32 | 3 |
| PO7 | 0 | 32 | 4 |
| PO8 | 0 | 30 | 8 |
| PO9 | 0 | 34 | 41 |
| POz | 0 | 33 | 1 |
| Pz | 0 | 19 | 0 |
| T7 | 0 | 41 | 72 |
| T8 | 0 | 37 | 70 |
| TP10 | 0 | 48 | 42 |
| TP7 | 0 | 37 | 21 |
| TP8 | 0 | 33 | 10 |
| TP9 | 0 | 50 | 65 |

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
| Delta | -0.0277 | -0.021 |
| Theta | +0.0036 | +0.003 |
| Alpha | +0.1217 | +0.110 |
| Beta | +0.0517 | +0.053 |

Mean alpha peak shift: +0.39 Hz

**Findings:**
- No strong pre/post differences detected in this sample

## Per-Subject Results

| Subject | Status | Session 2 | Pre-EO | Pre-EC | Issues |
|---------|--------|-----------|--------|--------|--------|
| sub-001 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): CP1 |
| sub-002 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC2, FC6, FC4; [warn] [EO] exc... |
| sub-003 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC5 |
| sub-004 | fail |  | yes | yes | [fail] [EO] median amplitude=213.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-005 | pass | yes | yes | yes |  |
| sub-006 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] railed channels (>1000.0 u... |
| sub-007 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] railed channels (>1000.0 ... |
| sub-008 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: C5 |
| sub-009 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC2; [fail] [EC] median amplitude=202.0 uV... |
| sub-010 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EC] excessive 50 Hz nois... |
| sub-011 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F5 |
| sub-012 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Cz; [warn] [EC] excessive 50 Hz noise: Cz |
| sub-013 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF7; [warn] [EO] excessive 50 ... |
| sub-014 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10, PO3; [warn] [EO] gross a... |
| sub-015 | fail |  | yes | yes | [fail] [EO] median amplitude=285.0 uV, exceeds 200.0; [warn] [EO] excessive 5... |
| sub-016 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, F8; [warn] [EC] railed channels (>1000... |
| sub-017 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Cz; [warn] [EC] railed channel... |
| sub-018 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EC] excessive 50 Hz nois... |
| sub-019 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-020 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5 |
| sub-021 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [fail] [EC] gross artifact=50.8%, exc... |
| sub-022 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO8; [warn] [EC] excessive 50 Hz noise: T7... |
| sub-023 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: O2; [warn] [EC] excessive 50 Hz noise: O2 |
| sub-024 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, Fz; [warn] [EC] excessive 50 Hz noise... |
| sub-025 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] railed channels (>1000.0 ... |
| sub-026 | fail |  | yes | yes | [fail] [EO] median amplitude=888.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-027 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC3; [warn] [EO] excessive 50 ... |
| sub-028 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, AF7; [warn] [EC] excessive 50 Hz noise... |
| sub-029 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: Fz |
| sub-030 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] excessive 50 Hz noise: Fp... |
| sub-031 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EC] railed channels (>1000.0 ... |
| sub-032 | pass |  | yes | yes |  |
| sub-033 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] railed channels (>1000.0 ... |
| sub-034 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: TP7 |
| sub-035 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [fail] [EO] gross artifact=59.5%... |
| sub-036 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EC] railed channels (>1000.0 ... |
| sub-037 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: TP9; [warn] [EC] gross artifact=23.7%, exc... |
| sub-038 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, TP7; [warn] [EC] railed channels (>100... |
| sub-039 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-040 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp2; [warn] [EC] excessive 50 ... |
| sub-041 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT9, FT7; [warn] [EC] railed channels (>10... |
| sub-042 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF7; [warn] [EO] excessive 50 ... |
| sub-043 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1; [warn] [EO] excessive 50 ... |
| sub-044 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-045 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC4; [warn] [EC] railed channels (>1000.0 ... |
| sub-046 | pass | yes | yes | yes |  |
| sub-047 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F1, FC3; [warn] [EC] railed channels (>100... |
| sub-048 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8, FC3; [warn] [EC] excessive 50 Hz nois... |
| sub-049 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: C3; [warn] [EC] railed channels (>1000.0 u... |
| sub-050 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8 |
| sub-051 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): Pz |
| sub-052 | fail | yes | yes | yes | [fail] [EO] median amplitude=387.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-053 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-054 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): Fp1, AF7, AF8, FT9; [warn] [EC... |
| sub-055 | fail |  | yes | yes | [fail] [EO] median amplitude=210.7 uV, exceeds 200.0; [fail] [EO] gross artif... |
| sub-056 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7; [warn] [EC] excessive 50 Hz nois... |
| sub-057 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): AF4 |
| sub-058 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9; [warn] [EC] railed channels (>1000.0 ... |
| sub-059 | fail | yes | yes | yes | [fail] [EO] median amplitude=331.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-060 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F8; [warn] [EC] excessive 50 Hz noise: Fp1 |
| sub-061 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-062 | pass |  | yes | yes |  |
| sub-063 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10; [warn] [EC] railed chann... |
| sub-064 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): O2; [warn] [EO] excessive 50 H... |
| sub-065 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: Fp... |
| sub-066 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, AF7, AF8; [fail] [EO] gross artifact=5... |
| sub-067 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-068 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F2; [warn] [EC] excessive 50 H... |
| sub-069 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP8; [warn] [EC] railed channels (>1000.0 ... |
| sub-070 | pass |  | yes | yes |  |
| sub-071 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [fail] [EO] gross artifact=53.6%, exc... |
| sub-072 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] gross artifact=20.9%, ex... |
| sub-073 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-074 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, FT8; [warn] [EO] gross artifact=44.3%... |
| sub-075 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Oz, AF4; [warn] [EO] excessive... |
| sub-076 | pass | yes | yes | yes |  |
| sub-077 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO3; [warn] [EO] excessive 50 ... |
| sub-078 | pass |  | yes | yes |  |
| sub-079 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10; [warn] [EO] excessive 50... |
| sub-080 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C2; [warn] [EO] excessive 50 H... |
| sub-081 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-082 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): P7; [warn] [EC] excessive 50 H... |
| sub-083 | warn |  | yes | yes | [warn] [EO] gross artifact=22.4%, exceeds 20.0%; [warn] [EC] gross artifact=4... |
| sub-084 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9; [warn] [EC] railed channels (>1000.0 ... |
| sub-085 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, Fp2, F7, F8, T7, TP10, AF... |
| sub-086 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10; [warn] [EO] excessive 50... |
| sub-087 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, PO10; [warn] [EC] excessive 50 Hz noi... |
| sub-088 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9; [warn] [EC] excessive 50 Hz noise: PO9 |
| sub-089 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10, PO3; [warn] [EC] excessive 50 Hz noi... |
| sub-090 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: T7 |
| sub-091 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, FC3; [warn] [EC] excessive 50 Hz nois... |
| sub-092 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EC] railed channels (>1000.0 ... |
| sub-093 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10, C2; [warn] [EC] railed channels... |
| sub-094 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-095 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF8; [warn] [EO] excessive 50 ... |
| sub-096 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FT9; [warn] [EC] gross artifac... |
| sub-097 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, TP10; [warn] [EC] excessive 50 Hz nois... |
| sub-098 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-099 | pass |  | yes | yes |  |
| sub-100 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF3; [fail] [EC] median amplitude=346... |
| sub-101 | pass |  | yes | yes |  |
| sub-102 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP9; [warn] [EO] excessive 50 ... |
| sub-103 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF... |
| sub-104 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] railed channels (>1000.0 ... |
| sub-105 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT9; [warn] [EO] excessive 50 ... |
| sub-106 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EC] excessive 50 Hz nois... |
| sub-107 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): T8; [warn] [EC] excessive 50 H... |
| sub-108 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EC] railed channels (>100... |
| sub-109 | pass | yes | yes | yes |  |
| sub-110 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): F8, Cz, PO9, PO10, FT9, FT8, F... |
| sub-111 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P1; [warn] [EO] excessive 50 H... |
| sub-112 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C2; [warn] [EO] excessive 50 H... |
| sub-113 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF3; [warn] [EO] excessive 50 ... |
| sub-114 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT9, PO3; [warn] [EO] excessiv... |
| sub-115 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF8, TP8; [warn] [EO] excessiv... |
| sub-116 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EC] railed channels (>1000.0 u... |
| sub-117 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, Fp2, AF7, AF3; [warn] [EO... |
| sub-118 | fail |  | yes | yes | [fail] [EO] median amplitude=315.5 uV, exceeds 200.0; [warn] [EO] excessive 5... |
| sub-119 | pass | yes | yes | yes |  |
| sub-120 | fail |  | yes | yes | [fail] [EO] median amplitude=201.0 uV, exceeds 200.0; [warn] [EO] excessive 5... |
| sub-121 | fail |  | yes | yes | [fail] [EO] median amplitude=303.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-122 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP2, FC3; [warn] [EC] railed channels (>10... |
| sub-123 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EC] excessive 50 Hz nois... |
| sub-124 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7 |
| sub-125 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] gross artifact=22.7%, ex... |
| sub-126 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F5, TP7; [warn] [EC] railed channels (>100... |
| sub-127 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, PO10; [warn] [EC] excessive 50 Hz noi... |
| sub-128 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: PO8 |
| sub-129 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-130 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2; [warn] [EC] railed channels (>1000.0 ... |
| sub-131 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P8, F5; [warn] [EO] excessive ... |
| sub-132 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7 |
| sub-133 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP10; [warn] [EC] railed channels (>1000.0... |
| sub-134 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] railed channels (>1000.0 ... |
| sub-135 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [fail] [EC] median amplitude=333.... |
| sub-136 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7, AF8 |
| sub-137 | fail | yes | yes | yes | [fail] [EO] median amplitude=267.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-138 | pass | yes | yes | yes |  |
| sub-139 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, TP7; [warn] [EC] excessive 50 Hz nois... |
| sub-140 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [fail] [EO] gross artifact=53.8%, exce... |
| sub-141 | pass |  | yes | yes |  |
| sub-142 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] excessive 50 Hz noise: T7... |
| sub-143 | pass | yes | yes | yes |  |
| sub-144 | fail |  | yes | yes | [fail] [EO] median amplitude=222.2 uV, exceeds 200.0; [fail] [EO] gross artif... |
| sub-145 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FT7; [warn] [EO] gross artifact=47.3%,... |
| sub-146 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, TP9; [warn] [EO] gross artifact=20.1%,... |
| sub-147 | pass | yes | yes | yes |  |
| sub-148 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-149 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP10; [warn] [EC] excessive 50 Hz noise: TP10 |
| sub-150 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz,... |
| sub-151 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EC] railed channels (>1000.0 ... |
| sub-152 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, PO10; [warn] [EC] excessive 50 Hz noi... |
| sub-153 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C1; [warn] [EO] excessive 50 H... |
| sub-154 | warn |  | yes | yes | [warn] [EO] gross artifact=40.7%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-155 | warn |  | yes | yes | [warn] [EO] gross artifact=27.8%, exceeds 20.0% |
| sub-156 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [warn] [EC] excessive 50 Hz noise: FC6 |
| sub-157 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P2; [warn] [EC] railed channel... |
| sub-158 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, FT8; [warn] [EC] excessive 50 Hz nois... |
| sub-159 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10; [warn] [EC] excessive 50 Hz noi... |
| sub-160 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-161 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] excessive 50 Hz noise: C6 |
| sub-162 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, FT8; [warn] [EO] gross artifact=30.6%... |
| sub-163 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO4; [warn] [EO] excessive 50 ... |
| sub-164 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] railed channels (>1000.0 u... |
| sub-165 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7 |
| sub-166 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FC5, FT7 |
| sub-167 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP7; [warn] [EO] excessive 50 ... |
| sub-168 | pass | yes | yes | yes |  |
| sub-169 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7; [warn] [EC] railed channels (>10... |
| sub-170 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, F5; [warn] [EC] excessive 50 Hz noise:... |
| sub-171 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F6; [warn] [EC] excessive 50 Hz noise: AF8 |
| sub-172 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5 |
| sub-173 | warn |  | yes | yes | [warn] [EO] gross artifact=33.3%, exceeds 20.0%; [warn] [EC] excessive 50 Hz ... |
| sub-174 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF3; [warn] [EC] railed channels (>10... |
| sub-175 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EC] excessive 50 Hz nois... |
| sub-176 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-177 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] gross artifact=23.4%, exce... |
| sub-178 | pass |  | yes | yes |  |
| sub-179 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP10; [warn] [EO] excessive 50... |
| sub-180 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: FT9 |
| sub-181 | pass | yes | yes | yes |  |
| sub-182 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-183 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EC] railed channels (>10... |
| sub-184 | pass | yes | yes | yes |  |
| sub-185 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): O2; [warn] [EC] gross artifact... |
| sub-186 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-187 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): POz; [warn] [EO] excessive 50 ... |
| sub-188 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: TP9; [warn] [EC] gross artifact=48.9%, exc... |
| sub-189 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: T8, TP10 |
| sub-190 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10; [warn] [EO] gross artifact=41.0... |
| sub-191 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] gross artifact=43.7%, exce... |
| sub-192 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] gross artifact=25.5%, exc... |
| sub-193 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP8; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-194 | fail |  | yes | yes | [warn] [EO] gross artifact=49.7%, exceeds 20.0%; [fail] [EC] median amplitude... |
| sub-195 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO4; [warn] [EO] excessive 50 ... |
| sub-196 | fail |  | yes | yes | [fail] [EO] median amplitude=388.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-197 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF7; [warn] [EO] excessive 50 ... |
| sub-198 | pass | yes | yes | yes |  |
| sub-199 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] gross artifact=21.4%, exc... |
| sub-200 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): F4; [warn] [EO] excessive 50 H... |
| sub-201 | pass |  | yes | yes |  |
| sub-202 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F8; [warn] [EC] railed channels (>1000.0 u... |
| sub-203 | fail |  | yes | yes | [fail] [EO] median amplitude=214.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-204 | pass |  | yes | yes |  |
| sub-205 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, FT7; [warn] [EC] railed channels (>10... |
| sub-206 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4, C2; [warn] [EC] railed channels (>100... |
| sub-207 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] excessive 50 Hz noise: CP... |
| sub-208 | fail |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC2, P2; [fail] [EC] gross art... |
| sub-209 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8, F6; [warn] [EC] excessive 50 Hz ... |
| sub-210 | fail | yes | yes | yes | [fail] [EO] median amplitude=369.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-211 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT7; [warn] [EC] excessive 50 Hz noise: T7... |
| sub-212 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-213 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F5; [warn] [EO] gross artifact=22.0%, exce... |
| sub-214 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [warn] [EC] excessive 50 Hz noise: Fp... |
| sub-215 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC1; [warn] [EC] excessive 50 ... |
| sub-216 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] railed channels (>1000.0 ... |
| sub-217 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): TP10 |
| sub-218 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] railed channels (>1000.0 ... |
| sub-219 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] railed channels (>1000.0 ... |
| sub-220 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: T... |
| sub-221 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC1 |
| sub-222 | fail | yes | yes | yes | [fail] [EO] median amplitude=421.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-223 | pass |  | yes | yes |  |
| sub-224 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-225 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EO] gross artifact=29.2%... |
| sub-226 | warn | yes | yes | yes | [warn] [EO] gross artifact=33.2%, exceeds 20.0% |
| sub-227 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-228 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] excessive 50 Hz noise: CP5 |
| sub-229 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: F8 |
| sub-230 | fail | yes | yes | yes | [fail] [EO] median amplitude=623.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-231 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): F5, F6, FT9; [warn] [EO] gross... |
| sub-232 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC2; [warn] [EO] excessive 50 ... |
| sub-233 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] excessive 50 Hz noise: CP5 |
| sub-234 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-235 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, AF4; [fail] [EO] gross artifact=60.1%,... |
| sub-236 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC1, AF8 |
| sub-237 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EO] gross artifact=25.6%, exc... |
| sub-238 | fail | yes | yes | yes | [fail] [EO] median amplitude=269.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-239 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): O1; [warn] [EC] gross artifact... |
| sub-240 | pass |  | yes | yes |  |
| sub-241 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3 |
| sub-242 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P6; [warn] [EO] excessive 50 H... |
| sub-243 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC2 |
| sub-244 | pass |  | yes | yes |  |
| sub-245 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EC] excessive 50 Hz noise: TP7 |
| sub-246 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-247 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] gross artifact=46.5%, exc... |
| sub-248 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EC] excessive 50 Hz noise: T8... |
| sub-249 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1 |
| sub-250 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FC2, Oz, FT8, PO7; [warn] [EC]... |
| sub-251 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-252 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): FT10 |
| sub-253 | fail |  | yes | yes | [fail] [EO] median amplitude=951.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-254 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2; [warn] [EC] excessive 50 Hz noise: PO... |
| sub-255 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-256 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C3; [warn] [EO] excessive 50 H... |
| sub-257 | fail |  | yes | yes | [fail] [EO] median amplitude=247.5 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-258 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP1; [warn] [EO] excessive 50 ... |
| sub-259 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO8; [warn] [EC] excessive 50 Hz noise: PO8 |
| sub-260 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-261 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-262 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): O2, FC3; [warn] [EC] railed ch... |
| sub-263 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: Fz... |
| sub-264 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP10, P3, FT9; [warn] [EO] exc... |
| sub-265 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7 |
| sub-266 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp2; [warn] [EO] excessive 50 ... |
| sub-267 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, Fp2, F8, T7, AF7, AF8, FT... |
| sub-268 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fz; [warn] [EC] excessive 50 Hz noise... |
| sub-269 | warn |  | yes | yes | [warn] [EO] gross artifact=44.6%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-270 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP9; [warn] [EO] excessive 50 ... |
| sub-271 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, F5; [warn] [EC] railed channels (>1000... |
| sub-272 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EC] railed channels (>1000... |
| sub-273 | pass |  | yes | yes |  |
| sub-274 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-275 | pass |  | yes | yes |  |
| sub-276 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-277 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP6; [warn] [EO] excessive 50 ... |
| sub-278 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [warn] [EO] gross artifact=22.7%... |
| sub-279 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): P4; [warn] [EC] excessive 50 H... |
| sub-280 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FC5; [warn] [EC] railed channels (>100... |
| sub-281 | pass |  | yes | yes |  |
| sub-282 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC1; [warn] [EC] railed channe... |
| sub-283 | pass |  | yes | yes |  |
| sub-284 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Pz; [warn] [EO] excessive 50 H... |
| sub-285 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F4; [warn] [EC] railed channels (>1000.0 u... |
| sub-286 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, TP9, TP10, AF7, FT9; [war... |
| sub-287 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, T8; [warn] [EC] railed channels (>100... |
| sub-288 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP5; [warn] [EO] excessive 50 ... |
| sub-289 | fail |  | yes | yes | [fail] [EO] median amplitude=242.1 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-290 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7 |
| sub-291 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO9; [warn] [EC] railed channe... |
| sub-292 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EO] gross artifact=36.1%, ... |
| sub-293 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: Fp1 |
| sub-294 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC1; [warn] [EC] railed channe... |
| sub-295 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Cz, CP5, F5; [warn] [EO] exces... |
| sub-296 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7 |
| sub-297 | warn |  | yes | yes | [warn] [EO] gross artifact=20.7%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-298 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-299 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EC] excessive 50 Hz noise: F7,... |
| sub-300 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-301 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F7, AF7; [warn] [EC] excessive... |
| sub-302 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P6; [warn] [EO] excessive 50 H... |
| sub-303 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] railed channels (>1000.0... |
| sub-304 | pass |  | yes | yes |  |
| sub-305 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7; [warn] [EO] gross artifact=33.2%, exc... |
| sub-306 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, FC3; [warn] [EC] excessive 50 Hz nois... |
| sub-307 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8 |
| sub-308 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, T7; [warn] [EC] excessive 50 Hz noise... |
| sub-309 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EC] railed channels (>1000... |
| sub-310 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EO] gross artifact=33.7%, exc... |
| sub-311 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8 |
| sub-312 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] gross artifact=22.8%, exc... |
| sub-313 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7, AF8; [warn] [EO] gross artifact=... |
| sub-314 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EC] excessive 50 Hz nois... |
| sub-315 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EC] excessive 50 Hz nois... |
| sub-316 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, FT8; [warn] [EC] railed channels (>10... |
| sub-317 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO7; [warn] [EC] excessive 50 Hz noise: PO7 |
| sub-318 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Oz; [warn] [EO] excessive 50 H... |
| sub-319 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): O2; [warn] [EO] excessive 50 H... |
| sub-320 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EO] gross artifact=44.3%, ex... |
| sub-321 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fp2; [warn] [EC] excessive 50 Hz nois... |
| sub-322 | fail | yes | yes | yes | [fail] [EO] median amplitude=962.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-323 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [fail] [EO] gross artifact=55.6%... |
| sub-324 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, AF4; [fail] [EO] gross artifact=56.8%... |
| sub-325 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, Fz; [warn] [EC] excessive 50 Hz noise: F7 |
| sub-326 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT9; [warn] [EO] excessive 50 ... |
| sub-327 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP10, TP7; [warn] [EC] railed channels (>1... |
| sub-328 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] gross artifact=42.9%, exce... |
| sub-329 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): CP1, FT9, P1 |
| sub-330 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C1; [warn] [EO] excessive 50 H... |
| sub-331 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7 |
| sub-332 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO4; [warn] [EO] excessive 50 ... |
| sub-333 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] excessive 50 Hz noise: T7 |
| sub-334 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5, FT8; [warn] [EC] railed channels (>10... |
| sub-335 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: O1; [warn] [EC] railed channels (>1000.0 u... |
| sub-336 | pass |  | yes | yes |  |
| sub-337 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, F3; [warn] [EC] excessive 50 Hz noise... |
| sub-338 | fail |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): T7, T8, FT9, FT7, TP7; [warn] ... |
| sub-339 | fail |  | yes | yes | [fail] [EO] median amplitude=273.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-340 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF8; [warn] [EC] excessive 50 ... |
| sub-341 | pass | yes | yes | yes |  |
| sub-342 | fail |  | yes | yes | [fail] [EO] median amplitude=545.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-343 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-344 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EO] gross artifact=31.5%, exce... |
| sub-345 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F3; [warn] [EC] excessive 50 Hz noise: F3 |
| sub-346 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] railed channels (>1000.0 ... |
| sub-347 | warn | yes | yes | yes | [warn] [EC] gross artifact=31.0%, exceeds 20.0% |
| sub-348 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: T7... |
| sub-349 | pass | yes | yes | yes |  |
| sub-350 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): CP1 |
| sub-351 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP1; [warn] [EO] excessive 50 ... |
| sub-352 | pass | yes | yes | yes |  |
| sub-353 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F5 |
| sub-354 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): TP9, CP5, C2; [warn] [EC] exce... |
| sub-355 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EC] excessive 50 Hz noise... |
| sub-356 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fp2 |
| sub-357 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-358 | warn |  | yes | yes | [warn] [EC] gross artifact=36.2%, exceeds 20.0% |
| sub-359 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT10; [warn] [EC] railed channels (>1000.0... |
| sub-360 | fail |  | yes | yes | [fail] [EO] median amplitude=252.6 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-361 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-362 | fail | yes | yes | yes | [fail] [EO] median amplitude=239.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-363 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EO] gross artifact=47.4%, exc... |
| sub-364 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9; [warn] [EC] excessive 50 Hz noise: TP9 |
| sub-365 | fail | yes | yes | yes | [fail] [EO] median amplitude=281.7 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-366 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: C1; [warn] [EC] excessive 50 Hz noise: C1 |
| sub-367 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: TP9 |
| sub-368 | pass | yes | yes | yes |  |
| sub-369 | pass |  | yes | yes |  |
| sub-370 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): P6; [warn] [EC] excessive 50 H... |
| sub-371 | fail |  | yes | yes | [fail] [EO] median amplitude=391.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-372 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): Fp2; [warn] [EC] excessive 50 ... |
| sub-373 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-374 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7 |
| sub-375 | fail |  | yes | yes | [fail] [EO] median amplitude=314.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-376 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC3; [warn] [EO] gross artifac... |
| sub-377 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC3 |
| sub-378 | fail |  | yes | yes | [fail] [EO] median amplitude=202.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-379 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F8, FC6, FT8; [warn] [EO] gross artifact=4... |
| sub-380 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): T8; [fail] [EO] gross artifact... |
| sub-381 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] excessive 50 Hz noise: PO... |
| sub-382 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-383 | pass |  | yes | yes |  |
| sub-384 | fail |  | yes | yes | [fail] [EO] median amplitude=382.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-385 | pass | yes | yes | yes |  |
| sub-386 | fail |  | yes | yes | [fail] [EO] median amplitude=243.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-387 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): O1, TP7, P5; [warn] [EC] gross... |
| sub-388 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO10; [warn] [EO] excessive 50... |
| sub-389 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EO] gross artifact=25.0%, exc... |
| sub-390 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, TP9, PO10; [warn] [EC] excessive 50 Hz... |
| sub-391 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO4; [warn] [EO] excessive 50 ... |
| sub-392 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, CP5; [warn] [EO] excessiv... |
| sub-393 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): O2, F5 |
| sub-394 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC2, TP9, C2; [warn] [EO] exce... |
| sub-395 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EO] gross artifact=41.5%, exc... |
| sub-396 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-397 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CPz; [warn] [EO] excessive 50 ... |
| sub-398 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-399 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-400 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10; [warn] [EO] excessive 50... |
| sub-401 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-402 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8, F6 |
| sub-403 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp2, AF7, AF3, AF4, AF8; [warn... |
| sub-404 | fail | yes | yes | yes | [fail] [EC] gross artifact=52.4%, exceeds 50.0% |
| sub-405 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5 |
| sub-406 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, TP8; [warn] [EC] excessive 50 Hz noise... |
| sub-407 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8 |
| sub-408 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4, FT7; [warn] [EC] railed channels (>10... |
| sub-409 | fail |  | yes | yes | [fail] [EC] median amplitude=216.3 uV, exceeds 200.0; [warn] [EC] railed chan... |
| sub-410 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: AF8 |
| sub-411 | fail | yes | yes | yes | [fail] [EO] median amplitude=348.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-412 | fail |  | yes | yes | [fail] [EC] median amplitude=210.3 uV, exceeds 200.0; [fail] [EC] gross artif... |
| sub-413 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EC] railed channels (>1000.0 ... |
| sub-414 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [fail] [EO] gross artifact=51.9%, exce... |
| sub-415 | fail | yes | yes | yes | [fail] [EO] median amplitude=887.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-416 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P1; [warn] [EO] excessive 50 H... |
| sub-417 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-418 | pass | yes | yes | yes |  |
| sub-419 | pass |  | yes | yes |  |
| sub-420 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6, T8, FT8; [warn] [EO] gross artifact=3... |
| sub-421 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, TP7; [warn] [EC] excessive 50 Hz noise... |
| sub-422 | pass |  | yes | yes |  |
| sub-423 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-424 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: FT9 |
| sub-425 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): O1; [warn] [EO] gross artifact... |
| sub-426 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-427 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3, FT7; [warn] [EC] excessive 50 Hz nois... |
| sub-428 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, Fp2, F7, AF7, AF3, AF8, F... |
| sub-429 | fail |  | yes | yes | [warn] [EO] gross artifact=44.1%, exceeds 20.0%; [warn] [EC] excessive 50 Hz ... |
| sub-430 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): TP9, FT9, POz; [warn] [EC] gro... |
| sub-431 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): CPz; [warn] [EC] excessive 50 ... |
| sub-432 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP10; [warn] [EO] excessive 50... |
| sub-433 | fail |  | yes | yes | [fail] [EO] gross artifact=55.1%, exceeds 50.0%; [fail] [EC] median amplitude... |
| sub-434 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO9; [warn] [EO] excessive 50 ... |
| sub-435 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EC] excessive 50 Hz noise: F7 |
| sub-436 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EC] excessive 50 Hz noise: FC2 |
| sub-437 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, FT8; [warn] [EC] excessive 50 Hz noise... |
| sub-438 | fail | yes | yes | yes | [warn] [EO] gross artifact=46.2%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-439 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: O2; [warn] [EC] excessive 50 Hz noise: O2 |
| sub-440 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] railed channels (>1000.0 u... |
| sub-441 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F8 |
| sub-442 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO8; [warn] [EO] excessive 50 ... |
| sub-443 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5; [warn] [EC] excessive 50 Hz noise: CP5 |
| sub-444 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FT10; [warn] [EO] excessive 50... |
| sub-445 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, TP10; [warn] [EC] excessive 50 Hz noi... |
| sub-446 | pass | yes | yes | yes |  |
| sub-447 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): AF3 |
| sub-448 | fail |  | yes | yes | [warn] [EO] gross artifact=42.7%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-449 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): CPz; [warn] [EC] gross artifac... |
| sub-450 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, AF7; [warn] [EC] excessive 50 Hz nois... |
| sub-451 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, AF3; [warn] [EC] railed channels (>100... |
| sub-452 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC2, Cz; [warn] [EC] railed channels (>100... |
| sub-453 | fail |  | yes | yes | [fail] [EO] gross artifact=63.9%, exceeds 50.0%; [warn] [EC] railed channels ... |
| sub-454 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-455 | pass | yes | yes | yes |  |
| sub-456 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP10, PO9, O1, FT8, FT10, PO7;... |
| sub-457 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EC] excessive 50 Hz noise... |
| sub-458 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4, F2; [warn] [EC] railed channels (>100... |
| sub-459 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: PO9 |
| sub-460 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] excessive 50 Hz noise: T8... |
| sub-461 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO7; [warn] [EO] excessive 50 ... |
| sub-462 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-463 | fail | yes | yes | yes | [fail] [EO] median amplitude=282.5 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-464 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F6; [warn] [EC] railed channels (>1000.0 u... |
| sub-465 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, TP8; [fail] [EO] gross artifact=55.8%,... |
| sub-466 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: Fp1 |
| sub-467 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF7, AF8; [warn] [EC] excessive 50 Hz... |
| sub-468 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP9; [warn] [EO] excessive 50 ... |
| sub-469 | warn |  | yes | yes | [warn] [EC] gross artifact=32.4%, exceeds 20.0% |
| sub-470 | pass |  | yes | yes |  |
| sub-471 | warn |  | yes | yes | [warn] [EO] gross artifact=39.4%, exceeds 20.0%; [warn] [EC] excessive 50 Hz ... |
| sub-472 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, Fp2, F7, F4, FC5, CP1, P8... |
| sub-473 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): Fp1, F3, F4, FC2, AF3, F2, FC4... |
| sub-474 | fail |  | yes | yes | [fail] [EO] median amplitude=882.6 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-475 | pass | yes | yes | yes |  |
| sub-476 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] excessive 50 Hz noise: Fz,... |
| sub-477 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF3 |
| sub-478 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EC] excessive 50 Hz noise... |
| sub-479 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: Fp1 |
| sub-480 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EC] excessive 50 Hz noise: T8,... |
| sub-481 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, FC3; [warn] [EC] excessive 50 Hz nois... |
| sub-482 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] excessive 50 Hz noise: TP10 |
| sub-483 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): P5; [warn] [EC] excessive 50 H... |
| sub-484 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-485 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3, AF4; [warn] [EO] gross artifact=2... |
| sub-486 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7 |
| sub-487 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9, O1; [warn] [EO] gross artifact=27.3%,... |
| sub-488 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-489 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, PO9; [warn] [EC] excessive 50 Hz nois... |
| sub-490 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: F8... |
| sub-491 | fail |  | yes | yes | [fail] [EO] median amplitude=248.9 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-492 | fail |  | yes | yes | [fail] [EO] gross artifact=56.5%, exceeds 50.0% |
| sub-493 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): FC3; [fail] [EC] median amplit... |
| sub-494 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, FT7; [warn] [EO] gross artifact=39.3%,... |
| sub-495 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F4, F8, T8, TP10, AF7, AF4, AF... |
| sub-496 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, AF7, AF8; [warn] [EC] railed channels... |
| sub-497 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, Fz; [warn] [EC] excessive 50 Hz noise... |
| sub-498 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1 |
| sub-499 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5, P6; [warn] [EC] railed channels (>100... |
| sub-500 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): Fz |
| sub-501 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8; [warn] [EC] excessive 50 Hz noise: AF8 |
| sub-502 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-503 | fail | yes | yes | yes | [fail] [EO] median amplitude=215.8 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-504 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): TP9 |
| sub-505 | fail | yes | yes | yes | [fail] [EO] gross artifact=59.8%, exceeds 50.0%; [warn] [EC] excessive 50 Hz ... |
| sub-506 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): PO3; [warn] [EO] excessive 50 ... |
| sub-507 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): PO9 |
| sub-508 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, F3; [warn] [EC] railed channels (>100... |
| sub-509 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F3 |
| sub-510 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7 |
| sub-511 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): AF3; [warn] [EO] excessive 50 ... |
| sub-512 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F3, AF3, F5; [warn] [EC] excessive 50 Hz n... |
| sub-513 | pass |  | yes | yes |  |
| sub-514 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: Fp1 |
| sub-515 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-516 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: CP5, AF4; [warn] [EC] railed channels (>10... |
| sub-517 | fail | yes | yes | yes | [fail] [EO] median amplitude=329.7 uV, exceeds 200.0; [fail] [EO] gross artif... |
| sub-518 | fail |  | yes | yes | [fail] [EO] median amplitude=223.7 uV, exceeds 200.0; [fail] [EO] gross artif... |
| sub-519 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): C3; [warn] [EC] railed channel... |
| sub-520 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP2, FT9; [warn] [EO] excessiv... |
| sub-521 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2, F7, AF8; [warn] [EC] excessive 50 Hz ... |
| sub-522 | warn | yes | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): AF8, CP3; [warn] [EC] excessiv... |
| sub-523 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-524 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EC] railed channels (>1000... |
| sub-525 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp2 |
| sub-526 | fail |  | yes | yes | [fail] [EO] median amplitude=259.4 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-527 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: TP9, O1, Oz; [warn] [EC] excessive 50 Hz n... |
| sub-528 | pass |  | yes | yes |  |
| sub-529 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF... |
| sub-530 | pass | yes | yes | yes |  |
| sub-531 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT7; [warn] [EC] excessive 50 Hz noise: T7 |
| sub-532 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F5; [warn] [EC] excessive 50 Hz noise: F5,... |
| sub-533 | pass | yes | yes | yes |  |
| sub-534 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP5; [warn] [EO] excessive 50 ... |
| sub-535 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, T7; [warn] [EC] excessive 50 Hz noise... |
| sub-536 | fail | yes | yes | yes | [warn] [EO] gross artifact=34.1%, exceeds 20.0%; [warn] [EC] railed channels ... |
| sub-537 | pass |  | yes | yes |  |
| sub-538 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1; [warn] [EC] railed channels (>1000.0 ... |
| sub-539 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-540 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] excessive 50 Hz noise: T7,... |
| sub-541 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3; [warn] [EC] railed channels (>100... |
| sub-542 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F8, AF8; [warn] [EC] railed channels (>100... |
| sub-543 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: TP9 |
| sub-544 | pass |  | yes | yes |  |
| sub-545 | fail | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): F8, Pz; [warn] [EO] gross arti... |
| sub-546 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4, F5; [warn] [EC] excessive 50 Hz noise... |
| sub-547 | fail |  | yes | yes | [fail] [EO] median amplitude=313.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-548 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5 |
| sub-549 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC3; [warn] [EO] gross artifact=29.4%, exc... |
| sub-550 | fail | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9; [warn] [EO] gross artifact=48.6%, exc... |
| sub-551 | pass |  | yes | yes |  |
| sub-552 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF8; [warn] [EC] excessive 50 Hz nois... |
| sub-553 | fail |  | yes | yes | [warn] [EO] gross artifact=39.9%, exceeds 20.0%; [fail] [EC] median amplitude... |
| sub-554 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP5; [warn] [EO] excessive 50 ... |
| sub-555 | warn | yes | yes | yes | [warn] [EC] excessive 50 Hz noise: F7, CP5 |
| sub-556 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO10; [warn] [EC] excessive 50 Hz noise: PO10 |
| sub-557 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7, AF8; [fail] [EC] median amplitude=327... |
| sub-558 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EC] railed channels (>1000.0 ... |
| sub-559 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: F7; [warn] [EC] excessive 50 Hz noise: AF3... |
| sub-560 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EC] excessive 50 Hz noise: Fz |
| sub-561 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF4; [warn] [EC] excessive 50 Hz noise: AF4 |
| sub-562 | fail |  | yes | yes | [fail] [EO] median amplitude=310.0 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-563 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT7; [warn] [EC] excessive 50 Hz noise: FT7 |
| sub-564 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5, FT7; [warn] [EC] excessive 50 Hz nois... |
| sub-565 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-566 | fail |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC6; [fail] [EO] gross artifact=62.6%, exc... |
| sub-567 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8, TP7; [warn] [EC] excessive 50 Hz noise... |
| sub-568 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF3 |
| sub-569 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz; [warn] [EO] gross artifact=33.0%, exce... |
| sub-570 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8 |
| sub-571 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F7, FT8; [warn] [EC] excessive 50 Hz noise... |
| sub-572 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF8 |
| sub-573 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7 |
| sub-574 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T8; [warn] [EC] excessive 50 Hz noise: T8,... |
| sub-575 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EC] railed channels (>1000.0 ... |
| sub-576 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP9; [warn] [EO] excessive 50 ... |
| sub-577 | fail |  | yes | yes | [fail] [EO] median amplitude=482.2 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-578 | warn |  | yes | yes | [warn] [EC] railed channels (>1000.0 uV >10%): F2 |
| sub-579 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF3; [warn] [EC] excessive 50 Hz noise: AF... |
| sub-580 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: AF7; [warn] [EC] railed channels (>1000.0 ... |
| sub-581 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: F8, FT8; [warn] [EC] railed channels (>100... |
| sub-582 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fz, AF3, AF4; [warn] [EC] excessive 50 Hz ... |
| sub-583 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: CP1; [warn] [EC] excessive 50 Hz noise: C2 |
| sub-584 | pass |  | yes | yes |  |
| sub-585 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FC5; [warn] [EC] excessive 50 Hz noise: C6 |
| sub-586 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: T7; [warn] [EC] railed channels (>1000.0 u... |
| sub-587 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FC3; [warn] [EC] excessive 50 Hz noise: FC3 |
| sub-588 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: Fp1, AF3; [warn] [EC] excessive 50 Hz nois... |
| sub-589 | pass |  | yes | yes |  |
| sub-590 | fail |  | yes | yes | [fail] [EO] median amplitude=298.3 uV, exceeds 200.0; [warn] [EO] railed chan... |
| sub-591 | pass | yes | yes | yes |  |
| sub-592 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: O1, Oz; [warn] [EO] gross artifact=46.7%, ... |
| sub-593 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: T7, T8; [warn] [EC] excessive 50 Hz noise:... |
| sub-594 | pass |  | yes | yes |  |
| sub-595 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: PO9 |
| sub-596 | pass |  | yes | yes |  |
| sub-597 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: PO9; [warn] [EC] excessive 50 Hz noise: TP... |
| sub-598 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP3; [warn] [EO] gross artifac... |
| sub-599 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: TP7 |
| sub-600 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: Fp1, AF7 |
| sub-601 | warn |  | yes | yes | [warn] [EC] excessive 50 Hz noise: PO10, TP7; [warn] [EC] gross artifact=26.7... |
| sub-602 | warn | yes | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): P2; [warn] [EO] excessive 50 H... |
| sub-603 | warn |  | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8; [warn] [EC] excessive 50 Hz noise: T7... |
| sub-604 | warn |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): TP9; [warn] [EO] excessive 50 ... |
| sub-605 | fail |  | yes | yes | [warn] [EO] railed channels (>1000.0 uV >10%): CP5; [warn] [EO] excessive 50 ... |
| sub-606 | warn | yes | yes | yes | [warn] [EO] excessive 50 Hz noise: FT8, FT10, C6; [warn] [EC] excessive 50 Hz... |
| sub-607 | pass |  | yes | yes |  |
| sub-608 | warn | yes | yes | yes | [warn] [EO] gross artifact=24.6%, exceeds 20.0% |

