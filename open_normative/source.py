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

# DK parcel → Brodmann area mapping (approximate, based on standard atlases).
# Used to derive per-DK-parcel corrected power from BA-level corrected power
# when --dk-corrected-power is not enabled (default, for performance reasons).
# Multiple BAs per parcel: averaged. Hemisphere is preserved.
# TODO: Compute true DK corrected power directly when compute budget allows.
_DK_TO_BA = {
    "precentral": ["BA4"],
    "postcentral": ["BA1", "BA2", "BA3"],
    "superiorfrontal": ["BA6", "BA8", "BA9"],
    "caudalmiddlefrontal": ["BA6", "BA8"],
    "rostralmiddlefrontal": ["BA9", "BA10", "BA46"],
    "parsopercularis": ["BA44"],
    "parstriangularis": ["BA45"],
    "parsorbitalis": ["BA47"],
    "superiortemporal": ["BA22", "BA41", "BA42"],
    "middletemporal": ["BA21"],
    "inferiortemporal": ["BA20"],
    "superiorparietal": ["BA5", "BA7"],
    "inferiorparietal": ["BA39", "BA40"],
    "supramarginal": ["BA40"],
    "precuneus": ["BA7"],
    "lateraloccipital": ["BA18", "BA19"],
    "cuneus": ["BA17", "BA18"],
    "lingual": ["BA17", "BA18", "BA19"],
    "pericalcarine": ["BA17"],
    "fusiform": ["BA37"],
    "medialorbitofrontal": ["BA11", "BA12"],
    "lateralorbitofrontal": ["BA47", "BA11"],
    "caudalanteriorcingulate": ["BA24", "BA32"],
    "rostralanteriorcingulate": ["BA24", "BA32"],
    "posteriorcingulate": ["BA23", "BA31"],
    "isthmuscingulate": ["BA29", "BA30"],
    "insula": ["BA13"],
    "frontalpole": ["BA10"],
    "temporalpole": ["BA38"],
    "transversetemporal": ["BA41", "BA42"],
    "entorhinal": ["BA28"],
    "parahippocampal": ["BA27", "BA35", "BA36"],
    "paracentral": ["BA4", "BA6"],
    "bankssts": ["BA22"],  # superior temporal sulcus, near BA22
}

# Inverse: BA → list of (dk_parcel, weight) where weight = 1/n_BAs_for_that_parcel
def _build_ba_to_dk():
    """Build BA → list of (dk_parcel, weight) for aggregation."""
    inv = {}
    for dk_parcel, ba_list in _DK_TO_BA.items():
        weight = 1.0 / len(ba_list)
        for ba in ba_list:
            inv.setdefault(ba, []).append((dk_parcel, weight))
    return inv

_BA_TO_DK = _build_ba_to_dk()

# Method name mapping for mne-connectivity
_METHOD_MAP = {
    "dwpli": "wpli2_debiased",
    "coh": "coh",
    "imcoh": "imcoh",
}

# ── Caches ────────────────────────────────────────────────────────────────

_SLORETA_COORDS_CACHE: Optional[np.ndarray] = None
_SLORETA_BA_CACHE: Optional[list] = None
_BA_LABELS_CACHE: dict = {}
_DK_LABELS_CACHE: dict = {}


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
    power_key: str = "absolute",
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
    power_key : str
        Key to extract from band_data (default "absolute", or
        "corrected_absolute" for specparam periodic-only power).

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
        abs_power = band_data.get(power_key)
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


# ── BA labels for BA-to-BA connectivity ──────────────────────────────────

def load_ba_labels(n_channels: int = 37) -> tuple[list, list[str]]:
    """Load pre-computed Brodmann Area labels for the fsaverage surface.

    Parameters
    ----------
    n_channels : int
        19 or 37.

    Returns
    -------
    labels : list[mne.Label]
        One Label per BA.
    ba_names : list[str]
        Sanitized BA name per label (e.g. "BA20").
    """
    if n_channels in _BA_LABELS_CACHE:
        return _BA_LABELS_CACHE[n_channels]

    pkl_path = _DATA_DIR / "source" / f"ba_labels_{n_channels}ch.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"BA labels not found: {pkl_path}. "
            f"Run 'python scripts/build_ba_labels.py --channels {n_channels}' first."
        )

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)  # noqa: S301

    labels = data["labels"]
    ba_names = data["ba_names"]
    _BA_LABELS_CACHE[n_channels] = (labels, ba_names)
    return labels, ba_names


