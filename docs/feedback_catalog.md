# Feedback Catalog

Source of truth for reusable student-facing strings: `lab/static/js/src/config/feedback_catalog.js`.
This doc mirrors it for content review. Emit with
`feedbackService.emit("<id>", { params, anchorRect, controlEl, inlineEl, context })`.

Grade feedback resolves via `FeedbackCatalog.resolveGradeFeedbackId(type, state, diagnostic)`
(most specific → `<type>.grade.<state>` → `exercise.grade.<state>`).

Only `feedback_service.js` may broadcast `EVENTS.BROADCAST.NOTIFICATION`. No `window.alert`
for student messages. Per-exercise authored instructions/prompts live in exercise data, NOT here.

## Adding feedback for a new exercise type
1. Classify into one taxonomy category (spec §1).
2. Pick the lightest surface (spec §2): global / inline / control / anchored / none.
3. Grade feedback: the universal `exercise.grade.<state>` already covers you. Add
   `<type>.grade.<state>` only for type-specific wording, and
   `<type>.grade.<state>.<diagnostic>` only if your grader reports that diagnostic.
4. Add the catalog entry + a row below.
5. Emit via the service; never inline strings or alerts.

Feedback id convention: `<domain>.<context>.<event>`. IDs are STABLE (analytics primary key).

## Registry
| Feedback ID | Category | Surface | Copy | Persistence | Emitted by |
|-------------|----------|---------|------|-------------|-----------|
| harmonization.click.note_cap | soft_constraint | control | "Chord is full. Remove a note to add another." | 1800ms | click_note.js |
| harmonization.click.outside_column | soft_constraint | none | "Finish this chord first — the next one opens when you do." | 2500ms | click_note.js |
| harmonization.click.empty_commit | soft_constraint | control | "Add a note or two first." | sticky | click_note.js |
| input.mode.changed_live | mode_state | inline | "Live input — play your keyboard or MIDI." | 2000ms | exercise.js toggle |
| input.mode.changed_click | mode_state | inline | "Click input — tap the staff to place each note." | 2000ms | exercise.js toggle |
| input.device.none | mode_state | inline | "No MIDI keyboard? No problem — …" | sticky | midi.js |

| exercise.grade.correct | success | anchored | "Yes — that's right." | 1500ms | exercise_context.js |
| exercise.grade.incorrect | recoverable_mistake | anchored | "Not quite — give it another try." | 4000ms | exercise_context.js |
| exercise.grade.partial | mode_state | none | "Good so far — keep going." | 2000ms | exercise_context.js |
| exercise.complete | success | inline | "Beautifully done." | 3000ms | exercise_context.js |
| chorale.grade.incorrect | recoverable_mistake | anchored | "That isn't the note in the score — listen, then try again." | 4000ms | chorale_grader.js |
| chorale.grade.correct | success | anchored | "That's the one." | 1500ms | chorale_grader.js |
| identification.grade.incorrect | recoverable_mistake | anchored | "Not the right name — take another look." | 4000ms | identification_grader.js |
| identification.grade.correct | success | anchored | "Exactly." | 1500ms | identification_grader.js |
| harmonization.grade.incorrect | recoverable_mistake | anchored | "Not quite — check the chord against the figure and try again." | 4000ms | harmonization_grader.js |
| harmonization.grade.correct | success | anchored | "Yes — that's it." | 1500ms | harmonization_grader.js |
| harmonization.grade.incorrect.wrong_inversion | recoverable_mistake | anchored | "Right chord — but the bass doesn't match the figure's inversion." | 4500ms | harmonization_grader.js |
| harmonization.grade.incorrect.wrong_quality | recoverable_mistake | anchored | "Close — check the chord quality (major, minor, diminished?)." | 4500ms | harmonization_grader.js |
| identification.grade.incorrect.wrong_octave | recoverable_mistake | anchored | "Right letter — wrong octave." | 4000ms | identification_grader.js |
| play.save.success | success | inline | "Saved. Your exercise is saved and reviewed." | 2500ms | play workbench save handler |
| play.save.invalid_meter | blocking_error | inline | "Can't save yet. Bar {bar} has {beats} beats, expected {expected}. Fix a duration or move a barline." | sticky | play workbench save handler |
| play.save.empty | blocking_error | inline | "Nothing to save. Bank at least two chords first." | 2500ms | play workbench save handler |

(Phase 4 adds the system.* rows.)
