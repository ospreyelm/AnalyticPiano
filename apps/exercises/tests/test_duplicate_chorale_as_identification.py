from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Exercise
from apps.exercises.tests.umto_test_helpers import make_umto_exercise


class DuplicateChoraleAsIdentificationTests(TestCase):
    def test_creates_identification_copy_from_chorale(self):
        author = User.objects.create_user(email="teacher@example.com", password="pw")
        source = make_umto_exercise(
            author=author,
            description="BWV1.6 (mm. 1-4)",
            complexity=1,
            unit=1
        )

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
