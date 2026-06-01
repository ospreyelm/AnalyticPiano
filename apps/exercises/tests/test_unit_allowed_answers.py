import pytest

from apps.exercises.unit_allowed_answers import _build_table, compute_unit_allowed_answers


def test_unit_9_matches_taxonomy_cumulative():
    table = compute_unit_allowed_answers()
    assert table[9] == ["I", "i", "V", "V7"]


def test_unit_14_includes_diatonic_sevenths():
    table = compute_unit_allowed_answers()
    assert "ii7" in table[14]
    assert "vii°7" in table[14]
    # cumulative: unit 14 is a superset of unit 12
    assert set(table[12]).issubset(set(table[14]))


def test_override_units_are_null_passthrough():
    table = compute_unit_allowed_answers()
    assert table[19] is None
    assert table[20] is None


def test_all_taxonomy_units_present():
    table = compute_unit_allowed_answers()
    for n in (9, 10, 11, 12, 13, 14, 15, 16, 17, 18):
        assert isinstance(table[n], list) and table[n], f"unit {n} missing"


# ---------------------------------------------------------------------------
# Tests for _build_table (pure helper, uses in-memory taxonomy dicts)
# ---------------------------------------------------------------------------

def _unit_node(n, values):
    """Build a minimal taxonomy unit node for _build_table tests."""
    return {
        "n": n,
        "analysis": {
            "roman": {
                "cumulative": [{"value": v} for v in values]
            }
        },
    }


def test_build_table_raises_on_duplicate_unit():
    """Duplicate unit n in taxonomy must raise ValueError (not silently clobber)."""
    taxonomy = {
        "units": [
            _unit_node(5, ["I", "V"]),
            _unit_node(5, ["I", "V", "IV"]),  # duplicate n=5
        ]
    }
    with pytest.raises(ValueError, match="Duplicate unit 5"):
        _build_table(taxonomy, {})


def test_build_table_raises_on_missing_value_key():
    """A cumulative entry without 'value' must raise KeyError mentioning the unit."""
    taxonomy = {
        "units": [
            {
                "n": 7,
                "analysis": {
                    "roman": {
                        "cumulative": [{"label": "I"}]  # 'value' key absent
                    }
                },
            }
        ]
    }
    with pytest.raises(KeyError, match="Unit 7"):
        _build_table(taxonomy, {})


# ---------------------------------------------------------------------------
# Test: generated JS module matches the loader output
# ---------------------------------------------------------------------------

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# test file: apps/exercises/tests/test_unit_allowed_answers.py → repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_GENERATED_JS = _REPO_ROOT / "lab/static/js/src/config/unit_allowed_answers.js"


def _parse_generated_js():
    """Extract the JSON object literal embedded in the generated AMD module."""
    text = _GENERATED_JS.read_text()
    match = re.search(r"return\s+(\{.*\});\s*\}\);\s*$", text, re.DOTALL)
    assert match, "generated module does not match expected AMD shape"
    return json.loads(match.group(1))


def test_additions_propagate_cumulatively():
    table = compute_unit_allowed_answers()
    # Cad64 (cadential six-four, dominant-function) added at unit 12
    for n in (12, 13, 14, 15, 16, 17, 18):
        assert "Cad64" in table[n], f"Cad64 missing from unit {n}"
        assert "ii°6" in table[n], f"ii°6 missing from unit {n}"
    # not added below 12
    for n in (9, 10, 11):
        assert "Cad64" not in table[n]
        assert "ii°6" not in table[n]
    # ii65 / iiø65 added at unit 14 -> present in 14..18, not below
    for n in (14, 15, 16, 17, 18):
        assert "ii65" in table[n] and "iiø65" in table[n]
    for n in (9, 10, 11, 12, 13):
        assert "ii65" not in table[n] and "iiø65" not in table[n]


def test_additions_do_not_duplicate_or_clobber():
    table = compute_unit_allowed_answers()
    # existing taxonomy figures still present, no dupes introduced
    assert table[14].count("ii65") == 1
    assert "ii7" in table[14]            # original taxonomy entry intact
    assert table[9] == ["I", "i", "V", "V7"]  # untouched unit


def test_generated_js_matches_loader():
    # Regenerate, then compare to the loader output.
    subprocess.run(
        [sys.executable, "manage.py", "build_unit_allowed_answers"],
        cwd=_REPO_ROOT,
        check=True,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "harmony.settings.local"},
    )
    from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers
    expected = {str(k): v for k, v in compute_unit_allowed_answers().items()}
    assert _parse_generated_js() == expected
