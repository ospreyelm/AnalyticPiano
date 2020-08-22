define([
	'lodash',
	'app/utils/analyze'
], function(
	_,
	Analyze
) {
	/**
	 * ExerciseGrader object is responsible for grading a given inputChords for
	 * an exercise.
	 *
	 * @param settings {object}
	 * @constructor
	 */
	var ExerciseGrader = function(settings) {
		this.settings = settings || {};
		this.analyzer = new Analyze(this.settings.keySignature); /* for analysis-based grading */
	};

	var INCORRECT = 'incorrect';
	var CORRECT = 'correct';
	var PARTIAL = 'partial';

	/**
	 * Defines the possible exercise result states.
	 * @const
	 */
	ExerciseGrader.STATE = {
		INCORRECT: INCORRECT,
		CORRECT: CORRECT,
		PARTIAL: PARTIAL
	};

	_.extend(ExerciseGrader.prototype, {
		/**
		 * Exposes the possible exercise result states.
		 */
		STATE: ExerciseGrader.STATE,
		/**
		 * Grades an exercise and returns a result.
		 *
		 * @param {ExerciseDefinition} definition The exercise definition
		 * @param {ChordBank} inputChords The chord bank that will server as inputChords
		 * @return {object} A result object
		 */
		grade: function(definition, inputChords) {
			var problems = definition.getProblems();
			var items = inputChords.items();
			var chords = _.pluck(items, "chord");
			var graded = {
				result: null,
				score: 0,
				problems:[]
			};
			var score_map = {};
			var result_map = []; 
			var i, len, result, score, active_idx = problems.length; 

			score_map[CORRECT]=0;
			score_map[PARTIAL]=1;
			score_map[INCORRECT]=2;
			result_map = [CORRECT,PARTIAL,INCORRECT];
			score = score_map[CORRECT];

			console.log (definition.exercise.type);

			for(i = 0, len = problems.length; i < len; i++) {
				expected_notes = problems[i].notes;
				actual_notes = [];
				if(chords[i]) {
					actual_notes = chords[i].getNoteNumbers();
				}
				switch (definition.exercise.type) {
					case "matching":
						result = this.notesMatch(expected_notes, actual_notes);
						break
					case "analytical":
						result = this.analysisMatch(expected_notes, actual_notes);
						break;
					case "echo_bass":
						result = this.bassMatch(expected_notes, actual_notes);
						break;
					case "echo_soprano":
						result = this.sopranoMatch(expected_notes, actual_notes);
						break;
					default:
						result = this.notesMatch(expected_notes, actual_notes);
				}
				graded.problems[i] = {
					score: score_map[result.state],
					count: result.count,
					note: result.note,
					notes: result.notes
				};
				if(score_map[result.state] > score) {
					score = score_map[result.state];
					active_idx = i;
				}
			}

			graded.score = score;
			graded.result = result_map[score];
			graded.activeIndex = active_idx;

			return graded;
		},
		/**
		 * Given a set of expected and actual notes, this function
		 * will match the notes and return one of three values:
		 *
		 *	- INCORRECT: one or more notes are incorrect
		 *	- PARTIAL: one or more notes matched, but not all
		 *	- CORRECT: all notes matches
		 *
		 * in addition to other data for proper interaction.
		 *
		 * @param {array} expected
		 * @param {array} delivered
		 */
		notesMatch: function(expected, delivered) {
			/* parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			var mistake = false;

			var i, len;
			for (i = 0, len = delivered.length; i < len; i++) {
				midi = delivered[i];

				if (expected.indexOf(midi) !== -1) {
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				} else {
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
					mistake = true;
				}
			}

			result.state = (mistake === true ? INCORRECT :
				(
					result.count[CORRECT].length < expected.length
					? PARTIAL : CORRECT
				)
			);

			return result;
		},
		analysisMatch: function(expected, delivered) {
			/* parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			var mistake = false;

			/* inefficient to keep looking up the analysis; do once per exercise */
			var target_analysis = this.analyzer.to_scale_degree(expected_notes);
			var probe_analysis = this.analyzer.to_scale_degree(actual_notes);

			result.state = (probe_analysis === target_analysis ? CORRECT : PARTIAL);

			return result;
		},
		bassMatch: function(expected, delivered) {
			/* parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			var mistake = false;

			var i, len;
			for (i = 0, len = Math.min(1, delivered.length) /* bass only */;
				i < len; i++) {

				midi = delivered[i];

				if (expected.indexOf(midi) === 0) { /* bass only */
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				} else {
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
					mistake = true;
				}
			}

			console.log(result.count);

			result.state = (mistake === true ? INCORRECT :
				(
					/* bass only */
					result.count[CORRECT].length < Math.min(1, expected.length)
					? PARTIAL : CORRECT
				)
			);

			return result;
		},
		sopranoMatch: function(expected, delivered) {
			/* parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			var mistake = false;

			var i, len;
			for (i = Math.max(0, delivered.length-1), len = delivered.length /* soprano only */;
				i < len; i++) {

				midi = delivered[i];

				if (expected.indexOf(midi) === expected.length-1) { /* soprano only */
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				} else {
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
					mistake = true;
				}
			}

			console.log(result.count);

			result.state = (mistake === true ? INCORRECT :
				(
					/* soprano only */
					result.count[CORRECT].length < Math.min(1, expected.length)
					? PARTIAL : CORRECT
				)
			);

			return result;
		}
	});

	return ExerciseGrader;
});
