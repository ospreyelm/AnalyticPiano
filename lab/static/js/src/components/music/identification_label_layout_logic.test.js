"use strict";

var assert = require("assert");
var Logic = require("./identification_label_layout_logic");
Logic = Logic.default || Logic;

function testPlacesKeyLabelOnBeatSlot() {
  var position = Logic.getKeyLabelPosition({
    slotX: 448,
    slotY: 740,
    textWidth: 72,
    canvasWidth: 2048,
    canvasHeight: 820,
  });

  assert.strictEqual(position.x, 448);
  assert.strictEqual(position.y, 774);
}

function testKeepsInitialKeyLabelLeftOfFirstSlot() {
  var position = Logic.getKeyLabelPosition({
    slotX: 448,
    slotY: 740,
    textWidth: 72,
    canvasWidth: 2048,
    canvasHeight: 820,
    initial: true,
  });

  assert.strictEqual(position.x, 222);
  assert.strictEqual(position.y, 774);
}

function testClampsKeyLabelInsideCanvas() {
  var position = Logic.getKeyLabelPosition({
    slotX: 42,
    slotY: 740,
    textWidth: 72,
    canvasWidth: 2048,
    canvasHeight: 760,
  });

  assert.strictEqual(position.x, 44);
  assert.strictEqual(position.y, 750);
}

testPlacesKeyLabelOnBeatSlot();
testKeepsInitialKeyLabelLeftOfFirstSlot();
testClampsKeyLabelInsideCanvas();

console.log("identification_label_layout_logic tests passed");
