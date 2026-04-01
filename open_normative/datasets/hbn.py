"""HBN (Healthy Brain Network) dataset loader.

The Healthy Brain Network is a large-scale pediatric mental health study
with resting-state EEG recordings using 128-channel EGI HydroCel
Geodesic Sensor Nets.

The BIDS-formatted data on S3 uses EEGLAB .set files.  Resting state is
stored as a single ``sub-*_task-RestingState_eeg.set`` file per subject
with alternating Eyes-Open (5x20s) and Eyes-Closed (5x40s) blocks.
Block boundaries are described in a companion ``_events.tsv``.

Reference: Alexander et al. (2017). An open resource for transdiagnostic
research in pediatric mental health and learning disorders. Scientific
Data, 4, 170181.
https://doi.org/10.1038/sdata.2017.181

Download from: http://fcon_1000.projects.nitrc.org/indi/cmi_healthy_brain_network/
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterator
from pathlib import Path

import mne

from open_normative.channels import pick_standard_19, set_egi128_montage
from open_normative.datasets.base import DatasetLoader, SubjectRecord

logger = logging.getLogger(__name__)

_DOWNLOAD_INSTRUCTIONS = """
HBN dataset requires a data usage agreement.

1. Visit: http://fcon_1000.projects.nitrc.org/indi/cmi_healthy_brain_network/
2. Register for data access through the LORIS portal.
3. Download the EEG resting-state data from the S3 BIDS archive.
   The BIDS layout uses EEGLAB .set files:

   hbn/
     participants.tsv                           # participant_id, age, sex
     sub-NDARXXXX/
       eeg/
         sub-NDARXXXX_task-RestingState_eeg.set
         sub-NDARXXXX_task-RestingState_events.tsv

   Each RestingState file contains alternating EO and EC blocks
   (~5x20s EO + 5x40s EC). The events.tsv describes block boundaries.

