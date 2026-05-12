# Unit 2: Add Barlines Exercise — Design

**Date:** 2026-05-12
**Status:** Design — ready for implementation planning
**Author:** avnerdorman
**Supersedes:** `2026-05-11-unit2-add-barlines-exploration.md` (exploration doc retained for context)

---

## Summary

A new interactive exercise type for Unit 2 (Rhythm & Meter). Student sees a notated passage with no barlines and must place them correctly using a keyboard-navigable beat cursor. Implemented as a QA player module first (Phase 1), with a defined migration path to a first-class UMTO exercise type (Phase 2).

---

## Pedagogical Model

Strongest possible test of meter internalization. MC symbolic questions (Phase 1 of Unit 2) test whether students can decode a time signature. Add-barlines tests whether students can feel the meter in actual notation — they must group beats from note durations alone.

**Difficulty axis:** time signature hidden (hard) → time signature shown (easy). Both modes are configurable per exercise, enabling easy-to-hard sequencing.

**Phase 2 extension:** division-level cursor (between division pulses rather than beats) for compound meter deepening.

---

## Scope

**In scope (Phase 1):**
- Simple meters: 2/4, 3/4, 4/4
- Compound meters: 6/8, 9/8, 12/8
- 2–4 measures per exercise, variable
- Rhythm-only passages (all notes on one pitch) OR real-pitch passages from Kern corpus — configurable per exercise
- Time signature shown or hidden — configurable per exercise
- Practice mode (retry with feedback) and test mode (reveal after submission)

**Out of scope (Phase 1):**
- Irregular meters (5/8, 7/8, 10/8)
- Common time C / cut time
- Beaming repair
- Division-level cursor
- Full UMTO integration + mastery tracking (Phase 2)
- Multi-voice or piano-grand-staff passages

---

## Interaction Model

### What the student sees

- Single-voice passage rendered in VexFlow on a treble or bass staff
- Time signature: shown or hidden depending on exercise configuration
- No barlines shown initially (opening and closing barlines only)
- Beat cursor: rectangular highlight over the current beat + dashed vertical line at its left edge
- Any placed barlines shown as solid vertical lines
- Beat pips at bottom of card (one per beat, labeled 1–N; active pip highlights current cursor gap; pips with placed barlines show a barline indicator on their right edge)

### Navigation and placement

| Input | Action |
|---|---|
| ← / → arrow keys | Move cursor one beat left / right |
| On-screen ← → buttons | Same (for mouse and touch) |
| Swipe left / right (mobile) | Same |
| Enter or Space | Toggle barline at cursor position |
| On-screen "Place / Remove" button | Same |
| Submit button | Grade the answer |

Barlines are toggled: placing where one exists removes it. Student can freely revise before submitting.

### Cursor position rule

Cursor navigates the **gaps between beats** — the `beat_count - 1` potential barline slots. Cursor position `i` (0-indexed) represents the gap between beat `i` and beat `i+1`. The cursor highlights beat `i`'s notes and shows a dashed barline at the right edge of that beat. Cursor range: `0` to `beat_count - 2` inclusive. Opening and closing barlines are fixed and not navigable.

### Feedback on submission

**Practice mode:**
- Incorrect positions highlighted red
- Missing positions highlighted amber
- Correct positions highlighted green
- Student can revise and resubmit

**Test mode:**
- One submission only
- Correct barlines revealed after submission
- Score recorded

---

## Implementation Architecture: Phase 1 (QA Player Module)

### Why QA player first

This is a new interaction type with no precedent in the stack. Validating the interaction with real students before wiring into core infrastructure reduces risk. The data format is UMTO-compatible from day one so Phase 2 migration has zero throwaway cost.

### Components

#### 1. Exercise data format (`unit2_add_barlines`)

