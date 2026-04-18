# Mastery Wiring + Feedback Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter mastery updates to canonical skill tags, add playlist-level feedback-mode override, record mode on each identification attempt, and gate frontend with per-mode attempt limits.

**Architecture:** Python/Django backend adds `MASTERY_TAGS` set and filters `record_attempt` against it. Two new DB fields (`Playlist.feedback_mode`, `IdentificationAttempt.mode`) ship in one migration. `generate_exercise_context` computes effective mode (playlist override OR exercise fallback) and a `modeLocked` flag. Frontend (`exercise_sheet.js`) renders a Practice↔Submit toggle honoring `modeLocked`, enforces per-mode attempt limits (3/2/1), and ships mode in the POST payload.

**Tech Stack:** Django 4+, PostgreSQL, Python 3.10+, Backbone/jQuery frontend, unittest + Django test runner.

**Spec:** `docs/superpowers/specs/2026-04-18-mastery-wiring-design.md`

**Branch:** `feature/music21_builder`

---

## File Structure

**Backend (Python):**
- `apps/exercises/skill_graph.py` — add `MASTERY_TAGS` constant (canonical + literacy + unit-number + branch unit tags).
- `apps/exercises/mastery.py` — filter `exercise.skill_tags` against `MASTERY_TAGS` in `record_attempt`.
- `apps/exercises/models.py` — add `Playlist.feedback_mode`, add `IdentificationAttempt.mode`, add shared `FEEDBACK_MODE_CHOICES` constant.
- `apps/exercises/migrations/0062_feedback_mode_and_attempt_mode.py` — single migration for both new fields.
- `apps/exercises/admin.py` — expose `feedback_mode` in `PlaylistAdmin.fieldsets`.
- `apps/exercises/views.py` — read `mode` from POST and persist on `IdentificationAttempt`.
- `lab/views.py` — `generate_exercise_context` emits `identMode` (effective) + `modeLocked`.

**Tests (Python):**
- `apps/exercises/tests/test_mastery.py` — add `TestRecordAttemptCanonicalFilter` class.
- `apps/exercises/tests/test_feedback_mode.py` — NEW: covers `Playlist.feedback_mode`, `IdentificationAttempt.mode`, effective-mode logic.

**Frontend (JS):**
- `lab/static/js/src/models/exercise_definition.js` — honor `modeLocked` and effective `identMode` from server context.
- `lab/static/js/src/models/exercise_context.js` — include `mode` in `submitIdentificationAnswers` POST payload; track per-slot attempt counts.
- `lab/static/js/src/components/music/exercise_sheet.js` — render Practice↔Submit toggle UI when not locked; enforce per-slot attempt limits (3/2/1); disable further edits on exhaustion.

---

## Task List

Tasks are ordered so each produces a commit that leaves the tree green. Tasks 1–3 are pure backend and independently testable. Task 4 is the migration. Task 5 wires the view. Task 6 wires the context. Tasks 7–9 are frontend. Task 10 is end-to-end smoke verification.

---

### Task 1: Add `MASTERY_TAGS` constant to skill_graph

**Files:**
- Modify: `apps/exercises/skill_graph.py`
- Test: `apps/exercises/tests/test_mastery.py` (new class)

- [ ] **Step 1: Write failing test**

Append to `apps/exercises/tests/test_mastery.py`:

```python
from apps.exercises.skill_graph import MASTERY_TAGS, LITERACY_TAGS


class TestMasteryTagsConstant(unittest.TestCase):
    def test_includes_all_canonical_harmony_tags(self):
        canonical = {
            "Diatonic_Triads", "Inversions_First", "Inversions_Second",
            "Dominant_Seventh", "Diminished_Seventh", "Half_Diminished_Seventh",
            "Cadence_Half", "Cadence_Perfect_Authentic", "Cadence_Deceptive", "Cadence_Plagal",
            "Secondary_Dominant", "Secondary_Leading_Tone",
            "Neapolitan_Sixth", "Augmented_Sixth",
            "Picardy_Third", "Modulation_Diatonic_Pivot",
        }
        self.assertTrue(canonical.issubset(MASTERY_TAGS))

    def test_includes_all_literacy_tags(self):
        self.assertTrue(set(LITERACY_TAGS).issubset(MASTERY_TAGS))

    def test_includes_unit_number_tags(self):
        self.assertIn("unit:1", MASTERY_TAGS)
        self.assertIn("unit:9", MASTERY_TAGS)
        self.assertIn("unit:51", MASTERY_TAGS)

    def test_includes_branch_unit_tags(self):
        self.assertIn("unit:A1", MASTERY_TAGS)
        self.assertIn("unit:A15", MASTERY_TAGS)
        self.assertIn("unit:B1", MASTERY_TAGS)
        self.assertIn("unit:B15", MASTERY_TAGS)
        self.assertIn("unit:C1", MASTERY_TAGS)
        self.assertIn("unit:C8", MASTERY_TAGS)
        self.assertIn("unit:D1", MASTERY_TAGS)
        self.assertIn("unit:D8", MASTERY_TAGS)

    def test_excludes_unit_prefixed_long_form_tags(self):
        # These are duplicates of canonical tags — should not appear in mastery set
        self.assertNotIn("unit:9_Dominant_Seventh", MASTERY_TAGS)
        self.assertNotIn("unit:10_inversions_first", MASTERY_TAGS)
        self.assertNotIn("unit:16_Secondary_Dominant", MASTERY_TAGS)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest apps/exercises/tests/test_mastery.py::TestMasteryTagsConstant -v`
