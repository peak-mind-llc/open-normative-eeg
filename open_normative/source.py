"""Source localization for normative EEG: sLORETA power and DICS connectivity.

Uses pre-computed transformation matrices and forward models to avoid
runtime dependency on FreeSurfer / fsaverage (license-incompatible with
commercial/clinical use).

sLORETA source power:
    TM @ channel_band_power -> 2394-voxel source maps -> aggregate per ROI

DICS source connectivity:
    Pre-computed forward model -> CSD -> DICS beamformer -> 18 DK ROIs ->
    spectral connectivity (dwPLI, coherence)
"""

from __future__ import annotations

import csv as _csv
import gc
import logging
import pickle
import warnings
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import mne
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

SLORETA_N_VOXELS = 2394
SLORETA_N_ORIENTATIONS = 3

_DATA_DIR = Path(__file__).parent / "data"

# ── ROI Definitions (18 Desikan-Killiany regions across 7 networks) ───────

ROI_DEFINITIONS = OrderedDict([
    ("DLPFC_L", {
        "label": "Left DLPFC",
        "labels": ["superiorfrontal-lh", "rostralmiddlefrontal-lh", "caudalmiddlefrontal-lh"],
        "network": "Executive",
    }),
    ("DLPFC_R", {
        "label": "Right DLPFC",
        "labels": ["superiorfrontal-rh", "rostralmiddlefrontal-rh", "caudalmiddlefrontal-rh"],
        "network": "Executive",
    }),
    ("mPFC", {
        "label": "Medial PFC",
        "labels": ["medialorbitofrontal-lh", "medialorbitofrontal-rh",
                    "rostralanteriorcingulate-lh", "rostralanteriorcingulate-rh"],
        "network": "DMN",
    }),
    ("ACC", {
        "label": "Anterior Cingulate",
        "labels": ["caudalanteriorcingulate-lh", "caudalanteriorcingulate-rh"],
        "network": "Salience",
    }),
    ("INS_L", {
        "label": "Left Insula",
        "labels": ["insula-lh"],
        "network": "Salience",
    }),
    ("INS_R", {
        "label": "Right Insula",
        "labels": ["insula-rh"],
        "network": "Salience",
    }),
    ("IFG_L", {
        "label": "Left IFG",
        "labels": ["parsopercularis-lh", "parstriangularis-lh", "parsorbitalis-lh"],
        "network": "Executive",
    }),
    ("IFG_R", {
        "label": "Right IFG",
        "labels": ["parsopercularis-rh", "parstriangularis-rh", "parsorbitalis-rh"],
        "network": "Executive",
    }),
    ("STG_L", {
        "label": "Left STG",
        "labels": ["superiortemporal-lh", "middletemporal-lh"],
        "network": "Language",
    }),
    ("STG_R", {
        "label": "Right STG",
        "labels": ["superiortemporal-rh", "middletemporal-rh"],
        "network": "Language",
    }),
    ("IPL_L", {
        "label": "Left IPL",
        "labels": ["inferiorparietal-lh", "supramarginal-lh"],
        "network": "Frontoparietal",
    }),
    ("IPL_R", {
        "label": "Right IPL",
        "labels": ["inferiorparietal-rh", "supramarginal-rh"],
        "network": "Frontoparietal",
    }),
    ("PCUN", {
        "label": "Precuneus",
        "labels": ["precuneus-lh", "precuneus-rh"],
        "network": "DMN",
    }),
    ("PCC", {
        "label": "Posterior Cingulate",
        "labels": ["posteriorcingulate-lh", "posteriorcingulate-rh",
                    "isthmuscingulate-lh", "isthmuscingulate-rh"],
        "network": "DMN",
    }),
    ("SMC_L", {
        "label": "Left Sensorimotor",
        "labels": ["precentral-lh", "postcentral-lh"],
        "network": "Sensorimotor",
    }),
    ("SMC_R", {
        "label": "Right Sensorimotor",
        "labels": ["precentral-rh", "postcentral-rh"],
        "network": "Sensorimotor",
    }),
    ("OCC_L", {
        "label": "Left Occipital",
        "labels": ["lateraloccipital-lh", "lingual-lh", "cuneus-lh", "pericalcarine-lh"],
        "network": "Visual",
    }),
    ("OCC_R", {
        "label": "Right Occipital",
        "labels": ["lateraloccipital-rh", "lingual-rh", "cuneus-rh", "pericalcarine-rh"],
        "network": "Visual",
    }),
])

