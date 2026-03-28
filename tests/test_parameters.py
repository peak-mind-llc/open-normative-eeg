"""Tests for pipeline parameters."""

from open_normative.parameters import PIPELINE_PARAMS


def test_pipeline_params_has_required_sections():
    required = ["preprocessing", "spectral", "connectivity"]
    for section in required:
        assert section in PIPELINE_PARAMS, f"Missing section: {section}"


def test_preprocessing_filter_params():
    filt = PIPELINE_PARAMS["preprocessing"]["filter"]
    assert filt["l_freq"] == 0.5
    assert filt["h_freq"] == 100.0
    assert filt["notch_freq"] == 60.0
    assert filt["notch_harmonics"] == [120.0, 180.0]
    assert filt["notch_width"] == 2.0


def test_preprocessing_ica_params():
    ica = PIPELINE_PARAMS["preprocessing"]["ica"]
    assert ica["method"] == "picard"
    assert ica["extended"] is True
    assert ica["n_components"] == 0.999
    assert ica["max_iter"] == 500
    assert ica["random_state"] == 42
    assert ica["two_stage_filter"] is True
    assert ica["ica_highpass"] == 1.0
    assert ica["brain_threshold"] == 0.80
    assert ica["review_threshold"] == 0.50


def test_preprocessing_asr_params():
    asr = PIPELINE_PARAMS["preprocessing"]["asr"]
    assert asr["cutoff"] == 20
    assert asr["window_length"] == 0.5


def test_preprocessing_bad_channels_params():
    bc = PIPELINE_PARAMS["preprocessing"]["bad_channels"]
    assert bc["method"] == "ransac"
    assert bc["correlation_threshold"] == 0.75
    assert bc["flat_threshold_factor"] == 0.01
    assert bc["noisy_threshold_factor"] == 10.0


def test_preprocessing_resample_params():
    rs = PIPELINE_PARAMS["preprocessing"]["resample"]
    assert rs["enabled"] is True
    assert rs["target_sfreq"] == 256.0


def test_preprocessing_reference():
    assert PIPELINE_PARAMS["preprocessing"]["reference"] == "average"


def test_spectral_bands():
    bands = PIPELINE_PARAMS["spectral"]["bands"]
    assert bands["Delta"] == [1, 4]
    assert bands["Theta"] == [4, 8]
    assert bands["Alpha"] == [8, 13]
    assert bands["Alpha1"] == [8, 10.5]
    assert bands["Alpha2"] == [10.5, 13]
    assert bands["Beta"] == [13, 30]
    assert bands["Beta1"] == [13, 15]
    assert bands["Beta2"] == [15, 18]
    assert bands["Beta3"] == [18, 25]
    assert bands["HighBeta"] == [25, 30]
    assert bands["Gamma"] == [30, 50]


def test_spectral_psd_params():
    s = PIPELINE_PARAMS["spectral"]
    assert s["method"] == "welch"
    assert s["fmin"] == 0.5
    assert s["fmax"] == 50.0
    assert s["n_fft"] == 1024


def test_spectral_aperiodic_params():
    ap = PIPELINE_PARAMS["spectral"]["aperiodic"]
    assert ap["freq_range"] == [2, 40]
    assert ap["r_squared_threshold"] == 0.85
    assert ap["peak_width_limits"] == [1, 8]
    assert ap["max_n_peaks"] == 6
    assert ap["min_peak_height"] == 0.1
    assert ap["peak_threshold"] == 2.0


def test_spectral_asymmetry_params():
    asym = PIPELINE_PARAMS["spectral"]["asymmetry"]
    assert [["F3", "F4"]] == [asym["homologous_pairs"][0]]
    assert len(asym["homologous_pairs"]) == 7
    assert asym["threshold"] == 0.15


def test_spectral_ratios():
    ratios = PIPELINE_PARAMS["spectral"]["ratios"]
    assert ["Theta", "Beta"] in ratios
    assert ["Theta", "Beta1"] in ratios


def test_connectivity_params():
    conn = PIPELINE_PARAMS["connectivity"]
    assert conn["epoch_length"] == 2.0
    assert conn["epoch_overlap"] == 0.0
    assert conn["min_epochs"] == 30
    assert conn["max_epochs"] == 120
    assert conn["methods"] == ["dwpli", "coh", "imcoh"]


def test_connectivity_hubs():
    hubs = PIPELINE_PARAMS["connectivity"]["hubs"]
    assert hubs["F_mid"] == ["Fz"]
    assert hubs["F_L"] == ["F3", "F7"]
    assert hubs["O"] == ["O1", "O2"]
    assert len(hubs) == 10


def test_connectivity_cfc_params():
    cfc = PIPELINE_PARAMS["connectivity"]["cfc"]
    assert cfc["enabled"] is True
    assert cfc["phase_band"] == [4, 8]
    assert cfc["amp_band"] == [30, 45]
    assert cfc["n_bins"] == 18


def test_connectivity_graph_params():
    graph = PIPELINE_PARAMS["connectivity"]["graph"]
    assert graph["threshold_percentile"] == 75


def test_channels_config():
    ch = PIPELINE_PARAMS["channels"]
    assert ch["target_montage"] == "standard_1020"
    assert len(ch["channels_19"]) == 19
    assert "Fp1" in ch["channels_19"]
    assert ch["name_mapping"]["T7"] == "T3"
