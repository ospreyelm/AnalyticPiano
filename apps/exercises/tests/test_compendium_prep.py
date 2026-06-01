import pytest
pytest.importorskip("music21")
from apps.exercises.compendium_source import load_cadence_examples
from apps.exercises.compendium_prep import CANDIDATE_UNITS, prepare_compendium_exercise


def _ex(eid):
    return next(e for e in load_cadence_examples() if e["id"] == eid)


def test_prep_6_5_bins_unit_14_with_template_rns():
    out = prepare_compendium_exercise(_ex("m111-112"), "D")  # 6/5 major -> D major
    assert out is not None
    assert out["unit"] == 14
    assert out["umto_kwargs"]["key"] == "jD_"
    assert out["umto_kwargs"]["source"] == "Compound Cadences with 6/5 in Four Voices in D major"
    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]
    assert rns == ["I", "I6", "ii65", "V", "I"]
    assert all(a["is_target"] for a in out["umto_kwargs"]["analysis_overrides"])
    assert len(out["description"]) <= 60
    assert out["score_data"]["measures"]  # non-empty CIR


def test_prep_uses_normalized_legacy_labels_for_import_answers():
    out = prepare_compendium_exercise(_ex("m145-146"), "A")
    assert out is not None

    target = next(
        target
        for target in out["umto_kwargs"]["analysis_overrides"]
        if target["offset"] == 1.0
    )

    assert target["content"]["roman_numeral"] == "ii°6"
    assert target["content"]["raw_roman_numeral"] == "ii°{z}"


def test_candidate_unit_range_covers_roman_curriculum():
    assert CANDIDATE_UNITS == list(range(9, 21))


def test_prep_6_4_bins_unit_12_cad64():
    out = prepare_compendium_exercise(_ex("m123-124"), "C")  # 6/4 major
    assert out["unit"] == 12
    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]
    assert rns == ["I", "I6", "Cad64", "V", "I"]


def test_prep_simple_three_voice_unit_9():
    out = prepare_compendium_exercise(_ex("m025-026"), "G")  # simple 3v major -> G
    assert out["unit"] == 9
    assert out["umto_kwargs"]["key"] == "jG_"


def test_compound_three_voice_keeps_simultaneous_upper_notes_in_separate_voices():
    from apps.exercises.umto_factory import build_umto_payload

    out = prepare_compendium_exercise(_ex("m075-076"), "D")
    assert out is not None

    score_measures = out["score_data"]["measures"]
    assert len(score_measures) == 2

    final_treble_voices = score_measures[1]["staves"]["treble"]["voices"]
    assert len(final_treble_voices) == 2
    assert [
        voice["items"][0]["pitch"]["step"]
        for voice in final_treble_voices
        if voice["items"] and voice["items"][0]["kind"] == "note"
    ] == ["D", "F"]
    assert all(
        voice["items"] == [voice["items"][0]]
        and voice["items"][0]["duration"] == {"type": "w", "dots": 0}
        for voice in final_treble_voices
    )

    payload = build_umto_payload(score_data=out["score_data"], **out["umto_kwargs"])
    assert len(payload["score"]["measures"]) == 2


def test_compound_three_voice_preserves_source_durations_before_final_measure():
    from apps.exercises.umto_factory import build_umto_payload

    out = prepare_compendium_exercise(_ex("m075-076"), "D")
    assert out is not None

    payload = build_umto_payload(score_data=out["score_data"], **out["umto_kwargs"])
    treble = payload["score"]["measures"][0]["staves"]["treble"]["voices"]

    assert [item["duration"] for item in treble[0]["items"]] == [
        {"type": "q", "dots": 0},
        {"type": "h", "dots": 0},
        {"type": "q", "dots": 0},
    ]
    assert [item["kind"] for item in treble[0]["items"]] == ["rest", "note", "note"]
    assert [item["pitch"]["step"] for item in treble[0]["items"] if item["kind"] == "note"] == ["D", "C"]

    assert [item["duration"] for item in treble[1]["items"]] == [
        {"type": "h", "dots": 0},
        {"type": "h", "dots": 0},
    ]
    assert [item["pitch"]["step"] for item in treble[1]["items"]] == ["F", "E"]


def test_evaded_minor_labels_and_bins_to_unit_17_by_family():
    out = prepare_compendium_exercise(_ex("m191-192"), "A")
    assert out["unit"] == 17
    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]
    assert rns == ["V", "i6", "iiø65", "V", "VI"]


def test_evaded_major_through_measure_217_uses_confirmed_music21_labels():
    out = prepare_compendium_exercise(_ex("m208-209"), "C")
    assert out["unit"] == 17

    rns = [a["content"]["roman_numeral"] for a in out["umto_kwargs"]["analysis_overrides"]]

    assert rns == ["V65", "I", "ii42", "vii°", "I"]


def test_confirmed_vii_diminished_four_displays_as_vii_64():
    out = prepare_compendium_exercise(_ex("m206-207"), "C")
    target = next(
        target
        for target in out["umto_kwargs"]["analysis_overrides"]
        if target["offset"] == 3.0
    )

    assert target["content"]["roman_numeral"] == "vii°64"


def test_unit_14_prep_builds_payload_without_validation_error():
    """Regression: complexity_score must allow unit 14 (was le=12, crashed save)."""
    from apps.exercises.umto_factory import build_umto_payload
    from pydantic import ValidationError

    out = prepare_compendium_exercise(_ex("m111-112"), "C")
    assert out is not None
    assert out["unit"] == 14

    # build_umto_payload is keyword-only; umto_kwargs maps directly onto its params.
    try:
        payload = build_umto_payload(score_data=out["score_data"], **out["umto_kwargs"])
    except ValidationError as exc:
        raise AssertionError(f"Pydantic ValidationError for unit-14 payload: {exc}") from exc

    assert payload is not None
    assert payload["complexity_score"] == 14
