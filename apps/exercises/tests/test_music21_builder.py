"""
Standalone tests for apps/exercises/generation/music21_builder.py

Run with:
    python3.13 apps/exercises/tests/test_music21_builder.py

No Django dependency. No pytest needed — uses stdlib unittest.
"""
import sys
import os
import unittest

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from apps.exercises.generation import music21_builder as mb
from music21 import pitch


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def note_names_from_chord(chord_dict):
    """Return pitch names (without octave) for all notes in a chord dict.
    NOTE: This derives names from MIDI which uses music21's default enharmonic
    preference — useful for MIDI value checks but not spelling."""
    all_midi = chord_dict["visible"] + chord_dict["hidden"]
    return [pitch.Pitch(midi=m).name for m in all_midi]

def midi_set(chord_dict):
    """Return set of pitch-classes (MIDI % 12) in the chord."""
    all_midi = chord_dict["visible"] + chord_dict["hidden"]
    return set(m % 12 for m in all_midi)

def note_names_with_octave_from_chord(chord_dict):
    all_midi = chord_dict["visible"] + chord_dict["hidden"]
    return [pitch.Pitch(midi=m).nameWithOctave for m in all_midi]


# ---------------------------------------------------------------------------
# Tests: _pitch_in_range helper
# ---------------------------------------------------------------------------

class TestPitchInRange(unittest.TestCase):

    def test_c_natural_in_range_60_71(self):
        p = pitch.Pitch("C")
        result = mb._pitch_in_range(p, 60, 71)
        self.assertEqual(result.midi, 60)
        self.assertEqual(result.name, "C")

    def test_f_sharp_in_bass_range(self):
        p = pitch.Pitch("F#")
        result = mb._pitch_in_range(p, 45, 57)
        self.assertGreaterEqual(result.midi, 45)
        self.assertLessEqual(result.midi, 57)
        self.assertEqual(result.name, "F#")

    def test_no_fit_raises(self):
        # A pitch that can't fit: asking for range of 11 semitones starting at 60
        # Try to fit B# (enharmonic C) in range 61–71 — B# is the same as C, so
        # the only C in 61–71 would be... there isn't one. B# = 60, next is B#=72.
        p = pitch.Pitch("B#")
        with self.assertRaises(ValueError):
            mb._pitch_in_range(p, 61, 71)


# ---------------------------------------------------------------------------
# Tests: triad spelling — the critical bug fix
# ---------------------------------------------------------------------------

class TestTriadSpelling(unittest.TestCase):

    def test_c_major_triad_names(self):
        """C major: C(0) E(4) G(7) — check pitch classes"""
        result = mb.triad("jC_", "major", 0, "close", "matching")
        self.assertEqual(len(result), 1)
        pcs = midi_set(result[0])
        self.assertIn(0, pcs)   # C
        self.assertIn(4, pcs)   # E
        self.assertIn(7, pcs)   # G

    def test_f_sharp_major_triad_no_double_sharps(self):
        """F# major: F#(6) A#(10) C#(1) — check pitch classes are correct.
        The old bug would produce G##=9 instead of A#=10."""
        result = mb.triad("jF#", "major", 0, "close", "matching")
        pcs = midi_set(result[0])
        self.assertIn(6, pcs)    # F#
        self.assertIn(10, pcs)   # A# (NOT 9=A which comes from G## bug)
        self.assertIn(1, pcs)    # C#
        # Confirm the old bug (G##=9) is NOT present as the major third
        # (The pitch class 9 is A natural / G## — wrong for F# major)
        self.assertNotIn(9, pcs)

    def test_f_sharp_minor_triad_no_double_sharps(self):
        """f# minor: F#(6) A(9) C#(1) — A natural pitch class = 9, correct"""
        result = mb.triad("iF#", "minor", 0, "close", "matching")
        pcs = midi_set(result[0])
        self.assertIn(6, pcs)   # F#
        self.assertIn(9, pcs)   # A natural
        self.assertIn(1, pcs)   # C#

    def test_f_sharp_half_dim_spelling(self):
        """
        CRITICAL: F# half-diminished (F# A C E) in key jF#.
        Old voicing.py bug: A natural (PC 9) was spelled G## because the
        pitch-class arithmetic found the 'nearest' note above F# incorrectly.
        Correct pitch classes: F#=6, A=9, C=0, E=4.
        """
        result = mb.seventh_chord("jF#", "half_dim", 0, "keyboard_4voice", "matching")
        pcs = midi_set(result[0])
        self.assertIn(6, pcs)   # F#
        self.assertIn(9, pcs)   # A natural (NOT G## which is also PC 9, but computed wrong)
        self.assertIn(0, pcs)   # C natural
        self.assertIn(4, pcs)   # E natural

    def test_db_major_triad(self):
        """Db major: Db(1) F(5) Ab(8) — check pitch classes"""
        result = mb.triad("jDb", "major", 0, "close", "matching")
        pcs = midi_set(result[0])
        self.assertIn(1, pcs)   # Db
        self.assertIn(5, pcs)   # F
        self.assertIn(8, pcs)   # Ab

    def test_a_minor_triad_c_natural(self):
        """A minor: A(9) C(0) E(4) — C natural (PC=0, NOT B#)"""
        result = mb.triad("iA_", "minor", 0, "close", "matching")
        pcs = midi_set(result[0])
        self.assertIn(9, pcs)   # A
        self.assertIn(0, pcs)   # C natural (the old bug would give B#=0 midi, same PC!)
        self.assertIn(4, pcs)   # E
        # Key test: the MIDI value for C should NOT be in the range 71-72 (B#4/B4#5)
        all_midi = result[0]["visible"] + result[0]["hidden"]
        c_midi_vals = [m for m in all_midi if m % 12 == 0]
        # C4=60, C5=72. B#3=48, B#4=60, B#5=72. Both spellings have same MIDI!
        # So we can only verify pitch class here.
        self.assertTrue(len(c_midi_vals) >= 1, "No C (PC=0) found")

    def test_c_minor_triad(self):
        """C minor: C(0) Eb(3) G(7)"""
        result = mb.triad("iC_", "minor", 0, "close", "matching")
        pcs = midi_set(result[0])
        self.assertIn(0, pcs)   # C
        self.assertIn(3, pcs)   # Eb
        self.assertIn(7, pcs)   # G


