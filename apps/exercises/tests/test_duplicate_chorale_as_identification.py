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
                                "treble": {"voices": []},
                                "bass": {"voices": []},
                            }
                        }
                    ],
                },
                "staffDistribution": "chorale",
                "introText": "Play this excerpt.",
                "reviewText": "Done.",
            },
        )
        source.save()

        call_command(
            "duplicate_chorale_as_identification",
            str(source.id),
            author="teacher@example.com",
            analysis="roman",
        )

        clone = Exercise.objects.exclude(id=source.id).latest("created")
        self.assertEqual(clone.data["type"], "chorale_identification")
        self.assertEqual(clone.data["analysisType"], "roman")
        self.assertEqual(clone.data["identMode"], "submit")
        self.assertEqual(clone.data["score"], source.data["score"])
        self.assertEqual(clone.authored_by_id, author.id)
