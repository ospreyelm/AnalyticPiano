# apps/exercises/tests/test_chordal_umto.py
from unittest import TestCase
from pydantic import ValidationError
from apps.exercises.umto import ChordEvent


class TestChordEvent(TestCase):
    def test_minimal_chord(self):
        c = ChordEvent(offset=0.0, duration=1.0, visible=[60, 64, 67])
        self.assertEqual(c.visible, [60, 64, 67])
        self.assertEqual(c.hidden, [])
        self.assertIsNone(c.spelling)

    def test_input_order_preserved(self):
        # bass-first ordering must NOT be sorted
        c = ChordEvent(offset=0.0, duration=1.0, visible=[36, 60, 64])
        self.assertEqual(c.visible, [36, 60, 64])

    def test_spelling_length_must_match_visible_plus_hidden(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=0.0, duration=1.0, visible=[60, 64], spelling=["C4"])

    def test_spelling_ok_when_length_matches(self):
        c = ChordEvent(offset=0.0, duration=1.0, visible=[60], hidden=[64],
                       spelling=["C4", "E4"])
        self.assertEqual(c.spelling, ["C4", "E4"])

    def test_negative_offset_rejected(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=-1.0, duration=1.0, visible=[60])

    def test_nonpositive_duration_rejected(self):
        with self.assertRaises(ValidationError):
            ChordEvent(offset=0.0, duration=0.0, visible=[60])


from apps.exercises.umto import Metadata


class TestScoreKind(TestCase):
    def _meta(self, **kw):
        base = dict(exercise_id="T", source="t", key="C", meter="4/4",
                    complexity_score=1)
        base.update(kw)
        return Metadata(**base)

    def test_default_is_voices(self):
        self.assertEqual(self._meta().score_kind, "voices")

    def test_chordal_allowed(self):
        self.assertEqual(self._meta(score_kind="chordal").score_kind, "chordal")

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValidationError):
            self._meta(score_kind="bogus")
