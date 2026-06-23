/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("vexflow"),
      require("../../../utils/measure_engine"),
      require("./vexflow_tickable_builder")
    );
  } else if (typeof define === "function" && define.amd) {
    define(
      [
        "vexflow",
        "app/utils/measure_engine",
        "app/components/music/rendering/vexflow_tickable_builder",
      ],
      factory
    );
  } else {
    root.VexflowStaffVoiceBuilder = factory(
      root.Vex,
      root.MeasureEngine,
      root.VexflowTickableBuilder
    );
  }
})(typeof self !== "undefined" ? self : this, function (Vex, MeasureEngine, VexflowTickableBuilder) {
  "use strict";

  // SATB voice id map: [staffId][voiceIndex] -> voice label
  var SATB_MAP = { treble: ["S", "A"], bass: ["T", "B"] };

  function durationToTicks(dur) {
    return MeasureEngine.getTicks(dur.type, dur.dots || 0);
  }

  function autoBeam(tickables, stemDirection) {
    try {
      return Vex.Flow.Beam.generateBeams(tickables, {
        beam_rests: false,
        stem_direction: stemDirection || 1,
      });
    } catch(e) {
      return [];
    }
  }

  // Builds the staffVoices(...) function for one render() call. `opts` carries
  // the per-render selectVoices/octaveShift filters; the rest are render-wide
  // flags that don't change per measure. `absoluteMeasureIndex` is taken as an
  // explicit call-time argument (undefined for the pre-loop pickup-width
  // pre-calc, set for the real per-measure render pass) rather than read off a
  // shared closure variable, matching the original implicit-undefined behavior.
  function createStaffVoicesFn(params) {
    var opts = params.opts;
    var isHarmonization = !!params.isHarmonization;
    var lockedVoices = params.lockedVoices || [];
    var voiceColors = params.voiceColors || null;
    var time = params.time;
    var showNotation = params.showNotation;
    var isAnalysisMatch = params.isAnalysisMatch;

    return function staffVoices(staffId, staff, clef, idState, keySignatureAlterations, measureStartTick, absoluteMeasureIndex) {
      if (!staff) return [];
      // Optional filtering: opts.selectVoices = { treble: [0], bass: [1] }
      var select = (opts && opts.selectVoices && opts.selectVoices[staffId]) || null;
      // Optional octave shift per staff: opts.octaveShift = { treble: 0, bass: -1 }
      var octaveShift = (opts && opts.octaveShift && (opts.octaveShift[staffId] || 0)) || 0;
      // Note playing state across this render; keep shared across entire piece for consistent IDs
      idState = idState || { nextId: 0, playedNoteIds: (opts && opts.playedNoteIds) || null };
      var measStartTick = measureStartTick || 0;
      var staffSatbLabels = SATB_MAP[staffId] || [];
      // Shared within-measure alteration tracker — reset per measure per staff,
      // shared across all voices so G# in one voice makes G♮ in another show a natural.
      var barAlterations = {};

      // Detect single-real-voice staff: all items across all voices are rests
      // except in exactly one voice.  When true, suppress the all-rest voice(s)
      // and render the remaining voice with natural single-voice stem direction
      // (down for bass, up for treble) instead of forced two-voice stems.
      var voices = staff.voices || [];
      function isAllRests(v) {
        return v.items.every(function(it) { return it.kind === 'rest'; });
      }
      var realVoiceIndices = voices.reduce(function(acc, v, i) {
        if (!isAllRests(v)) acc.push(i);
        return acc;
      }, []);
      var singleVoiceMode = realVoiceIndices.length === 1;

      return voices
        .map(function (v, vIdx) {
          if (select && select.indexOf(vIdx) === -1) return null; // filter out
          // In single-voice mode, skip all-rest padding voices entirely.
          if (singleVoiceMode && isAllRests(v)) return null;

          var satbLabel = staffSatbLabels[vIdx] || null;
          var selectedForHarmonization = !!(isHarmonization && select && select.indexOf(vIdx) !== -1);
          var hideCurrentVoice = isHarmonization && !selectedForHarmonization && satbLabel && lockedVoices.indexOf(satbLabel) === -1;
          var harmonizationOptions = {
            isHarmonization: isHarmonization,
            hideCurrentVoice: hideCurrentVoice,
            voiceSlot: satbLabel,
            voiceColors: voiceColors,
          };

          var localOnset = 0;
          var tickables = v.items.map(function (it) {
            var onsetToUse = measStartTick + localOnset;
            localOnset += durationToTicks(it.duration);
            return VexflowTickableBuilder.itemToTickable(clef, it, octaveShift, idState, keySignatureAlterations, onsetToUse, absoluteMeasureIndex, showNotation, isAnalysisMatch, harmonizationOptions, barAlterations);
          }).filter(Boolean);

          var stemDir;
          if (singleVoiceMode) {
            // Let VexFlow auto-stem per note (standard single-voice engraving).
            stemDir = null;
          } else {
            // In two-voice staff, "auto" follows SATB convention: v0 stems up, v1 stems down.
            stemDir = v.direction === "up" ? 1 : v.direction === "down" ? -1 : (vIdx === 0 ? 1 : -1);
            tickables.forEach(function (t) { if (t.setStemDirection) t.setStemDirection(stemDir); });
          }

          // Only beam outer voices (S=treble idx0 stems-up, B=bass idx1 stems-down).
          // Inner voices (A=treble idx1, T=bass idx0) beam toward the opposing staff — skip.
          var isOuterVoice = singleVoiceMode || (stemDir === 1 && vIdx === 0) || (stemDir === -1 && vIdx === 1);
          var beams = isOuterVoice ? autoBeam(tickables, stemDir) : [];

          var voice = VexflowTickableBuilder.buildVoice(time, tickables);
          voice.beams = beams; // Store beams for later drawing
          return voice;
        })
        .filter(Boolean);
    };
  }

  return {
    durationToTicks: durationToTicks,
    createStaffVoicesFn: createStaffVoicesFn,
  };
});
