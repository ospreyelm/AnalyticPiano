# Identification Mixin Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 1185-line `exercise_sheet_identification.js` mixin into four responsibility-scoped AMD mixins, with zero behavior change.

**Architecture:** All four `exercise_sheet*` files are flat objects merged into `ExerciseSheetComponent.prototype` via `_.extend` in `exercise_sheet.js`. Methods cross-call through `this.`, so moving a method between mixin objects requires no dependency threading — only that every object reaches the same prototype. This split is therefore a verbatim method-move plus three new entries in the `_.extend` list. Mirrors the existing `exercise_sheet.js` 4-way split (commits ef67e14d / 6db347ed).

**Tech Stack:** RequireJS (AMD), jQuery, Lodash, VexFlow. No build step for source; browser loads `src/` modules directly. Pure-logic tests are plain Node scripts (`*.test.js`) run with `node`.

---

## Why this is a move-refactor, not a rewrite

The mixin has **no unit-test harness** of its own — it is an AMD module bound to jQuery, the DOM, VexFlow, and `this.exerciseContext`. The only JS tests in the repo (`*.test.js`) cover pure-logic modules (e.g. `identification_label_layout_logic.test.js`) and are run directly with `node`. They do **not** import this mixin and will neither catch nor be broken by the move.

Because there is no test that exercises the mixin, the safety net for this refactor is **a method-manifest guard**: snapshot the exact set of property names the original file defines, then assert after the split that the union of the four files defines the identical set — no drops, no duplicates, no renames. Method **bodies are moved verbatim** (cut exact line ranges, paste unchanged); retyping them would only introduce risk, so steps reference line ranges rather than reproducing ~1000 lines.

Final functional confirmation is manual: load an identification exercise in the running app and confirm dropdown + text input, grading, and figured-bass label rendering still work (Task 6).

## File Structure

| File | Responsibility | Methods |
|---|---|---|
| `exercise_sheet_identification.js` (stays, shrinks to ~135 lines) | Type predicates + answer-apply/lock flow | `_isIdentificationLikeExercise`, `_isChoraleIdentificationExercise`, `_isIdentificationProblemLocked`, `_applyIdentificationAnswer` |
| `exercise_sheet_identification_input_mode.js` (NEW, ~295 lines) | Text-vs-dropdown mode state, text-input component lifecycle, answer-data accessors | `_IDENT_INPUT_MODE_KEY`, `_getStoredIdentInputMode`, `_supportsTextInputMode`, `_getRepresentableTextHydrationAnswers`, `_getTextInputState`, `_getIdentInputMode`, `_setIdentInputMode`, `_buildInputComponent`, `_getVisibleIdentificationProblems`, `_getVisibleIdentificationAnswers`, `_getStoredIdentificationAnswer`, `_cloneIdentificationAnswers`, `_serializeIdentificationAnswersForText`, `_hydrateTextInputComponent`, `_captureFocusedTextInput`, `_restoreFocusedTextInput`, `_destroyIdentificationInputComponent`, `_syncIdentificationInputComponent` |
| `exercise_sheet_identification_canvas.js` (NEW, ~350 lines) | Canvas slot layout, choice popup, on-canvas label drawing | `_getIdentificationSlots`, `drawIdentificationLabels`, `_showIdentPopup`, `_closeIdentPopup` |
| `exercise_sheet_identification_controls.js` (NEW, ~230 lines) | Mode/UI toggles, progress bar, keyboard nav, submit, DOM container helpers, init | `_getIdentificationInputContainer`, `initIdentificationMode`, `_updateIdentificationProgressUI`, `onSubmitIdentification`, `_onIdentKeyDown`, `_getActiveIdentificationMode`, `_syncIdentificationModeState`, `_refreshIdentificationModeUI`, `_getIdentificationToggleRow`, `renderModeToggle`, `renderInputModeToggle`, `onToggleMode` |

