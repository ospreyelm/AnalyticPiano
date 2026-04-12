# Identification Exercise Paging Design

**Date:** 2026-04-12
**Status:** Approved
**Branch:** feature/music21_builder

---

## Overview

Identification exercises (interval identification, chord identification, chorale identification) can contain many problems. The exercise sheet already limits display to 4 problems per page (matching the chorale `maxMeasures` default), but there is no way to navigate to subsequent pages. This design adds in-exercise paging so Next/Previous navigation moves through pages within the same exercise before falling through to playlist navigation.

Feature A (chorale MIDI page advance) is deferred — needs hands-on testing to determine whether the existing `_updateChoraleViewport` already handles it. Recorded as a TODO in plan.md.

---

## Architecture

### Page state — `ExerciseContext`

`ExerciseContext` owns page state for identification exercises:

- `_identPage` — integer, 0-indexed, current page (initialised to 0)
- `_identPageSize` — integer, default 4 (matches chorale maxMeasures)

New methods:

```
getIdentPage()         → current page index
getIdentPageSize()     → page size (default 4)
getTotalIdentPages()   → Math.ceil(allProblems.length / pageSize)
goToIdentPage(n)       → set _identPage, reset grader page state, trigger re-render
```

### Navigation interception

`goToNextExercise()` and a new `goToPreviousExercise()` in `ExerciseContext` check before propagating:

- Is this an identification exercise?
- Are there multiple pages?
- Is there a next/previous page available?

If yes → call `goToIdentPage(n ± 1)` and return. Do NOT broadcast `NEXTEXERCISE` / `PREVIOUSEXERCISE`.
If no (already on last/first page) → propagate the event to `MusicComponent` as today.

`MusicComponent` subscribes to `PREVIOUSEXERCISE`. `ExerciseContext` currently only has `goToNextExercise`. A `goToPreviousExercise` method needs to be added that mirrors it.

### Grading — `IdentificationGrader`

`grade(definition, pageOffset, pageSize)` — evaluates only the slice `problems[pageOffset ... pageOffset + pageSize]`.

Answers are keyed by **absolute** problem index (e.g. problem 5 on page 2 is stored as `answers[5]`). This means:
- Answers on earlier pages survive forward navigation
- Answers survive backward navigation within the same session

In "submit" mode, the Submit button grades only the **current page's** problems. Students complete and submit each page independently.

### Rendering — `ExerciseSheet`

`ExerciseSheet` reads `exerciseContext.getIdentPage()` and `getIdentPageSize()` to determine which problems to render and which label slots to draw. `ExerciseDefinition.getProblems()` is unchanged — always returns all problems. The sheet slices the display locally.

`drawIdentificationLabels()` adds a page indicator drawn on the canvas (e.g. "Page 2 of 5") below the staff.

---

## Data Flow

```
Student clicks Next
    ↓
music_controls.js broadcasts NEXTEXERCISE
    ↓
ExerciseContext.goToNextExercise() intercepts
    ↓
Is identification exercise with more pages?
    YES → goToIdentPage(current + 1)
           reset grader answers for new page? No — preserve all answers
           trigger "graded" re-render
    NO  → broadcast NEXTEXERCISE to MusicComponent (playlist advance)
```

---

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/models/exercise_context.js` | Add `_identPage`, `_identPageSize`, `getIdentPage()`, `getTotalIdentPages()`, `goToIdentPage()`, `goToPreviousExercise()`, interception logic in `goToNextExercise()` |
| `lab/static/js/src/models/identification_grader.js` | Accept `pageOffset` and `pageSize` in `grade()` |
| `lab/static/js/src/components/music/exercise_sheet.js` | Slice problems by page for rendering; add page indicator to `drawIdentificationLabels()` |

No changes needed to:
- `music_controls.js` (buttons already broadcast correct events)
- `events.js` (no new events needed)
- Django backend

---

## Behaviour Summary

| Scenario | Result |
|----------|--------|
| Single page exercise | No change — Next/Prev go to playlist neighbours as today |
| Multi-page, not on last page | Next → advance page |
| Multi-page, on last page | Next → playlist next exercise (or no-op if end of playlist) |
| Multi-page, not on page 0 | Prev → retreat page |
| Multi-page, on page 0 | Prev → playlist previous exercise (or no-op if start of playlist) |
| Student answers page 1, goes to page 2, returns to page 1 | Page 1 answers preserved in session |

---

## Deferred / Future Enhancements

### Chorale MIDI page advance (Feature A)
The existing `_updateChoraleViewport` in `exercise_sheet.js` may already handle measure-block scrolling for chorales. Needs hands-on testing before adding code. Recorded as a TODO in plan.md.

### Cross-session answer persistence
Currently, in-progress answers are held in memory only (`IdentificationGrader.answers`). If a student closes the browser mid-exercise, their page 1–3 answers are lost on next visit. Supporting persistence would require:
- Saving partial answers to the server as the student works (new Django endpoint)
- Loading partial answers on exercise init
- A partial-completion state in the Exercise/PerformanceData model

This is a meaningful feature but out of scope for this change. Behaviour matches all other exercise types — exercises are completed in one sitting.

---

## Testing

1. Import an interval identification exercise with more than 4 problems
2. Verify page 1 shows problems 1–4, page indicator shows "Page 1 of N"
3. Click Next — verify page 2 renders problems 5–8, page indicator updates
4. Answer some problems on page 2, click Prev — verify page 1 answers still present
5. Navigate to last page, click Next — verify playlist advance (or no-op if no next exercise)
6. On page 1, click Prev — verify playlist previous (or no-op if no previous exercise)
7. Single-page exercise: verify Next/Prev go directly to playlist neighbours unchanged
