"""LEMON dataset loader.

The LEMON (Leipzig Study for Mind-Body-Emotion Interactions) dataset is a
publicly available EEG dataset with resting-state recordings in Eyes Open
(EO) and Eyes Closed (EC) conditions.

Reference: Babayan et al. (2019). A mind-brain-body dataset of MRI, EEG,
and cognition from 227 healthy subjects. Scientific Data, 6, 180308.
https://doi.org/10.1038/sdata.2018.308

Download from: https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON/
"""

from __future__ import annotations

import csv
import logging
import tempfile
from collections.abc import Iterator
from pathlib import Path

import mne
import numpy as np

from open_normative.channels import pick_standard_19
from open_normative.datasets.base import DatasetLoader, SubjectRecord

logger = logging.getLogger(__name__)

_DOWNLOAD_INSTRUCTIONS = """
LEMON dataset must be downloaded manually.

1. Visit: https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Brain-Body-LEMON/
2. Download the EEG raw data from EEG_MPILMBB_LEMON/EEG_Raw_BIDS_ID/
3. Download the demographics file from Behavioural_Data_MPILMBB_LEMON/:
   META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv
4. Place the META CSV at the root of the data directory alongside the
   sub-*/ folders.

See: https://doi.org/10.1038/sdata.2018.308 for full documentation.
"""

# The META CSV shipped with the GWDG LEMON download.
_META_CSV_NAME = "META_File_IDs_Age_Gender_Education_Drug_Smoke_SKID_LEMON.csv"


class LEMONLoader(DatasetLoader):
    """Loader for the LEMON resting-state EEG dataset.

    Supports two demographics file formats:
    - The META CSV shipped with the GWDG download (auto-detected)
    - A BIDS-style participants.tsv (e.g. from OpenNeuro ds000221)
    """

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each EO/EC file in the LEMON dataset.

        Handles two LEMON data layouts:
        1. **Separate files** — filenames contain EO/EC (e.g.
           ``sub-010002_task-rest_EO_eeg.vhdr``).  One SubjectRecord per file.
        2. **Single file** — one ``.vhdr`` per subject with S210 (EO) and
           S200 (EC) markers inside.  The recording is split by markers and
           one SubjectRecord is yielded per condition found.

        Parameters
        ----------
        data_dir:
            Root directory containing sub-*/ folders and either the META CSV
            or a participants.tsv file.
        """
        participants = self._load_participants(data_dir)

        # Support both BIDS-like "eeg/" and the raw LEMON download's "RSEEG/" layout
        vhdr_files = sorted(
            set(data_dir.glob("sub-*/eeg/*.vhdr")) | set(data_dir.glob("sub-*/RSEEG/*.vhdr"))
        )

        if not vhdr_files:
            logger.warning("No .vhdr files found in %s/sub-*/{eeg,RSEEG}/", data_dir)
            return

        logger.info("Found %d .vhdr files", len(vhdr_files))

        for vhdr_path in vhdr_files:
            subject_id = vhdr_path.parts[-3]  # sub-XXXXXXX (directory name)

            # The BIDS download may remap subject IDs (e.g. sub-032301 dirs
            # contain files originally named sub-010002).  Extract the original
            # ID from the .vhdr's internal DataFile reference so we can match
            # against the demographics files which use original IDs.
            original_id = _extract_original_id(vhdr_path)
            info = participants.get(subject_id, {})
            if not info and original_id and original_id != subject_id:
                info = participants.get(original_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            # Try to detect condition from filename
            condition = self._detect_condition(vhdr_path.name)

            try:
                load_path = _fix_vhdr_refs(vhdr_path)
                raw = mne.io.read_raw_brainvision(str(load_path), preload=True, verbose=False)
            except Exception:
                logger.warning("Failed to load %s", vhdr_path, exc_info=True)
                continue

            # Drop non-EEG channels, then standardize to the 19-channel montage
            raw.pick("eeg")
            try:
                raw = pick_standard_19(raw)
            except Exception:
                logger.warning(
                    "Channel standardization failed for %s — skipping", vhdr_path, exc_info=True
                )
                continue

            metadata = {"source_file": str(vhdr_path), **info}

            if condition is not None:
                # Filename tells us the condition — yield as-is
                yield SubjectRecord(
                    subject_id=subject_id, age=age, sex=sex,
                    raw=raw, condition=condition, metadata=metadata,
                )
            else:
                # Single-file recording — split by S210/S200 markers
                splits = _split_by_markers(raw)
                if not splits:
                    logger.warning(
                        "No EO/EC markers (S210/S200) found in %s — skipping", vhdr_path
                    )
                    continue
                for cond, cond_raw in splits.items():
                    yield SubjectRecord(
                        subject_id=subject_id, age=age, sex=sex,
                        raw=cond_raw, condition=cond, metadata=metadata,
                    )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Load participant demographics from all available files.

        Loads the META CSV and participants.tsv/txt and merges them so that
        both original IDs (sub-010002) and BIDS-remapped IDs (sub-032301)
        are covered.  The META CSV takes priority when both have the same key.
        """
        participants: dict[str, dict] = {}

        # Load participants.tsv or .txt first (lower priority)
        for ext in ("participants.tsv", "participants.txt"):
            tsv_path = data_dir / ext
            if tsv_path.exists():
                participants.update(LEMONLoader._load_participants_tsv(tsv_path))
                break

        # Load META CSV (higher priority — overwrites tsv entries for same ID)
        for meta_path in (data_dir / _META_CSV_NAME, data_dir.parent / _META_CSV_NAME):
            if meta_path.exists():
                participants.update(LEMONLoader._load_meta_csv(meta_path))
                break

        if not participants:
            logger.warning(
                "No demographics file found in %s. "
                "Subjects will have age=NaN and won't be assigned to age bins.",
                data_dir,
            )
        return participants

    @staticmethod
    def _load_meta_csv(meta_path: Path) -> dict[str, dict]:
        """Parse the LEMON META CSV file.

        Columns:
          ID                             — subject ID (e.g. "sub-010017")
          Gender_ 1=female_2=male        — 1=female, 2=male
          Age                            — 5-year range (e.g. "20-25")
        """
        logger.info("Loading demographics from %s", meta_path)
        participants: dict[str, dict] = {}
        with meta_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                subject_id = row.get("ID", "").strip()
                if not subject_id:
                    continue

                raw_age = row.get("Age", "")
                age = _parse_age(raw_age)

                # Gender: 1=female, 2=male
                raw_gender = row.get("Gender_ 1=female_2=male", "").strip()
                if raw_gender == "1":
                    sex = "F"
                elif raw_gender == "2":
                    sex = "M"
                else:
                    sex = raw_gender

                participants[subject_id] = {
                    "age": age,
                    "sex": sex,
                }

        logger.info("Loaded demographics for %d subjects", len(participants))
        return participants

    @staticmethod
    def _load_participants_tsv(tsv_path: Path) -> dict[str, dict]:
        """Parse a BIDS-style participants.tsv.

        Handles both standard BIDS columns and the OpenNeuro ds000221
        variant which uses 'age (5-year bins)' and 'gender' columns.
        """
        logger.info("Loading demographics from %s", tsv_path)
        participants: dict[str, dict] = {}
        with tsv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                subject_id = row.get("participant_id", "").strip()
                if not subject_id:
                    continue

                # Age: try 'age', then 'age (5-year bins)' (OpenNeuro ds000221)
                raw_age = row.get("age", "")
                if not raw_age:
                    for key in row:
                        if key.lower().startswith("age"):
                            raw_age = row[key]
                            break
                age = _parse_age(raw_age)

                # Sex: try 'sex', then 'gender'
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
                       if k not in ("participant_id", "age", "sex", "gender")
                       and not k.lower().startswith("age")},
                }

        logger.info("Loaded demographics for %d subjects", len(participants))
        return participants

    @staticmethod
    def _detect_condition(filename: str) -> str | None:
        """Return 'ec' or 'eo' based on filename, or None if undetectable."""
        upper = filename.upper()
        if "EC" in upper:
            return "ec"
        if "EO" in upper:
            return "eo"
        return None


