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
import ExerciseInstructions from "app/config/exercise_instructions";
import FbHints from "app/config/figured_bass_hints";

export default  {
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
      if (!rejected) return null;
      var midiNotes = rejected.midi || [];
      if (!midiNotes.length) return null;
      return [{
        measureIndex: rejected.measureIndex || 0,
        onset: Math.max(0, rejected.onset || 0),
        durationTicks: 2048,
        midiNotes: midiNotes,
        spellings: (rejected.spellings && rejected.spellings.length) ? rejected.spellings : null,
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
    // Internal source labels that are never meaningful to students.
    _INTERNAL_SOURCE_RE: /^\s*(play view chordal exercise|roman from compendium|roman from clausulae|harmonization from clausulae)\s*$/i,

    _getModeInstructions: function () {
      var mode = this.exerciseContext && this.exerciseContext.getDefinition
        ? (this.exerciseContext.getDefinition().getMode
            ? this.exerciseContext.getDefinition().getMode()
            : null)
        : null;
      return ExerciseInstructions[mode] || ExerciseInstructions.playback;
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

      // Replace internal metadata labels with a mode-appropriate instruction.
      if (!promptText || this._INTERNAL_SOURCE_RE.test(promptText)) {
        promptText = this._getModeInstructions().short;
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

      // Detach any existing hint controls before wiping innerHTML below.
      // jQuery's .html() strips bound event handlers from descendants before
      // replacing them (jQuery.cleanData runs first); .detach() is the one
      // removal method that preserves handlers/data for later re-insertion,
      // which is what lets _renderHintControls reuse the same button/panel
      // (and its in-progress hint step) across re-renders of one exercise
      // instead of rebuilding from scratch every call.
      if (this._hintCache) {
        this._hintCache.$btn.detach();
        this._hintCache.$panel.detach();
      }

      $textEl.html(html);
      this._renderHintControls($textEl);

      return this;
    },

    // Dynamic figured-bass hints override the static instructions when the
    // exercise is figured-bass analysis (abbreviated or unabbreviated). Returns
    // {help, hints, moreInfo} or null (fall back to static instructions).
    _getDynamicInstructions: function () {
      var exc = this.exerciseContext;
      var definition = exc && exc.getDefinition ? exc.getDefinition() : null;
      if (!definition || !definition.getAnalysisType) return null;
      var analysisType = definition.getAnalysisType();
      var isFiguredBass = analysisType === "figured_bass" || analysisType === "figured_bass_unabbreviated";
      var isRoman = analysisType === "roman";
      if (!isFiguredBass && !isRoman) {
        return null;
      }
      // Mode read routed through ResolvedMode (single authority). Behavior-identical:
      // resolved.interactionMode === getMode() — both read the same post-parse
      // exercise.mode || score.umto.metadata.mode || null (see resolved_mode.js
      // resolveMode vs exercise_definition.js getMode). The literal comparisons
      // below stay (Phase 1.3 lint territory); only the read path changes.
      var resolved = definition && definition.getResolvedMode ? definition.getResolvedMode() : null;
      var mode = resolved ? resolved.interactionMode : null;
      var dyn = null;
      // "playback" covers the teacher-authored "Play + figures" mode
      // (InteractionMode.PLAYBACK + analysisType figured_bass*), which reads
      // the same harmonizationTargets shape as "harmonization" and needs the
      // same essential/omittable hint content. Roman-numeral analysis has no
      // harmonization mode (identification only), so it's excluded here.
      if (isFiguredBass && (mode === "harmonization" || mode === "playback")) {
        dyn = FbHints.buildHarmonizationHints(definition, analysisType);
      } else if (isFiguredBass && (mode === "identification" || mode === "chorale_identification")) {
        dyn = FbHints.buildIdentificationHints(definition, analysisType);
      } else if (isRoman && (mode === "identification" || mode === "chorale_identification")) {
        dyn = FbHints.buildRomanIdentificationHints(definition);
      } else {
        // No dynamic builder is defined for this mode at all (distinct from
        // a builder running and returning null) — fall back silently, no
        // warning, since nothing was ever expected to run here.
        return null;
      }
      if (!dyn) {
        // Fallback: helper returned null (no targets / no FB slices / figure
        // absent from the generated lookup). Log so the gap is visible in dev.
        console.warn(
          "[figured-bass hints] dynamic builder returned null for mode=" +
          mode + ", analysisType=" + analysisType +
          "; falling back to static instructions."
        );
        return null;
      }
      return dyn;
    },

    _renderHintControls: function ($textEl) {
      var definition = this.exerciseContext && this.exerciseContext.getDefinition
        ? this.exerciseContext.getDefinition()
        : null;
      var exerciseId = definition && definition.exercise
        ? definition.exercise.exerciseId
        : null;

      // Same exercise as the last render: re-attach the already-built
      // controls (click handler and in-progress hint step intact) instead
      // of recomputing hints and rebuilding the DOM on every call — this
      // function used to run on every note/chord the student played, since
      // renderExerciseText's $textEl.html(html) call (right before this)
      // wipes the DOM every time and the old "already present" guard here
      // could never see the button it had just wiped out.
      if (this._hintCache && this._hintCache.exerciseId === exerciseId) {
        $textEl.append(this._hintCache.$btn).append(this._hintCache.$panel);
        return;
      }

      var dyn = this._getDynamicInstructions();
      var instructions = dyn || this._getModeInstructions();
      var hints = instructions.hints || [];
      if (!hints.length && !instructions.help) {
        this._hintCache = null;
        return;
      }

      var $btn = $('<button type="button" class="ex-hint-btn" title="Get a hint">? Hint</button>');
      var $panel = $('<div class="ex-hint-panel" role="status" aria-live="polite" style="display:none;"></div>');
      var step = -1;

      // Each step carries an explicit html flag set at construction time,
      // rather than being inferred at render time by sniffing the string's
      // leading characters (content-based sniffing would misrender any
      // hint/help string that happened to start with the same characters).
      var allSteps = [];
      if (instructions.help) allSteps.push({ text: instructions.help, html: false });
      hints.forEach(function (h) { allSteps.push({ text: h, html: false }); });
      if (instructions.moreInfo) {
        // Builder can carry its own explanation-page URL (e.g. the Roman-numeral
        // / circle-of-thirds static page); fall back to the figured-bass canon
        // page when the builder doesn't specify one.
        var moreUrl = instructions.moreInfoUrl || FbHints.MORE_INFO_URL;
        var moreLabel = instructions.moreInfoUrl
          ? 'Open the chord & Roman-numeral lesson →'
          : 'More on reading figured bass →';
        allSteps.push({
          text: '<a class="fb-more-info" target="_blank" rel="noopener noreferrer" href="' +
            moreUrl + '">' + moreLabel + '</a>',
          html: true,
        });
      }

      $btn.on('click', function () {
        step = Math.min(step + 1, allSteps.length - 1);
        var s = allSteps[step];
        if (s.html) {
          $panel.html(s.text).show();
        } else {
          $panel.text(s.text).show();
        }
        if (step === allSteps.length - 1) {
          $btn.text('✓ Hint').prop('disabled', true);
        } else {
          $btn.text('More →');
        }
      });

      this._hintCache = { exerciseId: exerciseId, $btn: $btn, $panel: $panel };
      $textEl.append($btn).append($panel);
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
