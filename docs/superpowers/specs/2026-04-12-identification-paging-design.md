# Identification Exercise Paging Design

**Date:** 2026-04-12
**Status:** Revised after code review
**Branch:** feature/music21_builder

---

## Overview

Identification exercises (interval identification, chord identification, chorale identification) can contain many problems. The exercise sheet already limits display to 4 problems per page (matching the chorale `maxMeasures` default), but there is no way to navigate to subsequent pages. This design adds in-exercise paging so Next/Previous navigation moves through pages within the same exercise before falling through to playlist navigation.

Feature A (chorale MIDI page advance) is deferred — needs hands-on testing to determine whether the existing `_updateChoraleViewport` already handles it. Recorded as a TODO in plan.md.

---

## Key Design Principle: One Shared Visible Window

The first version of this spec proposed slicing problems locally inside the label-drawing layer. A code review identified this as incorrect: stave layout, chord generation, grading, and label placement are all coupled — they all derive from `getProblems()`. If only the label layer is page-aware, the rendered staves and the displayed labels fall out of sync.

The fix: **`ExerciseContext` owns a single authoritative visible window** — `[pageOffset, pageOffset + pageSize]` — and every layer reads from it. `createDisplayChords()`, `IdentificationGrader.grade()`, and `ExerciseSheet` label/slot rendering all consume the same slice.

---

## Architecture

### Page state — `ExerciseContext`

`ExerciseContext` owns:

- `_identPage` — integer, 0-indexed, current page (initialised to 0)
- `_identPageSize` — integer, default 4

New methods:

```
getIdentPage()            → current page index
getIdentPageSize()        → page size (default 4)
getIdentPageOffset()      → _identPage * _identPageSize
getTotalIdentPages()      → Math.ceil(allProblems.length / pageSize)
getVisibleProblems()      → definition.getProblems().slice(offset, offset + pageSize)
goToIdentPage(n)          → set _identPage, reset page-level state, trigger re-render
```

`getVisibleProblems()` is the single source of truth consumed by all three layers below.

### Layer 1: Chord generation — `ExerciseContext.createDisplayChords()`

Currently iterates `definition.getProblems()`. Change to iterate `this.getVisibleProblems()` when this is an identification exercise. This ensures the staves render only the current page's problems.

Note: `graded.problems` is indexed by **position within the current page** (0 to pageSize-1), not absolute index. The grader returns results in page-local order.

### Layer 2: Grading — `IdentificationGrader`

`grade(definition, visibleProblems)` — receives the already-sliced array from `ExerciseContext`. Evaluates only those problems.

Answers remain keyed by **absolute problem index** in `grader.answers` (e.g. problem index 5 on page 2 stored as `answers[5]`). This preserves answers across page navigation within a session. The grader maps absolute indices to page-local positions when building the `gradedProblems` result array.

### Layer 3: Rendering — `ExerciseSheet`

`_getIdentificationSlots()` and `drawIdentificationLabels()` derive slots from rendered staves, so they remain page-local by default (`0..visibleProblems.length-1`).

**Required mapping rule:**

```
localIndex = slot.index
absoluteIndex = exerciseContext.getIdentPageOffset() + localIndex
```

All answer reads/writes and grading lookups must use `absoluteIndex`:
- Popup click handler (`setAnswer`) stores by absolute index
- Label text (`chosen`) reads from `grader.answers[absoluteIndex]`
- Correct/incorrect colour lookup maps page-local graded result to local slot index

This preserves cross-page answers while keeping rendered slots page-local.

`drawIdentificationLabels()` adds a page indicator on the canvas (e.g. "Page 2 of 5") when `getTotalIdentPages() > 1`.

---

## Page Completion vs Exercise Completion

This is a critical distinction. Currently a `CORRECT` grade result in `ExerciseContext.grade()` seals the exercise, fires the timer, submits the report, and triggers auto-advance. We need to separate **page complete** from **exercise complete**.

### New state: page-complete

When the student submits page N and it grades as correct:
- Mark page N as complete (internal flag, e.g. `_completedPages` Set)
- Submit performance report for this page (see Persistence below)
- Reset `sealed`, `done`, `flawless`, `errorTally`, and the timer for the next page
- Call `goToIdentPage(N + 1)` — or, if on the last page, mark the whole exercise complete and run the normal exercise-completion path (auto-advance, next exercise, etc.)

The existing CORRECT branch in `ExerciseContext.grade()` is only reached for the **final page**. Earlier pages intercept before that point.

### Submit mode flow

```
Student answers all problems on current page
    ↓
Clicks Submit (or Next)
    ↓
ExerciseSheet.onSubmitIdentification() calls grader.grade(definition, visibleProblems)
    ↓
If correct AND not last page:
    submitExerciseReport() for this page
    reset page-level state
    goToIdentPage(current + 1)
If correct AND last page:
    normal exercise-complete path (timer end, report, auto-advance)
If incorrect:
    show results on current page, do not advance
```

---

