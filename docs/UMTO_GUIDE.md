# UMTO Developer Guide

## What UMTO is

Universal Music Theory Object — the single canonical Exercise payload shape.
Defined by the pydantic model at [apps/exercises/umto.py](../apps/exercises/umto.py)
and the schema at [apps/exercises/umto_schema.json](../apps/exercises/umto_schema.json).

## When to use it

Always. Every new Exercise row must be UMTO.

## Creating an Exercise

See CLAUDE.md "UMTO is the Canonical Exercise Representation" for the full
example. Short form:

```python
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode

ex = save_umto_exercise(
    description=...,
    score_data=cir_dict,
    author=user,
    skill_tags=[...],
    complexity=...,
    umto_kwargs=dict(mode=InteractionMode.IDENTIFICATION, ...),
)
```

## The three InteractionMode values

- `PLAYBACK` — student sees notation, plays each note on MIDI keyboard. Grading
  matches MIDI pitch to grading slice.
- `IDENTIFICATION` — student sees notation, picks a label (note name, roman
  numeral, scale degree) from choices. Grading matches selected label to
  `analysis.content`.
- `ANALYSIS_MATCH` — student sees a label, plays matching pitch in any octave.
  Grading relaxes octave constraint.

## Voice model

`voices.S`, `.A`, `.T`, `.B`. Each is a list of `VoiceEvent` (note or rest) with
absolute duration in quarter-lengths.

`metadata.clef` controls rendering:
- `"treble"` — single staff, all events rendered there regardless of voice id
- `"bass"` — same, single bass staff
- `"keyboard"` — SATB. Soprano+Alto → treble staff, Tenor+Bass → bass staff

## Analysis slices vs. grading slices

- `analysis[]` — pedagogical content (Roman numerals, figured bass, etc.) shown
  to the student. Drives label choices and correct-answer logic for
  identification/analysis modes, and can also provide overlays/debugging data
  for playback modes.
- `grading[]` — target MIDI pitches at each onset. Drives MIDI input grading.

Same `offset` in both arrays represents the same musical moment. Keep them
aligned when authoring.

## Adding a new analysis label type

1. Extend `AnalysisLayer` in `apps/exercises/umto.py`.
2. Update `get_allowed_answers` priority order if needed.
3. Run `python manage.py make_umto_schema` to regenerate the schema.
4. Add a fixture under `apps/exercises/tests/fixtures/umto/` exercising the new field.
5. Contract test #2 will fail in CI if you skip step 3.

## Common pitfalls

- `exercise_id="TEMP"` at build time. Factory's `save_umto_exercise` backfills
  the DB-assigned id after save.
- Unit-tag-driven filtering. `AnalysisSlice.unit_tags=[1]` triggers the Unit 1
  note-name bridge in the frontend. Set it when your exercise is pedagogically
  a "Unit N" exercise.
- The CIR→VexFlow bridge. `_convertUMTOToProcessedScore` in
  `lab/static/js/src/components/music/exercise_sheet.js` is a temporary
  adapter. Do not reach around it — if rendering is broken, fix the adapter or
  the UMTO, not the VexFlow layer.

## Chordal score-kind

`Metadata.score_kind` is `"voices" | "chordal"`, defaulting to `"voices"`. All
existing exercises are `"voices"` and are entirely unaffected.

### When to use chordal

Use `score_kind="chordal"` when the exercise is defined as a sequence of vertical
sonorities rather than independent voice lines — for example, root-position chord
identification, Roman numeral exercises drawn from harmonic snapshots, or any
play-the-chord drill where per-voice voice-leading grading is not required.

### `UMTO.chords` — `ChordEvent[]`

Each entry in `chords` is a `ChordEvent`:

| Field | Type | Constraint | Meaning |
|---|---|---|---|
| `offset` | `float` | ≥ 0 | Quarter-lengths from the start of the exercise |
| `duration` | `float` | > 0 | Quarter-lengths this chord sounds |
| `visible` | `List[int]` | — | MIDI pitches shown in notation |
| `hidden` | `List[int]` | — | MIDI pitches counted for grading but not rendered |
| `spelling` | `Optional[List[str]]` | len = `len(visible)+len(hidden)` if present | Positional enharmonic spelling override; `visible` pitches first, then `hidden` |

Input order within `visible` and `hidden` is preserved (not sorted). If `spelling`
is provided its length must exactly equal `len(visible) + len(hidden)`; the
validator (`ChordEvent.validate_spelling_length`) raises `ValueError` otherwise.

### Validation rules

The `UMTO.validate_score_kind` model-validator enforces:

- `score_kind="chordal"` → `chords` must be non-empty.
- `score_kind="voices"` (the default) → an explicit `voices` field must be
  present. Chordal payloads can omit `voices` because the `UMTO.voices` field has
  a `default_factory`, but voices-kind payloads may not rely on that default.

### Analysis stays top-level

`UMTO.analysis` (list of `AnalysisSlice`) is the canonical home for Roman
numerals, figured bass, and other pedagogical labels. Analysis is correlated to
chords by matching `offset` values. Chords do **not** carry inline analysis
labels.

### Chordal analysis review

Chordal imports may include analyzer-generated `analysis[]` slices aligned by
offset to `chords[]`. `metadata.analysis_review_status` records whether those
labels are:

- `none` — no analysis is available;
- `generated` — analyzer output exists but has not been reviewed;
- `reviewed` — a teacher saved the Workbench analysis review editor.

