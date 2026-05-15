(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.KeySigExerciseLogic = factory();
  }
})(this, function () {
  "use strict";

  function normalizeKeyAnswer(raw) {
    var s = (raw || "").trim();
    if (!s) return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function checkKeyAnswer(raw, problem) {
    var norm = normalizeKeyAnswer(raw);
    var normLower = norm.toLowerCase();
    return (problem.accepted_answers || []).some(function (a) {
      return a === norm || a.toLowerCase() === normLower;
    });
  }

  return { normalizeKeyAnswer: normalizeKeyAnswer, checkKeyAnswer: checkKeyAnswer };
});
