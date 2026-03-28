"""Spectral analysis: PSD, band powers, aperiodic fitting, asymmetry.

Mirrors CW's resting.py spectral computations with identical parameters.
"""

import warnings

import numpy as np


def compute_psd(raw, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Compute power spectral density using Welch's method.

    Args:
        raw: MNE Raw object (preprocessed).
        params: Spectral params with method, fmin, fmax, n_fft.

    Returns:
        (psds, freqs) — psds shape (n_channels, n_freqs), in V²/Hz.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="nperseg.*greater than input length")
        spectrum = raw.compute_psd(
            method=params.get("method", "welch"),
            fmin=params["fmin"],
            fmax=params["fmax"],
            n_fft=params.get("n_fft", 1024),
            verbose=False,
        )
    psds = spectrum.get_data()
    freqs = spectrum.freqs
    return psds, freqs


def compute_band_power(
    psds: np.ndarray, freqs: np.ndarray, bands: dict
) -> dict:
    """Compute absolute and relative band power for each channel.

    Args:
        psds: Shape (n_channels, n_freqs), in V²/Hz.
        freqs: Frequency array.
        bands: Dict of {band_name: [fmin, fmax]}.

    Returns:
        Dict of {band_name: {"absolute": array, "relative": array}}.
    """
    total_power = np.trapezoid(psds, freqs, axis=1)
    band_power = {}
    for band_name, (fmin, fmax) in bands.items():
        idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
        if len(idx) == 0:
            band_power[band_name] = {
                "absolute": np.zeros(psds.shape[0]),
                "relative": np.zeros(psds.shape[0]),
            }
            continue
        abs_power = np.trapezoid(psds[:, idx], freqs[idx], axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_power = np.where(total_power > 0, abs_power / total_power, 0.0)
        band_power[band_name] = {"absolute": abs_power, "relative": rel_power}
    return band_power


def compute_band_ratios(band_power: dict, ch_names: list[str]) -> dict:
    """Compute key band ratios at each channel."""
    ratio_defs = {
        "Theta/Beta": ("Theta", "Beta"),
        "Theta/Beta1": ("Theta", "Beta1"),
        "Delta/HighBeta": ("Delta", "HighBeta"),
        "Alpha/HighBeta": ("Alpha", "HighBeta"),
    }
    ratios = {}
    for ratio_name, (num_band, den_band) in ratio_defs.items():
        if num_band in band_power and den_band in band_power:
            num = band_power[num_band]["absolute"]
            den = band_power[den_band]["absolute"]
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = np.where(den > 0, num / den, np.nan)
            ratios[ratio_name] = dict(zip(ch_names, ratio.tolist()))
    return ratios


def compute_aperiodic(
    psds: np.ndarray,
    freqs: np.ndarray,
    ch_names: list[str],
    params: dict,
) -> dict:
    """Fit 1/f aperiodic component using specparam (FOOOF) per channel.

    Args:
        psds: Shape (n_channels, n_freqs), in V²/Hz.
        freqs: Frequency array.
        ch_names: Channel names.
        params: Aperiodic params (freq_range, thresholds, peak settings).

    Returns:
        Dict of {ch_name: {exponent, offset, slope, r_squared, ...}}.
    """
    from specparam import SpectralModel

    psds_uv = psds * 1e12
    r_sq_threshold = params.get("r_squared_threshold", 0.85)
    results = {}

    for i, ch in enumerate(ch_names):
        sm = SpectralModel(
            peak_width_limits=params.get("peak_width_limits", [1, 8]),
            max_n_peaks=params.get("max_n_peaks", 6),
            min_peak_height=params.get("min_peak_height", 0.1),
            peak_threshold=params.get("peak_threshold", 2.0),
            verbose=False,
        )
        try:
            sm.fit(freqs, psds_uv[i], params.get("freq_range", [2, 40]))
            if hasattr(sm, "aperiodic_params_"):
                exponent = float(sm.aperiodic_params_[-1])
                offset = float(sm.aperiodic_params_[0])
                r_squared = float(sm.r_squared_)
                n_peaks = int(sm.n_peaks_)
                peak_params = sm.peak_params_.tolist() if sm.n_peaks_ > 0 else []
            else:
                ap = sm.results.params.aperiodic
                exponent = float(ap.params[ap.indices["exponent"]])
                offset = float(ap.params[ap.indices["offset"]])
                r_squared = float(sm.results.metrics.results.get("gof_rsquared", 0))
                n_peaks = int(sm.results.n_peaks)
                peak_params = sm.results.params.periodic.params.tolist()

            fit_quality = "good" if r_squared >= r_sq_threshold else "poor"
            results[ch] = {
                "exponent": exponent,
                "offset": offset,
                "slope": abs(exponent),  # steepness magnitude; positive by convention
                "r_squared": r_squared,
                "fit_quality": fit_quality,
                "n_peaks": n_peaks,
                "peak_params": peak_params,
            }
        except Exception:
            results[ch] = {
                "exponent": np.nan,
                "offset": np.nan,
                "slope": np.nan,
                "r_squared": 0.0,
                "fit_quality": "failed",
                "n_peaks": 0,
                "peak_params": [],
            }
    return results


def compute_asymmetry(
    band_power: dict, ch_names: list[str], pairs: list[list[str]]
) -> dict:
    """Compute hemispheric asymmetry (laterality index) for homologous pairs.

    Formula: ASI = (Right - Left) / (Right + Left)
    """
    results = {}
    for left, right in pairs:
        if left not in ch_names or right not in ch_names:
            continue
        li = ch_names.index(left)
        ri = ch_names.index(right)
        pair_key = f"{left}/{right}"
        results[pair_key] = {}
        for band_name, powers in band_power.items():
            lp = powers["absolute"][li]
            rp = powers["absolute"][ri]
            denom = lp + rp
            if denom > 0:
                results[pair_key][band_name] = float((rp - lp) / denom)
            else:
                results[pair_key][band_name] = 0.0
    return results


def analyze_spectral(raw, params: dict) -> dict:
    """Run full spectral analysis pipeline.

    Returns:
        Dict with psds, freqs, band_power, ratios, aperiodic, asymmetry.
    """
    psds, freqs = compute_psd(raw, params)
    band_power = compute_band_power(psds, freqs, params["bands"])
    ratios = compute_band_ratios(band_power, raw.ch_names)
    aperiodic = compute_aperiodic(psds, freqs, raw.ch_names, params["aperiodic"])
    asymmetry = compute_asymmetry(
        band_power, raw.ch_names, params["asymmetry"]["homologous_pairs"]
    )
    return {
        "psds": psds,
        "freqs": freqs,
        "band_power": band_power,
        "ratios": ratios,
        "aperiodic": aperiodic,
        "asymmetry": asymmetry,
    }
