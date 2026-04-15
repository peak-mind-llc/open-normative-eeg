"""Channel name normalization, montage mapping, and EEG file loading.

Handles mapping from various EEG system naming conventions to the standard
19-channel 10-20 or 37-channel 10-10 montages used for normative processing.
"""

from __future__ import annotations

from pathlib import Path

import mne
import numpy as np

from open_normative.parameters import PIPELINE_PARAMS

_PARAMS = PIPELINE_PARAMS["channels"]
_CHANNELS_19 = _PARAMS["channels_19"]
_CHANNELS_37 = _PARAMS["channels_37"]
_NAME_MAP = _PARAMS["name_mapping"]
_CAP_FIXES = _PARAMS["capitalization_fixes"]

_CHANNEL_SETS = {
    19: _CHANNELS_19,
    37: _CHANNELS_37,
}

# Known channel base names for reference suffix detection
_KNOWN_BASES = {
    "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
    "T3", "C3", "Cz", "C4", "T4", "T5", "P3", "Pz", "P4", "T6",
    "O1", "O2", "T7", "T8", "P7", "P8",
    "AF3", "AF4", "FC1", "FC2", "FC3", "FC4", "FC5", "FC6",
    "FT7", "FT8", "FT9", "FT10",
    "CP1", "CP2", "CP3", "CP4", "CP5", "CP6",
    "TP7", "TP8", "TP9", "TP10",
    "PO3", "PO4", "PO7", "PO8",
    "Fpz", "CPz", "POz", "Oz", "Iz",
    "A1", "A2", "M1", "M2",
    "C1", "C2", "C5", "C6",
    "F1", "F2", "F5", "F6",
    "P1", "P2", "P5", "P6",
}


def strip_reference_suffix(name: str) -> str:
    """Strip a reference suffix (e.g. '-LE', '-AR') from a channel name.

    Preserves bipolar derivations like 'T3-T4' where both sides are
    known channel names.
    """
    if "-" not in name:
        return name
    parts = name.split("-", 1)
    base = parts[0].strip()
    suffix = parts[1].strip()
    if base in _KNOWN_BASES and suffix in _KNOWN_BASES:
        return name
    if base in _KNOWN_BASES:
        return base
    return name


def normalize_channel_names(ch_names: list[str]) -> list[str]:
    """Normalize a list of channel names to standard 10-20 convention.

    Handles:
    - EDF 'EEG Fp1-LE' prefix+suffix format
    - Reference suffixes (-LE, -AR, -Ref, etc.)
    - 10-10 -> 10-20 renaming (T7->T3, T8->T4, P7->T5, P8->T6)
    - Capitalization fixes (FP1->Fp1)
    """
    result = []
    for name in ch_names:
        if name.startswith("EEG "):
            name = name[4:]
        name = name.rstrip(". ")
        name = strip_reference_suffix(name)
        name = _CAP_FIXES.get(name, name)
        name = _NAME_MAP.get(name, name)
        result.append(name)
    return result


