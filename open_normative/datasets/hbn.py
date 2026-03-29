"""HBN (Healthy Brain Network) dataset loader.

The Healthy Brain Network is a large-scale pediatric mental health study
with resting-state EEG recordings using 128-channel EGI HydroCel
Geodesic Sensor Nets.

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
3. Download the EEG resting-state data and organize into BIDS-like layout:
   hbn/
     participants.tsv          # participant_id, age, sex
     sub-NDARXXXX/eeg/
       sub-NDARXXXX_task-restEO_eeg.mff/
       sub-NDARXXXX_task-restEC_eeg.mff/

See: https://doi.org/10.1038/sdata.2017.181 for full documentation.
"""


class HBNLoader(DatasetLoader):
    """Loader for the Healthy Brain Network EEG dataset.

    Expects a BIDS-like directory layout with 128-channel EGI .mff files
    and a participants.tsv with subject demographics.
    """

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each EO/EC file in the HBN dataset.

        Parameters
        ----------
        data_dir:
            Root of the dataset (contains participants.tsv and sub-*/).
        """
        participants = self._load_participants(data_dir)

        # Look for .mff directories and .raw files
        eeg_paths = sorted(
            list(data_dir.glob("sub-*/eeg/*.mff"))
            + list(data_dir.glob("sub-*/eeg/*.raw"))
        )

        for eeg_path in eeg_paths:
            subject_id = eeg_path.parts[-3]  # sub-NDARXXXX
            condition = self._detect_condition(eeg_path.name)
            if condition is None:
                logger.debug("Skipping %s: could not detect EO/EC condition", eeg_path)
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            try:
                raw = mne.io.read_raw_egi(str(eeg_path), preload=True, verbose=False)
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

            yield SubjectRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                raw=raw,
                condition=condition,
                metadata={
                    "source_file": str(eeg_path),
                    "dataset": "hbn",
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
        """Return 'ec' or 'eo' based on filename, or None if undetectable."""
        upper = filename.upper()
        if "EC" in upper:
            return "ec"
        if "EO" in upper:
            return "eo"
        # HBN may use "REST" without EO/EC distinction
        if "REST" in upper:
            return "eo"  # Default resting to eyes-open
        return None