ROI_NAMES = list(ROI_DEFINITIONS.keys())

# Method name mapping for mne-connectivity
_METHOD_MAP = {
    "dwpli": "wpli2_debiased",
    "coh": "coh",
    "imcoh": "imcoh",
}

# ── Caches ────────────────────────────────────────────────────────────────

_SLORETA_COORDS_CACHE: Optional[np.ndarray] = None
_SLORETA_BA_CACHE: Optional[list] = None


# ── sLORETA source power ─────────────────────────────────────────────────

def _get_voxel_coords() -> np.ndarray:
    """Return the standard 2394-voxel MNI coordinates, shape (2394, 3)."""
    global _SLORETA_COORDS_CACHE
    if _SLORETA_COORDS_CACHE is not None:
        return _SLORETA_COORDS_CACHE

    csv_path = _DATA_DIR / "LORETA-Talairach-BAs.csv"
    coords = []
    with open(csv_path) as f:
        reader = _csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            coords.append([float(row[0]), float(row[1]), float(row[2])])
    _SLORETA_COORDS_CACHE = np.array(coords, dtype=np.float64)
    return _SLORETA_COORDS_CACHE


def _get_voxel_brodmann() -> list[dict]:
    """Return Brodmann area labels for the 2394 voxels."""
    global _SLORETA_BA_CACHE
    if _SLORETA_BA_CACHE is not None:
        return _SLORETA_BA_CACHE

    csv_path = _DATA_DIR / "LORETA-Talairach-BAs.csv"
    if not csv_path.exists():
        return [{"ba": "", "region": "", "lobe": ""}] * SLORETA_N_VOXELS

    entries = []
    with open(csv_path) as f:
        reader = _csv.reader(f)
        next(reader)
        for row in reader:
            entries.append({
                "ba": row[7] if len(row) > 7 else "",
                "region": row[8] if len(row) > 8 else "",
                "lobe": row[9] if len(row) > 9 else "",
            })
    _SLORETA_BA_CACHE = entries
    return entries


def load_transformation_matrix(n_channels: int = 19) -> np.ndarray:
    """Load the pre-computed sLORETA transformation matrix.

    Parameters
    ----------
    n_channels : int
        19 or 37.

    Returns
    -------
    np.ndarray
        Shape (2394 * 3, n_channels).
    """
    tm_path = _DATA_DIR / f"transformation_matrix_{n_channels}ch.npy"
    if not tm_path.exists():
        raise FileNotFoundError(
            f"Transformation matrix not found: {tm_path}"
        )
    return np.load(tm_path)


def compute_source_power_from_tm(
    tm_matrix: np.ndarray, channel_power: np.ndarray,
) -> np.ndarray:
    """Compute source power from transformation matrix and channel power.

    Parameters
    ----------
    tm_matrix : np.ndarray
        Shape (2394 * 3, n_channels).
    channel_power : np.ndarray
        Shape (n_channels,) — band power per channel.

    Returns
    -------
    np.ndarray
        Shape (2394,) — RSS source power at each voxel.
    """
    source = tm_matrix @ channel_power
    source_3d = source.reshape(SLORETA_N_VOXELS, SLORETA_N_ORIENTATIONS)
    return np.sqrt(np.sum(source_3d**2, axis=1))


