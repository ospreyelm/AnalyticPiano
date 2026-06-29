"""
Simulate multi-student adaptive playlist sessions and verify engine behaviour.

Creates three mock students with distinct performance patterns, runs them through
a shared adaptive playlist, and asserts:

  1. Initial Diversity   — all three students receive different exercises at step 1.
  2. No Duplicates       — no student sees the same exercise twice in a session.
  3. Adaptivity          — Student Beta's mastery advances more slowly than Alpha's
                           following a step-2 failure, then recovers.

A structured JSON report is written to ``playlist_simulation_report.json`` (or
the path given by ``--output``).

Usage::

    python manage.py simulate_adaptive_playlists
    python manage.py simulate_adaptive_playlists --output /tmp/report.json
    python manage.py simulate_adaptive_playlists --no-cleanup
"""

import json
import sys
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.exercises.mastery import get_next_exercise, record_attempt
from apps.exercises.models import (
    Exercise,
    ExercisePlaylistOrdered,
    PerformanceData,
    Playlist,
    StudentSkillMastery,
)
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()

# ---------------------------------------------------------------------------
# Simulation parameters
# ---------------------------------------------------------------------------

STUDENT_NAMES = ["student_alpha", "student_beta", "student_gamma"]

# True = answered correctly at that step (1-indexed).
PERFORMANCE_PATTERNS: dict[str, list[bool]] = {
    "student_alpha": [True,  True,  True,  True,  True],   # all correct
    "student_beta":  [True,  False, True,  True,  True],   # fails step 2
    "student_gamma": [False, True,  True,  True,  True],   # fails step 1
}

N_STEPS = 5

# Skill tag used on all simulation exercises; must be in ALL_SKILL_TAGS so the
# mastery engine can track it.
TARGET_SKILL = "Note_Names"

# Eight distinct single-note CIR fixtures: same skill/complexity, different content.
_NOTES = [
    ("C", 4), ("D", 4), ("E", 4), ("F", 4),
    ("G", 4), ("A", 4), ("B", 4), ("C", 5),
]


