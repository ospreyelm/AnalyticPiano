define([
  "jquery",
  "lodash",
  "app/components/component",
], function ($, _, Component) {
  "use strict";

  /**
   * LabelInputComponent
   *
   * @constructor
   * @param {object} settings
   * @param {jQuery} settings.el - The container element.
   * @param {array} settings.choices - Initial array of label strings.
   * @param {function} settings.onSelect - Callback fn(label).
   */
  var LabelInputComponent = function (settings) {
    this.settings = settings || {};
    this.el = this.settings.el;
    this.choices = this.settings.choices || [];
    this.onSelect = this.settings.onSelect || function () {};

    this.buttons = {};
    this.isWait = false;
  };

  LabelInputComponent.prototype = new Component();

  _.extend(LabelInputComponent.prototype, {
    initComponent: function () {
      // render() is called explicitly by exercise_sheet.js after construction.
      // initComponent() is a no-op here; it exists only to satisfy the Component contract.
    },

    /**
     * Clears the container and renders a button for each choice string.
     *
     * @param {array} choices
     */
    render: function (choices) {
      if (typeof choices !== "undefined") {
        this.choices = choices;
      }
      
      this.el.empty();
      this.el.css("display", "flex");
      this.buttons = {};
      this.isWait = false;

      var self = this;
      _.each(this.choices, function (label) {
        var btn = $("<button></button>")
          .addClass("label-choice-btn")
          .text(label);

        btn.on("click", function (e) {
          e.preventDefault();
          if (self.isWait) {
            return;
          }

          btn.addClass("selected");
          self.isWait = true;
          self.onSelect(label);
        });

        self.buttons[label] = btn;
        self.el.append(btn);
      });

      return this;
    },

    /**
     * Shows the result of the selection.
     *
     * @param {string} label 
     * @param {boolean} correct 
     */
    showResult: function (label, correct) {
      var btn = this.buttons[label];
      if (!btn) {
        return;
      }

      var self = this;
      btn.removeClass("selected");

      if (correct) {
        btn.addClass("correct");
        // Exercise will advance via advance() manually, leaving the button in the correct state
        // until then. No timeout needed to re-enable them.
      } else {
        btn.addClass("incorrect");
        setTimeout(function () {
          btn.removeClass("incorrect");
          self.isWait = false;
        }, 800);
      }
    },

    /**
     * Resets for the next problem.
     *
     * @param {array} newChoices 
     */
    advance: function (newChoices) {
      this.render(newChoices);
    }
  });

  return LabelInputComponent;
});
