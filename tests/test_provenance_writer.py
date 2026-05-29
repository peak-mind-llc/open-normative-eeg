"""Smoke test for the PROVENANCE.md generator."""

from pathlib import Path


def test_provenance_writer_basic(tmp_path: Path):
    from scripts.build_norms import write_provenance_md

    subjects = [
        {"subject_id": "s01", "age": 25, "sex": "F", "condition": "ec"},
        {"subject_id": "s02", "age": 26, "sex": "F", "condition": "eo"},
        {"subject_id": "s03", "age": 35, "sex": "M", "condition": "ec"},
        {"subject_id": "s04", "age": 42, "sex": "", "condition": "ec"},
    ]
    out = tmp_path
    out.mkdir(exist_ok=True)
    write_provenance_md(subjects, out, age_bins=[20, 30, 40, 50])

    md = (out / "PROVENANCE.md").read_text()
    # The two required sections must be present.
    assert "## PSD freq-resolved category" in md
    assert "## Cohort sex breakdown" in md
    # The table header must be present.
    assert "| Age bin | Condition | F | M | Other/unknown | Total |" in md
    # And the cohort counts: 20-29 ec should have 1 F, 0 M, 0 unknown.
    # 30-39 ec should have 1 M.
    # 40-49 ec should have 1 unknown.
    assert "20-29" in md
    assert "30-39" in md
    assert "40-49" in md
    assert "Requires open_normative" in md