def _extract_original_id(vhdr_path: Path) -> str | None:
    """Extract the original subject ID from a .vhdr's internal DataFile reference.

    In the LEMON BIDS download the directories are renamed (e.g. sub-032301)
    but the internal DataFile still references the original filename
    (e.g. sub-010002.eeg).  Returns the stem of that reference, or None.
    """
    try:
        for line in vhdr_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DataFile="):
                ref = line.split("=", 1)[1].strip()
                return Path(ref).stem
    except Exception:
        pass
    return None


def _fix_vhdr_refs(vhdr_path: Path) -> Path:
    """Fix mismatched internal file references in a BrainVision .vhdr file.

    The LEMON BIDS download renames the .vhdr file (e.g. sub-010002 → sub-032301)
    but the .vmrk and .eeg files keep their original names, AND the .vhdr header
    still references the original filenames.  When the referenced files don't
    exist at the expected path, this function searches for the actual .vmrk and
    .eeg files in the same directory and writes a patched .vhdr copy.
    """
    parent = vhdr_path.parent
    text = vhdr_path.read_text(encoding="utf-8")

    # Check which references are broken
    ref_keys = {"DataFile": None, "MarkerFile": None}
    needs_patch = False
    for line in text.splitlines():
        for key in ref_keys:
            prefix = f"{key}="
            if line.startswith(prefix):
                ref_name = line[len(prefix):].strip()
                ref_keys[key] = ref_name
                if not (parent / ref_name).exists():
                    needs_patch = True

    if not needs_patch:
        return vhdr_path

    # Find the actual files in the directory by extension
    def _find_file(ext: str) -> str | None:
        candidates = list(parent.glob(f"*{ext}"))
        # Exclude our own patched files
        candidates = [c for c in candidates if not c.name.startswith(".")]
        if len(candidates) == 1:
            return candidates[0].name
        # Multiple candidates — try to match by the stem referenced in .vhdr
        if ref_keys.get("DataFile" if ext == ".eeg" else "MarkerFile"):
            old_stem = Path(ref_keys["DataFile" if ext == ".eeg" else "MarkerFile"]).stem
            for c in candidates:
                if c.stem == old_stem:
                    return c.name
        return None

    patched_lines = []
    for line in text.splitlines():
        if line.startswith("DataFile="):
            actual = _find_file(".eeg")
            if actual and not (parent / line.split("=", 1)[1].strip()).exists():
                patched_lines.append(f"DataFile={actual}")
                logger.debug("  DataFile: %s → %s", line.split("=", 1)[1].strip(), actual)
            else:
                patched_lines.append(line)
        elif line.startswith("MarkerFile="):
            actual = _find_file(".vmrk")
            if actual and not (parent / line.split("=", 1)[1].strip()).exists():
                patched_lines.append(f"MarkerFile={actual}")
                logger.debug("  MarkerFile: %s → %s", line.split("=", 1)[1].strip(), actual)
            else:
                patched_lines.append(line)
        else:
            patched_lines.append(line)

    patched_path = parent / f".{vhdr_path.stem}_patched.vhdr"
    patched_path.write_text("\n".join(patched_lines), encoding="utf-8")
    logger.debug("Patched .vhdr references: %s → %s", vhdr_path.name, patched_path.name)
    return patched_path


