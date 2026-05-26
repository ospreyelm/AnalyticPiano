/*
 * Run: node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
 */
"use strict";

var assert = require("assert");
var Logic = require("./vexflow_adapter_logic");

function fakeTickable(opts) {
  opts = opts || {};
  var tickable = {
    _isRest: !!opts.isRest,
    duration: opts.duration,
    getKeys: function () {
      return opts.keys || [];
    },
  };
  if (opts.hasIsRestMethod) {
    tickable.isRest = function () {
      return !!opts.isRestMethodValue;
    };
  }
  return tickable;
}

function testRestPlacementKeysDoNotBecomeScaleDegrees() {
  var rest = fakeTickable({ isRest: true, duration: "q", keys: ["d/5"] });
  assert.strictEqual(Logic.tickableToScaleDegreeMidi(rest), null);
}

function testNotesStillBecomeScaleDegreeMidi() {
  var note = fakeTickable({ duration: "q", keys: ["c/4"] });
  assert.deepStrictEqual(Logic.tickableToScaleDegreeMidi(note), [60]);
}

function testVexFlowIsRestMethodFalseDoesNotFilterNotes() {
  var note = fakeTickable({
    duration: "q",
    keys: ["e/4"],
    hasIsRestMethod: true,
    isRestMethodValue: false,
  });
  assert.deepStrictEqual(Logic.tickableToScaleDegreeMidi(note), [64]);
}

testRestPlacementKeysDoNotBecomeScaleDegrees();
testNotesStillBecomeScaleDegreeMidi();
testVexFlowIsRestMethodFalseDoesNotFilterNotes();

function testGetBassLabelAtOffsetReturnsLabel() {
  var slices = [
    { offset: 0.0, content: { functional_label: "①" } },
    { offset: 2.0, content: { functional_label: "⑤" } },
    { offset: 4.0, content: { functional_label: "①" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 2.0), "⑤");
}

function testGetBassLabelAtOffsetToleratesSmallDrift() {
  var slices = [
    { offset: 2.0, content: { functional_label: "⑤" } },
  ];
  // 0.04 is within the 0.05 tolerance
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 2.04), "⑤");
}

function testGetBassLabelAtOffsetReturnsNullForEmptyLabel() {
  var slices = [
    { offset: 1.0, content: { functional_label: "" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 1.0), null);
}

function testGetBassLabelAtOffsetReturnsNullForNoMatch() {
  var slices = [
    { offset: 0.0, content: { functional_label: "①" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 9.0), null);
}

testGetBassLabelAtOffsetReturnsLabel();
testGetBassLabelAtOffsetToleratesSmallDrift();
testGetBassLabelAtOffsetReturnsNullForEmptyLabel();
testGetBassLabelAtOffsetReturnsNullForNoMatch();

console.log("vexflow_adapter_logic tests passed");
