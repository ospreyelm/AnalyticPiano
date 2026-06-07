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
        # descending + shuffled: must NOT be sorted by the model
        c = ChordEvent(offset=0.0, duration=1.0, visible=[67, 36, 60], hidden=[72, 50])
        self.assertEqual(c.visible, [67, 36, 60])
        self.assertEqual(c.hidden, [72, 50])

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


from apps.exercises.umto import UMTO

META_VOICES = {"exercise_id": "T", "source": "t", "key": "C", "meter": "4/4",
               "complexity_score": 1, "score_kind": "voices"}
META_CHORDAL = {**META_VOICES, "score_kind": "chordal"}
ONE_CHORD = [{"offset": 0.0, "duration": 1.0, "visible": [60]}]


class TestUMTOValidator(TestCase):
    def test_chordal_requires_chords(self):
        with self.assertRaises(ValidationError):
            UMTO.model_validate({"metadata": META_CHORDAL, "chords": []})

    def test_chordal_ok_without_voices(self):
        obj = UMTO.model_validate({"metadata": META_CHORDAL, "chords": ONE_CHORD})
        self.assertEqual(obj.metadata.score_kind, "chordal")
        self.assertEqual(len(obj.chords), 1)

    def test_voices_kind_requires_explicit_voices(self):
        with self.assertRaises(ValidationError):
            UMTO.model_validate({"metadata": META_VOICES})

    def test_voices_kind_ok_with_explicit_voices(self):
        obj = UMTO.model_validate({
            "metadata": META_VOICES,
            "voices": {"S": [], "A": [], "T": [], "B": []},
        })
        self.assertEqual(obj.metadata.score_kind, "voices")


import json, os


class TestSchemaUpToDate(TestCase):
    def test_schema_contains_chord_and_score_kind(self):
        path = os.path.join(os.path.dirname(__file__), "..", "umto_schema.json")
        with open(path) as f:
            schema = json.load(f)
        text = json.dumps(schema)
        self.assertIn("ChordEvent", text)
        self.assertIn("score_kind", text)


from apps.exercises.umto_factory import build_chordal_umto_payload
from apps.exercises.umto import InteractionMode, UMTO


class TestChordalFactory(TestCase):
    def test_payload_stores_chords_under_score_umto(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP",
            source="Rule of the octave, C major, 3 voices",
            key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]}],
            analysis=[],
        )
        umto = payload["score"]["umto"]
        self.assertEqual(umto["metadata"]["score_kind"], "chordal")
        self.assertEqual(len(umto["chords"]), 1)
        self.assertEqual(payload["type"], "umto_chorale")
        self.assertTrue(payload["isUMTO"])

    def test_payload_validates_against_umto(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP", source="t", key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60]}], analysis=[],
        )
        UMTO.model_validate(payload["score"]["umto"])  # must not raise


class TestChordalMeasures(TestCase):
    def test_chords_become_measures_with_chord_items(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP", source="t", key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67]},
                {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69]},
            ],
            analysis=[],
        )
        measures = payload["score"]["measures"]
        self.assertTrue(len(measures) >= 1)
        first_items = measures[0]["staves"]["treble"]["voices"][0]["items"]
        self.assertEqual(first_items[0]["kind"], "chord")
        # chord carries a notes[] of {pitch:{step,alter,octave}}
        self.assertEqual(len(first_items[0]["notes"]), 3)
        self.assertIn("pitch", first_items[0]["notes"][0])
        p = first_items[0]["notes"][0]["pitch"]
        self.assertEqual({"step", "alter", "octave"} <= set(p.keys()), True)

    def test_single_pitch_becomes_note_item(self):
        payload = build_chordal_umto_payload(
            exercise_id="TEMP", source="t", key="C", meter="4/4", clef="keyboard",
            complexity_score=1, mode=InteractionMode.PLAYBACK,
            chords=[{"offset": 0.0, "duration": 1.0, "visible": [60]}], analysis=[],
        )
        item = payload["score"]["measures"][0]["staves"]["treble"]["voices"][0]["items"][0]
        self.assertEqual(item["kind"], "note")
        self.assertEqual(item["pitch"]["octave"], 4)   # MIDI 60 -> C4

    def test_midi_to_pitch_octave_correct(self):
        from apps.exercises.umto_factory import _midi_to_cir_pitch
        self.assertEqual(_midi_to_cir_pitch(60), {"step": "C", "alter": 0, "octave": 4})
        self.assertEqual(_midi_to_cir_pitch(61), {"step": "C", "alter": 1, "octave": 4})
        self.assertEqual(_midi_to_cir_pitch(72), {"step": "C", "alter": 0, "octave": 5})


from apps.exercises.umto_factory import legacy_chord_row_to_chordal_payload


class TestLegacyWrap(TestCase):
    def test_legacy_chord_array_wraps_to_chordal(self):
        legacy_data = {
            "type": "matching", "key": "C",
            "chord": [
                {"visible": [60, 64, 67], "hidden": []},
                {"visible": [62, 65, 69], "hidden": []},
            ],
        }
        payload = legacy_chord_row_to_chordal_payload(legacy_data)
        umto = payload["score"]["umto"]
        self.assertEqual(umto["metadata"]["score_kind"], "chordal")
        self.assertEqual(len(umto["chords"]), 2)
        self.assertEqual(umto["chords"][0]["visible"], [60, 64, 67])


class TestRoundTripEquivalence(TestCase):
    def test_wrapped_legacy_matches_legacy_grading_semantics(self):
        legacy = {"type": "matching", "key": "C",
                  "chord": [{"visible": [67, 60, 64], "hidden": []}]}
        payload = legacy_chord_row_to_chordal_payload(legacy)
        chords = payload["score"]["umto"]["chords"]
        # visible order preserved from source
        self.assertEqual(chords[0]["visible"], [67, 60, 64])
        # gradeable notes = sorted(visible+hidden) — matches the JS chordsToProblems() contract
        notes = sorted(chords[0]["visible"] + chords[0]["hidden"])
        self.assertEqual(notes, [60, 64, 67])
