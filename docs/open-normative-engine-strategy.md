# Open Normative Engine: Strategy & Implementation Plan

## The Idea

Open-source the normative comparison engine and processing pipeline as a standalone public research resource. The engine computes reference statistics from publicly available EEG datasets. Coherence Workstation provides the best interface for *using* that engine, but the engine itself is free, transparent, and independently verifiable.

This separates "how z-scores are computed" (open, inspectable, citable) from "how structural understanding is supported" (commercial, proprietary, the actual product).

---

## What Gets Open-Sourced

### Ring 1: The Open Normative Engine

**Repository:** `peak-mind-llc/open-normative-eeg` (new public repo, GitHub)

**License:** Apache 2.0 (permissive, allows commercial use by others, requires attribution, includes patent grant—important for a tool that produces clinical-adjacent outputs). Alternatively, BSD-3-Clause. Both are compatible with MNE-Python's BSD license.

**Contents:**

1. **Processing pipeline** — The complete Python/MNE pipeline that takes raw EEG recordings and produces spectral, connectivity, and slope metrics. Identical code path for normative and clinical data. Every parameter documented. Every step logged.

2. **Dataset loaders** — Scripts to download, validate, and prepare each source dataset for processing. Handle channel mapping, resampling, condition tagging, age binning.

3. **Normative statistics generator** — Code that processes all subjects in a dataset, computes per-metric distributions (mean, SD, percentiles) by age bin and condition, and outputs the normative reference tables.

4. **Comparison engine** — Code that takes a single clinical recording's metrics and computes z-scores (or percentile ranks) against the normative reference for matched age and condition.

5. **Validation suite** — Cross-validation against EEGLab, synthetic known-answer tests, inter-dataset consistency checks.

6. **Documentation** — Full methodology paper (could be submitted to a journal like *Data in Brief* or *Scientific Data*), parameter justifications, known limitations, usage guide.

### What Stays Proprietary (Ring 3: Coherence Workstation)

- Three-layer structural framework (substrate → architecture → dynamics)
- AI Research Assistant
- Topographic ERP template matching engine
- Phenotype detection
- Gated consultation model
- Expert notes generator
- Clinical report generation
- Interactive dashboard and visualizations
- All frontend code

The normative engine tells you where a value falls relative to the population. CW tells you what the *organization* looks like and helps you *understand* it. One is a ruler. The other is an architect.

---

## Data Sources

### Primary: Resting-State EEG

| Dataset | N | Ages | Channels | Conditions | License | Compatibility | Notes |
|---------|---|------|----------|------------|---------|---------------|-------|
| **LEMON** (MPI Leipzig) | 228 | 20–35 (young), 59–77 (old) | 62 (BrainProducts ActiCAP) | EO, EC | CC0 via FCP-INDI | ✅ Fully open, commercial OK | Reference: FCz. Sampling: 2500 Hz. Gap: ages 36–58 missing. Must downsample to 19ch before processing. |
| **HBN** (Child Mind Institute) | 3,000+ | 5–21 | 128 (EGI HydroCel) | Resting + 6 tasks | CC-BY-SA 4.0 (OpenNeuro releases); DUA required for full access | ⚠️ CC-BY-SA requires derivative works share alike; DUA has no analysis constraints, no co-authorship requirement | Pediatric/adolescent. Reference: Cz. EGI numbering → 10-20 mapping required. Not "healthy"—community-referred, many have psychiatric symptoms (but questionnaire data available for filtering). |
| **MIPDB** (Child Mind Institute) | 126 | 6–44 | 128 (EGI) | Resting + multiple tasks | CC-BY-NC-SA | ⚠️ Non-commercial clause. Cannot be used in commercial product directly. | Bridges pediatric to adult. DUA required for protected phenotypic data. EEG data itself is CC-BY-NC-SA. |
| **TDBRAIN** (Brainclinics) | 1,274 | Clinical lifespan | 26 | EO, EC | Custom DUA | ⚠️ Need to verify commercial use terms | Clinical population (psychiatric). Useful for clinical-comparison database (like BrainDx) but NOT for normative reference. Investigate. |

### Secondary: ERP Normative Reference

| Dataset | N | Ages | Paradigms | License | Notes |
|---------|---|------|-----------|---------|-------|
| **Nencki-Symfonia** | 42 | Young adults | MSIT, Oddball, Simple RT | CC BY 4.0 | Clean, well-characterized. Already in use for CW ERP templates. Cite as Dzianok et al. 2022. |
| **Isbell/ds006018** | 127 | Adults | Oddball | CC0 | Larger N but artifact contamination found in extracted templates (Fp1/Fp2 peaks). Needs re-extraction with tighter ICA rejection. |
| **HBN ERP tasks** | 3,000+ | 5–21 | Visual/auditory oddball, flanker, others | CC-BY-SA 4.0 | Massive pediatric ERP dataset. Would dramatically strengthen ERP norms for children/adolescents. |

### Age Coverage Analysis

