

var EPS = 1e-6;
  var PALETTE = [4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25];
  var PALETTE_SET = {}; PALETTE.forEach(function (v) { PALETTE_SET[v] = true; });

  function r6(x) { return Math.round(Number(x) * 1e6) / 1e6; }
  function isPaletteDuration(ql) { return PALETTE_SET[r6(ql)] === true; }

  function meterQuarterLength(meter) {
    if (!meter) return 0;
    var parts = String(meter).split("/");
    var num = parseInt(parts[0], 10) || 4;
    var den = parseInt(parts[1], 10) || 4;
    return num * (4 / den);
  }

  function offsetsFromDurations(durations) {
    var offs = []; var cur = 0;
    for (var i = 0; i < durations.length; i++) { offs.push(r6(cur)); cur = r6(cur + Number(durations[i])); }
    return offs;
  }

  // Auto-suggest barlines at meter boundaries that coincide with a chord onset.
  function suggestBarlines(offsets, durations, meter) {
    if (!meter) return [];
    var barLen = meterQuarterLength(meter);
    var total = offsets.length ? r6(offsets[offsets.length - 1] + Number(durations[durations.length - 1])) : 0;
    var onsetSet = {}; offsets.forEach(function (o) { onsetSet[r6(o)] = true; });
    var out = []; var b = r6(barLen);
    while (b < total - EPS) { if (onsetSet[b]) out.push(b); b = r6(b + barLen); }
    return out;
  }

  // Item count per measure given chord onsets and barline offsets (split contract).
  function measureItemCounts(offsets, barlineOffsets) {
    var splits = (barlineOffsets || []).map(r6).sort(function (a, b) { return a - b; });
    if (!splits.length) return offsets.length ? [offsets.length] : [];
    var counts = []; var si = 0; var count = 0;
    for (var i = 0; i < offsets.length; i++) {
      while (si < splits.length && r6(offsets[i]) >= splits[si] - EPS) {
        counts.push(count); count = 0; si++;
      }
      count++;
    }
    counts.push(count);
    return counts;
  }

  // Mirror of backend validate_chordal_rhythm. Returns {ok:bool, error?:string}.
  // Structural rules (both free and metered): palette, non-overlap, barline-on-onset.
  // Metered adds: every bar must exactly tile with contiguous chords summing to barLen.
  function checkRhythm(offsets, durations, meter, barlineOffsets) {
    var i;

    // --- Palette check (both modes) ---
    for (i = 0; i < durations.length; i++) {
      if (!isPaletteDuration(durations[i])) {
        return { ok: false, error: "Duration " + durations[i] + " is not in the palette." };
      }
    }

    if (!offsets.length) return { ok: true };

    // Sort by offset to mirror Python's sorted(chords, key=lambda c: round(float(c["offset"]), 6)).
    var indices = [];
    for (i = 0; i < offsets.length; i++) indices.push(i);
    indices.sort(function (a, b) { return r6(offsets[a]) - r6(offsets[b]); });

    var sortedOffsets = indices.map(function (idx) { return r6(offsets[idx]); });
    var sortedDurations = indices.map(function (idx) { return Number(durations[idx]); });

    // Build onset set.
    var onsetSet = {};
    sortedOffsets.forEach(function (o) { onsetSet[o] = true; });

    // Non-overlap / monotonic.
    var cursor = null;
    for (i = 0; i < sortedOffsets.length; i++) {
      var off = sortedOffsets[i];
      if (cursor !== null && off < cursor - EPS) {
        return { ok: false, error: "Chord at offset " + off + " overlaps the previous chord (ends at " + cursor + ")." };
      }
      cursor = r6(off + sortedDurations[i]);
    }

    // Barline structural checks: > 0, < total, on a chord onset, no duplicates.
    var total = r6(sortedOffsets[sortedOffsets.length - 1] + sortedDurations[sortedDurations.length - 1]);
    var bars = barlineOffsets || [];
    var seenBarlines = {};
    for (i = 0; i < bars.length; i++) {
      var rb = r6(bars[i]);
      if (rb <= 0.0 + EPS || rb >= total - EPS) {
        return { ok: false, error: "Barline at offset " + bars[i] + " must be > 0 and < the stream end (" + total + ")." };
      }
      if (seenBarlines[rb]) {
        return { ok: false, error: "Duplicate barline at offset " + bars[i] + "." };
      }
      seenBarlines[rb] = true;
      if (onsetSet[rb] !== true) {
        return { ok: false, error: "Barline at offset " + bars[i] + " does not coincide with a chord onset." };
      }
    }

    if (!meter) return { ok: true };  // free/open mode: structural checks done

    // --- Metered exact contiguous tiling ---
    var barLen = meterQuarterLength(meter);
    var sortedBars = bars.map(r6).sort(function (a, b) { return a - b; });
    var bounds = [0.0].concat(sortedBars).concat([total]);

    for (var bi = 0; bi < bounds.length - 1; bi++) {
      var start = bounds[bi], end = bounds[bi + 1];
      var beats = r6(end - start);
      if (Math.abs(beats - barLen) > EPS) {
        return { ok: false, error: "Bar " + (bi + 1) + " spans " + beats + " beats, expected " + barLen + "." };
      }
      // Collect bar chords: start - EPS <= offset < end - EPS
      var barChords = [];
      for (i = 0; i < sortedOffsets.length; i++) {
        var o = sortedOffsets[i];
        if (o >= start - EPS && o < end - EPS) {
          barChords.push({ offset: o, duration: sortedDurations[i] });
        }
      }
      if (!barChords.length) {
        return { ok: false, error: "Bar " + (bi + 1) + " is empty." };
      }
      var c = start;
      for (i = 0; i < barChords.length; i++) {
        var bc = barChords[i];
        if (Math.abs(bc.offset - c) > EPS) {
          return { ok: false, error: "Bar " + (bi + 1) + " has a gap/overlap at offset " + bc.offset + " (expected a chord at " + r6(c) + ")." };
        }
        c = r6(c + bc.duration);
      }
      if (Math.abs(c - end) > EPS) {
        var filled = r6(c - start);
        return { ok: false, error: "Bar " + (bi + 1) + " has " + filled + " beats, expected " + barLen + "." };
      }
    }

    return { ok: true };
  }

  // Map from palette quarter-length to VexFlow {duration, dots}.
  // duration is the VexFlow type string ("w","h","q","8","16").
  // dots is the dot count (0 or 1).
  var QL_TO_VEX = {
    4:    { duration: "w",  dots: 0 },
    3:    { duration: "h",  dots: 1 },
    2:    { duration: "h",  dots: 0 },
    1.5:  { duration: "q",  dots: 1 },
    1:    { duration: "q",  dots: 0 },
    0.75: { duration: "8",  dots: 1 },
    0.5:  { duration: "8",  dots: 0 },
    0.25: { duration: "16", dots: 0 },
  };

  /**
   * Convert a palette quarter-length to a VexFlow duration descriptor.
   *
   * @param {number} ql  Quarter-length (one of the eight palette values).
   * @return {{ duration: string, dots: number }}
   *   duration: VexFlow type string ("w","h","q","8","16").
   *   dots: dot count (0 or 1).
   *   Falls back to {duration:"q",dots:0} for unrecognised values.
   */
  function qlToVexDuration(ql) {
    var entry = QL_TO_VEX[r6(Number(ql))];
    return entry ? { duration: entry.duration, dots: entry.dots } : { duration: "q", dots: 0 };
  }

export default {
  PALETTE: PALETTE,
    isPaletteDuration: isPaletteDuration,
    meterQuarterLength: meterQuarterLength,
    offsetsFromDurations: offsetsFromDurations,
    suggestBarlines: suggestBarlines,
    measureItemCounts: measureItemCounts,
    checkRhythm: checkRhythm,
    qlToVexDuration: qlToVexDuration,
};
