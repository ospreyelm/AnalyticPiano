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


  function applySkillFilter(problems, skillTags, analysisType, explicitAllowedAnswers) {
    // Targeting is applied server-side via is_target on each analysis slice.
    // explicitAllowedAnswers (from analysisPolicy.allowedValues) is used only
    // to populate dropdown choices, not to hide slots.
    // This function is now a pass-through — slot visibility is already resolved.
    if (explicitAllowedAnswers && explicitAllowedAnswers.length > 0) {
      return _.map(problems, function (p) {
        if (p.hidden) return p;
        if (explicitAllowedAnswers.indexOf(p.answer) === -1) {
          p = _.clone(p);
          p.hidden = true;
        }
        return p;
      });
    }
    return problems;
  }

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
    musicxml: "musicxml",
  };

  function normalizeAnalysisLabel(label) {
    if (label === null || label === undefined) {
      return "";
    }
    var result = String(label).trim();
    // Normalize musical symbols to standard characters
    result = result.replace(/♭/g, "b").replace(/♯/g, "#");
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

  function computeNoteNameFromEvent(ev) {
    if (!ev) return "";
    var name = ev.step.toUpperCase();
    if (ev.alter === 1) name += "#";
    else if (ev.alter === -1) name += "b";
    else if (ev.alter === 2) name += "##";
    else if (ev.alter === -2) name += "bb";
    return name;
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
          // Priority: If we have a single event in the window, use its original spelling (step/alter)
          // This prevents enharmonic errors like Bb being called A#.
          if (windowEvents && windowEvents.length === 1) {
              return normalizeAnalysisLabel(computeNoteNameFromEvent(windowEvents[0]));
          }
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
        // Root-position triads use "5/3" as both stored and display value.
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
      // Some analyzer paths may return a rich object with no `.label`.
      // Never stringify arbitrary objects into "[object Object]" labels.
      if (typeof chord === "string") {
        return normalizeAnalysisLabel(chord);
      }
      return "";
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
      ? ["5/3", "6", "6/4", "7", "6/5", "4/3", "4/2"]
      : analysisType === "figured_bass_unabbreviated"
      ? ["8/5/3", "6/3", "6/4", "7/5/3", "6/5/3", "6/4/3", "6/4/2"]
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
    if (pool.length < 4) {
      _.each(fallbacks, function (item) {
        if (item !== correctLabel && pool.indexOf(item) === -1) {
          pool.push(item);
        }
      });
    }
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
    var firstOnset = windows.length > 0 ? windows[0].onset : 0;
    
    _.each(windows, function (window, idx) {
      var answer = labels[idx] || "";
      var measureIndex = window.events && window.events.length ? window.events[0].measureIndex : 0;
      
      // ALIGNMENT FIX: Normalize onset relative to the first window of the exercise
      var relativeOnset = window.onset - firstOnset;

      problems.push({
        windowIndex: idx,
        measureIndex: measureIndex,
        onset: relativeOnset,
        answer: answer,
        choices: buildChoices(answer, labels, analysisType, compoundIntervals),
        hidden: (answer === "") // Mark as hidden if no harmonic answer
      });
    });

    return problems;
  }

  function buildUMTOIdentificationProblems(exercise) {
    const umto = exercise.score.umto;
    if (!umto) return [];

    const rawProblems = [];
    const analysisType = exercise.analysisType || "roman";
    const hlKey = exercise.key;
    const keySignature = new KeySignature(hlKey, exercise.keySignature);
    const analyzer = new Analyze(keySignature);
    const score = exercise.score || {};
    const timeline = ScoreTimeline && ScoreTimeline.buildTimeline
      ? ScoreTimeline.buildTimeline(score)
      : [];
    const windows = buildAnalysisWindows(timeline);

    function ticksToRhythm(ticks) {
      if (ticks >= 4096) return "w";
      if (ticks >= 2048) return "h";
      if (ticks >= 1024) return "q";
      if (ticks >= 512)  return "8";
      if (ticks >= 256)  return "16";
      return "32";
    }

    function getWindowMeta(sliceOffset, idx) {
      if (windows && windows[idx]) {
        var win = windows[idx];
        var firstEv = win.events && win.events.length ? win.events[0] : null;
        var maxDur = firstEv && typeof firstEv.duration === "number" ? firstEv.duration : 1024;
        _.each(win.events, function(ev) {
          if (typeof ev.duration === "number" && ev.duration > maxDur) maxDur = ev.duration;
        });
        return {
          measureIndex: firstEv && typeof firstEv.measureIndex === "number" ? firstEv.measureIndex : 0,
          onset: typeof win.onset === "number" ? win.onset : sliceOffset,
          rhythm: ticksToRhythm(maxDur),
          hasSlot: true,
        };
      }
      return {
        measureIndex: 0,
        onset: sliceOffset,
        rhythm: "q",
        hasSlot: false,
      };
    }

    // Map UMTO analysis slices to problems
    _.each(umto.analysis, function (slice, idx) {
      let answer = "";
      // Targeting is applied server-side; respect it if present, otherwise default to true
      let isTarget = typeof slice.is_target === "boolean" ? slice.is_target : true;

      // Find the vertical sonority for this slice to check for context notes
      const pitchesAtOffset = umto.voices.S.concat(umto.voices.A, umto.voices.T, umto.voices.B)
          .filter(e => Math.abs(e.offset - slice.offset) < 0.001);
      
      // If any sounding note at this offset is marked as NOT a target, 
      // we might want to hide this slice from identification.
      // For Unit 1 specifically, we look at the grading slice.
      const gradingMatch = umto.grading.find(g => Math.abs(g.offset - slice.offset) < 0.001);
      if (gradingMatch && gradingMatch.target_midi_pitches.length === 0) {
          isTarget = false;
      }

      // Use !== null/undefined checks (not truthiness) for figured bass fields.
      if (analysisType === "figured_bass_unabbreviated" && slice.content.raw_figured_bass != null) {
        answer = slice.content.raw_figured_bass;
      } else if (analysisType === "figured_bass" && slice.content.figured_bass != null) {
        answer = slice.content.figured_bass;
      } else if (slice.content.roman_numeral) {
        answer = stripFiguredBassTokens(slice.content.roman_numeral);
      } else if (slice.content.pop_symbol) {
        answer = slice.content.pop_symbol;
      } else if (slice.content.figured_bass != null) {
        answer = slice.content.figured_bass;
      } else if (slice.content.functional_label) {
        answer = slice.content.functional_label;
      }

      // Unit 1 Bridge: Note Names
      var isNoteNameEx = (exercise.analysisType === "note_name") || 
                         (umto.metadata && umto.metadata.complexity_score === 1) ||
                         (exercise.unit && (exercise.unit == 1 || exercise.unit == "1" || String(exercise.unit).indexOf("Unit 1") !== -1));
      
      if (!answer && isNoteNameEx) {
          if (gradingMatch && gradingMatch.target_midi_pitches.length > 0) {
              const midi = gradingMatch.target_midi_pitches[0];
              answer = analyzer.to_note_name([midi]);
              isTarget = true;  // grading pitch confirms this note IS a target
          } else {
              isTarget = false;
          }
      }

      // If the slice has all-null content, it was intentionally blanked (e.g. chord outside
      // the unit's curriculum). Don't derive an answer from pitches — mark non-target.
      var allContentNull = slice.content.roman_numeral === null &&
        slice.content.pop_symbol === null &&
        slice.content.figured_bass === null &&
        slice.content.raw_figured_bass === null &&
        slice.content.functional_label === null;
      if (!answer && allContentNull) {
        isTarget = false;
      }

      // Fallback for SATB UMTO imports where analysis slices are intentionally blank:
      // derive the expected label directly from grading pitch content.
      if (!answer && !allContentNull && gradingMatch && gradingMatch.target_midi_pitches && gradingMatch.target_midi_pitches.length > 0) {
        answer = computeWindowLabel(
          gradingMatch.target_midi_pitches,
          analysisType,
          analyzer,
          false,
          []
        ) || "";
      }
      
      console.log("[ID] Problem built:", idx, "offset:", slice.offset, "answer:", answer, "isTarget:", isTarget);

      var winMeta = getWindowMeta(slice.offset, idx);

      rawProblems.push({
        windowIndex: idx,
        measureIndex: winMeta.measureIndex,
        onset: winMeta.onset,
        answer: normalizeAnalysisLabel(answer),
        choices: [],
        hidden: !answer || !isTarget || !winMeta.hasSlot,
        visible: (gradingMatch && gradingMatch.target_midi_pitches) ? gradingMatch.target_midi_pitches : [],
        notes: pitchesAtOffset.map(p => p.midi),
        rhythm: winMeta.rhythm || "q"
      });
    });

    var allAnswers = [];
    var answerSeen = {};
    _.each(rawProblems, function (p) {
      var ans = p && p.answer ? p.answer : null;
      if (!ans) {
        return;
      }
      if (!answerSeen[ans]) {
        answerSeen[ans] = true;
        allAnswers.push(ans);
      }
    });
    var explicitAllowedAnswers = [];
    if (
      exercise.analysisPolicy &&
      _.isArray(exercise.analysisPolicy.allowedValues) &&
      exercise.analysisPolicy.allowedValues.length > 0
    ) {
      explicitAllowedAnswers = exercise.analysisPolicy.allowedValues;
    } else {
      explicitAllowedAnswers = exercise.allowed_answers || [];
    }

    return _.map(rawProblems, function (problem) {
      var next = _.assign({}, problem);
      if (explicitAllowedAnswers.length > 0 && next.answer) {
        next.choices = _.map(buildChoices(next.answer, explicitAllowedAnswers, analysisType, false), normalizeAnalysisLabel);
      } else if (next.answer) {
        next.choices = _.map(buildChoices(next.answer, allAnswers, analysisType, false), normalizeAnalysisLabel);
      } else {
        next.choices = [];
      }
      return next;
    });
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
    
    // Idempotency check: If it already looks like a HarmonyLab key (starts with i/j followed by A-G), return as is.
    if ((cirKey.startsWith('i') || cirKey.startsWith('j')) && cirKey.length >= 2 && /^[A-G]/.test(cirKey[1])) {
        return cirKey;
    }
    
    // Check if minor (ends with 'm' or is lowercase)
    var isMinor = cirKey.endsWith('m') || (cirKey.length > 0 && cirKey[0] === cirKey[0].toLowerCase());
    var prefix = isMinor ? 'i' : 'j';
    var note = isMinor && cirKey.endsWith('m') ? cirKey.slice(0, -1) : cirKey;
    
    // Capitalize note name and normalize accidental
    if (note.length > 0) {
        note = note[0].toUpperCase() + note.slice(1);
    }
    note = note.replace('-', 'b');
    
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
     * Returns true if this is a UMTO exercise.
     * @return {boolean}
     */
    isUMTO: function () {
      return this.exercise.isUMTO === true;
    },
    /**
     * Returns the complexity score (Unit level).
     * @return {number}
     */
    getComplexityScore: function () {
      var score = this.exercise.complexity_score;
      if (score === undefined && this.exercise.score && this.exercise.score.umto && this.exercise.score.umto.metadata) {
        score = this.exercise.score.umto.metadata.complexity_score;
      }
      return score || 0;
    },
    /**
     * Returns true if the exercise belongs to a specific unit.
     * @param {number|string} unitNum
     * @return {boolean}
     */
    isUnit: function (unitNum) {
      var tags = (this.exercise.skill_tags || []).concat(this.exercise.playlistTags || []);
      var searchTags = ["unit:" + unitNum, "Unit " + unitNum];
      return _.some(tags, function(t) {
        return searchTags.indexOf(t) !== -1;
      });
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
      if (typeof this.isChoraleIdentification === "function" && this.isChoraleIdentification()) {
        var at = this.exercise.analysisType || "roman";
        var instruction;
        if (at === "figured_bass" || at === "figured_bass_unabbreviated") {
          instruction = "Click on the highlighted <strong>?</strong> buttons beneath the score to select the correct figures.";
        } else {
          instruction = "Click on the highlighted <strong>?</strong> buttons beneath the score to select the correct harmonic analysis.";
        }
        // Extract "(BWV Rxx, mm. xx-xx)" from source string and prepend
        var bwvMatch = text.match(/\(BWV[^)]+\)/);
        text = bwvMatch ? bwvMatch[0] + " &mdash; " + instruction : instruction;
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
     * Returns the explicit interaction mode if defined.
     * @return {string|null}
     */
    getMode: function () {
      return this.exercise.mode || (this.exercise.score && this.exercise.score.umto && this.exercise.score.umto.metadata && this.exercise.score.umto.metadata.mode) || null;
    },
    /**
     * Returns true if this is a chorale exercise.
     *
     * @return {boolean}
     */
    isChorale: function () {
      var mode = this.getMode();
      if (mode) {
        return mode === "playback" || mode === "analysis_match" || mode === "play-all-voices" || mode === "analysis";
      }
      return this.exercise.type === "chorale" || this.exercise.type === "umto_chorale";
    },
    /**
     * Returns true if this is a chorale identification exercise.
     *
     * @return {boolean}
     */
    isChoraleIdentification: function () {
      if (this.isSymbolicMeterQuestion()) {
        return false;
      }
      var type = this.exercise.type;
      var mode = this.getMode();
      return type === "chorale_identification" ||
        (type === "umto_chorale" && (mode === "identification" || mode === "chorale_identification"));
    },
    /**
     * Returns true if this is a symbolic meter question exercise.
     *
     * @return {boolean}
     */
    isSymbolicMeterQuestion: function () {
      return this.exercise.type === "umto_symbolic_meter";
    },
    /**
     * Returns true if this is a key signature exercise.
     *
     * @return {boolean}
     */
    isKeySignatureExercise: function () {
      return this.exercise.type === "umto_key_signature";
    },
    /**
     * Returns true if this is an analysis match exercise.
     *
     * @return {boolean}
     */
    isHarmonization: function () {
      return this.getMode() === "harmonization";
    },
    getHarmonizationTargets: function () {
      return this.exercise.harmonizationTargets || [];
    },
    getHarmonizationMetadata: function () {
      var score = this.exercise.score;
      return (score && score.umto && score.umto.metadata) || {};
    },
    isAnalysisMatch: function () {
      return this.getMode() === "analysis_match";
    },
    /**
     * Returns true if this is a musicxml exercise.
     *
     * @return {boolean}
     */
    isMusicXML: function () {
      return this.exercise.type === "musicxml";
    },
    /**
    isIdentification: function () {
      return this.exercise.type === "identification" || this.exercise.type === "chorale_identification" || this.isSymbolicMeterQuestion();
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
      if (this.exercise.analysisPolicy && this.exercise.analysisPolicy.family) {
        return this.exercise.analysisPolicy.family;
      }
      return this.exercise.analysisType || "roman";
    },
    /**
     * Returns the input mode for identification exercises.
     *
     * @return {string}
     */
    getInputMode: function () {
      return this.exercise.inputMode || "dropdown";
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
      exercise.exerciseId = definition.exerciseId;
      exercise.reviewMode = definition.reviewMode || false;
      exercise.reviewAnswers = definition.reviewAnswers;
      var problems = [];

      if (definition.isUMTO) {
        exercise.isUMTO = true;
        exercise.type = definition.type;
        exercise.score = definition.score || {};
        exercise.allowed_answers = definition.allowed_answers || [];
        exercise.analysisPolicy = definition.analysisPolicy || null;
        exercise.grading = definition.grading || [];
        exercise.key = convertCIRKeyToHarmonyLabKey(definition.key || "C");
        exercise.keySignature = false;

        exercise.introText = definition.introText || (definition.score && definition.score.umto && definition.score.umto.metadata && definition.score.umto.metadata.source) || false;
        exercise.reviewText = definition.reviewText || "Well done!";
        exercise.nextExercise = definition.nextExercise || false;
        exercise.exerciseList = definition.exerciseList || [];
        exercise.staffDistribution = definition.staffDistribution || "chorale";
        exercise.complexity_score = definition.complexity_score || 0;
        exercise.semibrevesPerLine = definition.semibrevesPerLine || 4;
        exercise.display = definition.display || {};
        exercise.mode = definition.mode || (definition.score && definition.score.umto && definition.score.umto.metadata && definition.score.umto.metadata.mode) || "play";
        exercise.analysisType = definition.analysisType || (exercise.complexity_score === 1 ? "note_name" : "roman");
        exercise.inputMode = definition.inputMode ||
          (definition.score && definition.score.umto && definition.score.umto.metadata && definition.score.umto.metadata.input_mode) ||
          "dropdown";
        exercise.analysis = {
          enabled: true,
          mode: {}
        };
        // Identification exercises: overlays are off — student provides the labels.
        // Non-identification (playback, analysis_match): show analysis overlays.
        var _isIdentMode = definition.mode === "identification" || definition.mode === "chorale_identification";
        if (!_isIdentMode) {
          if (exercise.analysisType === "note_name") {
            exercise.analysis.mode.note_names = true;
          } else {
            exercise.analysis.mode.roman_numerals = true;
          }
        }

        console.log("[UMTO-DEBUG] parsed exercise:", {
            type: exercise.type,
            mode: exercise.mode,
            analysisType: exercise.analysisType,
            analysis: exercise.analysis
        });

        if (exercise.type === "umto_chorale") {
          exercise.harmonizationTargets = definition.harmonizationTargets || [];
          var isIdent = exercise.mode === "identification" || exercise.mode === "chorale_identification";
          var isHarm = exercise.mode === "harmonization";
          console.log("[UMTO-DEBUG] isIdent:", isIdent, "isHarm:", isHarm, "mode:", exercise.mode);
          if (isHarm) {
            // Harmonization: targets are pre-built by generate_harmonization command.
            exercise.problems = exercise.harmonizationTargets;
            // Show figured bass or roman numeral overlays per analysisType.
            exercise.analysis = { enabled: true, mode: {} };
            if (exercise.analysisType === "figured_bass") {
              exercise.analysis.mode.thoroughbass = true;
            } else {
              exercise.analysis.mode.roman_numerals = true;
            }
          } else if (isIdent) {
            exercise.problems = applySkillFilter(
              buildUMTOIdentificationProblems(exercise),
              (definition.playlistSkillTags || []).concat(definition.playlistTags || []),
              exercise.analysisType,
              exercise.allowed_answers
            );
          } else {
            var isPlayback = exercise.mode === "playback" || exercise.mode === "analysis_match" || exercise.mode === "play-all-voices";
            console.log("[UMTO-DEBUG] using fallback problems for non-ident mode. isPlayback:", isPlayback);
            // Playback modes don't need problems structure; they use grading slices instead.
            exercise.problems = isPlayback ? [] : buildUMTOIdentificationProblems(exercise);
          }
        } else if (exercise.type === "umto_symbolic_meter") {
          exercise.problems = _.map(definition.problems || [], function (problem) {
            return _.assign({}, problem);
          });
          exercise.mode = definition.mode || "identification";
          exercise.analysisType = definition.analysisType || "unit2_symbolic_meter";
          exercise.inputMode = definition.inputMode || "dropdown";
          exercise.staffDistribution = definition.staffDistribution || "none";
          exercise.analysis = {
            enabled: false,
            mode: {}
          };
          exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
        } else if (exercise.type === "umto_key_signature") {
          exercise.problems = _.map(definition.problems || [], function (problem) {
            return _.assign({}, problem);
          });
          exercise.mode = definition.mode || "identification";
          exercise.analysisType = definition.analysisType || "unit3_key_signature";
          exercise.inputMode = definition.inputMode || "text";
          exercise.staffDistribution = definition.staffDistribution || "none";
          exercise.analysis = {
            enabled: false,
            mode: {}
          };
          exercise.highlight = _.cloneDeep(HIGHLIGHT_SETTINGS);
        } else if (exercise.type === "identification") {
          exercise.problems = _.map(definition.chord || [], function (chord) {
            var notes = ExerciseDefinition.sortNotes(chord.notes || []);
            return {
              visible: notes.slice(),
              hidden: [],
              notes: notes,
              answer: chord.answer || "",
              choices: chord.choices || [],
              unison_idx: null,
              rhythm: chord.rhythmValue || "w",
            };
          });
          exercise.mode = "identification";
          exercise.identMode = definition.identMode || "practice";
          exercise.analysisType = definition.analysisType || "chord_quality";
          exercise.inputMode = definition.inputMode || "dropdown";
          exercise.staffDistribution = definition.staffDistribution || "keyboard";
          exercise.analysis = { enabled: false, mode: {} };
        }
        exercise.playlistTags = definition.playlistTags || [];
        exercise.playlistSkillTags = definition.playlistSkillTags || [];
        exercise.skill_tags = definition.skillTags || [];
        exercise.complexity_score = definition.complexity_score || 0;
        return exercise;
      }

      // Special handling for chorale and musicxml exercises
      if (definition.type === "chorale" || definition.type === "musicxml") {
        exercise.type = definition.type;
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
        exercise.playlistTags = definition.playlistTags || [];
        exercise.playlistSkillTags = definition.playlistSkillTags || [];
        exercise.complexity_score = definition.complexity_score || 0;
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
        exercise.playlistSkillTags = definition.playlistSkillTags || [];
        exercise.skill_tags = definition.skillTags || [];
        exercise.playlistTags = definition.playlistTags || [];
        exercise.problems = applySkillFilter(
          buildChoraleIdentificationProblems(exercise),
          (exercise.playlistSkillTags).concat(exercise.playlistTags),
          exercise.analysisType
        );
        exercise.complexity_score = definition.complexity_score || 0;
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
      exercise.skillTags = definition.skillTags || [];
      exercise.playlistSkillTags = definition.playlistSkillTags || [];
      exercise.playlistTags = definition.playlistTags || [];

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