| Age Range | LEMON | HBN | MIPDB | Combined N (approx) | Status |
|-----------|-------|-----|-------|---------------------|--------|
| 5–9 | — | ✅ | ✅ | ~500+ | Pediatric: HBN dominant |
| 10–14 | — | ✅ | ✅ | ~800+ | Adolescent: HBN dominant |
| 15–21 | — | ✅ | ✅ | ~700+ | Late adolescent: HBN + MIPDB |
| 20–35 | ✅ | — | ✅ (partial) | ~180 | Young adult: LEMON dominant |
| 36–58 | — | — | ✅ (partial, up to 44) | ~20–30 | **GAP.** Minimal coverage. |
| 59–77 | ✅ | — | — | ~74 | Elderly: LEMON only |

**The 36–58 gap is real.** This is exactly the age range of many neurotherapy clients. Options: seek additional public datasets (TDBRAIN has this range but is clinical, not normative), or acknowledge the gap explicitly and report wider confidence intervals for this age range. Honesty about coverage gaps is itself a differentiator—no other normative database tells you when its bins are underpowered.

**UPDATE — Gap Filled: Dortmund Vital Study**

The Dortmund Vital Study (Getzmann et al., 2024) fills the mid-life gap. 608 healthy adults ages 20–70, 64-channel BrainProducts actiCHamp, EO + EC conditions, CC BY 4.0 license. Published September 2024 on OpenNeuro as ds005385.

**Revised Age Coverage with Dortmund:**

| Age Range | LEMON | Dortmund | HBN (filtered) | MIPDB | Combined N (approx) | Status |
|-----------|-------|----------|-----------------|-------|---------------------|--------|
| 5–9 | — | — | ✅ | ✅ | ~250+ | Pediatric: HBN dominant |
| 10–14 | — | — | ✅ | ✅ | ~400+ | Adolescent: HBN dominant |
| 15–21 | — | ✅ (partial) | ✅ | ✅ | ~350+ | Late adolescent: HBN + MIPDB |
| 20–35 | ✅ | ✅ | — | ✅ (partial) | ~350+ | Young adult — **strong** |
| 36–58 | — | **✅** | — | — | **~250+** | **Mid-life — GAP FILLED** |
| 59–77 | ✅ | ✅ (up to 70) | — | — | ~150+ | Elderly — **strong** |

The open normative engine now covers ages 5 through 77 with genuine healthy samples and transparent methodology. Combined estimated N after QC filtering: ~1,500–2,000+ clean subjects across the lifespan.

The Dortmund longitudinal data (208 subjects with 5-year follow-up) is a unique asset no competitor has—normative *change trajectories* for healthy aging.

---

## Dortmund Vital Study: Dataset Details & QC Plan

### Dataset Profile

- **Publication:** Getzmann, S., Gajewski, P.D., Schneider, D. & Wascher, E. (2024). Resting-state EEG data before and after cognitive activity across the adult lifespan and a 5-year follow-up. *Scientific Data*, 11:988.
- **OpenNeuro:** ds005385
- **N:** 608 (session 1), 208 (session 2 / 5-year follow-up)
- **Demographics:** Ages 20–70, mean 44.1 ± 14.5 years, 61.8% female, 93.1% right-handed
- **EEG system:** 64-channel BrainProducts actiCHamp (10-10 layout)
- **Conditions:** 3 minutes eyes-open + 3 minutes eyes-closed, recorded *before* and *after* a 2-hour block of cognitive tasks
- **Reference:** Verify — likely FCz (BrainProducts standard)
- **Sampling rate:** Verify — likely 500 or 1000 Hz
- **Format:** BIDS on OpenNeuro
- **License:** CC BY 4.0 (open, commercial OK, attribution required)
- **Citation required:** Getzmann et al. 2024

### Download

```bash
# OpenNeuro dataset ds005385
# Option 1: OpenNeuro CLI
pip install openneuro-py
openneuro download --dataset ds005385 ~/datasets/dortmund/

# Option 2: AWS S3 (OpenNeuro mirrors to S3)
aws s3 sync s3://openneuro.org/ds005385 ~/datasets/dortmund/ --no-sign-request

# Option 3: DataLad (version-controlled download)
datalad install https://github.com/OpenNeuroDatasets/ds005385.git
```

### QC Plan: Dortmund-Specific Issues

The Dortmund dataset is cleaner than HBN (healthy adults, high-quality lab recording) but has its own QC considerations.

**Claude Code prompt for Dortmund QC:**

