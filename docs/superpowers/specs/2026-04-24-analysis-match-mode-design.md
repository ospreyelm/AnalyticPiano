# Analysis Match Mode — Design Spec

**Date:** 2026-04-24  
**Branch:** feature/music21_builder  
**Status:** Approved

---

## Overview

Unit 1 has three exercise lanes per note window:

| Lane | Mode | Student sees | Student does |
|------|------|-------------|--------------|
| exact | `playback` | Notehead visible | Plays the note |
| identification | `identification` | `?` slot | Clicks correct label |
| analysis | `analysis_match` | Label visible, notehead invisible | Plays the note matching the label |

Analysis match is the inverse of identification: the label is given, the student must produce the pitch. Octave does not matter — any octave of the correct pitch class is accepted.

---

## Bugs Being Fixed

### Bug 1: `analysis_types` undefined in grader

**File:** `lab/static/js/src/models/exercise_grader.js:96-113`

`analysis_types` is set inside a block guarded by `["analytical", "analytical_pcs", "figured_bass", "figured_bass_pcs"].includes(type)`. When `umto_chorale` + `analysis_match` reaches line 132, `analysis_types` is `undefined`. The `analysisBool` loop at line 312 never runs, returns `true`, and every note is accepted as correct.

**Fix:** Hoist `analysis_types` derivation above the type guard so all exercise types can access it.

### Bug 2: No pitch-class comparison

`analysisMatch` calls `analysisBool` which compares `to_note_name([midi])` on expected vs delivered. This requires exact MIDI match. Unit 1 requires octave-agnostic matching.

**Fix:** New `pitchClassMatch()` method that compares `midi % 12` pitch classes.

### Bug 3: Wrong problem builder for `analysis_match`

`exercise_definition.js` falls through to `buildUMTOIdentificationProblems()` for `analysis_match` mode. That builder constructs ident-style problems (for clicking). Analysis match needs a different problem structure.

**Fix:** New `buildUMTOAnalysisMatchProblems()` builder, wired into the `parse()` switch.

---

## Architecture

### Problem Structure

`buildUMTOAnalysisMatchProblems(exercise)` in `exercise_definition.js`:

```javascript
{
  windowIndex: idx,
  onset: slice.offset,
  answer: "G",           // note name label shown to student
  midi: 55,              // expected MIDI (pitch class = midi % 12)
  notes: [],             // empty — no noteheads in chord bank
  visible: [],
  hidden: false,         // non-target slices: hidden: true
}
```

Source of `answer`: same as ident path — `gradingMatch.target_midi_pitches[0]` → `analyzer.to_note_name([midi])`. Non-target grading slices (empty `target_midi_pitches`) → `hidden: true`.

### Grader: `pitchClassMatch(expected, delivered)`

New method in `exercise_grader.js`:

```javascript
pitchClassMatch: function(expected, delivered) {
  // expected, delivered = arrays of MIDI integers
  // Returns {state, count, note, notes}
  
  if (!delivered || delivered.length < 1) → PARTIAL
  
  var expectedPCs = expected.map(m => m % 12);
  // For each delivered note:
  //   correct if its pitch class (m % 12) is in expectedPCs
  //   incorrect otherwise
  // state = INCORRECT if any wrong PC
  // state = PARTIAL if correct PCs but delivered.length < expected.length
  // state = CORRECT if all expected PCs matched and delivered.length >= expected.length
}
```

Routing in `grade()`:
```javascript
case "umto_chorale":
  if (mode === "analysis_match") {
    result = this.pitchClassMatch(expected_notes, actual_notes);
  } else { ... }
```

### Rendering: Invisible Noteheads

**File:** `lab/static/js/src/components/music/rendering/vexflow_adapter.js`

When `isAnalysisMatch()` is true:
- Unplayed noteheads render with fill color = `"white"` (or page background) → invisible
- Unplayed stems render with stroke color = `"white"` → invisible  
- Unplayed beams render with fill/stroke = `"white"` → invisible
- Played noteheads (in `playedNoteIds`) render normally (black)

The existing unplayed-note coloring path already branches on `playedNoteIds`. Add an `isAnalysisMatch` branch that substitutes white for the normal gray.

**Note name labels:** Already rendered by the `note_names` analysis overlay. The UMTO parse path sets `exercise.analysis.mode.note_names = true` when `analysisType === "note_name"`. No change needed here.

**Advancement:** Sequential window-by-window. `isChorale()` currently returns `true` for `analysis_match`, which causes `ExerciseGrader.grade()` to early-return `PARTIAL` at line 69 (the `isChorale()` branch fires before problems are checked). This must be fixed: `isChorale()` should return `false` for `analysis_match`, OR the early-return guard must be tightened to exclude `analysis_match`. Simplest fix: change `isChorale()` to exclude `analysis_match`, and add `isAnalysisMatch()` as a distinct branch in `exercise_context.grade()` that calls `this.grader.grade()` normally. The context then advances via `inputChords.goTo(graded.activeIndex)` — standard chord-bank flow.

---

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_definition.js` | Add `buildUMTOAnalysisMatchProblems()`, wire into `parse()` for `umto_chorale` + `analysis_match`; fix `isChorale()` to exclude `analysis_match` |
| `lab/static/js/src/models/exercise_grader.js` | Hoist `analysis_types`, add `pitchClassMatch()`, route `umto_chorale analysis_match` to it; fix early-return guard |
| `lab/static/js/src/models/exercise_context.js` | Add `isAnalysisMatch()` check so `grade()` routes correctly |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | Render unplayed noteheads/stems/beams white when `isAnalysisMatch()` |

No Python changes. No new exercise types. No schema changes.

---

## Data Flow

```
UMTO exercise (mode: analysis_match, analysisType: note_name)
    ↓
parse() → buildUMTOAnalysisMatchProblems()
    → problems[i] = { answer: "G", midi: 55, notes: [], hidden: false }
    ↓
VexFlow adapter renders score
    → note_names overlay shows "G", "Bb", etc. at each window
    → noteheads/stems/beams rendered white (invisible)
    ↓
Student plays MIDI note
    ↓
ExerciseGrader.grade() → pitchClassMatch(expected=[55], delivered=[67])
    → 67 % 12 === 55 % 12 (both = 7 = G) → CORRECT
    ↓
ExerciseContext advances window
VexFlow re-renders → notehead turns black
```

---

## Edge Cases

**Enharmonic equivalents:** `G#` and `Ab` share pitch class 8. Both accepted if either is the target. This is correct for Unit 1 (enharmonic reading is a listed skill tag).

**Multi-note windows:** Unit 1 exercises are single-voice, so each window has exactly one target note. `pitchClassMatch` handles multi-note arrays anyway for future use.

**Non-target slices:** Grading slices with `target_midi_pitches: []` → problem `hidden: true` → skipped by grader and renderer.

---

## What Is Not Changed

- Exact (playback) mode — unchanged
- Identification mode — unchanged  
- `isChorale()` return value — `analysis_match` already returns `true`, stays that way
- Python UMTO model, `InteractionMode`, factory — no changes
- `generate_unit1.py` — already emits `mode=InteractionMode.ANALYSIS_MATCH`, no changes needed
