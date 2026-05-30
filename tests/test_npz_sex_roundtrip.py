"""NPZ format_version 3 round-trip: sex array written, read back, defaults to 'pooled'."""

import json
from pathlib import Path

import numpy as np

from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import NormCell


def _make_cell(sex: str, mean: float = 1.0) -> NormCell:
    return NormCell(
        bin="20-29", condition="ec", channel="Fz",
        band="Alpha", metric="absolute_power",
        n=10, mean=mean, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={},
        sex=sex,
    )


def test_npz_sex_roundtrip(tmp_path: Path):
    cells = [_make_cell("pooled", 1.0), _make_cell("F", 1.5), _make_cell("M", 0.5)]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    by_sex = {c.sex: c.mean for c in loaded}
    assert by_sex == {"pooled": 1.0, "F": 1.5, "M": 0.5}


def test_npz_metadata_lists_format_version_3_and_unique_sexes(tmp_path: Path):
    cells = [_make_cell("pooled"), _make_cell("F"), _make_cell("M")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["format_version"] == 3
    cat = meta["categories"]["scalp_power"]
    assert sorted(cat["unique_sexes"]) == ["F", "M", "pooled"]


def test_npz_legacy_v2_without_sex_array_reads_as_pooled(tmp_path: Path):
    """Hand-write a v2 NPZ (no 'sex' array) and verify it reads back with sex='pooled'."""
    npz_dir = tmp_path / "npz"
    npz_dir.mkdir()

    # Minimal v2-style NPZ with all required arrays except 'sex'.
    np.savez_compressed(
        npz_dir / "scalp_power.npz",
        bins=np.array(["20-29"], dtype="U20"),
        conditions=np.array(["ec"], dtype="U10"),
        channels=np.array(["Fz"], dtype="U80"),
        bands=np.array(["Alpha"], dtype="U64"),
        metrics=np.array(["absolute_power"], dtype="U40"),
        mean=np.array([1.0], dtype=np.float64),
        sd=np.array([0.5], dtype=np.float64),
        n=np.array([10], dtype=np.int32),
        log_mean=np.array([np.nan], dtype=np.float64),
        log_sd=np.array([np.nan], dtype=np.float64),
        log_transformed=np.array([False], dtype=bool),
        skewness=np.array([np.nan], dtype=np.float64),
        kurtosis=np.array([np.nan], dtype=np.float64),
        normality_p=np.array([np.nan], dtype=np.float64),
        transform_normalized=np.array([np.nan], dtype=np.float64),
        percentile_points=np.array([50.0], dtype=np.float64),
        percentiles=np.full((1, 1), np.nan, dtype=np.float64),
    )
    meta = {
        "format_version": 2,
        "total_cells": 1,
        "categories": {"scalp_power": {"file": "scalp_power.npz", "n_cells": 1}},
        "age_bins": ["20-29"],
        "conditions": ["ec"],
    }
    (npz_dir / "metadata.json").write_text(json.dumps(meta))

    loaded = read_norms_npz(npz_dir)
    assert len(loaded) == 1
    assert loaded[0].sex == "pooled"


def test_scalp_node_strength_unique_metrics_in_metadata(tmp_path: Path):
    """When node-strength cells are written, their unique_metrics is the
    short form (dwpli/coh) — confirms the rename made it through to the
    category manifest."""
    cells = [
        NormCell(
            bin="20-29", condition="ec", channel="Fz",
            band="Alpha", metric="dwpli_node_strength",
            n=10, mean=1.0, sd=0.5,
            log_mean=None, log_sd=None, log_transformed=False,
            normality_p=None, percentiles={}, sex="pooled",
        ),
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["categories"]["scalp_node_strength"]["unique_metrics"] == ["dwpli"]