```
CONTEXT: I've downloaded the Dortmund Vital Study EEG dataset (608 subjects, 
ages 20-70, 64-channel BrainProducts actiCHamp, BIDS format) to 
~/datasets/dortmund/. I need a QC sweep before normative processing.

The Dortmund study recorded EEG in four blocks per session:
- Pre-task resting EO (3 min)
- Pre-task resting EC (3 min)
- [2 hours of cognitive tasks]
- Post-task resting EO (3 min)
- Post-task resting EC (3 min)

For normative purposes, I want the PRE-TASK resting data only. Post-task 
data may be contaminated by cognitive fatigue effects. The session 2 
(follow-up) data is valuable for longitudinal analysis but should be 
processed separately, not mixed into cross-sectional norms.

GOAL: Create scripts/normative/dortmund_qc.py that:

1. BIDS STRUCTURE VALIDATION
   - Verify BIDS compliance (participants.tsv, correct folder structure)
   - Parse participants.tsv: extract age, sex, handedness for each subject
   - Identify which subjects have session 1 only vs both sessions
   - Identify which resting-state files exist per subject (pre-task EO, 
     pre-task EC, post-task EO, post-task EC)
   - Flag subjects missing pre-task resting data

2. RECORDING PARAMETERS
   - Verify sampling rate (expected ~500 or 1000 Hz — check first few 
     subjects and report)
   - Verify channel count (expected 64)
   - Verify channel names match expected 10-10 positions
   - Identify reference channel (expected FCz absent if it was reference)
   - Report recording duration per condition per subject
   - Flag recordings shorter than 2 minutes per condition

3. CHANNEL MAPPING
   - Map 64-channel 10-10 layout to 19-channel 10-20 subset
   - Unlike HBN (EGI numbered), Dortmund uses standard 10-10 names — 
     the 19 standard 10-20 positions should be a direct subset
   - Verify all 19 channels are present in every subject
   - Flag any subjects with missing 10-20 channels
   - Report which additional 10-10 channels are available (useful for 
     denser analysis or better ICA decomposition before downsampling)

4. SIGNAL QUALITY (same metrics as LEMON QC)
   - Flat channels (variance < 0.1 µV)
   - Railed channels (amplitude > 500 µV for >10% of recording)
   - Excessive line noise (50 Hz for this European dataset, NOT 60 Hz)
   - Overall amplitude distribution
   - Gross artifact percentage
   - DC offset per channel

5. CONDITION VERIFICATION
   - Parse BIDS events files for resting-state condition markers
   - Verify EO and EC conditions are correctly tagged
   - Confirm pre-task vs post-task distinction is parseable
   - Report duration of usable data per condition after artifact flagging

6. PRE-TASK vs POST-TASK COMPARISON
   - For a subset (~20 subjects), compute basic spectral metrics for 
     both pre-task and post-task resting data
   - Report the magnitude of pre/post difference (expecting increased 
     theta/fatigue signatures post-task)
   - This validates our decision to use pre-task only for normative 
     purposes

7. AGE DISTRIBUTION CHECK
   - Histogram of ages in 5-year bins
   - Verify coverage across 20-70 range
   - Report N per decade bin
   - Flag any thin bins

8. SESSION 1 vs SESSION 2 SUBJECTS
   - Identify the 208 subjects with follow-up data
   - For session 1: include in cross-sectional norms normally
   - For session 2: flag for separate longitudinal analysis pipeline
   - DO NOT mix session 1 and session 2 data in cross-sectional norms 
     (the same person counted twice would violate independence)

Output:
- Per-subject JSON with all QC metrics
- Summary markdown: subject ID, age, sex, session(s), pass/warn/fail, issues
- Age distribution histogram data
- Channel mapping JSON (64ch → 19ch)
- "Ready to process" list (session 1, pre-task only, clean)
- "Excluded" list with reasons
- Pre/post task comparison summary

IMPORTANT: This is a European dataset. Line noise is 50 Hz, not 60 Hz. 
Make sure the notch filter and line noise detection use 50 Hz.
```

### Dortmund-Specific Processing Notes

**Channel downsampling strategy:** Unlike HBN (128ch EGI with approximate 10-20 mapping), Dortmund uses standard 10-10 names. The 19 standard 10-20 positions are a direct subset of the 64 10-10 positions—no approximate mapping needed. This makes Dortmund the cleanest dataset for 19-channel normative processing.

**Consider processing at 64 channels first, then extracting 19.** For ICA, more channels = better decomposition. You could run ICA at 64 channels, classify and reject artifact components, and *then* extract the 19-channel subset for metric computation. This gives you cleaner data than running ICA on 19 channels directly. BUT: this breaks the Golden Rule—your clinical data from Q21 runs ICA on 19 channels. If you run normative ICA on 64 channels, the component decompositions are fundamentally different.

**Resolution:** Downsample to 19 channels BEFORE ICA, just like LEMON and HBN. The Golden Rule wins. Document this tradeoff explicitly in the methodology paper—it's an honest limitation that reinforces the pipeline consistency argument.

**Pre-task vs post-task:** Use pre-task resting data only for normative tables. Post-task data is scientifically interesting (what does fatigue look like in the EEG?) but is not representative of "resting state" as clinicians understand it. A clinical recording is typically done at the start of a session, not after 2 hours of cognitive load.

**European line noise:** 50 Hz, not 60 Hz. This must be parameterized in the pipeline, not hardcoded. Clinical Q21 recordings in the US use 60 Hz. The normative pipeline needs to accept a `line_freq` parameter. Add this to the shared config.

