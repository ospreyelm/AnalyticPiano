/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("app/utils/measure_engine"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/utils/measure_engine"], factory);
  } else {
    root.BarlineSpacingUtils = factory(root.MeasureEngine);
  }
})(typeof self !== "undefined" ? self : this, function (MeasureEngine) {
  "use strict";

  function timeSignatureParsed(timeSignature) {
    if (!timeSignature) {
      return false;
    }
    var parsedSignature = timeSignature.split("/");
    if (parsedSignature.length !== 2) {
      return false;
    }
    var topNum = parsedSignature[0].trim();
    var bottomNum = parsedSignature[1].trim();
    if (
      isNaN(topNum) ||
      isNaN(bottomNum) ||
      topNum != parseInt(topNum, 10) ||
      bottomNum != parseInt(bottomNum, 10)
    ) {
      return false;
    }
    return [parseInt(topNum, 10), parseInt(bottomNum, 10)];
  }

  function getsBarline(timeSignature, elapsedWholeNotes) {
    if (!timeSignature || elapsedWholeNotes <= 0) {
      return false;
    }
    var ts = timeSignatureParsed(timeSignature);
    if (!ts) {
      return false;
    }
    var barCount = (elapsedWholeNotes * ts[1]) / ts[0];
    return Math.abs(barCount - Math.round(barCount)) < 1e-5;
  }

  function countElapsedBars(timeSignature, elapsedWholeNotes) {
    if (!timeSignature) return 0;
    var ts = timeSignatureParsed(timeSignature);
    if (!ts) {
      return 0;
    }
    var barCount = (elapsedWholeNotes * ts[1]) / ts[0];
    return Math.floor(barCount + 1e-5);
  }

  function getBarRemainder(timeSignature, elapsedWholeNotes) {
    if (!timeSignature) return null;
    var ts = timeSignatureParsed(timeSignature);
    if (!ts) {
      return null;
    }
    var barCount = (elapsedWholeNotes * ts[1]) / ts[0];
    if (isNaN(barCount) || barCount < 0) {
      return null;
    }
    return barCount % 1;
  }

  function getWholeNoteRemainder(timeSignature, elapsedWholeNotes) {
    if (!timeSignature) return false;
    var ts = timeSignatureParsed(timeSignature);
    if (!ts) {
      return false;
    }
    if (elapsedWholeNotes <= 0) {
      return 0;
    }
    var remainder = ((elapsedWholeNotes * ts[1]) % ts[0]) / ts[1];
    if (isNaN(remainder) || remainder < 0) {
      return null;
    }
    return remainder;
  }

  function getVisualWidth(rhythm_value) {
    if (rhythm_value === "w") {
      return 1;
    } else if (rhythm_value === "W") {
      return 1.25;
    } else if (rhythm_value === "H") {
      return 0.75;
    } else if (rhythm_value === "h") {
      return 0.675;
    } else if (rhythm_value === "Q") {
      return 0.5;
    } else if (rhythm_value === "q") {
      return 0.375;
    } else if (rhythm_value === "8") {
      return 0.25;
    } else {
      console.log("Unknown rhythm_value passed to getVisualWidth");
      return 1;
    }
  }

  function getWholeNoteCount(rhythm_value) {
    if (!rhythm_value) return 0.25;
    if (typeof rhythm_value === 'string') {
      return MeasureEngine.getWholeNoteCount(rhythm_value, 0);
    }
    return 0.25;
  }

  return {
    timeSignatureParsed: timeSignatureParsed,
    getsBarline: getsBarline,
    countElapsedBars: countElapsedBars,
    getBarRemainder: getBarRemainder,
    getWholeNoteRemainder: getWholeNoteRemainder,
    getVisualWidth: getVisualWidth,
    getWholeNoteCount: getWholeNoteCount,
  };
});
