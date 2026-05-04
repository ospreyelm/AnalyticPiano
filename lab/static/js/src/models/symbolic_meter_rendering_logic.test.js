"use strict";

var logic = require("./symbolic_meter_rendering_logic");

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    console.log("FAIL:", label, actual, expected);
    process.exit(1);
  }
  console.log("PASS:", label);
}

assertEqual(
  "stacked time signature markup keeps numerator and denominator separate",
  logic.renderTimeSignatureMarkup("12/16"),
  '<span class="meter-ts"><span class="meter-ts-top">12</span><span class="meter-ts-bottom">16</span></span>'
);

assertEqual(
  "music font stack begins with SMuFL-capable family",
  logic.getTimeSignatureFontStack().split(",")[0],
  '"Bravura Text"'
);

assertEqual(
  "non time-signature labels pass through unchanged",
  logic.renderTimeSignatureMarkup("compound triple"),
  "compound triple"
);
