"""Abstract base class for dataset loaders."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import mne


@dataclass
class SubjectRecord:
    """A single subject's data from a dataset."""
    subject_id: str
    age: float
    sex: str  # "M" or "F"
    raw: mne.io.Raw
    condition: str  # "eo" or "ec"
    metadata: dict


@dataclass
class SubjectFileRecord:
    """Lightweight record for parallel dispatch — no loaded data.

    Contains enough information for a worker process to independently
    load, standardize, and process one subject.
    """
    subject_id: str
    age: float
    sex: str
    condition: str  # "eo" or "ec"
    filepath: Path
    metadata: dict = field(default_factory=dict)
    # For single-file recordings that contain multiple conditions
    # (e.g. LEMON with S210/S200 markers), the marker code to extract.
    marker_condition: Optional[str] = None


class DatasetLoader(ABC):
    """Abstract base for public EEG dataset loaders."""

    # Line frequency for notch filtering. Subclasses should override
    # for non-US datasets (e.g. 50 Hz for European recordings).
    line_freq: float = 60.0

    # Target channel count for standardization (19 or 37).
    n_channels: int = 19

    @abstractmethod
    def download(self, dest_dir: Path) -> None:
        ...

    @abstractmethod
    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        ...

    def iter_subject_files(self, data_dir: Path) -> Iterator[SubjectFileRecord]:
        """Yield lightweight file records without loading raw data.

        Default implementation falls back to iter_subjects (loading data),
        extracts file info, then discards the Raw. Subclasses should override
        for better efficiency.
        """
        for record in self.iter_subjects(data_dir):
            filepath = Path(record.metadata.get("source_file", ""))
            yield SubjectFileRecord(
                subject_id=record.subject_id,
                age=record.age,
                sex=record.sex,
                condition=record.condition,
                filepath=filepath,
                metadata=record.metadata,
            )
            del record.raw
