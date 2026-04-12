# Identification Exercise Paging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-page navigation to identification exercises so large exercises (more than 4 problems) can be paged through using the existing Next/Previous buttons, with each completed page saved as performance data.

**Architecture:** `ExerciseContext` owns page state (`_identPage`, `_identPageSize`) and exposes `getVisibleProblems()` as the single source of truth consumed by all three layers — chord generation, grading, and sheet rendering. Next/Previous events are intercepted at `ExerciseContext` level; only on the first/last page do they fall through to playlist navigation. Page completion is distinct from exercise completion: earlier pages submit a report and reset state; the final page runs the normal exercise-complete lifecycle.

**Tech Stack:** JavaScript (RequireJS/AMD modules), jQuery, Underscore.js. No backend schema changes required. No existing test suite — verification is via browser console + manual interaction.

**Spec:** `docs/superpowers/specs/2026-04-12-identification-paging-design.md`

---

## File Map

| File | Role in this change |
|------|---------------------|
| `lab/static/js/src/models/exercise_context.js` | Add page state, `getVisibleProblems()`, `goToIdentPage()`, `goToPreviousExercise()`, page-complete path, updated `compileExerciseReport()` |
| `lab/static/js/src/models/identification_grader.js` | Accept `visibleProblems` array; map absolute answer indices to page-local results |
| `lab/static/js/src/components/music/exercise_sheet.js` | Use absolute index mapping in click/label handlers; call page-complete path from `onSubmitIdentification()`; add page indicator |

---

## Task 1: Add page state and `getVisibleProblems()` to `ExerciseContext`

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

This task adds the core data — page index, page size, and the slice method every other layer will consume. No behaviour changes yet.

- [ ] **Step 1: Add page state initialisation in the `ExerciseContext` constructor**

In `exercise_context.js`, the constructor ends at around line 100 with `this.init()`. Add after `this.sealed = false;` (around line 96):

```javascript
// Identification paging state
this._identPage = 0;
this._identPageSize = 4;
```

- [ ] **Step 2: Add page accessor methods to `ExerciseContext.prototype`**

Add the following methods inside `_.extend(ExerciseContext.prototype, { ... })`, after `getDefinition: function()` (around line 636):

```javascript
/**
 * Returns the current page index (0-indexed) for identification exercises.
 */
getIdentPage: function () {
  return this._identPage;
},
/**
 * Returns the number of problems per page.
 */
getIdentPageSize: function () {
  return this._identPageSize;
},
/**
 * Returns the absolute problem index of the first problem on the current page.
 */
getIdentPageOffset: function () {
  return this._identPage * this._identPageSize;
},
/**
 * Returns the total number of pages for the current identification exercise.
 */
getTotalIdentPages: function () {
  var allProblems = this.definition.getProblems();
  return Math.ceil(allProblems.length / this._identPageSize);
},
/**
 * Returns the slice of problems visible on the current page.
 * This is the single source of truth for all rendering and grading layers.
 */
getVisibleProblems: function () {
  var offset = this.getIdentPageOffset();
  var allProblems = this.definition.getProblems();
  return allProblems.slice(offset, offset + this._identPageSize);
},
/**
 * Returns true if this is any kind of identification exercise.
 */
_isIdentificationExercise: function () {
  return (
    (typeof this.definition.isIdentification === 'function' && this.definition.isIdentification()) ||
    (typeof this.definition.isChoraleIdentification === 'function' && this.definition.isChoraleIdentification())
  );
},
```

- [ ] **Step 3: Verify in browser console**

Load any identification exercise. Open DevTools console and run:

```javascript
// Get the exercise context from the sheet component
var ctx = window._exerciseContext; // may need to add temporary debug exposure — see note below
ctx.getIdentPage();       // expected: 0
ctx.getIdentPageSize();   // expected: 4
ctx.getIdentPageOffset(); // expected: 0
ctx.getTotalIdentPages(); // expected: Math.ceil(problems.length / 4)
ctx.getVisibleProblems(); // expected: first 4 problems
```

