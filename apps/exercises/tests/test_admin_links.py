from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.exercises.admin import _student_exercise_url, _student_playlist_url
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

User = get_user_model()


class AdminStudentLinkTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.exercise = Exercise.objects.create(
            _id=51001,
            description="Unit 11 item",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:11", "Predominant_Function"],
        )
        self.playlist = Playlist.objects.create(
            _id=52001,
            name="Unit 11 - Pre-dominants",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:11", "Predominant_Function"],
            tags=["unit:11", "Predominant_Function"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=53001,
            playlist=self.playlist,
            exercise=self.exercise,
            order=3,
        )

    def test_student_playlist_url_prefers_student_player(self):
        self.assertEqual(
            _student_playlist_url(self.playlist),
            reverse("student:player", kwargs={"unit_num": 11})
            + f"?playlist={self.playlist.id}&exercise_num=1",
        )

    def test_student_exercise_url_uses_playlist_position(self):
        self.assertEqual(
            _student_exercise_url(self.exercise),
            reverse("student:player", kwargs={"unit_num": 11})
            + f"?playlist={self.playlist.id}&exercise_num=3",
        )
