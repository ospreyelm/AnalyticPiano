import Vex from "vexflow";
import ScoreTimeline from "app/components/music/score_timeline";
import Analyze from "app/utils/analyze";
import KeySignature from "app/models/key_signature";
import KeyContext from "app/models/key_context_logic";
import VexflowAdapterLogic from "app/components/music/rendering/vexflow_adapter_logic";

// Stage 1: derive render-wide config (analysis mode, harmonization overlays,
  // y-offsets, key signature alterations) that doesn't change across measures.
  // Returns null when the score has no measures (render() should bail out).
  function buildRenderConfig(score, opts, canvas) {
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

    var staffYOffset = (opts && opts.staffYOffset) || 0;
    var baseRomanYOffset = 32;
    var baseFiguredYOffset = 18;
    var romanYOffset = baseRomanYOffset - staffYOffset;
    var figuredYOffset = baseFiguredYOffset - staffYOffset;

    // Calculate key signature alterations once for the entire score
    var keySignatureAlterations = VexflowAdapterLogic.getKeySignatureAlterations(meta.key);

    if (!score.measures || score.measures.length === 0) {
      return null;
    }

    return {
      margin: margin,
      width: width,
      height: height,
      meta: meta,
      analyzeConfig: analyzeConfig,
      keySignatureModel: keySignatureModel,
      analysisRenderer: analysisRenderer,
      inlineAnalyzer: inlineAnalyzer,
      renderRomans: renderRomans,
      renderFigured: renderFigured,
      renderRomanExp: renderRomanExp,
      renderNoteNames: renderNoteNames,
      renderScaleDegrees: renderScaleDegrees,
      showNotation: showNotation,
      analysisType: analysisType,
      isClausula: isClausula,
      isAnalysisMatch: isAnalysisMatch,
      harmonizationTargets: harmonizationTargets,
      harmonizationRealization: harmonizationRealization,
      harmonizationPending: harmonizationPending,
      harmonizationRejected: harmonizationRejected,
      harmonizationTargetByOffset: harmonizationTargetByOffset,
      romanYOffset: romanYOffset,
      figuredYOffset: figuredYOffset,
      keySignatureAlterations: keySignatureAlterations,
      isHarmonization: !!(opts && opts.isHarmonization),
      lockedVoices: (opts && opts.lockedVoices) || [],
      voiceColors: (opts && opts.voiceColors) || null,
    };
  }

  // Stage 2: select which measures to render, build the analysis timeline, and
  // lay out the treble/bass system vertically. Returns null when there are no
  // measures left to render at this startMeasure/maxMeasures combination
  // (render() should bail out).
  function selectMeasureWindow(score, opts, cfg) {
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
      return null;
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
    var staffDistribution = (opts && opts.staffDistribution) || (cfg.meta && cfg.meta.staffDistribution) || "grand_staff";
    var showTreble = staffDistribution !== "bass";
    var showBass = staffDistribution !== "treble";

    var systemGap = (opts && opts.systemGap) || 150; // vertical spacing between treble and bass staves
    var staffYOffset = (opts && opts.staffYOffset) || 0;
    var trebleY = cfg.margin.top + 30 + staffYOffset;
    var bassY = showTreble ? trebleY + systemGap : trebleY;

    // Time from metadata if present; default 4/4
    var meta = cfg.meta;
    var time = (function () {
      if (meta && meta.time) {
        var parts = meta.time.split("/");
        var num = parseInt(parts[0], 10) || 4;
        var den = parseInt(parts[1], 10) || 4;
        return { num_beats: num, beat_value: den, resolution: Vex.Flow.RESOLUTION };
      }
      return { num_beats: 4, beat_value: 4, resolution: Vex.Flow.RESOLUTION };
    })();

    return {
      maxMeasures: maxMeasures,
      startMeasure: startMeasure,
      totalMeasures: totalMeasures,
      numMeasures: numMeasures,
      measuresToRender: measuresToRender,
      timeline: timeline,
      absoluteWindowOffset: absoluteWindowOffset,
      startingLocalKeyContext: startingLocalKeyContext,
      analysisWindows: analysisWindows,
      staffDistribution: staffDistribution,
      showTreble: showTreble,
      showBass: showBass,
      trebleY: trebleY,
      bassY: bassY,
      time: time,
    };
  }

export default {
  buildRenderConfig: buildRenderConfig,
    selectMeasureWindow: selectMeasureWindow,
};
