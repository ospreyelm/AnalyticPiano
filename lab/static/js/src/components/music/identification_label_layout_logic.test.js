"use strict";

var assert = require("assert");
var Logic = require("./identification_label_layout_logic");

function testPlacesKeyLabelLeftOfFirstSlot() {
  var position = Logic.getKeyLabelPosition({
    slotX: 448,
    slotY: 740,
    textWidth: 72,
    canvasWidth: 2048,
    canvasHeight: 820,
  });

  assert.strictEqual(position.x, 342);
  assert.strictEqual(position.y, 768);
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

testPlacesKeyLabelLeftOfFirstSlot();
testClampsKeyLabelInsideCanvas();

console.log("identification_label_layout_logic tests passed");