To expose the context temporarily for debugging, find where `ExerciseContext` is instantiated in `exercise.js` (around line 110) and add `window._exerciseContext = context;` after creation. Remove this after Task 7.

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: add page state and getVisibleProblems() to ExerciseContext"
```

---

## Task 2: Update `createDisplayChords()` to use the visible window

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:721-766`

`createDisplayChords()` currently iterates all problems. Change it to use `getVisibleProblems()` for identification exercises so staves render only the current page.

- [ ] **Step 1: Update `createDisplayChords()` to slice by page for identification exercises**

Find `createDisplayChords: function ()` (around line 721). Change:

```javascript
var problems = this.definition.getProblems();
```

to:

```javascript
var problems = this._isIdentificationExercise()
  ? this.getVisibleProblems()
  : this.definition.getProblems();
```

The rest of the function is unchanged. `graded.problems[i]` continues to use page-local index `i` (0 to pageSize-1), which matches the grader output in Task 3.

- [ ] **Step 2: Verify in browser**

Load an identification exercise with more than 4 problems. The stave should render exactly 4 problems (not all of them). Check DevTools console for any errors.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: slice visible problems in createDisplayChords() for identification exercises"
```

---

## Task 3: Update `IdentificationGrader.grade()` to accept visible problems

**Files:**
- Modify: `lab/static/js/src/models/identification_grader.js`

The grader currently calls `definition.getProblems()` internally. Change it to accept a `visibleProblems` array so grading evaluates only the current page. Answers remain stored by absolute index.

- [ ] **Step 1: Rewrite `grade()` to accept `visibleProblems`**

Replace the current `grade: function (definition)` (lines 38–64) with:

```javascript
grade: function (definition, visibleProblems) {
  // Fall back to all problems if visibleProblems not supplied (single-page exercises)
  var problems = visibleProblems || definition.getProblems();
  var pageOffset = definition.getIdentPageOffset ? definition.getIdentPageOffset() : 0;
  var gradedProblems = [];
  var allAnswered = true;
  var allCorrect = true;

  for (var i = 0; i < problems.length; i++) {
    var absoluteIndex = pageOffset + i;
    var answer = problems[i].answer;
    var chosen = this.answers.hasOwnProperty(absoluteIndex) ? this.answers[absoluteIndex] : null;
    var correct = (chosen !== null && chosen !== '') ? (chosen === answer) : null;

    if (!chosen) { allAnswered = false; }
    if (correct !== true) { allCorrect = false; }

    gradedProblems.push({ answer: answer, chosen: chosen, correct: correct });
  }

  var resultState = (allAnswered && allCorrect) ? CORRECT : (allAnswered ? INCORRECT : PARTIAL);
  var score = (allAnswered && allCorrect) ? 0 : (allAnswered ? 2 : 1);

  return {
    result: resultState,
    score: score,
    activeIndex: null,
    problems: gradedProblems  // page-local indices 0..n
  };
}
```

Note: `pageOffset` is obtained from `definition.getIdentPageOffset()` which was added in Task 1. The grader does not own page state — it reads it from the definition/context passed in.

- [ ] **Step 2: Verify `setAnswer` still uses absolute index**

`setAnswer: function (problemIndex, label)` already stores `this.answers[problemIndex] = label`. The popup passes the absolute index (fixed in Task 4), so this is unchanged.

- [ ] **Step 3: Verify in browser**

Load an identification exercise. Answer a problem on page 1. Open console:

```javascript
window._exerciseContext.grader.answers; // should show { 0: "M2", ... } with absolute keys
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/models/identification_grader.js
git commit -m "feat: grade() accepts visibleProblems slice with absolute index mapping"
```

---

## Task 4: Fix absolute index mapping in `ExerciseSheet` label/slot handlers

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

Slot indices from `_getIdentificationSlots()` are page-local (0, 1, 2, 3). The popup click handler and label renderer must convert to absolute index before reading/writing answers.

- [ ] **Step 1: Add absolute index helper at top of identification click handler**

Find the canvas click handler inside `initIdentificationMode` (around line 191). The hit-test loop ends with `hitIndex = slot.index`. After that, before `self._showIdentPopup(...)`, add:

```javascript
var pageOffset = self.exerciseContext.getIdentPageOffset
  ? self.exerciseContext.getIdentPageOffset() : 0;
