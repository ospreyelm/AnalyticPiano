"use strict";

var { requireDefault } = require("../../test/require_esm");
var logic = requireDefault(require("./harmonization_grader_logic"));

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

// ---------------------------------------------------------------------------
// harmonizationMatch
// ---------------------------------------------------------------------------

var target = {
  bassMidi: 48,
  bassPc: 0,
  requiredUpperPcs: [9, 4],
  allowedPcs: [0, 9, 4],
  lockedVoices: { B: { midi: 48, pc: 0, spelling: "C" } },
  voiceCountPolicy: { expected: 4, min: 3, max: 4 }
};

assertEqual("correct three-voice realization passes",
  logic.harmonizationMatch(target, [48, 52, 57]).state, "correct");

assertEqual("correct four-voice realization passes",
  logic.harmonizationMatch(target, [48, 52, 57, 60]).state, "correct");

assertEqual("missing required pc is partial",
  logic.harmonizationMatch(target, [48, 52]).state, "partial");

assertEqual("illegal pc is incorrect",
  logic.harmonizationMatch(target, [48, 52, 58]).state, "incorrect");

assertEqual("wrong bass is incorrect",
  logic.harmonizationMatch(target, [47, 52, 57]).state, "incorrect");

assertEqual("too many voices is incorrect",
  logic.harmonizationMatch(target, [48, 52, 57, 60, 64]).state, "incorrect");

assertEqual("too few voices is partial",
  logic.harmonizationMatch(target, [48]).state, "partial");

// Locked soprano
var sopranoTarget = {
  bassMidi: 48,
  bassPc: 0,
  requiredUpperPcs: [9, 4],
  allowedPcs: [0, 9, 4],
  lockedVoices: { B: { midi: 48, pc: 0 }, S: { midi: 60, pc: 0 } },
  voiceCountPolicy: { expected: 4, min: 4, max: 4 }
};

assertEqual("locked soprano exact midi passes",
  logic.harmonizationMatch(sopranoTarget, [48, 52, 57, 60]).state, "correct");

assertEqual("locked soprano wrong octave fails",
  logic.harmonizationMatch(sopranoTarget, [48, 52, 57, 72]).state, "incorrect");

// note map
var result = logic.harmonizationMatch(target, [48, 52, 58]);
assertEqual("illegal note flagged in note map", result.note[58], "incorrect");
assertEqual("legal note correct in note map", result.note[52], "correct");

// ---------------------------------------------------------------------------
// createHeldNoteTracker
// ---------------------------------------------------------------------------

var tracker = logic.createHeldNoteTracker({ releaseGraceMs: 120 });
tracker.noteOn(48, 0);
tracker.noteOn(52, 20);
tracker.noteOn(57, 40);
assertEqual("tracker holds three notes", tracker.activeMidi(100), [48, 52, 57]);

tracker.noteOff(48, 110);
assertEqual("release grace keeps note briefly", tracker.activeMidi(150), [48, 52, 57]);
assertEqual("release grace expires note after timeout", tracker.activeMidi(240), [52, 57]);

tracker.noteOff(52, 250);
tracker.noteOff(57, 250);
assertEqual("all notes released after grace", tracker.activeMidi(400), []);

tracker.reset();
assertEqual("reset clears all notes", tracker.activeMidi(500), []);

tracker.noteOn(60);
tracker.noteOn(64);
tracker.noteOff(60, 0);
assertEqual("note still held (other notes active)", tracker.activeMidi(50), [60, 64]);

// ---------------------------------------------------------------------------
if (failed > 0) {
  console.log("\n" + failed + " test(s) FAILED");
  process.exit(1);
} else {
  console.log("\nAll tests passed.");
}
