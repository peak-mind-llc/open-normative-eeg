"""metadata.json includes canonical roi_order / roi_labels / ba_order when
the bundle contains source connectivity cells; the keys are absent when
those categories are empty."""

import json
from pathlib import Path

from open_normative.io import write_norms_npz
from open_normative.normative import NormCell
from open_normative.source import BA_ORDER, ROI_DEFINITIONS, ROI_NAMES


def _cell(channel: str, **overrides) -> NormCell:
    base = dict(
        bin="20-29", condition="ec", channel=channel,
        band="Alpha", metric="source_dwpli",
        n=10, mean=1.0, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={}, sex="pooled",
    )
    base.update(overrides)
    return NormCell(**base)


def test_roi_order_present_when_src_conn_cells_exist(tmp_path: Path):
    cells = [
        _cell("_src_conn_DLPFC_L_ACC"),
        _cell("Fz", metric="absolute_power"),  # unrelated, must not affect roi_order
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["roi_order"] == ROI_NAMES


def test_roi_labels_present_and_match_definitions(tmp_path: Path):
    cells = [_cell("_src_conn_DLPFC_L_ACC")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_labels" in meta
    # Sample a few — full map must equal the ROI_DEFINITIONS labels.
    expected = {k: v["label"] for k, v in ROI_DEFINITIONS.items()}
    assert meta["roi_labels"] == expected


def test_ba_order_present_when_src_ba_conn_cells_exist(tmp_path: Path):
    cells = [_cell("_src_ba_conn_BA1-lh_BA4-lh", metric="source_dwpli")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert meta["ba_order"] == BA_ORDER


def test_roi_and_ba_keys_absent_when_no_source_cells(tmp_path: Path):
    """A scalp-only bundle must not emit ROI/BA ordering metadata."""
    cells = [
        _cell("Fz", metric="absolute_power"),
        _cell("Cz", metric="dwpli_node_strength"),  # routed to scalp_node_strength
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_order" not in meta
    assert "roi_labels" not in meta
    assert "ba_order" not in meta


def test_src_conn_cells_only_emit_roi_keys_not_ba(tmp_path: Path):
    """Bundle with ROI cells but no BA cells gets roi_order/roi_labels but
    not ba_order."""
    cells = [_cell("_src_conn_DLPFC_L_ACC")]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    assert "roi_order" in meta
    assert "roi_labels" in meta
    assert "ba_order" not in meta
