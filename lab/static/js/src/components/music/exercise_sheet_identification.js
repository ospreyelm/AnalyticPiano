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
  };
