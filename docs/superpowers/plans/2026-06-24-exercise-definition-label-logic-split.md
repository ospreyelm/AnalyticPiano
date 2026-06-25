# exercise_definition.js Label Logic Split

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract 8 pure helper functions from `exercise_definition.js` into a zero-dependency UMD module, reducing the file by ~180 lines and gaining full Node.js test coverage for the extracted logic.

**Architecture:** Follow the existing `exercise_definition_logic.js` / `chordal_problems_logic.js` UMD pattern — no external deps in the new module (convert lodash calls to native JS), fully testable with `node file.test.js`. The AMD module ID is `app/models/exercise_definition_label_logic`. `computeWindowLabel` and the problem builders stay in `exercise_definition.js`; they call into `LabelLogic.*` after the split.

**Tech Stack:** RequireJS AMD (browser), Node.js CJS (tests), vanilla JS (no lodash in new module), existing Django test runner (`python manage.py test`).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `lab/static/js/src/models/exercise_definition_label_logic.js` | Pure label helpers: normalizeAnalysisLabel, FIGURE_TOKEN_MAP, expandFiguredBassToken, stripFiguredBassTokens, isPitchAnalysisType, computeNoteNameFromEvent, buildAnalysisWindows, buildChoices |
| Create | `lab/static/js/src/models/exercise_definition_label_logic.test.js` | Node.js characterization tests for the new module |
| Modify | `lab/static/js/src/models/exercise_definition.js` | Add `app/models/exercise_definition_label_logic` AMD dep; remove extracted functions; update all call sites to `LabelLogic.*` |

---

## Task 1: Write the failing test file

**Files:**
- Create: `lab/static/js/src/models/exercise_definition_label_logic.test.js`

