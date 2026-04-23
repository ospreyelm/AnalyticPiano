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
      this.attemptCounts = {}; // { problemIndex: count }
      this.activeIndex = 0;
    },

    initFromDefinition: function (definition) {
      this.definition = definition;
      this.reset();
      return this;
    },

    setAnswer: function (problemIndex, label) {
      this.answers[problemIndex] = label;
      this.attemptCounts[problemIndex] = (this.attemptCounts[problemIndex] || 0) + 1;
      
      // Update activeIndex to the next unanswered question on this page
      var problems = this.definition.getProblems();
      var nextActive = problemIndex + 1;
      while (nextActive < problems.length && (problems[nextActive].hidden || this.answers.hasOwnProperty(nextActive))) {
        nextActive++;
      }
      if (nextActive < problems.length) {
        this.activeIndex = nextActive;
      }
    },

    getActiveMeasureIndex: function () {
      if (
        this.definition &&
        typeof this.definition.getIdentPageOffset === "function"
      ) {
        return this.definition.getIdentPageOffset();
      }
      return 0;
    },

    grade: function (definition, visibleProblems, pageOffset) {
      var problems = visibleProblems || definition.getProblems();
      if (typeof pageOffset !== "number") {
        pageOffset =
          definition && typeof definition.getIdentPageOffset === "function"
            ? definition.getIdentPageOffset()
            : 0;
      }
      var gradedProblems = [];
      var allAnswered = true;
      var allCorrect = true;

      for (var i = 0; i < problems.length; i++) {
        if (problems[i].hidden) {
          gradedProblems.push({ answer: problems[i].answer, chosen: null, correct: null, hidden: true });
          continue;
        }
        var absoluteIndex = pageOffset + i;
        var answer = problems[i].answer;
        var chosen = this.answers.hasOwnProperty(absoluteIndex)
          ? this.answers[absoluteIndex]
          : null;
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
