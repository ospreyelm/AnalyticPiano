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
      this.pointer = 0;
      this.selections = [];
      this.mistakes = [];
      this.finished = false;
    },

    initFromDefinition: function (definition) {
      this.reset();
      var problems = definition.getProblems() || [];
      if (problems.length === 0) {
        this.finished = true;
      }
      return this;
    },

    selectLabel: function (label, definition) {
      if (this.finished) {
        return { correct: false, pointer: this.pointer, finished: true };
      }

      var problems = definition.getProblems();
      var currentProblem = problems[this.pointer];
      var isCorrect = (label === currentProblem.answer);

      this.selections[this.pointer] = label;
      this.mistakes[this.pointer] = !isCorrect;

      this.pointer += 1;

      if (this.pointer >= problems.length) {
        this.finished = true;
      }

      return {
        correct: isCorrect,
        pointer: this.pointer,
        finished: this.finished
      };
    },

    grade: function (definition) {
      var problems = definition.getProblems();
      var gradedProblems = [];
      var hasMistake = false;

      for (var i = 0; i < problems.length; i++) {
        var answer = problems[i].answer;
        var chosen = this.selections[i] !== undefined ? this.selections[i] : null;
        var correct = null;

        if (chosen !== null) {
          correct = !this.mistakes[i];
          if (!correct) {
            hasMistake = true;
          }
        }

        gradedProblems.push({
          answer: answer,
          chosen: chosen,
          correct: correct
        });
      }

      var resultState = PARTIAL;
      var score = 1;

      if (this.finished) {
        if (hasMistake) {
          resultState = INCORRECT;
          score = 2;
        } else {
          resultState = CORRECT;
          score = 0;
        }
      } else {
        resultState = PARTIAL;
        score = 1;
      }

      return {
        result: resultState,
        score: score,
        activeIndex: this.pointer,
        problems: gradedProblems
      };
    }
  });

  return IdentificationGrader;
});
