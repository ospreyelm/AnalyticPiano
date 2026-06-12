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

      this.subscribe(EVENTS.BROADCAST.PLAY_SAVED, (data) =>
        this.targetSelector.open(data.exerciseId)
      );
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
        this._openSaveDialog(json_data);
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
     * Opens the save-exercise dialog, fetches authoring-meta to populate it,
     * and wires up submit/cancel.
     *
     * @param {string} json_data  Serialised JSON payload (already stringified)
     * @return undefined
     */
    _openSaveDialog: function (json_data) {
      var that = this;
      var overlayEl = $("#play-save-dialog-overlay");
      var feedbackEl = $("#play-save-dialog-feedback");

      // Reset dialog state
      $("#play-save-description").val("Play view chordal exercise");
      $("#play-save-unit").html('<option value="">— no unit —</option>');
      $("#play-save-tags").val("");
      $("#play-save-playlist").html('<option value="">— none —</option><option value="__new__">New playlist…</option>');
      $("#play-save-new-playlist-row").hide();
      $("#play-save-new-playlist-name").val("");
      $("#play-save-public").prop("checked", false);
      $("#play-save-official").prop("checked", false);
      $("#play-save-official-row").hide();
      feedbackEl.text("").removeClass("is-visible");

      overlayEl.show();

      // Fetch authoring-meta to populate unit/playlist dropdowns
      $.ajax({
        type: "GET",
        url: window.location.origin + "/exercises/authoring-meta/",
        dataType: "json",
        success: function (meta) {
          // Populate units
          var unitSelect = $("#play-save-unit");
          $.each(meta.units || [], function (i, u) {
            unitSelect.append(
              $("<option>").val(u.n).text("Unit " + u.n + (u.title ? " — " + u.title : ""))
            );
          });

          // Populate playlists (locked ones disabled)
          var playlistSelect = $("#play-save-playlist");
          // Remove the __new__ option temporarily, re-append at end
          playlistSelect.html('<option value="">— none —</option>');
          $.each(meta.playlists || [], function (i, pl) {
            var optEl = $("<option>").val(pl.id).text(pl.name + (pl.locked ? " (locked)" : ""));
            if (pl.locked) {
              optEl.prop("disabled", true);
            }
            playlistSelect.append(optEl);
          });
          playlistSelect.append($("<option>").val("__new__").text("New playlist…"));

          // Show official checkbox only for superusers
          if (meta.isSuperuser) {
            $("#play-save-official-row").show();
          }
        },
        error: function () {
          // Non-fatal: dialog still usable without dropdowns populated
          console.warn("[play-save] Could not fetch authoring-meta");
        },
      });

      // Wire playlist select: show/hide new-name input
      $("#play-save-playlist").off("change.playsave").on("change.playsave", function () {
        if ($(this).val() === "__new__") {
          $("#play-save-new-playlist-row").show();
        } else {
          $("#play-save-new-playlist-row").hide();
        }
      });

      // Wire cancel button
      $("#play-save-cancel").off("click.playsave").on("click.playsave", function () {
        overlayEl.hide();
      });

      // Close on overlay background click
      overlayEl.off("click.playsave").on("click.playsave", function (e) {
        if ($(e.target).is(overlayEl)) {
          overlayEl.hide();
        }
      });

      // Wire submit button
      $("#play-save-submit").off("click.playsave").on("click.playsave", function () {
        that._submitSaveDialog(json_data, overlayEl, feedbackEl);
      });
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

      var description = $.trim($("#play-save-description").val());
      if (!description) {
        feedbackEl.text("Description is required.").addClass("is-visible");
        return;
      }

      // Build skill tags array: optional unit: prefix + free tags
      var skillTags = [];
      var unitVal = $("#play-save-unit").val();
      if (unitVal) {
        skillTags.push("unit:" + unitVal);
      }
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
      var saveAsOfficial = $("#play-save-official").is(":checked");

      var playlistSelectVal = $("#play-save-playlist").val();
      var playlistId = null;
      var playlistName = null;
      if (playlistSelectVal === "__new__") {
        playlistName = $.trim($("#play-save-new-playlist-name").val()) || null;
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
      if (playlistId !== null) {
        payload.playlistId = playlistId;
      }
      if (playlistName !== null) {
        payload.playlistName = playlistName;
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
          overlayEl.hide();
          if (that.feedback) {
            that.feedback.emit("play.save.success", { inlineEl: "#save-feedback" });
          }
          that.broadcast(EVENTS.BROADCAST.PLAY_SAVED, {
            exerciseId: data.id,
            reviewStatus: data.reviewStatus,
            playlistId: data.playlistId || null,
            playlistName: data.playlistName || null,
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
          }
        },
      });
    },
  });

  return MusicControlsComponent;
});
