/**
 * Tests for ExerciseScoreCard pure logic functions.
 * Run: node exercise_score_card.test.js
 * (No AMD loader needed — tests the exported logic directly.)
 */

"use strict";

// ---- Inline the pure functions under test (replicated from the module) ----
// These are extracted so we can test them without a DOM or RequireJS.

function scorePct(numerator, denominator) {
  if (!denominator || denominator === 0) return null;
  return Math.round((numerator / denominator) * 100);
}

function tierLabel(pct) {
  if (pct === null) return "—";
  if (pct === 100) return "Mastered";
  if (pct >= 80) return "Proficient";
  if (pct >= 60) return "Familiar";
  if (pct >= 40) return "Attempted";
  return "Needs Practice";
}

function masteryColor(pct) {
  if (pct === null) return "gray";
  if (pct === 100) return "green";
  if (pct >= 60) return "blue";
  return "amber";
}

function segmentColor(level) {
  var map = { mastered: "green", proficient: "blue", familiar: "amber", not_started: "lightgray" };
  return map[level] || "lightgray";
}

function primaryCta(pct, masteryChanges, nextSkillName) {
  var isLow = pct !== null && pct < 60;
  if (isLow) return "Try Again";
  var isMastered = false;
  if (masteryChanges) {
    var keys = Object.keys(masteryChanges);
    for (var i = 0; i < keys.length; i++) {
      if (masteryChanges[keys[i]].new === "mastered") {
        isMastered = true;
        break;
      }
    }
  }
  if (isMastered && nextSkillName) return "Start " + nextSkillName + " →";
  return "Next Exercise →";
}

function bannerState(masteryChanges) {
  if (!masteryChanges || Object.keys(masteryChanges).length === 0) return null;
  var keys = Object.keys(masteryChanges);
  for (var i = 0; i < keys.length; i++) {
    var change = masteryChanges[keys[i]];
    if (change.new === "mastered") return { type: "mastered", skill: keys[i], old: change.old, new: change.new };
  }
  // level-up (not mastered)
  var key = keys[0];
  return { type: "level_up", skill: key, old: masteryChanges[key].old, new: masteryChanges[key].new };
}

// ---- Test runner ----

var pass = 0, fail = 0;

function assert(label, condition) {
  if (condition) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    fail++;
  }
}

function assertEqual(label, actual, expected) {
  var ok = actual === expected;
  if (!ok) console.log("       got: " + JSON.stringify(actual) + ", expected: " + JSON.stringify(expected));
  assert(label, ok);
}

// ---- scorePct ----
console.log("\nscorePct:");
assertEqual("5/5 = 100", scorePct(5, 5), 100);
assertEqual("4/5 = 80", scorePct(4, 5), 80);
assertEqual("3/5 = 60", scorePct(3, 5), 60);
assertEqual("2/5 = 40", scorePct(2, 5), 40);
assertEqual("1/5 = 20", scorePct(1, 5), 20);
assertEqual("0 denominator = null", scorePct(0, 0), null);
assertEqual("null denominator = null", scorePct(5, null), null);

// ---- tierLabel ----
console.log("\ntierLabel:");
assertEqual("100% = Mastered", tierLabel(100), "Mastered");
assertEqual("95% = Proficient", tierLabel(95), "Proficient");
assertEqual("80% = Proficient", tierLabel(80), "Proficient");
assertEqual("70% = Familiar", tierLabel(70), "Familiar");
assertEqual("60% = Familiar", tierLabel(60), "Familiar");
assertEqual("50% = Attempted", tierLabel(50), "Attempted");
assertEqual("40% = Attempted", tierLabel(40), "Attempted");
assertEqual("39% = Needs Practice", tierLabel(39), "Needs Practice");
assertEqual("null = —", tierLabel(null), "—");

// ---- masteryColor ----
console.log("\nmasteryColor:");
assertEqual("100 = green", masteryColor(100), "green");
assertEqual("80 = blue", masteryColor(80), "blue");
assertEqual("60 = blue", masteryColor(60), "blue");
assertEqual("59 = amber", masteryColor(59), "amber");
assertEqual("null = gray", masteryColor(null), "gray");

// ---- segmentColor ----
console.log("\nsegmentColor:");
assertEqual("mastered = green", segmentColor("mastered"), "green");
assertEqual("proficient = blue", segmentColor("proficient"), "blue");
assertEqual("familiar = amber", segmentColor("familiar"), "amber");
assertEqual("not_started = lightgray", segmentColor("not_started"), "lightgray");
assertEqual("unknown = lightgray", segmentColor("unknown"), "lightgray");

// ---- primaryCta ----
console.log("\nprimaryCta:");
assertEqual("normal = Next Exercise →", primaryCta(80, {}, null), "Next Exercise →");
assertEqual("low (<60) = Try Again", primaryCta(50, {}, null), "Try Again");
assertEqual("null pct = Next Exercise →", primaryCta(null, {}, null), "Next Exercise →");
var masteredChange = { Note_Names: { old: "proficient", new: "mastered" } };
assertEqual("mastered with next = Start X →", primaryCta(100, masteredChange, "Ledger Lines"), "Start Ledger Lines →");
assertEqual("mastered no next = Next Exercise →", primaryCta(100, masteredChange, null), "Next Exercise →");
var levelUpChange = { Note_Names: { old: "familiar", new: "proficient" } };
assertEqual("level up (not mastered) = Next Exercise →", primaryCta(85, levelUpChange, "Ledger Lines"), "Next Exercise →");

// ---- bannerState ----
console.log("\nbannerState:");
assert("no changes = null", bannerState(null) === null);
assert("empty changes = null", bannerState({}) === null);
var b1 = bannerState(masteredChange);
assert("mastered type", b1 && b1.type === "mastered");
assert("mastered skill", b1 && b1.skill === "Note_Names");
var b2 = bannerState(levelUpChange);
assert("level_up type", b2 && b2.type === "level_up");
assert("level_up old", b2 && b2.old === "familiar");
assert("level_up new", b2 && b2.new === "proficient");

// ---- ExerciseScoreCard class interface test ----
// Requires the module to export _scorePct, _tierLabel, _masteryColor, _segmentColor,
// _primaryCta, _bannerState as testable helpers.
// Test that the module file exists and exports correctly.
console.log("\nExerciseScoreCard module:");
try {
  var mod = require("./exercise_score_card_logic");
  assert("exports _scorePct", typeof mod._scorePct === "function");
  assert("exports _tierLabel", typeof mod._tierLabel === "function");
  assert("exports _masteryColor", typeof mod._masteryColor === "function");
  assert("exports _segmentColor", typeof mod._segmentColor === "function");
  assert("exports _primaryCta", typeof mod._primaryCta === "function");
  assert("exports _bannerState", typeof mod._bannerState === "function");
  // Cross-check: module's logic matches inline
  assertEqual("module _scorePct(4,5)=80", mod._scorePct(4, 5), 80);
  assertEqual("module _tierLabel(100)=Mastered", mod._tierLabel(100), "Mastered");
  assertEqual("module _masteryColor(100)=green", mod._masteryColor(100), "green");
  assertEqual("module _segmentColor('mastered')=green", mod._segmentColor("mastered"), "green");
} catch (e) {
  console.log("  FAIL: module not found — " + e.message);
  fail += 7;
}

// ---- Summary ----
console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
