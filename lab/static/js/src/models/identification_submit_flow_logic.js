/**
 * Pure identification submit-flow decisions.
 */

"use strict";

function _planIdentificationSubmit(options) {
  var isCorrect = options.result === options.correctState;

  return {
    saveAttempt: !options.sealed,
    advancePage: !options.isLastPage && (options.fromUI || isCorrect),
    completeExercise: isCorrect && options.isLastPage,
  };
}

function _shouldAutosaveIdentificationChange(options) {
  return !!(options && options.hasAnswer);
}

function _selectIdentificationRestoreAnswers(options) {
  if (!options || !options.data) return null;
  return options.data.answers || null;
}

function _shouldRenderIdentificationPlaceholder(options) {
  if (options && options.reviewMode && !options.hasAnswer) {
    return false;
  }
  return true;
}

function _getIdentificationDisplayLabel(options) {
  if (options && options.answer) {
    return options.answer;
  }
  if (options && options.reviewMode && options.showCheck && options.fallbackAnswer) {
    return options.fallbackAnswer;
  }
  return "?";
}

var exportsObj = {
  _planIdentificationSubmit: _planIdentificationSubmit,
  _shouldAutosaveIdentificationChange: _shouldAutosaveIdentificationChange,
  _selectIdentificationRestoreAnswers: _selectIdentificationRestoreAnswers,
  _shouldRenderIdentificationPlaceholder: _shouldRenderIdentificationPlaceholder,
  _getIdentificationDisplayLabel: _getIdentificationDisplayLabel,
};

if (typeof define === "function" && define.amd) {
  define(function () {
    return exportsObj;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = exportsObj;
}
