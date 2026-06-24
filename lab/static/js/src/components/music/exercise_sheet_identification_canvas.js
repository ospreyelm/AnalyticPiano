/* global define: false */
define([
  "jquery",
  "jquery-ui",
  "lodash",
  "vexflow",
  "app/config",
  "app/utils/analyze",
  "app/components/events",
  "app/components/component",
  "app/utils/fontparser",
  "./stave",
  "./stave_notater",
  "./exercise_note_factory",
  "./rendering/vexflow_adapter",
  "./score_timeline",
  "app/components/input/text_input",
  "app/models/score_player",
  "app/models/identification_submit_flow_logic",
  "app/models/key_context_logic",
  "app/components/music/playback_controls",
  "app/utils/measure_engine",
  "app/models/harmonization_realization_logic",
  "app/components/music/identification_label_layout_logic",
  "app/models/chordal_problems_logic",
  "./chordal_umto_staff_distribution",
  "app/models/key_signature",
  "./chordal_spelling",
  "app/utils/chordal_barlines_logic",
  "app/utils/umto_score_converter",
  "app/utils/barline_spacing_utils",
], function (
  $,
  $UI,
  _,
  Vex,
  Config,
  Analyze,
  EVENTS,
  Component,
  FontParser,
  Stave,
  StaveNotater,
  ExerciseNoteFactory,
  VexFlowAdapter,
  ScoreTimeline,
  TextInput,
  ScorePlayer,
  IdentificationSubmitFlow,
  KeyContext,
  renderPlaybackControls,
  MeasureEngine,
  HarmonizationRealizationLogic,
  IdentificationLabelLayoutLogic,
  ChordalProblemsLogic,
  ChordalUMTOStaffDistribution,
  KeySignature,
  ChordalSpelling,
  ChordalBarlinesLogic,
  UMTOScoreConverter,
  BarlineSpacingUtils
) {
  "use strict";

  return {

    /**
     * Shows a position:fixed popup list of choices at the cursor.
     */
    _showIdentPopup: function (problemIndex, choices, clientX, clientY) {
      var self = this;
      this._closeIdentPopup();

      var popup = $('<div id="ident-popup"></div>');
      _.each(choices, function (choice) {
        var btn = $('<button></button>').addClass('ident-popup-btn').text(choice);
        btn.on('click', function (e) {
          e.stopPropagation();
          self._applyIdentificationAnswer(problemIndex, choice);
          self._closeIdentPopup();
        });
        popup.append(btn);
      });

      // Position popup to the right of cursor; shift left if near viewport edge
      var winW = $(window).width();
      var left = clientX + 8;
      popup.css({ top: clientY - 10, left: left });
      $('body').append(popup);
      var popupW = popup.outerWidth();
      if (left + popupW > winW - 10) {
        popup.css('left', clientX - popupW - 8);
      }

      this._identPopupEl = popup;

      // Close on any outside click
      setTimeout(function () {
        $(document).one('click.identpopup', function () {
          self._closeIdentPopup();
        });
      }, 0);
    },

    _closeIdentPopup: function () {
      if (this._identPopupEl) {
        this._identPopupEl.remove();
        this._identPopupEl = null;
      }
      $(document).off('click.identpopup');
    },

    /**
     * Draws the current answer (or a "?" placeholder) below the bass staff,
     * plus a ✓ or ✗ symbol when graded.
     * Called from renderStaves() after all staves are drawn.
     */
    _getIdentificationSlots: function () {
      var definition = this.exerciseContext.getDefinition();
      var problems = this.exerciseContext.getVisibleProblems
        ? this.exerciseContext.getVisibleProblems()
        : (definition.getProblems ? definition.getProblems() : []);
      if ((this._isChoraleIdentificationExercise() || definition.getScore()) && !_.isEmpty(this._identWindowLayout)) {
        var layout = this._identWindowLayout || {};
        var layoutByOnset = this._identWindowLayoutByOnset || {};
        return _.map(problems, function (problem, idx) {
          var slot = null;
          if (problem && typeof problem.windowIndex === "number" && layout[problem.windowIndex]) {
            slot = layout[problem.windowIndex];
          }
          if (
            !slot &&
            problem &&
            problem.measureIndex !== undefined &&
            problem.onset !== undefined
          ) {
            slot = layoutByOnset[problem.measureIndex + ":" + problem.onset] || null;
          }
          if (!slot) { return null; }
          return { index: idx, x: slot.x, y: slot.y };
        }).filter(Boolean);
      }

      var noteStaves = this.staves.slice(1);
      return _.map(noteStaves, function (treble, idx) {
        var bass = treble.connectedStave;
        if (!bass || !bass.staffSegment) {
          return null;
        }
        return {
          index: idx,
          x: bass.getStartX() + 8,
          y: bass.getBottomY() + 18,
        };
      }).filter(Boolean);
    },

    drawIdentificationLabels: function () {
      var slots = this._getIdentificationSlots();
      console.log("[ID] drawIdentificationLabels slots count:", slots.length);
      console.log("[ID] _identWindowLayout keys:", Object.keys(this._identWindowLayout || {}));
      var definition = this.exerciseContext.getDefinition();
      var inputMode = this._getIdentInputMode(definition);
      console.log("[ID] inputMode:", inputMode, "identMode:", this._currentMode);
      if (inputMode === 'text') {
        console.log("[ID] EARLY RETURN: text input mode active (user may have 'text' in localStorage).");
        if (this._currentMode === 'submit' && typeof this._updateIdentificationProgressUI === 'function') {
          var textProblems = this._getVisibleIdentificationProblems(definition);
          var textAnswers = this._getVisibleIdentificationAnswers(textProblems);
          var answeredInTextMode = _.filter(textAnswers, function (answer) {
            return answer !== undefined && answer !== null && answer !== '';
          }).length;
          this._updateIdentificationProgressUI(answeredInTextMode, textProblems.length);
        }
        return;
      }
      var grader = this.exerciseContext.grader;
      var identMode = this._currentMode;

      if (!slots.length) {
        if (identMode === 'submit' && typeof this._updateIdentificationProgressUI === 'function') {
          this._updateIdentificationProgressUI(0, 0);
        }
        return;
      }

      var reviewMode = !!(definition && definition.exercise && definition.exercise.reviewMode);
      var ctx = this.vexRenderer.getContext();
      var lastGraded = this.exerciseContext.graded;

      var origFont = ctx.font;
      var origFillStyle = ctx.fillStyle;
      var origTextAlign = ctx.textAlign;
      var origTextBaseline = ctx.textBaseline;
      var origLineWidth = ctx.lineWidth;

      // Center labels on slot.x so visual position and click target match.
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      var answeredCount = 0;
      var visibleSlotCount = 0;
      var pageOffset = this.exerciseContext && this.exerciseContext.getIdentPageOffset
        ? this.exerciseContext.getIdentPageOffset() : 0;
      var problems = definition.getProblems ? definition.getProblems() : [];
      var analysisType = definition.getAnalysisType ? definition.getAnalysisType() : 'roman';
      console.log("[ID] problems count:", problems.length, "pageOffset:", pageOffset);
      problems.forEach(function(p, i) {
        console.log("[ID] problem[" + i + "] hidden:", p && p.hidden, "windowIndex:", p && p.windowIndex, "measureIndex:", p && p.measureIndex, "answer:", p && p.answer);
      });

      function drawKeyChangeLabel(ctx, text, x, y) {
        ctx.save();
        ctx.font = '16px MainSerifs';
        ctx.fillStyle = '#444444';
        ctx.textAlign = 'center';
        var pos = IdentificationLabelLayoutLogic.getKeyLabelPosition({
          slotX: x,
          slotY: y,
          textWidth: ctx.measureText(text).width,
          canvasWidth: ctx.canvas && typeof ctx.canvas.width === 'number' ? ctx.canvas.width : null,
          canvasHeight: ctx.canvas && typeof ctx.canvas.height === 'number' ? ctx.canvas.height : null,
        });
        ctx.fillText(text, pos.x, pos.y);
        ctx.restore();
        ctx.textAlign = 'center';
      }

      if (analysisType === 'roman' && KeyContext && KeyContext.getKeyContext) {
        var priorContext = null;
        for (var ks = 0; ks < slots.length; ks++) {
          var keySlot = slots[ks];
          var keyProblem = problems[pageOffset + keySlot.index];
          if (!keyProblem || !keyProblem.localKey) {
            continue;
          }
          var currentContext = KeyContext.getKeyContext(keyProblem.localKey);
          if (!currentContext) {
            continue;
          }
          if (priorContext && !(KeyContext.sameKeyContext && KeyContext.sameKeyContext(currentContext.harmonyLabKey, priorContext.harmonyLabKey))) {
            drawKeyChangeLabel(ctx, currentContext.prefix, keySlot.x, keySlot.y);
          }
          priorContext = currentContext;
        }
      }

      for (var i = 0; i < slots.length; i++) {
        var slot = slots[i];
        var lx = slot.x;
        var ly = slot.y;

        var localIndex = slot.index;
        var absoluteIndex = pageOffset + localIndex;

        var problem = problems[absoluteIndex];
        if (problem && problem.hidden) { continue; } // LEAVE A SPACE
        visibleSlotCount++;
        var keyContext = null;
        if (analysisType === 'roman' && problem && problem.localKey && KeyContext && KeyContext.getKeyContext) {
          keyContext = KeyContext.getKeyContext(problem.localKey);
        }

        // AUTO-SCROLL LOGIC: Scroll the active problem into view
        var activeIndex = grader && grader.activeIndex !== undefined ? grader.activeIndex : 0;
        console.log("[ID] Slot", i, "absIdx:", absoluteIndex, "lx:", lx, "ly:", ly, "label:", (grader && grader.answers && grader.answers[absoluteIndex]) || '?');
        if (absoluteIndex === activeIndex && this.el && this.el.parent) {
          var container = this.el.parent();
          if (container.length) {
            var scrollX = lx - container.width() / 2;
            container.stop().animate({ scrollLeft: Math.max(0, scrollX) }, 200);
          }
        }

        var chosen = null;
        if (grader && grader.answers) {
          if (grader.answers[absoluteIndex] !== undefined && grader.answers[absoluteIndex] !== null && grader.answers[absoluteIndex] !== '') {
            chosen = grader.answers[absoluteIndex];
          } else if (grader.answers[String(absoluteIndex)] !== undefined && grader.answers[String(absoluteIndex)] !== null && grader.answers[String(absoluteIndex)] !== '') {
            chosen = grader.answers[String(absoluteIndex)];
          }
        }
        var fillStyle = '#888888'; // unanswered
        if (chosen) { fillStyle = '#444444'; answeredCount++; } // answered
        var showCheck = false;
        var showCross = false;

        // Show colour feedback when graded (never in test mode)
        if (lastGraded && lastGraded.problems && lastGraded.problems[localIndex] && identMode !== 'test') {
          var gp = lastGraded.problems[localIndex];
          if (gp.correct === true)  { fillStyle = '#28a745'; showCheck = true; }
          if (gp.correct === false) { fillStyle = '#dc3545'; showCross = true; }
        }
        if (reviewMode && chosen && !showCheck && !showCross && problem) {
          if (chosen === problem.answer) {
            fillStyle = '#28a745';
            showCheck = true;
          } else {
            fillStyle = '#dc3545';
            showCross = true;
          }
        }
        if (reviewMode && !chosen && !showCross) {
          showCheck = true;
          fillStyle = '#28a745';
        }
        var label = IdentificationSubmitFlow._getIdentificationDisplayLabel({
          answer: chosen,
          fallbackAnswer: problem && problem.answer,
          reviewMode: reviewMode,
          showCheck: showCheck,
        });
        var baseLabel = label;
        var hasDisplayAnswer = baseLabel !== '?';
        label = baseLabel;
        var shouldRenderPlaceholder = IdentificationSubmitFlow._shouldRenderIdentificationPlaceholder({
          reviewMode: reviewMode,
          hasAnswer: hasDisplayAnswer,
        });

        var labelY = ly;
        var markerY = ly + 18;
        if (ctx.canvas && typeof ctx.canvas.height === 'number') {
          var maxMarkerY = ctx.canvas.height - 6;
          if (markerY > maxMarkerY) {
            var delta = markerY - maxMarkerY;
            labelY -= delta;
            markerY -= delta;
          }
        }

        // ✓ or ✗ drawn below the label text
        var markerYOffset = showCheck || showCross ? 22 : 0;
        
        if (!hasDisplayAnswer && !shouldRenderPlaceholder) {
          // Review mode: hide unanswered placeholder labels, but keep completion marks.
        } else if (!hasDisplayAnswer) {
          // Draw a clear, clickable pill background for unanswered items
          ctx.beginPath();
          ctx.font = 'bold 18px sans-serif';
          var textWidth = ctx.measureText(label).width;
          var w = Math.max(32, textWidth + 12);
          var h = 28;
          var rx = lx - w/2;
          var ry = labelY - 20;
          var rConfig = 6;
          ctx.moveTo(rx + rConfig, ry);
          ctx.lineTo(rx + w - rConfig, ry);
          ctx.quadraticCurveTo(rx + w, ry, rx + w, ry + rConfig);
          ctx.lineTo(rx + w, ry + h - rConfig);
          ctx.quadraticCurveTo(rx + w, ry + h, rx + w - rConfig, ry + h);
          ctx.lineTo(rx + rConfig, ry + h);
          ctx.quadraticCurveTo(rx, ry + h, rx, ry + h - rConfig);
          ctx.lineTo(rx, ry + rConfig);
          ctx.quadraticCurveTo(rx, ry, rx + rConfig, ry);
          ctx.closePath();
          
          ctx.fillStyle = '#fefce8';
          ctx.fill();
          ctx.strokeStyle = '#facc15';
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.fillStyle = '#ca8a04';
          ctx.fillText(label, lx, labelY);
        } else {
          // Answered slot — render properly based on analysis type
          if (analysisType === 'figured_bass' || analysisType === 'figured_bass_unabbreviated') {
            // Convert to Sebastian font display format (mirrors stave_notater.drawThoroughbass)
            var lines = label.split('/').map(function(line) {
              if (line === '\u00b07') return '/';
              if (line === '6+') return '&';
              if (line === '5+' || line === '5\u00b0' || line === '5°') return '%';
              if (line === '4+') return '$';
              if (line === '2+') return '"';
              if (line.slice(0, 2) === '##') return ('x ' + line.slice(2)).trim();
              if (line.slice(0, 1) === '#') return ('# ' + line.slice(1)).trim();
              if (line.slice(0, 2) === 'bb') return ('a ' + line.slice(2)).trim();
              if (line.slice(0, 1) === 'b') return ('b ' + line.slice(1)).trim();
              if (line.slice(0, 1) === 'n') return ('n ' + line.slice(1)).trim();
              return line;
            });
            ctx.font = '28px Sebastian';
            ctx.fillStyle = fillStyle;
            ctx.textAlign = 'center';
            var skip = 14;
            var topY = labelY - (lines.length - 1) * skip;
            for (var li = 0; li < lines.length; li++) {
              ctx.fillText(lines[li], lx, topY + li * skip);
            }
          } else {
            ctx.font = '18px JazzSerifs';
            ctx.fillStyle = fillStyle;
            ctx.fillText(label, lx, labelY);
          }
        }

        if (showCheck || showCross) {
          ctx.font = 'bold 15px sans-serif';
          ctx.fillText(showCheck ? '✓' : '✗', lx, markerY);
        }
      }

      if (identMode === 'submit' && typeof this._updateIdentificationProgressUI === 'function') {
        this._updateIdentificationProgressUI(answeredCount, visibleSlotCount);
      }

      ctx.font = origFont;
      ctx.fillStyle = origFillStyle;
      ctx.textAlign = origTextAlign;
      ctx.textBaseline = origTextBaseline;
      ctx.lineWidth = origLineWidth;
    },
  };
});
