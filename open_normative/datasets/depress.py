"""Depression EEG dataset loader (ds003478).

122 subjects total (~55-70 healthy controls), ages 18-24, 64-channel
Neuroscan Synamps2, EEGLAB .set/.fdt format. CC0 license.

Data layout (BIDS on OpenNeuro ds003478):
    sub-XXX/eeg/sub-XXX_task-Rest_run-01_eeg.set
    sub-XXX/eeg/sub-XXX_task-Rest_run-01_eeg.fdt
    sub-XXX/eeg/sub-XXX_task-Rest_run-01_events.tsv

The recording contains alternating 1-minute blocks of eyes-open and
eyes-closed resting state. Event markers in events.tsv indicate block
boundaries ("Eyes Open: Every 500 ms", "Eyes Closed: Every 500 ms",
"Start and Finish").

Healthy controls are filtered by BDI <= 13 (minimal depression).
sub-038 is excluded (invalid participant, all NaN in demographics).

Channel names are UPPERCASE in the raw data (FP1, FPZ, CZ, etc.) and
must be normalized to standard MNE case (Fp1, Fpz, Cz, etc.).

Reference: Cavanagh et al. (2019). University of Arizona.
OpenNeuro: ds003478
"""

from __future__ import annotations

import csv
import logging
import math
from collections.abc import Iterator
from pathlib import Path
import mne

try:
    from open_normative.channels import pick_standard_channels
except ImportError:
    from open_normative.channels import pick_standard_19 as pick_standard_channels
from open_normative.datasets.base import DatasetLoader, SubjectRecord

logger = logging.getLogger(__name__)

_DOWNLOAD_INSTRUCTIONS = """
Depression EEG dataset can be downloaded from OpenNeuro.

    python scripts/depress_download.py ~/Data/EEG/Depression

Or manually:
    aws s3 sync s3://openneuro.org/ds003478 ~/Data/EEG/Depression/ \\
        --no-sign-request --exclude '*' --include '*_run-01_*' \\
        --include 'participants.tsv'

Citation: Cavanagh et al. (2019). University of Arizona Depression EEG.
"""

# Subjects to exclude regardless of BDI (invalid data)
_EXCLUDED_SUBJECTS = {"sub-038"}

# Maximum BDI score for healthy control classification
_MAX_BDI_HEALTHY = 13

# Channel name capitalization fixes: UPPERCASE -> standard MNE case.
# Standard 10-20 and 10-10 names that appear uppercase in this dataset.
_DEPRESS_CAP_FIXES = {
    "FP1": "Fp1", "FP2": "Fp2", "FPZ": "Fpz",
    "AF3": "AF3", "AF4": "AF4", "AF7": "AF7", "AF8": "AF8",
    "AFZ": "AFz",
    "F1": "F1", "F2": "F2", "F3": "F3", "F4": "F4",
    "F5": "F5", "F6": "F6", "F7": "F7", "F8": "F8", "FZ": "Fz",
    "FC1": "FC1", "FC2": "FC2", "FC3": "FC3", "FC4": "FC4",
    "FC5": "FC5", "FC6": "FC6", "FCZ": "FCz",
    "FT7": "FT7", "FT8": "FT8",
    "C1": "C1", "C2": "C2", "C3": "C3", "C4": "C4",
    "C5": "C5", "C6": "C6", "CZ": "Cz",
    "T7": "T7", "T8": "T8",
    "CP1": "CP1", "CP2": "CP2", "CP3": "CP3", "CP4": "CP4",
    "CP5": "CP5", "CP6": "CP6", "CPZ": "CPz",
    "TP7": "TP7", "TP8": "TP8",
    "P1": "P1", "P2": "P2", "P3": "P3", "P4": "P4",
    "P5": "P5", "P6": "P6", "P7": "P7", "P8": "P8", "PZ": "Pz",
    "PO3": "PO3", "PO4": "PO4", "PO7": "PO7", "PO8": "PO8",
    "POZ": "POz",
    "O1": "O1", "O2": "O2", "OZ": "Oz",
    # EOG channels (will be dropped, but normalize anyway)
    "HEOG": "HEOG", "VEOG": "VEOG",
}


def _normalize_depress_channels(raw: mne.io.Raw) -> mne.io.Raw:
    """Normalize uppercase channel names to standard MNE case.

    Applies the dataset-specific capitalization fixes, then falls through
    to the global name_mapping for 10-10 -> 10-20 renaming (T7->T3, etc.).
    """
    rename_map = {}
    for ch in raw.ch_names:
        fixed = _DEPRESS_CAP_FIXES.get(ch, ch)
        if fixed != ch:
            rename_map[ch] = fixed
    if rename_map:
        raw.rename_channels(rename_map)
    return raw


