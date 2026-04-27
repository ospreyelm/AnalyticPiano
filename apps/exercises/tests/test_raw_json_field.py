from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase

from apps.exercises.models import Playlist, RawJSONField

User = get_user_model()


class RawJSONFieldTests(SimpleTestCase):
    def test_from_db_value_accepts_already_decoded_dict(self):
        field = RawJSONField()
        value = {"kind": "note", "pitch": "C4"}

        self.assertEqual(field.from_db_value(value, None, None), value)

    def test_from_db_value_accepts_already_decoded_list(self):
        field = RawJSONField()
        value = [{"id": "EA0001"}]

        self.assertEqual(field.from_db_value(value, None, None), value)


class PlaylistSaveTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="playlist-save@test.com",
            password="testpass123",
            is_staff=True,
        )

    def test_save_force_insert_does_not_duplicate_second_internal_save(self):
        playlist = Playlist(
            name="Force Insert Playlist",
            authored_by=self.author,
            is_public=True,
        )

        try:
            playlist.save(force_insert=True)
        except IntegrityError as exc:  # pragma: no cover - current bug path
            self.fail(f"Playlist.save(force_insert=True) should not raise IntegrityError: {exc}")

        self.assertTrue(Playlist.objects.filter(pk=playlist.pk).exists())
