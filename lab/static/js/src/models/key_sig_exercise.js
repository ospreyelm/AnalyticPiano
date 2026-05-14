/* global define: false */
define(
  ["app/models/key_sig_exercise_logic", "vexflow", "jquery"],
  function (logic, Vex, $) {
    "use strict";

    var SHARPS_KEY = ["C", "G", "D", "A", "E", "B", "F#", "C#"];
    var FLATS_KEY  = ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"];

    function renderKeySignatureStaff(container, prompt) {
      $(container).empty();
      var VF = Vex.Flow;
      var renderer = new VF.Renderer(container, VF.Renderer.Backends.SVG);
      renderer.resize(200, 120);
      var context = renderer.getContext();
      var stave = new VF.Stave(10, 20, 160);
      stave.addClef("treble");

      var vexKey;
      if ((prompt.sharps || 0) > 0) {
        vexKey = SHARPS_KEY[prompt.sharps];
      } else if ((prompt.flats || 0) > 0) {
        vexKey = FLATS_KEY[prompt.flats];
      } else {
        vexKey = "C";
      }
      stave.addKeySignature(vexKey);
      stave.setContext(context).draw();
    }

    var KeySigExercise = function (definition, options) {
      this.problems = definition.exercise.problems || [];
      this.index    = 0;
      this.mistakes = 0;
      this.options  = options || {};
    };

    KeySigExercise.prototype = {
      start: function () { this._showProblem(); },

      _showProblem: function () {
        var p = this.problems[this.index];
        if (!p) return;
        if (this.options.staffContainer) {
          renderKeySignatureStaff(this.options.staffContainer, p.prompt);
        }
        if (this.options.inputEl) {
          $(this.options.inputEl).val("").focus();
        }
      },

      submit: function (rawAnswer) {
        var p = this.problems[this.index];
        if (!p) return;
        if (!logic.checkKeyAnswer(rawAnswer, p)) {
          this.mistakes++;
          return { correct: false, message: "Try again." };
        }
        this.index++;
        if (this.index >= this.problems.length) {
          if (this.options.onComplete) {
            this.options.onComplete({ score: this.mistakes === 0 ? 0 : 1 });
          }
        } else {
          if (this.options.onAdvance) {
            this.options.onAdvance({ index: this.index, total: this.problems.length });
          }
          this._showProblem();
        }
        return { correct: true };
      },
    };

    return { KeySigExercise: KeySigExercise };
  }
);
