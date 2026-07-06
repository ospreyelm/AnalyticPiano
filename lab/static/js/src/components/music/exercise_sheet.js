import $ from "jquery";
import $UI from "jquery-ui";
import _ from "lodash";
import Vex from "vexflow";
import Config from "app/config";
import Analyze from "app/utils/analyze";
import EVENTS from "app/components/events";
import Component from "app/components/component";
import FontParser from "app/utils/fontparser";
import Stave from "./stave";
import StaveNotater from "./stave_notater";
import ExerciseNoteFactory from "./exercise_note_factory";
import VexFlowAdapter from "./rendering/vexflow_adapter";
import ScoreTimeline from "./score_timeline";
import TextInput from "app/components/input/text_input";
import ScorePlayer from "app/models/score_player";
import IdentificationSubmitFlow from "app/models/identification_submit_flow_logic";
import KeyContext from "app/models/key_context_logic";
import renderPlaybackControls from "app/components/music/playback_controls";
import MeasureEngine from "app/utils/measure_engine";
import HarmonizationRealizationLogic from "app/models/harmonization_realization_logic";
import IdentificationLabelLayoutLogic from "app/components/music/identification_label_layout_logic";
import ChordalProblemsLogic from "app/models/chordal_problems_logic";
import ChordalUMTOStaffDistribution from "./chordal_umto_staff_distribution";
import KeySignature from "app/models/key_signature";
import ChordalSpelling from "./chordal_spelling";
import ChordalBarlinesLogic from "app/utils/chordal_barlines_logic";
import UMTOScoreConverter from "app/utils/umto_score_converter";
import BarlineSpacingUtils from "app/utils/barline_spacing_utils";
import ExerciseSheetIdentification from "./exercise_sheet_identification";
import ExerciseSheetIdentificationInputMode from "./exercise_sheet_identification_input_mode";
import ExerciseSheetIdentificationCanvas from "./exercise_sheet_identification_canvas";
import ExerciseSheetIdentificationControls from "./exercise_sheet_identification_controls";
import ExerciseSheetStatus from "./exercise_sheet_status";
import ExerciseSheetStaves from "./exercise_sheet_staves";
import ExerciseSheetPlayback from "./exercise_sheet_playback";
import ExerciseSheetIdentificationLogic from "./exercise_sheet_identification_logic";

