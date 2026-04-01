"""Canonical pipeline parameters for open-normative-eeg.

These parameters are extracted from Coherence Workstation's configs/default.yaml
and processing code. They define the exact processing pipeline used for both
normative database construction and clinical EEG analysis.

CW imports this dict to guarantee identical processing.
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
        "asr": {
            "cutoff": 20,
            "window_length": 0.5,
        },
        "ica": {
            "method": "picard",
            "extended": True,
            "n_components": 0.999,
            "max_iter": 500,
            "random_state": 42,
            "two_stage_filter": True,
            "ica_highpass": 1.0,
            "brain_threshold": 0.80,
            "review_threshold": 0.50,
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
        "ratios": [
            ["Theta", "Beta"],
            ["Theta", "Beta1"],
            ["Delta", "HighBeta"],
            ["Alpha", "HighBeta"],
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
        "methods": ["dwpli", "coh", "imcoh"],
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
