"""Tests for teacher-app playlist editor views."""

import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_chordal_umto_exercise
from apps.teacher.tests.test_views_db import _make_playlist, _make_teacher


def _make_exercise(author, public=True):
    return save_chordal_umto_exercise(
        description="Ex",
        author=author,
        chords=[{"offset": 0.0, "duration": 4.0, "visible": [60, 64, 67], "hidden": []}],
        key="C",
        meter="4/4",
        clef="keyboard",
        staff_distribution="keyboard",
        source="test",
        skill_tags=[],
        complexity=1,
        is_public=public,
        auto_playlist=False,
    )


class PlaylistDetailTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.playlist = _make_playlist(self.teacher, name="PL")
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_get_200(self):
        response = self.client.get(
            reverse("teacher:playlist-detail", args=[self.playlist.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PL")

    def test_other_teacher_private_playlist_404(self):
        other = _make_teacher(email="other@example.com")
        playlist = _make_playlist(other, name="Private")

        response = self.client.get(reverse("teacher:playlist-detail", args=[playlist.id]))

        self.assertEqual(response.status_code, 404)

    def test_public_playlist_readable_by_other_teacher(self):
        other = _make_teacher(email="other@example.com")
        playlist = Playlist.objects.create(
            name="Pub",
            authored_by=other,
            is_public=True,
        )

        response = self.client.get(reverse("teacher:playlist-detail", args=[playlist.id]))

        self.assertEqual(response.status_code, 200)


class PlaylistSaveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.playlist = _make_playlist(self.teacher)
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def _post(self, payload):
        return self.client.post(
            reverse("teacher:playlist-save", args=[self.playlist.id]),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_save_updates_name(self):
        self._post({"name": "Renamed"})

        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.name, "Renamed")

    def test_save_updates_skill_tags(self):
        self._post({"skill_tags": ["unit:9", "Cadence_PAC"]})

        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.skill_tags, ["unit:9", "Cadence_PAC"])

    def test_save_trims_name_to_64_chars(self):
        self._post({"name": "x" * 100})

        self.playlist.refresh_from_db()
        self.assertLessEqual(len(self.playlist.name), 64)

    def test_other_teacher_cannot_save(self):
        other = _make_teacher(email="other@example.com")
        client = Client()
        client.login(email=other.email, password="pass")

        response = client.post(
            reverse("teacher:playlist-save", args=[self.playlist.id]),
            data=json.dumps({"name": "Stolen"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)


class PlaylistAddRemoveTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher()
        self.playlist = _make_playlist(self.teacher)
        self.exercise = _make_exercise(self.teacher)
        self.client = Client()
        self.client.login(email=self.teacher.email, password="pass")

    def test_add_exercise(self):
        response = self.client.post(
            reverse("teacher:playlist-add-exercise", args=[self.playlist.id]),
            data=json.dumps({"exerciseId": self.exercise.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ExercisePlaylistOrdered.objects.filter(
                playlist=self.playlist,
                exercise=self.exercise,
            ).exists()
        )

    def test_remove_exercise(self):
        ordered = ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.exercise,
            order=0,
        )

        response = self.client.post(
            reverse("teacher:playlist-remove-exercise", args=[self.playlist.id, ordered.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ExercisePlaylistOrdered.objects.filter(pk=ordered.pk).exists())

    def test_reorder_exercises(self):
        second_exercise = _make_exercise(self.teacher)
        first_ordered = ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=self.exercise,
            order=0,
        )
        second_ordered = ExercisePlaylistOrdered.objects.create(
            playlist=self.playlist,
            exercise=second_exercise,
            order=1,
        )

        response = self.client.post(
            reverse("teacher:playlist-reorder", args=[self.playlist.id]),
            data=json.dumps({"order": [second_ordered.pk, first_ordered.pk]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        first_ordered.refresh_from_db()
        second_ordered.refresh_from_db()
        self.assertEqual(second_ordered.order, 0)
        self.assertEqual(first_ordered.order, 1)
