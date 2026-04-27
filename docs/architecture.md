# HarmonyLab Architecture

*Written: 2026-04-09*

This document explains how HarmonyLab actually works — the mental models agents need to make correct changes.

---

## What the App Does

HarmonyLab is a music theory practice platform. Students are presented with staff notation and must either play the correct notes on a MIDI keyboard (or QWERTY keyboard / on-screen piano), or identify what they see by selecting from a multiple-choice list. The app grades each attempt in real time and records performance.

The three core objects are **Exercise**, **Playlist**, and **Course**. Courses are shown to students. Playlists are the unit of assignment. Exercises are the individual problems.

```
Course
  └── Playlists (ordered, M2M via PlaylistCourseOrdered)
        └── Exercises (ordered, M2M via ExercisePlaylistOrdered)
```

---

## Data Model

### Exercise

An `Exercise` is a single problem. Its most important field is `data` — a JSON blob that fully specifies what is notated and how it should be graded.

```json
{
  "type": "matching",
  "key": "jC_",
  "keySignature": "",
  "staffDistribution": "keyboard",
  "introText": "<p>...</p>",
  "reviewText": "",
  "analysis": {
    "enabled": true,
    "tempo": false,
    "mode": { "roman_numerals": true, "chord_labels": false, ... }
  },
  "highlight": { "enabled": false, "mode": { ... } },
  "chord": [
    { "visible": [48, 64, 67, 72], "hidden": [], "rhythmValue": "w" }
  ]
}
```

Other model fields on `Exercise`:
- `id` — human-readable slug like `EA00WI` (auto-assigned, sequential base-36)
- `description` — short optional label
- `rhythm` — space-separated rhythm string like `"w h q"` (overridden per-chord in `data.chord`)
- `time_signature` — string like `"4/4"`
- `authored_by` — the creating teacher/user
- `is_public` — whether other users can include it in their playlists
- `locked` — set to `True` after any student has performed it (prevents editing)
- `tags` — array of strings

**The `chord` array is the exercise content.** Each entry is one chord the student must play, in order. `visible` = notes shown on staff; `hidden` = notes student must supply; `rhythmValue` = duration (`w` whole, `h` half, `q` quarter).

### Exercise Types

The `type` field determines the grading logic:

| Type | `visible` | `hidden` | What student does |
|---|---|---|---|
| `matching` | all notes | `[]` | Play what you see |
| `analytical` | `[]` | all notes | Notes hidden; roman numeral overlay shown — identify by ear |
| `figured_bass` | bass note only | upper voices | Bass shown; student fills in upper voices from figures |
| `identification` | all notes | `[]` | See notes, pick the answer from a multiple-choice list |
| `chorale` | (see below) | — | Play a Bach chorale segment, onset by onset |

For `identification`, each chord dict also has `"answer"` and `"choices"` keys.

For `chorale`, the `data` dict contains a `"score"` key with a CIR (Canonical Internal Representation) JSON object instead of a `"chord"` array. See `claude.md` and `docs/chorale_exercises_plan.md` for the full chorale system.

### Key Format

Keys are encoded as a 4-character string: `jC_` = C major, `iA_` = A minor.

- First char: `j` = major, `i` = minor
- Next chars: note name with accidental (`C`, `G`, `F#`, `Bb`, `Eb`, etc.)
- Trailing `_` = natural (no accidental in the name)

Full mapping:
```
jC_ jG_ jD_ jA_ jE_ jB_ jF# jDb jAb jEb jBb jF_
iA_ iE_ iB_ iF# iC# iG# iD_ iG_ iC_ iF_ iBb iEb
```

