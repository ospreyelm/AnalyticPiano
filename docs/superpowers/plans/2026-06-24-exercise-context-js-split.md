# exercise_context.js Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure timer-computation helpers and pure ident-pagination helpers from `exercise_context.js` into two zero-dependency UMD modules, reducing the file and gaining full Node.js test coverage for the extracted logic.

**Architecture:** Same zero-dep UMD pattern as `exercise_definition_label_logic.js`. Two new modules: `exercise_context_timer_logic.js` (timer state creation, duration formatting, tempo interval/stats/rating computation) and `exercise_context_ident_page_logic.js` (chorale page size, total pages, page offset, visible-problems slice). `exercise_context.js` keeps all `this`-bound methods but calls into the logic modules for pure computation; the `simple-statistics.min` AMD dep is removed because `computeTempoStats` re-implements mean/sample-stddev inline.

**Tech Stack:** RequireJS AMD (browser), Node.js CJS (tests), vanilla JS (no lodash in new modules), existing Django test runner.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `lab/static/js/src/models/exercise_context_timer_logic.js` | Pure helpers: `createTimerState`, `formatDurationString`, `computeTempoIntervals`, `SEMIBREVE_FRACTION`, `computeSemibreveCount`, `computeCentisemibrevesPerMin`, `computeTempoStats`, `computeTempoRating` |
| Create | `lab/static/js/src/models/exercise_context_timer_logic.test.js` | Node.js characterisation tests for timer logic module |
| Create | `lab/static/js/src/models/exercise_context_ident_page_logic.js` | Pure helpers: `getChoralePageMeasureCount`, `computeTotalIdentPages`, `computeIdentPageOffset`, `filterVisibleProblems` |
| Create | `lab/static/js/src/models/exercise_context_ident_page_logic.test.js` | Node.js characterisation tests for ident-page logic module |
| Modify | `lab/static/js/src/models/exercise_context.js` | Remove `simple-statistics.min` dep; add two new AMD deps; replace function bodies with calls to logic modules |

---

## Task 1: Write failing tests for exercise_context_timer_logic

**Files:**
- Create: `lab/static/js/src/models/exercise_context_timer_logic.test.js`

