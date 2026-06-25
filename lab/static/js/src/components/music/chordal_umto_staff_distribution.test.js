"use strict";

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var logic = require("./chordal_umto_staff_distribution");

function getVoiceCountFromConfig() {
  var configPath = path.resolve(__dirname, "../../config/general.js");
  var code = fs.readFileSync(configPath, "utf8");
  var voiceCounts = null;
  var context = {
    define: function (depsOrObj, factory) {
      var obj = typeof factory === "function" ? factory(undefined) : depsOrObj;
      voiceCounts = obj.voiceCountForKeyboardStyle;
    }
  };
  vm.runInNewContext(code, context);
  return voiceCounts;
}

// Set dynamic voice counts from config to avoid drift
var configCounts = getVoiceCountFromConfig();
logic._setKeyboardStyleCounts(configCounts);

var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    console.log("       got: " + JSON.stringify(actual));
    console.log("  expected: " + JSON.stringify(expected));
    fail++;
  }
}

console.log("\nchordal UMTO staff distribution:");

assertEqual(
  "LH routes every pitch to bass",
  logic.routeChordMidis([48, 60, 72], "LH"),
  { treble: [], bass: [48, 60, 72] }
);

assertEqual(
  "bass alias routes every pitch to bass",
  logic.routeChordMidis([48, 60, 72], "bass"),
  { treble: [], bass: [48, 60, 72] }
);

assertEqual(
  "RH routes every pitch to treble",
  logic.routeChordMidis([48, 60, 72], "RH"),
  { treble: [48, 60, 72], bass: [] }
);

assertEqual(
  "treble alias routes every pitch to treble",
  logic.routeChordMidis([48, 60, 72], "treble"),
  { treble: [48, 60, 72], bass: [] }
);

assertEqual(
  "grandStaff splits at middle C",
  logic.routeChordMidis([48, 60, 72], "grandStaff"),
  { treble: [60, 72], bass: [48] }
);

assertEqual(
  "keyboard keeps mixed register grand-staff routing",
  logic.routeChordMidis([48, 60, 64], "keyboard"),
  { treble: [60, 64], bass: [48] }
);

assertEqual(
  "keyboard moves lowest note to bass when all notes are high",
  logic.routeChordMidis([60, 64, 67], "keyboard"),
  { treble: [64, 67], bass: [60] }
);

assertEqual(
  "keyboardPlusRHBias routes non-keyboard-style chords below G3 to bass (using length 6 to bypass keyboard-style split)",
  logic.routeChordMidis([52, 55, 59, 62, 65, 68], "keyboardPlusRHBias"),
  { treble: [55, 59, 62, 65, 68], bass: [52] }
);

assertEqual(
  "keyboardPlusLHBias routes non-keyboard-style chords through F4 to bass (using length 6 to bypass keyboard-style split)",
  logic.routeChordMidis([52, 55, 59, 62, 65, 68], "keyboardPlusLHBias"),
  { treble: [68], bass: [52, 55, 59, 62, 65] }
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
