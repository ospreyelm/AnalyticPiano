import pytest
from apps.exercises.utils.figured_bass import abbreviate_figured_bass


def test_root_position_triad():
    assert abbreviate_figured_bass("8/5/3") == ""

def test_root_position_triad_without_octave():
    assert abbreviate_figured_bass("5/3") == ""

def test_first_inversion_triad():
    assert abbreviate_figured_bass("6/3") == "6"

def test_first_inversion_triad_with_double():
    assert abbreviate_figured_bass("6/3/3") == "6"

def test_second_inversion_triad():
    assert abbreviate_figured_bass("6/4") == "6/4"

def test_root_position_seventh():
    assert abbreviate_figured_bass("7/5/3") == "7"

def test_first_inversion_seventh():
    assert abbreviate_figured_bass("6/5/3") == "6/5"

def test_second_inversion_seventh():
    assert abbreviate_figured_bass("6/4/3") == "4/3"

def test_third_inversion_seventh():
    assert abbreviate_figured_bass("6/4/2") == "4/2"

def test_five_four_three():
    assert abbreviate_figured_bass("5/4/3") == "5/4"

def test_nine():
    assert abbreviate_figured_bass("9/5/3") == "9"

def test_nine_seven():
    assert abbreviate_figured_bass("9/7/3") == "9/7"

def test_chromatic_prefix_preserved_on_abbreviated():
    # b6/5/3 → b6/5
    assert abbreviate_figured_bass("b6/5/3") == "b6/5"

def test_chromatic_prefix_on_third():
    # 8/5/#3 → # (just the accidental on the third, root position)
    assert abbreviate_figured_bass("8/5/#3") == "#"

def test_chromatic_prefix_flat_third():
    assert abbreviate_figured_bass("8/5/b3") == "b"

def test_unknown_stack_passthrough():
    # Unrecognized stacks pass through unabbreviated — no data loss
    assert abbreviate_figured_bass("9/8/6/4") == "9/8/6/4"

def test_empty_string_passthrough():
    assert abbreviate_figured_bass("") == ""


from apps.exercises.utils.figured_bass import compute_figured_bass


def _make_chord(pitches_str: str, key_str: str):
    """Helper: build music21 chord + key from strings like 'A3 C#4 E4 A4', 'A'."""
    from music21 import chord as m21chord, key as m21key
    pitches = pitches_str.split()
    c = m21chord.Chord(pitches)
    k = m21key.Key(key_str)
    return c, k


def test_root_position_A_major():
    # A3 C#4 E4 A4 in A major — all diatonic, root position
    c, k = _make_chord("A3 C#4 E4 A4", "A")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "8/5/3"
    assert abbrev == ""


def test_root_position_C_major():
    # C4 E4 G4 C5 in C major
    c, k = _make_chord("C4 E4 G4 C5", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "8/5/3"
    assert abbrev == ""


def test_first_inversion_C_major():
    # E3 G3 C4 E4 in C major — first inversion triad
    c, k = _make_chord("E3 G3 C4 E4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "6" in raw
    assert "3" in raw
    assert abbrev == "6"


def test_dominant_seventh_C_major():
    # G3 B3 D4 F4 in C major — root position V7
    c, k = _make_chord("G3 B3 D4 F4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "7/5/3"
    assert abbrev == "7"


def test_chromatic_raised_pitch():
    # In C major, G#4 above E3 — G# is raised from diatonic G
    c, k = _make_chord("E3 G#4 C5", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "#" in raw  # some interval has # prefix


def test_chromatic_lowered_pitch():
    # In C major, Bb4 above C4 — Bb is lowered from diatonic B
    c, k = _make_chord("C4 E4 G4 Bb4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "b" in raw  # b7 present


def test_tritone_marker():
    # F3 B3 in C major — B above F is a tritone (aug 4th), F is diatonic
    c, k = _make_chord("F3 B3 D4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "4+" in raw or "#4" in raw  # tritone above F is augmented 4th
