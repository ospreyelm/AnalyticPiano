define([
	'lodash',
	'jquery',
	'microevent',
	'./exercise_chord',
	'./exercise_chord_bank',
    'app/config',
    'simple-statistics.min'
], function(
	_,
	$,
	MicroEvent,
	ExerciseChord,
	ExerciseChordBank,
	Config,
	SimpleStatistics
) {

	var AUTO_ADVANCE_ENABLED = Config.get('general.autoExerciseAdvance');

	var NEXT_EXERCISE_WAIT = Config.get('general.nextExerciseWait');

	var REPEAT_EXERCISE_WAIT = Config.get('general.repeatExerciseWait');

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
			sessionStorage.removeItem('HarmonyLabExGroupStartTime');
			sessionStorage.removeItem('HarmonyLabExGroupTracker');
			sessionStorage.removeItem('HarmonyLabExGroupRestarts');
			sessionStorage.removeItem('HarmonyLabExGroupMinTempo');
			sessionStorage.removeItem('HarmonyLabExGroupMaxTempo');
			sessionStorage.removeItem('HarmonyLabExGroupTempoRating');
			this.seriesTimer = null;
			this.restarts = null;
		} else if (sessionStorage.HarmonyLabExGroupStartTime) {
			this.resetSeriesTimer();
			this.seriesTimer.start = sessionStorage.getItem('HarmonyLabExGroupStartTime');
			this.restarts = sessionStorage.getItem('HarmonyLabExGroupRestarts') || 0;
		} else {
			this.seriesTimer = null;
			this.restarts = null;
		}

		this.sealed = false; /* when true, will be used to ignore input after completion */
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
			this.inputChords.bind("change", this.triggerTimer);
			this.inputChords.bind("change", this.grade);
		},
		/**
		 * For tempo assessment
		 */
		makeTimestamp: function() {
			var timestamp = new Date().getTime() / 1000;
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

			switch(graded.result) {
				case this.grader.STATE.CORRECT:
					if(this.sealed != true) {
						this.makeTimestamp();
					}
					this.done = true;

					var ex_num_current = this.definition.getExerciseList().reduce(function(selected, current, index) {
						return (selected < 0 && current.selected) ? index + 1 : selected;
					}, -1);
					var ex_num_prior = parseInt(sessionStorage.getItem('HarmonyLabExGroupTracker'));
					if(ex_num_current == ex_num_prior + 1) {
						sessionStorage.setItem('HarmonyLabExGroupTracker', ex_num_current);
					}else if(ex_num_current == ex_num_prior) {
						if(this.sealed != true) {
							var restart_count = parseInt(sessionStorage.getItem('HarmonyLabExGroupRestarts')) + 1;
							this.restarts = restart_count;
							sessionStorage.setItem('HarmonyLabExGroupRestarts', restart_count);
							sessionStorage.setItem('HarmonyLabExGroupTracker', ex_num_current);
						}
					}else {
						sessionStorage.setItem('HarmonyLabExGroupTracker', -1);
					}

					this.endTimer();

					if(!nextUrl) {
						if(this.sealed != true) {// For one-time function calls
							this.endSeriesTimer();
							this.compileReport();
							this.submitReport();
						}
					}
					if(this.flawless === true) {
						state = ExerciseContext.STATE.CORRECT;
						if(this.sealed != true) {// For one-time function calls
							this.recordTempoInformation();
							this.triggerNextExercise();
						}
					}else if(this.flawless === false) {
						state = ExerciseContext.STATE.FINISHED;
						if(this.sealed != true) {// For one-time function calls
							if(REPEAT_EXERCISE_ENABLED === true) {
								this.triggerRepeatExercise();
							}else {
								this.triggerNextExercise();
							}
						}
					}
					else {
						state = ExerciseContext.STATE.CORRECT;
					}
					
					this.sealed = true;
					break;
				case this.grader.STATE.INCORRECT:
					if(this.inputChords._items[0]._notes[86]) {
						window.console.dir('caught dummy note');
						state = ExerciseContext.STATE.CORRECT;
						break;
					}
					this.makeTimestamp();
					state = ExerciseContext.STATE.INCORRECT;
					this.done = false;
					this.flawless = false;
					/* The seriesFlawless value may be useful in addition to restarts. */
					// this.seriesFlawless = false;
					break;
				case this.grader.STATE.PARTIAL:
					this.makeTimestamp();
				default:
					state = ExerciseContext.STATE.WAITING;
					this.done = false;
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
		getTempoRating: function() {
			if(!this.timer.tempoRating) {
				return "";
			}
			return this.timer.tempoRating;
		},
		getGroupMinTempo: function() {
			if(parseInt(sessionStorage.getItem('HarmonyLabExGroupMinTempo')) == NaN) {
				window.console.dir('tempo not integer');
				return "";
			}
			return sessionStorage.getItem('HarmonyLabExGroupMinTempo');
		},
		getGroupMaxTempo: function() {
			if(parseInt(sessionStorage.getItem('HarmonyLabExGroupMaxTempo')) == NaN) {
				window.console.dir('tempo not integer');
				return "";
			}
			return sessionStorage.getItem('HarmonyLabExGroupMaxTempo');
		},
		getGroupTempoRating: function() {
			if(!sessionStorage.getItem('HarmonyLabExGroupTempoRating')) {
				return "";
			}
			return sessionStorage.getItem('HarmonyLabExGroupTempoRating');
		},
		getExerciseSeriesDuration: function() {
			if(sessionStorage.getItem('HarmonyLabExGroupTracker') == -1) {
				return "";
			}
			return this.seriesTimer.durationString;
		},
		getExerciseGroupRestarts: function() {
			if(sessionStorage.getItem('HarmonyLabExGroupTracker') == -1) {
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
			this.timer.start = (new Date().getTime() / 1000); /* seconds */
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
				this.timer.end = new Date().getTime() / 1000;
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
				let time_rel = Math.round( (tp[1] % time_zero + Number.EPSILON) * 1000 ) / 1000;
				return [tp[0], time_rel];
			});

			var i, len;

			var time_intervals = [];
			for(i = 1, len = rel_timepoints.length; i < len; i++) {
				time_intervals.push( rel_timepoints[i][1] - rel_timepoints[i-1][1] );
			}

			var semibreve_fraction = { "w": 1, "h": 0.5, "q": 0.25 };

			var semibreveCount = [];
			for (i = 0, len = this.inputChords._items.length; i < len; i++) {
				var rhythm_value = this.exerciseChords.settings.chords[i].settings.rhythm;
				if (rhythm_value == null) {
					rhythm_value = DEFAULT_RHYTHM_VALUE;
				}
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
				console.log(semibrevesPerMin);
				this.timer.tempoSD = SimpleStatistics.standardDeviation(semibrevesPerMin);
				this.timer.minTempo = Math.round(Math.min(... semibrevesPerMin));
				this.timer.maxTempo = Math.round(Math.max(... semibrevesPerMin));

				if ( isNaN(this.timer.tempoSD) || isNaN(this.timer.minTempo) ) {
					this.timer.tempoRating = null;
				} else {
					this.timer.tempoRating = "*"
						/* Tempo star-rating algorithm */
						.repeat(Math.max(1, Math.min(5,
								this.timer.tempoSD == 0 ? 5 :
									Math.floor(this.timer.minTempo / this.timer.tempoSD)
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
			if(sessionStorage.getItem('HarmonyLabExGroupMinTempo') && sessionStorage.getItem('HarmonyLabExGroupMinTempo') != "null") {
				former_min_tempo = parseInt(sessionStorage.getItem('HarmonyLabExGroupMinTempo'));
			}
			if(sessionStorage.getItem('HarmonyLabExGroupMaxTempo') && sessionStorage.getItem('HarmonyLabExGroupMaxTempo') != "null") {
				former_max_tempo = parseInt(sessionStorage.getItem('HarmonyLabExGroupMaxTempo'));
			}
			if(sessionStorage.getItem('HarmonyLabExGroupTempoRating') && sessionStorage.getItem('HarmonyLabExGroupTempoRating') != "null") {
				former_tempo_rating = sessionStorage.getItem('HarmonyLabExGroupTempoRating');
			}

			/* Updates tempo information in sessionStorage */
			if(former_min_tempo == null) {
				sessionStorage.setItem('HarmonyLabExGroupMinTempo', this.timer.minTempo);
			}else {
				var new_min_tempo = Math.min(this.timer.minTempo, former_min_tempo);
				sessionStorage.setItem('HarmonyLabExGroupMinTempo', new_min_tempo);
			}
			if(former_max_tempo == null) {
				sessionStorage.setItem('HarmonyLabExGroupMaxTempo', this.timer.maxTempo);
			}else {
				var new_max_tempo = Math.max(this.timer.maxTempo, former_max_tempo);
				sessionStorage.setItem('HarmonyLabExGroupMaxTempo', new_max_tempo);
			}
			if(former_tempo_rating == null) {
				sessionStorage.setItem('HarmonyLabExGroupTempoRating', this.timer.tempoRating);
			}else {
				var new_tempo_rating = this.timer.tempoRating;
				if(new_tempo_rating.length < former_tempo_rating.length) {
					sessionStorage.setItem('HarmonyLabExGroupTempoRating', new_tempo_rating);
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
			sessionStorage.setItem('HarmonyLabExGroupTracker', 0);
			this.seriesTimer.start = (new Date().getTime() / 1000); /* seconds */
			sessionStorage.setItem('HarmonyLabExGroupStartTime', this.seriesTimer.start);
			sessionStorage.setItem('HarmonyLabExGroupRestarts', 0);
			sessionStorage.setItem('HarmonyLabExGroupMinTempo', null);
			sessionStorage.setItem('HarmonyLabExGroupMaxTempo', null);
			sessionStorage.setItem('HarmonyLabExGroupTempoRating', null);
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
				this.seriesTimer.end = (new Date().getTime() / 1000);
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
		compileReport: function() {
			var report = Object.create(null, {});
			var parameters = [];
			parameters.push(['1 performer',
				sessionStorage.getItem('HarmonyLabPerformer')]);
			parameters.push(['2 exercise',
				this.definition.getExerciseList()[this.definition.getExerciseList().length - 1].id]);
			parameters.push(['3 submission date',
				new Date().toDateString()]);
			parameters.push(['4 series duration',
				this.seriesTimer.alternativeDurationString]);
			parameters.push(['5 overall tempo',
				sessionStorage.getItem('HarmonyLabExGroupMinTempo')
				+ '–' + sessionStorage.getItem('HarmonyLabExGroupMaxTempo')
				+ ' (' + sessionStorage.getItem('HarmonyLabExGroupTempoRating')
				+ ')']);
			parameters.push(['6 restarts',
				this.restarts]);
			parameters.push(['7 final drill duration',
				this.timer.alternativeDurationString]);
			parameters.push(['8 final drill tempo',
				this.timer.minTempo + '–' + this.timer.maxTempo]);
			parameters.push(['9 series completion time',
				this.seriesTimer.end]);
			parameters.push(['TIMEPOINTS',this.timepoints]);
			for(i = 0; i < parameters.length; i++) {
				if(parameters[i].length == 2 && parameters[i][1] != undefined) {
					report[parameters[i][0]] = parameters[i][1];
				}
			}
			window.console.dir(report);
		},
		submitReport: function() {
			// Do something
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
			var nextUrl = this.definition.getNextExercise();
			var target = {"action": "next", "url": nextUrl};
			if(nextUrl) {
				this.trigger('goto', target);
			}
		},
		/**
		 * Checks if the next exercise can be loaded.
		 *
		 * Returns true if the trigger notes are played together on the
		 * keyboard.
		 *
		 * @param {object} chord a Chord object
		 * @return {boolean} true if "B" and "C" are played together, false otherwise.
		 */
		canGoToNextExercise: async function(chord) {
			var is_exercise_done = (this.done === true);
			var trigger_notes = [36]; // the "C" and "E" two octaves below middle "C"
			var wanted_notes = {};
			var count_notes = 0;
			var can_trigger_next = false;
			var note_nums, i, len, note;

			if(is_exercise_done) {
				note_nums = chord.getSortedNotes();
				for(i = 0, len = note_nums.length; i < len; i++) {
					note_num = note_nums[i];
					if(_.contains(trigger_notes, note_num) && !(note_num in wanted_notes)) {
						wanted_notes[note_num] = true;
						++count_notes;
					}
					if(count_notes == trigger_notes.length) {
						can_trigger_next = true;
						break;
					}
				}
			}

			return can_trigger_next;
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
			if(this.done === true && AUTO_ADVANCE_ENABLED === true) {
				await this.sleep(NEXT_EXERCISE_WAIT);
				this.goToNextExercise();
			}
			// if(this.canGoToNextExercise(this.inputChords.current())) {
			// 	this.goToNextExercise();
			// }
		},
		/**
		 * This will trigger the application to refresh the current exercise.
		 *
		 * @return undefined
		 */
		triggerRepeatExercise: async function() {
			if(this.done === true && AUTO_ADVANCE_ENABLED === true) {
				await this.sleep(REPEAT_EXERCISE_WAIT);
				window.location.reload();
			}
			// if(this.canGoToNextExercise(this.inputChords.current())) {
			// 	this.goToNextExercise();
			// }
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
			var problems = this.definition.getProblems();
			var CORRECT = this.grader.STATE.CORRECT;
			var g_problem, chord, chords, rhythm;

			for(var i = 0, len = problems.length; i < len; i++) {
				notes = problems[i].visible;
				rhythm = problems[i].rhythm;
				g_problem = false;
				if(this.graded !== false && this.graded.problems[i]) {
					g_problem = this.graded.problems[i];
				}

				if(g_problem) {
					notes = notes.concat(g_problem.notes);
					notes = _.uniq(notes);
				}

				chord = new ExerciseChord({ notes: notes, rhythm: rhythm });

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

			chords = new ExerciseChordBank({chords: exercise_chords});

			return chords;
		},
		/**
		 * Helper function that creates the exercise chords.
		 *
		 * @return {object}
		 */
		createExerciseChords: function() {
			var problems = this.definition.getProblems();
			var notes = [];
			var exercise_chords = []; 
			var chords;
			var rhythm;

			for(var i = 0, len = problems.length; i < len; i++) {
				notes = problems[i].notes;
				rhythm = problems[i].rhythm;
				// we can push any notewise features through this entry point!
				chord = new ExerciseChord({ notes: notes, rhythm: rhythm });
				exercise_chords.push(chord);
			}

			chords = new ExerciseChordBank({chords: exercise_chords});

			return chords;
		}
	});

	MicroEvent.mixin(ExerciseContext);

	return ExerciseContext;
});
