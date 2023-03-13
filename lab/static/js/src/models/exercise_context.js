define([
  "lodash",
  "jquery",
  "microevent",
  "./exercise_chord",
  "./exercise_chord_bank",
  "app/config",
  "app/components/events",
  "simple-statistics.min",
], function (
  _,
  $,
  MicroEvent,
  ExerciseChord,
  ExerciseChordBank,
  Config,
  EVENTS,
  SimpleStatistics
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

    this.state = ExerciseContext.STATE.READY;
    this.graded = false;
    this.timer = null;
    this.displayChords = this.createDisplayChords();
    this.exerciseChords = this.createExerciseChords();
    this.timeSignature = this.definition.getTimeSignature();

    // this.playlistRestarts = null; // this obsolete measurement was valuable

    this.sealed = false; /* will be used to ignore input post-completion */

    _.bindAll(this, ["grade", "triggerTimer"]);

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
      this.inputChords.bind("change", this.triggerTimer);
      this.inputChords.bind("change", this.grade);
    },
    /**
     * For tempo assessment
     */
    makeTimestamp: function () {
      if (!this.timer.timepoints) {
        console.log('makeTimestamp failed: no timepoints object found');
        return null;
      }
      var timestamp = Math.floor(new Date().getTime()) / 1000;
      var idx = this.graded.activeIndex;
      // console.log(idx);
      if (idx == undefined && Object.keys(this.timer.timepoints).length == 0) {
        idx = 0; // necessary for the first exercise of a playlist, unsure why
      }
      if (idx != undefined) {
        // this function will typically be called multiple times per idx
        // the last update per idx should occur when the pitches are correct and complete
        this.timer.timepoints[idx] = timestamp;
      }
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

      graded = this.grader.grade(this.definition, this.inputChords);

      if (this.inputChords._items[0]._notes[109]) {
        // window.console.dir('catch dummy note');
        state = ExerciseContext.STATE.CORRECT;
      } else {
        switch (graded.result) {
          case this.grader.STATE.CORRECT:
            if (this.sealed != true) {
              this.makeTimestamp();
            }
            this.done = true;

            this.endTimer();

            if (this.sealed != true) {
              // For one-time function calls
              this.submitExerciseReport();
            }

            if (this.flawless === true) {
              state = ExerciseContext.STATE.CORRECT;
              if (this.sealed != true) {
                // For one-time function calls
                this.triggerNextExercise();
              }
              this.midiTriggerNextExercise();
            } else if (this.flawless === false) {
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
            state = ExerciseContext.STATE.INCORRECT;
            this.done = false;
            this.flawless = false;
            this.errorTally += 1;
            break;
          case this.grader.STATE.PARTIAL:
            this.makeTimestamp();
          default:
            state = ExerciseContext.STATE.WAITING;
            this.done = false;
        }
      }

      this.graded = graded;
      this.state = state;

      this.updateDisplayChords();
      this.inputChords.goTo(graded.activeIndex);

      this.trigger("graded");
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
      this.timer = {};
      this.timer.start = null;
      this.timer.end = null;
      this.timer.duration = null;
      this.timer.durationString = "";
      this.timer.alternativeDurationString = "";
      this.timer.minTempo = null;
      this.timer.maxTempo = null;
      this.timer.tempoSD = null;
      this.timer.tempoRating = null;
      this.timer.timepoints = {};
      this.timer.timeIntervals = [];
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
      return '*' * star_factor;
    },
    /**
     * Begins the timer.
     *
     * @return this
     */
    beginTimer: function () {
      if (this.timer === null) this.resetTimer();
      this.timer.start = Math.floor(new Date().getTime()) / 1000; /* seconds */
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
        this.timer.end = Math.floor(new Date().getTime()) / 1000;
        this.timer.duration = this.timer.end - this.timer.start;
        var mins = Math.floor(this.timer.duration / 60);
        var seconds = (this.timer.duration - mins * 60).toFixed(1);
        if (mins == 0) {
          this.timer.durationString = seconds + "&Prime;";
          this.timer.alternativeDurationString = seconds + "s";
        } else {
          this.timer.durationString = mins + "&prime; " + seconds + "&Prime;";
          this.timer.alternativeDurationString = mins + "m" + seconds + "s";
        }
      }

      var tp = this.timer.timepoints;
      var tp_indeces = Object.keys(tp).sort(function(a, b){return a-b});
      for (var i = 1, len = tp_indeces.length; i < len; i++) {
        this.timer.timeIntervals.push(
          Math.trunc((tp[tp_indeces[i]] - tp[tp_indeces[i-1]]) * 1000) / 1000
        );
      }

      // console.log(this.timer.timeIntervals);

      var semibreve_fraction = { W: 1.5, w: 1, H: 0.75, h: 0.5, Q: 0.375, q: 0.25, E: 0.1875, e: 0.125 };

      var semibreveCount = [];
      len = Math.min(
        this.inputChords._items.length,
        this.exerciseChords.settings.chords.length
      );
      for (i = 0; i < len; i++) {
        var rhythm_value =
          this.exerciseChords.settings.chords[i].settings.rhythm ||
          DEFAULT_RHYTHM_VALUE;
        semibreveCount.push(
          semibreve_fraction[rhythm_value] || DEFAULT_RHYTHM_VALUE || 1
        );
      }
      if (semibreveCount.length > 0) semibreveCount.pop();

      if (
        this.timer.timeIntervals.length <= 1 ||
        this.timer.timeIntervals.length != semibreveCount.length /* guard against miscalculations */
      ) {
        this.timer.minTempo = null;
        this.timer.maxTempo = null;
        this.timer.tempoSD = null;
        this.timer.tempoRating = null;
      } else {
        var semibrevesPerMin = [];
        for (i = 0, len = this.timer.timeIntervals.length; i < len; i++) {
          let spm =
            Math.round((
              (60 / this.timer.timeIntervals[i]) * semibreveCount[i] + Number.EPSILON) * 10
            ) / 10; /* semibreves per minute sensitive to 1/10 */
          semibrevesPerMin.push(spm);
        }

        // console.log(semibrevesPerMin);

        this.timer.tempoSD =
          Math.round((
            SimpleStatistics.standardDeviation(semibrevesPerMin) + Number.EPSILON) * 100
          ) / 100; /* semibreves per minute sensitive to 1/100 */
        this.timer.tempoMean = SimpleStatistics.mean(semibrevesPerMin);
        this.timer.minTempo = Math.round(Math.min(...semibrevesPerMin));
        this.timer.maxTempo = Math.round(Math.max(...semibrevesPerMin));

        /* Tempo star-rating algorithm */
        // TO DO: ADD GRADATIONS BECAUSE SD AS 1/8 OF MEAN IS TOO NARROW FOR TWO STARS
        if (isNaN(this.timer.tempoSD) || isNaN(this.timer.tempoMean)) {
          this.timer.tempoRating = null;
        } else {
          this.timer.tempoRating =
            /* If the SD is equal to or less than 1/(2^n) of the mean
             * then the star-rating is n-1:
             *    1/8 or less: two stars
             *    1/16 or less: three stars
             *    1/32 or less: four stars
             *    1/64 or less: five stars */
            Math.max(
              1, // at least
              Math.min(
                5, // at most
                this.timer.tempoSD == 0 ? 5 // if there is no tempo variation
                  : Math.floor(
                    this.timer.tempoMean / this.timer.tempoSD
                  ).toString(2).length - 1
              )
            ) || 0; // in case calculation fails
        }
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

      if (this.definition.exercise.performing_course == null) {
        console.log('No course context found.');
        return null;
      }

      var idx = this.definition
        .getExerciseList()
        .reduce(function (selected, current, index) {
          return selected < 0 && current.selected ? index : selected;
        }, -1);

      if (!this.definition.getExerciseList()[idx]) {
        console.log('Error: failed call of getExerciseList in compileExerciseReport');
        return null;
      }

      // TO DO: replace this definition with the following
      var report = {
        course_ID: this.definition.exercise.performing_course || null,
        exercise_ID:
          /* returns e.g. PA00AA/1 */
          this.definition.getExerciseList()[idx].id || false,
        time: new Date().toJSON().slice(0, 16) || false,
        timezone: timezone_str || false,
        exercise_error_tally:
          /* -1 means that errors are not reported (can't recall why not) */
          ["analytical", "figured_bass"].includes(this.definition.exercise.type) ?
          -1 : this.errorTally,
        exercise_duration: /* seconds, sensitive to 1/10 */
          Math.trunc(this.timer.duration * 10) / 10 || false ,
        exercise_mean_tempo: Math.round(this.timer.tempoMean) || false,
        exercise_tempo_rating:
          /* 0 means tempo cannot be assessed (e.g. when an exercise comprises two chords) */
          this.timer.tempoRating ? this.timer.tempoRating : 0,
      };

      return report;

      var newReport = { // ADOPT THIS INSTEAD AND RENAME EXISTING JSON DATA KEYS ACCORDINGLY
        course_ID: this.definition.exercise.performing_course || null,
        exercise_ID:
          /* returns e.g. PA00AA/1 */
          this.definition.getExerciseList()[idx].id || null, // any impact to changing false to null?
        completion_date: new Date(this.timer.end * 1000).toJSON() || false,
        error_tally:
          /* -1 means that errors are not reported (can't recall why not) */
          ["analytical", "figured_bass"].includes(this.definition.exercise.type) ?
          -1 : this.errorTally,
        performance_duration_in_seconds: /* seconds, sensitive to 1/10 */
          Math.trunc(this.timer.duration * 10) / 10 || false ,
        time_intervals_in_seconds: this.timer.timeIntervals,
        tempo_mean_semibreves_per_min: Math.round(this.timer.tempoMean) || false,
        tempo_SD_semibreves_per_min: this.timer.tempoSD,
        tempo_rating:
          /* 0 means tempo cannot be assessed (e.g. when an exercise comprises two chords) */
          this.timer.tempoRating ? this.timer.tempoRating : 0,
      };

      console.log(newReport);
    },
    submitExerciseReport: function () {
      const json_data = JSON.stringify(this.compileExerciseReport());
      if (json_data == null) {
        console.log("Outside the context of a course and playlist. No performance data submitted.");
        // window.alert("Outside the context of a course and playlist. No performance data submitted.");
        return null;
      }
      $.ajax({
        type: "POST",
        url: "/ajax/exercise-performance/",
        data: { data: json_data },
        dataType: "text",
      })
        .done(function (data) {
          console.log("Exercise performance saved");
        })
        .fail(function (jqXHR, textStatus, errorThrown) {
          console.log("Possible save failure", textStatus, errorThrown);
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
     * Advances to the next exercise.
     *
     * @return undefined
     */
    goToNextExercise: function () {
      this.exercise.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
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
     * to the next exercise in the sequence if the user
     * has played a special combination of keys on the piano.
     *
     * This is intended as a shortcut for hitting the "next"
     * button on the UI.
     *
     * @return undefined
     */
    triggerNextExercise: async function () {
      if (this.done === true && AUTO_ADVANCE === true) {
        await this.sleep(AUTO_ADVANCE_DELAY * 1000);
        this.goToNextExercise();
      }
    },
    /**
     * This will trigger the application to refresh the current exercise.
     *
     * @return undefined
     */
    triggerRepeatExercise: async function () {
      if (this.done === true && AUTO_REPEAT === true) {
        await this.sleep(AUTO_REPEAT_DELAY * 1000);
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
      var problems = this.definition.getProblems();
      var CORRECT = this.grader.STATE.CORRECT;
      var g_problem, chord, chords, rhythm;

      for (var i = 0, len = problems.length; i < len; i++) {
        notes = problems[i].visible;
        full_context = problems[i].notes;

        rhythm = problems[i].rhythm;
        g_problem = false;
        if (this.graded !== false && this.graded.problems[i]) {
          g_problem = this.graded.problems[i];
        }

        if (g_problem) {
          notes = notes.concat(g_problem.notes);
          notes = _.uniq(notes);
        }

        chord = new ExerciseChord({
          notes: notes,
          full_context: full_context,
          rhythm: rhythm,
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
        // staffDistribution: staffDistribution,
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
      var problems = this.definition.getProblems();
      var notes = [];
      var exercise_chords = [];
      var chords;
      var rhythm;

      for (var i = 0, len = problems.length; i < len; i++) {
        notes = problems[i].notes;
        rhythm = problems[i].rhythm;
        // we can push any notewise features through this entry point!
        chord = new ExerciseChord({
          staffDistribution: staffDistribution,
          notes: notes,
          rhythm: rhythm,
        });
        exercise_chords.push(chord);
      }

      chords = new ExerciseChordBank({
        // staffDistribution: staffDistribution,
        chords: exercise_chords,
      });

      return chords;
    },
  });

  MicroEvent.mixin(ExerciseContext);

  return ExerciseContext;
});