## Navigation Interception (Next/Previous buttons)

`goToNextExercise()` and a new `goToPreviousExercise()` in `ExerciseContext` intercept before propagating:

- Is this an identification exercise with multiple pages?
- Is there a next/previous page?

If yes → page turn (submit current page if moving forward, just navigate if moving backward).
If no → propagate `NEXTEXERCISE` / `PREVIOUSEXERCISE` to `MusicComponent` as today.

**Moving forward via Next** behaves identically to Submit — grades the page first. Only advances if the page is correct. If incomplete or incorrect, stays put (same as clicking Submit with wrong answers).

**Deterministic rule for the last page:** Next never bypasses grading.
- If current page is not valid/correct: remain on current page.
- If current page is valid/correct and this is not the last page: go to next page.
- If current page is valid/correct and this is the last page: run the normal exercise-complete path, then propagate playlist next.

**Moving backward** does not re-submit. It simply navigates to the previous page, which already has answers preserved in `grader.answers`.

---

## Persistence

Each page submission calls `submitExerciseReport()`. The current report payload does not carry per-problem answers or a page number. Two options:

**Option A (recommended now):** Keep the existing endpoint/model, but include lightweight page metadata in the existing JSON payload:
- `page_num` (1-indexed)
- `page_total`
- `is_final_page` (boolean)

`PerformanceData.data` is already a JSON blob, so this does **not** require a Django schema migration. It removes ambiguity in submission order and prevents page attempts from being indistinguishable.

**Option B (richer):** Add `page_num` and `page_answers` fields to the report payload, and a corresponding field to the `PerformanceData` Django model. Enables per-page analytics.

**Recommendation: Option A now.** It avoids schema changes while making page-level records explicit. Option B is a future enhancement for deep analytics.

---

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_context.js` | Add `_identPage`, `_identPageSize`, `getIdentPage/Size/Offset()`, `getTotalIdentPages()`, `getVisibleProblems()`, `goToIdentPage()`, `goToPreviousExercise()`, page-complete logic in grade path, intercept logic in `goToNextExercise()`, page-scoped reset, and page metadata in `compileExerciseReport()` payload |
| `lab/static/js/src/models/identification_grader.js` | Accept `visibleProblems` array in `grade()`; map absolute answer indices to page-local result positions |
| `lab/static/js/src/components/music/exercise_sheet.js` | Use local↔absolute index mapping for identification labels/popups, add page indicator in `drawIdentificationLabels()`, and ensure `onSubmitIdentification()` calls page-complete path |

No changes needed to:
- `music_controls.js` (buttons already broadcast correct events)
- `events.js` (no new events needed)
- Django schema/migrations (Option A)

---

## Behaviour Summary

| Scenario | Result |
|----------|--------|
| Single page exercise | No change — Next/Prev go to playlist neighbours as today |
| Multi-page, submit correct page, not last | Save report, advance to next page, reset page state |
| Multi-page, submit correct last page | Normal exercise-complete path (auto-advance, report) |
| Multi-page, submit incorrect page | Show results, stay on page |
| Multi-page Next button (not last page) | Same as submit + advance |
| Multi-page on last page, click Next | First validate/grade last page; only then run complete path + playlist next |
| Multi-page on page > 0, click Prev | Retreat to previous page, answers preserved |
| Multi-page on page 0, click Prev | Playlist previous exercise (or no-op) |
| Student navigates away mid-page | Current page in-progress answers lost; completed pages already saved |

---

## Deferred / Future Enhancements

### Chorale MIDI page advance (Feature A)
The existing `_updateChoraleViewport` in `exercise_sheet.js` may already handle measure-block scrolling for chorales. Needs hands-on testing before adding code. Recorded as a TODO in plan.md.

### Per-page analytics (Option B persistence)
Add `page_answers` (and optionally richer per-problem timing) to the report payload for deep per-page analytics. Keep `page_num/page_total/is_final_page` from Option A as the baseline contract.

### Mid-page persistence across sessions
Current in-progress answers (not yet submitted on the current page) are lost if the browser closes. Full mid-page persistence would require saving partial answers to the server as the student selects each answer. Out of scope — completed pages are already persisted.

---

## Testing

1. Import an interval identification exercise with more than 4 problems
2. Verify page 1 shows problems 1–4 on the staves; page indicator shows "Page 1 of N"
3. Answer all problems on page 1, click Submit — verify correct/incorrect feedback shown
4. Click Next — verify page 2 staves render problems 5–8, page indicator updates, page 1 report submitted
5. Navigate back (Prev) — verify page 1 answers still shown, no re-submission
6. Navigate to last page, submit correctly — verify exercise-complete path fires (auto-advance or next exercise)
7. Navigate to last page, click Next — verify playlist advance (or no-op)
8. On page 0, click Prev — verify playlist previous (or no-op)
9. Single-page exercise — verify Next/Prev go directly to playlist neighbours unchanged
10. Submit incorrect answers on a page — verify no page advance, error feedback shown
