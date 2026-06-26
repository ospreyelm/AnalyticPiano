"use strict";

// Structural guard for the identification mixin split.
// Asserts the four identification mixin files together define exactly the
// same set of property names, with no duplicates across files.
var assert = require("assert");
var fs = require("fs");
var path = require("path");

var DIR = path.join(__dirname, "..", "src", "components", "music");

var FILES = [
  "exercise_sheet_identification.js",
  "exercise_sheet_identification_input_mode.js",
  "exercise_sheet_identification_canvas.js",
  "exercise_sheet_identification_controls.js",
  "exercise_sheet_identification_logic.js",
];

// Top-level mixin properties are indented exactly four spaces in these files.
var PROP_RE = /^ {4}([_a-zA-Z][_a-zA-Z0-9]*):/;

var EXPECTED = [
  "_IDENT_INPUT_MODE_KEY",
  "_applyIdentificationAnswer",
  "_buildInputComponent",
  "_captureFocusedTextInput",
  "_cloneIdentificationAnswers",
  "_closeIdentPopup",
  "_destroyIdentificationInputComponent",
  "_getActiveIdentificationMode",
  "_getIdentInputMode",
  "_getIdentificationInputContainer",
  "_getIdentificationSlots",
  "_getIdentificationToggleRow",
  "_getRepresentableTextHydrationAnswers",
  "_getStoredIdentInputMode",
  "_getStoredIdentificationAnswer",
  "_getTextInputState",
  "_getVisibleIdentificationAnswers",
  "_getVisibleIdentificationProblems",
  "_hydrateTextInputComponent",
  "_isChoraleIdentificationExercise",
  "_isIdentificationLikeExercise",
  "_isIdentificationProblemLocked",
  "_onIdentKeyDown",
  "_refreshIdentificationModeUI",
  "_restoreFocusedTextInput",
  "_serializeIdentificationAnswersForText",
  "_setIdentInputMode",
  "_showIdentPopup",
  "_supportsTextInputMode",
  "_syncIdentificationInputComponent",
  "_syncIdentificationModeState",
  "_updateIdentificationProgressUI",
  "drawIdentificationLabels",
  "initIdentificationMode",
  "onSubmitIdentification",
  "onToggleMode",
  "renderInputModeToggle",
  "renderModeToggle",
].sort();

var seen = {};
var duplicates = [];

FILES.forEach(function (file) {
  var full = path.join(DIR, file);
  if (!fs.existsSync(full)) {
    throw new Error("Missing mixin file: " + file);
  }
  var lines = fs.readFileSync(full, "utf8").split("\n");
  lines.forEach(function (line) {
    var m = PROP_RE.exec(line);
    if (!m) { return; }
    var name = m[1];
    if (seen[name]) {
      duplicates.push(name + " (in " + seen[name] + " and " + file + ")");
    }
    seen[name] = file;
  });
});

assert.strictEqual(duplicates.length, 0, "Duplicate properties: " + duplicates.join(", "));

var actual = Object.keys(seen).sort();
assert.deepStrictEqual(actual, EXPECTED,
  "Method set drift.\nMissing: " + EXPECTED.filter(function (n) { return actual.indexOf(n) < 0; }) +
  "\nUnexpected: " + actual.filter(function (n) { return EXPECTED.indexOf(n) < 0; }));

console.log("identification mixin manifest guard passed (" + actual.length + " properties across " + FILES.length + " files)");
