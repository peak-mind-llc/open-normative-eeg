"""MIPDB (Multimodal Resource for Studying Information Processing in the Developing Brain) dataset loader stub."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from open_normative.datasets.base import DatasetLoader, SubjectRecord


class MIPDBLoader(DatasetLoader):
    """Loader for the MIPDB EEG dataset.

    Not yet implemented. See http://fcon_1000.projects.nitrc.org/indi/cmi_eeg/
    for dataset information and download instructions.
    """

    def download(self, dest_dir: Path) -> None:
        raise NotImplementedError(
            "MIPDBLoader.download() is not yet implemented. "
            "See http://fcon_1000.projects.nitrc.org/indi/cmi_eeg/ "
            "for download instructions."
        )

    def iter_subjects(self, data_dir: Path) -> Iterator[SubjectRecord]:
        raise NotImplementedError("MIPDBLoader.iter_subjects() is not yet implemented.")
