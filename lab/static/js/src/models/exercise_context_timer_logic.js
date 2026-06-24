/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.ExerciseContextTimerLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var SEMIBREVE_FRACTION = {
    W: 1.5,  w: 1,
    H: 0.75, h: 0.5,
    Q: 0.375, q: 0.25,
    E: 0.1875, e: 0.125,
  };

  function createTimerState() {
    return {
      start: null,
      end: null,
      duration: null,
      durationString: "",
      minTempo: null,
      maxTempo: null,
      tempoSD: null,
      tempoRating: null,
      timepoints: {},
      timeIntervals: [],
    };
  }

  function formatDurationString(durationMs) {
    var seconds = Math.round(durationMs / 1000);
    var minutes = Math.floor(seconds / 60);
    seconds %= 60;
    var s = "";
    if (minutes > 0) {
      s += String(minutes) + "&prime;&nbsp;";
    }
    s += String(seconds) + "&Prime;";
    return s;
  }

  function computeTempoIntervals(timepoints) {
    var indices = Object.keys(timepoints).sort(function (a, b) { return a - b; });
    var intervals = [];
    for (var i = 1; i < indices.length; i++) {
      intervals.push(timepoints[indices[i]] - timepoints[indices[i - 1]]);
    }
    return intervals;
  }

  function computeSemibreveCount(chordSettings, inputChordsLength, defaultRhythmValue) {
    var len = Math.min(inputChordsLength, chordSettings.length);
    var semibreveCount = [];
    for (var i = 0; i < len; i++) {
      var rv = chordSettings[i].settings.rhythm || defaultRhythmValue;
      semibreveCount.push(SEMIBREVE_FRACTION[rv] || defaultRhythmValue || 1);
    }
    if (semibreveCount.length > 0) semibreveCount.pop();
    return semibreveCount;
  }

  function computeCentisemibrevesPerMin(timeIntervals, semibreveCount) {
    if (timeIntervals.length !== semibreveCount.length) return [];
    var result = [];
    for (var i = 0; i < timeIntervals.length; i++) {
      result.push(Math.round((semibreveCount[i] * 6000000) / timeIntervals[i]));
    }
    return result;
  }

  function _mean(arr) {
    if (!arr.length) return 0;
    return arr.reduce(function (s, v) { return s + v; }, 0) / arr.length;
  }

  /* NOTE: original used SimpleStatistics.standardDeviation (population stddev, N divisor).
     This uses sample stddev (Bessel-corrected, N-1 divisor), which is more appropriate
     for small sample sizes and changes computed tempoSD values. */
  function _sampleStddev(arr) {
    if (arr.length < 2) return 0;
    var m = _mean(arr);
    var variance = arr.reduce(function (s, v) {
      return s + Math.pow(v - m, 2);
    }, 0) / (arr.length - 1);
    return Math.sqrt(variance);
  }

  function computeTempoStats(centisemibrevesPerMin) {
    var hasValues = centisemibrevesPerMin.length > 0;
    return {
      tempoSD:   Math.round(_sampleStddev(centisemibrevesPerMin)) / 100,
      tempoMean: Math.round(_mean(centisemibrevesPerMin) / 10) / 10,
      minTempo:  hasValues ? Math.round(Math.min.apply(null, centisemibrevesPerMin)) / 100 : null,
      maxTempo:  hasValues ? Math.round(Math.max.apply(null, centisemibrevesPerMin)) / 100 : null,
    };
  }

  function computeTempoRating(tempoSD, tempoMean) {
    try {
      return Math.max(
        1,
        Math.min(
          5,
          tempoSD == 0
            ? 5
            : Math.floor(tempoMean / tempoSD).toString(2).length - 1
        )
      ) || 0;
    } catch (e) {
      return 0;
    }
  }

  return {
    SEMIBREVE_FRACTION: SEMIBREVE_FRACTION,
    createTimerState: createTimerState,
    formatDurationString: formatDurationString,
    computeTempoIntervals: computeTempoIntervals,
    computeSemibreveCount: computeSemibreveCount,
    computeCentisemibrevesPerMin: computeCentisemibrevesPerMin,
    computeTempoStats: computeTempoStats,
    computeTempoRating: computeTempoRating,
  };
});
