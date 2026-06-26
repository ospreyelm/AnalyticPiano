"""Unit tests for spelling-preserving chord transposition.

These are pure-function tests for `_transpose_chords` — no DB required.

Run with:
    DJANGO_SETTINGS_MODULE=harmony.settings.local \\
    python3 manage.py test apps.exercises.tests.test_transpose_spelling -v 1
"""
from django.test import SimpleTestCase

from apps.exercises.services.transposition_service import _transpose_chords


class TransposeChordsSpellingTest(SimpleTestCase):
    """`_transpose_chords` must preserve enharmonic spelling, not just MIDI."""

    def test_diatonic_c_major_to_bflat_populates_key_correct_spelling(self):
        # C-major I chord (C E G) over a C bass, transposed down a major 2nd to Bb.
        chords = [
            {"offset": 0.0, "duration": 2.0, "visible": [60, 64, 67], "hidden": [48]},
        ]
        out = _transpose_chords(
            chords, midi_vector=-2, source_key_hl="jC_", target_key_hl="jBb"
        )
        chord = out[0]
        # MIDI shifted by the vector.
        self.assertEqual(chord["visible"], [58, 62, 65])
        self.assertEqual(chord["hidden"], [46])
        # Spelling populated (NOT null) and key-correct for Bb major: Bb, D, F.
        # spelling is positional over visible + hidden.
        self.assertIsNotNone(chord.get("spelling"))
        self.assertEqual(chord["spelling"], ["Bb", "D", "F", "Bb"])
        # Crucially the bass spells "Bb", never the chromatic "A#".
        self.assertNotIn("A#", chord["spelling"])

    def test_chromatic_source_spelling_preserved_via_interval(self):
        # A non-diatonic note carried with explicit source spelling must transpose
        # by interval, preserving enharmonic identity: F# up a M2 (C->D) -> G#, not Ab.
        chords = [
            {
                "offset": 0.0,
                "duration": 2.0,
                "visible": [62, 66, 69],          # D F# A  (D major triad in C context)
                "hidden": [],
                "spelling": ["D", "F#", "A"],
            },
        ]
        out = _transpose_chords(
            chords, midi_vector=2, source_key_hl="jC_", target_key_hl="jD_"
        )
        chord = out[0]
        self.assertEqual(chord["visible"], [64, 68, 71])
        # F# (pc6) -> G# (pc8), spelled as a sharp, not Ab.
        self.assertEqual(chord["spelling"], ["E", "G#", "B"])
        self.assertNotIn("Ab", chord["spelling"])
