define([
  "lodash",
  "jquery",
  "app/components/component",
  "app/models/symbolic_meter_rendering_logic",
], function (_, $, Component, SymbolicMeterRenderingLogic) {
  "use strict";

  var SymbolicQuestionSheet = function (settings) {
    Component.call(this, settings || {});
    this.settings = settings || {};
    this.exerciseContext = this.settings.exerciseContext;
  };

  SymbolicQuestionSheet.prototype = new Component();

  _.extend(SymbolicQuestionSheet.prototype, {
    initComponent: function () {},

    destroy: function () {
      return this;
    },

    renderTo: function (el) {
      var definition = this.exerciseContext.getDefinition();
      var problems = definition.getProblems() || [];
      var grader = this.exerciseContext.grader;
      var $el = $(el);

      $el.empty().addClass("symbolic-meter-area");

      _.each(problems, function (problem, idx) {
        var promptText = problem.prompt ? problem.prompt.text : "";
        var promptHtml = problem.prompt && problem.prompt.kind === "time_signature"
          ? SymbolicMeterRenderingLogic.renderTimeSignatureMarkup(promptText)
          : promptText;

        var $card = $('<div class="symbolic-meter-card"></div>');
        $card.append($('<div class="symbolic-meter-prompt"></div>').html(promptHtml));
        var $choices = $('<div class="symbolic-meter-choices"></div>');

        _.each(problem.choices || [], function (choice) {
          var $btn = $('<button type="button" class="symbolic-meter-choice simple-button"></button>').text(choice);
          $btn.on("click", function () {
            grader.setAnswer(idx, choice);
            this.exerciseContext.trigger("change");
          }.bind(this));
          $choices.append($btn);
        }.bind(this));

        $card.append($choices);
        $el.append($card);
      }.bind(this));
    },
  });

  return SymbolicQuestionSheet;
});
