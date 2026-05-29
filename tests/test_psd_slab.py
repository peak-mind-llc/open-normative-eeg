"""build_normative_psd emits a sex-stratified slab at npz/psd_spectrum.npz."""

import json
import logging
from pathlib import Path

import numpy as np


def _write_psd_checkpoint(path: Path, freqs, psds, ch_names):
    """Mirror save_psd_checkpoint in scripts/build_norms.py."""
    np.savez_compressed(path, freqs=freqs, psds=psds, ch_names=np.array(ch_names))


def test_psd_slab_has_sex_axis(tmp_path: Path):
    from scripts.build_norms import build_normative_psd

    # Synthetic: 2 F + 2 M subjects, single condition, 4 channels, 5 freqs.
    ch_names = ["Fz", "Cz", "Pz", "Oz"]
    freqs = np.linspace(1, 30, 5)
    # Different mean power per sex so pooled-vs-F-vs-M can be distinguished.
    psd_f = np.full((4, 5), 1e-12)
    psd_m = np.full((4, 5), 1e-10)

    psd_dir = tmp_path / "psd"
    psd_dir.mkdir()
    subjects = []
    for sid, age, sex, psd in [
        ("s01", 25, "F", psd_f),
        ("s02", 27, "F", psd_f),
        ("s03", 26, "M", psd_m),
        ("s04", 28, "M", psd_m),
    ]:
        _write_psd_checkpoint(psd_dir / f"{sid}_ec_psd.npz", freqs, psd, ch_names)
        subjects.append({"subject_id": sid, "age": age, "sex": sex,
                          "condition": "ec"})

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "npz").mkdir()
    build_normative_psd(
        psd_dir, subjects, age_bins=[20, 30, 100],
        output_path=out_dir / "npz" / "psd_spectrum.npz",
        logger=logging.getLogger("test"),
    )

    arr = np.load(out_dir / "npz" / "psd_spectrum.npz")
    # age_bins=[20, 30, 100] → 2 bins ("20-29", "30-99"); all subjects are 25-28
    # Axis order: (n_bins, n_conds, 3 sex, n_channels, n_freqs)
    assert arr["mean"].shape == (2, 1, 3, 4, 5)
    assert list(arr["sexes"]) == ["pooled", "F", "M"]
    pooled_idx = list(arr["sexes"]).index("pooled")
    f_idx = list(arr["sexes"]).index("F")
    m_idx = list(arr["sexes"]).index("M")
    # bin 0 ("20-29") has all 4 subjects
    # F slice mean ≈ log10(1e-12 * 1e12) = log10(1.0) = 0
    assert np.allclose(arr["mean"][0, 0, f_idx, :, :], 0.0, atol=1e-6)
    # M slice mean ≈ log10(1e-10 * 1e12) = log10(100) = 2
    assert np.allclose(arr["mean"][0, 0, m_idx, :, :], 2.0, atol=1e-6)
    # Pooled is the mean of all 4 subjects' log10 PSDs = mean(0, 0, 2, 2) = 1
    assert np.allclose(arr["mean"][0, 0, pooled_idx, :, :], 1.0, atol=1e-6)


def test_metadata_lists_psd_spectrum_category(tmp_path: Path):
    """After build_normative_psd writes the slab, metadata.json gets an entry."""
    from scripts.build_norms import register_psd_spectrum_in_metadata
    npz_dir = tmp_path
    # Pre-existing metadata.json (typical for a v2 run that already wrote
    # write_norms_npz output).
    (npz_dir / "metadata.json").write_text(json.dumps({
        "format_version": 3,
        "total_cells": 0,
        "categories": {},
        "age_bins": ["20-29"],
        "conditions": ["ec"],
    }))
    # And a slab file at the expected path.
    slab_path = npz_dir / "psd_spectrum.npz"
    np.savez_compressed(slab_path,
        freqs=np.linspace(1, 30, 5),
        bins=np.array(["20-29"]),
        conditions=np.array(["ec"]),
        sexes=np.array(["pooled", "F", "M"]),
        ch_names=np.array(["Fz"]),
        mean=np.zeros((1, 1, 3, 1, 5)),
    )
    register_psd_spectrum_in_metadata(npz_dir)
    meta = json.loads((npz_dir / "metadata.json").read_text())
    cat = meta["categories"]["psd_spectrum"]
    assert cat["file"] == "psd_spectrum.npz"
    assert cat["layout"] == "slab"
    assert sorted(cat["unique_sexes"]) == ["F", "M", "pooled"]
    assert cat["n_freqs"] == 5
    assert cat["n_channels"] == 1
