import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

pytest.importorskip("music21")


def _ivi_cadence_c_major():
    """Three onsets in C major: I (C/E/G), V (G/D/B), I (C/E/G) — SAB, half/half/whole."""
    def ev(step, octave, midi, ql):
        return VoiceEvent(kind="note", pitch=Pitch(step=step, alter=0, octave=octave, midi=midi),
                          duration=ql, duration_type="h" if ql == 2.0 else "w", dots=0, is_target=True)
    return Voices(
        S=[ev("G", 4, 67, 2.0), ev("B", 4, 71, 2.0), ev("G", 4, 67, 4.0)],
        A=[ev("E", 4, 64, 2.0), ev("D", 4, 62, 2.0), ev("E", 4, 64, 4.0)],
        T=[],
        B=[ev("C", 3, 48, 2.0), ev("G", 2, 43, 2.0), ev("C", 3, 48, 4.0)],
    )


def test_derive_simple_authentic_cadence():
    from apps.exercises.roman_derivation import derive_cadence
    verticals = derive_cadence(
        _ivi_cadence_c_major(),
        key="C",
        targets=[(0.0, 0.0), (2.0, 2.0), (4.0, 4.0)],
    )
    assert [v["rn"] for v in verticals] == ["I", "V", "I"]
    # offsets are actual sounding offsets (half/half/whole)
    assert [v["offset"] for v in verticals] == [0.0, 2.0, 4.0]
    # grading MIDI comes from the chordified vertical at each offset, not a position index
    assert verticals[0]["midi"] == [48, 64, 67]   # C3 E4 G4
    assert verticals[1]["midi"] == [43, 62, 71]   # G2 D4 B4


def test_normalize_diminished_uses_degree_sign():
    from apps.exercises.roman_derivation import normalize_figure
    assert normalize_figure("viio6") == "vii°6"
    assert normalize_figure("ii") == "ii"
    assert normalize_figure("V7") == "V7"


def test_derive_requires_explicit_targets():
    from apps.exercises.roman_derivation import derive_cadence
    with pytest.raises(ValueError):
        derive_cadence(_ivi_cadence_c_major(), key="C")


def test_bin_unit_lowest_cover():
    from apps.exercises.roman_derivation import bin_unit
    table = {
        9: ["I", "i", "V", "V7"],
        10: ["I", "i", "V", "V7", "I6", "V6", "vii°6"],
        12: ["I", "i", "V", "V7", "I6", "V6", "vii°6", "I64", "V64"],
        14: ["I", "i", "V", "V7", "I6", "V6", "vii°6", "I64", "V64", "ii7"],
    }
    candidates = [9, 10, 12, 14]
    assert bin_unit({"I", "V"}, table, candidates) == 9
    assert bin_unit({"I", "V6", "I6"}, table, candidates) == 10
    assert bin_unit({"I", "I64", "V"}, table, candidates) == 12
    assert bin_unit({"I", "ii7"}, table, candidates) == 14
    assert bin_unit({"I", "N6"}, table, candidates) is None  # uncovered -> reject
