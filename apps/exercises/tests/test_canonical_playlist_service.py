from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import (
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
)
from apps.exercises.services.canonical_playlist import (
    append_exercise_to_canonical_playlist,
    resolve_canonical_playlist,
)
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


class CanonicalPlaylistServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="teacher@example.com",
            password="x",
        )
        self.other_author = User.objects.create_user(
            email="other-teacher@example.com",
            password="x",
        )
        self.performer = User.objects.create_user(
            email="performer@example.com",
            password="x",
        )
        self.exercise = make_umto_exercise(
            self.author,
            description="First canonical service exercise",
            unit=11,
        )
        self.other_exercise = make_umto_exercise(
            self.author,
            description="Second canonical service exercise",
            unit=11,
        )

    def resolve(self, **overrides):
        params = {
            "author": self.author,
            "unit": 11,
            "mode": "roman",
            "is_public": False,
            "is_official": False,
        }
        params.update(overrides)
        return resolve_canonical_playlist(**params)

    def test_first_resolution_creates_canonical_playlist(self):
        playlist = self.resolve(unit="11", mode="roman", is_public=True)

        self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")
        self.assertEqual(playlist.skill_tags, ["unit:11"])
        self.assertTrue(playlist.is_public)
        self.assertFalse(playlist.is_official)
        self.assertEqual(playlist.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
        self.assertEqual(playlist.canonical_unit, 11)
        self.assertEqual(playlist.canonical_mode, "roman")

    def test_repeat_resolution_reuses_same_playlist(self):
        first = self.resolve(unit=11, mode="roman")
        second = self.resolve(unit=11, mode="roman")

        self.assertEqual(second.pk, first.pk)

    def test_public_resolution_promotes_but_private_resolution_does_not_demote(self):
        playlist = self.resolve(is_public=False)
        self.assertFalse(playlist.is_public)

        self.resolve(is_public=True)
        playlist.refresh_from_db()
        self.assertTrue(playlist.is_public)

        self.resolve(is_public=False)
        playlist.refresh_from_db()
        self.assertTrue(playlist.is_public)

    def test_official_resolution_promotes_but_unofficial_resolution_does_not_demote(self):
        playlist = self.resolve(is_official=False)
        self.assertFalse(playlist.is_official)

        self.resolve(is_official=True)
        playlist.refresh_from_db()
        self.assertTrue(playlist.is_official)

        self.resolve(is_official=False)
        playlist.refresh_from_db()
        self.assertTrue(playlist.is_official)

    def test_different_authors_get_different_playlists(self):
        first = self.resolve(author=self.author)
        second = self.resolve(author=self.other_author)

        self.assertNotEqual(first.pk, second.pk)

    def test_exact_legacy_row_is_adopted(self):
        legacy = Playlist.objects.create(
            name="Unit 11 — Exercises (Roman)",
            authored_by=self.author,
            skill_tags=["unit:11"],
        )

        resolved = self.resolve(unit=11, mode="roman")

        self.assertEqual(resolved.pk, legacy.pk)
        self.assertEqual(resolved.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
        self.assertEqual(resolved.canonical_unit, 11)
        self.assertEqual(resolved.canonical_mode, "roman")

    def test_ambiguous_legacy_rows_raise(self):
        for _ in range(2):
            Playlist.objects.create(
                name="Unit 11 — Exercises (Roman)",
                authored_by=self.author,
                skill_tags=["unit:11"],
            )

        with self.assertRaisesMessage(ValueError, "Multiple legacy playlists match"):
            self.resolve(unit=11, mode="roman")

    def test_contradictory_legacy_tags_raise(self):
        Playlist.objects.create(
            name="Unit 11 — Exercises (Roman)",
            authored_by=self.author,
            skill_tags=["unit:12"],
        )

        with self.assertRaisesMessage(ValueError, "contradictory unit tags"):
            self.resolve(unit=11, mode="roman")

    def test_corpus_playlist_is_not_reused(self):
        corpus = Playlist.objects.create(
            name="Unit 11 — Cadences (roman)",
            authored_by=self.author,
            skill_tags=["unit:11"],
        )

        resolved = self.resolve(unit=11, mode="roman")

        self.assertNotEqual(resolved.pk, corpus.pk)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaisesMessage(
            ValueError,
            "Unsupported interaction mode: counterpoint",
        ):
            self.resolve(mode="counterpoint")

    def test_performed_playlist_rejects_append(self):
        playlist = self.resolve()
        PerformanceData.objects.create(
            user=self.performer,
            playlist=playlist,
            data=[],
        )

        with self.assertRaisesMessage(
            ValueError,
            "Canonical playlist is locked because it has been performed.",
        ):
            append_exercise_to_canonical_playlist(playlist, self.exercise)

    def test_noncanonical_playlist_rejects_append(self):
        playlist = Playlist.objects.create(
            name="Legacy Draft Playlist",
            authored_by=self.author,
            skill_tags=["unit:11"],
        )

        with self.assertRaisesMessage(ValueError, "canonical"):
            append_exercise_to_canonical_playlist(playlist, self.exercise)

    def test_append_uses_next_order(self):
        playlist = self.resolve()

        append_exercise_to_canonical_playlist(playlist, self.exercise)
        append_exercise_to_canonical_playlist(playlist, self.other_exercise)

        self.assertEqual(
            list(
                ExercisePlaylistOrdered.objects.filter(playlist=playlist)
                .order_by("order")
                .values_list("order", flat=True)
            ),
            [1, 2],
        )
