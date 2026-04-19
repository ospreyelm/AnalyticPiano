# Mastery Wiring: Skill-Filtered Updates + Feedback Mode

**Date:** 2026-04-18  
**Status:** Approved for implementation  
**Branch:** feature/music21_builder

---

## Problem

1. `record_attempt` updates mastery for ALL `exercise.skill_tags`, including unit-prefixed duplicates (`unit:9_Dominant_Seventh`, `Dominant_Seventh`) and skills not actually tested in skill-filtered identification exercises.
2. No feedback mode override at playlist level — teacher cannot set all exercises in a playlist to test mode.
3. Mode not recorded per attempt — no audit trail for adaptive ranking.
4. Attempt limits are infinite — no pedagogical constraint.

---

## Design

### Principle

Mastery = did the student demonstrate the skill, yes/no. Mode affects UX and future adaptive ranking, not mastery history. Keep `compute_mastery_level` unchanged.

---

## Components

### 1. `MASTERY_TAGS` constant (NEW)

**File:** `apps/exercises/skill_graph.py`

Strict canonical set — only tags that map to meaningful mastery rows. Filters out unit-prefixed long forms (`unit:9_Dominant_Seventh`, `unit:10_inversions_first`, etc.).

```python
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
    # Unit-number-only tags — used by adaptive pool queries
    | {f"unit:{n}" for n in range(1, 52)}
    # Branch unit-number tags (Figured Bass A, Counterpoint B, Post-tonal C, Neo-Riemannian D)
    | {f"unit:A{n}" for n in range(1, 16)}
    | {f"unit:B{n}" for n in range(1, 16)}
    | {f"unit:C{n}" for n in range(1, 9)}
    | {f"unit:D{n}" for n in range(1, 9)}
)
```

Branch tag counts derived from `skill_graph.py` ALL_SKILL_TAGS: A1–A15, B1–B10+, C1–C8, D1–D8. Use generous upper bounds — extra tags in set cost nothing.

---

### 2. `record_attempt` canonical filter (MODIFIED)

**File:** `apps/exercises/mastery.py`

Add import and filter at top of loop:

```python
from apps.exercises.skill_graph import MASTERY_TAGS

def record_attempt(user_id: int, exercise, correct: bool) -> None:
    tags_to_update = [t for t in exercise.skill_tags if t in MASTERY_TAGS]
    for skill_tag in tags_to_update:
        ...  # existing logic unchanged
```

No `tested_tags` param — YAGNI. Per-problem attribution (mapping each visible slot to its specific skill tag) requires richer problem metadata not yet present. Deferred. Canonical filter eliminates duplicate rows — the primary value here.

---

### 3. Identification view: no change to `record_attempt` call

**File:** `apps/exercises/views.py`

`record_attempt` called as today. Canonical filter inside `record_attempt` handles deduplication. Visible-only skill attribution deferred (see Deferred section).

---

### 4. `Playlist.feedback_mode` override (NEW)

**File:** `apps/exercises/models.py`

```python
FEEDBACK_MODE_CHOICES = [
    ("submit",   "Submit — see results after submitting"),
    ("practice", "Practice — immediate feedback per slot"),
    ("test",     "Test — no feedback, answers locked"),
]

feedback_mode = models.CharField(
    "Feedback Mode Override",
    max_length=16,
    choices=FEEDBACK_MODE_CHOICES,
    blank=True,
    default="",
    help_text="Overrides exercise identMode for all exercises in this playlist. "
              "Leave blank to use each exercise's own setting.",
)
```

**Admin:** Add `feedback_mode` to `PlaylistAdmin` fieldsets.

---

### 5. `IdentificationAttempt.mode` field (NEW)

**File:** `apps/exercises/models.py`

```python
mode = models.CharField(
    "Feedback Mode",
    max_length=16,
    choices=FEEDBACK_MODE_CHOICES,
    blank=True,
    default="",
    help_text="Mode in effect when this attempt was submitted. "
              "Empty = pre-migration attempt (mode unknown).",
)
```

