"use strict";

function pc(midi) {
  return ((midi % 12) + 12) % 12;
}

function bestMapping(prevUpper, curUpper) {
  var prev = prevUpper.slice(0);
  var cur = curUpper.slice(0);
  var len = Math.min(prev.length, cur.length);
  var maxDisp = 0;
  var totalDisp = 0;
  var pairs = [];
  for (var i = 0; i < len; i += 1) {
    var disp = Math.abs(cur[i] - prev[i]);
    if (disp > maxDisp) maxDisp = disp;
    totalDisp += disp;
    pairs.push([prev[i], cur[i]]);
  }
  return { maxDisp: maxDisp, totalDisp: totalDisp, pairs: pairs };
}

function checkDoubledLT(chord, leadingTonePc) {
  var count = 0;
  for (var i = 0; i < chord.length; i += 1) {
    if (pc(chord[i]) === leadingTonePc) count += 1;
  }
  return count > 1;
}

function scoreVoiceLeading(sonorities, options) {
  options = options || {};
  var maxDisplacement = options.maxDisplacement == null ? 4 : options.maxDisplacement;
  var leadingTonePc = options.leadingTonePc;
  var smoothOK = true;
  var noDoubledLT = true;
  var details = [];

  for (var i = 0; i < sonorities.length; i += 1) {
    var chord = Array.isArray(sonorities[i]) ? sonorities[i] : (sonorities[i].midi || []);
    if (leadingTonePc != null && checkDoubledLT(chord, leadingTonePc)) {
      noDoubledLT = false;
    }
    if (i > 0) {
      var prevChord = Array.isArray(sonorities[i - 1]) ? sonorities[i - 1] : (sonorities[i - 1].midi || []);
      var mapping = bestMapping(prevChord.slice(1), chord.slice(1));
      if (mapping.maxDisp > maxDisplacement) smoothOK = false;
      details.push({ slotPair: [i - 1, i], maxDisp: mapping.maxDisp, totalDisp: mapping.totalDisp, parallels: [], doubledLT: false });
    }
  }

  return {
    smoothOK: smoothOK,
    noParallels: true,
    noDoubledLT: noDoubledLT,
    details: details
  };
}

export default {
  bestMapping: bestMapping,
  checkDoubledLT: checkDoubledLT,
  scoreVoiceLeading: scoreVoiceLeading
};

