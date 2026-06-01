/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseDefinitionLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function findAnalysisWindowByOffset(windows, sliceOffset, fallbackIndex) {
    if (!windows || !windows.length || typeof sliceOffset !== "number") {
      return null;
    }

    var targetTicks = sliceOffset * 1024;
    for (var i = 0; i < windows.length; i++) {
      var win = windows[i];
      if (!win || typeof win.onset !== "number") {
        continue;
      }
      if (Math.abs(win.onset - targetTicks) < 2) {
        return {
          index: i,
          window: win,
          hasSlot: true,
        };
      }
    }

    if (typeof fallbackIndex === "number" && windows[fallbackIndex]) {
      return {
        index: fallbackIndex,
        window: windows[fallbackIndex],
        hasSlot: true,
      };
    }

    return null;
  }

  return {
    findAnalysisWindowByOffset: findAnalysisWindowByOffset,
  };
});
