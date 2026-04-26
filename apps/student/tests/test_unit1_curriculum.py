from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from apps.exercises.models import Playlist
from apps.student import unit1_curriculum

User = get_user_model()


class Unit1CurriculumResolverTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="canonical-author@test.com",
            password="x",
            is_staff=True,
        )
        self.other_author = User.objects.create_user(
            email="other-author@test.com",
            password="x",
            is_staff=True,
        )

    def _playlist(self, *, name: str, author, skill_tags=None, tags=None, is_public=True):
        return Playlist.objects.create(
            name=name,
            authored_by=author,
            is_public=is_public,
            skill_tags=skill_tags or [],
            tags=tags or [],
        )

    def test_resolves_legacy_alias_when_curated_name_missing(self):
        canonical = self._playlist(
            name="Unit 1 - Note Names (Treble Name)",
            author=self.author,
            skill_tags=["unit:1"],
        )

        lanes = {
            "play_from_name_treble": {
                "activity_key": "play_from_name",
                "activity_title": "Play from Name",
                "lane_key": "play_from_name_treble",
                "label": "Treble",
                "playlist_name": "Unit 1 - Play from Name (Treble)",
                "playlist_name_candidates": (
                    "Unit 1 - Play from Name (Treble)",
                    "Unit 1 - Note Names (Treble Name)",
                ),
            }
        }

        with patch.object(unit1_curriculum, "UNIT1_CANONICAL_LANES", lanes):
            resolved = unit1_curriculum.get_unit1_playlist_ids()

        self.assertEqual(resolved["play_from_name_treble"], canonical.id)

    @override_settings(UNIT1_CURRICULUM_AUTHOR_EMAIL="canonical-author@test.com")
    def test_prefers_configured_author_match(self):
        self._playlist(
            name="Unit 1 - Identify the Notes (Treble)",
            author=self.other_author,
            skill_tags=["unit:1"],
        )
        canonical = self._playlist(
            name="Unit 1 - Identify the Notes (Treble)",
            author=self.author,
            skill_tags=["unit:1"],
        )

        lanes = {
            "identify_treble": {
                "activity_key": "identify",
                "activity_title": "Identify",
                "lane_key": "identify_treble",
                "label": "Treble",
                "playlist_name": "Unit 1 - Identify the Notes (Treble)",
                "playlist_name_candidates": ("Unit 1 - Identify the Notes (Treble)",),
            }
        }

        with patch.object(unit1_curriculum, "UNIT1_CANONICAL_LANES", lanes):
            resolved = unit1_curriculum.get_unit1_playlist_ids()

        self.assertEqual(resolved["identify_treble"], canonical.id)

    @override_settings(UNIT1_CURRICULUM_AUTHOR_EMAIL="canonical-author@test.com")
    def test_author_scope_can_fall_through_to_next_alias(self):
        self._playlist(
            name="Unit 1 - Play from Name (Treble)",
            author=self.other_author,
            skill_tags=["unit:1"],
        )
        canonical = self._playlist(
            name="Unit 1 - Note Names (Treble Name)",
            author=self.author,
            skill_tags=["unit:1"],
        )

        lanes = {
            "play_from_name_treble": {
                "activity_key": "play_from_name",
                "activity_title": "Play from Name",
                "lane_key": "play_from_name_treble",
                "label": "Treble",
                "playlist_name": "Unit 1 - Play from Name (Treble)",
                "playlist_name_candidates": (
                    "Unit 1 - Play from Name (Treble)",
                    "Unit 1 - Note Names (Treble Name)",
                ),
            }
        }

        with patch.object(unit1_curriculum, "UNIT1_CANONICAL_LANES", lanes):
            resolved = unit1_curriculum.get_unit1_playlist_ids()

        self.assertEqual(resolved["play_from_name_treble"], canonical.id)

    def test_raises_on_ambiguous_same_name_without_author_scope(self):
        self._playlist(
            name="Unit 1 - Play the Notes (Bass)",
            author=self.author,
            skill_tags=["unit:1"],
        )
        self._playlist(
            name="Unit 1 - Play the Notes (Bass)",
            author=self.other_author,
            skill_tags=["unit:1"],
        )

        lanes = {
            "play_the_notes_bass": {
                "activity_key": "play_the_notes",
                "activity_title": "Play the Notes",
                "lane_key": "play_the_notes_bass",
                "label": "Bass",
                "playlist_name": "Unit 1 - Play the Notes (Bass)",
                "playlist_name_candidates": ("Unit 1 - Play the Notes (Bass)",),
            }
        }

        with patch.object(unit1_curriculum, "UNIT1_CANONICAL_LANES", lanes):
            with self.assertRaises(ImproperlyConfigured):
                unit1_curriculum.get_unit1_playlist_ids()