def compute_sloreta_source_power(
    band_power_dict: dict,
    ch_names: list[str],
    n_channels: int = 19,
) -> dict:
    """Compute sLORETA source power for all frequency bands.

    Parameters
    ----------
    band_power_dict : dict
        Output from spectral analysis: {band: {"absolute": ndarray(n_ch,), ...}}
    ch_names : list[str]
        Channel names matching the band power arrays.
    n_channels : int
        19 or 37 — must match the TM.

    Returns
    -------
    dict
        {band: {
            "voxel_power": ndarray(2394,),
            "peak_voxel": int,
            "peak_mni": tuple,
            "peak_ba": dict,
            "ba_mean_power": {ba_label: float},
        }}
    """
    tm = load_transformation_matrix(n_channels)
    ba_labels = _get_voxel_brodmann()
    coords = _get_voxel_coords()

    results = {}
    for band_name, band_data in band_power_dict.items():
        abs_power = band_data.get("absolute")
        if abs_power is None or len(abs_power) != n_channels:
            continue

        voxel_power = compute_source_power_from_tm(tm, abs_power)

        # Peak voxel
        peak_idx = int(np.argmax(voxel_power))
        peak_mni = tuple(coords[peak_idx].tolist())
        peak_ba = ba_labels[peak_idx] if peak_idx < len(ba_labels) else {}

        # Aggregate per Brodmann area
        ba_mean = {}
        for i, ba_info in enumerate(ba_labels):
            ba_key = ba_info.get("ba", "")
            if ba_key:
                if ba_key not in ba_mean:
                    ba_mean[ba_key] = []
                ba_mean[ba_key].append(voxel_power[i])
        ba_mean_power = {k: float(np.mean(v)) for k, v in ba_mean.items()}

        results[band_name] = {
            "voxel_power": voxel_power,
            "peak_voxel": peak_idx,
            "peak_mni": peak_mni,
            "peak_ba": peak_ba,
            "ba_mean_power": ba_mean_power,
        }

    return results


# ── DICS source connectivity ─────────────────────────────────────────────

def load_forward_assets(n_channels: int = 37):
    """Load pre-computed forward model assets for DICS beamforming.

    Returns
    -------
    fwd : mne.Forward
    src : mne.SourceSpaces
    grouped_labels : list[mne.Label]
        18 merged ROI labels ordered by ROI_NAMES.
    """
    source_dir = _DATA_DIR / "source"
    fwd_path = source_dir / f"forward_{n_channels}ch.fif"
    src_path = source_dir / f"src_{n_channels}ch.fif"
    labels_path = source_dir / f"roi_labels_{n_channels}ch.pkl"

    missing = [p for p in [fwd_path, src_path, labels_path] if not p.is_file()]
    if missing:
        names = ", ".join(p.name for p in missing)
        raise FileNotFoundError(f"Missing forward assets: {names}")

    fwd = mne.read_forward_solution(str(fwd_path), verbose=False)
    src = mne.read_source_spaces(str(src_path), verbose=False)
    with open(labels_path, "rb") as f:
        grouped_labels = pickle.load(f)  # noqa: S301

    return fwd, src, grouped_labels