Expected: FAIL — `ImportError: cannot import name 'MASTERY_TAGS'`.

- [ ] **Step 3: Add MASTERY_TAGS constant to skill_graph.py**

Append after the `ALL_SKILL_TAGS` definition (just before `# Default prerequisite DAG.` at line ~153):

```python
# MASTERY_TAGS — canonical set of skill tags eligible for StudentSkillMastery rows.
# Filters out unit-prefixed long forms (unit:9_Dominant_Seventh etc.) that duplicate
# canonical tags (Dominant_Seventh). Used by apps.exercises.mastery.record_attempt.
MASTERY_TAGS = (
    # Canonical Knowledge Graph tags (16 harmonic skills)
    {
        "Diatonic_Triads", "Inversions_First", "Inversions_Second",
        "Dominant_Seventh", "Diminished_Seventh", "Half_Diminished_Seventh",
        "Cadence_Half", "Cadence_Perfect_Authentic", "Cadence_Deceptive", "Cadence_Plagal",
        "Secondary_Dominant", "Secondary_Leading_Tone",
        "Neapolitan_Sixth", "Augmented_Sixth",
        "Picardy_Third", "Modulation_Diatonic_Pivot",
    }
    # Literacy tags (emitted by analyzer for all valid exercises)
    | set(LITERACY_TAGS)
    # Core unit-number tags (unit:1..unit:51)
    | {f"unit:{n}" for n in range(1, 52)}
    # Branch unit-number tags (Figured Bass A, Partimenti B, Interval Cycles C, Neo-Riemannian D)
    | {f"unit:A{n}" for n in range(1, 16)}
    | {f"unit:B{n}" for n in range(1, 16)}
    | {f"unit:C{n}" for n in range(1, 9)}
    | {f"unit:D{n}" for n in range(1, 9)}
)
```

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest apps/exercises/tests/test_mastery.py::TestMasteryTagsConstant -v`
Expected: PASS, all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/skill_graph.py apps/exercises/tests/test_mastery.py
git commit -m "feat(mastery): add MASTERY_TAGS canonical tag set

Defines the strict set of skill tags eligible for StudentSkillMastery
rows. Filters out unit-prefixed long-form duplicates. Includes literacy
tags, unit-number tags (1-51), and branch unit tags (A1-A15, B1-B15,
C1-C8, D1-D8). See spec 2026-04-18-mastery-wiring-design.md."
```

---

### Task 2: Filter `record_attempt` against `MASTERY_TAGS`

**Files:**
- Modify: `apps/exercises/mastery.py:92-144`
- Test: `apps/exercises/tests/test_mastery.py`

- [ ] **Step 1: Write failing test**

Append to `apps/exercises/tests/test_mastery.py`:

```python
from unittest.mock import MagicMock, patch
from apps.exercises.mastery import record_attempt


class TestRecordAttemptCanonicalFilter(unittest.TestCase):
    """Verify record_attempt only updates StudentSkillMastery for MASTERY_TAGS."""

    def _make_exercise(self, tags):
        ex = MagicMock()
        ex.skill_tags = tags
        return ex

    @patch("apps.exercises.models.StudentSkillMastery")
    def test_only_canonical_tags_trigger_mastery_updates(self, mock_mastery_cls):
        mock_row = MagicMock()
        mock_row.level = "not_started"
        mock_row.last_practiced = None
        mock_row.recent_history = []
        mock_row.practice_days = []
        mock_row.total_attempts = 0
        mock_row.total_correct = 0
        mock_row.first_attempted = None
        mock_mastery_cls.objects.get_or_create.return_value = (mock_row, True)

        ex = self._make_exercise([
            "Dominant_Seventh",           # canonical — should update
            "unit:9_Dominant_Seventh",    # long-form duplicate — filtered out
            "unit:9",                     # unit-number — should update
            "bach",                       # free-form — filtered out
            "Read_Treble_Clef",           # literacy — should update
        ])

        record_attempt(user_id=1, exercise=ex, correct=True)

        called_tags = [
            call.kwargs["skill_tag"]
            for call in mock_mastery_cls.objects.get_or_create.call_args_list
        ]
        self.assertIn("Dominant_Seventh", called_tags)
        self.assertIn("unit:9", called_tags)
        self.assertIn("Read_Treble_Clef", called_tags)
        self.assertNotIn("unit:9_Dominant_Seventh", called_tags)
        self.assertNotIn("bach", called_tags)

    @patch("apps.exercises.models.StudentSkillMastery")
    def test_no_tags_triggers_no_updates(self, mock_mastery_cls):
        ex = self._make_exercise(["bach", "random_tag"])
        record_attempt(user_id=1, exercise=ex, correct=True)
        mock_mastery_cls.objects.get_or_create.assert_not_called()

    @patch("apps.exercises.models.StudentSkillMastery")
    def test_empty_skill_tags_triggers_no_updates(self, mock_mastery_cls):
        ex = self._make_exercise([])
        record_attempt(user_id=1, exercise=ex, correct=True)
        mock_mastery_cls.objects.get_or_create.assert_not_called()
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest apps/exercises/tests/test_mastery.py::TestRecordAttemptCanonicalFilter -v`
Expected: FAIL — current `record_attempt` iterates ALL tags, so long-form duplicates are passed through.

