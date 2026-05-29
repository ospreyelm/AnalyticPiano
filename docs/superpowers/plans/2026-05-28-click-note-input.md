# Click-on-Staff Note Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mouse click on empty staff positions as a MIDI-free pitch-input source for harmonization exercises, behind an explicit Live/Click source-mode toggle.

**Architecture:** A pure pixel→pitch module (`click_note_logic.js`) inverts canvas coordinates to MIDI using a staff-layout geometry the VexFlow adapter exports once per render. A new `ClickNoteInputComponent` (modeled on `note_name.js`) owns canvas hit-testing, an accidental palette, and a pending clicked-note set. Harmonization click input never broadcasts live `NOTE` events; on explicit commit it hands `exercise_context` a flat MIDI snapshot (`lockedTargetMidi + clickedMidi`) through a shared helper that the existing MIDI settle timer also calls — so the grading boundary stays input-method agnostic. A Live/Click source mode (separate from the existing qwerty/notename `INPUT_MODE`) arms the component and, in Click mode, suppresses the live-settle auto-grade for harmonization.

**Tech Stack:** AMD modules (RequireJS), Backbone-style `Component`, jQuery, lodash, VexFlow CANVAS backend. Pure-logic modules use the repo UMD `*_logic.js` + `.test.js` convention, run with plain `node` (no test runner).

**Spec:** [docs/superpowers/specs/2026-05-28-click-note-input-design.md](../specs/2026-05-28-click-note-input-design.md)

**Render-path note (verified):** The harmonization render path in `vexflow_adapter.js` lays all measures in a **single horizontal system** (`trebleY`/`bassY` computed once at lines 1234–1235; `currentX += measureWidth` at 1987; no row wrapping). So `onStaffLayout` emits exactly **one system** (`systemIndex: 0`) in v1. The `systems: []` array shape (from the spec) is preserved for forward compatibility with a future wrapping layout, and `click_note_logic` still picks the system by `py` first — trivially the only system today.

---

## Task 1: Extract key-signature logic to the shared module

The pixel→pitch math needs the same per-letter key-signature alteration map the adapter uses. Per the spec ("mandatory extraction") and the repo redundancy report, move `normalizeKeyForVexFlow` and `getKeySignatureAlterations` out of `vexflow_adapter.js` (where they are private) into the already-shared `vexflow_adapter_logic.js`, and have the adapter call them through its existing `VexflowAdapterLogic` import. Do not copy the table.

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js`
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js:366-416` (remove local defs), `:387`, `:1065`, `:1167` (call sites)
- Test: `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js`

- [ ] **Step 1: Write the failing test**

Append to `vexflow_adapter_logic.test.js` (before the final pass/exit block — match the existing `assertEqual` style already in that file):

```javascript
// --- getKeySignatureAlterations / normalizeKeyForVexFlow -------------------
function assertDeepEqual(label, actual, expected) {
  assertEqual(label, JSON.stringify(actual), JSON.stringify(expected));
}

assertEqual("normalize iG_ -> Gm", mod.normalizeKeyForVexFlow("iG_"), "Gm");
assertEqual("normalize jG_ -> G", mod.normalizeKeyForVexFlow("jG_"), "G");
assertEqual("normalize lowercase g -> Gm", mod.normalizeKeyForVexFlow("g"), "Gm");
assertEqual("normalize empty -> C", mod.normalizeKeyForVexFlow(""), "C");

assertDeepEqual("C major: no alterations", mod.getKeySignatureAlterations("jC_"), {});
assertDeepEqual("G major: F sharp", mod.getKeySignatureAlterations("jG_"), { F: 1 });
assertDeepEqual("F major: B flat", mod.getKeySignatureAlterations("jF_"), { B: -1 });
assertDeepEqual("D major: F# C#", mod.getKeySignatureAlterations("jD_"), { F: 1, C: 1 });
assertDeepEqual("A minor: no alterations", mod.getKeySignatureAlterations("iA_"), {});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js`
Expected: FAIL — `mod.normalizeKeyForVexFlow is not a function`.

- [ ] **Step 3: Add the two functions to the shared module**

In `vexflow_adapter_logic.js`, add these two functions inside the factory (after `getBassLabelAtOffset`, before the `return {...}`):

```javascript
  function normalizeKeyForVexFlow(key) {
    if (!key) return "C";
    var k = String(key).trim();
    if (k.startsWith("i") || k.startsWith("j")) {
      var mode = k.charAt(0);
      var root = k.substring(1).replace("_", "");
      return mode === "i" ? root + "m" : root;
    }
    if (k.length > 0 && k[0] === k[0].toLowerCase()) {
      var lower = k[0].toUpperCase() + k.substring(1);
      return lower.endsWith("m") ? lower : lower + "m";
    }
    return k;
  }

  function getKeySignatureAlterations(key) {
    if (!key) return {};
    var alterations = {};
    var k = normalizeKeyForVexFlow(key);
    var map = {
      "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
      "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
      "Am": 0, "Em": 1, "Bm": 2, "F#m": 3, "C#m": 4, "G#m": 5, "D#m": 6, "A#m": 7,
      "Dm": -1, "Gm": -2, "Cm": -3, "Fm": -4, "Bbm": -5, "Ebm": -6, "Abm": -7
    };
    var accCount = map[k] || 0;
    if (accCount > 0) {
      var sharpOrder = ["F", "C", "G", "D", "A", "E", "B"];
      for (var i = 0; i < accCount && i < sharpOrder.length; i++) {
        alterations[sharpOrder[i]] = 1;
      }
    } else if (accCount < 0) {
      var flatOrder = ["B", "E", "A", "D", "G", "C", "F"];
      for (var j = 0; j < Math.abs(accCount) && j < flatOrder.length; j++) {
        alterations[flatOrder[j]] = -1;
      }
    }
    return alterations;
  }
```

Add both to the returned object:

```javascript
  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
    getBassLabelAtOffset: getBassLabelAtOffset,
    normalizeKeyForVexFlow: normalizeKeyForVexFlow,
    getKeySignatureAlterations: getKeySignatureAlterations,
  };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js`
Expected: PASS (all assertions, exit 0).

- [ ] **Step 5: Point the adapter at the shared functions**

In `vexflow_adapter.js`, **delete** the local `normalizeKeyForVexFlow` (lines 366-381) and `getKeySignatureAlterations` (lines 383-416). Then update the three call sites to use the import:

- `:387` was inside the deleted function — gone with it.
- `:1065` `var k = normalizeKeyForVexFlow(key);` → `var k = VexflowAdapterLogic.normalizeKeyForVexFlow(key);`
- `:1167` `var keySignatureAlterations = getKeySignatureAlterations(meta.key);` → `var keySignatureAlterations = VexflowAdapterLogic.getKeySignatureAlterations(meta.key);`

(`VexflowAdapterLogic` is already imported at `vexflow_adapter.js:13`.)

- [ ] **Step 6: Verify no other references remain**

Run: `grep -n "normalizeKeyForVexFlow\|getKeySignatureAlterations" lab/static/js/src/components/music/rendering/vexflow_adapter.js`
Expected: only the two `VexflowAdapterLogic.`-prefixed call sites; no bare local references, no local `function` definitions.

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "refactor: extract key-signature alteration logic to shared adapter-logic module"
```

---

## Task 2: Add the two new broadcast events

`INPUT_SOURCE_MODE` (live/click) is a separate axis from the existing `INPUT_MODE` (qwerty/notename) — do not reuse it. `MIDI_INPUTS_CHANGED` is a structured availability signal so source-mode default does not depend on the text NOTIFICATION.

**Files:**
- Modify: `lab/static/js/src/components/events.js`

- [ ] **Step 1: Add the events**

In `events.js`, add two entries inside `BROADCAST` (after `INPUT_MODE`):

```javascript
    INPUT_MODE: "inputmode",
    INPUT_SOURCE_MODE: "inputsourcemode",
    MIDI_INPUTS_CHANGED: "midiinputschanged",
    LABEL_SELECTED: "labelselected",
