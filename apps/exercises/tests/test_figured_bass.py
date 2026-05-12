import pytest
from apps.exercises.utils.figured_bass import abbreviate_figured_bass


def test_root_position_triad():
    assert abbreviate_figured_bass("8/5/3") == "5/3"

def test_root_position_triad_without_octave():
    assert abbreviate_figured_bass("5/3") == "5/3"

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
    assert abbrev == "5/3"


def test_root_position_C_major():
    # C4 E4 G4 C5 in C major
    c, k = _make_chord("C4 E4 G4 C5", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert raw == "8/5/3"
    assert abbrev == "5/3"


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


# ---------------------------------------------------------------------------
# 9 vs 2 resolution rule:
#   A pitch a 9th above bass is labelled 9 if it descends next (→ resolves to 8).
#   If it stays or rises, it is a passing/melodic 2nd, labelled 2.
# next_pitch_map: {midi_of_pitch_in_chord: midi_of_same_voice_next_note}
# ---------------------------------------------------------------------------

def test_ninth_labelled_9_when_pitch_descends():
    # C3 bass, D4 a major 9th above. D4 moves down to C4 next → label 9.
    c, k = _make_chord("C3 E3 G3 D4", "C")
    next_map = {62: 60}  # D4 (midi 62) → C4 (midi 60), descends
    raw, abbrev = compute_figured_bass(c, k, next_pitch_map=next_map)
    assert "9" in raw
    assert "2" not in raw.split("/")[0]  # top interval is 9 not 2


def test_ninth_labelled_2_when_pitch_ascends():
    # C3 bass, D4 a major 9th above. D4 moves up to E4 next → label 2.
    c, k = _make_chord("C3 E3 G3 D4", "C")
    next_map = {62: 64}  # D4 (midi 62) → E4 (midi 64), ascends
    raw, abbrev = compute_figured_bass(c, k, next_pitch_map=next_map)
    assert "2" in raw
    assert "9" not in raw


def test_ninth_labelled_2_when_pitch_stays():
    # C3 bass, D4 a major 9th above. D4 stays on D4 next → label 2.
    c, k = _make_chord("C3 E3 G3 D4", "C")
    next_map = {62: 62}  # D4 stays
    raw, abbrev = compute_figured_bass(c, k, next_pitch_map=next_map)
    assert "2" in raw
    assert "9" not in raw


def test_ninth_defaults_to_9_without_context():
    # No next_pitch_map supplied → keep existing behaviour (label 9).
    c, k = _make_chord("C3 E3 G3 D4", "C")
    raw, abbrev = compute_figured_bass(c, k)
    assert "9" in raw


def test_riemenschneider1_m3_beat1pt5_is_2_not_9():
    # m3 b1.5: C3 B3 D4 G4 in G major.
    # B3 is a 7th above C3 (already a 7), but G4 is a 12th → reduces to 5.
    # The "9" we saw was the alto D4 (a 9th above C3 bass).
    # Alto D4 next pitch = E4 (goes up) → should be 2.
    c, k = _make_chord("C3 B3 D4 G4", "G")
    next_map = {62: 64}  # D4 (midi 62) → E4 (midi 64), ascends
    raw, abbrev = compute_figured_bass(c, k, next_pitch_map=next_map)
    assert "2" in raw
    assert "9" not in raw