**Dependency header:** Each new file copies the **identical full `define([...])` header and function-parameter list** from `exercise_sheet_identification.js` verbatim (lines 1-63). The sibling mixins (`exercise_sheet_status.js` etc.) already do this — they carry the full dep list regardless of what they use. Following that convention eliminates any risk of omitting a needed dependency. Do not prune the dep list.

**`_.bindAll` note:** `exercise_sheet.js:127` binds `onSubmitIdentification`, `onToggleMode`, `_onIdentKeyDown` — all three move to the controls mixin. `_.bindAll` runs against the already-merged prototype, so it keeps working with no change. Do not touch line 127.

---

## Task 0: Method-manifest guard script

**Files:**
- Create: `lab/static/js/test/identification_mixin_manifest.test.js`

This guard is the safety net for the whole refactor. It parses each mixin source file, extracts top-level property names, and asserts the union across the four files exactly equals the captured baseline from the pre-split file.

- [ ] **Step 1: Capture the baseline method set**

Run from repo root:

```bash
cd lab/static/js/src/components/music
grep -oE '^    [_a-zA-Z][_a-zA-Z0-9]*:' exercise_sheet_identification.js | sed 's/[: ]//g' | sort > /tmp/ident_baseline.txt
wc -l /tmp/ident_baseline.txt
```

Expected: 38 names (37 methods + `_IDENT_INPUT_MODE_KEY`). Record the list — it is the contract the split must preserve.

- [ ] **Step 2: Write the guard test**

Create `lab/static/js/test/identification_mixin_manifest.test.js`:

```javascript
"use strict";

// Structural guard for the identification mixin split.
// Asserts the four identification mixin files together define exactly the
// same set of property names, with no duplicates across files.
var assert = require("assert");
var fs = require("fs");
var path = require("path");

var DIR = path.join(__dirname, "..", "src", "components", "music");

var FILES = [
  "exercise_sheet_identification.js",
  "exercise_sheet_identification_input_mode.js",
  "exercise_sheet_identification_canvas.js",
  "exercise_sheet_identification_controls.js",
];

// Top-level mixin properties are indented exactly four spaces in these files.
var PROP_RE = /^ {4}([_a-zA-Z][_a-zA-Z0-9]*):/;

var EXPECTED = [
  "_IDENT_INPUT_MODE_KEY",
  "_applyIdentificationAnswer",
  "_buildInputComponent",
  "_captureFocusedTextInput",
  "_cloneIdentificationAnswers",
  "_closeIdentPopup",
  "_destroyIdentificationInputComponent",
  "_getActiveIdentificationMode",
  "_getIdentInputMode",
  "_getIdentificationInputContainer",
  "_getIdentificationSlots",
  "_getIdentificationToggleRow",
  "_getRepresentableTextHydrationAnswers",
  "_getStoredIdentInputMode",
  "_getStoredIdentificationAnswer",
  "_getTextInputState",
  "_getVisibleIdentificationAnswers",
  "_getVisibleIdentificationProblems",
  "_hydrateTextInputComponent",
  "_isChoraleIdentificationExercise",
  "_isIdentificationLikeExercise",
  "_isIdentificationProblemLocked",
  "_onIdentKeyDown",
  "_refreshIdentificationModeUI",
  "_restoreFocusedTextInput",
  "_serializeIdentificationAnswersForText",
  "_setIdentInputMode",
  "_showIdentPopup",
  "_supportsTextInputMode",
  "_syncIdentificationInputComponent",
  "_syncIdentificationModeState",
  "_updateIdentificationProgressUI",
  "drawIdentificationLabels",
  "initIdentificationMode",
  "onSubmitIdentification",
  "onToggleMode",
  "renderInputModeToggle",
  "renderModeToggle",
].sort();

var seen = {};
var duplicates = [];

FILES.forEach(function (file) {
  var full = path.join(DIR, file);
  if (!fs.existsSync(full)) {
    throw new Error("Missing mixin file: " + file);
  }
  var lines = fs.readFileSync(full, "utf8").split("\n");
  lines.forEach(function (line) {
    var m = PROP_RE.exec(line);
    if (!m) { return; }
    var name = m[1];
    if (seen[name]) {
      duplicates.push(name + " (in " + seen[name] + " and " + file + ")");
    }
    seen[name] = file;
  });
});

assert.strictEqual(duplicates.length, 0, "Duplicate properties: " + duplicates.join(", "));

var actual = Object.keys(seen).sort();
assert.deepStrictEqual(actual, EXPECTED,
  "Method set drift.\nMissing: " + EXPECTED.filter(function (n) { return actual.indexOf(n) < 0; }) +
  "\nUnexpected: " + actual.filter(function (n) { return EXPECTED.indexOf(n) < 0; }));

console.log("identification mixin manifest guard passed (" + actual.length + " properties across " + FILES.length + " files)");
```

