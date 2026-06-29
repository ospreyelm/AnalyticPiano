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

export default exportsObj;