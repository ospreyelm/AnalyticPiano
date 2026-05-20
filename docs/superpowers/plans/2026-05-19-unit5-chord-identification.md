# Unit 5 — Triads & Seventh Chord Identification: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create chord-quality identification exercises for Unit 5 (triads and seventh chords). Students see a single root-position chord on the keyboard staff, choose its quality from a dropdown (e.g. "major", "dominant 7"), and work through a staged curriculum that gradually widens the choice pool.

**Architecture:**
- UMTO-wrapped `identification` type: one exercise per problem (single `chord[]` entry per exercise). Reuses the existing `IdentificationGrader` and identification render path — no new grader.
- New backend factory `save_umto_chord_id_exercise()` in `umto_factory.py`, following the pattern of `save_umto_key_sig_exercise`.
- New management command `generate_unit5.py`: 3 triad stages + 4 seventh chord stages, 12 exercises per stage (round-robin quality × root), one playlist per stage group.
- Frontend: adds an `identification` handler inside the existing UMTO parse block in `exercise_definition.js` — maps `definition.chord[]` → `exercise.problems[]` so the existing render path works for UMTO-wrapped identification exercises.
- Per-chord display key derived via `spelling_key_for_pitches()` (e.g. C minor chord gets `Eb` context, not just `C`).

**Tech Stack:** Python/Django management commands, music21, UMTO/Pydantic, existing `IdentificationGrader`, RequireJS AMD frontend.

> **Retrospective note:** This plan was created after implementation. All completed tasks are marked `- [x]`.

---

## File Map

| Status | Path | Purpose |
|--------|------|---------|
| **Created** | `apps/exercises/management/commands/generate_unit5.py` | 3 triad + 4 seventh stages, 12 exercises each, playlists |
| **Modified** | `apps/exercises/umto_factory.py` | Added `save_umto_chord_id_exercise()` |
| **Modified** | `lab/static/js/src/models/exercise_definition.js` | Added `identification` handler in UMTO parse block |
| **Modified** | `apps/exercises/management/commands/list_exercise_generators.py` | Registered `generate_unit5` in catalog |
| **Modified** | `docs/management_commands.md` | Added Unit 5 section |

---

## Task 1: Backend factory

**Files:**
- Modify: `apps/exercises/umto_factory.py`

Add `save_umto_chord_id_exercise()` after `save_umto_key_sig_exercise`.

- [x] **Step 1: Implement `save_umto_chord_id_exercise`**

Creates a UMTO-wrapped `identification` exercise with a single problem. Key payload fields:
- `type: "identification"`, `isUMTO: True`, `mode: InteractionMode.IDENTIFICATION`
- `clef: "keyboard"`, `staffDistribution: "keyboard"`
- `chord: [{ notes: sorted(midi_notes), answer: answer, choices: choices, rhythmValue: "w" }]`
- `key`: per-chord display key (from `spelling_key_for_pitches()`, not just root key)
- Backfills `exerciseId` after save

Signature:
```python
def save_umto_chord_id_exercise(
    *, description, author, chord_key, midi_notes, answer, choices,
    skill_tags, complexity, is_public=True, overwrite=False
) -> "Exercise":
```