- [ ] Create the test file (fails because the module doesn't exist yet):

```javascript
"use strict";

var TimerLogic = require("./exercise_context_timer_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + "\n    got:  " + JSON.stringify(actual) + "\n    want: " + JSON.stringify(expected)); fail++; }
}

// --- createTimerState ---
var ts = TimerLogic.createTimerState();
eq("start=null",        ts.start,          null);
eq("end=null",          ts.end,            null);
eq("duration=null",     ts.duration,       null);
eq("durationString=''", ts.durationString, "");
eq("minTempo=null",     ts.minTempo,       null);
eq("maxTempo=null",     ts.maxTempo,       null);
eq("tempoSD=null",      ts.tempoSD,        null);
eq("tempoRating=null",  ts.tempoRating,    null);
eq("timepoints={}",     ts.timepoints,     {});
eq("timeIntervals=[]",  ts.timeIntervals,  []);

// --- formatDurationString ---
eq("0ms → '0&Prime;'",                    TimerLogic.formatDurationString(0),       "0&Prime;");
eq("30000ms → '30&Prime;'",               TimerLogic.formatDurationString(30000),   "30&Prime;");
eq("60000ms → '1&prime;&nbsp;0&Prime;'",  TimerLogic.formatDurationString(60000),   "1&prime;&nbsp;0&Prime;");
eq("90000ms → '1&prime;&nbsp;30&Prime;'", TimerLogic.formatDurationString(90000),   "1&prime;&nbsp;30&Prime;");
eq("3661000ms → '61&prime;&nbsp;1&Prime;'", TimerLogic.formatDurationString(3661000), "61&prime;&nbsp;1&Prime;");

// --- computeTempoIntervals ---
eq("empty timepoints → []",        TimerLogic.computeTempoIntervals({}),             []);
eq("one timepoint → []",           TimerLogic.computeTempoIntervals({0: 100}),       []);
eq("two timepoints → [500]",       TimerLogic.computeTempoIntervals({0: 100, 1: 600}), [500]);
eq("three timepoints → [500,500]", TimerLogic.computeTempoIntervals({0: 100, 1: 600, 2: 1100}), [500, 500]);
// keys are sorted numerically not lexically
eq("out-of-order keys → [500,500]",
  TimerLogic.computeTempoIntervals({2: 1200, 0: 200, 1: 700}), [500, 500]);

// --- SEMIBREVE_FRACTION ---
eq("SEMIBREVE_FRACTION.w = 1",    TimerLogic.SEMIBREVE_FRACTION["w"], 1);
eq("SEMIBREVE_FRACTION.h = 0.5",  TimerLogic.SEMIBREVE_FRACTION["h"], 0.5);
eq("SEMIBREVE_FRACTION.q = 0.25", TimerLogic.SEMIBREVE_FRACTION["q"], 0.25);
eq("SEMIBREVE_FRACTION.e = 0.125",TimerLogic.SEMIBREVE_FRACTION["e"], 0.125);

// --- computeSemibreveCount ---
var chords3 = [
  { settings: { rhythm: "q" } },
  { settings: { rhythm: "h" } },
  { settings: { rhythm: "w" } },
];
// 3 chords, 3 input items: min=3 → [0.25, 0.5, 1.0] → pop last → [0.25, 0.5]
eq("3 chords 3 items → [0.25, 0.5]",
  TimerLogic.computeSemibreveCount(chords3, 3, "q"), [0.25, 0.5]);
// input shorter than chords → use input count
eq("3 chords 2 items → min=2 → [0.25]",
  TimerLogic.computeSemibreveCount(chords3, 2, "q"), [0.25]);
// no rhythm on chord → fall back to defaultRhythmValue
var chordsNoRhythm = [{ settings: {} }, { settings: {} }];
eq("no rhythm → default 'q'=0.25 → pop → [0.25]",
  TimerLogic.computeSemibreveCount(chordsNoRhythm, 2, "q"), [0.25]);
// empty → []
eq("empty chords → []",
  TimerLogic.computeSemibreveCount([], 0, "q"), []);

// --- computeCentisemibrevesPerMin ---
// 1000ms interval, 1.0 semibreve: round(1.0 * 6000000 / 1000) = 6000
eq("1000ms 1.0sv → [6000,6000]",
  TimerLogic.computeCentisemibrevesPerMin([1000, 1000], [1.0, 1.0]), [6000, 6000]);
// mismatched lengths → []
eq("mismatched lengths → []",
  TimerLogic.computeCentisemibrevesPerMin([1000], [1.0, 0.5]), []);
eq("both empty → []",
  TimerLogic.computeCentisemibrevesPerMin([], []), []);

// --- computeTempoStats ---
// [100,200,300]: mean=200→round(200/10)/10=2.0; sampleSD=100→round(100)/100=1.0; min=1.0; max=3.0
var stats = TimerLogic.computeTempoStats([100, 200, 300]);
eq("tempoMean of [100,200,300]", stats.tempoMean, 2.0);
eq("tempoSD of [100,200,300]",   stats.tempoSD,   1.0);
eq("minTempo of [100,200,300]",  stats.minTempo,  1.0);
eq("maxTempo of [100,200,300]",  stats.maxTempo,  3.0);
// [6000,6000,6000]: mean=6000→60.0; sd=0; min=max=60.0
var statsFlat = TimerLogic.computeTempoStats([6000, 6000, 6000]);
eq("flat tempoMean=60.0",  statsFlat.tempoMean, 60.0);
eq("flat tempoSD=0",       statsFlat.tempoSD,   0);
eq("flat minTempo=60.0",   statsFlat.minTempo,  60.0);
eq("flat maxTempo=60.0",   statsFlat.maxTempo,  60.0);

// --- computeTempoRating ---
// SD=0 → 5 stars
eq("SD=0 → 5",            TimerLogic.computeTempoRating(0,   100), 5);
// floor(100/2)=50 → "110010" 6 chars → 5 → capped 5
eq("ratio=50 → 5",        TimerLogic.computeTempoRating(2,   100), 5);
// floor(100/25)=4 → "100" 3 chars → 2
eq("ratio=4 → 2",         TimerLogic.computeTempoRating(25,  100), 2);
// floor(100/100)=1 → "1" 1 char → 0 → max(1,0)=1
eq("ratio=1 → 1",         TimerLogic.computeTempoRating(100, 100), 1);
// floor(700/100)=7 → "111" 3 chars → 2
eq("ratio=7 → 2",         TimerLogic.computeTempoRating(100, 700), 2);
// floor(100/12.5)=8 → "1000" 4 chars → 3
eq("ratio=8 → 3",         TimerLogic.computeTempoRating(12.5, 100), 3);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] Run to confirm it fails (module missing):

```
node lab/static/js/src/models/exercise_context_timer_logic.test.js
```

Expected: `Error: Cannot find module './exercise_context_timer_logic'`

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_context_timer_logic.test.js
git commit -m "test(js): add failing tests for exercise_context_timer_logic"
```

---

## Task 2: Create exercise_context_timer_logic.js

**Files:**
- Create: `lab/static/js/src/models/exercise_context_timer_logic.js`

- [ ] Create the module:

```javascript
/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseContextTimerLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SEMIBREVE_FRACTION = {
    W: 1.5,  w: 1,
    H: 0.75, h: 0.5,
    Q: 0.375, q: 0.25,
    E: 0.1875, e: 0.125,
  };

  function createTimerState() {
    return {
      start: null,
      end: null,
      duration: null,
      durationString: "",
      minTempo: null,
      maxTempo: null,
      tempoSD: null,
      tempoRating: null,
      timepoints: {},
      timeIntervals: [],
    };
  }

  function formatDurationString(durationMs) {
    var seconds = Math.round(durationMs / 1000);
    var minutes = Math.floor(seconds / 60);
    seconds %= 60;
    var s = "";
    if (minutes > 0) {
      s += String(minutes) + "&prime;&nbsp;";
    }
    s += String(seconds) + "&Prime;";
    return s;
  }

  function computeTempoIntervals(timepoints) {
    var indices = Object.keys(timepoints).sort(function (a, b) { return a - b; });
    var intervals = [];
    for (var i = 1; i < indices.length; i++) {
      intervals.push(timepoints[indices[i]] - timepoints[indices[i - 1]]);
    }
    return intervals;
  }

  function computeSemibreveCount(chordSettings, inputChordsLength, defaultRhythmValue) {
    var len = Math.min(inputChordsLength, chordSettings.length);
    var semibreveCount = [];
    for (var i = 0; i < len; i++) {
      var rv = chordSettings[i].settings.rhythm || defaultRhythmValue;
      semibreveCount.push(SEMIBREVE_FRACTION[rv] || defaultRhythmValue || 1);
    }
    if (semibreveCount.length > 0) semibreveCount.pop();
    return semibreveCount;
  }

  function computeCentisemibrevesPerMin(timeIntervals, semibreveCount) {
    if (timeIntervals.length !== semibreveCount.length) return [];
    var result = [];
    for (var i = 0; i < timeIntervals.length; i++) {
      result.push(Math.round((semibreveCount[i] * 6000000) / timeIntervals[i]));
    }
    return result;
  }

  function _mean(arr) {
    if (!arr.length) return 0;
    return arr.reduce(function (s, v) { return s + v; }, 0) / arr.length;
  }

  function _sampleStddev(arr) {
    if (arr.length < 2) return 0;
    var m = _mean(arr);
    var variance = arr.reduce(function (s, v) {
      return s + Math.pow(v - m, 2);
    }, 0) / (arr.length - 1);
    return Math.sqrt(variance);
  }

  function computeTempoStats(centisemibrevesPerMin) {
    return {
      tempoSD:   Math.round(_sampleStddev(centisemibrevesPerMin)) / 100,
      tempoMean: Math.round(_mean(centisemibrevesPerMin) / 10) / 10,
      minTempo:  Math.round(Math.min.apply(null, centisemibrevesPerMin)) / 100,
      maxTempo:  Math.round(Math.max.apply(null, centisemibrevesPerMin)) / 100,
    };
  }

  function computeTempoRating(tempoSD, tempoMean) {
    try {
      return Math.max(
        1,
        Math.min(
          5,
          tempoSD == 0
            ? 5
            : Math.floor(tempoMean / tempoSD).toString(2).length - 1
        )
      ) || 0;
    } catch (e) {
      return 0;
    }
  }

  return {
    SEMIBREVE_FRACTION: SEMIBREVE_FRACTION,
    createTimerState: createTimerState,
    formatDurationString: formatDurationString,
    computeTempoIntervals: computeTempoIntervals,
    computeSemibreveCount: computeSemibreveCount,
    computeCentisemibrevesPerMin: computeCentisemibrevesPerMin,
    computeTempoStats: computeTempoStats,
    computeTempoRating: computeTempoRating,
  };
});
```

- [ ] Run tests to confirm they pass:

```
node lab/static/js/src/models/exercise_context_timer_logic.test.js
```

Expected: all tests pass, `N passed, 0 failed`.

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_context_timer_logic.js
git commit -m "feat(js): extract exercise_context_timer_logic module"
```

---

## Task 3: Write failing tests for exercise_context_ident_page_logic

**Files:**
- Create: `lab/static/js/src/models/exercise_context_ident_page_logic.test.js`

- [ ] Create the test file:

```javascript
"use strict";

var IdentPageLogic = require("./exercise_context_ident_page_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + "\n    got:  " + JSON.stringify(actual) + "\n    want: " + JSON.stringify(expected)); fail++; }
}

// --- getChoralePageMeasureCount ---
eq("maxMeasures=4 → 4",      IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 4 }), 4);
eq("maxMeasures=8 → 8",      IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 8 }), 8);
eq("maxMeasures=0 → default 4",
  IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 0 }), 4);
