import logic from "app/models/key_sig_exercise_logic";
import Vex from "vexflow";
import $ from "jquery";

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

    function shuffle(arr) {
      var a = arr.slice();
      for (var i = a.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
      }
      return a;
    }

    var KeySigExercise = function (definition, options) {
      this.problems         = shuffle(definition.exercise.problems || []);
      this.index            = 0;
      this.mistakes         = 0;
      this._mistakeThisProblem = false;
      this._correctFirstTry    = 0;
      this.options          = options || {};
    };

    KeySigExercise.prototype = {
      start: function () { this._showProblem(); },

      _showProblem: function () {
        var p = this.problems[this.index];
        if (!p) return;
        if (this.options.staffContainer) {
          renderKeySignatureStaff(this.options.staffContainer, p.prompt);
        }
        this._renderChoices(p);
      },

      _renderChoices: function (p) {
        var self = this;
        var el = this.options.choicesEl;
        if (!el) return;
        $(el).empty();
        var shuffledChoices = shuffle(p.choices || []);
        shuffledChoices.forEach(function (label) {
          var btn = $('<button>')
            .addClass('key-sig-choice simple-button')
            .css({
              'font-size': '1.1em',
              'padding': '8px 18px',
              'border-radius': '6px',
              'cursor': 'pointer',
            })
            .text(label);
          btn.on('click', function () {
            self._handleChoice(label);
          });
          $(el).append(btn);
        });
      },

      _handleChoice: function (label) {
        var p = this.problems[this.index];
        if (!p) return;
        // Submit the display_name directly — it IS in accepted_answers
        var result = this.submit(label);
        if (result && !result.correct) {
          if (this.options.onWrong) {
            this.options.onWrong("Not quite — try again.");
          }
          // Briefly flash the wrong button red
          var self = this;
          $(this.options.choicesEl).find('.key-sig-choice').filter(function () {
            return $(this).text() === label;
          }).css('background-color', '#fdd').one('transitionend click', function () {
            $(this).css('background-color', '');
          });
          setTimeout(function () {
            $(self.options.choicesEl).find('.key-sig-choice').css('background-color', '');
          }, 600);
        }
      },

      submit: function (rawAnswer) {
        var p = this.problems[this.index];
        if (!p) return;
        if (!logic.checkKeyAnswer(rawAnswer, p)) {
          this.mistakes++;
          this._mistakeThisProblem = true;
          return { correct: false, message: "Try again." };
        }
        if (!this._mistakeThisProblem) {
          this._correctFirstTry++;
        }
        this._mistakeThisProblem = false;
        this.index++;
        if (this.index >= this.problems.length) {
          if (this.options.onComplete) {
            this.options.onComplete({
              score: this.mistakes === 0 ? 0 : 1,
              numerator: this._correctFirstTry,
              denominator: this.problems.length,
            });
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

export default {
  KeySigExercise: KeySigExercise
};
