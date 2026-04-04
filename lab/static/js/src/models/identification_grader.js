/* global define: false */
define([
  "lodash"
], function (_) {
  "use strict";

  var INCORRECT = "incorrect";
  var CORRECT = "correct";
  var PARTIAL = "partial";

  var IdentificationGrader = function (settings) {
    this.settings = settings || {};
    this.reset();
  };

  IdentificationGrader.STATE = {
    INCORRECT: INCORRECT,
    CORRECT: CORRECT,
    PARTIAL: PARTIAL,
  };

  _.extend(IdentificationGrader.prototype, {
    STATE: IdentificationGrader.STATE,

    reset: function () {
      this.answers = {};  // { problemIndex: label }
    },

    initFromDefinition: function (definition) {
      this.reset();
      return this;
    },

    setAnswer: function (problemIndex, label) {
      this.answers[problemIndex] = label;
    },

    grade: function (definition) {
      var problems = definition.getProblems();
      var gradedProblems = [];
      var allAnswered = true;
      var allCorrect = true;

      for (var i = 0; i < problems.length; i++) {
        var answer = problems[i].answer;
        var chosen = this.answers.hasOwnProperty(i) ? this.answers[i] : null;
        var correct = (chosen !== null && chosen !== '') ? (chosen === answer) : null;

        if (!chosen) { allAnswered = false; }
        if (correct !== true) { allCorrect = false; }

        gradedProblems.push({ answer: answer, chosen: chosen, correct: correct });
      }

      var resultState = (allAnswered && allCorrect) ? CORRECT : (allAnswered ? INCORRECT : PARTIAL);
      var score = (allAnswered && allCorrect) ? 0 : (allAnswered ? 2 : 1);

      return {
        result: resultState,
        score: score,
        activeIndex: null,
        problems: gradedProblems
      };
    }
  });

  return IdentificationGrader;
});
