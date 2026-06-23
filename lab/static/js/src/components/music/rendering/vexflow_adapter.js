/* global define: false */

define([
  "lodash",
  "vexflow",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/utils/measure_engine",
  "app/models/key_signature",
  "app/models/key_context_logic",
  "app/models/harmonization_realization_logic",
  "app/components/music/rendering/vexflow_adapter_logic",
  "app/components/music/rendering/vexflow_annotation_renderer",
  "app/components/music/rendering/vexflow_tickable_builder",
  "app/components/music/identification_label_layout_logic",
], function (_, Vex, ScoreTimeline, Analyze, MeasureEngine, KeySignature, KeyContext, HarmonizationRealizationLogic, VexflowAdapterLogic, VexflowAnnotationRenderer, VexflowTickableBuilder, IdentificationLabelLayoutLogic) {
  "use strict";

  // Add a key signature with a minor->relative-major fallback for older VexFlow builds
  function addKeySignatureSafe(stave, key) {
    if (!key) return;
    var k = VexflowAdapterLogic.normalizeKeyForVexFlow(key);
    try {
      stave.addKeySignature(k);
    } catch (e) {
      // Some VexFlow versions only accept major names; try relative major for minor keys
      var minorToRelativeMajor = {
        "Am": "C",  "Em": "G",  "Bm": "D",  "F#m": "A",  "C#m": "E",
        "G#m": "B", "D#m": "F#", "A#m": "C#", "Dm": "F",   "Gm": "Bb",
        "Cm": "Eb", "Fm": "Ab", "Bbm": "Db", "Ebm": "Gb", "Abm": "Cb"
      };
      var fallback = minorToRelativeMajor[k];
      if (fallback) {
        try { stave.addKeySignature(fallback); } catch (_) { /* ignore */ }
      }
    }
  }

  function makeStave(ctx, x, y, w, clef, meta, addClef) {
    console.log("[ID] makeStave. clef:", clef, "addClef:", addClef, "meta:", meta);
    var stave = new Vex.Flow.Stave(x, y, w);
    stave.setContext(ctx);
    if (addClef) {
      stave.addClef(clef);
      if (meta && meta.key) {
        console.log("[ID] adding key:", meta.key);
        addKeySignatureSafe(stave, meta.key);
      }
      if (meta && meta.time) {
        console.log("[ID] adding time:", meta.time);
        stave.addTimeSignature(meta.time);
      }
    }
    return stave;
  }

  function render(score, renderer, opts) {
    var ctx = renderer.getContext();

    // Get canvas element - it's stored in ctx.canvas or ctx.element depending on VexFlow version
    var canvas = ctx.canvas || ctx.element;
    
    // Clear canvas first
    if (canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    
    ctx.save();
    try {
      var margin = { left: 20, right: 20, top: 20, bottom: 20 };
      var width = (opts && opts.width) || (canvas && canvas.width) || 800;
      var height = (opts && opts.height) || (canvas && canvas.height) || 300;
      var meta = score.meta || {};
      var analyzeConfig = (opts && opts.analyzeConfig) || { enabled: false, mode: {} };
      var keySignatureModel = (opts && opts.keySignature) || (score.meta && score.meta.key ? new KeySignature(score.meta.key) : new KeySignature("C"));
      var analysisRenderer = (opts && opts.analysisRenderer) || "notater"; // notater|adapter|none
      var inlineAnalyzer = null;
      if (analyzeConfig && analyzeConfig.enabled && analysisRenderer !== "none") {
        try {
          inlineAnalyzer = new Analyze(keySignatureModel);
        } catch (err) {
          inlineAnalyzer = null;
        }
      }
      var renderRomans = VexflowAdapterLogic.shouldRenderRoman(analyzeConfig);
      var renderFigured = !renderRomans && VexflowAdapterLogic.shouldRenderFigured(analyzeConfig);
      var renderRomanExp = !renderRomans && !renderFigured && VexflowAdapterLogic.shouldRenderRomanExp(analyzeConfig);
      var renderNoteNames = !renderRomans && !renderFigured && !renderRomanExp && VexflowAdapterLogic.shouldRenderNoteNames(analyzeConfig);
      var renderScaleDegrees = !renderRomans && !renderFigured && !renderRomanExp && !renderNoteNames && VexflowAdapterLogic.shouldRenderScaleDegrees(analyzeConfig);
      if (!inlineAnalyzer) {
        renderRomans = false;
        renderFigured = false;
        renderRomanExp = false;
        renderNoteNames = false;
        renderScaleDegrees = false;
      }
      var showNotation = opts && opts.showNotation !== undefined ? opts.showNotation : true;
      var analysisType = (opts && opts.analysisType) || null;
      var isClausula = analysisType === "clausula";
      var isAnalysisMatch = !!(opts && opts.isAnalysisMatch);
      var harmonizationTargets = (opts && opts.harmonizationTargets) || null;
      var harmonizationRealization = (opts && opts.harmonizationRealization) || null;
      var harmonizationPending = (opts && opts.harmonizationPending) || null;
      var harmonizationRejected = (opts && opts.harmonizationRejected) || null;
      // Build offset-keyed lookup so columns match targets by musical position,
      // not by coincidental array index.
      var harmonizationTargetByOffset = null;
      if (harmonizationTargets && harmonizationTargets.length) {
        harmonizationTargetByOffset = Object.create(null);
        for (var hti = 0; hti < harmonizationTargets.length; hti++) {
          var htOff = harmonizationTargets[hti].offset;
          if (typeof htOff === "number") {
            harmonizationTargetByOffset[String(Math.round(htOff * 1000))] = harmonizationTargets[hti];
          }
        }
      }

      var systemGap = (opts && opts.systemGap) || 150; // vertical spacing between treble and bass staves
      var staffYOffset = (opts && opts.staffYOffset) || 0;
      var baseRomanYOffset = 32;
      var baseFiguredYOffset = 18;
      var romanYOffset = baseRomanYOffset - staffYOffset;
      var figuredYOffset = baseFiguredYOffset - staffYOffset;
      
      // Calculate key signature alterations once for the entire score
      var keySignatureAlterations = VexflowAdapterLogic.getKeySignatureAlterations(meta.key);

      if (!score.measures || score.measures.length === 0) {
        return;
      }

      // Limit to first N measures for initial view (default 4)
      var maxMeasures = opts && opts.maxMeasures !== undefined ? opts.maxMeasures : 4;
      var startMeasure = opts && opts.startMeasure ? parseInt(opts.startMeasure, 10) : 0;
      if (isNaN(startMeasure) || startMeasure < 0) {
        startMeasure = 0;
      }
      var totalMeasures = score.measures.length;
      if (startMeasure >= totalMeasures) {
        startMeasure = Math.max(0, totalMeasures - 1);
      }
      var remainingMeasures = Math.max(0, totalMeasures - startMeasure);
      var numMeasures = Math.min(remainingMeasures, maxMeasures);
      if (numMeasures <= 0) {
        return;
      }
      var measuresToRender = score.measures.slice(startMeasure, startMeasure + numMeasures);
      var timeline = ScoreTimeline && ScoreTimeline.buildTimeline
        ? ScoreTimeline.buildTimeline(score, {
            startMeasure: startMeasure,
            maxMeasures: numMeasures,
          })
        : [];
      
      // Calculate absolute window offset for playhead alignment
      var absoluteWindowOffset = 0;
      if (startMeasure > 0 && ScoreTimeline && ScoreTimeline.buildTimeline) {
        var fullTimeline = ScoreTimeline.buildTimeline(score);
        var allWindows = VexflowAdapterLogic.buildAnalysisWindows(fullTimeline);
        for (var i = 0; i < allWindows.length; i++) {
          if (allWindows[i].measureIndex < startMeasure) {
            absoluteWindowOffset++;
          } else {
            break;
          }
        }
      }

      var startingLocalKeyContext = null;
      if (score && score.umto && score.umto.analysis && score.umto.analysis.length && KeyContext && KeyContext.getKeyContext) {
        for (var keyIdx = absoluteWindowOffset; keyIdx < score.umto.analysis.length; keyIdx++) {
          var keySlice = score.umto.analysis[keyIdx];
          var localKey = keySlice && keySlice.content ? keySlice.content.local_key : null;
          if (!localKey) {
            continue;
          }
          startingLocalKeyContext = KeyContext.getKeyContext(localKey);
          if (startingLocalKeyContext) {
            break;
          }
        }
      }

      var analysisWindows = VexflowAdapterLogic.buildAnalysisWindows(timeline);
      var analysisWindowIdx = 0;
      var staffDistribution = (opts && opts.staffDistribution) || (meta && meta.staffDistribution) || "grand_staff";
      var voiceColors = (opts && opts.voiceColors) || null;
      var showTreble = staffDistribution !== "bass";
      var showBass = staffDistribution !== "treble";

      var systemGap = (opts && opts.systemGap) || 150; // vertical spacing between treble and bass staves
      var staffYOffset = (opts && opts.staffYOffset) || 0;
      var trebleY = margin.top + 30 + staffYOffset;
      var bassY = showTreble ? trebleY + systemGap : trebleY;

      // Time from metadata if present; default 4/4
      var time = (function () {
        if (meta && meta.time) {
          var parts = meta.time.split("/");
          var num = parseInt(parts[0], 10) || 4;
          var den = parseInt(parts[1], 10) || 4;
          return { num_beats: num, beat_value: den, resolution: Vex.Flow.RESOLUTION };
        }
        return { num_beats: 4, beat_value: 4, resolution: Vex.Flow.RESOLUTION };
      })();

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

      // SATB voice id map: [staffId][voiceIndex] -> voice label
      var SATB_MAP = { treble: ["S", "A"], bass: ["T", "B"] };
      var isHarmonization = !!(opts && opts.isHarmonization);
      var lockedVoices = (opts && opts.lockedVoices) || [];

      function staffVoices(staffId, staff, clef, idState, keySignatureAlterations, measureStartTick) {
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
      }

      // Pre-calculate measure widths based on actual duration
      var measureWidths = [];
      
      // Helper to convert duration to ticks
      function durationToTicks(dur) {
        return MeasureEngine.getTicks(dur.type, dur.dots || 0);
      }
      
      // Count noteheads in a measure (respects optional voice filtering)
      function countNoteheads(meas) {
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
      
      // Number of noteheads prior to the first rendered measure (aligns note IDs with grader timeline)
      var startNoteOffset = 0;
      if (startMeasure > 0) {
        for (var pre = 0; pre < startMeasure; pre++) {
          var priorMeasure = score.measures[pre];
          if (priorMeasure) {
            startNoteOffset += countNoteheads(priorMeasure);
          }
        }
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

      var availableWidth = width - margin.left - margin.right;
      var requiredBase = baseWidths.reduce(function(a,b){return a+b;}, 0);
      var remaining = Math.max(0, availableWidth - requiredBase);
      var totalWeight = weights.reduce(function(a, b) { return a + b; }, 0) || 1;
      var unitWidth = remaining / totalWeight;

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

      // Render each measure horizontally (limited to numMeasures)
      var currentX = margin.left;
      // Shared ID state across all measures and staves to match timeline IDs
      var globalIdState = { nextId: startNoteOffset, playedNoteIds: (opts && opts.playedNoteIds) || null };
      var lastTrebleStave = null;
      var lastBassStave = null;
      var pendingRomanExpRun = null;
      var staffLayoutColumns = [];
      var staffLayoutStaves = [];
      var layoutSystemYTop = Infinity;
      var layoutSystemYBottom = -Infinity;
      var layoutSystemXLeft = Infinity;
      var layoutSystemXRight = -Infinity;

      function flushRomanExpRun() {
        if (!pendingRomanExpRun || !pendingRomanExpRun.columns.length) {
          pendingRomanExpRun = null;
          return;
        }
        VexflowAnnotationRenderer.drawInlineRomanExpRun(
          ctx,
          pendingRomanExpRun,
          pendingRomanExpRun.stave || lastBassStave,
          { yShift: romanYOffset, lineHeight: 11 }
        );
        pendingRomanExpRun = null;
      }

      function queueRomanExpColumn(col, expLabel, stave) {
        if (!expLabel || !expLabel.base) {
          flushRomanExpRun();
          return;
        }

        var expX = VexflowAdapterLogic.getColumnCenterX(col);
        if (expX === null) {
          flushRomanExpRun();
          return;
        }

        var column = {
          x: expX,
          figureLines: VexflowAdapterLogic.getRomanExpDisplayFigureLines(
            expLabel,
            pendingRomanExpRun ? pendingRomanExpRun.lastLabel : null
          ).slice(),
        };

        if (pendingRomanExpRun && pendingRomanExpRun.base === expLabel.base) {
          pendingRomanExpRun.columns.push(column);
          pendingRomanExpRun.stave = stave || pendingRomanExpRun.stave;
          pendingRomanExpRun.lastLabel = expLabel;
          return;
        }

        flushRomanExpRun();
        pendingRomanExpRun = {
          base: expLabel.base,
          columns: [column],
          lastLabel: expLabel,
          stave: stave || lastBassStave,
        };
      }

      var cumulativeMeasureTick = 0;
      for (var measIdx = 0; measIdx < numMeasures; measIdx++) {
        var meas = measuresToRender[measIdx];
        var treble = meas.staves.treble;
        var bass = meas.staves.bass;

        var measureWidth = measureWidths[measIdx];
        var isFirstMeasure = measIdx === 0;
        var absoluteMeasureIndex = startMeasure + measIdx;

        var trebleStave = showTreble ? makeStave(ctx, currentX, trebleY, measureWidth, "treble", isFirstMeasure ? meta : {}, isFirstMeasure) : null;
        var bassStave = showBass ? makeStave(ctx, currentX, bassY, measureWidth, "bass", isFirstMeasure ? meta : {}, isFirstMeasure) : null;
        var activeStaveForLabel = bassStave || trebleStave;

        if (opts && typeof opts.onStaffLayout === "function") {
          function recordStave(stave, clef, topStep, topOctave) {
            if (!stave) return;
            var topLineY = stave.getYForLine ? stave.getYForLine(0) : stave.getY();
            var bottomLineY = stave.getYForLine ? stave.getYForLine(4) : stave.getBottomY();
            var lineSpacing = stave.getYForLine ? (stave.getYForLine(1) - stave.getYForLine(0)) : 10;
            var sx = stave.getX();
            var sw = stave.getWidth ? stave.getWidth() : measureWidth;
            if (!staffLayoutStaves.some(function (s) { return s.clef === clef; })) {
              staffLayoutStaves.push({
                clef: clef,
                topLineY: topLineY,
                bottomLineY: bottomLineY,
                lineSpacing: lineSpacing,
                topLineStep: topStep,
                topLineOctave: topOctave,
              });
            }
            var top = topLineY - 6 * lineSpacing;
            var bot = bottomLineY + 6 * lineSpacing;
            if (top < layoutSystemYTop) layoutSystemYTop = top;
            if (bot > layoutSystemYBottom) layoutSystemYBottom = bot;
            if (sx < layoutSystemXLeft) layoutSystemXLeft = sx;
            if (sx + sw > layoutSystemXRight) layoutSystemXRight = sx + sw;
          }
          recordStave(trebleStave, "treble", "F", 5);
          recordStave(bassStave, "bass", "A", 3);
        }

        // Draw explicit key label beneath the bass clef (e.g., "a:", "C:")
        function formatKeyForDisplay(k) {
          if (!k || typeof k !== "string" || k.length < 2) return k;
          var mode = k.charAt(0);
          var tonic = k.slice(1).replace(/_/g, "");
          var isMinor = mode === "i";
          var tonicLetter = tonic.charAt(0);
          var accidental = tonic.slice(1);
          return (isMinor ? tonicLetter.toLowerCase() : tonicLetter.toUpperCase()) + accidental + ":";
        }

        var displayKey = startingLocalKeyContext
          ? startingLocalKeyContext.prefix
          : ((opts &&
              opts.keySignature &&
              typeof opts.keySignature.getKey === "function")
            ? formatKeyForDisplay(opts.keySignature.getKey())
            : formatKeyForDisplay(meta && meta.key));

        var deferKeyLabelToIdentificationSlot = !!(opts && typeof opts.onWindowPosition === "function");
        if (isFirstMeasure && displayKey && activeStaveForLabel && !(opts && opts.hideKeyLabel) && !deferKeyLabelToIdentificationSlot) {
          ctx.save();
          ctx.font = "20px MainSerifs";
          ctx.fillStyle = (opts && opts.color) || "#000";
          ctx.textAlign = "left";
          var labelX = currentX + 16;
          var labelY = activeStaveForLabel.getBottomY() + 22;
          ctx.fillText(displayKey, labelX, labelY);
          ctx.restore();
        }

        // Draw system connector only on first measure and only if both staves are shown
        if (isFirstMeasure && trebleStave && bassStave) {
          var connector = new Vex.Flow.StaveConnector(trebleStave, bassStave);
          connector.setType('brace').setContext(ctx).draw();
          var leftLine = new Vex.Flow.StaveConnector(trebleStave, bassStave);
          leftLine.setType('singleLeft').setContext(ctx).draw();
        }

        var trebleVoices = staffVoices("treble", treble, "treble", globalIdState, keySignatureAlterations, cumulativeMeasureTick);
        var bassVoices = staffVoices("bass", bass, "bass", globalIdState, keySignatureAlterations, cumulativeMeasureTick);

        if (harmonizationRealization) {
          var entriesInMeasure = harmonizationRealization.filter(function (e) {
            return e.measureIndex === absoluteMeasureIndex;
          });
          if (entriesInMeasure.length) {
            var overlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
              entriesInMeasure,
              measureDurations[measIdx] || fullMeasureTicks,
              time,
              keySignatureAlterations
            );
            if (overlay) {
              trebleVoices.push(overlay);
            } else {
              console.warn(
                "[VexFlowAdapter] harmonization overlay tick mismatch in measure",
                absoluteMeasureIndex,
                "- skipping overlay for this measure"
              );
            }
          }
        }

        if (harmonizationPending && harmonizationPending.length) {
          var pendingInMeasure = harmonizationPending.filter(function (e) {
            return e.measureIndex === absoluteMeasureIndex;
          });
          if (pendingInMeasure.length) {
            var pendingOverlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
              pendingInMeasure,
              measureDurations[measIdx] || fullMeasureTicks,
              time,
              keySignatureAlterations,
              "#5b8def"
            );
            if (pendingOverlay) {
              trebleVoices.push(pendingOverlay);
            }
          }
        }

        if (harmonizationRejected && harmonizationRejected.length) {
          var rejectedInMeasure = harmonizationRejected.filter(function (e) {
            return e.measureIndex === absoluteMeasureIndex;
          });
          if (rejectedInMeasure.length) {
            var rejectedOverlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
              rejectedInMeasure,
              measureDurations[measIdx] || fullMeasureTicks,
              time,
              keySignatureAlterations,
              "#cc2200"
            );
            if (rejectedOverlay) {
              trebleVoices.push(rejectedOverlay);
            }
          }
        }

        // Add barlines at the end of each measure
        var isLastMeasureOfPiece = (absoluteMeasureIndex === score.measures.length - 1);
        // Standard intermediate barline is 'single'. Piece end is 'end'.
        var barType = isLastMeasureOfPiece ? 'end' : 'single';
        

        if (trebleStave) {
          trebleStave.setBegBarType(isFirstMeasure ? 'single' : 'none');
          trebleStave.setEndBarType(barType);
          trebleStave.draw();
          lastTrebleStave = trebleStave;
        }
        if (bassStave) {
          bassStave.setBegBarType(isFirstMeasure ? 'single' : 'none');
          bassStave.setEndBarType(barType);
          bassStave.draw();
          lastBassStave = bassStave;
        }

        // Connect staves with a vertical barline at the end of each measure
        if (trebleStave && bassStave) {
          try {
            var rightLine = new Vex.Flow.StaveConnector(trebleStave, bassStave);
            var connectorType = isLastMeasureOfPiece ? 'boldDoubleRight' : 'singleRight';
            rightLine.setType(connectorType).setContext(ctx).draw();
          } catch (e) {
            console.warn("[VexFlowAdapter] StaveConnector error:", e);
          }
        }

        // Use VexFlow 4's improved formatter for better spacing
        var allVoices = trebleVoices.concat(bassVoices);
        if (allVoices.length) {
          var formatter = new Vex.Flow.Formatter();
          if (trebleVoices.length) formatter.joinVoices(trebleVoices);
          if (bassVoices.length) formatter.joinVoices(bassVoices);

          var leftPadTreble = trebleStave ? (trebleStave.getNoteStartX() - trebleStave.getX()) : 0;
          var leftPadBass = bassStave ? (bassStave.getNoteStartX() - bassStave.getX()) : 0;
          var leftPad = Math.max(leftPadTreble, leftPadBass);
          var rightPad = (measIdx === numMeasures - 1) ? 20 : 12;
          var notesWidth = Math.max(0, measureWidth - leftPad - rightPad);
          
          formatter.format(allVoices, notesWidth);

          var noteXShift = parseInt(opts && opts.noteXShift, 10) || 0;
          if (noteXShift) {
            var shiftedTickContexts = [];
            allVoices.forEach(function(voice) {
              var tickables = Array.isArray(voice.tickables)
                ? voice.tickables
                : (typeof voice.getTickables === "function" ? voice.getTickables() : []);
              tickables.forEach(function(tickable) {
                if (!tickable || typeof tickable.getTickContext !== "function") return;
                var tickContext = tickable.getTickContext();
                if (!tickContext ||
                    shiftedTickContexts.indexOf(tickContext) !== -1 ||
                    typeof tickContext.getX !== "function" ||
                    typeof tickContext.setX !== "function") {
                  return;
                }
                tickContext.setX(tickContext.getX() + noteXShift);
                shiftedTickContexts.push(tickContext);
              });
            });
          }
        }

        // In VexFlow, format() calculates layout. We don't need to draw unplayed notes if showNotation is false.
        // However, some versions of VexFlow require draw() to compute absolute coordinates for tickables.
        // We will draw them inside an invisible SVG group if openGroup is available.
        var hiddenGroup = null;
        if (!showNotation) {
          ctx.save();
          if (typeof ctx.setGlobalAlpha === "function") ctx.setGlobalAlpha(0);
          ctx.globalAlpha = 0;
          if (typeof ctx.openGroup === "function") {
            hiddenGroup = ctx.openGroup("hidden_notation");
          }
        }

        if (trebleStave) {
          trebleVoices.forEach(function (v) { 
            v.draw(ctx, trebleStave); 
            if (v.beams && showNotation) {
              v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
            }
          });
        }
        if (bassStave) {
          bassVoices.forEach(function (v) { 
            v.draw(ctx, bassStave); 
            if (v.beams && showNotation) {
              v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
            }
          });
        }

        if (!showNotation) {
          if (hiddenGroup) {
            ctx.closeGroup();
            hiddenGroup.setAttribute("opacity", "0");
            hiddenGroup.setAttribute("visibility", "hidden");
          }
          ctx.restore();
          
          // Second pass: Draw only the played notes with full opacity
          var drawPlayedNotes = function(voices, stave) {
            voices.forEach(function(v) {
              var tks = (typeof v.getTickables === 'function') ? v.getTickables() : (v.tickables || []);
              tks.forEach(function(t) {
                // If it's a played note, it will have a non-transparent fillStyle from itemToTickable
                var style = (t.getStyle ? t.getStyle() : null);
                if (style && style.fillStyle !== "transparent") {
                   t.setContext(ctx).setStave(stave).draw();
                }
              });
            });
          };
          if (trebleStave) drawPlayedNotes(trebleVoices, trebleStave);
          if (bassStave) drawPlayedNotes(bassVoices, bassStave);

          // Third pass: Draw beams if ALL notes in the beam are played
          var drawPlayedBeams = function(voices) {
            voices.forEach(function(v) {
              if (!v.beams) return;
              v.beams.forEach(function(beam) {
                var allPlayed = beam.notes.every(function(n) {
                  var style = (n.getStyle ? n.getStyle() : null);
                  return style && style.fillStyle !== "transparent";
                });
                if (allPlayed) {
                  beam.setContext(ctx).draw();
                }
              });
            });
          };
          drawPlayedBeams(trebleVoices);
          drawPlayedBeams(bassVoices);
        }


        // Analysis annotations using Notater bridge (maximum reuse)
        try {
          if ((analyzeConfig && analyzeConfig.enabled && analysisRenderer !== "none" && keySignatureModel) ||
              (opts && typeof opts.onWindowPosition === "function")) {
            // Collect all tickables in this measure after formatting to get absolute X positions
            var allTickables = [];
            function addVoiceTickables(arr, staffId) {
              arr.forEach(function(voice, vIdx){
                if (!voice || !voice.tickables) return;
                var tks = Array.isArray(voice.tickables)
                  ? voice.tickables
                  : (typeof voice.getTickables === 'function' ? voice.getTickables() : []);
                tks.forEach(function(t){
                  if (!t || typeof t.getAbsoluteX !== 'function') return;
                  if (t._isHarmonizationOverlay) return;
                  // Rests don't create identification/analysis columns.
                  if (VexflowAdapterLogic && VexflowAdapterLogic.isRestTickable(t)) return;
                  t._sdStaffId = staffId;
                  t._sdVoiceIdx = vIdx; 
                  allTickables.push(t);
                });
              });
            }
            addVoiceTickables(trebleVoices, 'treble');
            addVoiceTickables(bassVoices, 'bass');

            // Group by X position (pixel) with small tolerance
            var groups = [];
            var tol = 3; // px
            allTickables.sort(function(a,b){ return a.getAbsoluteX() - b.getAbsoluteX(); });
            allTickables.forEach(function(t){
              var x = t.getAbsoluteX();
              var g = null;
              for (var gi=0; gi<groups.length; gi++) {
                if (Math.abs(groups[gi].x - x) <= tol) { g = groups[gi]; break; }
              }
              if (!g) { g = { x: x, notes: [] }; groups.push(g); }
              g.notes.push(t);
            });

            // Helpers
            // Draw per onset column
            var prevColX = null;
            var drewDeferredKeyLabel = false;
            groups.forEach(function(col){
              var midiSet = Object.create(null);
              col.notes.forEach(function(t){
                if (VexflowAdapterLogic && VexflowAdapterLogic.isRestTickable(t)) return;
                var keys = (typeof t.getKeys === 'function') ? t.getKeys() : [];
                for (var i=0;i<keys.length;i++) {
                  var m = VexflowAdapterLogic ? VexflowAdapterLogic.keyToMidi(keys[i]) : null;
                  if (m !== null) midiSet[m] = true;
                }
              });
              var attackList = Object.keys(midiSet).map(function(k){ return parseInt(k,10); }).sort(function(a,b){return a-b;});
              var midi = attackList.slice();
              if (!midi.length) return;

              var currentNote = col.notes[0];
              var noteOnset = currentNote._onset;
              var noteMeasure = currentNote._measureIndex;

              if (analysisWindows.length) {
                var matchedWindow = null;
                var matchedIndex = -1;
                
                // Find EXACT match by measure and onset
                for (var seek = 0; seek < analysisWindows.length; seek++) {
                  var win = analysisWindows[seek];
                  if (win.measureIndex === noteMeasure && Math.abs(win.onset - noteOnset) < 2) {
                    matchedWindow = win;
                    matchedIndex = seek;
                    break;
                  }
                }

                if (matchedWindow && matchedWindow.midiStack) {
                  midi = matchedWindow.midiStack.slice();
                }
              }

              var activeStaveForAnnotations = bassStave || trebleStave;
              var columnCenterX = VexflowAdapterLogic.getColumnCenterX(col);
              if (opts && typeof opts.onStaffLayout === "function" && columnCenterX !== null) {
                staffLayoutColumns.push({
                  systemIndex: 0,
                  onset: noteOnset,
                  measureIndex: noteMeasure,
                  measureX: (trebleStave || bassStave) ? (trebleStave || bassStave).getX() : null,
                  measureWidth: measureWidth,
                  centerX: columnCenterX,
                });
              }
              if (opts && typeof opts.onWindowPosition === "function" && typeof matchedIndex === "number" && columnCenterX !== null && activeStaveForAnnotations) {
                opts.onWindowPosition({
                  windowIndex: absoluteWindowOffset + matchedIndex,
                  onset: matchedWindow ? matchedWindow.onset : null,
                  measureIndex: matchedWindow ? matchedWindow.measureIndex : null,
                  x: columnCenterX,
                  y: activeStaveForAnnotations.getBottomY() + 18,
                });
              }

              if (
                isFirstMeasure &&
                displayKey &&
                activeStaveForAnnotations &&
                !(opts && opts.hideKeyLabel) &&
                deferKeyLabelToIdentificationSlot &&
                !drewDeferredKeyLabel &&
                groups.length
              ) {
                var firstColX = VexflowAdapterLogic.getColumnCenterX(groups[0]);
                if (firstColX !== null) {
                  ctx.save();
                  ctx.font = "20px MainSerifs";
                  ctx.fillStyle = (opts && opts.color) || "#000";
                  ctx.textAlign = "center";
                  var keyPos = IdentificationLabelLayoutLogic.getKeyLabelPosition({
                    slotX: firstColX,
                    slotY: activeStaveForAnnotations.getBottomY() - 6,
                    textWidth: ctx.measureText(displayKey).width,
                    canvasWidth: ctx.canvas && typeof ctx.canvas.width === "number" ? ctx.canvas.width : null,
                    canvasHeight: ctx.canvas && typeof ctx.canvas.height === "number" ? ctx.canvas.height : null,
                    initial: true,
                  });
                  ctx.fillText(displayKey, keyPos.x, keyPos.y);
                  ctx.restore();
                  drewDeferredKeyLabel = true;
                }
              }

              var colGap = (prevColX !== null && columnCenterX !== null) ? (columnCenterX - prevColX) : null;
              if (columnCenterX !== null) prevColX = columnCenterX;

              // Look up harmonization target by musical offset (ticks/1024 = quarter beats),
              // not by array index, so figure display is always position-correct.
              var harmTargetByOffset = null;
              if (isHarmonization && harmonizationTargetByOffset && typeof noteOnset === "number") {
                var colOffsetQb = noteOnset / 1024;
                var colOffsetKey = String(Math.round(colOffsetQb * 1000));
                harmTargetByOffset = harmonizationTargetByOffset[colOffsetKey] || null;
              }
              if (isHarmonization && harmTargetByOffset && columnCenterX !== null && activeStaveForAnnotations) {
                var harmTarget = harmTargetByOffset;
                var displayFig = harmTarget && (harmTarget.displayFigure || (harmTarget.figures && harmTarget.figures.join("/")));
                if (displayFig && columnCenterX !== null) {
                  var figLines = displayFig.split("/").map(function(s) { return s.trim(); }).filter(Boolean);
                  var yBase = activeStaveForAnnotations.getBottomY ? activeStaveForAnnotations.getBottomY() : 0;
                  var figStartY = yBase + 16;
                  var lineH = 17;
                  ctx.save();
                  ctx.fillStyle = "#000";
                  ctx.font = "bold 18px MainSerifs";
                  ctx.textAlign = "center";
                  figLines.forEach(function(line, idx) {
                    ctx.fillText(line, columnCenterX, figStartY + idx * lineH);
                  });
                  ctx.restore();
                }
              } else if (renderRomans && activeStaveForAnnotations) {
                var storedRoman = VexflowAdapterLogic.getStoredRomanLabel(
                  score && score.umto && score.umto.analysis,
                  noteOnset
                );
                VexflowAnnotationRenderer.attachInlineRomanAnnotation(
                  col,
                  midi,
                  analyzeConfig,
                  inlineAnalyzer,
                  ctx,
                  activeStaveForAnnotations,
                  { yShift: romanYOffset, colGap: colGap },
                  storedRoman || undefined
                );
              } else if (renderFigured && activeStaveForAnnotations) {
                var figureLabel = VexflowAdapterLogic.computeFiguredLabel(
                  midi,
                  inlineAnalyzer,
                  !!(analyzeConfig &&
                    analyzeConfig.mode &&
                    analyzeConfig.mode.abbreviate_thoroughbass)
                );
                if (figureLabel && columnCenterX !== null) {
                  var figLines = figureLabel.split("\n");
                  var yBase = activeStaveForAnnotations.getBottomY ? activeStaveForAnnotations.getBottomY() : 0;
                  var figLineH = 14;
                  var figStartY = yBase + figuredYOffset;
                  ctx.save();
                  ctx.fillStyle = "#000";
                  ctx.font = "16px MainSerifs";
                  ctx.textAlign = "center";
                  figLines.forEach(function (line, idx) {
                    ctx.fillText(line, columnCenterX, figStartY + idx * figLineH);
                  });
                  ctx.restore();
                }
              } else if (renderRomanExp && activeStaveForAnnotations) {
                var expLabel = VexflowAdapterLogic.computeRomanExpLabel(midi, inlineAnalyzer);
                queueRomanExpColumn(col, expLabel, activeStaveForAnnotations);
              } else if (renderNoteNames && activeStaveForAnnotations) {
                var spelling = null;
                if (matchedWindow && matchedWindow.spellingStack) {
                  spelling = matchedWindow.spellingStack;
                }
                var explicitLabel = spelling ? VexflowAdapterLogic.formatExplicitNoteNames(spelling) : null;
                VexflowAnnotationRenderer.attachNoteNameAnnotation(
                  col,
                  midi,
                  analyzeConfig,
                  inlineAnalyzer,
                  ctx,
                  activeStaveForAnnotations,
                  { yShift: romanYOffset },
                  explicitLabel
                );
              } else if (renderScaleDegrees) {
                var degStave = trebleStave || activeStaveForAnnotations;
                if (degStave) {
                  // Build MIDI->label map from stored scale_degrees in UMTO analysis slices.
                  var sdMap = null;
                  if (score && score.umto && score.umto.analysis && score.umto.analysis.length) {
                    var absQL = noteOnset / 1024;
                    for (var sdi = 0; sdi < score.umto.analysis.length; sdi++) {
                      var sdSlice = score.umto.analysis[sdi];
                      if (Math.abs(sdSlice.offset - absQL) < 0.05 &&
                          sdSlice.content && sdSlice.content.scale_degrees && sdSlice.content.scale_degrees.length) {
                        sdMap = Object.create(null);
                        sdSlice.content.scale_degrees.forEach(function(sd) {
                          sdMap[sd.midi] = sd.label;
                        });
                        break;
                      }
                    }
                  }
                  VexflowAnnotationRenderer.drawScaleDegreeAbove(ctx, attackList, columnCenterX, degStave, inlineAnalyzer, col.notes, bassStave, sdMap);
                }
                if (isClausula && bassStave && score && score.umto && score.umto.analysis) {
                  var bassQL = noteOnset / 1024;
                  var bassLabel = VexflowAdapterLogic
                    ? VexflowAdapterLogic.getBassLabelAtOffset(score.umto.analysis, bassQL)
                    : null;
                  if (bassLabel) {
                    VexflowAnnotationRenderer.drawBassScaleDegreeBelow(ctx, bassStave, bassLabel, columnCenterX);
                  }
                }
              }
            });
          }
        } catch (e) {
          // Fail-safe: don't break rendering if analysis drawing fails
          // console.warn('[VexFlowAdapter] Analysis annotation error:', e);
        }
        
        // Move X position for next measure
        currentX += measureWidth;
        cumulativeMeasureTick += measureDurations[measIdx] || 0;
      }

      if (opts && typeof opts.onStaffLayout === "function" && staffLayoutStaves.length) {
        var sysX = layoutSystemXLeft;
        var sysRight = layoutSystemXRight;
        staffLayoutStaves.forEach(function (s) {
          s.x = sysX;
          s.width = sysRight - sysX;
        });

        staffLayoutColumns.sort(function (a, b) { return a.centerX - b.centerX; });
        staffLayoutColumns.forEach(function (c, i) {
          var prev = staffLayoutColumns[i - 1];
          var next = staffLayoutColumns[i + 1];
          var left = prev ? (prev.centerX + c.centerX) / 2 : sysX;
          var right = next ? (c.centerX + next.centerX) / 2 : sysRight;
          left = Math.max(left, sysX);
          right = Math.min(right, sysRight);
          c.rect = { x: left, width: Math.max(0, right - left) };
        });

        opts.onStaffLayout({
          systems: [{
            systemIndex: 0,
            yTop: layoutSystemYTop,
            yBottom: layoutSystemYBottom,
            xLeft: sysX,
            xRight: sysRight,
            staves: staffLayoutStaves,
          }],
          columns: staffLayoutColumns,
        });
      }

      flushRomanExpRun();

        // Wrong note rendering removed - will be implemented via exercise grading system
    } finally {
      ctx.restore();
    }
  }

  return { render: render };
});