- [ ] **Step 3: Run the guard — expect it to FAIL (new files absent)**

Run: `node lab/static/js/test/identification_mixin_manifest.test.js`
Expected: FAIL — `Error: Missing mixin file: exercise_sheet_identification_input_mode.js`. This confirms the guard actually checks for the new files.

- [ ] **Step 4: Commit the guard**

```bash
git add lab/static/js/test/identification_mixin_manifest.test.js
git commit -m "test: add structural guard for identification mixin split"
```

---

## Task 1: Extract input-mode + text-component + answer-data mixin

**Files:**
- Create: `lab/static/js/src/components/music/exercise_sheet_identification_input_mode.js`
- Modify: `lab/static/js/src/components/music/exercise_sheet_identification.js` (remove moved methods)

Methods to move (by current line range in `exercise_sheet_identification.js`):

| Method | Lines |
|---|---|
| `_IDENT_INPUT_MODE_KEY` | 76 |
| `_getStoredIdentInputMode` | 78-90 |
| `_supportsTextInputMode` | 92-116 |
| `_getRepresentableTextHydrationAnswers` | 118-137 |
| `_getTextInputState` | 139-155 |
| `_getIdentInputMode` | 157-165 |
| `_setIdentInputMode` | 167-175 |
| `_buildInputComponent` | 177-198 |
| `_getVisibleIdentificationProblems` | 200-204 |
| `_getVisibleIdentificationAnswers` | 215-243 |
| `_getStoredIdentificationAnswer` | 245-260 |
| `_cloneIdentificationAnswers` | 262-275 |
| `_serializeIdentificationAnswersForText` | 277-281 |
| `_hydrateTextInputComponent` | 283-304 |
| `_captureFocusedTextInput` | 306-320 |
| `_restoreFocusedTextInput` | 322-335 |
| `_destroyIdentificationInputComponent` | 337-344 |
| `_syncIdentificationInputComponent` | 346-395 |

- [ ] **Step 1: Create the new file scaffold**

Copy lines 1-63 (the `/* global define */` comment, the full `define([...])` dep array, the function parameter list, and `"use strict";`) **verbatim** from `exercise_sheet_identification.js` into the new file. Then add `return {` and the moved methods, closing with `};\n});`. Scaffold shape:

```javascript
/* global define: false */
define([
  /* ...identical dependency strings copied verbatim from exercise_sheet_identification.js lines 2-31... */
], function (
  /* ...identical parameter list copied verbatim from lines 32-62... */
) {
  "use strict";

  return {
    // <-- moved methods pasted here, verbatim, in the table order above
  };
});
```

- [ ] **Step 2: Move the method bodies verbatim**

Cut each method listed above from `exercise_sheet_identification.js` and paste it (unchanged, including its leading doc comments and trailing comma) into the `return { ... }` of the new file. Do not edit any body. Preserve four-space indentation so the manifest guard's `/^ {4}.../`  regex still matches.

- [ ] **Step 3: Wire the new mixin into the prototype**

In `exercise_sheet.js`, add the dependency string. Change lines 32-35 from:

```javascript
  "./exercise_sheet_identification",
  "./exercise_sheet_status",
  "./exercise_sheet_staves",
  "./exercise_sheet_playback",
```

