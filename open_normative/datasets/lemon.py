"""LEMON dataset loader.

The LEMON (Leipzig Study for Mind-Body-Emotion Interactions) dataset is a
publicly available BIDS-formatted EEG dataset with resting-state recordings
in Eyes Open (EO) and Eyes Closed (EC) conditions.

Reference: Babayan et al. (2019). A mind-body dataset of MRI and EEG data
from 227 young healthy subjects. Scientific Data, 6, 180308.
https://doi.org/10.1038/sdata.2018.308

Download from: https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Body-Emotion/
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

1. Visit: https://ftp.gwdg.de/pub/misc/MPI-Leipzig_Mind-Body-Emotion/
2. Download the EEG BIDS archive and extract to your data directory.
3. The directory should contain:
   - participants.tsv
   - sub-*/eeg/*.vhdr files

See: https://doi.org/10.1038/sdata.2018.308 for full documentation.
"""


class LEMONLoader(DatasetLoader):
    """Loader for the LEMON resting-state EEG dataset (BIDS format)."""

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each EO/EC file in the LEMON dataset.

        Parameters
        ----------
        data_dir:
            Root of the BIDS dataset (contains participants.tsv and sub-*/).
        """
        participants = self._load_participants(data_dir)

        for vhdr_path in sorted(data_dir.glob("sub-*/eeg/*.vhdr")):
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

                # Age may be stored as a range (e.g. "20-25") or a number
                raw_age = row.get("age", "")
                age = _parse_age(raw_age)

                # Sex: "M" / "F" or "male" / "female"
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
                    **{k: v for k, v in row.items() if k not in ("participant_id", "age", "sex", "gender")},
                }

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
