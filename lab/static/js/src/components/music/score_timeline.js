/* global define: false */

define([], function () {
  "use strict";

  function durToTicks(d) {
    var base = { 'w': 4096, 'h': 2048, 'q': 1024, '8': 512, '16': 256, '32': 128 }[d.type] || 1024;
    var dots = d.dots || 0;
    var tickVal = base;
    var add = base / 2;
    for (var i = 0; i < dots; i++) { tickVal += add; add /= 2; }
    return tickVal;
  }

  function stepToSemitone(step) {
    switch (step.toUpperCase()) {
      case 'C': return 0;
      case 'D': return 2;
      case 'E': return 4;
      case 'F': return 5;
      case 'G': return 7;
      case 'A': return 9;
      case 'B': return 11;
      default: return 0;
    }
  }

  function pitchToMidi(pitch) {
    var base = stepToSemitone(pitch.step);
    var alter = pitch.alter || 0; // -2..2
    var octave = pitch.octave; // MIDI C4 = 60 with octave=4
    var semitone = base + alter;
    return (octave + 1) * 12 + semitone;
  }

  // Build a flat, ordered list of note events from the CIR score
  // Each event: { id, onset, duration, midi, staff, voiceIndex, measureIndex, itemIndex, headIndex }
  // onset is CUMULATIVE across all measures for globally unique matching
  function buildTimeline(score, opts) {
    opts = opts || {};
    var timeline = [];
    var id = 0;
    if (!score || !score.measures || !score.measures.length) return timeline;

    var totalMeasures = score.measures.length;
    var startMeasure = Math.max(0, opts.startMeasure || 0);
    if (startMeasure >= totalMeasures) {
      startMeasure = Math.max(0, totalMeasures - 1);
    }

    var maxMeasures =
      opts.maxMeasures != null ? opts.maxMeasures : totalMeasures;
    // maxMeasures represents how many measures to include starting at startMeasure.
    var endMeasure = Math.min(totalMeasures, startMeasure + maxMeasures);
    var numMeasures = Math.max(0, endMeasure - startMeasure);
    
    var cumulativeOnsetByMeasure = buildMeasureOffsets(score, opts);

    for (var rel = 0; rel < numMeasures; rel++) {
      var m = startMeasure + rel;
      var meas = score.measures[m];
      var measureStartTick = cumulativeOnsetByMeasure[rel];
      ['treble', 'bass'].forEach(function(staffName) {
        var staff = meas.staves[staffName];
        if (!staff || !staff.voices) return;
        var select = (opts.selectVoices && opts.selectVoices[staffName]) || null;
        staff.voices.forEach(function(voice, vIdx) {
          if (select && select.indexOf(vIdx) === -1) return;
          var localOnset = 0; // relative to measure start
          for (var it = 0; it < voice.items.length; it++) {
            var item = voice.items[it];
            if (item.kind === 'rest') {
              localOnset += durToTicks(item.duration);
              continue;
            }
            var globalOnset = measureStartTick + localOnset;
            if (item.kind === 'note') {
              timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.pitch), step: item.pitch.step, alter: item.pitch.alter || 0, staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: 0 });
            } else if (item.kind === 'chord') {
              for (var h = 0; h < item.notes.length; h++) {
                timeline.push({ id: id++, onset: globalOnset, duration: durToTicks(item.duration), midi: pitchToMidi(item.notes[h].pitch), step: item.notes[h].pitch.step, alter: item.notes[h].pitch.alter || 0, staff: staffName, voiceIndex: vIdx, measureIndex: m, itemIndex: it, headIndex: h });
              }
            }
            localOnset += durToTicks(item.duration);
          }
        });
      });
    }
    
    // IMPORTANT: keep timeline in the same insertion order used by the renderer so
    // event.id values correspond to rendered notehead ids. Previously this function
    // performed a final sort by onset which changed ordering but left event.id values
    // as originally assigned; that produced a mismatch between grader ids and
    // renderer-assigned notehead ids and caused incorrect highlights. If callers
    // need onset-ordered windows, they should compute them separately without
    // changing the timeline array itself.
    
    return timeline;
  }

  function buildMeasureOffsets(score, opts) {
    opts = opts || {};
    if (!score || !score.measures || !score.measures.length) return [];

    var totalMeasures = score.measures.length;
    var startMeasure = Math.max(0, opts.startMeasure || 0);
    if (startMeasure >= totalMeasures) {
      startMeasure = Math.max(0, totalMeasures - 1);
    }

    var maxMeasures =
      opts.maxMeasures != null ? opts.maxMeasures : totalMeasures;
    var endMeasure = Math.min(totalMeasures, startMeasure + maxMeasures);
    var numMeasures = Math.max(0, endMeasure - startMeasure);
    var cumulativeOnsetByMeasure = [0];

    for (var rel = 0; rel < numMeasures; rel++) {
      var m = startMeasure + rel;
      var meas = score.measures[m];
      var maxDuration = 0;
      ['treble', 'bass'].forEach(function(staffName) {
        var staff = meas.staves[staffName];
        if (!staff || !staff.voices) return;
        staff.voices.forEach(function(voice) {
          var voiceDur = 0;
          for (var it = 0; it < voice.items.length; it++) {
            voiceDur += durToTicks(voice.items[it].duration);
          }
          maxDuration = Math.max(maxDuration, voiceDur);
        });
      });
      if (rel + 1 < numMeasures) {
        cumulativeOnsetByMeasure.push(
          cumulativeOnsetByMeasure[rel] + maxDuration
        );
      }
    }
    return cumulativeOnsetByMeasure;
  }

  return { buildTimeline: buildTimeline, buildMeasureOffsets: buildMeasureOffsets };
});
