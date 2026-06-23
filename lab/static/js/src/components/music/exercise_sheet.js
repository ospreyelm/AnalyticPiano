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

  /**
   * Defines the size of the chord bank (how many chords to display on
   * screen).
   * @type {number}
   */
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  var SETTING_HIDE_NEXT = Config.get("general.hideNextForAutoAdvance");

  var NUMBERED_EXERCISE_COUNT = Config.get("general.numberedExerciseCount");

  /**
   * ExerciseSheetComponent
   *
   * This object is responsible for knowing how to display plain sheet music
   * notation with the notes that have sounded (saved in the chord bank) and
   * are currently sounding via MIDI input or some other means. So this object
   * should know how to display the grand staff and configure it for analysis,
   * highlight, etc.
   *
   * @constructor
   * @param {object} settings
   * @param {ChordBank} settings.chords Required property.
   * @param {KeySignature} settings.keySignature Required property.
   */
  var ExerciseSheetComponent = function (settings) {
    this.settings = settings || {};

    if ("exerciseContext" in this.settings) {
      this.exerciseContext = this.settings.exerciseContext;
    } else {
      throw new Error("Missing parameter property: .exerciseContext");
    }

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("Missing parameter property: .keySignature");
    }

    if ("timeSignature" in this.settings.exerciseContext) {
      this.timeSignature = this.settings.exerciseContext.timeSignature;
    } else {
      throw new Error("Missing parameter property: .timeSignature");
    }

    this._inputSourceMode = "live";
    this._staffLayout = null;
    this._clickNoteComponent = null;
    this._ghost = null;
    this._ghostCanvasEl = null;

    _.bindAll(this, ["render", "onChordsUpdate", "onMidiNote", "onClickPristine", "onSubmitIdentification", "onToggleMode", "_onIdentKeyDown"]);
  };

  ExerciseSheetComponent.prototype = new Component();

  _.extend(ExerciseSheetComponent.prototype, {
    /**
     * Initializes the sheet.
     *
     * @param {object} config
     * @return undefined
     */
    initComponent: function () {
      this.el = $("canvas#staff");
      this.el[0].width = this.el.width();
      this.el[0].height = this.el.height();
      this.initRenderer();
      this.initStaves();
      this.initListeners();
      var definition = this.exerciseContext.getDefinition();
      // Chorale-specific init
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        this.initChoraleMode();
      }
      if (this._isIdentificationLikeExercise()) {
        this.initIdentificationMode();
      }

      // Playback
      var self = this;
      this.scorePlayer = new ScorePlayer(this.settings.midiDevice);
      this.scorePlayer.bind("tick", function (windowIndex) {
        self._playbackWindowIndex = windowIndex;
        self._drawPlaybackHighlight();
      });
      this.scorePlayer.bind("stopped", function () {
        self._playbackWindowIndex = null;
        self._clearPlaybackHighlight();
      });
      this._playbackWindowIndex = null;
    },
    /**
     * Initializes the canvas renderer and dom element.
     *
     * @return
     */
    initRenderer: function () {
      var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
      this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
      this.renderExerciseInfo();
      this.renderExerciseText();
    },
    /**
     * Initializes the staves that together will form the grand staff.
     *
     * @return undefined
     */
    initStaves: function () {
      this.updateStaves();
    },
    /**
     * Initializes event listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      this.parentComponent.bind("change", this.render);
      this.keySignature.bind("change", this.render);
      //this.getInputChords().bind('change', this.render);
      this.getInputChords().bind("change", this.onChordsUpdate);
      this.getInputChords().bind("clear", this.onChordsUpdate);
      this.exerciseContext.bind("goto", this.onGoToExercise);
      // Re-render when ident page changes (goToIdentPage fires "graded")
      this.exerciseContext.bind("graded", this.render);
      // Listen for MIDI notes globally
      this.subscribe(EVENTS.BROADCAST.NOTE, this.onMidiNote);
      // Listen for pristine/refresh button
      this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onClickPristine);
      // Arrow key page navigation for identification exercises
      window.removeEventListener("keydown", this._onIdentKeyDown, true);
      window.addEventListener("keydown", this._onIdentKeyDown, true);
    },
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
    _IDENT_INPUT_MODE_KEY: "harmonylab.identInputMode",

    _getStoredIdentInputMode: function (definition) {
      var fallbackMode = definition && definition.getInputMode
        ? definition.getInputMode()
        : "dropdown";
      var storedMode = null;

      try {
        storedMode = localStorage.getItem(this._IDENT_INPUT_MODE_KEY);
      } catch (e) {}

      var resolvedMode = storedMode || fallbackMode || "dropdown";
      return resolvedMode === "text" ? "text" : "dropdown";
    },

    _supportsTextInputMode: function (definition) {
      // Exercises can opt out of text input mode by setting inputModeFixed: "dropdown".
      // This preserves the visual slot UI (? circles under each beat), which is part
      // of the pedagogical design for chorale identification exercises.
      if (definition && definition.exercise && definition.exercise.inputModeFixed === "dropdown") {
        return false;
      }
      // Chorale identification exercises (umto_chorale or chorale_identification) always
      // use the ? slot UI — text entry is not applicable regardless of analysisType.
      if (definition && (
        (typeof definition.isChoraleIdentification === "function" && definition.isChoraleIdentification()) ||
        (definition.exercise && definition.exercise.type === "umto_chorale")
      )) {
        return false;
      }
      var analysisType = definition && definition.getAnalysisType
        ? definition.getAnalysisType()
        : "roman";
      return analysisType === "note_name" ||
        analysisType === "roman" ||
        analysisType === "figured_bass" ||
        analysisType === "figured_bass_unabbreviated" ||
        analysisType === "interval_generic" ||
        analysisType === "interval_specific";
    },

    _getRepresentableTextHydrationAnswers: function (answers) {
      var prefix = [];
      var sawGapAfterPrefix = false;

      for (var i = 0; i < (answers || []).length; i++) {
        var answer = answers[i];
        var hasAnswer = answer !== undefined && answer !== null && answer !== "";

        if (hasAnswer) {
          if (sawGapAfterPrefix || i !== prefix.length) {
            return null;
          }
          prefix.push(answer);
        } else if (prefix.length > 0) {
          sawGapAfterPrefix = true;
        }
      }

      return prefix;
    },

    _getTextInputState: function (definition, problems, currentAnswers) {
      var preferredMode = this._getStoredIdentInputMode(definition);
      var supported = this._supportsTextInputMode(definition);
      var hydrationAnswers = supported
        ? this._getRepresentableTextHydrationAnswers(currentAnswers)
        : null;
      var representable = hydrationAnswers !== null;
      var enabled = supported && representable;

      return {
        supported: supported,
        enabled: enabled,
        preferredMode: preferredMode,
        effectiveMode: enabled && preferredMode === "text" ? "text" : "dropdown",
        hydrationAnswers: hydrationAnswers || [],
      };
    },

    _getIdentInputMode: function (definition, problems, currentAnswers) {
      if (!problems) {
        problems = this._getVisibleIdentificationProblems(definition);
      }
      if (!currentAnswers) {
        currentAnswers = this._getVisibleIdentificationAnswers(problems);
      }
      return this._getTextInputState(definition, problems, currentAnswers).effectiveMode;
    },

    _setIdentInputMode: function (mode) {
      if (mode !== "dropdown" && mode !== "text") {
        return;
      }

      try {
        localStorage.setItem(this._IDENT_INPUT_MODE_KEY, mode);
      } catch (e) {}
    },

    _buildInputComponent: function (
      containerEl,
      problems,
      feedbackMode,
      onAnswer,
      currentAnswers
    ) {
      var self = this;
      return new TextInput({
        containerEl: containerEl,
        problems: problems,
        problemCount: problems.length,
        analysisType: this.exerciseContext.getDefinition().getAnalysisType(),
        feedbackMode: feedbackMode,
        onAnswer: onAnswer,
        onSubmit: function () {
          self.onSubmitIdentification();
        },
        currentAnswers: currentAnswers,
        initialAnswers: currentAnswers,
      });
    },

    _getVisibleIdentificationProblems: function (definition) {
      return this.exerciseContext.getVisibleProblems
        ? this.exerciseContext.getVisibleProblems()
        : definition.getProblems();
    },

    _getIdentificationInputContainer: function () {
      var $container = $("#ident-input-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-input-container" class="ident-input-container"></div>');
        $("#identification-actions").after($container);
      }
      return $container;
    },

    _getVisibleIdentificationAnswers: function (problems) {
      var answers = [];
      var graderAnswers = this.exerciseContext.grader && this.exerciseContext.grader.answers;
      var pageOffset = this.exerciseContext.getIdentPageOffset
        ? this.exerciseContext.getIdentPageOffset()
        : 0;

      if (!graderAnswers) {
        return answers;
      }

      for (var i = 0; i < problems.length; i++) {
        var absoluteIndex = pageOffset + i;
        var value = graderAnswers[absoluteIndex];
        if (
          (value === undefined || value === null || value === "") &&
          graderAnswers[String(absoluteIndex)] !== undefined &&
          graderAnswers[String(absoluteIndex)] !== null &&
          graderAnswers[String(absoluteIndex)] !== ""
        ) {
          value = graderAnswers[String(absoluteIndex)];
        }
        if (value !== undefined && value !== null && value !== "") {
          answers[i] = value;
        }
      }

      return answers;
    },

    _getStoredIdentificationAnswer: function (problemIndex) {
      var graderAnswers = this.exerciseContext.grader && this.exerciseContext.grader.answers;
      if (!graderAnswers) {
        return undefined;
      }

      if (graderAnswers.hasOwnProperty(problemIndex)) {
        return graderAnswers[problemIndex];
      }

      if (graderAnswers.hasOwnProperty(String(problemIndex))) {
        return graderAnswers[String(problemIndex)];
      }

      return undefined;
    },

    _cloneIdentificationAnswers: function (answers) {
      var clone = [];
      if (!answers) {
        return clone;
      }

      for (var i = 0; i < answers.length; i++) {
        if (typeof answers[i] !== "undefined") {
          clone[i] = answers[i];
        }
      }

      return clone;
    },

    _serializeIdentificationAnswersForText: function (answers) {
      return _.filter(answers || [], function (answer) {
        return answer !== undefined && answer !== null && answer !== "";
      }).join(" ");
    },

    _hydrateTextInputComponent: function (component, currentAnswers) {
      if (!component) {
        return;
      }

      var answersClone = this._cloneIdentificationAnswers(currentAnswers);
      var serializedAnswers = this._serializeIdentificationAnswersForText(answersClone);

      if (component.settings) {
        component.settings.currentAnswers = answersClone;
        component.settings.initialAnswers = answersClone;
      }

      component._prevAnswers = answersClone;

      if (component._fieldEl && component._fieldEl.length) {
        if (document.activeElement === component._fieldEl[0]) {
          return;
        }
        component._fieldEl.val(serializedAnswers);
      }
    },

    _captureFocusedTextInput: function () {
      var component = this._inputComponent;
      if (!component || !component._fieldEl || !component._fieldEl.length) {
        return null;
      }
      var field = component._fieldEl[0];
      if (document.activeElement !== field) {
        return null;
      }
      return {
        value: component._fieldEl.val(),
        selectionStart: field.selectionStart,
        selectionEnd: field.selectionEnd,
      };
    },

    _restoreFocusedTextInput: function (snapshot) {
      var component = this._inputComponent;
      if (!snapshot || !component || !component._fieldEl || !component._fieldEl.length) {
        return;
      }
      var field = component._fieldEl[0];
      component._fieldEl.val(snapshot.value);
      component._fieldEl.focus();
      if (typeof field.setSelectionRange === "function" &&
          typeof snapshot.selectionStart === "number" &&
          typeof snapshot.selectionEnd === "number") {
        field.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
      }
    },

    _destroyIdentificationInputComponent: function () {
      if (this._inputComponent && this._inputComponent.destroy) {
        this._inputComponent.destroy();
      }
      this._inputComponent = null;
      this._identInputSignature = null;
      this._identInputMode = null;
    },

    _syncIdentificationInputComponent: function () {
      if (!this._isIdentificationLikeExercise()) {
        return;
      }

      var definition = this.exerciseContext.getDefinition();
      var problems = this._getVisibleIdentificationProblems(definition);
      var currentAnswers = this._getVisibleIdentificationAnswers(problems);
      var textInputState = this._getTextInputState(definition, problems, currentAnswers);
      var feedbackMode = this._getActiveIdentificationMode();
      var inputMode = textInputState.effectiveMode;
      var analysisType = definition && definition.getAnalysisType
        ? definition.getAnalysisType()
        : "roman";
      var pageOffset = this.exerciseContext.getIdentPageOffset
        ? this.exerciseContext.getIdentPageOffset()
        : 0;
      var signature = [inputMode, analysisType, feedbackMode, pageOffset, problems.length].join(":");
      var $container = this._getIdentificationInputContainer();
      var self = this;

      if (inputMode !== "text" || !problems.length) {
        $container.hide().empty();
        this._destroyIdentificationInputComponent();
        return;
      }

      $container
        .removeClass("ident-input-dropdown")
        .addClass("ident-input-text")
        .css("display", "block");

      if (!this._inputComponent || this._identInputSignature !== signature) {
        this._destroyIdentificationInputComponent();
        this._inputComponent = this._buildInputComponent(
          $container,
          problems,
          feedbackMode,
          function (problemIndex, label) {
            self._applyIdentificationAnswer(pageOffset + problemIndex, label);
          },
          currentAnswers
        );
        this._inputComponent.render();
        this._identInputSignature = signature;
      }

      this._identInputMode = inputMode;
      this._hydrateTextInputComponent(this._inputComponent, textInputState.hydrationAnswers);
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
    /**
     * Chorale mode setup: ensure grader is initialized; keep display settings
     */
    initChoraleMode: function () {
      var def = this.exerciseContext.getDefinition();
      var display = def && def.getDisplay ? def.getDisplay() : {};
      var configuredMaxMeasures = parseInt(display && display.maxMeasures, 10);
      var maxMeasures = configuredMaxMeasures > 0 ? configuredMaxMeasures : 4;
      this._chorale = { maxMeasures: maxMeasures, startMeasure: 0 };
      console.log("[Chorale] initChoraleMode called");
      try {
        var score = def.getScore ? def.getScore() : null;
        console.log("[Chorale] score keys:", score ? Object.keys(score) : "null", "has umto:", !!(score && score.umto));
        if (score && score.umto && !ChordalProblemsLogic.shouldPreserveChordalMeasures(score)) {
          var converted = UMTOScoreConverter.convertUMTOToProcessedScore(score.umto);
          if (converted) {
            def.exercise.score = converted;
            console.log("[Chorale] Patched exercise.score from UMTO conversion:", converted.measures ? converted.measures.length : 0, "measures");
          }
        }
        if (def.isChorale && def.isChorale() && this.exerciseContext.grader && this.exerciseContext.grader.initFromDefinition) {
          this.exerciseContext.grader.initFromDefinition(def);
        }
      } catch (e) {
        console.error("[Chorale] initChoraleMode ERROR:", e && e.message, e);
      }
    },
    /**
     * Renders the grand staff and everything on it.
     *
     * @return this
     */
    render: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;
      if (this._isIdentificationLikeExercise()) {
        this._refreshIdentificationModeUI();
      }
      this.clear();
      this.renderStaves(exercise_midi_nums);
      this.renderExerciseStatus();
      if (this._isIdentificationLikeExercise()) {
        this.renderExerciseText();
      }
      this.clearGhostNote();

      // Playback controls — only for chorale exercise types (idempotent)
      var definition = this.exerciseContext.getDefinition();
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        var $toolbar = $("#staff-toolbar");
        if ($toolbar.length) {
          var self = this;
          renderPlaybackControls($toolbar, this.scorePlayer, function () {
            return self._calculatePlaybackOffsets();
          });
        }
      }
      this._calculatePlaybackOffsets();
      this.autoScroll();

      // Simple Debug Overlay
      if (window.location.search.indexOf('debug=1') !== -1) {
        this._renderDebugOverlay();
      }

      return this;
    },

    _buildHarmonizationPending: function () {
      var clickComp = this._clickNoteComponent;
      if (!clickComp || typeof clickComp.getPending !== "function") return null;
      var pending = clickComp.getPending();
      if (!pending || !pending.length) return null;
      var col = clickComp.getActiveColumn ? clickComp.getActiveColumn() : null;
      pending = pending.slice().sort(function (a, b) { return a.midi - b.midi; });
      var measureIndex = col ? col.measureIndex : 0;
      var measureTotalTicks = this._measureTotalTicks();
      var onsetWithinMeasure = col && typeof col.onset === "number"
        ? col.onset - (measureIndex * measureTotalTicks)
        : 0;
      return [{
        measureIndex: measureIndex,
        onset: Math.max(0, onsetWithinMeasure),
        // Pending click notes are a placement preview, not rhythmic notation.
        // Always use the same half-note overlay path; whole-note tickables can
        // recenter visually and make the clicked note appear to move/disappear.
        durationTicks: 2048,
        midiNotes: pending.map(function (n) { return n.midi; }),
        spellings: pending.map(function (n) {
          return { step: n.step, alter: n.alter, octave: n.octave };
        }),
      }];
    },

    _buildHarmonizationRejected: function () {
      var ctx = this.exerciseContext;
      var rejected = ctx && ctx._harmonizationRejected;
      if (!rejected || !rejected.spellings || !rejected.spellings.length) return null;
      var midiNotes = rejected.midi || [];
      if (!midiNotes.length) return null;
      return [{
        measureIndex: rejected.measureIndex || 0,
        onset: Math.max(0, rejected.onset || 0),
        durationTicks: 2048,
        midiNotes: midiNotes,
        spellings: rejected.spellings,
      }];
    },

    _measureTotalTicks: function () {
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore ? definition.getScore() : null;
      var meta = (score && score.meta) || {};
      var tsRaw = meta.time || meta.meter || meta.time_signature || "4/4";
      var tsParts = String(tsRaw).split("/");
      var numerator = parseInt(tsParts[0], 10) || 4;
      var denominator = parseInt(tsParts[1], 10) || 4;
      return numerator * (4096 / denominator);
    },

    setClickNoteComponent: function (comp) {
      this._clickNoteComponent = comp;
    },

    getStaffLayout: function () {
      return this._staffLayout || null;
    },

    setInputSourceMode: function (mode) {
      this._inputSourceMode = mode;
    },

    _ghostCanvas: function () {
      var base = this.el && this.el[0] ? this.el[0] : null;
      if (!base) return null;
      var overlay = this._ghostCanvasEl;
      if (!overlay) {
        overlay = document.createElement("canvas");
        overlay.className = "js-ghost-overlay";
        overlay.style.position = "absolute";
        overlay.style.pointerEvents = "none";
        overlay.style.left = base.offsetLeft + "px";
        overlay.style.top = base.offsetTop + "px";
        if (base.parentNode) {
          var ps = window.getComputedStyle(base.parentNode);
          if (ps.position === "static") base.parentNode.style.position = "relative";
          base.parentNode.appendChild(overlay);
        }
        this._ghostCanvasEl = overlay;
      }
      if (overlay.width !== base.width) overlay.width = base.width;
      if (overlay.height !== base.height) overlay.height = base.height;
      overlay.style.width = base.style.width || (base.width + "px");
      overlay.style.height = base.style.height || (base.height + "px");
      overlay.style.left = base.offsetLeft + "px";
      overlay.style.top = base.offsetTop + "px";
      return overlay;
    },

    drawGhostNote: function (resolved) {
      this._ghost = resolved || null;
      var overlay = this._ghostCanvas();
      if (!overlay) return;
      var c2d = overlay.getContext("2d");
      if (!c2d) return;
      c2d.clearRect(0, 0, overlay.width, overlay.height);
      if (this._ghost && this._staffLayout) this._drawGhostGlyph(c2d, this._ghost);
    },

    clearGhostNote: function () {
      this._ghost = null;
      if (!this._ghostCanvasEl) return;
      var c2d = this._ghostCanvasEl.getContext("2d");
      if (c2d) c2d.clearRect(0, 0, this._ghostCanvasEl.width, this._ghostCanvasEl.height);
    },

    _drawGhostGlyph: function (c2d, ghost) {
      if (!c2d || !this._staffLayout || !ghost || !ghost.column) return;
      var sys = (this._staffLayout.systems || [])[ghost.column.systemIndex]
        || (this._staffLayout.systems || [])[0];
      if (!sys) return;
      var stave = (sys.staves || []).filter(function (s) { return s.clef === ghost.staveClef; })[0]
        || sys.staves[0];
      if (!stave) return;
      var y = stave.topLineY + ghost.stepsFromTop * (stave.lineSpacing / 2);
      c2d.save();
      c2d.fillStyle = "#b0b8c4";
      c2d.beginPath();
      c2d.ellipse(ghost.column.centerX, y, 6, 4.5, 0, 0, 2 * Math.PI);
      c2d.fill();
      c2d.restore();
    },
    
    _renderDebugOverlay: function () {
      $('#id-debug-overlay').remove();
      var problems = this.exerciseContext.getDefinition().getProblems();
      var overlay = $('<div id="id-debug-overlay" style="position:fixed; top:10px; right:10px; background:rgba(0,0,0,0.8); color:white; padding:10px; font-size:10px; z-index:9999; max-height:80vh; overflow-y:auto; border-radius:5px; font-family:monospace;"></div>');
      overlay.append('<h3 style="margin:0 0 10px 0;">UMTO Logic Auditor</h3>');
      var table = $('<table border="1" style="border-collapse:collapse; width:100%;"><tr><th>Idx</th><th>Off</th><th>Ans</th><th>Tgt</th></tr></table>');
      _.each(problems, function(p, i) {
        var row = $('<tr></tr>');
        row.append('<td style="padding:2px;">'+i+'</td>');
        row.append('<td style="padding:2px;">'+p.onset.toFixed(2)+'</td>');
        row.append('<td style="padding:2px;">'+p.answer+'</td>');
        row.append('<td style="padding:2px;">'+(p.hidden?'No':'Yes')+'</td>');
        table.append(row);
      });
      overlay.append(table);
      $('body').append(overlay);
    },
    /**
     * Renders textual prompt for the exercise.
     *
     * @return this
     */
    renderExerciseStatus: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $statusEl = $("#exercise-status-and-tempo");
      var $passedEl = $("#passed-status");
      var statusTpl = _.template(
        // not called: time_to_complete and more
        `<p><span id="exercise-status" class="status-pill" style="background-color:<%= status_color %>"><%= status_text %></span></p>
                <% if (typeof(tempo_mean) !== "undefined" && tempo_mean != "" && typeof(tempo_rating) !== "undefined" && typeof(tempo_display_factor) !== "undefined") { %>
                    <p>Tempo&nbsp;<%= ["", "erratic", "unsteady", "steady", "very&nbsp;steady", "perfectly&nbsp;steady"][tempo_rating.length] %> at <%= Math.round(tempo_mean * tempo_display_factor) %>&nbsp;b.p.m.</p>
                <% } %>`
      );
      var passedTpl = `<span class="status-pill" id="exercise-passed-status">Exercise Passed</span>`;
      // the tempo verbiage above should match what is separately coded for my activity
      var html = "";
      var tpl_data = {};

      var status_map = {};
      status_map[exc.STATE.READY] = {
        text: "Ready",
        color: "#333333",
      };
      status_map[exc.STATE.WAITING] = {
        text: "Keep going",
        color: "#FF7F00",
      };
      status_map[exc.STATE.INCORRECT] = {
        text: "Fix the error",
        color: "#990000",
      };
      status_map[exc.STATE.FINISHED] = {
        text: "Go again",
        color: "#FFB700",
      };
      status_map[exc.STATE.CORRECT] = {
        text: "Passed",
        color: "#4C9900",
      };

      tpl_data.exercise_list = exc.definition.getExerciseList();
      tpl_data.exercise_num = tpl_data.exercise_list.reduce(function (
        selected,
        current,
        index
      ) {
        return selected < 0 && current.selected ? index + 1 : selected;
      },
      -1);
      tpl_data.status_text = status_map[exc.state].text;
      tpl_data.status_color = status_map[exc.state].color;

      $(".playlist-nav-links").css("display", "none");
      if ( // HOW DOES THIS WORK
        $("#playlist-passed-status").length == 0 &&
        definition.settings.definition.exerciseIsPerformed &&
        definition.settings.definition.exerciseErrorCount == 0
      ) {
        $passedEl.html(passedTpl);
      } else {
        $("#exercise-passed-status").hide();
      }
      switch (exc.state) {
        case exc.STATE.CORRECT:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
            tpl_data.tempo_display_factor = 1;
            try {
              // get beat information from time signature
              const time_sig = definition.exercise.timeSignature;
              const time_sig_numerator = Number(time_sig.split("/")[0]);
              let tempo_display_factor = Number(time_sig.split("/")[1]);
              if (time_sig_numerator > 3 && time_sig_numerator % 3 == 0) {
                // compound meter
                tempo_display_factor /= 3;
              }
              if (!isNaN(tempo_display_factor)) {
                tpl_data.tempo_display_factor = tempo_display_factor;
              }
            } catch (error) {
              console.log("Unable to retrieve beat value from time signature");
            }
          }
          // If this is the last exercise, display the nav links
          if (!this.exerciseContext.definition.exercise.nextExercise)
            $(".playlist-nav-links").css("display", "inline-flex");
          break;
        case exc.STATE.FINISHED:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
          }
          break;
        case exc.STATE.READY:
        default:
          break;
      }

      html = statusTpl(tpl_data);
      $statusEl.html(html);
      return this;
    },
    renderExerciseInfo: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $infoEl = $("#exercise-info");
      var tpl = _.template(
        `<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>
          <p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>
        <% } %>`
      );
      var html = "";
      var tpl_data = {};

      if (exc.definition.exercise.performing_course) {
        tpl_data.exercise_list = exc.definition.getExerciseList();
        tpl_data.exercise_num = 1;
        for (let i = 0; i < tpl_data.exercise_list.length; i++) {
          if (tpl_data.exercise_list[i].selected) {
            tpl_data.exercise_num = i + 1;
            break;
          }
        }
      } else {
        // get ID?
      }

      html = tpl(tpl_data);
      $infoEl.html(html);

      return this;
    },
    renderExerciseText: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $textEl = $("#exercise-text");
      var tpl = _.template(
        `<% if (typeof(prompt_text) == "string") { %>
                    <%= prompt_text %>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      var promptText = exc.definition.getExerciseText
        ? exc.definition.getExerciseText()
        : (exc.definition.getIntro ? exc.definition.getIntro() : "");
      var analysisType = definition && definition.getAnalysisType
        ? definition.getAnalysisType()
        : "roman";
      var inputMode = this._isIdentificationLikeExercise && this._isIdentificationLikeExercise()
        ? this._getIdentInputMode(definition)
        : "dropdown";
      if (
        inputMode === "text" &&
        (analysisType === "interval_generic" || analysisType === "interval_specific")
      ) {
        promptText = "Input the intervals in this text box with a space between them.";
      }

      tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(promptText);

      html = tpl(tpl_data);

      // Append page indicator for paged identification exercises
      if (this._isIdentificationLikeExercise && this._isIdentificationLikeExercise()) {
        var totalPages = exc.getTotalIdentPages ? exc.getTotalIdentPages() : 1;
        if (totalPages > 1) {
          var currentPage = exc.getIdentPage ? exc.getIdentPage() : 0;
          html += '<span class="page-indicator" style="margin-left:1em;color:#888;font-size:0.9em;">Page ' + (currentPage + 1) + ' of ' + totalPages + '</span>';
        }
      }

      $textEl.html(html);

      return this;
    },
    renderExerciseHistory: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $historyEl = $("#exercise-history");
      var tpl = _.template(
        `<% if (false && is_performed && typeof(latest_err_count) == "integer" && latest_err_count == 0) { %>
                    <p>PASSED on most recent attempt</p>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      $.ajax({
        type: "GET",
        url:
          window.location.origin +
          "/ajax" +
          window.location.pathname +
          "history/",
        async: false,
        success: function (response) {
          if (!response["valid"]) {
            var exerciseData = JSON.parse(response);
            tpl_data.is_performed = exerciseData.exerciseIsPerformed;
            tpl_data.latest_err_count = exerciseData.exerciseErrorCount;
          }
        },
        error: function (error) {
          alert("An error occurred while getting the exercise history.");
        },
      });

      html = tpl(tpl_data);
      $historyEl.html(html);

      return this;
    },
    /**
     * Clears the sheet.
     *
     * @return this
     */
    clear: function () {
      this.vexRenderer.getContext().clear();
      return this;
    },
    /**
     * Renders each individual stave.
     *
     * @return this
     */
    renderStaves: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore();
      var isHarmonization = !!(definition.isHarmonization && definition.isHarmonization());
      var isChoraleLike = (definition.isChorale() || definition.isChoraleIdentification() || isHarmonization);
      
      // If it's a UMTO chorale, always re-convert to ensure splitting is fresh and uses MeasureEngine.
      // This fixes cases where the database might have a single 'blob' measure.
      if (isChoraleLike && score && score.umto && !ChordalProblemsLogic.shouldPreserveChordalMeasures(score)) {
        score = UMTOScoreConverter.convertUMTOToProcessedScore(score.umto);
      }

      var hasMeasures = !!(score && score.measures && score.measures.length > 0);
      
      // Ensure score has metadata for VexFlowAdapter
      if (score && hasMeasures) {
        score.metadata = score.metadata || {};
        if (score.metadata.meter && !score.metadata.time) score.metadata.time = score.metadata.meter;
        if (!score.metadata.time) score.metadata.time = "4/4";
      }

      
      // Use VexFlow adapter for chorale exercises
      if (isChoraleLike && hasMeasures) {
        if (score && score.measures && score.measures.length > 0) {
          var self = this;
          this._identWindowLayout = {};
          this._identWindowLayoutByOnset = {};
          this._updateChoraleViewport(score);
          var canvas = this.el[0];
          var ctx = this.vexRenderer.getContext();
          var display = definition.getDisplay() || {};
          var analyzeConfig = _.cloneDeep(this.getAnalyzeConfig() || {});
          var _analysisType = definition.getAnalysisType ? definition.getAnalysisType() : null;
          if (_analysisType === "figured_bass" || _analysisType === "figured_bass_unabbreviated") {
            analyzeConfig.roman_numerals = false;
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.mode.roman_numerals = false;
          }
          var wantsRomans = !!display.showRomans;
          var wantsFigures = !!display.showFigures;
          var wantsChordLabels = !!display.showChordLabels;
          var wantsScaleDegrees = !!display.showScaleDegrees;
          var isAnalysisMatchMode = !!(definition.isAnalysisMatch && definition.isAnalysisMatch());
          var wantsNoteNames = !!display.showNoteNames || isAnalysisMatchMode;
          var isChoraleIdentification = this._isChoraleIdentificationExercise();


          // In chorale identification mode the figures/Romans ARE the student's
          // answers — rendering them via VexFlow would spoil the exercise.
          // The identification overlay draws "?" slots instead.
          if (isChoraleIdentification) {
            wantsRomans = false;
            wantsFigures = false;
            wantsChordLabels = false;
            wantsScaleDegrees = false;
            wantsNoteNames = false;
            analyzeConfig.enabled = false;
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.mode.roman_numerals = false;
            analyzeConfig.mode.thoroughbass = false;
            analyzeConfig.mode.chord_labels = false;
            analyzeConfig.mode.scale_degrees = false;
            analyzeConfig.mode.note_names = false;
          }

          if (isHarmonization) {
            analyzeConfig.enabled = true;
            analyzeConfig.mode = analyzeConfig.mode || {};
            if (definition.getAnalysisType && (definition.getAnalysisType() === "figured_bass" || definition.getAnalysisType() === "figured_bass_unabbreviated")) {
              analyzeConfig.mode.thoroughbass = true;
            } else {
              analyzeConfig.mode.roman_numerals = true;
            }
          }

          var wantsAnalysis = wantsRomans || wantsFigures || wantsChordLabels || wantsScaleDegrees || wantsNoteNames;

          // Preserve legacy chorale behavior that force-enables roman numerals,
          // but do not force overlays for chorale_identification.
          if (!wantsAnalysis && definition.isChorale && definition.isChorale() && !isAnalysisMatchMode && !isChoraleIdentification) {
            wantsRomans = true;
            wantsAnalysis = true;
          }
          // Ensure analysis renderer is not suppressed
          if (!display.analysisRenderer) {
            display.analysisRenderer = 'notater';
          }
          if (wantsAnalysis) {
            analyzeConfig.enabled = true;
            analyzeConfig.mode = analyzeConfig.mode || {};
            if (wantsRomans) {
              analyzeConfig.mode.roman_numerals = true;
            }
            if (wantsFigures) {
              analyzeConfig.mode.thoroughbass = true;
              if (display.figureStyle === "figures_abbrev") {
                analyzeConfig.mode.abbreviate_thoroughbass = true;
              }
            }
            if (wantsChordLabels) {
              analyzeConfig.mode.chord_labels = true;
            }
            if (wantsScaleDegrees) {
              analyzeConfig.mode.scale_degrees = true;
              // scale_degrees is mutually exclusive with roman_numerals/note_names/thoroughbass.
              // The inherited analyzeConfig from ANALYSIS_SETTINGS may have those enabled;
              // silence them so renderScaleDegrees isn't blocked in vexflow_adapter.
              if (!wantsRomans) analyzeConfig.mode.roman_numerals = false;
              if (!wantsFigures) analyzeConfig.mode.thoroughbass = false;
              if (!wantsNoteNames) analyzeConfig.mode.note_names = false;
            }
            if (wantsNoteNames) {
              analyzeConfig.mode.note_names = true;
            }
            if (!wantsRomans) {
              analyzeConfig.roman_numerals = false;
              analyzeConfig.mode.roman_numerals = false;
            }
          }

          // Play Authoring Phase B: if the exercise stored explicit {above, below} slots,
          // project them onto mode flags so the notater/adapter light up the right zones.
          // This block only runs when a stored slot directive is present (play-authored
          // exercises); legacy exercises have no top-level data.analyzeConfig so storedSlots
          // is null and the block is skipped entirely — no regression risk.
          var storedSlots = (definition.exercise && definition.exercise.analyzeConfig) || null;
          if (storedSlots && (storedSlots.above || storedSlots.below)) {
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.enabled = true;
            if (storedSlots.below === "roman_numerals" || storedSlots.below === "roman_numerals_exp") analyzeConfig.mode.roman_numerals = true;
            if (storedSlots.below === "thoroughbass") analyzeConfig.mode.thoroughbass = true;
            if (storedSlots.above === "scale_degrees") analyzeConfig.mode.scale_degrees = true;
            if (storedSlots.above === "note_names") analyzeConfig.mode.note_names = true;
          }

          var startMeasure =
            (this._chorale && typeof this._chorale.startMeasure === "number"
              ? this._chorale.startMeasure
              : 0);
          var staffYOffset = 20;
          var playedNoteIdsForRender =
            (this.exerciseContext && this.exerciseContext.grader && this.exerciseContext.grader.getPlayedNoteIds)
              ? this.exerciseContext.grader.getPlayedNoteIds()
              : null;

          // In chorale-identification mode, render all notation in black from the start.
          if (isChoraleIdentification) {
            playedNoteIdsForRender = new Set();
            _.each(ScoreTimeline.buildTimeline(score) || [], function (ev) {
              if (ev && typeof ev.id === 'number') {
                playedNoteIdsForRender.add(ev.id);
              }
            });
          }

          // For harmonization: compute selectVoices once (used for both timeline and render).
          var harmonizationSelectVoices = null;
          if (isHarmonization) {
            var lv = definition.exercise && definition.exercise.score && definition.exercise.score.umto
              ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
              : ["B"];
            function lockedVoiceIndex(staffName, preferredIndex) {
              var firstMeasure = score && score.measures && score.measures[0];
              var staff = firstMeasure && firstMeasure.staves && firstMeasure.staves[staffName];
              var voices = staff && staff.voices ? staff.voices : [];
              if (voices.length > preferredIndex) return preferredIndex;
              if (voices.length === 1) return 0;
              return preferredIndex;
            }
            var hvTreble = [], hvBass = [];
            if (lv.indexOf("S") !== -1) hvTreble.push(lockedVoiceIndex("treble", 0));
            if (lv.indexOf("A") !== -1) hvTreble.push(lockedVoiceIndex("treble", 1));
            if (lv.indexOf("T") !== -1) hvBass.push(lockedVoiceIndex("bass", 0));
            if (lv.indexOf("B") !== -1) hvBass.push(lockedVoiceIndex("bass", 1));
            harmonizationSelectVoices = { treble: hvTreble, bass: hvBass };
          }

          // For harmonization: bass notes at accepted target offsets turn black.
          // Build timeline with same selectVoices as renderer so IDs align.
          var harmonizationRealizationPayload = null;
          if (isHarmonization && this.exerciseContext) {
            var acceptedPtr = this.exerciseContext._harmonizationPointer || 0;
            var harmTargets = definition.getHarmonizationTargets ? definition.getHarmonizationTargets() : [];
            var acceptedOffsetTicks = {};
            for (var ai = 0; ai < acceptedPtr && ai < harmTargets.length; ai++) {
              var tOff = harmTargets[ai].offset;
              if (typeof tOff === "number") {
                acceptedOffsetTicks[Math.round(tOff * 1024)] = true;
              }
            }
            playedNoteIdsForRender = new Set();
            _.each(ScoreTimeline.buildTimeline(score, { selectVoices: harmonizationSelectVoices }) || [], function (ev) {
              if (ev && typeof ev.id === 'number' && acceptedOffsetTicks[ev.onset]) {
                playedNoteIdsForRender.add(ev.id);
              }
            });
            var accepted = this.exerciseContext.acceptedHarmonizationSonorities || [];
            var tsRaw = (score.meta && (score.meta.time || score.meta.meter || score.meta.time_signature)) || "4/4";
            var tsParts = String(tsRaw).split("/");
            var meter = {
              numerator: parseInt(tsParts[0], 10),
              denominator: parseInt(tsParts[1], 10)
            };
            harmonizationRealizationPayload = HarmonizationRealizationLogic.buildRealization(
              accepted,
              harmTargets,
              score,
              meter
            );
          }

          VexFlowAdapter.render(score, this.vexRenderer, {
            width: canvas.width,
            height: canvas.height,
            maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,
            startMeasure: startMeasure,
            playedNoteIds: playedNoteIdsForRender,
            showNotation: display.showNotation !== undefined ? display.showNotation : true,
            hideKeyLabel: !!display.hideKeyLabel,
            firstMeasureExtraWidth: parseInt(display.firstMeasureExtraWidth, 10) || 0,
            noteXShift: parseInt(display.noteXShift, 10) || 0,
            voiceColors: display.voiceColors || null,
            // Analysis wiring for chorale path (Notater bridge inside adapter)
            analyzeConfig: analyzeConfig,

            // Always use the definition's already-converted KeySignature model.
            // score.meta.key is raw (e.g. "C") and may not be a valid HL key string.
            keySignature: this.keySignature,
            analysisRenderer: display.analysisRenderer || "notater", // notater|adapter|none
            staffYOffset: staffYOffset,
            isAnalysisMatch: isAnalysisMatchMode,
            isHarmonization: isHarmonization,
            harmonizationTargets: isHarmonization ? (definition.getHarmonizationTargets ? definition.getHarmonizationTargets() : []) : null,
            harmonizationRealization: isHarmonization ? harmonizationRealizationPayload : null,
            harmonizationPending: isHarmonization ? self._buildHarmonizationPending() : null,
            harmonizationRejected: isHarmonization ? self._buildHarmonizationRejected() : null,
            lockedVoices: isHarmonization && definition.exercise && definition.exercise.score && definition.exercise.score.umto
              ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
              : null,
            selectVoices: harmonizationSelectVoices,
            analysisType: definition.getAnalysisType ? definition.getAnalysisType() : null,
            onStaffLayout: function (layout) { self._staffLayout = layout; },
            onWindowPosition: function (slot) {
              if (!slot || typeof slot.windowIndex !== "number") {
                return;
              }
              console.log("[ID] onWindowPosition received:", slot.windowIndex, slot.x, slot.y);
              self._identWindowLayout[slot.windowIndex] = slot;
              // Index by "measureIndex:pageLocalOnset" for cross-page playback highlight lookup.
              // The adapter emits absolute measureIndex and page-local onset.
              if (slot.measureIndex !== null && slot.measureIndex !== undefined && slot.onset !== null && slot.onset !== undefined) {
                self._identWindowLayoutByOnset[slot.measureIndex + ":" + slot.onset] = slot;
              }
            },
          });
          console.log("[ID] VexFlowAdapter.render finished.");



          if (this._isIdentificationLikeExercise()) {
            this.drawIdentificationLabels();
          }
        }
        return this;
      }
      
      // Legacy rendering for non-chorale exercises
      console.log("[ID] Using Legacy Renderer (FALLBACK)");
      const show_barlines = true;

      var i,
        len,
        stave,
        _staves = this.staves;
      var _barlines = this.barlines;
      for (i = 0, len = _staves.length; i < len; i++) {
        stave = _staves[i];
        const exercise_view_bool = true;
        const append_barline = _barlines.indexOf(i) != -1 && show_barlines;
        stave.render(exercise_midi_nums, exercise_view_bool, append_barline);
      }

      if (this._isIdentificationLikeExercise()) {
        this.drawIdentificationLabels();
      }

      return this;
    },
    /**
     * Adjusts which measures are displayed for chorale exercises as the user advances.
     */
    _updateChoraleViewport: function (score) {
      if (
        !this._chorale ||
        !score ||
        !score.measures ||
        !score.measures.length
      ) {
        return;
      }
      // During playback page turns, honour the override and skip grader-based calculation.
      if (this._playbackOverridePage !== null && this._playbackOverridePage !== undefined) {
        this._chorale.startMeasure = this._playbackOverridePage;
        return;
      }
      var totalMeasures = score.measures.length;
      var maxMeasures = this._chorale.maxMeasures || 4;
      if (totalMeasures <= maxMeasures) {
        this._chorale.startMeasure = 0;
        return;
      }
      var activeMeasure = 0;
      // For chorale_identification, page index comes from exerciseContext directly.
      // For chorale (play-through), it comes from the grader.
      var context = this.exerciseContext;
      if (context && typeof context.getIdentPageOffset === "function" && this._isChoraleIdentificationExercise()) {
        if (typeof context.getIdentPage === "function") {
          var page = context.getIdentPage();
          activeMeasure = Math.max(0, Math.min(page * maxMeasures, totalMeasures - 1));
        }
      } else {
        var grader = context && context.grader;
        if (grader && typeof grader.getActiveMeasureIndex === "function") {
          var idx = grader.getActiveMeasureIndex();
          if (typeof idx === "number" && !isNaN(idx)) {
            activeMeasure = Math.max(0, Math.min(idx, totalMeasures - 1));
          }
        }
      }
      var block = Math.floor(activeMeasure / maxMeasures);
      var desiredStart = block * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (desiredStart > lastPossibleStart) {
        desiredStart = lastPossibleStart;
      }
      if (desiredStart < 0) {
        desiredStart = 0;
      }
      if (this._chorale.startMeasure !== desiredStart) {
        this._chorale.startMeasure = desiredStart;
      }
    },
    /**
     * Resets the staves.
     *
     * @return this
     */
    resetStaves: function () {
      this.staves = [];
      this.barlines = [];
      return this;
    },
    /**
     * Adds staves.
     *
     * @param {array} staves
     * @return this
     */
    addStaves: function (staves) {
      this.staves = this.staves.concat(staves);
      return this;
    },

    /**
     * Updates and configures the staves.
     *
     * @return this
     */
    updateStaves: function () {
      var chord, treble, bass;
      var limit = 100; // arbitrary
      let bankSize = CHORD_BANK_SIZE;
      try {
        const custom_chord_bank_size = parseInt(this.getSemibrevesPerLine());
        if (
          typeof custom_chord_bank_size === "number" &&
          custom_chord_bank_size > 0
        ) {
          bankSize = custom_chord_bank_size;
        }
      } catch {
        console.log(
          "Failed to retrieve getSemibrevesPerLine property from Exercise definion."
        );
      }
      var display_items = this.getDisplayChords().items({
        limit: limit,
        reverse: false,
      });
      var exercise_items = this.getExerciseChords().items({
        limit: limit,
        reverse: false,
      });
      var staves = [];
      var barlines = [];
      var index = 0;
      var offset = 0;
      var count = display_items.length;
      var position = {
        index: index,
        count: count,
        offset: offset,
        maxCount: bankSize,
      };
      var display_chord;
      var exercise_chord;
      var treble_activeAlterations = Object.create(null);
      var bass_activeAlterations = Object.create(null);
      const timeSignature = this.getTimeSignature();
      const barlineSpace = 0.25; // relative to width of whole note

      // scrolling exercise view
      var scroll_exercise = false;
      var pageturns = [0];

      let rhythmValues = display_items.map((item) => item.chord._rhythmValue);
      let availableSpace = bankSize;

      const endOfBarWholeNoteCounts = [];
      if (timeSignature) {
        const wholeNoteSum = rhythmValues
          .map((item) => BarlineSpacingUtils.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        const barCount = BarlineSpacingUtils.countElapsedBars(timeSignature, wholeNoteSum);
        const ts = BarlineSpacingUtils.timeSignatureParsed(timeSignature);
        for (var i = 1, len = barCount; i <= len; i++) {
          endOfBarWholeNoteCounts.push((i * ts[0]) / ts[1]);
        }
      }

      for (var i = 0, len = rhythmValues.length; i < len; i++) {
        let neededSpace = BarlineSpacingUtils.getVisualWidth(rhythmValues[i]);

        let elapsedWholeNotes = rhythmValues
          .slice(0, i + 1)
          .map((item) => BarlineSpacingUtils.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        if (endOfBarWholeNoteCounts.includes(elapsedWholeNotes)) {
          neededSpace += barlineSpace;
        }
        if (neededSpace > availableSpace) {
          availableSpace = bankSize - neededSpace; // overlap space
          pageturns.push(i);
          scroll_exercise = true;
        }
        availableSpace -= neededSpace;
      }

      let previous_whole_note_count = 0;
      if (scroll_exercise) {
        let cursor = this.getInputChords()._currentIndex;
        var page_start = pageturns
          .filter(function (x, idx) {
            return x <= cursor;
          })
          .pop();
        var next_page =
          pageturns.filter(function (x, idx) {
            return x > cursor;
          })[0] || false;
        if (page_start > 0) {
          // create overlap (start new page with completed chord)
          page_start -= 1;
          // next_page -= 1; //unwise
        }

        position.offset = page_start;
        const previous_items = display_items.slice(0, page_start);

        if (next_page) {
          display_items = display_items.slice(page_start, next_page);
          exercise_items = exercise_items.slice(page_start, next_page);
        } else {
          display_items = display_items.slice(page_start);
          exercise_items = exercise_items.slice(page_start);
        }

        for (var i = 0, len = previous_items.length; i < len; i++) {
          let rhythm_value = null;
          if (previous_items[i].chord.settings.rhythm) {
            rhythm_value = previous_items[i].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          previous_whole_note_count += BarlineSpacingUtils.getWholeNoteCount(rhythm_value);
        }
      }

      // The first bar is a special case: it's reserved to show the
      // clef and key signature and nothing else.
      let first_page = true;
      if (previous_whole_note_count > 0) {
        first_page = false;
      }
      treble = this.createDisplayStave("treble", _.clone(position), first_page);
      bass = this.createDisplayStave("bass", _.clone(position), first_page);
      position.index += 1;
      treble.connect(bass);
      staves.push(treble);

      var treble_alterationHistory = Object.create(null);
      var bass_alterationHistory = Object.create(null);

      // now add the staves for showing the notes
      for (var i = 0, len = display_items.length; i < len; i++) {
        let elapsedWidthUnits = 0;
        let elapsedWholeNotes = 0;
        let extraWidth = 0;
        for (var j = 0; j < i; j++) {
          var rhythm_value = null;
          if (display_items[j].chord.settings.rhythm) {
            rhythm_value = display_items[j].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          elapsedWidthUnits += BarlineSpacingUtils.getVisualWidth(rhythm_value);
          elapsedWholeNotes += BarlineSpacingUtils.getWholeNoteCount(rhythm_value);
        }

        // spacing for barlines
        const complement_of_first_bar = BarlineSpacingUtils.getWholeNoteRemainder(
          timeSignature,
          previous_whole_note_count
        );
        const elapsedBarlines = BarlineSpacingUtils.countElapsedBars(
          timeSignature,
          elapsedWholeNotes + complement_of_first_bar - 0.01
        );
        if (elapsedBarlines) {
          elapsedWidthUnits += barlineSpace * elapsedBarlines;
        }

        // now take account of previous music for proper barring
        elapsedWholeNotes += previous_whole_note_count;

        var curr_value = null;
        if (display_items[i].chord.settings.rhythm) {
          curr_value = display_items[i].chord.settings.rhythm;
        } else {
          curr_value = DEFAULT_RHYTHM_VALUE;
        }
        if (i < len) {
          if (BarlineSpacingUtils.getsBarline(timeSignature, elapsedWholeNotes)) {
            if (i > 0) {
              // new bar begins here but not new system
              // draw barline at left
              barlines.push(i + 1);
              // add space to left of barline
              elapsedWidthUnits += barlineSpace;
            }
            // RESET # n b
            treble_activeAlterations = Object.create(null);
            bass_activeAlterations = Object.create(null);
          }
          if (
            BarlineSpacingUtils.getsBarline(
              timeSignature,
              elapsedWholeNotes + BarlineSpacingUtils.getWholeNoteCount(curr_value)
            )
          ) {
            // bar is completed here: add space
            extraWidth += barlineSpace;
          }
        }

        treble_alterationHistory[i] = treble_activeAlterations;
        bass_alterationHistory[i] = bass_activeAlterations;

        display_chord = display_items[i].chord;
        exercise_chord = exercise_items[i].chord;
        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          treble_activeAlterations,
          extraWidth
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          bass_activeAlterations,
          extraWidth
        );
        position.index += 1;
        treble.connect(bass);
        staves.push(treble);

        let treble_merged = {
          ...treble_activeAlterations,
          ...treble.noteFactory.bequestAlterations,
        };
        let treble_cancellations = treble.noteFactory.bequestCancellations;
        for (let j = 0, len_j = treble_cancellations.length; j < len_j; j++) {
          delete treble_merged[treble_cancellations[j]];
        }
        treble_activeAlterations = treble_merged;

        let bass_merged = {
          ...bass_activeAlterations,
          ...bass.noteFactory.bequestAlterations,
        };
        let bass_cancellations = bass.noteFactory.bequestCancellations;
        for (let j = 0, len_j = bass_cancellations.length; j < len_j; j++) {
          delete bass_merged[bass_cancellations[j]];
        }
        bass_activeAlterations = bass_merged;
      }

      treble.noteFactory.alterationHistory = treble_alterationHistory;
      bass.noteFactory.alterationHistory = bass_alterationHistory;

      this.resetStaves();
      this.addStaves(staves);
      this.barlines = barlines;

      return this;
    },
    /**
     * Creates a stave to display the clef, key signature, etc.
     *
     * @param {string} clef
     * @param {object} position
     * @return {Stave}
     */
    createDisplayStave: function (clef, position, first_page = true) {
      var stave = new Stave(clef, position);
      var stave_notater = this.createStaveNotater(clef, {
        stave: stave,
        keySignature: this.keySignature,
        analyzeConfig: this.getAnalyzeConfig(),
      });

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      if (first_page && BarlineSpacingUtils.timeSignatureParsed(this.timeSignature)) {
        // console.log(this.timeSignatureParsed(this.timeSignature).join('/'));
        stave.setTimeSignature(
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature).join("/")
        );
      } else {
        stave.setTimeSignature(false);
      }
      stave.setNotater(stave_notater);
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePosition();

      return stave;
    },
    /**
     * Creates a stave to display notes.
     *
     * @param {string} clef
     * @param {object} position
     * @param {Chord} chord
     * @return {Stave}
     */
    createNoteStave: function (
      clef,
      position,
      displayChord,
      exerciseChord,
      elapsedWidthUnits,
      activeAlterations,
      extraWidth = 0
    ) {
      var stave = new Stave(clef, position);
      var widthUnits = null;
      if (exerciseChord.settings.rhythm) {
        var rhythm_value = exerciseChord.settings.rhythm;
        if (rhythm_value == null) {
          rhythm_value = DEFAULT_RHYTHM_VALUE;
        }
        widthUnits = BarlineSpacingUtils.getVisualWidth(rhythm_value) + extraWidth;
      }

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      // timeSignature not required here
      // stave.setFirstBarWidth(this.keySignature);
      stave.setNoteFactory(
        new ExerciseNoteFactory({
          clef: clef,
          chord: displayChord,
          keySignature: this.keySignature,
          highlightConfig: this.getHighlightConfig(),
          activeAlterations: activeAlterations,
        })
      );
      stave.setNotater(
        this.createStaveNotater(clef, {
          stave: stave,
          chord: exerciseChord,
          keySignature: this.keySignature,
          analyzeConfig: this.getAnalyzeConfig(),
        })
      );
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePositionWithRhythm(widthUnits, elapsedWidthUnits);
      stave.updateAlterations(activeAlterations);

      return stave;
    },
    /**
     * Creates an instance of StaveNotater.
     *
     * @param {string} clef The clef, treble|bass, to create.
     * @param {object} config The config for the StaveNotater.
     * @return {object}
     */
    createStaveNotater: function (clef, config) {
      return StaveNotater.create(clef, config);
    },
    /**
     * Returns the width of the sheet.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.el.width();
    },
    /**
     * Returns the height of the sheet.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.el.height();
    },
    /**
     * Returns the analysis settings of the sheet.
     *
     * @return {object}
     */
    getAnalyzeConfig: function () {
      return this.parentComponent.analyzeConfig;
    },
    /**
     * Returns the highlight settings of the sheet.
     *
     * @return {object}
     */
    getHighlightConfig: function () {
      return this.parentComponent.highlightConfig;
    },
    /**
~     * Returns the chords for display.
     *
     * @return undefined
     */
    getDisplayChords: function () {
      return this.exerciseContext.getDisplayChords();
    },
    /**
     * Returns the chords for exercise analysis.
     *
     * @return undefined
     */
    getExerciseChords: function () {
      return this.exerciseContext.getExerciseChords();
    },
    /**
     * Returns the time signature for display.
     *
     * @return undefined
     */
    getTimeSignature: function () {
      return this.exerciseContext.getTimeSignature();
    },
    /**
     * Obtain semibreves per line for horizontal scaling.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.exerciseContext.getSemibrevesPerLine();
    },
    /**
     * Returns the input chords.
     *
     * @return undefined
     */
    getInputChords: function () {
      return this.exerciseContext.getInputChords();
    },
    /**
     * Handles a chord bank update.
     *
     * @return undefined
     */
    onChordsUpdate: function () {
      var definition = this.exerciseContext.getDefinition();
      // Chorale exercises don't use chord bank, so skip this
      if (definition.isChorale()) return;
      
      this.updateStaves();
      this.render();
    },
    /**
     * Calculates onset-to-measure mapping and page-start offsets for the current score.
     * Populate _playbackMeasureTickOffset so autoScroll and highlights work reliably.
     */
    _calculatePlaybackOffsets: function () {
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore ? definition.getScore() : null;
      if (!score) return null;

      var tl = ScoreTimeline.buildTimeline(score);
      var measureStarts = ScoreTimeline.buildMeasureOffsets
        ? ScoreTimeline.buildMeasureOffsets(score)
        : [];
      var onsetSeen = {};
      var order = [];
      var measureOffset = {};

      for (var i = 0; i < tl.length; i++) {
        var ev = tl[i];
        if (!onsetSeen[ev.onset]) {
          onsetSeen[ev.onset] = { measureIndex: ev.measureIndex };
          order.push(ev.onset);
        }
      }
      order.sort(function (a, b) { return a - b; });

      if (measureStarts && measureStarts.length) {
        for (var measureIndex = 0; measureIndex < measureStarts.length; measureIndex++) {
          measureOffset[measureIndex] = measureStarts[measureIndex];
        }
      }

      this._playbackWindowOnsets = order.slice();
      this._playbackWindowMeasures = order.map(function (onset) { return onsetSeen[onset].measureIndex; });
      this._playbackMeasureTickOffset = measureOffset;

      return tl;
    },
    /**
     * Handle MIDI note events in chorale and harmonization modes.
     */
    onMidiNote: function (state, noteNum) {
      var definition = this.exerciseContext.getDefinition();
      var isChorale = definition.isChorale && definition.isChorale();
      var isHarmonization = definition.isHarmonization && definition.isHarmonization();
      if (!isChorale && !isHarmonization) return;

      // Start timer on first interaction
      if (state === "on") {
        this.exerciseContext.triggerTimer();
      }

      if (isHarmonization) {
        if (this._inputSourceMode === "click") {
          return;
        }
        // New noteOn clears any red rejected-state overlay from a prior incorrect attempt.
        if (state === "on" && this.exerciseContext._harmonizationRejected) {
          this.exerciseContext._harmonizationRejected = null;
        }
        var ctx = this.exerciseContext;
        var tracker = ctx._harmonizationHeldTracker;
        if (tracker) {
          if (state === "on") {
            tracker.noteOn(noteNum);
          } else if (state === "off") {
            tracker.noteOff(noteNum, Date.now());
          }
        }
        var self = this;
        var settleMs = ctx._harmonizationChordSettleMs || 150;
        if (ctx._harmonizationSettleTimer) {
          clearTimeout(ctx._harmonizationSettleTimer);
        }
        ctx._harmonizationSettleTimer = setTimeout(function () {
          ctx._harmonizationSettleTimer = null;
          ctx.grade();
          self.render();
        }, settleMs);
        return;
      }

      var grader = this.exerciseContext.grader;
      if (!grader) return;
      if (state === "on" && typeof grader.noteOn === "function") {
        grader.noteOn(noteNum);
      } else if (state === "off" && typeof grader.noteOff === "function") {
        grader.noteOff(noteNum);
      }

      // Run the standard grading pipeline (handles state + auto-advance)
      this.exerciseContext.grade();

      // Repaint with updated highlights
      var playedIds = grader.getPlayedNoteIds ? grader.getPlayedNoteIds() : new Set();
      var idArray = [];
      playedIds.forEach(function(id) { idArray.push(id); });
      this.render();
      this.autoScroll();
    },

    /**
     * Automatically scrolls the sheet horizontally to keep the current active note in view.
     */
    autoScroll: function () {
      var grader = this.exerciseContext.grader;
      if (!grader || typeof grader.getActiveIndex !== "function") return;
      
      var windowIdx = grader.getActiveIndex();
      if (windowIdx === null || windowIdx === undefined) return;

      var globalOnset = grader.timeline && grader.timeline[windowIdx] && grader.timeline[windowIdx].onset;
      if (globalOnset === undefined) return;

      // Use the same coordinate mapping as playback highlight
      var measureIdx = grader.getMeasureIndexForWindow ? grader.getMeasureIndexForWindow(windowIdx) : 0;
      var targetStart = Math.floor(measureIdx / 4) * 4;
      var pageStartTick = (this._playbackMeasureTickOffset && this._playbackMeasureTickOffset[targetStart]) || 0;
      var pageLocalOnset = globalOnset - pageStartTick;
      var cacheKey = measureIdx + ":" + pageLocalOnset;

      var slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
      if (slot && slot.x) {
        var $container = $("#staffwrapper");
        if (!$container.length) {
          $container = this.el.parent();
        }
        
        var scrollLeft = $container.scrollLeft();
        var containerWidth = $container.width();
        var noteX = slot.x;

        // padding to keep some context
        var padding = 100;
        
        // If note is near the right edge or beyond, scroll it into view
        if (noteX > scrollLeft + containerWidth - padding) {
          $container.stop().animate({ scrollLeft: noteX - containerWidth + padding + 200 }, 300);
        } else if (noteX < scrollLeft + padding) {
          $container.stop().animate({ scrollLeft: Math.max(0, noteX - padding) }, 300);
        }
      }
    },
    /**
     * Handles navigating to the next exercise.
     *
     * @return undefined
     */
    onGoToExercise: function (target) {
      window.location = target.url;
    },
    /**
     * Handles the pristine/refresh button click.
     * Resets chorale state and exercise context.
     *
     * @return undefined
     */
    onClickPristine: function () {
      var definition = this.exerciseContext.getDefinition();

      // Reset chorale state if in chorale mode
      if (definition.isChorale()) {
        this.initChoraleMode();
      }

      // Reset harmonization state
      if (definition.isHarmonization && definition.isHarmonization()) {
        var ctx = this.exerciseContext;
        if (ctx._harmonizationSettleTimer) {
          clearTimeout(ctx._harmonizationSettleTimer);
          ctx._harmonizationSettleTimer = null;
        }
        if (ctx._harmonizationHeldTracker) {
          ctx._harmonizationHeldTracker.reset();
        }
        ctx._harmonizationPointer = 0;
        ctx.acceptedHarmonizationSonorities = [];
        ctx._harmonizationRejected = null;
        ctx.harmonizationVLScore = null;
        ctx.harmonizationTier = null;
      }

      // Reset exercise context state
      this.exerciseContext.done = false;
      this.exerciseContext.sealed = false;
      this.exerciseContext.state = this.exerciseContext.STATE.READY;

      // Re-render
      this.render();
      this.renderExerciseStatus();
    },

    _drawPlaybackHighlight: function () {
      var idx = this._playbackWindowIndex;
      if (idx === null || idx === undefined) return;
      if (!this._playbackWindowOnsets) return;

      var globalOnset = this._playbackWindowOnsets && this._playbackWindowOnsets[idx];
      if (globalOnset === undefined) return;
      var measureIdx = this._playbackWindowMeasures && this._playbackWindowMeasures[idx];
      if (measureIdx === undefined) return;

      var maxMeasures = (this._chorale && this._chorale.maxMeasures) || 4;
      var targetStart = Math.floor(measureIdx / maxMeasures) * maxMeasures;

      // Convert global onset → page-local onset by subtracting the tick at page start.
      var pageStartTick = this._playbackMeasureTickOffset && this._playbackMeasureTickOffset[targetStart];
      if (pageStartTick === undefined) return;
      var pageLocalOnset = globalOnset - pageStartTick;
      var cacheKey = measureIdx + ":" + pageLocalOnset;

      // Navigate to the correct page if this window is not on the current rendered page.
      var slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
      if (!slot && this._chorale) {
        if (targetStart !== this._chorale.startMeasure) {
          // Set flag so _updateChoraleViewport doesn't clobber our target page.
          this._playbackOverridePage = targetStart;
          this._chorale.startMeasure = targetStart;
          this.render(); // synchronously repopulates _identWindowLayoutByOnset
          this._playbackOverridePage = null;
          slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
        }
      }
      if (!slot) return;

      var canvas = this.el[0];
      var canvasOffset = $(canvas).offset();
      var w = 30;
      var h = slot.y;  // bassStave.getBottomY() + 18
      var left = canvasOffset.left + slot.x - w / 2;
      var top = canvasOffset.top;

      var $hl = $("#playback-highlight");
      if (!$hl.length) {
        $hl = $('<div id="playback-highlight">').css({
          position: "fixed",
          pointerEvents: "none",
          background: "rgba(79, 172, 254, 0.15)",
          border: "1px solid rgba(79, 172, 254, 0.35)",
          boxSizing: "border-box",
          zIndex: 10,
        });
        $("body").append($hl);
      }

      $hl.css({ left: left, top: top, width: w, height: h }).show();
    },

    _clearPlaybackHighlight: function () {
      $("#playback-highlight").hide();
    },
  });

  return ExerciseSheetComponent;
});
