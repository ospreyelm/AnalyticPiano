# Prompts to build the `identification` exercise type

Work through these prompts in order. Each step is self-contained and testable before moving to the next.

---

## Step 1 — Add the type to ExerciseDefinition

Read `lab/static/js/src/models/exercise_definition.js` in full, then implement the following:

1. Add `identification: "identification"` to `ExerciseDefinition.TYPES`.
2. Add `isIdentification()` to the prototype, returning `this.exercise.type === "identification"`.
3. In `parse()`, add a new branch for `type === "identification"`:
   - All notes in each problem go to `visible`; `hidden` is always `[]`.
   - Read `answer` (string) and `choices` (array of strings) from each chord object and store them on the normalized problem alongside `visible` and `notes`.
   - Set `exercise.analysis` to a deep clone of `ANALYSIS_SETTINGS` but with all mode flags set to `false` (no auto-labeling).
   - `exercise.problems` shape: `{ visible, hidden, notes, answer, choices }`.

Do not touch any other exercise type. Do not change `ExerciseGrader`.

---

## Step 2 — IdentificationGrader

Read `lab/static/js/src/models/exercise_grader.js` and `lab/static/js/src/models/chorale_grader.js` to understand the grader interface, then create `lab/static/js/src/models/identification_grader.js`.

The grader must:

- Maintain `pointer` (current problem index, starts at 0), `selections` (array of student-chosen labels, one per problem), `mistakes` (array of booleans, one per problem), `finished` (bool).
- Expose `initFromDefinition(definition)` — reads `definition.getProblems()`, resets all state.
- Expose `selectLabel(label, definition)`:
  - Compare `label` to `problems[pointer].answer`.
  - Record the selection in `selections[pointer]` and whether it was correct in `mistakes[pointer]`.
  - Advance `pointer`. If `pointer >= problems.length`, set `finished = true`.
  - Return `{ correct: bool, pointer: newPointer, finished: bool }`.
- Expose `grade(definition)` — returns:
  ```js
  {
    result: "correct" | "partial" | "incorrect",
    score: 0 | 1 | 2,       // 0 = no mistakes, 1 = in progress, 2 = has mistakes
    activeIndex: pointer,
    problems: [ { answer, chosen, correct }, ... ]
  }
  ```
  Grading logic: if `finished` and no mistakes → `correct` (score 0); if `finished` with any mistake → `incorrect` (score 2); otherwise → `partial` (score 1).

No dependencies outside `lodash`.

---

## Step 3 — LabelInputComponent

Read `lab/static/js/src/components/input/note_name.js` and `lab/static/js/src/components/events.js` to understand the component and event patterns, then create `lab/static/js/src/components/input/label_input.js`.

Requirements:

- AMD module, returns a `LabelInputComponent` constructor.
- Constructor accepts `{ el, choices, onSelect }` where `el` is a jQuery element and `choices` is the array of label strings for the current problem.
- `render(choices)` — clears `el` and renders a `<button>` for each choice string. Support Unicode (Roman numerals with accidentals, °, ø, △). Buttons get CSS class `label-choice-btn`.
- On button click: add class `selected` to the clicked button, call `onSelect(label)`.
- `showResult(label, correct)` — adds class `correct` or `incorrect` to the button matching `label`. On `incorrect`, remove the class after 800 ms and re-enable buttons.
- `advance(newChoices)` — call `render(newChoices)` to reset for the next problem.
- Does **not** fire `EVENTS.BROADCAST` directly — the caller (`exercise_sheet.js`) handles that.

---

## Step 4 — Wire into exercise_sheet.js

Read `lab/static/js/src/components/music/exercise_sheet.js` in full, then add identification mode support.

Add to the `define([...])` dependency list: `"app/components/input/label_input"`.

Add `initIdentificationMode()` to the prototype:
- Creates a `LabelInputComponent` targeting `$('#label-input')`.
- Calls `render(currentProblemChoices())` for the first problem.
- Passes `onSelect` callback that fires `EVENTS.BROADCAST.LABEL_SELECTED` with the label string.
- Stores the instance as `this.labelInput`.

