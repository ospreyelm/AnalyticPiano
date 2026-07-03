/*
 * Run: node lab/static/js/src/components/music/rendering/vexflow_annotation_renderer.test.js
 */
"use strict";

var assert = require("assert");
var Renderer = require("./vexflow_annotation_renderer");
Renderer = Renderer.default || Renderer;

function fakeCtx() {
  var calls = { fillText: [], save: 0, restore: 0 };
  return {
    calls: calls,
    fillStyle: null,
    font: null,
    textAlign: null,
    save: function () { calls.save++; },
    restore: function () { calls.restore++; },
    measureText: function (text) {
      return { width: String(text || "").length * 8 };
    },
    fillText: function (text, x, y) {
      calls.fillText.push({ text: text, x: x, y: y });
    },
  };
}

function fakeStave(bottomY) {
  return {
    getBottomY: function () { return bottomY; },
  };
}

function testDrawBassScaleDegreeBelowDrawsAtBottomYPlus22() {
  var ctx = fakeCtx();
  Renderer.drawBassScaleDegreeBelow(ctx, fakeStave(100), "①", 50);
  assert.strictEqual(ctx.calls.fillText.length, 1);
  assert.strictEqual(ctx.calls.fillText[0].text, "①");
  assert.strictEqual(ctx.calls.fillText[0].x, 50);
  assert.strictEqual(ctx.calls.fillText[0].y, 122);
}

function testDrawBassScaleDegreeBelowNoOpWithoutLabel() {
  var ctx = fakeCtx();
  Renderer.drawBassScaleDegreeBelow(ctx, fakeStave(100), null, 50);
  assert.strictEqual(ctx.calls.fillText.length, 0);
}

function testDrawBassScaleDegreeBelowNoOpWithoutStave() {
  var ctx = fakeCtx();
  Renderer.drawBassScaleDegreeBelow(ctx, null, "①", 50);
  assert.strictEqual(ctx.calls.fillText.length, 0);
}

testDrawBassScaleDegreeBelowDrawsAtBottomYPlus22();
testDrawBassScaleDegreeBelowNoOpWithoutLabel();
testDrawBassScaleDegreeBelowNoOpWithoutStave();

function testDrawInlineRomanNoOpWithoutLabel() {
  var ctx = fakeCtx();
  Renderer.drawInlineRoman(ctx, "", 50, fakeStave(100), {});
  assert.strictEqual(ctx.calls.fillText.length, 0);
  assert.strictEqual(ctx.calls.save, 0);
}

function testDrawInlineRomanDrawsPlainLabel() {
  var ctx = fakeCtx();
  Renderer.drawInlineRoman(ctx, "V7", 50, fakeStave(100), { yShift: 30 });
  assert.strictEqual(ctx.calls.save, 1);
  assert.strictEqual(ctx.calls.restore, 1);
  assert.ok(ctx.calls.fillText.length >= 1);
  assert.strictEqual(ctx.calls.fillText[0].text, "V7");
}

testDrawInlineRomanNoOpWithoutLabel();
testDrawInlineRomanDrawsPlainLabel();

function testAttachInlineRomanAnnotationNoOpWithoutAnalyzer() {
  var ctx = fakeCtx();
  Renderer.attachInlineRomanAnnotation({ notes: [] }, [60], {}, null, ctx, fakeStave(100), {});
  assert.strictEqual(ctx.calls.fillText.length, 0);
}

function testAttachInlineRomanAnnotationUsesLabelOverride() {
  var ctx = fakeCtx();
  var col = { centerX: 40, notes: [] };
  var fakeAnalyzer = {}; // unused since labelOverride is provided
  Renderer.attachInlineRomanAnnotation(col, [60], {}, fakeAnalyzer, ctx, fakeStave(100), { yShift: 28 }, "V");
  assert.strictEqual(ctx.calls.fillText.length, 1);
  assert.strictEqual(ctx.calls.fillText[0].text, "V");
}

testAttachInlineRomanAnnotationNoOpWithoutAnalyzer();
testAttachInlineRomanAnnotationUsesLabelOverride();

function testAttachNoteNameAnnotationNoOpWhenAllNotesAreRests() {
  var ctx = fakeCtx();
  var col = { centerX: 40, notes: [{ _isRest: true }] };
  Renderer.attachNoteNameAnnotation(col, [60], {}, {}, ctx, fakeStave(100), {}, "C");
  assert.strictEqual(ctx.calls.fillText.length, 0);
}

function testAttachNoteNameAnnotationDrawsLabelOverride() {
  var ctx = fakeCtx();
  var col = { centerX: 40, notes: [{ _isRest: false }] };
  Renderer.attachNoteNameAnnotation(col, [60], {}, {}, ctx, fakeStave(100), { yShift: 28 }, "C4");
  assert.strictEqual(ctx.calls.fillText.length, 1);
  assert.strictEqual(ctx.calls.fillText[0].text, "C4");
}

testAttachNoteNameAnnotationNoOpWhenAllNotesAreRests();
testAttachNoteNameAnnotationDrawsLabelOverride();

function testDrawScaleDegreeAboveSingleVoiceStacksAboveStave() {
  var ctx = fakeCtx();
  var trebleStave = {
    getYForLine: function (line) { return line === 0 ? 50 : 60; },
    getY: function () { return 50; },
  };
  var analyzer = { to_scale_degree: function () { return "1"; } };
  Renderer.drawScaleDegreeAbove(ctx, [60], 40, trebleStave, analyzer, null, null, null);
  assert.ok(ctx.calls.fillText.length >= 1);
}

function testDrawScaleDegreeAboveNoOpWithoutMidiNotes() {
  var ctx = fakeCtx();
  var trebleStave = { getYForLine: function () { return 50; }, getY: function () { return 50; } };
  Renderer.drawScaleDegreeAbove(ctx, [], 40, trebleStave, {}, null, null, null);
  assert.strictEqual(ctx.calls.fillText.length, 0);
}

testDrawScaleDegreeAboveSingleVoiceStacksAboveStave();
testDrawScaleDegreeAboveNoOpWithoutMidiNotes();

console.log("vexflow_annotation_renderer tests passed");
