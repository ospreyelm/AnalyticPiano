"use strict";

var assert = require("assert");
var Logic = require("./exercise_definition_logic");
Logic = Logic.default || Logic;

function testFindsWindowByMusicalOffsetNotArrayIndex() {
  var windows = [
    { onset: 0, measureIndex: 0 },
    { onset: 1024, measureIndex: 0 },
    { onset: 2048, measureIndex: 0 },
    { onset: 3072, measureIndex: 0 },
    { onset: 4096, measureIndex: 1 },
  ];

  var match = Logic.findAnalysisWindowByOffset(windows, 4, 3);

  assert.strictEqual(match.index, 4);
  assert.strictEqual(match.window.measureIndex, 1);
  assert.strictEqual(match.window.onset, 4096);
}

function testFallsBackToIndexWhenNoOffsetMatchExists() {
  var windows = [
    { onset: 0, measureIndex: 0 },
    { onset: 1024, measureIndex: 0 },
  ];

  var match = Logic.findAnalysisWindowByOffset(windows, 9, 1);

  assert.strictEqual(match.index, 1);
  assert.strictEqual(match.window.onset, 1024);
}

testFindsWindowByMusicalOffsetNotArrayIndex();
testFallsBackToIndexWhenNoOffsetMatchExists();

console.log("exercise_definition_logic tests passed");
