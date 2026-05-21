# Hand Mode Selector — Design Spec

_Date: 2026-05-21_
_Scope: Unit 3 scale play exercises (UMTO playback type) only_

---

## Problem

Scale exercises render a grand staff (treble = RH, bass = LH). Students practicing on an on-screen keyboard, or following a teacher-structured curriculum (RH first, then LH, then both hands), need a way to play only one hand at a time. The grader currently requires all notes across both staves.

---

## Decisions

| Question | Decision |
|---|---|
| Who sets default? | Teacher via generation command (`--hand-mode` flag); student overrides per-session |
| Score display when one hand active? | Full grand staff always shown — no masking or hiding |
| Mode switch mid-exercise? | Auto-reset (grader re-inits for new hand, student starts from note 1) |
| Persistence | Session only — no `localStorage`, no server call. Resets to teacher default on reload |
| Grading in single-hand mode | Same correct/incorrect/partial as both-hands; fewer notes required |
| Half-credit scoring per hand | Out of scope — current grader has no numeric scoring layer |
| SATB voice selector for chorales | Out of scope — separate feature, separate spec |
| Dashboard teacher edit | Out of scope — dashboard UMTO support pending separate rebuild |

---

## Data Model

`hand_mode` is an optional field in UMTO metadata (`Exercise.data["score"]["umto"]["metadata"]`).

**Values:** `"both"` (default) | `"rh"` | `"lh"`

**Schema addition** (`apps/exercises/umto_schema.json`):
```json
"hand_mode": {
  "type": "string",
  "enum": ["both", "rh", "lh"],
  "default": "both"
}
```

No DB migration needed — UMTO metadata is a schemaless JSON blob. Existing exercises without the field default to `"both"` at read time.

---

## Generation Command

`generate_unit3_scale_exercises.py` gains one new flag:

```bash
python manage.py generate_unit3_scale_exercises \
  --author admin@example.com \
  --mode both \
  --hand-mode both   # "rh" | "lh" | "both" (default: "both")
```

The flag applies to all exercises in the run. `hand_mode` is passed through `umto_kwargs`:

```python
umto_kwargs=dict(
    exercise_id="TEMP",
    source=f"Play the {display_name} scale on the keyboard.",
    key=key_id,
    meter="4/4",
    clef="keyboard",
    complexity_score=3,
    mode=InteractionMode.PLAYBACK,
    unit=3,
    hand_mode=options.get("hand_mode", "both"),  # new
)
```

No changes to `save_umto_exercise` or the UMTO factory — `umto_kwargs` already passes through to metadata.

Update `umto_schema.json` manually (or run `python manage.py make_umto_schema` after adding the field to the schema source) before running generation.

---

## Frontend: ExerciseDefinition

`exercise_definition.js` reads `hand_mode` from UMTO metadata and exposes it on the exercise object:

```javascript
exercise.handMode = (umto.metadata && umto.metadata.hand_mode) || "both";
```

This happens in the UMTO exercise parsing block (around line 975). The field is only meaningful for `mode === "playback"` exercises, but storing it unconditionally is harmless.

---

## Frontend: ChoraleGrader

`initFromDefinition` accepts a second `handMode` argument and translates it to `selectVoices` before calling `buildTimeline`:

```javascript
initFromDefinition: function(definition, handMode) {
  this.reset();
  var score = definition.getScore ? definition.getScore() : null;
  if (!score) return this;

  var opts = {};
  if (handMode === "rh") {
    opts.selectVoices = { treble: [0, 1], bass: [] };
  } else if (handMode === "lh") {
    opts.selectVoices = { treble: [], bass: [0, 1] };
  }
  // "both": no selectVoices filter

  this.timeline = ScoreTimeline.buildTimeline(score, opts);
  // ... rest of init unchanged
}
```

`buildMeasureOffsets` is **not** passed `selectVoices` — it always reads all voices to compute measure durations correctly for rendering.

`selectVoices` already exists in `ScoreTimeline.buildTimeline` (`score_timeline.js:66`). No changes to `score_timeline.js`.

---

## Frontend: UI Toggle

**Render condition:** only for UMTO playback exercises where `exercise.handMode != null`. Not shown for chorales, identification exercises, or any non-scale type.

**Placement:** Right side of the dark instruction bar (the bar below the score showing "Play the X scale on the keyboard." + READY button). Inline with existing bar content.

**HTML structure:**
```html
<div class="hand-mode-toggle">
  <button class="hand-mode-btn" data-mode="rh">RH</button>
  <button class="hand-mode-btn" data-mode="lh">LH</button>
  <button class="hand-mode-btn active" data-mode="both">Both</button>
</div>
```

Active button reflects current mode (teacher default on load).

**Click handler (in `exercise_sheet.js`):**
1. Set `currentHandMode = newMode` (local variable)
2. Update `.active` class on buttons
3. Call `grader.initFromDefinition(definition, newMode)` — resets grader, rebuilds timeline for new hand

No `localStorage`. No `/ajax/preferences/` call. State lives only in the `currentHandMode` local variable for the session.

---

## Files Changed

| File | Change |
|---|---|
| `apps/exercises/management/commands/generate_unit3_scale_exercises.py` | Add `--hand-mode` CLI arg; pass `hand_mode` in `umto_kwargs` |
| `apps/exercises/umto_schema.json` | Add optional `hand_mode` enum field; rebuild with `make_umto_schema` |
| `lab/static/js/src/models/exercise_definition.js` | Read `umto.metadata.hand_mode`, expose as `exercise.handMode` |
| `lab/static/js/src/models/chorale_grader.js` | Accept `handMode` in `initFromDefinition`; translate to `selectVoices` opts |
| `lab/static/js/src/components/music/exercise_sheet.js` | Pass `handMode` when calling `initFromDefinition`; render toggle; wire click handler |
| `docs/exercise_types.md` | Note `hand_mode` field on UMTO playback type entry |

No new files. No DB migration. No backend API changes.

---

## Existing Exercises

No migration or backfill required. JS defaults `handMode` to `"both"` when field absent:

```javascript
exercise.handMode = (umto.metadata && umto.metadata.hand_mode) || "both";
```

To explicitly set `hand_mode: "both"` on existing scale exercises, run:
```bash
python manage.py generate_unit3_scale_exercises --author <email> --mode both --overwrite
```

Not required for correct behaviour.

---

## Out of Scope

- SATB voice selector for chorale exercises
- Half-credit scoring (RH = 50%, LH = 50%)
- Teacher dashboard hand mode edit (pending dashboard UMTO rebuild)
- Persistence of student hand mode preference across sessions