```

- [ ] **Step 2: Commit**

```bash
git add lab/static/js/src/components/events.js
git commit -m "feat: add INPUT_SOURCE_MODE and MIDI_INPUTS_CHANGED broadcast events"
```

---

## Task 3: Pixel→pitch logic module (`click_note_logic.js`)

Pure, DOM-free coordinate inversion following the repo `*_logic.js` UMD convention. Imports the shared `getKeySignatureAlterations` (Task 1) so the key-sig table is never copied.

**Files:**
- Create: `lab/static/js/src/components/input/click_note_logic.js`
- Test: `lab/static/js/src/components/input/click_note_logic.test.js`

- [ ] **Step 1: Write the failing test**

Create `click_note_logic.test.js`:

```javascript
"use strict";

var mod = require("./click_note_logic");

var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual);
  var e = JSON.stringify(expected);
  if (a === e) {
    console.log("ok - " + label);
  } else {
    fail += 1;
    console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a);
  }
}

// Single-system layout: treble top line F5 at y=95, spacing 10 (so bottomLineY=135);
// bass top line A3 at y=175, spacing 10 (bottomLineY=215).
var LAYOUT = {
  systems: [{
    systemIndex: 0,
    yTop: 60, yBottom: 240,
    staves: [
      { clef: "treble", x: 60, width: 740, topLineY: 95, bottomLineY: 135,
        lineSpacing: 10, topLineStep: "F", topLineOctave: 5 },
      { clef: "bass", x: 60, width: 740, topLineY: 175, bottomLineY: 215,
        lineSpacing: 10, topLineStep: "A", topLineOctave: 3 }
    ]
  }],
  columns: [
    { systemIndex: 0, onset: 0, measureIndex: 0, measureX: 60, measureWidth: 360,
      centerX: 100, rect: { x: 60, width: 120 } },
    { systemIndex: 0, onset: 1024, measureIndex: 0, measureX: 60, measureWidth: 360,
      centerX: 240, rect: { x: 180, width: 120 } }
  ]
};

// key "jG_" = G major (F#). activeColumnOnset 0 => only onset-0 column clickable.

// Treble top line is F5 (py=95). Click exactly on it in column 0 with diatonic palette.
var r1 = mod.resolveClick({ px: 100, py: 95 }, LAYOUT, {
  key: "jG_", palette: "diatonic", activeColumnOnset: 0
});
// F5 in G major => F#5 => midi (5+1)*12 + 5 + 1 = 78
assertEqual("treble top line F5 -> F#5 (G major diatonic)", r1 && r1.midi, 78);
assertEqual("treble top line step", r1 && r1.step, "F");
assertEqual("treble top line alter (G major)", r1 && r1.alter, 1);
assertEqual("resolves to column onset 0", r1 && r1.column && r1.column.onset, 0);

// One diatonic step down from F5 top line = E5 (py = 95 + 5 = 100, half-spacing).
var r2 = mod.resolveClick({ px: 100, py: 100 }, LAYOUT, {
  key: "jG_", palette: "diatonic", activeColumnOnset: 0
});
// E5 not altered in G major => midi (5+1)*12 + 4 = 76
assertEqual("half-step below top line -> E5", r2 && r2.midi, 76);

// Natural palette forces F-natural even in G major.
var r3 = mod.resolveClick({ px: 100, py: 95 }, LAYOUT, {
  key: "jG_", palette: "natural", activeColumnOnset: 0
});
assertEqual("natural palette -> F5 natural midi 77", r3 && r3.midi, 77);

// Flat palette: F5 -> Fb5 midi 76.
var r4 = mod.resolveClick({ px: 100, py: 95 }, LAYOUT, {
  key: "jG_", palette: "flat", activeColumnOnset: 0
});
assertEqual("flat palette -> Fb5 midi 76", r4 && r4.midi, 76);

// Bass clef top line A3 (py=175) -> A3 midi 57 (G major, A unaltered).
var r5 = mod.resolveClick({ px: 100, py: 175 }, LAYOUT, {
  key: "jG_", palette: "diatonic", activeColumnOnset: 0
});
assertEqual("bass top line -> A3 midi 57", r5 && r5.midi, 57);

// Sequential gate: clicking the onset-1024 column when active target is onset 0 -> null.
var r6 = mod.resolveClick({ px: 240, py: 95 }, LAYOUT, {
  key: "jG_", palette: "diatonic", activeColumnOnset: 0
});
assertEqual("click outside active target column -> null", r6, null);

// Out-of-range: far above the treble staff (ledger lines beyond piano range) -> null.
var r7 = mod.resolveClick({ px: 100, py: -200 }, LAYOUT, {
  key: "jG_", palette: "diatonic", activeColumnOnset: 0
});
assertEqual("click far outside any system -> null", r7, null);

