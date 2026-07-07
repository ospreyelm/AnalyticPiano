import pytest

from apps.exercises.harmonization.voice_completion_eligibility import (
    VoiceCompletionEligibilityError,
    validate_voice_completion_eligibility,
)


def _note(midi, step, octave, duration=1.0, alter=0, is_tied_start=False, is_tied_stop=False):
    return {
        "kind": "note",
        "pitch": {"step": step, "alter": alter, "octave": octave, "midi": midi},
        "duration": duration,
        "duration_type": "q",
        "dots": 0,
        "is_tied_start": is_tied_start,
        "is_tied_stop": is_tied_stop,
        "is_target": True,
    }


def _rest(duration=1.0):
    return {
        "kind": "rest",
        "pitch": None,
        "duration": duration,
        "duration_type": "q",
        "dots": 0,
        "is_tied_start": False,
        "is_tied_stop": False,
        "is_target": False,
    }


def _base_voices():
    return {
        "S": [_note(60, "C", 4), _note(62, "D", 4)],
        "A": [_note(57, "A", 3), _note(59, "B", 3)],
        "T": [_note(52, "E", 3), _note(53, "F", 3)],
        "B": [_note(48, "C", 3), _note(50, "D", 3)],
    }


def test_eligible_source_returns_missing_voice():
    umto = {
        "metadata": {"locked_voices": ["B", "A", "T"]},
        "voices": _base_voices(),
    }

    assert validate_voice_completion_eligibility(umto) == "S"


def test_bass_not_locked_raises():
    umto = {
        "metadata": {"locked_voices": ["S", "A", "T"]},
        "voices": _base_voices(),
    }

    with pytest.raises(VoiceCompletionEligibilityError, match="Bass must be in locked_voices"):
        validate_voice_completion_eligibility(umto)


def test_locked_voice_rest_at_onset_raises():
    voices = _base_voices()
    voices["A"] = [_note(57, "A", 3), _rest(1.0)]
    umto = {
        "metadata": {"locked_voices": ["B", "A", "T"]},
        "voices": voices,
    }

    with pytest.raises(VoiceCompletionEligibilityError, match=r"Locked voice A has a rest at bass onset 1\.0"):
        validate_voice_completion_eligibility(umto)


def test_missing_voice_tied_note_raises():
    voices = _base_voices()
    voices["S"] = [
        _note(60, "C", 4, duration=1.0, is_tied_start=True),
        _note(60, "C", 4, duration=1.0, is_tied_stop=True),
    ]
    umto = {
        "metadata": {"locked_voices": ["B", "A", "T"]},
        "voices": voices,
    }

    with pytest.raises(VoiceCompletionEligibilityError, match="no fresh attack at bass onset"):
        validate_voice_completion_eligibility(umto)


def test_missing_voice_passing_tone_raises():
    voices = _base_voices()
    voices["S"] = [
        _note(60, "C", 4, duration=0.5),
        _note(61, "C#", 4, duration=0.5),
        _note(62, "D", 4, duration=1.0),
    ]
    umto = {
        "metadata": {"locked_voices": ["B", "A", "T"]},
        "voices": voices,
    }

    with pytest.raises(VoiceCompletionEligibilityError, match=r"attack\(s\) at offset\(s\) \[0\.5\]"):
        validate_voice_completion_eligibility(umto)


def test_multiple_missing_voices_raises_distinct_reason():
    umto = {
        "metadata": {"locked_voices": ["B"]},
        "voices": _base_voices(),
    }

    with pytest.raises(VoiceCompletionEligibilityError, match="Expected exactly one missing voice"):
        validate_voice_completion_eligibility(umto)


def test_bass_with_no_attacks_raises():
    voices = _base_voices()
    voices["B"] = [_rest(1.0), _rest(1.0)]
    umto = {
        "metadata": {"locked_voices": ["B", "A", "T"]},
        "voices": voices,
    }

    with pytest.raises(VoiceCompletionEligibilityError, match="no note attacks"):
        validate_voice_completion_eligibility(umto)
