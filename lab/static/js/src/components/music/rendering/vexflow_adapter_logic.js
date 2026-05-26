/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.VexflowAdapterLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function isRestTickable(tickable) {
    if (!tickable) return false;
    var methodValue = false;
    if (typeof tickable.isRest === "function") {
      methodValue = !!tickable.isRest();
    } else {
      methodValue = !!tickable.isRest;
    }
    return !!(
      tickable._isRest ||
      methodValue ||
      String(tickable.duration || "").indexOf("r") !== -1
    );
  }

  function keyToMidi(keyStr) {
    var parts = String(keyStr || "").split("/");
    if (parts.length !== 2) return null;
    var name = parts[0];
    var octave = parseInt(parts[1], 10);
    var step = name.charAt(0).toLowerCase();
    var acc = name.slice(1);
    var base = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[step];
    if (typeof base !== "number" || isNaN(octave)) return null;
    var delta = 0;
    if (acc === "#") delta = 1;
    else if (acc === "##") delta = 2;
    else if (acc === "b") delta = -1;
    else if (acc === "bb") delta = -2;
    else if (acc === "n") delta = 0;
    return 12 * (octave + 1) + base + delta;
  }

  function tickableToScaleDegreeMidi(tickable) {
    if (isRestTickable(tickable)) return null;
    var keys = tickable && typeof tickable.getKeys === "function" ? tickable.getKeys() : [];
    var midi = [];
    keys.forEach(function (key) {
      var value = keyToMidi(key);
      if (value !== null) midi.push(value);
    });
    return midi;
  }

  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
  };
});
