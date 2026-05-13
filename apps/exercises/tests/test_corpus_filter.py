from django.test import SimpleTestCase
from apps.exercises.utils.corpus_filter import assign_level, SMALLEST_VALUE_ORDER, is_valid_phrase, double_durations, phrase_fingerprint


class CorpusFilterLevelAssignmentTests(SimpleTestCase):
    """assign_level returns the lowest matching level, or None if no level matches."""

    def test_simple_quarter_only_is_level_1(self):
        self.assertEqual(assign_level("3/4", "q"), 1)

    def test_simple_quarter_in_44_is_level_1(self):
        self.assertEqual(assign_level("4/4", "q"), 1)

    def test_simple_24_quarter_only_is_level_2_not_1(self):
        self.assertEqual(assign_level("2/4", "q"), 2)

    def test_simple_eighth_is_level_2(self):
        self.assertEqual(assign_level("3/4", "8"), 2)

    def test_simple_sixteenth_is_level_3(self):
        self.assertEqual(assign_level("4/4", "16"), 3)

    def test_compound_dotted_quarter_is_level_4(self):
        self.assertEqual(assign_level("6/8", "q", dots=1), 4)

    def test_compound_eighth_is_level_5(self):
        self.assertEqual(assign_level("6/8", "8"), 5)

    def test_compound_sixteenth_is_level_6(self):
        self.assertEqual(assign_level("9/8", "16"), 6)

    def test_derived_simple_half_is_level_7(self):
        self.assertEqual(assign_level("3/2", "h"), 7)

    def test_derived_compound_quarter_is_level_8(self):
        self.assertEqual(assign_level("6/4", "q"), 8)

    def test_unsupported_meter_returns_none(self):
        self.assertIsNone(assign_level("5/4", "q"))

    def test_whole_note_in_simple_is_level_1(self):
        self.assertEqual(assign_level("4/4", "w"), 1)


class CorpusFilterValidityTests(SimpleTestCase):
    def _notes(self, *specs):
        return [{"pitch": "B4", "duration": d, "dots": dot} for d, dot in specs]

    def test_valid_phrase_passes(self):
        notes = self._notes(("q", 0), ("q", 0), ("q", 0), ("q", 0), ("q", 0), ("h", 0))
        self.assertTrue(is_valid_phrase("3/4", notes, measures=2))

    def test_last_note_shorter_than_preceding_fails(self):
        notes = self._notes(("h", 0), ("q", 0), ("q", 0), ("q", 0), ("q", 0), ("8", 0))
        self.assertFalse(is_valid_phrase("3/4", notes, measures=2))

    def test_wrong_total_duration_fails(self):
        notes = self._notes(("q", 0), ("q", 0), ("q", 0), ("q", 0))
        self.assertFalse(is_valid_phrase("3/4", notes, measures=2))

    def test_single_note_phrase_is_valid(self):
        notes = self._notes(("h", 0), ("h", 0))
        self.assertTrue(is_valid_phrase("2/2", notes, measures=1))

    def test_compound_meter_valid(self):
        notes = self._notes(("q", 1), ("q", 1))
        self.assertTrue(is_valid_phrase("6/8", notes, measures=1))

    def test_unsupported_meter_fails(self):
        notes = self._notes(("q", 0), ("q", 0))
        self.assertFalse(is_valid_phrase("5/4", notes, measures=1))


class CorpusFilterDoublingTests(SimpleTestCase):
    def test_eighth_becomes_quarter(self):
        notes = [{"pitch": "B4", "duration": "8", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "q", "dots": 0}])

    def test_dotted_eighth_becomes_dotted_quarter(self):
        notes = [{"pitch": "B4", "duration": "8", "dots": 1}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "q", "dots": 1}])

    def test_sixteenth_becomes_eighth(self):
        notes = [{"pitch": "B4", "duration": "16", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "8", "dots": 0}])

    def test_quarter_becomes_half(self):
        notes = [{"pitch": "B4", "duration": "q", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "h", "dots": 0}])

    def test_dotted_quarter_becomes_dotted_half(self):
        notes = [{"pitch": "B4", "duration": "q", "dots": 1}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "h", "dots": 1}])

    def test_half_becomes_whole(self):
        notes = [{"pitch": "B4", "duration": "h", "dots": 0}]
        self.assertEqual(double_durations(notes), [{"pitch": "B4", "duration": "w", "dots": 0}])

    def test_whole_note_raises_overflow(self):
        notes = [{"pitch": "B4", "duration": "w", "dots": 0}]
        with self.assertRaises(ValueError):
            double_durations(notes)

    def test_dotted_half_raises_overflow(self):
        notes = [{"pitch": "B4", "duration": "h", "dots": 1}]
        with self.assertRaises(ValueError):
            double_durations(notes)

    def test_multiple_notes_all_doubled(self):
        notes = [
            {"pitch": "B4", "duration": "8", "dots": 0},
            {"pitch": "C5", "duration": "q", "dots": 0},
        ]
        result = double_durations(notes)
        self.assertEqual(result[0]["duration"], "q")
        self.assertEqual(result[1]["duration"], "h")


class CorpusFilterFingerprintTests(SimpleTestCase):
    def _notes(self, *specs):
        return [{"pitch": p, "duration": d, "dots": dot} for p, d, dot in specs]

    def test_same_rhythm_different_pitch_same_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("C5", "h", 0))
        n2 = self._notes(("G4", "q", 0), ("A4", "h", 0))
        self.assertEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("3/4", n2))

    def test_different_rhythm_different_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("B4", "h", 0))
        n2 = self._notes(("B4", "h", 0), ("B4", "q", 0))
        self.assertNotEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("3/4", n2))

    def test_different_meter_different_fingerprint(self):
        n1 = self._notes(("B4", "q", 0), ("B4", "q", 0))
        self.assertNotEqual(phrase_fingerprint("3/4", n1), phrase_fingerprint("4/4", n1))

    def test_fingerprint_is_12_char_hex(self):
        n = self._notes(("B4", "q", 0))
        fp = phrase_fingerprint("3/4", n)
        self.assertEqual(len(fp), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))
