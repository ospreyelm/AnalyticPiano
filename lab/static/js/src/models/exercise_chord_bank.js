define(["lodash", "microevent", "./chord", "./chord_bank"], function (
  _,
  MicroEvent,
  Chord,
  ChordBank
) {
  var ExerciseChordBank = function (settings) {
    ChordBank.call(this, settings);
    this._currentIndex = 0;
    this._enableBanking = false;
  };

  ExerciseChordBank.prototype = new ChordBank();

  var proto = ExerciseChordBank.prototype;
  proto.init = function () {
    ChordBank.prototype.init.call(this);
  };

  proto.current = function () {
    return this._items[this._currentIndex];
  };

  proto.previous = function () {
    return this._items.length && this._items.length > 1
      ? this._items[this._currentIndex - 1]
      : false;
  };

  // Override superclass method to be a no-op
  proto.bank = function () {};

  // Go to a chord in the bank. Create one at that location if necessary.
  proto.goTo = function (index) {
    var current;
    if (index < 0 || index === this._currentIndex) {
      return this;
    }

    current = this.current();

    MAKE_NEW = !this._items[index];

    if (MAKE_NEW) {
      var chord = new Chord();
    }

    if (current) {
      // keep a hold of which keys are down
      const keys_down_true = Object.entries(current._keys_down)
        .filter(([k, v]) => v === true)
        .map(([k, v]) => k);
      var keys_down_obj = {};
      var notes_obj = {};
      for (let i = 0; i < keys_down_true.length; i++) {
        keys_down_obj[keys_down_true[i]] = true;
        notes_obj[keys_down_true[i]] = false;
        // if "true" these notes are received (however briefly) as errors for the next chord in the exercise
        // however, it is important to retain the object keys so that they can be passed to dropDampers()
      }
    }

    if (current && MAKE_NEW) {
      chord._sustain = current.dampersRaised();
      chord._keys_down = _.cloneDeep(keys_down_obj);
      chord._notes = _.cloneDeep(notes_obj);
    }

    if (current && !MAKE_NEW) {
      // not a current use case
    }

    if (MAKE_NEW) {
      this._items.splice(index, 1, chord);
    }

    if (current) {
      this._removeListeners(current);
    }

    this._addListeners(this._items[index]);
    this._currentIndex = index;

    return this;
  };

  return ExerciseChordBank;
});