eq("maxMeasures='bad' → default 4",
  IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: "notanumber" }), 4);
eq("null display → default 4",  IdentPageLogic.getChoralePageMeasureCount(null), 4);
eq("empty display → default 4", IdentPageLogic.getChoralePageMeasureCount({}), 4);

// --- computeTotalIdentPages (non-chorale) ---
var p5 = [{}, {}, {}, {}, {}];
eq("5 probs pageSize=4 → 2",   IdentPageLogic.computeTotalIdentPages(p5, false, 0, 0, 4), 2);
eq("4 probs pageSize=4 → 1",   IdentPageLogic.computeTotalIdentPages([{},{},{},{}], false, 0, 0, 4), 1);
eq("0 probs → 0",              IdentPageLogic.computeTotalIdentPages([], false, 0, 0, 4), 0);
eq("1 prob pageSize=4 → 1",    IdentPageLogic.computeTotalIdentPages([{}], false, 0, 0, 4), 1);

// --- computeTotalIdentPages (chorale) ---
eq("chorale 8 measures max=4 → 2", IdentPageLogic.computeTotalIdentPages(p5, true, 8, 4, 4), 2);
eq("chorale 0 probs → 1 (special)", IdentPageLogic.computeTotalIdentPages([], true, 8, 4, 4), 1);
eq("chorale 3 measures max=4 → 1", IdentPageLogic.computeTotalIdentPages(p5, true, 3, 4, 4), 1);
eq("chorale 9 measures max=4 → 3", IdentPageLogic.computeTotalIdentPages(p5, true, 9, 4, 4), 3);

