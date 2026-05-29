"""Tests for normative distribution computation."""

import json
import numpy as np
import pytest
from open_normative.normative import build_normative, NormCell, _is_log_transform
from open_normative.io import (
    read_norms_json,
    read_norms_npz,
    robust_z_from_percentiles,
    write_norms_csv,
    write_norms_json,
    write_norms_npz,
)


def test_build_normative_basic(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    assert len(norms) > 0
    assert isinstance(norms[0], NormCell)


def test_norm_cell_has_required_fields(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    cell = norms[0]
    for field in ["bin", "condition", "channel", "band", "metric", "n",
                  "mean", "sd", "log_mean", "log_sd", "log_transformed",
                  "normality_p", "percentiles"]:
        assert hasattr(cell, field)


def test_build_normative_age_bins(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics, age_bins=[20, 40, 60, 80])
    bins_seen = {cell.bin for cell in norms}
    assert len(bins_seen) > 0
    for b in bins_seen:
        assert "-" in b


def test_build_normative_log_transform_absolute_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    abs_power_cells = [c for c in norms if c.metric == "absolute_power"]
    if abs_power_cells:
        cell = abs_power_cells[0]
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_no_log_transform_relative_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    rel_power_cells = [c for c in norms if c.metric == "relative_power"]
    if rel_power_cells:
        cell = rel_power_cells[0]
        assert cell.log_transformed is False


def test_is_log_transform_helper():
    """Ratio bands (containing '/') get log-transformed regardless of metric."""
    # Power metrics by name
    assert _is_log_transform("absolute_power", "Alpha") is True
    assert _is_log_transform("corrected_absolute_power", "Alpha") is True
    assert _is_log_transform("relative_power", "Alpha") is False
    # Ratios — band contains "/"
    assert _is_log_transform("value", "Theta/Beta") is True
    assert _is_log_transform("value", "corrected_Theta/Beta") is True
    assert _is_log_transform("value", "(Delta+Theta)/(Alpha+Beta)") is True
    # Asymmetry pairs (e.g. F3/F4) are stored as channel, not band, so this
    # check is a band-name check; asymmetry's band is e.g. "Alpha".
    assert _is_log_transform("asymmetry_index", "Alpha") is False


def test_build_normative_log_transforms_ratios():
    """Ratio cells (band containing '/') should be log-transformed."""
    rng = np.random.RandomState(42)
    subjects = [
        {
            "subject_id": f"sub-{i:03d}",
            "age": rng.randint(20, 70),
            "sex": "F",
            "condition": "eo",
            "metrics": {
                "Fz": {
                    "Theta/Beta": {
                        "value": float(rng.lognormal(0.0, 0.4)),
                    },
                    "(Delta+Theta)/(Alpha+Beta)": {
                        "value": float(rng.lognormal(0.0, 0.5)),
                    },
                },
            },
        }
        for i in range(40)
    ]
    norms = build_normative(subjects)
    ratio_cells = [c for c in norms if "/" in c.band]
    assert len(ratio_cells) > 0
    for cell in ratio_cells:
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_log_transform_corrected_absolute_power(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    corr_abs_cells = [c for c in norms if c.metric == "corrected_absolute_power"]
    if corr_abs_cells:
        cell = corr_abs_cells[0]
        assert cell.log_transformed is True
        assert cell.log_mean is not None
        assert cell.log_sd is not None


def test_build_normative_percentiles(mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    for cell in norms:
        if cell.n >= 2:
            assert "50" in cell.percentiles
            assert cell.percentiles["50"] is not None


# ---------------------------------------------------------------------------
# Distribution disclosure + verify-and-flag (Wood et al. 2024)
# ---------------------------------------------------------------------------


def _subjects_with_metric(values, *, metric, channel="Fz", band="Alpha",
                          condition="eo"):
    """Build subject dicts each carrying one (channel, band, metric) value.

    Ages are spread inside a single 20-29 bin so every value lands in one cell.
    """
    subs = []
    for i, v in enumerate(values):
        subs.append({
            "subject_id": f"sub-{i:03d}",
            "age": 20 + (i % 10),
            "sex": "F",
            "condition": condition,
            "metrics": {channel: {band: {metric: float(v)}}},
        })
    return subs


def _one_cell(subjects):
    norms = build_normative(subjects, age_bins=[20, 30])
    pooled = [c for c in norms if c.sex == "pooled"]
    assert len(pooled) == 1
    return pooled[0]


def test_cell_reports_raw_skewness_and_kurtosis():
    rng = np.random.RandomState(0)
    vals = rng.lognormal(0.0, 0.6, size=120)  # right-skewed raw power
    cell = _one_cell(_subjects_with_metric(vals, metric="absolute_power"))
    assert cell.skewness is not None and cell.skewness > 0.3
    assert cell.kurtosis is not None  # excess (Fisher) kurtosis


def test_normality_p_uses_scoring_space_for_log_metrics():
    """For a log-transformed metric fed lognormal data, the log-space is
    Gaussian, so Shapiro (computed on the scoring space) should NOT reject —
    even though the raw values are right-skewed."""
    rng = np.random.RandomState(1)
    vals = rng.lognormal(0.0, 0.5, size=120)  # log(vals) ~ Normal
    cell = _one_cell(_subjects_with_metric(vals, metric="absolute_power"))
    assert cell.log_transformed is True
    assert cell.normality_p is not None
    assert cell.normality_p > 0.05
    assert cell.transform_normalized is True


def test_transform_normalized_false_when_log_cannot_fix():
    """A log metric whose log-space is itself non-normal (right-skewed) must
    be flagged transform_normalized=False."""
    rng = np.random.RandomState(2)
    vals = np.exp(rng.exponential(1.0, size=300))  # log-space ~ Exponential
    cell = _one_cell(_subjects_with_metric(vals, metric="absolute_power"))
    assert cell.log_transformed is True
    assert cell.transform_normalized is False


def test_prediction_interval_asymmetric_for_log_metrics():
    """PI for a log metric is computed in log space and exponentiated, so it
    is asymmetric about the mean and strictly positive."""
    import math
    from scipy import stats as _stats
    rng = np.random.RandomState(3)
    vals = rng.lognormal(0.0, 0.5, size=120)
    cell = _one_cell(_subjects_with_metric(vals, metric="absolute_power"))
    assert cell.pi_lower is not None and cell.pi_upper is not None
    assert cell.pi_lower > 0.0
    assert cell.pi_lower < cell.mean < cell.pi_upper
    lower_gap = cell.mean - cell.pi_lower
    upper_gap = cell.pi_upper - cell.mean
    assert abs(upper_gap - lower_gap) > 1e-6  # asymmetric
    n = cell.n
    t = float(_stats.t.ppf(0.975, df=n - 1))
    expected_upper = math.exp(
        cell.log_mean + t * cell.log_sd * math.sqrt(1 + 1 / n)
    )
    assert abs(cell.pi_upper - expected_upper) < 1e-6


def test_extended_tail_percentiles_present():
    rng = np.random.RandomState(4)
    vals = rng.lognormal(0.0, 0.5, size=300)
    cell = _one_cell(_subjects_with_metric(vals, metric="absolute_power"))
    for k in ["0.5", "2.5", "50", "97.5", "99.5"]:
        assert k in cell.percentiles


def test_write_and_read_norms_json(tmp_path, mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    fpath = tmp_path / "norms.json"
    write_norms_json(norms, fpath)
    assert fpath.exists()
    loaded = read_norms_json(fpath)
    assert len(loaded) == len(norms)
    assert loaded[0].bin == norms[0].bin


def test_write_norms_csv(tmp_path, mock_subject_metrics):
    norms = build_normative(mock_subject_metrics)
    fpath = tmp_path / "norms.csv"
    write_norms_csv(norms, fpath)
    assert fpath.exists()
    with open(fpath) as f:
        header = f.readline()
    assert "bin" in header
    assert "mean" in header


def test_write_norms_npz_preserves_long_band_names(tmp_path):
    """Regression: ratio band names like '(Delta+Theta)/(Alpha+Beta)' or
    'corrected_Alpha/HighBeta' must round-trip through NPZ without
    truncation. The bands array dtype must accommodate at least 64 chars
    so future ratio additions don't silently lose data.
    """
    long_bands = [
        "(Delta+Theta)/(Alpha+Beta)",          # 26 chars — was truncated to 20
        "corrected_(Delta+Theta)/(Alpha+Beta)",  # 36 chars
        "corrected_Alpha/HighBeta",             # 24 chars
        "corrected_Theta/Beta1",                # 21 chars
        "Theta/Beta",                           # 10 chars (control)
    ]
    cells = [
        NormCell(
            bin="20-29", condition="eo",
            channel="Fz", band=b, metric="value",
            n=10, mean=1.0, sd=0.1,
            log_mean=None, log_sd=None,
            log_transformed=False,
            normality_p=None, percentiles={},
        )
        for b in long_bands
    ]
    write_norms_npz(cells, tmp_path)

    data = np.load(tmp_path / "npz" / "scalp_power.npz", allow_pickle=False)
    round_tripped = sorted(set(str(b) for b in data["bands"]))
    assert sorted(long_bands) == round_tripped, (
        f"NPZ truncated band names: expected {sorted(long_bands)!r}, "
        f"got {round_tripped!r}"
    )


def _norms_for_io():
    """Deterministic single-cell norm set with a log-transformed metric."""
    rng = np.random.RandomState(7)
    vals = rng.lognormal(0.0, 0.5, size=60)
    return build_normative(
        _subjects_with_metric(vals, metric="absolute_power"),
        age_bins=[20, 30],
    )


def test_json_roundtrips_disclosure_fields(tmp_path):
    norms = _norms_for_io()
    cell = norms[0]
    assert cell.skewness is not None  # sanity: fixture exercises the fields
    fpath = tmp_path / "norms.json"
    write_norms_json(norms, fpath)
    lc = read_norms_json(fpath)[0]
    assert lc.skewness == cell.skewness
    assert lc.kurtosis == cell.kurtosis
    assert lc.transform_normalized == cell.transform_normalized


def test_read_norms_json_defaults_missing_disclosure_fields(tmp_path):
    """A v1 norms.json lacking the new fields must still load."""
    legacy = [{
        "bin": "20-29", "condition": "eo", "channel": "Fz", "band": "Alpha",
        "metric": "relative_power", "n": 12, "mean": 0.3, "sd": 0.05,
        "log_mean": None, "log_sd": None, "log_transformed": False,
        "normality_p": 0.4, "percentiles": {"50": 0.3},
    }]
    fpath = tmp_path / "legacy.json"
    fpath.write_text(json.dumps(legacy))
    cells = read_norms_json(fpath)
    assert len(cells) == 1
    assert cells[0].skewness is None
    assert cells[0].kurtosis is None
    assert cells[0].transform_normalized is None


def test_csv_includes_disclosure_columns(tmp_path):
    norms = _norms_for_io()
    fpath = tmp_path / "norms.csv"
    write_norms_csv(norms, fpath)
    header = fpath.read_text().splitlines()[0]
    for col in ["skewness", "kurtosis", "transform_normalized", "p0.5", "p99.5"]:
        assert col in header


def test_npz_includes_disclosure_fields_and_v2(tmp_path):
    norms = _norms_for_io()
    write_norms_npz(norms, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["format_version"] == 2
    cat = next(iter(meta["categories"]))
    data = np.load(tmp_path / "npz" / f"{cat}.npz", allow_pickle=False)
    for key in ["skewness", "kurtosis", "normality_p",
                "transform_normalized", "percentile_points", "percentiles"]:
        assert key in data.files
    assert data["percentiles"].shape[0] == data["mean"].shape[0]
    assert data["percentiles"].shape[1] == len(data["percentile_points"])


def test_read_norms_npz_roundtrips_v2(tmp_path):
    norms = _norms_for_io()
    write_norms_npz(norms, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    assert len(loaded) == len(norms)
    orig = norms[0]
    lc = next(c for c in loaded if c.channel == orig.channel and c.band == orig.band
              and c.metric == orig.metric and c.bin == orig.bin)
    assert abs(lc.mean - orig.mean) < 1e-9
    assert abs(lc.sd - orig.sd) < 1e-9
    assert lc.log_transformed == orig.log_transformed
    assert abs(lc.skewness - orig.skewness) < 1e-9
    assert abs(lc.kurtosis - orig.kurtosis) < 1e-9
    assert lc.transform_normalized == orig.transform_normalized
    # Percentiles reconstructed at the same points (float-key match).
    assert abs(lc.percentiles["50"] - orig.percentiles["50"]) < 1e-9
    assert "99.5" in lc.percentiles


def test_read_norms_npz_materializes_arrays_once(tmp_path, monkeypatch):
    """Regression guard: NpzFile.__getitem__ re-decompresses the whole array on
    every access, so indexing d['field'][i] inside the row loop is O(n²). The
    reader must hoist each array out of the loop — verified by counting array
    decompressions, which must stay ~constant per file, not ~n_fields*n_cells."""
    n = 200
    cells = [
        NormCell(
            bin="20-29", condition="eo", channel=f"C{i}", band="Alpha",
            metric="absolute_power", n=50, mean=1.0 + i, sd=0.2,
            log_mean=0.0, log_sd=0.2, log_transformed=True, normality_p=0.3,
            percentiles={"50": 1.0 + i, "95": 2.0 + i},
            skewness=0.5, kurtosis=0.1, transform_normalized=True,
        )
        for i in range(n)
    ]
    write_norms_npz(cells, tmp_path)

    npz_cls = type(np.load(tmp_path / "npz" / "scalp_power.npz", allow_pickle=False))
    orig_getitem = npz_cls.__getitem__
    count = {"n": 0}

    def counting(self, key):
        count["n"] += 1
        return orig_getitem(self, key)

    monkeypatch.setattr(npz_cls, "__getitem__", counting)
    loaded = read_norms_npz(tmp_path / "npz")

    assert len(loaded) == n
    assert loaded[5].channel == "C5" and abs(loaded[5].mean - 6.0) < 1e-9
    # Buggy O(n²) reader does ~15 * n accesses (~3000); the fix does a small
    # constant per file.
    assert count["n"] < 40, (
        f"O(n^2) regression: {count['n']} NPZ array decompressions for {n} cells"
    )


def test_read_norms_npz_v1_fallback(tmp_path):
    """A v1 NPZ dir (no disclosure arrays) loads with new fields defaulted."""
    npz_dir = tmp_path / "npz"
    npz_dir.mkdir()
    np.savez_compressed(
        npz_dir / "scalp_power.npz",
        bins=np.array(["20-29"], dtype="U20"),
        conditions=np.array(["eo"], dtype="U10"),
        channels=np.array(["Fz"], dtype="U80"),
        bands=np.array(["Alpha"], dtype="U64"),
        metrics=np.array(["relative_power"], dtype="U40"),
        mean=np.array([0.3]), sd=np.array([0.05]), n=np.array([20], dtype=np.int32),
        log_mean=np.array([np.nan]), log_sd=np.array([np.nan]),
        log_transformed=np.array([False]),
    )
    (npz_dir / "metadata.json").write_text(json.dumps({
        "format_version": 1, "total_cells": 1,
        "categories": {"scalp_power": {"file": "scalp_power.npz", "n_cells": 1}},
    }))
    cells = read_norms_npz(npz_dir)
    assert len(cells) == 1
    c = cells[0]
    assert c.skewness is None and c.kurtosis is None
    assert c.transform_normalized is None
    assert c.normality_p is None
    assert c.percentiles == {}


def test_robust_z_helper_matches_compare(tmp_path):
    """robust_z_from_percentiles must equal compare_to_norms's robust_z."""
    from open_normative.compare import compare_to_norms
    from open_normative.normative import _PERCENTILE_POINTS
    cell = NormCell(
        bin="30-39", condition="eo", channel="Fz", band="Alpha",
        metric="relative_power", n=300, mean=10.0, sd=4.0,
        log_mean=None, log_sd=None, log_transformed=False, normality_p=0.5,
        percentiles={"0.5": 1, "1": 2, "2.5": 3, "5": 4, "10": 5, "25": 7,
                     "50": 10, "75": 13, "90": 16, "95": 18, "97.5": 20,
                     "99": 22, "99.5": 24},
    )
    value = 18.0
    res = compare_to_norms({"Fz": {"Alpha": {"relative_power": value}}},
                           [cell], age=35, condition="eo", apply_fdr=False)[0]

    def _k(p):
        return str(int(p)) if float(p).is_integer() else str(p)
    row = [cell.percentiles[_k(p)] for p in _PERCENTILE_POINTS]
    helper = robust_z_from_percentiles(value, _PERCENTILE_POINTS, row, cell.n)
    assert abs(helper - res.robust_z) < 1e-9
