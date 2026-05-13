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
- Rhythm-only passages (all notes on one pitch) OR real-pitch passages from Kern/Humdrum sources, especially the Essen Folk Song Collection via music21 — configurable per exercise
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

This is a new interaction type with no precedent in the stack. Validating the interaction with real students before wiring into core infrastructure reduces risk. The data format is UMTO-adjacent and migration-friendly from day one, so Phase 2 can promote the exercise without replacing the core payload shape.

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
  "pickup_beats": 0,
  "beat_positions_ticks": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  "note_beat_onsets": [0, 1, 2, 3, 5, 6, 7.5, 8],
  "source": "Essen Folk Song Collection, no. 42",
  "tags": ["unit:2", "unit:2_meter_simple", "unit:2_meter_triple"]
}
```

**Field rules:**
- `correct_barline_positions`: 0-indexed cursor-slot indices **after which** a barline falls. Never includes the opening barline before slot 0 or the closing barline after the final slot. For pickup/anacrusis exercises, the pickup boundary is student-placeable and is represented as position `0`.
- `pitch_mode`: `"rhythm_only"` (all notes use a fixed pitch, e.g. B4) or `"melodic"` (real pitches from corpus).
- `show_time_signature`: controls whether VexFlow renders the time signature glyph.
- `beat_count`: integer cursor-slot count derived from notes + time_signature + optional pickup; stored for runtime convenience.
- `measures`: count of full measures after any pickup. Without pickup, `measures == len(correct_barline_positions) + 1`; with pickup, `correct_barline_positions` also includes the pickup boundary at position `0`.
- `pickup_beats`: optional anacrusis length in tactus beats. Must be non-negative and smaller than one full measure.
- `beat_positions_ticks`: integer slot boundaries for cursor rendering; includes shortened pickup slot when present.
- `note_beat_onsets`: note onset positions in tactus beats from passage start.
- `pitch` field always present (B4 for rhythm-only); VexFlow requires pitch to render noteheads.

#### 2. Beat structure computation (Python, import time)

Given `time_signature` and `notes`, compute:
- Total duration in beats
- Beat onset index for each note (which beat does this note start on?)
- `correct_barline_positions` (after every `beats_per_measure`-th beat)
- `beat_count`

Use `music21` for duration arithmetic. Validate that total duration equals `measures × beats_per_measure` before writing the exercise.

**Compound meter beat definition:** For 6/8, 9/8, 12/8, `beat_count` counts **dotted-quarter tactus beats** (not eighth-note pulses). `beats_per_measure` = 2, 3, 4 respectively. Division-level cursor (eighth pulses) is deferred to Phase 2.

**Beat boundary rule:** A beat boundary exists at every dotted-quarter (compound) or quarter (simple) offset from the start of the passage. If the passage has a pickup/anacrusis, the pickup is represented as one initial shortened cursor slot, followed by full-measure tactus slots. If no note begins exactly on a beat boundary (e.g. a tied note spans the boundary), the builder must still store that beat position in `beat_positions_ticks[]` so the cursor can render a slot there at runtime. `beat_positions_ticks` is stored alongside `notes` in the exercise JSON for all meters.

#### 3. VexFlow renderer (JS, inside QA player)

New rendering path in `barline_player.js` (a sibling ES module to `qa_player.js`) activated when `config.type === "umto_barline_placement"`. `qa_player.js` is not touched — `qa_player.html` already loads scripts as `<script type="module">`, so `barline_player.js` is loaded via a second `<script type="module">` tag in `qa_player.html` and boots independently on `DOMContentLoaded` when `window.__EXERCISE_CONFIG__.type === "umto_barline_placement"`.

VexFlow is not currently available in the QA player template. The spike must explicitly add `<script src="{% static 'js/lib/vexflow.js' %}">` to `qa_player.html` and verify `Vex.Flow` is accessible in the module context before any other work proceeds.

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
- `essen`: Essen Folk Song Collection, a Kern/Humdrum-derived source exposed by music21
- `kern`: arbitrary local Kern/Humdrum file path
- `manual`: read from a hand-authored JSON file

Command validates each generated exercise (total duration, barline count, note count) before saving.

---

## Corpus / Repertoire

### Primary: Essen Folk Song Collection (Kern/Humdrum via music21)

- Thousands of short monophonic folk melodies available through music21's built-in corpus
- Kern/Humdrum-derived repertoire source
- Public domain
- Simple and compound meters naturally represented
- Pickup/anacrusis examples are pedagogically important, though advanced
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

## Phase 1 Frontend Contract

This section defines the exact integration path so implementation needs no guesswork.

### Exercise type string

`type: "umto_barline_placement"` — this is the discriminator used at every layer.

### `generate_exercise_context` in `lab/views.py`

Add a branch alongside the existing `umto_symbolic_meter` branch:

```python
if exercise_context.get("type") == "umto_barline_placement":
    context["exercise_config_json"] = json.dumps(exercise_context)
    return render(request, "qa_player.html", context)
