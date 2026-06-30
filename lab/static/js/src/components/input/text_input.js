import $ from "jquery";
import _ from "lodash";
import Component from "app/components/component";

var VALID_NOTE_RE = /^([a-g])(#{1,2}|b{1,2})?$/;

  /**
   * TextInputComponent
   *
   * Renders a single free-text note-name input for identification answers.
   * Mirrors the external interface of LabelInputComponent so exercise_sheet
   * can swap the two components without changing its call sites.
   *
   * @constructor
   * @param {object}   settings
   * @param {jQuery}   settings.containerEl  - Absolutely-positioned container div.
   * @param {array}    settings.problems     - Array of visible problem objects.
   * @param {number}   settings.problemCount - Expected number of answers.
   * @param {string}   settings.feedbackMode - "practice" or "submit".
   * @param {function} settings.onAnswer     - Callback fn(problemIndex, label).
   */
  var TextInputComponent = function (settings) {
    this.settings = settings || {};
    this.containerEl = this.settings.containerEl;
    this.problems = this.settings.problems || [];
    this.problemCount = this.settings.problemCount || this.problems.length || 0;
    this.analysisType = this.settings.analysisType || "note_name";
    this.feedbackMode = this.settings.feedbackMode || "submit";
    this.onAnswer = this.settings.onAnswer || function () {};
    this.onSubmit = this.settings.onSubmit || function () {};
    this._didSeedInitialAnswers = false;
    this._prevAnswers = this._resolveInitialAnswers();
    this._wrapEl = null;
    this._fieldEl = null;
    this._buttonEl = null;
  };

  TextInputComponent.prototype = new Component();

  _.extend(TextInputComponent.prototype, {
    initComponent: function () {
      // no-op — render() is called explicitly from exercise_sheet.js
    },

    /**
     * Normalize a raw note token to the spelling expected by the grader.
     * Invalid note names return null.
     *
     * Examples:
     *   "bb" -> "Bb"
     *   "f#" -> "F#"
     *   "DBB" -> "Dbb"
     */
    _normalizeToken: function (raw) {
      if (!raw) {
        return null;
      }

      var trimmed = String(raw).replace(/^\s+|\s+$/g, "");
      if (!trimmed) {
        return null;
      }

      if (this.analysisType === "interval_generic") {
        return /^[1-8]$/.test(trimmed) ? trimmed : null;
      }

      if (this.analysisType === "interval_specific") {
        return /^[PMmAd][1-8]$/.test(trimmed) ? trimmed : null;
      }

      if (this.analysisType === "note_name") {
        var match = trimmed.toLowerCase().match(VALID_NOTE_RE);
        if (!match) {
          return null;
        }
        return match[1].toUpperCase() + (match[2] || "");
      }

      return trimmed;
    },

    /**
     * Parse valid note-name tokens from the field value.
     * Invalid tokens are ignored and do not consume a problem slot.
     *
     * @param {string} value
     * @returns {Array<{index: number, value: string}>}
     */
    _parseTokens: function (value) {
      var parsed = [];
      var rawTokens = String(value || "").split(/\s+/);
      var nextIndex = 0;

      for (var i = 0; i < rawTokens.length; i++) {
        if (!rawTokens[i] || nextIndex >= this.problemCount) {
          continue;
        }

        var normalized = this._normalizeToken(rawTokens[i]);
        if (!normalized) {
          continue;
        }

        parsed.push({
          index: nextIndex,
          value: normalized,
        });
        nextIndex++;
      }

      return parsed;
    },

    _answersArrayFromTokens: function (tokens) {
      var answers = [];
      _.each(tokens, function (token) {
        answers[token.index] = token.value;
      });
      return answers;
    },

    _cloneAnswers: function (answers) {
      var clone = [];
      if (!answers) {
        return clone;
      }

      for (var i = 0; i < answers.length; i++) {
        if (typeof answers[i] !== "undefined") {
          clone[i] = answers[i];
        }
      }

      return clone;
    },

    _snapshotAnswers: function (source) {
      var snapshot = [];
      if (!source) {
        return snapshot;
      }

      for (var i = 0; i < this.problemCount; i++) {
        var value = source[i];
        if (value === null || typeof value === "undefined" || value === "") {
          continue;
        }
        snapshot[i] = value;
      }

      return snapshot;
    },

    _resolveInitialAnswers: function () {
      if (this.settings && this.settings.currentAnswers) {
        return this._snapshotAnswers(this.settings.currentAnswers);
      }
      if (
        !this._didSeedInitialAnswers &&
        this.settings &&
        this.settings.initialAnswers
      ) {
        this._didSeedInitialAnswers = true;
        return this._snapshotAnswers(this.settings.initialAnswers);
      }
      return this._cloneAnswers(this._prevAnswers);
    },

    /**
     * Placeholder text for the enabled (Type) field, by analysisType.
     * The disabled (Click) field uses a fixed hint — see setDisabled.
     */
    _placeholderText: function () {
      if (this.analysisType === "interval_generic") {
        return "e.g. 5 8 3 6";
      }
      if (this.analysisType === "interval_specific") {
        return "e.g. P5 M3 m6 A4";
      }
      return "e.g. C D E F";
    },

    /**
     * Practice mode only submits answers whose normalized value changed since
     * the last parse event we committed.
     */
    _emitChangedAnswers: function (tokens) {
      var nextAnswers = this._answersArrayFromTokens(tokens);

      for (var i = 0; i < this._prevAnswers.length; i++) {
        if (
          typeof this._prevAnswers[i] !== "undefined" &&
          typeof nextAnswers[i] === "undefined"
        ) {
          this.onAnswer(i, "");
        }
      }

      for (var j = 0; j < nextAnswers.length; j++) {
        if (
          typeof nextAnswers[j] !== "undefined" &&
          this._prevAnswers[j] !== nextAnswers[j]
        ) {
          this.onAnswer(j, nextAnswers[j]);
        }
      }

      this._prevAnswers = nextAnswers;
    },

    _emitAllAnswers: function (tokens) {
      var nextAnswers = this._answersArrayFromTokens(tokens);

      for (var i = 0; i < this._prevAnswers.length; i++) {
        if (
          typeof this._prevAnswers[i] !== "undefined" &&
          typeof nextAnswers[i] === "undefined"
        ) {
          this.onAnswer(i, "");
        }
      }

      _.each(tokens, _.bind(function (token) {
        this.onAnswer(token.index, token.value);
      }, this));

      this._prevAnswers = nextAnswers;
    },

    _commitPracticeValue: function (rawValue) {
      this._emitChangedAnswers(this._parseTokens(rawValue));
    },

    _commitSubmitValue: function (rawValue) {
      this._emitAllAnswers(this._parseTokens(rawValue));
      this.onSubmit();
    },

    /**
     * Toggle the field's disabled state and its placeholder.
     * Called by exercise_sheet at the point of Click/Type state change so the
     * field stays mounted but read-only in Click mode, replacing the
     * attribute observers that used to live in player.html.
     */
    setDisabled: function (disabled) {
      if (!this._fieldEl || !this._fieldEl.length) {
        return;
      }
      this._fieldEl.prop("disabled", !!disabled);
      this._fieldEl.attr(
        "placeholder",
        disabled ? "Click the ? labels on the score" : this._placeholderText()
      );
    },

    /**
     * Flush the current field value to the grader then invoke onSubmit — but
     * ONLY when the field is enabled (Type mode). Returns false when there is
     * no enabled field so the caller can fall back to a direct submit.
     *
     * Replaces the capture-phase #identification-submit interceptor that used
     * to live in player.html (which clicked the hidden .text-id-check).
     * Never flushes a disabled/empty field: _emitAllAnswers would clear
     * existing grader answers for tokens present in _prevAnswers but absent
     * from the (empty) field.
     */
    flushAndSubmitIfActive: function () {
      if (!this._fieldEl || !this._fieldEl.length || this._fieldEl[0].disabled) {
        return false;
      }
      this._commitSubmitValue(this._fieldEl.val());
      return true;
    },

    /**
     * Render the text input, optional check button, and small usage hint.
     */
    render: function () {
      var self = this;

      if (this._wrapEl) {
        this._teardownDom();
      }

      this._prevAnswers = this._resolveInitialAnswers();
      this.containerEl.empty();

      var wrap = $('<div class="text-id-input"></div>');
      var pill = $('<div class="text-id-pill"></div>');
      var field = $('<input type="text" class="text-id-field" autocomplete="off" spellcheck="false" />');
      var button = $('<button type="button" class="text-id-check">Check ↵</button>');
      var hintText = this.analysisType === "interval_generic"
        ? "Space-separated interval numbers. 2 3 5 work."
        : this.analysisType === "interval_specific"
          ? "Space-separated intervals. Case matters: M2 m2 P4 A4 d5."
          : "Space-separated note names. Bb and F# work.";
      var hint = $('<div class="text-id-hint"></div>').text(hintText);

      field.attr("placeholder", this._placeholderText());

      pill.append(field).append(button);
      wrap.append(pill).append(hint);

      var _practiceDebounceTimer = null;
      field.on("input", function () {
        if (self.feedbackMode !== "practice") {
          return;
        }

        var rawValue = $(this).val();
        var parsed = self._parseTokens(rawValue);
        var endsWithSpace = /\s$/.test(rawValue);

        if (!endsWithSpace && parsed.length < self.problemCount) {
          return;
        }

        // Debounce: wait until user pauses before committing to the grader.
        // Without this, every space triggers onAnswer → render() →
        // _hydrateTextInputComponent → overwrites the field mid-keystroke.
        clearTimeout(_practiceDebounceTimer);
        _practiceDebounceTimer = setTimeout(function () {
          self._emitChangedAnswers(self._parseTokens(field.val()));
        }, 400);
      });

      field.on("keydown", function (e) {
        if (e.key !== "Enter") {
          return;
        }

        e.preventDefault();
        if (self.feedbackMode === "practice") {
          self._commitPracticeValue($(this).val());
        } else {
          self._commitSubmitValue($(this).val());
        }
      });

      button.on("click", function () {
        if (self.feedbackMode === "practice") {
          self._commitPracticeValue(field.val());
        } else {
          self._commitSubmitValue(field.val());
        }
      });

      this._wrapEl = wrap;
      this._fieldEl = field;
      this._buttonEl = button;

      this.containerEl.append(wrap);
      return this;
    },

    /**
     * No-op. This component has a fixed block layout, not one control per stave.
     */
    updatePositions: function () {},

    /**
     * No-op. Graded slot state is rendered elsewhere by the score UI.
     */
    showResults: function () {},

    /**
     * No-op. There are no individual DOM controls to selectively lock here.
     */
    lockCorrect: function () {},

    /**
     * Remove DOM and listeners so the component can be replaced safely.
     */
    _teardownDom: function () {
      if (this._buttonEl) {
        this._buttonEl.off();
      }
      if (this._fieldEl) {
        this._fieldEl.off();
      }
      if (this._wrapEl) {
        this._wrapEl.remove();
      }

      this._wrapEl = null;
      this._fieldEl = null;
      this._buttonEl = null;
    },

    /**
     * Remove DOM and listeners so the component can be replaced safely.
     */
    destroy: function () {
      this._teardownDom();
      this._prevAnswers = [];
    }
  });

export default TextInputComponent;
