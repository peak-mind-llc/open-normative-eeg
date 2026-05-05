"""Tests for spectral analysis functions."""

import numpy as np
import pytest
from open_normative.parameters import PIPELINE_PARAMS
from open_normative.spectral import (
    compute_psd,
    compute_band_power,
    compute_band_ratios,
    compute_aperiodic,
    compute_corrected_band_power,
    compute_asymmetry,
    analyze_spectral,
)


def test_compute_psd(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    assert psds.shape[0] == 19
    assert len(freqs) > 0
    assert freqs[0] >= 0
    assert freqs[-1] <= params["fmax"] + 1


def test_compute_band_power(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    bands = params["bands"]
    band_power = compute_band_power(psds, freqs, bands)
    assert "Alpha" in band_power
    assert "absolute" in band_power["Alpha"]
    assert "relative" in band_power["Alpha"]
    assert len(band_power["Alpha"]["absolute"]) == 19


def test_compute_band_power_relative_sums():
    """Relative power of non-overlapping bands should sum to ~1."""
    n_ch = 5
    n_freqs = 200
    freqs = np.linspace(0.5, 50.0, n_freqs)
    psds = np.ones((n_ch, n_freqs)) * 1e-12
    bands = {
        "Delta": [1, 4],
        "Theta": [4, 8],
        "Alpha": [8, 13],
        "Beta": [13, 30],
        "Gamma": [30, 50],
    }
    bp = compute_band_power(psds, freqs, bands)
    total_rel = sum(bp[b]["relative"][0] for b in bands)
    assert abs(total_rel - 1.0) < 0.05


def test_compute_band_ratios(mock_band_power):
    ch_names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T3", "C3", "Cz", "C4", "T4",
        "T5", "P3", "Pz", "P4", "T6",
        "O1", "O2",
    ]
    ratio_defs = PIPELINE_PARAMS["spectral"]["ratios"]
    ratios = compute_band_ratios(mock_band_power, ch_names, ratio_defs)
    expected_names = {
        "Theta/Beta", "Theta/Beta1", "Delta/HighBeta", "Alpha/HighBeta",
        "Alpha/Theta", "Delta/Alpha", "Alpha/Beta",
        "(Delta+Theta)/(Alpha+Beta)",
    }
    assert expected_names.issubset(ratios.keys())
    assert "Fp1" in ratios["Theta/Beta"]
    assert ratios["Theta/Beta"]["Fp1"] > 0


def test_compute_band_ratios_composite():
    """DTABR = (Delta+Theta)/(Alpha+Beta) — composite numerator and denominator."""
    bp = {
        "Delta": {"absolute": np.array([1.0, 2.0])},
        "Theta": {"absolute": np.array([3.0, 4.0])},
        "Alpha": {"absolute": np.array([5.0, 6.0])},
        "Beta":  {"absolute": np.array([7.0, 8.0])},
    }
    ratio_defs = [
        {"name": "DTABR", "num": ["Delta", "Theta"], "den": ["Alpha", "Beta"]},
    ]
    ratios = compute_band_ratios(bp, ["A", "B"], ratio_defs)
    # ch A: (1+3)/(5+7) = 4/12 = 0.3333
    # ch B: (2+4)/(6+8) = 6/14 = 0.4286
    assert ratios["DTABR"]["A"] == pytest.approx(4 / 12)
    assert ratios["DTABR"]["B"] == pytest.approx(6 / 14)


def test_compute_band_ratios_zero_denominator():
    """Sum-of-bands denominator of 0 should yield NaN, not divide-by-zero."""
    bp = {
        "Delta": {"absolute": np.array([1.0])},
        "Theta": {"absolute": np.array([2.0])},
        "Alpha": {"absolute": np.array([0.0])},
        "Beta":  {"absolute": np.array([0.0])},
    }
    ratio_defs = [
        {"name": "DTABR", "num": ["Delta", "Theta"], "den": ["Alpha", "Beta"]},
    ]
    ratios = compute_band_ratios(bp, ["A"], ratio_defs)
    assert np.isnan(ratios["DTABR"]["A"])


def test_compute_aperiodic(synthetic_raw_19ch):
    pytest.importorskip("specparam", reason="specparam not installed")
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    ap_results = compute_aperiodic(psds, freqs, synthetic_raw_19ch.ch_names, params["aperiodic"])
    assert "Fp1" in ap_results
    assert "exponent" in ap_results["Fp1"]
    assert "slope" in ap_results["Fp1"]
    assert "r_squared" in ap_results["Fp1"]
    # slope = -exponent; for 1/f data, exponent > 0 so slope < 0
    assert ap_results["Fp1"]["slope"] < 0


def test_compute_asymmetry(mock_band_power):
    ch_names = [
        "Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8",
        "T3", "C3", "Cz", "C4", "T4",
        "T5", "P3", "Pz", "P4", "T6",
        "O1", "O2",
    ]
    pairs = PIPELINE_PARAMS["spectral"]["asymmetry"]["homologous_pairs"]
    asym = compute_asymmetry(mock_band_power, ch_names, pairs)
    assert "F3/F4" in asym
    assert "Alpha" in asym["F3/F4"]
    for pair in asym:
        for band in asym[pair]:
            assert -1.0 <= asym[pair][band] <= 1.0


def test_compute_corrected_band_power(synthetic_raw_19ch):
    pytest.importorskip("specparam", reason="specparam not installed")
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    aperiodic = compute_aperiodic(psds, freqs, synthetic_raw_19ch.ch_names, params["aperiodic"])
    corrected = compute_corrected_band_power(
        psds, freqs, aperiodic, synthetic_raw_19ch.ch_names, params["bands"]
    )
    assert "Alpha" in corrected
    assert "corrected_absolute" in corrected["Alpha"]
    assert "corrected_relative" in corrected["Alpha"]
    assert len(corrected["Alpha"]["corrected_absolute"]) == 19
    # Corrected power should be non-negative (or NaN for failed fits)
    for band in corrected:
        vals = corrected[band]["corrected_absolute"]
        finite_vals = vals[np.isfinite(vals)]
        if len(finite_vals) > 0:
            assert np.all(finite_vals >= 0)


def test_corrected_power_differs_from_uncorrected(synthetic_raw_19ch):
    """Corrected power should differ from uncorrected (aperiodic removed)."""
    pytest.importorskip("specparam", reason="specparam not installed")
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    band_power = compute_band_power(psds, freqs, params["bands"])
    aperiodic = compute_aperiodic(psds, freqs, synthetic_raw_19ch.ch_names, params["aperiodic"])
    corrected = compute_corrected_band_power(
        psds, freqs, aperiodic, synthetic_raw_19ch.ch_names, params["bands"]
    )
    # Corrected absolute should be smaller than uncorrected (aperiodic removed)
    alpha_uncorrected = band_power["Alpha"]["absolute"]
    alpha_corrected = corrected["Alpha"]["corrected_absolute"]
    finite_mask = np.isfinite(alpha_corrected)
    if np.any(finite_mask):
        # Corrected power should be less than uncorrected (periodic < full PSD)
        assert np.all(alpha_corrected[finite_mask] < alpha_uncorrected[finite_mask])


def test_corrected_band_power_nan_on_failed_fit(synthetic_raw_19ch):
    """Channels with failed specparam fits should get NaN corrected values."""
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    # Simulate all-failed aperiodic fits
    ch_names = synthetic_raw_19ch.ch_names
    failed_aperiodic = {ch: {
        "exponent": np.nan, "offset": np.nan, "slope": np.nan,
        "r_squared": 0.0, "fit_quality": "failed",
    } for ch in ch_names}
    corrected = compute_corrected_band_power(
        psds, freqs, failed_aperiodic, ch_names, params["bands"]
    )
    for band in corrected:
        assert np.all(np.isnan(corrected[band]["corrected_absolute"]))


def test_analyze_spectral_returns_all_metrics(synthetic_raw_19ch):
    params = PIPELINE_PARAMS["spectral"]
    result = analyze_spectral(synthetic_raw_19ch, params)
    assert "psds" in result
    assert "freqs" in result
    assert "band_power" in result
    assert "corrected_band_power" in result
    assert "ratios" in result
    assert "corrected_ratios" in result
    assert "aperiodic" in result
    assert "asymmetry" in result
    assert "gsf" in result
    assert "gsf_band_power" in result
    assert "iaf" in result


def test_compute_gsf(synthetic_raw_19ch):
    from open_normative.spectral import compute_gsf, compute_psd
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    gsf, corrected = compute_gsf(psds, freqs)
    assert isinstance(gsf, float)
    assert corrected.shape == psds.shape
    # After GSF correction, mean of log10(corrected) should be ~0
    assert abs(np.mean(np.log10(np.maximum(corrected, 1e-30)))) < 1e-10


def test_compute_gsf_band_power(synthetic_raw_19ch):
    from open_normative.spectral import (
        compute_gsf, compute_gsf_band_power, compute_psd
    )
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    _, gsf_psds = compute_gsf(psds, freqs)
    gsf_bp = compute_gsf_band_power(gsf_psds, freqs, params["bands"])
    assert "Alpha" in gsf_bp
    assert "gsf_absolute" in gsf_bp["Alpha"]
    assert "gsf_relative" in gsf_bp["Alpha"]
    assert len(gsf_bp["Alpha"]["gsf_absolute"]) == 19


def test_compute_iaf(synthetic_raw_19ch):
    from open_normative.spectral import (
        compute_iaf, compute_psd, compute_aperiodic
    )
    params = PIPELINE_PARAMS["spectral"]
    psds, freqs = compute_psd(synthetic_raw_19ch, params)
    # Use mock aperiodic with no peaks (specparam not installed)
    aperiodic = {ch: {"peak_params": [], "fit_quality": "skipped"}
                 for ch in synthetic_raw_19ch.ch_names}
    iaf = compute_iaf(psds, freqs, list(synthetic_raw_19ch.ch_names),
                      aperiodic, params.get("iaf", {}))
    assert "per_channel" in iaf
    assert "global_cog" in iaf
    # CoG should be in alpha range since synthetic data has 10 Hz peak
    assert 7 <= iaf["global_cog"] <= 14
    # No peaks detected (no specparam), so global_peak should be None
    assert iaf["global_peak"] is None


def test_normative_includes_asymmetry(mock_subject_metrics):
    from open_normative.normative import build_normative
    norms = build_normative(mock_subject_metrics)
    asym_cells = [c for c in norms if c.channel == "F3/F4"]
    assert len(asym_cells) > 0
    assert any(c.metric == "asymmetry_index" for c in asym_cells)


def test_norm_cell_has_ci(mock_subject_metrics):
    from open_normative.normative import build_normative
    norms = build_normative(mock_subject_metrics)
    cells_with_ci = [c for c in norms if c.ci_lower is not None]
    assert len(cells_with_ci) > 0
    for c in cells_with_ci:
        assert c.ci_lower < c.mean
        assert c.ci_upper > c.mean


def test_fdr_correction():
    from open_normative.compare import ComparisonResult, apply_fdr_correction
    # Create results with a mix of significant and non-significant z-scores
    results = []
    for i in range(20):
        z = 0.5  # not significant
        results.append(ComparisonResult(
            channel="Fz", band="Alpha", metric="absolute_power",
            value=1.0, z_score=z, percentile_rank=50.0,
            norm_mean=1.0, norm_sd=1.0, norm_n=50,
            bin="20-29", low_confidence=False,
        ))
    # Add a few extreme values
    for z in [3.5, -4.0, 3.0]:
        results.append(ComparisonResult(
            channel="Fz", band="Theta", metric="absolute_power",
            value=1.0, z_score=z, percentile_rank=99.0,
            norm_mean=1.0, norm_sd=1.0, norm_n=50,
            bin="20-29", low_confidence=False,
        ))
    apply_fdr_correction(results)
    sig = [r for r in results if r.fdr_significant]
    non_sig = [r for r in results if r.fdr_significant is False]
    # The 3 extreme z-scores should survive FDR
    assert len(sig) == 3
    assert len(non_sig) == 20


# ---------------------------------------------------------------------------
# Clinical transparency tests (SE(z), Cohen's d, severity, PI, patterns)
# ---------------------------------------------------------------------------


def test_compute_se_z():
    from open_normative.compare import compute_se_z
    import math
    se = compute_se_z(2.0, 50)
    expected = math.sqrt(1/50 + 4/(2*50))
    assert abs(se - expected) < 1e-10
    assert compute_se_z(0.0, 1) is None  # n < 2


def test_cohen_d_classification():
    from open_normative.compare import classify_cohen_d
    assert classify_cohen_d(0.1) == "negligible"
    assert classify_cohen_d(0.3) == "small"
    assert classify_cohen_d(0.6) == "medium"
    assert classify_cohen_d(1.5) == "large"
    assert classify_cohen_d(-0.9) == "large"  # uses absolute value


def test_severity_labels():
    from open_normative.compare import assign_severity_label
    assert assign_severity_label(0.3) == "Within typical limits"
    assert assign_severity_label(0.7) == "Mildly atypical"
    assert assign_severity_label(1.2) == "Moderately atypical"
    assert assign_severity_label(1.8) == "Notably atypical"
    assert assign_severity_label(2.5) == "Markedly atypical"
    assert assign_severity_label(4.0) == "Extremely atypical"
    assert assign_severity_label(-2.5) == "Markedly atypical"  # uses abs


def test_prediction_interval_wider_than_ci(mock_subject_metrics):
    from open_normative.normative import build_normative
    norms = build_normative(mock_subject_metrics)
    for c in norms:
        if c.ci_lower is not None and c.pi_lower is not None:
            assert c.pi_lower < c.ci_lower, "PI should be wider than CI"
            assert c.pi_upper > c.ci_upper, "PI should be wider than CI"


def test_global_pattern_detection():
    from open_normative.compare import (
        ComparisonResult, EnrichedResult, detect_global_patterns
    )
    from open_normative.parameters import PIPELINE_PARAMS
    channels = PIPELINE_PARAMS["channels"]["channels_19"]
    # All 19 channels elevated in Alpha
    enriched = []
    for ch in channels:
        r = ComparisonResult(
            channel=ch, band="Alpha", metric="absolute_power",
            value=50.0, z_score=2.5, percentile_rank=99.0,
            norm_mean=20.0, norm_sd=10.0, norm_n=50,
            bin="20-29", low_confidence=False,
        )
        enriched.append(EnrichedResult(base=r))
    patterns = detect_global_patterns(enriched, channels)
    assert len(patterns) >= 1
    assert patterns[0]["direction"] == "elevated"
    assert patterns[0]["fraction"] >= 0.6


def test_cluster_detection():
    from open_normative.compare import (
        ComparisonResult, EnrichedResult, detect_deviation_clusters
    )
    from open_normative.parameters import REPORT_PARAMS
    adjacency = REPORT_PARAMS["adjacency_19"]
    # O1, O2, P3 are all adjacent — create a cluster
    enriched = []
    for ch in ["O1", "O2", "P3"]:
        r = ComparisonResult(
            channel=ch, band="Theta", metric="absolute_power",
            value=50.0, z_score=2.5, percentile_rank=99.0,
            norm_mean=20.0, norm_sd=10.0, norm_n=50,
            bin="20-29", low_confidence=False,
        )
        enriched.append(EnrichedResult(base=r))
    clusters = detect_deviation_clusters(enriched, adjacency)
    assert len(clusters) >= 1
    assert set(clusters[0].channels) == {"O1", "O2", "P3"}


def test_metric_disagreement():
    from open_normative.compare import (
        ComparisonResult, EnrichedResult, detect_metric_disagreements
    )
    enriched = [
        EnrichedResult(base=ComparisonResult(
            channel="Fz", band="Alpha", metric="absolute_power",
            value=50.0, z_score=2.5, percentile_rank=99.0,
            norm_mean=20.0, norm_sd=10.0, norm_n=50,
            bin="20-29", low_confidence=False,
        )),
        EnrichedResult(base=ComparisonResult(
            channel="Fz", band="Alpha", metric="corrected_absolute_power",
            value=18.0, z_score=-0.3, percentile_rank=40.0,
            norm_mean=20.0, norm_sd=10.0, norm_n=50,
            bin="20-29", low_confidence=False,
        )),
    ]
    disagreements = detect_metric_disagreements(enriched)
    assert len(disagreements) == 1
    assert disagreements[0]["channel"] == "Fz"
    assert "aperiodic" in disagreements[0]["interpretation"]


def test_comparison_report_to_dict(mock_subject_metrics):
    import json
    from open_normative.normative import build_normative
    from open_normative.compare import compare_and_report
    norms = build_normative(mock_subject_metrics)
    metrics = {
        "Fz": {
            "Alpha": {"absolute_power": 50.0, "relative_power": 0.35},
            "Theta": {"absolute_power": 20.0, "relative_power": 0.15},
        },
    }
    report = compare_and_report(metrics, norms, age=30, condition="eo")
    d = report.to_dict()
    # Should be JSON-serializable
    json_str = json.dumps(d)
    assert len(json_str) > 0
    assert "metadata" in d
    assert "results" in d
    assert "patterns" in d
    assert d["metadata"]["total_tests"] >= 0


def test_comparison_report_summary_text(mock_subject_metrics):
    from open_normative.normative import build_normative
    from open_normative.compare import compare_and_report
    norms = build_normative(mock_subject_metrics)
    metrics = {
        "Fz": {
            "Alpha": {"absolute_power": 50.0},
            "Theta": {"absolute_power": 20.0},
        },
    }
    report = compare_and_report(metrics, norms, age=30, condition="eo")
    text = report.summary_text()
    assert "Comparison Report" in text
    assert "tests performed" in text