- [ ] **Step 3: Modify `record_attempt` to filter**

Edit `apps/exercises/mastery.py`:

At the top of the file, update the imports from `skill_graph` to include `MASTERY_TAGS`:

```python
from apps.exercises.skill_graph import (
    ALL_SKILL_TAGS,
    DEFAULT_PREREQUISITES,
    MASTERY_LEVELS,
    MASTERY_TAGS,
    UNLOCK_THRESHOLD,
)
```

Replace the body of `record_attempt` (the `for skill_tag in exercise.skill_tags:` loop header at line 110) with a filtered iteration:

```python
    for skill_tag in exercise.skill_tags:
        if skill_tag not in MASTERY_TAGS:
            continue
        mastery, _ = StudentSkillMastery.objects.get_or_create(
            user_id=user_id,
            skill_tag=skill_tag,
        )
```

The remaining body (decay, history, save) stays unchanged.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest apps/exercises/tests/test_mastery.py -v`
Expected: PASS — all existing tests plus new `TestRecordAttemptCanonicalFilter`.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/mastery.py apps/exercises/tests/test_mastery.py
git commit -m "feat(mastery): filter record_attempt skill_tags to MASTERY_TAGS

Only canonical harmony tags, literacy tags, and unit-number tags now
produce StudentSkillMastery rows. Eliminates duplicate mastery rows
caused by unit-prefixed long-form tags (e.g. unit:9_Dominant_Seventh)
that coexisted with their canonical counterparts."
```

---

### Task 3: Add `FEEDBACK_MODE_CHOICES` + `Playlist.feedback_mode` field

**Files:**
- Modify: `apps/exercises/models.py`

- [ ] **Step 1: Add module-level FEEDBACK_MODE_CHOICES constant**

In `apps/exercises/models.py`, add a module-level constant immediately after the `User = get_user_model()` line (around line 35):

```python
FEEDBACK_MODE_CHOICES = [
    ("submit",   "Submit — see results after submitting"),
    ("practice", "Practice — immediate feedback per slot"),
    ("test",     "Test — no feedback, answers locked"),
]
```

- [ ] **Step 2: Add `feedback_mode` field to Playlist**

In `apps/exercises/models.py`, inside `class Playlist`, add this field immediately after `skill_tags = ArrayField(...)` (after line 549, before `zero_padding = "PA00A0"`):

```python
    feedback_mode = models.CharField(
        "Feedback Mode Override",
        max_length=16,
        choices=FEEDBACK_MODE_CHOICES,
        blank=True,
        default="",
        help_text=(
            "Overrides exercise identMode for all exercises in this playlist. "
            "Leave blank to use each exercise's own setting."
        ),
    )
```

- [ ] **Step 3: Add `mode` field to IdentificationAttempt**

In `apps/exercises/models.py`, inside `class IdentificationAttempt`, add this field after the `page_num` field (around line 423, before `class Meta`):

```python
    mode = models.CharField(
        "Feedback Mode",
        max_length=16,
        choices=FEEDBACK_MODE_CHOICES,
        blank=True,
        default="",
        help_text=(
            "Mode in effect when this attempt was submitted. "
            "Empty string = pre-migration attempt (mode unknown)."
        ),
    )
```

- [ ] **Step 4: Verify no syntax errors**

Run: `python -c "import django; django.setup()" 2>&1 | head -5` (with DJANGO_SETTINGS_MODULE set) OR simply try makemigrations in Task 4 — any syntax error will surface there.

No commit yet — Task 4 commits migration together with model changes.

---

