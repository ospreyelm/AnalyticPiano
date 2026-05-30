from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers


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
