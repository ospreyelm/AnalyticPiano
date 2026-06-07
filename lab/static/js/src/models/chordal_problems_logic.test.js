// lab/static/js/src/models/chordal_problems_logic.test.js
// Run: node lab/static/js/src/models/chordal_problems_logic.test.js
"use strict";
var logic = require("./chordal_problems_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + " got " + JSON.stringify(actual) + " want " + JSON.stringify(expected)); fail++; }
}

// chordsToProblems: chordal UMTO chords[] -> chord-bank gradeable problems
var chords = [
  { offset: 0.0, duration: 1.0, visible: [60, 64, 67], hidden: [] },
  { offset: 1.0, duration: 1.0, visible: [62], hidden: [50] }
];
var problems = logic.chordsToProblems(chords);
eq("two problems", problems.length, 2);
eq("first visible preserved order", problems[0].visible, [60, 64, 67]);
eq("first notes = visible+hidden", problems[0].notes, [60, 64, 67]);
eq("second merges hidden into notes", problems[1].notes, [50, 62]); // notes sorted for grading
eq("second visible only visible", problems[1].visible, [62]);
eq("second hidden preserved", problems[1].hidden, [50]);

// isChordalUMTO: detect chordal score-kind from a parsed definition-ish object
eq("chordal detected", logic.isChordalUMTO({ score: { umto: { metadata: { score_kind: "chordal" } } } }), true);
eq("voices not chordal", logic.isChordalUMTO({ score: { umto: { metadata: { score_kind: "voices" } } } }), false);
eq("missing umto not chordal", logic.isChordalUMTO({ score: {} }), false);
eq("preserve backend measures for chordal score", logic.shouldPreserveChordalMeasures({
  measures: [{ staves: { treble: { voices: [] } } }],
  umto: { metadata: { score_kind: "chordal" } }
}), true);
eq("do not preserve voices umto measures", logic.shouldPreserveChordalMeasures({
  measures: [{ staves: { treble: { voices: [] } } }],
  umto: { metadata: { score_kind: "voices" } }
}), false);

console.log(pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
