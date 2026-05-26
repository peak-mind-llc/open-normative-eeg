"""Tests for per-frequency percentiles in norms_psd.npz (psd_format_version 2)."""
import importlib.util
import logging
from pathlib import Path

import numpy as np

_SPEC = importlib.util.spec_from_file_location(
    "build_norms", Path(__file__).resolve().parent.parent / "scripts" / "build_norms.py"
)
bn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bn)

_PCT = list(bn._PERCENTILE_POINTS)  # keep in sync with the canonical source
_P50_IDX = _PCT.index(50)
_P2_5_IDX = _PCT.index(2.5)
_P97_5_IDX = _PCT.index(97.5)
_CH = ["Cz", "Pz"]
_FREQS = np.array([2.0, 4.0, 8.0, 16.0, 32.0])
_TRUE_MEAN = np.array([1.0, 0.8, 0.5, 0.0, -0.5])  # per-freq log10(µV²/Hz)
_TRUE_SD = 0.4


def _write_psd_checkpoint(psd_dir, subject_id, condition, log10_uv2):
    """log10_uv2: (n_ch, n_freq). Stored as V²/Hz, since the writer multiplies by 1e12."""
    uv2 = 10.0 ** log10_uv2          # µV²/Hz
    v2 = uv2 * 1e-12                 # → V²/Hz
    bn.save_psd_checkpoint(psd_dir, subject_id, condition, _FREQS, v2.astype(np.float64), _CH)


def _build(tmp_path, seed, n_full=400):
    rng = np.random.default_rng(seed)
    psd_dir = tmp_path / "psd_checkpoints"
    psd_dir.mkdir()
    subjects = []
    # bin "20-29": n_full near-normal subjects in log space
    for i in range(n_full):
        vals = _TRUE_MEAN[None, :] + rng.normal(0.0, _TRUE_SD, size=(len(_CH), len(_FREQS)))
        sid = f"sub-{i:04d}"
        _write_psd_checkpoint(psd_dir, sid, "ec", vals)
        subjects.append({"subject_id": sid, "condition": "ec", "age": 25})
    # bin "30-39": a single subject (n=1) → percentiles + normality must be NaN
    _write_psd_checkpoint(psd_dir, "sub-9000", "ec",
                          _TRUE_MEAN[None, :] + np.zeros((len(_CH), len(_FREQS))))
    subjects.append({"subject_id": "sub-9000", "condition": "ec", "age": 35})
    # bin "40-49": exactly 2 subjects → percentiles present, normality_p NaN (n<3)
    for j in range(2):
        vals = _TRUE_MEAN[None, :] + rng.normal(0.0, _TRUE_SD, size=(len(_CH), len(_FREQS)))
        sid = f"sub-95{j:02d}"
        _write_psd_checkpoint(psd_dir, sid, "ec", vals)
        subjects.append({"subject_id": sid, "condition": "ec", "age": 45})
    out = tmp_path / "norms_psd.npz"
    bn.build_normative_psd(psd_dir, subjects, [20, 30, 40, 50], out, logging.getLogger("test"))
    return np.load(out, allow_pickle=False)


def test_new_arrays_present_and_shaped(tmp_path):
    d = _build(tmp_path, 0)
    for k in ["freqs", "bins", "conditions", "ch_names", "mean", "sd", "n",
              "percentile_points", "percentiles", "normality_p", "psd_format_version"]:
        assert k in d.files, f"missing {k}"
    assert int(d["psd_format_version"]) == 2
    np.testing.assert_allclose(d["percentile_points"], _PCT)
    n_bins, n_cond, n_ch, n_freq = d["mean"].shape
    assert d["percentiles"].shape == (n_bins, n_cond, n_ch, n_freq, 13)
    assert d["percentiles"].dtype == np.float32
    assert d["normality_p"].shape == (n_bins, n_cond, n_ch, n_freq)
    assert d["normality_p"].dtype == np.float32


def test_p50_matches_mean(tmp_path):
    d = _build(tmp_path, 1)
    p50 = d["percentiles"][0, 0, :, :, _P50_IDX]
    np.testing.assert_allclose(p50, d["mean"][0, 0], atol=0.1)


def test_monotonic_along_points(tmp_path):
    d = _build(tmp_path, 2)
    diffs = np.diff(d["percentiles"][0, 0], axis=-1)  # (n_ch, n_freq, 12)
    assert np.all(diffs >= -1e-6)


def test_tails_bracket_two_sigma(tmp_path):
    d = _build(tmp_path, 3)
    mean, sd = d["mean"][0, 0], d["sd"][0, 0]
    p2_5 = d["percentiles"][0, 0, :, :, _P2_5_IDX]
    p97_5 = d["percentiles"][0, 0, :, :, _P97_5_IDX]
    assert np.all((p2_5 > mean - 2.5 * sd) & (p2_5 < mean - 1.4 * sd))
    assert np.all((p97_5 < mean + 2.5 * sd) & (p97_5 > mean + 1.4 * sd))


def test_nan_where_insufficient_n(tmp_path):
    d = _build(tmp_path, 4)
    assert int(d["n"][1, 0]) == 1                       # bin "30-39"
    assert np.all(np.isnan(d["percentiles"][1, 0]))     # n < 2
    assert np.all(np.isnan(d["normality_p"][1, 0]))     # n < 3


def test_existing_arrays_unchanged(tmp_path):
    d = _build(tmp_path, 5)
    assert d["mean"].dtype == np.float64
    assert d["sd"].dtype == np.float64
    assert list(d["ch_names"]) == _CH
    assert int(d["n"][0, 0]) == 400


def test_n2_bin_has_percentiles_but_no_normality(tmp_path):
    d = _build(tmp_path, 6)
    assert int(d["n"][2, 0]) == 2                       # bin "40-49"
    assert not np.all(np.isnan(d["percentiles"][2, 0]))  # n >= 2 → present
    assert np.all(np.isnan(d["normality_p"][2, 0]))      # n < 3 → NaN


def test_unit_guard_flags_misscaled_checkpoint(tmp_path, caplog):
    """A checkpoint stored in µV²/Hz (not V²/Hz) must trigger the unit-sanity warning."""
    psd_dir = tmp_path / "psd_checkpoints"
    psd_dir.mkdir()
    subjects = []
    # clean subject: proper V²/Hz scale
    _write_psd_checkpoint(psd_dir, "sub-clean", "ec",
                          _TRUE_MEAN[None, :] + np.zeros((len(_CH), len(_FREQS))))
    subjects.append({"subject_id": "sub-clean", "condition": "ec", "age": 25})
    # mis-scaled subject: store µV²/Hz directly (~1e0, i.e. ~1e12 too large)
    bad_uv2 = 10.0 ** (_TRUE_MEAN[None, :] + np.zeros((len(_CH), len(_FREQS))))
    bn.save_psd_checkpoint(psd_dir, "sub-bad", "ec", _FREQS, bad_uv2.astype(np.float64), _CH)
    subjects.append({"subject_id": "sub-bad", "condition": "ec", "age": 25})

    out = tmp_path / "norms_psd.npz"
    with caplog.at_level(logging.WARNING):
        bn.build_normative_psd(psd_dir, subjects, [20, 30], out, logging.getLogger("unitguard"))

    warnings_text = " ".join(r.message for r in caplog.records)
    assert "Unit-sanity" in warnings_text
    assert "sub-bad" in warnings_text       # mis-scaled one flagged
    assert "sub-clean" not in warnings_text  # clean one not flagged
