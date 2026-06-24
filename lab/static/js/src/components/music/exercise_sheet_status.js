/* global define: false */
define([
  "jquery",
  "jquery-ui",
  "lodash",
  "vexflow",
  "app/config",
  "app/utils/analyze",
  "app/components/events",
  "app/components/component",
  "app/utils/fontparser",
  "./stave",
  "./stave_notater",
  "./exercise_note_factory",
  "./rendering/vexflow_adapter",
  "./score_timeline",
  "app/components/input/text_input",
  "app/models/score_player",
  "app/models/identification_submit_flow_logic",
  "app/models/key_context_logic",
  "app/components/music/playback_controls",
  "app/utils/measure_engine",
  "app/models/harmonization_realization_logic",
  "app/components/music/identification_label_layout_logic",
  "app/models/chordal_problems_logic",
  "./chordal_umto_staff_distribution",
  "app/models/key_signature",
  "./chordal_spelling",
  "app/utils/chordal_barlines_logic",
  "app/utils/umto_score_converter",
  "app/utils/barline_spacing_utils",
], function (
  $,
  $UI,
  _,
  Vex,
  Config,
  Analyze,
  EVENTS,
  Component,
  FontParser,
  Stave,
  StaveNotater,
  ExerciseNoteFactory,
  VexFlowAdapter,
  ScoreTimeline,
  TextInput,
  ScorePlayer,
  IdentificationSubmitFlow,
  KeyContext,
  renderPlaybackControls,
  MeasureEngine,
  HarmonizationRealizationLogic,
  IdentificationLabelLayoutLogic,
  ChordalProblemsLogic,
  ChordalUMTOStaffDistribution,
  KeySignature,
  ChordalSpelling,
  ChordalBarlinesLogic,
  UMTOScoreConverter,
  BarlineSpacingUtils
) {
  "use strict";

  return {
    _buildHarmonizationPending: function () {
      var clickComp = this._clickNoteComponent;
      if (!clickComp || typeof clickComp.getPending !== "function") return null;
      var pending = clickComp.getPending();
      if (!pending || !pending.length) return null;
      var col = clickComp.getActiveColumn ? clickComp.getActiveColumn() : null;
      pending = pending.slice().sort(function (a, b) { return a.midi - b.midi; });
      var measureIndex = col ? col.measureIndex : 0;
      var measureTotalTicks = this._measureTotalTicks();
      var onsetWithinMeasure = col && typeof col.onset === "number"
        ? col.onset - (measureIndex * measureTotalTicks)
        : 0;
      return [{
        measureIndex: measureIndex,
        onset: Math.max(0, onsetWithinMeasure),
        // Pending click notes are a placement preview, not rhythmic notation.
        // Always use the same half-note overlay path; whole-note tickables can
        // recenter visually and make the clicked note appear to move/disappear.
        durationTicks: 2048,
        midiNotes: pending.map(function (n) { return n.midi; }),
        spellings: pending.map(function (n) {
          return { step: n.step, alter: n.alter, octave: n.octave };
        }),
      }];
    },

    _buildHarmonizationRejected: function () {
      var ctx = this.exerciseContext;
      var rejected = ctx && ctx._harmonizationRejected;
      if (!rejected || !rejected.spellings || !rejected.spellings.length) return null;
      var midiNotes = rejected.midi || [];
      if (!midiNotes.length) return null;
      return [{
        measureIndex: rejected.measureIndex || 0,
        onset: Math.max(0, rejected.onset || 0),
        durationTicks: 2048,
        midiNotes: midiNotes,
        spellings: rejected.spellings,
      }];
    },

    /**
     * Renders textual prompt for the exercise.
     *
     * @return this
     */
    renderExerciseStatus: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $statusEl = $("#exercise-status-and-tempo");
      var $passedEl = $("#passed-status");
      var statusTpl = _.template(
        // not called: time_to_complete and more
        `<p><span id="exercise-status" class="status-pill" style="background-color:<%= status_color %>"><%= status_text %></span></p>
                <% if (typeof(tempo_mean) !== "undefined" && tempo_mean != "" && typeof(tempo_rating) !== "undefined" && typeof(tempo_display_factor) !== "undefined") { %>
                    <p>Tempo&nbsp;<%= ["", "erratic", "unsteady", "steady", "very&nbsp;steady", "perfectly&nbsp;steady"][tempo_rating.length] %> at <%= Math.round(tempo_mean * tempo_display_factor) %>&nbsp;b.p.m.</p>
                <% } %>`
      );
      var passedTpl = `<span class="status-pill" id="exercise-passed-status">Exercise Passed</span>`;
      // the tempo verbiage above should match what is separately coded for my activity
      var html = "";
      var tpl_data = {};

      var status_map = {};
      status_map[exc.STATE.READY] = {
        text: "Ready",
        color: "#333333",
      };
      status_map[exc.STATE.WAITING] = {
        text: "Keep going",
        color: "#FF7F00",
      };
      status_map[exc.STATE.INCORRECT] = {
        text: "Fix the error",
        color: "#990000",
      };
      status_map[exc.STATE.FINISHED] = {
        text: "Go again",
        color: "#FFB700",
      };
      status_map[exc.STATE.CORRECT] = {
        text: "Passed",
        color: "#4C9900",
      };

      tpl_data.exercise_list = exc.definition.getExerciseList();
      tpl_data.exercise_num = tpl_data.exercise_list.reduce(function (
        selected,
        current,
        index
      ) {
        return selected < 0 && current.selected ? index + 1 : selected;
      },
      -1);
      tpl_data.status_text = status_map[exc.state].text;
      tpl_data.status_color = status_map[exc.state].color;

      $(".playlist-nav-links").css("display", "none");
      if ( // HOW DOES THIS WORK
        $("#playlist-passed-status").length == 0 &&
        definition.settings.definition.exerciseIsPerformed &&
        definition.settings.definition.exerciseErrorCount == 0
      ) {
        $passedEl.html(passedTpl);
      } else {
        $("#exercise-passed-status").hide();
      }
      switch (exc.state) {
        case exc.STATE.CORRECT:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
            tpl_data.tempo_display_factor = 1;
            try {
              // get beat information from time signature
              const time_sig = definition.exercise.timeSignature;
              const time_sig_numerator = Number(time_sig.split("/")[0]);
              let tempo_display_factor = Number(time_sig.split("/")[1]);
              if (time_sig_numerator > 3 && time_sig_numerator % 3 == 0) {
                // compound meter
                tempo_display_factor /= 3;
              }
              if (!isNaN(tempo_display_factor)) {
                tpl_data.tempo_display_factor = tempo_display_factor;
              }
            } catch (error) {
              console.log("Unable to retrieve beat value from time signature");
            }
          }
          // If this is the last exercise, display the nav links
          if (!this.exerciseContext.definition.exercise.nextExercise)
            $(".playlist-nav-links").css("display", "inline-flex");
          break;
        case exc.STATE.FINISHED:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
          }
          break;
        case exc.STATE.READY:
        default:
          break;
      }

      html = statusTpl(tpl_data);
      $statusEl.html(html);
      return this;
    },
    renderExerciseInfo: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $infoEl = $("#exercise-info");
      var tpl = _.template(
        `<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>
          <p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>
        <% } %>`
      );
      var html = "";
      var tpl_data = {};

      if (exc.definition.exercise.performing_course) {
        tpl_data.exercise_list = exc.definition.getExerciseList();
        tpl_data.exercise_num = 1;
        for (let i = 0; i < tpl_data.exercise_list.length; i++) {
          if (tpl_data.exercise_list[i].selected) {
            tpl_data.exercise_num = i + 1;
            break;
          }
        }
      } else {
        // get ID?
      }

      html = tpl(tpl_data);
      $infoEl.html(html);

      return this;
    },
    renderExerciseText: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $textEl = $("#exercise-text");
      var tpl = _.template(
        `<% if (typeof(prompt_text) == "string") { %>
                    <%= prompt_text %>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      var promptText = exc.definition.getExerciseText
        ? exc.definition.getExerciseText()
        : (exc.definition.getIntro ? exc.definition.getIntro() : "");
      var analysisType = definition && definition.getAnalysisType
        ? definition.getAnalysisType()
        : "roman";
      var inputMode = this._isIdentificationLikeExercise && this._isIdentificationLikeExercise()
        ? this._getIdentInputMode(definition)
        : "dropdown";
      if (
        inputMode === "text" &&
        (analysisType === "interval_generic" || analysisType === "interval_specific")
      ) {
        promptText = "Input the intervals in this text box with a space between them.";
      }

      tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(promptText);

      html = tpl(tpl_data);

      // Append page indicator for paged identification exercises
      if (this._isIdentificationLikeExercise && this._isIdentificationLikeExercise()) {
        var totalPages = exc.getTotalIdentPages ? exc.getTotalIdentPages() : 1;
        if (totalPages > 1) {
          var currentPage = exc.getIdentPage ? exc.getIdentPage() : 0;
          html += '<span class="page-indicator" style="margin-left:1em;color:#888;font-size:0.9em;">Page ' + (currentPage + 1) + ' of ' + totalPages + '</span>';
        }
      }

      $textEl.html(html);

      return this;
    },
    renderExerciseHistory: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $historyEl = $("#exercise-history");
      var tpl = _.template(
        `<% if (false && is_performed && typeof(latest_err_count) == "integer" && latest_err_count == 0) { %>
                    <p>PASSED on most recent attempt</p>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      $.ajax({
        type: "GET",
        url:
          window.location.origin +
          "/ajax" +
          window.location.pathname +
          "history/",
        async: false,
        success: function (response) {
          if (!response["valid"]) {
            var exerciseData = JSON.parse(response);
            tpl_data.is_performed = exerciseData.exerciseIsPerformed;
            tpl_data.latest_err_count = exerciseData.exerciseErrorCount;
          }
        },
        error: function (error) {
          alert("An error occurred while getting the exercise history.");
        },
      });

      html = tpl(tpl_data);
      $historyEl.html(html);

      return this;
    },
  };
});
