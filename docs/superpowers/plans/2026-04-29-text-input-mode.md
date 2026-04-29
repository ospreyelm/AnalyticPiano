# Text Input Mode for Pitch Identification — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typing-based input mode to pitch identification exercises so fluent students can type space-separated note names instead of clicking dropdowns, with a student-controlled toggle that persists via localStorage.

**Architecture:** New `TextInputComponent` mirrors the interface of `LabelInputComponent` (same `render` / `updatePositions` / `onAnswer` / `destroy` contract) so `exercise_sheet.js` can swap them with minimal branching. A segmented Click/Type toggle rendered by `exercise_sheet.js` writes the student preference to `localStorage`. The UMTO `Metadata` model gains an `input_mode` field so teachers can set the default.

**Tech Stack:** Python/Pydantic (UMTO model), Django (management command, dashboard template), RequireJS AMD modules (JS components), jQuery, existing VexFlow/canvas identification rendering pipeline.

---

## File Map

| File | Role |
|------|------|
| `apps/exercises/umto.py` | Add `input_mode: Literal["dropdown","text"] = "dropdown"` to `Metadata` |
| `apps/exercises/umto_schema.json` | Regenerated — no manual edits |
| `apps/exercises/management/commands/generate_unit1.py` | New `--input-mode` CLI flag |
| `apps/exercises/tests/test_umto_factory.py` | Test `input_mode` round-trip |
| `apps/dashboard/templates/dashboard/edit-exercise.html` | Input mode select in pitch-duplicate modal |
| `lab/static/js/src/components/input/label_input.js` | Add `destroy()` method |
| `lab/static/js/src/components/input/text_input.js` | New component (parser + DOM) |
| `lab/static/js/src/models/exercise_definition.js` | Add `getInputMode()` helper |
| `lab/static/js/src/components/music/exercise_sheet.js` | Read inputMode, render toggle, swap components |

---

## Task 1: Add `input_mode` to UMTO `Metadata`

**Files:**
- Modify: `apps/exercises/umto.py:80-88`
- Modify: `apps/exercises/umto.py:170-199` (payload serialisation)
- Test: `apps/exercises/tests/test_umto_factory.py`

- [ ] **Step 1: Write the failing test**

Add to `apps/exercises/tests/test_umto_factory.py`:

```python
def test_input_mode_defaults_to_dropdown(umto_exercise_factory):
    """input_mode defaults to 'dropdown' — existing exercises unaffected."""
    ex = umto_exercise_factory()
    umto = ex.data["umto"]
    assert umto["metadata"]["input_mode"] == "dropdown"

def test_input_mode_text_round_trips(umto_exercise_factory):
    """input_mode='text' survives save/load."""
    ex = umto_exercise_factory(input_mode="text")
    umto = ex.data["umto"]
    assert umto["metadata"]["input_mode"] == "text"

def test_input_mode_in_exercise_payload(umto_exercise_factory):
    """to_exercise_definition_payload() includes inputMode."""
    ex = umto_exercise_factory(input_mode="text")
    from apps.exercises.umto import UMTO
    umto_obj = UMTO.model_validate(ex.data["umto"])
    payload = umto_obj.to_exercise_definition_payload()
    assert payload["inputMode"] == "text"
```

Note: `umto_exercise_factory` is a pytest fixture — check `apps/exercises/tests/umto_test_helpers.py` for the existing factory and add `input_mode` kwarg support there.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test apps.exercises.tests.test_umto_factory --verbosity=2 2>&1 | grep -E "FAIL|ERROR|input_mode"
```

Expected: `AttributeError: 'Metadata' object has no attribute 'input_mode'` or similar.

- [ ] **Step 3: Add `input_mode` to `Metadata` in `apps/exercises/umto.py`**

In `apps/exercises/umto.py`, change `Metadata` (lines 80–88) from:

```python
class Metadata(BaseModel):
    exercise_id: str
    source: str
    key: str
    meter: str
    clef: str = "treble"
    complexity_score: int = Field(ge=1, le=12, description="Unit 1-12 ranking system")
    mode: InteractionMode = InteractionMode.PLAYBACK
    is_umto: bool = True
