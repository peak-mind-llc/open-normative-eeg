"""Canonical pipeline parameters for open-normative-eeg.

These parameters are extracted from Coherence Workstation's configs/default.yaml
and processing code. They define the exact processing pipeline used for both
normative database construction and clinical EEG analysis.

CW imports this dict to guarantee identical processing.

REPORT_PARAMS configures the clinical comparison report — severity labels,
effect size thresholds, pattern detection, and spatial adjacency for the
19-channel 10-20 montage.

Determinism note: all stochastic steps (ICA, RANSAC, ICLabel) are seeded
with random_state=42 here; specparam's fit is scipy curve_fit (LM,
deterministic). On a single machine the pipeline is bit-identical across
runs (enforced by tests/test_determinism.py). For bit-identity across
*different* machines — needed by the AWS-Batch reproducibility gate — the
container must pin BLAS threads:
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
otherwise BLAS reduction order varies with thread count and introduces
sub-ULP drift. Batch entrypoint sets those env vars.
"""

PIPELINE_PARAMS = {
    "preprocessing": {
        "resample": {
            "enabled": True,
            "target_sfreq": 256.0,
        },
        "filter": {
            "l_freq": 0.5,
            "h_freq": 100.0,
            "notch_freq": 60.0,
            "notch_harmonics": [120.0, 180.0],
            "notch_width": 2.0,
        },
        "bad_channels": {
            "method": "ransac",
            "correlation_threshold": 0.75,
            "flat_threshold_factor": 0.01,
            "noisy_threshold_factor": 10.0,
        },
        # ASR (burst reconstruction) is DISABLED by default — the canonical
        # pipeline is Neurofield-style (filter → bad ch → reference → ICA)
        # with no ASR. ASR remains available as an opt-in advanced feature
        # for research use; set asr.enabled=True to re-enable. See the
        # design note in open_normative.preprocessing.preprocess().
        "asr": {
            "enabled": False,
            "cutoff": 20,
            "window_length": 0.5,
        },
        # Line noise detection is DISABLED by default — pyprep RANSAC
        # already catches most line-noise-dominated channels via the
        # correlation check. This detector is available for cases where
        # line noise is a primary concern and RANSAC alone is insufficient.
        "line_noise": {
            "enabled": False,
            "line_freq": 60.0,
            "max_ratio": 0.4,
            "bandwidth": 2.0,
        },
        # Window rejection is DISABLED by default. Neurofield-style
        # cleaning does not drop windows; any residual artifact after
        # ICA rejection is handled clinically via manual artifact
        # annotation in the DataPrep workflow (CAP-01 §6).
        "window_rejection": {
            "enabled": False,
            "window_length": 0.5,
            "threshold_multiplier": 5.0,
        },
        "ica": {
            "method": "picard",
            "extended": True,
            # n_components: None → auto-compute as min(data_rank, nbchan-1).
            # This avoids rank collapse on drifty data (the old 0.999
            # variance-fraction default would fit only 5-10 components
            # when low-frequency drift dominated variance). Callers who
            # want explicit control can still pass an int or float <1.0.
            "n_components": None,
            "max_iter": 500,
            "random_state": 42,
            "two_stage_filter": True,
            "ica_highpass": 1.0,
            # ICLabel auto-decision thresholds:
            #   brain >= brain_threshold         → auto-keep
            #   brain < brain_threshold          → review
            #   non-brain >= review_threshold    → auto-reject
            #   non-brain < review_threshold     → review
            # Bumped review_threshold from 0.50 → 0.60 (April 2026) to
            # be more conservative on borderline artifact calls — the
            # clinician still sees review-flagged components and can
            # confirm.
            "brain_threshold": 0.80,
            "review_threshold": 0.60,
        },
        "reference": "average",
    },
    "spectral": {
        "method": "welch",
        "fmin": 0.5,
        "fmax": 50.0,
        "n_fft": 1024,
        "bands": {
            "Delta": [1, 4],
            "Theta": [4, 8],
            "Alpha": [8, 13],
            "Alpha1": [8, 10.5],
            "Alpha2": [10.5, 13],
            "Beta": [13, 30],
            "Beta1": [13, 15],
            "Beta2": [15, 18],
            "Beta3": [18, 25],
            "HighBeta": [25, 30],
            "Gamma": [30, 50],
        },
        # Each ratio is {"name", "num": [bands], "den": [bands]}.
        # Numerator and denominator are summed before division, so
        # composites like (Delta+Theta)/(Alpha+Beta) work uniformly.
        "ratios": [
            {"name": "Theta/Beta",        "num": ["Theta"], "den": ["Beta"]},
            {"name": "Theta/Beta1",       "num": ["Theta"], "den": ["Beta1"]},
            {"name": "Delta/HighBeta",    "num": ["Delta"], "den": ["HighBeta"]},
            {"name": "Alpha/HighBeta",    "num": ["Alpha"], "den": ["HighBeta"]},
            {"name": "Alpha/Theta",       "num": ["Alpha"], "den": ["Theta"]},
            {"name": "Delta/Alpha",       "num": ["Delta"], "den": ["Alpha"]},
            {"name": "Alpha/Beta",        "num": ["Alpha"], "den": ["Beta"]},
            {"name": "(Delta+Theta)/(Alpha+Beta)",
             "num": ["Delta", "Theta"], "den": ["Alpha", "Beta"]},
        ],
        "aperiodic": {
            "freq_range": [2, 40],
            "r_squared_threshold": 0.85,
            "peak_width_limits": [1, 8],
            "max_n_peaks": 6,
            "min_peak_height": 0.1,
            "peak_threshold": 2.0,
        },
        "asymmetry": {
            "homologous_pairs": [
                ["F3", "F4"],
                ["C3", "C4"],
                ["P3", "P4"],
                ["T3", "T4"],
                ["T5", "T6"],
                ["F7", "F8"],
                ["O1", "O2"],
            ],
            "homologous_pairs_37": [
                ["F3", "F4"],
                ["C3", "C4"],
                ["P3", "P4"],
                ["T3", "T4"],
                ["T5", "T6"],
                ["F7", "F8"],
                ["O1", "O2"],
                ["AF3", "AF4"],
                ["FC3", "FC4"],
                ["FC1", "FC2"],
                ["FT7", "FT8"],
                ["CP3", "CP4"],
                ["CP1", "CP2"],
                ["TP7", "TP8"],
                ["PO3", "PO4"],
                ["P1", "P2"],
            ],
            "threshold": 0.15,
        },
        "gsf": {
            "enabled": True,
        },
        "iaf": {
            "search_range": [7, 14],
            "posterior_channels": ["O1", "O2", "Pz", "P3", "P4"],
            "typical_range": [9, 11],
        },
    },
    "connectivity": {
        "epoch_length": 2.0,
        "epoch_overlap": 0.0,
        "min_epochs": 30,
        "max_epochs": 120,
        "methods": ["dwpli", "coh"],
        "bands": {
            "Delta": [1, 4],
            "Theta": [4, 8],
            "Alpha": [8, 13],
            "Beta": [13, 30],
            "HighBeta": [25, 30],
            "Gamma": [30, 50],
        },
        "hubs": {
            "F_mid": ["Fz"],
            "F_L": ["F3", "F7"],
            "F_R": ["F4", "F8"],
            "C_mid": ["Cz"],
            "T_L": ["T3", "T5"],
            "T_R": ["T4", "T6"],
            "P_mid": ["Pz"],
            "P_L": ["P3"],
            "P_R": ["P4"],
            "O": ["O1", "O2"],
        },
        "hubs_37": {
            "FP": ["Fp1", "Fp2"],
            "AF_L": ["AF3"],
            "AF_R": ["AF4"],
            "F_mid": ["Fz", "FC1", "FC2"],
            "F_L": ["F3", "F7", "FC3"],
            "F_R": ["F4", "F8", "FC4"],
            "C_mid": ["Cz"],
            "T_L": ["T3", "T5", "FT7", "TP7"],
            "T_R": ["T4", "T6", "FT8", "TP8"],
            "P_mid": ["Pz", "CP1", "CP2", "P1", "P2"],
            "P_L": ["P3", "CP3"],
            "P_R": ["P4", "CP4"],
            "PO_L": ["PO3"],
            "PO_R": ["PO4"],
            "O": ["O1", "O2"],
        },
        "graph": {
            "threshold_percentile": 75,
        },
        "cfc": {
            "enabled": True,
            "phase_band": [4, 8],
            "amp_band": [30, 45],
            "n_bins": 18,
            "hub_pairs": [
                ["F_mid", "P_mid"],
                ["F_L", "T_L"],
                ["F_R", "T_R"],
                ["T_L", "P_mid"],
                ["F_mid", "T_L"],
                ["F_mid", "T_R"],
            ],
        },
    },
    "channels": {
        "target_montage": "standard_1020",
        "channels_19": [
            "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
            "T3", "C3", "Cz", "C4", "T4",
            "T5", "P3", "Pz", "P4", "T6",
            "O1", "O2",
        ],
        "channels_37": [
            # Standard 10-20 (19 channels)
            "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
            "T3", "C3", "Cz", "C4", "T4",
            "T5", "P3", "Pz", "P4", "T6",
            "O1", "O2",
            # Extended 10-10 positions (18 additional)
            # Selected to match pre-computed source localization forward model
            "AF3", "AF4",
            "FC3", "FC1", "FC2", "FC4",
            "FT7", "FT8",
            "CP3", "CP1", "CP2", "CP4",
            "TP7", "TP8",
            "PO3", "PO4",
            "P1", "P2",
        ],
        "name_mapping": {
            "T7": "T3",
            "T8": "T4",
            "P7": "T5",
            "P8": "T6",
        },
        "capitalization_fixes": {
            "FP1": "Fp1",
            "FP2": "Fp2",
            "FPZ": "Fpz",
        },
    },
}


