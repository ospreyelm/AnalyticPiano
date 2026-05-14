import pytest
from apps.exercises.key_signature_problems import (
    KEY_TABLE,
    build_key_sig_problem_set,
    LEVEL_ACCIDENTAL_LIMIT,
)

def test_key_table_has_15_keys():
    assert len(KEY_TABLE) == 15

def test_key_table_c_major():
    c = next(k for k in KEY_TABLE if k["key_id"] == "jC_")
    assert c["accidentals"] == 0
    assert c["display_name"] == "C major"
    assert "C" in c["accepted_answers"]

def test_key_table_f_sharp_major():
    fs = next(k for k in KEY_TABLE if k["key_id"] == "jF#")
    assert fs["accidentals"] == 6
    assert "F#" in fs["accepted_answers"]

def test_level_limits():
    assert LEVEL_ACCIDENTAL_LIMIT == {1: 3, 2: 5, 3: 7}

def test_build_problem_set_level1():
    problems = build_key_sig_problem_set(level=1)
    assert all(p["accidentals"] <= 3 for p in problems)
    assert len(problems) == 7  # C, G, D, A, F, Bb, Eb

def test_build_problem_set_level3():
    problems = build_key_sig_problem_set(level=3)
    assert len(problems) == 15

def test_problem_structure():
    problems = build_key_sig_problem_set(level=1)
    p = problems[0]
    assert "prompt" in p
    assert p["prompt"]["kind"] == "key_signature"
    assert "sharps" in p["prompt"] or "flats" in p["prompt"]
    assert "answer" in p
    assert "accepted_answers" in p
    assert "choices" in p
    assert len(p["choices"]) == 4
    # Load-bearing invariants for exercise to function:
    assert p["answer"] in p["choices"]
    assert len(p["accepted_answers"]) > 0  # Must have at least one accepted answer

def test_enharmonic_exclusion_at_level2():
    level2 = build_key_sig_problem_set(level=2)
    level3 = build_key_sig_problem_set(level=3)
    level2_ids = {p["key_id"] for p in level2}
    level3_ids = {p["key_id"] for p in level3}
    # These keys have 6-7 accidentals and are excluded at level 2 (≤5)
    assert "jC#" not in level2_ids   # 7 accidentals, excluded by limit
    assert "jGb" not in level2_ids   # 6 accidentals, excluded by limit
    assert "jCb" not in level2_ids   # 7 accidentals, excluded by limit
    # At level 3, all are included (limit raised to 7)
    assert "jC#" in level3_ids
    assert "jGb" in level3_ids
    assert "jCb" in level3_ids


from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.umto_factory import save_umto_key_sig_exercise


class KeySigExerciseSaveTests(TestCase):
    def test_save_umto_key_sig_exercise_creates_exercise(self):
        from apps.exercises.key_signature_problems import build_key_sig_problem_set

        author = get_user_model().objects.create_user(
            email="kstest@example.com", password="x"
        )
        problems = build_key_sig_problem_set(level=1)
        ex = save_umto_key_sig_exercise(
            description="Unit 3 Key Sig Level 1",
            author=author,
            problems=problems,
            level=1,
            is_public=False,
        )
        self.assertIsNotNone(ex.pk)
        self.assertEqual(ex.data["type"], "umto_key_signature")
        self.assertEqual(ex.data["analysisType"], "unit3_key_signature")
        self.assertEqual(len(ex.data["problems"]), 7)
        self.assertIn("unit:3", ex.skill_tags)
        self.assertIn("unit:3_key_signature", ex.skill_tags)


class GenerateUnit3KeySigCommandTests(TestCase):
    def test_command_creates_exercises_and_playlists(self):
        from django.core.management import call_command
        from apps.exercises.models import Exercise, Playlist

        User = get_user_model()
        author = User.objects.create_user(
            email="cmd3@example.com", password="x"
        )
        call_command("generate_unit3_key_sig_exercises", author="cmd3@example.com")

        exercises = Exercise.objects.filter(
            description__startswith="Unit 3 Key Sig",
            authored_by=author,
        )
        self.assertEqual(exercises.count(), 3)  # levels 1, 2, 3

        playlists = Playlist.objects.filter(
            name__startswith="Unit 3 — Key Signatures",
            authored_by=author,
        )
        self.assertEqual(playlists.count(), 3)


class GenerateUnit3ScaleCommandTests(TestCase):
    def test_command_creates_scale_exercises_and_playlists(self):
        from django.core.management import call_command
        from apps.exercises.models import Exercise, Playlist

        User = get_user_model()
        author = User.objects.create_user(
            email="scale3@example.com", password="x"
        )
        import os
        # The MXL lives in docs/ at the repo root. Resolve relative to this test file's
        # location — from apps/exercises/tests/ we go up 3 levels to the repo root then into docs/.
        _here = os.path.dirname(os.path.abspath(__file__))
        mxl_path = os.path.normpath(
            os.path.join(_here, "../../../docs/scales-key-signatures/piano-major-scales-fingerings.mxl")
        )
        self.assertTrue(os.path.exists(mxl_path), f"MXL not found at {mxl_path}")
        call_command(
            "generate_unit3_scale_exercises",
            author="scale3@example.com",
            mxl=mxl_path,
        )

        exercises = Exercise.objects.filter(
            skill_tags__contains=["unit:3_major_scale"],
            authored_by=author,
        )
        self.assertEqual(exercises.count(), 15)

        playlists = Playlist.objects.filter(
            name__startswith="Unit 3 — Major Scales",
            authored_by=author,
        )
        self.assertEqual(playlists.count(), 3)

        # Level 1 has ≤3 accidentals → 7 keys (C, F, G, Bb, D, Eb, A)
        from apps.exercises.models import ExercisePlaylistOrdered
        level1 = Playlist.objects.get(
            name="Unit 3 — Major Scales, Level 1",
            authored_by=author,
        )
        self.assertEqual(ExercisePlaylistOrdered.objects.filter(playlist=level1).count(), 7)
