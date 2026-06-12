"""Tests for the is_official field on Exercise and Playlist models,
including backfill migration logic.

Run with:
    python manage.py test apps.exercises.tests.test_is_official_field -v 1
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import Exercise, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


class ExerciseIsOfficialDefaultTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="x"
        )

    def test_exercise_default_false(self):
        ex = make_umto_exercise(self.user, description="default test")
        self.assertFalse(ex.is_official)

    def test_playlist_default_false(self):
        pl = Playlist.objects.create(
            name="Test Playlist",
            authored_by=self.user,
            skill_tags=["unit:1"],
        )
        self.assertFalse(pl.is_official)


class IsOfficialFilterTest(TestCase):
    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password="x"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="x"
        )

    def test_is_official_filter_exercise(self):
        official_ex = make_umto_exercise(
            self.factory_user, description="official exercise"
        )
        official_ex.is_official = True
        official_ex.save()

        unofficial_ex = make_umto_exercise(
            self.other_user, description="unofficial exercise"
        )

        official_ids = set(
            Exercise.objects.filter(is_official=True).values_list("id", flat=True)
        )
        self.assertIn(official_ex.id, official_ids)
        self.assertNotIn(unofficial_ex.id, official_ids)

    def test_is_official_filter_playlist(self):
        official_pl = Playlist.objects.create(
            name="Official Playlist",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
            is_official=True,
        )
        unofficial_pl = Playlist.objects.create(
            name="My Playlist",
            authored_by=self.other_user,
            skill_tags=["unit:1"],
        )

        official_ids = set(
            Playlist.objects.filter(is_official=True).values_list("id", flat=True)
        )
        self.assertIn(official_pl.id, official_ids)
        self.assertNotIn(unofficial_pl.id, official_ids)


class BackfillIsOfficialTest(TestCase):
    """Test the backfill logic: rows authored by factory@monteverdi.app
    get is_official=True after the backfill runs."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password="x"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="x"
        )

    def _run_backfill(self):
        """Replicate the migration backfill logic against real model classes."""
        factory_user = User.objects.filter(email="factory@monteverdi.app").first()
        if factory_user is None:
            return
        Exercise.objects.filter(authored_by=factory_user).update(is_official=True)
        Playlist.objects.filter(authored_by=factory_user).update(is_official=True)

    def test_backfill_sets_factory_exercise_official(self):
        ex = make_umto_exercise(self.factory_user, description="factory exercise")
        self.assertFalse(ex.is_official)
        self._run_backfill()
        ex.refresh_from_db()
        self.assertTrue(ex.is_official)

    def test_backfill_sets_factory_playlist_official(self):
        pl = Playlist.objects.create(
            name="Factory Playlist",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
        )
        self.assertFalse(pl.is_official)
        self._run_backfill()
        pl.refresh_from_db()
        self.assertTrue(pl.is_official)

    def test_backfill_does_not_set_non_factory_official(self):
        ex = make_umto_exercise(self.other_user, description="other exercise")
        pl = Playlist.objects.create(
            name="Other Playlist",
            authored_by=self.other_user,
            skill_tags=["unit:1"],
        )
        self._run_backfill()
        ex.refresh_from_db()
        pl.refresh_from_db()
        self.assertFalse(ex.is_official)
        self.assertFalse(pl.is_official)

    def test_backfill_noop_when_no_factory_user(self):
        # Delete the factory user; backfill should not error
        self.factory_user.delete()
        ex = make_umto_exercise(self.other_user, description="no factory")
        # Should not raise
        self._run_backfill()
        ex.refresh_from_db()
        self.assertFalse(ex.is_official)


class CourseDetailOfficialLabelTest(TestCase):
    """Verify that source="official" logic is correct based on is_official field."""

    def setUp(self):
        self.factory_user = User.objects.create_user(
            email="factory@monteverdi.app", password="x"
        )
        self.other_user = User.objects.create_user(
            email="teacher@example.com", password="x"
        )

    def _get_source(self, playlist):
        """Replicate the source label logic from course_detail view."""
        return "official" if playlist.is_official else "mine"

    def test_official_playlist_source_label(self):
        pl = Playlist.objects.create(
            name="Official Unit 1",
            authored_by=self.factory_user,
            skill_tags=["unit:1"],
            is_official=True,
        )
        self.assertEqual(self._get_source(pl), "official")

    def test_non_official_playlist_source_label(self):
        pl = Playlist.objects.create(
            name="My Custom Playlist",
            authored_by=self.other_user,
            skill_tags=["unit:1"],
        )
        self.assertEqual(self._get_source(pl), "mine")