def compute_dics_source_connectivity(
    raw: mne.io.Raw,
    bands: dict,
    n_channels: int = 37,
    methods: list[str] | None = None,
    epoch_length: float = 2.0,
    reg: float = 0.05,
) -> dict:
    """Compute source-space connectivity using DICS beamforming.

    Parameters
    ----------
    raw : mne.io.Raw
        Preprocessed continuous EEG data.
    bands : dict
        {band_name: [fmin, fmax]} for connectivity estimation.
    n_channels : int
        19 or 37.
    methods : list[str]
        Connectivity methods (default: ["dwpli", "coh"]).
    epoch_length : float
        Epoch length in seconds.
    reg : float
        Regularization parameter for DICS.

    Returns
    -------
    dict with keys:
        "roi_connectivity": {method: {band: ndarray(18, 18)}}
        "network_connectivity": {method: {band: {"within": dict, "between": dict}}}
        "volume_conduction_flags": list[dict]
    """
    from mne.beamformer import apply_dics_epochs, make_dics
    from mne.time_frequency import csd_multitaper
    from mne_connectivity import spectral_connectivity_epochs

    if methods is None:
        methods = ["dwpli", "coh"]
    mne_methods = [_METHOD_MAP.get(m, m) for m in methods]

    # Load forward model
    fwd, src, grouped_labels = load_forward_assets(n_channels)

    # Epoch the data
    events = mne.make_fixed_length_events(raw, duration=epoch_length)
    epochs = mne.Epochs(
        raw, events, tmin=0, tmax=epoch_length - 1.0 / raw.info["sfreq"],
        baseline=None, preload=True, verbose=False,
    )

    if not any(p["desc"] == "eeg_ref_proj" for p in epochs.info.get("projs", [])):
        epochs.set_eeg_reference(projection=True, verbose=False)

    # DICS beamforming + parcellation per band
    roi_ts = {}
    for band_name, (fmin, fmax) in bands.items():
        logger.info(f"  DICS: {band_name} [{fmin}-{fmax} Hz]")

        csd = csd_multitaper(epochs, fmin=fmin, fmax=fmax,
                             adaptive=True, verbose=False)
        csd_mean = csd.mean()
        filters = make_dics(
            epochs.info, fwd, csd_mean,
            reg=reg, real_filter=True, pick_ori="max-power",
            verbose=False,
        )
        band_stcs = list(apply_dics_epochs(epochs, filters, verbose=False))

        tc_list = mne.extract_label_time_course(
            band_stcs, grouped_labels, src,
            mode="mean_flip", verbose=False,
        )
        roi_ts[band_name] = np.array(tc_list)

        del band_stcs, csd, csd_mean, filters, tc_list
        gc.collect()

    # Compute ROI-to-ROI connectivity
    results = {m: {} for m in methods}
    sfreq = raw.info["sfreq"]

    for band_name, data in roi_ts.items():
        fmin, fmax = bands[band_name]

        info = mne.create_info(
            ch_names=list(ROI_NAMES), sfreq=sfreq, ch_types="misc",
        )
        epochs_array = mne.EpochsArray(data, info, verbose=False)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*no Annotations.*")
            con = spectral_connectivity_epochs(
                epochs_array, method=mne_methods,
                fmin=[fmin], fmax=[fmax], faverage=True,
                n_jobs=1, verbose=False,
            )

        if not isinstance(con, list):
            con = [con]

        for i, method in enumerate(methods):
            con_data = con[i].get_data(output="dense")
            matrix = con_data[:, :, 0]
            matrix = (matrix + matrix.T) / 2
            np.fill_diagonal(matrix, 0)
            matrix = np.clip(matrix, 0, 1)
            results[method][band_name] = matrix

    # Volume conduction detection
    vc_flags = []
    if "coh" in results and "dwpli" in results:
        for band_name in results["dwpli"]:
            if band_name not in results["coh"]:
                continue
            coh_mat = results["coh"][band_name]
            dwpli_mat = results["dwpli"][band_name]
            n_rois = len(ROI_NAMES)
            for i in range(n_rois):
                for j in range(i + 1, n_rois):
                    if coh_mat[i, j] > 0.5 and dwpli_mat[i, j] < 0.1:
                        vc_flags.append({
                            "band": band_name,
                            "roi_a": ROI_NAMES[i],
                            "roi_b": ROI_NAMES[j],
                            "coherence": float(coh_mat[i, j]),
                            "dwpli": float(dwpli_mat[i, j]),
                        })

    # Network-level aggregation
    network_conn = _aggregate_network_connectivity(results)

    return {
        "roi_connectivity": results,
        "network_connectivity": network_conn,
        "volume_conduction_flags": vc_flags,
    }


def _aggregate_network_connectivity(results: dict) -> dict:
    """Compute within- and between-network mean connectivity."""
    # Build ROI → network mapping
    roi_networks = {name: defn["network"] for name, defn in ROI_DEFINITIONS.items()}
    networks = sorted(set(roi_networks.values()))

    network_conn = {}
    for method, band_dict in results.items():
        network_conn[method] = {}
        for band_name, matrix in band_dict.items():
            within = {}
            between = {}
            for net in networks:
                net_indices = [i for i, r in enumerate(ROI_NAMES) if roi_networks[r] == net]
                if len(net_indices) >= 2:
                    vals = []
                    for ii in range(len(net_indices)):
                        for jj in range(ii + 1, len(net_indices)):
                            vals.append(matrix[net_indices[ii], net_indices[jj]])
                    within[net] = float(np.mean(vals)) if vals else 0.0

            for ni, net_a in enumerate(networks):
                for nj, net_b in enumerate(networks):
                    if nj <= ni:
                        continue
                    idx_a = [i for i, r in enumerate(ROI_NAMES) if roi_networks[r] == net_a]
                    idx_b = [i for i, r in enumerate(ROI_NAMES) if roi_networks[r] == net_b]
                    vals = [matrix[a, b] for a in idx_a for b in idx_b]
                    between[f"{net_a}-{net_b}"] = float(np.mean(vals)) if vals else 0.0

            network_conn[method][band_name] = {"within": within, "between": between}

    return network_conn


# ── Integration helper ────────────────────────────────────────────────────

