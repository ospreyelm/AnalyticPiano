import pytest

pytest.importorskip("music21")

from music21 import pitch

from apps.exercises.utils.legacy_roman import (
    legacy_chord_code,
    legacy_roman_from_pitches,
    normalize_legacy_roman_label,
)


def _pitches(names):
    return [pitch.Pitch(name) for name in names]


def test_legacy_chord_code_matches_analyze_js_for_minor_first_inversion_iio():
    assert legacy_chord_code(_pitches(["D3", "B4", "D5", "F5"]), "A") == "5/28"


def test_legacy_roman_uses_minor_table_for_iio6():
    result = legacy_roman_from_pitches(_pitches(["D3", "B4", "D5", "F5"]), "A", "minor")

    assert result.chord_code == "5/28"
    assert result.label == "ii°{z}"
    assert result.normalized_label == "ii°6"


def test_legacy_roman_uses_minor_table_for_tonic_triad():
    result = legacy_roman_from_pitches(_pitches(["A3", "C4", "E4"]), "A", "minor")

    assert result.chord_code == "0/37"
    assert result.label == "i"


def test_legacy_roman_uses_major_table_for_dominant_triad():
    result = legacy_roman_from_pitches(_pitches(["G3", "D4", "B4"]), "C", "major")

    assert result.chord_code == "7/2z"
    assert result.label == "V"


def test_normalize_legacy_roman_label_converts_figured_bass_glyph_codes():
    assert normalize_legacy_roman_label("ii°{z}") == "ii°6"
    assert normalize_legacy_roman_label("ii⌀{z5}") == "iiø65"
    assert normalize_legacy_roman_label("V{r3}/V") == "V43/V"
    assert normalize_legacy_roman_label("Cad{Cz4}") == "Cad♭64"
