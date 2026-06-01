/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.IdentificationLabelLayoutLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function getKeyLabelPosition(opts) {
    opts = opts || {};
    var slotX = typeof opts.slotX === "number" ? opts.slotX : 0;
    var slotY = typeof opts.slotY === "number" ? opts.slotY : 0;
    var textWidth = Math.max(0, typeof opts.textWidth === "number" ? opts.textWidth : 0);
    var canvasWidth = typeof opts.canvasWidth === "number" ? opts.canvasWidth : null;
    var canvasHeight = typeof opts.canvasHeight === "number" ? opts.canvasHeight : null;
    var gap = Math.max(100, textWidth / 2 + 70);
    var minX = textWidth / 2 + 8;
    var x = slotX - gap;

    if (x < minX) x = minX;
    if (canvasWidth !== null) {
      var maxX = canvasWidth - textWidth / 2 - 8;
      if (x > maxX) x = maxX;
    }

    var y = slotY + 28;
    if (canvasHeight !== null) {
      y = Math.min(y, canvasHeight - 10);
    }

    return { x: Math.round(x), y: Math.round(y) };
  }

  return {
    getKeyLabelPosition: getKeyLabelPosition,
  };
});
