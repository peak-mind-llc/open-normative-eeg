"""Per-electrode node-strength cells route to scalp_node_strength.npz with
the metric renamed from dwpli_node_strength/coh_node_strength to dwpli/coh."""

import json
from pathlib import Path

from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import NormCell


def _cell(channel: str, metric: str, **overrides) -> NormCell:
    base = dict(
        bin="20-29", condition="ec", channel=channel,
        band="Alpha", metric=metric,
        n=10, mean=1.0, sd=0.5,
        log_mean=None, log_sd=None, log_transformed=False,
        normality_p=None, percentiles={}, sex="pooled",
    )
    base.update(overrides)
    return NormCell(**base)


def test_node_strength_cells_land_in_scalp_node_strength_category(tmp_path: Path):
    cells = [
        _cell("Fz", "absolute_power"),
        _cell("Fz", "dwpli_node_strength"),
        _cell("Fz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    files = sorted(p.name for p in (tmp_path / "npz").glob("*.npz"))
    assert "scalp_node_strength.npz" in files
    assert "scalp_power.npz" in files


def test_node_strength_metric_renamed_to_dwpli_or_coh(tmp_path: Path):
    cells = [
        _cell("Fz", "dwpli_node_strength", mean=2.0),
        _cell("Cz", "coh_node_strength", mean=3.0),
    ]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    by_channel = {c.channel: c for c in loaded}
    # Metric is renamed; mean value round-trips so we know the right row is
    # tagged with the right channel.
    assert by_channel["Fz"].metric == "dwpli"
    assert by_channel["Fz"].mean == 2.0
    assert by_channel["Cz"].metric == "coh"
    assert by_channel["Cz"].mean == 3.0


def test_scalp_power_no_longer_contains_node_strength_rows(tmp_path: Path):
    cells = [
        _cell("Fz", "absolute_power"),
        _cell("Fz", "dwpli_node_strength"),
        _cell("Fz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    metrics_in_scalp_power = {
        c.metric for c in loaded
        if c.channel == "Fz" and c.metric in {"absolute_power", "dwpli", "coh", "dwpli_node_strength", "coh_node_strength"}
    }
    # absolute_power stays; renamed metrics live under the new category.
    assert "absolute_power" in metrics_in_scalp_power
    # No row anywhere still carries the old long form.
    assert "dwpli_node_strength" not in metrics_in_scalp_power
    assert "coh_node_strength" not in metrics_in_scalp_power


def test_metadata_unique_metrics_for_node_strength_is_clean(tmp_path: Path):
    cells = [
        _cell("Fz", "dwpli_node_strength"),
        _cell("Cz", "coh_node_strength"),
    ]
    write_norms_npz(cells, tmp_path)
    meta = json.loads((tmp_path / "npz" / "metadata.json").read_text())
    cat = meta["categories"]["scalp_node_strength"]
    assert sorted(cat["unique_metrics"]) == ["coh", "dwpli"]
