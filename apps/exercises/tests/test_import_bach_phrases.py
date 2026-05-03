import unittest


class BuildRomanAnalysisOverridesTestCase(unittest.TestCase):
    def _call(self, phrase_score, global_key, unit_tags):
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_roman_analysis_overrides,
        )

        return _build_roman_analysis_overrides(phrase_score, global_key, unit_tags)

    def test_stores_raw_roman_numeral_not_targeted(self):
        from music21 import chord, key as m21key, stream

        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        m.append(chord.Chord(["C4", "E4", "G4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        first = overrides[0]
        self.assertIn("raw_roman_numeral", first["content"])
        self.assertIsNotNone(first["content"]["raw_roman_numeral"])
        self.assertIsNone(first["content"]["roman_numeral"])

    def test_no_filter_applied_for_out_of_scope_chord(self):
        from music21 import chord, key as m21key, stream

        s = stream.Score()
        part = stream.Part()
        m = stream.Measure()
        m.append(chord.Chord(["D4", "F4", "A4"]))
        part.append(m)
        s.append(part)
        global_key = m21key.Key("C")
        overrides = self._call(s, global_key, [9])
        self.assertTrue(len(overrides) > 0)
        self.assertIsNotNone(overrides[0]["content"]["raw_roman_numeral"])
        self.assertIsNone(overrides[0]["content"]["roman_numeral"])