/**
   * Defines the size of the chord bank (how many chords to display on
   * screen).
   * @type {number}
   */
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  var SETTING_HIDE_NEXT = Config.get("general.hideNextForAutoAdvance");

  var NUMBERED_EXERCISE_COUNT = Config.get("general.numberedExerciseCount");

  /**
   * ExerciseSheetComponent
   *
   * This object is responsible for knowing how to display plain sheet music
   * notation with the notes that have sounded (saved in the chord bank) and
   * are currently sounding via MIDI input or some other means. So this object
   * should know how to display the grand staff and configure it for analysis,
   * highlight, etc.
   *
   * @constructor
   * @param {object} settings
   * @param {ChordBank} settings.chords Required property.
   * @param {KeySignature} settings.keySignature Required property.
   */
  var ExerciseSheetComponent = function (settings) {
    this.settings = settings || {};

    if ("exerciseContext" in this.settings) {
      this.exerciseContext = this.settings.exerciseContext;
    } else {
      throw new Error("Missing parameter property: .exerciseContext");
    }

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("Missing parameter property: .keySignature");
    }

    if ("timeSignature" in this.settings.exerciseContext) {
      this.timeSignature = this.settings.exerciseContext.timeSignature;
    } else {
      throw new Error("Missing parameter property: .timeSignature");
    }

    this._inputSourceMode = "live";
    this._staffLayout = null;
    this._clickNoteComponent = null;
    this._ghost = null;
    this._ghostCanvasEl = null;

    _.bindAll(this, ["render", "onChordsUpdate", "onMidiNote", "onClickPristine", "onSubmitIdentification", "onToggleMode", "_onIdentKeyDown"]);
  };

  ExerciseSheetComponent.prototype = new Component();

  _.extend(
    ExerciseSheetComponent.prototype,
    ExerciseSheetIdentification,
    ExerciseSheetIdentificationInputMode,
    ExerciseSheetIdentificationCanvas,
    ExerciseSheetIdentificationControls,
    ExerciseSheetStatus,
    ExerciseSheetStaves,
    ExerciseSheetPlayback,
    ExerciseSheetIdentificationLogic,
    {
    /**
     * Initializes the sheet.
     *
     * @param {object} config
     * @return undefined
     */
    initComponent: function () {
      this.el = $("canvas#staff");
      this.el[0].width = this.el.width();
      this.el[0].height = this.el.height();
      this.initRenderer();
      this.initStaves();
      this.initListeners();
      var definition = this.exerciseContext.getDefinition();
      // Chorale-specific init
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        this.initChoraleMode();
      }
      if (this._isIdentificationLikeExercise()) {
        this.initIdentificationMode();
      }

      // Playback
      var self = this;
      this.scorePlayer = new ScorePlayer(this.settings.midiDevice);
      this.scorePlayer.bind("tick", function (windowIndex) {
        self._playbackWindowIndex = windowIndex;
        self._drawPlaybackHighlight();
      });
      this.scorePlayer.bind("stopped", function () {
        self._playbackWindowIndex = null;
        self._clearPlaybackHighlight();
      });
      this._playbackWindowIndex = null;
    },
    /**
     * Initializes the canvas renderer and dom element.
     *
     * @return
     */
    initRenderer: function () {
      var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
      this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
      this.renderExerciseInfo();
      this.renderExerciseText();
    },
    /**
     * Initializes the staves that together will form the grand staff.
     *
     * @return undefined
     */
    initStaves: function () {
      this.updateStaves();
    },
    /**
     * Initializes event listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      this.parentComponent.bind("change", this.render);
      this.keySignature.bind("change", this.render);
      //this.getInputChords().bind('change', this.render);
      this.getInputChords().bind("change", this.onChordsUpdate);
      this.getInputChords().bind("clear", this.onChordsUpdate);
      this.exerciseContext.bind("goto", this.onGoToExercise);
      // Re-render when ident page changes (goToIdentPage fires "graded")
      this.exerciseContext.bind("graded", this.render);
      // Listen for MIDI notes globally
      this.subscribe(EVENTS.BROADCAST.NOTE, this.onMidiNote);
      // Listen for pristine/refresh button
      this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onClickPristine);
      // Arrow key page navigation for identification exercises
      window.removeEventListener("keydown", this._onIdentKeyDown, true);
      window.addEventListener("keydown", this._onIdentKeyDown, true);
    },
    /**
     * Chorale mode setup: ensure grader is initialized; keep display settings
     */
    initChoraleMode: function () {
      var def = this.exerciseContext.getDefinition();
      var display = def && def.getDisplay ? def.getDisplay() : {};
      var configuredMaxMeasures = parseInt(display && display.maxMeasures, 10);
      var maxMeasures = configuredMaxMeasures > 0 ? configuredMaxMeasures : 4;
      this._chorale = { maxMeasures: maxMeasures, startMeasure: 0 };
      console.log("[Chorale] initChoraleMode called");
      try {
        var score = def.getScore ? def.getScore() : null;
        console.log("[Chorale] score keys:", score ? Object.keys(score) : "null", "has umto:", !!(score && score.umto));
        if (score && score.umto && !ChordalProblemsLogic.shouldPreserveChordalMeasures(score)) {
          var converted = UMTOScoreConverter.convertUMTOToProcessedScore(score.umto);
          if (converted) {
            def.exercise.score = converted;
            console.log("[Chorale] Patched exercise.score from UMTO conversion:", converted.measures ? converted.measures.length : 0, "measures");
          }
        }
        if (def.isChorale && def.isChorale() && this.exerciseContext.grader && this.exerciseContext.grader.initFromDefinition) {
          this.exerciseContext.grader.initFromDefinition(def);
        }
      } catch (e) {
        console.error("[Chorale] initChoraleMode ERROR:", e && e.message, e);
      }
    },
    /**
     * Renders the grand staff and everything on it.
     *
     * @return this
     */
    render: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;
      if (this._isIdentificationLikeExercise()) {
        this._refreshIdentificationModeUI();
      }
      this.clear();
      this.renderStaves(exercise_midi_nums);
      this.renderExerciseStatus();
      if (this._isIdentificationLikeExercise()) {
        this.renderExerciseText();
      }
      this.clearGhostNote();

      // Playback controls — only for chorale exercise types (idempotent)
      var definition = this.exerciseContext.getDefinition();
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        var $toolbar = $("#staff-toolbar");
        if ($toolbar.length) {
          var self = this;
          renderPlaybackControls($toolbar, this.scorePlayer, function () {
            return self._calculatePlaybackOffsets();
          });
        }
      }
      this._calculatePlaybackOffsets();
      this.autoScroll();

      // Simple Debug Overlay
      if (window.location.search.indexOf('debug=1') !== -1) {
        this._renderDebugOverlay();
      }

      return this;
    },

    _measureTotalTicks: function () {
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore ? definition.getScore() : null;
      var meta = (score && score.meta) || {};
      var tsRaw = meta.time || meta.meter || meta.time_signature || "4/4";
      var tsParts = String(tsRaw).split("/");
      var numerator = parseInt(tsParts[0], 10) || 4;
      var denominator = parseInt(tsParts[1], 10) || 4;
      return numerator * (4096 / denominator);
    },

    setClickNoteComponent: function (comp) {
      this._clickNoteComponent = comp;
    },

    getStaffLayout: function () {
      return this._staffLayout || null;
    },

    setInputSourceMode: function (mode) {
      this._inputSourceMode = mode;
    },

    _renderDebugOverlay: function () {
      $('#id-debug-overlay').remove();
      var problems = this.exerciseContext.getDefinition().getProblems();
      var overlay = $('<div id="id-debug-overlay" style="position:fixed; top:10px; right:10px; background:rgba(0,0,0,0.8); color:white; padding:10px; font-size:10px; z-index:9999; max-height:80vh; overflow-y:auto; border-radius:5px; font-family:monospace;"></div>');
      overlay.append('<h3 style="margin:0 0 10px 0;">UMTO Logic Auditor</h3>');
      var table = $('<table border="1" style="border-collapse:collapse; width:100%;"><tr><th>Idx</th><th>Off</th><th>Ans</th><th>Tgt</th></tr></table>');
      _.each(problems, function(p, i) {
        var row = $('<tr></tr>');
        row.append('<td style="padding:2px;">'+i+'</td>');
        row.append('<td style="padding:2px;">'+p.onset.toFixed(2)+'</td>');
        row.append('<td style="padding:2px;">'+p.answer+'</td>');
        row.append('<td style="padding:2px;">'+(p.hidden?'No':'Yes')+'</td>');
        table.append(row);
      });
      overlay.append(table);
      $('body').append(overlay);
    },
    /**
     * Clears the sheet.
     *
     * @return this
     */
    clear: function () {
      this.vexRenderer.getContext().clear();
      return this;
    },
    /**
     * Returns the width of the sheet.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.el.width();
    },
    /**
     * Returns the height of the sheet.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.el.height();
    },
    /**
     * Returns the analysis settings of the sheet.
     *
     * @return {object}
     */
    getAnalyzeConfig: function () {
      return this.parentComponent.analyzeConfig;
    },
    /**
     * Returns the highlight settings of the sheet.
     *
     * @return {object}
     */
    getHighlightConfig: function () {
      return this.parentComponent.highlightConfig;
    },
    /**
~     * Returns the chords for display.
     *
     * @return undefined
     */
    getDisplayChords: function () {
      return this.exerciseContext.getDisplayChords();
    },
    /**
     * Returns the chords for exercise analysis.
     *
     * @return undefined
     */
    getExerciseChords: function () {
      return this.exerciseContext.getExerciseChords();
    },
    /**
     * Returns the time signature for display.
     *
     * @return undefined
     */
    getTimeSignature: function () {
      return this.exerciseContext.getTimeSignature();
    },
    /**
     * Obtain semibreves per line for horizontal scaling.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.exerciseContext.getSemibrevesPerLine();
    },
    /**
     * Returns the input chords.
     *
     * @return undefined
     */
    getInputChords: function () {
      return this.exerciseContext.getInputChords();
    },
  });

export default ExerciseSheetComponent;
