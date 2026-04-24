/* global define: false */
define(["lodash"], function (_) {
  "use strict";

  var TICKS_PER_WHOLE = 4096;

  var DURATION_MAP = {
    "whole": 1.0, "w": 1.0, "1": 1.0,
    "half": 0.5, "h": 0.5, "2": 0.5,
    "quarter": 0.25, "q": 0.25, "4": 0.25,
    "eighth": 0.125, "e": 0.125, "8": 0.125,
    "16th": 0.0625, "s": 0.0625, "16": 0.0625,
    "32nd": 0.03125, "t": 0.03125, "32": 0.03125,
    // Support for legacy uppercase dotted notation
    "W": 1.5, "H": 0.75, "Q": 0.375, "E": 0.1875
  };

  /**
   * MeasureEngine
   */
  var MeasureEngine = {
    /**
     * Converts a duration type and dots into whole-note count.
     */
    getWholeNoteCount: function (type, dots) {
      var base = DURATION_MAP[type] || 0.25;
      var total = base;
      var add = base / 2;
      for (var i = 0; i < (dots || 0); i++) {
        total += add;
        add /= 2;
      }
      return total;
    },

    /**
     * Converts a duration type and dots into VexFlow ticks.
     */
    getTicks: function (type, dots) {
      return Math.round(this.getWholeNoteCount(type, dots) * TICKS_PER_WHOLE);
    },

    /**
     * Parses a time signature string into num_beats and beat_value.
     */
    parseTimeSignature: function (timeSig) {
      if (!timeSig) return { num: 4, den: 4 };
      var parts = String(timeSig).split("/");
      return {
        num: parseInt(parts[0], 10) || 4,
        den: parseInt(parts[1], 10) || 4
      };
    },

    /**
     * Returns the total ticks in a measure for a given time signature.
     */
    getMeasureTicks: function (timeSig) {
      var ts = this.parseTimeSignature(timeSig);
      return ts.num * (TICKS_PER_WHOLE / ts.den);
    },

    /**
     * Splits a flat list of notes into measures.
     * This is the "Engine" the user requested.
     */
    splitIntoMeasures: function (notes, timeSig) {
      var measureTicks = this.getMeasureTicks(timeSig);
      var measures = [];
      var currentMeasure = [];
      var currentTicks = 0;

      for (var i = 0; i < notes.length; i++) {
        var note = notes[i];
        var noteTicks = this.getTicks(note.duration_type || note.duration.type, note.dots || (note.duration && note.duration.dots) || 0);

        // Check if note fits in current measure
        if (currentTicks > 0 && currentTicks + noteTicks > measureTicks) {
          // Close current measure and start new one
          measures.push(currentMeasure);
          currentMeasure = [];
          currentTicks = 0;
        }

        currentMeasure.push(note);
        currentTicks += noteTicks;

        // If measure is exactly full, close it
        if (currentTicks >= measureTicks) {
          measures.push(currentMeasure);
          currentMeasure = [];
          currentTicks = 0;
        }
      }

      // Add final partial measure if any
      if (currentMeasure.length > 0) {
        measures.push(currentMeasure);
      }

      return measures;
    }
  };

  return MeasureEngine;
});
