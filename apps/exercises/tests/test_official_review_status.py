"""Tests for official review status fields."""

from django.test import TestCase

from apps.exercises.models import Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.teacher.tests.test_views_db import _make_playlist, _make_teacher


def _make_exercise(author):
    return save_chordal_umto_exercise(
        description="Reviewable Exercise",
        author=author,
        chords=[{"offset": 0.0, "duration": 4.0, "visible": [60, 64, 67], "hidden": []}],
        key="C",
        meter="4/4",
        clef="keyboard",
        staff_distribution="keyboard",
        source="test",
        skill_tags=[],
        complexity=1,
        is_public=False,
        auto_playlist=False,
    )


class OfficialReviewStatusModelTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()

    def test_playlist_defaults_to_none(self):
        playlist = _make_playlist(self.teacher)

        self.assertEqual(playlist.official_review_status, "none")

    def test_exercise_defaults_to_none(self):
        exercise = _make_exercise(self.teacher)

        self.assertEqual(exercise.official_review_status, "none")

    def test_can_set_pending(self):
        playlist = _make_playlist(self.teacher)
        playlist.official_review_status = "pending"
        playlist.save(update_fields=["official_review_status"])

        playlist.refresh_from_db()
        self.assertEqual(playlist.official_review_status, "pending")

    def test_can_set_approved(self):
        exercise = _make_exercise(self.teacher)
        exercise.official_review_status = "approved"
        exercise.save(update_fields=["official_review_status"])

        exercise.refresh_from_db()
        self.assertEqual(exercise.official_review_status, "approved")

    def test_invalid_status_raises(self):
        playlist = Playlist(name="Bad", authored_by=self.teacher)
        playlist.official_review_status = "unknown"

        with self.assertRaises(Exception):
            playlist.full_clean()
