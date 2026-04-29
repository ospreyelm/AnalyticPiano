define([
  "jquery",
  "lodash",
  "app/components/component",
], function ($, _, Component) {
  "use strict";

  /**
   * LabelInputComponent
   *
   * Renders one <select> dropdown per problem, positioned under each chord
   * on the staff.  The caller is responsible for calling updatePositions()
   * after VexFlow has drawn the staves so each select can be centred under
   * its corresponding chord.
   *
   * @constructor
   * @param {object}   settings
   * @param {jQuery}   settings.containerEl - Absolutely-positioned container div.
   * @param {array}    settings.problems    - Array of problem objects with .choices.
   * @param {function} settings.onAnswer    - Callback fn(problemIndex, label).
   */
  var LabelInputComponent = function (settings) {
    this.settings = settings || {};
    this.containerEl = this.settings.containerEl;
    this.problems = this.settings.problems || [];
    this.onAnswer = this.settings.onAnswer || function () {};
    this.selects = [];
  };

  LabelInputComponent.prototype = new Component();

  _.extend(LabelInputComponent.prototype, {
    initComponent: function () {
      // no-op — render() is called explicitly from exercise_sheet.js
    },

    /**
     * Creates one <select> per problem and appends them to containerEl.
     */
    render: function () {
      var self = this;
      this.containerEl.empty();
      this.selects = [];

      _.each(this.problems, function (problem, i) {
        var sel = $("<select></select>").addClass("chord-id-select");
        sel.append($("<option></option>").val("").text("—"));
        _.each(problem.choices, function (choice) {
          sel.append($("<option></option>").val(choice).text(choice));
        });
        sel.on("change", function () {
          self.onAnswer(i, $(this).val());
        });
        self.selects.push(sel);
        self.containerEl.append(sel);
      });

      return this;
    },

    /**
     * Positions each select under the centre of its chord stave.
     *
     * stave.start_x / stave.width are in canvas pixel coordinates.
     * #chord-dropdowns overlays #staffwrapper, not the canvas itself, so we
     * must add the canvas's offset within staffwrapper to translate.
     *
     * @param {array}  staves   - exercise_sheet.staves (treble staves; staves[0] is display stave)
     * @param {jQuery} canvasEl - The <canvas id="staff"> element
     */
    updatePositions: function (staves, canvasEl) {
      var noteStaves = staves.slice(1); // skip the clef/key-signature display stave
      if (noteStaves.length !== this.selects.length) {
        return;
      }

      // canvas offset relative to #staffwrapper (its offsetParent)
      var canvasOffsetLeft = canvasEl[0].offsetLeft || 0;
      var canvasOffsetTop  = canvasEl[0].offsetTop  || 0;

      for (var i = 0; i < noteStaves.length; i++) {
        var treble = noteStaves[i];
        var center = Math.round(canvasOffsetLeft + treble.start_x + treble.width / 2);

        var top = canvasOffsetTop + 10; // fallback
        try {
          var bassStave = treble.connectedStave;
          if (bassStave && bassStave.staffSegment) {
            top = Math.round(canvasOffsetTop + bassStave.staffSegment.getBottomY()) + 8;
          }
        } catch (e) { /* ignore */ }

        this.selects[i].css({ left: center + "px", top: top + "px" });
      }
    },

    /**
     * Marks each select correct/incorrect after a Submit.
     *
     * @param {array} gradedProblems - Array of {answer, chosen, correct} objects.
     */
    showResults: function (gradedProblems) {
      for (var i = 0; i < gradedProblems.length; i++) {
        var sel = this.selects[i];
        if (!sel) { continue; }
        var p = gradedProblems[i];
        sel.removeClass("id-correct id-incorrect id-unanswered");
        if (!p.chosen) {
          sel.addClass("id-unanswered");
        } else if (p.correct) {
          sel.addClass("id-correct");
        } else {
          sel.addClass("id-incorrect");
        }
      }
    },

    /**
     * Disables the selects for problems that are already correct so the
     * student only has to fix the wrong ones.
     *
     * @param {array} gradedProblems
     */
    lockCorrect: function (gradedProblems) {
      for (var i = 0; i < gradedProblems.length; i++) {
        if (gradedProblems[i] && gradedProblems[i].correct && this.selects[i]) {
          this.selects[i].prop("disabled", true);
        }
      }
    },

    /**
     * Tears down rendered DOM and event handlers so the component can be
     * discarded or replaced without leaving orphaned selects behind.
     */
    destroy: function () {
      _.each(this.selects, function (sel) {
        if (!sel) { return; }
        sel.off();
        sel.remove();
      });

      this.selects = [];
      this.containerEl = null;
      this.problems = null;
      this.onAnswer = null;
      this.settings = null;
    }
  });

  return LabelInputComponent;
});
