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


class DesignTokensTests(TestCase):
    def test_tokens_css_defines_required_custom_properties(self):
        tokens_path = (
            Path(__file__).resolve().parents[1] / "static" / "student" / "tokens.css"
        )
        content = tokens_path.read_text()
        for prop in (
            "--teal-header:",
            "--font-mono:",
            "--text-xs:",
            "--text-sm:",
            "--text-base:",
            "--text-lg:",
            "--text-xl:",
            "--surface: #f4f6f7;",
        ):
            self.assertIn(prop, content, f"tokens.css missing {prop}")
class PlayerCanvasCssExtractionTests(TestCase):
    def test_player_canvas_css_file_exists_and_has_content(self):
        # Check student-specific player-canvas.css
        player_css_path = (
            Path(__file__).resolve().parents[1]
            / "static" / "student" / "player-canvas.css"
        )
        self.assertTrue(player_css_path.exists(), "player-canvas.css was not created")
        player_content = player_css_path.read_text()
        for selector in (".s-toolbar-btn", ".s-player-header", ".harmony-ui"):
            self.assertIn(selector, player_content, f"player-canvas.css missing {selector}")

        # Check shared exercise-canvas.css
        exercise_css_path = (
            Path(__file__).resolve().parents[1]
            / "static" / "student" / "exercise-canvas.css"
        )
        self.assertTrue(exercise_css_path.exists(), "exercise-canvas.css does not exist")
        exercise_content = exercise_css_path.read_text()
        for selector in ("#piano", "#staffwrapper"):
            self.assertIn(selector, exercise_content, f"exercise-canvas.css missing {selector}")

    def test_player_template_links_correct_css_and_has_no_inline_style(self):
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates" / "student" / "player.html"
        )
        content = template_path.read_text()
        self.assertIn("student/player-canvas.css", content)
        self.assertIn("student/exercise-canvas.css", content)
        self.assertNotIn("css/harmony.css", content)
        self.assertNotIn("<style>", content)
        self.assertIn('student/player_base.html', content, "player.html must extend player_base.html (no nav header)")

    def test_player_base_template_has_ionicons_and_no_nav(self):
        base_path = (
            Path(__file__).resolve().parents[1]
            / "templates" / "student" / "player_base.html"
        )
        content = base_path.read_text()
        self.assertIn("ionicons-needed.css", content, "player_base.html must load ionicons")
        self.assertNotIn("s-header", content, "player_base.html must not render nav header")
        self.assertNotIn('class="s-main"', content, "player_base.html must not wrap content in s-main")