### Task 4: Generate single migration for both new fields

**Files:**
- Create: `apps/exercises/migrations/0062_feedback_mode_and_attempt_mode.py`

- [ ] **Step 1: Autogenerate migration**

Run:
```bash
python manage.py makemigrations exercises --name feedback_mode_and_attempt_mode
```

Expected output: `Migrations for 'exercises': 0062_feedback_mode_and_attempt_mode.py` listing `AddField: playlist.feedback_mode` and `AddField: identificationattempt.mode`.

- [ ] **Step 2: Inspect the generated file**

Run: `cat apps/exercises/migrations/0062_feedback_mode_and_attempt_mode.py`

Verify it contains exactly two `AddField` operations: one for `Playlist.feedback_mode` and one for `IdentificationAttempt.mode`, each with the `FEEDBACK_MODE_CHOICES` options, `blank=True`, `default=""`.

If Django split them into separate files, consolidate manually — there must be a single migration file with both operations.

- [ ] **Step 3: Run migration**

Run: `python manage.py migrate exercises`
Expected: `Applying exercises.0062_feedback_mode_and_attempt_mode... OK`.

- [ ] **Step 4: Verify via quick shell check**

Run:
```bash
python manage.py shell -c "from apps.exercises.models import Playlist, IdentificationAttempt; print(Playlist._meta.get_field('feedback_mode')); print(IdentificationAttempt._meta.get_field('mode'))"
```
Expected: two `<django.db.models.fields.CharField>` lines.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/models.py apps/exercises/migrations/0062_feedback_mode_and_attempt_mode.py
git commit -m "feat(models): add Playlist.feedback_mode and IdentificationAttempt.mode

- Playlist.feedback_mode: teacher-set override that forces identMode
  for all exercises in the playlist; blank means per-exercise default.
- IdentificationAttempt.mode: records the mode active at submission
  time for audit trail and future adaptive ranker weighting. Default is
  empty string (not 'submit') so pre-migration rows are distinguishable.
- Single migration file for both fields."
```

---

### Task 5: Expose `feedback_mode` in PlaylistAdmin

**Files:**
- Modify: `apps/exercises/admin.py:274-316`

- [ ] **Step 1: Add `feedback_mode` to PlaylistAdmin fieldsets**

In `apps/exercises/admin.py`, inside `PlaylistAdmin.fieldsets`, locate the tuple inside `"Playlist Information"` (currently lines 280-293). Add `"feedback_mode"` as a new field in that same fields tuple, immediately after `"skill_tags"`:

Change from:
```python
                    "skill_tags",
                    "min_complexity",
                    "max_complexity",
```
to:
```python
                    "skill_tags",
                    "feedback_mode",
                    "min_complexity",
                    "max_complexity",
```

- [ ] **Step 2: Verify admin renders**

Run: `python manage.py check`
Expected: `System check identified no issues`.

(Optional manual verify: start dev server, open `/admin/exercises/playlist/add/`, confirm "Feedback Mode Override" dropdown renders.)

- [ ] **Step 3: Commit**

```bash
git add apps/exercises/admin.py
git commit -m "feat(admin): expose Playlist.feedback_mode in PlaylistAdmin"
```

---

### Task 6: Persist `mode` on IdentificationAttempt in view

**Files:**
- Modify: `apps/exercises/views.py:128-163`
- Test: `apps/exercises/tests/test_feedback_mode.py` (new)

- [ ] **Step 1: Write failing test**

Create `apps/exercises/tests/test_feedback_mode.py`:

```python
"""Tests for Playlist.feedback_mode, IdentificationAttempt.mode, and effective-mode logic."""
import json
import os
import django

if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "harmony.settings"
    django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from apps.exercises.models import (
    Exercise, Playlist, Course, IdentificationAttempt,
)

User = get_user_model()


