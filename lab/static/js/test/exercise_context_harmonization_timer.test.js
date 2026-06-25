"use strict";

// Regression guard: harmonization click mode requires triggerTimer() at the
// start of the grade() harmonization branch. Without it, this.timer stays null
// in click mode (click_note.js never fires onMidiNote), causing
// compileExerciseReport() to throw on this.timer.end and return null —
// silently skipping the AJAX submission so the scoreCard never appears and
// the playlist never advances past exercise 1.

var assert = require("assert");
var fs = require("fs");
var path = require("path");

var src = fs.readFileSync(
  path.join(__dirname, "..", "src", "models", "exercise_context.js"),
  "utf8"
);

var lines = src.split("\n");

// Find the line index of the harmonization grade branch entry point.
var branchIdx = lines.findIndex(function (line) {
  return /else if \(isHarmonizationExercise\)/.test(line);
});
assert.ok(branchIdx >= 0, "Could not find harmonization grade branch in exercise_context.js");

// The very next non-empty line must call this.triggerTimer().
var nextLine = "";
for (var i = branchIdx + 1; i < lines.length; i++) {
  nextLine = lines[i].trim();
  if (nextLine !== "" && nextLine !== "{") break;
}

assert.ok(
  /this\.triggerTimer\(\)/.test(nextLine),
  "triggerTimer() must be the first call in the harmonization grade branch. " +
  "Got: " + JSON.stringify(nextLine) +
  " (line " + (branchIdx + 2) + ")"
);

console.log("PASS: harmonization grade branch calls triggerTimer() (line " + (branchIdx + 2) + ")");
