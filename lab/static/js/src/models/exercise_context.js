define([
  "lodash",
  "jquery",
  "microevent",
  "./exercise_chord",
  "./exercise_chord_bank",
  "app/config",
  "app/components/events",
  "./exercise_completion_flow_logic",
  "./identification_submit_flow_logic",
  "app/models/harmonization_grader_logic",
  "app/models/voice_leading_logic",
  "app/models/exercise_context_timer_logic",
  "app/models/exercise_context_ident_page_logic",
], function (
  _,
  $,
  MicroEvent,
  ExerciseChord,
  ExerciseChordBank,
  Config,
  EVENTS,
  ExerciseCompletionFlow,
  IdentificationSubmitFlow,
  HarmonizationGraderLogic,
  VoiceLeadingLogic,
  TimerLogic,
  IdentPageLogic
) {
  var AUTO_ADVANCE = Config.get("general.autoAdvance");
  var AUTO_ADVANCE_DELAY = Config.get("general.autoAdvanceDelay");

  var AUTO_REPEAT = Config.get("general.autoRepeat");
  var AUTO_REPEAT_DELAY = Config.get("general.autoRepeatDelay");

  /**
   * ajax call to GET the user preferences
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
        AUTO_ADVANCE = sticky_settings.auto_advance;
        AUTO_ADVANCE_DELAY = sticky_settings.auto_advance_delay;
        AUTO_REPEAT = sticky_settings.auto_repeat;
        AUTO_REPEAT_DELAY = sticky_settings.auto_repeat_delay;
        // AUTO_SUSTAIN_DURATION = sticky_settings.auto_sustain_duration;
      }
    },
  });

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");
  var IGNORE_MISTAKES_ON_AUTO_ADVANCE = Config.get(
    "general.ignoreMistakesOnAutoAdvance"
  );

  /**
   * ExerciseContext object coordinates the display and grading of
   * an exercise.
   *
   * @mixes MicroEvent
   * @param settings {object}
   * @param settings.definition ExerciseDefinition
   * @param settings.grader ExerciseGrader
   * @param settings.inputChords ChordBank
   * @constructor
   */
  var ExerciseContext = function (settings) {
    this.settings = settings || {};

    _.each(
      ["definition", "grader", "inputChords"],
      function (attr) {
        if (!(attr in this.settings)) {
          throw new Error(
            "missing settings." + attr + " constructor parameter"
          );
        }
      },
      this
    );

    this.definition = this.settings.definition;
    this.grader = this.settings.grader;
    this.inputChords = this.settings.inputChords;
    this.exercise = this.settings.exercise;
    this.scoreCard = this.settings.scoreCard || null;

    this.state = ExerciseContext.STATE.READY;
    this.graded = false;
    this.timer = null;
    this._identPage = 0;
    this._identPageSize = (this.definition.isSymbolicMeterQuestion && this.definition.isSymbolicMeterQuestion()) ? 1 : 4;
    this.displayChords = this.createDisplayChords();
    this.exerciseChords = this.createExerciseChords();
    this.timeSignature = this.definition.getTimeSignature();
    this.semibrevesPerLine = this.definition.getSemibrevesPerLine();
    this.sessionMode = this.settings.identMode || "submit";

    // this.playlistRestarts = null; // this obsolete measurement was valuable

    this.sealed = false; /* will be used to ignore input post-completion */

    this._harmonizationHeldTracker = null;
    this._harmonizationPointer = 0;
    this.acceptedHarmonizationSonorities = [];
    this.harmonizationVLScore = null;
    this.harmonizationTier = null;
    this._harmonizationActiveMidiOverride = null;
    this._harmonizationRejected = null; // { midi, spellings, measureIndex, onset, reasons } — cleared on next column

    _.bindAll(this, ["grade", "triggerTimer", "validateGradingAlignment"]);

    this.init();
  };

  /**
   * Defines the possible states
   * @type {object}
   * @const
   */
  ExerciseContext.STATE = {
    READY: "ready", // not started
    WAITING: "waiting", // so far so good
    INCORRECT: "incorrect", // errors
    CORRECT: "correct", // complete without errors
    FINISHED: "finished", // complete with errors
  };

  _.extend(ExerciseContext.prototype, {
    /**
     * Make the STATE values accessible via instance.
     */
    STATE: ExerciseContext.STATE,
    init: function () {
      this.initListeners();
    },
    /**
     * Initializes listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      let testing =
        window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false;
      if (true || testing) {
        // using .remove() in the following lines hampers the staff distribution (analysis too?)
        $(".js-play-view-controls").hide();
        $("#mainmenu").hide();
      }
      if (this._isHarmonizationExercise()) {
        var meta = this.definition.getHarmonizationMetadata
          ? this.definition.getHarmonizationMetadata()
          : {};
        var releaseGraceMs = meta.release_grace_ms || 120;
        this._harmonizationChordSettleMs = meta.chord_settle_ms || 150;
        this._harmonizationSettleTimer = null;
        this._harmonizationHeldTracker = HarmonizationGraderLogic.createHeldNoteTracker({
          releaseGraceMs: releaseGraceMs,
        });
      } else if (!this._isIdentificationExercise()) {
        this.inputChords.bind("change", this.triggerTimer);
        this.inputChords.bind("change", this.grade);
        this.inputChords.bind("change", this.validateGradingAlignment);
      }
    },
    /**
     * For tempo assessment
     */
    makeTimestamp: function () {
      if (!this.timer || !this.timer.timepoints) {
        return null;
      }
      try {
        var timestamp =
          new Date().getTime() % this.timer.start; /* milliseconds */
        var idx = this.graded.activeIndex;
        if (
          idx == undefined &&
          Object.keys(this.timer.timepoints).length == 0
        ) {
          idx = 0; // necessary for the first exercise of a playlist, unsure why
        }
        if (idx != undefined) {
          // this function will typically be called multiple times per idx
          // the last update per idx should occur when the pitches are correct and complete
          this.timer.timepoints[idx] = timestamp;
        }
      } catch {
        console.log("makeTimestamp failed");
        return null;
      }
    },
    computeHarmonizationGraded: function (activeMidi) {
      var targets = this.definition.getHarmonizationTargets
        ? this.definition.getHarmonizationTargets() : [];
      var ptr = this._harmonizationPointer;
      if (!activeMidi || !activeMidi.length) {
        return {
          result: this.grader.STATE.PARTIAL,
          score: 1,
          activeIndex: ptr,
          problems: [],
        };
      }
      var matchResult = HarmonizationGraderLogic.harmonizationMatch(targets[ptr] || {}, activeMidi);
      if (matchResult.state === "correct" || matchResult.state === "partial") {
        this._harmonizationRejected = null;
        this.acceptedHarmonizationSonorities.push({
          midi: activeMidi.slice(),
          targetIndex: ptr,
          ts: Date.now(),
        });
        this._harmonizationPointer = ptr + 1;
      } else if (matchResult.state === "incorrect") {
        var tgt = targets[ptr] || {};
        var offsetQb = tgt.offset || 0;
        var beatsPerMeasure = 4; // quarter-beat denominator; most exercises are 4/4
        var mIdx = Math.floor(offsetQb / beatsPerMeasure);
        var onsetWithinMeasure = Math.round((offsetQb - mIdx * beatsPerMeasure) * 1024);
        this._harmonizationRejected = {
          midi: activeMidi.slice(),
          spellings: null, // populated by click_note._commit for click path
          measureIndex: mIdx,
          onset: onsetWithinMeasure,
          reasons: matchResult.reasons,
          target: tgt,
        };
        this._emitHarmonizationIncorrectFeedback(matchResult);
      }
      var allDone = this._harmonizationPointer >= targets.length && targets.length > 0;
      return {
        result: allDone ? this.grader.STATE.CORRECT
          : (matchResult.state === "incorrect" ? this.grader.STATE.INCORRECT : this.grader.STATE.PARTIAL),
        score: allDone ? 0 : (matchResult.state === "incorrect" ? 2 : 1),
        activeIndex: this._harmonizationPointer,
        problems: [matchResult],
      };
    },

    /**
     * Runs the grading process for the given exercise definition
     * and input chords.
     *
     * @return undefined
     * @fires graded
     */
    grade: function () {
      var state, graded;
      var nextUrl = this.definition.getNextExercise();
      var isChoraleExercise =
        typeof this.definition.isChorale === "function" &&
        this.definition.isChorale();
      var isHarmonizationExercise = this._isHarmonizationExercise();
      var isIdentificationExercise =
        typeof this.definition.isIdentification === "function" &&
        this.definition.isIdentification();
      var isChoraleIdentificationExercise =
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification();
      var isAnyIdentificationExercise =
        isIdentificationExercise || isChoraleIdentificationExercise;

      if (isAnyIdentificationExercise) {
        this.submitIdentPage({ fromGrade: true });
        return;
      } else if (isHarmonizationExercise) {
        this.triggerTimer();
        var activeMidi;
        if (this._harmonizationActiveMidiOverride != null) {
          activeMidi = this._harmonizationActiveMidiOverride;
        } else {
          var tracker = this._harmonizationHeldTracker;
          activeMidi = tracker ? tracker.activeMidi(Date.now()) : [];
        }
        graded = this.computeHarmonizationGraded(activeMidi);
      } else {
        graded = this.grader.grade(this.definition, this.inputChords);
      }
      // TODO: What does this do?
      if (this.inputChords._items[0]._notes[109]) {
        // window.console.dir('catch dummy note');
        state = ExerciseContext.STATE.WAITING;
      } else {
        switch (graded.result) {
          case this.grader.STATE.CORRECT:
            if (this.sealed != true) {
              this.makeTimestamp();
            }
            this.done = true;

            this.endTimer();

            if (this.sealed != true && isHarmonizationExercise) {
              var vlMeta = (this.definition.exercise && this.definition.exercise.score &&
                this.definition.exercise.score.umto && this.definition.exercise.score.umto.metadata) || {};
              this.harmonizationVLScore = VoiceLeadingLogic.scoreVoiceLeading(
                this.acceptedHarmonizationSonorities || [],
                { maxDisplacement: vlMeta.max_voice_displacement || 4 }
              );
              this.harmonizationTier = (this.harmonizationVLScore.smoothOK &&
                this.harmonizationVLScore.noParallels &&
                this.harmonizationVLScore.noDoubledLT)
                ? "excellent" : "developing";
            }

            if (this.sealed != true) {
              // For one-time function calls
              this.submitExerciseReport();
            }

            var treatAsFlawless = this.flawless === true || isChoraleExercise || isHarmonizationExercise || isAnyIdentificationExercise;
            var treatAsFinishedWithErrors =
              this.flawless === false && !isChoraleExercise && !isHarmonizationExercise && !isAnyIdentificationExercise;

            if (treatAsFlawless) {
              state = ExerciseContext.STATE.CORRECT;
              if (this.sealed != true) {
                // For one-time function calls
                this.triggerNextExercise();
              }
              this.midiTriggerNextExercise();
            } else if (treatAsFinishedWithErrors) {
              state = ExerciseContext.STATE.FINISHED;
              if (this.sealed != true) {
                // For one-time function calls
                if (IGNORE_MISTAKES_ON_AUTO_ADVANCE === true) {
                  this.triggerNextExercise();
                } else {
                  this.triggerRepeatExercise();
                }
              }
            } else {
              console.log("Unexpected condition");
              state = ExerciseContext.STATE.CORRECT;
            }

            this.sealed = true;
            break;
          case this.grader.STATE.INCORRECT:
            this.makeTimestamp();
            this.flawless = false;
            this.errorTally += 1;
            state = ExerciseContext.STATE.INCORRECT;
            this.done = false;
            break;
          case this.grader.STATE.PARTIAL:
            this.makeTimestamp();
          default:
            state = ExerciseContext.STATE.WAITING;
            this.done = false;
        }
      }

      // If the activeIndex changes, we have advanced to the next chord
      //   use || 0 to prevent broadcast when the condition would otherwise be undefined != 0
      if ((this.graded.activeIndex || 0) != graded.activeIndex) {
        this.exercise.broadcast(EVENTS.BROADCAST.NEXT_CHORD);
      }
      this.graded = graded;
      this.state = state;

      this.updateDisplayChords();
      if (!isChoraleExercise && !isHarmonizationExercise && !isAnyIdentificationExercise) {
        this.inputChords.goTo(graded.activeIndex);
      }

      this.trigger("graded");
    },
    gradeHarmonizationMidiSet: function (activeMidi) {
      this._harmonizationActiveMidiOverride = activeMidi || [];
      try {
        this.grade();
      } finally {
        this._harmonizationActiveMidiOverride = null;
      }
    },
    _emitHarmonizationIncorrectFeedback: function (matchResult) {
      if (!this.feedback) return;
      var reasons = matchResult.reasons || [];
      var feedbackId = "harmonization.grade.incorrect";
      if (reasons.indexOf("wrong_bass") !== -1) {
        feedbackId = "harmonization.grade.incorrect.wrong_inversion";
      } else if (reasons.indexOf("illegal_pc") !== -1) {
        feedbackId = "harmonization.grade.incorrect.wrong_quality";
      }
      var canvas = document.querySelector("#staffwrapper canvas, canvas");
      var anchorRect = canvas ? canvas.getBoundingClientRect() : { top: 200, left: 100, height: 0 };
      this.feedback.emit(feedbackId, { anchorRect: anchorRect });
    },
    /**
     * Debugging helper to ensure played MIDI notes match the UMTO grading targets.
     */
    validateGradingAlignment: function () {
      if (!this.definition.isUMTO || !this.definition.isUMTO() || !this.definition.exercise.grading) return;
      if (this.definition.isChorale && this.definition.isChorale()) return;

      const currentChord = this.inputChords.current();
      const playedPitches = _.sortBy(currentChord.getNoteNumbers());

      if (playedPitches.length === 0) return;

      // Find if these pitches match any grading slice
      const match = _.find(this.definition.grading, function (s) {
        const target = _.sortBy(s.target_midi_pitches);
        // Check for exact pitch match
        if (_.isEqual(playedPitches, target)) return true;
        
        // Check for pitch-class match (Inversion Error)
        const playedPCs = _.sortBy(_.map(playedPitches, p => p % 12));
        const targetPCs = _.sortBy(_.map(target, p => p % 12));
        if (_.isEqual(playedPCs, targetPCs)) {
            console.warn("[UMTO Debug] Inversion Error: Pitch classes match, but vertical ordering or octaves are wrong. Expected:", target, "Played:", playedPitches);
            return false;
        }
        return false;
      });

      if (!match) {
        console.warn(
          "[UMTO Debug] Pitch Error: Played",
          playedPitches,
          "does not match any defined GradingSlice."
        );
      } else if (match.rhythmic_flexibility === false) {
          // Future: check timing/onset alignment here if rhythmic_flexibility is false
      }
    },
    /**
     * Trigger timer. (Desirable: on first note that is played.)
     *
     * @return undefined
     */
    triggerTimer: function () {
      if (this.timer == null) {
        this.beginTimer();
        /**
         * Remembers errors
         */
        this.flawless = true;
        this.errorTally = 0;
      }
    },
    /**
     * Resets the timer.
     *
     * @return this
     */
    resetTimer: function () {
      this.timer = TimerLogic.createTimerState();
      return this;
    },
    /**
     * Returns true if the timer is non-null.
     *
     * @return {boolean}
     */
    hasTimer: function () {
      return this.timer !== null;
    },
    /**
     * Returns the duration of the exercise as a string.
     *
     * @return {string}
     */
    getExerciseDuration: function () {
      return this.timer.durationString;
    },
    getMinTempo: function () {
      if (parseInt(this.timer.minTempo) == NaN) {
        window.console.dir("tempo not integer");
        return "";
      }
      return this.timer.minTempo;
    },
    getMaxTempo: function () {
      if (parseInt(this.timer.maxTempo) == NaN) {
        window.console.dir("tempo not integer");
        return "";
      }
      return this.timer.maxTempo;
    },
    getTempoMean: function () {
      if (!this.timer.tempoMean || isNaN(this.timer.tempoMean)) {
        return "";
      }
      return this.timer.tempoMean;
    },
    getTempoRating: function () {
      if (!this.timer.tempoRating) {
        return "";
      }
      const star_factor = Math.round(this.timer.tempoRating);
      return "*".repeat(star_factor);
    },
    /**
     * Begins the timer.
     *
     * @return this
     */
    beginTimer: function () {
      if (this.timer === null) this.resetTimer();
      this.timer.start = new Date().getTime(); /* date in milliseconds */
      return this;
    },
    /**
     * Ends the timer.
     *
     * @return this
     */
    endTimer: function () {
      if (!this.timer) return this;

      if (this.timer.start && !this.timer.end) {
        this.timer.end = new Date().getTime();
        this.timer.duration = this.timer.end - this.timer.start;
        this.timer.durationString = TimerLogic.formatDurationString(this.timer.duration);
      }

      this.timer.timeIntervals = TimerLogic.computeTempoIntervals(this.timer.timepoints);

      var semibreveCount = TimerLogic.computeSemibreveCount(
        this.exerciseChords.settings.chords,
        this.inputChords._items.length,
        DEFAULT_RHYTHM_VALUE
      );

      this.timer.minTempo = null;
      this.timer.maxTempo = null;
      this.timer.tempoSD = null;
      this.timer.tempoRating = null;

      if (
        this.timer.timeIntervals.length > 1 &&
        this.timer.timeIntervals.length === semibreveCount.length
      ) {
        var centisemibrevesPerMin = TimerLogic.computeCentisemibrevesPerMin(
          this.timer.timeIntervals,
          semibreveCount
        );
        var stats = TimerLogic.computeTempoStats(centisemibrevesPerMin);
        this.timer.tempoSD    = stats.tempoSD;
        this.timer.tempoMean  = stats.tempoMean;
        this.timer.minTempo   = stats.minTempo;
        this.timer.maxTempo   = stats.maxTempo;
        this.timer.tempoRating = TimerLogic.computeTempoRating(stats.tempoSD, stats.tempoMean);
      }
      return this;
    },
    compileExerciseReport: function () {
      // not relevant what timezone the user computer thinks it is in
      // we must assume the computer time, accessed by the browser, is accurate
      // in any case, we save the server time (currently as performed_at)
      let offset = new Date().getTimezoneOffset();
      let timezone_str =
        "UTC" +
        (offset === 0
          ? ""
          : offset > 0
          ? String((offset * -1) / 60)
          : "+" + String((offset * -1) / 60));

      // No course context enforcement - allows independent tracking

      var idx = this.definition
        .getExerciseList()
        .reduce(function (selected, current, index) {
          return selected < 0 && current.selected ? index : selected;
        }, -1);

      if (!this.definition.getExerciseList()[idx]) {
        console.log(
          "Error: failed call of getExerciseList in compileExerciseReport"
        );
        return null;
      }

      // ADOPT THIS INSTEAD AND RENAME EXISTING JSON DATA KEYS ACCORDINGLY
      // time --> client_completion_date
      // DELETE timezone
      // exercise_error_tally --> error_tally
      // exercise_duration --> performance_duration_in_seconds
      // exercise_mean_tempo --> tempo_mean_semibreves_per_min
      // exercise_tempo_rating --> tempo_rating
      // ADD tempo_SD_semibreves_per_min (value for existing rows: null)
      // ADD time_intervals_in_milliseconds (value for existing rows: null)
      try {
        var urlParams = new URLSearchParams(window.location.search);
        var attempt_type = urlParams.get("mode") === "challenge" ? "mastery_challenge" : "practice";

        var report = {
          // new
          /* this.definition.getExerciseList()[idx].id returns e.g. PA00AA/1 */
          course_ID: this.definition.exercise.performing_course, // string
          playlist_ID: this.definition.getExerciseList()[idx].id.split("/")[0], // string
          exercise_num: parseInt(
            this.definition.getExerciseList()[idx].id.split("/")[1]
          ),
          client_completion_date: new Date(this.timer.end).toJSON(),
          error_tally:
            /* -1 means that errors are not reported (can't recall why not) */
            /* Analytical and figured_bass don't track errors; chorale does */
            ["analytical", "figured_bass"].includes(
              this.definition.exercise.type
            )
              ? -1
              : this.errorTally,
          performance_duration_in_seconds: this.timer.duration / 1000, // includes time before the user starts playing
          time_intervals_in_milliseconds: this.timer.timeIntervals,
          tempo_mean_semibreves_per_min: this.timer.tempoMean,
          tempo_SD_semibreves_per_min: this.timer.tempoSD,
          tempo_rating: this.timer.tempoRating,
          page_num: this._isIdentificationExercise() ? this._identPage + 1 : null,
          page_total: this._isIdentificationExercise()
            ? this.getTotalIdentPages()
            : null,
          is_final_page: this._isIdentificationExercise()
            ? this._identPage >= this.getTotalIdentPages() - 1
            : null,
          attempt_type: attempt_type,
        };

        if (this._isHarmonizationExercise()) {
          var targets = this.definition.getHarmonizationTargets ? this.definition.getHarmonizationTargets() : [];
          report.score_numerator = targets.length;
          report.score_denominator = targets.length;
        } else if (this.grader && typeof this.grader.getScore === "function") {
          var scoreData = this.grader.getScore();
          report.score_numerator = scoreData.numerator;
          report.score_denominator = scoreData.denominator;
        }

        if (this._isHarmonizationExercise()) {
          report.harmonization_accepted_sonorities = this.acceptedHarmonizationSonorities;
          report.harmonization_target_count = this.definition.getHarmonizationTargets
            ? this.definition.getHarmonizationTargets().length
            : null;
          report.harmonization_tier = this.harmonizationTier || null;
          report.vl_score = this.harmonizationVLScore || null;
        }
      } catch {
        return null;
      }

      return report;
    },
    submitExerciseReport: function (options) {
      const exercise_report = this.compileExerciseReport();
      console.log("[SCORE-DEBUG] Payload:", exercise_report);
      if (exercise_report == null) {
        console.log(
          "The course-playlist context could not be determined. No performance data submitted."
        );
        // window.alert("The course-playlist context could not be determined. No performance data submitted.");
        return null;
      }
      const json_data = JSON.stringify(exercise_report);
      const scoreCard = this.scoreCard;
      const shouldShowScoreCard = !(options && options.showScoreCard === false);
      $.ajax({
        type: "POST",
        url: "/ajax/exercise-performance/",
        data: { data: json_data },
        dataType: "json",
      })
        .done(function (data) {
          console.log("Exercise performance saved");
          if (shouldShowScoreCard && scoreCard && data && data.status === "ok") {
            scoreCard.show(data);
          }
        })
        .fail(function (jqXHR, textStatus, errorThrown) {
          console.log("Possible save failure", textStatus, errorThrown);
        });
    },
    saveIdentState: function () {
      if (!this._isIdentificationExercise()) return;
      var exerciseId = this.definition.exercise.exerciseId;
      if (!exerciseId) return;
      if (!this._identStateCache) this._identStateCache = {};
      var state = {
        answers: _.clone(this.grader.answers),
        identPage: this._identPage
      };
      this._identStateCache[exerciseId] = state;
      try {
        localStorage.setItem("identAnswers:" + exerciseId, JSON.stringify({
          answers: state.answers,
          identPage: state.identPage,
          savedAt: Date.now()
        }));
      } catch (e) {
        // localStorage unavailable — ignore
      }
    },

    restoreIdentState: function (exerciseId) {
      if (!this._isIdentificationExercise()) return;
      var cached = this._identStateCache && this._identStateCache[exerciseId];
      if (cached) {
        this.grader.answers = _.clone(cached.answers);
        this._identPage = cached.identPage;
      } else {
        var local = this._readLocalIdentState(exerciseId);
        if (local) {
          this.grader.answers = local.answers;
          this._identPage = local.identPage || 0;
          if (!this._identStateCache) this._identStateCache = {};
          this._identStateCache[exerciseId] = local;
        } else {
          // Try server fallback (async, fires after render)
          this._restoreIdentStateFromServer(exerciseId);
          // Reset immediately so the page shows clean while the fetch runs
          this.grader.reset();
          this._identPage = 0;
        }
      }
    },

    _restoreIdentStateFromServer: function (exerciseId) {
      var self = this;
      // Set a restoring flag so any input that arrives before the response
      // is ignored rather than graded against a blank state.
      this.grader._restoring = true;
      var restoreData = { exercise_id: exerciseId };
      var playlistId = this.definition && this.definition.exercise && this.definition.exercise.playlistName;
      if (playlistId) { restoreData.playlist_id = playlistId; }
      $.ajax({
        type: "GET",
        url: "/ajax/identification-answers/",
        data: restoreData,
        dataType: "json",
        timeout: 5000,
        success: function (data) {
          self.grader._restoring = false;
          var reviewMode = !!(self.definition && self.definition.exercise && self.definition.exercise.reviewMode);
          var restoreAnswers = IdentificationSubmitFlow._selectIdentificationRestoreAnswers({
            reviewMode: reviewMode,
            data: data,
          });
          if (restoreAnswers && Object.keys(restoreAnswers).length > 0) {
            self.grader.answers = restoreAnswers;
            self._identPage = reviewMode ? 0 : (data.page_num || 0);
            self.updateDisplayChords();
            self.trigger("graded");
          }
        },
        error: function (jqXHR, textStatus, errorThrown) {
          self.grader._restoring = false;
          console.log("Identification state restore failed:", textStatus, errorThrown);
        }
      });
    },
    _readLocalIdentState: function (exerciseId) {
      try {
        var raw = localStorage.getItem("identAnswers:" + exerciseId);
        if (!raw) return null;
        var data = JSON.parse(raw);
        var sevenDays = 7 * 24 * 60 * 60 * 1000;
        if (!data.savedAt || Date.now() - data.savedAt > sevenDays) {
          localStorage.removeItem("identAnswers:" + exerciseId);
          return null;
        }
        return data;
      } catch (e) {
        return null;
      }
    },
    submitIdentificationAnswers: function (options) {
      var isPageSubmit = options && options.is_page_submit === true;
      if (!this._isIdentificationExercise()) return;
      // No course context enforcement - allows independent tracking

      var grader = this.grader;
      if (!grader.answers || Object.keys(grader.answers).length === 0) return;

      // Compute correctness and score from current grader state
      var allProblems = this.definition.getProblems();
      var answers = grader.answers;
      var correctness = {};
      var correct = 0, incorrect = 0, unanswered = 0;

      for (var i = 0; i < allProblems.length; i++) {
        if (answers.hasOwnProperty(String(i))) {
          var isCorrect = answers[String(i)] === allProblems[i].answer;
          correctness[String(i)] = isCorrect;
          if (isCorrect) { correct++; } else { incorrect++; }
        } else {
          unanswered++;
        }
      }

      var idx = this.definition.getExerciseList().reduce(function (sel, cur, index) {
        return sel < 0 && cur.selected ? index : sel;
      }, -1);
      if (idx < 0) return;
      var listEntry = this.definition.getExerciseList()[idx];

      // Build correct_answers snapshot from problem definitions
      var correct_answers = {};
      for (var j = 0; j < allProblems.length; j++) {
        correct_answers[String(j)] = allProblems[j].answer;
      }

      var urlParams = new URLSearchParams(window.location.search);
      var attempt_type = urlParams.get("mode") === "challenge" ? "mastery_challenge" : "practice";

      var payload = {
        course_ID: this.definition.exercise.performing_course,
        playlist_ID: listEntry.id.split("/")[0],
        exercise_num: parseInt(listEntry.id.split("/")[1], 10),
        answers: answers,
        correctness: correctness,
        score: { correct: correct, incorrect: incorrect, unanswered: unanswered },
        correct_answers: correct_answers,
        page_num: this._identPage,
        is_page_submit: isPageSubmit,
        mode: options && options.mode ? options.mode : this.sessionMode,
        attempt_type: attempt_type,
      };

      var selfExerciseId = this.definition.exercise.exerciseId;
      $.ajax({
        type: "POST",
        url: "/ajax/identification-answers/",
        data: { data: JSON.stringify(payload) },
        dataType: "json"
      }).done(function (data) {
        console.log("Identification answers saved");
        try { localStorage.removeItem("identAnswers:" + selfExerciseId); } catch (e) {}
      }).fail(function (jqXHR, textStatus, errorThrown) {
        console.log("Identification answers save failed", textStatus, errorThrown);
      });
    },
    /**
     * Returns chords for display on screen.
     *
     * @return {object}
     */
    getDisplayChords: function () {
      return this.displayChords;
    },
    /**
     * Returns chords for exercise analysis on screen.
     *
     * @return {object}
     */
    getExerciseChords: function () {
      return this.exerciseChords;
    },
    /**
     * Returns the time signature for display.
     *
     * @return undefined
     */
    getTimeSignature: function () {
      return this.timeSignature;
    },
    /**
     * Obtain semibreves per line for horizontal scaling.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.semibrevesPerLine;
    },
    /**
     * Returns the chords being used for input to the exercise.
     *
     * @return {object}
     */
    getInputChords: function () {
      return this.inputChords;
    },
    /**
     * Returns the state of the exercise context.
     *
     * @return {string}
     */
    getState: function () {
      return this.state;
    },
    /**
     * Returns a graded object for the exercise, or false
     * if the exercise hasn't been graded yet.
     *
     * @return {boolean|object}
     */
    getGraded: function () {
      return this.graded;
    },
    /**
     * Returns the exercise definition object.
     *
     * @return {object}
     */
    getDefinition: function () {
      return this.definition;
    },
    /**
     * Returns true when the active exercise is identification-like.
     *
     * @return {boolean}
     */
    _isIdentificationExercise: function () {
      return (
        (typeof this.definition.isIdentification === "function" &&
          this.definition.isIdentification()) ||
        (typeof this.definition.isChoraleIdentification === "function" &&
          this.definition.isChoraleIdentification())
      );
    },
    _isHarmonizationExercise: function () {
      return (
        typeof this.definition.isHarmonization === "function" &&
        this.definition.isHarmonization()
      );
    },
    /**
     * Returns the current identification page index.
     *
     * @return {number}
     */
    getIdentPage: function () {
      return this._identPage;
    },
    /**
     * Returns the configured identification page size.
     *
     * @return {number}
     */
    getIdentPageSize: function () {
      return this._identPageSize;
    },
    _getChoraleIdentPageMeasureCount: function () {
      var display = this.definition && this.definition.getDisplay
        ? this.definition.getDisplay()
        : {};
      return IdentPageLogic.getChoralePageMeasureCount(display);
    },
    /**
     * Returns the absolute index of the first problem on the active page.
     *
     * @return {number}
     */
    getIdentPageOffset: function () {
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.computeIdentPageOffset(this._identPage, this._identPageSize, false, [], 0, 0);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.computeIdentPageOffset(
        this._identPage, this._identPageSize, true,
        this.definition.getProblems() || [], totalMeasures, maxMeasures
      );
    },
    /**
     * Returns the total number of identification pages.
     *
     * @return {number}
     */
    getTotalIdentPages: function () {
      var allProblems = this.definition.getProblems() || [];
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.computeTotalIdentPages(allProblems, false, 0, 0, this._identPageSize);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.computeTotalIdentPages(allProblems, true, totalMeasures, maxMeasures, this._identPageSize);
    },
    /**
     * Returns the identification problems visible on the active page.
     *
     * @return {Array}
     */
    getVisibleProblems: function () {
      var allProblems = this.definition.getProblems() || [];
      var isChoraleIdent = !!(this.definition &&
        typeof this.definition.isChoraleIdentification === "function" &&
        this.definition.isChoraleIdentification());
      if (!isChoraleIdent) {
        return IdentPageLogic.filterVisibleProblems(allProblems, false, this._identPage, this._identPageSize, 0, 0);
      }
      var maxMeasures = this._getChoraleIdentPageMeasureCount();
      var score = this.definition.getScore();
      var totalMeasures = score && score.measures ? score.measures.length : 0;
      return IdentPageLogic.filterVisibleProblems(
        allProblems, true, this._identPage, this._identPageSize, totalMeasures, maxMeasures
      );
    },
    /**
     * Navigates to a specific identification page.
     *
     * @param {number} n
     * @return {boolean}
     */
    goToIdentPage: function (n) {
      var total = this.getTotalIdentPages();
      if (n < 0 || n >= total) {
        return false;
      }
      var self = this;
      var direction = n > this._identPage ? 'next' : 'prev';
      var wrapper = document.getElementById('staffwrapper');
      var renderDelay = 0;

      if (wrapper) {
        wrapper.classList.remove('ident-page-turn-next', 'ident-page-turn-prev');
        void wrapper.offsetWidth; // force reflow so re-adding triggers animation
        wrapper.classList.add('ident-page-turn-' + direction);
        renderDelay = 140; // wait until opacity=0 at 40% of 350ms animation
        setTimeout(function () {
          wrapper.classList.remove('ident-page-turn-next', 'ident-page-turn-prev');
        }, 400);
      }

      setTimeout(function () {
        self._identPage = n;
        self.sealed = false;
        self.done = false;
        self.flawless = true;
        self.errorTally = 0;
        self.timer = null;
        self.state = ExerciseContext.STATE.READY;
        self.updateDisplayChords();
        // Re-grade the new page so colour feedback is visible immediately
        // (e.g. when navigating back to an already-answered page).
        var visibleProblems = self.getVisibleProblems();
        var pageOffset = self.getIdentPageOffset();
        var hasAnyAnswer = visibleProblems.some(function (_, i) {
          return self.grader.answers && self.grader.answers.hasOwnProperty(pageOffset + i);
        });
        if (hasAnyAnswer) {
          self.graded = self.grader.grade(self.definition, visibleProblems, pageOffset);
        } else {
          self.graded = false;
        }
        if (self.exercise && typeof self.exercise.trigger === "function") {
          self.exercise.trigger("change");
        }
        self.trigger("graded");
      }, renderDelay);

      return true;
    },
    /**
     * Submits the active identification page.
     *
     * @param {object=} options
     * @param {boolean=} options.fromGrade
     * @param {boolean=} options.fromUI
     * @param {boolean=} options.triggerPlaylistAdvance
     * @return {object|null}
     */
    submitIdentPage: function (options) {
      var graded, isLastPage, shouldAdvancePlaylist, submitPlan;
      var visibleProblems = this.getVisibleProblems();
      var totalPages = this.getTotalIdentPages();

      if (!visibleProblems.length) {
        return null;
      }

      graded = this.grader.grade(this.definition, visibleProblems, this.getIdentPageOffset());
      this.graded = graded;
      this.updateDisplayChords();
      graded.handled = true;
      graded.advancedPage = false;
      graded.completedExercise = false;

      shouldAdvancePlaylist = true;
      if (options && options.triggerPlaylistAdvance === false) {
        shouldAdvancePlaylist = false;
      }

      var fromUI = options && options.fromUI === true;
      isLastPage = this._identPage >= totalPages - 1;
      submitPlan = IdentificationSubmitFlow._planIdentificationSubmit({
        fromUI: fromUI,
        isLastPage: isLastPage,
        result: graded.result,
        correctState: this.grader.STATE.CORRECT,
        sealed: this.sealed == true,
      });

      if (submitPlan.saveAttempt) {
        this.submitIdentificationAnswers({
          is_page_submit: true,
          mode: options && options.mode
        });
      }

      if (graded.result === this.grader.STATE.CORRECT) {
        if (this.sealed != true) {
          this.makeTimestamp();
        }

        if (!isLastPage) {
          this.done = false;
          if (!this.timer) { this.triggerTimer(); }
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport({ showScoreCard: false });
          }
          graded.advancedPage = true;
          this.goToIdentPage(this._identPage + 1);
        } else {
          this.done = true;
          if (!this.timer) { this.triggerTimer(); }
          this.endTimer();
          if (this.sealed != true) {
            this.submitExerciseReport();
          }
          this.state = ExerciseContext.STATE.CORRECT;
          this.sealed = true;
          graded.completedExercise = true;
          if (this.exercise && typeof this.exercise.trigger === "function") {
            this.exercise.trigger("change");
          }
          this.trigger("graded");
          if (shouldAdvancePlaylist) {
            this.triggerNextExercise();
          }
        }
      } else {
        // A failed submit-mode check should fall back to practice immediately
        // so the UI stops implying the page is still in submit/correction mode.
        this.done = false;
        this.sealed = false;
        this.state =
          graded.result === this.grader.STATE.INCORRECT
            ? ExerciseContext.STATE.INCORRECT
            : ExerciseContext.STATE.WAITING;
        if (graded.result === this.grader.STATE.INCORRECT) {
          this.flawless = false;
          this.errorTally += 1;
        }
        if (this.sessionMode === "submit") {
          this.sessionMode = "practice";
        }
        if (submitPlan.advancePage) {
          graded.advancedPage = true;
          this.goToIdentPage(this._identPage + 1);
          return graded;
        }
        if (this.exercise && typeof this.exercise.trigger === "function") {
          this.exercise.trigger("change");
        }
        this.trigger("graded");
      }

      return graded;
    },
    /**
     * Advances to the next exercise.
     *
     * @return undefined
     */
    goToNextExercise: function (options) {
      var fromUI = options && options.fromUI === true;
      var totalPages = this.getTotalIdentPages();
      var isLastPage = this._identPage >= totalPages - 1;

      if (
        this._isIdentificationExercise() &&
        totalPages > 1 &&
        !isLastPage &&
        this.sealed !== true
      ) {
        return this.submitIdentPage({
          fromUI: fromUI,
          triggerPlaylistAdvance: !fromUI,
        });
      }
      // When called from the UI Next button, return null so the caller
      // (renderNextExercise) handles renderPristine — avoids re-broadcasting
      // NEXTEXERCISE which would recurse back into renderNextExercise.
      if (fromUI) {
        return null;
      }
      this.exercise.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
      return null;
    },
    /**
     * Advances to the previous exercise or page.
     *
     * @return undefined
     */
    goToPreviousExercise: function (options) {
      var fromUI = options && options.fromUI === true;
      if (
        this._isIdentificationExercise() &&
        this.getTotalIdentPages() > 1 &&
        this._identPage > 0
      ) {
        this.goToIdentPage(this._identPage - 1);
        return { handled: true, completedExercise: false };
      }
      if (fromUI) {
        return null;
      }
      this.exercise.broadcast(EVENTS.BROADCAST.PREVIOUSEXERCISE);
      return null;
    },
    reloadExercise: function () {
      this.exercise.broadcast(EVENTS.BROADCAST.PRISTINE);
    },
    /**
     * Returns true if the trigger notes are played together on the
     * keyboard.
     */
    midiTriggerNextExercise: async function () {
      if (this.done !== true || AUTO_ADVANCE === true) {
        return false;
      }
      var chord = this.inputChords.current().getSortedNotes();
      var trigger_notes = [60, 62, 64, 65, 67, 69, 71];
      if (chord.length != trigger_notes.length) {
        return false;
      }
      var i, len;
      for (i = 0, len = chord.length; i < len; i += 1) {
        if (chord[i] != trigger_notes[i]) {
          return false;
        }
      }
      this.goToNextExercise();
    },
    /**
     * Wait function.
     */
    sleep: function (ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    },
    /**
     * This will trigger the application to automatically advance
     * to the next exercise (if there is one) in the sequence if the user
     * has played a special combination of keys on the piano.
     *
     * This is intended as a shortcut for hitting the "next"
     * button on the UI.
     *
     * @return undefined
     */
    triggerNextExercise: async function () {
      if (ExerciseCompletionFlow._shouldDeferCompletionAutomation(this.scoreCard)) {
        return;
      }
      if (
        this.done === true &&
        AUTO_ADVANCE === true &&
        this.definition.exercise.nextExercise
      ) {
        await this.sleep(AUTO_ADVANCE_DELAY * 1000);
        if (ExerciseCompletionFlow._shouldDeferCompletionAutomation(this.scoreCard)) {
          return;
        }
        this.goToNextExercise();
      }
    },
    /**
     * This will trigger the application to refresh the current exercise.
     *
     * @return undefined
     */
    triggerRepeatExercise: async function () {
      if (ExerciseCompletionFlow._shouldDeferCompletionAutomation(this.scoreCard)) {
        return;
      }
      if (this.done === true && AUTO_REPEAT === true) {
        await this.sleep(AUTO_REPEAT_DELAY * 1000);
        if (ExerciseCompletionFlow._shouldDeferCompletionAutomation(this.scoreCard)) {
          return;
        }
        this.reloadExercise();
      }
    },
    /**
     * Creates a new set of display chords.
     * Called for its side effects.
     *
     * @return this
     */
    updateDisplayChords: function () {
      this.displayChords = this.createDisplayChords();
      return this;
    },
    /**
     * Helper function that creates the display chords.
     *
     * @return {object}
     */
    createDisplayChords: function () {
      var notes = [];
      var exercise_chords = [];
      var staffDistribution = this.definition.getStaffDistribution();
      var problems = this._isIdentificationExercise()
        ? this.getVisibleProblems()
        : this.definition.getProblems();
      var CORRECT = this.grader.STATE.CORRECT;
      var g_problem, chord, chords, rhythm;

      for (var i = 0, len = problems.length; i < len; i++) {
        notes = problems[i].visible;
        full_context = problems[i].notes;
        rhythm = problems[i].rhythm;
        unison_idx = problems[i].unison_idx;

        g_problem = false;
        if (this.graded !== false && this.graded.problems[i]) {
          g_problem = this.graded.problems[i];
        }

        if (g_problem && g_problem.notes) {
          notes = notes.concat(g_problem.notes);
          notes = _.uniq(notes);
        }

        chord = new ExerciseChord({
          notes: notes,
          full_context: full_context,
          rhythm: rhythm,
          unison_idx: unison_idx,
        });

        if (g_problem) {
          _.each(
            g_problem.count,
            function (notes, correctness) {
              var is_correct = correctness === CORRECT;
              if (notes.length > 0) {
                chord.grade(notes, is_correct);
              }
            },
            this
          );
        }

        exercise_chords.push(chord);
      }

      chords = new ExerciseChordBank({
        staffDistribution: staffDistribution,
        chords: exercise_chords,
      });

      return chords;
    },
    /**
     * Helper function that creates the exercise chords.
     *
     * @return {object}
     */
    createExerciseChords: function () {
      var staffDistribution = this.definition.getStaffDistribution();
      var problems = this._isIdentificationExercise()
        ? this.getVisibleProblems()
        : this.definition.getProblems();
      var notes = [];
      var exercise_chords = [];
      var chords;
      var rhythm;

      for (var i = 0, len = problems.length; i < len; i++) {
        notes = problems[i].notes;
        rhythm = problems[i].rhythm;
        unison_idx = problems[i].unison_idx;
        // we can push any notewise features through this entry point!
        chord = new ExerciseChord({
          staffDistribution: staffDistribution,
          notes: notes,
          rhythm: rhythm,
          unison_idx: unison_idx,
        });
        exercise_chords.push(chord);
      }

      chords = new ExerciseChordBank({
        staffDistribution: staffDistribution,
        chords: exercise_chords,
      });

      return chords;
    },
  });

  MicroEvent.mixin(ExerciseContext);

  return ExerciseContext;
});