**5-year follow-up data:** Process separately, store separately, don't mix into cross-sectional norms. This data enables a future feature: "normative aging trajectory"—what does the slope, the alpha peak, the connectivity pattern look like as healthy adults age? That's a question nobody else's database can answer. Save it for Phase 2 of the normative engine.

---

## License Strategy

### The Core Decision: Can you distribute processed normative statistics from these datasets?

**LEMON (CC0):** Yes. CC0 = public domain. No restrictions. You can process the data, compute statistics, and distribute the results in any form, commercially or otherwise.

**Dortmund Vital Study (CC BY 4.0):** Yes, with attribution. You can process, distribute, and use commercially. Cite Getzmann et al. 2024 in all outputs that use Dortmund-derived norms. No share-alike requirement—the most commercially friendly license after CC0.

**HBN (CC-BY-SA 4.0 on OpenNeuro):** This is the tricky one. CC-BY-SA requires that derivative works are shared under the same license. The processed normative statistics are arguably a derivative work. This means: you *can* distribute them, but they must also be CC-BY-SA. That's fine for the open-source engine—the engine is already open. But it means the normative tables themselves can't become a proprietary asset. They stay open. This is actually aligned with the strategy: the normative tables are public, the *understanding framework* is commercial.

The DUA for full HBN access (non-OpenNeuro route) has no analysis constraints and no co-authorship requirement. Verify whether the DUA route has different terms for derivative distribution.

**MIPDB (CC-BY-NC-SA):** Non-commercial. The processed statistics from MIPDB cannot be included in a commercial product. Options: include MIPDB-derived norms only in the open-source engine (which is non-commercial by nature), and exclude them from any CW-specific distribution. Or use MIPDB only for validation, not as a normative source.

**Nencki-Symfonia (CC BY 4.0):** Yes, with attribution. Cite Dzianok et al. 2022 in all outputs.

**Isbell/ds006018 (CC0):** Yes, unrestricted.

### Recommended License Architecture

```
open-normative-eeg repo (Apache 2.0)
├── Pipeline code: Apache 2.0 (fully open)
├── Dataset loaders: Apache 2.0
├── Normative tables from LEMON: CC0 (unrestricted)
├── Normative tables from Dortmund: CC BY 4.0 (attribution required)
├── Normative tables from HBN: CC-BY-SA 4.0 (share alike)
├── Normative tables from MIPDB: CC-BY-NC-SA (non-commercial only)
├── ERP templates from Nencki: CC BY 4.0 (attribution required)
└── ERP templates from Isbell: CC0 (unrestricted)
```

CW (commercial) can freely use:
- The pipeline code (Apache 2.0 allows commercial use)
- LEMON-derived norms (CC0)
- Dortmund-derived norms (CC BY 4.0—commercial use OK, cite Getzmann et al. 2024)
- HBN-derived norms (CC-BY-SA—CW must acknowledge the share-alike, but since the norms are already published openly, CW is *using* them, not *distributing* a new derivative)
- Nencki templates (with attribution)
- Isbell templates (CC0)

CW should NOT bundle MIPDB-derived norms directly. Instead, CW can point users to the open-source engine where MIPDB norms are available under non-commercial terms.

---

## Implementation Plan

### Phase 1: Pipeline Extraction (2–3 weeks)

**Goal:** Extract the normative processing pipeline from the CW codebase into a standalone, well-documented open-source package.

This is not a rewrite. It's a clean extraction of the existing code paths that process normative data, with the CW-specific parts (dashboard, AI, reports) removed.

**Claude Code prompt for extraction:**

```
CONTEXT: I'm extracting the normative processing pipeline from Coherence 
Workstation into a standalone open-source package called open-normative-eeg. 
The pipeline must be identical to what CW uses—same code paths, same 
parameters—because pipeline consistency is the entire point.

GOAL: Create a new Python package structure at ~/open-normative-eeg/ with:

1. open_normative/pipeline.py — The core processing pipeline. Extract from 
   nf_eeg/ the stages needed for normative processing: data loading, channel 
   standardization, resampling, filtering, bad channel detection, artifact 
   rejection, re-referencing, ICA, spectral analysis (including slope), 
   connectivity, and metric extraction. Must be parameterized identically 
   to how CW processes clinical data.

2. open_normative/datasets/ — Loader modules for each source dataset:
   - lemon.py: download, extract, map 62ch → 19ch, tag conditions
   - dortmund.py: download from OpenNeuro ds005385, extract pre-task 
     resting only, map 64ch → 19ch, tag conditions, handle 50 Hz line freq
   - hbn.py: download, extract, map 128ch EGI → 19ch, tag conditions
   - mipdb.py: download, extract, map 128ch EGI → 19ch, tag conditions

3. open_normative/normative.py — Compute normative distributions:
   - Process all subjects through pipeline
   - Bin by age (decade bins, configurable)
   - Compute mean, SD, percentiles per metric per channel per band per bin
   - Output as JSON and CSV

4. open_normative/compare.py — Compare a single recording against norms:
   - Load clinical metrics (from CW stage JSON or direct pipeline output)
   - Match age bin and condition
   - Compute z-scores and percentile ranks
   - Output comparison report

5. README.md with methodology overview, dataset descriptions, and usage

6. pyproject.toml with dependencies (MNE, specparam, etc.)

CRITICAL: The pipeline parameters must be extractable as a configuration 
dict that CW can import directly, guaranteeing identical processing. 
Consider a shared config module or a parameters.json that both packages read.

OUT OF SCOPE: Don't touch CW's codebase. This is a new standalone package. 
CW will import from it later.
```