# LEMON stimulus markers for resting-state conditions
_EO_MARKER = "Stimulus/S210"
_EC_MARKER = "Stimulus/S200"


def _split_by_markers(raw: mne.io.BaseRaw) -> dict[str, mne.io.BaseRaw]:
    """Split a single LEMON recording into EO/EC using S210 and S200 markers.

    The GWDG LEMON download stores both conditions in one continuous file.
    Markers ``S210`` denote Eyes-Open epochs and ``S200`` denote Eyes-Closed
    epochs, each spaced at regular intervals (typically every 2 s at 2500 Hz).

    This function groups consecutive same-type markers into contiguous blocks,
    crops each block from the raw recording, and concatenates them per
    condition.

    Returns
    -------
    dict
        ``{"eo": Raw, "ec": Raw}`` for each condition that has markers.
        Conditions with no markers are omitted.
    """
    marker_map = {_EO_MARKER: "eo", _EC_MARKER: "ec"}

    # Collect onset times per condition
    onsets: dict[str, list[float]] = {"eo": [], "ec": []}
    for ann in raw.annotations:
        desc = ann["description"].strip()
        cond = marker_map.get(desc)
        if cond:
            onsets[cond].append(ann["onset"])

    results: dict[str, mne.io.BaseRaw] = {}
    for cond in ("eo", "ec"):
        if len(onsets[cond]) < 2:
            continue

        sorted_onsets = sorted(onsets[cond])

        # Compute epoch duration from median inter-marker interval
        intervals = np.diff(sorted_onsets)
        epoch_dur = float(np.median(intervals))

        # Group consecutive markers into contiguous blocks.
        # A gap > 2.5× the epoch duration signals a new block.
        blocks: list[tuple[float, float]] = []
        block_start = sorted_onsets[0]
        prev = sorted_onsets[0]
        for onset in sorted_onsets[1:]:
            if onset - prev > epoch_dur * 2.5:
                blocks.append((block_start, prev + epoch_dur))
                block_start = onset
            prev = onset
        blocks.append((block_start, prev + epoch_dur))

        # Crop each block and concatenate
        max_time = raw.times[-1] + raw.first_time
        segments = []
        for bstart, bend in blocks:
            bend = min(bend, max_time)
            if bend <= bstart:
                continue
            try:
                segments.append(raw.copy().crop(tmin=bstart, tmax=bend))
            except ValueError:
                logger.debug("Could not crop block [%.1f, %.1f] from %s", bstart, bend, cond)
                continue

        if segments:
            results[cond] = mne.concatenate_raws(segments)
            logger.info(
                "  %s: %d blocks, %.1f s total",
                cond.upper(), len(segments), results[cond].times[-1],
            )

    return results


def _parse_age(raw: str) -> float:
    """Convert an age string to a float.

    Accepts numeric strings ("25") or range strings ("20-25", "20_25").
    Returns the midpoint for ranges, or float('nan') if unparseable.
    """
    raw = raw.strip()
    if not raw:
        return float("nan")

    # Try a plain number first
    try:
        return float(raw)
    except ValueError:
        pass

    # Try a range separated by "-" or "_"
    for sep in ("-", "_"):
        if sep in raw:
            parts = raw.split(sep, 1)
            try:
                lo, hi = float(parts[0]), float(parts[1])
                return (lo + hi) / 2.0
            except ValueError:
                pass

    logger.debug("Could not parse age value: %r", raw)
    return float("nan")
