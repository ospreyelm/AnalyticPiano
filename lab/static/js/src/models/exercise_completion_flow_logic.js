"use strict";

function _shouldDeferCompletionAutomation(scoreCard) {
  if (!scoreCard) return false;
  if (typeof scoreCard.isVisible === "function") {
    return !!scoreCard.isVisible();
  }
  return scoreCard.visible === true;
}

var exportsObj = {
  _shouldDeferCompletionAutomation: _shouldDeferCompletionAutomation,
};

if (typeof define === "function" && define.amd) {
  define(function () {
    return exportsObj;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = exportsObj;
}