- [ ] Create the test file (it will fail because the module doesn't exist yet):

```javascript
"use strict";

var assert = require("assert");
var LabelLogic = require("./exercise_definition_label_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + "\n    got:  " + JSON.stringify(actual) + "\n    want: " + JSON.stringify(expected)); fail++; }
}

// --- normalizeAnalysisLabel ---
eq("null → empty string", LabelLogic.normalizeAnalysisLabel(null), "");
eq("undefined → empty string", LabelLogic.normalizeAnalysisLabel(undefined), "");
eq("trims whitespace", LabelLogic.normalizeAnalysisLabel("  V7  "), "V7");
eq("normalizes flat symbol", LabelLogic.normalizeAnalysisLabel("♭VI"), "bVI");
eq("normalizes sharp symbol", LabelLogic.normalizeAnalysisLabel("♯IV"), "#IV");
eq("strips leading parens", LabelLogic.normalizeAnalysisLabel("(V7)"), "V7");
eq("strips leading comma", LabelLogic.normalizeAnalysisLabel(",IV"), "IV");
eq("preserves internal slash", LabelLogic.normalizeAnalysisLabel("V6/5"), "V6/5");
eq("preserves slash intact", LabelLogic.normalizeAnalysisLabel("6/4"), "6/4");

// --- FIGURE_TOKEN_MAP ---
eq("z maps to 6", LabelLogic.FIGURE_TOKEN_MAP["z"], "6");
eq("z4 maps to 6/4", LabelLogic.FIGURE_TOKEN_MAP["z4"], "6/4");
eq("u maps to 7", LabelLogic.FIGURE_TOKEN_MAP["u"], "7");

// --- expandFiguredBassToken ---
eq("expands z", LabelLogic.expandFiguredBassToken("z"), "6");
eq("expands z4", LabelLogic.expandFiguredBassToken("z4"), "6/4");
eq("expands u", LabelLogic.expandFiguredBassToken("u"), "7");
eq("expands r", LabelLogic.expandFiguredBassToken("r"), "4");
eq("passthrough unknown", LabelLogic.expandFiguredBassToken("xyz"), "xyz");

// --- stripFiguredBassTokens ---
eq("strips {z} to 6", LabelLogic.stripFiguredBassTokens("V{z}"), "V6");
eq("strips {z4} to 6/4", LabelLogic.stripFiguredBassTokens("I{z4}"), "I6/4");
eq("strips {u} to 7", LabelLogic.stripFiguredBassTokens("V{u}"), "V7");
eq("passthrough no tokens", LabelLogic.stripFiguredBassTokens("V7"), "V7");
eq("null passthrough", LabelLogic.stripFiguredBassTokens(null), null);
eq("empty string → empty", LabelLogic.stripFiguredBassTokens(""), "");

// --- isPitchAnalysisType ---
eq("note_name is pitch", LabelLogic.isPitchAnalysisType("note_name"), true);
eq("solfege is pitch", LabelLogic.isPitchAnalysisType("solfege"), true);
eq("do_based_solfege is pitch", LabelLogic.isPitchAnalysisType("do_based_solfege"), true);
eq("scale_degree is pitch", LabelLogic.isPitchAnalysisType("scale_degree"), true);
eq("fixed_do is pitch", LabelLogic.isPitchAnalysisType("fixed_do"), true);
eq("pitch_class is pitch", LabelLogic.isPitchAnalysisType("pitch_class"), true);
eq("roman is not pitch", LabelLogic.isPitchAnalysisType("roman"), false);
eq("interval_generic is not pitch", LabelLogic.isPitchAnalysisType("interval_generic"), false);
eq("figured_bass is not pitch", LabelLogic.isPitchAnalysisType("figured_bass"), false);

// --- computeNoteNameFromEvent ---
eq("natural C", LabelLogic.computeNoteNameFromEvent({ step: "C", alter: 0 }), "C");
eq("sharp F", LabelLogic.computeNoteNameFromEvent({ step: "F", alter: 1 }), "F#");
eq("flat B", LabelLogic.computeNoteNameFromEvent({ step: "B", alter: -1 }), "Bb");
eq("double sharp C", LabelLogic.computeNoteNameFromEvent({ step: "C", alter: 2 }), "C##");
eq("double flat A", LabelLogic.computeNoteNameFromEvent({ step: "A", alter: -2 }), "Abb");
eq("null event → empty", LabelLogic.computeNoteNameFromEvent(null), "");

// --- buildAnalysisWindows ---
var emptyWindows = LabelLogic.buildAnalysisWindows([]);
eq("empty timeline → []", emptyWindows.length, 0);

var singleWindow = LabelLogic.buildAnalysisWindows([
  { onset: 0, duration: 1024, midi: 60, step: "C", alter: 0 }
]);
eq("single event → 1 window", singleWindow.length, 1);
eq("single window onset=0", singleWindow[0].onset, 0);
eq("single window midiStack=[60]", singleWindow[0].midiStack, [60]);

// Two events at same onset → one window, both midis in stack
var sameOnset = LabelLogic.buildAnalysisWindows([
  { onset: 0, duration: 1024, midi: 60, step: "C", alter: 0 },
  { onset: 0, duration: 1024, midi: 64, step: "E", alter: 0 }
]);
eq("same onset → 1 window", sameOnset.length, 1);
eq("same onset midiStack sorted", sameOnset[0].midiStack, [60, 64]);

// Sustain: first note (dur=2048) still active at onset=1024
var sustainWindows = LabelLogic.buildAnalysisWindows([
  { onset: 0,    duration: 2048, midi: 60, step: "C", alter: 0 },
  { onset: 1024, duration: 1024, midi: 64, step: "E", alter: 0 }
]);
eq("sustain → 2 windows", sustainWindows.length, 2);
eq("second window includes sustained note", sustainWindows[1].midiStack, [60, 64]);

// Null timeline → []
eq("null timeline → []", LabelLogic.buildAnalysisWindows(null).length, 0);

// --- buildChoices ---
var choices1 = LabelLogic.buildChoices("I", ["I", "IV", "V", "vi", "ii"], "roman", false);
eq("buildChoices returns 5", choices1.length, 5);
eq("correct answer included", choices1.indexOf("I") !== -1, true);

// Sparse pool — fallbacks fill the gap
var choices2 = LabelLogic.buildChoices("I", ["I"], "roman", false);
eq("sparse pool still returns 5", choices2.length, 5);
eq("correct answer always present in sparse", choices2.indexOf("I") !== -1, true);

// figured_bass fallbacks
var choices3 = LabelLogic.buildChoices("6", [], "figured_bass", false);
eq("figured_bass returns 5", choices3.length, 5);
eq("figured_bass correct answer present", choices3.indexOf("6") !== -1, true);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] Run to confirm it fails (module missing):

```
node lab/static/js/src/models/exercise_definition_label_logic.test.js
```

Expected: `Error: Cannot find module './exercise_definition_label_logic'`

- [ ] Commit (failing test locked in):

```bash
git add lab/static/js/src/models/exercise_definition_label_logic.test.js
git commit -m "test(js): add failing tests for exercise_definition_label_logic"
```

---

## Task 2: Create exercise_definition_label_logic.js

**Files:**
- Create: `lab/static/js/src/models/exercise_definition_label_logic.js`

- [ ] Create the module. Use the existing UMD wrapper pattern (zero external deps; lodash calls converted to native JS):

```javascript
/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseDefinitionLabelLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function normalizeAnalysisLabel(label) {
    if (label === null || label === undefined) {
      return "";
    }
    var result = String(label).trim();
    result = result.replace(/♭/g, "b").replace(/♯/g, "#");
    result = result.replace(/^[\s,;:\-()]+|[\s,;:\-()]+$/g, "");
    return result;
  }

  var FIGURE_TOKEN_MAP = {
    "z": "6",
    "z4": "6/4",
    "Cz4": "b6/4",
    "z5": "6/5",
    "u": "7",
    "u3": "6/5",
    "u5": "7/5",
    "r": "4",
    "r2": "4/2",
    "r3": "4/3",
    "i3": "3",
    "q e": "13",
  };

  function expandFiguredBassToken(abbrev) {
    if (FIGURE_TOKEN_MAP[abbrev]) {
      return FIGURE_TOKEN_MAP[abbrev];
    }
    for (var key in FIGURE_TOKEN_MAP) {
      if (FIGURE_TOKEN_MAP.hasOwnProperty(key) && abbrev.indexOf(key) === 0) {
        return FIGURE_TOKEN_MAP[key];
      }
    }
    return abbrev;
  }

  function stripFiguredBassTokens(label) {
    if (!label) return label;
    var result = String(label);
    result = result.replace(/\{([A-Za-z0-9]+)\}/g, function (match, token) {
      return FIGURE_TOKEN_MAP[token] || "";
    });
    return result.trim();
  }

  function isPitchAnalysisType(analysisType) {
    return [
      "note_name",
      "solfege",
      "do_based_solfege",
      "scale_degree",
      "fixed_do",
      "pitch_class",
    ].indexOf(analysisType) !== -1;
  }

  function computeNoteNameFromEvent(ev) {
    if (!ev) return "";
    var name = ev.step.toUpperCase();
    if (ev.alter === 1) name += "#";
    else if (ev.alter === -1) name += "b";
    else if (ev.alter === 2) name += "##";
    else if (ev.alter === -2) name += "bb";
    return name;
  }

  function buildAnalysisWindows(timeline) {
    var grouped = [];
    var onsetIndex = Object.create(null);
    var activeNotes = [];

    (timeline || []).forEach(function (ev) {
      if (!Object.prototype.hasOwnProperty.call(onsetIndex, ev.onset)) {
        onsetIndex[ev.onset] = { onset: ev.onset, events: [] };
        grouped.push(onsetIndex[ev.onset]);
      }
      onsetIndex[ev.onset].events.push(ev);
    });

    grouped.sort(function (a, b) { return a.onset - b.onset; });

    grouped.forEach(function (window) {
      activeNotes = activeNotes.filter(function (n) {
        return n.end > window.onset;
      });
      (window.events || []).forEach(function (ev) {
        activeNotes.push({ midi: ev.midi, end: ev.onset + ev.duration });
      });
      var midiMap = Object.create(null);
      activeNotes.forEach(function (n) { midiMap[n.midi] = true; });
      window.midiStack = Object.keys(midiMap)
        .map(function (k) { return parseInt(k, 10); })
        .sort(function (a, b) { return a - b; });
    });

    return grouped;
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function buildChoices(correctLabel, allLabels, analysisType, compoundIntervals) {
    var seen = Object.create(null);
    var pool = (allLabels || []).filter(function (l) {
      if (!l || l === correctLabel) return false;
      if (seen[l]) return false;
      seen[l] = true;
      return true;
    });

    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "7", "6/5", "4/3", "4/2"]
      : analysisType === "figured_bass_unabbreviated"
      ? ["8/5/3", "6/3", "6/4", "7/5/3", "6/5/3", "6/4/3", "6/4/2"]
      : analysisType === "note_name"
      ? ["C", "D", "E", "F", "G", "A", "B"]
      : (analysisType === "solfege" || analysisType === "do_based_solfege" || analysisType === "fixed_do")
      ? ["Do", "Re", "Mi", "Fa", "So", "La", "Ti"]
      : analysisType === "scale_degree"
      ? ["1", "2", "3", "4", "5", "6", "7"]
      : analysisType === "pitch_class"
      ? ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
      : analysisType === "interval_generic"
      ? (compoundIntervals
        ? ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"]
        : ["2", "3", "4", "5", "6", "7", "8"])
      : analysisType === "interval_specific"
      ? (compoundIntervals
        ? ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8", "m9", "M9", "m10", "M10", "P11", "P12", "m13", "M13", "m14", "M14"]
        : ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"])
      : ["I", "ii", "IV", "V", "vi", "I6/4", "i6/4", "V6/4", "Cad6/4", "Cadb6/4"];

    if (pool.length < 4) {
      fallbacks.forEach(function (item) {
        if (item !== correctLabel && pool.indexOf(item) === -1) {
          pool.push(item);
        }
      });
    }

    var distractors = shuffle(pool).slice(0, 4);
    var choices = shuffle([correctLabel].concat(distractors));
    while (choices.length < 5) { choices.push(correctLabel); }
    return choices.slice(0, 5);
  }

  return {
    normalizeAnalysisLabel: normalizeAnalysisLabel,
    FIGURE_TOKEN_MAP: FIGURE_TOKEN_MAP,
    expandFiguredBassToken: expandFiguredBassToken,
    stripFiguredBassTokens: stripFiguredBassTokens,
    isPitchAnalysisType: isPitchAnalysisType,
    computeNoteNameFromEvent: computeNoteNameFromEvent,
    buildAnalysisWindows: buildAnalysisWindows,
    buildChoices: buildChoices,
  };
});
```

- [ ] Run the tests to verify they pass:

```
node lab/static/js/src/models/exercise_definition_label_logic.test.js
```

Expected: all tests pass, `N passed, 0 failed`.

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_definition_label_logic.js
git commit -m "feat(js): extract exercise_definition_label_logic module"
```

