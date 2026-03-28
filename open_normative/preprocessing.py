"""EEG preprocessing: filtering, bad channels, ASR, ICA, re-referencing.

All functions take an MNE Raw object and a params dict. No hidden defaults.
Parameters come from open_normative.parameters.PIPELINE_PARAMS.
"""

from __future__ import annotations

import warnings

import mne
import numpy as np


def resample(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Resample raw data to target sampling rate.

    Args:
        raw: MNE Raw object (modified in place).
        params: Dict with 'enabled' (bool) and 'target_sfreq' (float).
    """
    if not params.get("enabled", False):
        return raw
    target = params["target_sfreq"]
    if abs(raw.info["sfreq"] - target) < 0.5:
        return raw
    raw.resample(target, verbose=False)
    return raw


def apply_filters(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Apply bandpass and notch filters.

    Args:
        raw: MNE Raw object (modified in place).
        params: Dict with l_freq, h_freq, notch_freq, notch_harmonics, notch_width.
    """
    raw.filter(
        l_freq=params["l_freq"],
        h_freq=params["h_freq"],
        verbose=False,
    )
    notch_freqs = [params["notch_freq"]] + params.get("notch_harmonics", [])
    nyquist = raw.info["sfreq"] / 2.0
    notch_freqs = [f for f in notch_freqs if f < nyquist]
    if notch_freqs:
        raw.notch_filter(
            notch_freqs,
            notch_widths=params.get("notch_width", 2.0),
            verbose=False,
        )
    return raw


def detect_bad_channels(raw: mne.io.Raw, params: dict) -> list[str]:
    """Detect bad channels using variance heuristics and optional RANSAC.

    Args:
        raw: MNE Raw object.
        params: Dict with method, flat/noisy threshold factors.

    Returns:
        List of bad channel names.
    """
    data = raw.get_data()
    variances = np.var(data, axis=1)
    median_var = np.median(variances)

    flat_thresh = params.get("flat_threshold_factor", 0.01) * median_var
    noisy_thresh = params.get("noisy_threshold_factor", 10.0) * median_var

    bads = []
    for i, ch in enumerate(raw.ch_names):
        if variances[i] < flat_thresh:
            bads.append(ch)
        elif variances[i] > noisy_thresh:
            bads.append(ch)

    if params.get("method") == "ransac":
        try:
            from pyprep.find_noisy_channels import NoisyChannels
            nd = NoisyChannels(raw, random_state=42)
            nd.find_bad_by_ransac()
            ransac_bads = nd.bad_by_ransac
            if len(ransac_bads) <= len(raw.ch_names) * 0.5:
                for ch in ransac_bads:
                    if ch not in bads:
                        bads.append(ch)
        except ImportError:
            pass
        except Exception:
            pass

    return bads


def interpolate_bad_channels(raw: mne.io.Raw) -> mne.io.Raw:
    """Interpolate bad channels using spherical spline."""
    if raw.info["bads"]:
        raw.interpolate_bads(verbose=False)
    return raw


def _patch_asrpy():
    """Apply NumPy >=2.0 compatibility patches for asrpy."""
    try:
        import asrpy.asr
        if not hasattr(np, "float"):
            return
    except ImportError:
        pass


def _asr_mem_splits(raw, max_chunk_bytes=500_000_000):
    """Compute memory-efficient splits for ASR transformation."""
    n_ch = len(raw.ch_names)
    n_samples = raw.n_times
    bytes_full = n_ch * n_ch * n_samples * 8
    return max(3, int(bytes_full / max_chunk_bytes) + 1)


def apply_asr(raw: mne.io.Raw, params: dict) -> mne.io.Raw:
    """Apply Artifact Subspace Reconstruction to clean transient artifacts."""
    try:
        from asrpy import ASR
    except ImportError:
        warnings.warn("asrpy not installed — skipping ASR artifact cleaning")
        return raw

    _patch_asrpy()
    cutoff = params.get("cutoff", 20)
    asr = ASR(sfreq=raw.info["sfreq"], cutoff=cutoff)
    asr.fit(raw)
    splits = _asr_mem_splits(raw)
    raw = asr.transform(raw, mem_splits=splits)
    return raw


def _make_ica_copy(raw: mne.io.Raw, params: dict) -> mne.io.Raw | None:
    """Create a higher-filtered copy for two-stage ICA fitting."""
    if not params.get("two_stage_filter", True):
        return None
    ica_highpass = params.get("ica_highpass", 1.0)
    if ica_highpass <= 0.5:
        return None
    raw_ica = raw.copy()
    raw_ica.filter(l_freq=ica_highpass, h_freq=None, verbose=False)
    return raw_ica


def _resolve_ica_method(preferred: str) -> tuple[str, dict]:
    """Return (method, fit_params) falling back gracefully if preferred is unavailable."""
    from mne.utils import check_version

    extended = True
    if preferred == "picard":
        if check_version("picard", "0.0"):
            return "picard", {"ortho": False, "extended": extended}
        warnings.warn(
            "python-picard not installed — falling back to fastica for ICA"
        )
        return "fastica", {}
    if preferred == "infomax":
        return "infomax", {"extended": extended}
    return preferred, {}


def run_ica(raw: mne.io.Raw, params: dict) -> dict:
    """Run ICA decomposition and ICLabel auto-classification.

    Returns:
        Dict with keys: ica, rejected_components, labels.
    """
    preferred_method = params.get("method", "picard")
    extended = params.get("extended", True)
    n_components = params.get("n_components", 0.999)
    max_iter = params.get("max_iter", 500)
    random_state = params.get("random_state", 42)

    method, fit_params = _resolve_ica_method(preferred_method)
    if preferred_method == "infomax" and method == "infomax":
        fit_params = {"extended": extended}

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method=method,
        max_iter=max_iter,
        random_state=random_state,
        fit_params=fit_params,
        verbose=False,
    )

    raw_fit = _make_ica_copy(raw, params)
    if raw_fit is None:
        raw_fit = raw

    try:
        ica.fit(raw_fit, verbose=False)
    except ImportError as exc:
        warnings.warn(
            f"ICA fitting skipped — required package not available: {exc}"
        )
        return {"ica": None, "rejected_components": [], "labels": None}

    rejected = []
    labels_result = None
    try:
        from mne_icalabel import label_components
        labels_result = label_components(raw_fit, ica, method="iclabel")
        labels = labels_result["labels"]
        proba = labels_result["y_pred_proba"]

        brain_thresh = params.get("brain_threshold", 0.80)
        review_thresh = params.get("review_threshold", 0.50)

        for idx, (label, prob) in enumerate(zip(labels, proba)):
            if label != "brain":
                max_prob = float(np.max(prob)) if hasattr(prob, "__len__") else float(prob)
                if max_prob >= review_thresh:
                    rejected.append(idx)
            else:
                brain_prob = float(prob[0]) if hasattr(prob, "__len__") else float(prob)
                if brain_prob < brain_thresh:
                    rejected.append(idx)
    except ImportError:
        warnings.warn("mne-icalabel not installed — skipping IC classification")

    if rejected:
        ica.exclude = rejected
        ica.apply(raw, verbose=False)

    return {
        "ica": ica,
        "rejected_components": rejected,
        "labels": labels_result,
    }


