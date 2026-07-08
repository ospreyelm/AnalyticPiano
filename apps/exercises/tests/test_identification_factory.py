"""Tests for apps/exercises/identification_factory.py (U2).

Covers the extracted save_umto_chord_id_exercise: spelling/timeSignature
payload additions, back-compat (no spelling), overwrite path, and the
no-per-problem-hidden-flag regression (identification payloads use a flat
"notes" key, not the visible/hidden split — and never a boolean "hidden").
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from apps.exercises.identification_factory import save_umto_chord_id_exercise


class SaveUmmtoChordIdExerciseTest(TestCase):
    def _chords_with_spelling(self):
        return [
            {
                "notes": [48, 64, 67, 72],
                "answer": "major",
                "choices": ["major", "minor"],
                "rhythmValue": "w",
                "spelling": ["c/3", "e/4", "g/4", "c/5"],
            },
            {
                "notes": [51, 67, 70, 75],
                "answer": "major",
                "choices": ["major", "minor"],
                "rhythmValue": "w",
                "spelling": ["eb/3", "g/4", "bb/4", "eb/5"],
            },
        ]

    @patch("apps.exercises.identification_factory.Exercise")
    def test_chords_with_spelling_persisted_and_time_signature(self, mock_exercise_class):
        mock_author = MagicMock()
        mock_instance = mock_exercise_class.return_value
        mock_instance.id = 999

        save_umto_chord_id_exercise(
            description="Unit 5 test",
            author=mock_author,
            chord_key="jC_",
            chords=self._chords_with_spelling(),
            skill_tags=["unit:5"],
            complexity=5,
        )

        payload = mock_exercise_class.call_args.kwargs["data"]
        self.assertEqual(payload["timeSignature"], "4/4")
        self.assertEqual(payload["meter"], "4/4")
        self.assertEqual(len(payload["chord"]), 2)
        self.assertEqual(payload["chord"][0]["spelling"], ["c/3", "e/4", "g/4", "c/5"])
        self.assertEqual(payload["chord"][1]["spelling"], ["eb/3", "g/4", "bb/4", "eb/5"])
        # notes are sorted on save
        self.assertEqual(payload["chord"][0]["notes"], [48, 64, 67, 72])

    @patch("apps.exercises.identification_factory.Exercise")
    def test_chords_without_spelling_back_compat(self, mock_exercise_class):
        mock_author = MagicMock()
        mock_exercise_class.return_value.id = 1

        chords = [
            {
                "notes": [60, 64, 67],
                "answer": "major",
                "choices": ["major", "minor"],
            }
        ]
        save_umto_chord_id_exercise(
            description="Legacy",
            author=mock_author,
            chord_key="jC_",
            chords=chords,
            skill_tags=["unit:5"],
            complexity=5,
        )

        payload = mock_exercise_class.call_args.kwargs["data"]
        # spelling present but None — legacy exercises keep the frontend fallback.
        self.assertIsNone(payload["chord"][0]["spelling"])
        # timeSignature is always set on the top-level payload.
        self.assertEqual(payload["timeSignature"], "4/4")

    @patch("apps.exercises.identification_factory.Exercise")
    def test_single_chord_path_spelling_none(self, mock_exercise_class):
        mock_author = MagicMock()
        mock_exercise_class.return_value.id = 1

        save_umto_chord_id_exercise(
            description="Single",
            author=mock_author,
            chord_key="jG_",
            midi_notes=[67, 71, 74],
            answer="major",
            choices=["major", "minor"],
            skill_tags=["unit:5"],
            complexity=5,
        )

        payload = mock_exercise_class.call_args.kwargs["data"]
        self.assertEqual(len(payload["chord"]), 1)
        self.assertIsNone(payload["chord"][0]["spelling"])
        self.assertEqual(payload["chord"][0]["notes"], [67, 71, 74])
        self.assertEqual(payload["timeSignature"], "4/4")

    @patch("apps.exercises.identification_factory.Exercise")
    def test_overwrite_updates_existing_row_payload(self, mock_exercise_class):
        mock_author = MagicMock()
        existing = MagicMock()
        existing.id = 42
        mock_exercise_class.objects.filter.return_value.first.return_value = existing

        save_umto_chord_id_exercise(
            description="Overwrite me",
            author=mock_author,
            chord_key="jEb",
            chords=self._chords_with_spelling(),
            skill_tags=["unit:5"],
            complexity=5,
            overwrite=True,
        )

        # Overwrite path reassigns ex.data = payload, so existing.data is the payload.
        self.assertEqual(existing.data["timeSignature"], "4/4")
        self.assertEqual(existing.data["chord"][0]["spelling"], ["c/3", "e/4", "g/4", "c/5"])
        # id-stamping mutates the assigned payload.
        self.assertEqual(existing.data["exerciseId"], 42)
        self.assertEqual(existing.data["score"]["umto"]["metadata"]["exercise_id"], 42)
        # must have saved at least once with the data field.
        self.assertTrue(existing.save.called)

    @patch("apps.exercises.identification_factory.Exercise")
    def test_no_per_problem_hidden_flag_introduced(self, mock_exercise_class):
        """Identification chord entries use a flat 'notes' key, never a boolean
        'hidden' (the documented identification payload footgun)."""
        mock_author = MagicMock()
        mock_exercise_class.return_value.id = 1

        save_umto_chord_id_exercise(
            description="No hidden",
            author=mock_author,
            chord_key="jC_",
            chords=self._chords_with_spelling(),
            skill_tags=["unit:5"],
            complexity=5,
        )

        payload = mock_exercise_class.call_args.kwargs["data"]
        for entry in payload["chord"]:
            self.assertNotIn("hidden", entry)
            self.assertIn("notes", entry)

    def test_requires_chords_or_midi_notes(self):
        with self.assertRaises(ValueError):
            save_umto_chord_id_exercise(
                description="Bad",
                author=MagicMock(),
                chord_key="jC_",
                skill_tags=["unit:5"],
                complexity=5,
            )