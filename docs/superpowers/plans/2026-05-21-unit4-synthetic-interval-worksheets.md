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
- [x] Scope key-label suppression to Unit 4 synthetic worksheets so chorale key labels still render.
- [x] Change the default output to six one-page worksheets per lane/stage with eight intervals per worksheet.
- [x] Add Unit 4 display metadata for one-page rendering and extra first-measure spacing.
- [x] Add a Unit 4 note/label X-shift so sparse interval worksheets are visually centered.
- [x] Extend text-input mode to Unit 4 generic and specific interval worksheets.
- [x] Increase the default Unit 4 worksheet bank from 6 to 24 variants per lane/stage.
- [x] Personalize Unit 4 playlist serving order per student while keeping the exercise bank static.
- [x] Use the personalized Unit 4 order consistently in player progression, definition refresh, and submission writes.
- [x] Update Unit 4 docs to describe the larger worksheet bank and per-student seeded ordering.

## Notes

The shipped Unit 4 worksheets now use `type: "umto_chorale"` with `mode: "identification"`. That keeps them on the modern UMTO path while still using the existing score-identification renderer and grader.

The serving model is intentionally different from a true adaptive playlist. Unit 4 keeps a 24-item worksheet bank per stage in the database, but the student app exposes only 6 seeded slots from that bank for any given student. This keeps progress and assignment semantics finite (`1/6`, `2/6`, etc.) while still producing per-student variation from a larger pool. By contrast, Unit 1's normal lane playlists remain fixed curated sequences; only Unit 1 challenge playlists are assembled per-user.
