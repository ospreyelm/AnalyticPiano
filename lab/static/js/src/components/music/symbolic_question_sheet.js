import _ from "lodash";
import $ from "jquery";
import Component from "app/components/component";
import SymbolicMeterRenderingLogic from "app/models/symbolic_meter_rendering_logic";
import {
  toolbarSlot,
  mountProgressContainer,
  showToolbarSepIfNeeded,
} from "app/components/music/identification_layout_targets";

var SymbolicQuestionSheet = function (settings) {
    Component.call(this, settings || {});
    this.settings = settings || {};
    this.exerciseContext = this.settings.exerciseContext;
    this._currentMode = this.exerciseContext.sessionMode || "submit";
  };

  SymbolicQuestionSheet.prototype = new Component();

  _.extend(SymbolicQuestionSheet.prototype, {
    initComponent: function () {},

    destroy: function () {
      $("#identification-submit").off(".symbolicmeter");
      $("#ident-mode-container").off(".symbolicmeter");
      return this;
    },

    renderTo: function (el) {
      this.$el = $(el);
      this.render();
    },

    _getVisibleProblems: function () {
      return this.exerciseContext.getVisibleProblems
        ? this.exerciseContext.getVisibleProblems()
        : (this.exerciseContext.getDefinition().getProblems() || []);
    },

    _getPageOffset: function () {
      return this.exerciseContext.getIdentPageOffset
        ? this.exerciseContext.getIdentPageOffset()
        : 0;
    },

    _syncModeState: function () {
      this._currentMode = this.exerciseContext.sessionMode || this._currentMode || "submit";
      return this._currentMode;
    },

    _bindActions: function () {
      var self = this;
      var $submitBtn = $("#identification-submit");
      $submitBtn.attr("type", "button");
      $submitBtn.off(".symbolicmeter").on("click.symbolicmeter", function () {
        self.exerciseContext.submitIdentPage({ fromUI: true, mode: self._currentMode });
        self.render();
      });
    },

    _renderModeToggle: function () {
      var self = this;
      var $container = $("#ident-mode-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-mode-container" class="ident-mode-toggle symbolic-mode-toggle"></div>');
        $container.appendTo(toolbarSlot());
        showToolbarSepIfNeeded();
      }
      $container.empty();
      if (this.exerciseContext.sealed || this._currentMode === "test") {
        return;
      }

      var $switch = $('<div class="mode-switch"></div>');
      _.each([
        { id: "practice", label: "Practice" },
        { id: "submit", label: "Submit" },
      ], function (mode) {
        var $opt = $('<div class="mode-option"></div>').text(mode.label);
        if (mode.id === self._currentMode) {
          $opt.addClass("active");
        }
        $opt.on("click.symbolicmeter", function () {
          if (self._currentMode === mode.id) {
            return;
          }
          self.exerciseContext.sessionMode = mode.id;
          self._currentMode = mode.id;
          self.exerciseContext.graded = null;
          self.render();
        });
        $switch.append($opt);
      });
      $container.append($switch);
    },

    _updateSubmitUI: function (answeredCount, totalCount) {
      var $actions = $("#identification-actions");
      var $btn = $("#identification-submit");
      $actions.show();

      if (this.exerciseContext.sealed) {
        $btn.hide();
        $("#ident-progress-container").hide();
        return;
      }

      if (this._currentMode !== "submit") {
        $btn.hide();
        $("#ident-progress-container").hide();
        return;
      }

      var $progContainer = $("#ident-progress-container");
      if ($progContainer.length === 0) {
        $progContainer = $('<div id="ident-progress-container" style="width: 250px; margin: 0 auto 15px; background: #e2e8f0; border-radius: 9999px; height: 6px; overflow: hidden; display: none;"><div id="ident-progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); transition: width 0.3s ease;"></div></div>');
        mountProgressContainer($progContainer);
      }

      var globalProblems = this.exerciseContext.getDefinition().getProblems() || [];
      var globalAnswers = (this.exerciseContext.grader && this.exerciseContext.grader.answers) || {};
      var globalAnswered = _.reduce(globalProblems, function (count, problem, idx) {
        if (problem.hidden) {
          return count;
        }
        return count + ((globalAnswers.hasOwnProperty(idx) && globalAnswers[idx] !== null && globalAnswers[idx] !== "") ? 1 : 0);
      }, 0);
      var globalVisible = _.filter(globalProblems, function (problem) { return !problem.hidden; });

      $progContainer.show();
      $("#ident-progress-bar").css("width", (globalVisible.length ? (globalAnswered / globalVisible.length) * 100 : 0) + "%");

      $btn.show();
      if (answeredCount >= totalCount && totalCount > 0) {
        var isLastPage = this.exerciseContext.getIdentPage() >= this.exerciseContext.getTotalIdentPages() - 1;
        $btn.text(isLastPage ? "Check" : "Next Page").addClass("ready");
      } else {
        $btn.text("Complete Analysis").removeClass("ready");
      }
    },

    _applyChoice: function (absoluteIndex, choice) {
      var definition = this.exerciseContext.getDefinition();
      var visibleProblems = this._getVisibleProblems();
      var pageOffset = this._getPageOffset();
      var grader = this.exerciseContext.grader;

      grader.setAnswer(absoluteIndex, choice);

      if (this._currentMode === "practice") {
        var graded = grader.grade(definition, visibleProblems, pageOffset);
        this.exerciseContext.graded = graded;
        this.render();
        if (graded.result === "correct") {
          setTimeout(_.bind(function () {
            this.exerciseContext.grade();
            this.render();
          }, this), 0);
        }
        return;
      }

      this.exerciseContext.graded = null;
      this.render();
    },

    render: function () {
      var definition = this.exerciseContext.getDefinition();
      var grader = this.exerciseContext.grader;
      var problems = this._getVisibleProblems();
      var pageOffset = this._getPageOffset();
      var gradedProblems = this.exerciseContext.graded && this.exerciseContext.graded.problems
        ? this.exerciseContext.graded.problems
        : [];

      this._syncModeState();
      this._bindActions();
      this._renderModeToggle();

      this.$el.empty().addClass("symbolic-meter-area");

      var answeredCount = 0;
      _.each(problems, function (problem, localIndex) {
        var absoluteIndex = pageOffset + localIndex;
        var promptText = problem.prompt ? problem.prompt.text : "";
        var promptHtml = problem.prompt && problem.prompt.kind === "time_signature"
          ? SymbolicMeterRenderingLogic.renderTimeSignatureMarkup(promptText)
          : _.escape(promptText);
        var chosen = grader.answers.hasOwnProperty(absoluteIndex)
          ? grader.answers[absoluteIndex]
          : null;
        var graded = gradedProblems[localIndex] || null;

        if (chosen) {
          answeredCount++;
        }

        var $card = $('<div class="symbolic-meter-card"></div>');
        $card.append($('<div class="symbolic-meter-prompt"></div>').html(promptHtml));

        if (graded && graded.correct === true) {
          $card.append($('<div class="symbolic-meter-feedback symbolic-meter-feedback-correct">Correct</div>'));
        } else if (graded && graded.correct === false) {
          $card.append($('<div class="symbolic-meter-feedback symbolic-meter-feedback-incorrect">Try again</div>'));
        }

        var $choices = $('<div class="symbolic-meter-choices"></div>');
        _.each(problem.choices || [], function (choice) {
          var $btn = $('<button type="button" class="symbolic-meter-choice simple-button"></button>').text(choice);
          if (chosen === choice) {
            $btn.addClass("selected");
          }
          if (graded && graded.correct === true && chosen === choice) {
            $btn.addClass("correct");
          } else if (graded && graded.correct === false && chosen === choice) {
            $btn.addClass("incorrect");
          }
          if (this.exerciseContext.sealed || (this._currentMode === "submit" && graded && graded.correct === true)) {
            $btn.prop("disabled", true);
          }
          $btn.on("click", _.bind(function () {
            this._applyChoice(absoluteIndex, choice);
          }, this));
          $choices.append($btn);
        }, this);

        $card.append($choices);
        this.$el.append($card);
      }, this);

      this._updateSubmitUI(answeredCount, problems.length);
      return this;
    },
  });

export default SymbolicQuestionSheet;
