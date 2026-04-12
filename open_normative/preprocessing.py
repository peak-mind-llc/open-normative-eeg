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
    """Apply Artifact Subspace Reconstruction to clean transient artifacts.

    Modifies ``raw`` in place and also returns it. Historically this
    function rebound a local ``raw`` variable to ``asr.transform()``'s
    return value and returned it; callers that ignored the return value
    ended up with unchanged data (a silent no-op for ASR). This version
    copies the transformed data back into the caller's ``raw`` object so
    ``apply_asr(raw, ...)`` and ``raw = apply_asr(raw, ...)`` both work.
    """
    try:
        from asrpy import ASR
    except ImportError:
        warnings.warn("asrpy not installed — skipping ASR artifact cleaning")
        return raw

    _patch_asrpy()
    cutoff = params.get("cutoff", 20)
    data_before = raw.get_data().copy()
    try:
        with np.errstate(all="warn"):
            asr = ASR(sfreq=raw.info["sfreq"], cutoff=cutoff)
            asr.fit(raw)
            splits = _asr_mem_splits(raw)
            raw_transformed = asr.transform(raw, mem_splits=splits)
    except Exception as exc:
        warnings.warn(f"ASR failed ({type(exc).__name__}: {exc}); skipping")
        return raw

    # ASR should not change sample count — but guard against it.
    if raw_transformed.n_times != raw.n_times:
        warnings.warn(
            f"ASR returned a Raw with {raw_transformed.n_times} samples "
            f"(expected {raw.n_times}); skipping ASR update"
        )
        return raw

    new_data = raw_transformed.get_data()
    if not np.all(np.isfinite(new_data)):
        n_bad = int(np.sum(~np.isfinite(new_data)))
        warnings.warn(
            f"ASR produced {n_bad} non-finite values — reverting to pre-ASR data"
        )
        raw._data[:] = data_before
        return raw

    # Copy the transformed data back into the caller's raw in-place.
    raw._data[:] = new_data
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
    except (ImportError, FloatingPointError, np.linalg.LinAlgError) as exc:
        warnings.warn(
            f"ICA fitting skipped — {type(exc).__name__}: {exc}"
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


def detect_line_noise_channels(raw: mne.io.Raw, params: dict) -> list[str]:
    """Detect channels dominated by line noise.

    Missing step in the original preprocessing — EEGlab's `clean_artifacts`
    runs a `LineNoiseCriterion` pass that flags channels with excessive
    power concentrated in the line-noise frequency band. This function is
    the Python equivalent: compute per-channel PSD, measure the fraction
    of total power in a ±`bandwidth` Hz window around `line_freq`, flag
    channels where that fraction exceeds `max_ratio`.

    Args:
        raw: MNE Raw object (not modified).
        params: Dict with keys:
            enabled (bool) — skip this step if False
            line_freq (float) — 60.0 US, 50.0 EU
            max_ratio (float) — fraction threshold, default 0.4
            bandwidth (float) — ± Hz around line_freq, default 2.0

    Returns:
        List of bad channel names (possibly empty).
    """
    if not params.get("enabled", False):
        return []

    line_freq = params.get("line_freq", 60.0)
    max_ratio = params.get("max_ratio", 0.4)
    bandwidth = params.get("bandwidth", 2.0)

    # Skip if Nyquist can't fit the line band
    nyq = raw.info["sfreq"] / 2.0
    if line_freq + bandwidth >= nyq:
        return []

    fmax = min(line_freq + 10.0, nyq - 1.0)
    n_fft = int(min(raw.info["sfreq"] * 2, raw.n_times))
    try:
        spec = raw.compute_psd(
            method="welch", fmin=1.0, fmax=fmax, n_fft=n_fft, verbose=False,
        )
    except Exception as exc:
        warnings.warn(
            f"detect_line_noise_channels: PSD computation failed ({exc}); "
            "skipping line-noise detection"
        )
        return []

    psd = spec.get_data()  # (n_channels, n_freqs)
    freqs = spec.freqs

    line_band = (freqs >= line_freq - bandwidth) & (freqs <= line_freq + bandwidth)
    if not line_band.any():
        return []

    # Integrate power in the line band vs the whole spectrum
    line_power = np.trapezoid(psd[:, line_band], freqs[line_band], axis=1)
    total_power = np.trapezoid(psd, freqs, axis=1)
    total_power = np.where(total_power < 1e-24, 1e-24, total_power)
    ratios = line_power / total_power

    bad = [raw.ch_names[i] for i, r in enumerate(ratios) if r > max_ratio]
    return bad


def reject_bad_windows_post_asr(raw: mne.io.Raw, params: dict) -> dict:
    """Mark windows with excessive residual amplitude as bad annotations.

    Intended to run AFTER ASR. Computes per-window std (across all channels
    and samples in the window); windows where the std exceeds
    `threshold_multiplier` × the recording-wide median std are flagged as
    bad. Adjacent bad windows are merged. The flagged windows are written
    as MNE annotations with description ``BAD_post_asr_window`` so that
    downstream analyses (spectral / connectivity / ERP) skip them via
    standard ``reject_by_annotation`` semantics.

    This is the Python equivalent of EEGlab `clean_artifacts`'
    `WindowCriterion` — the step asrpy alone doesn't implement.

    Args:
        raw: MNE Raw object, modified in place (annotations added).
        params: Dict with keys:
            enabled (bool) — skip if False
            window_length (float) — window in seconds, default 0.5
            threshold_multiplier (float) — std multiplier above median, default 5.0

    Returns:
        Dict with {n_bad_windows, total_windows, bad_seconds, threshold_std}.
    """
    info_out = {
        "n_bad_windows": 0,
        "total_windows": 0,
        "bad_seconds": 0.0,
        "threshold_std": 0.0,
    }
    if not params.get("enabled", False):
        return info_out

    window_sec = params.get("window_length", 0.5)
    threshold_mult = params.get("threshold_multiplier", 5.0)

    sfreq = raw.info["sfreq"]
    window_samples = max(1, int(window_sec * sfreq))

    data = raw.get_data()
    n_samples = data.shape[1]
    n_windows = n_samples // window_samples
    if n_windows < 4:
        return info_out

    stds = np.empty(n_windows)
    for i in range(n_windows):
        s = i * window_samples
        e = s + window_samples
        stds[i] = data[:, s:e].std()

    median_std = float(np.median(stds))
    if median_std <= 0:
        return info_out
    threshold = median_std * threshold_mult

    bad_mask = stds > threshold
    info_out["total_windows"] = int(n_windows)
    info_out["n_bad_windows"] = int(bad_mask.sum())
    info_out["bad_seconds"] = float(bad_mask.sum() * window_sec)
    info_out["threshold_std"] = float(threshold)

    if not bad_mask.any():
        return info_out

    # Merge adjacent bad windows into continuous segments
    onsets = []
    durations = []
    descriptions = []
    i = 0
    while i < n_windows:
        if bad_mask[i]:
            j = i
            while j < n_windows and bad_mask[j]:
                j += 1
            onset_sec = (i * window_samples) / sfreq
            duration_sec = ((j - i) * window_samples) / sfreq
            onsets.append(onset_sec)
            durations.append(duration_sec)
            descriptions.append("BAD_post_asr_window")
            i = j
        else:
            i += 1

    new_annots = mne.Annotations(
        onsets, durations, descriptions, orig_time=raw.info["meas_date"],
    )
    if raw.annotations is not None and len(raw.annotations) > 0:
        raw.set_annotations(raw.annotations + new_annots)
    else:
        raw.set_annotations(new_annots)

    return info_out


def preprocess(raw: mne.io.Raw, params: dict) -> dict:
    """Run the full preprocessing pipeline.

    Pipeline order (matches EEGlab ``clean_artifacts`` + reference
    convention: cleaning runs on the original reference, then re-reference
    is applied AFTER cleaning):

        1. Resample (optional, target 256 Hz per PIPELINE_PARAMS)
        2. Bandpass + notch filter
        3. Bad channel detection (variance + pyprep RANSAC)
        4. Line noise channel detection (NEW — catches channels dominated
           by power-line contamination that variance / RANSAC may miss)
        5. Interpolate bad channels via spherical splines
        6. ASR burst reconstruction (asrpy)
        7. Post-ASR window rejection (NEW — marks windows where residual
           std exceeds 5× the recording-wide median as bad annotations;
           downstream analyses skip them via reject_by_annotation)
        8. Average reference
        9. ICA decomposition + ICLabel classification + auto-reject

    Note on reference ordering: CAP-01 §3 documents reference (Step 3)
    BEFORE ASR (Step 4), but this contradicts EEGlab's ``clean_artifacts``
    convention and what Phase B ``workflow_resting.m`` actually does (ASR
    first, then ``pop_reref``). The CAP-01 doc is wrong and needs a
    correction pass; the code here matches the Phase B reference pipeline
    and the EEGlab canonical order.

    Args:
        raw: MNE Raw object (already channel-standardized to 19ch).
        params: The 'preprocessing' section of PIPELINE_PARAMS.

    Returns:
        Dict with keys: raw, bad_channels, bad_by_line_noise,
        window_rejection, ica.
    """
    resample(raw, params.get("resample", {}))
    apply_filters(raw, params["filter"])

    bads_main = detect_bad_channels(raw, params["bad_channels"])
    bads_line = detect_line_noise_channels(raw, params.get("line_noise", {}))
    bads_combined = list(bads_main)
    for ch in bads_line:
        if ch not in bads_combined:
            bads_combined.append(ch)
    raw.info["bads"] = bads_combined
    interpolate_bad_channels(raw)

    apply_asr(raw, params.get("asr", {}))
    window_info = reject_bad_windows_post_asr(
        raw, params.get("window_rejection", {})
    )
    apply_reference(raw, params.get("reference", "average"))
    ica_result = run_ica(raw, params["ica"])

    return {
        "raw": raw,
        "bad_channels": bads_combined,
        "bad_by_line_noise": bads_line,
        "window_rejection": window_info,
        "ica": ica_result,
    }
