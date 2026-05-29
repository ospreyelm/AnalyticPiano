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

(Phase 2 adds the grade.* rows; Phase 4 adds the system.* rows.)
