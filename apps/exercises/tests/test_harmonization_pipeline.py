"""Integration tests: harmonization save → serve pipeline.

Covers the chain:
  teacher saves via play view → (optional: transposition) → student loads
  → generate_exercise_context → JS payload has mode + harmonizationTargets

These tests exist to catch cross-component data loss that unit tests miss.
"""
import json

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.exercises.models import Exercise, Playlist
from apps.exercises.services.exercise_context import generate_exercise_context
from apps.exercises.services.transposition_service import generate_transposed_copies
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_chordal_umto_exercise


# Minimal chordal exercise with analysis slices so targets can be computed.
_CHORDS = [
    {"offset": 0.0, "duration": 2.0, "visible": [72, 76, 79, 48], "hidden": [], "spelling": ["C5", "E5", "G5", "C3"]},
    {"offset": 2.0, "duration": 2.0, "visible": [71, 74, 79, 55], "hidden": [], "spelling": ["B4", "D5", "G5", "G3"]},
    {"offset": 4.0, "duration": 4.0, "visible": [72, 76, 79, 48], "hidden": [], "spelling": ["C5", "E5", "G5", "C3"]},
]

_ANALYSIS = [
    {"offset": 0.0, "is_target": True, "unit_tags": [], "visual": None, "content": {
        "local_key": "jC_", "roman_numeral": "I", "raw_roman_numeral": "I",
        "figured_bass": "5/3", "raw_figured_bass": "8/5/3",
        "pop_symbol": None, "functional_label": None, "scale_degrees": None, "spacing": None,
    }},
    {"offset": 2.0, "is_target": True, "unit_tags": [], "visual": None, "content": {
        "local_key": "jC_", "roman_numeral": "V", "raw_roman_numeral": "V",
        "figured_bass": "5/3", "raw_figured_bass": "8/5/3",
        "pop_symbol": None, "functional_label": None, "scale_degrees": None, "spacing": None,
    }},
    {"offset": 4.0, "is_target": True, "unit_tags": [], "visual": None, "content": {
        "local_key": "jC_", "roman_numeral": "I", "raw_roman_numeral": "I",
        "figured_bass": "5/3", "raw_figured_bass": "8/5/3",
        "pop_symbol": None, "functional_label": None, "scale_degrees": None, "spacing": None,
    }},
]


def _make_playlist(author, exercise):
    pl = Playlist.objects.create(
        id="TESTPL",
        name="Test Playlist",
        authored_by=author,
        skill_tags=["unit:7"],
    )
    pl.exercise_list = [exercise.id]
    pl.save()
    return pl


class HarmonizationSaveServeTest(TestCase):
    """save_chordal_umto_exercise → generate_exercise_context roundtrip."""

    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    def _make_harmonization_exercise(self):
        return save_chordal_umto_exercise(
            description="Integration test harm",
            author=self.author,
            chords=_CHORDS,
            key="jC_",
            meter="2/2",
            clef="keyboard",
            staff_distribution="keyboard",
            skill_tags=["unit:7"],
            barline_offsets=[4.0],
            analysis=_ANALYSIS,
            mode=InteractionMode.HARMONIZATION,
        )

    def test_save_stores_harmonization_mode(self):
        ex = self._make_harmonization_exercise()
        self.assertEqual(ex.data["mode"], "harmonization")
        self.assertEqual(ex.data["score"]["umto"]["metadata"]["mode"], "harmonization")

    def test_save_stores_harmonization_targets(self):
        ex = self._make_harmonization_exercise()
        targets = ex.data.get("harmonizationTargets")
        self.assertIsNotNone(targets, "harmonizationTargets must be present in exercise.data")
        self.assertGreater(len(targets), 0, "harmonizationTargets must be non-empty")

    def test_generate_exercise_context_includes_mode(self):
        ex = self._make_harmonization_exercise()
        pl = _make_playlist(self.author, ex)
        ctx = generate_exercise_context(exercise_num=1, exercise=ex, user=self.author, playlist=pl)
        self.assertEqual(ctx["mode"], "harmonization")

    def test_generate_exercise_context_includes_harmonization_targets(self):
        ex = self._make_harmonization_exercise()
        pl = _make_playlist(self.author, ex)
        ctx = generate_exercise_context(exercise_num=1, exercise=ex, user=self.author, playlist=pl)
        targets = ctx.get("harmonizationTargets")
        self.assertIsNotNone(targets, "harmonizationTargets must reach the frontend context")
        self.assertGreater(len(targets), 0)