to:

```javascript
  "./exercise_sheet_identification",
  "./exercise_sheet_identification_input_mode",
  "./exercise_sheet_status",
  "./exercise_sheet_staves",
  "./exercise_sheet_playback",
```

Add the matching parameter. Change lines 66-69 from:

```javascript
  ExerciseSheetIdentification,
  ExerciseSheetStatus,
  ExerciseSheetStaves,
  ExerciseSheetPlayback
```

to:

```javascript
  ExerciseSheetIdentification,
  ExerciseSheetIdentificationInputMode,
  ExerciseSheetStatus,
  ExerciseSheetStaves,
  ExerciseSheetPlayback
```

Add it to the `_.extend` list. Change lines 133-137 from:

```javascript
    ExerciseSheetComponent.prototype,
    ExerciseSheetIdentification,
    ExerciseSheetStatus,
    ExerciseSheetStaves,
    ExerciseSheetPlayback,
```

to:

```javascript
    ExerciseSheetComponent.prototype,
    ExerciseSheetIdentification,
    ExerciseSheetIdentificationInputMode,
    ExerciseSheetStatus,
    ExerciseSheetStaves,
    ExerciseSheetPlayback,
```

- [ ] **Step 4: Lint both edited source files for syntax**

Run: `node --check lab/static/js/src/components/music/exercise_sheet_identification_input_mode.js && node --check lab/static/js/src/components/music/exercise_sheet_identification.js && node --check lab/static/js/src/components/music/exercise_sheet.js`
Expected: no output (exit 0). `node --check` parses without executing — it validates that the `define(...)` wrapper and method bodies are syntactically intact even though `define` is not a Node global.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet_identification_input_mode.js lab/static/js/src/components/music/exercise_sheet_identification.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "refactor: extract identification input-mode mixin"
```

---

## Task 2: Extract canvas mixin (slots, popup, label drawing)

**Files:**
- Create: `lab/static/js/src/components/music/exercise_sheet_identification_canvas.js`
- Modify: `lab/static/js/src/components/music/exercise_sheet_identification.js`

Methods to move (include each method's leading doc comment block):

| Method | Lines (incl. preceding doc comment) |
|---|---|
| `_showIdentPopup` | 653-689 |
| `_closeIdentPopup` | 691-697 |
| `_getIdentificationSlots` | 699-742 |
| `drawIdentificationLabels` | 744-998 |

- [ ] **Step 1: Create the new file scaffold**

Same scaffold as Task 1, Step 1: copy lines 1-63 verbatim from `exercise_sheet_identification.js`, then `return { ... };\n});`.

- [ ] **Step 2: Move the method bodies verbatim**

Cut the four methods (with their doc comments) from `exercise_sheet_identification.js` into the new file's `return {}`. Do not modify bodies — the leftover `console.log("[ID]...")` debug lines inside `drawIdentificationLabels` move **as-is**; they are addressed in the follow-up plan (see "Deferred" below), not here.

- [ ] **Step 3: Wire into the prototype**

In `exercise_sheet.js`, after the `"./exercise_sheet_identification_input_mode"` line add:

```javascript
  "./exercise_sheet_identification_canvas",
```

After the `ExerciseSheetIdentificationInputMode,` parameter add:

```javascript
  ExerciseSheetIdentificationCanvas,
```

After the `ExerciseSheetIdentificationInputMode,` entry in the `_.extend` list add:

```javascript
    ExerciseSheetIdentificationCanvas,
```

- [ ] **Step 4: Syntax check**

Run: `node --check lab/static/js/src/components/music/exercise_sheet_identification_canvas.js && node --check lab/static/js/src/components/music/exercise_sheet_identification.js && node --check lab/static/js/src/components/music/exercise_sheet.js`
Expected: no output (exit 0).

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet_identification_canvas.js lab/static/js/src/components/music/exercise_sheet_identification.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "refactor: extract identification canvas mixin"
```

---

## Task 3: Extract controls mixin (mode/UI, progress, keyboard, submit, init)

