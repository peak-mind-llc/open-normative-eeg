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
    ratios = compute_band_ratios(mock_band_power, ch_names)
    assert "Theta/Beta" in ratios
    assert "Fp1" in ratios["Theta/Beta"]
    assert ratios["Theta/Beta"]["Fp1"] > 0


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