// --- computeIdentPageOffset (non-chorale) ---
eq("page=0 size=4 → 0", IdentPageLogic.computeIdentPageOffset(0, 4, false, [], 0, 0), 0);
eq("page=1 size=4 → 4", IdentPageLogic.computeIdentPageOffset(1, 4, false, [], 0, 0), 4);
eq("page=2 size=4 → 8", IdentPageLogic.computeIdentPageOffset(2, 4, false, [], 0, 0), 8);

// --- computeIdentPageOffset (chorale) ---
// problems: measureIndex 0,1,4,5; totalMeasures=8, maxMeasures=4
var cp = [
  { measureIndex: 0 }, { measureIndex: 1 },
  { measureIndex: 4 }, { measureIndex: 5 },
];
// page=0: targetMeasure=0, lastPossibleStart=4; first prob measureIndex>=0 → index 0
eq("chorale page=0 → 0", IdentPageLogic.computeIdentPageOffset(0, 4, true, cp, 8, 4), 0);
// page=1: targetMeasure=4, lastPossibleStart=4; first prob measureIndex>=4 → index 2
eq("chorale page=1 → 2", IdentPageLogic.computeIdentPageOffset(1, 4, true, cp, 8, 4), 2);
// page=3: targetMeasure=12>lastPossibleStart=4 → clamp to 4 → same as page=1 → 2
eq("chorale page=3 clamped → 2", IdentPageLogic.computeIdentPageOffset(3, 4, true, cp, 8, 4), 2);
// no problem has measureIndex >= targetMeasure → returns problems.length
var cpShort = [{ measureIndex: 0 }];
eq("no matching problem → problems.length",
  IdentPageLogic.computeIdentPageOffset(1, 4, true, cpShort, 8, 4), 1);

// --- filterVisibleProblems (non-chorale) ---
var ap = [{id:0},{id:1},{id:2},{id:3},{id:4},{id:5}];
var vis0 = IdentPageLogic.filterVisibleProblems(ap, false, 0, 4, 0, 0);
eq("page=0 size=4: 4 visible", vis0.length, 4);
eq("page=0 first id=0", vis0[0].id, 0);
var vis1 = IdentPageLogic.filterVisibleProblems(ap, false, 1, 4, 0, 0);
eq("page=1 size=4: 2 visible", vis1.length, 2);
eq("page=1 first id=4", vis1[0].id, 4);

// --- filterVisibleProblems (chorale) ---
// measures 0,1,3 on page 0 (0–3); measures 4,5,7 on page 1 (4–7)
var cap = [
  { measureIndex: 0 }, { measureIndex: 1 }, { measureIndex: 3 },
  { measureIndex: 4 }, { measureIndex: 5 }, { measureIndex: 7 },
];
var chVis0 = IdentPageLogic.filterVisibleProblems(cap, true, 0, 4, 8, 4);
eq("chorale page=0: 3 probs (measures 0–3)", chVis0.length, 3);
var chVis1 = IdentPageLogic.filterVisibleProblems(cap, true, 1, 4, 8, 4);
eq("chorale page=1: 3 probs (measures 4–7)", chVis1.length, 3);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
```

- [ ] Run to confirm failure:

```
node lab/static/js/src/models/exercise_context_ident_page_logic.test.js
```

Expected: `Error: Cannot find module './exercise_context_ident_page_logic'`

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_context_ident_page_logic.test.js
git commit -m "test(js): add failing tests for exercise_context_ident_page_logic"
```

