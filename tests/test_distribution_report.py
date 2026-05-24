"""Tests for scripts/distribution_report.py — the qEEG distribution
disclosure report (Wood et al. 2024)."""

import importlib.util
from pathlib import Path

import pytest

from open_normative.normative import NormCell

_SPEC = importlib.util.spec_from_file_location(
    "distribution_report",
    Path(__file__).resolve().parent.parent / "scripts" / "distribution_report.py",
)
dr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dr)


def _cell(metric, log, skew, kurt, norm_p, tnorm, percentiles=None):
    return NormCell(
        bin="20-29", condition="eo", channel="Fz", band="Alpha",
        metric=metric, n=50, mean=1.0, sd=0.2,
        log_mean=0.0 if log else None, log_sd=0.2 if log else None,
        log_transformed=log, normality_p=norm_p,
        percentiles=percentiles or {},
        skewness=skew, kurtosis=kurt, transform_normalized=tnorm,
    )


@pytest.fixture
def cells():
    return [
        _cell("absolute_power", True, 2.0, 5.0, 0.40, True),
        _cell("absolute_power", True, 3.0, 8.0, 0.001, False),
        _cell("relative_power", False, 0.1, 0.0, 0.60, True),
        _cell("relative_power", False, -0.2, 0.2, 0.02, False),
    ]


def test_summarize_overall(cells):
    s = dr.summarize_distribution(cells, alpha=0.05)
    o = s["overall"]
    assert o["total_cells"] == 4
    assert o["cells_with_moments"] == 4
    assert abs(o["median_abs_skewness"] - 1.1) < 1e-9
    assert abs(o["median_excess_kurtosis"] - 2.6) < 1e-9
    assert abs(o["frac_log_transformed"] - 0.5) < 1e-9
    assert abs(o["frac_non_normal"] - 0.5) < 1e-9
    assert o["n_transform_failed"] == 2
    assert abs(o["frac_transform_failed"] - 0.5) < 1e-9


def test_summarize_by_metric(cells):
    s = dr.summarize_distribution(cells, alpha=0.05)
    bm = s["by_metric"]
    assert set(bm) == {"absolute_power", "relative_power"}
    assert bm["absolute_power"]["n_cells"] == 2
    assert abs(bm["absolute_power"]["mean_abs_skewness"] - 2.5) < 1e-9
    assert abs(bm["absolute_power"]["normality_pass_rate"] - 0.5) < 1e-9
    assert abs(bm["absolute_power"]["transform_pass_rate"] - 0.5) < 1e-9


def test_worst_cells_lists_transform_failures(cells):
    s = dr.summarize_distribution(cells, alpha=0.05)
    worst = s["worst_cells"]
    # The two transform failures should surface, most-non-normal first.
    assert len(worst) >= 2
    assert worst[0]["normality_p"] == 0.001
    assert worst[0]["transform_normalized"] is False


def test_render_markdown_has_sections(cells):
    s = dr.summarize_distribution(cells, alpha=0.05)
    md = dr.render_markdown(s)
    assert "Distribution Disclosure Report" in md
    assert "Skewness" in md or "skewness" in md
    assert "absolute_power" in md
    # The headline transparency number should appear.
    assert "transform" in md.lower()