def pick_standard_channels(raw: mne.io.Raw, n_channels: int = 19) -> mne.io.Raw:
    """Reduce a Raw object to a standard channel montage.

    Supports 19-channel (10-20) and 37-channel (10-10) montages.

    First normalizes channel names, then picks channels by name matching.
    If fewer than the target number of channels match by name and the raw
    has montage positions, falls back to spatial nearest-neighbor matching.

    Parameters
    ----------
    raw : mne.io.Raw
        Input raw EEG data.
    n_channels : int
        Target channel count (19 or 37). Default 19.
    """
    target_channels = _CHANNEL_SETS.get(n_channels)
    if target_channels is None:
        raise ValueError(
            f"Unsupported channel count: {n_channels}. "
            f"Supported: {sorted(_CHANNEL_SETS.keys())}"
        )
    n_required = len(target_channels)

    raw = raw.copy()

    new_names = normalize_channel_names(raw.ch_names)
    rename_map = {}
    for old, new in zip(raw.ch_names, new_names):
        if old != new:
            rename_map[old] = new
    if rename_map:
        raw.rename_channels(rename_map)

    available = [ch for ch in target_channels if ch in raw.ch_names]

    if len(available) >= n_required:
        raw.pick(available)
        raw.reorder_channels(available)
        montage = mne.channels.make_standard_montage("standard_1020")
        raw.set_montage(montage, on_missing="ignore", verbose=False)
        return raw

    # Spatial nearest-neighbor fallback for high-density systems
    if raw.get_montage() is not None:
        target_montage = mne.channels.make_standard_montage("standard_1020")
        target_pos = target_montage.get_positions()["ch_pos"]
        raw_pos = raw.get_montage().get_positions()["ch_pos"]

        raw_chs_with_pos = {ch: pos for ch, pos in raw_pos.items() if ch in raw.ch_names}
        if len(raw_chs_with_pos) >= n_required:
            matched = {}
            used_sources = set()
            for target_ch in target_channels:
                if target_ch in available:
                    matched[target_ch] = target_ch
                    used_sources.add(target_ch)
                    continue
                if target_ch not in target_pos:
                    continue
                t_pos = target_pos[target_ch]
                best_dist = np.inf
                best_ch = None
                for src_ch, src_pos in raw_chs_with_pos.items():
                    if src_ch in used_sources:
                        continue
                    dist = np.linalg.norm(np.array(t_pos) - np.array(src_pos))
                    if dist < best_dist:
                        best_dist = dist
                        best_ch = src_ch
                if best_ch is not None:
                    matched[target_ch] = best_ch
                    used_sources.add(best_ch)

            if len(matched) >= n_required:
                src_chs = list(matched.values())
                raw.pick(src_chs)
                rename = {v: k for k, v in matched.items() if v != k}
                if rename:
                    raw.rename_channels(rename)
                raw.reorder_channels(target_channels)
                montage = mne.channels.make_standard_montage("standard_1020")
                raw.set_montage(montage, on_missing="ignore", verbose=False)
                return raw

    if available:
        raw.pick(available)
        montage = mne.channels.make_standard_montage("standard_1020")
        raw.set_montage(montage, on_missing="ignore", verbose=False)
        return raw

    raise ValueError(
        f"Cannot map channels to standard {n_channels}-channel montage. "
        f"Found {len(available)} matching channels out of {n_required} required. "
        f"Raw channels: {raw.ch_names[:10]}..."
    )


def pick_standard_19(raw: mne.io.Raw) -> mne.io.Raw:
    """Reduce a Raw object to the standard 19-channel 10-20 montage.

    Convenience wrapper around :func:`pick_standard_channels`.
    """
    return pick_standard_channels(raw, n_channels=19)


_LOADERS = {
    ".vhdr": mne.io.read_raw_brainvision,
    ".edf": mne.io.read_raw_edf,
    ".set": mne.io.read_raw_eeglab,
    ".fif": mne.io.read_raw_fif,
    ".mff": mne.io.read_raw_egi,
}


def set_egi128_montage(raw: mne.io.Raw) -> mne.io.Raw:
    """Set the GSN-HydroCel-128 montage on an EGI raw object if needed.

    EGI 128-channel data uses electrode names like 'E1', 'E2', ..., 'E128'
    plus 'Cz'. This function sets the standard montage so that spatial
    nearest-neighbor channel mapping can work.
    """
    if raw.get_montage() is not None:
        return raw
    try:
        montage = mne.channels.make_standard_montage("GSN-HydroCel-128")
        raw.set_montage(montage, on_missing="ignore", verbose=False)
    except Exception:
        pass
    return raw


def load_and_standardize(
    filepath: str | Path, n_channels: int = 19,
) -> mne.io.Raw:
    """Load an EEG file and standardize to a standard channel montage.

    Supports: .vhdr (BrainVision), .edf, .set (EEGLAB), .fif (MNE)

    Parameters
    ----------
    filepath : str or Path
        Path to the EEG file.
    n_channels : int
        Target channel count (19 or 37). Default 19.
    """
    filepath = Path(filepath)
    ext = filepath.suffix.lower()
    loader = _LOADERS.get(ext)
    if loader is None:
        raise ValueError(
            f"Unsupported file format: {ext}. Supported: {list(_LOADERS.keys())}"
        )

    raw = loader(filepath, preload=True, verbose=False)

    eeg_types = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(eeg_types) < len(raw.ch_names):
        raw.pick("eeg")

    return pick_standard_channels(raw, n_channels=n_channels)
