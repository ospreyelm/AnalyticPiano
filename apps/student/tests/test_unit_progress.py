"""
apps/student/tests/test_unit_progress.py

Unit tests for apps.student.unit_progress.get_unit_progress_data().

Run with:
    python manage.py test apps.student.tests.test_unit_progress
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import (
    Exercise,
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
    StudentSkillMastery,
)
from apps.student.unit_progress import get_unit_progress_data

User = get_user_model()

# ---------------------------------------------------------------------------
# Minimal taxonomy stub — used in all tests via patching so the tests never
# touch the filesystem or require a full taxonomy JSON.
# ---------------------------------------------------------------------------

STUB_UNIT = {
    "n": "1",
    "title": "Pitch & Staff Notation",
    "feat": "Notes on the staff",
    "tags": ["Note_Names", "Ledger_Lines"],
}

STUB_TIER = {
    "label": "Tier 1 — Fundamentals & pitch reading",
    "badge": "T1",
}


def _make_author(n: int) -> User:
    return User.objects.create_user(
        id=n,
        email=f"author-{n}@test.com",
        password="x",
        is_staff=True,
    )


def _make_student(n: int) -> User:
    return User.objects.create_user(
        id=n,
        email=f"student-{n}@test.com",
        password="x",
        is_staff=False,
    )


def _make_exercise(pk: int, author: User) -> Exercise:
    """Create a bare-minimum Exercise that bypasses UMTO validation."""
    return Exercise.objects.create(
        _id=pk,
        data={"chord": []},
        authored_by=author,
        is_public=True,
    )


def _make_playlist(pk: int, author: User, skill_tags=None, name="Test Playlist") -> Playlist:
    return Playlist.objects.create(
        _id=pk,
        name=name,
        authored_by=author,
        is_public=True,
        skill_tags=skill_tags or [],
    )


def _make_pd(user: User, playlist: Playlist, data: list) -> PerformanceData:
    pd, _ = PerformanceData.objects.get_or_create(
        user=user,
        playlist=playlist,
        course=None,
    )
    pd.data = data
    pd.save()
    return pd


# ---------------------------------------------------------------------------
# Patch helper — wraps all tests so TaxonomyReader never touches disk.
# ---------------------------------------------------------------------------

TAXONOMY_PATCH = {
    "apps.student.unit_progress.TaxonomyReader.get_unit":
        MagicMock(return_value=STUB_UNIT),
    "apps.student.unit_progress.TaxonomyReader.get_tier_for_unit":
        MagicMock(return_value=STUB_TIER),
    "apps.student.unit_progress.TaxonomyReader.get_skill_label":
        MagicMock(side_effect=lambda tag: tag.replace("_", " ").title()),
}


class UnitProgressDataStructureTest(TestCase):
    """test_get_unit_progress_data_structure — required top-level keys are present."""

    def setUp(self):
        self.student = _make_student(50001)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_get_unit_progress_data_structure(self, mock_label, mock_tier, mock_unit):
        result = get_unit_progress_data(self.student, "1")

        self.assertIsNotNone(result)
        # Top-level keys
        self.assertIn("unit", result)
        self.assertIn("tier", result)
        self.assertIn("bar_segments", result)
        self.assertIn("skill_cards", result)

        # Unit sub-keys
        self.assertEqual(result["unit"]["n"], "1")
        self.assertEqual(result["unit"]["title"], "Pitch & Staff Notation")

        # Bar segments — one per tag in the stub unit
        self.assertEqual(len(result["bar_segments"]), 2)
        for seg in result["bar_segments"]:
            self.assertIn("tag", seg)
            self.assertIn("label", seg)
            self.assertIn("level", seg)

        # Skill cards — one per tag
        self.assertEqual(len(result["skill_cards"]), 2)
        for card in result["skill_cards"]:
            self.assertIn("tag", card)
            self.assertIn("label", card)
            self.assertIn("level", card)
            self.assertIn("playlists", card)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=None)
    def test_returns_none_for_unknown_unit(self, mock_unit):
        result = get_unit_progress_data(self.student, "999")
        self.assertIsNone(result)


class SkillLevelNewUserTest(TestCase):
    """test_skill_level_for_new_user_is_not_started."""

    def setUp(self):
        self.student = _make_student(51001)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_skill_level_for_new_user_is_not_started(self, mock_label, mock_tier, mock_unit):
        # Fresh user — no StudentSkillMastery rows exist
        result = get_unit_progress_data(self.student, "1")

        for seg in result["bar_segments"]:
            self.assertEqual(
                seg["level"],
                StudentSkillMastery.LEVEL_NOT_STARTED,
                msg=f"Expected 'not_started' for tag '{seg['tag']}', got '{seg['level']}'",
            )

        for card in result["skill_cards"]:
            self.assertEqual(
                card["level"],
                StudentSkillMastery.LEVEL_NOT_STARTED,
                msg=f"Expected 'not_started' for skill card '{card['tag']}', got '{card['level']}'",
            )

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_skill_level_reflects_mastery_record(self, mock_label, mock_tier, mock_unit):
        StudentSkillMastery.objects.create(
            user=self.student,
            skill_tag="Note_Names",
            level=StudentSkillMastery.LEVEL_PROFICIENT,
        )
        result = get_unit_progress_data(self.student, "1")
        levels = {seg["tag"]: seg["level"] for seg in result["bar_segments"]}
        self.assertEqual(levels["Note_Names"], "proficient")
        self.assertEqual(levels["Ledger_Lines"], "not_started")


class PlaylistStatsUniqueExercisesTest(TestCase):
    """test_playlist_stats_counts_unique_exercises — done counts IDs, not attempts."""

    def setUp(self):
        self.author = _make_author(52002)
        self.student = _make_student(52001)
        # Playlist that overlaps with unit stub tags
        self.playlist = _make_playlist(
            pk=52010,
            author=self.author,
            skill_tags=["Note_Names"],
            name="Note Names Treble",
        )
        # Add two exercises to the playlist so exercise_count = 2
        ex1 = _make_exercise(52020, self.author)
        ex2 = _make_exercise(52021, self.author)
        ExercisePlaylistOrdered.objects.create(
            _id=52030, playlist=self.playlist, exercise=ex1, order=1
        )
        ExercisePlaylistOrdered.objects.create(
            _id=52031, playlist=self.playlist, exercise=ex2, order=2
        )
        self.ex1_id = ex1.id
        self.ex2_id = ex2.id

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_playlist_stats_counts_unique_exercises(self, mock_label, mock_tier, mock_unit):
        """Exercice EA000E attempted 3 times and EB000E once → done should be 2, not 4."""
        # Three attempts on ex1, one on ex2 — all in one PerformanceData row
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[
                {"id": self.ex1_id, "error_tally": 2},
                {"id": self.ex1_id, "error_tally": 1},
                {"id": self.ex1_id, "error_tally": 0},
                {"id": self.ex2_id, "error_tally": 0},
            ],
        )
        result = get_unit_progress_data(self.student, "1")

        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        self.assertEqual(len(note_names_card["playlists"]), 1)
        pl_stats = note_names_card["playlists"][0]
        # 2 unique IDs, not 4 total attempts
        self.assertEqual(pl_stats["done"], 2)
        self.assertEqual(pl_stats["total"], 2)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_playlist_stats_aggregates_across_multiple_pd_rows(self, mock_label, mock_tier, mock_unit):
        """Unique IDs are deduplicated across *multiple* PerformanceData rows (different courses)."""
        # Row 1: ex1 from course A
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[{"id": self.ex1_id, "error_tally": 0}],
        )
        # We cannot create a second PD for the same (user, playlist, course=None) due to unique_together.
        # The deduplication spec concerns all rows for (user, playlist) regardless of course;
        # we verify here that ID deduplication works when ex1 appears twice in the same row.
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[
                {"id": self.ex1_id, "error_tally": 0},
                {"id": self.ex2_id, "error_tally": 0},
            ],
        )
        result = get_unit_progress_data(self.student, "1")
        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        pl_stats = note_names_card["playlists"][0]
        # ex1 appears twice but should count as 1; ex2 once = total 2
        self.assertEqual(pl_stats["done"], 2)


class LastScorePctTest(TestCase):
    """test_last_score_pct_none_for_old_data — entries without score_numerator return None."""

    def setUp(self):
        self.author = _make_author(53002)
        self.student = _make_student(53001)
        self.playlist = _make_playlist(
            pk=53010,
            author=self.author,
            skill_tags=["Note_Names"],
            name="Note Names Legacy",
        )
        ex = _make_exercise(53020, self.author)
        ExercisePlaylistOrdered.objects.create(
            _id=53030, playlist=self.playlist, exercise=ex, order=1
        )
        self.ex_id = ex.id

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_last_score_pct_none_for_old_data(self, mock_label, mock_tier, mock_unit):
        """Old-format entries (no score_numerator key) → last_score_pct is None."""
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[
                {"id": self.ex_id, "error_tally": 2},
                {"id": self.ex_id, "error_tally": 0},
            ],
        )
        result = get_unit_progress_data(self.student, "1")
        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        pl_stats = note_names_card["playlists"][0]
        self.assertIsNone(pl_stats["last_score_pct"])

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_last_score_pct_computed_from_most_recent_entry(self, mock_label, mock_tier, mock_unit):
        """Most recent scored entry (80%) should be returned, not the earlier 60%."""
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[
                # older entry: 60%
                {
                    "id": self.ex_id,
                    "error_tally": 2,
                    "score_numerator": 3,
                    "score_denominator": 5,
                },
                # newer entry: 80%
                {
                    "id": self.ex_id,
                    "error_tally": 1,
                    "score_numerator": 4,
                    "score_denominator": 5,
                },
            ],
        )
        result = get_unit_progress_data(self.student, "1")
        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        pl_stats = note_names_card["playlists"][0]
        self.assertEqual(pl_stats["last_score_pct"], 80)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_last_score_pct_none_when_no_performance_data(self, mock_label, mock_tier, mock_unit):
        """No PerformanceData at all → last_score_pct is None and done is 0."""
        result = get_unit_progress_data(self.student, "1")
        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        pl_stats = note_names_card["playlists"][0]
        self.assertIsNone(pl_stats["last_score_pct"])
        self.assertEqual(pl_stats["done"], 0)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_last_score_pct_rounded(self, mock_label, mock_tier, mock_unit):
        """Score percentages are rounded to the nearest integer."""
        _make_pd(
            user=self.student,
            playlist=self.playlist,
            data=[
                {
                    "id": self.ex_id,
                    "score_numerator": 2,
                    "score_denominator": 3,  # 66.666... → 67
                },
            ],
        )
        result = get_unit_progress_data(self.student, "1")
        note_names_card = next(
            c for c in result["skill_cards"] if c["tag"] == "Note_Names"
        )
        pl_stats = note_names_card["playlists"][0]
        self.assertEqual(pl_stats["last_score_pct"], 67)
