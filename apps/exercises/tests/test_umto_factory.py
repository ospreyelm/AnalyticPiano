import pytest
from apps.exercises.umto_factory import NonUMTOExerciseError


def test_non_umto_exercise_error_is_value_error_subclass():
    assert issubclass(NonUMTOExerciseError, ValueError)


def test_non_umto_exercise_error_carries_message():
    err = NonUMTOExerciseError("test message")
    assert str(err) == "test message"


from apps.exercises.umto import InteractionMode


SINGLE_VOICE_CIR = {
    "meta": {"key": "C", "time": "4/4"},
    "measures": [
        {
            "staves": {
                "treble": {
                    "voices": [
                        {
                            "items": [
                                {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "F", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                            ]
                        }
                    ]
                }
            }
        }
    ],
}


def test_build_umto_payload_single_voice_treble_identification():
    from apps.exercises.umto_factory import build_umto_payload

    payload = build_umto_payload(
        exercise_id="TEMP",
        source="Test",
        key="C",
        meter="4/4",
        clef="treble",
        complexity_score=1,
        mode=InteractionMode.IDENTIFICATION,
        score_data=SINGLE_VOICE_CIR,
        target_voice="soprano",
        unit=1,
    )

    assert payload["isUMTO"] is True
    assert payload["type"] == "umto_chorale"
    assert payload["mode"] == "identification"
    assert payload["clef"] == "treble"
    assert payload["staffDistribution"] == "treble"
    assert payload["complexity_score"] == 1
    assert payload["key"] == "C"
    assert payload["meter"] == "4/4"

    umto = payload["score"]["umto"]
    assert len(umto["voices"]["S"]) == 4
    assert umto["voices"]["S"][0]["pitch"]["midi"] == 60
    assert umto["voices"]["S"][1]["pitch"]["midi"] == 62
    assert umto["voices"]["S"][2]["pitch"]["midi"] == 64
    assert umto["voices"]["S"][3]["pitch"]["midi"] == 65
    assert len(umto["grading"]) == 4
    assert umto["grading"][0]["offset"] == 0.0
    assert umto["grading"][1]["offset"] == 1.0
    assert umto["grading"][2]["offset"] == 2.0
    assert umto["grading"][3]["offset"] == 3.0
    assert umto["grading"][0]["target_midi_pitches"] == [60]
    assert len(umto["analysis"]) == 4
    assert umto["analysis"][0]["unit_tags"] == [1]