---

## Task 4: Create exercise_context_ident_page_logic.js

**Files:**
- Create: `lab/static/js/src/models/exercise_context_ident_page_logic.js`

- [ ] Create the module:

```javascript
/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseContextIdentPageLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function getChoralePageMeasureCount(display) {
    var maxMeasures = parseInt(display && display.maxMeasures, 10);
    return maxMeasures > 0 ? maxMeasures : 4;
  }

  function computeTotalIdentPages(allProblems, isChoraleIdent, totalMeasures, maxMeasures, pageSize) {
    if (isChoraleIdent) {
      if (!allProblems || !allProblems.length) return 1;
      return Math.ceil(totalMeasures / maxMeasures);
    }
    return Math.ceil(allProblems.length / pageSize);
  }

  function computeIdentPageOffset(identPage, identPageSize, isChoraleIdent, problems, totalMeasures, maxMeasures) {
    if (isChoraleIdent) {
      var targetMeasure = identPage * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (targetMeasure > lastPossibleStart) targetMeasure = lastPossibleStart;
      for (var i = 0; i < problems.length; i++) {
        if (problems[i].measureIndex >= targetMeasure) return i;
      }
      return problems.length;
    }
    return identPage * identPageSize;
  }

  function filterVisibleProblems(allProblems, isChoraleIdent, identPage, pageSize, totalMeasures, maxMeasures) {
    if (isChoraleIdent) {
      var startMeasure = identPage * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (startMeasure > lastPossibleStart) startMeasure = lastPossibleStart;
      var endMeasure = startMeasure + maxMeasures;
      return allProblems.filter(function (p) {
        return p.measureIndex >= startMeasure && p.measureIndex < endMeasure;
      });
    }
    var offset = computeIdentPageOffset(identPage, pageSize, false, [], 0, 0);
    return allProblems.slice(offset, offset + pageSize);
  }

  return {
    getChoralePageMeasureCount: getChoralePageMeasureCount,
    computeTotalIdentPages: computeTotalIdentPages,
    computeIdentPageOffset: computeIdentPageOffset,
    filterVisibleProblems: filterVisibleProblems,
  };
});
```

- [ ] Run tests to confirm they pass:

```
node lab/static/js/src/models/exercise_context_ident_page_logic.test.js
```

Expected: all tests pass, `N passed, 0 failed`.

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_context_ident_page_logic.js
git commit -m "feat(js): extract exercise_context_ident_page_logic module"
```

---

## Task 5: Update exercise_context.js

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js`

### Step 5a — Update the AMD define header

Replace lines 1–27 (the `define([...], function(...) {` block). Remove `"simple-statistics.min"` and `SimpleStatistics`; add the two new deps at the end.

Old:
```javascript
define([
  "lodash",
  "jquery",
  "microevent",
  "./exercise_chord",
  "./exercise_chord_bank",
  "app/config",
  "app/components/events",
  "simple-statistics.min",
  "./exercise_completion_flow_logic",
  "./identification_submit_flow_logic",
  "app/models/harmonization_grader_logic",
  "app/models/voice_leading_logic",
], function (
  _,
  $,
  MicroEvent,
  ExerciseChord,
  ExerciseChordBank,
  Config,
  EVENTS,
  SimpleStatistics,
  ExerciseCompletionFlow,
  IdentificationSubmitFlow,
  HarmonizationGraderLogic,
  VoiceLeadingLogic
) {
```

New:
```javascript
define([
  "lodash",
  "jquery",
  "microevent",
  "./exercise_chord",
  "./exercise_chord_bank",
  "app/config",
  "app/components/events",
  "./exercise_completion_flow_logic",
  "./identification_submit_flow_logic",
  "app/models/harmonization_grader_logic",
  "app/models/voice_leading_logic",
  "app/models/exercise_context_timer_logic",
  "app/models/exercise_context_ident_page_logic",
], function (
  _,
  $,
  MicroEvent,
  ExerciseChord,
  ExerciseChordBank,
  Config,
  EVENTS,
  ExerciseCompletionFlow,
  IdentificationSubmitFlow,
  HarmonizationGraderLogic,
  VoiceLeadingLogic,
  TimerLogic,
  IdentPageLogic
) {
```

- [ ] Make the define header change above.

### Step 5b — Replace resetTimer body (lines ~454–467)

