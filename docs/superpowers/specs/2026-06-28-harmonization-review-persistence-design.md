# Harmonization Review Persistence — Design

**Date:** 2026-06-28
**Status:** Approved (design); pending implementation plan
**Scope:** Render a student's saved harmonization answer when an exercise is opened
in review mode. Harmonization exercises only.

## Problem

When a completed harmonization exercise is reopened in review mode, the staff
renders the bare exercise (given bass + figured bass) without the student's
played/locked chords. Example: Unit 9 "Authentic Cadences (Harmonization)",
playlist `PA03SM`.

Root cause (traced):

- The frontend submits `harmonization_accepted_sonorities` in its performance
  report (`exercise_context.js:627`) to `/ajax/exercise-performance/`. This is
  stored in `PerformanceData.data` (a JSON list, one dict per exercise pass,
  keyed by `id`), so **the student's answer is already persisted** — no new
  model or migration is needed.
- The review-mode backend (`apps/student/views.py`) only restores
  identification answers (`reviewAnswers`, from `IdentificationAttempt`). It
  never surfaces stored harmonization sonorities.
- The renderer reads `acceptedHarmonizationSonorities`
  (`exercise_sheet_staves.js:238` → `HarmonizationRealizationLogic.buildRealization`),
  but that array is only filled during live play and reset on load — never
  restored in review.

This is an unbuilt read-back/restore feature, not a regression.

## Decisions (from brainstorming)

- **Which pass to render:** the most-complete pass (most accepted sonorities);
  ties broken by most recent.
- **Behavior in review:** pure display. Input and grading are disabled; the
  student cannot practice over a harmonization in review.
- **No new persistence:** reuse `PerformanceData.data`.
- **Approach:** backend selects the pass and embeds it in the page payload
  (mirrors the existing `reviewAnswers` pattern); frontend restores it into the
  existing render path. No new AJAX endpoint.

## Data shape

Stored entries (`exercise_context.js:202`) have the shape consumed directly by
`buildRealization(accepted, targets, score, meter)`:

```js
{ midi: [number, ...], targetIndex: number, ts: number }
```

`buildRealization` reads only `.targetIndex` and `.midi`, so the persisted array
can be assigned straight to `acceptedHarmonizationSonorities` with no transform.

## Components

### 1. Model — selection logic

`PerformanceData.get_best_harmonization_pass(self, exercise_id) -> list | None`

- Iterate `self.data`. Consider an entry a candidate when:
  - its id matches this exercise — compare on the 6-char base id
    (`entry.get("id", "")[:6] == exercise_id[:6]`) so transposed variants count,
    consistent with `exercise_id[0:6]` usage elsewhere in this model; and
  - it carries a non-empty `harmonization_accepted_sonorities` list.
- Return the candidate with the greatest `len(harmonization_accepted_sonorities)`.
  On a tie, return the one appearing later in `self.data` (most recent, since
  `data` is append-ordered).
- Return `None` when there are no candidates.

Keep this on the model so the view stays thin and the logic is unit-testable.

### 2. View — embed in payload

In the review-mode branches that already set `reviewAnswers`:

- HTML player view (`apps/student/views.py` ~975)
- player-definition JSON endpoint (`apps/student/views.py` ~1169)

When the exercise is a harmonization exercise, look up the user's
`PerformanceData` for this context, call
`get_best_harmonization_pass(exercise_id)`, and if the result is non-null set
`exercise_context["reviewHarmonizationSonorities"]` to it.

`PerformanceData` is keyed by `(user, playlist, course)` (`unique_together`),
and `course` may be `None` for independent (non-course) play. The lookup must
use the same context the page resolves for this request (the `playlist` and
`course` already in scope in the review branch). Query defensively (e.g.
`filter(...).first()`) and treat a missing row the same as no pass.

- Gate strictly on harmonization so identification and other review flows are
  unchanged.
- Use the same harmonization discriminator the codebase already uses for this
  exercise (e.g. `data.mode == "harmonization"`); confirm the exact check during
  implementation.
- If `PerformanceData` for the context does not exist, or the method returns
  `None`, omit the key entirely.

### 3. Frontend — restore + display-only

Restore (`lab/static/js/src/components/app/exercise.js`, getModels, near the
existing `reviewMode`/`reviewAnswers` block at line ~164):

```
if (definition.reviewMode
    && definition.reviewHarmonizationSonorities
    && models.exerciseContext._isHarmonizationExercise()) {
  models.exerciseContext.acceptedHarmonizationSonorities =
    _.cloneDeep(definition.reviewHarmonizationSonorities);
  models.exerciseContext._reviewDisplayOnly = true;
}
```

Display-only guards (`exercise_context.js` and the harmonization input
components):

- In `initialize()` harmonization branch (`exercise_context.js:144`), when
  `_reviewDisplayOnly`, do not wire input → grade.
- `gradeHarmonizationMidiSet` and `click_note._commit` early-return when
  `_reviewDisplayOnly` is set.
- Hide/disable the Lock-chord button and accidental palette in review.
- Ensure the sheet renders after restore so the saved sonorities draw on load
  (reuses `acceptedHarmonizationSonorities → buildRealization`).

### 4. Banner copy

For harmonization display-only review, change the review hint (set in
`player.html` `refreshPlayerChrome`, ~line 218) from:

> Review mode — your result is preserved, practice freely.

to:

> Review mode — showing your saved result.

Only for the harmonization display-only case; other review hints unchanged.

## Testing

- **Model unit tests** (`apps/exercises/tests/`): `get_best_harmonization_pass`
  — picks most-complete pass; tie resolves to most recent; returns `None` with
  no candidates / no matching id / empty sonorities.
- **View tests** (`apps/student/tests/test_player_views.py`): review payload
  includes `reviewHarmonizationSonorities` for a harmonization exercise with a
  stored pass; absent for non-harmonization and when no pass exists. Mirror the
  existing `test_player_review_mode_*` tests.
- **Manual QA:** complete a harmonization exercise, reload in review →
  saved answer renders, input controls disabled, banner copy updated; reopening
  an exercise with no prior pass renders the bare exercise without error.

## Edge cases

- No `PerformanceData` / no matching pass / empty sonorities → key omitted,
  review renders the bare exercise (today's behavior), no crash.
- Identification and other review flows unchanged (harmonization-gated).
- Transposed variants: matched via 6-char base id.

## Out of scope

- Bug B: harmonization Enter/Lock-chord wiping played notes during normal play
  (tracked separately in memory `project_harmonization_enter_wipes_notes`).
- Practicing over a saved harmonization in review (explicitly excluded — review
  is pure display).
- Review persistence for non-harmonization played-notes exercises.
