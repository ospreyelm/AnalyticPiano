define([
  "lodash",
  "app/config",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/models/key_signature",
  "tonal",
], function (_, Config, ScoreTimeline, Analyze, KeySignature, Tonal) {
  var ANALYSIS_SETTINGS = Config.get("general.analysisSettings");
  var HIGHLIGHT_SETTINGS = Config.get("general.highlightSettings");
  var STAFF_DISTRIBUTION = Config.get("general.staffDistribution");
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;

  /**
   * ExerciseDefinition object is responsible for knowing the definition
   * or description of an exercise.
   *
   * @param settings {object}
   * @param settings.definition {object}
   * @constructor
   */
  var ExerciseDefinition = function (settings) {
    this.settings = settings || {};

    if (!("definition" in this.settings)) {
      throw new Error("missing settings.definition");
    }

    this.exercise = this.parse(this.settings.definition);
  };

  /**
   * Defines the possible exercise types.
   */
  ExerciseDefinition.TYPES = {
    matching: "matching",
    analytical: "analytical",
    analytical_pcs: "analytical_pcs",
    figured_bass: "figured_bass",
    figured_bass_pcs: "figured_bass_pcs",
    chorale: "chorale",
    chorale_identification: "chorale_identification",
    identification: "identification",
  };

  function normalizeAnalysisLabel(label) {
    if (label === null || label === undefined) {
      return "";
    }
    var result = String(label).trim();
    // Remove trailing/leading punctuation that shouldn't be in chord labels
    result = result.replace(/^[\s,;:\-()]+|[\s,;:\-()]+$/g, '');
    return result;
  }

  // Token map for converting abbreviated figured bass codes to display symbols
  var FIGURE_TOKEN_MAP = {
    "z": "6",
    "z4": "6/4",
    "Cz4": "b6/4",
    "z5": "6/5",
    "u": "7",
    "u3": "6/5",
    "u5": "7/5",
    "r": "4",
    "r2": "4/2",
    "r3": "4/3",
    "i3": "3",
    "q e": "13",
  };

  function expandFiguredBassToken(abbrev) {
    // Try exact match first, then try partial matches
    if (FIGURE_TOKEN_MAP[abbrev]) {
      return FIGURE_TOKEN_MAP[abbrev];
    }
    // Check if it starts with a token key
    for (var key in FIGURE_TOKEN_MAP) {
      if (FIGURE_TOKEN_MAP.hasOwnProperty(key) && abbrev.indexOf(key) === 0) {
        return FIGURE_TOKEN_MAP[key];
      }
    }
    return abbrev; // return unchanged if no match
  }

  function midiEventToTonalName(event) {
    var alterStr = "";
    if (event.alter > 0) {
      alterStr = new Array(event.alter + 1).join("#");
    } else if (event.alter < 0) {
      alterStr = new Array(-event.alter + 1).join("b");
    }
    var octave = Math.floor(event.midi / 12) - 1;
    return event.step.toUpperCase() + alterStr + octave;
    // e.g. { step: "F", alter: 1, midi: 66 } -> "F#4"
  }

  function tonalIntervalToHarmonyLabFormat(itvl) {
    // Tonal returns number-first: "3m", "5P", "4A". HarmonyLab uses quality-first: "m3", "P5", "A4".
    var num = String(Tonal.Interval.num(itvl));
    var quality = Tonal.Interval.quality(itvl);
    return quality + num;
  }

  function computeIntervalViaTonal(lowerEvent, upperEvent, analysisType, compoundIntervals) {
    if (!lowerEvent || !upperEvent) return "";
    try {
      var lowerName = midiEventToTonalName(lowerEvent);
      var upperName = midiEventToTonalName(upperEvent);
      var raw = Tonal.Interval.distance(lowerName, upperName);
      if (!raw) return "";
      var itvl = compoundIntervals ? raw : Tonal.Interval.simplify(raw);
      if (analysisType === "interval_generic") {
        return String(Math.abs(Tonal.Interval.num(itvl)));
      }
      return tonalIntervalToHarmonyLabFormat(itvl);
    } catch (_err) {
      return "";
    }
  }

  function stripFiguredBassTokens(label) {
    // For Roman numeral labels, expand {z}, {u}, etc. to their figured bass equivalents
    // e.g., "V{z}" becomes "V6", "I{z4}" becomes "I6/4"
    if (!label) return label;
    var result = String(label);
    // Replace {token} patterns with their expanded forms
    result = result.replace(/\{([A-Za-z0-9]+)\}/g, function (match, token) {
      return FIGURE_TOKEN_MAP[token] || '';
    });
    return result.trim();
  }

  function isPitchAnalysisType(analysisType) {
    return [
      "note_name",
      "solfege",
      "do_based_solfege",
      "scale_degree",
      "fixed_do",
      "pitch_class",
    ].indexOf(analysisType) !== -1;
  }

  function computeWindowLabel(midiStack, analysisType, analyzer, compoundIntervals, windowEvents) {
    if (!midiStack || !midiStack.length || !analyzer) {
      return "";
    }
    try {
      if (isPitchAnalysisType(analysisType)) {
        if (midiStack.length !== 1) {
          console.warn("[chorale_identification] expected a single MIDI note for pitch analysis type", analysisType, "but got", midiStack);
          return "";
        }

        var midi = midiStack[0];
        if (analysisType === "note_name") {
          return normalizeAnalysisLabel(analyzer.to_note_name([midi]));
        }
        if (analysisType === "solfege") {
          return normalizeAnalysisLabel(analyzer.to_solfege([midi]));
        }
        if (analysisType === "do_based_solfege") {
          return normalizeAnalysisLabel(analyzer.to_do_based_solfege([midi]));
        }
        if (analysisType === "scale_degree") {
          return normalizeAnalysisLabel(analyzer.to_scale_degree([midi]));
        }
        if (analysisType === "fixed_do") {
          return normalizeAnalysisLabel(analyzer.to_fixed_do([midi]));
        }
        if (analysisType === "pitch_class") {
          return analyzer.to_pitch_class([midi]).toString();
        }
      }

      if (midiStack.length < 2) {
        return "";
      }

      if (analysisType === "interval_generic" || analysisType === "interval_specific") {
        var lowerMidi = midiStack[0];
        var upperMidi = midiStack[midiStack.length - 1];
        // Find matching events for lower and upper notes (by midi value)
        var lowerEvent = _.find(windowEvents || [], function (e) { return e.midi === lowerMidi; });
        var upperEvent = _.find(windowEvents || [], function (e) { return e.midi === upperMidi; });

        // analyze.js path
        var analyzeLabel = "";
        try {
          var result = analyzer.to_interval([lowerMidi, upperMidi]);
          if (result && result.name) {
            analyzeLabel = analysisType === "interval_generic" ? result.size : result.name;
            analyzeLabel = normalizeAnalysisLabel(analyzeLabel);
          }
        } catch (_e) { analyzeLabel = ""; }

        // Tonal.js path (authoritative)
        var tonalLabel = computeIntervalViaTonal(lowerEvent, upperEvent, analysisType, compoundIntervals);
        tonalLabel = normalizeAnalysisLabel(tonalLabel);

        if (analyzeLabel && analyzeLabel !== tonalLabel) {
          console.warn("[interval] analyze/tonal mismatch:", analyzeLabel, "vs", tonalLabel, "midi:", lowerMidi, upperMidi);
        }
        return tonalLabel || analyzeLabel;
      }
      if (analysisType === "figured_bass") {
        var abbrevFigure = analyzer.abbrev_thoroughbass_figure(midiStack);
        // Root-position triads conventionally have no figure (""),
        // but identification exercises need an explicit label — use the full figure.
        if (!abbrevFigure) {
          abbrevFigure = analyzer.full_thoroughbass_figure_minus_octave
            ? analyzer.full_thoroughbass_figure_minus_octave(midiStack)
            : "5/3";
        }
        var expanded = expandFiguredBassToken(abbrevFigure);
        return normalizeAnalysisLabel(expanded);
      }
      var chord = analyzer.to_chord(midiStack, "roman only");
      if (chord && chord.label) {
        // Strip any embedded tokens from Roman numeral labels
        var cleanLabel = stripFiguredBassTokens(chord.label);
        return normalizeAnalysisLabel(cleanLabel);
      }
      return normalizeAnalysisLabel(chord);
    } catch (_err) {
      return "";
    }
  }

  function buildAnalysisWindows(timeline) {
    var grouped = [];
    var onsetIndex = Object.create(null);
    var activeNotes = [];

    _.each(timeline || [], function (ev) {
      if (!Object.prototype.hasOwnProperty.call(onsetIndex, ev.onset)) {
        onsetIndex[ev.onset] = {
          onset: ev.onset,
          events: [],
        };
        grouped.push(onsetIndex[ev.onset]);
      }
      onsetIndex[ev.onset].events.push(ev);
    });

    grouped.sort(function (a, b) {
      return a.onset - b.onset;
    });

    _.each(grouped, function (window) {
      activeNotes = _.filter(activeNotes, function (n) {
        return n.end > window.onset;
      });
      _.each(window.events, function (ev) {
        activeNotes.push({ midi: ev.midi, end: ev.onset + ev.duration });
      });
      var midiMap = Object.create(null);
      _.each(activeNotes, function (n) {
        midiMap[n.midi] = true;
      });
      window.midiStack = _.sortBy(
        _.map(Object.keys(midiMap), function (k) {
          return parseInt(k, 10);
        }),
        function (m) { return m; }
      );
    });

    return grouped;
  }

  function buildChoices(correctLabel, allLabels, analysisType, compoundIntervals) {
    var pool = _.uniq(_.filter(allLabels, function (l) {
      return !!l && l !== correctLabel;
    }));
    var fallbacks = analysisType === "figured_bass"
      ? ["5/3", "6", "6/4", "6/5", "7"]
      : analysisType === "note_name"
      ? ["C", "D", "E", "F", "G", "A", "B"]
      : (analysisType === "solfege" || analysisType === "do_based_solfege" || analysisType === "fixed_do")
      ? ["Do", "Re", "Mi", "Fa", "So", "La", "Ti"]
      : analysisType === "scale_degree"
      ? ["1", "2", "3", "4", "5", "6", "7"]
      : analysisType === "pitch_class"
      ? ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
      : analysisType === "interval_generic"
      ? (compoundIntervals
        ? ["2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15"]
        : ["2", "3", "4", "5", "6", "7", "8"])
      : analysisType === "interval_specific"
      ? (compoundIntervals
        ? ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8", "m9", "M9", "m10", "M10", "P11", "P12", "m13", "M13", "m14", "M14"]
        : ["m2", "M2", "m3", "M3", "P4", "P5", "m6", "M6", "m7", "M7", "P8"])
      : ["I", "ii", "IV", "V", "vi", "I6/4", "i6/4", "V6/4", "Cad6/4", "Cadb6/4"];
    _.each(fallbacks, function (item) {
      if (item !== correctLabel && pool.indexOf(item) === -1) {
        pool.push(item);
      }
    });
    var distractors = _.shuffle(pool).slice(0, 4);
    var choices = _.shuffle([correctLabel].concat(distractors));
    while (choices.length < 5) {
      choices.push(correctLabel);
    }
    return choices.slice(0, 5);
  }

  function buildChoraleIdentificationProblems(exercise) {
    var score = exercise.score || {};
    var timeline = ScoreTimeline && ScoreTimeline.buildTimeline
      ? ScoreTimeline.buildTimeline(score)
      : [];
    var windows = buildAnalysisWindows(timeline);
    if (!windows.length) {
      return [];
    }

    var hlKey = exercise.key;
    var keySignature = new KeySignature(hlKey, exercise.keySignature);
    var analyzer = new Analyze(keySignature);
    var analysisType = exercise.analysisType || "roman";
    var compoundIntervals = exercise.compoundIntervals || false;

    var labels = _.map(windows, function (window) {
      return computeWindowLabel(window.midiStack, analysisType, analyzer, compoundIntervals, window.events);
    });

    var problems = [];
    _.each(windows, function (window, idx) {
      var answer = labels[idx] || "";
      var measureIndex = window.events && window.events.length ? window.events[0].measureIndex : 0;
      
      problems.push({
        windowIndex: idx,
        measureIndex: measureIndex,
        onset: window.onset,
        answer: answer,
        choices: buildChoices(answer, labels, analysisType, compoundIntervals),
        hidden: (answer === "") // Mark as hidden if no harmonic answer
      });
    });

    return problems;
  }

  /**
   * Converts a CIR-style key (e.g., "F", "Fm", "Bb", "C#m") to HarmonyLab key format (e.g., "jF_", "iF_", "jBb", "iC#").
   *
   * @param {string} cirKey - Key in CIR format
   * @return {string} Key in HarmonyLab format
   */
  function convertCIRKeyToHarmonyLabKey(cirKey) {
    if (!cirKey || typeof cirKey !== 'string') {
      return 'jC_'; // default to C major
    }
    
    // Check if minor (ends with 'm')
    var isMinor = cirKey.endsWith('m');
    var prefix = isMinor ? 'i' : 'j';
    var note = isMinor ? cirKey.slice(0, -1) : cirKey;
    
    // Add underscore suffix for naturals (no accidentals)
    var suffix = (note.indexOf('#') === -1 && note.indexOf('b') === -1) ? '_' : '';
    
    return prefix + note + suffix;
  }

  _.extend(ExerciseDefinition.prototype, {
    /**
     * Returns true if the exercise has introductory text, false otherwies.
     *
     * @return {boolean}
     */
    hasIntro: function () {
      return this.exercise.introText !== false;
    },
    /**
     * Returns true if the exercise has review text, false otherwise.
     *
     * @return {boolean}
     */
    hasReview: function () {
      return this.exercise.reviewText !== false;
    },
    /**
     * Returns true if the exercise has any problems attached.
     *
     * @return {boolean}
     */
    hasProblems: function () {
      return this.exercise.problems.length > 0;
    },
    /**
     * Returns the exercise description or instructions.
     *
     * @return {string}
     */
    getExerciseText: function () {
      var text = this.exercise.introText || "";
      if (typeof this.isChoraleIdentification === "function" && this.isChoraleIdentification() && text.indexOf("Provide the") > -1) {
          text = "Click on the highlighted <strong>?</strong> buttons beneath the score to select the correct harmonic analysis.";
      }
      return text;
    },
    /**
     * Returns the key for the exercise (i.e. C major, A minor, etc).
     * The format of the key string should be consistent with the
     * KeySignature model.
     *
     * @return {string}
     */
    getKey: function () {
      return this.exercise.key;
    },
    /**
     * Returns the key signature for the exercise.
     *
     * The format of the key signature string should be consistent with the
     * KeySignature model.
     *
     * @return {string}
     */
    getKeySignature: function () {
      return this.exercise.keySignature;
    },
    /**
     * Returns the review text.
     *
     * @return {string}
     */
    getReview: function () {
      return this.exercise.reviewText;
    },
    /**
     * Returns the URL to the next exercise.
     *
     * @return {string}
     */
    getNextExercise: function () {
      return this.exercise.nextExercise;
    },
    /*
     * Returns the list of exercises in the set.
     *
     * @return {array}
     */
    getExerciseList: function () {
      return this.exercise.exerciseList.slice(0);
    },
    /**
     * Returns the analysis settings.
     *
     * @return {object}
     */
    getAnalysisSettings: function () {
      return this.exercise.analysis;
    },
    /**
     * Returns the highlight settings.
     *
     * @return {object}
     */
    getHighlightSettings: function () {
      return this.exercise.highlight;
    },
    /**
     * Returns the staff distribution settings.
     *
     * @return {object}
     */
    getStaffDistribution: function () {
      return this.exercise.staffDistribution;
    },
    /**
     * Returns the exercise type.
     *
     * @return {string}
     */
    getType: function () {
      return this.exercise.type;
    },
    /**
     * Returns true if this is a chorale exercise.
     *
     * @return {boolean}
     */
    isChorale: function () {
      return this.exercise.type === "chorale";
    },
    /**
     * Returns true if this is a chorale identification exercise.
     *
     * @return {boolean}
     */
    isChoraleIdentification: function () {
      return this.exercise.type === "chorale_identification";
    },
    /**
     * Returns true if this is an identification exercise.
     *
     * @return {boolean}
     */
    isIdentification: function () {
      return this.exercise.type === "identification";
    },
    /**
     * Returns the feedback mode for identification exercises.
     * "submit"   — student picks all, presses Submit, then sees results (default)
     * "practice" — correct/incorrect shown immediately after each selection
     * "test"     — answers locked after choosing, no feedback ever shown
     *
     * @return {string}
     */
    getIdentMode: function () {
      return this.exercise.identMode || "submit";
    },
    /**
     * Returns the analysis type for identification exercises
     * (e.g. "roman", "figured_bass", "interval_specific").
     *
     * @return {string}
     */
    getAnalysisType: function () {
      return this.exercise.analysisType || "roman";
    },
    /**
     * Returns the score for chorale exercises.
     *
     * @return {object}
     */
    getScore: function () {
      return this.exercise.score || {};
    },
    /**
     * Returns the mode for chorale exercises (e.g., "play-all-voices").
     *
     * @return {string}
     */
    getMode: function () {
      return this.exercise.mode || "play-all-voices";
    },
    /**
     * Returns display settings for chorale exercises.
     *
     * @return {object}
     */
    getDisplay: function () {
      return this.exercise.display || {};
    },
    /**
     * Returns grading settings for chorale exercises.
     *
     * @return {object}
     */
    getGrading: function () {
      return this.exercise.grading || {};
    },
    /**
     * Returns the time signature setting.
     *
     * @return {string}
     */
    getTimeSignature: function () {
      return this.exercise.timeSignature;
    },
    /**
     * Returns the semibreves per line setting.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.exercise.semibrevesPerLine;
    },
    /**
     * Returns all the problems.
     *
     * @return {array}
     */
    getProblems: function () {
      return this.exercise.problems;
    },
    /**
     * Returns the number of problems.
     *
     * @return {number}
     */
    getNumProblems: function () {
      return this.exercise.problems.length;
    },
    /**
     * Returns the given problem at an index.
     *
     * @return {object}
     */
    getProblemAt: function (index) {
      var num_problems = this.exercise.problems;
      if (index < 0 || index >= num_problems) {
        throw new Error("invalid problem index: " + index);
      } else if (!this.exercise.problems[index]) {
        throw new Error("problem doesn not exist at index: " + index);
      }
      return this.exercise.problems[index];
    },
    /**
     * Parses an exercise definition and performs sanity checking
     * and basic validation.
     *
     * @param {object} definition
     * @return {object} the parsed definition
     */
    parse: function (definition) {
      var exercise = {};
      var problems = [];

      // Special handling for chorale exercises
      if (definition.type === "chorale") {
        exercise.type = "chorale";
        exercise.score = definition.score || {};
        exercise.mode = definition.mode || "play-all-voices";
        exercise.targetVoices = definition.targetVoices || "all";
        exercise.display = definition.display || {};
        // Allow editor to choose analysis renderer for chorales
        // Values: 'notater' (default, maximum reuse), 'adapter', 'none'
        if (!exercise.display.hasOwnProperty('analysisRenderer')) {
          exercise.display.analysisRenderer = 'notater';
        }
        exercise.grading = definition.grading || {};
        exercise.excerpt = definition.excerpt || {};
        // Use default analysis settings (from ANALYSIS_SETTINGS) for chorale overlays
        exercise.analysis = _.cloneDeep(ANALYSIS_SETTINGS);
        // Allow explicit overrides from the incoming definition
        if (definition.hasOwnProperty("analysis") && definition.analysis) {
          Object.assign(exercise.analysis, definition.analysis);
        }
        
        // Convert CIR key format to HarmonyLab key format
        var cirKey = (definition.score && definition.score.meta && definition.score.meta.key) || definition.key || "C";
        exercise.key = convertCIRKeyToHarmonyLabKey(cirKey);
        // Don't set keySignature - let KeySignature model derive it from key
        exercise.keySignature = false;
        
        exercise.introText = definition.introText || false;
        exercise.reviewText = definition.reviewText || false;
        exercise.problems = []; // Chorales don't use the chord-based problem structure
        exercise.exerciseList = []; // Chorales are standalone, not part of a list
        exercise.nextExercise = definition.nextExercise || false;
        exercise.staffDistribution = definition.staffDistribution || "chorale";
        exercise.semibrevesPerLine = definition.semibrevesPerLine || 4;
        return exercise;
      }

      if (definition.type === "chorale_identification") {
        exercise.type = "chorale_identification";
        exercise.score = definition.score || {};
        exercise.analysisType = definition.analysisType || "roman";
        exercise.compoundIntervals = definition.compoundIntervals || false;
        exercise.identMode = definition.identMode || "submit";
        exercise.display = definition.display || {};

        var choraleIdentCIRKey =
          (definition.score && definition.score.meta && definition.score.meta.key) ||
          definition.key ||
          "C";
        exercise.key = convertCIRKeyToHarmonyLabKey(definition.key || choraleIdentCIRKey);
        exercise.keySignature = false;

        exercise.introText = definition.introText || false;
        exercise.reviewText = definition.reviewText || false;
        exercise.nextExercise = definition.nextExercise || false;
        exercise.exerciseList = definition.exerciseList || [];
        exercise.staffDistribution = definition.staffDistribution || "chorale";
        exercise.semibrevesPerLine = definition.semibrevesPerLine || 4;

        exercise.analysis = _.cloneDeep(ANALYSIS_SETTINGS);
        if (exercise.analysis && exercise.analysis.mode) {
          for (var modeKey in exercise.analysis.mode) {
            if (exercise.analysis.mode.hasOwnProperty(modeKey)) {
              exercise.analysis.mode[modeKey] = false;
            }
          }
        }
        exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
        exercise.problems = buildChoraleIdentificationProblems(exercise);

        return exercise;
      }

      // check for a chord entry which may be an array of note numbers
      // to represent one chord, or an array of arrays to represent
      // chord sequence
      if (definition.hasOwnProperty("chord")) {
        if (_.isArray(definition.chord)) {
          if (_.isArray(definition.chord[0])) {
            problems = definition.chord;
          } else if (_.isObject(definition.chord[0])) {
            problems = definition.chord;
          } else {
            problems = [definition.chord];
          }
        } else {
          throw new Error("definition.problems must be an array");
        }
      }

      // check that the problem type is supported
      if (
        definition.hasOwnProperty("type") &&
        definition.type in ExerciseDefinition.TYPES
      ) {
        exercise.type = definition.type;
      } else {
        throw new Error("invalid definition.type: " + definition.type);
      }

      // normalize the internal representation of each chord in the
      // set of problems to have VISIBLE/HIDDEN parts
      problems = _.map(problems, function (chord, index) {
        // var normalized = {"visible":[], "hidden":[],"notes":[]};
        var normalized = { visible: [], hidden: [], notes: [], unison_idx: null, rhythm: null };

        if (_.isArray(chord)) {
          normalized.visible = chord;
          console.log('chord received as simple array by ExerciseDefinition.parse')
        } else if (_.isObject(chord)) {
          if (exercise.type === "identification") {
            var rawNotes = chord.notes || [];
            if (chord.visible) rawNotes = rawNotes.concat(chord.visible);
            if (chord.hidden) rawNotes = rawNotes.concat(chord.hidden);
            normalized.visible = ExerciseDefinition.sortNotes(rawNotes);
            normalized.hidden = [];
          } else {
            if (
              !chord.hasOwnProperty("visible") ||
              !chord.hasOwnProperty("hidden")
            ) {
              throw new Error(
                "invalid chord at index: " +
                  index +
                  "; chord must have 'visible' and 'hidden' properties"
              );
            }
            normalized.visible = ExerciseDefinition.sortNotes(chord.visible);
            normalized.hidden = ExerciseDefinition.sortNotes(chord.hidden);
          }
        } else {
          throw new Error("invalid chord at index: " + index);
        }

        // sum of the visible and hidden notes
        normalized.notes = ExerciseDefinition.sortNotes(
          ExerciseDefinition.getNotesForProblem(
            normalized.visible,
            normalized.hidden
          )
        );

        if (["analytical", "analytical_pcs"].includes(exercise.type)) {
          normalized.visible = [];
          normalized.hidden = normalized.notes;
        } else if (
          ["figured_bass", "figured_bass_pcs"].includes(exercise.type)
        ) {
          normalized.visible = normalized.notes.slice(0, 1);
          normalized.hidden = normalized.notes.slice(1);
        } else if (exercise.type === "identification") {
          normalized.visible = normalized.notes.slice();
          normalized.hidden = [];
          if (_.isObject(chord)) {
            normalized.answer = chord.answer || "";
            normalized.choices = chord.choices || [];
          }
        }

        if (chord.hasOwnProperty("rhythmValue")) {
          normalized.rhythm = chord.rhythmValue;
        }

        if (chord.hasOwnProperty("unison_idx")) {
          normalized.unison_idx = chord.unison_idx
        }

        return normalized;
      });

      exercise.problems = problems;

      // check for the "key" entry to use for the problem set
      exercise.key = "h"; // means "no key"
      if (definition.hasOwnProperty("key")) {
        exercise.key = definition.key;
      }

      // check for the "keySignature" entry
      exercise.keySignature = false;
      if (definition.hasOwnProperty("keySignature")) {
        exercise.keySignature = definition.keySignature;
      }

      // check for the introductory text
      exercise.introText = false;
      if (definition.hasOwnProperty("introText")) {
        exercise.introText = definition.introText;
      }

      // check for the review text
      exercise.reviewText = false;
      if (definition.hasOwnProperty("reviewText")) {
        exercise.reviewText = definition.reviewText;
      }

      // check for the next exercise
      exercise.nextExercise = false;
      if (
        definition.hasOwnProperty("nextExercise") &&
        definition.nextExercise
      ) {
        exercise.nextExercise = definition.nextExercise;
      }

      // check for the exercise list
      exercise.exerciseList = [];
      if (
        definition.hasOwnProperty("exerciseList") &&
        definition.exerciseList
      ) {
        exercise.exerciseList = definition.exerciseList.slice(0);
      }

      exercise.analysis = _.cloneDeep(ANALYSIS_SETTINGS);
      if (definition.hasOwnProperty("analysis") && definition.analysis) {
        Object.assign(exercise.analysis, definition.analysis);
      }
      // Force all analysis overlays off for identification — must run after the
      // Object.assign above so a definition-level "analysis" key can't re-enable them.
      if (exercise.type === "identification") {
        for (var modeKey in exercise.analysis.mode) {
          if (exercise.analysis.mode.hasOwnProperty(modeKey)) {
            exercise.analysis.mode[modeKey] = false;
          }
        }
        exercise.identMode = definition.identMode || "submit";
      }

      exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
      if (definition.hasOwnProperty("highlight") && definition.highlight) {
        Object.assign(exercise.highlight, definition.highlight);
      }

      exercise.staffDistribution = STAFF_DISTRIBUTION;
      if (
        definition.hasOwnProperty("staffDistribution") &&
        definition.staffDistribution
      ) {
        exercise.staffDistribution = definition.staffDistribution;
      }

      exercise.timeSignature = false;
      if (definition.hasOwnProperty("timeSignature")) {
        exercise.timeSignature = definition.timeSignature;
      }

      exercise.semibrevesPerLine = CHORD_BANK_SIZE;
      if (definition.hasOwnProperty("semibrevesPerLine")) {
        exercise.semibrevesPerLine = definition.semibrevesPerLine;
      }

      exercise.performing_course = definition.courseId;

      return exercise;
    },
    /**
     * Utility function to assert that a given set of keys are
     * present, otherwise throw an exception.
     *
     * @param {array} valid_keys The valid key names to check
     * @param {array} actual_keys The actual key names to check
     * @param {string} msg The prefix for the exception message
     * @return undefined
     */
    assertHasKeys: function (valid_keys, actual_keys, msg) {
      var i,
        len,
        map = {};
      msg = msg || "invalid key: ";

      for (i = 0, len = valid_keys.length; i < len; i++) {
        map[valid_keys[i]] = true;
      }

      for (i = 0, len = actual_keys.length; i < len; i++) {
        if (!map[actual_keys[i]]) {
          throw new Error(msg + actual_keys[i]);
        }
      }
    },
  });

  /**
   * Returns a complete list of the notes that is the sum of the
   * visible and hidden parts.
   *
   * @param {array} visible the visible note numbers
   * @param {array} hidden the hidden note numbers
   * @return {array} the set of unique notes from the visible and hidden parts
   */
  ExerciseDefinition.getNotesForProblem = function (visible, hidden) {
    var note,
      notes = [],
      map = {};

    for (var i = 0, len = visible.length; i < len; i++) {
      note = visible[i];
      if (!map.hasOwnProperty(note)) {
        map[note] = 1;
        notes.push(note);
      }
    }

    for (var i = 0, len = hidden.length; i < len; i++) {
      note = hidden[i];
      if (!map.hasOwnProperty(note)) {
        map[note] = 1;
        notes.push(note);
      }
    }

    return notes;
  };

  /**
   * Returns a sorted copy of the notes. Expects
   * an array of note numbers.
   *
   * @param {array} notes
   * @return {array} of sorted notes
   */
  ExerciseDefinition.sortNotes = function (notes) {
    var copy = notes.slice();
    copy.sort(function (a, b) {
      return a - b;
    });
    return copy;
  };

  return ExerciseDefinition;
});