Old:
```javascript
    resetTimer: function () {
      this.timer = {};
      this.timer.start = null;
      this.timer.end = null;
      this.timer.duration = null;
      this.timer.durationString = "";
      this.timer.minTempo = null;
      this.timer.maxTempo = null;
      this.timer.tempoSD = null;
      this.timer.tempoRating = null;
      this.timer.timepoints = {};
      this.timer.timeIntervals = [];
      return this;
    },
```

New:
```javascript
    resetTimer: function () {
      this.timer = TimerLogic.createTimerState();
      return this;
    },
```

- [ ] Make this replacement.

### Step 5c — Replace endTimer body (lines ~526–640)

Old (full function):
```javascript
    endTimer: function () {
      if (!this.timer) return this;

      if (this.timer.start && !this.timer.end) {
        this.timer.end = new Date().getTime(); /* date in milliseconds */
        this.timer.duration =
          this.timer.end - this.timer.start; /* duration in milliseconds */
        let seconds = Math.round(this.timer.duration / 1000);
        const minutes = Math.floor(seconds / 60);
        seconds %= 60;
        this.timer.durationString = "";
        if (minutes > 0) {
          this.timer.durationString += String(minutes) + "&prime;&nbsp;";
        }
        this.timer.durationString += String(seconds) + "&Prime;";
      }

      var tp = this.timer.timepoints;
      var tp_indeces = Object.keys(tp).sort(function (a, b) {
        return a - b;
      });
      for (var i = 1, len = tp_indeces.length; i < len; i++) {
        this.timer.timeIntervals.push(
          tp[tp_indeces[i]] - tp[tp_indeces[i - 1]]
        );
      }

      // console.log(this.timer.timeIntervals);

      var semibreve_fraction = {
        W: 1.5,
        w: 1,
        H: 0.75,
        h: 0.5,
        Q: 0.375,
        q: 0.25,
        E: 0.1875,
        e: 0.125,
      };

      var semibreveCount = [];
      len = Math.min(
        this.inputChords._items.length,
        this.exerciseChords.settings.chords.length
      );
      for (i = 0; i < len; i++) {
        var rhythm_value =
          this.exerciseChords.settings.chords[i].settings.rhythm ||
          DEFAULT_RHYTHM_VALUE;
        semibreveCount.push(
          semibreve_fraction[rhythm_value] || DEFAULT_RHYTHM_VALUE || 1
        );
      }
      if (semibreveCount.length > 0) semibreveCount.pop();

      // necessary?
      this.timer.minTempo = null;
      this.timer.maxTempo = null;
      this.timer.tempoSD = null;
      this.timer.tempoRating = null;

      if (
        this.timer.timeIntervals.length > 1 &&
        /* need at least three events to determine tempo consistency */
        this.timer.timeIntervals.length == semibreveCount.length
        /* guard against miscalculations */
      ) {
        var centisemibrevesPerMin = [];
        for (i = 0, len = this.timer.timeIntervals.length; i < len; i++) {
          let spm = Math.round(
            (semibreveCount[i] * 6000000) / this.timer.timeIntervals[i]
          ); /* centi-semibreves per minute ... yup, because integer math is less troublesome */
          centisemibrevesPerMin.push(spm);
        }

        this.timer.tempoSD =
          Math.round(
            SimpleStatistics.standardDeviation(centisemibrevesPerMin)
          ) / 100; /* semibreves per minute sensitive to two decimal places */
        this.timer.tempoMean =
          Math.round(SimpleStatistics.mean(centisemibrevesPerMin) / 10) /
          10; /* semibreves per minute sensitive to one decimal place */
        this.timer.minTempo =
          Math.round(Math.min(...centisemibrevesPerMin)) / 100;
        this.timer.maxTempo =
          Math.round(Math.max(...centisemibrevesPerMin)) / 100;

        /* Tempo star-rating algorithm */
        // TO DO: ADD GRADATIONS BECAUSE SD AS 1/8 OF MEAN IS TOO NARROW FOR TWO STARS
        try {
          this.timer.tempoRating =
            /* If the SD is equal to or less than 1/(2^n) of the mean
             * then the star-rating is n-1:
             *    1/8 or less: two stars
             *    1/16 or less: three stars
             *    1/32 or less: four stars
             *    1/64 or less: five stars */
            Math.max(
              1, // at least
              Math.min(
                5, // at most
                this.timer.tempoSD == 0
                  ? 5 // if there is no tempo variation
                  : Math.floor(
                      this.timer.tempoMean / this.timer.tempoSD
                    ).toString(2).length - 1 // toString(2) renders a binary number
              )
            ) || 0; // in case calculation fails
        } catch {
          /* 0 means tempo cannot be assessed (e.g. when an exercise comprises two chords) */
          this.timer.tempoRating = 0;
        }
      }
      return this;
    },
```