```

to:

```python
from typing import Literal  # add to existing imports at top of file

class Metadata(BaseModel):
    exercise_id: str
    source: str
    key: str
    meter: str
    clef: str = "treble"
    complexity_score: int = Field(ge=1, le=12, description="Unit 1-12 ranking system")
    mode: InteractionMode = InteractionMode.PLAYBACK
    is_umto: bool = True
    input_mode: Literal["dropdown", "text"] = "dropdown"
```

- [ ] **Step 4: Add `inputMode` to `to_exercise_definition_payload()` in `apps/exercises/umto.py`**

In the `to_exercise_definition_payload` method (around line 184), add `"inputMode"` to the returned dict:

```python
return {
    "type": "umto_chorale",
    "isUMTO": True,
    "mode": self.metadata.mode.value if hasattr(self.metadata.mode, 'value') else self.metadata.mode,
    "staffDistribution": self.metadata.clef,
    "complexity_score": self.metadata.complexity_score,
    "exerciseId": self.metadata.exercise_id,
    "key": self.metadata.key,
    "meter": self.metadata.meter,
    "clef": self.metadata.clef,
    "semibrevesPerLine": 4,
    "analysisType": "note_name" if self.metadata.complexity_score == 1 else "roman",
    "introText": self.metadata.source,
    "reviewText": "Well done!",
    "inputMode": self.metadata.input_mode,
    "allowed_answers": self.get_allowed_answers(unit),
    "score": {
        "meta": {
            "key": self.metadata.key,
            "time": self.metadata.meter,
            "clef": self.metadata.clef,
            "staffDistribution": self.metadata.clef
        },
        "measures": self._to_legacy_measures(),
        "umto": self.model_dump()
    },
    "grading": [s.model_dump() for s in self.grading]
}
```

- [ ] **Step 5: Update `umto_test_helpers.py` factory to accept `input_mode`**

In `apps/exercises/tests/umto_test_helpers.py`, find the factory helper (look for a function that calls `save_umto_exercise`) and add `input_mode="dropdown"` as a kwarg, passing it through to `umto_kwargs`. Example — if the factory looks like:

```python
def make_umto_exercise(mode=InteractionMode.IDENTIFICATION, ...):
    return save_umto_exercise(
        ...,
        umto_kwargs=dict(exercise_id="TEST", source="test", key="C", meter="4/4",
                         clef="treble", complexity_score=1, mode=mode)
    )