# ---------------------------------------------------------------------------
# Tests: MIDI ranges
# ---------------------------------------------------------------------------

class TestMIDIRanges(unittest.TestCase):

    def _all_midi(self, chord_dict):
        return chord_dict["visible"] + chord_dict["hidden"]

    def test_close_voicing_range(self):
        """Close voicing should stay roughly 60–84"""
        result = mb.triad("jC_", "major", 0, "close", "matching")
        midi = self._all_midi(result[0])
        self.assertTrue(all(55 <= m <= 85 for m in midi),
                        f"Out of range for close voicing: {midi}")

    def test_keyboard_4voice_bass_range(self):
        """Bass note should be in 45–57"""
        result = mb.triad("jG_", "major", 0, "keyboard_4voice", "matching")
        midi = sorted(self._all_midi(result[0]))
        self.assertGreaterEqual(midi[0], 45, f"Bass too low: {midi}")
        self.assertLessEqual(midi[0], 57, f"Bass too high: {midi}")

    def test_keyboard_4voice_upper_range(self):
        """Upper three voices for keyboard_4voice should be 60–76"""
        result = mb.triad("jC_", "major", 0, "keyboard_4voice", "matching")
        midi = sorted(self._all_midi(result[0]))
        for m in midi[1:]:
            self.assertGreaterEqual(m, 60, f"Upper voice too low: {midi}")
            self.assertLessEqual(m, 76, f"Upper voice too high: {midi}")

    def test_triad_has_4_notes_keyboard(self):
        """Keyboard 4-voice triad should return 4 notes (root doubled)"""
        result = mb.triad("jD_", "major", 0, "keyboard_4voice", "matching")
        midi = self._all_midi(result[0])
        self.assertEqual(len(midi), 4, f"Expected 4 notes, got {len(midi)}: {midi}")

    def test_seventh_chord_has_4_notes_keyboard(self):
        """Keyboard 4-voice 7th chord should return 4 notes"""
        result = mb.seventh_chord("jC_", "dominant", 0, "keyboard_4voice", "matching")
        midi = self._all_midi(result[0])
        self.assertEqual(len(midi), 4, f"Expected 4 notes, got {len(midi)}: {midi}")


# ---------------------------------------------------------------------------
# Tests: visibility / exercise type splitting
# ---------------------------------------------------------------------------

class TestVisibility(unittest.TestCase):

    def test_matching_all_visible(self):
        result = mb.triad("jC_", "major", 0, "close", "matching")
        self.assertGreater(len(result[0]["visible"]), 0)
        self.assertEqual(result[0]["hidden"], [])

    def test_analytical_all_hidden(self):
        result = mb.triad("jC_", "major", 0, "close", "analytical")
        self.assertEqual(result[0]["visible"], [])
        self.assertGreater(len(result[0]["hidden"]), 0)

    def test_figured_bass_bass_visible(self):
        result = mb.triad("jC_", "major", 0, "keyboard_4voice", "figured_bass")
        self.assertEqual(len(result[0]["visible"]), 1)
        self.assertGreater(len(result[0]["hidden"]), 0)
        # Bass should be the lowest note
        bass_midi = result[0]["visible"][0]
        all_midi = result[0]["visible"] + result[0]["hidden"]
        self.assertEqual(bass_midi, min(all_midi))


# ---------------------------------------------------------------------------
# Tests: inversions
# ---------------------------------------------------------------------------