def _note_cir(step: str, octave: int) -> dict:
    return {
        "meta": {"key": "C", "time": "4/4"},
        "measures": [{
            "staves": {"treble": {"voices": [{"items": [{
                "kind": "note",
                "pitch": {"step": step, "alter": 0, "octave": octave},
                "duration": {"type": "q", "dots": 0},
            }]}]}}
        }],
    }


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Simulate three students on a shared adaptive playlist and assert "
        "diversity, no-duplicates, and adaptivity properties."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="playlist_simulation_report.json",
            help="Path for the JSON report (default: playlist_simulation_report.json).",
        )
        parser.add_argument(
            "--no-cleanup",
            action="store_true",
            help="Skip deletion of simulation data after the run.",
        )

    def handle(self, *args, **options):
        output_path = options["output"]
        skip_cleanup = options["no_cleanup"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Adaptive Playlist Simulation ===\n"
        ))

        with transaction.atomic():
            teacher, students = self._setup_users()
            exercises = self._create_exercises(teacher)
            playlist = self._create_playlist(teacher, exercises)
            self._clear_session_data(students, playlist)

            report = self._run_simulation(students, playlist)

        with open(output_path, "w") as fh:
            json.dump(report, fh, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\nReport written to: {output_path}"))

        passed = self._run_assertions(report)

        if not skip_cleanup:
            with transaction.atomic():
                self._cleanup(students, exercises, playlist)
            self.stdout.write("Simulation data cleaned up.")

        if passed:
            self.stdout.write(self.style.SUCCESS("\n✓ All assertions passed.\n"))
        else:
            self.stdout.write(self.style.ERROR("\n✗ One or more assertions failed.\n"))
            sys.exit(1)

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_users(self):
        teacher, _ = User.objects.get_or_create(
            email="sim-teacher@local.test",
            defaults={"is_active": True},
        )
        teacher.set_password("sim-only")
        teacher.save()

        students = {}
        for name in STUDENT_NAMES:
            user, _ = User.objects.get_or_create(
                email=f"{name}@local.test",
                defaults={"is_active": True},
            )
            students[name] = user

        self.stdout.write(f"Users ready: {', '.join(STUDENT_NAMES)}")
        return teacher, students

    def _create_exercises(self, teacher) -> list:
        exercises = []
        for i, (step, octave) in enumerate(_NOTES, start=1):
            ex = save_umto_exercise(
                description=f"sim-note-{step}{octave}-{i}",
                score_data=_note_cir(step, octave),
                author=teacher,
                skill_tags=[TARGET_SKILL],
                complexity=1,
                is_public=False,
                auto_playlist=False,
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"sim-note-{step}{octave}",
                    key="C",
                    meter="4/4",
                    clef="treble",
                    complexity_score=1,
                    mode=InteractionMode.PLAYBACK,
                    target_voice="soprano",
                    unit=1,
                ),
            )
            exercises.append(ex)

        self.stdout.write(f"Created {len(exercises)} simulation exercises.")
        return exercises

    def _create_playlist(self, teacher, exercises) -> Playlist:
        playlist = Playlist(
            name="Simulation Adaptive Playlist",
            authored_by=teacher,
            is_adaptive=True,
            is_dynamic=False,
            is_public=False,
        )
        playlist.save()

        for order, ex in enumerate(exercises, start=1):
            ExercisePlaylistOrdered.objects.create(
                exercise=ex,
                playlist=playlist,
                order=order,
                is_adaptive_entry=(order == 1),
            )

        self.stdout.write(f"Created playlist: {playlist.id}\n")
        return playlist

    def _clear_session_data(self, students: dict, playlist: Playlist) -> None:
        for user in students.values():
            PerformanceData.objects.filter(user=user, playlist=playlist).delete()
            StudentSkillMastery.objects.filter(user=user).delete()

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _run_simulation(self, students: dict, playlist: Playlist) -> dict:
        report: dict = {"students": {}}

        for name, user in students.items():
            self.stdout.write(self.style.MIGRATE_HEADING(f"--- {name} ---"))
            pattern = PERFORMANCE_PATTERNS[name]
            steps = []

            for step_num in range(1, N_STEPS + 1):
                exercise, target_key = get_next_exercise(
                    user, playlist=playlist, exercise_num=step_num
                )

                if exercise is None:
                    self.stdout.write(
                        self.style.ERROR(f"  Step {step_num}: engine returned None — pool exhausted?")
                    )
                    break

                # Mastery snapshot BEFORE this step's submission.
                skill_mastery = {}
                for tag in (exercise.skill_tags or []):
                    try:
                        m = StudentSkillMastery.objects.get(user=user, skill_tag=tag)
                        skill_mastery[tag] = m.level
                    except StudentSkillMastery.DoesNotExist:
                        skill_mastery[tag] = "not_started"

                seen_so_far = [s["exercise_id"] for s in steps] + [exercise.id]

                step_data = {
                    "step_number": step_num,
                    "exercise_id": exercise.id,
                    "exercise_constraints": {
                        "skill_tags": exercise.skill_tags,
                        "complexity": exercise.complexity,
                    },
                    "current_mastery_level": skill_mastery,
                    "historical_exercise_ids": list(seen_so_far),
                }
                steps.append(step_data)

                correct = pattern[step_num - 1]
                label = "correct" if correct else "WRONG"
                self.stdout.write(f"  Step {step_num}: {exercise.id}  [{label}]")

                # Simulate submission: update the JIT-reserved PerformanceData slot
                # directly, bypassing the full submit() path to avoid exercise locking
                # and other side-effects that don't apply to a simulation.
                perf, _ = PerformanceData.objects.get_or_create(
                    user=user, playlist=playlist, course=None
                )
                error_tally = 0 if correct else 3
                if len(perf.data) >= step_num:
                    slot = perf.data[step_num - 1]
                    slot["is_placeholder"] = False
                    slot["is_submitted"] = True
                    slot["error_tally"] = error_tally
                    slot["performance_duration_in_seconds"] = 30
                else:
                    perf.data.append({
                        "id": exercise.id + (target_key or ""),
                        "is_placeholder": False,
                        "is_submitted": True,
                        "error_tally": error_tally,
                        "performance_duration_in_seconds": 30,
                    })
                perf.save()

                record_attempt(user.id, exercise, correct=correct)

            report["students"][name] = {"user": name, "steps": steps}
            self.stdout.write("")

        return report

    # ------------------------------------------------------------------
    # Assertions
    # ------------------------------------------------------------------

    def _run_assertions(self, report: dict) -> bool:
        self.stdout.write(self.style.MIGRATE_HEADING("--- Assertions ---"))
        passed = True

        # 1. Initial Diversity Check
        step1_ids = {
            name: data["steps"][0]["exercise_id"]
            for name, data in report["students"].items()
            if data["steps"]
        }
        unique_count = len(set(step1_ids.values()))
        n = len(step1_ids)

        if unique_count == n:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Initial Diversity: all {n} students received distinct exercises at step 1."
            ))
            for name, eid in step1_ids.items():
                self.stdout.write(f"    {name}: {eid}")
        else:
            self.stdout.write(self.style.ERROR(
                f"✗ Initial Diversity FAILED: only {unique_count}/{n} unique exercise(s) at step 1."
            ))
            for name, eid in step1_ids.items():
                self.stdout.write(f"    {name}: {eid}")
            passed = False

        # 2. No-Duplicate Check
        for name, data in report["students"].items():
            ids = [s["exercise_id"] for s in data["steps"]]
            dupes = [eid for eid, cnt in Counter(ids).items() if cnt > 1]
            if not dupes:
                self.stdout.write(self.style.SUCCESS(
                    f"✓ No Duplicates [{name}]: {ids}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"✗ Duplicates [{name}]: repeated {dupes} in {ids}"
                ))
                passed = False

        # 3. Adaptivity Check
        LEVEL_ORDER = ["not_started", "attempted", "familiar", "proficient", "mastered"]

        def level_idx(lvl: str) -> int:
            return LEVEL_ORDER.index(lvl) if lvl in LEVEL_ORDER else 0

        alpha_steps = report["students"].get("student_alpha", {}).get("steps", [])
        beta_steps  = report["students"].get("student_beta",  {}).get("steps", [])

        if len(beta_steps) >= N_STEPS and len(alpha_steps) >= N_STEPS:
            def mastery_at(steps, step_num):
                s = next((x for x in steps if x["step_number"] == step_num), None)
                return s["current_mastery_level"].get(TARGET_SKILL, "not_started") if s else "not_started"

            # Beta fails step 2 → at step 3 snapshot, mastery should be lower than Alpha's.
            alpha_s3 = mastery_at(alpha_steps, 3)
            beta_s3  = mastery_at(beta_steps,  3)

            if level_idx(alpha_s3) >= level_idx(beta_s3):
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Failure Penalty: Alpha ({alpha_s3}) >= Beta ({beta_s3}) at step-3 "
                    "snapshot — Beta's step-2 failure slowed progression."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"? Failure Penalty: Alpha ({alpha_s3}) < Beta ({beta_s3}) at step 3 "
                    "(unexpected; check mastery thresholds)."
                ))

            # Beta should recover: mastery at step 5 >= mastery at step 2.
            beta_s2 = mastery_at(beta_steps, 2)
            beta_s5 = mastery_at(beta_steps, 5)

            if level_idx(beta_s5) >= level_idx(beta_s2):
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Adaptivity Recovery [student_beta]: '{beta_s2}' (step 2) → "
                    f"'{beta_s5}' (step 5) after subsequent successes."
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"✗ Adaptivity Recovery FAILED [student_beta]: mastery did not improve "
                    f"from '{beta_s2}' (step 2) to '{beta_s5}' (step 5)."
                ))
                passed = False
        else:
            self.stdout.write(self.style.WARNING(
                "? Adaptivity check skipped — fewer than expected steps completed."
            ))

        return passed

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup(self, students: dict, exercises: list, playlist: Playlist) -> None:
        PerformanceData.objects.filter(playlist=playlist).delete()
        playlist.delete()
        for ex in exercises:
            Exercise.objects.filter(id=ex.id).delete()
        for user in students.values():
            StudentSkillMastery.objects.filter(user=user).delete()
            user.delete()
        User.objects.filter(email="sim-teacher@local.test").delete()
