"""HBN (Healthy Brain Network) dataset loader stub."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from open_normative.datasets.base import DatasetLoader, SubjectRecord


class HBNLoader(DatasetLoader):
    """Loader for the Healthy Brain Network EEG dataset.

    Not yet implemented. See https://fcon_1000.projects.nitrc.org/indi/cmi_healthy_brain_network/
    for dataset information and download instructions.
    """

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(
            "HBNLoader.download() is not yet implemented. "
            "See https://fcon_1000.projects.nitrc.org/indi/cmi_healthy_brain_network/ "
            "for download instructions."
        )

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        raise NotImplementedError("HBNLoader.iter_subjects() is not yet implemented.")
