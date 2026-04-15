"""SRM (Stavanger/Reading/Magdeburg) Resting-state EEG dataset loader.

111 healthy adults ages 17-71, 64-channel BioSemi ActiveTwo (10-10),
eyes-closed resting state (4 minutes), 1024 Hz, EDF format. CC0 license.

Data layout (BIDS on OpenNeuro ds003775):
    sub-XXX/ses-t1/eeg/sub-XXX_ses-t1_task-resteyesc_eeg.edf

Only session t1 is used for normative purposes. Session t2 (retest)
is available for 42 subjects but excluded by default.

Reference: Hatlestad-Hall et al. (2020). European Journal of Neuroscience.
OpenNeuro: ds003775
"""

from __future__ import annotations

import csv
import logging
import math
from collections.abc import Iterator
from pathlib import Path

import mne

from open_normative.channels import pick_standard_channels
from open_normative.datasets.base import DatasetLoader, SubjectFileRecord, SubjectRecord

logger = logging.getLogger(__name__)

_DOWNLOAD_INSTRUCTIONS = """
SRM dataset can be downloaded from OpenNeuro.

    python scripts/srm_download.py ~/Data/EEG/SRM

Or manually:
    aws s3 sync s3://openneuro.org/ds003775 ~/Data/EEG/SRM/ --no-sign-request

Citation: Hatlestad-Hall et al. (2020). European Journal of Neuroscience.
"""


class SRMLoader(DatasetLoader):
    """Loader for the SRM resting-state EEG dataset.

    Recorded in Norway — line noise is 50 Hz.
    Eyes-closed only (task-resteyesc).
    """

    line_freq: float = 50.0

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each subject in session t1."""
        participants = self._load_participants(data_dir)

        edf_files = sorted(data_dir.glob(
            "sub-*/ses-t1/eeg/*_task-resteyesc_eeg.edf"
        ))

        if not edf_files:
            logger.warning(
                "No EDF files found in %s/sub-*/ses-t1/eeg/", data_dir
            )
            return

        logger.info("Found %d EDF files in session t1", len(edf_files))

        for edf_path in edf_files:
            subject_id = None
            for part in edf_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                logger.warning("Could not extract subject ID from %s", edf_path)
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            if math.isnan(age):
                logger.warning("No demographics for %s — age will be NaN", subject_id)

            try:
                raw = mne.io.read_raw_edf(str(edf_path), preload=True, verbose=False)
                raw.pick("eeg")
                raw = pick_standard_channels(raw, n_channels=self.n_channels)
            except Exception:
                logger.warning("Failed to load %s", edf_path, exc_info=True)
                continue

            metadata = {"source_file": str(edf_path), **info}

            yield SubjectRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                raw=raw,
                condition="ec",  # eyes-closed only
                metadata=metadata,
            )

    def iter_subject_files(self, data_dir: Path) -> Iterator[SubjectFileRecord]:
        """Yield SubjectFileRecord for each subject without loading data."""
        participants = self._load_participants(data_dir)

        edf_files = sorted(data_dir.glob(
            "sub-*/ses-t1/eeg/*_task-resteyesc_eeg.edf"
        ))

        for edf_path in edf_files:
            subject_id = None
            for part in edf_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")
            metadata = {"source_file": str(edf_path), **info}

            yield SubjectFileRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                condition="ec",
                filepath=edf_path,
                metadata=metadata,
            )

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Parse participants.tsv for age, sex."""
        tsv_path = data_dir / "participants.tsv"
        if not tsv_path.exists():
            logger.warning("No participants.tsv found in %s", data_dir)
            return {}

        participants: dict[str, dict] = {}
        with tsv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                sid = row.get("participant_id", "").strip()
                if not sid:
                    continue

                raw_age = row.get("age", "").strip()
                try:
                    age = float(raw_age)
                except (ValueError, TypeError):
                    age = float("nan")

                raw_sex = row.get("sex", "").strip().upper()
                if raw_sex.startswith("M"):
                    sex = "M"
                elif raw_sex.startswith("F"):
                    sex = "F"
                else:
                    sex = raw_sex

                participants[sid] = {"age": age, "sex": sex}

        logger.info("Loaded demographics for %d subjects", len(participants))
        return participants
