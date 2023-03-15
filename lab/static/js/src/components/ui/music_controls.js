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
  StaffDistributionWidget
) {
  /**
   * Defines whether the shortcuts are enabled by default or not.
   * @type {boolean}
   * @const
   */
  var KEYBOARD_SHORTCUTS_ENABLED = Config.get(
    "general.keyboardShortcutsEnabled"
  );
  /**
   * Defines the default keyboard size.
   * @type {number}
   * @const
   */
  var DEFAULT_KEYBOARD_SIZE = Config.get("general.defaultKeyboardSize");
  var DEFAULT_OCTAVE_ADJUSTMENT = Config.get("general.defaultOctaveAdjustment");

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
        DEFAULT_KEYBOARD_SIZE = sticky_settings.keyboard_size;
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

    if (settings.exerciseContext) {
      this.exerciseContext = settings.exerciseContext;
    } else {
      this.exerciseContext = false;
    }

    this.addComponent(new ModalComponent());

    this.headerEl = $(settings.headerEl);
    this.containerEl = $(settings.containerEl);

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
      $(".js-btn-upload-json").on("mousedown", () =>
        this.onClickSaveJSON("upload")
      );
      $(".js-btn-download-json").on("mousedown", () => this.onClickSaveJSON());
      $(".js-btn-pristine").on("mousedown", () => this.onClickPristine());
      $(".js-btn-nextexercise").on("mousedown", () =>
        this.onClickNextExercise()
      );
      $(".js-btn-previousexercise").on("mousedown", () =>
        this.onClickPreviousExercise()
      );
      $(".js-btn-firstexercise").on("mousedown", () =>
        this.onClickFirstExercise()
      );

      this.initControlsLayout();
      this.initKeySignatureTab();
      this.initNotationTab();
      this.renderInstrumentSelect();
      this.renderKeyboardSizeSelect();
      this.renderOctaveAdjustment();
      this.renderKeyboardShortcuts();
      this.initMidiTab();
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
      var analyze_widget = new AnalyzeWidget(
        analysisSettings,
        is_exercise_view
      );
      var highlight_widget = new HighlightWidget(
        highlightSettings,
        is_exercise_view
      );
      var staff_distribution_widget = new StaffDistributionWidget(
        staffDistribution,
        is_exercise_view
      );
      var event_for = {
        highlight: EVENTS.BROADCAST.HIGHLIGHT_NOTES,
        analyze: EVENTS.BROADCAST.ANALYZE_NOTES,
        distribute: EVENTS.BROADCAST.DISTRIBUTE_NOTES,
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

      highlight_widget.bind("changeCategory", onChangeCategory);
      highlight_widget.bind("changeOption", onChangeOption);

      analyze_widget.bind("changeCategory", onChangeCategory);
      analyze_widget.bind("changeOption", onChangeOption);

      staff_distribution_widget.bind("changeValue", onChangeValue);

      analyze_widget.render();
      highlight_widget.render();
      staff_distribution_widget.render();

      el.append(
        analyze_widget.el,
        highlight_widget.el,
        staff_distribution_widget.el
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
      var selected = DEFAULT_KEYBOARD_SIZE;

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
      var options = tpl({ adjustments: [-2, -1, 0, 1, 2] });
      var selected = DEFAULT_OCTAVE_ADJUSTMENT;

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
      var $canvas = $("#staff-area canvas");
      var $target = $(evt.target);
      var data_url = $canvas[0].toDataURL();
      $target[0].href = data_url;
      $target[0].target = "_blank";
      return true;
    },
    /**
     * Handler to upload or download JSON data for the current notation.
     *
     * @param {string} destination
     * @return {boolean} true
     */
    onClickSaveJSON: function (destination = "download") {
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
        $.ajax({
          type: "POST",
          url: window.location.origin + "/exercises/add/",
          data: { data: json_data },
          dataType: "json",
          success: function (data) {
            let exerciseID = data.id;
            window.alert(
              `Exercise uploaded! Exercise ID: ${exerciseID}. Taking you to the new exercise now.`
            );
            window.open(`/dashboard/exercises/${exerciseID}/`, "_blank");
          },
          error: function (error) {
            console.log(error);
          },
        });
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
  });

  return MusicControlsComponent;
});
