# Unit 4 Synthetic Interval Worksheets

## Goal

Replace the earlier Unit 4 interval prototype with a score-backed synthetic worksheet flow that behaves like later identification units: visible notation, clickable `?` slots, staged answer sets, and management-command generation.

## Completed tasks

- [x] Add `generate_unit4` management command for staged generic and specific interval worksheets.
- [x] Generate Unit 4 content as UMTO-backed score identification exercises instead of isolated legacy `identification` chords.
- [x] Render Unit 4 worksheets as treble-only notation with one whole-note interval per measure and visible barlines.
- [x] Reuse score-based identification slot placement so each interval column gets a clickable `?` label.
- [x] Fix frontend exercise-type detection so static `identification` is not misclassified as chorale-style score identification.
- [x] Harden identification paging helpers against missing `problems` arrays.
- [x] Support playlist definition refresh routes that pass `exercise_num` in the URL path.
- [x] Add focused tests for Unit 4 generation output.
- [x] Register the command in `list_exercise_generators.py`.
- [x] Document the command in `docs/management_commands.md`.
- [x] Document the score-based identification runtime shape in `docs/exercise_types.md`.

## Notes

The shipped Unit 4 worksheets now use `type: "umto_chorale"` with `mode: "identification"`. That keeps them on the modern UMTO path while still using the existing score-identification renderer and grader.
