"""Connectivity analysis: dwPLI, coherence, graph metrics, PAC.

Computes hub-level and electrode-level functional connectivity using
spectral methods (dwPLI, coherence, imaginary coherence), summarises
network topology with NetworkX graph metrics, and optionally estimates
theta-gamma phase-amplitude coupling via the Modulation Index.
"""

from __future__ import annotations

import logging
import warnings
from typing import Optional

import mne
import mne.io
import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

logger = logging.getLogger(__name__)

# Map public method names to mne-connectivity method strings.
_METHOD_MAP = {
    "dwpli": "wpli2_debiased",
    "coh": "coh",
    "imcoh": "imcoh",
}


# ---------------------------------------------------------------------------
# Epoching
# ---------------------------------------------------------------------------

def epoch_continuous(
    raw: mne.io.BaseRaw,
    epoch_length: float = 2.0,
    overlap: float = 0.0,
    min_epochs: int = 30,
    max_epochs: int = 120,
) -> Optional[mne.Epochs]:
    """Create fixed-length non-overlapping (or overlapping) epochs from raw.

    Args:
        raw: MNE Raw object.
        epoch_length: Epoch duration in seconds.
        overlap: Fractional overlap [0, 1).
        min_epochs: Minimum required epochs. Returns None if not met.
        max_epochs: Maximum epochs to keep (0 = no cap; selects from middle).

    Returns:
        MNE Epochs or None if recording is too short.
    """
    sfreq = raw.info["sfreq"]
    step = epoch_length * (1.0 - overlap)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        events = mne.make_fixed_length_events(
            raw,
            duration=epoch_length,
            overlap=epoch_length * overlap,
        )

    if len(events) < min_epochs:
        logger.debug(
            "Only %d epochs available, need %d — returning None.",
            len(events),
            min_epochs,
        )
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        epochs = mne.Epochs(
            raw,
            events,
            tmin=0.0,
            tmax=epoch_length - 1.0 / sfreq,
            baseline=None,
            preload=True,
            verbose=False,
        )

    # Cap at max_epochs by selecting from the middle of the recording.
    if max_epochs and len(epochs) > max_epochs:
        n = len(epochs)
        start = (n - max_epochs) // 2
        epochs = epochs[start : start + max_epochs]

    return epochs


# ---------------------------------------------------------------------------
# Hub averaging
# ---------------------------------------------------------------------------

def average_hub_signals(
    epochs: mne.Epochs,
    hubs: dict,
) -> tuple[mne.EpochsArray, list[str], dict]:
    """Average channels within each hub to create hub-level epochs.

    Args:
        epochs: MNE Epochs with electrode-level data.
        hubs: Dict of {hub_name: [channel_names]}.

    Returns:
        (hub_epochs, hub_names, hub_mapping) where hub_mapping maps
        hub_name → list of channels actually used (intersection with data).
    """
    ch_names_in = epochs.ch_names
    data = epochs.get_data()  # (n_epochs, n_channels, n_times)

    hub_names = list(hubs.keys())
    hub_mapping: dict[str, list[str]] = {}
    hub_data = []

    for hub_name in hub_names:
        wanted = hubs[hub_name]
        available = [c for c in wanted if c in ch_names_in]
        hub_mapping[hub_name] = available

        if not available:
            # Fallback: zero signal rather than dropping the hub.
            logger.warning("Hub %s has no matching channels — using zeros.", hub_name)
            hub_data.append(np.zeros((data.shape[0], 1, data.shape[2])))
        else:
            indices = [ch_names_in.index(c) for c in available]
            hub_data.append(data[:, indices, :].mean(axis=1, keepdims=True))

    hub_array = np.concatenate(hub_data, axis=1)  # (n_epochs, n_hubs, n_times)

    info = mne.create_info(
        ch_names=hub_names,
        sfreq=epochs.info["sfreq"],
        ch_types="eeg",
    )
    hub_epochs = mne.EpochsArray(hub_array, info, verbose=False)
    return hub_epochs, hub_names, hub_mapping


# ---------------------------------------------------------------------------
# Spectral connectivity
# ---------------------------------------------------------------------------

