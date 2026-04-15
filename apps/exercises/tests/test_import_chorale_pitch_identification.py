import json
import os

from django.core.management import CommandError, call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Exercise


class ImportChoralePitchIdentificationTests(TestCase):
    def setUp(self):
        self.author_email = "teacher@example.com"
        User.objects.create_user(email=self.author_email, password="pw")

        self.corpus_file = "tpi.json"
        self.corpus_path = os.path.join("data", "corpus", "bach", self.corpus_file)
        self.addCleanup(self._cleanup_corpus_file)

        corpus = {
            "score": {
                "meta": {"key": "C", "time": "4/4"},
                "measures": [
                    {
                        "number": 1,
                        "staves": {
                            "treble": {
                                "voices": [
                                    {"items": [{"kind": "note", "pitch": {"step": "C", "octave": 5}}]},
                                    {"items": [{"kind": "note", "pitch": {"step": "A", "octave": 4}}]},
                                ]
                            },
                            "bass": {
                                "voices": [
                                    {"items": [{"kind": "note", "pitch": {"step": "E", "octave": 3}}]},
                                    {"items": [{"kind": "note", "pitch": {"step": "C", "octave": 3}}]},
                                ]
                            },
                        },
                    }
                ],
            }
        }

        with open(self.corpus_path, "w") as f:
            json.dump(corpus, f)

    def _cleanup_corpus_file(self):
        if os.path.exists(self.corpus_path):
            os.remove(self.corpus_path)

    def test_pitch_analysis_requires_voice_in_identify_mode(self):
        with self.assertRaises(CommandError):
            call_command(
                "import_chorale",
                self.corpus_file,
                author=self.author_email,
                mode="identify",
                analysis="note_name",
                start=0,
                end=1,
            )

    def test_pitch_analysis_with_voice_creates_identification(self):
        call_command(
            "import_chorale",
            self.corpus_file,
            author=self.author_email,
            mode="identify",
            analysis="note_name",
            voice="soprano",
            start=0,
            end=1,
        )

        ex = Exercise.objects.latest("created")
        self.assertEqual(ex.data["type"], "chorale_identification")
        self.assertEqual(ex.data["analysisType"], "note_name")
