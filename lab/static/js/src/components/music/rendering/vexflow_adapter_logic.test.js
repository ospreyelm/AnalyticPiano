/*
 * Run: node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
 */
"use strict";

var assert = require("assert");
var { requireDefault } = require("../../../../test/require_esm");
var Logic = requireDefault(require("./vexflow_adapter_logic"));

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

function testNormalizeKeyForVexFlow() {
  assert.strictEqual(Logic.normalizeKeyForVexFlow("iG_"), "Gm");
  assert.strictEqual(Logic.normalizeKeyForVexFlow("jG_"), "G");
  assert.strictEqual(Logic.normalizeKeyForVexFlow("g"), "Gm");
  assert.strictEqual(Logic.normalizeKeyForVexFlow(""), "C");
}

function testGetKeySignatureAlterations() {
  assert.deepStrictEqual(Logic.getKeySignatureAlterations("jC_"), {});
  assert.deepStrictEqual(Logic.getKeySignatureAlterations("jG_"), { F: 1 });
  assert.deepStrictEqual(Logic.getKeySignatureAlterations("jF_"), { B: -1 });
  assert.deepStrictEqual(Logic.getKeySignatureAlterations("jD_"), { F: 1, C: 1 });
  assert.deepStrictEqual(Logic.getKeySignatureAlterations("iA_"), {});
}

testNormalizeKeyForVexFlow();
testGetKeySignatureAlterations();

function testResolveChordNoteStylesNoNotesPlayedYieldsVoiceColorBaseAndNoPlayedKeys() {
  var playedNoteIds = new Set();
  var result = Logic.resolveChordNoteStyles({
    keyCount: 2,
    baseId: 10,
    playedNoteIds: playedNoteIds,
    showNotation: true,
    isAnalysisMatch: false,
    hideForHarmonization: false,
    voiceColor: "rgb(50,50,50)",
  });
  assert.deepStrictEqual(result.baseStyle, { fillStyle: "rgb(50,50,50)", strokeStyle: "rgb(50,50,50)" });
  assert.deepStrictEqual(result.playedKeyIndices, []);
}

function testResolveChordNoteStylesOnlyLowerNotePlayedDoesNotBlackenWholeChord() {
  // Regression: a chord whose first notehead (id 10, index 0) is played must
  // NOT turn the whole chord black — only index 0 should be reported as
  // played. The base style stays the unplayed voice color so the caller can
  // leave the second notehead (id 11, index 1) unstyled by setKeyStyle.
  var playedNoteIds = new Set([10]);
  var result = Logic.resolveChordNoteStyles({
    keyCount: 2,
    baseId: 10,
    playedNoteIds: playedNoteIds,
    showNotation: true,
    isAnalysisMatch: false,
    hideForHarmonization: false,
    voiceColor: "rgb(50,50,50)",
  });
  assert.deepStrictEqual(result.baseStyle, { fillStyle: "rgb(50,50,50)", strokeStyle: "rgb(50,50,50)" });
  assert.deepStrictEqual(result.playedKeyIndices, [0]);
}

function testResolveChordNoteStylesBothNotesPlayedReportsBothIndices() {
  var playedNoteIds = new Set([10, 11]);
  var result = Logic.resolveChordNoteStyles({
    keyCount: 2,
    baseId: 10,
    playedNoteIds: playedNoteIds,
    showNotation: true,
    isAnalysisMatch: false,
    hideForHarmonization: false,
    voiceColor: "rgb(50,50,50)",
  });
  assert.deepStrictEqual(result.playedKeyIndices, [0, 1]);
}

function testResolveChordNoteStylesHiddenWhenNotationOff() {
  var result = Logic.resolveChordNoteStyles({
    keyCount: 1,
    baseId: 0,
    playedNoteIds: new Set(),
    showNotation: false,
    isAnalysisMatch: false,
    hideForHarmonization: false,
    voiceColor: "rgb(50,50,50)",
  });
  assert.deepStrictEqual(result.baseStyle, { fillStyle: "transparent", strokeStyle: "transparent" });
}

testResolveChordNoteStylesNoNotesPlayedYieldsVoiceColorBaseAndNoPlayedKeys();
testResolveChordNoteStylesOnlyLowerNotePlayedDoesNotBlackenWholeChord();
testResolveChordNoteStylesBothNotesPlayedReportsBothIndices();
testResolveChordNoteStylesHiddenWhenNotationOff();

console.log("vexflow_adapter_logic tests passed");
