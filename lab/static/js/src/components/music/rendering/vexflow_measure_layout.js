import Vex from "vexflow";
import VexflowStaffVoiceBuilder from "app/components/music/rendering/vexflow_staff_voice_builder";

// Count noteheads in a measure (respects optional voice filtering)
  function countNoteheads(meas, opts) {
    var total = 0;
    ['treble', 'bass'].forEach(function(staffName) {
      var staff = meas.staves[staffName];
      if (!staff || !staff.voices) return;
      var select = (opts && opts.selectVoices && opts.selectVoices[staffName]) || null;
      staff.voices.forEach(function(voice, vIdx) {
        if (select && select.indexOf(vIdx) === -1) return;
        voice.items.forEach(function(item) {
          if (item.kind === 'note') total += 1;
          if (item.kind === 'chord' && item.notes && item.notes.length) total += item.notes.length;
        });
      });
    });
    return total;
  }

  // Estimate key signature complexity by counting accidentals
  function getKeyAccidentalsCount(key) {
    if (!key) return 0;
    // Normalize key string (capitalize first char, keep trailing m if minor)
    var k = String(key).trim();
    var map = {
      'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
      'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
      'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
      'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5, 'Ebm': -6, 'Abm': -7
    };
    // Try exact; otherwise attempt uppercase base with optional 'm'
    if (Object.prototype.hasOwnProperty.call(map, k)) return map[k];
    return 0;
  }

  // Compute dynamic overhead for first measure (clef + key + time). Only applied for pickups.
  function computeFirstMeasureOverhead(meta) {
    var baseClefPx = 28;      // clef glyph
    var leftGapPx = 10;       // breathing room before first note
    var perAccidentalPx = 12; // width per sharp/flat
    var perTimeDigitPx = 8;   // width per time signature digit
    var timeGapPx = 6;        // gap after time signature
    var accCount = Math.abs(getKeyAccidentalsCount(meta && meta.key));
    var timeDigits = 0;
    if (meta && meta.time && meta.time.indexOf('/') !== -1) {
      var parts = meta.time.split('/');
      timeDigits = (parts[0] ? String(parts[0]).length : 0) + (parts[1] ? String(parts[1]).length : 0);
    }
    return leftGapPx + baseClefPx + (accCount * perAccidentalPx) + (timeDigits * perTimeDigitPx) + timeGapPx;
  }

  // Stage 3: pre-calculate per-measure pixel widths and the notehead-count
  // offset used to keep note IDs aligned with the grader timeline when
  // rendering a window that starts partway through the score.
  function computeMeasureLayout(score, opts, cfg, win) {
    var meta = cfg.meta;
    var keySignatureAlterations = cfg.keySignatureAlterations;
    var time = win.time;
    var numMeasures = win.numMeasures;
    var measuresToRender = win.measuresToRender;
    var startMeasure = win.startMeasure;

    var staffVoices = VexflowStaffVoiceBuilder.createStaffVoicesFn({
      opts: opts,
      isHarmonization: cfg.isHarmonization,
      lockedVoices: cfg.lockedVoices,
      voiceColors: cfg.voiceColors,
      time: time,
      showNotation: cfg.showNotation,
      isAnalysisMatch: cfg.isAnalysisMatch,
    });
    var durationToTicks = VexflowStaffVoiceBuilder.durationToTicks;

    // Number of noteheads prior to the first rendered measure (aligns note IDs with grader timeline)
    var startNoteOffset = 0;
    if (startMeasure > 0) {
      for (var pre = 0; pre < startMeasure; pre++) {
        var priorMeasure = score.measures[pre];
        if (priorMeasure) {
          startNoteOffset += countNoteheads(priorMeasure, opts);
        }
      }
    }

    // A full measure in this time signature (e.g., 4 quarter notes in 4/4 = 4096 ticks)
    var fullMeasureTicks = time.num_beats * (4096 / time.beat_value);

    // Calculate duration for each measure
    var measureDurations = [];
    for (var i = 0; i < numMeasures; i++) {
      var meas = measuresToRender[i];
      var maxTicks = 0;

      // Calculate actual duration (max across voices)
      ['treble', 'bass'].forEach(function(staffName) {
        var staff = meas.staves[staffName];
        if (staff && staff.voices) {
          staff.voices.forEach(function(voice) {
            var voiceTicks = 0;
            voice.items.forEach(function(item) {
              voiceTicks += durationToTicks(item.duration);
            });
            maxTicks = Math.max(maxTicks, voiceTicks);
          });
        }
      });

      measureDurations.push(maxTicks);
    }

    // Calculate widths using weights and dynamic overhead for pickup
    var minPartialMeasureWidth = 80; // Minimum width for partial measures (for notes area only)
    var isPickup = measureDurations.length > 0 && (measureDurations[0] < fullMeasureTicks * 0.95);
    // For pickups, dynamicOverhead reserves space for clef/key/time before notes.
    var dynamicOverhead = isPickup ? computeFirstMeasureOverhead(meta) : 0;
    // For full first measures, compensate left padding so its notes area matches other full bars.
    var firstBarCompensation = !isPickup ? computeFirstMeasureOverhead(meta) : 0;

    // Minimum notes width for the pickup based on VexFlow's formatter (pre-calculated)
    var pickupNotesMinWidth = 0;
    if (isPickup) {
      try {
        var pickupMeasure = measuresToRender[0];
        var voicesT = staffVoices("treble", pickupMeasure.staves.treble, "treble", null, keySignatureAlterations);
        var voicesB = staffVoices("bass", pickupMeasure.staves.bass, "bass", null, keySignatureAlterations);
        var allPickupVoices = voicesT.concat(voicesB);
        if (allPickupVoices.length) {
          var fmin = new Vex.Flow.Formatter();
          // Join by staff for better alignment before measuring
          if (voicesT.length) fmin.joinVoices(voicesT);
          if (voicesB.length) fmin.joinVoices(voicesB);
          pickupNotesMinWidth = fmin.preCalculateMinTotalWidth(allPickupVoices) || 0;
        }
      } catch (e) {
        pickupNotesMinWidth = 0; // fallback silently
      }
    }

    // Helper: get minimal notes width for an arbitrary measure (used for other partials, e.g., final bar)
    function measureNotesMinWidth(mIndex) {
      try {
        var m = measuresToRender[mIndex];
        var vT = staffVoices("treble", m.staves.treble, "treble", null, keySignatureAlterations);
        var vB = staffVoices("bass", m.staves.bass, "bass", null, keySignatureAlterations);
        var all = vT.concat(vB);
        if (!all.length) return 0;
        var fm = new Vex.Flow.Formatter();
        if (vT.length) fm.joinVoices(vT);
        if (vB.length) fm.joinVoices(vB);
        return fm.preCalculateMinTotalWidth(all) || 0;
      } catch (e) { return 0; }
    }

    // Build weights: full = 1, partials < 1; pickup scales with duration and note density
    var weights = [];
    for (var wi = 0; wi < numMeasures; wi++) {
      var dur = measureDurations[wi];
      var ratio = Math.max(0, Math.min(1, dur / fullMeasureTicks));
      if (dur >= fullMeasureTicks * 0.95) {
        weights.push(1);
      } else if (wi === 0 && numMeasures > 1) {
        // Pickup BEFORE full bars: we've already reserved a base width (overhead +
        // min notes width). Give it zero proportional share so it doesn't steal
        // space from the full bars that follow. Only applies when other measures
        // exist — a standalone short/free-mode measure is not a pickup-to-nothing
        // and must stretch to fill the width (see the weight-1 fallthrough below).
        weights.push(0);
      } else {
        // Other partials (rare): tie to duration with a floor
        weights.push(Math.max(0.5, ratio));
      }
    }

    // Establish base widths (fixed) and distribute the remainder proportionally via weights
    var baseWidths = new Array(numMeasures).fill(0);
    if (isPickup) {
      // Convert notes min width to whole-measure min using our notes area factor (80%)
      var pickupMinMeasureFromNotes = pickupNotesMinWidth > 0 ? (pickupNotesMinWidth / 0.8) : 0;
      baseWidths[0] = dynamicOverhead + Math.max(minPartialMeasureWidth, pickupMinMeasureFromNotes);
    } else {
      // No pickup: compensate for clef/key/time so first full bar's notesWidth is not penalized.
      baseWidths[0] = firstBarCompensation + ((opts && opts.firstMeasureExtraWidth) || 0);
    }

    var availableWidth = cfg.width - cfg.margin.left - cfg.margin.right;
    var requiredBase = baseWidths.reduce(function(a,b){return a+b;}, 0);
    var remaining = Math.max(0, availableWidth - requiredBase);
    var totalWeight = weights.reduce(function(a, b) { return a + b; }, 0) || 1;
    var unitWidth = remaining / totalWeight;

    var measureWidths = [];
    for (var mw = 0; mw < numMeasures; mw++) {
      var extra = unitWidth * weights[mw];
      var widthCandidate = baseWidths[mw] + extra;
      // Enforce a minimum notes-area width for a partial measure to avoid crumpling
      // ONLY when other (full) measures share the row. A standalone partial/free-mode
      // measure keeps its distributed width so it stretches to fill, instead of being
      // clamped to ~min and leaving the staff tiny.
      if (numMeasures > 1 && measureDurations[mw] < fullMeasureTicks * 0.95) {
        var minFromNotes = 0;
        var notesMin = (mw === 0 ? pickupNotesMinWidth : measureNotesMinWidth(mw));
        if (notesMin > 0) minFromNotes = notesMin / 0.8; // convert to whole-measure width
        widthCandidate = Math.max(baseWidths[mw], Math.max(minPartialMeasureWidth, minFromNotes));
      }
      measureWidths.push(widthCandidate);
    }

    return {
      measureWidths: measureWidths,
      startNoteOffset: startNoteOffset,
      fullMeasureTicks: fullMeasureTicks,
      measureDurations: measureDurations,
    };
  }

export default {
  computeMeasureLayout: computeMeasureLayout,
};
