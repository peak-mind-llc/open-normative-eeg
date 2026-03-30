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
from collections.abc import Iterator
from pathlib import Path

import mne

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
        for vhdr_path in vhdr_files:
            subject_id = vhdr_path.parts[-3]  # sub-XXXXXXX
            condition = self._detect_condition(vhdr_path.name)
            if condition is None:
                logger.debug("Skipping %s: could not detect EO/EC condition", vhdr_path)
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            try:
                raw = mne.io.read_raw_brainvision(str(vhdr_path), preload=True, verbose=False)
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

            yield SubjectRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                raw=raw,
                condition=condition,
                metadata={
                    "source_file": str(vhdr_path),
                    **info,
                },
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Load participant demographics from the META CSV or participants.tsv.

        Tries the LEMON META CSV first (the file shipped with the GWDG
        download), then falls back to BIDS-style participants.tsv.
        """
        # Try the META CSV first (shipped with GWDG LEMON download)
        meta_path = data_dir / _META_CSV_NAME
        if meta_path.exists():
            return LEMONLoader._load_meta_csv(meta_path)

        # Also check parent directory (META CSV might be one level up)
        parent_meta = data_dir.parent / _META_CSV_NAME
        if parent_meta.exists():
            return LEMONLoader._load_meta_csv(parent_meta)

        # Fall back to BIDS participants.tsv or .txt
        for ext in ("participants.tsv", "participants.txt"):
            tsv_path = data_dir / ext
            if tsv_path.exists():
                return LEMONLoader._load_participants_tsv(tsv_path)

        logger.warning(
            "No demographics file found. Looked for:\n"
            "  %s\n"
            "  %s (or .txt)\n"
            "Subjects will have age=NaN and won't be assigned to age bins.",
            meta_path,
            data_dir / "participants.tsv",
        )
        return {}

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
