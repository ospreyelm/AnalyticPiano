/* Run: node lab/static/js/src/models/keyboard_range_logic.test.js */
"use strict";

var mod = require("./keyboard_range_logic");
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

assertEqual(
  "keeps default range for ordinary targets",
  mod.resolveKeyboardRange({
    targetMidis: [60, 64, 67],
    shortcutMin: 43,
    shortcutMax: 77,
    baseNoteAnchor: 0,
    baseOctaveAdjustment: 0
  }),
  { noteAnchor: 0, octaveAdjustment: 0, octaveShift: 0 }
);

assertEqual(
  "shifts up one octave when all targets sit above the shortcut range",
  mod.resolveKeyboardRange({
    targetMidis: [76, 79],
    shortcutMin: 43,
    shortcutMax: 77,
    baseNoteAnchor: 0,
    baseOctaveAdjustment: 0
  }),
  { noteAnchor: 12, octaveAdjustment: 1, octaveShift: 12 }
);

assertEqual(
  "does not shift when a wide exercise cannot fit and the default misses least",
  mod.resolveKeyboardRange({
    targetMidis: [43, 79],
    shortcutMin: 43,
    shortcutMax: 77,
    baseNoteAnchor: 0,
    baseOctaveAdjustment: 0
  }),
  { noteAnchor: 0, octaveAdjustment: 0, octaveShift: 0 }
);

assertEqual(
  "extracts targets from UMTO grading slices",
  mod.collectTargetMidis({
    getGrading: function () {
      return [
        { target_midi_pitches: [76] },
        { target_midi_pitches: [79, 83] }
      ];
    }
  }),
  [76, 79, 83]
);

if (fail > 0) {
  console.error("\n" + fail + " test(s) failed");
  process.exit(1);
}
console.log("\nAll tests passed");
