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
