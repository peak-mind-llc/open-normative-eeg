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


def _subject(subject_id, age, sex, value, condition="ec"):
    """Tiny subject record for build_normative."""
    return {
        "subject_id": subject_id,
        "age": age,
        "sex": sex,
        "condition": condition,
        "metrics": {"Fz": {"Alpha": {"absolute_power": value}}},
    }


def test_build_normative_fans_to_three_sex_variants():
    """Mixed-sex dataset produces a pooled cell + an F cell + an M cell per tuple."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "F", 1.1),
        _subject("s03", 25, "F", 1.2),
        _subject("s04", 25, "M", 2.0),
        _subject("s05", 25, "M", 2.1),
        _subject("s06", 25, "M", 2.2),
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    assert set(by_sex) == {"pooled", "F", "M"}
    assert by_sex["pooled"].n == 6
    assert by_sex["F"].n == 3
    assert by_sex["M"].n == 3
    # Pooled mean is the mean of all 6 values; F mean is the mean of 3.
    assert by_sex["pooled"].mean == pytest.approx((1.0 + 1.1 + 1.2 + 2.0 + 2.1 + 2.2) / 6)
    assert by_sex["F"].mean == pytest.approx((1.0 + 1.1 + 1.2) / 3)
    assert by_sex["M"].mean == pytest.approx((2.0 + 2.1 + 2.2) / 3)


def test_build_normative_other_sex_contributes_to_pooled_only():
    """Subjects with empty/unrecognised sex are pooled-only — no own-sex cell shipped."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "M", 2.0),
        _subject("s03", 25, "", 3.0),      # unknown
        _subject("s04", 25, "Other", 4.0),  # explicit other
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    # Only pooled / F / M variants exist — no "Other" or "" cell.
    assert set(by_sex) == {"pooled", "F", "M"}
    # Pooled n includes all 4 subjects (including Other and unknown).
    assert by_sex["pooled"].n == 4
    assert by_sex["F"].n == 1
    assert by_sex["M"].n == 1
    # Pooled mean averages all 4 raw values.
    assert by_sex["pooled"].mean == pytest.approx((1.0 + 2.0 + 3.0 + 4.0) / 4)


def test_build_normative_single_sex_dataset_omits_other_sex_cell():
    """All-F dataset: pooled and F cells ship; the M cell is genuinely absent."""
    subjects = [
        _subject("s01", 25, "F", 1.0),
        _subject("s02", 25, "F", 1.1),
    ]
    cells = build_normative(subjects, age_bins=[20, 30, 100])
    by_sex = {c.sex: c for c in cells
              if c.bin == "20-29" and c.band == "Alpha" and c.channel == "Fz"
              and c.metric == "absolute_power" and c.condition == "ec"}

    assert set(by_sex) == {"pooled", "F"}
    assert by_sex["pooled"].n == 2
    assert by_sex["F"].n == 2


def test_csv_writer_includes_sex_column(tmp_path: Path):
    import csv
    from open_normative.io import write_norms_csv

    cells = [
        NormCell(
            bin="20-29", condition="ec", channel="Fz", band="Alpha",
            metric="absolute_power", n=10, mean=1.0, sd=0.5,
            log_mean=None, log_sd=None, log_transformed=False,
            normality_p=None, percentiles={}, sex="F",
        ),
    ]
    path = tmp_path / "norms.csv"
    write_norms_csv(cells, path)

    with open(path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert "sex" in rows[0]
    assert rows[0]["sex"] == "F"
