"""Tests for the save-with-transpositions endpoint.

Regression coverage for a prod incident: an official (save_as_official=True)
MusicXML import created its inline transpositions under the factory user
(correct), but the follow-up "File it" call to save-with-transpositions
created a second, duplicate batch under the real logged-in user instead of
the factory user. Since generate_transposed_copies dedupes on
(description, authored_by), the author mismatch meant the duplicate batch
was never recognized as already existing, doubling the exercise count.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import ROLE_TEACHER
from apps.exercises.models import Exercise
from apps.exercises.umto_factory import save_chordal_umto_exercise

User = get_user_model()


class SaveWithTranspositionsAuthorTest(TestCase):
    def setUp(self):
        self.client = Client()

        self.superuser = User.objects.create_superuser(
            email="super@example.com", password="testpass123"
        )

        factory_email = getattr(settings, "FACTORY_USER_EMAIL", "factory@example.com")
        self.factory_user, _ = User.objects.get_or_create(
            email=factory_email,
            defaults={"is_staff": True, "is_superuser": True},
        )

        # Simulate the exercise as it would exist after an official
        # MusicXML-import save: authored by the factory user.
        self.official_source = save_chordal_umto_exercise(
            description="Rule of the Octave in 3 parts",
            author=self.factory_user,
            chords=[
                {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
            ],
            key="jC_",
            meter=None,
            clef="keyboard",
            staff_distribution="keyboard",
            barline_offsets=[],
            analysis_type="figured_bass_unabbreviated",
        )

    def test_official_transpositions_authored_by_factory_user_not_requester(self):
        """When is_official=True, created transpositions must be authored by the
        factory user (matching the original save), not request.user — otherwise
        a later duplicate call isn't deduped and doubles the exercise count."""
        self.client.login(email="super@example.com", password="testpass123")

        response = self.client.post(
            reverse("teacher:save-with-transpositions"),
            data={
                "exerciseId": self.official_source.id,
                "key_set": ["G"],
                "is_official": True,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        created_id = response.json()["created"][0]
        created = Exercise.objects.get(id=created_id)
        self.assertEqual(created.authored_by, self.factory_user)

    def test_repeated_official_call_is_idempotent(self):
        """Calling save-with-transpositions twice for the same official source
        and key must not create a duplicate batch."""
        self.client.login(email="super@example.com", password="testpass123")

        body = {
            "exerciseId": self.official_source.id,
            "key_set": ["G"],
            "is_official": True,
        }
        self.client.post(
            reverse("teacher:save-with-transpositions"), data=body, content_type="application/json"
        )
        self.client.post(
            reverse("teacher:save-with-transpositions"), data=body, content_type="application/json"
        )

        matches = Exercise.objects.filter(description="Rule of the Octave in 3 parts (G)")
        self.assertEqual(matches.count(), 1)
