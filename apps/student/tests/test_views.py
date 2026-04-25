from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
import json
from pathlib import Path

from apps.exercises.models import (
    Course,
    Exercise,
    ExercisePlaylistOrdered,
    Playlist,
    PlaylistCourseOrdered,
)


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

    def test_login_page_uses_monteverdi_branding(self):
        response = self.client.get(reverse("student:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monteverdi")
        self.assertNotContains(response, "HarmonyLab")

    def test_login_post_valid_redirects_to_home(self):
        response = self.client.post(
            reverse("student:login"),
            {"email": "sarah@test.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("student:home"))

    def test_login_post_invalid_rerenders_form(self):
        response = self.client.post(
            reverse("student:login"),
            {"email": "nobody@test.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"form", response.content.lower())

    def test_home_redirects_unauthenticated_to_student_login(self):
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/s/login/", response["Location"])

    def test_home_redirects_instructor_to_dashboard(self):
        self.client.force_login(self.instructor)
        response = self.client.get(reverse("student:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard/", response["Location"])

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

    def test_unit_view_returns_200_for_student(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))
        self.assertEqual(response.status_code, 200)

    def test_unit_page_uses_monteverdi_branding(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Monteverdi")
        self.assertNotContains(response, "HarmonyLab")

    def test_unit_view_context_has_skills(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("student:unit", kwargs={"unit_num": 1}))
        self.assertIn("skills", response.context)
        self.assertGreaterEqual(len(response.context["skills"]), 1)

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
class StudentPlayerViewTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=20001,
            email="student-case@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=20002,
            email="author-case@test.com",
            password="x",
            is_staff=True,
        )
        self.exercise = Exercise.objects.create(
            _id=21001,
            description="Unit 1 note names",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        self.playlist = Playlist.objects.create(
            _id=22001,
            name="Unit 1 - Note Names (Treble)",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23001,
            playlist=self.playlist,
            exercise=self.exercise,
            order=1,
        )
        self.course = Course.objects.create(
            _id=24001,
            title="Unit 1: Pitch & Staff Notation",
            authored_by=self.author,
            is_public=True,
        )
        PlaylistCourseOrdered.objects.create(
            _id=25001,
            playlist=self.playlist,
            course=self.course,
            order=1,
        )
        self.client.force_login(self.student)

    def test_player_returns_200_with_exercise_num(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )
        self.assertEqual(response.status_code, 200)

    def test_player_context_has_course_id(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.course.id).encode(), response.content)

    def test_player_redirects_to_unit_when_exercise_num_exceeds_playlist(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=999"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("student:unit", kwargs={"unit_num": 1}))

    def test_player_next_url_stays_in_student_player(self):
        second_exercise = Exercise.objects.create(
            _id=21002,
            description="Unit 1 note names 2",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23002,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/s/units/1/play/?playlist=", response.content)
        self.assertNotIn(b"/lab/", response.content)

    def test_player_uses_force_redirect_for_student_navigation(self):
        second_exercise = Exercise.objects.create(
            _id=21003,
            description="Unit 1 note names 3",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23003,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"forceRedirect": true', response.content)

    def test_player_navigation_buttons_have_visible_labels(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b">Previous<", response.content)
        self.assertIn(b">Reset<", response.content)
        self.assertIn(b">Next<", response.content)

    def test_player_page_does_not_render_harmonylab_branding(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "HarmonyLab")

    def test_player_disables_computer_keyboard_for_unit1_playback_note_names(self):
        with open(FIXTURES_DIR / "unit1_playback_treble.json") as fh:
            umto_data = json.load(fh)

        self.exercise.data = umto_data
        self.exercise.description = "BWV1.6 m.1-2 Soprano (exact) S1"
        self.exercise.skill_tags = ["unit:1", "Note_Names"]
        self.exercise.complexity = 1
        self.exercise.save(update_fields=["data", "description", "skill_tags", "complexity"])
        self.playlist.name = "Unit 1 - Note Names (Treble Play)"
        self.playlist.save(update_fields=["name"])

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"disableComputerKeyboardInput": true', response.content)
        self.assertIn(b"Use MIDI or click the on-screen piano.", response.content)


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
        self.assertIn(str(self.treble_playlist.id).encode(), response.content)
        self.assertIn(str(bass_playlist.id).encode(), response.content)

    def test_get_playlists_for_tag_finds_playlist_with_only_tags_field(self):
        from apps.student.views import _get_playlists_for_tag

        tags_only_playlist = Playlist.objects.create(
            _id=32003,
            name="Unit 1 - Tags Only",
            authored_by=self.author,
            is_public=True,
            skill_tags=[],
            tags=["unit:1", "Note_Names"],
        )

        results = _get_playlists_for_tag("Note_Names")
        result_ids = [item["id"] for item in results]

        self.assertIn(tags_only_playlist.id, result_ids)