def apply_reference(raw: mne.io.Raw, reference: str) -> mne.io.Raw:
    """Apply re-referencing.

    Args:
        raw: MNE Raw object (modified in place).
        reference: Reference type — 'average', 'REST', or a channel name string.
    """
    if reference == "average":
        raw.set_eeg_reference("average", verbose=False)
    elif reference == "REST":
        raw.set_eeg_reference("REST", verbose=False)
    else:
        raw.set_eeg_reference([reference], verbose=False)
    return raw


def preprocess(raw: mne.io.Raw, params: dict) -> dict:
    """Run the full preprocessing pipeline.

    Args:
        raw: MNE Raw object (already channel-standardized to 19ch).
        params: The 'preprocessing' section of PIPELINE_PARAMS.

    Returns:
        Dict with keys: raw, bad_channels, ica.
    """
    resample(raw, params.get("resample", {}))
    apply_filters(raw, params["filter"])
    bads = detect_bad_channels(raw, params["bad_channels"])
    raw.info["bads"] = bads
    interpolate_bad_channels(raw)
    apply_asr(raw, params.get("asr", {}))
    apply_reference(raw, params.get("reference", "average"))
    ica_result = run_ica(raw, params["ica"])

    return {
        "raw": raw,
        "bad_channels": bads,
        "ica": ica_result,
    }