if (fail > 0) {
  console.error("\n" + fail + " assertion(s) failed.");
  process.exit(1);
} else {
  console.log("\nAll click_note_logic assertions passed.");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node lab/static/js/src/components/input/click_note_logic.test.js`
Expected: FAIL — `Cannot find module './click_note_logic'`.

- [ ] **Step 3: Implement `click_note_logic.js`**

Create the module. It requires the shared adapter-logic module for the key-sig table.

```javascript
/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("../music/rendering/vexflow_adapter_logic"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/components/music/rendering/vexflow_adapter_logic"], factory);
  } else {
    root.ClickNoteLogic = factory(root.VexflowAdapterLogic);
  }
})(typeof self !== "undefined" ? self : this, function (VexflowAdapterLogic) {
  "use strict";

  var STEP_SEMITONE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  // Diatonic ladder, high to low within an octave.
  var LADDER = ["C", "D", "E", "F", "G", "A", "B"];
  var LEDGER_HALF_STEPS = 12; // ~6 ledger lines above/below (each line/space = one half-spacing)

  function pickSystem(layout, py) {
    var systems = (layout && layout.systems) || [];
    if (!systems.length) return null;
    for (var i = 0; i < systems.length; i++) {
      if (py >= systems[i].yTop && py <= systems[i].yBottom) return systems[i];
    }
    // Nearest by edge distance.
    var best = null, bestDist = Infinity;
    for (var j = 0; j < systems.length; j++) {
      var s = systems[j];
      var d = py < s.yTop ? s.yTop - py : py - s.yBottom;
      if (d < bestDist) { bestDist = d; best = s; }
    }
    return best;
  }

  function pickStave(system, py) {
    var staves = (system && system.staves) || [];
    var best = null, bestDist = Infinity;
    for (var i = 0; i < staves.length; i++) {
      var st = staves[i];
      var zoneTop = st.topLineY - LEDGER_HALF_STEPS * st.lineSpacing;
      var zoneBottom = st.bottomLineY + LEDGER_HALF_STEPS * st.lineSpacing;
      if (py >= zoneTop && py <= zoneBottom) return st;
      var d = py < zoneTop ? zoneTop - py : py - zoneBottom;
      if (d < bestDist) { bestDist = d; best = st; }
    }
    return best;
  }

  // Walk the diatonic ladder down (positive steps) or up (negative) from the top line.
  function stepFromTopLine(topStep, topOctave, stepsDown) {
    var idx = LADDER.indexOf(topStep);
    var octave = topOctave;
    var n = stepsDown;
    while (n > 0) { // descend: B -> A ... C -> B(octave-1)
      idx -= 1;
      if (idx < 0) { idx = LADDER.length - 1; octave -= 1; }
      n -= 1;
    }
    while (n < 0) { // ascend
      idx += 1;
      if (idx >= LADDER.length) { idx = 0; octave += 1; }
      n += 1;
    }
    return { step: LADDER[idx], octave: octave };
  }

  function pickColumn(layout, system, px, activeColumnOnset) {
    var cols = (layout && layout.columns) || [];
    var inSystem = cols.filter(function (c) { return c.systemIndex === system.systemIndex; });
    var hit = null;
    for (var i = 0; i < inSystem.length; i++) {
      var c = inSystem[i];
      if (c.rect && px >= c.rect.x && px <= c.rect.x + c.rect.width) { hit = c; break; }
    }
    if (!hit) {
      var best = null, bestDist = Infinity;
      for (var j = 0; j < inSystem.length; j++) {
        var d = Math.abs(inSystem[j].centerX - px);
        if (d < bestDist) { bestDist = d; best = inSystem[j]; }
      }
      hit = best;
    }
    if (!hit) return null;
    // Sequential v1 gate: only the active target column is clickable.
    if (typeof activeColumnOnset === "number" && hit.onset !== activeColumnOnset) return null;
    return hit;
  }

  function applyPalette(letter, palette, keyAlterations) {
    if (palette === "sharp") return 1;
    if (palette === "flat") return -1;
    if (palette === "natural") return 0;
    // diatonic (default): take the key-signature alteration for this letter.
    return keyAlterations[letter] || 0;
  }

  // opts: { key, palette, activeColumnOnset }
  function resolveClick(point, layout, opts) {
    opts = opts || {};
    var px = point.px, py = point.py;
    var system = pickSystem(layout, py);
    if (!system) return null;
    var stave = pickStave(system, py);
    if (!stave) return null;

    var stepsFromTop = Math.round((py - stave.topLineY) / (stave.lineSpacing / 2));
    var pos = stepFromTopLine(stave.topLineStep, stave.topLineOctave, stepsFromTop);

    var keyAlterations = VexflowAdapterLogic.getKeySignatureAlterations(opts.key);
    var alter = applyPalette(pos.step, opts.palette, keyAlterations);

    var midi = (pos.octave + 1) * 12 + STEP_SEMITONE[pos.step] + alter;
    if (midi < 21 || midi > 108) return null;

    var column = pickColumn(layout, system, px, opts.activeColumnOnset);
    if (!column) return null;

    return {
      midi: midi, step: pos.step, alter: alter, octave: pos.octave,
      stepsFromTop: stepsFromTop, staveClef: stave.clef, column: column
    };
  }

  return {
    pickSystem: pickSystem,
    pickStave: pickStave,
    stepFromTopLine: stepFromTopLine,
    pickColumn: pickColumn,
    resolveClick: resolveClick,
  };
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node lab/static/js/src/components/input/click_note_logic.test.js`
Expected: PASS — all assertions, exit 0.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/input/click_note_logic.js lab/static/js/src/components/input/click_note_logic.test.js
git commit -m "feat: add pure pixel-to-pitch click-note logic module"
```

---

## Task 4: Source-mode + cap + snapshot pure helpers

Pure helpers used by the component and entrypoints, kept testable. Add to `click_note_logic.js` (same module) so the component has one logic dependency.

**Files:**
- Modify: `lab/static/js/src/components/input/click_note_logic.js`
- Test: `lab/static/js/src/components/input/click_note_logic.test.js`

- [ ] **Step 1: Write the failing test**

Append to `click_note_logic.test.js` (before the final pass/exit block):

```javascript
// --- source mode default ---------------------------------------------------
assertEqual("no device -> click", mod.defaultSourceMode(0, null), "click");
assertEqual("device present -> live", mod.defaultSourceMode(2, null), "live");
assertEqual("stored preference overrides (live) with 0 devices",
  mod.defaultSourceMode(0, "live"), "live");
assertEqual("stored preference overrides (click) with devices",
  mod.defaultSourceMode(3, "click"), "click");
assertEqual("invalid stored pref ignored -> falls back to count",
  mod.defaultSourceMode(0, "garbage"), "click");

// --- chord cap -------------------------------------------------------------
assertEqual("cap = max(0, policyMax - lockedCount): 4 - 1 = 3",
  mod.capRemaining({ min: 3, max: 4 }, 1), 3);
assertEqual("cap floors at 0", mod.capRemaining({ min: 3, max: 4 }, 5), 0);
assertEqual("cap default policy max 4 when policy missing",
  mod.capRemaining(null, 1), 3);

// --- commit snapshot -------------------------------------------------------
assertEqual("snapshot merges + dedups + sorts",
  mod.buildCommitSnapshot([48], [67, 60, 64, 48]), [48, 60, 64, 67]);
assertEqual("snapshot with no locked notes",
  mod.buildCommitSnapshot([], [64, 60]), [60, 64]);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node lab/static/js/src/components/input/click_note_logic.test.js`
Expected: FAIL — `mod.defaultSourceMode is not a function`.

- [ ] **Step 3: Implement the helpers**

Add to `click_note_logic.js` before the `return {...}`:

```javascript
  function defaultSourceMode(inputCount, storedPref) {
    if (storedPref === "live" || storedPref === "click") return storedPref;
    return inputCount > 0 ? "live" : "click";
  }

  function capRemaining(voiceCountPolicy, lockedVoiceCount) {
    var max = (voiceCountPolicy && typeof voiceCountPolicy.max === "number")
      ? voiceCountPolicy.max : 4;
    return Math.max(0, max - (lockedVoiceCount || 0));
  }

  function buildCommitSnapshot(lockedMidi, clickedMidi) {
    var seen = {};
    var out = [];
    (lockedMidi || []).concat(clickedMidi || []).forEach(function (m) {
      if (!seen[m]) { seen[m] = true; out.push(m); }
    });
    return out.sort(function (a, b) { return a - b; });
  }
```

Add them to the returned object:

```javascript
    resolveClick: resolveClick,
    defaultSourceMode: defaultSourceMode,
    capRemaining: capRemaining,
    buildCommitSnapshot: buildCommitSnapshot,
  };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node lab/static/js/src/components/input/click_note_logic.test.js`
Expected: PASS — all assertions, exit 0.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/input/click_note_logic.js lab/static/js/src/components/input/click_note_logic.test.js
git commit -m "feat: add source-mode, chord-cap, and commit-snapshot pure helpers"
```

---

## Task 5: Extract the harmonization grade helper in `exercise_context.js`

Factor the harmonization acceptance logic now inline in `grade()` (lines 224-255) into `gradeHarmonizationMidiSet(activeMidi)` so both the MIDI settle timer and click commit feed the same explicit-MIDI-set contract. The downstream state machine (the `switch` at 264-331) is shared and stays in `grade()`.

**Files:**
- Modify: `lab/static/js/src/models/exercise_context.js:205-348`

- [ ] **Step 1: Add the helper method**

In `exercise_context.js`, add this method to the prototype, immediately **before** `grade:` (before line 205):

```javascript
    /**
     * Compute the harmonization `graded` object from an explicit flat MIDI set.
     * Input-method agnostic: MIDI settle timer and click commit both call this.
     * Mutates acceptance state (accepted sonorities, pointer) on a correct match.
     *
     * @param {number[]} activeMidi  flat set of sounding MIDI (locked + student)
     * @return {object} graded { result, score, activeIndex, problems }
     */
    computeHarmonizationGraded: function (activeMidi) {
      var targets = this.definition.getHarmonizationTargets
        ? this.definition.getHarmonizationTargets() : [];
      var ptr = this._harmonizationPointer;
      if (!activeMidi || !activeMidi.length) {
        return {
          result: this.grader.STATE.PARTIAL,
          score: 1,
          activeIndex: ptr,
          problems: [],
        };
      }
      var matchResult = HarmonizationGraderLogic.harmonizationMatch(targets[ptr] || {}, activeMidi);
      if (matchResult.state === "correct") {
        this.acceptedHarmonizationSonorities.push({
          midi: activeMidi.slice(),
          targetIndex: ptr,
          ts: Date.now(),
        });
        this._harmonizationPointer = ptr + 1;
      }
      var allDone = this._harmonizationPointer >= targets.length && targets.length > 0;
      return {
        result: allDone ? this.grader.STATE.CORRECT
          : (matchResult.state === "incorrect" ? this.grader.STATE.INCORRECT : this.grader.STATE.PARTIAL),
        score: allDone ? 0 : (matchResult.state === "incorrect" ? 2 : 1),
        activeIndex: this._harmonizationPointer,
        problems: [matchResult],
      };
    },
```

- [ ] **Step 2: Replace the inline branch with a call + add an override hook**

In `grade()`, replace the harmonization branch (current lines 224-255) with:

```javascript
      } else if (isHarmonizationExercise) {
        var activeMidi;
        if (this._harmonizationActiveMidiOverride != null) {
          activeMidi = this._harmonizationActiveMidiOverride;
        } else {
          var tracker = this._harmonizationHeldTracker;
          activeMidi = tracker ? tracker.activeMidi(Date.now()) : [];
        }
        graded = this.computeHarmonizationGraded(activeMidi);
      } else {
```

The override lets click commit hand in an explicit snapshot while reusing the entire shared downstream (`switch`, `NEXT_CHORD` broadcast, VL scoring, `trigger("graded")`).

- [ ] **Step 3: Add the click-commit entrypoint**

Add this method to the prototype, after `grade:` closes (after line 348):

```javascript
    /**
     * Grade an explicit harmonization MIDI snapshot (click-commit path).
     * Sets a one-shot activeMidi override, runs the shared grade() downstream,
     * then clears the override so the MIDI settle path is unaffected.
     *
     * @param {number[]} activeMidi  locked target MIDI + pending clicked MIDI
     * @return undefined
     */
    gradeHarmonizationMidiSet: function (activeMidi) {
      this._harmonizationActiveMidiOverride = activeMidi || [];
      try {
        this.grade();
      } finally {
        this._harmonizationActiveMidiOverride = null;
      }
    },
```

- [ ] **Step 4: Initialize the override field**

In the constructor, beside the other harmonization fields (after line 114 `this.harmonizationTier = null;`):

```javascript
    this._harmonizationActiveMidiOverride = null;
```

- [ ] **Step 5: Verify the refactor is behavior-preserving**

Run: `grep -n "computeHarmonizationGraded\|gradeHarmonizationMidiSet\|_harmonizationActiveMidiOverride" lab/static/js/src/models/exercise_context.js`
Expected: helper defined once, called from `grade()`; `gradeHarmonizationMidiSet` defined once; override field init + read + cleared.

Reasoning check (no automated test — this is event-bus glue): with `_harmonizationActiveMidiOverride === null`, `grade()` reads `tracker.activeMidi(Date.now())` exactly as before, and `computeHarmonizationGraded` produces the same `graded` object the old inline branch did. The downstream `switch` is untouched.

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "refactor: extract shared harmonization grade helper for input-agnostic commit"
```

---

## Task 6: Staff-layout export + pending overlay in `vexflow_adapter.js`

Add `opts.onStaffLayout(layout)` (fired once per render, single-system) and `opts.harmonizationPending` (a pending realization rendered via the existing overlay builder in a distinct style).

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`

- [ ] **Step 1: Accumulate columns during the annotation loop**

The per-column annotation loop (around `vexflow_adapter.js:1820`, `groups.forEach(function(col){...})`) already computes `columnCenterX`, `noteOnset`, `noteMeasure`. Just before the `for (var measIdx ...)` render loop (near line 1557), declare an accumulator:

```javascript
      var staffLayoutColumns = [];
      var staffLayoutStaves = [];
      var layoutSystemYTop = Infinity;
      var layoutSystemYBottom = -Infinity;
```

Inside `groups.forEach`, right after `var columnCenterX = getColumnCenterX(col);` (line 1858), push a column record (guard against null centerX):

```javascript
              if (opts && typeof opts.onStaffLayout === "function" && columnCenterX !== null) {
                staffLayoutColumns.push({
                  systemIndex: 0,
                  onset: noteOnset,
                  measureIndex: noteMeasure,
                  measureX: (trebleStave || bassStave) ? (trebleStave || bassStave).getX() : null,
                  measureWidth: measureWidth,
                  centerX: columnCenterX,
                });
              }
```

- [ ] **Step 2: Capture stave geometry once per measure**

Inside the measure loop, after both staves are created (after line 1568, `var bassStave = ...`), capture stave geometry the first time each clef is seen and track the system y-extent:

```javascript
        if (opts && typeof opts.onStaffLayout === "function") {
          function recordStave(stave, clef, topStep, topOctave) {
            if (!stave) return;
            var topLineY = stave.getYForLine ? stave.getYForLine(0) : stave.getY();
            var bottomLineY = stave.getYForLine ? stave.getYForLine(4) : stave.getBottomY();
            var lineSpacing = stave.getYForLine ? (stave.getYForLine(1) - stave.getYForLine(0)) : 10;
            if (!staffLayoutStaves.some(function (s) { return s.clef === clef; })) {
              staffLayoutStaves.push({
                clef: clef,
                x: stave.getX(),
                width: stave.getWidth ? stave.getWidth() : measureWidth,
                topLineY: topLineY,
                bottomLineY: bottomLineY,
                lineSpacing: lineSpacing,
                topLineStep: topStep,
                topLineOctave: topOctave,
              });
            }
            var top = topLineY - 6 * lineSpacing;
            var bot = bottomLineY + 6 * lineSpacing;
            if (top < layoutSystemYTop) layoutSystemYTop = top;
            if (bot > layoutSystemYBottom) layoutSystemYBottom = bot;
          }
          recordStave(trebleStave, "treble", "F", 5);
          recordStave(bassStave, "bass", "A", 3);
        }
```

The `x`/`width` here are per-measure; the system-wide clickable x-range is the union, fixed up in Step 3. (Treble top line = F5, bass top line = A3 — fixed per clef.)

- [ ] **Step 3: Compute rects and fire the callback after the render loop**

After the measure loop closes (after `currentX += measureWidth;` at line 1987, outside the `for`), emit the layout. Columns get a hit-rect = midpoint between adjacent centers, clamped to the system x-range:

```javascript
      if (opts && typeof opts.onStaffLayout === "function" && staffLayoutStaves.length) {
        var sysX = Math.min.apply(null, staffLayoutStaves.map(function (s) { return s.x; }));
        var sysRight = Math.max.apply(null, staffLayoutStaves.map(function (s) { return s.x + s.width; }));
        staffLayoutStaves.forEach(function (s) { s.x = sysX; s.width = sysRight - sysX; });

        staffLayoutColumns.sort(function (a, b) { return a.centerX - b.centerX; });
        staffLayoutColumns.forEach(function (c, i) {
          var prev = staffLayoutColumns[i - 1];
          var next = staffLayoutColumns[i + 1];
          var left = prev ? (prev.centerX + c.centerX) / 2 : sysX;
          var right = next ? (c.centerX + next.centerX) / 2 : sysRight;
          left = Math.max(left, sysX);
          right = Math.min(right, sysRight);
          c.rect = { x: left, width: Math.max(0, right - left) };
        });

        opts.onStaffLayout({
          systems: [{
            systemIndex: 0,
            yTop: layoutSystemYTop,
            yBottom: layoutSystemYBottom,
            staves: staffLayoutStaves,
          }],
          columns: staffLayoutColumns,
        });
      }
```

- [ ] **Step 4: Add a color-override param to the overlay builder**

`buildHarmonizationOverlayVoice` (line 961) hardcodes the notehead color at line 1033:
`if (note.setStyle) note.setStyle({ fillStyle: "#000000", strokeStyle: "#000000" });`.
Add an optional `colorOverride` parameter so the pending overlay can reuse the exact
same builder in a distinct color. Change the signature:

```javascript
  function buildHarmonizationOverlayVoice(entriesInMeasure, measureTotalTicks, voiceTime, keySigAlters, colorOverride) {
```

and line 1033 to:

```javascript
      var overlayColor = colorOverride || "#000000";
      if (note.setStyle) note.setStyle({ fillStyle: overlayColor, strokeStyle: overlayColor });
```

The accepted-realization call site (line 1616) passes no 5th arg, so it stays black.

- [ ] **Step 5: Read the pending opt and render it through the same path**

Near the accepted-realization opt read (line 1145), add:

```javascript
      var harmonizationPending = (opts && opts.harmonizationPending) || null;
```

`harmonizationPending` is an **array of realization entries** with the same shape the
accepted `harmonizationRealization` uses — each entry is
`{ measureIndex, onset, durationTicks, midiNotes, spellings: [{step, alter, octave}] }`
(the sheet builds this in Task 7). Immediately after the accepted-realization block
(after line 1632, still inside the `for (var measIdx ...)` loop), add a mirror block
that builds the pending overlay in blue and pushes it onto `trebleVoices` so it formats
and draws with everything else:

```javascript
        if (harmonizationPending && harmonizationPending.length) {
          var pendingInMeasure = harmonizationPending.filter(function (e) {
            return e.measureIndex === absoluteMeasureIndex;
          });
          if (pendingInMeasure.length) {
            var pendingOverlay = buildHarmonizationOverlayVoice(
              pendingInMeasure,
              measureDurations[measIdx] || fullMeasureTicks,
              time,
              keySignatureAlterations,
              "#5b8def"
            );
            if (pendingOverlay) {
              trebleVoices.push(pendingOverlay);
            }
          }
        }
```

(If the builder returns null — e.g. a pending duration that overflows the measure —
the preview is simply skipped that frame; the committed realization always uses real
durations. No warn needed for the transient preview.)

- [ ] **Step 6: Manual verification (no unit test — canvas render)**

Per CLAUDE.md UI rule this is verified in the browser in Task 11. For now confirm syntax:

Run: `node -e "require('fs').readFileSync('lab/static/js/src/components/music/rendering/vexflow_adapter.js','utf8'); console.log('readable')"`
Expected: prints `readable` (file parses as text; full JS lint happens via the app build).

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "feat: export staff layout geometry and render pending harmonization overlay"
```

---

## Task 7: Wire the sheet — store layout, build pending, ghost, route grading

`exercise_sheet.js` stores `_staffLayout`, builds `harmonizationPending` from the click component's pending set, draws the ghost note, and (in click mode) suppresses the live-settle auto-grade for harmonization while routing commit through `gradeHarmonizationMidiSet`.

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

- [ ] **Step 1: Pass `onStaffLayout` + `harmonizationPending` into the adapter render call**

Find the adapter `render({...})` options object in `exercise_sheet.js` (the one that already passes `harmonizationTargets` at line 1894 and `lockedVoices` at 1896). Add:

```javascript
            onStaffLayout: function (layout) { self._staffLayout = layout; },
            harmonizationPending: self._buildHarmonizationPending(),
```

(Ensure a `self` alias exists in that scope, matching the file's convention; if the render method uses `var self = this;` reuse it.)

- [ ] **Step 2: Add the pending-builder + accessors**

Add to the `exercise_sheet` prototype:

```javascript
    /**
     * Builds the pending harmonization overlay payload from the click
     * component's pending clicked-note set for the active target column.
     * Returns an array of realization entries (same shape as the accepted
     * `harmonizationRealization`) so the adapter renders it through the exact
     * same `buildHarmonizationOverlayVoice` path. Returns null when there is no
     * click component or no pending notes.
     */
    _buildHarmonizationPending: function () {
      var clickComp = this._clickNoteComponent;
      if (!clickComp || typeof clickComp.getPending !== "function") return null;
      var pending = clickComp.getPending(); // [{ midi, step, alter, octave }]
      if (!pending || !pending.length) return null;
      var col = clickComp.getActiveColumn ? clickComp.getActiveColumn() : null;
      // Sort low->high so the chord stack mirrors the accepted overlay.
      pending = pending.slice().sort(function (a, b) { return a.midi - b.midi; });
      return [{
        measureIndex: col ? col.measureIndex : 0,
        onset: col ? col.onset : 0,
        durationTicks: 1024, // quarter-note preview block; overflow -> skipped frame
        midiNotes: pending.map(function (n) { return n.midi; }),
        spellings: pending.map(function (n) {
          return { step: n.step, alter: n.alter, octave: n.octave };
        }),
      }];
    },

    /** Component registers itself so the sheet can read pending state + layout. */
    setClickNoteComponent: function (comp) { this._clickNoteComponent = comp; },

    /** Click component reads the exported geometry. */
    getStaffLayout: function () { return this._staffLayout || null; },
```

- [ ] **Step 3: Ghost-note draw + clear**

Add ghost methods to the prototype. The ghost is a single faint notehead drawn on top after the adapter render; throttle by only redrawing when the snapped midi/column changes.

```javascript
    /** Draw a faint ghost notehead at the snapped column/pitch (top layer). */
    drawGhostNote: function (resolved) {
      this._ghost = resolved || null;
      this.render();
    },

    clearGhostNote: function () {
      if (!this._ghost) return;
      this._ghost = null;
      this.render();
    },
```

Then, at the very end of `render()` (after the adapter draws), draw the ghost on top:

```javascript
      if (this._ghost && this._staffLayout) {
        this._drawGhostGlyph(this._ghost);
      }
```

Add the glyph helper (uses the canvas 2D context directly — a lightweight filled ellipse at the column centerX and the pitch y, color `#b0b8c4`):

```javascript
    _drawGhostGlyph: function (ghost) {
      if (!this._staffLayout || !ghost || !ghost.column) return;
      var canvas = this.el ? this.el.querySelector("canvas") : null;
      if (!canvas) return;
      var c2d = canvas.getContext("2d");
      if (!c2d) return;
      var sys = (this._staffLayout.systems || [])[ghost.column.systemIndex]
        || (this._staffLayout.systems || [])[0];
      if (!sys) return;
      var stave = (sys.staves || []).filter(function (s) { return s.clef === ghost.staveClef; })[0]
        || sys.staves[0];
      if (!stave) return;
      // resolveClick already returned stepsFromTop relative to this stave's top line.
      var y = stave.topLineY + ghost.stepsFromTop * (stave.lineSpacing / 2);
      c2d.save();
      c2d.fillStyle = "#b0b8c4";
      c2d.beginPath();
      c2d.ellipse(ghost.column.centerX, y, 6, 4.5, 0, 0, 2 * Math.PI);
      c2d.fill();
      c2d.restore();
    },
```

The glyph y is derived from the `stepsFromTop` + `staveClef` fields `resolveClick` already returns — no extra computation in the component. Keep the glyph a simple ellipse; do not pull in a VexFlow notehead for the preview.

- [ ] **Step 4: Suppress live-settle auto-grade for harmonization in click mode**

In `onMidiNote` (line 2610), the harmonization branch (2621) schedules the settle-timer grade. Gate it on source mode: when the sheet is in `click` source mode, do not run the settle path for harmonization (a connected device must not auto-grade behind the deliberate build). At the top of the `if (isHarmonization)` block (after line 2621), add:

```javascript
        if (this._inputSourceMode === "click") {
          // Click mode: physical MIDI/computer-keyboard note events are ignored
          // for harmonization v1; all grading goes through click commit.
          return;
        }
```

Add a setter the entrypoint calls on mode change:

```javascript
    setInputSourceMode: function (mode) { this._inputSourceMode = mode; },
```

Default `this._inputSourceMode` to `"live"` wherever the sheet initializes its fields (so existing MIDI behavior is unchanged until a mode is set).

- [ ] **Step 5: Remove the debug log**

Delete line 2622: `console.log("[HARM-DEBUG] onMidiNote harmonization branch. state:", state, "note:", noteNum);`

- [ ] **Step 6: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat: wire staff layout, pending overlay, ghost note, and click-mode grade routing into sheet"
```

---

## Task 8: Emit structured MIDI availability from `midi.js`

`MIDI_INPUTS_CHANGED { inputCount }` on initial access, WebMIDI error (count 0), and device state changes — so source-mode default does not piggyback on the text NOTIFICATION.

**Files:**
- Modify: `lab/static/js/src/components/midi.js`

- [ ] **Step 1: Emit on init**

In `onWebMIDIInit` (line 172), after `this.initListeners();` (line 182) and before the zero-input notification, add:

```javascript
      var inputCount = Array.from(MIDIAccess.inputs.values()).length;
      this.broadcast(EVENTS.BROADCAST.MIDI_INPUTS_CHANGED, { inputCount: inputCount });
```

Change the following `if (Array.from(...).length === 0)` to reuse `inputCount` for clarity:

```javascript
      if (inputCount === 0) {
```

- [ ] **Step 2: Emit on device state change**

The updater closure (`this.midiDevice.setUpdater(function () {...})`, lines 174-180) runs on `onstatechange`. Inside it, after `this.selectDefaults(inputs);`, add:

```javascript
        this.broadcast(EVENTS.BROADCAST.MIDI_INPUTS_CHANGED, { inputCount: inputs.length });
```

(Confirm `this` is bound to the midi component inside the updater; if it is invoked with a different `this`, capture `var self = this;` before `setUpdater` and use `self.broadcast`.)

- [ ] **Step 3: Emit on WebMIDI error**

In `onWebMIDIError` (line 196), after the NOTIFICATION broadcast and before `this.initListeners();`:

```javascript
      this.broadcast(EVENTS.BROADCAST.MIDI_INPUTS_CHANGED, { inputCount: 0 });
```

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/midi.js
git commit -m "feat: broadcast structured MIDI_INPUTS_CHANGED availability signal"
```

---

## Task 9: `ClickNoteInputComponent` (`click_note.js`)

The component: accidental palette UI (mounted to `#piano`), canvas hit-testing, pending clicked-note set, ghost preview, explicit commit. Modeled on `note_name.js` lifecycle (`initComponent`, `enable`/`disable`, `renderTo`, `destroy`). Harmonization click never broadcasts live `NOTE`.

**Files:**
- Create: `lab/static/js/src/components/input/click_note.js`

- [ ] **Step 1: Implement the component**

```javascript
define([
  "jquery",
  "lodash",
  "app/components/events",
  "app/components/component",
  "app/components/input/click_note_logic",
], function ($, _, EVENTS, Component, ClickNoteLogic) {

  var STEP_SEMITONE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

  /**
   * ClickNoteInputComponent — MIDI-free pitch entry by clicking empty staff
   * positions. Armed only in "click" source mode. For harmonization it mutates
   * a pending clicked-note set and overlay while building, and on explicit
   * commit hands exercise_context a flat MIDI snapshot — it never broadcasts a
   * live NOTE event during chord construction (that channel drives the
   * settle-timer auto-grade).
   *
   * @constructor
   */
  var ClickNoteInputComponent = function (settings) {
    this.settings = settings || {};
    this.sheet = this.settings.sheet || null;
    this.exerciseContext = this.settings.exerciseContext || null;
    this.keySignature = this.settings.keySignature || null;

    this.enabled = false;
    this.palette = "diatonic"; // diatonic | sharp | flat | natural
    this._pending = [];        // [{ midi, step, alter, octave }]
    this._lastGhostKey = null;
  };

  ClickNoteInputComponent.prototype = new Component();

  _.extend(ClickNoteInputComponent.prototype, {

    initComponent: function () {
      _.bindAll(this, ["_onCanvasClick", "_onCanvasMove", "_onCanvasLeave",
        "_onSourceModeChange", "_onNextChord", "_commit"]);
      this.el = this._buildEl();
      if (this.sheet && typeof this.sheet.setClickNoteComponent === "function") {
        this.sheet.setClickNoteComponent(this);
      }
      this.subscribe(EVENTS.BROADCAST.INPUT_SOURCE_MODE, this._onSourceModeChange);
      this.subscribe(EVENTS.BROADCAST.NEXT_CHORD, this._onNextChord);
      // Commit gesture: bank key (SPACE/ENTER) routed through BANK_NOTES.
      this.subscribe(EVENTS.BROADCAST.BANK_NOTES, this._commit);
    },

    // ---- pending-state accessors (read by exercise_sheet) -----------------
    getPendingMidi: function () { return this._pending.map(function (n) { return n.midi; }); },
    getPendingSpellings: function () {
      return this._pending.map(function (n) {
        var acc = n.alter === 1 ? "#" : n.alter === -1 ? "b" : "";
        return n.step + acc + "/" + n.octave;
      });
    },
    getActiveColumn: function () { return this._activeColumn || null; },

    // ---- arming -----------------------------------------------------------
    _onSourceModeChange: function (mode) {
      if (mode === "click") { this.enable(); } else { this.disable(); }
      this._syncPalettePanel();
    },

    enable: function () {
      if (this.enabled) return;
      this.enabled = true;
      var canvas = this._canvas();
      if (canvas) {
        canvas.addEventListener("click", this._onCanvasClick);
        canvas.addEventListener("mousemove", this._onCanvasMove);
        canvas.addEventListener("mouseleave", this._onCanvasLeave);
      }
    },

    disable: function () {
      if (!this.enabled) return;
      this.enabled = false;
      var canvas = this._canvas();
      if (canvas) {
        canvas.removeEventListener("click", this._onCanvasClick);
        canvas.removeEventListener("mousemove", this._onCanvasMove);
        canvas.removeEventListener("mouseleave", this._onCanvasLeave);
      }
      this._clearPending();
    },

    _clearPending: function () {
      this._pending = [];
      if (this.sheet && typeof this.sheet.clearGhostNote === "function") this.sheet.clearGhostNote();
      if (this.sheet && typeof this.sheet.render === "function") this.sheet.render();
    },

    _onNextChord: function () {
      // Advancing to a new target clears any in-flight pending notes.
      this._pending = [];
    },

    // ---- geometry helpers -------------------------------------------------
    _canvas: function () {
      if (this.sheet && this.sheet.el) {
        var c = this.sheet.el.querySelector ? this.sheet.el.querySelector("canvas") : null;
        if (c) return c;
      }
      return document.querySelector("#staff canvas, canvas#staff, #staff-canvas");
    },

    _layout: function () {
      return (this.sheet && this.sheet.getStaffLayout) ? this.sheet.getStaffLayout() : null;
    },

    _key: function () {
      if (this.keySignature && this.keySignature.getKey) return this.keySignature.getKey();
      if (this.exerciseContext && this.exerciseContext.getDefinition) {
        var def = this.exerciseContext.getDefinition();
        if (def && def.getKeyName) return def.getKeyName();
      }
      return "C";
    },

    _activeTargetOnset: function () {
      var ctx = this.exerciseContext;
      if (!ctx) return null;
      var ptr = ctx._harmonizationPointer || 0;
      var targets = (ctx.getDefinition && ctx.getDefinition().getHarmonizationTargets)
        ? ctx.getDefinition().getHarmonizationTargets() : [];
      var t = targets[ptr];
      // Targets carry an offset in quarter-lengths; columns carry tick onsets.
      return t ? Math.round(t.offset * 1024) : null;
    },

    _eventPoint: function (e) {
      var canvas = this._canvas();
      var rect = canvas.getBoundingClientRect();
      return { px: e.clientX - rect.left + canvas.scrollLeft, py: e.clientY - rect.top };
    },

    _resolve: function (e) {
      var layout = this._layout();
      if (!layout) return null;
      // resolveClick already returns stepsFromTop + staveClef; the sheet derives
      // the ghost glyph's y from those, so no pixel recompute is needed here.
      return ClickNoteLogic.resolveClick(this._eventPoint(e), layout, {
        key: this._key(),
        palette: this.palette,
        activeColumnOnset: this._activeTargetOnset(),
      });
    },

    // ---- mouse handlers ---------------------------------------------------
    _onCanvasMove: function (e) {
      if (!this.enabled) return;
      var resolved = this._resolve(e);
      var key = resolved ? (resolved.midi + ":" + resolved.column.onset) : null;
      if (key === this._lastGhostKey) return; // throttle: only on change
      this._lastGhostKey = key;
      if (!resolved) { if (this.sheet) this.sheet.clearGhostNote(); return; }
      this._activeColumn = resolved.column;
      if (this.sheet) this.sheet.drawGhostNote(resolved);
    },

    _onCanvasLeave: function () {
      this._lastGhostKey = null;
      if (this.sheet) this.sheet.clearGhostNote();
    },

    _onCanvasClick: function (e) {
      if (!this.enabled) return;
      var resolved = this._resolve(e);
      if (!resolved) return; // out of range / outside active column / no layout
      this._activeColumn = resolved.column;

      // Toggle off if the exact pitch is already pending.
      var existing = -1;
      for (var i = 0; i < this._pending.length; i++) {
        if (this._pending[i].midi === resolved.midi) { existing = i; break; }
      }
      if (existing !== -1) {
        this._pending.splice(existing, 1);
        if (this.sheet) this.sheet.render();
        return;
      }

      // Hard size cap = voiceCountPolicy.max - lockedVoiceCount.
      var cap = this._capRemaining();
      if (this._pending.length >= cap) {
        this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
          type: "info", title: "Maximum notes",
          description: "This chord allows up to " + cap + " note(s).",
        });
        return;
      }

      this._pending.push({
        midi: resolved.midi, step: resolved.step,
        alter: resolved.alter, octave: resolved.octave,
      });
      if (this.sheet) this.sheet.render();
    },

    _capRemaining: function () {
      var ctx = this.exerciseContext;
      var policy = null, suppliedCount = 0;
      if (ctx && ctx.getDefinition) {
        var targets = ctx.getDefinition().getHarmonizationTargets
          ? ctx.getDefinition().getHarmonizationTargets() : [];
        var t = targets[ctx._harmonizationPointer || 0] || {};
        policy = t.voiceCountPolicy || null;
        var locked = t.lockedVoices || {};
        // Only voices SUPPLIED by the score (concrete .midi) are given notes the
        // student doesn't click — they reduce clickable slots and are merged at
        // commit. A pc-only locked voice is a constraint the student satisfies by
        // clicking, so it does NOT reduce slots. Same rule as the commit merge,
        // so future RN targets (no lockedVoices.B) give the student max slots and
        // require clicking the bass.
        suppliedCount = Object.keys(locked).filter(function (k) {
          return typeof locked[k].midi === "number";
        }).length;
      }
      return ClickNoteLogic.capRemaining(policy, suppliedCount);
    },

    // ---- commit -----------------------------------------------------------
    _commit: function () {
      if (!this.enabled) return;
      var ctx = this.exerciseContext;
      if (!ctx || typeof ctx.gradeHarmonizationMidiSet !== "function") return;
      var targets = ctx.getDefinition().getHarmonizationTargets
        ? ctx.getDefinition().getHarmonizationTargets() : [];
      var target = targets[ctx._harmonizationPointer || 0] || {};
      var lockedMidi = [];
      var locked = target.lockedVoices || {};
      Object.keys(locked).forEach(function (k) {
        if (typeof locked[k].midi === "number") lockedMidi.push(locked[k].midi);
      });
      var snapshot = ClickNoteLogic.buildCommitSnapshot(lockedMidi, this.getPendingMidi());
      ctx.gradeHarmonizationMidiSet(snapshot);
      this._pending = [];
      if (this.sheet) this.sheet.render();
    },

    // ---- palette UI -------------------------------------------------------
    setPalette: function (p) {
      this.palette = p;
      this._syncPaletteButtons();
    },

    _buildEl: function () {
      var self = this;
      var wrap = $('<div class="click-note-input" style="display:none;"></div>');
      var palette = $('<div class="accidental-palette input-mode-toggle"></div>');
      var defs = [
        ["diatonic", "Key"], ["sharp", "♯"], ["flat", "♭"], ["natural", "♮"]
      ];
      this._paletteBtns = {};
      defs.forEach(function (d) {
        var btn = $('<button class="input-mode-btn"></button>').text(d[1]);
        btn.on("click", function (e) { e.preventDefault(); self.setPalette(d[0]); });
        self._paletteBtns[d[0]] = btn;
        palette.append(btn);
      });
      var doneBtn = $('<button class="input-mode-btn click-note-done">Done</button>');
      doneBtn.on("click", function (e) { e.preventDefault(); self._commit(); });
      wrap.append(palette).append(doneBtn);
      this._paletteWrap = wrap;
      this._syncPaletteButtons();
      return wrap;
    },

    _syncPaletteButtons: function () {
      var self = this;
      Object.keys(this._paletteBtns || {}).forEach(function (k) {
        self._paletteBtns[k]
          .toggleClass("input-mode-btn-active", k === self.palette)
          .toggleClass("input-mode-btn-inactive", k !== self.palette);
      });
    },

    _syncPalettePanel: function () {
      if (!this._paletteWrap) return;
      if (this.enabled) { this._paletteWrap.show(); } else { this._paletteWrap.hide(); }
    },

    render: function () { return this; },
    renderTo: function (selector) { $(selector).append(this.el); return this; },
    destroy: function () { this.disable(); },
  });

  return ClickNoteInputComponent;
});
```

> **Implementer note:** the `_key()`/`getKeyName` and `_activeTargetOnset` offset→tick conversion assume the harmonization target carries `offset` in quarter-lengths (×1024 = tick onset, matching `getBassLabelAtOffset`'s `noteOnset / 1024`). Confirm against a real harmonization exercise's `harmonizationTargets` in Task 11; if the target stores onset differently, adjust `_activeTargetOnset` only — the column records already carry tick `onset` from the adapter.

- [ ] **Step 2: Commit**

```bash
git add lab/static/js/src/components/input/click_note.js
git commit -m "feat: add ClickNoteInputComponent for MIDI-free staff click entry"
```

---

## Task 10: Wire the component + source mode into `exercise.js` and `play.js`

Instantiate `ClickNoteInputComponent` beside `NoteNameInputComponent` in both entrypoints, gated identically. Each entrypoint owns source-mode state: default from `MIDI_INPUTS_CHANGED`, persist per session in `localStorage`, broadcast `INPUT_SOURCE_MODE`, and inform the sheet.

**Files:**
- Modify: `lab/static/js/src/components/app/exercise.js`
- Modify: `lab/static/js/src/components/app/play.js`

- [ ] **Step 1: Add the AMD dependency in both files**

In each entrypoint's `define([...], function(...) {` header, add the module id `"app/components/input/click_note"` and the matching `ClickNoteInputComponent` parameter, beside the existing `NoteNameInputComponent` import.

- [ ] **Step 2: Add a source-mode bootstrap helper**

In each entrypoint, add a small inline source-mode controller (same code in both — they have separate component graphs). Place near where components are created:

```javascript
      var SOURCE_MODE_KEY = "harmonylab.inputSourceMode";
      var self = this;
      var _midiInputCount = 0;
      var _sourceMode = null;
      function readStoredMode() {
        try { return window.localStorage.getItem(SOURCE_MODE_KEY); } catch (e) { return null; }
      }
      function persistMode(m) {
        try { window.localStorage.setItem(SOURCE_MODE_KEY, m); } catch (e) {}
      }
      function applySourceMode(mode) {
        _sourceMode = mode;
        self.broadcast(EVENTS.BROADCAST.INPUT_SOURCE_MODE, mode);
        var sheet = self.models && self.models.exerciseSheet;
        if (sheet && sheet.setInputSourceMode) sheet.setInputSourceMode(mode);
      }
      this.subscribe(EVENTS.BROADCAST.MIDI_INPUTS_CHANGED, function (payload) {
        _midiInputCount = (payload && payload.inputCount) || 0;
        if (_sourceMode === null) {
          applySourceMode(ClickNoteLogic.defaultSourceMode(_midiInputCount, readStoredMode()));
        }
        // Mid-session change updates recommendation only; never force-switch.
      });
```

> **Implementer note:** match the file's real references for the app instance (`self`), the events module (`EVENTS`), the sheet model accessor (`self.models.exerciseSheet` or equivalent — verify the actual property name in each entrypoint), and `ClickNoteLogic` (add to the `define` header). Wire the Live/Click toggle buttons to call `persistMode(m); applySourceMode(m);` — render them in a small toolbar near `#piano` (mirror `note_name.js`'s toggle markup). On manual toggle, clear pending state (the component already clears on `INPUT_SOURCE_MODE` change via `_onSourceModeChange` → `disable`/`enable`).

- [ ] **Step 3: Instantiate the component (exercise.js)**

In `exercise.js`, add a new component initializer beside the `NoteNameInputComponent` block (after line 247), gated identically:

```javascript
      function () {
        if (disableComputerKeyboardInput || isSymbolicMeterExercise || isKeySignatureExercise) {
          return;
        }
        var c = new ClickNoteInputComponent({
          sheet: this.models.exerciseSheet,
          exerciseContext: this.models.exerciseContext,
          keySignature: this.models.keySignature,
        });
        c.init(this);
        c.renderTo("#piano");
        this.addComponent(c);
      },
```

- [ ] **Step 4: Instantiate the component (play.js)**

In `play.js`, add beside the `NoteNameInputComponent` block (after line 104):

```javascript
      function () {
        var c = new ClickNoteInputComponent({
          sheet: this.models.exerciseSheet,
          exerciseContext: this.models.exerciseContext,
          keySignature: this.models.keySignature,
        });
        c.init(this);
        c.renderTo("#piano");
        this.addComponent(c);
      },
```

> **Implementer note:** verify the exact model accessor names (`this.models.exerciseSheet`, `this.models.exerciseContext`, `this.models.keySignature`) in each entrypoint and adjust if the file uses different names. The component degrades gracefully if a model is absent (`_key()` falls back to `"C"`), but the sheet reference is required for layout + ghost.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/components/app/exercise.js lab/static/js/src/components/app/play.js
git commit -m "feat: wire click-note component and Live/Click source mode into both entrypoints"
```

---

## Task 11: Manual browser verification + cleanup

Per the CLAUDE.md UI rule, canvas/DOM behavior is verified in the browser. The pure logic is already covered by node tests (Tasks 1, 3, 4).

**Files:**
- (Verification only; any fixes land in the relevant module above.)

- [ ] **Step 1: Run all pure-logic tests**

```bash
node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
node lab/static/js/src/components/input/click_note_logic.test.js
```
Expected: both exit 0, all assertions pass.

- [ ] **Step 2: Confirm the debug log is gone**

Run: `grep -rn "HARM-DEBUG" lab/static/js/src/`
Expected: no matches.

- [ ] **Step 3: Browser pass — harmonization, no MIDI device**

Open a harmonization exercise from the **play** view with no MIDI controller connected. Verify:
- App defaults to **Click** mode and surfaces the "using click input" recommendation.
- Accidental palette + **Done** button are visible; qwerty/notename toggle is not the same control.
- Hovering the staff draws a faint ghost notehead that tracks the cursor and snaps to staff positions; leaving the canvas clears it.
- Clicking empty positions in the active target column adds blue/gray pending noteheads; re-clicking the same pitch removes it.
- Clicking a new pitch past the cap (`voiceCountPolicy.max - lockedVoiceCount`) is a no-op with a brief "Maximum notes" hint; toggling an existing pending pitch off still works.
- Columns ahead of the current target are inert (no ghost, no add).
- Pressing **Done** (or SPACE/ENTER) grades `lockedTargetMidi + pendingClickedMidi` — a correct chord advances to the next target and clears pending; verify it does **not** grade an empty set.
- After advance, pending state is cleared.

- [ ] **Step 4: Browser pass — device present + mode toggle**

With a MIDI controller connected (or simulated): app defaults to **Live**; palette/Done hidden; existing MIDI settle-grade path works unchanged; qwerty/notename keyboard sub-toggle still works in Live mode. Toggle to **Click**: a connected device no longer auto-grades harmonization or adds to the pending set; only click commit grades. Switch modes mid-build: pending chord clears. Repeat the Step 3 build/commit flow from the **exercise** view entrypoint to confirm both wirings.

- [ ] **Step 5: Browser pass — device change mid-session**

Unplug the last device mid-session: verify the recommendation updates (offer "switch to click input?") but the student is **not** force-switched out of the current mode.

- [ ] **Step 6: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address click-note input issues found in manual browser verification"
```

---

## Documentation

No new exercise type or management command, so no `docs/exercise_types.md` / `docs/management_commands.md` change (per spec §8). This plan + the committed spec satisfy the CLAUDE.md "significant new feature" documentation requirement.
