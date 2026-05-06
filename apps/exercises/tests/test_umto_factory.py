from unittest import TestCase
from unittest.mock import MagicMock, patch
from copy import deepcopy
from pydantic import ValidationError
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import NonUMTOExerciseError, build_umto_payload, save_umto_exercise

SINGLE_VOICE_CIR = {
    "meta": {"key": "C", "time": "4/4"},
    "measures": [
        {
            "staves": {
                "treble": {
                    "voices": [
                        {
                            "items": [
                                {"kind": "note", "pitch": {"step": "C", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "E", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                                {"kind": "note", "pitch": {"step": "F", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
                            ]
                        }
                    ]
                }
            }
        }
    ],
}

SATB_CIR = {
    "meta": {"key": "G", "time": "4/4"},
    "measures": [
        {
            "staves": {
                "treble": {
                    "voices": [
                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                        {"items": [{"kind": "note", "pitch": {"step": "D", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}]},
                    ]
                },
                "bass": {
                    "voices": [
                        {"items": [{"kind": "note", "pitch": {"step": "B", "alter": 0, "octave": 3}, "duration": {"type": "q", "dots": 0}}]},
                        {"items": [{"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 2}, "duration": {"type": "q", "dots": 0}}]},
                    ]
                },
            }
        }
    ],
}


class UMTOFactoryTests(TestCase):
    def test_non_umto_exercise_error_is_value_error_subclass(self):
        self.assertTrue(issubclass(NonUMTOExerciseError, ValueError))

    def test_non_umto_exercise_error_carries_message(self):
        err = NonUMTOExerciseError("test message")
        self.assertEqual(str(err), "test message")

    def test_build_umto_payload_single_voice_treble_identification(self):
        payload = build_umto_payload(
            exercise_id="TEMP",
            source="Test",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            score_data=SINGLE_VOICE_CIR,
            target_voice="soprano",
            unit=1,
        )

        self.assertTrue(payload["isUMTO"])
        self.assertEqual(payload["type"], "umto_chorale")
        self.assertEqual(payload["mode"], "identification")
        self.assertEqual(payload["clef"], "treble")
        self.assertEqual(payload["staffDistribution"], "treble")
        self.assertEqual(payload["complexity_score"], 1)
        self.assertEqual(payload["key"], "C")
        self.assertEqual(payload["meter"], "4/4")

        umto = payload["score"]["umto"]
        self.assertEqual(len(umto["voices"]["S"]), 4)
        self.assertEqual(umto["voices"]["S"][0]["pitch"]["midi"], 60)
        self.assertEqual(umto["voices"]["S"][1]["pitch"]["midi"], 62)
        self.assertEqual(umto["voices"]["S"][2]["pitch"]["midi"], 64)
        self.assertEqual(umto["voices"]["S"][3]["pitch"]["midi"], 65)
        self.assertEqual(len(umto["grading"]), 4)
        self.assertEqual(umto["grading"][0]["offset"], 0.0)
        self.assertEqual(umto["grading"][1]["offset"], 1.0)
        self.assertEqual(umto["grading"][2]["offset"], 2.0)
        self.assertEqual(umto["grading"][3]["offset"], 3.0)
        self.assertEqual(umto["grading"][0]["target_midi_pitches"], [60])
        self.assertEqual(len(umto["analysis"]), 4)
        self.assertEqual(umto["analysis"][0]["unit_tags"], [1])

    def test_build_umto_payload_satb_all_voices_playback(self):
        payload = build_umto_payload(
            exercise_id="TEMP",
            source="Test SATB",
            key="G",
            meter="4/4",
            clef="keyboard",
            complexity_score=9,
            mode=InteractionMode.PLAYBACK,
            score_data=SATB_CIR,
            target_voice=None,
            unit=9,
        )

        self.assertTrue(payload["isUMTO"])
        umto = payload["score"]["umto"]
        self.assertEqual(len(umto["voices"]["S"]), 1)
        self.assertEqual(len(umto["voices"]["A"]), 1)
        self.assertEqual(len(umto["voices"]["T"]), 1)
        self.assertEqual(len(umto["voices"]["B"]), 1)
        self.assertEqual(umto["voices"]["S"][0]["pitch"]["midi"], 67)
        self.assertEqual(umto["voices"]["A"][0]["pitch"]["midi"], 62)
        self.assertEqual(umto["voices"]["T"][0]["pitch"]["midi"], 59)
        self.assertEqual(umto["voices"]["B"][0]["pitch"]["midi"], 43)

    @patch("apps.exercises.umto_factory.Exercise")
    def test_save_umto_exercise_logic_flows(self, mock_exercise_class):
        mock_author = MagicMock()
        mock_instance = mock_exercise_class.return_value
        mock_instance.id = 999
        mock_instance.pk = 999
        mock_instance.data = {"score": {"umto": {"metadata": {}}}}

        ex = save_umto_exercise(
            description="Factory test",
            score_data=SINGLE_VOICE_CIR,
            author=mock_author,
            skill_tags=["unit:1", "Note_Names"],
            complexity=11,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Factory test",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.IDENTIFICATION,
                target_voice="soprano",
                unit=1,
            ),
        )

        self.assertEqual(mock_instance.save.call_count, 2)
        self.assertEqual(ex.data["exerciseId"], 999)
        self.assertEqual(ex.data["score"]["umto"]["metadata"]["exercise_id"], 999)

    @patch("apps.exercises.umto_factory.Exercise")
    def test_save_umto_exercise_can_skip_legacy_auto_playlist(self, mock_exercise_class):
        mock_author = MagicMock()
        mock_instance = mock_exercise_class.return_value
        mock_instance.id = 999
        mock_instance.pk = 999
        mock_instance.data = {"score": {"umto": {"metadata": {}}}}

        save_umto_exercise(
            description="Factory test",
            score_data=SINGLE_VOICE_CIR,
            author=mock_author,
            skill_tags=["unit:1", "Note_Names"],
            complexity=11,
            auto_playlist=False,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Factory test",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.IDENTIFICATION,
                target_voice="soprano",
                unit=1,
            ),
        )

        first_call = mock_instance.save.call_args_list[0]
        self.assertEqual(first_call.kwargs, {"skip_auto_playlist": True})

    def test_save_umto_exercise_rejects_legacy_score_data(self):
        mock_author = MagicMock()
        with self.assertRaises(NonUMTOExerciseError):
            save_umto_exercise(
                description="Bad",
                score_data={"meta": {}, "measures": []},  # empty → UMTO validation triggers
                author=mock_author,
                skill_tags=[],
                complexity=1,
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source="",
                    key="C",
                    meter="4/4",
                    clef="treble",
                    complexity_score=0,  # invalid: must be >=1
                    mode=InteractionMode.PLAYBACK,
                ),
            )

    def test_input_mode_defaults_to_dropdown(self):
        payload = build_umto_payload(
            exercise_id="TEMP",
            source="Test",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            score_data=SINGLE_VOICE_CIR,
            target_voice="soprano",
            unit=1,
        )

        self.assertEqual(payload["inputMode"], "dropdown")
        self.assertEqual(
            payload["score"]["umto"]["metadata"]["input_mode"],
            "dropdown",
        )

    def test_input_mode_text_round_trips_through_build_payload(self):
        payload = build_umto_payload(
            exercise_id="TEMP",
            source="Test",
            key="C",
            meter="4/4",
            clef="treble",
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            score_data=SINGLE_VOICE_CIR,
            target_voice="soprano",
            unit=1,
            input_mode="text",
        )

        self.assertEqual(payload["inputMode"], "text")
        self.assertEqual(
            payload["score"]["umto"]["metadata"]["input_mode"],
            "text",
        )

    @patch("apps.exercises.umto_factory.Exercise")
    def test_save_umto_exercise_propagates_input_mode_from_umto_kwargs(self, mock_exercise_class):
        mock_author = MagicMock()
        constructor_payloads = []

        def build_mock_exercise(**kwargs):
            constructor_payloads.append(deepcopy(kwargs["data"]))
            mock_instance = MagicMock()
            mock_instance.id = 999
            mock_instance.pk = 999
            mock_instance.data = kwargs["data"]
            return mock_instance

        mock_exercise_class.side_effect = build_mock_exercise

        ex = save_umto_exercise(
            description="Factory test",
            score_data=SINGLE_VOICE_CIR,
            author=mock_author,
            skill_tags=["unit:1", "Note_Names"],
            complexity=11,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Factory test",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.IDENTIFICATION,
                target_voice="soprano",
                unit=1,
                input_mode="text",
            ),
        )

        constructor_payload = constructor_payloads[0]
        self.assertEqual(constructor_payload["exerciseId"], "TEMP")
        self.assertEqual(
            constructor_payload["inputMode"],
            "text",
        )
        self.assertEqual(
            constructor_payload["score"]["umto"]["metadata"]["exercise_id"],
            "TEMP",
        )
        self.assertEqual(
            constructor_payload["score"]["umto"]["metadata"]["input_mode"],
            "text",
        )
        self.assertEqual(ex.data["exerciseId"], 999)
        self.assertEqual(ex.data["inputMode"], "text")
        self.assertEqual(
            ex.data["score"]["umto"]["metadata"]["exercise_id"],
            999,
        )
        self.assertEqual(
            ex.data["score"]["umto"]["metadata"]["input_mode"],
            "text",
        )

    def test_build_umto_payload_rejects_invalid_input_mode(self):
        with self.assertRaises(ValidationError):
            build_umto_payload(
                exercise_id="TEMP",
                source="Test",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.IDENTIFICATION,
                score_data=SINGLE_VOICE_CIR,
                target_voice="soprano",
                unit=1,
                input_mode="free_text",
            )
