define([
  "jquery",
  "lodash",
  "app/config",
  "app/components/events",
  "app/components/component",
  "app/components/ui/modal",
  "app/utils/instruments",
  "app/widgets/key_signature",
  "app/widgets/analyze",
  "app/widgets/highlight",
  "app/widgets/staff_distribute",
  "app/components/ui/target_selector",
], function (
  $,
  _,
  Config,
  EVENTS,
  Component,
  ModalComponent,
  Instruments,
  KeySignatureWidget,
  AnalyzeWidget,
  HighlightWidget,
  StaffDistributionWidget,
  TargetSelectorComponent
) {
  /**
   * Defines whether the shortcuts are enabled by default or not.
   * @type {boolean}
   * @const
   */
  var KEYBOARD_SHORTCUTS_ENABLED = Config.get(
    "general.keyboardShortcutsEnabled"
  );
  var DESIRED_KEYBOARD_SIZE = Config.get("general.defaultKeyboardSize");
  var DESIRED_KEYBOARD_OCTAVES_OFFSET = 0;

  /**
   * ajax call to GET the keyboard size
   * this will set the keyboard size in the controls on the right (not the actual keyboard)
   * if no one is logged in the size is 49 per apps.accounts.models
   */

  $.ajax({
    type: "GET",
    url: this.location.origin + "/ajax/preferences/",
    async: false,
    success: function (response) {
      if (!response["valid"]) {
        /** if the call is successful response.instance will hold the json sent by the server
         * use the following two lines to log the response to the console
         * console.log(response);
         * console.log(JSON.parse(response.instance)); */
        var sticky_settings = JSON.parse(response.instance);
        DESIRED_KEYBOARD_SIZE = sticky_settings.keyboard_size;
        DESIRED_KEYBOARD_OCTAVES_OFFSET =
          sticky_settings.keyboard_octaves_offset;
      }
    },
  });

  /**
   * Defines a namespace for settings.
   * canvas.
   *
   * @namespace
   */
  var MusicControlsComponent = function (settings) {
    this.settings = settings || {};
    if (!("keySignature" in settings)) {
      throw new Error("missing keySignature setting");
    }
    if (!("midiDevice" in settings)) {
      throw new Error("missing midiDevice setting");
    }
    this.keySignature = settings.keySignature;
    this.midiDevice = settings.midiDevice;
    this.feedback = settings.feedback || null;

    if (settings.exerciseContext) {
      this.exerciseContext = settings.exerciseContext;
    } else {
      this.exerciseContext = false;
    }

    this.addComponent(new ModalComponent());

    this.targetSelector = new TargetSelectorComponent({
      onChoose: (payload) => this._onTargetChosen(payload),
    });
    this.addComponent(this.targetSelector);

    this.headerEl = $(settings.headerEl);
    this.containerEl = $(settings.containerEl);
    this._authoringMetaLoaded = false;
    this._isSuperuser = false;
    this._suggestedUnits = {};
    this._pendingSaveJsonData = null;
    this._currentUnitSuggestionKey = null;
    this._completedUnitSuggestionKeys = {};
    this._unitSuggestionInFlightByKey = {};
    this._unitSuggestionCallbacksByKey = {};
    this._autoSelectedSuggestedUnits = {};
    this._applyingSuggestedUnits = false;

    // _.bindAll(this, []);
  };

  MusicControlsComponent.prototype = new Component();

  _.extend(MusicControlsComponent.prototype, {
    /**
     * Initializes the component.
     *
     * @return undefined
     */
    initComponent: function () {
      $(".js-btn-help", this.headerEl).on("click", this.onClickInfo);
      $(".js-btn-screenshot").on("mousedown", this.onClickScreenshot);
      $(".js-btn-upload-json").on("mousedown", (e) => {
        switch (e.which) {
          case 1:
            this.onClickSaveJSON("upload");
            break;
          // on right click
          case 3:
            this.onClickSaveJSON("upload", true);
            break;
        }
      });
      // returns false to prevent context menu from popping up
      $(".js-btn-upload-json").on("contextmenu", () => false);
      $(".js-btn-download-json").on("mousedown", () => this.onClickSaveJSON());
      $(".js-btn-pristine").on("click", (e) => {
        e.preventDefault();
        this.onClickPristine();
      });
      $(".js-btn-import-musicxml").on("click", (e) => {
        e.preventDefault();
        $("#musicxml-upload-input").click();
      });
      $("#musicxml-upload-input").on("change", (e) => {
        var file = e.target.files[0];
        if (!file) return;
        this._importMusicXMLPreview(file);
      });
      $(".js-btn-nextexercise").on("click", (e) => {
        e.preventDefault();
        this.onClickNextExercise();
      });
      $(".js-btn-previousexercise").on("click", (e) => {
        e.preventDefault();
        this.onClickPreviousExercise();
      });
      $(".js-btn-firstexercise").on("click", (e) => {
        e.preventDefault();
        this.onClickFirstExercise();
      });

      this.initControlsLayout();
      this.initKeySignatureTab();
      this.initNotationTab();
      this.renderInstrumentSelect();
      this.renderKeyboardSizeSelect();
      this.renderOctaveAdjustment();
      this.renderKeyboardShortcuts();
      this.initMidiTab();
      this.initSavePanel();
      this.initBatchWizard();

      this.subscribe(EVENTS.BROADCAST.PLAY_SAVED, (data) =>
        this.targetSelector.open(data)
      );
      this.subscribe(EVENTS.BROADCAST.PRISTINE, () => {
        this._activeMusicXMLFile = null;
        this._pendingSaveJsonData = null;
        $("#play-save-musicxml-options").hide();
        $("#musicxml-upload-input").val("");
      });
    },
    /**
     * Initializes the controls layout.
     *
     * @return undefined
     */
    initControlsLayout: function () {
      this.containerEl.children(".accordion").accordion({
        active: false,
        collapsible: true,
        heightStyle: "content",
      });
    },
    /**
     * Initializes the content of the midi.
     *
     * @return undefined
     */
    initMidiTab: function () {
      var containerEl = this.containerEl;
      var renderDevices = function (midiDevice) {
        var inputs = midiDevice.getInputs();
        var outputs = midiDevice.getOutputs();
        var tpl = _.template('<option value="<%= id %>"><%= name %></option>');
        var makeOptions = function (device, idx) {
          return tpl({ id: idx, name: device.name });
        };
        var devices = {
          input: {
            selector: $(".js-select-midi-input", containerEl),
            options: _.map(inputs, makeOptions),
          },
          output: {
            selector: $(".js-select-midi-output", containerEl),
            options: _.map(outputs, makeOptions),
          },
        };

        _.each(devices, function (device, type) {
          if (device.options.length > 0) {
            $(device.selector).html(device.options.join(""));
          } else {
            $(device.selector).html("<option>--</option>");
          }

          if (device.readonly) {
            $(device.selector).attr("disabled", "disabled");
          } else {
            $(device.selector).on("change", function () {
              var index = parseInt($(this).val(), 10);
              var inputs =
                this.length; /* this is the number of available devices */
              midiDevice[type == "input" ? "selectInput" : "selectOutput"](
                index,
                inputs
              );
            });
          }
        });
      };

      $(".js-refresh-midi-devices", containerEl).on(
        "click",
        this.midiDevice.update
      );

      this.midiDevice.bind("updated", renderDevices);

      renderDevices(this.midiDevice);
    },
    /**
     * Initializes the content of the key signature.
     *
     * @return undefined
     */
    initKeySignatureTab: function () {
      var containerEl = this.headerEl;
      var el = $(".js-keysignature-widget", containerEl);
      var widget = new KeySignatureWidget(this.keySignature);
      widget.render();
      el.append(widget.el);
    },
    /**
     * Initializes the content of the notation containerEl.
     *
     * @return undefined
     */
    initNotationTab: function () {
      var that = this;
      var containerEl = this.containerEl;
      var el = $(".js-notation-opts-widget", containerEl);
      var analysisSettings = {};
      var highlightSettings = {};
      var staffDistribution = {};
      var is_exercise_view = false;
      if (this.exerciseContext) {
        is_exercise_view = true;
        analysisSettings = this.exerciseContext
          .getDefinition()
          .getAnalysisSettings();
        highlightSettings = this.exerciseContext
          .getDefinition()
          .getHighlightSettings();
        staffDistribution = this.exerciseContext
          .getDefinition()
          .getStaffDistribution();
        /* TO DO: grab additional settings <-- no longer sure which */
      }
      var staff_distribution_widget = new StaffDistributionWidget(
        staffDistribution,
        is_exercise_view
      );
      var analyze_widget = new AnalyzeWidget(
        analysisSettings,
        is_exercise_view
      );
      var highlight_widget = new HighlightWidget(
        highlightSettings,
        is_exercise_view
      );
      var event_for = {
        distribute: EVENTS.BROADCAST.DISTRIBUTE_NOTES,
        highlight: EVENTS.BROADCAST.HIGHLIGHT_NOTES,
        analyze: EVENTS.BROADCAST.ANALYZE_NOTES,
      };
      var onChangeCategory = function (category, enabled) {
        if (event_for[category]) {
          that.broadcast(event_for[category], {
            key: "enabled",
            value: enabled,
          });
        }
      };
      var onChangeOption = function (category, mode, enabled) {
        var value = {};
        if (event_for[category]) {
          value[mode] = enabled;
          that.broadcast(event_for[category], { key: "mode", value: value });
        }
      };
      var onChangeValue = function (category, value) {
        that.broadcast(event_for[category], value);
      };

      staff_distribution_widget.bind("changeValue", onChangeValue);

      highlight_widget.bind("changeCategory", onChangeCategory);
      highlight_widget.bind("changeOption", onChangeOption);

      analyze_widget.bind("changeCategory", onChangeCategory);
      analyze_widget.bind("changeOption", onChangeOption);

      staff_distribution_widget.render();
      analyze_widget.render();
      highlight_widget.render();

      el.append(
        staff_distribution_widget.el,
        analyze_widget.el,
        highlight_widget.el
      );
    },
    /**
     * Renders the instrument selector.
     *
     * @return undefined
     */
    renderInstrumentSelect: function () {
      var that = this;
      var containerEl = this.containerEl;
      var el = $(".js-instrument", containerEl);
      var selectEl = $("<select/>");
      var tpl = _.template(
        '<% _.forEach(instruments, function(inst) { %><option value="<%= inst.num %>"><%- inst.name %></option><% }); %>'
      );
      var options = tpl({ instruments: Instruments.getEnabled() });

      selectEl.append(options);
      selectEl.on("change", function () {
        var instrument_num = $(this).val();
        that.broadcast(EVENTS.BROADCAST.INSTRUMENT, instrument_num);
      });

      el.append(selectEl);
    },
    /**
     * Renders the keyboard size selector.
     *
     * @return undefined
     */
    renderKeyboardSizeSelect: function () {
      var that = this;
      var containerEl = this.containerEl;
      var el = $(".js-keyboardsize", containerEl);
      var selectEl = $("<select/>");
      var tpl = _.template(
        '<% _.forEach(sizes, function(size) { %><option value="<%= size %>"><%- size %></option><% }); %>'
      );
      var options = tpl({ sizes: [25, 32, 37, 49, 61, 88] });
      var selected = DESIRED_KEYBOARD_SIZE;

      selectEl.append(options);
      selectEl.find("[value=" + selected + "]").attr("selected", "selected");
      selectEl.on("change", function () {
        var size = parseInt($(this).val(), 10);
        that.broadcast(EVENTS.BROADCAST.KEYBOARD_SIZE, size);
      });

      el.append(selectEl).wrapInner("<label>Piano keys&ensp;</label>");
    },
    /**
     * Renders the octave adjustment selector.
     *
     * @return undefined
     */
    renderOctaveAdjustment: function () {
      var that = this;
      var containerEl = this.containerEl;
      var el = $(".js-octaveadjustment", containerEl);
      var selectEl = $("<select/>");
      var tpl = _.template(
        '<% _.forEach(adjustments, function(adj) { %><option value="<%= adj %>"><%- adj %></option><% }); %>'
      );
      var options = tpl({ adjustments: [-1, 0, 1, 2, 3] });
      var selected = DESIRED_KEYBOARD_OCTAVES_OFFSET;

      selectEl.append(options);
      selectEl.find("[value=" + selected + "]").attr("selected", "selected");
      selectEl.on("change", function () {
        var adj = parseInt($(this).val(), 10);
        that.broadcast(EVENTS.BROADCAST.OCTAVE_ADJUSTMENT, adj);
      });

      el.append(selectEl).wrapInner("<label>Octave adjustment&ensp;</label>");
    },
    /**
     * Renders the keyboard shorcuts.
     *
     * @return undefined
     */
    renderKeyboardShortcuts: function () {
      var that = this;
      var containerEl = this.containerEl;
      var el = $(".js-keyboardshortcuts", containerEl);
      var inputEl = $(
        '<input type="checkbox" name="keyboard_shortcuts" value="on" />'
      );
      el.append("Computer keyboard as piano&ensp;")
        .append(inputEl)
        .wrap("<label/>");

      // toggle shortcuts on/off via gui control
      inputEl.attr("checked", KEYBOARD_SHORTCUTS_ENABLED);
      inputEl.on("change", function () {
        var toggle = $(this).is(":checked") ? true : false;
        that.broadcast(EVENTS.BROADCAST.TOGGLE_SHORTCUTS, toggle);
        $(this).blur(); // trigger blur so it loses focus
      });

      // update gui control when toggled via ESC key
      this.subscribe(EVENTS.BROADCAST.TOGGLE_SHORTCUTS, function (enabled) {
        inputEl[0].checked = enabled;
      });
    },
    /**
     * Handler to generate a screenshot/image of the staff area.
     *
     * @param {object} evt
     * @return {boolean} true
     */
    onClickScreenshot: function (evt) {
      var canvas = document.getElementById("staff");
      var dataURL = canvas.toDataURL("image/png");
      var newTab = window.open("about:blank", "image from canvas");
      newTab.document.write("<img src='" + dataURL + "' alt='from canvas'/>");
      return true;
    },

    initSavePanel: function () {
      var that = this;
      var panelEl = $("#play-save-panel");
      if (!panelEl.length) {
        return;
      }

      this._loadAuthoringMeta();

      $("#play-save-description, #play-save-tags, #play-save-mode, " +
        "#play-save-create-transpositions, #play-save-key-set, #play-save-public, " +
        "#play-save-official, #play-save-new-playlist-name")
        .off(".playsave")
        .on("input.playsave change.playsave", function () {
          that._validateSavePanel(false);
        });

      $("#play-save-unit").off("change.playsave").on("change.playsave", function () {
        if (!that._applyingSuggestedUnits) {
          that._autoSelectedSuggestedUnits = {};
        }
        that._validateSavePanel(false);
      });

      $("#play-save-playlist").off("change.playsave").on("change.playsave", function () {
        if ($(this).val() === "__new__") {
          $("#play-save-new-playlist-row").show();
        } else {
          $("#play-save-new-playlist-row").hide();
        }
        that._validateSavePanel(false);
      });

      $("#play-save-key-set-preset").off("change.playsave").on("change.playsave", function () {
        that._applyKeySetPreset($(this).val());
        that._validateSavePanel(false);
      });

      $("#play-save-submit").off("click.playsave").on("click.playsave", function () {
        var jsonData = that._pendingSaveJsonData || that._getCurrentSaveJsonData();
        if (!jsonData) {
          that._setSavePanelFeedback("No score is ready to save.");
          return;
        }
        var requestKey = that._suggestionRequestKey(jsonData);
        $("#play-save-submit").prop("disabled", true);
        that._ensureUnitSuggestionsForScore(jsonData, function () {
          var currentJsonData = that._pendingSaveJsonData || that._getCurrentSaveJsonData();
          if (that._suggestionRequestKey(currentJsonData) !== requestKey) {
            that._validateSavePanel(false);
            return;
          }
          that._submitSaveDialog(jsonData, null, $("#play-save-dialog-feedback"));
        });
      });

      var musicxmlTimer = null;
      $("#musicxml-start-measure, #musicxml-end-measure, #musicxml-complexity")
        .off(".musicxml")
        .on("change.musicxml input.musicxml", function () {
          if (that._activeMusicXMLFile) {
            clearTimeout(musicxmlTimer);
            musicxmlTimer = setTimeout(function () {
              that._importMusicXMLPreview(that._activeMusicXMLFile);
            }, 400);
          }
        });

      this._applyKeySetPreset($("#play-save-key-set-preset").val() || "common");
      this._validateSavePanel(false);
    },

    _loadAuthoringMeta: function () {
      var that = this;
      var unitSelect = $("#play-save-unit");
      var playlistSelect = $("#play-save-playlist");

      if (!unitSelect.length || this._authoringMetaLoaded) {
        return;
      }

      $.ajax({
        type: "GET",
        url: window.location.origin + "/exercises/authoring-meta/",
        dataType: "json",
        success: function (meta) {
          that._authoringMetaLoaded = true;
          that._isSuperuser = !!meta.isSuperuser;

          unitSelect.empty();
          $.each(meta.units || [], function (i, u) {
            var label = "Unit " + u.n + (u.title ? " - " + u.title : "");
            unitSelect.append(
              $("<option>").val(String(u.n)).text(label).attr("data-base-label", label)
            );
          });

          playlistSelect.html('<option value="">None</option>');
          $.each(meta.playlists || [], function (i, pl) {
            var optEl = $("<option>").val(pl.id).text(pl.name + (pl.locked ? " (locked)" : ""));
            if (pl.locked) {
              optEl.prop("disabled", true);
            }
            playlistSelect.append(optEl);
          });
          playlistSelect.append($("<option>").val("__new__").text("New playlist..."));

          if (that._isSuperuser) {
            $("#play-save-official-row").show();
          } else {
            $("#play-save-official").prop("checked", false);
            $("#play-save-official-row").hide();
          }

          that._applySuggestedUnits();
          that._validateSavePanel(false);
        },
        error: function () {
          that._setSavePanelFeedback("Could not load units and playlists.");
          console.warn("[play-save] Could not fetch authoring-meta");
        },
      });
    },

    _getCurrentSaveJsonData: function () {
      var currentState = sessionStorage.getItem("current_state");
      if (!currentState) {
        return null;
      }
      try {
        return JSON.stringify(JSON.parse(currentState), null, 0);
      } catch (e) {
        console.warn("[play-save] Failed to parse current_state", e);
        return null;
      }
    },

    _prepareSavePanel: function (json_data, focusPanel) {
      this._pendingSaveJsonData = json_data;
      this._loadAuthoringMeta();
      if (this._currentUnitSuggestionKey !== this._suggestionRequestKey(json_data)) {
        this._clearAutoSuggestedUnits();
      }
      this._ensureUnitSuggestionsForScore(json_data);
      this._validateSavePanel(false);

      if (focusPanel && $("#play-save-panel").length) {
        $("html, body").animate({ scrollTop: $("#play-save-panel").offset().top - 16 }, 180);
        $("#play-save-description").trigger("focus");
      }
    },

    _suggestionRequestKey: function (json_data) {
      return json_data || "";
    },

    _clearAutoSuggestedUnits: function () {
      var unitSelect = $("#play-save-unit");
      var autoSelected = this._autoSelectedSuggestedUnits || {};
      this._suggestedUnits = {};
      this._autoSelectedSuggestedUnits = {};
      if (!unitSelect.length) {
        return;
      }
      unitSelect.find("option").each(function () {
        var option = $(this);
        var value = String(option.val());
        var baseLabel = option.attr("data-base-label") || option.text().replace(/ \(suggested\)$/, "");
        option.attr("data-base-label", baseLabel);
        option.text(baseLabel);
        if (autoSelected[value]) {
          option.prop("selected", false);
        }
      });
    },

    _ensureUnitSuggestionsForScore: function (json_data, callback) {
      var key = this._suggestionRequestKey(json_data);
      if (this._completedUnitSuggestionKeys[key]) {
        if (callback) callback();
        return;
      }

      if (callback) {
        if (!this._unitSuggestionCallbacksByKey[key]) {
          this._unitSuggestionCallbacksByKey[key] = [];
        }
        this._unitSuggestionCallbacksByKey[key].push(callback);
      }

      if (this._unitSuggestionInFlightByKey[key]) {
        return;
      }

      this._currentUnitSuggestionKey = key;
      this._unitSuggestionInFlightByKey[key] = true;
      this._setSaveSuggestionStatus("Checking suggested units...");
      this._suggestUnitsForCurrentScore(json_data, key, () => {
        var callbacks = this._unitSuggestionCallbacksByKey[key] || [];
        delete this._unitSuggestionCallbacksByKey[key];
        delete this._unitSuggestionInFlightByKey[key];
        this._completedUnitSuggestionKeys[key] = true;
        $.each(callbacks, function (i, cb) {
          cb();
        });
      });
    },

    _suggestUnitsForCurrentScore: function (json_data, requestKey, done) {
      var that = this;
      var payload;
      var finish = done || function () {};
      try {
        payload = JSON.parse(json_data);
      } catch (e) {
        if (requestKey === this._currentUnitSuggestionKey) {
          this._setSaveSuggestionStatus("");
        }
        finish();
        return;
      }

      var cirScore = payload.score || payload.cir_score || payload;
      var key = payload.key || (payload.meta && payload.meta.key) || "jC_";

      $.ajax({
        type: "POST",
        url: window.location.origin + "/teacher/play/api/suggest-units/",
        data: JSON.stringify({ cir_score: cirScore, key: key }),
        contentType: "application/json",
        dataType: "json",
        headers: { "X-CSRFToken": that._getCsrfToken() },
        success: function (data) {
          var suggested = data && data.suggested_units ? data.suggested_units : [];
          if (requestKey === that._currentUnitSuggestionKey) {
            that._suggestedUnits = {};
            $.each(suggested, function (i, unitNum) {
              that._suggestedUnits[String(unitNum)] = true;
            });
            that._applySuggestedUnits();
            that._setSaveSuggestionStatus(suggested.length ? "Suggested units selected." : "");
            that._validateSavePanel(false);
          }
          finish();
        },
        error: function () {
          if (requestKey === that._currentUnitSuggestionKey) {
            that._clearAutoSuggestedUnits();
            that._setSaveSuggestionStatus("");
            that._validateSavePanel(false);
          }
          console.warn("[play-save] Could not fetch unit suggestions");
          finish();
        },
      });
    },

    _applySuggestedUnits: function () {
      var unitSelect = $("#play-save-unit");
      if (!unitSelect.length) {
        return;
      }

      var current = unitSelect.val() || [];
      var currentSelected = {};
      var selected = {};
      var manualSelected = {};
      var newAutoSelected = {};
      $.each(current, function (i, value) {
        currentSelected[String(value)] = true;
      });

      $.each(currentSelected, (value) => {
        if (!this._autoSelectedSuggestedUnits[value]) {
          manualSelected[value] = true;
          selected[value] = true;
        }
      });

      $.each(this._suggestedUnits || {}, function (value) {
        selected[String(value)] = true;
        if (!manualSelected[String(value)]) {
          newAutoSelected[String(value)] = true;
        }
      });

      this._autoSelectedSuggestedUnits = newAutoSelected;
      unitSelect.data("suggested-map", this._suggestedUnits || {});
      this._applyingSuggestedUnits = true;
      unitSelect.find("option").each(function () {
        var option = $(this);
        var value = String(option.val());
        var baseLabel = option.attr("data-base-label") || option.text().replace(/ \(suggested\)$/, "");
        option.attr("data-base-label", baseLabel);
        option.text(baseLabel + ((unitSelect.data("suggested-map") || {})[value] ? " (suggested)" : ""));
        option.prop("selected", !!selected[value]);
      });
      this._applyingSuggestedUnits = false;
    },

    _applyKeySetPreset: function (preset) {
      var presets = {
        common: "C, G, D, F, Bb, Eb",
        sharp: "C, G, D, A, E, B",
        flat: "C, F, Bb, Eb, Ab, Db",
        all: "C, G, D, A, E, B, F#, Db, Ab, Eb, Bb, F",
      };
      if (preset && preset !== "custom" && presets[preset]) {
        $("#play-save-key-set").val(presets[preset]);
      }
    },

    _getSelectedUnits: function () {
      var value = $("#play-save-unit").val() || [];
      if (!$.isArray(value)) {
        value = value ? [value] : [];
      }
      return value;
    },

    _getSelectedKeySet: function () {
      var raw = $("#play-save-key-set").val() || "";
      var keys = [];
      var seen = {};
      $.each(raw.split(/[,\s]+/), function (i, value) {
        var key = $.trim(value);
        if (key && !seen[key]) {
          keys.push(key);
          seen[key] = true;
        }
      });
      return keys;
    },

    _setSavePanelFeedback: function (message) {
      var feedbackEl = $("#play-save-dialog-feedback");
      feedbackEl.text(message || "");
      feedbackEl.toggleClass("is-visible", !!message);
    },

    _setSaveSuggestionStatus: function (message) {
      $("#play-save-suggestion-status").text(message || "");
    },

    _validateSavePanel: function (showMessage) {
      var description = $.trim($("#play-save-description").val() || "");
      var units = this._getSelectedUnits();
      var createTranspositions = $("#play-save-create-transpositions").is(":checked");
      var keySet = this._getSelectedKeySet();
      var message = "";

      var playlistSelectVal = $("#play-save-playlist").val();
      var newPlaylistName = $.trim($("#play-save-new-playlist-name").val() || "");

      if (!description) {
        message = "Description is required.";
      } else if (units.length === 0) {
        message = "Select at least one unit tag.";
      } else if (playlistSelectVal === "__new__" && !newPlaylistName) {
        message = "Enter a name for the new playlist.";
      } else if (createTranspositions && keySet.length === 0) {
        message = "Choose at least one key for transpositions.";
      }

      $("#play-save-submit").prop("disabled", !!message);
      this._setSavePanelFeedback(message);
      return !message;
    },

    /**
     * Handler to upload or download JSON data for the current notation.
     *
     * @param {string} destination
     * @return {boolean} true
     */
    onClickSaveJSON: function (destination = "download", quiet = false) {
      advanced = true;

      var json_data =
        JSON.parse(sessionStorage.getItem("current_state")) || false;
      if (!json_data /* || json_data["chords"].length < 1 */) {
        console.log("Cannot find JSON data");
        return false;
      }

      // OLD EXERCISE CREATION FLOW, DELETE IF NO LONGER USEFUL BY 2024

      // if (advanced) {
      //   const type_input = prompt(
      //     "Enter a number for exercise type: (1) matching (2) analytical (3) analytical_pcs (4) figured_bass (5) figured_bass_pcs"
      //   );
      //   if (type_input == null) {
      //     window.alert("Exercise upload cancelled by user.");
      //     return false;
      //   }
      //   const type_options = {
      //     1: "matching",
      //     2: "analytical",
      //     3: "analytical_pcs",
      //     4: "figured_bass",
      //     5: "figured_bass_pcs",
      //   };
      //   const type = type_input
      //     ? type_options.hasOwnProperty(type_input)
      //       ? type_options[type_input]
      //       : false
      //     : false;
      //   if (type == false) {
      //     window.alert("Exercise upload cancelled due to invalid input.");
      //     return false;
      //   }

      //   const user_input = prompt("Enter the Intro Text");
      //   if (user_input == null) {
      //     window.alert("Exercise upload cancelled by user.");
      //     return false;
      //   }
      //   const intro_text =
      //     "<p>" +
      //     (!user_input
      //       ? ""
      //       : user_input
      //           .replace(/[^-\w\.:;,!?/&*()[\] '"]+/g, "")
      //           .replace(/^\"/g, "“")
      //           .replace(/ \"/g, " “")
      //           .replace(/^\'/g, "‘")
      //           .replace(/ \'/g, " ‘")
      //           .replace(/\"$/g, "”")
      //           .replace(/\" /g, "” ")
      //           .replace(/\'$/g, "’")
      //           .replace(/\' /g, "’ ")
      //           .replace(/\'(s)\b/g, "’$1")
      //           .replace(/-{3}/g, "—")
      //           .replace(/-{2}/g, "–")) +
      //     "</p>";
      //   // do not allow < > until these field is verified as good html

      //   if (type == "matching") {
      //     const visibility_input = prompt(
      //       "Enter a visibility pattern using any combination of: b = bass, f = first, l = last, s = soprano, n = none."
      //     );
      //     if (visibility_input == null) {
      //       window.alert("Exercise upload cancelled by user.");
      //       return false;
      //     }
      //     const visibility_reqs =
      //       visibility_input === "n"
      //         ? ["none"]
      //         : visibility_input
      //             .replace(/[^flsb]/gi, "")
      //             .split("")
      //             .sort();

      //     let flsb = json_data.chord;
      //     if (visibility_reqs.length >= 1) {
      //       var i, len;
      //       for (i = 0, len = flsb.length; i < len; i++) {
      //         flsb[i].hidden = flsb[i].visible;
      //         flsb[i].visible = [];
      //       }
      //     }

      //     if (visibility_reqs.indexOf("b") !== -1) {
      //       for (i = 0, len = flsb.length; i < len; i++) {
      //         flsb[i].visible = []
      //           .concat(flsb[i].visible, flsb[i].hidden.shift())
      //           .sort();
      //       }
      //     }
      //     if (visibility_reqs.indexOf("s") !== -1) {
      //       for (i = 0, len = flsb.length; i < len; i++) {
      //         flsb[i].visible = []
      //           .concat(flsb[i].visible, flsb[i].hidden.pop())
      //           .sort();
      //       }
      //     }
      //     if (visibility_reqs.indexOf("f") !== -1 && flsb.length >= 1) {
      //       flsb[0].visible = [].concat(flsb[0].visible, flsb[0].hidden).sort();
      //       flsb[0].hidden = [];
      //     }
      //     if (visibility_reqs.indexOf("l") !== -1 && flsb.length >= 2) {
      //       let idx = flsb.length - 1;
      //       flsb[idx].visible = []
      //         .concat(flsb[idx].visible, flsb[idx].hidden)
      //         .sort();
      //       flsb[idx].hidden = [];
      //     }

      //     if (visibility_reqs.length >= 1) {
      //       json_data.chord = flsb;
      //     }
      //   }

      //   if (intro_text) {
      //     json_data.introText = intro_text;
      //   }
      //   if (type) {
      //     json_data.type = type;
      //   }
      // }

      // var intro_text = json_data.introText;
      json_data = JSON.stringify(json_data, null, 0);

      if (destination === "upload") {
        var validity = JSON.parse(sessionStorage.getItem("current_state_validity") || "null");
        if (validity && !validity.ok) {
          if (this.feedback) {
            if (validity.code === "empty") {
              this.feedback.emit("play.save.empty", { inlineEl: "#save-feedback" });
            } else {
              var m = /Bar (\d+) (?:has|spans) (\S+) beats, expected ([^.]+)/.exec(validity.error || "");
              this.feedback.emit("play.save.invalid_meter", {
                inlineEl: "#save-feedback",
                params: m ? { bar: m[1], beats: m[2], expected: m[3] } : { bar: "?", beats: "?", expected: "?" },
              });
            }
          }
          return false;
        }
        this._prepareSavePanel(json_data, true);
      } else {
        console.log("Download", json_data);
        var file_name = "exercise_download";
        if (advanced) {
          let probe = intro_text
            .replace(/[^-\w ]+/g, "")
            .replace(/ +/g, "_")
            .slice(0, 30);
          if (probe && probe.length >= 1 && typeof probe === "string") {
            file_name = probe;
          }
        }

        var blob = new Blob([json_data], {
          type: "application/json;charset=utf-8",
        });
        saveAs(blob, file_name + ".json");
      }

      return true;
    },
    /**
     * Handler to broadcast request for pristine sheet music div.
     *
     * @param {string} destination
     * @return {boolean} true
     */
    onClickPristine: function () {
      this.broadcast(EVENTS.BROADCAST.PRISTINE);
      return true;
    },
    /**
     * Handlers to broadcast requests for sheet music div. of exercises
     *
     * @param {object} evt
     * @return {boolean} true
     */
    onClickNextExercise: function () {
      this.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
      return true;
    },
    onClickPreviousExercise: function () {
      this.broadcast(EVENTS.BROADCAST.PREVIOUSEXERCISE);
      return true;
    },
    onClickFirstExercise: function () {
      this.broadcast(EVENTS.BROADCAST.FIRSTEXERCISE);
      return true;
    },
    /**
     * Receives the seam-contract payload from TargetSelectorComponent.
     * Logs it as the durable handoff record for Threads 2/3 (assign + curriculum).
     * v1 wires "library" only.
     *
     * @param {object} payload  { exerciseId, targetIntent, sectionId, create_transpositions, key_set }
     * @return undefined
     */
    _onTargetChosen: function (payload) {
      var that = this;

      if (payload.create_transpositions && payload.key_set && payload.key_set.length > 0) {
        var body = JSON.stringify({
          exerciseId: payload.exerciseId,
          key_set: payload.key_set,
          playlistId: payload.playlistId || null,
          is_official: payload.is_official || false,
        });
        fetch(window.location.origin + "/teacher/play/api/save-with-transpositions/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": that._getCsrfToken(),
          },
          body: body,
        }).then(function (res) {
          if (!res.ok) {
            console.warn("[play-target] save-with-transpositions failed", res.status);
          }
        }).catch(function (err) {
          console.warn("[play-target] save-with-transpositions error", err);
        });
      }

      if (payload.targetIntent === "library") {
        if (this.feedback) this.feedback.emit("play.save.success", { inlineEl: "#save-feedback" });
        window.open("/dashboard/exercises/" + payload.exerciseId + "/", "_blank");
      }
    },

    /**
     * Reads the csrftoken cookie value (set by ensure_csrf_cookie on PlayView).
     *
     * @return {string}
     */
    _getCsrfToken: function () {
      var value = "; " + document.cookie;
      var parts = value.split("; csrftoken=");
      if (parts.length === 2) {
        return parts.pop().split(";").shift();
      }
      return "";
    },

    /**
     * Collects dialog field values, extends the json_data payload, and POSTs
     * to /exercises/add/.
     *
     * @param {string}  json_data   Already-stringified score JSON
     * @param {jQuery}  overlayEl
     * @param {jQuery}  feedbackEl
     * @return undefined
     */
    _submitSaveDialog: function (json_data, overlayEl, feedbackEl) {
      var that = this;

      if (!this._validateSavePanel(true)) {
        return;
      }

      var description = $.trim($("#play-save-description").val());
      if (!description) {
        feedbackEl.text("Description is required.").addClass("is-visible");
        return;
      }

      if (this._activeMusicXMLFile) {
        this._submitMusicXMLSaveDialog(feedbackEl);
        return;
      }

      // Build skill tags array: optional unit: prefix + free tags
      var skillTags = [];
      var unitVals = this._getSelectedUnits();
      $.each(unitVals, function (i, unitVal) {
        skillTags.push("unit:" + unitVal);
      });
      var freeTags = $("#play-save-tags").val();
      if (freeTags) {
        var parsed = freeTags.split(",");
        for (var i = 0; i < parsed.length; i++) {
          var tag = $.trim(parsed[i]);
          if (tag) {
            skillTags.push(tag);
          }
        }
      }

      var isPublic = $("#play-save-public").is(":checked");
      var saveAsOfficial = this._isSuperuser && $("#play-save-official-row").is(":visible") && $("#play-save-official").is(":checked");
      var createTranspositions = $("#play-save-create-transpositions").is(":checked");
      var keySet = this._getSelectedKeySet();
      var selectedMode = $("#play-save-mode").val() || "play";

      var playlistSelectVal = $("#play-save-playlist").val();
      var playlistId = null;
      var playlistName = null;
      var isAdaptive = false;
      if (playlistSelectVal === "__new__") {
        playlistName = $.trim($("#play-save-new-playlist-name").val()) || null;
        isAdaptive = $("#play-save-adaptive").is(":checked");
      } else if (playlistSelectVal) {
        playlistId = playlistSelectVal;
      }

      // Parse existing json_data, extend with new fields, re-serialise
      var payload;
      try {
        payload = JSON.parse(json_data);
      } catch (e) {
        console.error("[play-save] Failed to parse json_data", e);
        return;
      }
      payload.description = description;
      payload.skillTags = skillTags;
      payload.isPublic = isPublic;
      payload.saveAsOfficial = saveAsOfficial;
      payload.mode = selectedMode;
      if (playlistId !== null) {
        payload.playlistId = playlistId;
      }
      if (playlistName !== null) {
        payload.playlistName = playlistName;
        payload.isAdaptive = isAdaptive;
      }

      var extendedData = JSON.stringify(payload, null, 0);

      $("#play-save-submit").prop("disabled", true);
      feedbackEl.text("").removeClass("is-visible");

      $.ajax({
        type: "POST",
        url: window.location.origin + "/exercises/add/",
        data: { data: extendedData },
        dataType: "json",
        headers: { "X-CSRFToken": that._getCsrfToken() },
        success: function (data) {
          $("#play-save-submit").prop("disabled", false);
          if (data.playlistId && data.playlistName) {
            var playlistSelect = $("#play-save-playlist");
            var existingOpt = playlistSelect.find("option[value='" + data.playlistId + "']");
            if (!existingOpt.length) {
              var newOpt = $("<option>").val(data.playlistId).text(data.playlistName);
              playlistSelect.find("option[value='__new__']").before(newOpt);
            }
            playlistSelect.val(String(data.playlistId));
            $("#play-save-new-playlist-row").hide();
            $("#play-save-new-playlist-name").val("");
          }
          if (overlayEl && overlayEl.hide) {
            overlayEl.hide();
          }
          if (that.feedback) {
            that.feedback.emit("play.save.success", { inlineEl: "#save-feedback" });
          }
          that._pendingSaveJsonData = null;
          that.broadcast(EVENTS.BROADCAST.PLAY_SAVED, {
            exerciseId: data.id,
            reviewStatus: data.reviewStatus,
            playlistId: data.playlistId || null,
            playlistName: data.playlistName || null,
            create_transpositions: createTranspositions,
            key_set: keySet,
            is_official: saveAsOfficial,
          });
        },
        error: function (xhr) {
          $("#play-save-submit").prop("disabled", false);
          var errMsg = null;
          try {
            errMsg = JSON.parse(xhr.responseText).error || null;
          } catch (e) { /* ignore */ }

          var feedbackId = "play.save.invalid_meter";
          if (errMsg) {
            var lower = errMsg.toLowerCase();
            if (lower.indexOf("tag") !== -1) {
              feedbackId = "play.save.invalid_tags";
            } else if (lower.indexOf("locked") !== -1 || lower.indexOf("playlist") !== -1) {
              feedbackId = "play.save.playlist_locked";
            } else if (lower.indexOf("official") !== -1 || lower.indexOf("superuser") !== -1 || xhr.status === 403) {
              feedbackId = "play.save.forbidden_official";
            }
          } else if (xhr.status === 403) {
            feedbackId = "play.save.forbidden_official";
          }

          if (that.feedback) {
            that.feedback.emit(feedbackId, {
              inlineEl: "#play-save-dialog-feedback",
              params: { bar: "?", beats: "?", expected: "?" },
            });
          } else {
            that._setSavePanelFeedback(errMsg || "Could not save exercise.");
          }
        },
      });
    },
    /* ------------------------------------------------------------------
     * Batch generation wizard (sub-plans 3.2–4.3)
     * ------------------------------------------------------------------ */

    initBatchWizard: function () {
      var that = this;
      var overlay = $("#batch-wizard-overlay");
      if (!overlay.length) { return; }

      // Populate unit select from already-loaded authoring meta
      var populateUnits = function () {
        var batchUnitSel = $("#batch-unit");
        var saveUnitSel = $("#play-save-unit");
        if (batchUnitSel.children("option").length > 1) { return; }
        saveUnitSel.children("option").each(function () {
          if ($(this).val()) {
            batchUnitSel.append($(this).clone().prop("selected", false));
          }
        });
      };

      // Populate playlist select from save panel
      var populatePlaylists = function () {
        var batchPl = $("#batch-playlist");
        var savePl = $("#play-save-playlist");
        // Clear all except None / New playlist
        batchPl.children("option").not("[value=''][value='__new__']").remove();
        savePl.children("option").each(function () {
          var v = $(this).val();
          if (v && v !== "__new__") {
            batchPl.append($(this).clone().prop("selected", false));
          }
        });
      };

      // Wire open button
      $("#play-batch-generate-btn").off("click.batch").on("click.batch", function () {
        if (that._authoringMetaLoaded) {
          populateUnits();
          populatePlaylists();
        } else {
          // Wait for meta then reopen
          var waitInterval = setInterval(function () {
            if (that._authoringMetaLoaded) {
              clearInterval(waitInterval);
              populateUnits();
              populatePlaylists();
            }
          }, 200);
        }
        var isSuperuser = $("#play-save-official-row").is(":visible");
        $("#batch-official-row").toggle(isSuperuser);
        that._openBatchWizard();
      });

      // Wire close buttons
      overlay.off("click.batch").on("click.batch", ".batch-wizard-close, #batch-cancel-btn", function () {
        that._closeBatchWizard();
      });
      // Click outside dialog closes
      overlay.on("click.batchoverlay", function (e) {
        if ($(e.target).is(overlay)) { that._closeBatchWizard(); }
      });

      // Playlist toggle
      overlay.on("change.batch", "#batch-playlist", function () {
        $("#batch-new-playlist-row").toggle($(this).val() === "__new__");
        that._validateBatchForm();
      });

      // Key preset change
      overlay.on("change.batch", "#batch-key-preset", function () {
        that._applyBatchKeyPreset($(this).val());
        that._validateBatchForm();
      });

      // Debounced estimate on form change
      var estimateTimer = null;
      overlay.on("input.batch change.batch",
        "#batch-source-ref, #batch-unit, #batch-type-play, #batch-type-identify, " +
        "#batch-type-roman, #batch-type-figures, #batch-key-set, #batch-key-preset",
        function () {
          that._validateBatchForm();
          clearTimeout(estimateTimer);
          estimateTimer = setTimeout(function () { that._fetchBatchEstimate(); }, 500);
        }
      );

      // Execute
      overlay.on("click.batch", "#batch-execute-btn", function () {
        that._executeBatch();
      });

      // Reject all
      overlay.on("click.batch", "#batch-reject-all-btn", function () {
        that._rejectAllBatchResults();
      });

      // Done
      overlay.on("click.batch", "#batch-results-done-btn", function () {
        that._closeBatchWizard();
      });

      // Per-row delete
      overlay.on("click.batch", ".batch-result-del", function () {
        var row = $(this).closest(".batch-result-row");
        var exerciseId = row.data("exercise-id");
        that._deleteBatchExercise(exerciseId, row);
      });

      // Regenerate selected
      overlay.on("click.batch", "#batch-regen-btn", function () {
        var selected = $(".batch-result-row input[type=checkbox]:checked")
          .map(function () { return $(this).closest(".batch-result-row").data("exercise-id"); })
          .get();
        if (!selected.length) { return; }
        that._executeBatch(true, selected);
      });

      this._applyBatchKeyPreset("common");
      this._validateBatchForm();
    },

    _openBatchWizard: function () {
      $("#batch-wizard-overlay").show();
      $("#batch-wizard-form").show();
      $("#batch-wizard-results").hide();
      $("#batch-wizard-feedback").text("");
      $("#batch-dry-run-estimate").hide();
      $("body").css("overflow", "hidden");
    },

    _closeBatchWizard: function () {
      $("#batch-wizard-overlay").hide();
      $("body").css("overflow", "");
      this._batchGeneratedIds = [];
    },

    _applyBatchKeyPreset: function (preset) {
      var presets = {
        common: "C, G, D, F, Bb, Eb",
        sharp:  "C, G, D, A, E, B",
        flat:   "C, F, Bb, Eb, Ab, Db",
        all:    "C, G, D, A, E, B, F#, F, Bb, Eb, Ab, Db",
      };
      if (preset !== "custom" && presets[preset]) {
        $("#batch-key-set").val(presets[preset]);
      }
    },

    _getBatchFormData: function () {
      var sourceRef = $.trim($("#batch-source-ref").val());
      var unit = $("#batch-unit").val();
      var keySetRaw = $.trim($("#batch-key-set").val());
      var keySet = keySetRaw ? keySetRaw.split(",").map(function (s) { return $.trim(s); }).filter(Boolean) : [];
      var exerciseTypes = [];
      if ($("#batch-type-play").is(":checked")) { exerciseTypes.push("play"); }
      if ($("#batch-type-identify").is(":checked")) { exerciseTypes.push("identify"); }
      if ($("#batch-type-roman").is(":checked")) { exerciseTypes.push("roman"); }
      if ($("#batch-type-figures").is(":checked")) { exerciseTypes.push("figures"); }
      var playlistVal = $("#batch-playlist").val();
      var playlistTarget = (playlistVal && playlistVal !== "__new__") ? parseInt(playlistVal, 10) : null;
      var newPlaylistName = $.trim($("#batch-new-playlist-name").val());
      var isOfficial = $("#batch-is-official").is(":checked");
      return { sourceRef: sourceRef, unit: unit, keySet: keySet, exerciseTypes: exerciseTypes,
               playlistTarget: playlistTarget, newPlaylistName: newPlaylistName, isOfficial: isOfficial };
    },

    _validateBatchRangeStr: function (str) {
      if (!str) { return false; }
      // Accept "N" or "N-M"
      return /^\d+(-\d+)?$/.test(str.replace(/\s/g, ""));
    },

    _validateBatchForm: function () {
      var d = this._getBatchFormData();
      var ok = this._validateBatchRangeStr(d.sourceRef) &&
               d.unit &&
               d.exerciseTypes.length > 0 &&
               d.keySet.length > 0;
      if (d.isOfficial && !$("#play-save-official-row").is(":visible")) { ok = false; }
      $("#batch-execute-btn").prop("disabled", !ok);
      return ok;
    },

    _fetchBatchEstimate: function () {
      if (!this._validateBatchForm()) { return; }
      var d = this._getBatchFormData();
      var payload = {
        source: "bach_riemenschneider",
        source_ref: d.sourceRef,
        unit: parseInt(d.unit, 10),
        skill_tags: [],
        exercise_types: d.exerciseTypes,
        key_set: d.keySet,
        playlist_target: d.playlistTarget,
        is_official: d.isOfficial,
        author_email: "",
        dry_run: true,
      };
      var csrfToken = $("[name=csrfmiddlewaretoken]").val() ||
        document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*=\s*([^;]*).*$)|^.*$/, "$1");
      $.ajax({
        url: "/teacher/play/api/generate-manifest/dry-run/",
        method: "POST",
        contentType: "application/json",
        headers: { "X-CSRFToken": csrfToken },
        data: JSON.stringify(payload),
        success: function (data) {
          var est = data.estimated_exercises || 0;
          var typeCount = (data.exercise_types || []).length;
          var keyCount = data.key_count || 0;
          $("#batch-estimate-text").text(
            est + " exercises (" + typeCount + " type" + (typeCount !== 1 ? "s" : "") +
            " × " + keyCount + " key" + (keyCount !== 1 ? "s" : "") + ")"
          );
          $("#batch-dry-run-estimate").show();
        },
        error: function () {
          $("#batch-dry-run-estimate").hide();
        },
      });
    },

    _executeBatch: function (overwrite, exerciseIds) {
      var d = this._getBatchFormData();
      if (!this._validateBatchForm()) { return; }
      var csrfToken = $("[name=csrfmiddlewaretoken]").val() ||
        document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*=\s*([^;]*).*$)|^.*$/, "$1");
      var payload = {
        source: "bach_riemenschneider",
        source_ref: d.sourceRef,
        unit: parseInt(d.unit, 10),
        skill_tags: [],
        exercise_types: d.exerciseTypes,
        key_set: d.keySet,
        playlist_target: d.playlistTarget,
        new_playlist_name: d.newPlaylistName || null,
        is_official: d.isOfficial,
        author_email: "",
        dry_run: false,
      };
      if (overwrite) { payload.overwrite = true; }
      if (exerciseIds && exerciseIds.length) { payload.overwrite_ids = exerciseIds; }

      $("#batch-execute-btn").prop("disabled", true).text("Generating…");
      $("#batch-wizard-feedback").text("");
      var that = this;

      $.ajax({
        url: "/teacher/play/api/generate-manifest/execute/",
        method: "POST",
        contentType: "application/json",
        headers: { "X-CSRFToken": csrfToken },
        data: JSON.stringify(payload),
        success: function (data) {
          $("#batch-execute-btn").prop("disabled", false).text("Generate");
          that._batchGeneratedIds = (data.exercise_ids || []).concat(that._batchGeneratedIds || []);
          that._renderBatchResults(data);
        },
        error: function (xhr) {
          $("#batch-execute-btn").prop("disabled", false).text("Generate");
          var msg = "Generation failed.";
          try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e) { /* ignore */ }
          $("#batch-wizard-feedback").text(msg);
        },
      });
    },

    _renderBatchResults: function (data) {
      var exercises = data.exercises || [];
      var total = exercises.length;
      var byType = {};
      exercises.forEach(function (ex) {
        byType[ex.exercise_type] = (byType[ex.exercise_type] || 0) + 1;
      });
      var typeSummary = Object.keys(byType).map(function (t) {
        return byType[t] + " " + t;
      }).join(", ");

      var summaryHtml = "<strong>" + total + " exercise" + (total !== 1 ? "s" : "") +
        " created</strong>" + (typeSummary ? " (" + typeSummary + ")" : "");
      $("#batch-results-summary").html(summaryHtml);

      var listHtml = "";
      exercises.forEach(function (ex) {
        var previewUrl = "/s/exercises/" + encodeURIComponent(ex.id) + "/";
        listHtml += '<div class="batch-result-row" data-exercise-id="' + ex.id + '">' +
          '<input type="checkbox" class="batch-result-select" />' +
          '<span class="batch-result-type">' + (ex.exercise_type || "") + "</span>" +
          '<span class="batch-result-key">' + (ex.key || "") + "</span>" +
          '<a href="' + previewUrl + '" target="_blank">' +
            (ex.description || ("Exercise " + ex.id)) + "</a>" +
          '<button type="button" class="batch-result-del" title="Delete">&times;</button>' +
          "</div>";
      });
      $("#batch-results-list").html(listHtml);
      $("#batch-regen-btn").show();

      $("#batch-wizard-form").hide();
      $("#batch-wizard-results").show();
    },

    _rejectAllBatchResults: function () {
      var ids = this._batchGeneratedIds || [];
      if (!ids.length) { this._closeBatchWizard(); return; }
      var csrfToken = $("[name=csrfmiddlewaretoken]").val() ||
        document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*=\s*([^;]*).*$)|^.*$/, "$1");
      var that = this;
      $.ajax({
        url: "/dashboard/api/exercises/bulk-delete/",
        method: "POST",
        contentType: "application/json",
        headers: { "X-CSRFToken": csrfToken },
        data: JSON.stringify({ ids: ids }),
        complete: function () {
          that._batchGeneratedIds = [];
          $(".batch-result-row").addClass("deleted");
          setTimeout(function () { that._closeBatchWizard(); }, 600);
        },
      });
    },

    _deleteBatchExercise: function (exerciseId, rowEl) {
      var csrfToken = $("[name=csrfmiddlewaretoken]").val() ||
        document.cookie.replace(/(?:(?:^|.*;\s*)csrftoken\s*=\s*([^;]*).*$)|^.*$/, "$1");
      var that = this;
      $.ajax({
        url: "/dashboard/api/exercises/bulk-delete/",
        method: "POST",
        contentType: "application/json",
        headers: { "X-CSRFToken": csrfToken },
        data: JSON.stringify({ ids: [exerciseId] }),
        success: function () {
          rowEl.addClass("deleted");
          that._batchGeneratedIds = (that._batchGeneratedIds || []).filter(function (id) {
            return id !== exerciseId;
          });
        },
        error: function () {
          rowEl.find(".batch-result-del").prop("disabled", false);
        },
      });
    },

    _getSheetComponent: function () {
      if (!this.parentComponent) return null;
      var musicComponent = _.find(this.parentComponent.components, function (comp) {
        return comp && typeof comp.hasComponent === "function" && comp.hasComponent("sheet");
      });
      return musicComponent ? musicComponent.getComponent("sheet") : null;
    },

    _importMusicXMLPreview: function (file) {
      var that = this;
      var fd = new FormData();
      fd.append("musicxml_file", file);
      fd.append("start", $("#musicxml-start-measure").val() || 0);
      fd.append("end", $("#musicxml-end-measure").val() || "");
      fd.append("complexity", $("#musicxml-complexity").val() || "");
      fd.append("harmony_key", this.keySignature.getKey() || "");

      this._setSavePanelFeedback("Importing MusicXML...");

      $.ajax({
        url: "/teacher/play/api/import-musicxml/preview/",
        type: "POST",
        data: fd,
        processData: false,
        contentType: false,
        headers: { "X-CSRFToken": that._getCsrfToken() },
        success: function (data) {
          that._setSavePanelFeedback("");
          if (data.success) {
            that._activeMusicXMLFile = file;
            that._pendingSaveJsonData = JSON.stringify(data.payload);
            
            // Set form values
            $("#play-save-description").val(data.title || file.name.split('.')[0]);
            $("#musicxml-complexity").val(data.complexity || 1);
            
            // Sync key signature model
            if (data.key) {
              that.keySignature.changeKey(data.key, true);
            }
            
            // Suggested units
            that._suggestedUnits = {};
            $.each(data.suggested_units || [], function (i, unitNum) {
              that._suggestedUnits[String(unitNum)] = true;
            });
            that._applySuggestedUnits();
            
            // Set mode restrictions
            if (data.route === "chordal") {
              $("#play-save-mode option[value='roman']").prop("disabled", false).show();
              $("#play-save-mode option[value='figures']").prop("disabled", false).show();
            } else {
              $("#play-save-mode option[value='roman']").prop("disabled", true).hide();
              $("#play-save-mode option[value='figures']").prop("disabled", true).hide();
              var curVal = $("#play-save-mode").val();
              if (curVal === "roman" || curVal === "figures") {
                $("#play-save-mode").val("play");
              }
            }

            // Show options
            $("#play-save-musicxml-options").show();
            
            // Load onto sheet
            var sheet = that._getSheetComponent();
            if (sheet) {
              sheet.setCorpusPayload(data.payload);
              sheet.render();
            }
            
            // Open/focus save panel
            if ($("#play-save-panel").length) {
              $("html, body").animate({ scrollTop: $("#play-save-panel").offset().top - 16 }, 180);
              $("#play-save-description").trigger("focus");
            }
            that._validateSavePanel(false);
          } else {
            that._setSavePanelFeedback(data.error || "Failed to preview MusicXML.");
          }
        },
        error: function (xhr) {
          var msg = "Failed to preview MusicXML.";
          try {
            msg = JSON.parse(xhr.responseText).error || msg;
          } catch (e) {}
          that._setSavePanelFeedback(msg);
        }
      });
    },

    _submitMusicXMLSaveDialog: function (feedbackEl) {
      var that = this;
      $("#play-save-submit").prop("disabled", true);
      feedbackEl.text("").removeClass("is-visible");

      var description = $.trim($("#play-save-description").val());
      var unitVals = this._getSelectedUnits();
      var freeTags = $("#play-save-tags").val();
      var isPublic = $("#play-save-public").is(":checked");
      var saveAsOfficial = this._isSuperuser && $("#play-save-official-row").is(":visible") && $("#play-save-official").is(":checked");
      var createTranspositions = $("#play-save-create-transpositions").is(":checked");
      var keySet = this._getSelectedKeySet();
      var selectedMode = $("#play-save-mode").val() || "play";

      var playlistSelectVal = $("#play-save-playlist").val();
      var playlistId = null;
      var playlistName = null;
      var isAdaptive = false;
      if (playlistSelectVal === "__new__") {
        playlistName = $.trim($("#play-save-new-playlist-name").val()) || null;
        isAdaptive = $("#play-save-adaptive").is(":checked");
      } else if (playlistSelectVal) {
        playlistId = playlistSelectVal;
      }

      var fd = new FormData();
      fd.append("musicxml_file", this._activeMusicXMLFile);
      fd.append("description", description);
      
      $.each(unitVals, function (i, u) {
        fd.append("unit", u);
      });

      fd.append("tags", freeTags);
      fd.append("is_public", isPublic);
      fd.append("save_as_official", saveAsOfficial);
      fd.append("start", $("#musicxml-start-measure").val() || 0);
      fd.append("end", $("#musicxml-end-measure").val() || "");
      fd.append("harmony_key", this.keySignature.getKey() || "jC_");
      fd.append("complexity", $("#musicxml-complexity").val() || 1);
      fd.append("mode", selectedMode);

      if (playlistId !== null) {
        fd.append("playlist_id", playlistId);
      }
      if (playlistName !== null) {
        fd.append("playlist_name", playlistName);
        fd.append("is_adaptive", isAdaptive);
      }

      fd.append("create_transpositions", createTranspositions);
      fd.append("key_set", $("#play-save-key-set").val() || "");

      $.ajax({
        url: "/teacher/play/api/import-musicxml/save/",
        type: "POST",
        data: fd,
        processData: false,
        contentType: false,
        headers: { "X-CSRFToken": that._getCsrfToken() },
        success: function (data) {
          if (that.feedback) {
            that.feedback.emit("play.save.success", { inlineEl: "#save-feedback" });
          }
          
          // Clear active file and payload
          that._activeMusicXMLFile = null;
          that._pendingSaveJsonData = null;
          $("#play-save-musicxml-options").hide();
          $("#musicxml-upload-input").val("");
          
          // Reset sheet to normal blackboard state (clears corpus rendering)
          var sheet = that._getSheetComponent();
          if (sheet) {
            sheet.clearCorpusPayload();
            sheet.render();
          }

          that.broadcast(EVENTS.BROADCAST.PLAY_SAVED, {
            exerciseId: data.id,
            reviewStatus: data.reviewStatus,
            playlistId: data.playlistId || null,
            playlistName: data.playlistName || null,
            create_transpositions: createTranspositions,
            key_set: keySet,
            is_official: saveAsOfficial,
          });
        },
        error: function (xhr) {
          $("#play-save-submit").prop("disabled", false);
          var errMsg = null;
          try {
            errMsg = JSON.parse(xhr.responseText).error || null;
          } catch (e) {}
          
          var feedbackId = "play.save.invalid_meter";
          if (errMsg) {
            var lower = errMsg.toLowerCase();
            if (lower.indexOf("tag") !== -1) {
              feedbackId = "play.save.invalid_tags";
            } else if (lower.indexOf("locked") !== -1 || lower.indexOf("playlist") !== -1) {
              feedbackId = "play.save.playlist_locked";
            } else if (lower.indexOf("official") !== -1 || lower.indexOf("superuser") !== -1 || xhr.status === 403) {
              feedbackId = "play.save.forbidden_official";
            }
          }
          
          if (that.feedback) {
            that.feedback.emit(feedbackId, {
              inlineEl: "#play-save-dialog-feedback",
              params: { bar: "?", beats: "?", expected: "?" }
            });
          } else {
            that._setSavePanelFeedback(errMsg || "Could not save exercise.");
          }
        }
      });
    },

  });

  return MusicControlsComponent;
});
