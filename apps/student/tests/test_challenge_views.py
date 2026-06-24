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
