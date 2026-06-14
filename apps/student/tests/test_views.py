from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
import json
import random
from pathlib import Path
from unittest.mock import patch

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
class PlayerViewTests(TransactionTestCase):
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

    def test_player_returns_404_for_private_playlist_without_access(self):
        self.playlist.is_public = False
        self.playlist.save(update_fields=["is_public"])

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 404)

    def test_player_allows_private_playlist_with_content_permit(self):
        self.playlist.is_public = False
        self.playlist.save(update_fields=["is_public"])
        self.author.content_permits = [self.student.id]
        self.author.save(update_fields=["content_permits"])

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)

    def test_player_redirects_future_step_to_current_pending_step(self):
        second_exercise = Exercise.objects.create(
            _id=21004,
            description="Unit 1 note names 4",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23004,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=2"
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1",
        )

    def test_player_allows_completed_prior_step_in_review_mode(self):
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[{"id": self.exercise.id, "score_numerator": 1, "score_denominator": 1}],
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review mode")
        self.assertIn(b'"reviewMode": true', response.content)
        self.assertIn(b'"previousExerciseId": false', response.content)

    def test_player_review_mode_uses_submitted_identification_answers(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            playlist=self.playlist,
            exercise=self.exercise,
            answers={"0": "Student answer"},
            correct_answers={"0": "Answer key"},
            score={"correct": 1, "incorrect": 0, "unanswered": 0},
            is_page_submit=True,
            mode="submit",
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('"reviewMode": true', content)
        self.assertIn('"reviewAnswers": {"0": "Student answer"}', content)
        self.assertNotIn('"reviewAnswers": {"0": "Answer key"}', content)

    def test_player_sets_next_navigation_metadata_for_review_mode(self):
        second_exercise = Exercise.objects.create(
            _id=21005,
            description="Unit 1 note names 5",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23005,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )
        PerformanceData.objects.create(
            user=self.student,
            playlist=self.playlist,
            course=None,
            data=[
                {"id": self.exercise.id, "score_numerator": 1, "score_denominator": 1},
                {"id": second_exercise.id, "score_numerator": 1, "score_denominator": 1},
            ],
        )

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'"nextExerciseId": "{second_exercise.id}"'.encode(), response.content)
        self.assertIn(
            (
                reverse("student:player", kwargs={"unit_num": 1})
                + f"?playlist={self.playlist.id}&exercise_num=2"
            ).encode(),
            response.content,
        )

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

    def test_player_renders_barline_placement_with_qa_template(self):
        self.exercise.data = {
            "type": "umto_barline_placement",
            "isUMTO": True,
            "mode": "identification",
            "time_signature": "3/4",
            "show_time_signature": False,
            "clef": "treble",
            "measures": 1,
            "pickup_beats": 0,
            "pitch_mode": "rhythm_only",
            "notes": [{"pitch": "B4", "duration": "q", "dots": 0}] * 3,
            "note_beat_onsets": [0, 1, 2],
            "correct_barline_positions": [],
            "beat_count": 3,
            "beat_positions_ticks": [0, 1, 2, 3],
            "source": "student barline test",
            "tags": ["unit:1"],
        }
        self.exercise.save(update_fields=["data"])

        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "qa_player.html")
        self.assertIn("exercise_config_json", response.context)
        self.assertIn(b'"type": "umto_barline_placement"', response.content)

    def test_player_initial_payload_includes_playlist_metadata_without_force_redirect(self):
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
        self.assertIn(f'"playlistId": "{self.playlist.id}"'.encode(), response.content)
        self.assertIn(b'"totalExercises": 2', response.content)
        self.assertNotIn(b'"forceRedirect": true', response.content)

    def test_player_definition_returns_json_payload_for_current_step(self):
        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["exerciseNum"], 1)
        self.assertEqual(payload["playlistId"], self.playlist.id)
        self.assertEqual(payload["totalExercises"], 1)
        self.assertFalse(payload["reviewMode"])

    def test_player_definition_returns_redirect_payload_for_skipped_step(self):
        second_exercise = Exercise.objects.create(
            _id=21006,
            description="Unit 1 note names 6",
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=23006,
            playlist=self.playlist,
            exercise=second_exercise,
            order=2,
        )

        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "redirect": reverse("student:player", kwargs={"unit_num": 1})
                + f"?playlist={self.playlist.id}&exercise_num=1"
            },
        )

    def test_player_definition_includes_review_answers_in_review_mode(self):
        IdentificationAttempt.objects.create(
            user=self.student,
            playlist=self.playlist,
            exercise=self.exercise,
            answers={"0": "Student answer"},
            correct_answers={"0": "Answer key"},
            score={"correct": 1, "incorrect": 0, "unanswered": 0},
            is_page_submit=True,
            mode="submit",
        )

        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["reviewMode"])
        self.assertEqual(payload["reviewAnswers"], {"0": "Student answer"})
        self.assertNotEqual(payload["reviewAnswers"], {"0": "Answer key"})

    def test_player_page_exposes_definition_endpoint_and_chrome_hooks(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            reverse("student:player-definition", kwargs={"unit_num": 1}).encode(),
            response.content,
        )
        self.assertIn(b"window.PLAYER_DEFINITION_URL", response.content)
        self.assertIn(b"window.refreshPlayerChrome", response.content)

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
        self.assertIn(b'"mode": "playback"', response.content)
        self.assertIn(b'"analysisType": "note_name"', response.content)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class Unit4PersonalizedServingViewTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=26001,
            email="unit4-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=26002,
            email="unit4-author@test.com",
            password="x",
            is_staff=True,
        )
        self.playlist = Playlist.objects.create(
            name="Unit 4 - Specific Intervals: Stage 4",
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:4", "Interval_Specific", "unit:4_L4"],
            tags=["unit:4", "Interval_Specific", "unit:4_L4"],
        )
        self.exercises = []
        for idx in range(1, 9):
            exercise = make_umto_exercise(
                self.author,
                description=f"Unit 4 Specific Worksheet {idx}",
                skill_tags=["unit:4", "Interval_Specific", "unit:4_L4"],
                unit=4,
                mode=InteractionMode.IDENTIFICATION,
                input_mode="dropdown",
            )
            exercise.data["analysisType"] = "interval_specific"
            exercise.save(update_fields=["data"])
            ExercisePlaylistOrdered.objects.create(
                playlist=self.playlist,
                exercise=exercise,
                order=idx,
            )
            self.exercises.append(exercise)
        self.client.force_login(self.student)

    def _expected_first_exercise(self):
        ordered_ids = [exercise.id for exercise in self.exercises]
        rng = random.Random(f"{self.student.id}:{self.playlist.id}:unit4")
        rng.shuffle(ordered_ids)
        return ordered_ids[0]

    def test_player_view_caps_unit4_total_exercises_at_six(self):
        response = self.client.get(
            reverse("student:player", kwargs={"unit_num": 4})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_exercises"], 6)

    def test_player_definition_uses_personalized_unit4_order(self):
        response = self.client.get(
            reverse("student:player-definition", kwargs={"unit_num": 4})
            + f"?playlist={self.playlist.id}&exercise_num=1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["exerciseId"], self._expected_first_exercise())

    def test_identification_submission_uses_personalized_unit4_order(self):
        payload = {
            "course_ID": None,
            "playlist_ID": self.playlist.id,
            "exercise_num": 1,
            "answers": {"0": "P5"},
            "correctness": {"0": True},
            "score": {"correct": 1, "incorrect": 0, "unanswered": 0},
            "correct_answers": {"0": "P5"},
            "page_num": 0,
            "is_page_submit": True,
            "mode": "practice",
            "attempt_type": "practice",
        }

        response = self.client.post(
            reverse("lab:identification-answers"),
            {"data": json.dumps(payload)},
        )

        self.assertEqual(response.status_code, 201)
        attempt = IdentificationAttempt.objects.get(user=self.student, playlist=self.playlist)
        self.assertEqual(attempt.exercise.id, self._expected_first_exercise())


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
class StudentHomeResumeTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=37001,
            email="resume-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=37002,
            email="resume-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)

    def _make_lane_playlist(self, pk, name):
        playlist = Playlist.objects.create(
            _id=pk,
            name=name,
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        exercise = Exercise.objects.create(
            _id=pk + 100,
            description=name,
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=pk + 200,
            playlist=playlist,
            exercise=exercise,
            order=1,
        )
        return playlist, exercise

    def test_home_resume_uses_canonical_unit1_lane_order(self):
        identify_treble, identify_treble_exercise = self._make_lane_playlist(
            37100, "Unit 1 - Identify the Notes (Treble)"
        )
        identify_bass, _ = self._make_lane_playlist(
            37200, "Unit 1 - Identify the Notes (Bass)"
        )
        self._make_lane_playlist(37300, "Unit 1 - Play from Name (Treble)")
        self._make_lane_playlist(37400, "Unit 1 - Play from Name (Bass)")
        self._make_lane_playlist(37500, "Unit 1 - Play the Notes (Treble)")
        self._make_lane_playlist(37600, "Unit 1 - Play the Notes (Bass)")
        legacy_identify_treble, _ = self._make_lane_playlist(
            37700, "Unit 1 - Note Names (Treble)"
        )
        legacy_identify_bass, _ = self._make_lane_playlist(
            37800, "Unit 1 - Note Names (Bass)"
        )

        PerformanceData.objects.create(
            user=self.student,
            playlist=identify_treble,
            course=None,
            data=[{"id": identify_treble_exercise.id, "score_numerator": 1, "score_denominator": 1}],
        )

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={identify_bass.id}&exercise_num=1",
        )
        self.assertNotEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={legacy_identify_treble.id}&exercise_num=1",
        )
        self.assertNotEqual(
            response.context["resume_url"],
            reverse("student:player", kwargs={"unit_num": 1})
            + f"?playlist={legacy_identify_bass.id}&exercise_num=1",
        )
        self.assertEqual(
            response.context["units"][0]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "1"}),
        )


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentHomeUnitDiscoveryTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=38001,
            email="unit-discovery-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=38002,
            email="unit-discovery-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)

    def _make_playlist(self, pk, name, skill_tags):
        return Playlist.objects.create(
            _id=pk,
            name=name,
            authored_by=self.author,
            is_public=True,
            skill_tags=skill_tags,
            tags=skill_tags,
        )

    def test_home_discovers_units_with_accessible_playlists(self):
        self._make_playlist(38100, "Unit 1 - Identify the Notes (Treble)", ["unit:1", "Note_Names"])
        self._make_playlist(38101, "Unit 9 - Tonic & dominant", ["unit:9", "Tonic_Triad", "Dominant_Triad"])
        self._make_playlist(38102, "Unit 11 - Pre-dominants", ["unit:11", "Predominant_Function"])
        self._make_playlist(38103, "Unit 12 - Second inversions", ["unit:12", "Second_Inversion"])

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        units = response.context["units"]
        by_num = {unit["num"]: unit for unit in units}

        from apps.student.views import unit_sort_key
        self.assertEqual([unit["num"] for unit in units], sorted(by_num.keys(), key=unit_sort_key))
        self.assertFalse(by_num["1"]["locked"])
        self.assertFalse(by_num["9"]["locked"])
        self.assertFalse(by_num["11"]["locked"])
        self.assertFalse(by_num["12"]["locked"])
        self.assertTrue(by_num["2"]["locked"])
        self.assertIsNone(by_num["2"]["url"])
        self.assertEqual(
            by_num["9"]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "9"}),
        )

    def test_home_discovers_teacher_shared_private_playlists(self):
        self.author.content_permits = [self.student.id]
        self.author.save(update_fields=["content_permits"])
        Playlist.objects.create(
            _id=38104,
            name="Unit 16 - Applied chords",
            authored_by=self.author,
            is_public=False,
            skill_tags=["unit:16", "Secondary_Dominant"],
            tags=["unit:16", "Secondary_Dominant"],
        )

        response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)
        by_num = {unit["num"]: unit for unit in response.context["units"]}
        self.assertFalse(by_num["16"]["locked"])
        self.assertEqual(
            by_num["16"]["url"],
            reverse("student:unit-progress", kwargs={"unit_n": "16"}),
        )


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class StudentHomeQueryBudgetTests(TransactionTestCase):
    reset_sequences = True
    # session + user + accessible playlists + batched mastery + course-unit
    # dates + enrolled-courses PCO join (two constant PCO queries)
    QUERY_BUDGET = 6

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=39001,
            email="home-budget-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=39002,
            email="home-budget-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)
        self._pk = 39100

    def _next_pk(self):
        self._pk += 1
        return self._pk

    def _taxonomy_for_units(self, count):
        units = [
            {
                "n": str(i),
                "title": f"Budget Unit {i}",
                "feat": f"Skill budget {i}",
                "tags": [f"Skill_{i}_A", f"Skill_{i}_B"],
            }
            for i in range(2, 2 + count)
        ]
        branches = [
            {
                "id": "core",
                "label": "Core",
                "tiers": [
                    {
                        "label": "Budget Tier",
                        "badge": "BT",
                        "units": units,
                    }
                ],
            }
        ]
        by_n = {unit["n"]: unit for unit in units}
        by_tag = {
            tag: unit
            for unit in units
            for tag in unit["tags"]
        }
        return branches, units, by_n, by_tag

    def _seed_units(self, count):
        for i in range(2, 2 + count):
            exercise = Exercise.objects.create(
                _id=self._next_pk(),
                description=f"Budget exercise {i}",
                data={"chord": []},
                authored_by=self.author,
                is_public=True,
                skill_tags=[f"Skill_{i}_A", f"unit:{i}"],
            )
            playlist = Playlist.objects.create(
                _id=self._next_pk(),
                name=f"Budget Unit {i}",
                authored_by=self.author,
                is_public=True,
                skill_tags=[f"Skill_{i}_A", f"unit:{i}"],
                tags=[f"Skill_{i}_A", f"unit:{i}"],
            )
            ExercisePlaylistOrdered.objects.create(
                _id=self._next_pk(),
                playlist=playlist,
                exercise=exercise,
                order=1,
            )
            PerformanceData.objects.create(
                user=self.student,
                playlist=playlist,
                data=[{"id": exercise.id, "score_numerator": 1, "score_denominator": 1}],
            )
            StudentSkillMastery.objects.create(
                user=self.student,
                skill_tag=f"Skill_{i}_A",
                level=StudentSkillMastery.LEVEL_MASTERED,
            )

    def test_home_query_count_is_constant_in_unit_count(self):
        branches, units, by_n, by_tag = self._taxonomy_for_units(6)
        self._seed_units(6)

        def get_unit(unit_n):
            return by_n.get(str(unit_n))

        def get_unit_for_tag(tag):
            return by_tag.get(tag)

        with (
            patch("apps.student.views.TaxonomyReader.get_branches", return_value=branches),
            patch("apps.student.views.TaxonomyReader.get_all_units", return_value=units),
            patch("apps.student.views.TaxonomyReader.get_unit", side_effect=get_unit),
            patch("apps.student.views.TaxonomyReader.get_unit_for_tag", side_effect=get_unit_for_tag),
            patch("apps.student.views.TaxonomyReader.get_tier_for_unit", return_value=branches[0]["tiers"][0]),
            patch("apps.student.views.TaxonomyReader.get_skill_label", side_effect=lambda tag: tag.replace("_", " ").title()),
        ):
            with self.assertNumQueries(self.QUERY_BUDGET):
                response = self.client.get(reverse("student:home"))

        self.assertEqual(response.status_code, 200)

    def test_batched_home_summary_matches_unit_progress_summary(self):
        from apps.student.unit_progress import get_unit_progress_data
        from apps.student.views import _batch_home_unit_summaries, _summarize_unit_progress

        branches, units, by_n, by_tag = self._taxonomy_for_units(1)
        self._seed_units(1)

        def get_unit(unit_n):
            return by_n.get(str(unit_n))

        def get_unit_for_tag(tag):
            return by_tag.get(tag)

        with (
            patch("apps.student.views.TaxonomyReader.get_unit", side_effect=get_unit),
            patch("apps.student.views.TaxonomyReader.get_unit_for_tag", side_effect=get_unit_for_tag),
            patch("apps.student.views.TaxonomyReader.get_tier_for_unit", return_value=branches[0]["tiers"][0]),
            patch("apps.student.views.TaxonomyReader.get_skill_label", side_effect=lambda tag: tag.replace("_", " ").title()),
        ):
            expected = _summarize_unit_progress(get_unit_progress_data(self.student, "2"))
            summaries = _batch_home_unit_summaries(self.student, units, {"2"})

        self.assertEqual(summaries["2"]["percent"], expected["percent"])
        self.assertEqual(summaries["2"]["mastered_count"], expected["mastered_count"])


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


