from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.umto_factory import save_chordal_umto_exercise


class AnalysisReviewBadgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="badge@example.com", password="pw12345")

    def _make_chordal(self):
        return save_chordal_umto_exercise(
            description="Badge test exercise",
            author=self.user,
            chords=[{"offset": 0.0, "duration": 4.0, "visible": [60, 64, 67], "hidden": []}],
            key="jC_", meter="4/4", clef="keyboard", staff_distribution="keyboard",
        )

    def test_edit_page_shows_needs_review_badge(self):
        ex = self._make_chordal()
        # status should be "generated" right after save (analysis slices were built)
        self.client.force_login(self.user)
        resp = self.client.get(reverse("dashboard:edit-exercise", kwargs={"exercise_id": ex.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Needs review")