```json
{
  "family": "unit2_add_barlines",
  "time_signature": "3/4",
  "show_time_signature": false,
  "clef": "treble",
  "measures": 3,
  "pitch_mode": "rhythm_only",
  "notes": [
    { "pitch": "B4", "duration": "q", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 0 },
    { "pitch": "B4", "duration": "h", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 1 },
    { "pitch": "B4", "duration": "8", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 0 },
    { "pitch": "B4", "duration": "q", "dots": 0 }
  ],
  "correct_barline_positions": [2, 5],
  "beat_count": 9,
  "source": "Essen Folk Song Collection, no. 42",
  "tags": ["unit:2", "unit:2_meter_simple", "unit:2_meter_triple"]
}
```

**Field rules:**
- `correct_barline_positions`: 0-indexed beat indices **after which** a barline falls. Never includes 0 (before beat 0) or `beat_count - 1` (after last beat).
- `pitch_mode`: `"rhythm_only"` (all notes use a fixed pitch, e.g. B4) or `"melodic"` (real pitches from corpus).
- `show_time_signature`: controls whether VexFlow renders the time signature glyph.
- `beat_count`: derived from notes + time_signature; stored for runtime convenience.
- `measures`: must equal `len(correct_barline_positions) + 1`.
- `pitch` field always present (B4 for rhythm-only); VexFlow requires pitch to render noteheads.

#### 2. Beat structure computation (Python, import time)

Given `time_signature` and `notes`, compute:
- Total duration in beats
- Beat onset index for each note (which beat does this note start on?)
- `correct_barline_positions` (after every `beats_per_measure`-th beat)
- `beat_count`

Use `music21` for duration arithmetic. Validate that total duration equals `measures × beats_per_measure` before writing the exercise.

#### 3. VexFlow renderer (JS, inside QA player)

New rendering path in `qa_player.js` (or a companion module `barline_player.js`) activated when `problem.family === "unit2_add_barlines"`.

Steps:
1. Create VexFlow `Stave` with or without time signature glyph per `show_time_signature`.
2. Suppress measure barlines — render entire passage as one long stave.
3. Render notes using `StaveNote` with `pitch` and `duration` from exercise data.
4. After `Formatter.format()` and `draw()`, read `note.getAbsoluteX()` for each note whose beat onset is a beat boundary. Store as `beatX[]` array.
5. Add opening and closing barlines only.

#### 4. Beat cursor (JS)

State: integer `cursorPos` (0 to `beat_count - 2`), `Set<int> placedAt`.

Cursor rendering:
- Overlay `<div>` positioned absolutely over the VexFlow canvas
- Left edge: `beatX[cursorPos]` (pixel value from VexFlow, scaled to container)
- Width: `beatX[cursorPos + 1] - beatX[cursorPos]` (or to closing barline for last beat)
- Highlight box: semi-transparent blue fill, dashed border
- Dashed vline: solid blue, 2px, at left edge of box

On window resize: re-read `beatX[]` from VexFlow and reposition overlay.

#### 5. Grader (JS)

```javascript
function grade(placedAt, correctSet) {
  const missing = [...correctSet].filter(i => !placedAt.has(i));
  const extra   = [...placedAt].filter(i => !correctSet.has(i));
  return { correct: missing.length === 0 && extra.length === 0, missing, extra };
}
```

Practice mode: return `missing` and `extra` arrays for per-beat visual feedback.
Test mode: return `correct` boolean only, then reveal correct positions.

#### 6. Django import command

```bash
python manage.py import_barline_exercises \
  --source essen \
  --meter 3/4 \
  --measures 3 \
  --pitch-mode rhythm_only \
  --count 20 \
  --author admin@example.com
```

Sources:
- `essen`: Essen Folk Song Collection (via music21 corpus or local Kern files)
- `kern`: arbitrary Kern file path
- `manual`: read from a hand-authored JSON file

Command validates each generated exercise (total duration, barline count, note count) before saving.

---

## Corpus / Repertoire

### Primary: Essen Folk Song Collection

- Thousands of short monophonic folk melodies in music21's built-in corpus
- Public domain
- Simple and compound meters naturally represented
- Short phrases (4–8 beats) easily extractable
- Access via `music21.corpus.search('essenFolksong')`

### Secondary: Chopin mazurkas / other Kern scores

