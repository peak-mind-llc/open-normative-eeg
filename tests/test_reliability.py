"""Tests for open_normative.reliability — test-retest reliability,
reliable-change, and heteroscedasticity (Wood et al. 2024, Simulation 2)."""

import math

import numpy as np

from open_normative.reliability import (
    icc_2_1,
    sem_from_icc,
    mdc95,
    bland_altman,
    heteroscedasticity_slope,
    paired_reliability,
    build_paired_arrays,
    summarize_reliability,
)


def test_icc_perfect_agreement():
    x = np.array([1.0, 2, 3, 4, 5, 6, 7, 8], dtype=float)
    assert abs(icc_2_1(x, x.copy()) - 1.0) < 1e-9


def test_icc_independent_noise_near_zero():
    rng = np.random.RandomState(0)
    x1 = rng.normal(0, 1, 300)
    x2 = rng.normal(0, 1, 300)
    assert abs(icc_2_1(x1, x2)) < 0.25


def test_sem_from_icc_formula():
    vals = np.array([0.0, 2.0, 4.0, 6.0])  # std (ddof=1) = sqrt(20/3) ≈ 2.582
    sd = float(np.std(vals, ddof=1))
    assert abs(sem_from_icc(vals, 0.75) - sd * math.sqrt(0.25)) < 1e-9


def test_mdc95_formula():
    # MDC95 = z_{.975} * sqrt(2) * SEM; ~1.96*sqrt(2) with the rounded z.
    assert abs(mdc95(1.0) - 1.96 * math.sqrt(2.0)) < 1e-3


def test_bland_altman_bias_and_loa():
    x1 = np.array([10.0, 20, 30])
    x2 = np.array([12.0, 22, 32])  # constant +2 bias, zero variance of diff
    ba = bland_altman(x1, x2)
    assert abs(ba["bias"] - 2.0) < 1e-9
    assert abs(ba["loa_lower"] - 2.0) < 1e-9
    assert abs(ba["loa_upper"] - 2.0) < 1e-9


def test_heteroscedastic_diffs_have_positive_slope():
    """Multiplicative noise → spread of differences grows with level."""
    rng = np.random.RandomState(1)
    x1 = rng.uniform(1, 100, 400)
    x2 = x1 + rng.normal(0, 1, 400) * x1 * 0.2
    het = heteroscedasticity_slope(x1, x2)
    assert het["slope"] > 0
    assert het["p"] < 0.01
    assert het["tail_center_var_ratio"] > 1.5


def test_homoscedastic_diffs_have_flat_slope():
    rng = np.random.RandomState(2)
    x1 = rng.uniform(1, 100, 400)
    x2 = x1 + rng.normal(0, 5, 400)
    het = heteroscedasticity_slope(x1, x2)
    assert het["p"] > 0.05


def test_paired_reliability_keys_and_perfect_icc():
    x = np.array([1.0, 2, 3, 4, 5, 6, 7, 8])
    r = paired_reliability(x, x.copy())
    for k in ["n", "icc", "sem", "mdc95", "frac_exceeding_mdc",
              "bias", "ba_slope", "loa_lower", "loa_upper"]:
        assert k in r
    assert r["n"] == 8
    assert abs(r["icc"] - 1.0) < 1e-9
    assert abs(r["mdc95"]) < 1e-9          # perfect reliability → no detectable change
    assert r["frac_exceeding_mdc"] == 0.0


def test_build_paired_arrays_pairs_only_complete_subjects():
    def rec(subj, ses, val):
        return {
            "subject_id": subj, "session": ses, "condition": "ec",
            "metrics": {"Fz": {"Alpha": {"absolute_power": val}}},
        }
    records = [
        rec("sub-01", "session1", 10.0), rec("sub-01", "session2", 11.0),
        rec("sub-02", "session1", 20.0), rec("sub-02", "session2", 19.0),
        rec("sub-03", "session1", 30.0),  # missing session2 → excluded
    ]
    pairs = build_paired_arrays(records, sessions=("session1", "session2"))
    key = ("ec", "Fz", "Alpha", "absolute_power")
    assert key in pairs
    x1, x2 = pairs[key]
    assert list(x1) == [10.0, 20.0]
    assert list(x2) == [11.0, 19.0]


def test_trt_loader_multisession(tmp_path):
    from open_normative.datasets.trt import TRTLoader
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tage\tsex\nsub-01\t25\tm\n"
    )
    for ses in ("session1", "session2"):
        d = tmp_path / "sub-01" / f"ses-{ses}" / "eeg"
        d.mkdir(parents=True)
        (d / f"sub-01_ses-{ses}_task-eyesclosed_eeg.vhdr").write_text("")
        (d / f"sub-01_ses-{ses}_task-eyesopen_eeg.vhdr").write_text("")

    loader = TRTLoader()
    recs = list(loader.iter_subject_files(tmp_path, sessions=("session1", "session2")))
    assert len(recs) == 4  # 2 sessions × 2 conditions
    assert sorted({r.metadata["session"] for r in recs}) == ["session1", "session2"]
    # Default is unchanged: session 1 only.
    default = list(loader.iter_subject_files(tmp_path))
    assert {r.metadata["session"] for r in default} == {"session1"}


def test_summarize_reliability_counts():
    rows = [
        {"icc": 0.95, "ba_slope": 0.1, "ba_slope_p": 0.5, "frac_exceeding_mdc": 0.04},
        {"icc": 0.50, "ba_slope": 0.8, "ba_slope_p": 0.001, "frac_exceeding_mdc": 0.30},
        {"icc": 0.60, "ba_slope": -0.2, "ba_slope_p": 0.2, "frac_exceeding_mdc": 0.10},
        {"icc": 0.80, "ba_slope": 0.3, "ba_slope_p": 0.01, "frac_exceeding_mdc": 0.06},
    ]
    s = summarize_reliability(rows, low_icc=0.70)
    assert s["n_metrics"] == 4
    assert abs(s["median_icc"] - 0.70) < 1e-9   # median of [0.5,0.6,0.8,0.95]
    assert s["n_low_icc"] == 2                  # 0.50 and 0.60
    # significant positive BA slope: rows 2 (0.001) and 4 (0.01)
    assert s["n_heteroscedastic"] == 2
