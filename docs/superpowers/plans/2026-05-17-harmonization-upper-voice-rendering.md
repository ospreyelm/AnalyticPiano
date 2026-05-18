# Harmonization Upper-Voice Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw the student's accepted upper-voice pitches (S/A/T) on the treble staff in harmonization exercises, one chord per accepted target, using the source UMTO's canonical spelling.

**Architecture:** A new pure module `harmonization_realization_logic.js` builds a per-accepted-target payload (`harmonizationRealization`) from `ExerciseContext.acceptedHarmonizationSonorities`, source CIR score, and the targets list. `exercise_sheet.js` constructs the payload on each render and passes it to `VexFlowAdapter.render`. The adapter adds an opt-in overlay voice on the treble staff for each measure containing realization entries — a single `StaveNote` chord at each entry's onset, padded with transparent rests so the overlay Voice's tick total equals the measure's tick total. Triggered by the existing `"graded"` event re-render — no new wiring.

**Tech Stack:** RequireJS AMD modules; VexFlow 4 (`Vex.Flow.StaveNote`, `Vex.Flow.Voice`, `Vex.Flow.Formatter`); plain Node `require()` test modules executed via `node <file>.test.js` (existing convention).

**Spec:** [docs/superpowers/specs/2026-05-17-harmonization-upper-voice-rendering-design.md](../specs/2026-05-17-harmonization-upper-voice-rendering-design.md)

---

## File Structure

**New files:**

- `lab/static/js/src/models/harmonization_realization_logic.js` — pure builder
  - `buildPcSpellingMap(score, targetOffsetQb)` → `{ <pc>: {step, alter} }`
  - `spellMidi(midi, pcMap)` → `{step, alter, octave}` or `null`
  - `buildRealization(accepted, targets, score, meter)` → array of payload entries
  - `ticksToDurationChunks(ticks)` → `[{type, dots, ticks}, ...]` (greedy)
- `lab/static/js/src/models/harmonization_realization_logic.test.js` — node test file

**Modified files:**

- `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
  - Accept new `harmonizationRealization` opt (default `null`)
  - New internal helper `buildHarmonizationOverlayVoice(entries, measureIndex, measureTotalTicks, time, keySignatureAlterations)` returning a `Vex.Flow.Voice` or `null`
  - In per-measure render loop: build overlay, push onto `trebleVoices` before `joinVoices`
- `lab/static/js/src/components/music/exercise_sheet.js`
  - In the existing `isHarmonization && this.exerciseContext` block (~line 1693), build `harmonizationRealizationPayload` via the new logic module
  - Pass `harmonizationRealization: harmonizationRealizationPayload` into the `VexFlowAdapter.render(...)` opts

No backend / Python changes. No model changes.

---

## Task 1: Greedy `ticksToDurationChunks` helper + tests

**Files:**
- Create: `lab/static/js/src/models/harmonization_realization_logic.js`
- Create: `lab/static/js/src/models/harmonization_realization_logic.test.js`

- [ ] **Step 1: Write failing tests for `ticksToDurationChunks`**

Create `lab/static/js/src/models/harmonization_realization_logic.test.js`:

```js
"use strict";

var logic = require("./harmonization_realization_logic");

var failed = 0;

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label);
    console.log("  got:     ", JSON.stringify(actual));
    console.log("  expected:", JSON.stringify(expected));
    failed += 1;
  } else {
    console.log("PASS:", label);
  }
}

// ticksToDurationChunks
assertEqual("quarter exact",
  logic.ticksToDurationChunks(1024),
  [{ type: "q", dots: 0, ticks: 1024 }]);

assertEqual("dotted half exact",
  logic.ticksToDurationChunks(3072),
  [{ type: "h", dots: 1, ticks: 3072 }]);

assertEqual("whole exact",
  logic.ticksToDurationChunks(4096),
  [{ type: "w", dots: 0, ticks: 4096 }]);

assertEqual("quarter + eighth (1536) prefers dotted quarter",
  logic.ticksToDurationChunks(1536),
  [{ type: "q", dots: 1, ticks: 1536 }]);

assertEqual("half + quarter chunks to half + quarter (greedy)",
  logic.ticksToDurationChunks(3072 + 1024 - 0).slice(0, 1),
  [{ type: "w", dots: 0, ticks: 4096 }]);

assertEqual("eighth (512)",
  logic.ticksToDurationChunks(512),
  [{ type: "8", dots: 0, ticks: 512 }]);

assertEqual("128 ticks = 32nd",
  logic.ticksToDurationChunks(128),
  [{ type: "32", dots: 0, ticks: 128 }]);

assertEqual("greedy split 1280 = q + 16",
  logic.ticksToDurationChunks(1280),
  [
    { type: "q", dots: 0, ticks: 1024 },
    { type: "16", dots: 0, ticks: 256 }
  ]);

assertEqual("undivisible remainder returns null",
  logic.ticksToDurationChunks(100),
  null);

assertEqual("zero ticks returns empty array",
  logic.ticksToDurationChunks(0),
  []);

if (failed > 0) { console.log("\n" + failed + " test(s) FAILED"); process.exit(1); }
else { console.log("\nAll tests passed."); }
```

- [ ] **Step 2: Run tests, expect MODULE_NOT_FOUND**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `Error: Cannot find module './harmonization_realization_logic'`

- [ ] **Step 3: Create module with `ticksToDurationChunks`**

Create `lab/static/js/src/models/harmonization_realization_logic.js`:

```js
"use strict";