New:
```javascript
    endTimer: function () {
      if (!this.timer) return this;

      if (this.timer.start && !this.timer.end) {
        this.timer.end = new Date().getTime();
        this.timer.duration = this.timer.end - this.timer.start;
        this.timer.durationString = TimerLogic.formatDurationString(this.timer.duration);
      }

      this.timer.timeIntervals = TimerLogic.computeTempoIntervals(this.timer.timepoints);

      var semibreveCount = TimerLogic.computeSemibreveCount(
        this.exerciseChords.settings.chords,
        this.inputChords._items.length,
        DEFAULT_RHYTHM_VALUE
      );

      this.timer.minTempo = null;
      this.timer.maxTempo = null;
      this.timer.tempoSD = null;
      this.timer.tempoRating = null;

      if (
        this.timer.timeIntervals.length > 1 &&
        this.timer.timeIntervals.length === semibreveCount.length
      ) {
        var centisemibrevesPerMin = TimerLogic.computeCentisemibrevesPerMin(
          this.timer.timeIntervals,
          semibreveCount
        );
        var stats = TimerLogic.computeTempoStats(centisemibrevesPerMin);
        this.timer.tempoSD    = stats.tempoSD;
        this.timer.tempoMean  = stats.tempoMean;
        this.timer.minTempo   = stats.minTempo;
        this.timer.maxTempo   = stats.maxTempo;
        this.timer.tempoRating = TimerLogic.computeTempoRating(stats.tempoSD, stats.tempoMean);
      }
      return this;
    },
```

- [ ] Make this replacement.

### Step 5d — Replace _getChoraleIdentPageMeasureCount body (lines ~1022–1027)

Old:
```javascript
    _getChoraleIdentPageMeasureCount: function () {
      var display = this.definition && this.definition.getDisplay
        ? this.definition.getDisplay()
        : {};
      var maxMeasures = parseInt(display && display.maxMeasures, 10);
      return maxMeasures > 0 ? maxMeasures : 4;
    },
```

New:
```javascript
    _getChoraleIdentPageMeasureCount: function () {
      var display = this.definition && this.definition.getDisplay
        ? this.definition.getDisplay()
        : {};
      return IdentPageLogic.getChoralePageMeasureCount(display);
    },
```

- [ ] Make this replacement.

### Step 5e — Replace getIdentPageOffset body (lines ~1034–1048)

Old:
```javascript
    getIdentPageOffset: function () {
      if (this.definition && typeof this.definition.isChoraleIdentification === "function" && this.definition.isChoraleIdentification()) {
         var maxMeasures = this._getChoraleIdentPageMeasureCount();
         var totalMeasures = this.definition.getScore() && this.definition.getScore().measures ? this.definition.getScore().measures.length : 0;
         var targetMeasure = this._identPage * maxMeasures;
         var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
         if (targetMeasure > lastPossibleStart) targetMeasure = lastPossibleStart;
         var problems = this.definition.getProblems() || [];
         for (var i = 0; i < problems.length; i++) {
            if (problems[i].measureIndex >= targetMeasure) return i;
         }
         return problems.length;
      }
      return this._identPage * this._identPageSize;
    },
```

New:
```javascript
    getIdentPageOffset: function () {
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.computeIdentPageOffset(this._identPage, this._identPageSize, false, [], 0, 0);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.computeIdentPageOffset(
        this._identPage, this._identPageSize, true,
        this.definition.getProblems() || [], totalMeasures, maxMeasures
      );
    },
```

- [ ] Make this replacement.

### Step 5f — Replace getTotalIdentPages body (lines ~1054–1063)

Old:
```javascript
    getTotalIdentPages: function () {
      var allProblems = this.definition.getProblems() || [];
      if (this.definition && typeof this.definition.isChoraleIdentification === "function" && this.definition.isChoraleIdentification()) {
          if (!allProblems || !allProblems.length) return 1;
          var totalMeasures = this.definition.getScore() && this.definition.getScore().measures ? this.definition.getScore().measures.length : 0;
          var maxMeasures = this._getChoraleIdentPageMeasureCount();
          return Math.ceil(totalMeasures / maxMeasures);
      }
      return Math.ceil(allProblems.length / this._identPageSize);
    },
```

New:
```javascript
    getTotalIdentPages: function () {
      var allProblems = this.definition.getProblems() || [];
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.computeTotalIdentPages(allProblems, false, 0, 0, this._identPageSize);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.computeTotalIdentPages(allProblems, true, totalMeasures, maxMeasures, this._identPageSize);
    },
```

- [ ] Make this replacement.

### Step 5g — Replace getVisibleProblems body (lines ~1069–1084)

