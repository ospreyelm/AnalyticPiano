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
