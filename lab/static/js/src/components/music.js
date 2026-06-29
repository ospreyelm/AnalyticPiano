import $ from "jquery";
import _ from "lodash";
import Config from "app/config";
import EVENTS from "app/components/events";
import Component from "app/components/component";
import KeySignature from "app/models/key_signature";

/**
   * This is a map of analysis modes to booleans indicating whether the mode
   * is enabled or disabled by default.
   * @type {object}
   */
  var ANALYSIS_SETTINGS = Config.get("general.analysisSettings");
  /**
   * This is a map of highlight modes to booleans indicating whether the mode
   * is enabled or disabled by default.
   * @type {object}
   */
  var HIGHLIGHT_SETTINGS = Config.get("general.highlightSettings");

  const VALID_STAFF_DISTRIBUTIONS = Config.get(
    "general.validStaffDistributions"
  );
  var STAFF_DISTRIBUTION = Config.get("general.staffDistribution");

  if (false) {
    sessionStorage.removeItem("staffDistribution"); // retire this function
  } else {
    var storage_staff_dist = sessionStorage.getItem("staffDistribution");
    if (
      storage_staff_dist &&
      VALID_STAFF_DISTRIBUTIONS.includes(storage_staff_dist)
    ) {
      STAFF_DISTRIBUTION = storage_staff_dist;
    }
  }

  /**
   * Creates an instance of MusicComponent.
   *
   * This object is responsible for displaying the sheet music and
   * handling runtime configuration changes.
   *
   * @constructor
   * @param {object} settings
   * @param {Sheet} settings.sheet Required property.
   */
  var MusicComponent = function (settings) {
    this.settings = settings || {};
    this.settings.analysisSettings = this.settings.analysisSettings || {};
    this.settings.highlightSettings = this.settings.highlightSettings || {};

    /**
     * Defines the music element.
     * @type {jQuery}
     */
    this.el = $("<div></div>");
    /**
     * Configuration settings for highlighting notes on the sheet music.
     * @type {object}
     */
    this.highlightConfig = _.extend(
      {},
      HIGHLIGHT_SETTINGS,
      this.settings.highlightSettings
    );
    /**
     * Configuration settings for analyzing notes on the sheet music.
     * @type {object}
     */
    this.analyzeConfig = _.extend(
      { tempo: false },
      ANALYSIS_SETTINGS,
      this.settings.analysisSettings
    );
    /**
     * Configuration settings for staff distribution on the sheet music.
     * @type {object}
     */
    this.staffDistributionConfig = _.extend(
      {},
      STAFF_DISTRIBUTION,
      this.settings.sheet?.chords?.settings || {}
    );

    if (!("sheet" in this.settings)) {
      throw new Error("missing settings.sheet parameter");
    }

    // this.setComponent("pristine", this.settings.pristine);
    this.setComponent("sheet", this.settings.sheet);

    _.bindAll(this, [
      "onAnalyzeChange",
      "onHighlightChange",
      "onStaffDistributionChange",
      "onMetronomeChange",
      "onRedrawRequest",
      "onNextExerciseRequest",
      "onPreviousExerciseRequest",
      "onFirstExerciseRequest",
    ]);
  };

  MusicComponent.prototype = new Component();

  _.extend(MusicComponent.prototype, {
    /**
     * Initializes the music.
     *
     * @return undefined
     */
    initComponent: function () {
      this.initListeners();
    },
    /**
     * Initializes event listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      this.subscribe(EVENTS.BROADCAST.HIGHLIGHT_NOTES, this.onHighlightChange);
      this.subscribe(EVENTS.BROADCAST.ANALYZE_NOTES, this.onAnalyzeChange);
      this.subscribe(
        EVENTS.BROADCAST.DISTRIBUTE_NOTES,
        this.onStaffDistributionChange
      );
      this.subscribe(EVENTS.BROADCAST.METRONOME, this.onMetronomeChange);
      this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onRedrawRequest);
      this.subscribe(EVENTS.BROADCAST.NEXTEXERCISE, this.onNextExerciseRequest);
      this.subscribe(
        EVENTS.BROADCAST.PREVIOUSEXERCISE,
        this.onPreviousExerciseRequest
      );
      this.subscribe(
        EVENTS.BROADCAST.FIRSTEXERCISE,
        this.onFirstExerciseRequest
      );
    },
    /**
     * Renders the music.
     *
     * @return this
     */
    render: function () {
      this.renderSheet();
      return this;
    },
    /**
     * Renders the sheet.
     *
     * @return this
     */
    renderSheet: function () {
      var sheetComponent = this.getComponent("sheet");

      if (sheetComponent.hasOwnProperty("exerciseContext")) {
        // NOT WHAT WE NEED
        // console.log('previously performed:', sheetComponent.exerciseContext.settings.definition.settings.definition.exerciseIsPerformed);
        // console.log('most recent error count:', sheetComponent.exerciseContext.settings.definition.settings.definition.exerciseErrorCount);
      }

      sheetComponent.clear();

      if (sheetComponent.hasOwnProperty("exerciseContext")) {
        var exercise_midi_nums =
          sheetComponent.exerciseContext.exerciseChords._items.map((item) =>
            item.getNoteNumbers()
          );
        sheetComponent.render(exercise_midi_nums);
      } else {
        sheetComponent.render();
      }
      return this;
    },
    renderPristine: function (exerciseAction = "reload") {
      var sheetComponent = this.getComponent("sheet");
      if (sheetComponent.scorePlayer && sheetComponent.scorePlayer.isPlaying()) {
        sheetComponent.scorePlayer.stop();
      }
      if (!sheetComponent.hasOwnProperty("exerciseContext")) {
        /* play view */
        sheetComponent.chords.clear();
        if (typeof sheetComponent.clearCorpusPayload === "function") {
          sheetComponent.clearCorpusPayload();
        }
        $("#play-save-musicxml-options").hide();
        var fileInput = $("#musicxml-upload-input");
        if (fileInput.length) {
          fileInput.val("");
        }
      } else {
        /* exercise view */
        let scex = sheetComponent.exerciseContext;
        let setdef = scex.settings.definition;

        // Save current identification state before navigating away
        if (scex._isIdentificationExercise && scex._isIdentificationExercise()) {
          scex.saveIdentState();
          scex.submitIdentificationAnswers({ is_page_submit: false });
        }

        // The following was used to generate newData as we built this function
        // let currentData = JSON.stringify(setdef.settings.definition, null, 0);
        let newData = {};
        function loadDefinition(targetExerciseNum, targetExerciseId) {
          var requestUrl = window.PLAYER_DEFINITION_URL || "definition";
          var requestData;

          if (window.PLAYER_DEFINITION_URL) {
            requestData = {
              playlist: setdef.settings.definition.playlistId,
              exercise_num: targetExerciseNum,
            };
          } else {
            requestData = {
              playlist_name: setdef.settings.definition.playlistName,
              exercise_id: targetExerciseId,
              exercise_num: targetExerciseNum,
            };
          }

          $.ajax({
            type: "GET",
            url: requestUrl,
            async: false,
            data: requestData,
            dataType: "json",
            success: function (data) {
              if (data.redirect) {
                window.location.href = data.redirect;
                return;
              }
              newData = data;
            },
          });
        }
        // var testing = (window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false);
        if (exerciseAction === "reload") {
          loadDefinition(
            setdef.settings.definition.exerciseNum,
            setdef.settings.definition.exerciseId
          );

          if (!Object.keys(newData).length) {
            console.log("Error reloading exercise data!");
            return null;
          }
        } else if (
          exerciseAction === "next" &&
          setdef.settings.definition.nextExerciseId
        ) {
          loadDefinition(
            setdef.settings.definition.nextExerciseNum,
            setdef.settings.definition.nextExerciseId
          );

          if (!Object.keys(newData).length) {
            console.log("No next exercise; end of playlist");
            return null;
          }
        } else if (
          exerciseAction === "previous" &&
          setdef.settings.definition.previousExerciseId
        ) {
          loadDefinition(
            setdef.settings.definition.previousExerciseNum,
            setdef.settings.definition.previousExerciseId
          );

          if (!Object.keys(newData).length) {
            console.log("No previous exercise; start of playlist");
            return null;
          }
        } else if (exerciseAction === "first") {
          loadDefinition(1, setdef.settings.definition.firstExerciseId);

          if (!Object.keys(newData).length) {
            console.log("Error finding first exercise!");
            return null;
          }
        }

        // Prevents notes from slipping through the cracks when going between exercises
        this.broadcast(EVENTS.BROADCAST.CLEAR_NOTES);
        // Prevents issues with chord bank when advancing with sustain on
        this.broadcast(EVENTS.BROADCAST.PEDAL, "sustain", "off", "ui");

        scex.inputChords.clear();
        scex.inputChords.goTo(0);
        sheetComponent.barlines = [];
        this.settings.sheet.barlines = [];

        // TODO: work in progress code to enable URL to change dynamically with exercise without refreshing
        //   postponed because of wide range of intersections/conflicts with Django's view features
        if (!!newData?.exerciseNum && !window.PLAYER_DEFINITION_URL) {
          const newPath = location.pathname.split("/").slice(0, -2);
          newPath.push(newData.exerciseNum);
          newPath.push("");
          window.history.replaceState("", "", newPath.join("/"));
        }

        if (Object.keys(newData).length) {
          scex.definition.exercise = scex.definition.parse(newData);

          scex.definition.settings.definition = newData;

          scex.settings.definition.exercise = scex.definition.parse(newData);

          scex.settings.definition.settings.definition = newData;

          if (window.refreshPlayerChrome) {
            window.refreshPlayerChrome(newData);
          }

          sheetComponent.keySignature = new KeySignature(
            newData.key,
            newData.keySignature
          );

          sheetComponent.settings.keySignature = new KeySignature(
            newData.key,
            newData.keySignature
          );

          this.settings.staffDistribution = newData.staffDistribution;

          this.staffDistributionConfig.staffDistribution =
            newData.staffDistribution;

          sheetComponent.timeSignature = newData.timeSignature;

          // FIX ME: BEST ROUTE TO THIS PROPERTY?
          try {
            this.parentComponent.models.exerciseContext.timeSignature =
              newData.timeSignature;
          } catch (err) {
            console.log(
              "Cannot find this.parentComponent.models.exerciseContext.timeSignature"
            );
          }

          /* similar to updateSettings */
          // is there a way to do these things once each?
          Object.assign(this.analyzeConfig, newData.analysis);
          Object.assign(this.settings.analysisSettings, newData.analysis);
          // Object.assign(this.staffDistributionConfig.analysisSettings, newData.analysis);

          Object.assign(this.highlightConfig, newData.highlight);
          Object.assign(this.settings.highlightSettings, newData.highlight);
          // Object.assign(this.staffDistributionConfig.highlightSettings, newData.highlight);
          /* could add use of listeners here to update the menu */

          scex.inputChords.staffDistribution = newData.staffDistribution;

          // Reset stateful grading modes before creating display and exercise chords
          if ((scex.definition.isChorale && scex.definition.isChorale()) ||
              (scex.definition.isChoraleIdentification && scex.definition.isChoraleIdentification())) {
            if (typeof sheetComponent.initChoraleMode === "function") {
              sheetComponent.initChoraleMode();
            }
            // Clear prior answers so old labels don't flash on the new exercise.
            if (scex.grader && typeof scex.grader.reset === "function") {
              scex.grader.reset();
            }
            // Re-initialize chorale play grader from the new exercise score.
            // reset() clears the timeline; without re-init the grader has no
            // windows and ignores all MIDI input on the navigated-to exercise.
            if (scex.definition.isChorale && scex.definition.isChorale() &&
                !(scex.definition.isChoraleIdentification && scex.definition.isChoraleIdentification()) &&
                scex.grader && typeof scex.grader.initFromDefinition === "function") {
              scex.grader.initFromDefinition(scex.definition);
            }
          }

          if (scex._isHarmonizationExercise && scex._isHarmonizationExercise()) {
            if (scex._harmonizationSettleTimer) {
              clearTimeout(scex._harmonizationSettleTimer);
              scex._harmonizationSettleTimer = null;
            }
            if (scex._harmonizationHeldTracker) {
              scex._harmonizationHeldTracker.reset();
            }
            scex._harmonizationPointer = 0;
            scex.acceptedHarmonizationSonorities = [];
            scex.harmonizationVLScore = null;
            scex.harmonizationTier = null;
          }

          scex.displayChords = scex.createDisplayChords();
          scex.exerciseChords = scex.createExerciseChords();

          this.trigger("change");
        }

        // Restore identification state for new exercise (from cache or server)
        // Skip for chorale identification — answer indices are targeting-dependent and unstable.
        if (scex._isIdentificationExercise && scex._isIdentificationExercise() &&
            !(scex.definition.isChoraleIdentification && scex.definition.isChoraleIdentification())) {
          var newExerciseId = newData.exerciseId;
          scex.restoreIdentState(newExerciseId);
        }

        sheetComponent.renderExerciseInfo();
        sheetComponent.renderExerciseText();
        scex.sealed = false;
        scex.done = false;
        scex.graded = false;
        scex.timer = null;
        scex.timepoints = {};

        // window.console.dir('send dummy note');
        this.broadcast(EVENTS.BROADCAST.NOTE, "on", 109, 0);
        this.broadcast(EVENTS.BROADCAST.NOTE, "off", 109, 0);
        this.broadcast(EVENTS.BROADCAST.PEDAL, "sustain", "off", "refresh");

        scex.state = "ready"; // READY
      }

      sheetComponent.clear();
      sheetComponent.render();

      return this;
    },
    renderNextExercise: function () {
      var sheetComponent = this.getComponent("sheet");
      var context = sheetComponent && sheetComponent.exerciseContext;
      if (
        context &&
        typeof context.goToNextExercise === "function"
      ) {
        var handled = context.goToNextExercise({ fromUI: true });
        if (handled) {
          if (handled.completedExercise) {
            this.renderPristine("next");
          }
          return this;
        }
      }
      this.renderPristine("next");
    },
    renderPreviousExercise: function () {
      var sheetComponent = this.getComponent("sheet");
      var context = sheetComponent && sheetComponent.exerciseContext;
      if (
        context &&
        typeof context.goToPreviousExercise === "function"
      ) {
        var handled = context.goToPreviousExercise({ fromUI: true });
        if (handled) {
          return this;
        }
      }
      this.renderPristine("previous");
    },
    renderFirstExercise: function () {
      this.renderPristine("first");
    },
    /**
     * Returns the width.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.el.width();
    },
    /**
     * Returns the height.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.el.height();
    },
    /**
     * Handles a change to the highlight settings.
     *
     * @param {object} settings
     * @return undefined
     */
    onHighlightChange: function (settings) {
      this.updateSettings("highlightConfig", settings);
      this.trigger("change");
    },
    /**
     * Handles a change to the analyze settings.
     *
     * @param {object} settings
     * @return undefined
     */
    onAnalyzeChange: function (settings) {
      this.updateSettings("analyzeConfig", settings);
      this.trigger("change");
    },
    /**
     * Handles a change to the staff distribution setting.
     *
     * @param {object} settings
     * @return undefined
     */
    onStaffDistributionChange: function (value) {
      if (this.settings.sheet.chords == undefined) {
        return null;
      }
      this["staffDistributionConfig"].staffDistribution = value;
      this.settings.sheet.chords._items[0].settings.staffDistribution = value;
      var sheetComponent = this.getComponent("sheet");
      sheetComponent.chords.bank("redistribute");
    },
    /**
     * Handles a change to the metronome settings.
     *
     * @param {object} settings
     * @return undefined
     */
    onMetronomeChange: function (metronome) {
      if (metronome.isPlaying()) {
        this.analyzeConfig.tempo = metronome.getTempo();
      } else {
        this.analyzeConfig.tempo = false;
      }
      this.render();
    },
    onRedrawRequest: function () {
      this.renderPristine();
    },
    onNextExerciseRequest: function () {
      this.renderNextExercise();
    },
    onPreviousExerciseRequest: function () {
      this.renderPreviousExercise();
    },
    onFirstExerciseRequest: function () {
      this.renderFirstExercise();
    },
    /**
     * Updates settings.
     *
     * @param {string} prop
     * @param {object} setting
     * @return this
     */
    updateSettings: function (prop, setting) {
      var mode = _.cloneDeep(this[prop].mode);
      switch (setting.key) {
        case "enabled":
          this[prop].enabled = setting.value;
          break;
        case "mode":
          _.assign(mode, setting.value);
          this[prop].mode = mode;
          break;
        default:
          throw new Error("Invalid setting key");
      }
      return this;
    },
  });

export default MusicComponent;
