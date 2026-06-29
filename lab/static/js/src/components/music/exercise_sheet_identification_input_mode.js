import $ from "jquery";
import $UI from "jquery-ui";
import _ from "lodash";
import Vex from "vexflow";
import Config from "app/config";
import Analyze from "app/utils/analyze";
import EVENTS from "app/components/events";
import Component from "app/components/component";
import FontParser from "app/utils/fontparser";
import Stave from "./stave";
import StaveNotater from "./stave_notater";
import ExerciseNoteFactory from "./exercise_note_factory";
import VexFlowAdapter from "./rendering/vexflow_adapter";
import ScoreTimeline from "./score_timeline";
import TextInput from "app/components/input/text_input";
import ScorePlayer from "app/models/score_player";
import IdentificationSubmitFlow from "app/models/identification_submit_flow_logic";
import KeyContext from "app/models/key_context_logic";
import renderPlaybackControls from "app/components/music/playback_controls";
import MeasureEngine from "app/utils/measure_engine";
import HarmonizationRealizationLogic from "app/models/harmonization_realization_logic";
import IdentificationLabelLayoutLogic from "app/components/music/identification_label_layout_logic";
import ChordalProblemsLogic from "app/models/chordal_problems_logic";
import ChordalUMTOStaffDistribution from "./chordal_umto_staff_distribution";
import KeySignature from "app/models/key_signature";
import ChordalSpelling from "./chordal_spelling";
import ChordalBarlinesLogic from "app/utils/chordal_barlines_logic";
import UMTOScoreConverter from "app/utils/umto_score_converter";
import BarlineSpacingUtils from "app/utils/barline_spacing_utils";

export default  {


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