Workbench analysis projections from chordal imports require `reviewed` status.
Exact Match playback can be cloned before review because it does not expose
analysis labels as answer keys.

Generated labels use HarmonyLab analyzer logic first:

- `compute_figured_bass()` for raw and abbreviated figured bass;
- `legacy_roman_from_pitches()` for Roman labels matching the browser analyzer;
- music21 Roman analysis only as fallback when HarmonyLab has no table label.

### Rendering and the playback window

`build_chordal_umto_payload` in `umto_factory.py` calls `_chordal_to_measures`
to materialise `score.measures` from `chords[]`. `_chordal_to_measures` emits
standard CIR items:

- Multiple pitches → `{kind: "chord", notes: [{pitch: {step, alter, octave}}], duration: {type, dots}}`
- Single pitch → `{kind: "note", pitch: {step, alter, octave}, duration: {type, dots}}`
- No pitches → `{kind: "rest", ...}`

Pitch spelling uses `_midi_to_cir_pitch`, which applies a C-major-ish spelling
(sharps for black keys). Measures break when accumulated quarter-lengths reach the
meter's beats-per-measure.

The existing `score_timeline.js buildTimeline` already consumes CIR chord items,
so no frontend timeline changes were required (spike 5a, W1).

### Frontend wiring

`type` remains `"umto_chorale"`. Within the `umto_chorale` block in
`exercise_definition.js`, `isChordalUMTO` (from
`lab/static/js/src/models/chordal_problems_logic.js`) is checked first. When
true, `chordsToProblems(chords)` populates `exercise.problems` so the chord-bank
grader can evaluate MIDI input against `visible + hidden` pitches.

```javascript
// chordal_problems_logic.js — public API
isChordalUMTO(def)        // true when def.score.umto.metadata.score_kind === "chordal"
chordsToProblems(chords)  // maps ChordEvent[] → [{visible, hidden, notes}]
                          // notes = sorted(visible + hidden)
```

### Creating a chordal exercise

```python
from apps.exercises.umto_factory import build_chordal_umto_payload, save_umto_exercise
from apps.exercises.umto import InteractionMode

payload = build_chordal_umto_payload(
    exercise_id="TEMP",
    source="Identify the Roman numeral.",
    key="C Major",
    meter="4/4",
    clef="treble",
    complexity_score=9,
    mode=InteractionMode.IDENTIFICATION,
    chords=[
        {"offset": 0.0, "duration": 1.0, "visible": [60, 64, 67], "hidden": []},
        {"offset": 1.0, "duration": 1.0, "visible": [62, 65, 69], "hidden": []},
    ],
    analysis=[
        {"offset": 0.0, "content": {"roman_numeral": "I"}, "unit_tags": [9]},
        {"offset": 1.0, "content": {"roman_numeral": "ii"}, "unit_tags": [9]},
    ],
)
```

`build_chordal_umto_payload` returns a frontend-ready dict. There is no
`save_chordal_umto_exercise` helper; persistence uses the standard
`Exercise(data=payload, ...).save()` flow (or a management command that wraps it).

### Legacy load path

`legacy_chord_row_to_chordal_payload(data)` in `umto_factory.py` wraps a legacy
`data.chord` row into a chordal payload at **request time only** — it does not
rewrite the database row. The function is wired into `lab/views.py` as a fallback
branch for non-UMTO rows that have a `chord` array.

```python
payload = legacy_chord_row_to_chordal_payload(exercise.data)
```

Accepted chord shapes: `{visible, hidden}`, `{notes}` (mapped to `visible`), or a
bare MIDI list. Each chord is assigned `duration=1.0` quarter-length.

### Import routing

MusicXML import uses `apps.exercises.utils.umto_import_router` to choose the UMTO
score kind before saving:

- stable 2-, 3-, or 4-part scores with no explicit chord events import as
  voices-kind UMTO;
- one-part, monophonic, explicit-chord, ragged, or homophonic sources import as
  chordal UMTO;
- chordal conversion groups attacks by absolute quarter-length offset and
  preserves `spelling[]` alongside MIDI values for future transpose support.

Legacy CSV chord-bank material can be validated/imported explicitly:

```bash
python manage.py import_legacy_chord_csv exercises_2026-04-03.csv \
  --author admin@example.com --dry-run --limit 10
```

### Known limitations

- **No per-voice voice-leading grading.** Chordal mode has no independent voice
  streams, so voice-leading errors cannot be flagged individually. This is
  acceptable for identification, Roman numeral, figured-bass, and play-the-chord
  exercises.
- **Native chordal transpose UI is not complete.** Spec B preserves chordal
  source spelling so a later transpose layer can avoid enharmonic loss.

## FAQ

**Q: Why is there still a bridge to CIR (`_convertUMTOToProcessedScore`)?**
A: The VexFlow adapter still speaks legacy. Native UMTO rendering is a future
phase, tracked separately. Until then the bridge keeps the frontend working.

**Q: Can I create an Exercise from a Jupyter notebook / shell?**
A: Yes — use `save_umto_exercise`. If you have data in a legacy shape and need
to migrate, use a dedicated management command with
`HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` set.

**Q: The model guard blocks my test.**
A: Use `apps.exercises.tests.umto_test_helpers.make_umto_exercise(...)`. The
bypass env var is only for migration scripts.
