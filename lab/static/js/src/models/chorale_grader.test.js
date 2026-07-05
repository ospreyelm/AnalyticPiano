/*
 * Run: node lab/static/js/src/models/chorale_grader.test.js
 */
"use strict";

var assert = require("assert");
var { requireDefault } = require("../../test/require_esm");
var ChoraleGrader = requireDefault(require("./chorale_grader"));

// Builds a grader with hand-rolled timeline/windowGroups, bypassing
// initFromDefinition (and its ScoreTimeline dependency) since
// restorePlayedState() only touches this internal state.
function makeGrader(timeline, windowGroups) {
  var grader = new ChoraleGrader({});
  grader.timeline = timeline;
  grader.windowGroups = windowGroups;
  grader.pointer = 0;
  grader.playedNoteIds = new Set();
  grader.finished = false;
  return grader;
}

// Regression: reloading a page used to wipe grader.playedNoteIds/pointer
// entirely, since nothing persisted or restored them (unlike identification's
// localStorage-backed answers). restorePlayedState() is the piece that lets
// a saved snapshot put the grader back where the student left off.

function testRestorePlayedStateAdvancesPointerPastCompletedWindows() {
  var timeline = [{ id: 0 }, { id: 1 }, { id: 2 }, { id: 3 }];
  var windowGroups = [[0, 1], [2, 3]]; // window 0: ids 0,1 — window 1: ids 2,3
  var grader = makeGrader(timeline, windowGroups);

  grader.restorePlayedState([0, 1]); // window 0 fully played

  assert.strictEqual(grader.pointer, 1, "pointer should advance past the completed window");
  assert.strictEqual(grader.finished, false);
  assert.ok(grader.getPlayedNoteIds().has(0));
  assert.ok(grader.getPlayedNoteIds().has(1));
}

testRestorePlayedStateAdvancesPointerPastCompletedWindows();

function testRestorePlayedStateDoesNotAdvancePastPartiallyPlayedWindow() {
  var timeline = [{ id: 0 }, { id: 1 }, { id: 2 }, { id: 3 }];
  var windowGroups = [[0, 1], [2, 3]];
  var grader = makeGrader(timeline, windowGroups);

  grader.restorePlayedState([0]); // only half of window 0 played

  assert.strictEqual(grader.pointer, 0, "pointer should stay on the incomplete window");
}

testRestorePlayedStateDoesNotAdvancePastPartiallyPlayedWindow();

function testRestorePlayedStateMarksFinishedWhenAllWindowsComplete() {
  var timeline = [{ id: 0 }, { id: 1 }];
  var windowGroups = [[0, 1]];
  var grader = makeGrader(timeline, windowGroups);

  grader.restorePlayedState([0, 1]);

  assert.strictEqual(grader.pointer, 1);
  assert.strictEqual(grader.finished, true);
}

testRestorePlayedStateMarksFinishedWhenAllWindowsComplete();

function testRestorePlayedStateNoOpOnEmptyInput() {
  var timeline = [{ id: 0 }, { id: 1 }];
  var windowGroups = [[0, 1]];
  var grader = makeGrader(timeline, windowGroups);

  grader.restorePlayedState([]);

  assert.strictEqual(grader.pointer, 0);
  assert.strictEqual(grader.getPlayedNoteIds().size, 0);
}

testRestorePlayedStateNoOpOnEmptyInput();

console.log("chorale_grader tests passed");
