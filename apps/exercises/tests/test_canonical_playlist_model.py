"""Tests for canonical teacher playlist identity."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase

from apps.exercises.models import Playlist

User = get_user_model()


class CanonicalPlaylistIdentityTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="x",
        )

    def test_duplicate_canonical_identity_raises_integrity_error(self):
        with transaction.atomic():
            Playlist.objects.create(
                name="Teacher Play A",
                authored_by=self.teacher,
                playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                canonical_unit="9",
                canonical_mode="roman",
            )

            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Playlist.objects.create(
                        name="Teacher Play B",
                        authored_by=self.teacher,
                        playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                        canonical_unit="9",
                        canonical_mode="roman",
                    )

    def test_different_canonical_modes_are_allowed(self):
        Playlist.objects.create(
            name="Teacher Play A",
            authored_by=self.teacher,
            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
            canonical_unit="9",
            canonical_mode="roman",
        )

        playlist = Playlist.objects.create(
            name="Teacher Play B",
            authored_by=self.teacher,
            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
            canonical_unit="9",
            canonical_mode="figures",
        )

        self.assertIsNotNone(playlist.pk)

    def test_malformed_teacher_play_identity_raises_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Playlist.objects.create(
                    name="Teacher Play Missing Unit",
                    authored_by=self.teacher,
                    playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                    canonical_mode="roman",
                )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Playlist.objects.create(
                    name="Teacher Play Blank Mode",
                    authored_by=self.teacher,
                    playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                    canonical_unit="9",
                    canonical_mode="",
                )

    def test_duplicate_noncanonical_rows_are_allowed(self):
        first = Playlist.objects.create(
            name="Draft A",
            authored_by=self.teacher,
            canonical_unit="9",
            canonical_mode="roman",
        )
        second = Playlist.objects.create(
            name="Draft B",
            authored_by=self.teacher,
            canonical_unit="9",
            canonical_mode="roman",
        )

        self.assertIsNotNone(first.pk)
        self.assertIsNotNone(second.pk)

    def test_canonical_unit_accepts_branch_unit_token(self):
        playlist = Playlist.objects.create(
            name="Teacher Play Branch B17",
            authored_by=self.teacher,
            playlist_family=Playlist.FAMILY_TEACHER_PLAY,
            canonical_unit="B17",
            canonical_mode="figures",
        )
        playlist.refresh_from_db()
        self.assertEqual(playlist.canonical_unit, "B17")