def compute_connectivity(
    hub_epochs: mne.EpochsArray,
    hub_names: list[str],
    params: dict,
) -> tuple[dict, list]:
    """Compute spectral connectivity per band for each requested method.

    Args:
        hub_epochs: Hub-averaged epochs (n_epochs, n_hubs, n_times).
        hub_names: Ordered list of hub labels.
        params: Connectivity params dict from PIPELINE_PARAMS.

    Returns:
        (results, vc_flags) where results is
        {method: {band_name: (n_hubs, n_hubs) matrix}} and vc_flags is a
        list of (band, hub_i, hub_j) tuples where volume conduction is
        suspected.
    """
    from mne_connectivity import spectral_connectivity_epochs

    sfreq = hub_epochs.info["sfreq"]
    epoch_length = hub_epochs.times[-1] - hub_epochs.times[0]
    min_freq = 5.0 / epoch_length  # reliable lower bound

    bands = params["bands"]
    methods = params["methods"]
    n_hubs = len(hub_names)

    # Collect all frequency limits needed.
    valid_bands = {
        name: freqs
        for name, freqs in bands.items()
        if freqs[0] >= min_freq
    }

    results: dict[str, dict] = {m: {} for m in methods}

    for method in methods:
        mne_method = _METHOD_MAP[method]

        for band_name, (fmin, fmax) in valid_bands.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                con = spectral_connectivity_epochs(
                    hub_epochs,
                    method=mne_method,
                    mode="multitaper",
                    sfreq=sfreq,
                    fmin=fmin,
                    fmax=fmax,
                    faverage=True,
                    verbose=False,
                )

            # con.get_data() shape: (n_pairs, 1) with faverage=True
            con_data = np.abs(con.get_data()).squeeze()  # (n_pairs,)

            # Reconstruct square matrix from lower-triangular indices.
            matrix = np.zeros((n_hubs, n_hubs))
            idx = 0
            for i in range(n_hubs):
                for j in range(i + 1, n_hubs):
                    val = float(con_data[idx]) if con_data.ndim > 0 else float(con_data)
                    idx += 1
                    matrix[i, j] = val
                    matrix[j, i] = val  # symmetrise

            np.fill_diagonal(matrix, 0.0)
            results[method][band_name] = matrix

    # Detect possible volume conduction: high coh + low dwpli.
    vc_flags = []
    if "coh" in results and "dwpli" in results:
        for band_name in valid_bands:
            coh_mat = results["coh"].get(band_name)
            dwpli_mat = results["dwpli"].get(band_name)
            if coh_mat is None or dwpli_mat is None:
                continue
            for i in range(n_hubs):
                for j in range(i + 1, n_hubs):
                    if coh_mat[i, j] > 0.6 and dwpli_mat[i, j] < 0.1:
                        vc_flags.append((band_name, hub_names[i], hub_names[j]))

    return results, vc_flags


# ---------------------------------------------------------------------------
# Electrode-level connectivity
# ---------------------------------------------------------------------------

def compute_electrode_connectivity(
    epochs: mne.Epochs,
    params: dict,
) -> tuple[dict, dict, list[str]]:
    """All-to-all electrode-level dwPLI and coherence.

    Args:
        epochs: Electrode-level epochs.
        params: Connectivity params.

    Returns:
        (node_strength, matrices, ch_names) where node_strength maps
        {method: {band: array(n_ch)}} and matrices maps
        {method: {band: (n_ch, n_ch) array}}.
    """
    from mne_connectivity import spectral_connectivity_epochs

    sfreq = epochs.info["sfreq"]
    epoch_length = epochs.times[-1] - epochs.times[0]
    min_freq = 5.0 / epoch_length
    ch_names = epochs.ch_names
    n_ch = len(ch_names)

    bands = params["bands"]
    valid_bands = {
        name: freqs
        for name, freqs in bands.items()
        if freqs[0] >= min_freq
    }

    matrices: dict[str, dict] = {"dwpli": {}, "coh": {}}
    node_strength: dict[str, dict] = {"dwpli": {}, "coh": {}}

    for method_key, mne_method in [("dwpli", "wpli2_debiased"), ("coh", "coh")]:
        for band_name, (fmin, fmax) in valid_bands.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                con = spectral_connectivity_epochs(
                    epochs,
                    method=mne_method,
                    mode="multitaper",
                    sfreq=sfreq,
                    fmin=fmin,
                    fmax=fmax,
                    faverage=True,
                    verbose=False,
                )

            con_data = np.abs(con.get_data()).squeeze()

            matrix = np.zeros((n_ch, n_ch))
            idx = 0
            for i in range(n_ch):
                for j in range(i + 1, n_ch):
                    val = float(con_data[idx]) if con_data.ndim > 0 else float(con_data)
                    idx += 1
                    matrix[i, j] = val
                    matrix[j, i] = val

            np.fill_diagonal(matrix, 0.0)
            matrices[method_key][band_name] = matrix
            node_strength[method_key][band_name] = matrix.sum(axis=1)

    return node_strength, matrices, ch_names


# ---------------------------------------------------------------------------
# Graph metrics
# ---------------------------------------------------------------------------