REPORT_PARAMS = {
    "severity": {
        "thresholds": [0.5, 1.0, 1.5, 2.0, 3.0],
        "labels": [
            "Within typical limits",
            "Mildly atypical",
            "Moderately atypical",
            "Notably atypical",
            "Markedly atypical",
            "Extremely atypical",
        ],
    },
    "cohen_d": {
        "negligible": 0.2,
        "small": 0.2,
        "medium": 0.5,
        "large": 0.8,
    },
    "global_pattern": {
        "channel_fraction_threshold": 0.6,
        "z_threshold": 1.5,
    },
    "cluster": {
        "z_threshold": 1.5,
    },
    "disagreement": {
        "z_threshold": 1.5,
    },
    # Robust (percentile-derived) z-score and distribution-trust flags.
    # Wood et al. (2024): the parametric z assumes Gaussianity that EEG band
    # power violates, so when a cell's scoring space fails the normality test
    # we also report a robust z derived from the empirical percentile rank and
    # flag the divergence between the two.
    "robust_z": {
        "normality_alpha": 0.05,        # scoring-space Shapiro p below this is "non-normal"
        "discrepancy_threshold": 1.0,   # |parametric_z - robust_z| above this is flagged
        "tail_percentile_min_n": 200,   # n below this: don't trust p0.5/p99.5, clamp to p1/p99
    },
    "adjacency_19": {
        "Fp1": ["Fp2", "F3", "F7"],
        "Fp2": ["Fp1", "F4", "F8"],
        "F7":  ["Fp1", "F3", "T3"],
        "F3":  ["Fp1", "F7", "Fz", "C3"],
        "Fz":  ["F3", "F4", "Cz"],
        "F4":  ["Fp2", "Fz", "F8", "C4"],
        "F8":  ["Fp2", "F4", "T4"],
        "T3":  ["F7", "C3", "T5"],
        "C3":  ["F3", "T3", "Cz", "P3"],
        "Cz":  ["Fz", "C3", "C4", "Pz"],
        "C4":  ["F4", "Cz", "T4", "P4"],
        "T4":  ["F8", "C4", "T6"],
        "T5":  ["T3", "P3", "O1"],
        "P3":  ["C3", "T5", "Pz", "O1"],
        "Pz":  ["Cz", "P3", "P4"],
        "P4":  ["C4", "Pz", "T6", "O2"],
        "T6":  ["T4", "P4", "O2"],
        "O1":  ["T5", "P3", "O2"],
        "O2":  ["T6", "P4", "O1"],
    },
    "adjacency_37": {
        "Fp1":  ["Fp2", "AF3", "F3", "F7"],
        "Fp2":  ["Fp1", "AF4", "F4", "F8"],
        "AF3":  ["Fp1", "F3", "FC1", "FC3"],
        "AF4":  ["Fp2", "F4", "FC2", "FC4"],
        "F7":   ["Fp1", "F3", "FT7", "FC3"],
        "F3":   ["Fp1", "AF3", "F7", "Fz", "FC3", "FC1"],
        "Fz":   ["F3", "F4", "FC1", "FC2", "Cz"],
        "F4":   ["Fp2", "AF4", "Fz", "F8", "FC2", "FC4"],
        "F8":   ["Fp2", "F4", "FT8", "FC4"],
        "FT7":  ["F7", "FC3", "T3"],
        "FC3":  ["AF3", "F7", "F3", "FT7", "FC1", "C3", "T3"],
        "FC1":  ["AF3", "F3", "Fz", "FC3", "FC2", "C3", "Cz"],
        "FC2":  ["AF4", "Fz", "F4", "FC1", "FC4", "Cz", "C4"],
        "FC4":  ["AF4", "F4", "F8", "FC2", "FT8", "C4", "T4"],
        "FT8":  ["F8", "FC4", "T4"],
        "T3":   ["FT7", "FC3", "C3", "TP7", "T5"],
        "C3":   ["FC3", "FC1", "T3", "Cz", "CP3", "CP1"],
        "Cz":   ["FC1", "FC2", "C3", "C4", "CP1", "CP2"],
        "C4":   ["FC2", "FC4", "Cz", "T4", "CP2", "CP4"],
        "T4":   ["FT8", "FC4", "C4", "TP8", "T6"],
        "TP7":  ["T3", "T5", "CP3"],
        "CP3":  ["C3", "T5", "TP7", "CP1", "P3"],
        "CP1":  ["C3", "Cz", "CP3", "CP2", "P3", "P1", "Pz"],
        "CP2":  ["Cz", "C4", "CP1", "CP4", "Pz", "P2", "P4"],
        "CP4":  ["C4", "T6", "CP2", "TP8", "P4"],
        "TP8":  ["T4", "T6", "CP4"],
        "T5":   ["T3", "TP7", "CP3", "P3", "PO3", "O1"],
        "P3":   ["CP3", "CP1", "T5", "P1", "Pz", "PO3"],
        "P1":   ["CP1", "P3", "Pz", "PO3"],
        "Pz":   ["CP1", "CP2", "P1", "P3", "P4", "P2"],
        "P2":   ["CP2", "Pz", "P4", "PO4"],
        "P4":   ["CP2", "CP4", "Pz", "P2", "T6", "PO4"],
        "T6":   ["T4", "CP4", "TP8", "P4", "PO4", "O2"],
        "PO3":  ["T5", "P3", "P1", "O1", "O2"],
        "PO4":  ["P2", "P4", "T6", "O1", "O2"],
        "O1":   ["T5", "PO3", "PO4", "O2"],
        "O2":   ["PO4", "T6", "PO3", "O1"],
    },
    "fdr_alpha": 0.05,
    "low_confidence_n": 10,
    "prediction_interval_confidence": 0.95,
}
