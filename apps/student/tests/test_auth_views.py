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
class StudentBasicViewTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=10001,
            email="sarah@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.instructor = User.objects.create_user(
            id=10002,
            email="prof@test.com",
            password="testpass123",
            is_staff=True,
        )

    def test_login_get_returns_200(self):
        response = self.client.get(reverse("student:login"))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_teacher_login_get_redirects_to_teacher_courses(self):
        self.instructor.role = ROLE_TEACHER
        self.instructor.save(update_fields=["role"])
        self.client.force_login(self.instructor)

        response = self.client.get(reverse("student:login"))

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_login_page_uses_monteverdi_branding(self):
        response = self.client.get(reverse("student:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monteverdi")
        self.assertNotContains(response, "HarmonyLab")

    def test_student_base_header_uses_post_logout_form(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            content,
            rf'<form[^>]*method="post"[^>]*action="{reverse("student:logout")}"',
        )
        self.assertIn("csrfmiddlewaretoken", content)
        self.assertNotIn(f'href="{reverse("student:logout")}"', content)

    def test_login_post_valid_redirects_to_home(self):
        response = self.client.post(
            reverse("student:login"),
            {"email": "sarah@test.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("student:home"))

    def test_login_post_restores_safe_guarded_student_destination(self):
        guarded_path = reverse(
            "student:unit-progress",
            kwargs={"unit_n": "1"},
        )
        guarded_response = self.client.get(guarded_path)
        login_url = guarded_response["Location"]

        login_response = self.client.get(login_url)
        self.assertEqual(login_response.status_code, 200)

        response = self.client.post(
            login_url,
            {"email": "sarah@test.com", "password": "testpass123"},
        )

        self.assertRedirects(
            response,
            guarded_path,
            fetch_redirect_response=False,
        )

    def test_login_post_rejects_external_next_and_redirects_to_student_home(self):
        response = self.client.post(
            f"{reverse('student:login')}?next=https://example.com/steal",
            {"email": "sarah@test.com", "password": "testpass123"},
        )

        self.assertRedirects(
            response,
            reverse("student:home"),
            fetch_redirect_response=False,
        )

    def test_teacher_login_post_redirects_to_teacher_courses(self):
        self.instructor.role = ROLE_TEACHER
        self.instructor.save(update_fields=["role"])

        response = self.client.post(
            f"{reverse('student:login')}?next={reverse('student:home')}",
            {"email": "prof@test.com", "password": "testpass123"},
        )

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_login_post_invalid_rerenders_form(self):
        response = self.client.post(
            reverse("student:login"),
            {"email": "nobody@test.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"form", response.content.lower())

    def test_student_logout_get_returns_405(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("student:logout"))

        self.assertEqual(response.status_code, 405)

    def test_student_logout_post_redirects_to_student_login(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("student:logout"))

        self.assertRedirects(
            response,
            reverse("student:login"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_home_redirects_unauthenticated_to_student_login(self):
        response = self.client.get(reverse("student:home"))
        self.assertRedirects(
            response,
            f"{reverse('student:login')}?next={reverse('student:home')}",
            fetch_redirect_response=False,
        )

    def test_home_redirects_teacher_to_teacher_courses(self):
        self.instructor.role = ROLE_TEACHER
        self.instructor.save(update_fields=["role"])
        self.client.force_login(self.instructor)

        response = self.client.get(reverse("student:home"))

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )

    def test_staff_student_is_not_treated_as_teacher(self):
        staff_student = User.objects.create_user(
            email="staff-student@example.com",
            password="testpass123",
            role=ROLE_STUDENT,
            is_staff=True,
        )
        self.client.force_login(staff_student)

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)

    def test_home_returns_200_for_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 200)

    def test_home_page_uses_monteverdi_branding(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monteverdi")
        self.assertNotContains(response, "HarmonyLab")

    def test_home_context_has_units(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        self.assertIn("units", response.context)
        self.assertGreaterEqual(len(response.context["units"]), 1)

    def test_home_context_has_resume_url_when_in_progress(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:home"))
        self.assertIn("resume_url", response.context)

    def test_unit_view_redirects_unit1_to_curated_progress_surface(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "student/unit_progress.html")

    def test_unit_page_uses_monteverdi_branding(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "1"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monteverdi")
        self.assertNotContains(response, "HarmonyLab")

    def test_unit_view_context_has_curated_activity_cards(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "1"})
        )
        self.assertIn("activity_cards", response.context)

    def test_player_view_404_without_playlist_param(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:player", kwargs={"unit_num": 1}))
        self.assertEqual(response.status_code, 404)

    def test_player_view_404_with_bad_playlist_id(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1}) + "?playlist=NONEXISTENT"
        )
        self.assertEqual(response.status_code, 404)

    def test_player_view_200_with_valid_playlist(self):
        exercise = Exercise.objects.create(
            _id=11001,
            data={"chord": []},
            authored_by=self.student,
            is_public=True,
        )
        playlist = Playlist.objects.create(
            _id=12001,
            name="Test Playlist",
            authored_by=self.student,
            is_public=True,
            tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=13001,
            playlist=playlist,
            exercise=exercise,
            order=1,
        )
        course = Course.objects.create(
            _id=14001,
            title="Unit 1 Test Course",
            authored_by=self.student,
            is_public=True,
        )
        PlaylistCourseOrdered.objects.create(
            _id=15001,
            playlist=playlist,
            course=course,
            order=1,
        )
        self.client.force_login(self.student)

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={playlist.id}"
        )
        self.assertEqual(response.status_code, 200)
@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentRoleBoundaryTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="role-boundary-teacher@test.com",
            password="testpass123",
            role=ROLE_TEACHER,
        )
        self.client.force_login(self.teacher)

    def test_anonymous_challenge_redirects_to_student_login_with_next(self):
        self.client.logout()
        path = reverse(
            "student:unit1-challenge",
            kwargs={"group_key": "treble"},
        )

        response = self.client.get(path)

        self.assertRedirects(
            response,
            f"{reverse('student:login')}?next={path}",
            fetch_redirect_response=False,
        )

    def test_anonymous_unit_progress_redirects_to_student_login_with_next(self):
        self.client.logout()
        path = reverse("student:unit-progress", kwargs={"unit_n": "1"})

        response = self.client.get(path)

        self.assertRedirects(
            response,
            f"{reverse('student:login')}?next={path}",
            fetch_redirect_response=False,
        )

    def test_teacher_challenge_redirects_before_creating_playlist(self):
        lane_keys = [
            "identify_treble",
            "play_from_name_treble",
            "play_the_notes_treble",
        ]
        exercises = [
            make_umto_exercise(
                self.teacher,
                description=f"Challenge source {index}",
            )
            for index in range(6)
        ]
        source_exercises = {
            lane_key: exercises[index * 2 : index * 2 + 2]
            for index, lane_key in enumerate(lane_keys)
        }
        progress = {
            "bar_segments": [
                {"tag": lane_key, "level": "proficient"}
                for lane_key in lane_keys
            ]
        }
        playlist_count = Playlist.objects.count()

        with (
            patch(
                "apps.student.unit_progress.get_unit_progress_data",
                return_value=progress,
            ),
            patch(
                "apps.student.unit1_curriculum.get_unit1_challenge_source_exercises",
                return_value=source_exercises,
            ),
        ):
            response = self.client.get(
                reverse("student:unit1-challenge", kwargs={"group_key": "treble"})
            )

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )
        self.assertEqual(Playlist.objects.count(), playlist_count)

    def test_teacher_unit_progress_redirects_to_teacher_courses(self):
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "1"})
        )

        self.assertRedirects(
            response,
            reverse("teacher:course-list"),
            fetch_redirect_response=False,
        )
