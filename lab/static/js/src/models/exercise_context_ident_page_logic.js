/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseContextIdentPageLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function getChoralePageMeasureCount(display) {
    var maxMeasures = parseInt(display && display.maxMeasures, 10);
    return maxMeasures > 0 ? maxMeasures : 4;
  }

  function computeTotalIdentPages(allProblems, isChoraleIdent, totalMeasures, maxMeasures, pageSize) {
    if (isChoraleIdent) {
      if (!allProblems || !allProblems.length) return 1;
      return Math.ceil(totalMeasures / maxMeasures);
    }
    return Math.ceil(allProblems.length / pageSize);
  }

  function computeIdentPageOffset(identPage, identPageSize, isChoraleIdent, problems, totalMeasures, maxMeasures) {
    if (isChoraleIdent) {
      var targetMeasure = identPage * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (targetMeasure > lastPossibleStart) targetMeasure = lastPossibleStart;
      for (var i = 0; i < problems.length; i++) {
        if (problems[i].measureIndex >= targetMeasure) return i;
      }
      return problems.length;
    }
    return identPage * identPageSize;
  }

  function filterVisibleProblems(allProblems, isChoraleIdent, identPage, pageSize, totalMeasures, maxMeasures) {
    if (isChoraleIdent) {
      var startMeasure = identPage * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (startMeasure > lastPossibleStart) startMeasure = lastPossibleStart;
      var endMeasure = startMeasure + maxMeasures;
      return allProblems.filter(function (p) {
        return p.measureIndex >= startMeasure && p.measureIndex < endMeasure;
      });
    }
    var offset = identPage * pageSize;
    return allProblems.slice(offset, offset + pageSize);
  }

  return {
    getChoralePageMeasureCount: getChoralePageMeasureCount,
    computeTotalIdentPages: computeTotalIdentPages,
    computeIdentPageOffset: computeIdentPageOffset,
    filterVisibleProblems: filterVisibleProblems,
  };
});