class TestIdentificationAttemptMode(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@test.com",
            password="pw",
            first_name="T",
            last_name="Student",
        )
        self.exercise = Exercise.objects.create(
            authored_by=self.user,
            data={"type": "identification"},
        )
        self.playlist = Playlist.objects.create(
            authored_by=self.user,
            name="Test Playlist",
        )
        self.playlist.append_exercise(self.exercise.id)
        self.course = Course.objects.create(
            authored_by=self.user,
            title="Test Course",
        )

    def test_attempt_saves_mode_from_post(self):
        client = Client()
        client.force_login(self.user)
        payload = {
            "course_ID": self.course.id,
            "playlist_ID": self.playlist.id,
            "exercise_num": 1,
            "answers": {"0": "I"},
            "correctness": {"0": True},
            "score": {"correct": 1, "incorrect": 0, "unanswered": 0},
            "correct_answers": {"0": "I"},
            "mode": "practice",
        }
        resp = client.post(
            "/ajax/identification-answers/",
            {"data": json.dumps(payload)},
        )
        self.assertEqual(resp.status_code, 201)
        attempt = IdentificationAttempt.objects.filter(user=self.user).last()
        self.assertEqual(attempt.mode, "practice")

    def test_attempt_without_mode_defaults_to_empty(self):
        client = Client()
        client.force_login(self.user)
        payload = {
            "course_ID": self.course.id,
            "playlist_ID": self.playlist.id,
            "exercise_num": 1,
            "answers": {"0": "I"},
            "correctness": {"0": True},
            "score": {"correct": 1, "incorrect": 0, "unanswered": 0},
            "correct_answers": {"0": "I"},
            # no "mode" key
        }
        resp = client.post(
            "/ajax/identification-answers/",
            {"data": json.dumps(payload)},
        )
        self.assertEqual(resp.status_code, 201)
        attempt = IdentificationAttempt.objects.filter(user=self.user).last()
        self.assertEqual(attempt.mode, "")
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest apps/exercises/tests/test_feedback_mode.py::TestIdentificationAttemptMode -v`
Expected: FAIL — view does not yet persist `mode`, so `attempt.mode` is `""` for both or test errors because `.mode` attr exists but view never wrote it.

(First test should fail; second should already pass because default is `""`.)

- [ ] **Step 3: Persist mode in identification_answers_view**

Edit `apps/exercises/views.py`, inside `identification_answers_view` POST branch. Modify the `IdentificationAttempt.objects.create(...)` call (at lines 142-153) to include a `mode` kwarg:

```python
        IdentificationAttempt.objects.create(
            user=request.user,
            exercise=exercise,
            course=course,
            playlist=playlist,
            answers=data.get("answers", {}),
            correctness=data.get("correctness", {}),
            score=data.get("score", {}),
            correct_answers=data.get("correct_answers", {}),
            page_num=data.get("page_num"),
            is_page_submit=data.get("is_page_submit", False),
            mode=data.get("mode", ""),
        )
```

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest apps/exercises/tests/test_feedback_mode.py::TestIdentificationAttemptMode -v`
Expected: PASS — both tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/exercises/views.py apps/exercises/tests/test_feedback_mode.py
git commit -m "feat(views): persist mode on IdentificationAttempt

Reads 'mode' from POST payload and stores it on the new
IdentificationAttempt.mode field. Default '' when missing preserves
pre-migration audit boundary."
```

---

### Task 7: Emit effective `identMode` + `modeLocked` from `generate_exercise_context`

**Files:**
- Modify: `lab/views.py:272-298`
- Test: `apps/exercises/tests/test_feedback_mode.py`

- [ ] **Step 1: Add failing test**

Append to `apps/exercises/tests/test_feedback_mode.py`:

```python
class TestEffectiveIdentMode(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="t2@test.com", password="pw",
            first_name="T", last_name="Two",
        )
        self.exercise = Exercise.objects.create(
            authored_by=self.user,
            data={"type": "identification", "identMode": "submit"},
        )
        self.playlist = Playlist.objects.create(
            authored_by=self.user, name="P",
        )
        self.playlist.append_exercise(self.exercise.id)

    def test_playlist_override_wins(self):
        from lab.views import generate_exercise_context
        self.playlist.feedback_mode = "practice"
        self.playlist.save()
        ctx = generate_exercise_context(
            exercise_num=1, exercise=self.exercise,
            user=self.user, playlist=self.playlist, course=None,
        )
        self.assertEqual(ctx["identMode"], "practice")
        self.assertTrue(ctx["modeLocked"])

    def test_exercise_fallback_when_playlist_blank(self):
        from lab.views import generate_exercise_context
        self.playlist.feedback_mode = ""
        self.playlist.save()
        ctx = generate_exercise_context(
            exercise_num=1, exercise=self.exercise,
            user=self.user, playlist=self.playlist, course=None,
        )
        self.assertEqual(ctx["identMode"], "submit")
        self.assertFalse(ctx["modeLocked"])

    def test_exercise_missing_ident_mode_defaults_to_submit(self):
        from lab.views import generate_exercise_context
        self.exercise.data = {"type": "identification"}  # no identMode
        self.exercise.save()
        ctx = generate_exercise_context(
            exercise_num=1, exercise=self.exercise,
            user=self.user, playlist=self.playlist, course=None,
        )
        self.assertEqual(ctx["identMode"], "submit")
        self.assertFalse(ctx["modeLocked"])
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest apps/exercises/tests/test_feedback_mode.py::TestEffectiveIdentMode -v`
Expected: FAIL — keys `identMode` / `modeLocked` not in context dict yet.

- [ ] **Step 3: Add identMode + modeLocked to context**

Edit `lab/views.py`, inside `generate_exercise_context()`. Locate the `exercise_context.update({...})` block starting at line 272. Add two new keys to the update dict (any location in the dict is fine, keeping them near `skillTags` is conventional):

```python
            "skillTags": getattr(exercise, "skill_tags", []),
            "playlistSkillTags": getattr(playlist, "skill_tags", []),
            "identMode": (
                (getattr(playlist, "feedback_mode", "") or "")
                or (exercise.data.get("identMode", "submit") if isinstance(getattr(exercise, "data", None), dict) else "submit")
            ),
            "modeLocked": bool(getattr(playlist, "feedback_mode", "") or ""),
