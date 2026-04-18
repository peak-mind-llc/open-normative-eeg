"""Regression test: specparam fitting is bit-identical on the same machine.

The AWS-Batch reproducibility gate depends on per-subject checkpoints matching
across runs. scipy's LM fit is deterministic, but we want this asserted in
CI so a future accidentally-unseeded RNG doesn't silently break identity.

Cross-machine bit-identity requires BLAS thread pinning
(OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1); that's enforced in
the container entrypoint, not here.
"""
import numpy as np
import pytest

from open_normative.spectral import compute_aperiodic


@pytest.fixture
def synthetic_psds():
    """Deterministic synthetic PSDs for 19 channels, 1–50 Hz at 0.25 Hz res."""
    rng = np.random.RandomState(42)
    freqs = np.arange(1.0, 50.25, 0.25)
    # 1/f^exponent aperiodic background + alpha bump at 10 Hz
    n_ch = 19
    psds = np.zeros((n_ch, len(freqs)))
    for i in range(n_ch):
        exp = 1.0 + 0.1 * rng.randn()
        offset = -20 + 0.5 * rng.randn()
        background = 10 ** (offset - exp * np.log10(freqs))
        alpha = 2e-11 * np.exp(-((freqs - 10.0) ** 2) / 2.0)
        noise = background * (1.0 + 0.05 * rng.randn(len(freqs)))
        psds[i] = noise + alpha
    ch_names = [f"ch{i:02d}" for i in range(n_ch)]
    return freqs, psds, ch_names


def test_specparam_fit_is_bit_identical(synthetic_psds):
    freqs, psds, ch_names = synthetic_psds
    params = {
        "freq_range": [2, 40],
        "peak_width_limits": [1, 8],
        "max_n_peaks": 6,
        "min_peak_height": 0.1,
        "peak_threshold": 2.0,
        "r_squared_threshold": 0.85,
    }
    a = compute_aperiodic(psds, freqs, ch_names, params)
    b = compute_aperiodic(psds, freqs, ch_names, params)

    assert set(a) == set(b)
    for ch in ch_names:
        for key in ("exponent", "offset", "r_squared", "n_peaks"):
            av, bv = a[ch][key], b[ch][key]
            # NaN-safe equality
            if isinstance(av, float) and np.isnan(av):
                assert np.isnan(bv), f"{ch}.{key}: NaN vs {bv}"
            else:
                assert av == bv, f"{ch}.{key}: {av!r} vs {bv!r}"
        # peak_params is a list-of-lists; compare element-by-element as floats
        assert a[ch]["peak_params"] == b[ch]["peak_params"], (
            f"{ch} peak_params differ"
        )