def parse_events_tsv(events_path: Path) -> list[dict]:
    """Parse a BIDS events.tsv file.

    Returns list of {onset: float, duration: float, trial_type: str}.
    """
    events = []
    if not events_path.exists():
        return events
    try:
        with events_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                try:
                    onset = float(row.get("onset", "nan"))
                    duration = float(row.get("duration", "0") or "0")
                except (ValueError, TypeError):
                    continue
                trial_type = row.get(
                    "trial_type",
                    row.get("value", row.get("description", ""))
                ).strip()
                events.append({
                    "onset": onset,
                    "duration": duration,
                    "trial_type": trial_type,
                })
    except Exception:
        logger.warning("Failed to parse events.tsv: %s", events_path, exc_info=True)
    return events


def _find_events_tsv(set_path: Path) -> Path:
    """Find the BIDS events.tsv companion for a .set file."""
    stem = set_path.name
    for suffix in ("_eeg.set", ".set"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return set_path.parent / f"{stem}_events.tsv"


def segment_eo_ec(events: list[dict], raw_duration: float) -> dict[str, list[tuple[float, float]]]:
    """Parse event markers to identify EO and EC block boundaries.

    The Depression dataset uses alternating 1-minute blocks of eyes-open
    and eyes-closed. Events contain markers like:
        "Eyes Open: Every 500 ms"
        "Eyes Closed: Every 500 ms"
        "Start and Finish"

    Returns dict with 'eo' and 'ec' keys, each mapping to a list of
    (tmin, tmax) tuples in seconds.
    """
    segments: dict[str, list[tuple[float, float]]] = {"eo": [], "ec": []}

    if not events:
        return segments

    # Find condition-change events
    condition_events = []
    for ev in events:
        tt = ev["trial_type"].lower()
        if "eyes open" in tt:
            condition_events.append((ev["onset"], "eo"))
        elif "eyes closed" in tt:
            condition_events.append((ev["onset"], "ec"))
        elif "start and finish" in tt or "start" in tt.split():
            # "Start and Finish" marks recording boundaries
            condition_events.append((ev["onset"], "boundary"))

    if not condition_events:
        logger.warning("No EO/EC events found in events.tsv")
        return segments

    # Sort by onset time
    condition_events.sort(key=lambda x: x[0])

    # Build segments: each condition runs until the next condition change
    for i, (onset, cond) in enumerate(condition_events):
        if cond == "boundary":
            continue

        # Find end: next event onset, or recording end
        if i + 1 < len(condition_events):
            end = condition_events[i + 1][0]
        else:
            end = raw_duration

        # Sanity check: segment should be at least 5 seconds
        if end - onset >= 5.0:
            segments[cond].append((onset, end))

    return segments


def split_raw_by_events(raw: mne.io.Raw, set_path: Path, condition: str) -> mne.io.Raw:
    """Split a raw recording into EO or EC segments using events.tsv.

    Concatenates all segments of the requested condition into a single Raw.
    Raises ValueError if no segments found for the condition.

    Parameters
    ----------
    raw : mne.io.Raw
        The loaded raw recording (preloaded).
    set_path : Path
        Path to the .set file (used to find companion events.tsv).
    condition : str
        "eo" or "ec".

    Returns
    -------
    mne.io.Raw
        Concatenated raw segments for the requested condition.
    """
    events_path = _find_events_tsv(set_path)
    events = parse_events_tsv(events_path)
    segments = segment_eo_ec(events, raw.times[-1])

    if not segments.get(condition):
        raise ValueError(
            f"No {condition} segments found in {events_path}. "
            f"Events: {[e['trial_type'] for e in events[:10]]}"
        )

    # Crop and concatenate segments
    raws = []
    for tmin, tmax in segments[condition]:
        # Clamp to recording bounds
        tmin = max(tmin, raw.times[0])
        tmax = min(tmax, raw.times[-1])
        if tmax - tmin < 5.0:
            continue
        segment = raw.copy().crop(tmin=tmin, tmax=tmax)
        raws.append(segment)

    if not raws:
        raise ValueError(
            f"All {condition} segments too short in {set_path}"
        )

    if len(raws) == 1:
        return raws[0]

    return mne.concatenate_raws(raws)


class DepressLoader(DatasetLoader):
    """Loader for the Depression EEG dataset.

    Recorded in USA (University of Arizona) — line noise is 60 Hz.
    Contains both eyes-open and eyes-closed resting state, alternating
    in 1-minute blocks within a single run.

    Healthy controls: BDI <= 13, excluding sub-038.
    """

    line_freq: float = 60.0

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each healthy control, EO and EC separately."""
        participants = self._load_participants(data_dir)

        set_files = sorted(data_dir.glob(
            "sub-*/eeg/*_task-Rest_run-01_eeg.set"
        ))

        if not set_files:
            logger.warning(
                "No .set files found in %s/sub-*/eeg/", data_dir
            )
            return

        logger.info("Found %d .set files for run-01", len(set_files))

        for set_path in set_files:
            subject_id = None
            for part in set_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                logger.warning("Could not extract subject ID from %s", set_path)
                continue

            # Only healthy controls
            if subject_id not in participants:
                logger.debug("Skipping %s — not a healthy control", subject_id)
                continue

            info = participants[subject_id]
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            if math.isnan(age):
                logger.warning("No age for %s — will be NaN", subject_id)

            # Load the recording
            try:
                raw = mne.io.read_raw_eeglab(str(set_path), preload=True, verbose=False)
            except Exception:
                logger.warning("Failed to load %s", set_path, exc_info=True)
                continue

            # Normalize channel names and drop EOG
            raw = _normalize_depress_channels(raw)
            eog_channels = [ch for ch in raw.ch_names
                            if ch.upper() in ("HEOG", "VEOG", "EOG")]
            if eog_channels:
                raw.drop_channels(eog_channels)
            raw.pick("eeg")

            # Segment into EO and EC conditions
            for condition in ("eo", "ec"):
                try:
                    cond_raw = split_raw_by_events(raw, set_path, condition)
                    cond_raw = pick_standard_channels(cond_raw)
                except Exception:
                    logger.warning(
                        "Failed to extract %s for %s",
                        condition, subject_id, exc_info=True,
                    )
                    continue

                metadata = {"source_file": str(set_path), **info}

                yield SubjectRecord(
                    subject_id=subject_id,
                    age=age,
                    sex=sex,
                    raw=cond_raw,
                    condition=condition,
                    metadata=metadata,
                )

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Parse participants.tsv, filter to healthy controls.

        Healthy control criteria:
        - BDI <= 13 (minimal depression)
        - Not in _EXCLUDED_SUBJECTS (sub-038 = invalid, all NaN)
        - Valid age and sex data

        Sex coding: 1 = Female, 2 = Male.

        Returns dict keyed by subject_id with age, sex, bdi, etc.
        """
        tsv_path = data_dir / "participants.tsv"
        if not tsv_path.exists():
            logger.warning("No participants.tsv found in %s", data_dir)
            return {}

        all_participants: dict[str, dict] = {}
        healthy: dict[str, dict] = {}
        n_excluded_bdi = 0
        n_excluded_invalid = 0

        with tsv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                sid = row.get("participant_id", "").strip()
                if not sid:
                    continue

                # Age
                raw_age = row.get("age", "").strip()
                try:
                    age = float(raw_age)
                except (ValueError, TypeError):
                    age = float("nan")

                # Sex: 1 = Female, 2 = Male
                raw_sex = row.get("sex", "").strip()
                try:
                    sex_code = int(raw_sex)
                    if sex_code == 1:
                        sex = "F"
                    elif sex_code == 2:
                        sex = "M"
                    else:
                        sex = ""
                except (ValueError, TypeError):
                    sex = ""

                # BDI score
                raw_bdi = row.get("BDI", "").strip()
                try:
                    bdi = float(raw_bdi)
                except (ValueError, TypeError):
                    bdi = float("nan")

                # Additional clinical measures (metadata only)
                info = {
                    "age": age,
                    "sex": sex,
                    "bdi": bdi,
                }
                for field in ("STAI", "SCID", "HamD"):
                    raw_val = row.get(field, "").strip()
                    try:
                        info[field.lower()] = float(raw_val)
                    except (ValueError, TypeError):
                        info[field.lower()] = raw_val

                all_participants[sid] = info

                # Filter: excluded subjects
                if sid in _EXCLUDED_SUBJECTS:
                    n_excluded_invalid += 1
                    continue

                # Filter: BDI threshold
                if math.isnan(bdi) or bdi > _MAX_BDI_HEALTHY:
                    n_excluded_bdi += 1
                    continue

                healthy[sid] = info

        logger.info(
            "Loaded %d total participants, %d healthy controls "
            "(excluded: %d BDI>%d, %d invalid)",
            len(all_participants), len(healthy),
            n_excluded_bdi, _MAX_BDI_HEALTHY, n_excluded_invalid,
        )
        return healthy