### Phase 2: Process Datasets (2–4 weeks, compute-heavy)

**Goal:** Run all source datasets through the pipeline, generate normative tables.

This is compute-intensive. Processing 228 LEMON subjects + 608 Dortmund subjects + 3,000+ HBN subjects through full ICA decomposition takes significant CPU time. Plan for running on the "brains" NUC 9 or a cloud compute instance.

**Claude Code prompt for batch processing:**

```
CONTEXT: The open-normative-eeg pipeline is built. I need to process 
all source datasets and generate normative reference tables.

GOAL: Create a batch processing script at scripts/process_all.py that:

1. For each dataset (LEMON, Dortmund, HBN, MIPDB):
   a. Download/validate source data (check checksums)
   b. Process each subject through the pipeline
   c. Log all parameters and any processing failures
   d. Save per-subject metrics as JSON
   e. Flag subjects that failed QC (>3 bad channels, >50% epochs rejected)
   f. Generate per-dataset summary statistics

2. After all datasets are processed:
   a. Combine subjects across datasets (with dataset source tagged)
   b. Compute age-binned normative distributions
   c. Report sample size per bin, flag bins with N < 30
   d. Output normative_tables.json and normative_tables.csv
   e. Generate a processing report with QC summary

3. Log everything. Every subject, every parameter, every rejection reason.

The script should be resumable—if it crashes at subject 150 of LEMON, 
it should pick up at 151 on restart.

Estimated compute time: [estimate based on ~2 minutes per subject for 
full pipeline × ~4,000 subjects = ~140 hours]. Plan for parallelization 
where possible (subjects are independent).
```

**Using AI for QC:** After batch processing, use Claude to review the QC summary:

```
CONTEXT: I've processed [N] subjects through the open-normative-eeg 
pipeline. Here is the QC summary report [attach].

GOAL: Review the QC results and flag:
1. Subjects with anomalous metrics that might indicate processing errors 
   (not clinical anomalies—processing artifacts)
2. Age bins with insufficient sample size
3. Any systematic differences between datasets that might indicate 
   pipeline inconsistency (e.g., LEMON spectral power systematically 
   higher than HBN after accounting for age)
4. Recommendations for which subjects to exclude from normative tables

Be conservative—when in doubt, exclude. A smaller, cleaner normative 
database is more valuable than a larger contaminated one.
```

### Phase 3: Validation (1–2 weeks)

**Goal:** Prove the normative tables are trustworthy.

1. **Internal consistency:** Split-half reliability. Randomly divide subjects into two halves, compute normative tables separately, compare. The tables should be very similar (r > 0.95 for all metrics).

2. **Cross-dataset consistency:** Compare LEMON-only norms to Dortmund-only norms in the overlapping age range (20–35 and 59–70). They should agree within expected demographic and equipment variance. Also compare HBN-only norms to MIPDB-only norms in the overlapping pediatric range. Systematic differences may indicate equipment effects (BrainProducts vs EGI) that need to be modeled or documented.

3. **Known-effect validation:** Eyes-open alpha power should be significantly lower than eyes-closed alpha power. If the normative tables don't show this well-established effect, something is wrong.

4. **Comparison to published norms:** Where possible, compare computed z-scores to published values from NeuroGuide or HBI for the same metrics. They won't match exactly (different pipelines), but they should agree on the direction and approximate magnitude of effects.

### Phase 4: Documentation & Publication (1–2 weeks)

**Goal:** Make the engine citable and trustworthy.

1. **Methodology paper.** Submit to *Scientific Data* or *Data in Brief*. Describe the pipeline, the datasets, the normative tables, the validation results. This makes the engine citable in clinical reports and gives it academic credibility.

2. **GitHub documentation.** README, API reference, usage examples, parameter justifications.

3. **"Why Open?" explainer.** A page in the docs explaining the philosophy: transparency as a prerequisite for trust. "Every other normative database in clinical QEEG is a black box. This one shows its work."

### Phase 5: Integration with CW (1 week)

**Goal:** CW imports the open-source engine and displays its outputs.

CW adds `open-normative-eeg` as a dependency. The normative comparison stage of CW's pipeline calls the open engine's comparison function. The results are displayed in CW's dashboard alongside the structural analysis.

The integration is thin: CW calls the engine, gets z-scores and percentiles, and displays them. All the structural understanding—the three-layer model, the phenotype detection, the AI Research Assistant—sits on top of and contextualizes those numbers.

---

