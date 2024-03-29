define(["lodash", "vexflow", "app/utils/analyze", "app/config"], function (
  _,
  Vex,
  Analyze,
  Config
) {
  "use strict";

  var DEFAULT_NOTE_COLOR = Config.get("general.defaultNoteColor");

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  /**
   * StaveNoteFactory.
   *
   * This class knows how to create Vex.Flow.StaveNote objects with modifiers.
   *
   * In addition to the basic responsibility of creating notes with the
   * correct accidental modifiers, it can highlight notes in different
   * colors to draw attention to specific musical phenomena.
   *
   * @constructor
   * @param {object} settings
   * @param {object} settings.clef
   * @param {object} settings.chord
   * @param {object} settings.keySignature
   * @param {object} settings.highlightConfig
   * @param {object} settings.modifierCallback
   * @return
   */
  var StaveNoteFactory = function (settings) {
    this.settings = settings || {};

    _.each(
      [
        "chord",
        "keySignature",
        "clef",
        "highlightConfig",
        "modifierCallback",
        "activeAlterations",
      ],
      function (prop) {
        if (prop in this.settings) {
          this[prop] = this.settings[prop];
        } else {
          throw new Error("missing required settings." + prop);
        }
      },
      this
    );

    this.init();
  };

  _.extend(StaveNoteFactory.prototype, {
    /**
     * Initializes the object.
     *
     * @return
     */
    init: function () {
      this.defaultNoteColor =
        this.settings.defaultNoteColor || DEFAULT_NOTE_COLOR;
      this.highlightMap = {};
    },
    /**
     * VexFlow rhythm code:
     * w = whole note
     * H = dotted half note // AnalyticPiano code, later parsed for VexFlow
     * h = half note
     * q = quarter note
     * Unsupported in stave.js: createStaveVoice(): "r" = suffix for rest
     */
    getRhythmValue: function () {
      if (!this.chord._rhythmValue) {
        return DEFAULT_RHYTHM_VALUE;
      } else {
        return this.chord._rhythmValue;
      }
    },
    /**
     * Creates one more Vex.Flow.StaveNote's. Must equal one measure.
     *
     * @public
     * @return {array}
     */
    createStaveNotes: function (duration = undefined) {
      // console.log(duration, 'passed to createStaveNotes');
      let vexflow_duration = duration
        ? duration
        : this.getRhythmValue().toLowerCase();
      let vexflow_dots =
        this.getRhythmValue().toUpperCase() == this.getRhythmValue() ? 1 : 0;
      let vexflow_keys = this.getNoteKeys();
      let full_context = this.chord.settings.full_context || false;

      const CHORALE_FORMAT = this.chord.settings.staffDistribution === "chorale";

      if (CHORALE_FORMAT && vexflow_keys.length == 2) {
        // not needed once VexFlow voices were properly formatted
        // const unison_bool =
        //   vexflow_keys[0][0] == vexflow_keys[1][0] &&
        //   vexflow_keys[0][vexflow_keys[0].length-1] == vexflow_keys[1][vexflow_keys[1].length-1];
        // if (unison_bool) {
        //   console.log('unison on ' + String(this.clef) + ' clef', vexflow_keys);
        // }
        var stave_note_1 = this._makeStaveNote(
          [vexflow_keys[0]],
          this.getNoteModifiers(),
          vexflow_duration,
          vexflow_dots,
          -1, // stem_direction
          'AB' // part is alto or bass
        );
        var stave_note_2 = this._makeStaveNote(
          [vexflow_keys[1]],
          this.getNoteModifiers(),
          vexflow_duration,
          vexflow_dots,
          1, // stem_direction
          'ST' // part is soprano or tenor
        );
        return [stave_note_1, stave_note_2];
      } else if (CHORALE_FORMAT && vexflow_keys.length == 1
        && full_context && full_context.length == 4) {
        let note_num = this.chord.getNoteNumbers(this.clef)[0];
        if (note_num == full_context[0] || note_num == full_context[2]) {
          var stave_note_1 = this._makeStaveNote(
            [vexflow_keys[0]],
            this.getNoteModifiers(),
            vexflow_duration,
            vexflow_dots,
            -1, // stem_direction
            'AB' // part is alto or bass
          );
        } else if (note_num == full_context[1] || note_num == full_context[3]) {
          var stave_note_1 = this._makeStaveNote(
            [vexflow_keys[0]],
            this.getNoteModifiers(),
            vexflow_duration,
            vexflow_dots,
            1, // stem_direction
            'ST' // part is soprano or tenor
          );
        } else {
          var stave_note_1 = this._makeStaveNote(
            vexflow_keys,
            this.getNoteModifiers(),
            vexflow_duration,
            vexflow_dots,
            0, // stem_direction
          );
        }
        return [stave_note_1];
      } else {
        var stave_note_1 = this._makeStaveNote(
          vexflow_keys,
          this.getNoteModifiers(),
          vexflow_duration,
          vexflow_dots,
          0, // stem_direction
        );
        return [stave_note_1];
      }
    },
    /**
     * Returns true if there are any stave notes to create, false otherwise.
     *
     * @public
     * @return {boolean}
     */
    hasStaveNotes: function () {
      return this.chord.hasNotes(this.clef);
    },
    /**
     * Returns a list of key names for this stave only ["note/octave", ...]
     *
     * @return {array}
     */
    getNoteKeys: function () {
      var note_nums = this.chord.getNoteNumbers(this.clef);
      var all_note_nums = this.chord.getNoteNumbers();
      if (
        typeof this.chord.settings.full_context === "object" &&
        !(
          this.chord.settings.full_context.length === 2 &&
          this.keySignature.key === "h"
        )
      ) {
        /* the second half of the conditional safeguards spelling of intervals in no key*/
        all_note_nums = this.chord.settings.full_context;
      }
      var note_name,
        note_keys = [];

      for (var i = 0, len = note_nums.length; i < len; i++) {
        note_name = this.getNoteName(note_nums[i], all_note_nums);
        note_keys.push(note_name);
      }

      return note_keys;
    },
    /**
     * Returns an array of functions that will modify a Vex.Flow.StaveNote
     * that is passed as a parameter.
     *
     * @return {array}
     */
    getNoteModifiers: function () {
      return this.modifierCallback.call(this);
    },
    /**
     * Returns the correct spelling or note name of a given note in a
     * collection of notes.
     *
     * Note: this delegates to a utility function that handles the spelling
     * logic, because in some cases, a note may not use the default
     * spelling, but instead be re-spelled on the fly (snap spelling).
     *
     * @param {number} note
     * @param {array} notes
     * @return {string} the note name or spelling
     */
    getNoteName: function (note, notes) {
      var analyzer = this._makeAnalyzer();
      return analyzer.getNoteName(note, notes);
    },
    /**
     * Returns an array of objects containing each key and accidental
     *
     * @protected
     * @param {array} noteKeys
     * @return {array}
     */
    getAccidentalsOf: function (
      noteKeys,
      activeAlterations = Object.create(null)
    ) {
      let note_dict = {}
      for (var i = 0, len = noteKeys.length; i < len; i++) {
        let str = noteKeys[i];
        try {
          let note_regex = new RegExp('^([a-g])([b#]*)\/([0-9]+)$', 'g');
          let matches = note_regex.exec(str).slice(1);
          note_dict[i] = {
            "alphabet": matches[0],
            "accidental": matches[1],
            "register": matches[2]
          }
        }
        catch { console.log('Error parsing note names for getAccidentalsOf', str) }
      }

      let keySignature = this.keySignature;
      let accidentals = [];
      let note,
        note_spelling,
        quality,
        natural_note,
        natural_found_idx,
        is_doubled;

      for (var i = 0, len = noteKeys.length; i < len; i++) {
        accidentals.push("");
      }

      for (var i = 0, len = noteKeys.length; i < len; i++) {
        // skip to next iteration is for the case that the
        // note has already been assigned a natural because
        // the same note name appears twice (i.e. is doubled).
        if (accidentals[i]) {
          continue;
        }

        note = noteKeys[i];
        note_spelling = note.replace(/\/\d$/, "");
        quality = note_spelling.substr(1); // get qualifier
        natural_note = note.replace(quality + "/", "/");
        natural_found_idx = noteKeys.indexOf(natural_note);
        is_doubled = natural_found_idx !== -1 && natural_found_idx !== i && natural_note[0] != note_spelling;

        // check to see if this note is doubled - that is, the natural version of
        // the note is also active at the same time, in which case it needs to be
        // distinguished with a natural accidental

        if (is_doubled) {
          accidentals[natural_found_idx] = "n";
        }

        accidentals[i] = quality;

        // let is_signed_alteration =
        // 	keySignature.signatureContains(note_spelling);
        // 	// diatonic and non-natural
        const staff_line = note[0] + note.split("/")[1];
        const is_diatonic = keySignature.isDiatonic(note_spelling);

        if (is_diatonic) {
          if (activeAlterations[staff_line] == undefined) {
            accidentals[i] = "";
          } else if (activeAlterations[staff_line] != quality) {
            if (quality == "") {
              accidentals[i] = "n";
            } else {
              accidentals[i] = quality;
            }
          }
        } else {
          // chromatic
          if (activeAlterations[staff_line] == quality) {
            accidentals[i] = "";
          } else if (activeAlterations[staff_line] == undefined) {
            if (quality == "") {
              accidentals[i] = "n";
            }
          } else if (activeAlterations[staff_line] !== quality) {
            if (quality == "") {
              accidentals[i] = "n";
            }
          }
        }
      }

      return accidentals;
    },
    getCancellations: function (
      noteKeys,
      activeAlterations = Object.create(null)
    ) {
      var keySignature = this.keySignature;
      var cancellations = [];
      var accidental, note, note_spelling;

      for (var i = 0, len = noteKeys.length; i < len; i++) {
        note = noteKeys[i];
        note_spelling = note.replace(/\/\d$/, "");
        accidental = note_spelling.substr(1); // get qualifier

        let staff_line = note[0] + note.split("/")[1];
        let is_diatonic = keySignature.isDiatonic(note_spelling);

        if (is_diatonic) {
          if (activeAlterations[staff_line] != undefined) {
            cancellations.push(staff_line);
          }
        }
      }

      return cancellations;
    },
    isolateChromatics: function (noteKeys) {
      var keySignature = this.keySignature;
      var chromatics = Object.create(null);
      var accidental, note, note_spelling, staff_line;

      for (var i = 0, len = noteKeys.length; i < len; i++) {
        note = noteKeys[i];
        note_spelling = note.replace(/\/\d$/, "");
        if (keySignature.isDiatonic(note_spelling)) {
          continue;
        }

        accidental = note_spelling.substr(1); // get qualifier
        staff_line = note[0] + note.split("/")[1];

        // allow for strange case of two chromatics on the same staff line in a single chord
        if (
          chromatics[staff_line] != undefined &&
          chromatics[staff_line] != accidental
        ) {
          chromatics[staff_line] = [chromatics[staff_line], accidental];
        } else {
          chromatics[staff_line] = accidental;
        }
      }

      return chromatics;
    },
    /**
     * Returns the analysis color for a given note.
     *
     * @return {object} An object containg keyStyle options
     */
    getAnalysisHighlightOf: function (noteNumber, chordNoteNumbers) {
      var keyStyleOpts = {};
      var analyzer = this._makeAnalyzer({
        highlightMode: this.highlightConfig.mode,
      });
      var color = analyzer.get_color(noteNumber, chordNoteNumbers);
      if (!color) {
        return false;
      }

      keyStyleOpts = {
        //shadowColor: color,
        //shadowBlur: 15,
        fillStyle: color,
        strokeStyle: color,
      };

      return keyStyleOpts;
    },
    /**
     * Resets the note highlight mappings.
     *
     * @return this
     */
    resetHighlight: function () {
      this.highlightMap = {};
      return this;
    },
    /**
     * Highlights a note in a Vex.Flow.StaveNote, given by key index,
     * and applies a key style. Since there may be several styles
     * applied to a single key, each highlight should have a priority.
     * If all keys have a priority, then the order is undefined.
     *
     * Note: in order to retrieve the computed highlight, call
     * makeHighlightModifier() once for each keyIndex.
     *
     * @return this
     */
    highlightNote: function (keyIndex, keyStyleOpts, priority) {
      if (typeof priority === "undefined") {
        priority = 0;
      }
      if (typeof keyStyleOpts === "undefined") {
        keyStyleOpts = {
          //shadowColor: color,
          //shadowBlur: color,
          //fillStyle: color,
          //strokeStyle: color
        };
      }

      if (!this.highlightMap.hasOwnProperty(keyIndex)) {
        this.highlightMap[keyIndex] = [];
      }

      this.highlightMap[keyIndex].push({
        priority: priority,
        keyStyle: keyStyleOpts,
      });

      return this;
    },
    /**
     * Returns the highlight for a given key with the highest priority.
     *
     * @return {object} An object containing key style options.
     */
    getHighlightOf: function (keyIndex) {
      var hmap = this.highlightMap;
      var defaultKeyStyle = {
        fillStyle: this.defaultNoteColor,
        strokeStyle: this.defaultNoteColor,
      };
      var styles = [];

      if (hmap[keyIndex]) {
        if (hmap[keyIndex].length == 1) {
          return hmap[keyIndex][0].keyStyle;
        }
        styles = hmap[keyIndex].slice(0);
        styles.sort(this.comparePriority);
        return styles[0].keyStyle;
      }

      return defaultKeyStyle;
    },
    /**
     * Compares two objects by the value of their priority attribute.
     *
     * @return -1 if a>b, 0 if a==b, or 1 if a<b
     */
    comparePriority: function (a, b) {
      if (a.priority > b.priority) {
        return -1;
      } else if (a.priority == b.priority) {
        return 0;
      }
      return 1;
    },
    /**
     * Returns the octave for a note, taking into account the current note spelling.
     *
     * @protected
     * @param {number} pitchClass
     * @param {number} octave
     * @param {string} note
     * @return {number}
     */
    calculateOctave: function (pitchClass, octave, note) {
      var note_letter = note.charAt(0);
      if (pitchClass === 0 && note_letter === "B") {
        return octave - 1;
      } else if (pitchClass === 11 && note_letter === "C") {
        return octave + 1;
      }
      return octave;
    },
    /**
     * Returns a function that will add an accidental to a
     * Vex.Flow.StaveNote.
     *
     * @protected
     * @param {number} keyIndex
     * @param {string} accidental
     * @return {function}
     */
    makeAccidentalModifier: function (keyIndex, accidental) {
      return function (staveNote) {
        staveNote.addAccidental(keyIndex, new Vex.Flow.Accidental(accidental));
      };
    },
    /**
     * Returns a function that will add a highlight color to a
     * Vex.Flow.StaveNote.
     *
     * @protected
     * @param {number} keyIndex
     * @param {object} keyStyle Object of keyStyleOptions
     * @return {function}
     */
    makeHighlightModifier: function (keyIndex, keyStyle) {
      return function (staveNote) {
        staveNote.setKeyStyle(keyIndex, keyStyle);
      };
    },
    setStemStyle: function (style) {
      return function (staveNote) {
        if (typeof staveNote.setStemStyle === "function") {
          staveNote.setStemStyle(style);
        }
      };
    },
    setStemDirection: function (style) {
      return function (staveNote) {
        if (typeof staveNote.setStemDirection === "function") {
          staveNote.setStemDirection(style);
        }
      };
    },
    setLedgerLineStyle: function (style) {
      return function (staveNote) {
        if (typeof staveNote.setLedgerLineStyle === "function") {
          staveNote.setLedgerLineStyle(style);
        }
      };
    },
    /**
     * Returns a new instance of Analyze using the current key signature.
     *
     * Used by the highlight method to highlight certain notes and also by
     * the method that looks up the note name.
     *
     * @param {object} options
     * @return {object}
     */
    _makeAnalyzer: function (options) {
      return new Analyze(this.keySignature, options);
    },
    /**
     * Returns a new Vex.Flow.StaveNote with all modifiers added.
     *
     * @protected
     * @param {array} keys
     * @param {array} modifiers
     * @return {Vex.Flow.StaveNote}
     */
    _makeStaveNote: function (
      keys,
      modifiers,
      rhythm_value,
      dot_count = 0,
      stem_direction = 0,
      part = null,
      unison_bool = false,
    ) {
      modifiers = modifiers || [];

      var stave_note = new Vex.Flow.StaveNote({
        keys: keys,
        /**
         * Duration must equal a full bar as defined
         * in stave.js and vexflow.js (Vex.Flow.METER)
         */
        duration: rhythm_value,
        // type: "r", // make a rest
        dots: dot_count,
        clef: this.clef,
        auto_stem: stem_direction === 0,
        stem_direction: stem_direction,
        // displaced: unison_bool,
      });
      if (dot_count) {
        stave_note = stave_note.addDotToAll();
      }

      if (["AB", "ST"].includes(part)) {
        // circumventing the modifiers callbacks because the index becomes wrong

        const accidental = this.getAccidentalsOf(keys, this.activeAlterations)[0] || false;
        try {
          if (accidental) { stave_note.addAccidental(0, new Vex.Flow.Accidental(accidental)); }
        } catch { console.log('Bad parameters for VexFlow .addAccidental', accidental) }
        const style = this.getHighlightOf(["AB", "ST"].indexOf(part));
        try {
          stave_note.setKeyStyle(0, style);
        } catch { console.log('Bad parameters for VexFlow .setKeyStyle') }
        try {
          stave_note.setStemStyle(style);
        } catch { console.log('Bad parameters for VexFlow .setStemStyle') }

        let stem_adjustment = 0; // 10 is the height of each space
        if ( // inner parts
          part == "AB" && this.clef == "treble" ||
          part == "ST" && this.clef == "bass"
        ) {
          stem_adjustment = -10;
        }
        // uses a custom VexFlow function that must be duplicated if VexFlow is updated
        stave_note.setStemHeightAdjustment(stem_adjustment);

      } else for (var i = 0, len = modifiers.length; i < len; i++) {
        // as of December 2023, winds up as
        // staveNote.addAccidental()
        // staveNote.setKeyStyle() which is applying colors in AnalyticPiano
        // staveNote.setStemStyle() which is applying colors in AnalyticPiano
        var function_regex = /(staveNote\.[a-zA-Z]+\()/g; // for console debugging
        try {
          modifiers[i](stave_note);
        } catch {
          console.log("FAILED", this.clef, stave_note.keys, String(i), String(modifiers[i]).match(function_regex)[0]);
        }
      }

      return stave_note;
    },
  });

  return StaveNoteFactory;
});
