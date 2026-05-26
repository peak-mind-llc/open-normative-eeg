"""Tests for the release orchestrator core (open_normative/release.py)."""
import json
import hashlib
from pathlib import Path

import numpy as np
import pytest

from open_normative import release as rel


def test_normalize_version_strips_v_and_validates():
    assert rel.normalize_version("v0.2.0") == "0.2.0"
    assert rel.normalize_version("0.2.0") == "0.2.0"
    with pytest.raises(ValueError):
        rel.normalize_version("0.2")        # not X.Y.Z
    with pytest.raises(ValueError):
        rel.normalize_version("v1.2.x")     # non-numeric


def test_bump_version_rewrites_both_files(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "open-normative-eeg"\nversion = "0.1.0"\n'
    )
    pkg = tmp_path / "open_normative"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""pkg."""\n__version__ = "0.1.0"\n')

    rel.bump_version("0.2.0", tmp_path)

    assert 'version = "0.2.0"' in (tmp_path / "pyproject.toml").read_text()
    assert '__version__ = "0.2.0"' in (pkg / "__init__.py").read_text()
    assert 'name = "open-normative-eeg"' in (tmp_path / "pyproject.toml").read_text()


def test_pipeline_params_sha256_is_stable_and_hex():
    h1 = rel.pipeline_params_sha256()
    h2 = rel.pipeline_params_sha256()
    assert h1 == h2
    assert len(h1) == 64 and int(h1, 16) >= 0
