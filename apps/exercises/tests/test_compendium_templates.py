from apps.exercises.compendium_templates import template_for, COMPENDIUM_TEMPLATES
from apps.exercises.unit_allowed_answers import compute_unit_allowed_answers


def test_lookup_known_types():
    assert template_for("Simple Cadences in Three Voices", "major") == [(0.0, "I"), (2.0, "V"), (4.0, "I")]
    assert template_for("Compound Cadences with 6/5 in Four Voices", "minor") == [
        (0.0, "i"), (1.0, "i6"), (2.0, "iiø65"), (3.0, "V"), (4.0, "i")]
    assert template_for("Compound Cadences with 6/4 in Four Voices", "major") == [
        (0.0, "I"), (1.0, "I6"), (2.0, "Cad64"), (3.0, "V"), (4.0, "I")]
    assert template_for("Compound Cadences with 6/4 in Four Voices", "minor") == [
        (0.0, "i"), (1.0, "i6"), (2.0, "Cad64"), (3.0, "V"), (4.0, "i")]
    assert template_for("Evaded Cadences in Three Voices", "minor") == [
        (0.0, "V"), (1.0, "i6"), (2.0, "iiø65"), (3.0, "V"), (4.0, "VI")]


def test_skipped_types_return_none():
    # two-voice / double / ornamented are intentionally not templated this round
    assert template_for("Simple Cadences in Two Voices", "major") is None
    assert template_for("Double Cadences in Three Voices", "major") is None
    assert template_for("Cudworth Cadence", "major") is None
    assert template_for("Nonexistent Page", "major") is None


def test_every_template_rn_is_binnable():
    # Each RN in every template must appear in at least one unit's answer set,
    # else the exercise can never be binned/answered.
    table = compute_unit_allowed_answers()
    all_answers = set()
    for vals in table.values():
        if vals:
            all_answers.update(vals)
    for (pt, mode), targets in COMPENDIUM_TEMPLATES.items():
        for _off, rn in targets:
            assert rn in all_answers, f"template RN {rn!r} ({pt}/{mode}) not in any unit answer set"
