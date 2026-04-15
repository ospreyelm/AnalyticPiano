from django.test import TestCase

from apps.exercises.pitch_voice_utils import strip_to_voice, validate_pitch_voice


class PitchVoiceUtilsTests(TestCase):
    def test_strip_to_voice_preserves_measure_fields(self):
        score = {
            "meta": {"key": "G"},
            "measures": [
                {
                    "number": 1,
                    "staves": {
                        "treble": {
                            "voices": [
                                {"items": [{"kind": "note"}]},
                                {"items": [{"kind": "note"}]},
                            ]
                        },
                        "bass": {
                            "voices": [
                                {"items": [{"kind": "note"}]},
                                {"items": [{"kind": "note"}]},
                            ]
                        },
                    },
                }
            ],
        }

        out = strip_to_voice(score, "soprano")

        self.assertEqual(out["measures"][0]["number"], 1)
        # Both staves must exist for vexflow_adapter to work correctly
        self.assertEqual(sorted(out["measures"][0]["staves"].keys()), ["bass", "treble"])
        # Soprano is treble voice 0: one voice with items
        self.assertEqual(len(out["measures"][0]["staves"]["treble"]["voices"]), 1)
        # Bass staff should be empty (no voices)
        self.assertEqual(len(out["measures"][0]["staves"]["bass"]["voices"]), 0)

    def test_validate_pitch_voice_rejects_chords(self):
        score = {
            "measures": [
                {
                    "number": 1,
                    "staves": {
                        "treble": {
                            "voices": [
                                {"items": [{"kind": "chord", "notes": []}]},
                            ]
                        }
                    },
                }
            ]
        }

        with self.assertRaises(ValueError):
            validate_pitch_voice(score, "soprano")

    def test_validate_pitch_voice_allows_rests(self):
        score = {
            "measures": [
                {
                    "number": 1,
                    "staves": {
                        "treble": {
                            "voices": [
                                {"items": [{"kind": "rest"}, {"kind": "note"}]},
                            ]
                        }
                    },
                }
            ]
        }

        validate_pitch_voice(score, "soprano")
