"""End-to-end smoke test: build a tiny synthetic norm bundle, read it back,
   compare a patient against it with sex='F', verify the report carries the
   expected resolved_sex_summary."""

from pathlib import Path

import pytest

from open_normative.compare import compare_and_report
from open_normative.io import read_norms_npz, write_norms_npz
from open_normative.normative import build_normative


def test_smoke_build_write_read_compare(tmp_path: Path):
    # 6 subjects: 3 F (low alpha values ~1.0-1.2), 3 M (higher values ~2.0-2.2),
    # all in the same age bin and condition.
    subjects = []
    for sid, age, sex, val in [
        ("s01", 25, "F", 1.0), ("s02", 26, "F", 1.1), ("s03", 27, "F", 1.2),
        ("s04", 25, "M", 2.0), ("s05", 26, "M", 2.1), ("s06", 27, "M", 2.2),
    ]:
        subjects.append({"subject_id": sid, "age": age, "sex": sex,
                          "condition": "ec",
                          "metrics": {"Fz": {"Alpha": {"absolute_power": val}}}})

    norms = build_normative(subjects, age_bins=[20, 30, 100])
    write_norms_npz(norms, tmp_path)
    loaded = read_norms_npz(tmp_path / "npz")
    assert len(loaded) == len(norms)

    # Patient: age 25, sex F, value 2.0 (in M range, not F range).
    patient_metrics = {"Fz": {"Alpha": {"absolute_power": 2.0}}}
    report_f = compare_and_report(patient_metrics, loaded, age=25, condition="ec", sex="F")
    report_pooled = compare_and_report(patient_metrics, loaded, age=25, condition="ec", sex=None)

    # F-matched z should be much larger than pooled-matched z because F mean is ~1.1
    # and F sd is small, while pooled mean is ~1.6.
    f_z = report_f.results[0].base.z_score
    pooled_z = report_pooled.results[0].base.z_score
    assert f_z > pooled_z > 0
    # And the F report's metadata reflects F matching.
    assert report_f.to_dict()["metadata"]["resolved_sex_summary"] == {"F": 1}
    assert report_pooled.to_dict()["metadata"]["resolved_sex_summary"] == {"pooled": 1}
