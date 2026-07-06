import _ from "lodash";

export default  {
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
      if (definition && definition.exercise && definition.exercise.inputModeFixed === "dropdown") {
        return false;
      }
      if (definition && (
        (typeof definition.isChoraleIdentification === "function" && definition.isChoraleIdentification()) ||
        // eslint-disable-next-line harmonylab-pipelines/no-raw-pipeline-discriminator -- permanent exemption (Phase 1.3): routing to resolved.isChorale would widen this gate from type=umto_chorale to legacy type=chorale (behavior change, proven by the Phase 1.2 reviewer pass). Raw umto_chorale guard preserved verbatim; no ResolvedMode field names exactly this type-narrow predicate.
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

    _getActiveIdentificationMode: function () {
      return this.exerciseContext.sessionMode ||
        this.exerciseContext.settings.identMode ||
        this._currentMode ||
        "submit";
    },
  };
