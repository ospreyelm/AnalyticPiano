define([
    'lodash',
    'jquery',
    'microevent',
    './exercise_chord',
    './exercise_chord_bank',
    'app/config',
    'app/components/events',
    'simple-statistics.min'
], function(
    _,
    $,
    MicroEvent,
    ExerciseChord,
    ExerciseChordBank,
    Config,
    EVENTS,
    SimpleStatistics
) {

    var testing = (window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false);

    var AUTO_ADVANCE_ENABLED = (testing ? true : Config.get('general.autoExerciseAdvance'));

    var NEXT_EXERCISE_WAIT = (testing ? 1000 : Config.get('general.nextExerciseWait'));

    var REPEAT_EXERCISE_WAIT = (testing ? 2000 : Config.get('general.repeatExerciseWait'));

    var REPEAT_EXERCISE_ENABLED = Config.get('general.repeatExercise');

    var DEFAULT_RHYTHM_VALUE = Config.get('general.defaultRhythmValue');

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
    var ExerciseContext = function(settings) {
        this.settings = settings || {};

        _.each(['definition','grader','inputChords'], function(attr) {
            if(!(attr in this.settings)) {
                throw new Error("missing settings."+attr+" constructor parameter");
            }
        }, this);

        this.definition = this.settings.definition;
        this.grader = this.settings.grader;
        this.inputChords = this.settings.inputChords;
        this.exercise = this.settings.exercise;

        this.state = ExerciseContext.STATE.READY;
        this.graded = false;
        this.timer = null;
        this.displayChords = this.createDisplayChords();
        this.exerciseChords = this.createExerciseChords();

        var ex_num_current = this.definition.getExerciseList().reduce(
            function(selected, current, index) {
                return (selected < 0 && current.selected) ? index + 1 : selected;
            },
            -1
        );
        if (ex_num_current == 1) {
            sessionStorage.removeItem('HarmonyLabPlaylistStartTime');
            sessionStorage.removeItem('HarmonyLabPlaylistTracker');
            sessionStorage.removeItem('HarmonyLabPlaylistRestarts');
            sessionStorage.removeItem('HarmonyLabPlaylistMinTempo');
            sessionStorage.removeItem('HarmonyLabPlaylistMaxTempo');
            sessionStorage.removeItem('HarmonyLabPlaylistTempoRating');
            this.seriesTimer = null;
            this.restarts = null;
            sessionStorage.removeItem('HarmonyLabPlaylistRestarts');
        } else if (sessionStorage.HarmonyLabPlaylistStartTime) {
            this.resetSeriesTimer(); // ?
            this.seriesTimer.start = sessionStorage.getItem('HarmonyLabPlaylistStartTime');
            this.restarts = parseInt(sessionStorage.getItem('HarmonyLabPlaylistRestarts')) || 0;
        } else {
            this.seriesTimer = null;
            this.restarts = null;
        }

        this.sealed = false; /* will be used to ignore input post-completion */
        this.timepoints = [];

        _.bindAll(this, ['grade', 'triggerTimer']);

        this.init();
    };

    /**
     * Defines the possible states
     * @type {object}
     * @const
     */
    ExerciseContext.STATE = {
        READY: "ready",// not started
        WAITING: "waiting",// so far so good
        INCORRECT: "incorrect",// errors
        CORRECT: "correct",// complete without errors
        FINISHED: "finished"// complete with errors
    };

    _.extend(ExerciseContext.prototype, {
        /**
         * Make the STATE values accessible via instance.
         */
        STATE: ExerciseContext.STATE,
        init: function() {
            this.initListeners();
        },
        /**
         * Initializes listeners.
         *
         * @return undefined
         */
        initListeners: function() {
            let testing = (window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false);
            if (testing && false) {
                $('.js-notation-opts-widget').hide();
                $('.js-keysignature-widget').hide();
            }
            this.inputChords.bind("change", this.triggerTimer);
            this.inputChords.bind("change", this.grade);
        },
        /**
         * For tempo assessment
         */
        makeTimestamp: function() {
            var timestamp = Math.floor(new Date().getTime()) / 1000;
            var idx = this.graded.activeIndex;
            if (idx == 0 && this.timepoints.length == 1) { /* updates */
                this.timepoints = [[idx, timestamp]];
            } else if (!this.timepoints[idx]) {
                this.timepoints.push([idx, timestamp]);
            }
        },
        /**
         * Runs the grading process for the given exercise definition
         * and input chords.
         *
         * @return undefined
         * @fires graded
         */
        grade: function() {
            var state, graded;
            var nextUrl = this.definition.getNextExercise();

            graded = this.grader.grade(this.definition, this.inputChords);

            if (this.inputChords._items[0]._notes[109]) {
                // window.console.dir('catch dummy note');
                state = ExerciseContext.STATE.CORRECT;
            } else { switch(graded.result) {
                case this.grader.STATE.CORRECT:
                    if (this.sealed != true) {
                        this.makeTimestamp();
                    }
                    this.done = true;

                    var ex_num_current = this.definition.getExerciseList().reduce(function(selected, current, index) {
                        return (selected < 0 && current.selected) ? index + 1 : selected;
                    }, -1);
                    var ex_num_prior = parseInt(sessionStorage.getItem('HarmonyLabPlaylistTracker'));
                    if(ex_num_current == ex_num_prior + 1) {
                        sessionStorage.setItem('HarmonyLabPlaylistTracker', ex_num_current);
                    }else if(ex_num_current == ex_num_prior) {
                        if(this.sealed != true) {
                            var restart_count = parseInt(sessionStorage.getItem('HarmonyLabPlaylistRestarts')) + 1;
                            this.restarts = restart_count;
                            sessionStorage.setItem('HarmonyLabPlaylistRestarts', restart_count);
                            sessionStorage.setItem('HarmonyLabPlaylistTracker', ex_num_current);
                        }
                    }else {
                        sessionStorage.setItem('HarmonyLabPlaylistTracker', -1);
                    }

                    this.endTimer();

                    if (this.sealed != true) {// For one-time function calls
                        this.submitExerciseReport();
                        if (!nextUrl) {
                            this.endSeriesTimer();
                            this.submitPlaylistReport();
                        }
                    }

                    this.recordTempoInformation();

                    if (this.flawless === true) {
                        state = ExerciseContext.STATE.CORRECT;
                        if (this.sealed != true) {// For one-time function calls
                            this.triggerNextExercise();
                        }
                        this.midiTriggerNextExercise();
                    } else if (this.flawless === false) {
                        state = ExerciseContext.STATE.FINISHED;
                        if (this.sealed != true) {// For one-time function calls
                            if (REPEAT_EXERCISE_ENABLED === true) {
                                this.triggerRepeatExercise();
                            } else {
                                this.triggerNextExercise();
                            }
                        }
                    } else {
                        console.log ('Unexpected condition');
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
                    /* The seriesFlawless value may be useful in addition to restarts. */
                    // this.seriesFlawless = false;
                    break;
                case this.grader.STATE.PARTIAL:
                    this.makeTimestamp();
                default:
                    state = ExerciseContext.STATE.WAITING;
                    this.done = false;
            }}

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
        triggerTimer: function() {
            if (this.seriesTimer == null) {
                this.beginSeriesTimer();
            }
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
        resetTimer: function() {
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
            return this;
        },
        resetSeriesTimer: function() {
            this.seriesTimer = {};
            this.seriesTimer.start = null;
            this.seriesTimer.end = null;
            this.seriesTimer.duration = null;
            this.seriesTimer.durationString = "";
            this.seriesTimer.alternativeDurationString = "";
            return this;
        },
        /**
         * Returns true if the timer is non-null.
         *
         * @return {boolean}
         */
        hasTimer: function() {
            return this.timer !== null;
        },
        hasSeriesTimer: function() {
            return this.seriesTimer !== null;
        },
        /**
         * Returns the duration of the exercise as a string.
         *
         * @return {string}
         */
        getExerciseDuration: function() {
            return this.timer.durationString;
        },
        getMinTempo: function() {
            if(parseInt(this.timer.minTempo) == NaN) {
                window.console.dir('tempo not integer');
                return "";
            }
            return this.timer.minTempo;
        },
        getMaxTempo: function() {
            if(parseInt(this.timer.maxTempo) == NaN) {
                window.console.dir('tempo not integer');
                return "";
            }
            return this.timer.maxTempo;
        },
        getTempoMean: function() {
            if( !this.timer.tempoMean || isNaN(this.timer.tempoMean) ) {
                return "";
            }
            return this.timer.tempoMean;
        },
        getTempoRating: function() {
            if(!this.timer.tempoRating) {
                return "";
            }
            return this.timer.tempoRating;
        },
        getGroupMinTempo: function() {
            if(parseInt(sessionStorage.getItem('HarmonyLabPlaylistMinTempo')) == NaN) {
                window.console.dir('tempo not integer');
                return "";
            }
            return sessionStorage.getItem('HarmonyLabPlaylistMinTempo');
        },
        getGroupMaxTempo: function() {
            if(parseInt(sessionStorage.getItem('HarmonyLabPlaylistMaxTempo')) == NaN) {
                window.console.dir('tempo not integer');
                return "";
            }
            return sessionStorage.getItem('HarmonyLabPlaylistMaxTempo');
        },
        getGroupTempoRating: function() {
            if(!sessionStorage.getItem('HarmonyLabPlaylistTempoRating')) {
                return "";
            }
            return sessionStorage.getItem('HarmonyLabPlaylistTempoRating');
        },
        getExerciseSeriesDuration: function() {
            if(sessionStorage.getItem('HarmonyLabPlaylistTracker') == -1) {
                return "";
            }
            return this.seriesTimer.durationString;
        },
        getExerciseGroupRestarts: function() {
            if(sessionStorage.getItem('HarmonyLabPlaylistTracker') == -1) {
                return "";
            }
            if(this.getExerciseSeriesDuration() == "") {
                return "";
            }
            return parseInt(this.restarts);
        },
        /**
         * Begins the timer.
         *
         * @return this
         */
        beginTimer: function() {
            if (this.timer === null) this.resetTimer();
            this.timer.start = Math.floor(new Date().getTime()) / 1000; /* seconds */
            return this;
        },
        /**
         * Ends the timer.
         *
         * @return this
         */
        endTimer: function() {
            if (!this.timer) return this;

            if (this.timer.start && !this.timer.end) {
                this.timer.end = Math.floor(new Date().getTime()) / 1000;
                this.timer.duration = this.timer.end - this.timer.start;
                var mins = Math.floor(this.timer.duration / 60);
                var seconds = (this.timer.duration - (mins * 60)).toFixed(1);
                if (mins == 0) {
                    this.timer.durationString = seconds + "&Prime;";
                    this.timer.alternativeDurationString = seconds + "s";
                } else {
                    this.timer.durationString = mins + "&prime; " + seconds + "&Prime;";
                    this.timer.alternativeDurationString = mins + "m" + seconds + "s";
                }
            }

            var time_zero = this.timepoints[0][1];
            var rel_timepoints = this.timepoints.map(function (tp) {
                /* sensitive to milliseconds */
                let time_rel = tp[1] % time_zero;
                return [tp[0], time_rel];
            });

            var i, len;

            var time_intervals = [];
            for(i = 1, len = rel_timepoints.length; i < len; i++) {
                time_intervals.push( rel_timepoints[i][1] - rel_timepoints[i-1][1] );
            }

            var semibreve_fraction = { "w": 1, "H": 0.75, "h": 0.5, "q": 0.25 };

            var semibreveCount = [];
            len = Math.min(
                this.inputChords._items.length,
                this.exerciseChords.settings.chords.length
            );
            for (i = 0; i < len; i++) {
                var rhythm_value = this.exerciseChords.settings.chords[i].settings.rhythm || DEFAULT_RHYTHM_VALUE;
                semibreveCount.push( semibreve_fraction[rhythm_value] || DEFAULT_RHYTHM_VALUE || 1 );
            }
            if (semibreveCount.length > 0) semibreveCount.pop();

            if (time_intervals.length < 1 || time_intervals.length != semibreveCount.length) {
                this.timer.minTempo = null;
                this.timer.maxTempo = null;
                this.timer.tempoSD = null;
                this.timer.tempoRating = null;
            } else {
                var semibrevesPerMin = [];
                for (i = 0, len = time_intervals.length; i < len; i++) {
                    let spm = Math.round( (60 / time_intervals[i] * semibreveCount[i] + Number.EPSILON) * 10 ) / 10; /* bpm sensitive to 1/10 */
                    semibrevesPerMin.push(spm);
                }
                this.timer.tempoSD = SimpleStatistics.standardDeviation(semibrevesPerMin);
                this.timer.tempoMean = SimpleStatistics.mean(semibrevesPerMin);
                this.timer.minTempo = Math.round(Math.min(... semibrevesPerMin));
                this.timer.maxTempo = Math.round(Math.max(... semibrevesPerMin));

                if ( isNaN(this.timer.tempoSD) || isNaN(this.timer.tempoMean) ) {
                    this.timer.tempoRating = null;
                } else {
                    this.timer.tempoRating = "*"
                        /* Tempo star-rating algorithm */
                        .repeat(Math.max(1, Math.min(5,
                                this.timer.tempoSD == 0 ? 5 :
                                    Math.floor(this.timer.tempoMean / this.timer.tempoSD)
                                    .toString(2).length - 1
                        ))) || "";
                }
            }
            return this;
        },
        /* Assess tempo aspect of exercise completion */
        recordTempoInformation: function() {
            /* Prepares tempo information */
            var former_min_tempo = null;
            var former_max_tempo = null;
            var former_tempo_rating = null;
            if(sessionStorage.getItem('HarmonyLabPlaylistMinTempo') && sessionStorage.getItem('HarmonyLabPlaylistMinTempo') != "null") {
                former_min_tempo = parseInt(sessionStorage.getItem('HarmonyLabPlaylistMinTempo'));
            }
            if(sessionStorage.getItem('HarmonyLabPlaylistMaxTempo') && sessionStorage.getItem('HarmonyLabPlaylistMaxTempo') != "null") {
                former_max_tempo = parseInt(sessionStorage.getItem('HarmonyLabPlaylistMaxTempo'));
            }
            if(sessionStorage.getItem('HarmonyLabPlaylistTempoRating') && sessionStorage.getItem('HarmonyLabPlaylistTempoRating') != "null") {
                former_tempo_rating = sessionStorage.getItem('HarmonyLabPlaylistTempoRating');
            }

            /* Updates tempo information in sessionStorage */
            if(former_min_tempo == null) {
                sessionStorage.setItem('HarmonyLabPlaylistMinTempo', this.timer.minTempo);
            }else {
                var new_min_tempo = Math.min(this.timer.minTempo, former_min_tempo);
                sessionStorage.setItem('HarmonyLabPlaylistMinTempo', new_min_tempo);
            }
            if(former_max_tempo == null) {
                sessionStorage.setItem('HarmonyLabPlaylistMaxTempo', this.timer.maxTempo);
            }else {
                var new_max_tempo = Math.max(this.timer.maxTempo, former_max_tempo);
                sessionStorage.setItem('HarmonyLabPlaylistMaxTempo', new_max_tempo);
            }
            if(former_tempo_rating == null) {
                sessionStorage.setItem('HarmonyLabPlaylistTempoRating', this.timer.tempoRating);
            }else {
                var new_tempo_rating = this.timer.tempoRating;
                let length = (new_tempo_rating ? new_tempo_rating.length : 0);
                if (length < former_tempo_rating.length && length !== 0) {
                    sessionStorage.setItem('HarmonyLabPlaylistTempoRating', new_tempo_rating);
                }
            }
        },
        /**
         * Begins the timer for whole exercise group.
         *
         * @return this
         */
        beginSeriesTimer: function() {
            if(this.seriesTimer === null) {
                this.resetSeriesTimer();
            }
            sessionStorage.setItem('HarmonyLabPlaylistTracker', 0);
            this.seriesTimer.start = (new Date().getTime() / 1000); /* seconds */
            sessionStorage.setItem('HarmonyLabPlaylistStartTime', this.seriesTimer.start);
            sessionStorage.setItem('HarmonyLabPlaylistRestarts', 0);
            sessionStorage.setItem('HarmonyLabPlaylistMinTempo', null);
            sessionStorage.setItem('HarmonyLabPlaylistMaxTempo', null);
            sessionStorage.setItem('HarmonyLabPlaylistTempoRating', null);
            return this;
        },
        /**
         * Ends the timer for whole exercise group.
         *
         * @return this
         */
        endSeriesTimer: function() {
            // window.console.dir('end series timer');
            var mins, seconds;
            if(this.seriesTimer && this.seriesTimer.start && !this.seriesTimer.end) {
                this.seriesTimer.end = (Math.floor(new Date().getTime()) / 1000);
                this.seriesTimer.duration = (this.seriesTimer.end - this.seriesTimer.start);
                mins = Math.floor(this.seriesTimer.duration / 60);
                seconds = (this.seriesTimer.duration - (mins * 60)).toFixed(0);
                if(mins == 0) {
                    this.seriesTimer.durationString = seconds + "&Prime;";
                    this.seriesTimer.alternativeDurationString = seconds + "s";
                } else {
                    this.seriesTimer.durationString = mins + "&prime;" + seconds + "&Prime;";
                    this.seriesTimer.alternativeDurationString = mins + "m" + seconds + "s";
                }
            }
            return this;
        },
        compileExerciseReport: function() {
            
            let offset = new Date().getTimezoneOffset()
            let timezone_str = "GMT" + ( offset === 0 ? "" : offset > 0 ? String(offset * -1 / 60) : "+" + String(offset *-1 / 60) );

            var idx = this.definition.getExerciseList().reduce(
                function(selected, current, index) {
                    return (selected < 0 && current.selected) ? index : selected;
                },-1);

            if (! this.definition.getExerciseList()[idx] ) {
                return null;
            }

            var report = {
                performer: sessionStorage.getItem('HarmonyLabPerformer') || null,
                exercise_ID: this.definition.getExerciseList()[idx].id || false,
                time: new Date().toJSON().slice(0,16) || false,
                timezone: timezone_str || false,
                exercise_error_tally: (["analytical", "figured_bass"].includes(this.definition.exercise.type) ? "n/a" : this.errorTally),
                exercise_tempo_rating: (this.timer.tempoRating ? this.timer.tempoRating.length : 0), // 0 means unable to asses
                exercise_mean_tempo: Math.round(this.timer.tempoMean) || false,
                exercise_duration: Math.floor((this.timer.duration + Number.EPSILON) * 10) / 10 || false, /* seconds, sensitive to 1/10 */
            };

            // if (idx+1 === getExerciseList().length) {
            //  report[playlist_restart_tally]: this.restarts || 0,
            //  report[playlist_lowest_tempo_rating]:
            //      Math.min(
            //          sessionStorage.getItem('HarmonyLabPlaylistTempoRating').length,
            //          this.timer.tempoRating.length /* unclear whether this is already factored in */
            //      ) || "",
            //  report[playlist_duration]: Math.floor((this.seriesTimer.duration + Number.EPSILON) * 10) / 10 || "", /* seconds, sensitive to 1/10 */
            // }

            return report;
        },
        compilePlaylistReport: function() {
            
            let offset = new Date().getTimezoneOffset()
            let timezone_str = "GMT" + ( offset === 0 ? "" : offset > 0 ? String(offset * -1 / 60) : "+" + String(offset *-1 / 60) );

            if (! this.definition.getExerciseList()[this.definition.getExerciseList().length - 1] ) {
                return null;
            }
            
            var report = {
                performer: sessionStorage.getItem('HarmonyLabPerformer') || null,
                time: new Date().toJSON().slice(0,16) || "",
                timezone: timezone_str || "",
                playlist_restart_tally: this.restarts || 0,
                playlist_lowest_tempo_rating:
                    // data from final exercise should be factored in already
                    sessionStorage.getItem('HarmonyLabPlaylistTempoRating').length || "",
                playlist_duration: Math.floor((this.seriesTimer.duration + Number.EPSILON) * 10) / 10 || "", /* seconds, sensitive to 1/10 */
                exercise_ID: this.definition.getExerciseList()[this.definition.getExerciseList().length - 1].id || "",
                };

            return report;
        },
        submitExerciseReport: function() {
            if (this.compileExerciseReport() == null) {
                console.log( "Outisde of a playlist. No data submitted.")
                return null;
            }
            // console.log( this.compileExerciseReport() );
            const json_data = JSON.stringify(this.compileExerciseReport());
            $.ajax({
                type: "POST",
                url: 'exercise-performance',
                data: {'data': json_data},
                dataType: 'json',
            });
        },
        submitPlaylistReport: function() {
            if (this.compilePlaylistReport() == null) {
                console.log( "Outisde of a playlist. No data submitted.")
                return null;
            }
            // console.log( this.compilePlaylistReport() );
            const json_data = JSON.stringify(this.compilePlaylistReport());
            $.ajax({
                type: "POST",
                url: 'playlist-performance',
                data: {'data': json_data},
                dataType: 'json',
            });
        },
        /**
         * Returns chords for display on screen.
         *
         * @return {object}
         */
        getDisplayChords: function() {
            return this.displayChords;
        },
        /**
         * Returns chords for exercise analysis on screen.
         *
         * @return {object}
         */
        getExerciseChords: function() {
            return this.exerciseChords;
        },
        /**
         * Returns the chords being used for input to the exercise.
         *
         * @return {object}
         */
        getInputChords: function() {
            return this.inputChords;
        },
        /**
         * Returns the state of the exercise context.
         *
         * @return {string}
         */
        getState: function() {
            return this.state;
        },
        /**
         * Returns a graded object for the exercise, or false
         * if the exercise hasn't been graded yet.
         *
         * @return {boolean|object}
         */
        getGraded: function() {
            return this.graded;
        },
        /**
         * Returns the exercise definition object.
         *
         * @return {object}
         */
        getDefinition: function() {
            return this.definition;
        },
        /**
         * Advances to the next exercise.
         *
         * @return undefined
         */
        goToNextExercise: function() {
            this.exercise.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
        },
        reloadExercise: function() {
            this.exercise.broadcast(EVENTS.BROADCAST.PRISTINE);
        },
        /**
         * Returns true if the trigger notes are played together on the
         * keyboard.
         */
        midiTriggerNextExercise: async function() {
            if (this.done !== true || AUTO_ADVANCE_ENABLED === true) {
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
        sleep: function(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
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
        triggerNextExercise: async function() {
            if (this.done === true && AUTO_ADVANCE_ENABLED === true) {
                await this.sleep(NEXT_EXERCISE_WAIT);
                this.goToNextExercise();
            }
        },
        /**
         * This will trigger the application to refresh the current exercise.
         *
         * @return undefined
         */
        triggerRepeatExercise: async function() {
            if (this.done === true && AUTO_ADVANCE_ENABLED === true) {
                await this.sleep(REPEAT_EXERCISE_WAIT);
                this.reloadExercise();
            }
        },
        /**
         * Creates a new set of display chords.
         * Called for its side effects.
         *
         * @return this
         */
        updateDisplayChords: function() {
            this.displayChords = this.createDisplayChords();
            return this;
        },
        /**
         * Helper function that creates the display chords.
         *
         * @return {object}
         */
        createDisplayChords: function() {
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
                if(this.graded !== false && this.graded.problems[i]) {
                    g_problem = this.graded.problems[i];
                }

                if(g_problem) {
                    notes = notes.concat(g_problem.notes);
                    notes = _.uniq(notes);
                }

                chord = new ExerciseChord({
                    notes: notes,
                    full_context: full_context,
                    rhythm: rhythm
                });

                if(g_problem) {
                    _.each(g_problem.count, function(notes, correctness) {
                        var is_correct = (correctness === CORRECT);
                        if(notes.length > 0) {
                            chord.grade(notes, is_correct);
                        }
                    }, this);
                }

                exercise_chords.push(chord);
            }

            chords = new ExerciseChordBank({
                // staffDistribution: staffDistribution,
                chords: exercise_chords
            });

            return chords;
        },
        /**
         * Helper function that creates the exercise chords.
         *
         * @return {object}
         */
        createExerciseChords: function() {
            var staffDistribution = this.definition.getStaffDistribution();
            var problems = this.definition.getProblems();
            var notes = [];
            var exercise_chords = [];
            var chords;
            var rhythm;

            for(var i = 0, len = problems.length; i < len; i++) {
                notes = problems[i].notes;
                rhythm = problems[i].rhythm;
                // we can push any notewise features through this entry point!
                chord = new ExerciseChord({
                    staffDistribution: staffDistribution,
                    notes: notes,
                    rhythm: rhythm
                });
                exercise_chords.push(chord);
            }

            chords = new ExerciseChordBank({
                // staffDistribution: staffDistribution,
                chords: exercise_chords
            });

            return chords;
        }
    });

    MicroEvent.mixin(ExerciseContext);

    return ExerciseContext;
});
