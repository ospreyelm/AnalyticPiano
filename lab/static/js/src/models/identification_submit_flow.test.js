/**
 * Tests for identification submit-flow decisions.
 * Run: node identification_submit_flow.test.js
 */

"use strict";

var logic = require("./identification_submit_flow_logic");
logic = logic.default || logic;

var pass = 0;
var fail = 0;

function assertEqual(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) {
    console.log("  PASS: " + label);
    pass++;
  } else {
    console.log("  FAIL: " + label);
    console.log("       got: " + JSON.stringify(actual) + ", expected: " + JSON.stringify(expected));
    fail++;
  }
}

console.log("\nidentification submit flow:");

assertEqual(
  "UI submit on a non-final page saves before advancing",
  logic._planIdentificationSubmit({
    fromUI: true,
    isLastPage: false,
    result: "correct",
    correctState: "correct",
    sealed: false,
  }),
  { saveAttempt: true, advancePage: true, completeExercise: false }
);

assertEqual(
  "incorrect submit is still saved as an attempt",
  logic._planIdentificationSubmit({
    fromUI: true,
    isLastPage: true,
    result: "incorrect",
    correctState: "correct",
    sealed: false,
  }),
  { saveAttempt: true, advancePage: false, completeExercise: false }
);

assertEqual(
  "sealed exercises do not save duplicate attempts",
  logic._planIdentificationSubmit({
    fromUI: true,
    isLastPage: true,
    result: "correct",
    correctState: "correct",
    sealed: true,
  }),
  { saveAttempt: false, advancePage: false, completeExercise: true }
);

assertEqual(
  "answer changes autosave once an answer exists",
  logic._shouldAutosaveIdentificationChange({ hasAnswer: true }),
  true
);

assertEqual(
  "review restore uses student answers for draft autosaves",
  logic._selectIdentificationRestoreAnswers({
    reviewMode: true,
    data: {
      answers: { "0": "E", "1": "A" },
      correct_answers: { "0": "E", "1": "A", "2": "A" },
      is_page_submit: false,
    },
  }),
  { "0": "E", "1": "A" }
);

assertEqual(
  "review restore uses submitted student answers for submitted attempts",
  logic._selectIdentificationRestoreAnswers({
    reviewMode: true,
    data: {
      answers: { "0": "E", "1": "wrong" },
      correct_answers: { "0": "E", "1": "A" },
      is_page_submit: true,
    },
  }),
  { "0": "E", "1": "wrong" }
);

assertEqual(
  "review mode hides unanswered placeholders",
  logic._shouldRenderIdentificationPlaceholder({ reviewMode: true, hasAnswer: false }),
  false
);

assertEqual(
  "normal mode shows unanswered placeholders",
  logic._shouldRenderIdentificationPlaceholder({ reviewMode: false, hasAnswer: false }),
  true
);

assertEqual(
  "review mode can display correct answer text for completed restored slots",
  logic._getIdentificationDisplayLabel({
    answer: null,
    fallbackAnswer: "C#",
    reviewMode: true,
    showCheck: true,
  }),
  "C#"
);

assertEqual(
  "normal mode still displays placeholders for unanswered slots",
  logic._getIdentificationDisplayLabel({
    answer: null,
    fallbackAnswer: "C#",
    reviewMode: false,
    showCheck: false,
  }),
  "?"
);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
