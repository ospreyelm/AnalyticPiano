define([
  "lodash",
  "microevent",
  "app/config",
  "app/components/events",
], function (_, MicroEvent, Config, EVENTS) {
  "use strict";

  const VALID_STAFF_DISTRIBUTIONS = Config.get(
    "general.validStaffDistributions"
  );
  const VOICE_COUNT_FOR_KEYBOARD_STYLE = Config.get(
    "general.voiceCountForKeyboardStyle"
  );
  var STAFF_DISTRIBUTION = Config.get("general.staffDistribution");

  /**
   * Creates an instance of a chord.
   *
   * A chord represents a collection of notes that are sounding at a
   * given point in time (the precise point in time is not our concern).
   *
   * It collaborates closely with objects that interface with MIDI NOTE ON/OFF
   * messages.
   *
   * @mixes MicroEvent
   * @fires change
   * @fires clear
   * @constructor
   */
  var Chord = function (settings) {
    if (false) {
    } else if (sessionStorage.getItem("staffDistribution")) {
      /* temporary hack */
      STAFF_DISTRIBUTION = sessionStorage.getItem("staffDistribution");
    }

    this.settings = settings || {};

    if (
      this.settings.staffDistribution &&
      VALID_STAFF_DISTRIBUTIONS.includes(this.settings.staffDistribution)
    ) {
      STAFF_DISTRIBUTION = this.settings.staffDistribution;
    } else {
      this.settings.staffDistribution = STAFF_DISTRIBUTION;
    }

    this.init();
  };

  _.extend(Chord.prototype, {
    /**
     * Initializes the object.
     *
     * @return undefined
     */
    init: function () {
      /**
       * Duration for specific note. Value can be "w", "W", "H", "h", "Q", or "q"
       * @type {string}
       * @protected
       */
      this._rhythmValue = null;
      /**
       * Index of the midi note, in the ordered set of midi notes, that (most recently) was indicated as a unison
       * @type {integer}
       */
      this._unison_idx = null;
      /**
       * Container for the notes that are active.
       * @type {object}
       * @protected
       */
      this._notes = {};
      /**
       * Sustain flag. When true means notes should be sustained.
       * @type {boolean}
       * @protected
       */
      this._sustain = false;
      /**
       * Container for the note state changes that occur while notes are
       * being sustained.
       * @type {object}
       * @protected
       */
      this._sustained = {};
      this._culled_from_sustain = [];
      /**
       * Transpose value expressed as the number of semitones.
       * @type {number}
       * @protected
       */
      this._transpose = 0;
      /**
       * Arbitrary properties associated with each note.
       * @type {object}
       * @protected
       */
      this._noteProps = {};

      // initialize rhythm value
      if ("rhythm" in this.settings) {
        this._rhythmValue = this.settings.rhythm;
      }

      // initialize notes that should be on
      if ("notes" in this.settings) {
        this.noteOn(this.settings.notes);
      }

      // UNISONS
      if ("unison_idx" in this.settings) {
        this._unison_idx = this.settings.unison_idx;
      }
    },
    /**
     * Clears all the notes in the chord.
     *
     * @fires clear
     * @return undefined
     */
    clear: function () {
      this._notes = {};
      this._sustained = {};
      this._culled_from_sustain = [];
      this.trigger("clear");
    },
    /**
     * Command to turn on a note.
     *
     * If the status of the note has changed, it will fire a change event.
     *
     * @fires change
     * @param {number|array|object} notes The note or notes to turn on
     * @return {boolean} True if the note status changed, false otherwise.
     */
    noteOn: function (notes) {
      var i, noteObj, len, noteNumber;
      var changed = false;
      var _transpose = this._transpose;
      var _sustain = this._sustain;

      // make sure the argument is an array of note numbers
      if (typeof notes === "number") {
        notes = [notes];
      } else if (!_.isArray(notes) && typeof notes === "object") {
        noteObj = notes;
        notes = noteObj.notes;
        if (noteObj.hasOwnProperty("overrideSustain")) {
          _sustain = noteObj.overrideSustain ? false : _sustain;
        }
      }

      for (i = 0, len = notes.length; i < len; i++) {
        noteNumber = notes[i];
        if (_transpose) {
          noteNumber = this.transpose(noteNumber);
        }
        if (_sustain) {
          this._sustained[noteNumber] = true;
        }

        if (!changed) {
          changed = this._notes[noteNumber] !== true;
        }

        const currently_on_notes = Object.entries(this._notes).filter(([k, v]) => v === true).map(([k, v]) => parseInt(k));
        if (this._notes[noteNumber] === true) {
          let latest_double_tap_idx = currently_on_notes.indexOf(noteNumber);
          if (latest_double_tap_idx == -1) {
            console.log('unexpected condition [1] in call of chord.noteOn')
          }
          if (this._unison_idx === latest_double_tap_idx) { // === is crucial here, to ensure that the test (false === 0) fails
            this._unison_idx = null; // toggle off
          } else {
            this._unison_idx = latest_double_tap_idx;
          }
          changed = true;
        } else {
          let unison_idx = this._unison_idx;
          if (unison_idx != null &&
            Number.isInteger(unison_idx) && // should be redundant
            currently_on_notes[unison_idx] > noteNumber // i.e. the user is adding a note below the doubled note
          ) {
            this._unison_idx += 1;
          }
          if (!changed) {
            console.log('unexpected condition [2] in call of chord.noteOn')
            changed = true;
          }
        }
        this._notes[noteNumber] = true;
      }

      if (changed) {
        this.trigger("change", "note:on");
      }

      return changed;
    },
    /**
     * Command to turn off a note.
     *
     * If the status of the note has changed, it will fire a change event.
     *
     * Note: this command will be ignored if the chord is sustaining notes
     * and this method will return false.
     *
     * @fires change
     * @param {number|array|object} notes The note or notes to turn off
     * @return {boolean} True if the note status changed, false otherwise.
     */
    noteOff: function (notes) {
      var i, noteObj, len, noteNumber;
      var changed = false;
      var _transpose = this._transpose;
      var _sustain = this._sustain;
      var cull_from_sustain = false;

      // make sure the argument is an array of note numbers
      if (typeof notes === "number") {
        notes = [notes];
      } else if (!_.isArray(notes) && typeof notes === "object") {
        noteObj = notes;
        notes = noteObj.notes;
        if (noteObj.hasOwnProperty("cullFromSustain")) {
          cull_from_sustain = noteObj.cullFromSustain === true;
        }
      }

      for (i = 0, len = notes.length; i < len; i++) {
        noteNumber = notes[i];
        if (_transpose) {
          noteNumber = this.transpose(noteNumber);
        }
        if (_sustain) {
          this._sustained[noteNumber] = false;
          if (cull_from_sustain) {
            const currently_on_notes = Object.entries(this._notes).filter(([k, v]) => v === true).map(([k, v]) => parseInt(k));
            const doubled_note_num = currently_on_notes[this._unison_idx] || null;
            let unison_idx = this._unison_idx;

            if (doubled_note_num !== null) {
              if (doubled_note_num == noteNumber) {
                this._unison_idx = null;
              } else if (doubled_note_num > noteNumber) {
                this._unison_idx += -1;
              }
            }
            this._culled_from_sustain.push(noteNumber);
            // TO DO!
            // Use broadcast / events to relay to Tone.js that midi note [noteNumber] should be turned off
          }
        }
        if (!_sustain || cull_from_sustain) {
          if (!changed) {
            changed = this._notes[noteNumber] === true;
          }
          this._notes[noteNumber] = false;
        }
      }

      if (changed) {
        this.trigger("change", "note:off");
      }

      return changed;
    },
    /**
     * Sets note properties.
     *
     * @param {number|array} notes
     * @param {object}
     */
    setNoteProps: function (notes, props) {
      props = props || {};
      if (typeof notes === "number") {
        notes = [notes];
      }
      for (var i = 0, len = notes.length; i < len; i++) {
        this._noteProps[notes[i]] = _.assign({}, props);
      }
      return this;
    },
    /**
     * Returns all note properties.
     *
     * @return {object}
     */
    getNoteProps: function () {
      return this._noteProps;
    },
    /**
     * Returns properties associated with a single note.
     *
     * @return {object}
     */
    getNoteProp: function (note) {
      if (!this._noteProps.hasOwnProperty(note)) {
        return false;
      }
      return this._noteProps[note];
    },
    /**
     * Commands the chord to sustain all notes that are turned on (i.e.
     * ignore "noteOff" messages).
     *
     * This should be used in conjunction with the releaseSustain() method.
     *
     * @return undefined
     */
    sustainNotes: function () {
      this._sustain = true;
    },
    /**
     * Releases the sustain.
     *
     * @fires change
     * @return undefined
     */
    releaseSustain: function () {
      this._sustain = false;
    },
    /**
     * Synchronize the notes playing with those that are being sustained.
     *
     * @returns {boolean}
     */
    syncSustainedNotes: function (prev_notes = false, prev_sustained = false) {
      var _notes = this._notes;
      let _sustained = this._sustained;
      let _culled_from_sustain = this._culled_from_sustain;
      var changed = false;

      let notes_to_turn_off = [];

      _.each(
        _sustained,
        function (state, noteNumber) {
          if (_notes[noteNumber] !== state) {
            if (state === false) {
              notes_to_turn_off.push(noteNumber);
            }
            _notes[noteNumber] = state;
            changed = true;
          }
        },
        this
      );

      if (prev_notes) {
        // needs improvement: too harsh
        _.each(
          prev_notes,
          function (state, noteNumber) {
            if (_sustained[noteNumber] !== state) {
              notes_to_turn_off.push(noteNumber);
              changed = true;
            }
          },
          this
        );
      }

      // if (prev_notes && prev_sustained) {
      //  _.each(prev_sustained, function(state, noteNumber) {
      //    if(prev_notes[noteNumber] !== state) {
      //      if(state === false) {
      //        notes_to_turn_off.push(noteNumber);
      //      }
      //      // DO NOT EDIT prev_notes (as _notes above)
      //      // Breaks exercise grading
      //      changed = true;
      //    }
      //  }, this);
      // }

      // if (prev_notes) {
      //  // this is too lenient
      //  _.each(prev_notes, function(state, noteNumber) {
      //    console.log(state, noteNumber, _sustained[noteNumber]);
      //    if(_sustained[noteNumber] !== undefined && _sustained[noteNumber] === false && state === false) {
      //      notes_to_turn_off.push(noteNumber);
      //      _notes[noteNumber] = false;
      //      changed = true;
      //    }
      //  }, this);
      // }

      this._sustained = {};
      this._culled_from_sustain = [];

      if (changed) {
        this.trigger("change");
      }

      try {
        notes_to_turn_off = notes_to_turn_off.concat(
          _culled_from_sustain.map(String)
        );
      } catch {}

      return notes_to_turn_off;
    },
    /**
     * Returns true if notes are being sustained, false otherwise.
     *
     * @return {boolean}
     */
    isSustained: function () {
      return this._sustain ? true : false;
    },
    /**
     * Sets the transpose for the chord and returns true if successful,
     * false otherwise.
     *
     * Transposing the chord will raise or lower the notes by a number
     * of semitones into different key. Setting the transpose to zero
     * will return the chord to its original key.
     *
     * @param {number} newTranspose A number of semitones.
     * @return {boolean} True if the transpose succeeded, false otherwise.
     */
    setTranspose: function (value) {
      if (!this.isValidTranspose(value)) {
        return false;
      }

      var new_transpose = parseInt(value, 10);
      var old_transpose = this._transpose;
      var effective_transpose = new_transpose - old_transpose;

      this._notes = _.reduce(
        this._notes,
        function (result, state, noteNumber) {
          var transposition = effective_transpose + parseInt(noteNumber, 10);
          result[transposition] = state;
          return result;
        },
        {}
      );

      this._transpose = new_transpose;

      this.trigger("change", "notes:transpose");

      return true;
    },
    /**
     * Returns the current transpose value.
     *
     * @return {number}
     */
    getTranspose: function () {
      return this._transpose;
    },
    /**
     * Copies the transpose to another chord.
     *
     * @param {Chord} chord
     * @return undefined
     */
    copyTranspose: function (chord) {
      this.setTranspose(chord.getTranspose());
    },
    /**
     * Copies the sustain to another chord.
     *
     * @param {Chord} chord
     * @return undefined
     */
    copySustain: function (chord) {
      this._sustain = chord.isSustained();
    },
    /**
     * Copies the notes to another chord.
     *
     * @param {Chord} chord
     * @return undefined
     */
    copyNotes: function (chord) {
      this._notes = _.cloneDeep(chord._notes);
      this._sustained = _.cloneDeep(chord._sustained);
      this._culled_from_sustain = _.cloneDeep(chord._culled_from_sustain);
    },
    /**
     * Copies the chord.
     *
     * @param {Chord} chord
     * @return this
     */
    copy: function (chord) {
      this.copyTranspose(chord);
      this.copySustain(chord);
      this.copyNotes(chord);
      return this;
    },
    /**
     * Returns true if the transpose value is valid, false otherwise.
     *
     * @param {number} value
     * @return {boolean}
     */
    isValidTranspose: function (value) {
      var TRANSPOSE_MIN = -12,
        TRANSPOSE_MAX = 12;
      if (!/^-?\d+$/.test(value)) {
        return false;
      }
      return value >= TRANSPOSE_MIN && value <= TRANSPOSE_MAX;
    },
    /**
     * Transposes the given note number using the current transpose setting.
     *
     * When transpose is set to zero, this is just the identity function.
     *
     * @param {number} noteNumber
     * @return {number}
     */
    transpose: function (noteNumber) {
      var transposed = this._transpose + noteNumber;
      if (transposed >= 0 && transposed <= 127) {
        return transposed;
      }
      return noteNumber;
    },
    /**
     * Reverses a transpose operation.
     *
     * Note: noteNumber should equal untranspose(transpose(noteNumber))
     *
     * @param {number} noteNumber
     * @return {number}
     */
    untranspose: function (noteNumber) {
      var untransposed = noteNumber - this._transpose;
      if (untransposed >= 0 && untransposed <= 127) {
        return untransposed;
      }
      return noteNumber;
    },
    /**
     * This is a combined map/filter over the notes in the collection
     * that returns a list of notes.
     *
     * Optionally accepts a clef to filter the notes.
     * Optionally accepts a callback function to execute on the notes.
     *
     * - If no clef is given, all notes will be mapped over.
     * - If no callback is given, the note number is returned.
     *
     * @param {string} clef treble|bass
     * @param {function} callback
     * @return {array}
     */
    mapNotes: function (clef, callback) {
      var mapped_notes = [],
        notes = this.getSortedNotes();
      var wanted = true,
        note_num,
        i,
        len;

      if (Number.isInteger(this._unison_idx) && this._unison_idx < notes.length) {
        if (!(STAFF_DISTRIBUTION == 'chorale' && notes.length === 3 && this._unison_idx === 1)) {
          notes.push(notes[this._unison_idx]) // length of notes issue with rendering unisons
          notes.sort()
        }
      }

      for (i = 0, len = notes.length; i < len; i++) {
        note_num = parseInt(notes[i], 10);
        if (clef) {
          wanted = this.noteNumBelongsToClef(note_num, clef);
        }
        if (wanted) {
          if (callback) {
            mapped_notes.push(callback.call(this, note_num));
          } else {
            mapped_notes.push(note_num);
          }
        }
      }

      return mapped_notes;
    },
    /**
     * Returns true if the given clef has any notes.
     *
     * If no clef is given, returns true if any clef has notes.
     *
     * @param {string} clef treble|bass
     * @return {boolean}
     */
    hasNotes: function (clef) {
      var notes = this.getSortedNotes();
      var note_num, i, len;
      for (i = 0, len = notes.length; i < len; i++) {
        note_num = parseInt(notes[i], 10);
        if (clef) {
          if (this.noteNumBelongsToClef(note_num, clef)) {
            return true;
          }
        } else {
          return true;
        }
      }

      return false;
    },
    /**
     * Returns all note numbers on the given clef.
     *
     * @param {string} clef treble|bass
     * @return {array}
     */
    getNoteNumbers: function (clef) {
      var callback = false; // so we just get the raw note numbers
      return this.mapNotes(clef, callback);
    },
    /**
     * Returns a list of note numbers in sorted order.
     *
     * @return {array}
     */
    getSortedNotes: function () {
      var _notes = this._notes;
      var notes = [];
      var note_num;
      for (var note in _notes) {
        if (_notes.hasOwnProperty(note) && _notes[note]) {
          note_num = parseInt(note, 10); // convert string key to num
          notes.push(note_num);
        }
      }
      notes.sort(function (a, b) {
        return a - b;
      });
      return notes;
    },
    /**
     * Returns all note pitches and octaves on the given clef.
     *
     * @param {string} clef treble|bass
     * @return {array}
     */
    getNotePitches: function (clef) {
      return this.mapNotes(clef, function (noteNum) {
        return {
          noteNum: noteNum,
          pitchClass: noteNum % 12,
          octave: Math.floor(noteNum / 12) - 1,
        };
      });
    },
    /**
     * Returns true if the ntoe belongs to the given clef, false otherwise.
     *
     * @param {number} noteNum
     * @param {string} clef treble|bass
     * @return {boolean}
     */
    noteNumBelongsToClef: function (midi, clef) {
      const high_threshold = 65;
      const mid_threshold = 60;
      const low_threshold = 55;

      if (
        ["keyboard", "keyboardPlusRHBias", "keyboardPlusLHBias"].includes(
          STAFF_DISTRIBUTION
        ) &&
        VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(this.getSortedNotes().length) &&
        midi == this.getSortedNotes()[0]
      ) {
        // lowest note
        return clef == (midi <= high_threshold ? "bass" : "treble");
      } else if (
        ["keyboard", "keyboardPlusRHBias", "keyboardPlusLHBias"].includes(
          STAFF_DISTRIBUTION
        ) &&
        VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(this.getSortedNotes().length) &&
        this.getSortedNotes().slice(1).includes(midi)
      ) {
        // not lowest note
        return clef == (midi < low_threshold ? "bass" : "treble");
      } else if (STAFF_DISTRIBUTION === "grandStaff") {
        return clef == (midi < mid_threshold ? "bass" : "treble");
      } else if (
        STAFF_DISTRIBUTION === "keyboard" &&
        !VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(this.getSortedNotes().length)
      ) {
        return clef == (midi < mid_threshold ? "bass" : "treble");
      } else if (
        STAFF_DISTRIBUTION === "keyboardPlusRHBias" &&
        !VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(this.getSortedNotes().length)
      ) {
        return clef == (midi < low_threshold ? "bass" : "treble");
      } else if (
        STAFF_DISTRIBUTION === "keyboardPlusLHBias" &&
        !VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(this.getSortedNotes().length)
      ) {
        return clef == (midi <= high_threshold ? "bass" : "treble");
      } else if (STAFF_DISTRIBUTION === "LH") {
        return clef == "bass";
      } else if (STAFF_DISTRIBUTION === "RH") {
        return clef == "treble";
      } else if (
        STAFF_DISTRIBUTION === "chorale" &&
        this.getSortedNotes().length === 4
      ) {
        return (
          clef ==
          (this.getSortedNotes().slice(0, 2).includes(midi) ? "bass" : "treble")
        );
      } else if (
        // UNISONS
        STAFF_DISTRIBUTION === "chorale" &&
        this.getSortedNotes().length === 3 &&
        [0, 1, 2].includes(this._unison_idx)
      ) {
        if (this._unison_idx === 0) {
          return (
            clef ==
            (this.getSortedNotes().slice(0, 1).includes(midi) ? "bass" : "treble")
          );
        } else if (this._unison_idx === 2) {
          return (
            clef ==
            (this.getSortedNotes().slice(0, 2).includes(midi) ? "bass" : "treble")
          );
        } else { // this._unison_ix === 1
          return (
            [["bass"], ["bass", "treble"], ["treble"]][this.getSortedNotes().indexOf(midi)].includes(clef)
          );
        }
      } else {
        return clef == (midi < mid_threshold ? "bass" : "treble");
      }
      throw new Error("staff distribution code failed");
      return false;
    },
  });

  /**
   * The method getNotes() is aliased to getNoteNumbers().
   *
   * @param {string} clef treble|bass
   * @return {array}
   */
  Chord.prototype.getNotes = Chord.prototype.getNoteNumbers;

  MicroEvent.mixin(Chord); // make object observable

  return Chord;
});
