"""Tests for build_binned_payload — derived RNs, unit binning, page_title, per-unit answers.

Task 8: Verifies the new build_binned_payload() and structural_targets() helpers
in generate_roman_from_clausulae.py.
"""
import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

pytest.importorskip("music21")


def _ivi_voices():
    def ev(step, octave, midi, ql, dt):
        return VoiceEvent(kind="note", pitch=Pitch(step=step, alter=0, octave=octave, midi=midi),
                          duration=ql, duration_type=dt, dots=0, is_target=True)
    return Voices(
        S=[ev("G", 4, 67, 2.0, "h"), ev("B", 4, 71, 2.0, "h"), ev("G", 4, 67, 4.0, "w")],
        A=[ev("E", 4, 64, 2.0, "h"), ev("D", 4, 62, 2.0, "h"), ev("E", 4, 64, 4.0, "w")],
        T=[],
        B=[ev("C", 3, 48, 2.0, "h"), ev("G", 2, 43, 2.0, "h"), ev("C", 3, 48, 4.0, "w")],
    )


def test_build_payload_bins_simple_cadence_to_unit_9():
    from apps.exercises.management.commands.generate_roman_from_clausulae import (
        build_binned_payload,
    )
    result = build_binned_payload(_ivi_voices(), key="C", family="simple", n_voices=3,
                                   fingerprint="D:D-Ti-D B:D-Sol-D")
    assert result is not None
    payload, unit, derived = result
    assert unit == 9
    assert derived == ["I", "V", "I"]
    assert payload["analysisType"] == "roman"
    assert payload["allowed_answers"] == ["I", "i", "V", "V7"]
    targets = [s for s in payload["score"]["umto"]["analysis"] if s["is_target"]]
    assert len(targets) == 3
    assert payload["score"]["umto"]["metadata"]["source"] == "Simple Cadences in Three Voices in C major"
    assert payload["description"].startswith("RfC u9 simple 3v C ")
    assert len(payload["description"]) <= 60