def compute_graph_metrics(
    dwpli_matrices: dict,
    hub_names: list[str],
    params: dict,
) -> dict:
    """Compute NetworkX graph metrics from dwPLI connectivity matrices.

    Args:
        dwpli_matrices: {band_name: (n_hubs, n_hubs) array}.
        hub_names: Ordered list of hub labels.
        params: Connectivity params; uses params["graph"]["threshold_percentile"].

    Returns:
        {band_name: {"strength", "betweenness", "clustering",
                     "global_efficiency", "char_path_length"}} — each value
        is a dict keyed by hub_name (except scalar graph-level metrics).
    """
    import networkx as nx

    threshold_pct = params.get("graph", {}).get("threshold_percentile", 75)
    graph_metrics: dict[str, dict] = {}

    for band_name, matrix in dwpli_matrices.items():
        # Threshold: keep top (100 - pct) % of edges.
        thr = np.percentile(matrix[matrix > 0], threshold_pct) if np.any(matrix > 0) else 0.0
        adj = matrix.copy()
        adj[adj < thr] = 0.0

        G = nx.from_numpy_array(adj)
        mapping = {i: hub_names[i] for i in range(len(hub_names))}
        G = nx.relabel_nodes(G, mapping)

        strength = {n: float(d) for n, d in G.degree(weight="weight")}
        betweenness = nx.betweenness_centrality(G, weight="weight")
        clustering = nx.clustering(G, weight="weight")

        try:
            global_efficiency = nx.global_efficiency(G)
        except Exception:
            global_efficiency = float("nan")

        try:
            # char path on largest connected component only
            if nx.is_connected(G):
                char_path = nx.average_shortest_path_length(G, weight="weight")
            else:
                largest_cc = max(nx.connected_components(G), key=len)
                subG = G.subgraph(largest_cc)
                char_path = nx.average_shortest_path_length(subG, weight="weight")
        except Exception:
            char_path = float("nan")

        graph_metrics[band_name] = {
            "strength": strength,
            "betweenness": betweenness,
            "clustering": clustering,
            "global_efficiency": global_efficiency,
            "char_path_length": char_path,
        }

    return graph_metrics


# ---------------------------------------------------------------------------
# PAC helpers
# ---------------------------------------------------------------------------

def _bandpass(
    data: np.ndarray,
    fmin: float,
    fmax: float,
    sfreq: float,
    order: int = 4,
) -> np.ndarray:
    """Zero-phase Butterworth bandpass filter.

    Args:
        data: Shape (..., n_times).
        fmin: Low cutoff (Hz).
        fmax: High cutoff (Hz).
        sfreq: Sampling frequency (Hz).
        order: Filter order.

    Returns:
        Filtered array, same shape as data.
    """
    nyq = sfreq / 2.0
    low = fmin / nyq
    high = fmax / nyq
    sos = butter(order, [low, high], btype="band", output="sos")
    return sosfiltfilt(sos, data, axis=-1)


def _modulation_index(
    theta_phase: np.ndarray,
    gamma_amp: np.ndarray,
    n_bins: int = 18,
) -> float:
    """Tort et al. (2010) Modulation Index.

    Args:
        theta_phase: Instantaneous phase, radians, shape (n_samples,).
        gamma_amp: Instantaneous amplitude envelope, shape (n_samples,).
        n_bins: Number of phase bins.

    Returns:
        MI value normalised to [0, 1].
    """
    bin_edges = np.linspace(-np.pi, np.pi, n_bins + 1)
    amp_by_phase = np.zeros(n_bins)
    for b in range(n_bins):
        mask = (theta_phase >= bin_edges[b]) & (theta_phase < bin_edges[b + 1])
        if mask.sum() > 0:
            amp_by_phase[b] = gamma_amp[mask].mean()

    total = amp_by_phase.sum()
    if total == 0:
        return 0.0

    p = amp_by_phase / total
    p = np.where(p > 0, p, 1e-12)  # avoid log(0)
    h = -np.sum(p * np.log(p))
    h_max = np.log(n_bins)
    mi = (h_max - h) / h_max
    return float(mi)


# ---------------------------------------------------------------------------
# PAC computation
# ---------------------------------------------------------------------------

