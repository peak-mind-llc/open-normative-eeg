"""Dortmund Vital Study dataset loader.

The Dortmund Vital Study (Getzmann et al., 2024) provides resting-state EEG
from 608 healthy adults ages 20-70, recorded with 64-channel BrainProducts
actiCHamp. CC BY 4.0 license.

Data layout (BIDS on OpenNeuro ds005385):
  sub-XXX/ses-1/eeg/sub-XXX_ses-1_task-{EyesOpen,EyesClosed}_acq-{pre,post}_eeg.vhdr

For normative purposes, only session 1 pre-task resting data is used.
Post-task data may be contaminated by cognitive fatigue effects.
Session 2 (5-year follow-up) is flagged for longitudinal analysis only.

Reference: Getzmann, S., Gajewski, P.D., Schneider, D. & Wascher, E. (2024).
Resting-state EEG data before and after cognitive activity across the adult
lifespan and a 5-year follow-up. Scientific Data, 11:988.

OpenNeuro: ds005385
"""

from __future__ import annotations

import csv
import logging
import math
from collections.abc import Iterator
from pathlib import Path

import mne

from open_normative.channels import pick_standard_19
from open_normative.datasets.base import DatasetLoader, SubjectRecord

logger = logging.getLogger(__name__)

_DOWNLOAD_INSTRUCTIONS = """
Dortmund Vital Study must be downloaded from OpenNeuro.

Option 1: openneuro-py
    pip install openneuro-py
    openneuro download --dataset ds005385 ~/datasets/dortmund/

Option 2: AWS S3
    aws s3 sync s3://openneuro.org/ds005385 ~/datasets/dortmund/ --no-sign-request

Option 3: DataLad
    datalad install https://github.com/OpenNeuroDatasets/ds005385.git

Citation: Getzmann et al. (2024). Scientific Data, 11:988.
"""


class DortmundLoader(DatasetLoader):
    """Loader for the Dortmund Vital Study resting-state EEG.

    Yields only session 1, pre-task resting data (EO and EC).
    European dataset: line noise is 50 Hz.
    """

    line_freq: float = 50.0

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(_DOWNLOAD_INSTRUCTIONS)

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        """Yield SubjectRecord for each pre-task EO/EC file in session 1.

        Parameters
        ----------
        data_dir:
            Root BIDS directory containing sub-*/ folders and participants.tsv.
        """
        participants = self._load_participants(data_dir)

        # Find all .vhdr files in session 1
        vhdr_files = sorted(
            set(data_dir.glob("sub-*/ses-1/eeg/*.vhdr"))
            | set(data_dir.glob("sub-*/eeg/*.vhdr"))
        )

        if not vhdr_files:
            logger.warning(
                "No .vhdr files found in %s/sub-*/{ses-1/eeg,eeg}/", data_dir
            )
            return

        logger.info("Found %d .vhdr files in session 1", len(vhdr_files))

        for vhdr_path in vhdr_files:
            # Only process pre-task files
            if not self._is_pre_task(vhdr_path):
                continue

            # Extract subject ID
            subject_id = None
            for part in vhdr_path.parts:
                if part.startswith("sub-"):
                    subject_id = part
                    break
            if subject_id is None:
                logger.warning("Could not extract subject ID from %s", vhdr_path)
                continue

            # Detect condition from filename
            condition = self._detect_condition(vhdr_path.name)
            if condition is None:
                logger.warning(
                    "Could not determine EO/EC condition from %s — skipping",
                    vhdr_path.name,
                )
                continue

            # Get demographics
            info = participants.get(subject_id, {})
            age = info.get("age", float("nan"))
            sex = info.get("sex", "")

            if math.isnan(age):
                logger.warning(
                    "No demographics for %s — age will be NaN", subject_id
                )

            # Load the recording
            try:
                raw = mne.io.read_raw_brainvision(
                    str(vhdr_path), preload=True, verbose=False
                )
            except Exception:
                logger.warning("Failed to load %s", vhdr_path, exc_info=True)
                continue

            # Drop non-EEG channels, standardize to 19 channels
            raw.pick("eeg")
            try:
                raw = pick_standard_19(raw)
            except Exception:
                logger.warning(
                    "Channel standardization failed for %s — skipping",
                    vhdr_path,
                    exc_info=True,
                )
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

                # Age
                raw_age = row.get("age", "").strip()
                try:
                    age = float(raw_age)
                except (ValueError, TypeError):
                    age = float("nan")

                # Sex
                raw_sex = row.get("sex", row.get("gender", "")).strip().upper()
                if raw_sex.startswith("M"):
                    sex = "M"
                elif raw_sex.startswith("F"):
                    sex = "F"
                else:
                    sex = raw_sex

                participants[sid] = {"age": age, "sex": sex}

        logger.info("Loaded demographics for %d subjects", len(participants))
        return participants

    @staticmethod
    def _is_pre_task(vhdr_path: Path) -> bool:
        """Return True if this file is a pre-task recording.

        Checks for:
        - acq-pre / acq-pretask in filename
        - run-01 (if no acq entity, assume run-01 = pre)
        - absence of 'post' in filename
        """
        name = vhdr_path.name.lower()
        # Explicit pre-task marker
        if "acq-pre" in name:
            return True
        # Explicit post-task marker — skip
        if "acq-post" in name:
            return False
        # No acq entity — check run number (run-01 = pre)
        if "run-01" in name or "run-1_" in name:
            return True
        if "run-02" in name or "run-2_" in name:
            return False
        # Single run with no acq/run — assume pre-task
        return True

    @staticmethod
    def _detect_condition(filename: str) -> str | None:
        """Return 'eo' or 'ec' from a Dortmund filename.

        Handles:
        - task-EyesOpen / task-EyesClosed (Dortmund standard)
        - task-restEO / task-restEC
        - EO / EC in filename
        """
        lower = filename.lower()
        if "eyesopen" in lower or "resteo" in lower or "_eo_" in lower:
            return "eo"
        if "eyesclosed" in lower or "restec" in lower or "_ec_" in lower:
            return "ec"
        upper = filename.upper()
        if "EO" in upper.split("_"):
            return "eo"
        if "EC" in upper.split("_"):
            return "ec"
        return None
