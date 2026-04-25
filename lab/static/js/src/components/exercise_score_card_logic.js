/**
 * Pure logic helpers for ExerciseScoreCard.
 * No DOM, no AMD — exported for both node tests and AMD bundle.
 */

"use strict";

function _scorePct(numerator, denominator) {
  if (!denominator || denominator === 0) return null;
  return Math.round((numerator / denominator) * 100);
}

function _tierLabel(pct) {
  if (pct === null) return "—";
  if (pct === 100) return "Mastered";
  if (pct >= 80) return "Proficient";
  if (pct >= 60) return "Familiar";
  if (pct >= 40) return "Attempted";
  return "Needs Practice";
}

function _masteryColor(pct) {
  if (pct === null) return "gray";
  if (pct === 100) return "green";
  if (pct >= 60) return "blue";
  return "amber";
}

function _segmentColor(level) {
  var map = { mastered: "green", proficient: "blue", familiar: "amber", attempted: "amber", not_started: "lightgray" };
  return map[level] || "lightgray";
}

function _primaryCta(pct, masteryChanges, nextSkillName) {
  if (pct !== null && pct < 60) return "Try Again";
  var keys = masteryChanges ? Object.keys(masteryChanges) : [];
  for (var i = 0; i < keys.length; i++) {
    if (masteryChanges[keys[i]].new === "mastered" && nextSkillName) {
      return "Start " + nextSkillName + " →";
    }
  }
  return "Next Exercise →";
}

function _bannerState(masteryChanges) {
  if (!masteryChanges || Object.keys(masteryChanges).length === 0) return null;
  var keys = Object.keys(masteryChanges);
  for (var i = 0; i < keys.length; i++) {
    if (masteryChanges[keys[i]].new === "mastered") {
      return { type: "mastered", skill: keys[i], old: masteryChanges[keys[i]].old, new: "mastered" };
    }
  }
  return { type: "level_up", skill: keys[0], old: masteryChanges[keys[0]].old, new: masteryChanges[keys[0]].new };
}

// Node.js export (for tests); AMD loader ignores this.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { _scorePct: _scorePct, _tierLabel: _tierLabel, _masteryColor: _masteryColor, _segmentColor: _segmentColor, _primaryCta: _primaryCta, _bannerState: _bannerState };
}
