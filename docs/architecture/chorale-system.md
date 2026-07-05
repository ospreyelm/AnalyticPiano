# Chorale Exercise System

## Scope

This document routes contributors to the durable specifications and principal
code for chorale playback, identification, harmonization, grading, and
rendering. Historical commit summaries and troubleshooting detail no longer
belong in always-loaded agent instructions.

## Canonical representation

All new chorale exercises use UMTO. Legacy `chorale`,
`chorale_identification`, and raw-CIR Exercise shapes are frozen.

Read:

- [UMTO guide](../UMTO_GUIDE.md)
- [Exercise type reference](../exercise_types.md)
- [Chorale exercise plan](../chorale_exercises_plan.md)
- [Chorale analysis](../chorale_analysis.md)
- [Future improvements](../chorale_future_improvements.md)
- [Grading pipeline](../grading_pipeline.md)

Roman-numeral exercises sourced from Clausulae must follow:

[Roman from Clausulae lessons](../superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md)

Do not revive the exploratory compendium MusicXML-to-derived-CIR path for
student-facing Roman exercises.

## Two rendering pipelines — do not confuse them

There are two independent renderers that both use "chorale" terminology
(`isChorale()`, `CHORALE_FORMAT`, `staffDistribution: "chorale"`). A bug
report naming "chorale" does not tell you which one is broken — check the
URL first.

**Student play** (`/s/units/<n>/play/`, `apps/student/views.PlayerView`,
`@_require_student`, never reachable by teachers):
`app/components/app/exercise.js` → `ExerciseSheetComponent`
(`exercise_sheet.js` + `exercise_sheet_staves.js`). For chorale-like
exercises (`isChorale() || isChoraleIdentification() || isHarmonization()`
is true — covers `chorale`, `chorale_identification`, `harmonization`,
`analysis_match`/`playback`), `renderStaves()` branches into
`VexFlowAdapter.render()` (`rendering/vexflow_adapter.js` +
`vexflow_tickable_builder.js` + `vexflow_staff_voice_builder.js`). Only the
non-chorale-like fallback (`matching`, `figured_bass`) uses
`ExerciseNoteFactory`/`StaveNoteFactory`. **Do not assume every student
exercise type uses the same note factory — check `isChoraleLike` in
`exercise_sheet_staves.js` first.**

**Teacher authoring** (`/teacher/play/`, `lab/views.PlayView`, gated by
`apps/teacher/middleware.TeacherAccessMiddleware`, never reachable by
students): `app/components/app/play.js` → `PlaySheetComponent`
(`play_sheet.js`) → `Stave`/`stave_note_factory.js`/`play_note_factory.js`
(legacy chord-based renderer, including its own separate `CHORALE_FORMAT`
two-voice-per-staff branch in `stave_note_factory.js`). `play_sheet.js`
does import `VexFlowAdapter`, but only calls `.render()` at two specific
preview call sites (authoring-toolbar live preview, sample preview) — it is
**not** the primary renderer here. Seeing `VexFlowAdapter` imported in a
file does not mean it's what actually draws the notes in that file.

These two pipelines share no rendering code. A fix in one does not touch
the other, and vice versa — verify which pipeline a bug report actually
hit (check the URL, then the view class, then the JS entry module) before
tracing further.

## Principal code

- `apps/exercises/umto_factory.py`: sanctioned UMTO creation.
- `apps/exercises/management/commands/import_chorale.py`: chorale import.
- `apps/exercises/pitch_voice_utils.py`: voice extraction and validation.
- `apps/exercises/utils/music21_builder.py`: exercise-to-music21 conversion.
- `apps/exercises/utils/skills_analyzer.py`: pedagogical skill detection.
- `lab/static/js/src/models/chorale_grader.js`: onset-based MIDI grading
  (student pipeline only — selected in `components/app/exercise.js` for
  `playback`/`analysis_match` modes only). **`harmonization` mode matches
  neither the identification nor the chorale-grader branch there and falls
  through to `ExerciseGrader`, which delegates to
  `harmonization_grader_logic.js`.** Rendering for harmonization still goes
  through `VexFlowAdapter` (below) — grader selection and renderer
  selection are two separate branches on two different conditions; do not
  assume the same mode routes to the same class on both axes.
- `lab/static/js/src/components/music/score_timeline.js`: score timeline.
- `lab/static/js/src/components/music/exercise_sheet.js` +
  `exercise_sheet_staves.js`: student exercise UI and chorale-branch render.
- `lab/static/js/src/components/music/rendering/vexflow_adapter.js` +
  `vexflow_tickable_builder.js` + `vexflow_staff_voice_builder.js`: the
  actual chorale note-building/rendering pipeline (student-facing).
- `lab/static/js/src/components/music/play_sheet.js` +
  `stave_note_factory.js`: teacher authoring renderer — separate pipeline,
  see above.

## Grading model

The chorale grader builds a flat timeline of note events and groups nearby
onsets into windows. MIDI input is matched against new attacks and notes held
from prior windows. Window completion advances the assignment position.

Important invariants:

- event IDs must remain stable between timeline construction and rendering;
- held-note detection must track staff and voice;
- repeated notes require explicit student input;
- passing tones close in time may belong to one playable window; and
- grading should be pedagogically forgiving rather than performance-punitive.

## Debugging

Browser logs use:

- `[INIT]` for timeline initialization;
- `[1. PLAY]` for MIDI input;
- `[2. GRADE]` for matching and advancement; and
- `[3. VISUAL]` for rendering state.

When diagnosing:

1. verify the stored UMTO/CIR score;
2. inspect timeline events and onset windows;
3. compare expected MIDI numbers with incoming input;
4. verify held-note duration and voice identity;
5. verify event IDs shared by grader and renderer; and
6. reproduce with a focused automated test before changing grading behavior.

## Related generation constraints

Before Bach/Riemenschneider bulk generation or deduplication, follow:

[Efficient Bach generation](../superpowers/plans/2026-06-02-efficient-bach-generation.md)

Before passing stored keys into music21, follow:

[Music21 key normalization](../superpowers/plans/2026-06-02-music21-key-normalization.md)

Do not add another ad hoc batch script when the approved generation service or
management-command path can be extended.
