from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Exercise


class DuplicateChoraleAsIdentificationTests(TestCase):
    def test_creates_identification_copy_from_chorale(self):
        author = User.objects.create_user(email="teacher@example.com", password="pw")
        source = Exercise(
            authored_by=author,
            is_public=True,
            description="BWV1.6 (mm. 1-4)",
            data={
                "type": "chorale",
                "score": {
                    "meta": {"key": "G", "time": "4/4"},
                    "measures": [
                        {
                            "staves": {
                                "treble": {
                                    "voices": [
                                        {
                                            "items": [
                                                {"kind": "note", "pitch": {"step": "G", "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}}
                                            ]
                                        }
                                    ]
                                },
                                "bass": {"voices": []},
                            }
                        }
                    ],
                },
                "staffDistribution": "chorale",
            },
        )
        source.save()

        # Refactored command no longer takes 'analysis' argument
        call_command(
            "duplicate_chorale_as_identification",
            str(source.id),
            author="teacher@example.com",
        )

        clone = Exercise.objects.exclude(id=source.id).latest("created")
        # Now expects UMTO structure
        self.assertEqual(clone.data["type"], "umto_chorale")
        self.assertEqual(clone.data["mode"], "identification")
        self.assertTrue(clone.data["isUMTO"])
        self.assertEqual(clone.authored_by_id, author.id)
        # Verify the score was preserved (via umto synthesis)
        self.assertIn("umto", clone.data["score"])
        self.assertEqual(clone.data["score"]["umto"]["voices"]["S"][0]["pitch"]["midi"], 67)