## Pipeline Features: Prioritized Roadmap

These features go beyond basic z-score computation and represent the methodological rigor that makes the open normative engine worth citing. Prioritized by impact on normative quality and implementation complexity.

### Tier 1: Ship With v1.0 (Essential for Credibility)

**1. GSF (Global Scale Factor) Correction**

Non-neurophysiological variance—skull thickness, hair, skin conductance, amplifier gain differences, electrode impedance—scales the entire power spectrum uniformly across channels. GSF accounts for roughly 42% of total variance in age-corrected EEG data. Without it, a thin-skulled person looks globally hot and a thick-haired person looks globally cold. Neither finding is neurological.

This is *especially* critical for the multi-dataset approach. LEMON and Dortmund use BrainProducts amplifiers. HBN uses EGI. Different amplifier gain structures produce different absolute power levels. GSF normalizes this out before cross-dataset comparison.

Implementation:
```python
import numpy as np

def compute_gsf(psd_array):
    """
    psd_array: shape (n_channels, n_freqs) — power spectral density
    Returns: GSF-corrected PSD
    """
    log_psd = np.log10(psd_array)
    gsf = np.mean(log_psd)  # global mean across all channels and freqs
    return 10 ** (log_psd - gsf)
```

Apply after spectral computation, before z-score comparison. The normative tables store GSF-corrected values. Clinical data is GSF-corrected the same way before comparison.

Note: specparam's aperiodic fit absorbs *some* global scaling, but GSF is more principled for the uncorrected band-power metrics (absolute power, coherence). Both corrections should be applied—GSF first (removes global scaling), then specparam (separates periodic from aperiodic).

**2. Individual Alpha Frequency (IAF)**

Fixed 8–12 Hz alpha band boundaries mischaracterize anyone whose peak alpha is outside 9–11 Hz. A person with alpha at 8 Hz has their alpha split across the theta and alpha bands—"elevated theta" and "low alpha" that are entirely artifacts of the boundary, not the brain.

Implementation: Compute IAF per subject using the method from Corcoran et al. (2018)—center of gravity of the alpha peak region. Report IAF prominently. Use fixed bands for primary z-scores (what clinicians expect) but flag when IAF is outside the 9–11 Hz typical range, because fixed band boundaries may mischaracterize the spectrum.

Future: Offer IAF-adjusted band boundaries as a secondary normative comparison option. This is methodologically superior but complicates normative comparison (the normative distributions need to be computed in IAF-relative terms).

**3. CBCL/Phenotypic Filtering for HBN**

HBN is not a healthy sample. Filtering or regression correction is mandatory for normative use.

Implementation options (offer all three as selectable normative references):
- **Strict filter:** Exclude subjects with CBCL Total Problems T-score > 60
- **Regression-corrected:** Regress out CBCL subscale variance from EEG metrics, keep full N
- **Unfiltered (labeled):** Full sample, clearly labeled as "community-referred, not normative"

The regression approach preserves statistical power. The filtered approach is simpler and more conservative. Offering both lets the clinician choose—and teaches them to think critically about what "normative" means.

**4. Artifact Detection and Classification (Gunkelman Standards)**

Not just "reject bad data" but *classify what kind of artifact contaminated it*. This matters for QC reporting—knowing that 30% of a recording was rejected for eye blinks is different from knowing 30% was rejected for EMG.

Detection thresholds:
- **EOG:** Peak-to-peak amplitude > 100 µV in frontal channels (Fp1, Fp2), especially with characteristic slow waveform
- **EMG:** Elevated broadband power above 30 Hz, especially in temporal channels (T3, T4, T5, T6)
- **Electrode pop:** Sudden spike > 200 µV in a single channel, duration < 100ms
- **Movement:** Simultaneous slow drift > 200 µV across multiple channels
- **Sweat artifact:** Very low frequency drift < 0.5 Hz with characteristic slow ramp

Report per subject: which artifact types were present, what percentage of data each type contaminated, and what remained after removal.

**5. Minimum Usable Data Duration**

After artifact removal, flag subjects with less than 2 minutes of clean resting data per condition. Below this threshold, spectral estimates are unstable (especially for low frequencies) and the subject should be excluded from normative tables.

Report: pre-rejection duration, post-rejection duration, rejection rate, and a pass/fail flag per condition.

**6. Confidence Intervals Per Cell**

Every normative value should report not just mean and SD but a confidence interval based on the bin's sample size. A z-score computed against a bin with N=200 means something different than a z-score against a bin with N=15.

Implementation: Report 95% CI for the mean of each normative cell. In the comparison output, flag z-scores where the normative bin has N < 30 or wide CI. Let the clinician see the precision of the reference, not just the value.

**7. Split-Half and Cross-Dataset Reliability**

Compute and report:
- Split-half reliability (r) for each metric in each age bin—how stable are the norms internally?
- Cross-dataset agreement for overlapping age ranges (LEMON vs Dortmund at ages 20–35 and 59–70)
- Flag metrics or bins with reliability below r = 0.80