// Supported atoms in descending tick order. Each atom is { type, dots, ticks }
// matching the CIR duration shape used by score_timeline.js / vexflow_adapter.js.
var ATOMS = [
  { type: "w",  dots: 0, ticks: 4096 },
  { type: "h",  dots: 1, ticks: 3072 },
  { type: "h",  dots: 0, ticks: 2048 },
  { type: "q",  dots: 1, ticks: 1536 },
  { type: "q",  dots: 0, ticks: 1024 },
  { type: "8",  dots: 1, ticks: 768 },
  { type: "8",  dots: 0, ticks: 512 },
  { type: "16", dots: 1, ticks: 384 },
  { type: "16", dots: 0, ticks: 256 },
  { type: "32", dots: 0, ticks: 128 }
];

function ticksToDurationChunks(ticks) {
  if (ticks === 0) return [];
  var remaining = ticks;
  var out = [];
  while (remaining > 0) {
    var picked = null;
    for (var i = 0; i < ATOMS.length; i += 1) {
      if (ATOMS[i].ticks <= remaining) { picked = ATOMS[i]; break; }
    }
    if (!picked) return null;
    out.push({ type: picked.type, dots: picked.dots, ticks: picked.ticks });
    remaining -= picked.ticks;
  }
  return out;
}

var exports = {
  ticksToDurationChunks: ticksToDurationChunks
};

if (typeof define === "function" && define.amd) {
  define([], function () { return exports; });
} else if (typeof module !== "undefined") {
  module.exports = exports;
}
```

- [ ] **Step 4: Run tests, expect all PASS**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `All tests passed.`

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_realization_logic.js \
        lab/static/js/src/models/harmonization_realization_logic.test.js
git commit -m "feat(harmonization): add ticksToDurationChunks greedy helper"
```

---

## Task 2: `spellMidi` octave-aware spelling helper

**Files:**
- Modify: `lab/static/js/src/models/harmonization_realization_logic.js`
- Modify: `lab/static/js/src/models/harmonization_realization_logic.test.js`

- [ ] **Step 1: Add failing tests for `spellMidi`**

Append to `lab/static/js/src/models/harmonization_realization_logic.test.js` before the `if (failed > 0)` block:

```js
// spellMidi: octave label follows natural-letter base, not sounding pitch
var pcMap = {
  0:  { step: "C", alter: 0 },
  11: { step: "B", alter: 0 }
};

assertEqual("spellMidi C4 natural",
  logic.spellMidi(60, { 0: { step: "C", alter: 0 } }),
  { step: "C", alter: 0, octave: 4 });

assertEqual("spellMidi Cb5 (sounds B4 / midi 71)",
  logic.spellMidi(71, { 11: { step: "C", alter: -1 } }),
  { step: "C", alter: -1, octave: 5 });

assertEqual("spellMidi B#4 (sounds C5 / midi 72)",
  logic.spellMidi(72, { 0: { step: "B", alter: 1 } }),
  { step: "B", alter: 1, octave: 4 });

assertEqual("spellMidi Cbb5 (sounds Bb4 / midi 70)",
  logic.spellMidi(70, { 10: { step: "C", alter: -2 } }),
  { step: "C", alter: -2, octave: 5 });

assertEqual("spellMidi B##4 (sounds C#5 / midi 73)",
  logic.spellMidi(73, { 1: { step: "B", alter: 2 } }),
  { step: "B", alter: 2, octave: 4 });

assertEqual("spellMidi returns null when pc missing from map",
  logic.spellMidi(60, { 7: { step: "G", alter: 0 } }),
  null);
```

- [ ] **Step 2: Run tests, expect FAIL (spellMidi undefined)**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: 6 FAILs with `logic.spellMidi is not a function`.

- [ ] **Step 3: Implement `spellMidi`**

In `harmonization_realization_logic.js`, add before the `exports` block:

```js
function spellMidi(midi, pcMap) {
  var pc = ((midi % 12) + 12) % 12;
  var entry = pcMap[pc];
  if (!entry) return null;
  // Octave label follows the natural letter, not the sounding pitch.
  // Subtract alter to land on the letter's natural MIDI, then convert that
  // MIDI to its standard octave label. Handles B#/Cb (and double accidentals)
  // across octave boundaries.
  var letterBaseMidi = midi - entry.alter;
  var octave = Math.floor(letterBaseMidi / 12) - 1;
  return { step: entry.step, alter: entry.alter, octave: octave };
}
```

Update the `exports` literal:

```js
var exports = {
  ticksToDurationChunks: ticksToDurationChunks,
  spellMidi: spellMidi
};
```

- [ ] **Step 4: Run tests, expect all PASS**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `All tests passed.`

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_realization_logic.js \
        lab/static/js/src/models/harmonization_realization_logic.test.js