var absoluteHitIndex = pageOffset + hitIndex;
```

Then change the popup call from:
```javascript
self._showIdentPopup(hitIndex, problem.choices, e.clientX, e.clientY);
```
to:
```javascript
self._showIdentPopup(absoluteHitIndex, problem.choices, e.clientX, e.clientY);
```

And change the problem lookup from:
```javascript
var problem = problems[hitIndex];
```
to:
```javascript
var problems = definition.getProblems();
var problem = problems[absoluteHitIndex];
```

(The `problems` variable is already declared just above — update it to use `definition.getProblems()` so it has all problems, not just visible ones. Only the hit-index-to-problem lookup uses this.)

- [ ] **Step 2: Fix test-mode lock check to use absolute index**

Still inside the click handler, find:
```javascript
if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(hitIndex)) {
```
Change `hitIndex` to `absoluteHitIndex`:
```javascript
if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(absoluteHitIndex)) {
```

- [ ] **Step 3: Fix `drawIdentificationLabels()` to use absolute index for answer lookup**

Find `drawIdentificationLabels: function ()` (around line 365). Inside the slot loop, find:

```javascript
var problemIndex = slot.index;
var chosen = grader && grader.answers && grader.answers.hasOwnProperty(problemIndex)
  ? grader.answers[problemIndex] : null;
```

Replace with:

```javascript
var localIndex = slot.index;
var pageOffset = self.exerciseContext && self.exerciseContext.getIdentPageOffset
  ? self.exerciseContext.getIdentPageOffset() : 0;
var absoluteIndex = pageOffset + localIndex;
var chosen = grader && grader.answers && grader.answers.hasOwnProperty(absoluteIndex)
  ? grader.answers[absoluteIndex] : null;
```

Note: `self` is not in scope inside `drawIdentificationLabels` — use `this` instead:

```javascript
var pageOffset = this.exerciseContext && this.exerciseContext.getIdentPageOffset
  ? this.exerciseContext.getIdentPageOffset() : 0;
var absoluteIndex = pageOffset + localIndex;
```

Also update the graded result lookup below it from:
```javascript
if (lastGraded && lastGraded.problems && lastGraded.problems[problemIndex] && identMode !== 'test') {
  var gp = lastGraded.problems[problemIndex];
```
to:
```javascript
if (lastGraded && lastGraded.problems && lastGraded.problems[localIndex] && identMode !== 'test') {
  var gp = lastGraded.problems[localIndex];
```
(Graded results are page-local, so use `localIndex` here, not `absoluteIndex`.)

- [ ] **Step 4: Verify in browser**

Load a multi-page identification exercise. Answer problem on page 1 (e.g. "M2"). Navigate to page 2 (temporarily via console: `window._exerciseContext._identPage = 1; window._exerciseContext.updateDisplayChords(); /* trigger render */`). Answer a problem on page 2. Navigate back to page 1 — the answer should still be there.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: use absolute index mapping for identification label slots and answer lookup"
```

---

## Task 5: Add `goToIdentPage()` with page-level state reset

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

`goToIdentPage(n)` resets per-page state (sealed, done, graded, timer) and triggers a re-render. This is the transition function used by both the submit flow and Next/Previous interception.

- [ ] **Step 1: Add `goToIdentPage()` method**

Add after `getVisibleProblems: function ()` (added in Task 1):

```javascript
/**
 * Navigates to page n of a multi-page identification exercise.
 * Resets per-page state so the new page starts fresh.
 * Does NOT reset grader.answers — those persist across pages.
 */
goToIdentPage: function (n) {
  var total = this.getTotalIdentPages();
  if (n < 0 || n >= total) { return; }
  this._identPage = n;
  // Reset per-page exercise state
  this.sealed = false;
  this.done = false;
  this.graded = false;
  this.flawless = true;
  this.errorTally = 0;
  this.timer = null;
  this.state = ExerciseContext.STATE.READY;
  // Rebuild display chords for the new page
  this.updateDisplayChords();
  this.trigger('graded');
},
```

- [ ] **Step 2: Verify in browser console**

```javascript
window._exerciseContext.goToIdentPage(1);
// Expected: staves re-render with problems 5-8, page indicator (once added) shows Page 2
window._exerciseContext.getIdentPage(); // expected: 1
window._exerciseContext.getIdentPageOffset(); // expected: 4
```

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: add goToIdentPage() with page-level state reset"
```

---

## Task 6: Add page-complete submit path in `ExerciseSheet.onSubmitIdentification()`

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js:437-444`
- Modify: `lab/static/js/src/models/exercise_context.js` (add `submitIdentPage()` helper)

Currently `onSubmitIdentification` calls `grader.grade(definition)`. Change it to pass `visibleProblems`, handle the page-complete vs exercise-complete distinction, and call `submitExerciseReport()` before advancing.

- [ ] **Step 1: Add `submitIdentPage()` to `ExerciseContext`**

Add after `goToIdentPage:` (Task 5):

```javascript
/**
 * Called when the student submits a page of an identification exercise.
 * If the page grades correctly:
 *   - If not the last page: save report and advance to next page.
 *   - If the last page: run the normal exercise-complete lifecycle.
 * If incorrect: show results, stay on page.
 */
submitIdentPage: function () {
  var visibleProblems = this.getVisibleProblems();
  var graded = this.grader.grade(this.definition, visibleProblems);
  this.graded = graded;
  this.updateDisplayChords();
  this.trigger('graded');

  if (graded.result !== this.grader.STATE.CORRECT) {
    // Incorrect or partial — stay on page, show feedback
    this.state = ExerciseContext.STATE.INCORRECT;
    return;
  }

  var isLastPage = (this._identPage >= this.getTotalIdentPages() - 1);

  if (!isLastPage) {
    // Page correct but not done — save this page's report and advance
    this.endTimer();
    this.submitExerciseReport();
    var nextPage = this._identPage + 1;
    this.goToIdentPage(nextPage);
  } else {
    // Last page correct — run normal exercise-complete lifecycle
    this.done = true;
    this.flawless = true;
    this.endTimer();
    if (this.sealed !== true) {
      this.submitExerciseReport();
      this.sealed = true;
    }
    this.state = ExerciseContext.STATE.CORRECT;
    this.triggerNextExercise();
    this.trigger('graded');
  }
},
```

- [ ] **Step 2: Update `onSubmitIdentification` in `ExerciseSheet` to call `submitIdentPage()`**

Find `onSubmitIdentification: function ()` (around line 437). Replace the entire function body with:

```javascript
onSubmitIdentification: function () {
  this.exerciseContext.submitIdentPage();
  this.render();
},
```

The page-complete logic now lives entirely in `ExerciseContext`. The sheet just triggers it and re-renders.

- [ ] **Step 3: Verify page advance in browser**

Load an identification exercise with more than 4 problems. Answer all 4 problems on page 1 correctly. Click Submit. Expected:
- Staves re-render with problems 5–8
- Console shows "Exercise performance saved" (from the AJAX call)
- Page indicator (once added in Task 7) updates

- [ ] **Step 4: Verify last-page completion**

Navigate to the final page, answer all correctly, click Submit. Expected:
- Exercise-complete state fires (status pill changes)
- Performance data saved
- Auto-advance to next exercise (if enabled and next exercise exists)

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: add submitIdentPage() — page-complete vs exercise-complete lifecycle"
```

---

## Task 7: Intercept Next/Previous for identification page navigation

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

Currently `goToNextExercise()` always broadcasts `NEXTEXERCISE`. Add interception: for multi-page identification exercises, Next = submit-and-advance (same as Submit button). Previous = retreat a page without re-submitting.

- [ ] **Step 1: Replace `goToNextExercise()` with page-aware version**

Find `goToNextExercise: function ()` (around line 642). Replace with:

```javascript
goToNextExercise: function () {
  if (this._isIdentificationExercise() && this.getTotalIdentPages() > 1) {
    // Multi-page identification: Next = submit current page, then advance if correct
    this.submitIdentPage();
    return;
  }
  this.exercise.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
},
```

- [ ] **Step 2: Add `goToPreviousExercise()` with page-aware version**

Add after `goToNextExercise:`:

```javascript
/**
 * Goes to the previous page of a multi-page identification exercise,
 * or falls through to the previous exercise in the playlist if on page 0.
 */
goToPreviousExercise: function () {
  if (this._isIdentificationExercise() && this.getTotalIdentPages() > 1 && this._identPage > 0) {
    // Retreat to previous page — answers already preserved in grader.answers
    this.goToIdentPage(this._identPage - 1);
    return;
  }
  this.exercise.broadcast(EVENTS.BROADCAST.PREVIOUSEXERCISE);
},
```

- [ ] **Step 3: Wire `goToPreviousExercise()` into the event system**

Search for where `PREVIOUSEXERCISE` event is subscribed in `exercise_context.js` or `music_controls.js`. The Previous button in `music_controls.js` broadcasts `PREVIOUSEXERCISE` directly. `ExerciseContext` doesn't currently subscribe to this event — it flows directly to `MusicComponent`.

To intercept it, we need the exercise context to handle it. Find `initListeners` in `exercise_context.js` (around line 129). Add:

```javascript
// Subscribe to previous exercise event to enable page retreat
var self = this;
$(document).on(EVENTS.BROADCAST.PREVIOUSEXERCISE, function () {
  if (self._isIdentificationExercise() && self.getTotalIdentPages() > 1 && self._identPage > 0) {
    self.goToIdentPage(self._identPage - 1);
    // Prevent MusicComponent from also handling this event
    return false;
  }
  // Otherwise let it propagate to MusicComponent
});
```

**Note:** Check how events are actually dispatched — if they use jQuery custom events on `$(document)`, the above works. If they use the app's `broadcast`/`subscribe` system from `Component`, use that API instead. Look at how `EVENTS.BROADCAST.PRISTINE` is subscribed in `exercise_context.js` for the correct pattern and replicate it.

- [ ] **Step 4: Verify Next/Previous in browser**

Load a multi-page identification exercise.
- Click Next without answering → stays on current page (submitIdentPage grades as PARTIAL)
- Answer all correctly, click Next → advances to page 2
- Click Prev → returns to page 1 with answers preserved
- On page 1, click Prev → falls through to playlist (or no-op)
- On last page, answer correctly, click Next → exercise complete, playlist advance

- [ ] **Step 5: Remove temporary `window._exerciseContext` debug exposure** (added in Task 1 Step 3)

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: intercept Next/Previous for identification page navigation"
```

---

## Task 8: Add page indicator to canvas

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js:365-432`

Draw "Page 2 of 5" on the canvas below the staff when there are multiple pages.

- [ ] **Step 1: Add page indicator at the end of `drawIdentificationLabels()`**

Find the end of `drawIdentificationLabels: function ()` (around line 428), just before the lines that restore `ctx.font`, `ctx.fillStyle`, etc. Add:

```javascript
// Page indicator
var totalPages = this.exerciseContext.getTotalIdentPages
  ? this.exerciseContext.getTotalIdentPages() : 1;
if (totalPages > 1) {
  var currentPage = this.exerciseContext.getIdentPage ? this.exerciseContext.getIdentPage() : 0;
  var pageText = 'Page ' + (currentPage + 1) + ' of ' + totalPages;
  ctx.font = '13px sans-serif';
  ctx.fillStyle = '#888888';
  ctx.textAlign = 'right';
  var canvasWidth = ctx.canvas ? ctx.canvas.width : 600;
  var canvasHeight = ctx.canvas ? ctx.canvas.height : 400;
  ctx.fillText(pageText, canvasWidth - 12, canvasHeight - 10);
}
```

- [ ] **Step 2: Verify in browser**

Load a multi-page identification exercise. "Page 1 of N" should appear in the bottom-right corner of the canvas. Navigate pages — indicator should update.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: add page indicator to identification exercise canvas"
```

---

## Task 9: Add page metadata to performance report

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:479-547`

Include `page_num`, `page_total`, `is_final_page` in the report payload (Option A — no schema migration, stored in the existing `data` JSON blob).

- [ ] **Step 1: Update `compileExerciseReport()` to include page metadata**

Find `compileExerciseReport: function ()` (around line 479). The `report` object is built around line 520. Add three fields at the end of the report object, before the `return report` statement:

```javascript
// Identification paging metadata (page_num is 1-indexed for readability)
page_num: this._isIdentificationExercise() ? this._identPage + 1 : null,
page_total: this._isIdentificationExercise() ? this.getTotalIdentPages() : null,
is_final_page: this._isIdentificationExercise()
  ? (this._identPage >= this.getTotalIdentPages() - 1)
  : null,
```

- [ ] **Step 2: Verify in browser console**

Load a multi-page identification exercise. Answer page 1 correctly. Click Submit. In DevTools Network tab, find the POST to `/ajax/exercise-performance/`. Inspect the `data` payload — it should include `"page_num":1,"page_total":N,"is_final_page":false`.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat: include page metadata in exercise performance report"
```

---

## Task 10: End-to-end verification

**Files:** None — verification only.

- [ ] **Step 1: Test single-page exercise (regression)**

Load an identification exercise with 4 or fewer problems. Verify:
- Renders all problems as before
- Submit works as before
- Next/Prev navigate to playlist neighbours as before
- No page indicator shown (only 1 page)

- [ ] **Step 2: Test multi-page forward navigation**

Load an identification exercise with more than 4 problems.
- Page 1 shows problems 1–4; "Page 1 of N" indicator visible
- Answer all 4 incorrectly → Submit stays on page 1, shows error colours
- Answer all 4 correctly → Submit saves report, advances to page 2, "Page 2 of N" shown
- Repeat through all pages; final page triggers exercise-complete state

- [ ] **Step 3: Test cross-page answer preservation**

- Navigate to page 2, answer a problem
- Click Prev to return to page 1
- Verify page 1 answers still present
- Click Next (page grades correctly) → page 2 answers still present

- [ ] **Step 4: Test playlist fallthrough**

- Multi-page exercise, on page 1 → click Prev → goes to previous playlist exercise (or no-op)
- Multi-page exercise, on last page, answer correctly, click Next → goes to next playlist exercise (or no-op)

- [ ] **Step 5: Test chorale identification exercise**

Load a chorale identification exercise (which uses `isChoraleIdentification`). Verify paging works the same way. The `_isIdentificationExercise()` helper covers both identification types.

- [ ] **Step 6: Final commit if any fixes made during verification**

```bash
git add -p
git commit -m "fix: identification paging verification fixes"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `getVisibleProblems()` as single source of truth | Task 1, 2 |
| Grader accepts `visibleProblems` | Task 3 |
| Absolute index mapping in sheet | Task 4 |
| `goToIdentPage()` with state reset | Task 5 |
| Page-complete vs exercise-complete | Task 6 |
| Next/Prev interception | Task 7 |
| Page indicator | Task 8 |
| Page metadata in report | Task 9 |
| Single-page regression | Task 10 |
| Chorale identification coverage | Task 10 |

**Known risk — Previous event interception (Task 7 Step 3):** The `PREVIOUSEXERCISE` event plumbing needs care. The current codebase wires it from `music_controls.js` → broadcast → `MusicComponent`. `ExerciseContext` sits inside `MusicComponent`'s render cycle, not above it. Check the event subscription pattern used by `EVENTS.BROADCAST.PRISTINE` in `exercise_context.js` to confirm the correct API before writing Task 7 Step 3.
