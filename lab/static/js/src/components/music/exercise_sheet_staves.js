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

var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;
  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  export default  {
    /**
     * VexFlow render stack — used by the chorale, harmonization, and
     * chorale_identification pipelines. The per-pipeline sheet supplies `cfg`
     * (which pipeline flags apply); this method does NOT read `resolved` — the
     * stack selection is owned by the calling sheet, not a runtime
     * resolved-mode check inside the render path.
     *
     * @param {object} cfg - `{ isHarmonization, isChoraleIdentification,
     *   isAnalysisMatchMode, isChorale }` — all booleans, supplied by the
     *   per-pipeline sheet that owns this render stack.
     * @return this
     */
    _renderStavesVexFlow: function (exercise_midi_nums, cfg) {
      exercise_midi_nums = exercise_midi_nums || false;
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore();

      // If it's a UMTO chorale, always re-convert to ensure splitting is fresh and uses MeasureEngine.
      // This fixes cases where the database might have a single 'blob' measure.
      // (VexFlow sheets are chorale-like, so the prior isChoraleLike gate is always true here.)
      if (score && score.umto && !ChordalProblemsLogic.shouldPreserveChordalMeasures(score)) {
        score = UMTOScoreConverter.convertUMTOToProcessedScore(score.umto);
      }

      var hasMeasures = !!(score && score.measures && score.measures.length > 0);

      // Ensure score has metadata for VexFlowAdapter
      if (score && hasMeasures) {
        score.metadata = score.metadata || {};
        if (score.metadata.meter && !score.metadata.time) score.metadata.time = score.metadata.meter;
        if (!score.metadata.time) score.metadata.time = "4/4";
      }

      // Flags from the calling sheet (no resolved-mode read inside the render path).
      var isHarmonization = !!(cfg && cfg.isHarmonization);
      var isAnalysisMatchMode = !!(cfg && cfg.isAnalysisMatchMode);
      var isChorale = !!(cfg && cfg.isChorale);
      var isChoraleIdentification = !!(cfg && cfg.isChoraleIdentification);

      // A chorale-like exercise with no measures renders via the legacy stack —
      // preserve the prior fork's `else` fall-through.
      if (!hasMeasures) {
        return this._renderStavesLegacy(exercise_midi_nums);
      }

      // Use VexFlow adapter for chorale exercises
      if (score && score.measures && score.measures.length > 0) {
          var self = this;
          this._identWindowLayout = {};
          this._identWindowLayoutByOnset = {};
          this._updateChoraleViewport(score);
          var canvas = this.el[0];
          var ctx = this.vexRenderer.getContext();
          var display = definition.getDisplay() || {};
          var analyzeConfig = _.cloneDeep(this.getAnalyzeConfig() || {});
          var _analysisType = definition.getAnalysisType ? definition.getAnalysisType() : null;
          if (_analysisType === "figured_bass" || _analysisType === "figured_bass_unabbreviated") {
            analyzeConfig.roman_numerals = false;
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.mode.roman_numerals = false;
          }
          var wantsRomans = !!display.showRomans;
          var wantsFigures = !!display.showFigures;
          var wantsChordLabels = !!display.showChordLabels;
          var wantsScaleDegrees = !!display.showScaleDegrees;
          var wantsNoteNames = !!display.showNoteNames || isAnalysisMatchMode;


          // In chorale identification mode the figures/Romans ARE the student's
          // answers — rendering them via VexFlow would spoil the exercise.
          // The identification overlay draws "?" slots instead.
          if (isChoraleIdentification) {
            wantsRomans = false;
            wantsFigures = false;
            wantsChordLabels = false;
            wantsScaleDegrees = false;
            wantsNoteNames = false;
            analyzeConfig.enabled = false;
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.mode.roman_numerals = false;
            analyzeConfig.mode.thoroughbass = false;
            analyzeConfig.mode.chord_labels = false;
            analyzeConfig.mode.scale_degrees = false;
            analyzeConfig.mode.note_names = false;
          }

          if (isHarmonization) {
            analyzeConfig.enabled = true;
            analyzeConfig.mode = analyzeConfig.mode || {};
            if (definition.getAnalysisType && (definition.getAnalysisType() === "figured_bass" || definition.getAnalysisType() === "figured_bass_unabbreviated")) {
              analyzeConfig.mode.thoroughbass = true;
            } else {
              analyzeConfig.mode.roman_numerals = true;
            }
          }

          var wantsAnalysis = wantsRomans || wantsFigures || wantsChordLabels || wantsScaleDegrees || wantsNoteNames;

          // Preserve legacy chorale behavior that force-enables roman numerals,
          // but do not force overlays for chorale_identification.
          if (!wantsAnalysis && isChorale && !isAnalysisMatchMode && !isChoraleIdentification) {
            wantsRomans = true;
            wantsAnalysis = true;
          }
          // Ensure analysis renderer is not suppressed
          if (!display.analysisRenderer) {
            display.analysisRenderer = 'notater';
          }
          if (wantsAnalysis) {
            analyzeConfig.enabled = true;
            analyzeConfig.mode = analyzeConfig.mode || {};
            if (wantsRomans) {
              analyzeConfig.mode.roman_numerals = true;
            }
            if (wantsFigures) {
              analyzeConfig.mode.thoroughbass = true;
              if (display.figureStyle === "figures_abbrev") {
                analyzeConfig.mode.abbreviate_thoroughbass = true;
              }
            }
            if (wantsChordLabels) {
              analyzeConfig.mode.chord_labels = true;
            }
            if (wantsScaleDegrees) {
              analyzeConfig.mode.scale_degrees = true;
              // scale_degrees is mutually exclusive with roman_numerals/note_names/thoroughbass.
              // The inherited analyzeConfig from ANALYSIS_SETTINGS may have those enabled;
              // silence them so renderScaleDegrees isn't blocked in vexflow_adapter.
              if (!wantsRomans) analyzeConfig.mode.roman_numerals = false;
              if (!wantsFigures) analyzeConfig.mode.thoroughbass = false;
              if (!wantsNoteNames) analyzeConfig.mode.note_names = false;
            }
            if (wantsNoteNames) {
              analyzeConfig.mode.note_names = true;
            }
            if (!wantsRomans) {
              analyzeConfig.roman_numerals = false;
              analyzeConfig.mode.roman_numerals = false;
            }
          }

          // Play Authoring Phase B: if the exercise stored explicit {above, below} slots,
          // project them onto mode flags so the notater/adapter light up the right zones.
          // This block only runs when a stored slot directive is present (play-authored
          // exercises); legacy exercises have no top-level data.analyzeConfig so storedSlots
          // is null and the block is skipped entirely — no regression risk.
          var storedSlots = (definition.exercise && definition.exercise.analyzeConfig) || null;
          if (storedSlots && (storedSlots.above || storedSlots.below)) {
            analyzeConfig.mode = analyzeConfig.mode || {};
            analyzeConfig.enabled = true;
            if (storedSlots.below === "roman_numerals" || storedSlots.below === "roman_numerals_exp") analyzeConfig.mode.roman_numerals = true;
            if (storedSlots.below === "thoroughbass") analyzeConfig.mode.thoroughbass = true;
            if (storedSlots.above === "scale_degrees") analyzeConfig.mode.scale_degrees = true;
            if (storedSlots.above === "note_names") analyzeConfig.mode.note_names = true;
          }

          var startMeasure =
            (this._chorale && typeof this._chorale.startMeasure === "number"
              ? this._chorale.startMeasure
              : 0);
          var staffYOffset = 20;
          var playedNoteIdsForRender =
            (this.exerciseContext && this.exerciseContext.grader && this.exerciseContext.grader.getPlayedNoteIds)
              ? this.exerciseContext.grader.getPlayedNoteIds()
              : null;

          // In chorale-identification mode, render all notation in black from the start.
          if (isChoraleIdentification) {
            playedNoteIdsForRender = new Set();
            _.each(ScoreTimeline.buildTimeline(score) || [], function (ev) {
              if (ev && typeof ev.id === 'number') {
                playedNoteIdsForRender.add(ev.id);
              }
            });
          }

          // For harmonization: compute selectVoices once (used for both timeline and render).
          var harmonizationSelectVoices = null;
          if (isHarmonization) {
            var lv = definition.exercise && definition.exercise.score && definition.exercise.score.umto
              ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
              : ["B"];
            function lockedVoiceIndex(staffName, preferredIndex) {
              var firstMeasure = score && score.measures && score.measures[0];
              var staff = firstMeasure && firstMeasure.staves && firstMeasure.staves[staffName];
              var voices = staff && staff.voices ? staff.voices : [];
              if (voices.length > preferredIndex) return preferredIndex;
              if (voices.length === 1) return 0;
              return preferredIndex;
            }
            var hvTreble = [], hvBass = [];
            if (lv.indexOf("S") !== -1) hvTreble.push(lockedVoiceIndex("treble", 0));
            if (lv.indexOf("A") !== -1) hvTreble.push(lockedVoiceIndex("treble", 1));
            if (lv.indexOf("T") !== -1) hvBass.push(lockedVoiceIndex("bass", 0));
            if (lv.indexOf("B") !== -1) hvBass.push(lockedVoiceIndex("bass", 1));
            harmonizationSelectVoices = { treble: hvTreble, bass: hvBass };
          }

          // For harmonization: bass notes at accepted target offsets turn black.
          // Build timeline with same selectVoices as renderer so IDs align.
          var harmonizationRealizationPayload = null;
          if (isHarmonization && this.exerciseContext) {
            var acceptedPtr = this.exerciseContext._harmonizationPointer || 0;
            var harmTargets = definition.getHarmonizationTargets ? definition.getHarmonizationTargets() : [];
            var acceptedOffsetTicks = {};
            for (var ai = 0; ai < acceptedPtr && ai < harmTargets.length; ai++) {
              var tOff = harmTargets[ai].offset;
              if (typeof tOff === "number") {
                acceptedOffsetTicks[Math.round(tOff * 1024)] = true;
              }
            }
            playedNoteIdsForRender = new Set();
            _.each(ScoreTimeline.buildTimeline(score, { selectVoices: harmonizationSelectVoices }) || [], function (ev) {
              if (ev && typeof ev.id === 'number' && acceptedOffsetTicks[ev.onset]) {
                playedNoteIdsForRender.add(ev.id);
              }
            });
            var accepted = this.exerciseContext.acceptedHarmonizationSonorities || [];
            var tsRaw = (score.meta && (score.meta.time || score.meta.meter || score.meta.time_signature)) || "4/4";
            var tsParts = String(tsRaw).split("/");
            var meter = {
              numerator: parseInt(tsParts[0], 10),
              denominator: parseInt(tsParts[1], 10)
            };
            harmonizationRealizationPayload = HarmonizationRealizationLogic.buildRealization(
              accepted,
              harmTargets,
              score,
              meter
            );
          }

          VexFlowAdapter.render(score, this.vexRenderer, {
            width: canvas.width,
            height: canvas.height,
            maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,
            startMeasure: startMeasure,
            playedNoteIds: playedNoteIdsForRender,
            showNotation: display.showNotation !== undefined ? display.showNotation : true,
            hideKeyLabel: !!display.hideKeyLabel,
            firstMeasureExtraWidth: parseInt(display.firstMeasureExtraWidth, 10) || 0,
            noteXShift: parseInt(display.noteXShift, 10) || 0,
            voiceColors: display.voiceColors || null,
            // Analysis wiring for chorale path (Notater bridge inside adapter)
            analyzeConfig: analyzeConfig,

            // Always use the definition's already-converted KeySignature model.
            // score.meta.key is raw (e.g. "C") and may not be a valid HL key string.
            keySignature: this.keySignature,
            analysisRenderer: display.analysisRenderer || "notater", // notater|adapter|none
            staffYOffset: staffYOffset,
            isAnalysisMatch: isAnalysisMatchMode,
            isHarmonization: isHarmonization,
            harmonizationTargets: isHarmonization ? (definition.getHarmonizationTargets ? definition.getHarmonizationTargets() : []) : null,
            harmonizationRealization: isHarmonization ? harmonizationRealizationPayload : null,
            harmonizationPending: isHarmonization ? self._buildHarmonizationPending() : null,
            harmonizationRejected: isHarmonization ? self._buildHarmonizationRejected() : null,
            lockedVoices: isHarmonization && definition.exercise && definition.exercise.score && definition.exercise.score.umto
              ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
              : null,
            selectVoices: harmonizationSelectVoices,
            analysisType: definition.getAnalysisType ? definition.getAnalysisType() : null,
            onStaffLayout: function (layout) { self._staffLayout = layout; },
            onWindowPosition: function (slot) {
              if (!slot || typeof slot.windowIndex !== "number") {
                return;
              }
              console.log("[ID] onWindowPosition received:", slot.windowIndex, slot.x, slot.y);
              self._identWindowLayout[slot.windowIndex] = slot;
              // Index by "measureIndex:pageLocalOnset" for cross-page playback highlight lookup.
              // The adapter emits absolute measureIndex and page-local onset.
              if (slot.measureIndex !== null && slot.measureIndex !== undefined && slot.onset !== null && slot.onset !== undefined) {
                self._identWindowLayoutByOnset[slot.measureIndex + ":" + slot.onset] = slot;
              }
            },
          });
          console.log("[ID] VexFlowAdapter.render finished.");



          if (this._isIdentificationLikeExercise()) {
            this.drawIdentificationLabels();
          }
      }
      return this;
    },
    /**
     * Legacy stave render stack — used by the matching, figured_bass, and
     * identification pipelines, and as the hasMeasures fall-through for
     * VexFlow-family sheets whose score has no measures.
     *
     * @return this
     */
    _renderStavesLegacy: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;

      // Legacy rendering for non-chorale exercises
      console.log("[ID] Using Legacy Renderer (FALLBACK)");
      const show_barlines = true;

      var i,
        len,
        stave,
        _staves = this.staves;
      var _barlines = this.barlines;
      for (i = 0, len = _staves.length; i < len; i++) {
        stave = _staves[i];
        const exercise_view_bool = true;
        const append_barline = _barlines.indexOf(i) != -1 && show_barlines;
        stave.render(exercise_midi_nums, exercise_view_bool, append_barline);
      }

      if (this._isIdentificationLikeExercise()) {
        this.drawIdentificationLabels();
      }

      return this;
    },
    /**
     * Adjusts which measures are displayed for chorale exercises as the user advances.
     */
    _updateChoraleViewport: function (score) {
      if (
        !this._chorale ||
        !score ||
        !score.measures ||
        !score.measures.length
      ) {
        return;
      }
      // During playback page turns, honour the override and skip grader-based calculation.
      if (this._playbackOverridePage !== null && this._playbackOverridePage !== undefined) {
        this._chorale.startMeasure = this._playbackOverridePage;
        return;
      }
      var totalMeasures = score.measures.length;
      var maxMeasures = this._chorale.maxMeasures || 4;
      if (totalMeasures <= maxMeasures) {
        this._chorale.startMeasure = 0;
        return;
      }
      var activeMeasure = 0;
      // For chorale_identification, page index comes from exerciseContext directly.
      // For chorale (play-through), it comes from the grader.
      var context = this.exerciseContext;
      if (context && typeof context.getIdentPageOffset === "function" && this._isChoraleIdentificationExercise()) {
        if (typeof context.getIdentPage === "function") {
          var page = context.getIdentPage();
          activeMeasure = Math.max(0, Math.min(page * maxMeasures, totalMeasures - 1));
        }
      } else {
        var grader = context && context.grader;
        if (grader && typeof grader.getActiveMeasureIndex === "function") {
          var idx = grader.getActiveMeasureIndex();
          if (typeof idx === "number" && !isNaN(idx)) {
            activeMeasure = Math.max(0, Math.min(idx, totalMeasures - 1));
          }
        }
      }
      var block = Math.floor(activeMeasure / maxMeasures);
      var desiredStart = block * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (desiredStart > lastPossibleStart) {
        desiredStart = lastPossibleStart;
      }
      if (desiredStart < 0) {
        desiredStart = 0;
      }
      if (this._chorale.startMeasure !== desiredStart) {
        this._chorale.startMeasure = desiredStart;
      }
    },
    /**
     * Resets the staves.
     *
     * @return this
     */
    resetStaves: function () {
      this.staves = [];
      this.barlines = [];
      return this;
    },
    /**
     * Adds staves.
     *
     * @param {array} staves
     * @return this
     */
    addStaves: function (staves) {
      this.staves = this.staves.concat(staves);
      return this;
    },

    /**
     * Updates and configures the staves.
     *
     * @return this
     */
    updateStaves: function () {
      var chord, treble, bass;
      var limit = 100; // arbitrary
      let bankSize = CHORD_BANK_SIZE;
      try {
        const custom_chord_bank_size = parseInt(this.getSemibrevesPerLine());
        if (
          typeof custom_chord_bank_size === "number" &&
          custom_chord_bank_size > 0
        ) {
          bankSize = custom_chord_bank_size;
        }
      } catch {
        console.log(
          "Failed to retrieve getSemibrevesPerLine property from Exercise definion."
        );
      }
      var display_items = this.getDisplayChords().items({
        limit: limit,
        reverse: false,
      });
      var exercise_items = this.getExerciseChords().items({
        limit: limit,
        reverse: false,
      });
      var staves = [];
      var barlines = [];
      var index = 0;
      var offset = 0;
      var count = display_items.length;
      var position = {
        index: index,
        count: count,
        offset: offset,
        maxCount: bankSize,
      };
      var display_chord;
      var exercise_chord;
      var treble_activeAlterations = Object.create(null);
      var bass_activeAlterations = Object.create(null);
      const timeSignature = this.getTimeSignature();
      const barlineSpace = 0.25; // relative to width of whole note

      // scrolling exercise view
      var scroll_exercise = false;
      var pageturns = [0];

      let rhythmValues = display_items.map((item) => item.chord._rhythmValue);
      let availableSpace = bankSize;

      const endOfBarWholeNoteCounts = [];
      if (timeSignature) {
        const wholeNoteSum = rhythmValues
          .map((item) => BarlineSpacingUtils.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        const barCount = BarlineSpacingUtils.countElapsedBars(timeSignature, wholeNoteSum);
        const ts = BarlineSpacingUtils.timeSignatureParsed(timeSignature);
        for (var i = 1, len = barCount; i <= len; i++) {
          endOfBarWholeNoteCounts.push((i * ts[0]) / ts[1]);
        }
      }

      for (var i = 0, len = rhythmValues.length; i < len; i++) {
        let neededSpace = BarlineSpacingUtils.getVisualWidth(rhythmValues[i]);

        let elapsedWholeNotes = rhythmValues
          .slice(0, i + 1)
          .map((item) => BarlineSpacingUtils.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        if (endOfBarWholeNoteCounts.includes(elapsedWholeNotes)) {
          neededSpace += barlineSpace;
        }
        if (neededSpace > availableSpace) {
          availableSpace = bankSize - neededSpace; // overlap space
          pageturns.push(i);
          scroll_exercise = true;
        }
        availableSpace -= neededSpace;
      }

      let previous_whole_note_count = 0;
      if (scroll_exercise) {
        let cursor = this.getInputChords()._currentIndex;
        var page_start = pageturns
          .filter(function (x, idx) {
            return x <= cursor;
          })
          .pop();
        var next_page =
          pageturns.filter(function (x, idx) {
            return x > cursor;
          })[0] || false;
        if (page_start > 0) {
          // create overlap (start new page with completed chord)
          page_start -= 1;
          // next_page -= 1; //unwise
        }

        position.offset = page_start;
        const previous_items = display_items.slice(0, page_start);

        if (next_page) {
          display_items = display_items.slice(page_start, next_page);
          exercise_items = exercise_items.slice(page_start, next_page);
        } else {
          display_items = display_items.slice(page_start);
          exercise_items = exercise_items.slice(page_start);
        }

        for (var i = 0, len = previous_items.length; i < len; i++) {
          let rhythm_value = null;
          if (previous_items[i].chord.settings.rhythm) {
            rhythm_value = previous_items[i].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          previous_whole_note_count += BarlineSpacingUtils.getWholeNoteCount(rhythm_value);
        }
      }

      // The first bar is a special case: it's reserved to show the
      // clef and key signature and nothing else.
      let first_page = true;
      if (previous_whole_note_count > 0) {
        first_page = false;
      }
      treble = this.createDisplayStave("treble", _.clone(position), first_page);
      bass = this.createDisplayStave("bass", _.clone(position), first_page);
      position.index += 1;
      treble.connect(bass);
      staves.push(treble);

      var treble_alterationHistory = Object.create(null);
      var bass_alterationHistory = Object.create(null);

      // now add the staves for showing the notes
      for (var i = 0, len = display_items.length; i < len; i++) {
        let elapsedWidthUnits = 0;
        let elapsedWholeNotes = 0;
        let extraWidth = 0;
        for (var j = 0; j < i; j++) {
          var rhythm_value = null;
          if (display_items[j].chord.settings.rhythm) {
            rhythm_value = display_items[j].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          elapsedWidthUnits += BarlineSpacingUtils.getVisualWidth(rhythm_value);
          elapsedWholeNotes += BarlineSpacingUtils.getWholeNoteCount(rhythm_value);
        }

        // spacing for barlines
        const complement_of_first_bar = BarlineSpacingUtils.getWholeNoteRemainder(
          timeSignature,
          previous_whole_note_count
        );
        const elapsedBarlines = BarlineSpacingUtils.countElapsedBars(
          timeSignature,
          elapsedWholeNotes + complement_of_first_bar - 0.01
        );
        if (elapsedBarlines) {
          elapsedWidthUnits += barlineSpace * elapsedBarlines;
        }

        // now take account of previous music for proper barring
        elapsedWholeNotes += previous_whole_note_count;

        var curr_value = null;
        if (display_items[i].chord.settings.rhythm) {
          curr_value = display_items[i].chord.settings.rhythm;
        } else {
          curr_value = DEFAULT_RHYTHM_VALUE;
        }
        if (i < len) {
          if (BarlineSpacingUtils.getsBarline(timeSignature, elapsedWholeNotes)) {
            if (i > 0) {
              // new bar begins here but not new system
              // draw barline at left
              barlines.push(i + 1);
              // add space to left of barline
              elapsedWidthUnits += barlineSpace;
            }
            // RESET # n b
            treble_activeAlterations = Object.create(null);
            bass_activeAlterations = Object.create(null);
          }
          if (
            BarlineSpacingUtils.getsBarline(
              timeSignature,
              elapsedWholeNotes + BarlineSpacingUtils.getWholeNoteCount(curr_value)
            )
          ) {
            // bar is completed here: add space
            extraWidth += barlineSpace;
          }
        }

        treble_alterationHistory[i] = treble_activeAlterations;
        bass_alterationHistory[i] = bass_activeAlterations;

        display_chord = display_items[i].chord;
        exercise_chord = exercise_items[i].chord;
        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          treble_activeAlterations,
          extraWidth
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          bass_activeAlterations,
          extraWidth
        );
        position.index += 1;
        treble.connect(bass);
        staves.push(treble);

        let treble_merged = {
          ...treble_activeAlterations,
          ...treble.noteFactory.bequestAlterations,
        };
        let treble_cancellations = treble.noteFactory.bequestCancellations;
        for (let j = 0, len_j = treble_cancellations.length; j < len_j; j++) {
          delete treble_merged[treble_cancellations[j]];
        }
        treble_activeAlterations = treble_merged;

        let bass_merged = {
          ...bass_activeAlterations,
          ...bass.noteFactory.bequestAlterations,
        };
        let bass_cancellations = bass.noteFactory.bequestCancellations;
        for (let j = 0, len_j = bass_cancellations.length; j < len_j; j++) {
          delete bass_merged[bass_cancellations[j]];
        }
        bass_activeAlterations = bass_merged;
      }

      treble.noteFactory.alterationHistory = treble_alterationHistory;
      bass.noteFactory.alterationHistory = bass_alterationHistory;

      this.resetStaves();
      this.addStaves(staves);
      this.barlines = barlines;

      return this;
    },
    /**
     * Creates a stave to display the clef, key signature, etc.
     *
     * @param {string} clef
     * @param {object} position
     * @return {Stave}
     */
    createDisplayStave: function (clef, position, first_page = true) {
      var stave = new Stave(clef, position);
      var stave_notater = this.createStaveNotater(clef, {
        stave: stave,
        keySignature: this.keySignature,
        analyzeConfig: this.getAnalyzeConfig(),
      });

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      if (first_page && BarlineSpacingUtils.timeSignatureParsed(this.timeSignature)) {
        // console.log(this.timeSignatureParsed(this.timeSignature).join('/'));
        stave.setTimeSignature(
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature).join("/")
        );
      } else {
        stave.setTimeSignature(false);
      }
      stave.setNotater(stave_notater);
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig, this.timeSignature);
      }
      stave.updatePosition();

      return stave;
    },
    /**
     * Creates a stave to display notes.
     *
     * @param {string} clef
     * @param {object} position
     * @param {Chord} chord
     * @return {Stave}
     */
    createNoteStave: function (
      clef,
      position,
      displayChord,
      exerciseChord,
      elapsedWidthUnits,
      activeAlterations,
      extraWidth = 0
    ) {
      var stave = new Stave(clef, position);
      var widthUnits = null;
      if (exerciseChord.settings.rhythm) {
        var rhythm_value = exerciseChord.settings.rhythm;
        if (rhythm_value == null) {
          rhythm_value = DEFAULT_RHYTHM_VALUE;
        }
        widthUnits = BarlineSpacingUtils.getVisualWidth(rhythm_value) + extraWidth;
      }

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      // timeSignature not required here
      // stave.setFirstBarWidth(this.keySignature);

      // Identification exercises present the chord as the prompt, not as
      // user-played input, so the notation should render black rather than
      // the default gray for unplayed notes.
      if (
        typeof this._isIdentificationLikeExercise === "function" &&
        this._isIdentificationLikeExercise()
      ) {
        displayChord.setNoteProps(displayChord.getNoteNumbers(), {
          correctness: true,
        });
      }

      stave.setNoteFactory(
        new ExerciseNoteFactory({
          clef: clef,
          chord: displayChord,
          keySignature: this.keySignature,
          highlightConfig: this.getHighlightConfig(),
          activeAlterations: activeAlterations,
        })
      );
      stave.setNotater(
        this.createStaveNotater(clef, {
          stave: stave,
          chord: exerciseChord,
          keySignature: this.keySignature,
          analyzeConfig: this.getAnalyzeConfig(),
        })
      );
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          BarlineSpacingUtils.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig, this.timeSignature);
      }
      stave.updatePositionWithRhythm(widthUnits, elapsedWidthUnits);
      stave.updateAlterations(activeAlterations);

      return stave;
    },
    /**
     * Creates an instance of StaveNotater.
     *
     * @param {string} clef The clef, treble|bass, to create.
     * @param {object} config The config for the StaveNotater.
     * @return {object}
     */
    createStaveNotater: function (clef, config) {
      return StaveNotater.create(clef, config);
    },
  };
