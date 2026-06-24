from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import logging
import os

from apps.exercises.models import Exercise


class ViewUMTOLoggingTests(TestCase):
    def test_legacy_exercise_emits_warning_log(self):
        """
        Verifies that loading an exercise that claims to be UMTO but fails validation
        triggers the [LEGACY EXERCISE] logger warning.
        """
        os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"] = "1"
        try:
            User = get_user_model()
            author = User.objects.create(email="w@w.com")
            self.client.force_login(author)
            
            # Create a row that claims to be UMTO but has empty/invalid data
            ex = Exercise.objects.create(
                description="legacy failure",
                data={"isUMTO": True, "metadata": {}, "voices": {}}, # Missing required UMTO fields
                authored_by=author,
            )
            
            url = reverse("lab:exercise-view", kwargs={"exercise_id": ex.id})
            
            with self.assertLogs('apps.exercises.services.exercise_context', level='WARNING') as cm:
                self.client.get(url)
            
            self.assertTrue(any("[LEGACY EXERCISE]" in output for output in cm.output))
            self.assertTrue(any("failed UMTO validation" in output for output in cm.output))
        finally:
            del os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"]
