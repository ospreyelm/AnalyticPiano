/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("vexflow"),
      require("./vexflow_stave_factory"),
      require("./vexflow_staff_voice_builder"),
      require("./vexflow_tickable_builder"),
      require("./vexflow_annotation_pass")
    );
  } else if (typeof define === "function" && define.amd) {
    define(
      [
        "vexflow",
        "app/components/music/rendering/vexflow_stave_factory",
        "app/components/music/rendering/vexflow_staff_voice_builder",
        "app/components/music/rendering/vexflow_tickable_builder",
        "app/components/music/rendering/vexflow_annotation_pass",
      ],
      factory
    );
  } else {
    root.VexflowRenderPipeline = factory(
      root.Vex,
      root.VexflowStaveFactory,
      root.VexflowStaffVoiceBuilder,
      root.VexflowTickableBuilder,
      root.VexflowAnnotationPass
    );
  }
})(typeof self !== "undefined" ? self : this, function (Vex, VexflowStaveFactory, VexflowStaffVoiceBuilder, VexflowTickableBuilder, VexflowAnnotationPass) {
  "use strict";

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

  // Records one stave's geometry for the onStaffLayout callback consumer
  // (identification slot positioning). `loopState` accumulates across the
  // whole render() call; `measureWidth` is this measure's pixel width.
  function recordStave(stave, clef, topStep, topOctave, measureWidth, loopState) {
    if (!stave) return;
    var topLineY = stave.getYForLine ? stave.getYForLine(0) : stave.getY();
    var bottomLineY = stave.getYForLine ? stave.getYForLine(4) : stave.getBottomY();
    var lineSpacing = stave.getYForLine ? (stave.getYForLine(1) - stave.getYForLine(0)) : 10;
    var sx = stave.getX();
    var sw = stave.getWidth ? stave.getWidth() : measureWidth;
    if (!loopState.staffLayoutStaves.some(function (s) { return s.clef === clef; })) {
      loopState.staffLayoutStaves.push({
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
    if (top < loopState.layoutSystemYTop) loopState.layoutSystemYTop = top;
    if (bot > loopState.layoutSystemYBottom) loopState.layoutSystemYBottom = bot;
    if (sx < loopState.layoutSystemXLeft) loopState.layoutSystemXLeft = sx;
    if (sx + sw > loopState.layoutSystemXRight) loopState.layoutSystemXRight = sx + sw;
  }

  // Stage 4: draw every measure in the window — staves, voices, harmonization
  // overlays, barlines, beam/format pass, and (delegated) analysis
  // annotations — then emit the accumulated staff-layout callback.
  function renderMeasures(ctx, score, opts, cfg, win, layout) {
    var staffVoices = VexflowStaffVoiceBuilder.createStaffVoicesFn({
      opts: opts,
      isHarmonization: cfg.isHarmonization,
      lockedVoices: cfg.lockedVoices,
      voiceColors: cfg.voiceColors,
      time: win.time,
      showNotation: cfg.showNotation,
      isAnalysisMatch: cfg.isAnalysisMatch,
    });

    var displayKey = win.startingLocalKeyContext
      ? win.startingLocalKeyContext.prefix
      : ((opts &&
          opts.keySignature &&
          typeof opts.keySignature.getKey === "function")
        ? formatKeyForDisplay(opts.keySignature.getKey())
        : formatKeyForDisplay(cfg.meta && cfg.meta.key));
    var deferKeyLabelToIdentificationSlot = !!(opts && typeof opts.onWindowPosition === "function");

    var loopState = {
      currentX: cfg.margin.left,
      globalIdState: { nextId: layout.startNoteOffset, playedNoteIds: (opts && opts.playedNoteIds) || null },
      lastTrebleStave: null,
      lastBassStave: null,
      pendingRomanExpRun: null,
      staffLayoutColumns: [],
      staffLayoutStaves: [],
      layoutSystemYTop: Infinity,
      layoutSystemYBottom: -Infinity,
      layoutSystemXLeft: Infinity,
      layoutSystemXRight: -Infinity,
      cumulativeMeasureTick: 0,
    };
    var romanExp = VexflowAnnotationPass.createRomanExpRunHelpers(ctx, loopState, cfg.romanYOffset);

    for (var measIdx = 0; measIdx < win.numMeasures; measIdx++) {
      var meas = win.measuresToRender[measIdx];
      var treble = meas.staves.treble;
      var bass = meas.staves.bass;

      var measureWidth = layout.measureWidths[measIdx];
      var isFirstMeasure = measIdx === 0;
      var absoluteMeasureIndex = win.startMeasure + measIdx;

      var trebleStave = win.showTreble ? VexflowStaveFactory.makeStave(ctx, loopState.currentX, win.trebleY, measureWidth, "treble", isFirstMeasure ? cfg.meta : {}, isFirstMeasure) : null;
      var bassStave = win.showBass ? VexflowStaveFactory.makeStave(ctx, loopState.currentX, win.bassY, measureWidth, "bass", isFirstMeasure ? cfg.meta : {}, isFirstMeasure) : null;
      var activeStaveForLabel = bassStave || trebleStave;

      if (opts && typeof opts.onStaffLayout === "function") {
        recordStave(trebleStave, "treble", "F", 5, measureWidth, loopState);
        recordStave(bassStave, "bass", "A", 3, measureWidth, loopState);
      }

      if (isFirstMeasure && displayKey && activeStaveForLabel && !(opts && opts.hideKeyLabel) && !deferKeyLabelToIdentificationSlot) {
        ctx.save();
        ctx.font = "20px MainSerifs";
        ctx.fillStyle = (opts && opts.color) || "#000";
        ctx.textAlign = "left";
        var labelX = loopState.currentX + 16;
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

      var trebleVoices = staffVoices("treble", treble, "treble", loopState.globalIdState, cfg.keySignatureAlterations, loopState.cumulativeMeasureTick, absoluteMeasureIndex);
      var bassVoices = staffVoices("bass", bass, "bass", loopState.globalIdState, cfg.keySignatureAlterations, loopState.cumulativeMeasureTick, absoluteMeasureIndex);

      if (cfg.harmonizationRealization) {
        var entriesInMeasure = cfg.harmonizationRealization.filter(function (e) {
          return e.measureIndex === absoluteMeasureIndex;
        });
        if (entriesInMeasure.length) {
          var overlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
            entriesInMeasure,
            layout.measureDurations[measIdx] || layout.fullMeasureTicks,
            win.time,
            cfg.keySignatureAlterations
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

      if (cfg.harmonizationPending && cfg.harmonizationPending.length) {
        var pendingInMeasure = cfg.harmonizationPending.filter(function (e) {
          return e.measureIndex === absoluteMeasureIndex;
        });
        if (pendingInMeasure.length) {
          var pendingOverlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
            pendingInMeasure,
            layout.measureDurations[measIdx] || layout.fullMeasureTicks,
            win.time,
            cfg.keySignatureAlterations,
            "#5b8def"
          );
          if (pendingOverlay) {
            trebleVoices.push(pendingOverlay);
          }
        }
      }

      if (cfg.harmonizationRejected && cfg.harmonizationRejected.length) {
        var rejectedInMeasure = cfg.harmonizationRejected.filter(function (e) {
          return e.measureIndex === absoluteMeasureIndex;
        });
        if (rejectedInMeasure.length) {
          var rejectedOverlay = VexflowTickableBuilder.buildHarmonizationOverlayVoice(
            rejectedInMeasure,
            layout.measureDurations[measIdx] || layout.fullMeasureTicks,
            win.time,
            cfg.keySignatureAlterations,
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
        loopState.lastTrebleStave = trebleStave;
      }
      if (bassStave) {
        bassStave.setBegBarType(isFirstMeasure ? 'single' : 'none');
        bassStave.setEndBarType(barType);
        bassStave.draw();
        loopState.lastBassStave = bassStave;
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
        var rightPad = (measIdx === win.numMeasures - 1) ? 20 : 12;
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
      if (!cfg.showNotation) {
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
          if (v.beams && cfg.showNotation) {
            v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
          }
        });
      }
      if (bassStave) {
        bassVoices.forEach(function (v) {
          v.draw(ctx, bassStave);
          if (v.beams && cfg.showNotation) {
            v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
          }
        });
      }

      if (!cfg.showNotation) {
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
      VexflowAnnotationPass.drawMeasureAnnotations({
        ctx: ctx,
        cfg: cfg,
        opts: opts,
        trebleVoices: trebleVoices,
        bassVoices: bassVoices,
        analysisWindows: win.analysisWindows,
        absoluteWindowOffset: win.absoluteWindowOffset,
        isFirstMeasure: isFirstMeasure,
        displayKey: displayKey,
        deferKeyLabelToIdentificationSlot: deferKeyLabelToIdentificationSlot,
        trebleStave: trebleStave,
        bassStave: bassStave,
        score: score,
        romanExpHelpers: romanExp,
        staffLayoutColumns: loopState.staffLayoutColumns,
        measureWidth: measureWidth,
      });

      // Move X position for next measure
      loopState.currentX += measureWidth;
      loopState.cumulativeMeasureTick += layout.measureDurations[measIdx] || 0;
    }

    if (opts && typeof opts.onStaffLayout === "function" && loopState.staffLayoutStaves.length) {
      var sysX = loopState.layoutSystemXLeft;
      var sysRight = loopState.layoutSystemXRight;
      loopState.staffLayoutStaves.forEach(function (s) {
        s.x = sysX;
        s.width = sysRight - sysX;
      });

      loopState.staffLayoutColumns.sort(function (a, b) { return a.centerX - b.centerX; });
      loopState.staffLayoutColumns.forEach(function (c, i) {
        var prev = loopState.staffLayoutColumns[i - 1];
        var next = loopState.staffLayoutColumns[i + 1];
        var left = prev ? (prev.centerX + c.centerX) / 2 : sysX;
        var right = next ? (c.centerX + next.centerX) / 2 : sysRight;
        left = Math.max(left, sysX);
        right = Math.min(right, sysRight);
        c.rect = { x: left, width: Math.max(0, right - left) };
      });

      opts.onStaffLayout({
        systems: [{
          systemIndex: 0,
          yTop: loopState.layoutSystemYTop,
          yBottom: loopState.layoutSystemYBottom,
          xLeft: sysX,
          xRight: sysRight,
          staves: loopState.staffLayoutStaves,
        }],
        columns: loopState.staffLayoutColumns,
      });
    }

    romanExp.flush();

    // Wrong note rendering removed - will be implemented via exercise grading system
  }

  return {
    renderMeasures: renderMeasures,
  };
});
