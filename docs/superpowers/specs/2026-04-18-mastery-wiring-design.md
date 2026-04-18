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

Strict canonical set — only tags that map to meaningful mastery rows. Filters out unit-prefixed long forms.

```python
MASTERY_TAGS = {
    # Canonical Knowledge Graph tags
    "Diatonic_Triads", "Inversions_First", "Inversions_Second",
    "Dominant_Seventh", "Diminished_Seventh", "Half_Diminished_Seventh",
    "Cadence_Half", "Cadence_Perfect_Authentic", "Cadence_Deceptive", "Cadence_Plagal",
    "Secondary_Dominant", "Secondary_Leading_Tone",
    "Neapolitan_Sixth", "Augmented_Sixth",
    "Picardy_Third", "Modulation_Diatonic_Pivot",
    # Unit-number tags (without suffix) — used by adaptive pool queries
    *[f"unit:{n}" for n in range(1, 52)],
}
```

---

### 2. `record_attempt` gains `tested_tags` param (MODIFIED)

**File:** `apps/exercises/mastery.py`

```python
def record_attempt(user_id: int, exercise, correct: bool, tested_tags=None) -> None:
```

- `tested_tags=None` → use `exercise.skill_tags` filtered by `MASTERY_TAGS`
- `tested_tags=[...]` → use caller-supplied list (already filtered to visible skills)

Internal filter applied regardless:
```python
from apps.exercises.skill_graph import MASTERY_TAGS
tags_to_update = [t for t in (tested_tags or exercise.skill_tags) if t in MASTERY_TAGS]
```

This deduplicates: one mastery row per canonical skill, no `unit:9_Dominant_Seventh` rows.

---

### 3. Identification view derives `tested_tags` from visible problems (MODIFIED)

**File:** `apps/exercises/views.py`, `identification_answers_view`

After saving `IdentificationAttempt`, before calling `record_attempt`:

```python
# Derive skill_tags for only the skills actually tested (non-hidden problems)
# exercise.data["problems"] contains the full problem list including hidden ones.
# The submitted answers dict only has keys for visible problems.
answered_indices = set(data.get("answers", {}).keys())
all_problems = exercise.data.get("problems", [])
tested_skills = set()
for idx, prob in enumerate(all_problems):
    if not prob.get("hidden") and str(idx) in answered_indices:
        # Each problem has an 'answer' field with the roman numeral label.
        # Map back to skill_tags via exercise.skill_tags (coarse — use exercise tags).
        pass

# Simpler: use exercise.skill_tags filtered by MASTERY_TAGS.
# Tested-only filtering is enforced by the hidden problem mechanism —
# students cannot answer hidden slots, so exercise.skill_tags is correct
# IF the exercise was generated from a skill-filtered playlist.
# For now: pass exercise.skill_tags; tested_tags refinement deferred.
record_attempt(user_id=request.user.id, exercise=exercise, correct=correct)
```

**Note:** Full per-problem skill attribution (mapping each roman numeral slot to a specific canonical tag) requires richer problem metadata. Deferred. The canonical filter in `record_attempt` already prevents duplicate rows — this is the higher-value fix.

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

**Migration:** Single `AddField`.

**Admin:** Add `feedback_mode` to `PlaylistAdmin` fieldsets.

---

### 5. `IdentificationAttempt.mode` field (NEW)

**File:** `apps/exercises/models.py`

```python
mode = models.CharField(
    "Feedback Mode",
    max_length=16,
    choices=FEEDBACK_MODE_CHOICES,
    default="submit",
)
```

**Migration:** Single `AddField` with default `submit` (backward compatible with existing attempts).

View saves mode from POST data:
```python
IdentificationAttempt.objects.create(
    ...
    mode=data.get("mode", "submit"),
)
```

---

### 6. Exercise context sends effective mode (MODIFIED)

**File:** `lab/views.py`, `generate_exercise_context()`

```python
exercise_mode = exercise.data.get("identMode", "submit")
playlist_mode = getattr(playlist, "feedback_mode", "") or ""
effective_mode = playlist_mode or exercise_mode

context["identMode"] = effective_mode
context["playlistLockMode"] = bool(playlist_mode)  # frontend disables toggle if True
```

---

### 7. Frontend: mode toggle + attempt limits (NEW)

**Files:** `lab/static/js/src/components/music/exercise_sheet.js`

- On load: read `identMode` from exercise context. Set session mode.
- If `playlistLockMode=true` OR `identMode="test"`: hide toggle, mode locked.
- Otherwise: show toggle button `Practice ↔ Submit` with nudge copy:
  `"Switch to Submit mode to earn full mastery credit"`
- Per-slot attempt counter:

```
practice → 3 attempts
submit   → 2 attempts
test     → 1 attempt
```

After limit: popup closes, slot rendered as "unanswered" (neutral). Student moves on.

- Mode sent with POST on submit:
```javascript
data.mode = currentMode;  // "practice" | "submit" | "test"
```

---

## Data Flow

```
generate_exercise_context()
  → identMode = playlist.feedback_mode OR exercise.data["identMode"]
  → playlistLockMode = bool(playlist.feedback_mode)

ExerciseSheet (frontend)
  → reads identMode, sets session mode
  → toggle shown if !playlistLockMode && mode != "test"
  → enforces per-slot attempt limits (3/2/1)
  → sends mode with submission POST

identification_answers_view (backend)
  → saves IdentificationAttempt with mode
  → calls record_attempt(exercise, correct, tested_tags=None)

record_attempt (mastery.py)
  → filters skill_tags to MASTERY_TAGS (canonical only, no duplicates)
  → updates StudentSkillMastery rows (bool history, unchanged thresholds)
```

---

## What Is NOT Changed

| Component | Reason |
|-----------|--------|
| `compute_mastery_level` | Thresholds unchanged — history stays boolean |
| `exercise.data["identMode"]` | Existing field, read-only by new logic |
| Chorale play path | `record_attempt` called with `tested_tags=None` — full exercise tags, canonical-filtered |
| Mastery gating / unlock logic | Out of scope — separate task (seed DAG cross-unit edges) |

---

## Files Changed

| File | Change |
|------|--------|
| `apps/exercises/skill_graph.py` | Add `MASTERY_TAGS` constant |
| `apps/exercises/mastery.py` | `record_attempt` gains `tested_tags`, filters to `MASTERY_TAGS` |
| `apps/exercises/models.py` | `Playlist.feedback_mode`, `IdentificationAttempt.mode` |
| `apps/exercises/admin.py` | Expose `feedback_mode` in PlaylistAdmin |
| `apps/exercises/migrations/XXXX_*` | Two new migrations |
| `lab/views.py` | `generate_exercise_context` sends `identMode` + `playlistLockMode` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Mode toggle UI, attempt limits, send mode with POST |

---

## Deferred

| Item | Reason |
|------|--------|
| Per-problem skill attribution (map each roman numeral slot → canonical tag) | Requires richer problem metadata; canonical filter in `record_attempt` solves the duplicate row problem adequately |
| Mode weight in adaptive ranker | Deferred until ranker built |
| Cross-unit DAG edges (unit:10→unit:9) | Separate task |
