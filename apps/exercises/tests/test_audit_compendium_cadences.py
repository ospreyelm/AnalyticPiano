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
