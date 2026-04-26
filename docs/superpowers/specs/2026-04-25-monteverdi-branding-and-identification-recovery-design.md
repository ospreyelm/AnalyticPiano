# Monteverdi Branding And Identification Recovery — Design Spec

**Date:** 2026-04-25  
**Status:** Approved — ready for implementation planning  
**Feature scope:** Student-facing behavior and branding only

---

## Overview

This spec covers two user-facing changes:

1. **Identification recovery flow** — when a student fails a `Submit` attempt on a note-identification exercise, the UI should stop looking like a failed final submission and instead move the student into a guided correction flow.
2. **Student-facing rename to `Monteverdi`** — visible product branding in the student experience should use the new name, while the private repository name and internal identifiers remain unchanged.

These are intentionally separate scopes that ship together because they both affect the student-facing surface, but they do not require a full platform rename or any database migration.

---

## Goals

- Remove the contradiction where a student is told to fix mistakes but still sees a `Submit`-mode presentation with stale wrong markers.
- Preserve the pedagogical distinction between first-pass mastery and success after correction.
- Rename the visible student product to `Monteverdi` without expanding into operational or infrastructure changes.

## Non-Goals

- No GitHub repository rename.
- No domain, deployment, email, package, or internal module rename.
- No dashboard/admin branding pass in this phase.
- No logo generation or logo asset rollout in this phase. That can be a follow-up once the visible name placement is stable.

---

## Current Problem

### Identification flow

In `submit` mode, a failed identification page submit currently:

- leaves the student in a failed-submission visual state
- preserves wrong markings under the notes
- invites correction, but does not actually switch interaction models

That produces a confusing hybrid state: the student is effectively correcting work, but the screen still looks like a final graded submission.

### Branding

The student-facing product still shows the old name in titles and visible labels. The user wants the student experience branded as `Monteverdi`, tied to `www.monteverdimusic.com`, without renaming the private code repository.

---

## Design

## Section 1: Identification Recovery Flow

### Decision

On a failed `Submit` for an identification page, the app will **automatically switch that exercise session into `Practice` mode**.

This is the chosen design because it matches the teaching model:

- `Submit` means “final check”
- `Practice` means “fix with immediate feedback”

Once a page fails `Submit`, the student is no longer doing a final check. They are correcting mistakes. The UI should reflect that explicitly.

### Behavior

When the student presses `Submit` on an identification page and the page is not fully correct:

1. The exercise state becomes `incorrect` as it does now.
2. The session mode changes from `submit` to `practice`.
3. The segmented mode control updates visually to show `Practice` as active.
4. Existing correct answers remain in place.
5. Incorrect slots remain editable.
6. As the student changes answers in this recovery state, immediate correctness feedback is shown using normal `practice` behavior.
7. Once the page becomes fully correct, the student may continue and complete the exercise through the corrected state.

### Important clarification

This design does **not** reset the page, clear all answers, or discard mistakes already recorded in `error_tally`.

The recovery flow is a UI/interaction change, not a data-loss change.

### Resulting student experience

Before:
- failed submit leaves red wrong markers in a `Submit` workflow

After:
- failed submit clearly transitions into correction mode
- students fix mistakes with immediate feedback
- the interaction model matches the instruction being shown

---

## Section 2: Status And Copy

The incorrect-state status copy remains aligned with the recovery flow:

- `Fix the errors and resubmit`

Because the page will now automatically move into `Practice` mode after a failed submit, that copy becomes instructional rather than contradictory.

If needed in implementation, the copy may be tightened slightly to fit narrow layouts, but the meaning should stay the same: students are fixing multiple issues and then resubmitting.

---

## Section 3: Completion And Progress Semantics

The backend treatment of mistakes remains unchanged in this phase:

- final correctness is still computed from the final submitted answers
- mistakes are still recorded separately through `error_tally`
- score card messaging continues to distinguish first-pass `Mastered` from corrected `Corrected`

This means the recovery-flow change is only about the interaction model during correction, not about redefining grading.

---

## Section 4: Student-Facing Monteverdi Branding

### Decision

Rename **visible student-facing branding only** to `Monteverdi`.

### Included scope

Update visible strings such as:

- browser page title
- student-facing headers
- visible product-name text in student templates
- other directly student-visible app-name labels discovered during implementation

### Excluded scope

Do not rename:

- repository name
- Python package/module names
- database values unless they are directly used as visible branding
- deployment identifiers
- Git remotes
- internal config names unless they surface directly to students

### Domain note

The domain `www.monteverdimusic.com` is accepted as the intended public-facing identity, but this spec does not include infrastructure or hosting changes.

---

## Architecture Impact

### Files likely affected

**Identification flow**
- `lab/static/js/src/models/exercise_context.js`
- `lab/static/js/src/components/music/exercise_sheet.js`

**Student-facing branding**
- student templates under `apps/student/templates/student/`
- any student-facing page-title or branding string source discovered during implementation

No database migration is expected.

---

## Implementation Outline

### Identification flow

In the identification submit path:

- detect failed page submit in `submit` mode
- switch `sessionMode` to `practice`
- ensure the mode control and rendering react immediately
- keep current answers, but let practice-mode grading take over for subsequent edits

The existing rule that only correctly graded slots lock in submit mode should remain intact. The difference is that, after a failed submit, the student is no longer left in submit mode.

### Branding

Find and replace visible student-facing product-name strings with `Monteverdi`, keeping the change scoped to student-facing rendering only.

---

## Testing

### Identification flow

Manual verification:

1. Open a Unit 1 identification exercise in `submit` mode.
2. Enter one or more wrong answers.
3. Press `Submit`.
4. Confirm the UI switches to `Practice` mode automatically.
5. Correct the wrong notes.
6. Confirm immediate feedback appears while correcting.
7. Complete the page/exercise and verify progress and score-card behavior still work.

Regression checks:

- correct first-pass `Submit` should still complete normally
- page navigation should still work across multi-page identification exercises
- `error_tally` should still increment on failed submit

### Branding

Manual verification:

1. Load the student unit page and student player.
2. Confirm visible product-name strings show `Monteverdi`.
3. Confirm no obvious old product name remains in student-facing titles or headers.

---

## Risks

### Risk 1: Mode-switch drift

If the session mode changes internally but the segmented control or render path does not re-render immediately, the UI could still look inconsistent.

**Mitigation:** force re-render after switching modes and verify the toggle state in manual testing.

### Risk 2: Partial branding rename

If branding strings are duplicated across templates, some old labels may remain visible.

**Mitigation:** do a targeted search for visible app-name strings in student templates and title sources during implementation.

---

## Follow-Up Work

These are explicitly out of scope for this spec, but good next candidates:

- create a `Monteverdi` logo and introduce it into the student-facing header
- broader dashboard/admin branding pass
- public-facing domain/config cleanup
- deeper naming cleanup if the product rename becomes permanent across the whole stack