```

Keep this compact and inline — `exercise.data` is always a dict in practice but the `isinstance` guard keeps tests with minimal fixtures stable.

- [ ] **Step 4: Run test to verify pass**

Run: `python -m pytest apps/exercises/tests/test_feedback_mode.py -v`
Expected: PASS — all 5 feedback_mode tests green.

- [ ] **Step 5: Commit**

```bash
git add lab/views.py apps/exercises/tests/test_feedback_mode.py
git commit -m "feat(lab): emit effective identMode + modeLocked from context

generate_exercise_context now sends:
  identMode   = playlist.feedback_mode OR exercise.data['identMode']
  modeLocked  = bool(playlist.feedback_mode)

Frontend uses these to wire the mode toggle and pin mode when the
teacher has overridden at the playlist level."
```

---

### Task 8: Frontend — consume `modeLocked` / `identMode` in exercise_definition

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js:562-564`

- [ ] **Step 1: Update `getIdentMode` fallback + add `isModeLocked`**

In `lab/static/js/src/models/exercise_definition.js`, replace the `getIdentMode` function (at line 562) and add a sibling `isModeLocked` method:

```javascript
    /**
     * Returns the effective feedback mode for identification exercises.
     * Server writes the effective value (playlist override OR exercise default)
     * into exercise.identMode; frontend treats it as authoritative.
     *
     * @return {string}  "submit" | "practice" | "test"
     */
    getIdentMode: function () {
      return this.exercise.identMode || "submit";
    },
    /**
     * True when the teacher has locked the feedback mode at the playlist level.
     * Frontend must hide the mode-toggle UI when this is true.
     *
     * @return {boolean}
     */
    isModeLocked: function () {
      return !!this.exercise.modeLocked;
    },
```

In the same file, locate the two places that set `exercise.identMode = definition.identMode || "submit"` (lines 705 and 894) — add a `exercise.modeLocked = !!definition.modeLocked;` line immediately after each:

At line 705 area:
```javascript
        exercise.identMode = definition.identMode || "submit";
        exercise.modeLocked = !!definition.modeLocked;
```

At line 894 area:
```javascript
        exercise.identMode = definition.identMode || "submit";
        exercise.modeLocked = !!definition.modeLocked;
```

- [ ] **Step 2: Syntax check**

No backend test covers this — JS module loads only in-browser. Run the Django collectstatic no-op to confirm no parse error surfaces at build time:

```bash
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat(frontend): propagate modeLocked flag through definition

getIdentMode() already reads exercise.identMode; now also accept the
modeLocked boolean so exercise_sheet can decide whether to render the
Practice<->Submit toggle."
```

---

### Task 9: Frontend — mode toggle UI, per-slot attempt limits, POST mode

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:668-728`
- Modify: `lab/static/js/src/components/music/exercise_sheet.js:172-198`, `291-342`

- [ ] **Step 1: Send mode in submitIdentificationAnswers payload**

In `lab/static/js/src/models/exercise_context.js`, inside `submitIdentificationAnswers` (around line 704), add `mode` to the payload object. Change:

```javascript
      var payload = {
        course_ID: this.definition.exercise.performing_course,
        playlist_ID: listEntry.id.split("/")[0],
        exercise_num: parseInt(listEntry.id.split("/")[1], 10),
        answers: answers,
        correctness: correctness,
        score: { correct: correct, incorrect: incorrect, unanswered: unanswered },
        correct_answers: correct_answers,
        page_num: this._identPage,
        is_page_submit: isPageSubmit
      };
```

to:

```javascript
      var payload = {
        course_ID: this.definition.exercise.performing_course,
        playlist_ID: listEntry.id.split("/")[0],
        exercise_num: parseInt(listEntry.id.split("/")[1], 10),
        answers: answers,
        correctness: correctness,
        score: { correct: correct, incorrect: incorrect, unanswered: unanswered },
        correct_answers: correct_answers,
        page_num: this._identPage,
        is_page_submit: isPageSubmit,
        mode: (this.definition.getIdentMode ? this.definition.getIdentMode() : "submit")
      };
