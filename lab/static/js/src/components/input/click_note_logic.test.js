/*
 * Run: node lab/static/js/src/components/input/click_note_logic.test.js
 */
"use strict";

var { requireDefault } = require("../../../test/require_esm");
var mod = requireDefault(require("./click_note_logic"));

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

// Sharp palette: F5 -> F#5 midi 78.
var rSharp = mod.resolveClick({ px: 100, py: 95 }, LAYOUT, {
  key: "jG_", palette: "sharp", activeColumnOnset: 0
});
assertEqual("sharp palette -> F#5 midi 78", rSharp && rSharp.midi, 78);

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

var r5b = mod.resolveClick({ px: 100, py: 175 }, LAYOUT, {
  key: "jEb", palette: "diatonic", activeColumnOnset: 0
});
assertEqual("Eb major key palette -> A3 becomes Ab3", r5b && r5b.midi, 56);
assertEqual("Eb major key palette -> A alteration is flat", r5b && r5b.alter, -1);

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

if (fail > 0) {
  console.error("\n" + fail + " assertion(s) failed.");
  process.exit(1);
} else {
  console.log("\nAll click_note_logic assertions passed.");
}
