/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("./vexflow_adapter_logic"),
      require("./vexflow_annotation_renderer"),
      require("../identification_label_layout_logic")
    );
  } else if (typeof define === "function" && define.amd) {
    define(
      [
        "app/components/music/rendering/vexflow_adapter_logic",
        "app/components/music/rendering/vexflow_annotation_renderer",
        "app/components/music/identification_label_layout_logic",
      ],
      factory
    );
  } else {
    root.VexflowAnnotationPass = factory(
      root.VexflowAdapterLogic,
      root.VexflowAnnotationRenderer,
      root.IdentificationLabelLayoutLogic
    );
  }
})(typeof self !== "undefined" ? self : this, function (VexflowAdapterLogic, VexflowAnnotationRenderer, IdentificationLabelLayoutLogic) {
  "use strict";

  // The "Roman numeral expanded" annotation renders as a run spanning several
  // columns (so labels can share a baseline/connector), so it can't be drawn
  // column-by-column like the other analysis renderers — it has to be queued
  // and flushed as a run breaks or the measure loop ends. `loopState` is the
  // single object the render pipeline threads through the whole render() call
  // (mirrors what used to be plain closure variables shared across the loop).
  function createRomanExpRunHelpers(ctx, loopState, romanYOffset) {
    function flush() {
      if (!loopState.pendingRomanExpRun || !loopState.pendingRomanExpRun.columns.length) {
        loopState.pendingRomanExpRun = null;
        return;
      }
      VexflowAnnotationRenderer.drawInlineRomanExpRun(
        ctx,
        loopState.pendingRomanExpRun,
        loopState.pendingRomanExpRun.stave || loopState.lastBassStave,
        { yShift: romanYOffset, lineHeight: 11 }
      );
      loopState.pendingRomanExpRun = null;
    }

    function queue(col, expLabel, stave) {
      if (!expLabel || !expLabel.base) {
        flush();
        return;
      }

      var expX = VexflowAdapterLogic.getColumnCenterX(col);
      if (expX === null) {
        flush();
        return;
      }

      var column = {
        x: expX,
        figureLines: VexflowAdapterLogic.getRomanExpDisplayFigureLines(
          expLabel,
          loopState.pendingRomanExpRun ? loopState.pendingRomanExpRun.lastLabel : null
        ).slice(),
      };

      if (loopState.pendingRomanExpRun && loopState.pendingRomanExpRun.base === expLabel.base) {
        loopState.pendingRomanExpRun.columns.push(column);
        loopState.pendingRomanExpRun.stave = stave || loopState.pendingRomanExpRun.stave;
        loopState.pendingRomanExpRun.lastLabel = expLabel;
        return;
      }

      flush();
      loopState.pendingRomanExpRun = {
        base: expLabel.base,
        columns: [column],
        lastLabel: expLabel,
        stave: stave || loopState.lastBassStave,
      };
    }

    return { flush: flush, queue: queue };
  }

  // Stage: draw the per-onset-column analysis annotations (Roman numerals,
  // figured bass, scale degrees, note names, harmonization figures, deferred
  // key label) for one already-formatted measure. Fails safe: an error here
  // must not break note/stave rendering for the rest of the score.
  function drawMeasureAnnotations(params) {
    var ctx = params.ctx;
    var cfg = params.cfg;
    var opts = params.opts;
    var trebleVoices = params.trebleVoices;
    var bassVoices = params.bassVoices;
    var analysisWindows = params.analysisWindows;
    var absoluteWindowOffset = params.absoluteWindowOffset;
    var isFirstMeasure = params.isFirstMeasure;
    var displayKey = params.displayKey;
    var deferKeyLabelToIdentificationSlot = params.deferKeyLabelToIdentificationSlot;
    var trebleStave = params.trebleStave;
    var bassStave = params.bassStave;
    var score = params.score;
    var romanExp = params.romanExpHelpers;
    var staffLayoutColumns = params.staffLayoutColumns;

    try {
      if ((cfg.analyzeConfig && cfg.analyzeConfig.enabled && cfg.analysisRenderer !== "none" && cfg.keySignatureModel) ||
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
              measureWidth: params.measureWidth,
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
          if (cfg.isHarmonization && cfg.harmonizationTargetByOffset && typeof noteOnset === "number") {
            var colOffsetQb = noteOnset / 1024;
            var colOffsetKey = String(Math.round(colOffsetQb * 1000));
            harmTargetByOffset = cfg.harmonizationTargetByOffset[colOffsetKey] || null;
          }
          if (cfg.isHarmonization && harmTargetByOffset && columnCenterX !== null && activeStaveForAnnotations) {
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
          } else if (cfg.renderRomans && activeStaveForAnnotations) {
            var storedRoman = VexflowAdapterLogic.getStoredRomanLabel(
              score && score.umto && score.umto.analysis,
              noteOnset
            );
            VexflowAnnotationRenderer.attachInlineRomanAnnotation(
              col,
              midi,
              cfg.analyzeConfig,
              cfg.inlineAnalyzer,
              ctx,
              activeStaveForAnnotations,
              { yShift: cfg.romanYOffset, colGap: colGap },
              storedRoman || undefined
            );
          } else if (cfg.renderFigured && activeStaveForAnnotations) {
            var figureLabel = VexflowAdapterLogic.computeFiguredLabel(
              midi,
              cfg.inlineAnalyzer,
              !!(cfg.analyzeConfig &&
                cfg.analyzeConfig.mode &&
                cfg.analyzeConfig.mode.abbreviate_thoroughbass)
            );
            if (figureLabel && columnCenterX !== null) {
              var figLines2 = figureLabel.split("\n");
              var yBase2 = activeStaveForAnnotations.getBottomY ? activeStaveForAnnotations.getBottomY() : 0;
              var figLineH = 14;
              var figStartY2 = yBase2 + cfg.figuredYOffset;
              ctx.save();
              ctx.fillStyle = "#000";
              ctx.font = "16px MainSerifs";
              ctx.textAlign = "center";
              figLines2.forEach(function (line, idx) {
                ctx.fillText(line, columnCenterX, figStartY2 + idx * figLineH);
              });
              ctx.restore();
            }
          } else if (cfg.renderRomanExp && activeStaveForAnnotations) {
            var expLabel = VexflowAdapterLogic.computeRomanExpLabel(midi, cfg.inlineAnalyzer);
            romanExp.queue(col, expLabel, activeStaveForAnnotations);
          } else if (cfg.renderNoteNames && activeStaveForAnnotations) {
            var spelling = null;
            if (matchedWindow && matchedWindow.spellingStack) {
              spelling = matchedWindow.spellingStack;
            }
            var explicitLabel = spelling ? VexflowAdapterLogic.formatExplicitNoteNames(spelling) : null;
            VexflowAnnotationRenderer.attachNoteNameAnnotation(
              col,
              midi,
              cfg.analyzeConfig,
              cfg.inlineAnalyzer,
              ctx,
              activeStaveForAnnotations,
              { yShift: cfg.romanYOffset },
              explicitLabel
            );
          } else if (cfg.renderScaleDegrees) {
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
              VexflowAnnotationRenderer.drawScaleDegreeAbove(ctx, attackList, columnCenterX, degStave, cfg.inlineAnalyzer, col.notes, bassStave, sdMap);
            }
            if (cfg.isClausula && bassStave && score && score.umto && score.umto.analysis) {
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
  }

  return {
    createRomanExpRunHelpers: createRomanExpRunHelpers,
    drawMeasureAnnotations: drawMeasureAnnotations,
  };
});