```

Change to:

```python
def make_umto_exercise(mode=InteractionMode.IDENTIFICATION, input_mode="dropdown", ...):
    return save_umto_exercise(
        ...,
        umto_kwargs=dict(exercise_id="TEST", source="test", key="C", meter="4/4",
                         clef="treble", complexity_score=1, mode=mode, input_mode=input_mode)
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python manage.py test apps.exercises.tests.test_umto_factory --verbosity=2 2>&1 | grep -E "OK|FAIL|ERROR"
```

Expected: all three new tests pass.

- [ ] **Step 7: Regenerate schema**

```bash
python manage.py make_umto_schema
```

Expected: `apps/exercises/umto_schema.json` updated — `input_mode` appears under `metadata.properties`.

- [ ] **Step 8: Commit**

```bash
git add apps/exercises/umto.py apps/exercises/umto_schema.json apps/exercises/tests/test_umto_factory.py apps/exercises/tests/umto_test_helpers.py
git commit -m "feat: add input_mode field to UMTO Metadata"
```

---

## Task 2: Add `--input-mode` flag to `generate_unit1` command

**Files:**
- Modify: `apps/exercises/management/commands/generate_unit1.py`

- [ ] **Step 1: Add the argument**

In `apps/exercises/management/commands/generate_unit1.py`, find `add_arguments` (around line 265) and add after the existing `--file` argument:

```python
parser.add_argument(
    "--input-mode",
    choices=["dropdown", "text"],
    default="dropdown",
    help="Default input mode for identification exercises (dropdown or text).",
)
```

- [ ] **Step 2: Thread the value to `umto_kwargs` for identification exercises**

Search the file for the `InteractionMode.IDENTIFICATION` calls (around lines 563 and 584). Both calls build `umto_kwargs` — add `input_mode=options["input_mode"]` to each. Example, before:

```python
umto_kwargs=dict(
    exercise_id="TEMP",
    source=...,
    key=...,
    meter=...,
    clef=...,
    complexity_score=...,
    mode=InteractionMode.IDENTIFICATION,
    target_voice=...,
),
```

After:

```python
umto_kwargs=dict(
    exercise_id="TEMP",
    source=...,
    key=...,
    meter=...,
    clef=...,
    complexity_score=...,
    mode=InteractionMode.IDENTIFICATION,
    target_voice=...,
    input_mode=options["input_mode"],
),
```

- [ ] **Step 3: Verify the flag is wired (dry-run)**

```bash
python manage.py generate_unit1 --author admin@example.com --lane identification --input-mode text --dry-run 2>&1 | head -20
```

Expected: command runs without error, prints dry-run output.

- [ ] **Step 4: Commit**

```bash
git add apps/exercises/management/commands/generate_unit1.py
git commit -m "feat: add --input-mode flag to generate_unit1 command"
```

---

## Task 3: Add `input_mode` select to dashboard pitch-duplicate modal

**Files:**
- Modify: `apps/dashboard/templates/dashboard/edit-exercise.html:1-44`

- [ ] **Step 1: Add the select field to the modal**

In `apps/dashboard/templates/dashboard/edit-exercise.html`, find the `pitch-duplicate-modal` dialog (around line 6). After the `identMode` select block (lines 22–29), add:

```html
<div style="margin-bottom: 10px;">
    <label for="pitch-input-mode" style="margin-right: 6px;">Input mode:</label>
    <select id="pitch-input-mode" name="inputMode">
        <option value="dropdown">Dropdown (click)</option>
        <option value="text">Text (type)</option>
    </select>
</div>
```

- [ ] **Step 2: Wire the value in `apps/dashboard/views/exercises.py`**

In `apps/dashboard/views/exercises.py`, find the `duplicate-as-pitch-identification` branch (around line 218). After the `ident_mode` line (line 222), add:

```python
input_mode = request.POST.get("inputMode", "dropdown")
if input_mode not in ("dropdown", "text"):
    input_mode = "dropdown"
```

Then in the `umto_kwargs` dict passed to `save_umto_exercise` (around line 245), add:

```python
input_mode=input_mode,
```

- [ ] **Step 3: Manual verification**

Open the dashboard, navigate to a chorale exercise, open "Duplicate as Pitch Identification" modal — confirm "Input mode" dropdown appears. Select "Text", create — confirm the saved exercise has `data["umto"]["metadata"]["input_mode"] == "text"` in Django shell:

```python
from apps.exercises.models import Exercise
ex = Exercise.objects.last()
ex.data["umto"]["metadata"]["input_mode"]  # should be "text"
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/templates/dashboard/edit-exercise.html apps/dashboard/views/exercises.py
git commit -m "feat: add input_mode selector to pitch-identification duplicate modal"
```

---

## Task 4: Add `destroy()` to `LabelInputComponent`

**Files:**
- Modify: `lab/static/js/src/components/input/label_input.js:131`

- [ ] **Step 1: Add `destroy()` after `lockCorrect()`**

In `lab/static/js/src/components/input/label_input.js`, before the closing `});` of the `_.extend` block (line 131), add:

```javascript
/**
 * Removes all select elements and unbinds events. Called when swapping to text input mode.
 */