`default=""` — pre-migration rows marked unknown, not retroactively assigned `submit`. Cleaner audit trail.

View saves mode from POST:
```python
IdentificationAttempt.objects.create(
    ...
    mode=data.get("mode", ""),
)
```

**Migration:** Both `Playlist.feedback_mode` and `IdentificationAttempt.mode` in a single migration file — one deploy step.

---

### 6. Exercise context sends effective mode (MODIFIED)

**File:** `lab/views.py`, `generate_exercise_context()`

```python
exercise_mode = exercise.data.get("identMode", "submit")
playlist_mode = getattr(playlist, "feedback_mode", "") or ""
effective_mode = playlist_mode or exercise_mode

context["identMode"] = effective_mode
context["modeLocked"] = bool(playlist_mode)  # frontend disables toggle if True
```

---

### 7. Frontend: mode toggle + attempt limits (NEW)

**Files:** `lab/static/js/src/components/music/exercise_sheet.js`

- On load: read `identMode` from exercise context. Set session mode.
- If `modeLocked=true` OR `identMode="test"`: hide toggle, mode locked.
- Otherwise: show toggle button `Practice ↔ Submit` with nudge copy:
  `"Switch to Submit mode to earn full mastery credit"`

**Per-slot attempt limits:**

```
practice → 3 attempts per slot
submit   → 2 attempts per slot
test     → 1 attempt per slot
```

After limit reached: popup closes. Slot treated as **incorrect** for mastery (unanswered = miss). Student sees neutral indicator (no red/green). `record_attempt` called with `correct=False` for that exercise when final submit fires.

**Mode sent with POST on submit:**
```javascript
data.mode = currentMode;  // "practice" | "submit" | "test"
```

---

## Data Flow

```
generate_exercise_context()
  → identMode = playlist.feedback_mode OR exercise.data["identMode"]
  → modeLocked = bool(playlist.feedback_mode)

ExerciseSheet (frontend)
  → reads identMode, sets session mode
  → toggle shown if !modeLocked && mode != "test"
  → enforces per-slot attempt limits (3/2/1)
  → exhausted slot = neutral UI, counts as incorrect on submit
  → sends mode with submission POST

identification_answers_view (backend)
  → saves IdentificationAttempt with mode
  → calls record_attempt(exercise, correct)

record_attempt (mastery.py)
  → filters skill_tags to MASTERY_TAGS (canonical only, no duplicates)
  → updates StudentSkillMastery rows (bool history, unchanged thresholds)
```

---

## What Is NOT Changed

| Component | Reason |
|-----------|--------|
| `compute_mastery_level` | Thresholds unchanged — history stays boolean |
| `exercise.data["identMode"]` | Existing field, read as fallback |
| Chorale play path | `record_attempt` unchanged — canonical filter applies automatically |
| Mastery gating / unlock logic | Out of scope — separate task (seed DAG cross-unit edges) |
| Mode weight in adaptive ranker | Deferred until ranker built |

---

## Files Changed

| File | Change |
|------|--------|
| `apps/exercises/skill_graph.py` | Add `MASTERY_TAGS` constant |
| `apps/exercises/mastery.py` | Filter `exercise.skill_tags` to `MASTERY_TAGS` before loop |
| `apps/exercises/models.py` | `Playlist.feedback_mode`, `IdentificationAttempt.mode` |
| `apps/exercises/admin.py` | Expose `feedback_mode` in PlaylistAdmin |
| `apps/exercises/migrations/XXXX_feedback_mode_and_attempt_mode.py` | Single migration, both fields |
| `lab/views.py` | `generate_exercise_context` sends `identMode` + `modeLocked` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Mode toggle UI, attempt limits, send mode with POST |

---

## Deferred

| Item | Reason |
|------|--------|
| Per-problem skill attribution (map each visible slot → specific canonical tag) | Requires richer problem metadata in exercise.data; canonical filter in `record_attempt` solves duplicate row problem adequately for now |
| Mode weight in adaptive ranker | Deferred until ranker built |
| Cross-unit DAG edges (unit:10→unit:9) | Separate task |