**Files:**
- Create: `lab/static/js/src/components/music/exercise_sheet_identification_controls.js`
- Modify: `lab/static/js/src/components/music/exercise_sheet_identification.js`

Methods to move (include leading doc comments):

| Method | Lines (incl. preceding doc comment) |
|---|---|
| `_getIdentificationInputContainer` | 206-213 |
| `initIdentificationMode` | 515-651 |
| `_updateIdentificationProgressUI` | 1000-1083 |
| `onSubmitIdentification` | 1085-1091 |
| `_onIdentKeyDown` | 1093-1103 |
| `_getActiveIdentificationMode` | 1105-1110 |
| `_syncIdentificationModeState` | 1112-1115 |
| `_refreshIdentificationModeUI` | 1117-1151 |
| `_getIdentificationToggleRow` | 1153-1160 |
| `renderModeToggle` | 1162-1196 |
| `renderInputModeToggle` | 1198-1238 |
| `onToggleMode` | 1240-1249 |

After this task, `exercise_sheet_identification.js` retains only: `_isIdentificationLikeExercise`, `_isChoraleIdentificationExercise`, `_isIdentificationProblemLocked`, `_applyIdentificationAnswer`.

- [ ] **Step 1: Create the new file scaffold**

Same scaffold as Task 1, Step 1.

- [ ] **Step 2: Move the method bodies verbatim**

Cut the twelve methods (with doc comments) into the new file's `return {}`. Do not modify bodies. Note `onSubmitIdentification`, `onToggleMode`, `_onIdentKeyDown` are named in `exercise_sheet.js:127` `_.bindAll` — that line stays untouched and continues to bind them on the merged prototype.

- [ ] **Step 3: Wire into the prototype**

In `exercise_sheet.js`, after `"./exercise_sheet_identification_canvas"` add:

```javascript
  "./exercise_sheet_identification_controls",
```

After the `ExerciseSheetIdentificationCanvas,` parameter add:

```javascript
  ExerciseSheetIdentificationControls,
```

After the `ExerciseSheetIdentificationCanvas,` entry in the `_.extend` list add:

```javascript
    ExerciseSheetIdentificationControls,
```

- [ ] **Step 4: Syntax check**