def compute_pac(
    hub_epochs: mne.EpochsArray,
    hub_names: list[str],
    params: dict,
) -> Optional[dict]:
    """Compute theta-gamma phase-amplitude coupling across hub epochs.

    Args:
        hub_epochs: Hub-averaged epochs.
        hub_names: Hub labels.
        params: Connectivity params; reads params["cfc"].

    Returns:
        Dict with "theta_gamma_pac" containing "within_hub" and "between_hub"
        sub-dicts, or None if CFC is disabled.
    """
    cfc_params = params.get("cfc", {})
    if not cfc_params.get("enabled", True):
        return None

    sfreq = hub_epochs.info["sfreq"]
    phase_band = cfc_params.get("phase_band", [4, 8])
    amp_band = cfc_params.get("amp_band", [30, 45])
    n_bins = cfc_params.get("n_bins", 18)
    hub_pairs = cfc_params.get("hub_pairs", [])

    data = hub_epochs.get_data()  # (n_epochs, n_hubs, n_times)

    # Concatenate epochs along time axis for better phase estimates.
    # Shape: (n_hubs, n_epochs * n_times)
    n_epochs, n_hubs, n_times = data.shape
    continuous = data.transpose(1, 0, 2).reshape(n_hubs, -1)

    # Compute filtered signals and extract phase / amplitude.
    theta_filt = _bandpass(continuous, phase_band[0], phase_band[1], sfreq)
    gamma_filt = _bandpass(continuous, amp_band[0], amp_band[1], sfreq)

    theta_phase = np.angle(hilbert(theta_filt, axis=-1))  # (n_hubs, n_samples)
    gamma_amp = np.abs(hilbert(gamma_filt, axis=-1))       # (n_hubs, n_samples)

    # Within-hub PAC.
    within_hub: dict[str, float] = {}
    for h_idx, hub in enumerate(hub_names):
        mi = _modulation_index(theta_phase[h_idx], gamma_amp[h_idx], n_bins)
        within_hub[hub] = mi

    # Between-hub PAC for specified pairs.
    between_hub: dict[str, float] = {}
    for pair in hub_pairs:
        if pair[0] not in hub_names or pair[1] not in hub_names:
            continue
        i = hub_names.index(pair[0])
        j = hub_names.index(pair[1])
        key = f"{pair[0]}__{pair[1]}"
        # Phase from hub i, amplitude from hub j.
        mi = _modulation_index(theta_phase[i], gamma_amp[j], n_bins)
        between_hub[key] = mi

    return {
        "theta_gamma_pac": {
            "within_hub": within_hub,
            "between_hub": between_hub,
        }
    }


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def analyze_connectivity(
    raw: mne.io.BaseRaw,
    params: dict,
) -> dict:
    """Run the full connectivity analysis pipeline.

    Steps:
        1. Epoch the continuous recording.
        2. Average channels within each hub.
        3. Compute hub-level connectivity (dwPLI, coh, imcoh) per band.
        4. Compute electrode-level connectivity.
        5. Compute graph metrics from hub-level dwPLI.
        6. Compute theta-gamma PAC.

    Args:
        raw: Preprocessed MNE Raw object.
        params: Connectivity params from PIPELINE_PARAMS["connectivity"].

    Returns:
        Dict with keys:
            "hub_connectivity": {method: {band: (n_hubs, n_hubs) matrix}},
            "vc_flags": list of suspected volume-conduction triples,
            "graph_metrics": {band: {metric: values}},
            "hub_names": list of hub labels,
            "hub_mapping": {hub: [channels]},
            "electrode_connectivity": {
                "node_strength": {method: {band: array}},
                "matrices": {method: {band: matrix}},
                "ch_names": list,
            },
            "pac": PAC dict or None,
    """
    epochs = epoch_continuous(
        raw,
        epoch_length=params["epoch_length"],
        overlap=params.get("epoch_overlap", 0.0),
        min_epochs=params["min_epochs"],
        max_epochs=params["max_epochs"],
    )

    if epochs is None:
        logger.warning("Insufficient epochs for connectivity analysis.")
        return {
            "hub_connectivity": {},
            "vc_flags": [],
            "graph_metrics": {},
            "hub_names": [],
            "hub_mapping": {},
            "electrode_connectivity": {},
            "pac": None,
        }

    hub_epochs, hub_names, hub_mapping = average_hub_signals(
        epochs, params["hubs"]
    )

    hub_connectivity, vc_flags = compute_connectivity(
        hub_epochs, hub_names, params
    )

    graph_metrics = compute_graph_metrics(
        hub_connectivity.get("dwpli", {}), hub_names, params
    )

    node_strength, elec_matrices, ch_names = compute_electrode_connectivity(
        epochs, params
    )

    pac = compute_pac(hub_epochs, hub_names, params)

    return {
        "hub_connectivity": hub_connectivity,
        "vc_flags": vc_flags,
        "graph_metrics": graph_metrics,
        "hub_names": hub_names,
        "hub_mapping": hub_mapping,
        "electrode_connectivity": {
            "node_strength": node_strength,
            "matrices": elec_matrices,
            "ch_names": ch_names,
        },
        "pac": pac,
    }
