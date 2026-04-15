"""TRT (Test-Retest) EEG dataset loader.

60 healthy adults ages 18-28, 64-channel BrainVision (10-10),
eyes-closed and eyes-open resting state (~5 min each), 500 Hz. CC0 license.
Recorded in China — line noise is 50 Hz.

Data layout (BIDS on OpenNeuro ds004148):
    sub-XX/ses-session1/eeg/sub-XX_ses-session1_task-eyesclosed_eeg.vhdr
    sub-XX/ses-session1/eeg/sub-XX_ses-session1_task-eyesopen_eeg.vhdr

Only session 1 is used for normative purposes. Sessions 2 and 3 (retest)
are available but excluded by default.

Reference: Li et al. (2022). OpenNeuro ds004148.
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
TRT dataset can be downloaded from OpenNeuro.

    python scripts/trt_download.py ~/Data/EEG/TRT

Or manually:
    aws s3 sync s3://openneuro.org/ds004148 ~/Data/EEG/TRT/ --no-sign-request

Citation: Li et al. (2022). OpenNeuro ds004148.
"""

# Map BIDS task labels to condition codes
_TASK_CONDITION_MAP = {
    "eyesclosed": "ec",
    "eyesopen": "eo",
}


class TRTLoader(DatasetLoader):
    """Loader for the Test-Retest EEG dataset.

    Recorded in China — line noise is 50 Hz.
    Both eyes-closed (task-eyesclosed) and eyes-open (task-eyesopen).
    """

    line_freq: float = 50.0

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each subject/condition in session 1."""
        participants = self._load_participants(data_dir)

        # Glob for both tasks
        vhdr_files = sorted(
            list(data_dir.glob(
                "sub-*/ses-session1/eeg/*_task-eyesclosed_eeg.vhdr"
            ))
            + list(data_dir.glob(
                "sub-*/ses-session1/eeg/*_task-eyesopen_eeg.vhdr"
            ))
        )

        if not vhdr_files:
            logger.warning(
                "No .vhdr files found in %s/sub-*/ses-session1/eeg/", data_dir
            )
            return

        logger.info("Found %d .vhdr files in session 1", len(vhdr_files))

        for vhdr_path in vhdr_files:
            subject_id = None
            for part in vhdr_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                logger.warning("Could not extract subject ID from %s", vhdr_path)
                continue

            # Determine condition from task label in filename
            condition = self._extract_condition(vhdr_path)
            if condition is None:
                logger.warning("Could not determine condition from %s", vhdr_path)
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            if math.isnan(age):
                logger.warning("No demographics for %s — age will be NaN", subject_id)

            try:
                raw = mne.io.read_raw_brainvision(str(vhdr_path), preload=True, verbose=False)
                raw.pick("eeg")
                raw = pick_standard_channels(raw, n_channels=self.n_channels)
            except Exception:
                logger.warning("Failed to load %s", vhdr_path, exc_info=True)
                continue

            metadata = {"source_file": str(vhdr_path), **info}

            yield SubjectRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                raw=raw,
                condition=condition,
                metadata=metadata,
            )

    def iter_subject_files(self, data_dir: Path) -> Iterator[SubjectFileRecord]:
        """Yield SubjectFileRecord for each subject/condition without loading data."""
        participants = self._load_participants(data_dir)

        vhdr_files = sorted(
            list(data_dir.glob(
                "sub-*/ses-session1/eeg/*_task-eyesclosed_eeg.vhdr"
            ))
            + list(data_dir.glob(
                "sub-*/ses-session1/eeg/*_task-eyesopen_eeg.vhdr"
            ))
        )

        for vhdr_path in vhdr_files:
            subject_id = None
            for part in vhdr_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                continue

            condition = self._extract_condition(vhdr_path)
            if condition is None:
                continue

            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")
            metadata = {"source_file": str(vhdr_path), **info}

            yield SubjectFileRecord(
                subject_id=subject_id,
                age=age,
                sex=sex,
                condition=condition,
                filepath=vhdr_path,
                metadata=metadata,
            )

    @staticmethod
    def _extract_condition(filepath: Path) -> str | None:
        """Extract condition ('ec' or 'eo') from BIDS task label in filename."""
        name = filepath.stem
        for task_label, condition in _TASK_CONDITION_MAP.items():
            if f"task-{task_label}" in name:
                return condition
        return None

    @staticmethod
    def _load_participants(data_dir: Path) -> dict[str, dict]:
        """Parse participants.tsv for age, sex.

        The TRT dataset uses lowercase m/f for sex — we normalize to M/F.
        """
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

                # Normalize lowercase m/f to uppercase M/F
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
