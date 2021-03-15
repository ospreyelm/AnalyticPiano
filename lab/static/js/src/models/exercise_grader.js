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
				problems: []
			};
			var score_map = {};
			var result_map = []; 
			var i, len, result, score, active_idx = problems.length; 

			score_map[CORRECT]=0;
			score_map[PARTIAL]=1;
			score_map[INCORRECT]=2;
			result_map = [CORRECT,PARTIAL,INCORRECT];
			score = score_map[CORRECT];

			var supported = [
				"chord_labels",
				"fixed_do",
				"intervals",
				"note_names",
				"pci",
				"pitch_class",
				"set_class_set",
				"set_class_normal",
				"set_class_prime",
				"set_class_forte",
				"roman_numerals",
				"scale_degrees",
				"scientific_pitch",
				"solfege",
				"do_based_solfege",
				"thoroughbass",
			];
			if (["analytical", "analytical_pcs", "figured_bass", "figured_bass_pcs"].includes(definition.exercise.type)) {
				var analysis_types = Object.keys(definition.exercise.analysis.mode)
					.filter( function(key) {return definition.exercise.analysis.mode[key];} )
					.filter( function(mode) {return supported.includes(mode);} );
				var abbrev_switch = definition.exercise.analysis.mode.abbreviate_thoroughbass;
			}

			for(i = 0, len = problems.length; i < len; i++) {
				expected_notes = problems[i].notes;
				actual_notes = [];
				if(chords[i]) {
					actual_notes = chords[i].getNoteNumbers();
					const dummy_idx = actual_notes.indexOf(109);
					if (dummy_idx > -1) {
						actual_notes.splice(dummy_idx, 1);
					}
				}
				switch (definition.exercise.type) {
					case "matching":
						result = this.notesMatch(expected_notes, actual_notes);
						break
					case "analytical":
						result = this.analysisMatch(expected_notes, actual_notes, analysis_types);
						break;
					case "analytical_pcs":
						result = this.analysisPcsMatch(expected_notes, actual_notes, analysis_types);
						break;
					case "figured_bass":
						/* Assessments by abbreviated figure likely flawed
						 * in the absence of pitch-class checks */
						abbrev_switch = false;
						result = this.figuredBassMatch(expected_notes, actual_notes, abbrev_switch);
						break;
					case "figured_bass_pcs":
						result = this.figuredBassPcsMatch(expected_notes, actual_notes, abbrev_switch);
						break;
					// case "echo_bass":
					// 	result = this.bassMatch(expected_notes, actual_notes);
					// 	break;
					// case "echo_soprano":
					// 	result = this.sopranoMatch(expected_notes, actual_notes);
					// 	break;
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

			// if (expected.length == 0) {
			// 	result.state = CORRECT;
			// 	return result;
			// }

			var mistake = false;

			var i, len;
			for (i = 0, len = delivered.length; i < len; i++) {
				var midi = delivered[i];

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
		analysisBool: function(expected, delivered, analysis_types) {
			var analyze_funcs = {
				"abbrev_thoroughbass": "abbrev_thoroughbass_figure",
				"chord_labels": "to_chord",
				"fixed_do": "to_fixed_do",
				"full_thoroughbass": "full_thoroughbass_figure_minus_octave",
				"intervals": "to_interval",
				"note_names": "to_note_name",
				"pci": "to_pci",
				"pitch_class": "to_pitch_class",
				"set_class_set": "to_set_class_set",
				"set_class_normal": "to_set_class_normal",
				"set_class_prime": "to_set_class_prime",
				"set_class_forte": "to_set_class_forte",
				"roman_numerals": "to_chord",
				"scale_degrees": "to_scale_degree",
				"scientific_pitch": "getNoteName",
				"solfege": "to_solfege",
				"do_based_solfege": "to_do_based_solfege",
			};
			var analyze_props = {
				"abbrev_thoroughbass": "", // ok
				"chord_labels": ".label", // ok
				"fixed_do": "", // ok
				"full_thoroughbass": "", // ok
				"intervals": ".name", // ok
				"note_names": "", // ok
				"pci": "", // ok
				"pitch_class": "",
				"set_class_set": "",
				"set_class_normal": "",
				"set_class_prime": "",
				"set_class_forte": "",
				"roman_numerals": ".label", // ok
				"scale_degrees": "", // ok
				"scientific_pitch": "", // ok
				"solfege": "", // ok
				"do_based_solfege": "",
			};
			var i, len;
			for (i = 0, len = analysis_types.length; i < len; i++) {
				var expected_result = "";
				var delivered_result = "";

				var func = analyze_funcs[analysis_types[i]];
				var prop = analyze_props[analysis_types[i]];

				if (func == "getNoteName") {
					if (expected.length == 1) {
						/* Possible change: run this once only per exercise? */
						expected_result = eval("this.analyzer."
							+ func + "(expected[0],expected)"
							+ prop);
					}
					if (delivered.length == 1) {
						delivered_result = eval("this.analyzer."
							+ func + "(delivered[0],delivered)"
							+ prop);
					}
				} else {
					/* Possible change: run this once only per exercise? */
					expected_result = eval("this.analyzer."
						+ func + "(expected)" + prop);
					delivered_result = eval("this.analyzer."
						+ func + "(delivered)" + prop);
				}
				// console.log(expected_result, delivered_result);
				if (expected_result != delivered_result) return false;
			}
			return true;
		},
		analysisPcsMatch: function(expected, delivered, analysis_types) {
			/* first two parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			if (!delivered || delivered == null || delivered.length < 1) {
				result.state = PARTIAL;
				return result;
			}


			/* Checks pitch classes */
			var pc_mistake = false;
			var expected_pcs = expected.map( function(midi) {return midi % 12} );
			var i, len;
			for (i = 0, len = delivered.length; i < len; i++) {
				var midi = delivered[i];

				if (expected_pcs.indexOf(midi % 12) !== -1) {
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				} else {
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
					pc_mistake = true;
				}
			}

			var analysisBool = this.analysisBool(expected, delivered, analysis_types);
			var lengthBool = delivered.length >= expected.length;

			result.state = (pc_mistake ? INCORRECT
				: (analysisBool ? (lengthBool ? CORRECT : PARTIAL) : PARTIAL));

			return result;
		},
		analysisMatch: function(expected, delivered, analysis_types) {
			/* first two parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			if (!delivered || delivered == null || delivered.length < 1) {
				result.state = PARTIAL;
				return result;
			}


			var analysisBool = this.analysisBool(expected, delivered, analysis_types);

			if (analysisBool) {
				for (i = 0, len = delivered.length; i < len; i++) {
					var midi = delivered[i];
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				}
			} else {
				for (i = 0, len = delivered.length; i < len; i++) {
					var midi = delivered[i];
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
				}
			}

			var lengthBool = delivered.length >= expected.length;

			result.state = (analysisBool ? (lengthBool ? CORRECT : PARTIAL) : PARTIAL);

			return result;
		},
		figuredBassPcsMatch: function(expected, delivered, abbreviated) {
			/* first two parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			if (!delivered || delivered == null || delivered.length < 1) {
				result.state = PARTIAL;
				return result;
			}


			var wrong_bass = false;
			if (delivered.length >= 1 & expected.length >= 1) {

				let bass_midi = delivered.sort()[0]; // sort should be redundant
				let target = expected.sort()[0]; // sort should be redundant

				if (bass_midi != target) {
					result.note[bass_midi] = INCORRECT;
					result.count[INCORRECT].push(bass_midi);
					wrong_bass = true;
				} else {
					result.note[bass_midi] = CORRECT;
					result.count[CORRECT].push(bass_midi);
				}
			}

			var fig_type = (abbreviated ? "abbrev_thoroughbass" : "full_thoroughbass");
			var analysisBool = (wrong_bass ? false
				: this.analysisBool(expected, delivered, [fig_type])
				);

			/* Checks pitch classes */
			var pc_mistake = false;
			var expected_pcs = expected.map( function(midi) {return midi % 12} );
			var i, len;
			for (i = 0, len = delivered.length; i < len; i++) {
				if (i == 0) continue; // bass assessed already

				var midi = delivered[i];

				if (expected_pcs.indexOf(midi % 12) !== -1) {
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				} else {
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
					pc_mistake = true;
				}
			}

			var lengthBool = delivered.length >= expected.length;

			result.state = (pc_mistake ? INCORRECT
				: (analysisBool ? (lengthBool ? CORRECT : PARTIAL) : PARTIAL));

			return result;
		},
		figuredBassMatch: function(expected, delivered, abbreviated) {
			/* first two parameters are arrays of midi numbers */

			var result = {
				state: null,
				count: { correct: [], incorrect: [] }, // poorly named
				note: {},
				notes: delivered,
			};

			if (!delivered || delivered == null || delivered.length < 1) {
				result.state = PARTIAL;
				return result;
			}


			var wrong_bass = false;
			if (delivered.length >= 1 & expected.length >= 1) {

				let bass_midi = delivered.sort()[0]; // sort should be redundant
				let target = expected.sort()[0]; // sort should be redundant

				if (bass_midi != target) {
					result.note[bass_midi] = INCORRECT;
					result.count[INCORRECT].push(bass_midi);
					wrong_bass = true;
				} else {
					result.note[bass_midi] = CORRECT;
					result.count[CORRECT].push(bass_midi);
				}
			}

			var fig_type = (abbreviated ? "abbrev_thoroughbass" : "full_thoroughbass");
			var analysisBool = (wrong_bass ? false
				: this.analysisBool(expected, delivered, [fig_type])
				);

			if (analysisBool) {
				for (i = 0, len = delivered.length; i < len; i++) {
					if (i == 0) continue; // bass assessed already

					var midi = delivered[i];
					result.note[midi] = CORRECT;
					result.count[CORRECT].push(midi);
				}
			} else {
				for (i = 0, len = delivered.length; i < len; i++) {
					if (i == 0) continue; // bass assessed already

					var midi = delivered[i];
					result.note[midi] = INCORRECT;
					result.count[INCORRECT].push(midi);
				}
			}

			var lengthBool = delivered.length >= expected.length;

			result.state = (analysisBool ? (lengthBool ? CORRECT : PARTIAL) : PARTIAL);

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