```

- [ ] **Step 2: Render toggle + track per-slot attempts in initIdentificationMode**

In `lab/static/js/src/components/music/exercise_sheet.js`, inside `initIdentificationMode` (line 172), add toggle logic and an attempts bookkeeping object immediately after reading `identMode` (after line 182):

Replace the block from line 182 through line 198 (the `if (identMode === 'submit') { ... } else { ... }` block) with:

```javascript
      var identMode = definition.getIdentMode ? definition.getIdentMode() : 'submit';
      var modeLocked = definition.isModeLocked ? definition.isModeLocked() : false;

      // Per-slot attempt tracking.  practice=3, submit=2, test=1.
      this._slotAttempts = {};
      this._attemptLimitFor = function (mode) {
        if (mode === 'practice') return 3;
        if (mode === 'test')     return 1;
        return 2; // submit
      };

      // Show Submit button only in submit mode
      if (identMode === 'submit') {
        $('#identification-actions').show();
        var $submitBtn = $('#identification-submit');
        $submitBtn.attr('type', 'button');
        var submitBtnEl = $submitBtn[0];
        if (submitBtnEl) {
          submitBtnEl.onclick = null;
          submitBtnEl.onclick = _.bind(this.onSubmitIdentification, this);
        }
      } else {
        $('#identification-actions').hide();
      }

      // Mode toggle: Practice <-> Submit.  Hidden when locked or when in test mode.
      var $toggleContainer = $('#ident-mode-toggle-container');
      if ($toggleContainer.length === 0) {
        $toggleContainer = $(
          '<div id="ident-mode-toggle-container" style="text-align:center;margin-bottom:8px;">' +
          '  <button id="ident-mode-toggle" type="button" style="font-size:12px;padding:4px 10px;border-radius:14px;border:1px solid #ccc;background:#fff;cursor:pointer;"></button>' +
          '  <span id="ident-mode-nudge" style="display:block;font-size:11px;color:#888;margin-top:4px;"></span>' +
          '</div>'
        );
        $('#identification-actions').before($toggleContainer);
      }

      if (modeLocked || identMode === 'test') {
        $toggleContainer.hide();
      } else {
        var $btn = $('#ident-mode-toggle');
        var $nudge = $('#ident-mode-nudge');
        var labelFor = function (m) { return m === 'practice' ? 'Mode: Practice (switch to Submit)' : 'Mode: Submit (switch to Practice)'; };
        $btn.text(labelFor(identMode));
        $nudge.text(identMode === 'practice' ? 'Switch to Submit mode to earn full mastery credit' : '');
        $toggleContainer.show();
        $btn.off('click.modetoggle').on('click.modetoggle', function () {
          var cur = definition.getIdentMode ? definition.getIdentMode() : 'submit';
          var next = cur === 'practice' ? 'submit' : 'practice';
          definition.exercise.identMode = next;
          $btn.text(labelFor(next));
          $nudge.text(next === 'practice' ? 'Switch to Submit mode to earn full mastery credit' : '');
          // Reset per-slot attempts so the new mode's allowance applies cleanly.
          self._slotAttempts = {};
          self.render();
        });
      }