class ChallengeGenerationConstraintTests(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=65001,
            email="challenge-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=65002,
            email="challenge-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)

    @patch("apps.student.unit_progress.get_unit_progress_data")
    def test_challenge_generation_fails_loudly_when_incomplete_pool(self, mock_progress):
        from apps.exercises.models import Playlist
        for name in [
            "Unit 1 - Identify the Notes (Treble)",
            "Unit 1 - Play from Name (Treble)",
            "Unit 1 - Play the Notes (Treble)",
            "Unit 1 - Identify the Notes (Bass)",
            "Unit 1 - Play from Name (Bass)",
            "Unit 1 - Play the Notes (Bass)"
        ]:
            Playlist.objects.create(
                name=name,
                authored_by=self.author,
                is_public=True,
                skill_tags=["unit:1"]
            )
        mock_progress.return_value = {
            "bar_segments": [
                {"tag": "identify_treble", "level": "proficient"},
                {"tag": "play_from_name_treble", "level": "proficient"},
                {"tag": "play_the_notes_treble", "level": "proficient"},
            ]
        }
        response = self.client.get(reverse("student:unit1-challenge", kwargs={"group_key": "treble"}))
        self.assertEqual(response.status_code, 404)

    @patch("apps.student.unit_progress.get_unit_progress_data")
    def test_retry_creates_new_challenge_playlist_without_deleting_old_runs(self, mock_progress):
        from apps.exercises.models import Exercise, Playlist, ExercisePlaylistOrdered

        lane_names = [
            "Unit 1 - Identify the Notes (Treble)",
            "Unit 1 - Play from Name (Treble)",
            "Unit 1 - Play the Notes (Treble)",
            "Unit 1 - Identify the Notes (Bass)",
            "Unit 1 - Play from Name (Bass)",
            "Unit 1 - Play the Notes (Bass)",
        ]
        lane_playlists = {}
        for idx, name in enumerate(lane_names, start=1):
            playlist = Playlist.objects.create(
                _id=65100 + idx,
                name=name,
                authored_by=self.author,
                is_public=True,
                skill_tags=["unit:1"],
                tags=["unit:1"],
            )
            lane_playlists[name] = playlist

        treble_names = lane_names[:3]
        exercise_seed = 66000
        epo_seed = 67000
        for lane_name in treble_names:
            for order in range(1, 3):
                exercise = Exercise.objects.create(
                    _id=exercise_seed,
                    description=f"{lane_name} S{order + 3}",
                    data={"chord": []},
                    authored_by=self.author,
                    is_public=True,
                )
                exercise_seed += 1
                ExercisePlaylistOrdered.objects.create(
                    _id=epo_seed,
                    playlist=lane_playlists[lane_name],
                    exercise=exercise,
                    order=order,
                    difficulty_tier=3,
                    is_mastery_challenge_source=True,
                )
                epo_seed += 1

        mock_progress.return_value = {
            "bar_segments": [
                {"tag": "identify_treble", "level": "proficient"},
                {"tag": "play_from_name_treble", "level": "proficient"},
                {"tag": "play_the_notes_treble", "level": "proficient"},
                {"tag": "identify_bass", "level": "attempted"},
                {"tag": "play_from_name_bass", "level": "attempted"},
                {"tag": "play_the_notes_bass", "level": "attempted"},
            ]
        }

        first = self.client.get(reverse("student:unit1-challenge", kwargs={"group_key": "treble"}))
        self.assertEqual(first.status_code, 302)

        second = self.client.get(reverse("student:unit1-challenge", kwargs={"group_key": "treble"}))
        self.assertEqual(second.status_code, 302)

        created = Playlist.objects.filter(
            authored_by=self.student,
            name__startswith=f"_challenge_{self.student.id}_treble",
        )
        self.assertEqual(created.count(), 2)