See: https://doi.org/10.1038/sdata.2017.181 for full documentation.
"""


class HBNLoader(DatasetLoader):
    """Loader for the Healthy Brain Network EEG dataset.

    Expects a BIDS-like directory layout with 128-channel EGI recordings
    and a participants.tsv with subject demographics.

    Supports three file formats:
    - ``.set`` (EEGLAB) — the primary format in the S3 BIDS archive
    - ``.mff`` (EGI native) — legacy/alternative layout
    - ``.raw`` (EGI raw) — legacy/alternative layout
    """

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each EO/EC recording in the HBN dataset.

        For ``.set`` RestingState files the recording is split into separate
        EO and EC segments (two SubjectRecords per file).  For legacy
        ``.mff``/``.raw`` files with explicit EO/EC in the filename, one
        SubjectRecord is yielded per file.

        Parameters
        ----------
        data_dir:
            Root of the dataset (contains participants.tsv and sub-*/).
        """
        participants = self._load_participants(data_dir)

        # Collect all EEG files across supported formats
        eeg_paths = sorted(
            set(data_dir.glob("sub-*/eeg/*.set"))
            | set(data_dir.glob("sub-*/eeg/*.mff"))
            | set(data_dir.glob("sub-*/eeg/*.raw"))
        )

        if not eeg_paths:
            logger.warning(
                "No EEG files (.set, .mff, .raw) found in %s/sub-*/eeg/",
                data_dir,
            )
            return

        logger.info("Found %d EEG files", len(eeg_paths))

        for eeg_path in eeg_paths:
            subject_id = eeg_path.parts[-3]  # sub-NDARXXXX
            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            # Load the raw recording
            try:
                raw = self._load_raw(eeg_path)
            except Exception:
                logger.warning("Failed to load %s", eeg_path, exc_info=True)
                continue

            # Pick EEG channels only
            raw.pick("eeg")

            # Set EGI montage for spatial nearest-neighbor mapping
            set_egi128_montage(raw)

            try:
                raw = pick_standard_19(raw)
            except Exception:
                logger.warning(
                    "Channel standardization failed for %s — skipping",
                    eeg_path,
                    exc_info=True,
                )
                continue

            metadata = {
                "source_file": str(eeg_path),
                "dataset": "hbn",
                **info,
            }

            # Determine how to yield: split or single condition
            condition = self._detect_condition(eeg_path.name)

            if condition is None:
                # RestingState file — split into EO and EC segments
                events_tsv = eeg_path.with_name(
                    eeg_path.name.replace("_eeg.set", "_events.tsv")
                )
                splits = _split_resting_state(raw, events_tsv)

                if not splits:
                    logger.warning(
                        "Could not split EO/EC for %s — yielding as 'eo'",
                        eeg_path,
                    )
                    yield SubjectRecord(
                        subject_id=subject_id,
                        age=age,
                        sex=sex,
                        raw=raw,
                        condition="eo",
                        metadata=metadata,
                    )
                    continue

                for cond, cond_raw in splits.items():
                    yield SubjectRecord(
                        subject_id=subject_id,
                        age=age,
                        sex=sex,
                        raw=cond_raw,
                        condition=cond,
                        metadata=metadata,
                    )
            else:
                # Filename explicitly indicates EO or EC
                yield SubjectRecord(
                    subject_id=subject_id,
                    age=age,
                    sex=sex,
                    raw=raw,
                    condition=condition,
                    metadata=metadata,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_raw(eeg_path: Path) -> mne.io.BaseRaw:
        """Load a raw EEG file, choosing the reader based on extension."""
        suffix = eeg_path.suffix.lower()
        if suffix == ".set":
            return mne.io.read_raw_eeglab(str(eeg_path), preload=True, verbose=False)
        elif suffix == ".mff":
            return mne.io.read_raw_egi(str(eeg_path), preload=True, verbose=False)
        elif suffix == ".raw":
            return mne.io.read_raw_egi(str(eeg_path), preload=True, verbose=False)
        else:
            raise ValueError(f"Unsupported EEG file format: {suffix}")

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Parse participants.tsv and return a dict keyed by subject ID."""
        tsv_path = data_dir / "participants.tsv"
        if not tsv_path.exists():
            logger.warning("participants.tsv not found at %s", tsv_path)
            return {}

        participants: dict[str, dict] = {}
        with tsv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                subject_id = row.get("participant_id", "").strip()
                if not subject_id:
                    continue

                raw_age = row.get("age", "").strip()
                try:
                    age = float(raw_age)
                except (ValueError, TypeError):
                    age = float("nan")

                raw_sex = row.get("sex", row.get("gender", "")).strip().upper()
                if raw_sex.startswith("M"):
                    sex = "M"
                elif raw_sex.startswith("F"):
                    sex = "F"
                else:
                    sex = raw_sex

                participants[subject_id] = {
                    "age": age,
                    "sex": sex,
                    **{k: v for k, v in row.items()
                       if k not in ("participant_id", "age", "sex", "gender")},
                }

        return participants

    @staticmethod
    def _detect_condition(filename: str) -> str | None:
        """Return 'ec' or 'eo' based on filename, or None if ambiguous.

        Returns None for "RestingState" files (which contain both EO and EC
        and must be split), and a condition string for files with explicit
        EO/EC in the name (e.g. ``task-restEO``, ``task-restEC``).
        """
        upper = filename.upper()
        # RestingState files contain both conditions — signal "split needed"
        if "RESTINGSTATE" in upper or "RESTING_STATE" in upper:
            return None
        if "EC" in upper:
            return "ec"
        if "EO" in upper:
            return "eo"
        # Ambiguous "REST" without EO/EC — also needs splitting or default
        if "REST" in upper:
            return None
        return None


# ------------------------------------------------------------------
# Resting-state splitting helpers
# ------------------------------------------------------------------

def _split_resting_state(
    raw: mne.io.BaseRaw,
    events_tsv: Path,
) -> dict[str, mne.io.BaseRaw]:
    """Split a combined RestingState recording into EO and EC segments.

    Tries the following strategies in order:
    1. Parse the companion BIDS ``_events.tsv`` for block boundaries.
    2. Fall back to annotations embedded in the Raw object.

    Returns
    -------
    dict
        ``{"eo": Raw, "ec": Raw}`` for each condition found.
        Empty dict if splitting was not possible.
    """
    # Strategy 1: BIDS events.tsv
    if events_tsv.exists():
        result = _split_from_events_tsv(raw, events_tsv)
        if result:
            return result
        logger.debug(
            "events.tsv at %s did not yield usable EO/EC blocks; "
            "falling back to annotations",
            events_tsv,
        )

    # Strategy 2: Raw annotations
    result = _split_from_annotations(raw)
    if result:
        return result

    return {}


def _classify_trial_type(trial_type: str) -> str | None:
    """Map a trial_type string to 'eo' or 'ec', or None if unrecognized."""
    t = trial_type.strip().lower()
    # Eyes-open variants
    if "open" in t or t == "eo" or t == "eyes open" or t == "eyesopen":
        return "eo"
    # Eyes-closed variants
    if "closed" in t or "close" in t or t == "ec" or t == "eyes closed" or t == "eyesclosed":
        return "ec"
    return None


def _split_from_events_tsv(
    raw: mne.io.BaseRaw,
    events_tsv: Path,
) -> dict[str, mne.io.BaseRaw]:
    """Split using a BIDS events.tsv (onset, duration, trial_type columns).

    Returns
    -------
    dict
        ``{"eo": Raw, "ec": Raw}`` or empty dict on failure.
    """
    try:
        with events_tsv.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            rows = list(reader)
    except Exception:
        logger.warning("Could not read events.tsv at %s", events_tsv, exc_info=True)
        return {}

    if not rows:
        return {}

    # Require the three essential columns
    required = {"onset", "duration", "trial_type"}
    if not required.issubset(rows[0].keys()):
        logger.debug(
            "events.tsv missing required columns (has %s, need %s)",
            list(rows[0].keys()), required,
        )
        return {}

    # Classify each event row
    blocks: dict[str, list[tuple[float, float]]] = {"eo": [], "ec": []}
    for row in rows:
        cond = _classify_trial_type(str(row["trial_type"]))
        if cond is None:
            continue
        try:
            onset = float(row["onset"])
            duration = float(row["duration"])
        except (ValueError, TypeError):
            continue
        if duration > 0:
            blocks[cond].append((onset, onset + duration))

    return _crop_and_concat(raw, blocks)


def _split_from_annotations(
    raw: mne.io.BaseRaw,
) -> dict[str, mne.io.BaseRaw]:
    """Split using MNE annotations embedded in the Raw object.

    Returns
    -------
    dict
        ``{"eo": Raw, "ec": Raw}`` or empty dict on failure.
    """
    blocks: dict[str, list[tuple[float, float]]] = {"eo": [], "ec": []}

    for ann in raw.annotations:
        cond = _classify_trial_type(ann["description"])
        if cond is None:
            continue
        onset = float(ann["onset"])
        duration = float(ann["duration"])
        if duration > 0:
            blocks[cond].append((onset, onset + duration))

    return _crop_and_concat(raw, blocks)


def _crop_and_concat(
    raw: mne.io.BaseRaw,
    blocks: dict[str, list[tuple[float, float]]],
) -> dict[str, mne.io.BaseRaw]:
    """Crop and concatenate blocks for each condition.

    Parameters
    ----------
    raw:
        The full recording.
    blocks:
        ``{"eo": [(start, end), ...], "ec": [(start, end), ...]}``

    Returns
    -------
    dict
        ``{"eo": Raw, "ec": Raw}`` for conditions with valid segments.
    """
    max_time = raw.times[-1] + raw.first_time
    results: dict[str, mne.io.BaseRaw] = {}

    for cond in ("eo", "ec"):
        if not blocks[cond]:
            continue

        segments = []
        for bstart, bend in sorted(blocks[cond]):
            bend = min(bend, max_time)
            if bend <= bstart:
                continue
            try:
                segments.append(raw.copy().crop(tmin=bstart, tmax=bend))
            except ValueError:
                logger.debug(
                    "Could not crop block [%.1f, %.1f] for %s",
                    bstart, bend, cond,
                )
                continue

        if segments:
            results[cond] = mne.concatenate_raws(segments)
            logger.info(
                "  %s: %d blocks, %.1f s total",
                cond.upper(), len(segments), results[cond].times[-1],
            )

    return results