- [x] **Step 2: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('apps/exercises/umto_factory.py').read()); print('OK')"
```

---

## Task 2: Management command

**Files:**
- Create: `apps/exercises/management/commands/generate_unit5.py`

Generates 7 exercise groups (3 triad stages + 4 seventh chord stages). Each stage: 12 exercises, round-robin across `quality × root` pairs. One playlist per stage.

- [x] **Step 1: Define stage data structures**

```python
ALL_ROOTS = [
    ("jC_", "C", 0), ("jG_", "G", 1), ("jF_", "F", 1), ("jD_", "D", 2),
    ("jBb", "Bb", 2), ("jA_", "A", 3), ("jEb", "Eb", 3), ("jE_", "E", 4),
    ("jAb", "Ab", 4), ("jB_", "B", 5), ("jDb", "Db", 5), ("jF#", "F#", 6),
]
TRIAD_STAGES = [
    (1, ["major", "minor"],                          ["major", "minor"],                 3),
    (2, ["major", "minor", "diminished"],            [...],                              5),
    (3, ["major", "minor", "diminished", "augmented"], [...],                           99),
]
SEVENTH_STAGES = [
    (1, ["dominant 7", "major 7"],                          [...], 3),
    (2, ["dominant 7", "major 7", "minor 7"],               [...], 5),
    (3, ["dominant 7", "major 7", "minor 7", "half-dim 7"], [...], 99),
    (4, ["dominant 7", "major 7", "minor 7", "half-dim 7", "diminished 7"], [...], 99),
]
```

- [x] **Step 2: Implement `_chord_notes_and_key()` helper**

Calls `music21_builder._pitches_for_quality()` → `_keyboard_4voice()` → `spelling_key_for_pitches()` to derive MIDI notes and correct enharmonic display key for each quality/root pair.

- [x] **Step 3: Implement `_generate_problems()` helper**

Round-robin over `quality × root` pairs (deterministic, no randomness), capped at `n=12`.

- [x] **Step 4: Implement `Command.handle()` + `_handle_type()` + `_build_playlist()`**

- CLI flags: `--type triads|sevenths|both`, `--author`, `--public`, `--overwrite`
- Skill tags: `["unit:5", "chord_quality", f"unit:5_{chord_type}_stage_{stage_num}"]`
- Playlist tags: `["unit:5", f"unit:5_{chord_type}", f"unit:5_{chord_type}_stage_{stage_num}"]`

- [x] **Step 5: Syntax check**

```bash
python3 -c "import ast; ast.parse(open('apps/exercises/management/commands/generate_unit5.py').read()); print('OK')"
```

---

## Task 3: Frontend — UMTO `identification` handler

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

The UMTO parse block branches on `exercise.type`. Add a handler for `"identification"` so UMTO-wrapped exercises reach the existing identification render/grade path.

- [x] **Step 1: Add `identification` branch in the UMTO parse `if/else if` chain**

Added after the `umto_key_signature` handler:

```javascript
} else if (exercise.type === "identification") {
  exercise.problems = _.map(definition.chord || [], function (chord) {
    var notes = ExerciseDefinition.sortNotes(chord.notes || []);
    return {
      visible: notes.slice(), hidden: [], notes: notes,
      answer: chord.answer || "", choices: chord.choices || [],
      unison_idx: null, rhythm: chord.rhythmValue || "w",
    };
  });
  exercise.mode = "identification";
  exercise.identMode = definition.identMode || "practice";
  exercise.analysisType = definition.analysisType || "chord_quality";
  exercise.inputMode = definition.inputMode || "dropdown";
  exercise.staffDistribution = definition.staffDistribution || "keyboard";
  exercise.analysis = { enabled: false, mode: {} };
}
```

Reuses `IdentificationGrader` unchanged — no new grader code needed.

---

## Task 4: Register in catalog and docs

- [x] **Step 1: Register in `list_exercise_generators.py`**

Added a "Triads and seventh chords (Unit 5)" group to `CATALOG`:
```python
("Triads and seventh chords (Unit 5)", [
    (
        "generate_unit5",
        "Generate Unit 5 chord-quality identification exercises (triads and/or seventh chords, staged choice counts).",
        "python manage.py generate_unit5 --type both --author admin@example.com --public",
    ),
]),
```

- [x] **Step 2: Add to `docs/management_commands.md`**

Added `generate_unit5` entry under "### Triads and seventh chords (Unit 5)".

---

## Task 5: Browser testing (pending)

The `exercise_definition.js` change needs browser verification before PR #44 merges.

- [ ] **Step 1: Generate content against a local DB**

```bash
python manage.py generate_unit5 --type both --author <email> --public
```

- [ ] **Step 2: Golden path — Unit 5 exercise works correctly**

Open a Unit 5 playlist in the student player and verify:
- Chord renders on the keyboard grand staff at the correct pitch
- Correct quality choices appear in the dropdown
- Selecting the right answer marks it green (practice mode); wrong answer marks red
- Exercise advances problem-by-problem, completes playlist item

- [ ] **Step 3: Regression — existing identification exercises unchanged**

- Open a `chorale_identification` exercise: verify paging (4/page), grading, and slide animation work
- Open a static `identification` exercise: verify it still loads and grades correctly

- [ ] **Step 4: Commit fixes if any**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "fix(unit5): browser smoke-test fixes"
```

---

## Verification

```bash
# Syntax check (no Django required)
python3 -c "import ast; ast.parse(open('apps/exercises/management/commands/generate_unit5.py').read()); print('generate_unit5 OK')"
python3 -c "import ast; ast.parse(open('apps/exercises/umto_factory.py').read()); print('umto_factory OK')"

# Catalog
python manage.py list_exercise_generators | grep -A3 "Unit 5"

# Content counts (requires live DB)
python manage.py generate_unit5 --type both --author <email> --public
python manage.py shell -c "
from apps.exercises.models import Exercise, Playlist
print('Unit 5 exercises:', Exercise.objects.filter(skill_tags__contains=['unit:5']).count())  # expect 84 (7 stages × 12)
print('Unit 5 playlists:', Playlist.objects.filter(name__startswith='Unit 5').count())        # expect 7
"
```