- Good for 3/4 specifically
- More rhythmically interesting
- Access via `music21.converter.parse('path/to/file.krn')`
- Use as supplement for triple meter

### Rhythm-only exercises (no corpus needed)

Hand-authored or algorithmically generated note sequences. Useful for early exercises where pitch is a distraction.

---

## Data Storage

Phase 1: exercises stored as UMTO `Exercise` rows with `mode=InteractionMode.IDENTIFICATION` (closest existing mode) and `family` field in the UMTO data distinguishing them. The `family: "unit2_add_barlines"` key in `data` is the runtime discriminator.

Phase 2: add `InteractionMode.BARLINE_PLACEMENT` to UMTO schema and migrate.

---

## File Map

| File | Role |
|---|---|
| `lab/static/js/src/qa_player.js` | Extend to detect `unit2_add_barlines` family and delegate to barline renderer |
| `lab/static/js/src/barline_player.js` | New module: VexFlow rendering + cursor + grader for barline exercises |
| `harmony/settings/requirejs.py` | Add `barline_player` path entry |
| `apps/exercises/management/commands/import_barline_exercises.py` | New import command |
| `apps/exercises/utils/barline_exercise_builder.py` | Beat structure computation, exercise JSON generation, validation |
| `apps/exercises/tests/test_barline_exercise_builder.py` | Unit tests for builder |

---

## Key Technical Risks

| Risk | Mitigation |
|---|---|
| VexFlow `getAbsoluteX()` unreliable after single-stave render | Spike: render one unbarred passage, log note x-coords, verify they match visual positions |
| Cursor overlay misaligns on resize | Re-read x-coords on `ResizeObserver` callback; use `%`-based positioning as fallback |
| music21 Essen corpus parse failures | Wrap each parse in try/except, skip and log failures; validate beat totals before saving |
| QA player surgery breaks existing MC exercises | Isolate barline path behind `if (family === 'unit2_add_barlines')` guard; no shared state |

---

## Recommended Spike (Before Full Build)

1-day spike before committing to full build:
1. Render one unbarred 3/4 passage (9 quarter notes) in VexFlow inside qa_player.js
2. Log `note.getAbsoluteX()` for each note
3. Position a cursor overlay div using those values
4. Move it left/right with arrow keys
5. Confirm overlay tracks notes correctly on resize

If spike works cleanly → proceed to full build.
If VexFlow x-coord access is unreliable → reassess (fallback: compute beat widths from stave width ÷ beat count).

---

## Effort Estimate

| Work item | Effort |
|---|---|
| VexFlow unbarred rendering (suppress time sig + barlines) | Medium |
| Beat-cursor overlay (DOM positioned from note x-coords) | Low-medium |
| Keyboard + on-screen arrow navigation | Low |
| Mobile swipe | Low |
| Grader (set-equality, practice + test mode feedback) | Low |
| Essen corpus import pipeline + builder | Medium |
| QA player extension (family dispatch) | Low |
| `barline_player.js` module | Medium |
| Django import command | Low |
| Tests (builder + grader) | Low-medium |

**Total: ~2–3 weeks solo.**

---

## Phase 2: UMTO Promotion (Deferred)

After student validation:
1. Add `InteractionMode.BARLINE_PLACEMENT` to `apps/exercises/umto.py`
2. Add barline placement schema to `apps/exercises/umto_schema.json`
3. Wire into `exercise_definition.js`, `exercise_context.js`, `exercise_sheet.js`
4. Full mastery/progress tracking
5. Migrate existing `unit2_add_barlines` exercises to new mode

Data format designed above is forward-compatible — no field changes needed for migration.

---

## Open Questions (Resolved at Design Time)

| Question | Decision |
|---|---|
| Time signature shown or hidden? | Both — `show_time_signature` field, configurable per exercise |
| Pitch or rhythm-only? | Both — `pitch_mode` field, configurable per exercise |
| How many measures? | 2–4, variable, set per exercise |
| Feedback on wrong answer? | Practice = retry with visual feedback; Test = reveal after one submission |
| Architecture? | Hybrid: QA player first, UMTO migration when validated |
