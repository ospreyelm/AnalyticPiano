# Chorale Identification Exercise Type — Design Spec

_Date: 2026-04-10_
_Status: Approved_

---

## Overview

A new exercise type, `chorale_identification`, that shows students a full SATB chorale score (all voices visible) and asks them to label each onset window with a Roman numeral, figured bass symbol, or other analysis label. Students click a `?` slot below the staff and choose from a popup of 5 options. Grading uses the existing `IdentificationGrader` and supports all three feedback modes (`submit`, `practice`, `test`).

This is distinct from the existing `chorale` (play-through) type and the existing `identification` (isolated chord) type. It combines the chorale renderer with the identification UX.

---

## Data Format

```json
{
  "type": "chorale_identification",
  "identMode": "submit",
  "analysisType": "roman",
  "score": {
    "meta": { "key": "G", "time": "4/4" },
    "measures": [ ... ]
  },
  "key": "jG_",
  "staffDistribution": "chorale",
  "introText": "Label the Roman numerals for BWV1.6, measures 1–4.",
  "reviewText": "Well done! You labeled all chords correctly."
}
```

Note: `problems` (with `answer` and `choices`) is **not stored in the DB**. It is computed client-side by `ExerciseDefinition.parse()` at load time from the `score` data and `analysisType`. See the Analysis Computation section below.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"chorale_identification"` |
| `identMode` | string | `"submit"` \| `"practice"` \| `"test"` (default: `"submit"`) |
| `analysisType` | string | `"roman"` \| `"figured_bass"` \| `"interval"` \| `"note_name"` \| `"pc_set"` — controls what is labeled. Phase 1: `roman` and `figured_bass` only. |
| `score` | object | CIR score — same format as `chorale` type |
| `problems` | array | One entry per onset window (see below) |
| `key` | string | HarmonyLab key format (e.g. `"jG_"`) |
| `staffDistribution` | string | Always `"chorale"` |

### Per-problem fields (computed at load time by parse(), not stored in DB)

| Field | Type | Description |
|-------|------|-------------|
| `windowIndex` | int | Index into the onset window sequence |
| `onset` | int | Tick position of this window |
| `answer` | string | The correct label — computed from MIDI pitches via `Analyze.to_chord()` |
| `choices` | string[] | 5 options shown in popup — correct answer + 4 distractors sampled from other windows, shuffled |

### `analysisType` values (Phase 1 only)

- `roman` — Roman numeral labels drawn from CIR annotation data (e.g. `"I"`, `"V7"`, `"ii°"`)
- `figured_bass` — Figured bass symbols drawn from CIR annotation data (e.g. `"6"`, `"6/4"`, `"7"`)

Future types (`interval`, `note_name`, `pc_set`) are reserved — the format supports them but import does not generate them yet.

---

## Analysis Computation

The CIR JSON files contain **no analysis annotations** — only pitch and duration data. Roman numerals and figured bass must be computed from the MIDI pitches of each onset window.

The existing analysis logic lives entirely in JavaScript (`lab/static/js/src/utils/analyze.js`, `Analyze.to_chord()`). There is no Python equivalent.

**Resolution: compute answers client-side at exercise load time.**

`ExerciseDefinition.parse()` for `chorale_identification`:
1. Builds the onset window sequence from the score (same logic as `ScoreTimeline`, ported inline or via a shared helper).
2. For each window, collects the MIDI pitches of all sounding notes.
3. Calls `Analyze.to_chord(midi_array)` to get the Roman numeral / figured bass label.
4. Samples 4 distractors from other windows' labels in the excerpt (all choices are real labels from the piece). Shuffles + includes the correct answer = 5 choices total.
5. Populates `exercise.problems` in place before the exercise starts.

This means the `problems` array in the DB record stores only `windowIndex` and `onset` — **not** `answer` or `choices`. Those are computed fresh at load time from the score data and the key. This is acceptable: the score is already in the DB record, computation is fast, and it avoids duplicating analysis logic in Python.

```json
// Stored in DB — no answers or choices:
"problems": [
  { "windowIndex": 0, "onset": 0 },
  { "windowIndex": 1, "onset": 1024 }
]
```

```json
// After parse() runs client-side — fully populated:
"problems": [
  { "windowIndex": 0, "onset": 0,    "answer": "I",  "choices": ["I", "ii", "IV", "V", "vi"] },
  { "windowIndex": 1, "onset": 1024, "answer": "V",  "choices": ["I", "ii", "IV", "V", "vi"] }
]
```

Alternatively, the import command can omit `problems` entirely and let `parse()` build the full array from scratch using just the `score` and `analysisType`.

---

## Creation Flows

### Flow A — Import from file

`import_chorale.py` gains a `--mode` argument (default: `play`) and an `--analysis` argument:

```bash
python manage.py import_chorale bwv1.6.json \
  --author=admin@example.com \
  --start=0 --end=4 \
  --mode identify \
  --analysis roman \
  --public
```

When `--mode identify`:
1. Loads CIR JSON and extracts the excerpt (same as play-through).
2. Writes a `chorale_identification` exercise record with `score`, `analysisType`, and `identMode`.
3. Does **not** pre-compute `problems` — `parse()` builds them client-side at load time.

### Flow B — Duplicate from existing chorale

A management command converts an existing `chorale` exercise into a new `chorale_identification` record:

```bash
python manage.py duplicate_chorale_as_identification <exercise_id> \
  --author=admin@example.com \
  --analysis roman
