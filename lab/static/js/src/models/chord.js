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
       * Object whose keys are midi numbers and whose values are true or false.
       * Notes that are sounding or not.
       * @type {object}
       * @protected
       */
      this._notes = {};
      /**
       * Sustain flag. When true means the sustain pedal is depressed.
       * @type {boolean}
       * @protected
       */
      this._sustain = false;
      /**
       * Object whose keys are midi numbers and whose values are true or false.
       * Notes whose piano keys are depressed or not.
       * @type {object}
       * @protected
       */
      this._keys_down = {};
      /**
       * Array of midi numbers which have been manually dampened during the current depression of the sustain pedal.
       */
      this._manually_dampened = [];
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
      this._keys_down = {};
      this._manually_dampened = [];
      this._unison_idx = {};
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
      if (_.isArray(notes)) {
        var incoming = notes; // the midi numbers of notes that must be added
      } else if (Number.isInteger(notes)) {
        var incoming = [notes];
      } else if (!_.isArray(notes) && typeof notes === "object") {
        var incoming = notes.notes;
      } else {
        var incoming = [];
        console.log("Warning: Chord.noteOn did not receive midi numbers as expected!")
      }

      // circumstances
      let _transpose = this._transpose;
      let _sustain = this._sustain; // sustain pedal true or false

      // store these properties to check if they change
      const as_was = _.cloneDeep({
        _notes: this._notes,
        _unison_idx: this._unison_idx,
        _keys_down: this._keys_down
      });

      for (let i = 0, len = incoming.length; i < len; i++) {
        // take each midi number
        let noteNumber = incoming[i];
        if (_transpose) {
          noteNumber = this.transpose(noteNumber);
        }

        // deal with changes in the one possible unison placement
        const currently_on_notes = Object.entries(this._notes)
          .filter(([k, v]) => v === true)
          .map(([k, v]) => parseInt(k));
        if (this._notes[noteNumber] === true) {
          let latest_double_tap_idx = currently_on_notes.indexOf(noteNumber);
          if (this._unison_idx == latest_double_tap_idx) {
            this._unison_idx = null; // toggle off
          } else {
            this._unison_idx = latest_double_tap_idx;
          }
        } else if (this._unison_idx == null) {
        } else {
          let unison_idx = this._unison_idx;
          if (noteNumber < currently_on_notes[unison_idx]) {
            // a note must be added below the doubled note
            this._unison_idx += 1;
          }
        }
        this._notes[noteNumber] = true;
        this._keys_down[noteNumber] = true;
      }

      const as_is = {
        _notes: this._notes,
        _unison_idx: this._unison_idx,
        _keys_down: this._keys_down
      }

      this.trigger("change", "note:on");

      if (!_.isEqual(as_is, as_was)) {
        // console.log({is: as_is, was: as_was});
        return true;
      } else {
        return false;
      }
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
      let manually_dampen = false;
      if (_.isArray(notes)) {
        var outgoing = notes; // the midi numbers of notes that must be silenced
      } else if (Number.isInteger(notes)) {
        var outgoing = [notes];
      } else if (!_.isArray(notes) && typeof notes === "object") {
        var outgoing = notes.notes;
        if (notes.hasOwnProperty("manuallyDampen")) {
          manually_dampen = notes.manuallyDampen === true;
        }
      } else {
        var outgoing = [];
        console.log("Warning: Chord.noteOff did not receive midi numbers as expected!")
      }

      // circumstances
      var _transpose = this._transpose;
      var _sustain = this._sustain;

      // store these properties to check if they change
      const as_was = _.cloneDeep({
        _notes: this._notes,
        _unison_idx: this._unison_idx,
        _keys_down: this._keys_down
      });

      for (let i = 0, len = outgoing.length; i < len; i++) {
        // take each midi number
        let noteNumber = outgoing[i];
        if (_transpose) {
          noteNumber = this.transpose(noteNumber);
        }

        let to_be_silenced = false;
        if (_sustain) {
          if (manually_dampen) {
            this._manually_dampened.push(noteNumber);
            // this.broadcast(EVENTS.BROADCAST.NOTE, "off", noteNumber); // TO DO VEYSEL
            to_be_silenced = true;
          }
        }
        if (!_sustain) {
          to_be_silenced = true;
        }

        if (to_be_silenced) {
          // deal with changes in the one possible unison placement
          const currently_on_notes = Object.entries(this._notes)
            .filter(([k, v]) => v === true)
            .map(([k, v]) => parseInt(k));
          const doubled_note_num = currently_on_notes[this._unison_idx] || null;
          let unison_idx = this._unison_idx;
          if (doubled_note_num !== null) {
            if (doubled_note_num > noteNumber) {
              this._unison_idx += -1;
            } else if (doubled_note_num == noteNumber) {
              this._unison_idx = null; // toggle off
            } else { }
          }
          this._notes[noteNumber] = false;
        }

        this._keys_down[noteNumber] = false;
      }

      const as_is = {
        _notes: this._notes,
        _unison_idx: this._unison_idx,
        _keys_down: this._keys_down
      };

      this.trigger("change", "note:on");

      if (!_.isEqual(as_is, as_was)) {
        // console.log({is: as_is, was: as_was});
        return true;
      } else {
        return false;
      }
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
     * Synchronize the notes playing with those that are being sustained.
     *
     * @returns {boolean}
     */
    dropDampers: function (prev_notes = false) {
      this._manually_dampened = [];

      let notes_to_turn_off = [];

      const were_active = Object.keys(prev_notes).filter(function(key) {
        return prev_notes[key] // values are boolean
      });
      const _notes = this._notes;
      const are_active = Object.keys(_notes).filter(function(key) {
        return _notes[key]
      });
      const _keys_down = this._keys_down;
      const are_keys_down = Object.keys(_keys_down).filter(function(key) {
        return _keys_down[key] // does this actually mean that the keys are depressed?
      });

      let all_notes_on_radar = new Array(...new Set([
        were_active,
        are_active
      ].flat()))

      for (let i = 0; i < all_notes_on_radar.length; i++) {
        if (!are_keys_down.includes(all_notes_on_radar[i])) {
          notes_to_turn_off.push(all_notes_on_radar[i]);
          this._notes[all_notes_on_radar[i]] = false;
        }
      }
      this.trigger("change");

      return notes_to_turn_off;
    },
    /**
     * Whether the sustain pedal is depressed or not.
     *
     * @return {boolean}
     */
    dampersRaised: function () {
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

      this._notes = _.reduce( // TO DO: replicate this for _keys_down
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
    getTranspose: function () {
      return this._transpose;
    },
    /**
     * Copies the notes to another chord.
     * @return undefined
     */
    copy: function (chord) {
      const notes_false = Object.entries(chord._notes)
        .filter(([k, v]) => v === false)
        .map(([k, v]) => k);
      let notes_obj = {};
      for (let i = 0; i < notes_false.length; i++) {
        notes_obj[notes_false[i]] = false;
      }
      const keys_down_true = Object.entries(chord._keys_down)
        .filter(([k, v]) => v === true)
        .map(([k, v]) => k);
      let keys_down_obj = {};
      for (let i = 0; i < keys_down_true.length; i++) {
        keys_down_obj[keys_down_true[i]] = true;
        notes_obj[keys_down_true[i]] = true;
      }
      this.setTranspose(chord.getTranspose());
      this._sustain = chord.dampersRaised();
      this._notes = _.cloneDeep(notes_obj);
      this._keys_down = _.cloneDeep(keys_down_obj);
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
        if (
          STAFF_DISTRIBUTION == 'chorale' &&
          notes.length === 3 &&
          this._unison_idx === 1
        ) {
        } else if (
          ["keyboard", "keyboardPlusRHBias", "keyboardPlusLHBias"].includes(STAFF_DISTRIBUTION) &&
          VOICE_COUNT_FOR_KEYBOARD_STYLE.includes(notes.length) && notes.length != 2 &&
          this._unison_idx === 0
        ) {
        } else {
          notes.push(notes[this._unison_idx]) // length of notes may become an issue with rendering unisons
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
        // UNISONS
        if (this._unison_idx === 0) {
          return [["bass", "treble"], ["treble"]][midi <= high_threshold ? 0 : 1].includes(clef);
        } else {
          return clef == (midi <= high_threshold ? "bass" : "treble");
        }
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
