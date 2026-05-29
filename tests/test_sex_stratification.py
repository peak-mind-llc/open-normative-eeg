"""Sex stratification tests — NormCell carries sex; build_normative fans to pooled + F + M."""

from pathlib import Path

import pytest

from open_normative.io import read_norms_json, write_norms_json
from open_normative.normative import NormCell, build_normative


def _make_cell(**overrides) -> NormCell:
    """Build a NormCell with sensible defaults for testing."""
    base = dict(
        bin="20-29",
        condition="ec",
        channel="Fz",
        band="Alpha",
        metric="absolute_power",
        n=10,
        mean=1.0,
        sd=0.5,
        log_mean=None,
        log_sd=None,
        log_transformed=False,
        normality_p=None,
        percentiles={},
    )
    base.update(overrides)
    return NormCell(**base)


def test_normcell_sex_defaults_to_pooled():
    cell = _make_cell()
    assert cell.sex == "pooled"


def test_normcell_sex_roundtrips_through_json(tmp_path: Path):
    cells = [_make_cell(sex="F"), _make_cell(sex="M"), _make_cell(sex="pooled")]
    path = tmp_path / "norms.json"
    write_norms_json(cells, path)
    loaded = read_norms_json(path)
    assert [c.sex for c in loaded] == ["F", "M", "pooled"]


def test_normcell_legacy_json_without_sex_field_reads_as_pooled(tmp_path: Path):
    """Old bundles have no `sex` field in JSON — must deserialize as 'pooled'."""
    import json
    legacy = [{
        "bin": "20-29", "condition": "ec", "channel": "Fz",
        "band": "Alpha", "metric": "absolute_power",
        "n": 10, "mean": 1.0, "sd": 0.5,
        "log_mean": None, "log_sd": None, "log_transformed": False,
        "normality_p": None, "percentiles": {},
        # Note: no 'sex' field
    }]
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy))
    loaded = read_norms_json(path)
    assert len(loaded) == 1
    assert loaded[0].sex == "pooled"