Run: `node --check lab/static/js/src/components/music/exercise_sheet_identification_controls.js && node --check lab/static/js/src/components/music/exercise_sheet_identification.js && node --check lab/static/js/src/components/music/exercise_sheet.js`
Expected: no output (exit 0).

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet_identification_controls.js lab/static/js/src/components/music/exercise_sheet_identification.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "refactor: extract identification controls mixin"
```

---

## Task 4: Verify the manifest guard passes

**Files:**
- Test: `lab/static/js/test/identification_mixin_manifest.test.js`

- [ ] **Step 1: Run the guard**

Run: `node lab/static/js/test/identification_mixin_manifest.test.js`
Expected: PASS — `identification mixin manifest guard passed (38 properties across 4 files)`.

- [ ] **Step 2: If it fails**

The error names missing/unexpected/duplicate properties. Fix by moving the named method to its planned file (no renames, no drops). Re-run until green. Do not edit `EXPECTED` to match reality — the array IS the contract.

---

## Task 5: Run the full JS logic-test suite (regression)

Confirms the move did not disturb any sibling pure-logic module.

- [ ] **Step 1: Run every `*.test.js`**

Run from repo root:

```bash
find lab/static/js -name "*.test.js" -print0 | xargs -0 -n1 node
```

Expected: each prints its own `... tests passed` / guard-passed line and exits 0; no stack traces. (29 pre-existing test files plus the new guard.)

- [ ] **Step 2: Confirm the original file shrank as planned**

Run: `wc -l lab/static/js/src/components/music/exercise_sheet_identification.js`
Expected: ~135 lines (down from 1251). Confirm only the four core methods remain:

Run: `grep -oE '^    [_a-zA-Z][_a-zA-Z0-9]*:' lab/static/js/src/components/music/exercise_sheet_identification.js`
Expected exactly: `_isIdentificationLikeExercise`, `_isChoraleIdentificationExercise`, `_isIdentificationProblemLocked`, `_applyIdentificationAnswer`.

---

## Task 6: Manual in-app smoke test

The mixin has no automated DOM coverage, so a human/agent must load the running app once.

- [ ] **Step 1: Launch the app**

Use the `run-harmonylab` skill (or `/run`) to start the local server.

- [ ] **Step 2: Open a Roman-numeral identification exercise**

Confirm:
- "?" slots render under the bass staff.
- Clicking a slot opens the choice popup; selecting an answer draws the label.
- The Click/Type toggle appears and switching to Type shows the text field; typing answers grades them.
- Practice mode shows ✓/✗ immediately; Submit mode shows the progress bar + Check button.

- [ ] **Step 3: Open a figured-bass identification exercise**

Confirm stacked figured-bass labels render in the Sebastian font (the `drawIdentificationLabels` formatting block at original lines 953-975).

- [ ] **Step 4: Open a chorale identification exercise**

Confirm window-based slot placement still works (the `_identWindowLayout` branch of `_getIdentificationSlots`).

- [ ] **Step 5: Final diff review + worktree status**

Run: `git log --oneline master..HEAD` and `git status`
Expected: four refactor commits + one test commit; clean working tree. Per CLAUDE.md, inspect the final diff before reporting completion.

---

## Deferred to next round: decompose `drawIdentificationLabels`

`drawIdentificationLabels` (original lines 744-998, **~254 lines** — by far the largest method) is moved **verbatim** in this plan and is **not** decomposed here. It carries three distinct problems that warrant a dedicated follow-up plan:

1. **Single 254-line method doing four jobs.** It interleaves: (a) a text-mode early-return branch that also drives the submit progress UI (lines ~751-762); (b) a key-change-label pass over all slots using `KeyContext` (lines ~814-831 plus the nested `drawKeyChangeLabel` closure at ~797-812); (c) a per-slot loop resolving answer text, answered/graded/review colour state, ✓/✗ markers, and auto-scroll (lines ~833-918); and (d) analysis-type-specific label rendering — the figured-bass Sebastian-font stacking and the plain JazzSerifs path (lines ~951-981). Each is a candidate for its own named helper, ideally pure functions that take a slot + state and return draw instructions, leaving `drawIdentificationLabels` as a thin orchestrator.

2. **Leftover debug logging runs every render.** Roughly nine `console.log("[ID] ...")` statements (original lines ~746-747, ~750-752, ~792-795, ~851) fire on every redraw of every identification exercise — console noise and a small perf cost in the hot render path. The follow-up should strip them (or gate them behind a debug flag).

3. **Figured-bass formatter is duplicated logic.** The `lines.map(...)` block at ~953-975 converts answer text to Sebastian-font glyphs and, per its own inline comment, "mirrors `stave_notater.drawThoroughbass`." That accidental-symbol/font mapping should be extracted into a shared, unit-testable util (e.g. alongside `identification_label_layout_logic.js`, which already has a `.test.js`) and called from both sites — removing the duplication and giving the figured-bass mapping real test coverage.

Doing (3) first yields a pure function with tests; (1) and (2) then shrink the method against a green guard. That sequencing belongs in its own plan, written after this split lands.

---

## Self-Review notes

- **Spec coverage:** All 38 original properties are assigned to exactly one destination file (4 core + 18 input-mode + 4 canvas + 12 controls = 38); the Task 0 `EXPECTED` array enumerates all 38 and is the enforced contract.
- **Type consistency:** New mixin variable names (`ExerciseSheetIdentificationInputMode`, `...Canvas`, `...Controls`) are used identically in the dep string, the parameter list, and the `_.extend` call within each task.
- **No behavior change intended:** every method body is moved verbatim; the only logic edits in the whole plan are additive (`_.extend` list, dep arrays). `console.log` removal and method decomposition are explicitly deferred.
