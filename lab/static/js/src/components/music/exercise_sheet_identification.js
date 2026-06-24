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
    _isIdentificationLikeExercise: function () {
      var definition = this.exerciseContext.getDefinition();
      var isIdent = (definition.isIdentification && definition.isIdentification()) ||
             (definition.isChoraleIdentification && definition.isChoraleIdentification());
      return isIdent;
    },
    _isChoraleIdentificationExercise: function () {
      var definition = this.exerciseContext.getDefinition();
      return !!(definition.isChoraleIdentification && definition.isChoraleIdentification());
    },

    _getIdentificationInputContainer: function () {
      var $container = $("#ident-input-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-input-container" class="ident-input-container"></div>');
        $("#identification-actions").after($container);
      }
      return $container;
    },

    _isIdentificationProblemLocked: function (problemIndex) {
      var grdr = this.exerciseContext.grader;
      var currentMode = this._getActiveIdentificationMode();
      var limits = { practice: 3, submit: 2, test: 1 };
      var limit = limits[currentMode] || 3;
      var graderCounts = (grdr && grdr.attemptCounts) || {};
      var count = graderCounts[problemIndex] || 0;

      if (count >= limit) {
        return true;
      }

      if (
        currentMode === "test" &&
        grdr &&
        grdr.answers &&
        (
          (grdr.answers.hasOwnProperty(problemIndex) && grdr.answers[problemIndex] !== "") ||
          (grdr.answers.hasOwnProperty(String(problemIndex)) && grdr.answers[String(problemIndex)] !== "")
        )
      ) {
        return true;
      }

      if (this.exerciseContext.graded && currentMode !== "practice") {
        var pageOffset = this.exerciseContext.getIdentPageOffset
          ? this.exerciseContext.getIdentPageOffset()
          : 0;
        var localIndex = problemIndex - pageOffset;
        var gradedProblem = this.exerciseContext.graded.problems
          ? this.exerciseContext.graded.problems[localIndex]
          : null;
        if (gradedProblem && gradedProblem.correct) {
          return true;
        }
      }

      return false;
    },

    _applyIdentificationAnswer: function (problemIndex, label) {
      var grdr = this.exerciseContext.grader;
      var currentMode = this._getActiveIdentificationMode();

      if (!grdr || !grdr.setAnswer) {
        return;
      }

      if (this._isIdentificationProblemLocked(problemIndex)) {
        var lockDefinition = this.exerciseContext.getDefinition();
        var lockProblems = this._getVisibleIdentificationProblems(lockDefinition);
        this._hydrateTextInputComponent(
          this._inputComponent,
          this._getTextInputState(
            lockDefinition,
            lockProblems,
            this._getVisibleIdentificationAnswers(lockProblems)
          ).hydrationAnswers
        );
        return;
      }

      var existingAnswer = this._getStoredIdentificationAnswer(problemIndex);
      if ((existingAnswer || "") === (label || "")) {
        return;
      }

      this.exerciseContext.triggerTimer();
      grdr.setAnswer(problemIndex, label);

      if (
        IdentificationSubmitFlow._shouldAutosaveIdentificationChange({
          hasAnswer: !(label === null || label === undefined || label === ""),
        })
      ) {
        this.exerciseContext.saveIdentState();
        this.exerciseContext.submitIdentificationAnswers({
          is_page_submit: false,
          mode: currentMode,
        });
      }

      if (currentMode === "practice") {
        var textInputSnapshot = this._captureFocusedTextInput();
        var visibleProblems = this._getVisibleIdentificationProblems(this.exerciseContext.getDefinition());
        var practicePageOffset = this.exerciseContext.getIdentPageOffset
          ? this.exerciseContext.getIdentPageOffset()
          : 0;
        var graded = grdr.grade(this.exerciseContext.getDefinition(), visibleProblems, practicePageOffset);
        this.exerciseContext.graded = graded;
        this.render();
        this._restoreFocusedTextInput(textInputSnapshot);
        if (graded.result === "correct") {
          setTimeout(_.bind(function () {
            this.exerciseContext.grade();
          }, this), 500);
        }
      } else if (currentMode === "test") {
        this.exerciseContext.graded = null;
        this.render();
        var allProblems = this.exerciseContext.getDefinition().getProblems();
        var allAnswered = true;
        for (var i = 0; i < allProblems.length; i++) {
          if (!grdr.answers || !grdr.answers.hasOwnProperty(i)) {
            allAnswered = false;
            break;
          }
        }
        if (allAnswered) {
          grdr.grade(this.exerciseContext.getDefinition());
          setTimeout(_.bind(function () {
            this.exerciseContext.grade();
          }, this), 500);
        }
      } else {
        this.render();
      }
    },
    /**
     * Set up identification mode.  No DOM selects are created here —
     * answers are drawn on the canvas and editing happens via a position:fixed
     * popup that appears at the cursor when the student clicks near a label.
     *
     * Three modes (set via exercise data.identMode):
     *   "submit"   — pick all answers, press Submit, then see results (default)
     *   "practice" — correct/incorrect shown immediately after each selection
     *   "test"     — answers locked after choosing, no feedback ever shown
     */
    initIdentificationMode: function () {
      var self = this;
      var definition = this.exerciseContext.getDefinition();
      var grader = this.exerciseContext.grader;
      if (grader && grader.initFromDefinition) {
        grader.initFromDefinition(definition);
      }

      this._identActiveIndex = null;
      this._identPopupEl = null;
      this._syncIdentificationModeState();
      this._modeLocked = this.exerciseContext.settings.modeLocked || false;

      var $submitBtn = $('#identification-submit');
      $submitBtn.attr('type', 'button');
      // Use direct DOM property to ensure the handler cannot be removed by
      // subsequent .off('click') calls or overridden by other jQuery bindings.
      var submitBtnEl = $submitBtn[0];
      if (submitBtnEl) {
        submitBtnEl.onclick = null; // clear any prior handler
        submitBtnEl.onclick = _.bind(this.onSubmitIdentification, this);
      }

      this._refreshIdentificationModeUI();

      // Canvas click: open popup only inside the label hit zone below bass staff
      this.el.off('click.identification').on('click.identification', function (e) {
        if (!self._isIdentificationLikeExercise()) { return; }
        if (self._getIdentInputMode(definition) === "text") { return; }

        // Lock individual correct items so users can still modify incorrect choices or finish a new page
        var currentMode = self._currentMode;

        var offset = self.el.offset();
        var clickX = e.pageX - offset.left;
        var clickY = e.pageY - offset.top;

        var hitIndex = -1;
        var slots = self._getIdentificationSlots();
        for (var i = 0; i < slots.length; i++) {
          var slot = slots[i];
          if (!slot) { continue; }
          
          var problems = self.exerciseContext.getVisibleProblems
            ? self.exerciseContext.getVisibleProblems()
            : definition.getProblems();
          var problem = problems[slot.index];
          if (problem && problem.hidden) { continue; } // Skip hidden slots

          if (
            clickX >= slot.x - 20 && clickX <= slot.x + 20 &&
            clickY >= slot.y - 20 && clickY <= slot.y + 46
          ) {
            hitIndex = slot.index;
            break;
          }
        }
        // Lock slots that already have an answer in test mode, or are already graded correct in submit mode.
        var grdr = self.exerciseContext.grader;
        var pageOffset = self.exerciseContext.getIdentPageOffset
          ? self.exerciseContext.getIdentPageOffset() : 0;
        var absoluteHitIndex = pageOffset + hitIndex;
        
        var limits = { practice: 3, submit: 2, test: 1 };
        var limit = limits[self._currentMode] || 3;
        var graderCounts = (self.exerciseContext.grader && self.exerciseContext.grader.attemptCounts) || {};
        var count = graderCounts[absoluteHitIndex] || 0;

        if (count >= limit) {
          return;
        }

        if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(absoluteHitIndex)) {
          return;
        }

        if (self.exerciseContext.graded && currentMode !== 'practice') {
            var gp = self.exerciseContext.graded.problems ? self.exerciseContext.graded.problems[hitIndex] : null;
            if (gp && gp.correct) {
                return; // Lock only correctly graded items so users can still modify mistakes
            }
        }

        var problems = self.exerciseContext.getVisibleProblems
          ? self.exerciseContext.getVisibleProblems()
          : definition.getProblems();
        var problem = problems[hitIndex];
        if (!problem) { return; }

        self._showIdentPopup(absoluteHitIndex, problem.choices, e.clientX, e.clientY);
      });

      // Change cursor to pointer when hovering over a label zone
      this.el.off('mousemove.identification').on('mousemove.identification', function (e) {
        if (!self._isIdentificationLikeExercise()) { return; }
        if (self._getIdentInputMode(definition) === "text") {
          self.el.attr('title', '');
          self.el.css('cursor', '');
          return;
        }
        var offset = self.el.offset();
        var cx = e.pageX - offset.left;
        var cy = e.pageY - offset.top;
        var slots = self._getIdentificationSlots();
        var over = false;
        for (var i = 0; i < slots.length; i++) {
          var slot = slots[i];
          if (!slot) { continue; }

          var problems = self.exerciseContext.getVisibleProblems
            ? self.exerciseContext.getVisibleProblems()
            : definition.getProblems();
          var problem = problems[slot.index];
          if (problem && problem.hidden) { continue; } // Skip hidden slots

          if (
            cx >= slot.x - 20 && cx <= slot.x + 20 &&
            cy >= slot.y - 20 && cy <= slot.y + 46
          ) {
            over = true;
            break;
          }
        }
        self.el.attr('title', over ? 'Click to choose an answer. Use Type above for keyboard entry.' : '');
        self.el.css('cursor', over ? 'pointer' : '');
      });
    },

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

    _updateIdentificationProgressUI: function(answeredCount, totalCount) {
      var $btn = $('#identification-submit');
      if ($btn.length === 0) return;

      var $progContainer = $('#ident-progress-container');
      if ($progContainer.length === 0) {
          $progContainer = $('<div id="ident-progress-container" style="width: 250px; margin: 0 auto 15px; background: #e2e8f0; border-radius: 9999px; height: 6px; overflow: hidden; display: none;">' +
                           '<div id="ident-progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); transition: width 0.3s ease;"></div>' +
                           '</div>');
          $('#identification-actions').prepend($progContainer);
          
          if ($('#ident-premium-css').length === 0) {
              $('<style id="ident-premium-css">' +
                '#identification-submit {' +
                '  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);' +
                '  color: white;' +
                '  border: none;' +
                '  border-radius: 22px;' +
                '  padding: 10px 36px;' +
                '  font-size: 16px;' +
                '  font-weight: 600;' +
                '  cursor: default;' +
                '  opacity: 0.45;' +
                '  letter-spacing: 0.02em;' +
                '} ' +
                '#identification-submit.ready {' +
                '  cursor: pointer;' +
                '  opacity: 1;' +
                '  box-shadow: 0 4px 12px rgba(0, 198, 255, 0.45);' +
                '  transition: box-shadow 0.2s, opacity 0.2s;' +
                '} ' +
                '#identification-submit.ready:not(.hint-pulse):hover {' +
                '  box-shadow: 0 6px 18px rgba(0, 198, 255, 0.65);' +
                '}' +
                '#identification-submit.hint-pulse {' +
                '  animation: ident-hint-pulse 1.4s ease-in-out infinite !important;' +
                '  transition: none !important;' +
                '}' +
                '@keyframes ident-hint-pulse {' +
                '  0%,100% { box-shadow: 0 4px 12px rgba(0,198,255,0.45); opacity:1; }' +
                '  50% { box-shadow: 0 0 28px 6px rgba(0,198,255,0.85); opacity:1; }' +
                '}' +
                '</style>').appendTo('head');
          }
      }

      // Hide progress bar only after the exercise is fully completed (sealed)
      if (totalCount === 0 || this.exerciseContext.sealed) {
          $progContainer.hide();
          $btn.hide(); // Hide button when completed/sealed
          return;
      }

      var allProblems = this.exerciseContext.getDefinition().getProblems() || [];
      var visibleProblems = _.filter(allProblems, function(p) { return !p.hidden; });
      var globalTotal = visibleProblems.length;
      var answers = (this.exerciseContext.grader && this.exerciseContext.grader.answers) ? this.exerciseContext.grader.answers : {};
      var globalAnswered = 0;
      for (var i = 0; i < allProblems.length; i++) {
          if (allProblems[i] && !allProblems[i].hidden && answers && typeof answers.hasOwnProperty === 'function' && answers.hasOwnProperty(i) && answers[i] !== null && answers[i] !== '') {
              globalAnswered++;
          }
      }

      $progContainer.show();
      var progressPct = globalTotal > 0 ? (globalAnswered / globalTotal) * 100 : 0;
      $('#ident-progress-bar').css('width', progressPct + '%');

      var isLastPage = this.exerciseContext.getIdentPage && this.exerciseContext.getTotalIdentPages
         ? (this.exerciseContext.getIdentPage() >= this.exerciseContext.getTotalIdentPages() - 1)
         : true;

      // The button only cares if the CURRENT page is complete
      if (answeredCount >= totalCount) {
          $btn.addClass('ready').text(isLastPage ? 'Check' : 'Next Page');
          if (!isLastPage) {
            $btn.addClass('hint-pulse');
          } else {
            $btn.removeClass('hint-pulse');
          }
      } else {
          $btn.removeClass('ready hint-pulse').text('Complete Analysis');
      }
    },

    /**
     * Called when the student clicks Submit (submit mode only).
     */
    onSubmitIdentification: function () {
      var graded = this.exerciseContext.submitIdentPage({ fromUI: true, mode: this._currentMode });
      return graded;
    },

    _onIdentKeyDown: function (e) {
      if (!this._isIdentificationLikeExercise()) return;
      if ($(e.target).is("input, textarea, select") || e.target.isContentEditable) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        this.exerciseContext.goToIdentPage(this.exerciseContext.getIdentPage() + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        this.exerciseContext.goToIdentPage(this.exerciseContext.getIdentPage() - 1);
      }
    },

    _getActiveIdentificationMode: function () {
      return this.exerciseContext.sessionMode ||
        this.exerciseContext.settings.identMode ||
        this._currentMode ||
        "submit";
    },

    _syncIdentificationModeState: function () {
      this._currentMode = this._getActiveIdentificationMode();
      return this._currentMode;
    },

    _refreshIdentificationModeUI: function () {
      var identMode = this._syncIdentificationModeState();
      $("#identification-actions").show();
      if (identMode === "submit" && !this.exerciseContext.sealed) {
        $("#identification-submit").show();
      } else {
        $("#identification-submit").hide();
        $("#ident-progress-container").hide();
      }
      if ($("#ident-text-input-css").length === 0) {
        $("<style id='ident-text-input-css'>" +
          ".ident-input-container { margin: 10px auto 0; max-width: 640px; text-align: center; gap: 8px; flex-wrap: wrap; justify-content: center; align-items: center; }" +
          ".text-id-input { margin: 8px auto; max-width: 520px; }" +
          ".text-id-pill { display: flex; border: 2px solid #3b82f6; border-radius: 6px; overflow: hidden; background: #fff; }" +
          ".text-id-field { flex: 1; padding: 8px 12px; font-size: 15px; font-family: monospace; border: none; outline: none; }" +
          ".text-id-check { background: #3b82f6; color: #fff; border: none; padding: 8px 16px; font-size: 13px; cursor: pointer; white-space: nowrap; }" +
          ".text-id-check:hover { background: #2563eb; }" +
          ".text-id-hint { font-size: 11px; color: #94a3b8; text-align: center; margin-top: 4px; }" +
          ".ident-toggle-row { display: flex; justify-content: center; align-items: center; gap: 10px; flex-wrap: wrap; width: 100%; margin-top: 8px; }" +
          ".ident-mode-toggle { display: flex; justify-content: center; margin-top: 0; font-family: sans-serif; }" +
          ".mode-switch { position: relative; display: inline-flex; align-items: center; background: #f8fafc; border-radius: 999px; padding: 3px; border: 1px solid #dbe3ee; box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.05); }" +
          ".mode-option { min-width: 92px; padding: 7px 16px; font-size: 13px; font-weight: 600; color: #64748b; cursor: pointer; transition: all 0.18s ease; border-radius: 999px; text-align: center; line-height: 1; user-select: none; }" +
          ".mode-option.active { color: #0f172a; background: #ffffff; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12); }" +
          ".mode-option.disabled { color: #94a3b8; cursor: default; opacity: 0.7; }" +
          ".mode-option:hover:not(.active):not(.disabled) { color: #334155; background: rgba(255,255,255,0.55); }" +
          ".mode-option.disabled:hover { color: #94a3b8; background: transparent; }" +
          "</style>").appendTo("head");
      }
      var definition = this.exerciseContext.getDefinition();
      var problems = this._getVisibleIdentificationProblems(definition);
      var currentAnswers = this._getVisibleIdentificationAnswers(problems);
      this.renderInputModeToggle(this._getTextInputState(definition, problems, currentAnswers));
      this.renderModeToggle();
      this._syncIdentificationInputComponent();
    },

    _getIdentificationToggleRow: function () {
      var $row = $("#ident-toggle-row");
      if ($row.length === 0) {
        $row = $('<div id="ident-toggle-row" class="ident-toggle-row"></div>');
        $("#identification-actions").append($row);
      }
      return $row;
    },

    renderModeToggle: function () {
      this._syncIdentificationModeState();
      if (this._modeLocked || this._currentMode === "test") {
        $("#ident-mode-container").remove();
        return;
      }

      var $container = $("#ident-mode-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-mode-container" class="ident-mode-toggle"></div>');
      }
      this._getIdentificationToggleRow().append($container);

      var self = this;
      $container.empty();
      var $switch = $('<div class="mode-switch"></div>');
      
      var modes = [
        { id: "practice", label: "Practice" },
        { id: "submit", label: "Submit" }
      ];

      _.each(modes, function (m) {
        var $opt = $('<div class="mode-option"></div>').text(m.label).data("mode", m.id);
        if (self._currentMode === m.id) {
          $opt.addClass("active");
        }
        $opt.on("click", function () {
          self.onToggleMode(m.id);
        });
        $switch.append($opt);
      });

      $container.append($switch);
    },

    renderInputModeToggle: function (textInputState) {
      var self = this;
      var $existing = $("#ident-input-toggle-container");
      if ($existing.length) {
        $existing.remove();
      }

      if (!textInputState || !textInputState.supported) {
        return;
      }

      var $container = $('<div id="ident-input-toggle-container" class="ident-mode-toggle"></div>');
      var $switch = $('<div class="mode-switch"></div>');
      var modes = [
        { id: "dropdown", label: "Click" },
        { id: "text", label: "Type" }
      ];

      _.each(modes, function (m) {
        var $opt = $('<div class="mode-option"></div>').text(m.label);
        if (m.id === textInputState.effectiveMode) {
          $opt.addClass("active");
        }
        if (m.id === "text" && !textInputState.enabled) {
          $opt.addClass("disabled");
        }
        $opt.on("click", function () {
          if (m.id === textInputState.effectiveMode || (m.id === "text" && !textInputState.enabled)) {
            return;
          }
          self._closeIdentPopup();
          self._setIdentInputMode(m.id);
          self._identInputSignature = null;
          self.render();
        });
        $switch.append($opt);
      });

      $container.append($switch);
      this._getIdentificationToggleRow().append($container);
    },

    onToggleMode: function (newMode) {
      this._syncIdentificationModeState();
      if (this._modeLocked || this._currentMode === "test" || this._currentMode === newMode) {
        return;
      }
      this._currentMode = newMode;
      this.exerciseContext.sessionMode = newMode;
      this._refreshIdentificationModeUI();
      this.render(); // Re-render to update UI elements
    },
  };
});