The key affects note spelling via `keyMap` in `lab/static/js/src/config/general.js` — enharmonic spelling (e.g. F# vs Gb) depends on the key. **MIDI note numbers are absolute pitch-class; the `key` field controls how they are spelled on the staff.** This is why being in the wrong key causes notes to appear with wrong accidentals (G## instead of A).

### Staff Distribution

`staffDistribution` controls the staff layout:

| Value | Layout |
|---|---|
| `keyboard` | Grand staff (treble + bass), standard keyboard split |
| `keyboardPlusLHBias` | Grand staff, bass dominant (e.g. ROTO exercises) |
| `keyboardPlusRHBias` | Grand staff, treble dominant |
| `RH` | Treble staff only |
| `LH` | Bass staff only |
| `grandStaff` | Grand staff, no keyboard |
| `chorale` | SATB chorale layout (S+A treble, T+B bass) |

### Playlist

A `Playlist` is an ordered sequence of exercises. Key fields:
- `exercises` — M2M to `Exercise` via `ExercisePlaylistOrdered` (has an `order` field)
- `transpose_requests` — list of key signature strings (e.g. `["C", "G", "D"]`)
- `transposition_type` — `"Exercise Loop"` or `"Playlist Loop"` (or null = no transposition)
- `is_auto` — True if auto-generated when exercises were saved (not manually curated)
- `is_adaptive` — If True, exercises in the playlist are served via the Mastery Engine ranking algorithm rather than in sequential order.
- `is_adaptive_entry` — (on ExercisePlaylistOrdered) if True, this exercise is an entry point for students with no prior mastery in an adaptive playlist.

**Transposition** is the primary mechanism for presenting the same exercise in multiple keys without duplicating Exercise objects. If a playlist has 3 exercises and `transpose_requests: ["C", "G", "D"]` with `transposition_type: "Exercise Loop"`, the playlist virtually expands to 9 exercises: A+C, A+G, A+D, B+C, B+G, B+D, C+C, C+G, C+D. Transposed exercises get dynamically generated IDs like `EA00DD+16`.

### Course

A `Course` is an ordered collection of playlists assigned to students. Key fields:
- `playlists` — M2M to `Playlist` via `PlaylistCourseOrdered`
- `open` — if True, visible to all the teacher's student connections; if False, only to specified groups
- `timely_credit / tardy_credit / late_credit / tardy_threshold` — due-date grading weights
- `authored_by` — the teacher who owns the course
- `adaptive_mode` — Choice toggle to enable adaptive logic for all playlists in the course.
- `mastery_threshold` — (familiar, proficient, mastered) Defines the competency level required to "close" a skill in this course.

---

## How Exercises Are Served (Request Flow)

```
Student hits URL
  ↓
  ↓
Django view (lab/views.py: PlaylistView / ExerciseView / CourseView)
  ↓
[If Adaptive] get_next_exercise() (apps/exercises/mastery.py)
  - Rank pool by: lowest_mastery_level -> complexity -> random
  - Apply session-stable seed for consistency
  - Fetch target_key for transposition variety
  ↓
generate_exercise_context() assembles:
  - exercise.data (all the music content)
  - navigation: nextExercise, previousExercise, exerciseList
  - playlistName, courseId, exerciseNum
  - exerciseIsPerformed, exerciseErrorCount (from PerformanceData)
  ↓
RequirejsContext.set_module_params("app/components/app/exercise", context)
  ↓
Django renders exercise.html template
  ↓
Browser loads RequireJS → main.js → app/components/app/exercise AMD module
  ↓
JS reads exercise data via module.config() (injected by Django as requirejs.config JSON)
  ↓
ExerciseDefinition parses data → ExerciseContext manages state
  ↓
ExerciseSheetComponent renders VexFlow notation on <canvas id="staff">
  ↓
MIDI/keyboard input → grader (ExerciseGrader / ChoraleGrader / IdentificationGrader)
  ↓
Performance data POSTed to submit_exercise_performance view → PerformanceData saved
```

The JS app never makes its own Django API calls to load exercise data — everything is injected into the page as inline JSON at render time via `module.config()`.

---

## Frontend Architecture

The frontend uses RequireJS (AMD modules). There is no bundler in dev mode — each module loads individually. An optional build at `data/requirejs/build.json` can point to a compiled bundle.

**Boot sequence:**
1. Django injects `requirejs.config(...)` into the page (paths, shims, module params)
2. `main.js` reads `module.config().app_module` and requires it
3. The app module (e.g. `app/components/app/exercise`) wires together components

**Key JS files:**
- `lab/static/js/src/main.js` — RequireJS bootstrap
- `lab/static/js/src/components/app/exercise.js` — exercise app (wires piano + sheet + grader)
- `lab/static/js/src/models/exercise_definition.js` — parses exercise data JSON
- `lab/static/js/src/models/exercise_context.js` — manages state (current chord, score)
- `lab/static/js/src/components/music/exercise_sheet.js` — renders VexFlow canvas
- `lab/static/js/src/models/exercise_grader.js` — grading for matching/analytical/figured_bass
- `lab/static/js/src/models/chorale_grader.js` — grading for chorales
- `lab/static/js/src/models/identification_grader.js` — grading for identification

**Adding a new AMD module:** add a `paths` entry in `harmony/settings/requirejs.py`. Never move files without updating that file.

---

## Grading

### Standard Exercises (matching / analytical / figured_bass)

`ExerciseGrader` compares the set of MIDI notes currently held against the expected chord's `visible + hidden` notes. The student advances to the next chord when all expected notes are held simultaneously.

### Identification Exercises

`IdentificationGrader` waits for the student to click a multiple-choice answer button rather than playing notes. The `answer` and `choices` fields on each chord dict drive the UI.

### Chorale Exercises

`ChoraleGrader` uses an onset-based window system — the score is parsed into time-ordered groups of notes, and the student must play each group in sequence. See `claude.md` for the full algorithm.

---

## Performance Data

`PerformanceData` records are keyed to `(user, playlist, course)`. Each record has a `data` JSON array — one entry per exercise attempted, with `id`, `error_tally`, `tempo_rating`, and other metrics. The gradebook views in `apps/exercises/views.py` and the dashboard read from these records.

---

## Student Progress Semantics

Student unit pages intentionally use two different meanings of "progress":

- **Mastery progress**: high-meaning skill state used in top segmented bars
- **Practice progress**: lane completion / fluency-building used in per-lane rows

These are not interchangeable.

### Mastery progress

Top segments should represent durable skill state such as:

- `not_started`
- `attempted`
- `proficient`
- `mastered`

In scaffolded curricula, `proficient` should require success on sufficiently
advanced lane content, not merely success on the easiest opening exercises.
`mastered` is reserved for mixed confirmation, typically via a mastery
challenge built from the hardest tier of the unit.

### Practice progress

Per-lane rows should continue to show:

- `done / total`
- mini progress bars
- recent score information

These rows exist to show volume of recommended practice and fluency-building.
They may use richer intermediate color bands than the top mastery bar so that
students see visible movement inside long practice lanes.

In practice, prefer a small number of clearly distinguishable row-color bands
plus a granular mini-progress bar, rather than a large number of subtly
different background colors.

### Why the distinction exists

Music pedagogy needs both:

- clear evidence that the student understands the skill
- visible encouragement that repeated practice is still meaningful after basic
  competence is established

Therefore, a student may be `proficient` or even `mastered` while still having
recommended lane work remaining.

### Challenge metadata belongs to the lane, not UMTO

When a unit defines a mastery challenge, whether a given exercise is
challenge-eligible should be determined by the curricular sequencing layer
(playlist / lane placement metadata), not by the canonical UMTO payload.

Reason:

- UMTO defines what the exercise *is*
- challenge eligibility defines how that exercise is *used in a specific lane*

This keeps exercise representation canonical while allowing different units or
curricular contexts to reuse the same exercise differently.

---

## Non-Obvious Patterns

**Exercise keys are baked in.** An Exercise object has a specific `key` in its `data`. The key controls both note spelling on the staff and the analytical overlay (Roman numerals, figured bass). You cannot display the same Exercise in a different key without either transposing it or generating a new Exercise.

**Multi-key content via playlist transposition.** One Exercise can be presented in multiple keys by adding `transpose_requests` to the playlist. Transposed copies get virtual IDs and are generated on the fly — no duplicate Exercise rows.

**Auto-playlists.** Every time a teacher creates an exercise through the editor, `Exercise.set_auto_playlist()` adds it to an auto-generated playlist (`is_auto=True`). This is a convenience feature so newly-created exercises are immediately playable. Auto-playlists are created per session (within the last 8 hours).

**`locked` prevents editing.** Once `PerformanceData` exists for an exercise, it is locked. This prevents teachers from changing an exercise that students have already answered (which would invalidate their scores).

**RequireJS paths are the source of truth for the frontend.** If a JS file moves, update `harmony/settings/requirejs.py` or the module will 404 silently.

**`keySignature` vs `key`.** `key` is the HarmonyLab key string (`jC_`). `keySignature` is the staff key signature string used by VexFlow (empty string for C major, `"F"` for one flat, etc.). Both are typically set; `keySignature` can be derived from `key` but they are stored separately.

---

## Mastery & Adaptive System

For a deep dive into the pedagogical algorithms, see [Adaptive Learning Guide](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/docs/adaptive_learning.md).

### Skill Graph (`apps/exercises/skill_graph.py`)
Defines the `ALL_SKILL_TAGS` taxonomy and the `DEFAULT_PREREQUISITES` DAG. This module is pure Python and acts as the source of truth for the curriculum structure.

### Mastery Engine (`apps/exercises/mastery.py`)
Computes current student competency based on `PerformanceData` and `StudentSkillMastery` records. 
- **Decay Logic**: Skills lose "freshness" over time based on an exponential decay formula (halflife).
- **Adaptive Selection**: `get_next_exercise` finds the "edge of knowledge" for a user by identifying the weakest unlocked skill that hasn't reached the `mastery_threshold`.

### Visual Skill Map
A Cytoscape.js directed-acyclic-graph implementation that renders the Knowledge Graph for students.
- **Backend**: `get_skill_map_elements` formats nodes/edges with live mastery color-coding.
- **Frontend**: `lab/static/js/src/components/skill_map.js` manages the interactive graph rendering.