This is validation evidence AND a feature. No competitor publishes their normative reliability. You would.

### Tier 2: Ship With v1.1 (Valuable, Not Blocking)

**8. Hemispheric Asymmetry Indices**

Left-right power differences at homologous pairs: F3/F4, C3/C4, P3/P4, O1/O2. Compute as (R-L)/(R+L) to normalize for overall power level. Report per frequency band.

Clinically relevant for depression screening (frontal alpha asymmetry), lateralized lesions, and hemispheric dominance patterns. Standard in NeuroGuide.

**9. Finer Age Binning**

Decade bins are standard but crude. The brain changes rapidly in childhood and slowly in middle age. Appropriate bin widths:
- Ages 5–16: yearly bins (brain developing rapidly)
- Ages 16–20: two-year bins (transitional period)
- Ages 20–70+: five-year bins (slower change)

This requires sufficient N per bin, which is why it's Tier 2—verify that HBN has enough subjects per yearly bin in the pediatric range before committing to this granularity.

**10. Age Interpolation Between Bins**

Instead of hard bin edges (29-year-old compared against 20–29 bin, 30-year-old jumps to 30–39 bin), compute weighted averages of adjacent bin statistics based on the subject's exact age. A 29-year-old gets a reference that's 90% weighted from the 20–29 bin and 10% from the 30–39 bin.

Eliminates discontinuities at bin boundaries. Simple to implement, meaningfully improves accuracy for subjects near bin edges.

