from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
import json
import random
from pathlib import Path
from unittest.mock import patch

from apps.accounts.models import ROLE_STUDENT, ROLE_TEACHER
from apps.exercises.models import (
    Course,
    Exercise,
    ExercisePlaylistOrdered,
    IdentificationAttempt,
    PerformanceData,
    Playlist,
    PlaylistCourseOrdered,
    StudentSkillMastery,
)
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode


User = get_user_model()
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "exercises" / "tests" / "fixtures" / "umto"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentUnitViewTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=30001,
            email="unit-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=30002,
            email="unit-author@test.com",
            password="x",
            is_staff=True,
        )
        self.course = Course.objects.create(
            _id=34001,
            title="Unit 1: Pitch & Staff Notation",
            authored_by=self.author,
            is_public=True,
        )
        self.treble_exercise = Exercise.objects.create(
            _id=31001,
            description="Treble note names",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        self.treble_playlist = Playlist.objects.create(
            _id=32001,
            name="Unit 1 - Note Names (Treble)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=33001,
            playlist=self.treble_playlist,
            exercise=self.treble_exercise,
            order=1,
        )
        PlaylistCourseOrdered.objects.create(
            _id=35001,
            playlist=self.treble_playlist,
            course=self.course,
            order=1,
        )
        self.client.force_login(self.student)

    def test_unit_page_shows_both_treble_and_bass_playlist_links(self):
        bass_exercise = Exercise.objects.create(
            _id=31002,
            description="Bass note names",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        bass_playlist = Playlist.objects.create(
            _id=32002,
            name="Unit 1 - Note Names (Bass)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=33002,
            playlist=bass_playlist,
            exercise=bass_exercise,
            order=1,
        )
        PlaylistCourseOrdered.objects.create(
            _id=35002,
            playlist=bass_playlist,
            course=self.course,
            order=2,
        )

        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "student/unit_progress.html")

    def test_student_unit_route_renders_curated_unit1_surface(self):
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "1"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "student/unit_progress.html")
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentUnitProgressBackLinkTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=39001,
            email="unit-back-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.client.force_login(self.student)

    def test_unit_progress_back_url_always_points_to_home(self):
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "9"}),
            HTTP_REFERER=reverse("student:player", kwargs={"unit_num": 9}) + "?playlist=PA01DN&exercise_num=1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], reverse("student:home"))