destroy: function () {
  _.each(this.selects, function (sel) {
    sel.off();
    sel.remove();
  });
  this.selects = [];
},
```

- [ ] **Step 2: Commit**

```bash
git add lab/static/js/src/components/input/label_input.js
git commit -m "feat: add destroy() to LabelInputComponent for component swap support"
```

---

## Task 5: Add `getInputMode()` to `ExerciseDefinition`

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js` (near `getAnalysisType`, around line 816)

- [ ] **Step 1: Add the helper**

In `lab/static/js/src/models/exercise_definition.js`, after `getAnalysisType` (around line 818), add:

```javascript
/**
 * Returns the default input mode for identification exercises.
 * "dropdown" = click-based label selects (default)
 * "text"     = single text box, space-separated answers
 *
 * @return {string}
 */
getInputMode: function () {
  return this.exercise.inputMode || "dropdown";
},
```

- [ ] **Step 2: Verify `inputMode` is parsed from UMTO payload**

In `lab/static/js/src/models/exercise_definition.js`, find where UMTO exercise fields are parsed from `definition` (around line 920–965). After the `exercise.analysisType` line (around line 928), add:

```javascript
exercise.inputMode = definition.inputMode || (definition.score && definition.score.umto && definition.score.umto.metadata && definition.score.umto.metadata.input_mode) || "dropdown";
```

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "feat: add getInputMode() to ExerciseDefinition"
```

---

## Task 6: Build `TextInputComponent`

**Files:**
- Create: `lab/static/js/src/components/input/text_input.js`

- [ ] **Step 1: Create the file**

Create `lab/static/js/src/components/input/text_input.js`:

```javascript
define([
  "jquery",
  "lodash",
  "app/components/component",
], function ($, _, Component) {
  "use strict";

  var VALID_NOTE_RE = /^[A-Ga-g](#{1,2}|b{1,2})?$/;

  var NORMALIZE_MAP = {
    "cb": "Cb", "db": "Db", "eb": "Eb", "fb": "Fb", "gb": "Gb", "ab": "Ab", "bb": "Bb",
    "c#": "C#", "d#": "D#", "e#": "E#", "f#": "F#", "g#": "G#", "a#": "A#", "b#": "B#",
    "c##": "C##", "d##": "D##", "f##": "F##", "g##": "G##", "a##": "A##",
    "cbb": "Cbb", "dbb": "Dbb", "ebb": "Ebb", "gbb": "Gbb", "abb": "Abb",
    "c": "C", "d": "D", "e": "E", "f": "F", "g": "G", "a": "A", "b": "B"
  };

  /**
   * TextInputComponent
   *
   * Renders a single fused <input>+<button> pill for space-separated note-name answers.
   * Mirrors the external interface of LabelInputComponent.
   *
   * @constructor
   * @param {object}   settings
   * @param {jQuery}   settings.containerEl  - Element to append the pill into.
   * @param {number}   settings.problemCount - Expected number of answers.
   * @param {string}   settings.feedbackMode - "practice" or "submit".
   * @param {function} settings.onAnswer     - Callback fn(problemIndex, normalizedLabel).
   */
  var TextInputComponent = function (settings) {
    this.settings = settings || {};
    this.containerEl = this.settings.containerEl;
    this.problemCount = this.settings.problemCount || 0;
    this.feedbackMode = this.settings.feedbackMode || "submit";
    this.onAnswer = this.settings.onAnswer || function () {};
    this._prevTokens = [];
    this._fieldEl = null;
    this._pillEl = null;
  };

  TextInputComponent.prototype = new Component();

  _.extend(TextInputComponent.prototype, {
    initComponent: function () {},

    /**
     * Normalise a raw token string to title-case note name, or null if invalid.
     * e.g. "bb" -> "Bb", "F#" -> "F#", "bbb" -> null
     */
    _normalizeToken: function (raw) {
      if (!raw) { return null; }
      var lower = raw.toLowerCase();
      if (NORMALIZE_MAP[lower]) { return NORMALIZE_MAP[lower]; }
      // Fallback: capitalise first letter, keep rest
      var candidate = raw.charAt(0).toUpperCase() + raw.slice(1);
      return VALID_NOTE_RE.test(candidate) ? candidate : null;
    },

    /**
     * Split input string into valid note-name tokens.
     * Invalid tokens are skipped without advancing the problem index.
     * Returns array of {index, value} — index is the 0-based problem slot.
     *
     * @param {string} str
     * @returns {Array<{index: number, value: string}>}
     */
    _parseTokens: function (str) {
      var self = this;
      var raw = (str || "").trim().split(/\s+/);
      var results = [];
      var problemIndex = 0;
      for (var i = 0; i < raw.length; i++) {
        if (problemIndex >= self.problemCount) { break; }
        var norm = self._normalizeToken(raw[i]);
        if (norm) {
          results.push({ index: problemIndex, value: norm });
          problemIndex++;
        }
      }
      return results;
    },

    /**
     * Fire onAnswer for tokens that changed since last parse (practice mode).
     */
    _fireNewAnswers: function (tokens) {
      var self = this;
      _.each(tokens, function (t) {
        var prev = self._prevTokens[t.index];
        if (prev !== t.value) {
          self.onAnswer(t.index, t.value);
        }
      });
      // Build sparse array for comparison on next call
      var arr = [];
      _.each(tokens, function (t) { arr[t.index] = t.value; });
      self._prevTokens = arr;
    },

    render: function () {
      var self = this;
      if (this._pillEl) { this._pillEl.remove(); }

      var $pill = $('<div class="text-id-pill"></div>');
      var $field = $('<input type="text" class="text-id-field" autocomplete="off" spellcheck="false" />')
        .attr("placeholder", "e.g. C D E F G");
      var $btn = $('<button type="button" class="text-id-check">Check ↵</button>');
      var $hint = $('<div class="text-id-hint">Space-separated · Bb and F# ok</div>');
      var $wrap = $('<div class="text-id-input"></div>');

      $pill.append($field).append($btn);
      $wrap.append($pill).append($hint);

      if (this.feedbackMode === "practice") {
        $field.on("input", function () {
          var raw = $(this).val();
          // In practice mode, fire answers for tokens followed by a space,
          // OR when token count reaches expected problem count.
          var endsWithSpace = /\s$/.test(raw);
          var tokens = self._parseTokens(raw);
          var shouldFire = endsWithSpace || tokens.length >= self.problemCount;
          if (shouldFire) {
            self._fireNewAnswers(tokens);
          }
        });
        $field.on("keydown", function (e) {
          if (e.key === "Enter") {
            var tokens = self._parseTokens($(this).val());
            self._fireNewAnswers(tokens);
          }
        });
      }

      $btn.on("click", function () {
        var tokens = self._parseTokens($field.val());
        if (self.feedbackMode === "practice") {
          self._fireNewAnswers(tokens);
        } else {
          // submit mode: fire all at once
          _.each(tokens, function (t) { self.onAnswer(t.index, t.value); });
        }
      });

      $field.on("keydown", function (e) {
        if (e.key === "Enter" && self.feedbackMode === "submit") {
          var tokens = self._parseTokens($(this).val());
          _.each(tokens, function (t) { self.onAnswer(t.index, t.value); });
        }
      });

      this._fieldEl = $field;
      this._pillEl = $wrap;
      this.containerEl.append($wrap);
      return this;
    },

    /** No-op — text input has fixed position, not per-stave. */
    updatePositions: function () {},

    /** No-op — results shown via canvas slot rendering, not on this component. */
    showResults: function () {},

    /** No-op — no individual slots to lock. */
    lockCorrect: function () {},

    destroy: function () {
      if (this._pillEl) {
        this._pillEl.off();
        if (this._fieldEl) { this._fieldEl.off(); }
        this._pillEl.remove();
        this._pillEl = null;
        this._fieldEl = null;
      }
      this._prevTokens = [];
    }
  });

  return TextInputComponent;
});
```

- [ ] **Step 2: Add CSS for the pill**

CSS lives inline-injected in `exercise_sheet.js` (the codebase pattern — see `ident-toggle-css` injection around line 770). This CSS will be added in Task 7, not here.

- [ ] **Step 3: Write unit tests for `_parseTokens` and `_normalizeToken`**

Create `lab/static/js/test/text_input_test.js` (or add to existing JS test file if one exists — check `lab/static/js/test/`):

```javascript
// Manual test — run in browser console by loading the module, or adapt to QUnit/Jasmine if project uses them.
// Check: does the project have a JS test runner?
// Run: grep -r "QUnit\|jasmine\|mocha" lab/static/js/ --include="*.js" -l

// If no runner, document expected behaviour in comments and rely on integration testing.
// _parseTokens("c d e f") -> [{index:0,value:"C"},{index:1,value:"D"},{index:2,value:"E"},{index:3,value:"F"}]
// _parseTokens("bb f# Eb") -> [{index:0,value:"Bb"},{index:1,value:"F#"},{index:2,value:"Eb"}]
// _parseTokens("H bbb Q") -> [] (all invalid, skipped)
// _parseTokens("c H d") -> [{index:0,value:"C"},{index:1,value:"D"}] (H skipped, D gets index 1)
// _normalizeToken("bb") -> "Bb"
// _normalizeToken("BB") -> "Bb"
// _normalizeToken("bbb") -> null
// _normalizeToken("H") -> null
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/input/text_input.js
git commit -m "feat: add TextInputComponent for typed note-name identification"
```

---

## Task 7: Wire `TextInputComponent` into `exercise_sheet.js`

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

This is the integration task. `exercise_sheet.js` currently uses `LabelInput` via the `label_input` module loaded at the top. We add `TextInput`, a localStorage-aware factory, a segmented toggle, and CSS.

- [ ] **Step 1: Add `TextInput` to the define() imports**

At the top of `lab/static/js/src/components/music/exercise_sheet.js`, find the `define([...` array (line 1 area). Add `"app/components/input/text_input"` to the array and `TextInput` to the corresponding function parameter. Example — before:

```javascript
define([
  ...
  "app/components/input/label_input",
  ...
], function (..., LabelInput, ...) {
```

After:

```javascript
define([
  ...
  "app/components/input/label_input",
  "app/components/input/text_input",
  ...
], function (..., LabelInput, TextInput, ...) {
```

- [ ] **Step 2: Add localStorage helpers and input component factory**

Find `initIdentificationMode` (around line 196). Just before it, add these helpers:

```javascript
_IDENT_INPUT_MODE_KEY: "harmonylab.identInputMode",

_getIdentInputMode: function (definition) {
  var stored = null;
  try { stored = localStorage.getItem(this._IDENT_INPUT_MODE_KEY); } catch (e) {}
  return stored || (definition.getInputMode ? definition.getInputMode() : "dropdown");
},

_setIdentInputMode: function (mode) {
  try { localStorage.setItem(this._IDENT_INPUT_MODE_KEY, mode); } catch (e) {}
},

_buildInputComponent: function (mode, containerEl, problems, feedbackMode, onAnswer) {
  if (mode === "text") {
    return new TextInput({
      containerEl: containerEl,
      problemCount: problems.length,
      feedbackMode: feedbackMode,
      onAnswer: onAnswer
    });
  }
  return new LabelInput({
    containerEl: containerEl,
    problems: problems,
    onAnswer: onAnswer
  });
},
```

- [ ] **Step 3: Add `renderInputModeToggle()` method**

After `renderModeToggle` (around line 758), add:

```javascript
renderInputModeToggle: function (currentMode, onSwitch) {
  var self = this;
  var $existing = $("#ident-input-toggle-container");
  if ($existing.length) { $existing.remove(); }

  var $container = $('<div id="ident-input-toggle-container" class="ident-mode-toggle" style="margin-top:8px;"></div>');
  var $switch = $('<div class="mode-switch"></div>');

  var modes = [
    { id: "dropdown", label: "🖱 Click" },
    { id: "text",     label: "⌨ Type"  }
  ];

  _.each(modes, function (m) {
    var $opt = $('<span class="mode-option"></span>').text(m.label);
    if (m.id === currentMode) { $opt.addClass("active"); }
    $opt.on("click", function () {
      if (m.id !== currentMode) { onSwitch(m.id); }
    });
    $switch.append($opt);
  });

  $container.append($switch);
  // Insert above the Practice/Submit toggle (#ident-mode-container)
  var $modeContainer = $("#ident-mode-container");
  if ($modeContainer.length) {
    $modeContainer.before($container);
  } else {
    $("#identification-actions").append($container);
  }
},
```

- [ ] **Step 4: Inject CSS for the pill (once)**

In `_refreshIdentificationModeUI` (around line 746), before the `renderModeToggle()` call, add a one-time CSS injection:

```javascript
if ($("#ident-text-input-css").length === 0) {
  $("<style id='ident-text-input-css'>" +
    ".text-id-input { margin: 8px auto; max-width: 520px; }" +
    ".text-id-pill { display: flex; border: 2px solid #3b82f6; border-radius: 6px; overflow: hidden; }" +
    ".text-id-field { flex: 1; padding: 8px 12px; font-size: 15px; font-family: monospace; border: none; outline: none; }" +
    ".text-id-check { background: #3b82f6; color: #fff; border: none; padding: 8px 16px; font-size: 13px; cursor: pointer; white-space: nowrap; }" +
    ".text-id-check:hover { background: #2563eb; }" +
    ".text-id-hint { font-size: 11px; color: #94a3b8; text-align: center; margin-top: 4px; }" +
    "</style>").appendTo("head");
}
```

- [ ] **Step 5: Update `initIdentificationMode` to use the factory and render the toggle**

In `initIdentificationMode` (around line 196), find where the grader is initialised and labels are first drawn. Add the following at the end of `initIdentificationMode`, replacing any existing direct `LabelInput` instantiation in this method:

```javascript
// Build the input component based on stored/exercise preference
var self = this;
var definition = this.exerciseContext.getDefinition();
var inputMode = this._getIdentInputMode(definition);
var problems = this.exerciseContext.getVisibleProblems
  ? this.exerciseContext.getVisibleProblems()
  : definition.getProblems();
var feedbackMode = this._getActiveIdentificationMode();

// Container for the input component (below #identification-actions)
var $inputContainer = $("#ident-text-input-container");
if ($inputContainer.length === 0) {
  $inputContainer = $('<div id="ident-text-input-container"></div>');
  $("#identification-actions").after($inputContainer);
}

var onAnswer = function (problemIndex, label) {
  // Route to the same handler as dropdown selections
  if (self.exerciseContext.grader && self.exerciseContext.grader.onIdentificationAnswer) {
    self.exerciseContext.grader.onIdentificationAnswer(problemIndex, label);
  }
  self.drawIdentificationLabels();
};

if (this._inputComponent) { this._inputComponent.destroy(); }
this._inputComponent = this._buildInputComponent(inputMode, $inputContainer, problems, feedbackMode, onAnswer);
this._inputComponent.render();
if (this._inputComponent.updatePositions) {
  this._inputComponent.updatePositions(this.staves, this.el.find("#staff"));
}

this.renderInputModeToggle(inputMode, function (newMode) {
  self._setIdentInputMode(newMode);
  if (self._inputComponent) { self._inputComponent.destroy(); }
  self._inputComponent = self._buildInputComponent(newMode, $inputContainer, problems, feedbackMode, onAnswer);
  self._inputComponent.render();
  self.renderInputModeToggle(newMode, arguments.callee);
});
```

- [ ] **Step 6: Verify existing dropdown path still works**

Load an identification exercise in the browser. Confirm:
1. Dropdowns still appear (default `inputMode = "dropdown"`)
2. The "🖱 Click / ⌨ Type" toggle renders above the Practice/Submit toggle
3. No JS errors in console

- [ ] **Step 7: Verify text input mode**

Click "⌨ Type" toggle. Confirm:
1. Dropdowns disappear
2. Text input pill appears
3. Typing `C D E F` in practice mode turns slots green as you type (after each space)
4. Typing in submit mode: no feedback until "Check ↵" is clicked
5. Preference survives page reload (localStorage persists)
6. Switching back to "🖱 Click" restores dropdowns, answers already given remain in grader

- [ ] **Step 8: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: wire TextInputComponent and input mode toggle into exercise_sheet"
```

---

## Task 8: Verify `onAnswer` routing in identification grader

**Files:**
- Read: `lab/static/js/src/models/identification_grader.js` (or wherever identification answers are handled)

The `onAnswer` callback in Task 7 calls `grader.onIdentificationAnswer`. Verify this method exists in the grader; if the method name differs, fix the call in Task 7's Step 5.

- [ ] **Step 1: Find the actual grader answer handler**

```bash
grep -n "onIdentificationAnswer\|onAnswer\|setAnswer\|recordAnswer" lab/static/js/src/models/identification_grader.js 2>/dev/null | head -20
grep -rn "onIdentificationAnswer\|setAnswer\|recordAnswer" lab/static/js/src/components/music/exercise_sheet.js | head -20
```

- [ ] **Step 2: If method name differs, update the call in exercise_sheet.js**

In the `onAnswer` function added in Task 7 Step 5, replace `grader.onIdentificationAnswer(problemIndex, label)` with the actual method name found in Step 1.

- [ ] **Step 3: Confirm full end-to-end flow in browser**

In practice mode with text input:
1. Type `C ` (C followed by space)
2. Slot 0 should turn green ✓ if C is correct
3. Type rest of answers — each slot updates live

In submit mode with text input:
1. Type all answers
2. Nothing changes on score yet
3. Click "Check ↵"
4. All slots update to green ✓ / red ✗

- [ ] **Step 4: Commit if any fixes were needed**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "fix: correct onAnswer routing for text input mode"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `input_mode` field on UMTO Metadata | Task 1 |
| `input_mode` default = `"dropdown"` (existing exercises unaffected) | Task 1 |
| `input_mode` in exercise payload (`inputMode`) | Task 1 |
| `--input-mode` flag on `generate_unit1` | Task 2 |
| Input mode select in dashboard modal | Task 3 |
| `destroy()` on `LabelInputComponent` | Task 4 |
| `getInputMode()` on `ExerciseDefinition` | Task 5 |
| `TextInputComponent` with parser | Task 6 |
| localStorage preference + toggle | Task 7 |
| Practice mode: live per-token feedback | Task 7 |
| Submit mode: deferred until Check | Task 7 |
| Score slots reuse existing rendering | Task 7 |
| `onAnswer` routing to grader | Task 8 |

**No placeholders found.** All code blocks are complete.

**Type consistency:**
- `_buildInputComponent` → returns component with `render()`, `updatePositions()`, `destroy()`, `showResults()`, `lockCorrect()` — all defined on both `TextInputComponent` and `LabelInputComponent`. ✓
- `onAnswer(problemIndex, label)` signature consistent across Tasks 6, 7, 8. ✓
- `getInputMode()` defined in Task 5, called in Task 7 (`definition.getInputMode()`). ✓
- `_getIdentInputMode`, `_setIdentInputMode`, `_buildInputComponent`, `renderInputModeToggle` all defined in Task 7 before use. ✓