# ── DK parcel labels for full DK connectivity ────────────────────────────

def load_dk_labels(n_channels: int = 37) -> tuple[list, list[str]]:
    """Load pre-computed individual Desikan-Killiany parcel labels.

    Parameters
    ----------
    n_channels : int
        19 or 37.

    Returns
    -------
    labels : list[mne.Label]
        One Label per DK parcel (68 total).
    dk_names : list[str]
        Parcel name per label (e.g. "superiorfrontal-lh").
    """
    if n_channels in _DK_LABELS_CACHE:
        return _DK_LABELS_CACHE[n_channels]

    pkl_path = _DATA_DIR / "source" / f"dk_labels_{n_channels}ch.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(
            f"DK labels not found: {pkl_path}. "
            f"Run 'python scripts/build_dk_labels.py --channels {n_channels}' first."
        )

    with open(pkl_path, "rb") as f:
        data = pickle.load(f)  # noqa: S301

    labels = data["labels"]
    dk_names = data["dk_names"]
    _DK_LABELS_CACHE[n_channels] = (labels, dk_names)
    return labels, dk_names


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
    ba_connectivity: bool = False,
    dk_connectivity: bool = False,
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
    ba_connectivity : bool
        If True, also compute Brodmann Area-to-BA connectivity.
    dk_connectivity : bool
        If True, also compute individual DK parcel-to-parcel connectivity.

    Returns
    -------
    dict with keys:
        "roi_connectivity": {method: {band: ndarray(18, 18)}}
        "network_connectivity": {method: {band: {"within": dict, "between": dict}}}
        "volume_conduction_flags": list[dict]
        "ba_connectivity": {method: {band: ndarray(n_ba, n_ba)}} or None
        "ba_names": list[str] or None
        "dk_connectivity": {method: {band: ndarray(n_dk, n_dk)}} or None
        "dk_names": list[str] or None
    """
    from mne.beamformer import apply_dics_epochs, make_dics
    from mne.time_frequency import csd_multitaper
    from mne_connectivity import spectral_connectivity_epochs

    if methods is None:
        methods = ["dwpli", "coh"]
    mne_methods = [_METHOD_MAP.get(m, m) for m in methods]

    # Load forward model
    fwd, src, grouped_labels = load_forward_assets(n_channels)

    # BA labels are no longer extracted directly — BA metrics are derived
    # from DK parcel aggregation. ba_connectivity flag now triggers DK
    # extraction internally so BA can be derived.
    ba_labels, ba_names = None, None  # legacy, unused

    # Load DK parcel labels if either DK or BA connectivity is requested.
    # DK is the canonical source of truth for both atlases.
    dk_labels, dk_names = None, None
    if dk_connectivity or ba_connectivity:
        dk_labels, dk_names = load_dk_labels(n_channels)
        logger.info(f"  DK extraction: {len(dk_names)} parcels (canonical for DK + derived BA)")

    # Epoch the data
    events = mne.make_fixed_length_events(raw, duration=epoch_length)
    epochs = mne.Epochs(
        raw, events, tmin=0, tmax=epoch_length - 1.0 / raw.info["sfreq"],
        baseline=None, preload=True, verbose=False,
    )

    if not any(p["desc"] == "eeg_ref_proj" for p in epochs.info.get("projs", [])):
        epochs.set_eeg_reference(projection=True, verbose=False)

    # DICS beamforming + parcellation per band
    # Wrap in np.errstate to prevent FloatingPointError from numpy operations
    # inside MNE (csd_multitaper, make_dics). We use adaptive regularization
    # to handle ill-conditioned CSD matrices.
    roi_ts = {}
    dk_ts = {}
    with np.errstate(all="warn"):
        for band_name, (fmin, fmax) in bands.items():
            logger.info(f"  DICS: {band_name} [{fmin}-{fmax} Hz]")

            try:
                csd = csd_multitaper(epochs, fmin=fmin, fmax=fmax,
                                     adaptive=True, verbose=False)
            except (FloatingPointError, np.linalg.LinAlgError) as exc:
                logger.warning(f"    {band_name}: CSD failed ({exc}), skipping band")
                continue
            csd_mean = csd.mean()

            # Adaptive regularization: try default reg, escalate if CSD is
            # ill-conditioned.
            band_stcs = None
            for try_reg in [reg, 0.1, 0.2, 0.5]:
                try:
                    filters = make_dics(
                        epochs.info, fwd, csd_mean,
                        reg=try_reg, real_filter=True, pick_ori="max-power",
                        verbose=False,
                    )
                    band_stcs = list(apply_dics_epochs(epochs, filters, verbose=False))
                    if try_reg != reg:
                        logger.info(f"    {band_name}: succeeded with reg={try_reg}")
                    break
                except (FloatingPointError, np.linalg.LinAlgError):
                    logger.warning(
                        f"    {band_name}: reg={try_reg} failed (ill-conditioned CSD), "
                        f"trying higher"
                    )
                    continue

            if band_stcs is None:
                logger.error(f"    {band_name}: DICS failed at all reg levels, skipping band")
                continue

            tc_list = mne.extract_label_time_course(
                band_stcs, grouped_labels, src,
                mode="mean_flip", verbose=False,
            )
            roi_ts[band_name] = np.array(tc_list)

            # Extract individual DK parcel time courses (canonical for BA + DK)
            if dk_labels is not None:
                dk_tc_list = mne.extract_label_time_course(
                    band_stcs, dk_labels, src,
                    mode="mean_flip", verbose=False,
                )
                dk_ts[band_name] = np.array(dk_tc_list)
                del dk_tc_list

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

    # BA-to-BA connectivity is no longer computed directly — it's derived
    # from DK parcel connectivity in source_result_to_metrics().
    ba_results = None

    # Compute individual DK parcel-to-parcel connectivity
    dk_results = None
    if dk_labels is not None and dk_ts:
        dk_results = {m: {} for m in methods}
        for band_name, data in dk_ts.items():
            fmin, fmax = bands[band_name]

            dk_info = mne.create_info(
                ch_names=list(dk_names), sfreq=sfreq, ch_types="misc",
            )
            dk_epochs_array = mne.EpochsArray(data, dk_info, verbose=False)

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*no Annotations.*")
                dk_con = spectral_connectivity_epochs(
                    dk_epochs_array, method=mne_methods,
                    fmin=[fmin], fmax=[fmax], faverage=True,
                    n_jobs=1, verbose=False,
                )

            if not isinstance(dk_con, list):
                dk_con = [dk_con]

            for i, method in enumerate(methods):
                con_data = dk_con[i].get_data(output="dense")
                matrix = con_data[:, :, 0]
                matrix = (matrix + matrix.T) / 2
                np.fill_diagonal(matrix, 0)
                matrix = np.clip(matrix, 0, 1)
                dk_results[method][band_name] = matrix

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
        "ba_connectivity": ba_results,
        "ba_names": ba_names,
        "dk_connectivity": dk_results,
        "dk_names": dk_names,
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


# ── Source-level specparam (corrected DICS power) ────────────────────────

def _broadband_dics(
    raw: mne.io.Raw,
    n_channels: int = 37,
    epoch_length: float = 2.0,
    reg: float = 0.05,
) -> tuple[list, object, float]:
    """Compute broadband DICS source estimates (shared across label sets).

    Returns
    -------
    stcs : list[SourceEstimate]
        Source time courses per epoch.
    src : mne.SourceSpaces
        Source space.
    sfreq : float
        Sampling frequency.
    """
    from mne.beamformer import apply_dics_epochs, make_dics
    from mne.time_frequency import csd_multitaper

    fwd, src, _ = load_forward_assets(n_channels)

    events = mne.make_fixed_length_events(raw, duration=epoch_length)
    epochs = mne.Epochs(
        raw, events, tmin=0, tmax=epoch_length - 1.0 / raw.info["sfreq"],
        baseline=None, preload=True, verbose=False,
    )
    if not any(p["desc"] == "eeg_ref_proj" for p in epochs.info.get("projs", [])):
        epochs.set_eeg_reference(projection=True, verbose=False)

    with np.errstate(all="warn"):
        csd = csd_multitaper(epochs, fmin=1.0, fmax=50.0,
                             adaptive=True, verbose=False)
        csd_mean = csd.mean()

        stcs = None
        for try_reg in [reg, 0.1, 0.2, 0.5]:
            try:
                filters = make_dics(
                    epochs.info, fwd, csd_mean,
                    reg=try_reg, real_filter=True, pick_ori="max-power",
                    verbose=False,
                )
                stcs = list(apply_dics_epochs(epochs, filters, verbose=False))
                break
            except (FloatingPointError, np.linalg.LinAlgError):
                continue

    if stcs is None:
        raise RuntimeError("Broadband DICS failed at all regularization levels")

    del csd, csd_mean, filters
    gc.collect()

    return stcs, src, raw.info["sfreq"]


def _specparam_from_stcs(
    stcs: list,
    labels: list,
    label_names: list[str],
    src,
    sfreq: float,
    bands: dict,
    ap_params: dict,
) -> dict:
    """Extract label time courses from precomputed stcs, run specparam.

    Returns
    -------
    dict
        {label_name: {band_name: {"corrected_dics_power": float, "aperiodic_exponent": float}}}
    """
    from scipy.signal import welch as scipy_welch

    try:
        from specparam import SpectralModel
    except ImportError:
        return None

    tc_list = mne.extract_label_time_course(
        stcs, labels, src, mode="mean_flip", verbose=False,
    )
    tc_array = np.array(tc_list)  # (n_epochs, n_labels, n_times)
    n_epochs, n_labels, n_times = tc_array.shape
    tc_concat = tc_array.transpose(1, 0, 2).reshape(n_labels, -1)

    n_fft = min(int(sfreq * 2), tc_concat.shape[1])
    freq_range = ap_params.get("freq_range", [2, 40])

    results = {}
    for li, lname in enumerate(label_names):
        freqs_psd, psd = scipy_welch(
            tc_concat[li], fs=sfreq, nperseg=n_fft,
            noverlap=n_fft // 2, window="hann",
        )

        sm = SpectralModel(
            peak_width_limits=ap_params.get("peak_width_limits", [1, 8]),
            max_n_peaks=ap_params.get("max_n_peaks", 6),
            min_peak_height=ap_params.get("min_peak_height", 0.1),
            peak_threshold=ap_params.get("peak_threshold", 2.0),
            verbose=False,
        )
        try:
            sm.fit(freqs_psd, psd, freq_range)
            if hasattr(sm, "aperiodic_params_"):
                exponent = float(sm.aperiodic_params_[-1])
                offset = float(sm.aperiodic_params_[0])
            else:
                ap = sm.results.params.aperiodic
                exponent = float(ap.params[ap.indices["exponent"]])
                offset = float(ap.params[ap.indices["offset"]])
        except Exception:
            results[lname] = {
                band_name: {"corrected_dics_power": float("nan"),
                            "aperiodic_exponent": float("nan")}
                for band_name in bands
            }
            continue

        # Subtract aperiodic in log10 space
        with np.errstate(divide="ignore", invalid="ignore"):
            log10_freqs = np.log10(freqs_psd)
            log10_psd = np.log10(psd)
        log10_aperiodic = offset - exponent * log10_freqs
        periodic_log10 = log10_psd - log10_aperiodic
        periodic_linear = np.maximum(np.power(10.0, periodic_log10), 0.0)

        label_results = {}
        for band_name, (fmin, fmax) in bands.items():
            idx = np.where((freqs_psd >= fmin) & (freqs_psd <= fmax))[0]
            if len(idx) > 0:
                bp = float(np.trapezoid(periodic_linear[idx], freqs_psd[idx]))
            else:
                bp = float("nan")
            label_results[band_name] = {
                "corrected_dics_power": bp,
                "aperiodic_exponent": exponent,
            }
        results[lname] = label_results

    return results


def compute_dics_corrected_power(
    raw: mne.io.Raw,
    labels: list,
    label_names: list[str],
    bands: dict,
    params: dict,
    n_channels: int = 37,
    epoch_length: float = 2.0,
    reg: float = 0.05,
) -> dict | None:
    """Compute specparam-corrected source power via broadband DICS.

    Runs broadband DICS beamformer → extracts label time courses →
    computes Welch PSD per label → runs specparam → subtracts aperiodic →
    computes periodic-only band power.

    Parameters
    ----------
    raw : mne.io.Raw
        Preprocessed continuous EEG data.
    labels : list[mne.Label]
        Labels to extract time courses from (ROIs, BAs, or DK parcels).
    label_names : list[str]
        Name per label.
    bands : dict
        {band_name: [fmin, fmax]} for band power computation.
    params : dict
        Pipeline parameters (uses "spectral.aperiodic" for specparam settings).
    n_channels : int
        19 or 37.
    epoch_length : float
        Epoch length in seconds for DICS.
    reg : float
        Regularization parameter.

    Returns
    -------
    dict or None
        {label_name: {band_name: {"corrected_dics_power": float, "aperiodic_exponent": float}}}
    """
    from mne.beamformer import apply_dics_epochs, make_dics
    from mne.time_frequency import csd_multitaper
    from scipy.signal import welch as scipy_welch

    try:
        from specparam import SpectralModel
    except ImportError:
        logger.warning("specparam not installed — skipping DICS corrected power")
        return None

    fwd, src, _ = load_forward_assets(n_channels)

    # Epoch the data
    events = mne.make_fixed_length_events(raw, duration=epoch_length)
    epochs = mne.Epochs(
        raw, events, tmin=0, tmax=epoch_length - 1.0 / raw.info["sfreq"],
        baseline=None, preload=True, verbose=False,
    )
    if not any(p["desc"] == "eeg_ref_proj" for p in epochs.info.get("projs", [])):
        epochs.set_eeg_reference(projection=True, verbose=False)

    sfreq = raw.info["sfreq"]

    # Broadband DICS (1-50 Hz)
    logger.info("  Broadband DICS for source-level specparam...")
    with np.errstate(all="warn"):
        try:
            csd = csd_multitaper(epochs, fmin=1.0, fmax=50.0,
                                 adaptive=True, verbose=False)
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            logger.warning(f"  Broadband CSD failed ({exc}), skipping DICS corrected power")
            return None

        csd_mean = csd.mean()

        stcs = None
        for try_reg in [reg, 0.1, 0.2, 0.5]:
            try:
                filters = make_dics(
                    epochs.info, fwd, csd_mean,
                    reg=try_reg, real_filter=True, pick_ori="max-power",
                    verbose=False,
                )
                stcs = list(apply_dics_epochs(epochs, filters, verbose=False))
                break
            except (FloatingPointError, np.linalg.LinAlgError):
                continue

    if stcs is None:
        logger.warning("  Broadband DICS failed at all reg levels")
        return None

    # Extract label time courses
    tc_list = mne.extract_label_time_course(
        stcs, labels, src, mode="mean_flip", verbose=False,
    )
    tc_array = np.array(tc_list)  # (n_epochs, n_labels, n_times)

    del stcs, csd, csd_mean, filters
    gc.collect()

    # Concatenate epochs for PSD estimation
    n_epochs, n_labels, n_times = tc_array.shape
    # Reshape to (n_labels, n_epochs * n_times)
    tc_concat = tc_array.transpose(1, 0, 2).reshape(n_labels, -1)

    # Welch PSD per label
    n_fft = min(int(sfreq * 2), tc_concat.shape[1])
    ap_params = params.get("spectral", {}).get("aperiodic", {})

    results = {}
    for li, lname in enumerate(label_names):
        freqs_psd, psd = scipy_welch(
            tc_concat[li], fs=sfreq, nperseg=n_fft,
            noverlap=n_fft // 2, window="hann",
        )

        # Run specparam
        sm = SpectralModel(
            peak_width_limits=ap_params.get("peak_width_limits", [1, 8]),
            max_n_peaks=ap_params.get("max_n_peaks", 6),
            min_peak_height=ap_params.get("min_peak_height", 0.1),
            peak_threshold=ap_params.get("peak_threshold", 2.0),
            verbose=False,
        )
        freq_range = ap_params.get("freq_range", [2, 40])
        try:
            # specparam expects log10(power) internally; input in linear
            sm.fit(freqs_psd, psd, freq_range)
            if hasattr(sm, "aperiodic_params_"):
                exponent = float(sm.aperiodic_params_[-1])
                offset = float(sm.aperiodic_params_[0])
            else:
                ap = sm.results.params.aperiodic
                exponent = float(ap.params[ap.indices["exponent"]])
                offset = float(ap.params[ap.indices["offset"]])
        except Exception:
            results[lname] = {
                band_name: {"corrected_dics_power": float("nan"),
                            "aperiodic_exponent": float("nan")}
                for band_name in bands
            }
            continue

        # Subtract aperiodic in log10 space
        with np.errstate(divide="ignore", invalid="ignore"):
            log10_freqs = np.log10(freqs_psd)
            log10_psd = np.log10(psd)
        log10_aperiodic = offset - exponent * log10_freqs
        periodic_log10 = log10_psd - log10_aperiodic
        periodic_linear = np.maximum(np.power(10.0, periodic_log10), 0.0)

        # Band power from periodic PSD
        label_results = {}
        for band_name, (fmin, fmax) in bands.items():
            idx = np.where((freqs_psd >= fmin) & (freqs_psd <= fmax))[0]
            if len(idx) > 0:
                bp = float(np.trapezoid(periodic_linear[idx], freqs_psd[idx]))
            else:
                bp = float("nan")
            label_results[band_name] = {
                "corrected_dics_power": bp,
                "aperiodic_exponent": exponent,
            }
        results[lname] = label_results

    return results


# ── Integration helper ────────────────────────────────────────────────────

def analyze_source(
    raw: mne.io.Raw,
    spectral_result: dict,
    params: dict,
    n_channels: int = 37,
    ba_connectivity: bool = False,
    dk_connectivity: bool = False,
    dk_corrected_power: bool = False,
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
    ba_connectivity : bool
        If True, also compute BA-to-BA connectivity via DICS.
    dk_connectivity : bool
        If True, also compute individual DK parcel-to-parcel connectivity.

    Returns
    -------
    dict with keys:
        "source_power": sLORETA results per band
        "corrected_source_power": periodic-only source power (or None)
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

        # Corrected (periodic-only) source power via specparam
        corrected_bp = spectral_result.get("corrected_band_power", {})
        if corrected_bp:
            logger.info("Computing corrected sLORETA source power...")
            result["corrected_source_power"] = compute_sloreta_source_power(
                corrected_bp, ch_names, n_channels=n_channels,
                power_key="corrected_absolute",
            )
        else:
            result["corrected_source_power"] = None
    else:
        logger.warning(
            f"Skipping sLORETA: expected {n_channels} channels, "
            f"got {len(ch_names)}"
        )
        result["source_power"] = None
        result["corrected_source_power"] = None

    # DICS source connectivity
    conn_bands = params.get("connectivity", {}).get("bands", {})
    if conn_bands:
        logger.info("Computing DICS source connectivity...")
        try:
            conn_methods = params.get("connectivity", {}).get("methods", ["dwpli", "coh"])
            epoch_length = params.get("connectivity", {}).get("epoch_length", 2.0)
            with np.errstate(all="warn"):
                result["source_connectivity"] = compute_dics_source_connectivity(
                    raw, bands=conn_bands, n_channels=n_channels,
                    methods=conn_methods, epoch_length=epoch_length,
                    ba_connectivity=ba_connectivity,
                    dk_connectivity=dk_connectivity,
                )
        except BaseException as exc:
            logger.error("DICS source connectivity failed: %s", exc)
            result["source_connectivity"] = None
    else:
        result["source_connectivity"] = None

    # DICS source-level specparam (corrected DICS power)
    # DK is the canonical atlas: BA values are derived from DK in
    # source_result_to_metrics(). We always compute ROI and DK directly.
    spectral_bands = params.get("spectral", {}).get("bands", {})
    result["dics_corrected_roi"] = None
    result["dics_corrected_ba"] = None  # legacy field, never populated directly
    result["dics_corrected_dk"] = None

    needs_dk = dk_connectivity or ba_connectivity
    if spectral_bands and conn_bands:
        logger.info("Computing source-level specparam (corrected DICS power)...")
        epoch_length = params.get("connectivity", {}).get("epoch_length", 2.0)

        try:
            stcs, src, sfreq_dics = _broadband_dics(
                raw, n_channels, epoch_length,
            )
        except BaseException as exc:
            logger.error("Broadband DICS failed: %s", exc)
            stcs = None

        if stcs is not None:
            ap_params = params.get("spectral", {}).get("aperiodic", {})

            # ROIs (always)
            fwd, src_space, grouped_labels = load_forward_assets(n_channels)
            try:
                result["dics_corrected_roi"] = _specparam_from_stcs(
                    stcs, grouped_labels, list(ROI_NAMES), src_space,
                    sfreq_dics, spectral_bands, ap_params,
                )
            except BaseException as exc:
                logger.error("DICS corrected ROI power failed: %s", exc)

            # DK parcels (canonical for both DK and derived BA)
            if needs_dk:
                try:
                    dk_labels_l, dk_names_l = load_dk_labels(n_channels)
                    result["dics_corrected_dk"] = _specparam_from_stcs(
                        stcs, dk_labels_l, dk_names_l, src_space,
                        sfreq_dics, spectral_bands, ap_params,
                    )
                except BaseException as exc:
                    logger.error("DICS corrected DK power failed: %s", exc)

            del stcs
            gc.collect()

    return result


_SOURCE_RATIO_POWER_KEYS = (
    "source_power",
    "corrected_source_power",
    "corrected_dics_power",
)


def add_source_ratios(metrics: dict, ratio_defs: list[dict]) -> None:
    """Inject ratio bands into source metrics in place.

    For each source channel and each available power_key
    (source_power / corrected_source_power / corrected_dics_power),
    compute every ratio in ratio_defs from the underlying band values
    and store as ``metrics[ch][<ratio_band>]["value"]``, where:

    - source_power → ratio band ``<name>``
    - corrected_source_power / corrected_dics_power → ratio band
      ``corrected_<name>``

    This mirrors the scalp convention where corrected ratios are stored
    as a separate band keyed ``corrected_<ratio_name>``.
    """
    if not ratio_defs:
        return
    for ch, bands in list(metrics.items()):
        if not isinstance(bands, dict):
            continue
        for power_key in _SOURCE_RATIO_POWER_KEYS:
            band_to_val: dict = {}
            for band_name, vals in bands.items():
                if not isinstance(vals, dict):
                    continue
                if power_key in vals:
                    band_to_val[band_name] = vals[power_key]
            if not band_to_val:
                continue
            prefix = "" if power_key == "source_power" else "corrected_"
            for spec in ratio_defs:
                num_vals = [band_to_val.get(b) for b in spec["num"]]
                den_vals = [band_to_val.get(b) for b in spec["den"]]
                if any(v is None for v in num_vals + den_vals):
                    continue
                try:
                    num = float(sum(num_vals))
                    den = float(sum(den_vals))
                except (TypeError, ValueError):
                    continue
                if not np.isfinite(num) or not np.isfinite(den) or den <= 0:
                    val = float("nan")
                else:
                    val = num / den
                ratio_band = f"{prefix}{spec['name']}"
                if ratio_band not in metrics[ch]:
                    metrics[ch][ratio_band] = {}
                metrics[ch][ratio_band]["value"] = val


def source_result_to_metrics(
    source_result: dict, ratio_defs: Optional[list[dict]] = None
) -> dict:
    """Convert source analysis results to flat metric dicts for normative aggregation.

    Returns a dict keyed by synthetic "channel" names:
    - "_src_ba_{BA}" for Brodmann area source power (+ corrected_source_power)
    - "_src_roi_{ROI}" for ROI-level source power peaks
    - "_src_conn_{ROI_A}_{ROI_B}" for ROI-to-ROI connectivity
    - "_src_ba_conn_{BA_A}_{BA_B}" for BA-to-BA connectivity
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

    # Corrected (periodic-only) source power per Brodmann area
    csp = source_result.get("corrected_source_power")
    if csp:
        for band_name, band_data in csp.items():
            ba_power = band_data.get("ba_mean_power", {})
            for ba_label, power_val in ba_power.items():
                key = f"_src_ba_{ba_label}"
                if key not in metrics:
                    metrics[key] = {}
                if band_name not in metrics[key]:
                    metrics[key][band_name] = {}
                metrics[key][band_name]["corrected_source_power"] = power_val

    # DICS corrected power (source-level specparam) per ROI
    dcr = source_result.get("dics_corrected_roi")
    if dcr:
        for roi_name, band_dict in dcr.items():
            key = f"_src_conn_{roi_name}"  # reuse ROI channel prefix
            for band_name, vals in band_dict.items():
                if key not in metrics:
                    metrics[key] = {}
                if band_name not in metrics[key]:
                    metrics[key][band_name] = {}
                metrics[key][band_name]["corrected_dics_power"] = vals.get("corrected_dics_power", float("nan"))
                metrics[key][band_name]["source_aperiodic_exponent"] = vals.get("aperiodic_exponent", float("nan"))

    # DICS corrected power per DK parcel (canonical, direct from DK labels)
    dcdk = source_result.get("dics_corrected_dk")
    if dcdk:
        for dk_name, band_dict in dcdk.items():
            key = f"_src_dk_power_{dk_name}"
            for band_name, vals in band_dict.items():
                if key not in metrics:
                    metrics[key] = {}
                if band_name not in metrics[key]:
                    metrics[key][band_name] = {}
                metrics[key][band_name]["corrected_dics_power"] = vals.get("corrected_dics_power", float("nan"))
                metrics[key][band_name]["source_aperiodic_exponent"] = vals.get("aperiodic_exponent", float("nan"))

        # Derive BA corrected DICS power from DK parcels (aggregation).
        # For each BA, average the corrected_dics_power of its mapped DK
        # parcels, weighted by 1/n_BAs_per_parcel (so a parcel split across
        # 3 BAs contributes 1/3 to each).
        for ba_short, parcel_weights in _BA_TO_DK.items():
            ba_key = f"_src_ba_{ba_short}"
            for hemi in ("lh", "rh"):
                # Aggregate per band
                band_values: dict = {}
                band_exponents: dict = {}
                total_weight = 0.0
                for dk_parcel, weight in parcel_weights:
                    dk_name = f"{dk_parcel}-{hemi}"
                    if dk_name not in dcdk:
                        continue
                    total_weight += weight
                    for band_name, vals in dcdk[dk_name].items():
                        cdp = vals.get("corrected_dics_power", float("nan"))
                        exp = vals.get("aperiodic_exponent", float("nan"))
                        if not np.isnan(cdp):
                            band_values.setdefault(band_name, []).append((cdp, weight))
                        if not np.isnan(exp):
                            band_exponents.setdefault(band_name, []).append((exp, weight))

                if not band_values:
                    continue

                # Hemisphere-specific BA key (BA17-lh, BA17-rh, etc.)
                # Or aggregate both hemispheres? We'll keep them separate.
                key = f"{ba_key}-{hemi}"
                if key not in metrics:
                    metrics[key] = {}
                for band_name, weighted in band_values.items():
                    if band_name not in metrics[key]:
                        metrics[key][band_name] = {}
                    weights = sum(w for _, w in weighted)
                    weighted_sum = sum(v * w for v, w in weighted)
                    metrics[key][band_name]["corrected_dics_power"] = float(weighted_sum / weights)
                    if band_name in band_exponents:
                        exp_weights = sum(w for _, w in band_exponents[band_name])
                        exp_sum = sum(v * w for v, w in band_exponents[band_name])
                        metrics[key][band_name]["source_aperiodic_exponent"] = float(exp_sum / exp_weights)

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

        # Individual DK parcel-to-parcel connectivity (canonical)
        dk_conn = sc.get("dk_connectivity")
        dk_names = sc.get("dk_names", [])
        dk_idx = {name: i for i, name in enumerate(dk_names)}
        if dk_conn and dk_names:
            for method, band_dict in dk_conn.items():
                for band_name, matrix in band_dict.items():
                    for i in range(len(dk_names)):
                        for j in range(i + 1, len(dk_names)):
                            key = f"_src_dk_{dk_names[i]}_{dk_names[j]}"
                            if key not in metrics:
                                metrics[key] = {}
                            if band_name not in metrics[key]:
                                metrics[key][band_name] = {}
                            metrics[key][band_name][f"source_{method}"] = float(matrix[i, j])

            # Derive BA-to-BA connectivity from DK by averaging mapped pairs.
            # For BA-A → BA-B: collect all (parcel_a, parcel_b) DK pairs where
            # parcel_a is in BA-A's list and parcel_b is in BA-B's list, then
            # average those connectivity values.
            ba_short_list = sorted(_BA_TO_DK.keys())
            for hemi in ("lh", "rh"):
                # Build BA → list of dk indices for this hemisphere
                ba_to_dk_idx = {}
                for ba_short, parcel_weights in _BA_TO_DK.items():
                    indices = []
                    for parcel, _w in parcel_weights:
                        dk_name = f"{parcel}-{hemi}"
                        if dk_name in dk_idx:
                            indices.append(dk_idx[dk_name])
                    if indices:
                        ba_to_dk_idx[ba_short] = indices

                ba_in_hemi = sorted(ba_to_dk_idx.keys())
                for method, band_dict in dk_conn.items():
                    for band_name, matrix in band_dict.items():
                        for ai, ba_a in enumerate(ba_in_hemi):
                            for bi in range(ai + 1, len(ba_in_hemi)):
                                ba_b = ba_in_hemi[bi]
                                idxs_a = ba_to_dk_idx[ba_a]
                                idxs_b = ba_to_dk_idx[ba_b]
                                pair_vals = []
                                for ia in idxs_a:
                                    for ib in idxs_b:
                                        if ia == ib:
                                            continue
                                        pair_vals.append(matrix[ia, ib])
                                if not pair_vals:
                                    continue
                                key = f"_src_ba_conn_{ba_a}-{hemi}_{ba_b}-{hemi}"
                                if key not in metrics:
                                    metrics[key] = {}
                                if band_name not in metrics[key]:
                                    metrics[key][band_name] = {}
                                metrics[key][band_name][f"source_{method}"] = float(np.mean(pair_vals))

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

    if ratio_defs is None:
        from open_normative.parameters import PIPELINE_PARAMS
        ratio_defs = PIPELINE_PARAMS.get("spectral", {}).get("ratios", [])
    add_source_ratios(metrics, ratio_defs)

    return metrics