Add `onLabelSelected(label)` to the prototype:
- Calls `this.labelInput.showResult(label, wasCorrect)` — get `wasCorrect` from `this.exerciseContext.grader.selectLabel(label, definition)`.
- If the pointer advanced and the exercise is not finished, calls `this.labelInput.advance(nextChoices())`.
- If finished, triggers the normal exercise completion path (calls `this.exerciseContext.grade()` and lets `ExerciseContext` handle auto-advance).

In `initComponent()`, add:
```js
if (this.exerciseContext.getDefinition().isIdentification()) {
  this.initIdentificationMode();
}
```

In `initListeners()`, bind `EVENTS.BROADCAST.LABEL_SELECTED` → `this.onLabelSelected` when `isIdentification()`.

MIDI-based chord bank listeners remain in place (piano still active for audio preview) but don't trigger grading.

---

## Step 5 — Wire into exercise_context.js and exercise.js

Read `lab/static/js/src/models/exercise_context.js` and `lab/static/js/src/components/app/exercise.js` in full.

**In `exercise_context.js`:**
- In the grading branch (wherever `ChoraleGrader` is checked), add a parallel branch: if `definition.isIdentification()`, use the `IdentificationGrader` instance (passed in via constructor or set directly — follow whichever pattern `ChoraleGrader` uses).
- `grade()` should delegate to `identificationGrader.grade(definition)` when `isIdentification()` and return the result in the standard shape.

**In `exercise.js` → `getModels()`:**
- Add: `"app/models/identification_grader"` to the `define` dependency list.
- After the `ChoraleGrader` branch, add:
  ```js
  if (models.exerciseDefinition.isIdentification()) {
      models.grader = new IdentificationGrader();
      models.grader.initFromDefinition(models.exerciseDefinition);
  }
  ```

Do not break the existing `matching` / `analytical` / `figured_bass` / `chorale` paths.

---

## Step 6 — Template and CSS

Read `lab/templates/exercise.html` and `lab/static/css/` to understand the existing layout.

**In `exercise.html`:**
Add `<div id="label-input"></div>` immediately after `<canvas id="staff">`. It should be hidden by default via CSS and shown only when the exercise type is `identification` (add a class to the container based on the exercise type, or control visibility from JS).

**In the relevant CSS file:**
Add styles for:
```css
#label-input { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; justify-content: center; }
.label-choice-btn { padding: 8px 20px; font-size: 1rem; border: 2px solid #ccc; background: #fff; cursor: pointer; border-radius: 4px; }
.label-choice-btn.selected { border-color: #555; }
.label-choice-btn.correct { background: #d4edda; border-color: #28a745; }
.label-choice-btn.incorrect { background: #f8d7da; border-color: #dc3545; }
```

---

## Step 7 — Smoke test

1. Create a minimal identification exercise directly in the Django admin (`/analytic-piano-app-admin/`) or via the Django shell, pasting this as the `data` JSON:
   ```json
   {
     "type": "identification",
     "key": "jC_",
     "introText": "Identify each chord.",
     "chord": [
       { "visible": [60, 64, 67], "hidden": [], "answer": "I",   "choices": ["I", "ii", "IV", "V"] },
       { "visible": [62, 65, 69], "hidden": [], "answer": "ii",  "choices": ["I", "ii", "IV", "V"] },
       { "visible": [65, 69, 72], "hidden": [], "answer": "IV",  "choices": ["I", "ii", "IV", "V"] },
       { "visible": [67, 71, 74], "hidden": [], "answer": "V",   "choices": ["I", "ii", "IV", "V"] }
     ]
   }
   ```
2. Add it to a playlist and open the exercise player.
3. Verify:
   - Notes render fully visible on the staff.
   - No roman numeral or analytical overlay appears above/below the staff.
   - Four buttons appear below the canvas with the choices.
   - Selecting the correct button flashes green then advances to the next chord.
   - Selecting a wrong button flashes red, resets after ~800 ms, and allows retry.
   - After the last problem, the exercise completes and auto-advances (or shows completion state) per the existing `autoAdvance` setting.
   - Piano keyboard still plays audio when keys are pressed; no MIDI input is graded.
