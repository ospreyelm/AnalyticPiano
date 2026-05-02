"use strict";

function _getDefaultExerciseInputMode() {
  return "qwerty";
}

function _getShortcutDisplayLabel(keyName) {
  var specialLabels = {
    GRAVE: "`",
    BACKSL: "\\",
    BACKSP: "\u232b",
    SPACE: "\u2423",
    ENTER: "\u21b5",
  };

  if (specialLabels.hasOwnProperty(keyName)) {
    return specialLabels[keyName];
  }

  return String(keyName || "").toUpperCase();
}

var exportsObj = {
  _getDefaultExerciseInputMode: _getDefaultExerciseInputMode,
  _getShortcutDisplayLabel: _getShortcutDisplayLabel,
};

if (typeof define === "function" && define.amd) {
  define(function () {
    return exportsObj;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = exportsObj;
}