Old:
```javascript
    getVisibleProblems: function () {
      var allProblems = this.definition.getProblems() || [];
      if (this.definition && typeof this.definition.isChoraleIdentification === "function" && this.definition.isChoraleIdentification()) {
          var maxMeasures = this._getChoraleIdentPageMeasureCount();
          var totalMeasures = this.definition.getScore() && this.definition.getScore().measures ? this.definition.getScore().measures.length : 0;
          var startMeasure = this._identPage * maxMeasures;
          var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
          if (startMeasure > lastPossibleStart) startMeasure = lastPossibleStart;
          var endMeasure = startMeasure + maxMeasures;
          return allProblems.filter(function(p) {
             return p.measureIndex >= startMeasure && p.measureIndex < endMeasure;
          });
      }
      var offset = this.getIdentPageOffset();
      return allProblems.slice(offset, offset + this._identPageSize);
    },
```

New:
```javascript
    getVisibleProblems: function () {
      var allProblems = this.definition.getProblems() || [];
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.filterVisibleProblems(allProblems, false, this._identPage, this._identPageSize, 0, 0);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.filterVisibleProblems(
        allProblems, true, this._identPage, this._identPageSize, totalMeasures, maxMeasures
      );
    },
```

- [ ] Make this replacement.

### Step 5h — Verify no remaining bare `SimpleStatistics` references

```bash
grep -n "SimpleStatistics\|simple-statistics" lab/static/js/src/models/exercise_context.js
```

Expected: no output.

- [ ] Commit:

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "refactor(js): replace inline timer and ident-page helpers with logic modules"
```

---

## Task 6: Verify

**Files:** No changes.

- [ ] Run both new logic test suites:

```bash
node lab/static/js/src/models/exercise_context_timer_logic.test.js
node lab/static/js/src/models/exercise_context_ident_page_logic.test.js
```

Expected: all tests pass for both.

- [ ] Run the existing Node.js logic test suites to confirm nothing is broken:

```bash
node lab/static/js/src/models/exercise_definition_logic.test.js
node lab/static/js/src/models/chordal_problems_logic.test.js
node lab/static/js/src/models/input_method_logic.test.js
node lab/static/js/src/models/key_context_logic.test.js
node lab/static/js/src/models/exercise_definition_label_logic.test.js
```

Expected: all pass.

- [ ] Run the Django test suite:

```bash
python manage.py test apps.exercises apps.student --settings=harmony.settings.local -v 1
```

Expected: all existing tests pass.

- [ ] Check line count reduction:

```bash
wc -l lab/static/js/src/models/exercise_context.js \
       lab/static/js/src/models/exercise_context_timer_logic.js \
       lab/static/js/src/models/exercise_context_ident_page_logic.js
```

Expected: `exercise_context.js` near 1,370 lines (down from 1,484); timer module ~90 lines; ident-page module ~55 lines.

- [ ] Final commit if any issues were fixed during verification (otherwise skip):

```bash
git add -p
git commit -m "fix(js): address issues found during exercise_context split verification"
```

---

## Self-Review

**Spec coverage:**
- Timer methods (`triggerTimer`, `resetTimer`, `hasTimer`, `getExerciseDuration`, `getMinTempo`, `getMaxTempo`, `getTempoMean`, `getTempoRating`): getter methods stay on prototype; `resetTimer` now delegates to `TimerLogic.createTimerState()`; `endTimer` fully delegated to TimerLogic helpers. ✓
- Report compilation (`compileExerciseReport`): deeply entangled with `this.definition`, `this.timer`, `window.location` — NOT extracted (no pure core to isolate without large param bag). Deferred per the "Methods with jQuery/ajax/DOM deps are NOT good candidates" constraint. ✓
- Ident pagination state (`getIdentPage`, `getIdentPageSize`, `getIdentPageOffset`, `getTotalIdentPages`, `getVisibleProblems`, `goToIdentPage`): trivial getters and `goToIdentPage` (uses DOM + setTimeout) stay on prototype; offset/total/filter pure cores extracted to IdentPageLogic. ✓

**Placeholder scan:** No TBDs. All code blocks complete. ✓

**Type consistency:** `IdentPageLogic.computeIdentPageOffset(identPage, identPageSize, isChoraleIdent, problems, totalMeasures, maxMeasures)` — 6-arg signature consistent across all three callers (getIdentPageOffset, getTotalIdentPages uses computeTotalIdentPages not computeIdentPageOffset — different function). `TimerLogic.computeTempoStats(centisemibrevesPerMin)` returns `{tempoSD, tempoMean, minTempo, maxTempo}` — all four keys consumed in endTimer. ✓

**AMD module identity:** `exercise_context.js` AMD ID unchanged (it's a return value at end, not a `define` with id string). Only internal dep list changes. ✓

**SimpleStatistics removal:** only usage was the two calls in endTimer, replaced by `computeTempoStats`. Removing the AMD dep is safe. ✓
