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


def compute_band_ratios(
    band_power: dict,
    ch_names: list[str],
    ratio_defs: list[dict],
    power_key: str = "absolute",
) -> dict:
    """Compute frequency band ratios at each channel.

    Args:
        band_power: Dict of {band_name: {power_key: array, ...}}.
        ch_names: Channel names.
        ratio_defs: List of {"name": str, "num": [bands], "den": [bands]}.
            Numerator and denominator bands are summed before division so
            single (Theta/Beta) and composite ((Delta+Theta)/(Alpha+Beta))
            ratios are handled uniformly.
        power_key: Key for power arrays (e.g. "absolute" or
            "corrected_absolute").
    """
    ratios = {}
    for spec in ratio_defs:
        name = spec["name"]
        try:
            num = sum(band_power[b][power_key] for b in spec["num"])
            den = sum(band_power[b][power_key] for b in spec["den"])
        except (KeyError, TypeError):
            continue
        if num is None or den is None:
            continue
        num = np.asarray(num, dtype=float)
        den = np.asarray(den, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(den > 0, num / den, np.nan)
        ratios[name] = dict(zip(ch_names, ratio.tolist()))
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
    try:
        from specparam import SpectralModel
    except ImportError:
        import warnings
        warnings.warn(
            "specparam not installed — skipping aperiodic fitting; "
            "install with: pip install specparam"
        )
        return {ch: {
            "exponent": float("nan"),
            "offset": float("nan"),
            "slope": float("nan"),
            "r_squared": 0.0,
            "fit_quality": "skipped",
            "n_peaks": 0,
            "peak_params": [],
        } for ch in ch_names}

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
                "slope": float(-exponent),
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


def compute_corrected_band_power(
    psds: np.ndarray,
    freqs: np.ndarray,
    aperiodic: dict,
    ch_names: list[str],
    bands: dict,
) -> dict:
    """Compute specparam-corrected (periodic-only) band power per channel.

    Removes the aperiodic (1/f) component from the PSD before computing band
    power, isolating oscillatory activity. Uses log-space subtraction as per
    the standard specparam approach.

    Args:
        psds: Shape (n_channels, n_freqs), in V²/Hz.
        freqs: Frequency array.
        aperiodic: Dict from compute_aperiodic() — {ch: {offset, exponent, ...}}.
        ch_names: Channel names matching psds rows.
        bands: Dict of {band_name: [fmin, fmax]}.

    Returns:
        Dict of {band_name: {"corrected_absolute": array, "corrected_relative": array}}.
        Channels with failed/skipped specparam fits get NaN values.
    """
    n_channels = psds.shape[0]
    # Build periodic-only PSD per channel via log-space subtraction.
    periodic_psds = np.full_like(psds, np.nan)

    for i, ch in enumerate(ch_names):
        ap = aperiodic.get(ch, {})
        fit_quality = ap.get("fit_quality", "skipped")
        if fit_quality in ("failed", "skipped"):
            continue

        offset = ap.get("offset", np.nan)
        exponent = ap.get("exponent", np.nan)
        if np.isnan(offset) or np.isnan(exponent):
            continue

        # Specparam works in log10(µV²/Hz) space.
        # Convert PSD from V²/Hz to µV²/Hz for consistency.
        psd_uv = psds[i] * 1e12

        # Reconstruct aperiodic in log10 space: L = offset - exponent * log10(f)
        with np.errstate(divide="ignore", invalid="ignore"):
            log10_freqs = np.log10(freqs)
        log10_aperiodic = offset - exponent * log10_freqs

        # Full PSD in log10 space
        with np.errstate(divide="ignore", invalid="ignore"):
            log10_psd = np.log10(psd_uv)

        # Periodic = full - aperiodic in log10 space
        periodic_log10 = log10_psd - log10_aperiodic

        # Convert back to linear V²/Hz
        periodic_linear = np.power(10.0, periodic_log10) * 1e-12

        # Floor at zero (shouldn't be needed with log-space subtraction, but safety)
        periodic_linear = np.maximum(periodic_linear, 0.0)
        periodic_psds[i] = periodic_linear

    # Compute band power on periodic-only PSD.
    # For channels with NaN periodic PSD, results will be NaN.
    total_periodic = np.nansum(
        periodic_psds[:, (freqs >= freqs[0]) & (freqs <= freqs[-1])],
        axis=1,
    ) * (freqs[1] - freqs[0]) if len(freqs) > 1 else np.zeros(n_channels)

    corrected = {}
    for band_name, (fmin, fmax) in bands.items():
        idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
        if len(idx) == 0:
            corrected[band_name] = {
                "corrected_absolute": np.full(n_channels, np.nan),
                "corrected_relative": np.full(n_channels, np.nan),
            }
            continue

        abs_power = np.trapezoid(periodic_psds[:, idx], freqs[idx], axis=1)
        total_power = np.trapezoid(periodic_psds, freqs, axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_power = np.where(total_power > 0, abs_power / total_power, np.nan)

        corrected[band_name] = {
            "corrected_absolute": abs_power,
            "corrected_relative": rel_power,
        }

    return corrected


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


def compute_gsf(
    psds: np.ndarray, freqs: np.ndarray
) -> tuple[float, np.ndarray]:
    """Compute Global Scale Factor and GSF-corrected PSD.

    GSF captures non-neurophysiological variance (skull thickness, hair,
    amplifier gain) that scales the entire spectrum uniformly. Accounts
    for ~42% of variance in age-corrected EEG data. Critical for
    multi-dataset normative builds across different amplifier systems.

    Args:
        psds: Shape (n_channels, n_freqs), in V^2/Hz.
        freqs: Frequency array.

    Returns:
        (gsf, corrected_psds) where gsf is the scalar log10-mean and
        corrected_psds is the GSF-corrected PSD, same shape as psds.
    """
    psds_positive = np.maximum(psds, 1e-30)
    log10_psds = np.log10(psds_positive)
    gsf = float(np.mean(log10_psds))
    corrected_log10 = log10_psds - gsf
    corrected_psds = np.power(10.0, corrected_log10)
    return gsf, corrected_psds


def compute_gsf_band_power(
    gsf_psds: np.ndarray, freqs: np.ndarray, bands: dict
) -> dict:
    """Compute band power from GSF-corrected PSD.

    Args:
        gsf_psds: GSF-corrected PSD, shape (n_channels, n_freqs).
        freqs: Frequency array.
        bands: Dict of {band_name: [fmin, fmax]}.

    Returns:
        Dict of {band_name: {"gsf_absolute": array, "gsf_relative": array}}.
    """
    total_power = np.trapezoid(gsf_psds, freqs, axis=1)
    band_power = {}
    for band_name, (fmin, fmax) in bands.items():
        idx = np.where((freqs >= fmin) & (freqs <= fmax))[0]
        if len(idx) == 0:
            band_power[band_name] = {
                "gsf_absolute": np.zeros(gsf_psds.shape[0]),
                "gsf_relative": np.zeros(gsf_psds.shape[0]),
            }
            continue
        abs_power = np.trapezoid(gsf_psds[:, idx], freqs[idx], axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rel_power = np.where(total_power > 0, abs_power / total_power, 0.0)
        band_power[band_name] = {
            "gsf_absolute": abs_power,
            "gsf_relative": rel_power,
        }
    return band_power


def compute_iaf(
    psds: np.ndarray,
    freqs: np.ndarray,
    ch_names: list[str],
    aperiodic: dict,
    params: dict,
) -> dict:
    """Compute Individual Alpha Frequency per channel and global.

    Uses two methods:
    1. Peak frequency: highest-power specparam peak in the alpha search range.
    2. Center of gravity (CoG): spectral centroid of the alpha region
       (Corcoran et al., 2018).

    Args:
        psds: Shape (n_channels, n_freqs), in V^2/Hz.
        freqs: Frequency array.
        ch_names: Channel names.
        aperiodic: Dict from compute_aperiodic() with peak_params per channel.
        params: IAF params with search_range, posterior_channels.

    Returns:
        Dict with per_channel, global_peak, global_cog, posterior_channels,
        typical_range.
    """
    search_range = params.get("search_range", [7, 14])
    posterior_channels = params.get(
        "posterior_channels", ["O1", "O2", "Pz", "P3", "P4"]
    )
    typical_lo, typical_hi = params.get("typical_range", [9, 11])

    alpha_idx = np.where(
        (freqs >= search_range[0]) & (freqs <= search_range[1])
    )[0]
    alpha_freqs = freqs[alpha_idx]

    per_channel = {}
    for i, ch in enumerate(ch_names):
        # Method 1: Peak from specparam peak_params
        peak_freq = None
        ap = aperiodic.get(ch, {})
        peaks = ap.get("peak_params", [])
        alpha_peaks = [
            p for p in peaks
            if search_range[0] <= p[0] <= search_range[1]
        ]
        if alpha_peaks:
            best_peak = max(alpha_peaks, key=lambda p: p[1])
            peak_freq = float(best_peak[0])

        # Method 2: Center of gravity on the PSD in alpha range
        cog_freq = float("nan")
        if len(alpha_idx) > 0:
            alpha_psd = psds[i, alpha_idx]
            total = np.sum(alpha_psd)
            if total > 0:
                cog_freq = float(np.sum(alpha_freqs * alpha_psd) / total)

        per_channel[ch] = {
            "peak_freq": peak_freq,
            "cog_freq": cog_freq,
        }

    # Global IAF: average over posterior channels
    posterior_peaks = [
        per_channel[ch]["peak_freq"]
        for ch in posterior_channels
        if ch in per_channel and per_channel[ch]["peak_freq"] is not None
    ]
    posterior_cogs = [
        per_channel[ch]["cog_freq"]
        for ch in posterior_channels
        if ch in per_channel and not np.isnan(per_channel[ch]["cog_freq"])
    ]

    global_peak = float(np.mean(posterior_peaks)) if posterior_peaks else None
    global_cog = float(np.mean(posterior_cogs)) if posterior_cogs else float("nan")

    # Flag typical range
    iaf_value = global_peak if global_peak is not None else global_cog
    typical_range = None
    if iaf_value is not None and not np.isnan(iaf_value):
        typical_range = typical_lo <= iaf_value <= typical_hi

    return {
        "per_channel": per_channel,
        "global_peak": global_peak,
        "global_cog": global_cog,
        "posterior_channels": posterior_channels,
        "typical_range": typical_range,
    }


def analyze_spectral(raw, params: dict) -> dict:
    """Run full spectral analysis pipeline.

    Returns:
        Dict with psds, freqs, band_power, corrected_band_power, ratios,
        corrected_ratios, aperiodic, asymmetry.
    """
    psds, freqs = compute_psd(raw, params)
    band_power = compute_band_power(psds, freqs, params["bands"])
    ratio_defs = params.get("ratios", [])
    ratios = compute_band_ratios(band_power, raw.ch_names, ratio_defs)
    aperiodic = compute_aperiodic(psds, freqs, raw.ch_names, params["aperiodic"])
    corrected_band_power = compute_corrected_band_power(
        psds, freqs, aperiodic, raw.ch_names, params["bands"]
    )
    corrected_ratios = compute_band_ratios(
        corrected_band_power,
        raw.ch_names,
        ratio_defs,
        power_key="corrected_absolute",
    )
    asymmetry = compute_asymmetry(
        band_power, raw.ch_names, params["asymmetry"]["homologous_pairs"]
    )

    # GSF correction
    gsf_scalar, gsf_psds = compute_gsf(psds, freqs)
    gsf_band_power = compute_gsf_band_power(gsf_psds, freqs, params["bands"])

    # Individual Alpha Frequency
    iaf = compute_iaf(
        psds, freqs, list(raw.ch_names), aperiodic,
        params.get("iaf", {}),
    )

    return {
        "psds": psds,
        "freqs": freqs,
        "band_power": band_power,
        "corrected_band_power": corrected_band_power,
        "ratios": ratios,
        "corrected_ratios": corrected_ratios,
        "aperiodic": aperiodic,
        "asymmetry": asymmetry,
        "gsf": gsf_scalar,
        "gsf_band_power": gsf_band_power,
        "iaf": iaf,
    }