**11. Effect Size (Cohen's d) Alongside Z-Scores**

Z-scores tell you how many SDs from the mean. Cohen's d tells you how *clinically meaningful* that deviation is relative to the variability in the population. For metrics with high inter-individual variance, a z-score of 2.0 might not be clinically significant. For metrics with low variance, a z-score of 1.5 might be very significant.

Report Cohen's d alongside z-scores. Include benchmarks: d = 0.2 (small), 0.5 (medium), 0.8 (large). This helps clinicians calibrate their sense of what "deviant" means for each metric.

**12. Multiple Comparison Correction**

A standard 19-channel × 6-band QEEG report tests 114 values. At p = 0.05, you expect ~6 "significant" deviations by chance alone. Without correction, clinicians over-interpret noise.

Implement FDR (Benjamini-Hochberg)—less conservative than Bonferroni, controls the expected proportion of false positives. Report both uncorrected and FDR-corrected significance alongside each z-score.

This is rare in clinical QEEG tools and would be a methodological differentiator. NeuroGuide doesn't correct for multiple comparisons. WinEEG doesn't. The field has been ignoring this problem for decades.

**13. Clinical Severity Thresholds (Named Levels)**

Provide interpretive anchors for z-score ranges. Not diagnoses—organizational labels:
- |z| < 1.0: Within typical range
- |z| 1.0–1.5: Mildly atypical
- |z| 1.5–2.0: Moderately atypical
- |z| 2.0–2.5: Notably atypical
- |z| 2.5–3.0: Markedly atypical
- |z| > 3.0: Extremely atypical

These are descriptive, not diagnostic. They give clinicians (especially less experienced ones) a vocabulary for the numbers. The language is deliberately structural—"atypical," not "abnormal"—consistent with VOICE.md.

### Tier 3: Future / Research Phase

**14. Post-ICA Quality Verification**

After ICA artifact removal, re-run the artifact detection checks. Verify that EOG, EMG, and other artifacts were actually removed. If artifact signatures persist post-ICA, the ICA decomposition failed or the wrong components were rejected. Flag these subjects.

This is a quality gate that almost no automated pipeline implements. It catches the failure mode where ICA "succeeds" (runs without error) but doesn't actually clean the data.

**15. Normative Aging Trajectories (Dortmund Longitudinal)**

Using the 208 Dortmund subjects with 5-year follow-up: compute within-subject change trajectories for each metric. What does healthy aging look like in the spectral slope? In alpha power? In frontal theta?

This enables a future CW feature: compare a client's longitudinal changes (pre/post treatment) not just against static norms but against the expected trajectory of healthy aging. A 60-year-old whose alpha power increases after treatment—is that improvement, or just noise? The aging trajectory tells you what direction healthy change goes.

No competitor has this. The data exists now. Process it separately; integrate later.

### Feature Priority Matrix

| # | Feature | Tier | Complexity | Impact | Dependencies |
|---|---------|------|------------|--------|--------------|
| 1 | GSF correction | v1.0 | Low | High — critical for multi-dataset | None |
| 2 | IAF computation | v1.0 | Low | High — prevents mischaracterization | None |
| 3 | CBCL filtering/regression | v1.0 | Medium | High — HBN unusable without it | HBN phenotypic data access |
| 4 | Artifact type classification | v1.0 | Medium | High — QC credibility | None |
| 5 | Minimum data duration | v1.0 | Low | Medium — quality gate | Artifact detection |
| 6 | Confidence intervals | v1.0 | Low | High — precision transparency | None |
| 7 | Reliability metrics | v1.0 | Medium | High — publishable, unique | Full processing complete |
| 8 | Hemispheric asymmetry | v1.1 | Low | Medium — expected by clinicians | None |
| 9 | Finer age bins | v1.1 | Low | Medium — pediatric precision | Sufficient N per bin |
| 10 | Age interpolation | v1.1 | Low | Medium — eliminates edge artifacts | Age bins defined |
| 11 | Cohen's d | v1.1 | Low | Medium — clinical calibration | None |
| 12 | Multiple comparison correction | v1.1 | Low | High — methodological differentiator | None |
| 13 | Clinical severity thresholds | v1.1 | Low | Medium — accessibility | VOICE.md compliance |
| 14 | Post-ICA quality check | Future | Medium | Medium — catches silent failures | ICA pipeline |
| 15 | Aging trajectories | Future | High | High — unique asset | Dortmund longitudinal processed |

---

## Regulatory Implications

### What this changes

The normative engine is an open-source research tool. It computes statistics. It doesn't diagnose, recommend, or interpret. Anyone can use it, inspect it, verify it, modify it. It's a calculator, not a clinical instrument.

CW *uses* the engine the same way it uses MNE-Python or specparam—as an open-source computational dependency. The regulatory surface of CW is about what CW does with the numbers (display, contextualize, describe structure), not about how the numbers are computed.

### What this doesn't change

If FDA decides CW is a medical device, the normative engine being open source doesn't change that determination. The *product*—CW as a whole, with its clinical workflow and AI—is what FDA would evaluate. But the transparency argument strengthens every conversation:

"Our normative methodology is fully open source, published, peer-reviewed, and independently verifiable. The processing pipeline is identical for normative and clinical data—you can confirm this by reading the code. No other clinical QEEG tool offers this level of transparency."

That's not a regulatory argument. It's a credibility argument. And credibility is what actually matters in this market.

### The key separation

The open-source engine says: "This value is 2.3 standard deviations from the age-matched reference mean."

CW says: "Here is the structural organization of this brain—substrate, architecture, dynamics—and here is where the normative reference values sit within that structure, for your consideration."

The engine measures. CW helps you understand. The line between them is clean.

---

## Timeline Summary

| Phase | Duration | Key Deliverable |
|-------|----------|----------------|
| 1: Pipeline Extraction | 2–3 weeks | Standalone `open-normative-eeg` package |
| 2: Process Datasets | 2–4 weeks | Normative reference tables (JSON/CSV) |
| 3: Validation | 1–2 weeks | Validation report, split-half reliability, cross-dataset consistency |
| 4: Documentation | 1–2 weeks | Methodology paper draft, GitHub docs, "Why Open?" page |
| 5: CW Integration | 1 week | Normative comparison live in CW dashboard |
| **Total** | **7–12 weeks** | **Open-source normative engine, published, validated, integrated** |

---

## What This Costs

Primarily time, not money.

- **Compute:** Processing ~4,000 subjects is CPU-intensive but runs on existing hardware (brains NUC 9). Cloud compute for parallelization: ~$50–$200 on AWS/GCP spot instances if you want to speed it up.
- **Storage:** Raw datasets are ~600–700GB total (LEMON ~55GB raw, Dortmund ~TBD verify, HBN ~500GB+). Processed outputs much smaller. Existing infrastructure handles this.
- **James's time:** Reviewing methodology decisions, writing the "Why Open?" narrative, reviewing the validation results. Maybe 20–30 hours over the 7–12 week timeline.
- **Cyrus's time:** Pipeline extraction, batch processing scripts, validation suite, documentation. This is the bulk of the implementation work—spec-first, then Claude Code.
- **Publication:** *Scientific Data* and *Data in Brief* have article processing charges (~$1,500–$2,000). Worthwhile for the citability and credibility.

---

## The Strategic Payoff

1. **"We show our work"** becomes an unchallengeable competitive claim. No competitor can say this.

2. **Pipeline consistency becomes verifiable.** Not a marketing claim—a checkable fact. Anyone can read the code and confirm normative and clinical data go through identical processing.

3. **Academic credibility.** A published, peer-reviewed methodology paper makes CW citable in research contexts. Researchers who use the open engine in their work become aware of CW.

4. **Community building.** An open-source normative engine attracts contributors: researchers who want to add datasets, improve processing, extend the methodology. Every contribution makes CW's normative layer stronger.

5. **Regulatory positioning.** The engine is a research tool. CW is a structural understanding tool that happens to display the engine's outputs. The boundary is architecturally clean.

6. **Lifespan coverage with no gaps.** Ages 5 through 77, from four datasets, all healthy samples (or regression-corrected), all processed through identical code paths. No other open or commercial normative database achieves this range with this transparency.

7. **Longitudinal aging norms (unique).** The Dortmund 5-year follow-up data enables normative change trajectories—what does healthy EEG aging look like? No competitor can offer this. Future feature, but the data asset is secured now.

8. **The argument against every black-box competitor.** "Our normative methodology is open. Theirs isn't. Which one can you trust?"