```

- Reads `score` and `meta` from the existing `chorale` record — no file access required.
- Saves a new `chorale_identification` exercise record with `score` and `analysisType`.
- The `problems` array is built client-side by `parse()` at load time.
- The original `chorale` record is unchanged.

This is the primary creation path once chorales are already in the DB.

**Future:** A "Duplicate as identification" button in the exercise audit view (2.19) will call this same logic via an API endpoint. Deferred to 2.19 implementation.

### Flow C — MusicXML import

Deferred. When 2.13 gets its UI, `import_musicxml` will gain a `--mode identify` option using whatever analysis data is embedded in the MusicXML.

---

## Frontend: ExerciseDefinition

### New method

```javascript
isChoraleIdentification: function () {
  return this.exercise.type === "chorale_identification";
}
```

### parse() changes

When `type === "chorale_identification"`:
- Copy `analysisType` through to `exercise.analysisType`.
- Copy `identMode` through (defaulting to `"submit"`).
- Force all analysis overlays off (same logic as `identification`) — label slots replace them.
- Set `staffDistribution` to `"chorale"` if not already set.
- `getScore()`, `getIdentMode()`, `getProblems()` all work without change.

### ExerciseDefinition.TYPES

Add `chorale_identification: "chorale_identification"`.

---

## Frontend: Rendering & UX

### exercise_sheet.js — initComponent()

```javascript
if (definition.isChorale() || definition.isChoraleIdentification()) {
  this.initChoraleMode();   // grand staff renderer, all voices visible, no MIDI grading
}
if (definition.isIdentification() || definition.isChoraleIdentification()) {
  this.initIdentificationMode();  // label slots, popup, submit button
}
```

Both init methods run for `chorale_identification`. The chorale renderer draws all four voices. The identification UX draws `?` slots and handles clicks.

### drawIdentificationLabels() — slot positioning

For the existing `identification` type, slot x-positions come from chord-bank stave columns (`noteStaves`).

For `chorale_identification`, slot x-positions come from onset windows. The chorale renderer already tracks the x-position of each onset column. A mapping `windowIndex → x` is passed into `drawIdentificationLabels()` so it can position labels correctly below the bass staff at each onset.

All other label behaviour is unchanged: `?` placeholder, dark when answered, green ✓ / red ✗ after grading, test/practice/submit mode branching.

### exercise_context.js

`isChoraleIdentification` is treated as `isIdentification` for grading purposes:
- Uses `IdentificationGrader` (not `ChoraleGrader`).
- No chord-bank advancement.
- Correct result → flawless pass → exercise advances.
- Adds to existing `isIdentification` checks rather than duplicating branch logic.

---

## Grader

`IdentificationGrader` is used directly — no subclass, no copy. It grades `problems[i].answer` against `grader.answers[i]` regardless of how the score was rendered.

---

## Admin

The Django admin exercise change form detects `data.type === "chorale_identification"` and shows an **Identification settings** fieldset (same as for `identification`): feedback mode radio (`submit` / `practice` / `test`). Hides irrelevant fields (rhythm, MIDI grading config).

---

## Constraints

- **Do not modify `analyze.js`** — it is a large, shared analysis library used across the entire app. Consume it read-only via `Analyze.to_chord(midiArray)` (initialized with the key signature). No extensions or changes to that file.
- **Do not modify `identification_grader.js`** — it is used directly without subclassing or alteration.
- **Do not modify `score_timeline.js`** — reuse `ScoreTimeline.buildTimeline()` as-is from `exercise_definition.js`.

---

## Out of Scope (Phase 1)

- `interval`, `note_name`, `pc_set` analysis types — format reserved, import not implemented
- "Duplicate as identification" UI button — deferred to 2.19
- MusicXML identification import UI — deferred to 2.13
- Visual distinction between analysis types in label rendering (all use same font/position for now)

---

## Key Files Touched

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_definition.js` | Add `isChoraleIdentification()`, extend `parse()`, add to `TYPES` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Branch `initComponent()`, adjust `drawIdentificationLabels()` slot positioning |
| `lab/static/js/src/models/exercise_context.js` | Add `isChoraleIdentification` alongside identification branches |
| `apps/exercises/management/commands/import_chorale.py` | Add `--mode` and `--analysis` arguments |
| `apps/exercises/management/commands/duplicate_chorale_as_identification.py` | New command |
| `apps/exercises/admin.py` | Detect `chorale_identification`, show identification fieldset |

---

## Data Flow

```
CIR JSON (or existing chorale Exercise record)
    ↓
import_chorale --mode identify  OR  duplicate_chorale_as_identification
    → build onset windows
    → read analysis annotations per window
    → sample distractors from excerpt
    → write problems[] array
    ↓
Exercise.data (Django DB) — type: "chorale_identification"
    ↓  served as JSON to the browser
ExerciseDefinition.parse()
    → isChoraleIdentification() = true
    → getScore(), getProblems(), getIdentMode() all work
    ↓
ExerciseSheet.initComponent()
    → initChoraleMode()          — renders grand staff, all voices
    → initIdentificationMode()   — label slots, popup, feedback
    ↓
Student clicks slot → _showIdentPopup() → IdentificationGrader.setAnswer()
    → practice: grade + render immediately
    → test: render, auto-submit when all answered
    → submit: await Submit button click
    ↓
IdentificationGrader.grade() → {result, score, problems[]}
    → drawIdentificationLabels() → colours + ✓/✗
    → if correct: exerciseContext.grade() → advance
```