class HarmonizationTranspositionPipelineTest(TestCase):
    """Transposed harmonization exercise must preserve mode + targets."""

    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.source = save_chordal_umto_exercise(
            description="Source harm C",
            author=self.author,
            chords=_CHORDS,
            key="jC_",
            meter="2/2",
            clef="keyboard",
            staff_distribution="keyboard",
            skill_tags=["unit:7"],
            barline_offsets=[4.0],
            analysis=_ANALYSIS,
            mode=InteractionMode.HARMONIZATION,
        )
        self.playlist = _make_playlist(self.author, self.source)

    def _get_transposed(self):
        generate_transposed_copies(
            source_exercise=self.source,
            key_set=["G"],
            playlist=self.playlist,
            author=self.author,
        )
        return Exercise.objects.filter(
            skill_tags__contains=["transposed_from:" + self.source.id]
        ).first()

    def test_transposed_exercise_has_harmonization_mode(self):
        transposed = self._get_transposed()
        self.assertIsNotNone(transposed)
        self.assertEqual(transposed.data["mode"], "harmonization",
                         "Transposed copy must preserve harmonization mode")

    def test_transposed_exercise_has_harmonization_targets(self):
        transposed = self._get_transposed()
        targets = transposed.data.get("harmonizationTargets")
        self.assertIsNotNone(targets, "harmonizationTargets must be present in transposed copy")
        self.assertGreater(len(targets), 0)

    def test_transposed_context_includes_mode_and_targets(self):
        transposed = self._get_transposed()
        pl = Playlist.objects.create(
            id="TESTPL2", name="Transposed Playlist",
            authored_by=self.author, skill_tags=["unit:7"],
        )
        pl.exercise_list = [transposed.id]
        pl.save()
        ctx = generate_exercise_context(exercise_num=1, exercise=transposed, user=self.author, playlist=pl)
        self.assertEqual(ctx["mode"], "harmonization")
        self.assertIsNotNone(ctx.get("harmonizationTargets"))
        self.assertGreater(len(ctx["harmonizationTargets"]), 0)


class HarmonizationPlayViewPipelineTest(TestCase):
    """Full path: POST to play view → generate_exercise_context."""

    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.client = Client()
        self.client.login(email="teacher@example.com", password="pw")

    def _post_harmonization(self):
        payload = {
            "chord": [
                {"offset": 0.0, "duration": 2.0, "visible": [72, 76, 79, 48], "hidden": [],
                 "spelling": ["C5", "E5", "G5", "C3"]},
                {"offset": 2.0, "duration": 2.0, "visible": [71, 74, 79, 55], "hidden": [],
                 "spelling": ["B4", "D5", "G5", "G3"]},
                {"offset": 4.0, "duration": 4.0, "visible": [72, 76, 79, 48], "hidden": [],
                 "spelling": ["C5", "E5", "G5", "C3"]},
            ],
            "key": "jC_",
            "meter": "2/2",
            "clef": "keyboard",
            "staffDistribution": "keyboard",
            "skillTags": ["unit:7"],
            "mode": "harmonization",
            "barline_offsets": [4.0],
            "analysisSlices": _ANALYSIS,
        }
        return self.client.post(reverse("lab:add-exercise"), {"data": json.dumps(payload)})

    def test_play_view_harmonization_post_produces_targets(self):
        resp = self._post_harmonization()
        self.assertEqual(resp.status_code, 201)
        ex = Exercise.objects.get(id=resp.json()["id"])
        targets = ex.data.get("harmonizationTargets")
        self.assertIsNotNone(targets)
        self.assertGreater(len(targets), 0)

    def test_play_view_harmonization_context_roundtrip(self):
        resp = self._post_harmonization()
        ex = Exercise.objects.get(id=resp.json()["id"])
        pl_id = resp.json()["playlistId"]
        pl = Playlist.objects.get(id=pl_id)
        ctx = generate_exercise_context(exercise_num=1, exercise=ex, user=self.author, playlist=pl)
        self.assertEqual(ctx["mode"], "harmonization")
        self.assertIsNotNone(ctx.get("harmonizationTargets"))
        self.assertGreater(len(ctx["harmonizationTargets"]), 0)