---

## Task 3: Update exercise_definition.js

**Files:**
- Modify: `lab/static/js/src/models/exercise_definition.js`

This task has two sub-steps: (a) add the new AMD dep and (b) remove extracted code + update call sites.

- [ ] **Step 3a: Add the AMD dependency.**

In the `define([...], function(...) { ... })` call at the top of the file, add `"app/models/exercise_definition_label_logic"` and `LabelLogic` as the last dependency/parameter:

Old first line of `define`:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "app/models/key_context_logic",
  "app/models/input_method_logic",
  "app/config/unit_allowed_answers",
  "app/models/exercise_definition_logic",
  "app/models/chordal_problems_logic",
  "tonal",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, KeyContext, InputMethodLogic, UNIT_ALLOWED_ANSWERS_RAW, ExerciseDefinitionLogic, ChordalProblemsLogic, Tonal) {
```

New:
```javascript
define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "app/models/key_context_logic",
  "app/models/input_method_logic",
  "app/config/unit_allowed_answers",
  "app/models/exercise_definition_logic",
  "app/models/chordal_problems_logic",
  "tonal",
  "app/models/exercise_definition_label_logic",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, KeyContext, InputMethodLogic, UNIT_ALLOWED_ANSWERS_RAW, ExerciseDefinitionLogic, ChordalProblemsLogic, Tonal, LabelLogic) {
```

- [ ] **Step 3b: Remove extracted function bodies (lines 109–218 and 315–395) and the constant (lines 122–135).**

Delete these blocks from exercise_definition.js:
- Lines 109–119: `function normalizeAnalysisLabel(...) { ... }`
- Lines 122–135: `var FIGURE_TOKEN_MAP = { ... };`
- Lines 137–149: `function expandFiguredBassToken(...) { ... }`
- Lines 187–197: `function stripFiguredBassTokens(...) { ... }`
- Lines 199–208: `function isPitchAnalysisType(...) { ... }`
- Lines 210–218: `function computeNoteNameFromEvent(...) { ... }`
- Lines 315–355: `function buildAnalysisWindows(...) { ... }`
- Lines 357–395: `function buildChoices(...) { ... }`

- [ ] **Step 3c: Update call sites inside `computeWindowLabel` (lines ~220–313).**

`computeWindowLabel` stays in exercise_definition.js but calls extracted functions. Update each call:

| Old call | New call |
|---|---|
| `isPitchAnalysisType(analysisType)` | `LabelLogic.isPitchAnalysisType(analysisType)` |
| `computeNoteNameFromEvent(windowEvents[0])` | `LabelLogic.computeNoteNameFromEvent(windowEvents[0])` |
| `normalizeAnalysisLabel(...)` (all 8 occurrences in computeWindowLabel) | `LabelLogic.normalizeAnalysisLabel(...)` |
| `expandFiguredBassToken(abbrevFigure)` | `LabelLogic.expandFiguredBassToken(abbrevFigure)` |
| `stripFiguredBassTokens(chord.label)` | `LabelLogic.stripFiguredBassTokens(chord.label)` |

- [ ] **Step 3d: Update call sites in `buildChoraleIdentificationProblems`.**

```javascript
// Old:
var windows = buildAnalysisWindows(timeline);
// New:
var windows = LabelLogic.buildAnalysisWindows(timeline);

// Old:
choices: buildChoices(answer, labels, analysisType, compoundIntervals),
// New:
choices: LabelLogic.buildChoices(answer, labels, analysisType, compoundIntervals),
```

- [ ] **Step 3e: Update call sites in `buildUMTOIdentificationProblems`.**

```javascript
// Old (line ~453):
const windows = buildAnalysisWindows(timeline);
// New:
const windows = LabelLogic.buildAnalysisWindows(timeline);

// Old (line ~516):
answer = stripFiguredBassTokens(slice.content.roman_numeral);
// New:
answer = LabelLogic.stripFiguredBassTokens(slice.content.roman_numeral);

// Old (line ~571):
answer: normalizeAnalysisLabel(answer),
// New:
answer: LabelLogic.normalizeAnalysisLabel(answer),

// Old (lines ~607–609):
next.choices = _.map(buildChoices(next.answer, explicitAllowedAnswers, analysisType, false), normalizeAnalysisLabel);
// ...
next.choices = _.map(buildChoices(next.answer, allAnswers, analysisType, false), normalizeAnalysisLabel);
// New:
next.choices = _.map(LabelLogic.buildChoices(next.answer, explicitAllowedAnswers, analysisType, false), LabelLogic.normalizeAnalysisLabel);
// ...
next.choices = _.map(LabelLogic.buildChoices(next.answer, allAnswers, analysisType, false), LabelLogic.normalizeAnalysisLabel);
```

- [ ] **Step 3f: Update call sites in the chordal ident path inside `parse()` (~lines 1087–1135).**

```javascript
// Old (line ~1087):
var chordalWindows = buildAnalysisWindows(chordalTimeline);
// New:
var chordalWindows = LabelLogic.buildAnalysisWindows(chordalTimeline);

// Old (line ~1102):
answer = stripFiguredBassTokens(content.roman_numeral);
// New:
answer = LabelLogic.stripFiguredBassTokens(content.roman_numeral);

// Old (line ~1110):
answer = normalizeAnalysisLabel(answer);
// New:
answer = LabelLogic.normalizeAnalysisLabel(answer);

// Old (line ~1135):
problem.choices = _.map(buildChoices(problem.answer, answerPool, exercise.analysisType, false), normalizeAnalysisLabel);
// New:
problem.choices = _.map(LabelLogic.buildChoices(problem.answer, answerPool, exercise.analysisType, false), LabelLogic.normalizeAnalysisLabel);
```

- [ ] Verify no remaining bare calls to extracted names by grepping:

```bash
grep -n "normalizeAnalysisLabel\|expandFiguredBassToken\|stripFiguredBassTokens\|isPitchAnalysisType\|computeNoteNameFromEvent\|buildAnalysisWindows\|buildChoices\|FIGURE_TOKEN_MAP" lab/static/js/src/models/exercise_definition.js
```

Expected: all remaining occurrences are prefixed with `LabelLogic.`.

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_definition.js
git commit -m "refactor(js): replace inline label helpers with exercise_definition_label_logic"
```

---

## Task 4: Verify

**Files:** No changes.

- [ ] Run the label logic unit tests:

```bash
node lab/static/js/src/models/exercise_definition_label_logic.test.js
```

Expected: all tests pass.

- [ ] Run the existing Node.js logic test suite to confirm nothing is broken:

```bash
node lab/static/js/src/models/exercise_definition_logic.test.js
node lab/static/js/src/models/chordal_problems_logic.test.js
node lab/static/js/src/models/input_method_logic.test.js
node lab/static/js/src/models/key_context_logic.test.js
```

Expected: all pass.

- [ ] Run the Django/Python test suite (exercises app, which covers exercise context generation and verifies the JSON payload shapes that exercise_definition.js consumes):

```bash
python manage.py test apps.exercises --settings=harmony.settings.local -v 1
```

Expected: all existing tests pass.

- [ ] Verify line count reduction:

```bash
wc -l lab/static/js/src/models/exercise_definition.js lab/static/js/src/models/exercise_definition_label_logic.js
```

Expected: `exercise_definition.js` near 1,390 lines (down from 1,569); new module near 140 lines.

- [ ] Final commit if anything was fixed in this task (otherwise skip):

```bash
git add -p
git commit -m "fix(js): address any issues found during verification"
```

---

## Self-Review

**Spec coverage:** All 8 functions (normalizeAnalysisLabel, FIGURE_TOKEN_MAP, expandFiguredBassToken, stripFiguredBassTokens, isPitchAnalysisType, computeNoteNameFromEvent, buildAnalysisWindows, buildChoices) are covered by Task 1 tests and extracted in Task 2. All call sites updated in Task 3. ✓

**Placeholder scan:** No TBDs. All code blocks complete. ✓

**Type consistency:** `LabelLogic.buildChoices` signature `(correctLabel, allLabels, analysisType, compoundIntervals)` matches all call sites. `LabelLogic.buildAnalysisWindows(timeline)` matches all call sites. ✓

**AMD module identity:** `exercise_definition.js` AMD ID unchanged (`app/models/exercise_definition`). Only its internal dep list grows by one entry. ✓

**Behavior parity:** `buildChoices` lodash→native conversion preserves all branching logic; `_.uniq` replaced with `seen` object; `_.shuffle` replaced with Fisher-Yates. `buildAnalysisWindows` lodash→native is a line-for-line translation. ✓