def analyze_source(
    raw: mne.io.Raw,
    spectral_result: dict,
    params: dict,
    n_channels: int = 37,
) -> dict:
    """Run full source analysis: sLORETA power + DICS connectivity.

    Parameters
    ----------
    raw : mne.io.Raw
        Preprocessed continuous EEG data.
    spectral_result : dict
        Output from analyze_spectral() — must contain "band_power" and "ch_names".
    params : dict
        Pipeline parameters (uses "connectivity" section for bands).
    n_channels : int
        19 or 37.

    Returns
    -------
    dict with keys:
        "source_power": sLORETA results per band
        "source_connectivity": DICS connectivity results (or None if failed)
    """
    result = {}

    # sLORETA source power
    band_power = spectral_result.get("band_power", {})
    ch_names = spectral_result.get("ch_names", [])
    if band_power and len(ch_names) == n_channels:
        logger.info("Computing sLORETA source power...")
        result["source_power"] = compute_sloreta_source_power(
            band_power, ch_names, n_channels=n_channels,
        )
    else:
        logger.warning(
            f"Skipping sLORETA: expected {n_channels} channels, "
            f"got {len(ch_names)}"
        )
        result["source_power"] = None

    # DICS source connectivity
    conn_bands = params.get("connectivity", {}).get("bands", {})
    if conn_bands:
        logger.info("Computing DICS source connectivity...")
        try:
            conn_methods = params.get("connectivity", {}).get("methods", ["dwpli", "coh"])
            epoch_length = params.get("connectivity", {}).get("epoch_length", 2.0)
            result["source_connectivity"] = compute_dics_source_connectivity(
                raw, bands=conn_bands, n_channels=n_channels,
                methods=conn_methods, epoch_length=epoch_length,
            )
        except Exception:
            logger.error("DICS source connectivity failed", exc_info=True)
            result["source_connectivity"] = None
    else:
        result["source_connectivity"] = None

    return result


def source_result_to_metrics(source_result: dict) -> dict:
    """Convert source analysis results to flat metric dicts for normative aggregation.

    Returns a dict keyed by synthetic "channel" names:
    - "_src_ba_{BA}" for Brodmann area source power
    - "_src_roi_{ROI}" for ROI-level source power peaks
    - "_src_conn_{ROI_A}_{ROI_B}" for ROI-to-ROI connectivity
    - "_src_net_{network}" for network-level connectivity

    These slot into the existing normative.py aggregation without changes.
    """
    metrics = {}

    # Source power per Brodmann area
    sp = source_result.get("source_power")
    if sp:
        for band_name, band_data in sp.items():
            ba_power = band_data.get("ba_mean_power", {})
            for ba_label, power_val in ba_power.items():
                key = f"_src_ba_{ba_label}"
                if key not in metrics:
                    metrics[key] = {}
                if band_name not in metrics[key]:
                    metrics[key][band_name] = {}
                metrics[key][band_name]["source_power"] = power_val

    # Source connectivity (ROI-to-ROI)
    sc = source_result.get("source_connectivity")
    if sc:
        roi_conn = sc.get("roi_connectivity", {})
        for method, band_dict in roi_conn.items():
            for band_name, matrix in band_dict.items():
                for i in range(len(ROI_NAMES)):
                    for j in range(i + 1, len(ROI_NAMES)):
                        key = f"_src_conn_{ROI_NAMES[i]}_{ROI_NAMES[j]}"
                        if key not in metrics:
                            metrics[key] = {}
                        if band_name not in metrics[key]:
                            metrics[key][band_name] = {}
                        metrics[key][band_name][f"source_{method}"] = float(matrix[i, j])

        # Network-level
        net_conn = sc.get("network_connectivity", {})
        for method, band_dict in net_conn.items():
            for band_name, net_data in band_dict.items():
                for net_name, val in net_data.get("within", {}).items():
                    key = f"_src_net_{net_name}"
                    if key not in metrics:
                        metrics[key] = {}
                    if band_name not in metrics[key]:
                        metrics[key][band_name] = {}
                    metrics[key][band_name][f"within_{method}"] = val
                for net_pair, val in net_data.get("between", {}).items():
                    key = f"_src_net_{net_pair}"
                    if key not in metrics:
                        metrics[key] = {}
                    if band_name not in metrics[key]:
                        metrics[key][band_name] = {}
                    metrics[key][band_name][f"between_{method}"] = val

    return metrics
