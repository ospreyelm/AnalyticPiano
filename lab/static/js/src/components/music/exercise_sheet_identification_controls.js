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

    _getIdentificationInputContainer: function () {
      var $container = $("#ident-input-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-input-container" class="ident-input-container"></div>');
        $("#identification-actions").after($container);
      }
      return $container;
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