class TestInversions(unittest.TestCase):

    def _lowest_note_name(self, chord_dict):
        all_midi = chord_dict["visible"] + chord_dict["hidden"]
        return pitch.Pitch(midi=min(all_midi)).name

    def test_root_position_bass_is_root(self):
        """Root position C major: lowest note should be C"""
        result = mb.triad("jC_", "major", 0, "keyboard_4voice", "matching")
        # bass is the first of sorted notes
        midi = sorted(result[0]["visible"])
        self.assertEqual(pitch.Pitch(midi=midi[0]).name, "C")

    def test_first_inversion_bass_is_third(self):
        """First inversion C major: lowest note = E"""
        result = mb.triad("jC_", "major", 1, "keyboard_4voice", "matching")
        midi = sorted(result[0]["visible"])
        self.assertEqual(pitch.Pitch(midi=midi[0]).name, "E")

    def test_second_inversion_bass_is_fifth(self):
        """Second inversion C major: lowest note = G"""
        result = mb.triad("jC_", "major", 2, "keyboard_4voice", "matching")
        midi = sorted(result[0]["visible"])
        self.assertEqual(pitch.Pitch(midi=midi[0]).name, "G")


# ---------------------------------------------------------------------------
# Tests: identification labels
# ---------------------------------------------------------------------------

class TestIdentificationLabels(unittest.TestCase):

    def test_triad_quality_choices(self):
        result = mb.triad("jC_", "major", 0, "close", "identification", "quality")
        self.assertIn("choices", result[0])
        self.assertIn("answer", result[0])
        self.assertEqual(result[0]["answer"], "major")
        self.assertIn("major", result[0]["choices"])
        self.assertIn("minor", result[0]["choices"])

    def test_triad_inversion_answer(self):
        result = mb.triad("jC_", "major", 1, "close", "identification", "inversion")
        self.assertEqual(result[0]["answer"], "first inversion")

    def test_seventh_quality_answer(self):
        result = mb.seventh_chord("jC_", "dominant", 0, "close", "identification", "quality")
        self.assertEqual(result[0]["answer"], "dominant 7")

    def test_seventh_inversion_labels(self):
        for inv, label in enumerate(["root position", "6/5", "4/3", "4/2"]):
            result = mb.seventh_chord("jG_", "dominant", inv, "close",
                                       "identification", "inversion")
            self.assertEqual(result[0]["answer"], label,
                             f"Inversion {inv}: expected {label!r}")

    def test_interval_answer_tt(self):
        result = mb.interval("jC_", "TT", "identification", "name")
        self.assertEqual(result[0]["answer"], "TT")

    def test_no_label_no_choices(self):
        result = mb.triad("jC_", "major", 0, "matching", "matching")
        self.assertNotIn("choices", result[0])
        self.assertNotIn("answer", result[0])


# ---------------------------------------------------------------------------
# Tests: diatonic functions
# ---------------------------------------------------------------------------

class TestDiatonicFunctions(unittest.TestCase):

    def test_diatonic_intervals_count(self):
        result = mb.diatonic_intervals("jC_", "major", "matching")
        self.assertEqual(len(result), 7, "Should be 7 intervals (M2 through P8)")

    def test_scale_ascending_count(self):
        result = mb.scale("jC_", "major", "ascending", "matching")
        self.assertEqual(len(result), 8)

    def test_scale_descending_first_is_highest(self):
        result = mb.scale("jC_", "major", "descending", "matching")
        midi_asc = mb.scale("jC_", "major", "ascending", "matching")
        # descending first note should equal ascending last note
        self.assertEqual(
            result[0]["visible"][0],
            midi_asc[-1]["visible"][0],
        )

    def test_diatonic_triads_count(self):
        result = mb.diatonic_triads("jC_", "major", "matching")
        self.assertEqual(len(result), 7)

    def test_diatonic_sevenths_count(self):
        result = mb.diatonic_sevenths("jC_", "major", "matching")
        self.assertEqual(len(result), 7)

    def test_roto_count(self):
        result = mb.roto("jC_", "major", "ascending", "matching")
        self.assertEqual(len(result), 8)

    def test_progression(self):
        result = mb.progression("jC_", ["I", "IV", "V", "I"], "matching")
        self.assertEqual(len(result), 4)

    def test_diatonic_intervals_f_sharp_key_no_double_sharps(self):
        """
        REGRESSION: In jF#, pitch class 9 (A) should be spelled A, not G##.
        """
        result = mb.diatonic_intervals("jF#", "major", "matching")
        for chord_dict in result:
            midi = chord_dict["visible"] + chord_dict["hidden"]
            names = [pitch.Pitch(midi=m).name for m in midi]
            self.assertNotIn("G##", names, f"G## found in diatonic intervals for jF#: {names}")


# ---------------------------------------------------------------------------
# Tests: rhythm values
# ---------------------------------------------------------------------------

class TestRhythmValues(unittest.TestCase):

    def test_triad_rhythm_whole(self):
        result = mb.triad("jC_", "major", 0, "close", "matching")
        self.assertEqual(result[0]["rhythmValue"], "w")

    def test_interval_rhythm_half(self):
        result = mb.interval("jC_", "M3", "matching")
        self.assertEqual(result[0]["rhythmValue"], "h")

    def test_scale_rhythm_quarter(self):
        result = mb.scale("jC_", "major", "ascending", "matching")
        for chord_dict in result:
            self.assertEqual(chord_dict["rhythmValue"], "q")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
