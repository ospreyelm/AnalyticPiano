import csv
from io import StringIO

import pytest

pytest.importorskip("music21")

from apps.exercises.management.commands.audit_compendium_cadences import (
    CSV_FIELDS,
    build_audit_rows,
    write_audit_csv,
)


def test_audit_rows_include_corrected_evaded_minor_labels():
    rows = build_audit_rows(unit=17, keys=["A"])
    row_by_offset = {
        row["offset"]: row
        for row in rows
        if row["source_id"] == "m191-192" and row["target_key"] == "A"
    }

    assert row_by_offset["0.0"]["proposed_rn"] == "V"
    assert row_by_offset["0.0"]["music21_rn"] == "V"
    assert row_by_offset["0.0"]["final_rn"] == "V"
    assert row_by_offset["0.0"]["status"] == "match"
    assert row_by_offset["4.0"]["proposed_rn"] == "VI"
    assert row_by_offset["4.0"]["music21_rn"] == "bVI"
    assert row_by_offset["4.0"]["status"] == "accepted"
    assert row_by_offset["4.0"]["exception_reason"] == "minor VI displayed without flat"


def test_write_audit_csv_round_trips_rows():
    rows = build_audit_rows(unit=12, keys=["C"])
    out = StringIO()
    write_audit_csv(rows[:2], out)
    out.seek(0)

    parsed = list(csv.DictReader(out))
    assert parsed
    assert parsed[0].keys() == set(CSV_FIELDS)
    assert parsed[0]["source_id"]
    assert parsed[0]["final_rn"] == parsed[0]["proposed_rn"]


def test_audit_rows_include_deterministic_legacy_analysis_fields():
    rows = build_audit_rows(unit=12, keys=["A"])
    row = next(
        row
        for row in rows
        if row["source_id"] == "m145-146"
        and row["target_key"] == "A"
        and row["offset"] == "1.0"
    )

    assert row["z7_stack"] == "3 1 3 5"
    assert row["bass_z7"] == "3"
    assert row["legacy_chord_code"] == "5/28"
    assert row["legacy_rn_raw"] == "ii°{z}"
    assert row["our_rn"] == "ii°6"
    assert row["final_rn"] == "ii°6"
    assert row["raw_figured_bass"] == "8/6/3"
    assert row["figured_bass"] == "6"


def test_audit_uses_legacy_analysis_for_major_evaded_opening_dominant():
    rows = build_audit_rows(unit=17, keys=["C"])
    row = next(
        row
        for row in rows
        if row["source_id"] == "m187-188"
        and row["target_key"] == "C"
        and row["offset"] == "0.0"
    )

    assert row["legacy_chord_code"] == "7/2z"
    assert row["legacy_rn_raw"] == "V"
    assert row["our_rn"] == "V"
    assert row["music21_rn"] == "V"
    assert row["final_rn"] == "V"


def test_audit_normalizes_incomplete_root_position_dominant_seventh():
    rows = build_audit_rows(unit=17, keys=["C"])
    row = next(
        row
        for row in rows
        if row["source_id"] == "m203-205"
        and row["target_key"] == "C"
        and row["offset"] == "0.0"
    )

    assert row["legacy_chord_code"] == "7/5z"
    assert row["legacy_rn_raw"] == "V{u3}"
    assert row["our_rn"] == "V7"
    assert row["music21_rn"] == "V7"
    assert row["final_rn"] == "V7"
    assert row["status"] == "match"
