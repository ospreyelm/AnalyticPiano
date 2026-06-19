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

## Principal code

- `apps/exercises/umto_factory.py`: sanctioned UMTO creation.
- `apps/exercises/management/commands/import_chorale.py`: chorale import.
- `apps/exercises/pitch_voice_utils.py`: voice extraction and validation.
- `apps/exercises/utils/music21_builder.py`: exercise-to-music21 conversion.
- `apps/exercises/utils/skills_analyzer.py`: pedagogical skill detection.
- `lab/static/js/src/models/chorale_grader.js`: onset-based MIDI grading.
- `lab/static/js/src/components/music/score_timeline.js`: score timeline.
- `lab/static/js/src/components/music/exercise_sheet.js`: exercise UI.
- `lab/static/js/src/components/music/rendering/vexflow_adapter.js`: rendering.

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
