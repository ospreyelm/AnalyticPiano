/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("lodash"),
      require("app/models/key_signature"),
      require("app/components/music/chordal_spelling"),
      require("app/components/music/chordal_umto_staff_distribution"),
      require("app/utils/chordal_barlines_logic"),
      require("app/utils/measure_engine")
    );
  } else if (typeof define === "function" && define.amd) {
    define([
      "lodash",
      "app/models/key_signature",
      "app/components/music/chordal_spelling",
      "app/components/music/chordal_umto_staff_distribution",
      "app/utils/chordal_barlines_logic",
      "app/utils/measure_engine"
    ], factory);
  } else {
    root.UMTOScoreConverter = factory(
      root._,
      root.KeySignature,
      root.ChordalSpelling,
      root.ChordalUMTOStaffDistribution,
      root.ChordalBarlinesLogic,
      root.MeasureEngine
    );
  }
})(typeof self !== "undefined" ? self : this, function (
  _,
  KeySignature,
  ChordalSpelling,
  ChordalUMTOStaffDistribution,
  ChordalBarlinesLogic,
  MeasureEngine
) {
  "use strict";

  function convertChordalUMTOToProcessedScore(umto) {
    var meta = _.cloneDeep(umto.metadata || {});
    if (meta.meter && !meta.time) meta.time = meta.meter;
    var hasMeter = !!meta.time;

    var dist = meta.staffDistribution || "keyboard";
    var spellingTable = null;
    if (meta.key) {
      try {
        spellingTable = new KeySignature(meta.key).keyToSpelling(meta.key);
      } catch (e) {
        console.warn("[exercise_sheet] Bad or missing key in chordal UMTO:", meta.key, "- falling back to default (sharp) spelling");
      }
    }
    var midiToPitch = function (m) {
      return ChordalSpelling.keyAwarePitch(m, spellingTable);
    };
    var DUR_PARTS = {
      4: { type: "w", dots: 0 }, 3: { type: "h", dots: 1 }, 2: { type: "h", dots: 0 },
      1.5: { type: "q", dots: 1 }, 1: { type: "q", dots: 0 }, 0.75: { type: "8", dots: 1 },
      0.5: { type: "8", dots: 0 }, 0.25: { type: "16", dots: 0 }, 0.125: { type: "32", dots: 0 }
    };
    var durParts = function (ql) { return DUR_PARTS[Number(ql)] || { type: "q", dots: 0 }; };

    var forceTreble = dist === "RH" || dist === "treble";
    var forceBass = dist === "LH" || dist === "bass";

    var trebleItems = [];
    var bassItems = [];
    _.each(umto.chords, function (c) {
      var midis = (c.visible || []).slice();
      var resolved = ChordalSpelling.resolveChordPitches(c, spellingTable);
      var dp = durParts(Number(c.duration));
      var dur = { type: dp.type, dots: dp.dots };
      var hi, lo;
      var routed = ChordalUMTOStaffDistribution.routeChordMidis(midis, dist);
      hi = routed.treble;
      lo = routed.bass;
      var mkItem = function (ms) {
        var pitches = ms.map(function (m) { return resolved[m] || midiToPitch(m); });
        if (pitches.length > 1) {
          return { kind: "chord", notes: pitches.map(function (p) { return { pitch: p }; }), duration: dur };
        }
        if (pitches.length === 1) {
          return { kind: "note", pitch: pitches[0], duration: dur };
        }
        return { kind: "rest", duration: dur };
      };
      trebleItems.push(mkItem(hi));
      bassItems.push(mkItem(lo));
    });

    var barlineOffsets = (umto.metadata && umto.metadata.barline_offsets) || [];
    var chordOffsets = (umto.chords || []).map(function (c) { return Number(c.offset); });
    var trebleMeasures, bassMeasures;
    if (barlineOffsets.length || !hasMeter) {
      var counts = ChordalBarlinesLogic.measureItemCounts(chordOffsets, barlineOffsets);
      var sliceByCounts = function (items) {
        var out = []; var idx = 0;
        for (var k = 0; k < counts.length; k++) { out.push(items.slice(idx, idx + counts[k])); idx += counts[k]; }
        if (!out.length) out.push(items.slice());
        return out;
      };
      trebleMeasures = sliceByCounts(trebleItems);
      bassMeasures = sliceByCounts(bassItems);
    } else {
      trebleMeasures = MeasureEngine.splitIntoMeasures(trebleItems, meta.time);
      bassMeasures = MeasureEngine.splitIntoMeasures(bassItems, meta.time);
    }
    var numMeasures = Math.max(trebleMeasures.length, bassMeasures.length);

    var measures = [];
    for (var i = 0; i < numMeasures; i++) {
      var staves = {};
      if (!forceBass) {
        staves.treble = { voices: [{ items: trebleMeasures[i] || [], direction: "auto" }] };
      }
      if (!forceTreble) {
        staves.bass = { voices: [{ items: bassMeasures[i] || [], direction: "auto" }] };
      }
      measures.push({ staves: staves });
    }

    return {
      meta: { key: meta.key, time: hasMeter ? meta.time : null, clef: meta.clef,
              staffDistribution: dist, noTimeSignature: !hasMeter },
      metadata: { time: hasMeter ? meta.time : null, meter: hasMeter ? meta.time : null },
      measures: measures,
      umto: umto,
    };
  }

  function convertUMTOToProcessedScore(umto) {
    if (umto && umto.metadata && umto.metadata.score_kind === "chordal" &&
        umto.chords && umto.chords.length) {
      return convertChordalUMTOToProcessedScore(umto);
    }
    if (!umto || !umto.voices) {
      console.error("[ID] UMTO or voices missing", umto);
      return null;
    }

    var meta = _.cloneDeep(umto.metadata || {});
    if (meta.meter && !meta.time) meta.time = meta.meter;
    if (!meta.time) meta.time = "4/4";

    var voiceKeys = ['S', 'A', 'T', 'B'];
    var splitVoices = {};
    var maxMeasures = 0;
    
    _.each(voiceKeys, function(vk) {
      var voiceItems = umto.voices[vk] || [];
      var processedItems = _.map(voiceItems, function(ev) {
        var item = _.cloneDeep(ev);
        item.kind = ev.kind || 'note';
        item.duration = {
          type: ev.duration_type || 'q',
          dots: ev.dots || 0
        };
        if (ev.pitch) {
          item.pitch = _.cloneDeep(ev.pitch);
        }
        return item;
      });
      
      splitVoices[vk] = MeasureEngine.splitIntoMeasures(processedItems, meta.time);
      maxMeasures = Math.max(maxMeasures, splitVoices[vk].length);
    });
    
    var measures = [];
    for (var mIdx = 0; mIdx < maxMeasures; mIdx++) {
      var m = { staves: { treble: { voices: [] }, bass: { voices: [] } } };
      
      _.each(voiceKeys, function(vk) {
        var items = (splitVoices[vk][mIdx]) || [];
        if (items.length === 0) return;
        
        var staffName = (vk === 'S' || vk === 'A') ? 'treble' : 'bass';
        if (meta.staffDistribution === 'bass') staffName = 'bass';
        else if (meta.staffDistribution === 'treble') staffName = 'treble';
        
        if (!m.staves[staffName]) m.staves[staffName] = { voices: [] };
        
        var dir = 'auto';
        if (staffName === 'treble') {
          dir = (vk === 'S' && umto.voices.A && umto.voices.A.length > 0) ? 'up' : 'auto';
          if (vk === 'A') dir = 'down';
        } else {
          dir = (vk === 'T' && umto.voices.B && umto.voices.B.length > 0) ? 'up' : 'auto';
          if (vk === 'B') dir = 'down';
        }
        
        m.staves[staffName].voices.push({ items: items, direction: dir });
      });
      
      if (m.staves.treble && m.staves.treble.voices.length === 0) delete m.staves.treble;
      if (m.staves.bass && m.staves.bass.voices.length === 0) delete m.staves.bass;
      
      measures.push(m);
    }
    
    var processed = {
      meta: meta,
      measures: measures,
      umto: umto
    };
    return processed;
  }

  return {
    convertChordalUMTOToProcessedScore: convertChordalUMTOToProcessedScore,
    convertUMTOToProcessedScore: convertUMTOToProcessedScore
  };
});
