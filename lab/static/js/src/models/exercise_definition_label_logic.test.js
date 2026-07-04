"use strict";

var assert = require("assert");
var { requireDefault } = require("../../test/require_esm");
var LabelLogic = requireDefault(require("./exercise_definition_label_logic"));

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