```

- [ ] **Step 3: Enforce per-slot attempt limit inside popup click handler**

In the same file, inside `_showIdentPopup` (line 291), the popup button click handler currently calls `grdr.setAnswer(problemIndex, choice)` unconditionally. Wrap that call with an attempt-limit check. Replace the inner body of the `btn.on('click', ...)` handler (lines 298-341) with a version that increments and gates:

Find the block:

```javascript
        btn.on('click', function (e) {
          e.stopPropagation();
          var grdr = self.exerciseContext.grader;
          grdr.setAnswer(problemIndex, choice);
          self._closeIdentPopup();

          var currentMode = self.exerciseContext.getDefinition().getIdentMode
            ? self.exerciseContext.getDefinition().getIdentMode() : 'submit';
```

Replace with:

```javascript
        btn.on('click', function (e) {
          e.stopPropagation();
          var grdr = self.exerciseContext.grader;
          var currentMode = self.exerciseContext.getDefinition().getIdentMode
            ? self.exerciseContext.getDefinition().getIdentMode() : 'submit';

          // Per-slot attempt limit (3/2/1 for practice/submit/test).
          if (!self._slotAttempts) { self._slotAttempts = {}; }
          var used = self._slotAttempts[problemIndex] || 0;
          var limit = self._attemptLimitFor
            ? self._attemptLimitFor(currentMode)
            : (currentMode === 'practice' ? 3 : currentMode === 'test' ? 1 : 2);
          if (used >= limit) {
            self._closeIdentPopup();
            return;
          }
          self._slotAttempts[problemIndex] = used + 1;

          grdr.setAnswer(problemIndex, choice);
          self._closeIdentPopup();
```

Leave the remainder of that handler (the `if (currentMode === 'practice') { ... } else if (currentMode === 'test') { ... } else { ... }` block) unchanged.

- [ ] **Step 4: Block re-opening the popup after exhaustion**

In the canvas click handler in `initIdentificationMode` (around line 238-246), add an attempt-limit check that prevents opening the popup for exhausted slots. Locate the `if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(absoluteHitIndex))` block and add a sibling check right after it:

```javascript
        if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(absoluteHitIndex)) {
          return;
        }

        // Block reopening once per-slot attempt limit is reached.
        var attemptsUsed = (self._slotAttempts && self._slotAttempts[absoluteHitIndex]) || 0;
        var attemptsLimit = self._attemptLimitFor
          ? self._attemptLimitFor(currentMode)
          : (currentMode === 'practice' ? 3 : currentMode === 'test' ? 1 : 2);
        if (attemptsUsed >= attemptsLimit) {
          return;
        }
```

- [ ] **Step 5: Manual smoke test**

Start dev server, load an identification exercise inside a playlist:

```bash
python manage.py runserver
```

Scenarios to click through:
1. No playlist override, exercise `identMode=submit` → toggle visible, says "Mode: Submit (switch to Practice)", 2 attempts per slot.
2. Playlist `feedback_mode=practice` → toggle hidden, page runs in practice mode, 3 attempts per slot.
3. Exercise with `identMode=test` → toggle hidden, 1 attempt per slot, no colour feedback.
4. Click a slot 3 times in practice mode — 3rd click still registers, 4th click does nothing.
5. Submit → POST payload includes `"mode": "<current>"` (inspect in DevTools Network tab).

Record any failures in commit message if they require follow-up.

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(frontend): mode toggle, per-slot attempt limits, send mode on POST

- Practice<->Submit toggle button appears in initIdentificationMode
  when !modeLocked && mode != 'test'.  Nudge copy prompts the student
  to earn full mastery credit by switching to Submit.
- Per-slot attempt limits enforced in the popup click handler and the
  canvas hit-zone handler: 3 (practice), 2 (submit), 1 (test).
  Exhausted slots ignore further clicks.
- submitIdentificationAnswers POST payload now includes 'mode' so the
  IdentificationAttempt row records which mode was active."
```

---

### Task 10: End-to-end verification

**Files:** None (verification only).

- [ ] **Step 1: Run full test suite**

Run:
```bash
python -m pytest apps/exercises/tests/ -v
```
Expected: all tests pass, including the new `TestMasteryTagsConstant`, `TestRecordAttemptCanonicalFilter`, `TestIdentificationAttemptMode`, `TestEffectiveIdentMode`.

- [ ] **Step 2: Confirm migrations are up to date**

Run:
```bash
python manage.py makemigrations --dry-run
```
Expected: `No changes detected`.

- [ ] **Step 3: Django system check**

Run:
```bash
python manage.py check
```
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Spot-check StudentSkillMastery growth**

Start shell:
```bash
python manage.py shell
```
```python
from apps.exercises.models import Exercise, StudentSkillMastery
from apps.exercises.mastery import record_attempt

# Pick any exercise with a mix of canonical and long-form tags
ex = Exercise.objects.exclude(skill_tags=[]).first()
print("Tags:", ex.skill_tags)

before = StudentSkillMastery.objects.count()
record_attempt(user_id=1, exercise=ex, correct=True)
after = StudentSkillMastery.objects.count()
print(f"Created {after - before} mastery rows (expected <= canonical tag count)")
```
Expected: number of new rows equals number of tags present in `MASTERY_TAGS`, not total tag count.

- [ ] **Step 5: Final commit (if any) + push**

If any of the above steps required a fix, commit it. Otherwise the branch is ready:

```bash
git log --oneline feature/music21_builder ^master | head -10
```
Expected: ~9 new commits (Tasks 1–9).

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Implemented in |
|--------------|----------------|
| 1. `MASTERY_TAGS` constant | Task 1 |
| 2. `record_attempt` canonical filter | Task 2 |
| 3. Identification view — no change needed | N/A (verified in Task 6 test) |
| 4. `Playlist.feedback_mode` override | Task 3 + Task 4 (migration) + Task 5 (admin) |
| 5. `IdentificationAttempt.mode` field | Task 3 + Task 4 + Task 6 (view persist) |
| 6. Exercise context sends effective mode | Task 7 |
| 7. Frontend: toggle + attempt limits | Tasks 8, 9 |

**Deferred items from spec remain deferred:** per-problem skill attribution, mode weight in adaptive ranker, cross-unit DAG edges. No tasks opened for these.

**Constraints honored:**
- `compute_mastery_level` untouched ✓
- `exercise.data["identMode"]` read-only ✓ (server writes `identMode` into context as the effective value; does not mutate `exercise.data`)
- Single migration file (Task 4) ✓
- `IdentificationAttempt.mode` default is `""` not `"submit"` ✓
- No `tested_tags` param added ✓