```

### `window.__EXERCISE_CONFIG__` shape

The same `exercise_config_json` mechanism already used by `umto_symbolic_meter`. The config is a top-level object (not wrapped in `problems[]`):

```json
{
  "type": "umto_barline_placement",
  "time_signature": "3/4",
  "show_time_signature": false,
  "clef": "treble",
  "measures": 3,
  "pitch_mode": "rhythm_only",
  "notes": [...],
  "correct_barline_positions": [2, 5],
  "beat_count": 9,
  "pickup_beats": 0,
  "beat_positions_ticks": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  "note_beat_onsets": [0, 1, 2, 3, 5, 6, 7.5, 8],
  "source": "Essen Folk Song Collection, no. 42",
  "tags": ["unit:2", "unit:2_meter_simple", "unit:2_meter_triple"],
  "courseId": "...",
  "playlistName": "...",
  "exerciseNum": 1
}
```

`problems[]` is not used — this is a single-problem exercise, not a paged MC set.

### Result submission

Reuse the existing `/ajax/identification-answers/` endpoint. Serialize result as:

```json
{
  "course_ID": "...",
  "playlist_ID": "...",
  "exercise_num": 1,
  "answers": { "barlines": [2, 5] },
  "correctness": { "0": true },
  "score": { "correct": 1, "incorrect": 0, "unanswered": 0 }
}
```

### UMTO data storage

Exercises stored as `Exercise` rows using a new `save_umto_barline_exercise()` helper that mirrors the existing symbolic-meter save path, with a new `type: "umto_barline_placement"` field in the data payload. This is "UMTO-adjacent and migration-friendly" — the JSON is structurally compatible with UMTO conventions but does not declare a new `InteractionMode` until Phase 2. The `type` key in the stored data is the runtime discriminator.

Phase 2: add `InteractionMode.BARLINE_PLACEMENT` to `apps/exercises/umto.py` and migrate.

---

## Data Storage

Phase 1: exercises stored as `Exercise` rows via `save_umto_barline_exercise()` in `apps/exercises/umto_factory.py`. The `data` payload uses `type: "umto_barline_placement"` as discriminator. `mode` is set to `InteractionMode.IDENTIFICATION` as the closest existing value until Phase 2 adds a dedicated mode.

Phase 2: add `InteractionMode.BARLINE_PLACEMENT` to `apps/exercises/umto.py` and `apps/exercises/umto_schema.json`; migrate existing rows.

---

## File Map

| File | Change |
|---|---|
| `lab/static/js/src/barline_player.js` | **New** — ES module: VexFlow rendering + beat cursor + grader. Boots on `DOMContentLoaded` when `config.type === "umto_barline_placement"` |
| `lab/templates/qa_player.html` | **Edit** — add `<script src="vexflow.js">` and `<script type="module" src="barline_player.js">` |
| `lab/views.py` — `generate_exercise_context` caller | **Edit** — add `umto_barline_placement` branch alongside `umto_symbolic_meter` |
| `apps/exercises/umto_factory.py` | **Edit** — add `save_umto_barline_exercise()` helper, mirroring `save_umto_symbolic_exercise()` |
| `apps/exercises/management/commands/generate_unit2_barline_exercises.py` | **New** — sibling to `generate_unit2_meter_exercises.py`; imports from Essen corpus and hand-authored JSON |
| `apps/exercises/utils/barline_exercise_builder.py` | **New** — beat structure computation, exercise JSON generation, validation |
| `apps/exercises/tests/test_barline_exercise_builder.py` | **New** — unit tests for builder and grader logic |
| `harmony/settings/requirejs.py` | **No change** — QA player uses ES modules, not RequireJS |

---

## Key Technical Risks

| Risk | Mitigation |
|---|---|
| VexFlow not accessible inside `<script type="module">` in qa_player.html | Spike step 1 — verify before anything else; fallback: load VexFlow as global script before the module |
| VexFlow `getAbsoluteX()` unreliable after single-stave render | Spike step 3 — log and verify; fallback: uniform spacing from stave width ÷ beat_count |
| Cursor overlay misaligns on resize | Re-read x-coords on `ResizeObserver` callback |
| music21 Essen corpus parse failures | Wrap each parse in try/except, skip and log; validate beat totals before saving |
| Tied note spans beat boundary — no note at beat position | Store `beat_positions_ticks[]` in exercise JSON; cursor slots come from that array, not note positions |
| `barline_player.js` interferes with `qa_player.js` on same page | Both modules gate on `config.type` — only one boots per page; no shared state |

---

## Recommended Spike (Before Full Build)

1-day spike before committing to full build:

1. Add `<script src="{% static 'js/lib/vexflow.js' %}">` to `qa_player.html` and confirm `Vex.Flow` is accessible inside a `<script type="module">` — this is the first unknown.
2. In a new `barline_player.js`, render one unbarred 3/4 passage (9 quarter notes) on a single VexFlow `Stave` with no time signature and no measure barlines.
3. Log `note.getAbsoluteX()` for each note after `Formatter.format()` + `Voice.draw()`.
4. Position a cursor overlay `<div>` using those x-values.
5. Move it left/right with arrow keys.
6. Confirm overlay tracks notes correctly on window resize.

If all 6 steps work cleanly → proceed to full build.
If VexFlow x-coord access is unreliable → fallback: compute beat widths as `stave.getWidth() ÷ beat_count` (uniform spacing, less accurate but functional).

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
| QA template/view routing for barline player | Low |
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
