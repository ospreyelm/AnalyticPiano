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
  };
});
