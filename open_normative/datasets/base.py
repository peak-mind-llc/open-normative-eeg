"""Abstract base class for dataset loaders."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

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


class DatasetLoader(ABC):
    """Abstract base for public EEG dataset loaders."""

    # Line frequency for notch filtering. Subclasses should override
    # for non-US datasets (e.g. 50 Hz for European recordings).
    line_freq: float = 60.0

    @abstractmethod
    def download(self, dest_dir: Path) -> None:
        ...

    @abstractmethod
    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        ...