git commit -m "feat(harmonization): add spellMidi for canonical step/alter→octave"
```

---

## Task 3: `buildPcSpellingMap` via ScoreTimeline

**Files:**
- Modify: `lab/static/js/src/models/harmonization_realization_logic.js`
- Modify: `lab/static/js/src/models/harmonization_realization_logic.test.js`

**Context:** `ScoreTimeline.buildTimeline(score)` returns events shaped like
`{ id, onset, duration, midi, step, alter, staff, voiceIndex, measureIndex, itemIndex, headIndex }`
with `onset` and `duration` in ticks (1024 ticks per quarter). The timeline already carries
`step` and `alter` per event, so the realization builder reads the spelling directly off the
event rather than indexing back into the score.

- [ ] **Step 1: Add failing tests for `buildPcSpellingMap`**

Append to the test file (before `if (failed > 0)`):

```js
// buildPcSpellingMap: pc→{step,alter} for non-rest pitches sounding at offset
// Inject a fake ScoreTimeline so the test does not need a full CIR score.
var ScoreTimelineStub = {
  events: [],
  buildTimeline: function () { return this.events; }
};
require.cache[require.resolve("./harmonization_realization_logic")].exports.__setScoreTimeline(ScoreTimelineStub);

// Single chord at offset 0 (ticks 0). Quarter at 1024 ticks → covers offsets [0,1024).
ScoreTimelineStub.events = [
  { onset: 0, duration: 1024, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 67, step: "G", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 1024, midi: 48, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];

assertEqual("pcMap at offset 0 contains C/E/G",
  logic.buildPcSpellingMap({}, 0),
  { 0: { step: "C", alter: 0 }, 4: { step: "E", alter: 0 }, 7: { step: "G", alter: 0 } });

// F# in source → pc 6 spelled with alter +1
ScoreTimelineStub.events = [
  { onset: 0, duration: 1024, midi: 66, step: "F", alter: 1, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("pcMap reflects sharp from source",
  logic.buildPcSpellingMap({}, 0),
  { 6: { step: "F", alter: 1 } });

// Tied/held note across barline: D5 held from m1 beat 4 into m2 beat 1.
// m1 ticks 0..4096, beat 4 starts at tick 3072. Note duration 2048 ticks → sounds through 5120.
// Target offset is m2 beat 1 = absolute quarter-beat 4 → 4096 ticks.
ScoreTimelineStub.events = [
  { onset: 3072, duration: 2048, midi: 74, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 3, headIndex: 0 }
];
assertEqual("pcMap includes notes held across barline",
  logic.buildPcSpellingMap({}, 4),
  { 2: { step: "D", alter: 0 } });

// Offset in quarter-beats with rounding: 2.5 qb → 2560 ticks
ScoreTimelineStub.events = [
  { onset: 2560, duration: 512, midi: 62, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 5, headIndex: 0 }
];
assertEqual("pcMap honors fractional qb offsets via tick rounding",
  logic.buildPcSpellingMap({}, 2.5),
  { 2: { step: "D", alter: 0 } });
```

- [ ] **Step 2: Run tests, expect FAIL (`__setScoreTimeline` undefined)**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `TypeError: ...__setScoreTimeline is not a function`.

- [ ] **Step 3: Implement `buildPcSpellingMap` with injectable ScoreTimeline**

In `harmonization_realization_logic.js`, replace the file with:

```js
"use strict";

var ATOMS = [
  { type: "w",  dots: 0, ticks: 4096 },
  { type: "h",  dots: 1, ticks: 3072 },
  { type: "h",  dots: 0, ticks: 2048 },
  { type: "q",  dots: 1, ticks: 1536 },
  { type: "q",  dots: 0, ticks: 1024 },
  { type: "8",  dots: 1, ticks: 768 },
  { type: "8",  dots: 0, ticks: 512 },
  { type: "16", dots: 1, ticks: 384 },
  { type: "16", dots: 0, ticks: 256 },
  { type: "32", dots: 0, ticks: 128 }
];

function ticksToDurationChunks(ticks) {
  if (ticks === 0) return [];
  var remaining = ticks;
  var out = [];
  while (remaining > 0) {
    var picked = null;
    for (var i = 0; i < ATOMS.length; i += 1) {
      if (ATOMS[i].ticks <= remaining) { picked = ATOMS[i]; break; }
    }
    if (!picked) return null;
    out.push({ type: picked.type, dots: picked.dots, ticks: picked.ticks });
    remaining -= picked.ticks;
  }
  return out;
}

function spellMidi(midi, pcMap) {
  var pc = ((midi % 12) + 12) % 12;
  var entry = pcMap[pc];
  if (!entry) return null;
  var letterBaseMidi = midi - entry.alter;
  var octave = Math.floor(letterBaseMidi / 12) - 1;
  return { step: entry.step, alter: entry.alter, octave: octave };
}

// Resolved lazily so unit tests can inject a stub before any call.
var _ScoreTimeline = null;
function getScoreTimeline() {
  if (_ScoreTimeline) return _ScoreTimeline;
  if (typeof require === "function" && typeof module !== "undefined") {
    try { _ScoreTimeline = require("../components/music/score_timeline"); } catch (e) {}
  }
  return _ScoreTimeline;
}
function __setScoreTimeline(stub) { _ScoreTimeline = stub; }

function buildPcSpellingMap(score, targetOffsetQb) {
  var ST = getScoreTimeline();
  if (!ST || typeof ST.buildTimeline !== "function") return {};
  var timeline = ST.buildTimeline(score) || [];
  var targetTick = Math.round(targetOffsetQb * 1024);
  var pcMap = {};
  for (var i = 0; i < timeline.length; i += 1) {
    var ev = timeline[i];
    if (typeof ev.midi !== "number") continue;
    var sounding = (ev.onset <= targetTick) && (ev.onset + ev.duration > targetTick);
    if (!sounding) continue;
    var pc = ((ev.midi % 12) + 12) % 12;
    if (!pcMap[pc]) pcMap[pc] = { step: ev.step, alter: ev.alter || 0 };
  }
  return pcMap;
}

var exports = {
  ticksToDurationChunks: ticksToDurationChunks,
  spellMidi: spellMidi,
  buildPcSpellingMap: buildPcSpellingMap,
  __setScoreTimeline: __setScoreTimeline
};

if (typeof define === "function" && define.amd) {
  define(["app/components/music/score_timeline"], function (ST) {
    __setScoreTimeline(ST);
    return exports;
  });
} else if (typeof module !== "undefined") {
  module.exports = exports;
}
```

- [ ] **Step 4: Run tests, expect all PASS**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `All tests passed.`

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_realization_logic.js \
        lab/static/js/src/models/harmonization_realization_logic.test.js
git commit -m "feat(harmonization): add buildPcSpellingMap via ScoreTimeline"
```

---

## Task 4: `buildRealization` builder

**Files:**
- Modify: `lab/static/js/src/models/harmonization_realization_logic.js`
- Modify: `lab/static/js/src/models/harmonization_realization_logic.test.js`

**Context:**
- `accepted` entries from `ExerciseContext`: `{ midi: number[], targetIndex: number, ts: number }`
- `targets[i]` shape: `{ offset: <quarter-beats>, bassMidi, bassPc, allowedPcs, lockedVoices: { B: {midi, pc, spelling}, ... }, ... }`
- `meter`: `{ numerator, denominator }` derived from CIR `score.meta.time` ("4/4")
- Output entries (one per accepted target): `{ measureIndex, onset, durationTicks, midiNotes, spellings }`

The measure tick total in CIR is `numerator * (4096 / denominator)` (matches `fullMeasureTicks` formula in adapter at line 1152).

- [ ] **Step 1: Add failing tests for `buildRealization`**

Append to the test file (before `if (failed > 0)`):

```js
// buildRealization
// Reuse the ScoreTimelineStub fixture above (single C/E/G chord at offset 0).
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 67, step: "G", alter: 0, staff: "bass",   voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
var meter = { numerator: 4, denominator: 4 };
var targets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0, spelling: "C" } } }
];

assertEqual("buildRealization: single target, bass dropped, S/A/T spelled",
  logic.buildRealization(
    [{ midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 }],
    targets, {}, meter),
  [{
    measureIndex: 0,
    onset: 0,
    durationTicks: 4096,
    midiNotes: [60, 64, 67],
    spellings: [
      { step: "C", alter: 0, octave: 4 },
      { step: "E", alter: 0, octave: 4 },
      { step: "G", alter: 0, octave: 4 }
    ]
  }]);

assertEqual("buildRealization: bass MIDI dropped once, upper-octave doubling kept",
  logic.buildRealization(
    [{ midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 }],
    targets, {}, meter)[0].midiNotes,
  [60, 64, 67]);

// Student plays bass 36 plus pc=0 doublings at 48 and 60 (no second 36)
assertEqual("buildRealization: only the bass MIDI instance dropped, not all pc matches",
  logic.buildRealization(
    [{ midi: [36, 48, 60, 64], targetIndex: 0, ts: 1 }],
    targets, {}, meter)[0].midiNotes,
  [48, 60, 64]);

// lockedVoices.B.midi absent → fall back to pc match
var pcTargets = [
  { offset: 0, lockedVoices: { B: { pc: 0, spelling: "C" } } }
];
assertEqual("buildRealization: missing bass midi falls back to dropping one pc match",
  logic.buildRealization(
    [{ midi: [60, 64, 67], targetIndex: 0, ts: 1 }],
    pcTargets, {}, meter)[0].midiNotes,
  [64, 67]);

// Duplicate accepted entries for same targetIndex → keep most recent (by ts)
assertEqual("buildRealization: dedupes duplicate targetIndex, keeps most recent",
  logic.buildRealization(
    [
      { midi: [36, 60, 64, 67], targetIndex: 0, ts: 1 },
      { midi: [36, 62, 65, 69], targetIndex: 0, ts: 2 }
    ],
    targets, {}, meter)[0].midiNotes.length,
  3);

// Multi-target same measure: durationTicks runs to next target's onset
var twoTargets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } },
  { offset: 2, lockedVoices: { B: { midi: 36, pc: 0 } } }
];
ScoreTimelineStub.events = [
  { onset: 0, duration: 2048, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 2048, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 2048, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 62, step: "D", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 1, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 67, step: "G", alter: 0, staff: "treble", voiceIndex: 1, measureIndex: 0, itemIndex: 1, headIndex: 0 },
  { onset: 2048, duration: 2048, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 1, headIndex: 0 }
];
var twoOut = logic.buildRealization(
  [
    { midi: [36, 60, 64], targetIndex: 0, ts: 1 },
    { midi: [36, 62, 67], targetIndex: 1, ts: 2 }
  ],
  twoTargets, {}, meter);
assertEqual("buildRealization: first entry durationTicks = next onset",
  twoOut[0].durationTicks, 2048);
assertEqual("buildRealization: last entry durationTicks = measure end",
  twoOut[1].durationTicks, 2048);

// Cross-measure: target at offset 4 (m2 beat 1)
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 60, step: "C", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 4096, duration: 4096, midi: 64, step: "E", alter: 0, staff: "treble", voiceIndex: 0, measureIndex: 1, itemIndex: 0, headIndex: 0 },
  { onset: 4096, duration: 4096, midi: 43, step: "G", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 1, itemIndex: 0, headIndex: 0 }
];
var twoMeasureTargets = [
  { offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } },
  { offset: 4, lockedVoices: { B: { midi: 43, pc: 7 } } }
];
var twoMeasOut = logic.buildRealization(
  [
    { midi: [36, 60], targetIndex: 0, ts: 1 },
    { midi: [43, 64], targetIndex: 1, ts: 2 }
  ],
  twoMeasureTargets, {}, meter);
assertEqual("buildRealization: second target lands in measure 1",
  twoMeasOut[1].measureIndex, 1);
assertEqual("buildRealization: second target onset within its measure",
  twoMeasOut[1].onset, 0);

// Source-spelling lookup: F# in source → midi 66 spelled with alter +1
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 66, step: "F", alter: 1, staff: "treble", voiceIndex: 0, measureIndex: 0, itemIndex: 0, headIndex: 0 },
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass",   voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
var sharpOut = logic.buildRealization(
  [{ midi: [36, 66], targetIndex: 0, ts: 1 }],
  [{ offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } }],
  {}, meter);
assertEqual("buildRealization: F# spelled from source",
  sharpOut[0].spellings, [{ step: "F", alter: 1, octave: 4 }]);

// Empty upper voices (student plays only bass) → entry skipped
ScoreTimelineStub.events = [
  { onset: 0, duration: 4096, midi: 36, step: "C", alter: 0, staff: "bass", voiceIndex: 1, measureIndex: 0, itemIndex: 0, headIndex: 0 }
];
assertEqual("buildRealization: skips entry when no upper voices remain",
  logic.buildRealization(
    [{ midi: [36], targetIndex: 0, ts: 1 }],
    [{ offset: 0, lockedVoices: { B: { midi: 36, pc: 0 } } }],
    {}, meter),
  []);

// Empty input
assertEqual("buildRealization: returns [] for empty accepted",
  logic.buildRealization([], targets, {}, meter), []);
```

- [ ] **Step 2: Run tests, expect FAIL (`buildRealization` undefined)**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `TypeError: logic.buildRealization is not a function`.

- [ ] **Step 3: Implement `buildRealization`**

In `harmonization_realization_logic.js`, add before the `exports` block:

```js
function _measureTickTotal(meter) {
  var num = (meter && meter.numerator) || 4;
  var den = (meter && meter.denominator) || 4;
  return num * (4096 / den);
}

function _dropOneBassInstance(midiArr, target) {
  var bassMidi = target.lockedVoices && target.lockedVoices.B && target.lockedVoices.B.midi;
  var bassPc = target.lockedVoices && target.lockedVoices.B && target.lockedVoices.B.pc;
  var dropped = false;
  if (typeof bassMidi === "number") {
    return midiArr.filter(function (m) {
      if (!dropped && m === bassMidi) { dropped = true; return false; }
      return true;
    });
  }
  if (typeof bassPc === "number") {
    return midiArr.filter(function (m) {
      if (!dropped && (((m % 12) + 12) % 12) === bassPc) { dropped = true; return false; }
      return true;
    });
  }
  return midiArr.slice();
}

function buildRealization(accepted, targets, score, meter) {
  if (!accepted || !accepted.length) return [];
  var measureTotal = _measureTickTotal(meter);

  // 1. Dedupe by targetIndex, keep most recent (largest ts; falls back to last seen).
  var byIndex = {};
  for (var i = 0; i < accepted.length; i += 1) {
    var ent = accepted[i];
    var existing = byIndex[ent.targetIndex];
    if (!existing || (ent.ts || 0) >= (existing.ts || 0)) {
      byIndex[ent.targetIndex] = ent;
    }
  }

  // 2. Build raw entries (one per accepted target, in target-index order).
  var raw = [];
  var indices = Object.keys(byIndex).map(function (k) { return parseInt(k, 10); })
                                     .sort(function (a, b) { return a - b; });
  for (var k = 0; k < indices.length; k += 1) {
    var ti = indices[k];
    var target = targets[ti];
    if (!target) continue;

    var absOffsetQb = target.offset;
    var absOffsetTicks = Math.round(absOffsetQb * 1024);
    var measureIndex = Math.floor(absOffsetTicks / measureTotal);
    var onsetWithinMeasure = absOffsetTicks - (measureIndex * measureTotal);

    var upperMidi = _dropOneBassInstance(byIndex[ti].midi || [], target);
    if (!upperMidi.length) continue;
    upperMidi = upperMidi.slice().sort(function (a, b) { return a - b; });

    var pcMap = buildPcSpellingMap(score, absOffsetQb);
    var spellings = upperMidi.map(function (m) { return spellMidi(m, pcMap); });
    // If any spelling fails (should not happen for accepted notes), skip entry.
    if (spellings.indexOf(null) !== -1) continue;

    raw.push({
      measureIndex: measureIndex,
      onset: onsetWithinMeasure,
      _absOnsetTicks: absOffsetTicks,
      midiNotes: upperMidi,
      spellings: spellings
    });
  }

  // 3. Sort by (measureIndex, onset) and compute durationTicks per entry.
  raw.sort(function (a, b) {
    if (a.measureIndex !== b.measureIndex) return a.measureIndex - b.measureIndex;
    return a.onset - b.onset;
  });
  for (var j = 0; j < raw.length; j += 1) {
    var cur = raw[j];
    var nextSameMeasure = (j + 1 < raw.length) && (raw[j + 1].measureIndex === cur.measureIndex)
      ? raw[j + 1] : null;
    cur.durationTicks = nextSameMeasure
      ? (nextSameMeasure.onset - cur.onset)
      : (measureTotal - cur.onset);
    delete cur._absOnsetTicks;
  }
  return raw;
}
```

Update `exports`:

```js
var exports = {
  ticksToDurationChunks: ticksToDurationChunks,
  spellMidi: spellMidi,
  buildPcSpellingMap: buildPcSpellingMap,
  buildRealization: buildRealization,
  __setScoreTimeline: __setScoreTimeline
};
```

- [ ] **Step 4: Run tests, expect all PASS**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `All tests passed.`

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/models/harmonization_realization_logic.js \
        lab/static/js/src/models/harmonization_realization_logic.test.js
git commit -m "feat(harmonization): add buildRealization payload builder"
```

---

## Task 5: Adapter overlay voice + accept new render opt

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`

**Context:**
- Existing per-measure render loop runs `for (var measIdx = 0; measIdx < numMeasures; measIdx++)` at [vexflow_adapter.js:1326](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1326).
- `absoluteMeasureIndex = startMeasure + measIdx` ([line 1333](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1333)).
- `measureDurations[measIdx]` holds the measure's tick total (computed by the duration loop ending around line 1170).
- `time` is the VexFlow time signature object `{ num_beats, beat_value, resolution }` ([line 1015](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1015)).
- `keySignatureAlterations` is computed once per render and threaded into `staffVoices(...)` ([line 1375](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1375)) — reuse the same map for the overlay.
- `trebleVoices` is the array fed into `Formatter.joinVoices` ([line 1413](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1413)). Push the overlay onto this array before `joinVoices`.
- `buildVoice(time, tickables)` ([line 852](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L852)) wraps tickables in a `Vex.Flow.Voice` with `SOFT` mode — use it.

- [ ] **Step 1: Add `buildHarmonizationOverlayVoice` helper near `buildVoice`**

Insert after the `buildVoice` function definition (currently ending around line 858):

```js
  // Build a treble overlay Voice containing one chord StaveNote per realization
  // entry in this measure. Gaps before/between/after entries become transparent
  // rests so the Voice's total ticks equals measureTotalTicks (required by
  // Formatter.joinVoices).
  function buildHarmonizationOverlayVoice(entriesInMeasure, measureTotalTicks, voiceTime, keySigAlters) {
    if (!entriesInMeasure || !entriesInMeasure.length) return null;
    var sorted = entriesInMeasure.slice().sort(function (a, b) { return a.onset - b.onset; });
    var tickables = [];
    var cursor = 0;

    function emitTransparentRests(ticks) {
      if (ticks <= 0) return true;
      var chunks = HarmonizationRealizationLogic.ticksToDurationChunks(ticks);
      if (!chunks) return false;
      for (var c = 0; c < chunks.length; c += 1) {
        var r = new Vex.Flow.StaveNote({
          clef: "treble",
          keys: ["b/4"],
          duration: chunks[c].type + "r",
          dots: chunks[c].dots
        });
        if (chunks[c].dots > 0) Vex.Flow.Dot.buildAndAttach([r], { all: true });
        if (r.setStyle) r.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
        tickables.push(r);
      }
      return true;
    }

    for (var i = 0; i < sorted.length; i += 1) {
      var entry = sorted[i];
      if (entry.onset < cursor) return null; // overlap — bail
      if (!emitTransparentRests(entry.onset - cursor)) return null;

      var chunks = HarmonizationRealizationLogic.ticksToDurationChunks(entry.durationTicks);
      if (!chunks || !chunks.length) return null;
      var headChunk = chunks[0];

      var keys = entry.midiNotes.map(function (m, ki) {
        var sp = entry.spellings[ki];
        var acc = sp.alter === 1 ? "#"
                : sp.alter === -1 ? "b"
                : sp.alter === 2 ? "##"
                : sp.alter === -2 ? "bb"
                : "";
        return sp.step.toLowerCase() + acc + "/" + sp.octave;
      });

      var note = new Vex.Flow.StaveNote({
        clef: "treble",
        keys: keys,
        duration: headChunk.type,
        dots: headChunk.dots,
        auto_stem: false
      });
      if (headChunk.dots > 0) Vex.Flow.Dot.buildAndAttach([note], { all: true });
      note.setStemDirection(1);

      // Add accidentals only when the spelling contradicts the key signature.
      for (var ki2 = 0; ki2 < entry.spellings.length; ki2 += 1) {
        var sp2 = entry.spellings[ki2];
        var step2 = sp2.step.toUpperCase();
        var keyAlter = (keySigAlters && keySigAlters[step2]) || 0;
        if (sp2.alter !== keyAlter) {
          var accType = sp2.alter === 1 ? "#"
                      : sp2.alter === -1 ? "b"
                      : sp2.alter === 2 ? "##"
                      : sp2.alter === -2 ? "bb"
                      : "n";
          note.addModifier(new Vex.Flow.Accidental(accType), ki2);
        }
      }
      if (note.setStyle) note.setStyle({ fillStyle: "#000000", strokeStyle: "#000000" });
      tickables.push(note);
      cursor = entry.onset + headChunk.ticks;

      // Remaining chunks (if any) become transparent rests so the Voice's tick
      // total matches `entry.durationTicks`.
      for (var c2 = 1; c2 < chunks.length; c2 += 1) {
        var rr = new Vex.Flow.StaveNote({
          clef: "treble",
          keys: ["b/4"],
          duration: chunks[c2].type + "r",
          dots: chunks[c2].dots
        });
        if (chunks[c2].dots > 0) Vex.Flow.Dot.buildAndAttach([rr], { all: true });
        if (rr.setStyle) rr.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
        tickables.push(rr);
        cursor += chunks[c2].ticks;
      }
    }

    if (cursor > measureTotalTicks) return null;
    if (!emitTransparentRests(measureTotalTicks - cursor)) return null;
    return buildVoice(voiceTime, tickables);
  }
```

- [ ] **Step 2: Add module require for `HarmonizationRealizationLogic`**

At the top of `vexflow_adapter.js`, locate the `define([...])` header (RequireJS). Add `"app/models/harmonization_realization_logic"` to the dependency array and `HarmonizationRealizationLogic` to the matching parameter list.

The current header is:

```js
define([
  "lodash",
  "vexflow",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/utils/measure_engine",
  "app/models/key_signature",
], function (_, Vex, ScoreTimeline, Analyze, MeasureEngine, KeySignature) {
```

Update it to:

```js
define([
  "lodash",
  "vexflow",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/utils/measure_engine",
  "app/models/key_signature",
  "app/models/harmonization_realization_logic",
], function (_, Vex, ScoreTimeline, Analyze, MeasureEngine, KeySignature, HarmonizationRealizationLogic) {
```

Run: `grep -n "^define\|^  define" lab/static/js/src/components/music/rendering/vexflow_adapter.js | head -3`
Inspect the surrounding header after editing and confirm dependency order matches the callback parameter order. Do **not** use a lazy `require(...)` inside `render(...)`; `buildHarmonizationOverlayVoice` is module-scoped and needs the AMD dependency in module scope.

- [ ] **Step 3: Plumb the new render opt and call the helper inside the measure loop**

Inside `render(...)`, near the top where opts are read (around line 1038), add:

```js
      var harmonizationRealization = (opts && opts.harmonizationRealization) || null;
```

Inside the per-measure render loop, between the existing
`var trebleVoices = staffVoices("treble", ...)` line (~1375) and the
`var allVoices = trebleVoices.concat(bassVoices);` line (~1410), insert:

```js
        if (harmonizationRealization && HarmonizationRealizationLogic) {
          var measureTotal = measureDurations[measIdx] || fullMeasureTicks;
          var entriesInMeasure = harmonizationRealization.filter(function (e) {
            return e.measureIndex === absoluteMeasureIndex;
          });
          if (entriesInMeasure.length) {
            var overlay = buildHarmonizationOverlayVoice(
              entriesInMeasure, measureTotal, time, keySignatureAlterations
            );
            if (overlay) {
              trebleVoices.push(overlay);
            } else {
              console.warn("[VexFlowAdapter] harmonization overlay tick mismatch in measure",
                absoluteMeasureIndex, "— skipping overlay for this measure");
            }
          }
        }
```

- [ ] **Step 4: Manual sanity check — adapter still renders non-harmonization scores**

Run: `make test` (or the project's existing JS test runner) and confirm no new failures in adapter-adjacent tests.

If no automated adapter test exists, open a non-harmonization exercise in the browser (e.g. any chorale exercise) and confirm the treble staff still renders normally. The new code path is gated on `harmonizationRealization` being truthy.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "feat(harmonization): treble overlay voice from harmonizationRealization"
```

---

## Task 6: Wire `exercise_sheet.js` to build + pass the payload

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

**Context:** The existing harmonization render block already runs on every `"graded"` event re-render. Build the payload inside it; pass to the adapter call below.

- [ ] **Step 1: Add `HarmonizationRealizationLogic` to the file's RequireJS deps**

At the top of `exercise_sheet.js`, find the `define([...], function (...) {})` header and add `"app/models/harmonization_realization_logic"` to the dependency array with matching parameter name `HarmonizationRealizationLogic`.

The current dependency tail is:

```js
  "app/components/music/playback_controls",
  "app/utils/measure_engine",
], function (
  ...
  renderPlaybackControls,
  MeasureEngine
) {
```

Update it to:

```js
  "app/components/music/playback_controls",
  "app/utils/measure_engine",
  "app/models/harmonization_realization_logic",
], function (
  ...
  renderPlaybackControls,
  MeasureEngine,
  HarmonizationRealizationLogic
) {
```

Verification command:

```bash
sed -n '1,45p' lab/static/js/src/components/music/exercise_sheet.js
```

Confirm dependency order matches callback parameter order.

- [ ] **Step 2: Build the payload inside the existing harmonization block**

At [exercise_sheet.js:1693](lab/static/js/src/components/music/exercise_sheet.js#L1693) — inside the `if (isHarmonization && this.exerciseContext)` block, AFTER the existing `playedNoteIdsForRender` assignment loop (after the closing `});` around line 1708) — add:

```js
            var accepted = this.exerciseContext.acceptedHarmonizationSonorities || [];
            // CIR stores meter as score.meta.time ("4/4"); legacy paths may use
            // score.meta.meter or score.meta.time_signature.
            var tsRaw = (score.meta &&
              (score.meta.time || score.meta.meter || score.meta.time_signature)) || "4/4";
            var tsParts = String(tsRaw).split("/");
            var meter = {
              numerator: parseInt(tsParts[0], 10),
              denominator: parseInt(tsParts[1], 10)
            };
            var harmonizationRealizationPayload = HarmonizationRealizationLogic.buildRealization(
              accepted, harmTargets, score, meter
            );
```

- [ ] **Step 3: Pass the payload into the adapter call**

Inside the existing `VexFlowAdapter.render(score, this.vexRenderer, { ... })` call at [exercise_sheet.js:1712](lab/static/js/src/components/music/exercise_sheet.js#L1712), add this key alongside the other opts:

```js
            harmonizationRealization: isHarmonization ? harmonizationRealizationPayload : null,
```

Place it next to `harmonizationTargets:` for proximity.

- [ ] **Step 4: Declare `harmonizationRealizationPayload` in scope above the `if (isHarmonization ...)` block**

So the `render(...)` call can reference it whether or not the if-branch was taken. Just above `if (isHarmonization && this.exerciseContext) {`, add:

```js
          var harmonizationRealizationPayload = null;
```

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(harmonization): build realization payload and pass to adapter"
```

---

## Task 7: Manual integration verification

**Files:** none

- [ ] **Step 1: Run the full JS logic test suite**

Run: `node lab/static/js/src/models/harmonization_realization_logic.test.js`
Expected: `All tests passed.`

Run the other harmonization-adjacent tests to confirm no regressions:

```bash
node lab/static/js/src/models/harmonization_grader_logic.test.js
node lab/static/js/src/models/harmonization_targets_logic.test.js
```

Expected: each prints `All tests passed.`.

- [ ] **Step 2: Open the demo Bach harmonization exercise in a browser**

Start the dev server and open a harmonization exercise (locked bass) — the user mentioned exercise EB57HG as the demo. Use any other harmonization exercise if EB57HG measure numbering looks off (this is a known unrelated issue per the user's note about the reverted gap-filter tweak).

Verify in the browser:
- Treble staff renders empty before any input (no overlay entries yet).
- Play the bass note + correct S/A/T for the first chord. After acceptance, three (or however many upper voices played) noteheads appear on the treble staff at beat 1.
- Accidentals appear only when the spelling contradicts the key signature.
- Continue through the phrase. Each accepted target adds its chord at the correct beat within the correct measure.
- Existing bass-coloring still works (black at accepted offsets).
- Figured-bass numerals still render below the bass staff.

- [ ] **Step 3: If any visual regression appears, capture console output and stop**

Specifically watch for:
- `[VexFlowAdapter] harmonization overlay tick mismatch in measure N` — indicates `ticksToDurationChunks` failed for an entry's `durationTicks`. Inspect the target offsets and meter; the spec accepts skipping the overlay for that measure rather than corrupting Voice ticks.
- VexFlow `addTickable` / `Formatter.joinVoices` errors — typically a Voice tick-total mismatch. Cross-check `measureDurations[measIdx]` against the sum of overlay tickable ticks.

- [ ] **Step 4: Commit any docs touchups (if needed)**

Only if you made code-comment fixes during verification.

```bash
git status
# if anything changed:
git add <files>
git commit -m "docs(harmonization): clarify <whatever>"
```

---

## Self-Review Summary

**Spec coverage:**

| Spec section | Covered by |
|---|---|
| Data flow / `harmonizationRealization` payload contract | Task 4 (`buildRealization`) |
| `buildPcSpellingMap` via timeline (including tie/held-across-barline) | Task 3 |
| `spellMidi` with octave-following-letter | Task 2 |
| `ticksToDurationChunks` greedy + transparent rests | Task 1 + Task 5 helper |
| Adapter `harmonizationRealization` opt + overlay voice on `trebleVoices` | Task 5 |
| `exercise_sheet.js` wiring + meter read from `score.meta.time` | Task 6 |
| Edge case: drop one bass instance (preserve upper-octave doubling) | Task 4 tests |
| Edge case: missing `lockedVoices.B.midi` falls back to pc match | Task 4 tests |
| Edge case: duplicate `targetIndex` deduped (most recent kept) | Task 4 tests |
| Edge case: empty upper voices → entry skipped | Task 4 tests |
| Edge case: tick-mismatch overlay → warn + skip measure | Task 5 helper return path |
| Existing `"graded"` event triggers re-render — no new wiring | Confirmed in spec; no task needed |
| Manual integration | Task 7 |

**Placeholders:** none. Every code step shows the exact code to write. Test steps show the exact commands and expected output.

**Type consistency:**
- `harmonizationRealization` entry shape `{ measureIndex, onset, durationTicks, midiNotes, spellings }` is used identically in Task 4 (producer) and Task 5 (consumer).
- `spellMidi` returns `{ step, alter, octave }`, consumed by Task 5's `keys.map(...)` and accidental loop in matching shape.
- `ticksToDurationChunks` returns `[{ type, dots, ticks } | null]`; consumers in Tasks 4 & 5 handle the `null`/empty cases.
- `target.lockedVoices.B.midi` confirmed by reading `apps/exercises/harmonization/targets.py` — server-side payload includes `midi`, `pc`, `spelling`.
- `accepted[i]` shape `{ midi, targetIndex, ts }` confirmed at [exercise_context.js:241](lab/static/js/src/models/exercise_context.js#L241).
