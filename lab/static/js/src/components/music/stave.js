/* global define: false */
define(["lodash", "microevent", "vexflow"], function (_, MicroEvent, Vex) {
  "use strict";

  /**
   * Creates an instance of a Stave.
   *
   * A stave represents the view of a single bar of a stave. A stave may be
   * associated with either the treble or bass clef and this determines its
   * vertical position. Since the treble and bass staves need to be aligned, a
   * treble stave should know how to connect with a bass stave in order to
   * keep their positions in sync.
   *
   * To visualize how the staves are intended to organized:
   *
   * Treble clef: [Stave][Stave][Stave][Stave]...
   *                 |     |      |      |
   * Connected:      |     |      |      |
   *                 V     V      V      V
   * Bass clef:   [Stave][Stave][Stave][Stave]
   *
   * This object collaborates closely with KeySignature, StaveNotater, and
   * StaveNoteFactory. It delegates the responsibility to generate notes to
   * the StaveNoteFactory and to notate/annotate the stave to the
   * StaveNotater.
   *
   * @constructor
   * @param {string} clef
   * @param {object} position
   */
  var Stave = function (clef, position) {
    /**
     * The clef this measure is associated with (treble or bass).
     * @type {string}
     * @return
     */
    this.clef = "";
    /**
     * The starting X position of the measure.
     * @type {number}
     */
    this.start_x = 0;
    /**
     * The starting Y position of the measure.
     * @type {number}
     */
    this.start_y = 0;
    /**
     * The maximum width of the measure.
     * @type {number}
     */
    this.maxWidth = null;
    /**
     * The position of the measure in a series of measures.
     * @type {object}
     */
    this.position = { index: 0, count: 0 };
    /**
     * True if the measure is considered "banked" or false if not.
     * @type {boolean}
     */
    this._isBanked = false;
    /**
     * Tracker for whether active chord is novel.
     * @type {boolean}
     */
    this._isNovel = true;

    var getUrlVars = function () {
      var vars = {};
      var parts = window.location.href.replace(
        /[?&]+([^=&]+)=([^&]*)/gi,
        function (m, key, value) {
          vars[key] = value;
        }
      );
      return vars;
    };
    // console.log('URL variables', getUrlVars());

    this.showDiagram =
      getUrlVars().hasOwnProperty("diagram") &&
      getUrlVars()["diagram"] === "true"
        ? true
        : false;

    _.bindAll(this, ["onNotated"]);

    this.init(clef, position);
  };

  _.extend(Stave.prototype, {
    /**
     * The width of the first stave bar in a sequence of staves.
     * This is a special case since the first stave should be reserved for
     * displaying the clef symbol and key signature, but no notes.
     * @type {number}
     */
    firstBarWidth: 90 /* should vary with key signature */,
    /**
     * The default width of a stave.
     * @type {number}
     */
    defaultBarWidth: 80,
    /**
     * The margins for the stave.
     * @type {number}
     */
    margin: { left: 20, right: 1 },
    /**
     * Initializes the Stave.
     *
     * @param {string} clef treble|bass
     * @param {object} position
     * @return undefined
     */
    init: function (clef, position) {
      if (!clef || !position) {
        throw new Error("missing stave clef or position");
      }
      if (!this.validatePosition(position)) {
        throw new Error("missing or invalid stave position");
      }

      this.clef = clef;
      this.position = position;
      if (this.showDiagram) {
        this.margin["left"] = 80;
      }
    },
    /**
     * Validates the position of the stave.
     *
     * @param {object} position
     * @param {object} position.index The index of the stave in a sequence.
     * @param {object} position.count A count of the staves in the sequence.
     * @param {object} position.maxCount The maximum number of staves that
     * may be displayed.
     * @return {boolean} True if the position is valid, false otherwise.
     */
    validatePosition: function (position) {
      var intRe = /^\d+$/;
      var numRe = /^[.\d]+$/;
      /* a decimal has no impact at the moment */
      /* if it did, the impact might be bad and restoring integer validation may be good */

      if (
        !position.hasOwnProperty("index") ||
        !position.hasOwnProperty("count") ||
        !position.hasOwnProperty("maxCount") ||
        !intRe.test(position.index) ||
        !intRe.test(position.count) ||
        !numRe.test(position.maxCount)
      ) {
        return false;
      }

      // ensure the maximum number of bars is nonzero
      // since we must display at least one stave bar
      if (position.maxCount === 0) {
        return false;
      }

      return true;
    },
    /**
     * Prepares for rendering.
     *
     * @return this
     */
    prepareForRender: function (append_barline = false) {
      this.createStaveBar(append_barline);
      this.createStaveVoice();
      return this;
    },
    /**
     * Renders the stave.
     *
     * @return this
     */
    render: function (
      exercise_midi_nums = false,
      exercise_view_bool = false,
      append_barline = false
    ) {
      if (!this.isConnected()) {
        return;
      }
      this.prepareForRender(append_barline);
      this.doConnected("prepareForRender", append_barline);

      this.formatStaveVoices();

      this.drawStaveVoice();
      this.drawLowVoice();
      this.doConnected("drawStaveVoice");
      this.doConnected("drawLowVoice");
      this.drawStaveBar();
      this.doConnected("drawStaveBar");

      this.renderStaveConnector(exercise_view_bool, append_barline);

      this.notate();
      this.doConnected("notate", exercise_midi_nums); // pass variable to bass staff

      return this;
    },
    /**
     * Renders the connected stave (if any).
     *
     * @return this
     */
    renderConnected: function () {
      return this.doConnected("render");
    },
    /**
     * Renders the system line and brace.
     *
     * @return this
     */
    renderStaveConnector: function (
      exercise_view_bool = false,
      append_barline = false
    ) {
      if (this.isFirstBar()) this.drawBeginStaveConnector();
      if (this.isLastBar() && exercise_view_bool) this.drawEndStaveConnector();
      if (append_barline && !this.isFirstBar()) {
        this.drawBarline();
      }
      return this;
    },
    /**
     * Draws a connector at the beginning of the stave.
     *
     * @return undefined
     */
    drawBeginStaveConnector: function () {
      var systemLine = Vex.Flow.StaveConnector.type.SINGLE_LEFT;
      if (Vex.Version && Vex.Version == "old") {
        var systemLine = Vex.Flow.StaveConnector.type.SINGLE;
      }
      var BRACE = Vex.Flow.StaveConnector.type.BRACE;
      var staff1 = this.getStaveBar();
      var staff2 = this.connectedStave.getStaveBar();
      this.drawStaveConnector(staff1, staff2, systemLine);
      this.drawStaveConnector(staff1, staff2, BRACE);
    },
    /**
     * Draws a connector at the end of the stave.
     *
     * @return undefined
     */
    drawEndStaveConnector: function () {
      let next_x = this.start_x + this.width; // RIGHT-HAND SIDE
      let treble_y = this.getYForClef("treble");
      let bass_y = this.getYForClef("bass");
      var staff1 = new Vex.Flow.Stave(next_x, treble_y, -1);
      var staff2 = new Vex.Flow.Stave(next_x, bass_y, -1);

      let ctx = this.getContext();
      staff1.setContext(ctx);
      staff2.setContext(ctx);

      var finishLine = Vex.Flow.StaveConnector.type.THIN_DOUBLE;
      if (Vex.Version && Vex.Version == "old") {
        var finishLine = Vex.Flow.StaveConnector.type.SINGLE;
        let staff1 = new Vex.Flow.Stave(next_x - 3, treble_y, -1);
        let staff2 = new Vex.Flow.Stave(next_x - 3, bass_y, -1);
        this.drawStaveConnector(staff1, staff2, finishLine);
      }
      this.drawStaveConnector(staff1, staff2, finishLine);
    },
    drawBarline: function () {
      let x_pos = this.start_x; // LEFT-HAND SIDE
      let treble_y = this.getYForClef("treble");
      let bass_y = this.getYForClef("bass");
      var staff1 = new Vex.Flow.Stave(x_pos, treble_y, -1);
      var staff2 = new Vex.Flow.Stave(x_pos, bass_y, -1);

      if (Vex.Version && Vex.Version == "old") {
        staff1 = new Vex.Flow.Stave(x_pos - 3, treble_y, -1);
        staff2 = new Vex.Flow.Stave(x_pos - 3, bass_y, -1);
      }

      let ctx = this.getContext();
      staff1.setContext(ctx);
      staff2.setContext(ctx);

      var barline_type = Vex.Flow.StaveConnector.type.SINGLE;
      this.drawStaveConnector(staff1, staff2, barline_type);
    },
    /**
     * Draws a stave connector between two staves.
     *
     * @param {Stave} staff1
     * @param {Stave} staff2
     * @param connectorType
     * @return undefined
     */
    drawStaveConnector: function (staff1, staff2, connectorType) {
      var ctx = this.getContext();
      var connector = new Vex.Flow.StaveConnector(staff1, staff2);
      connector.setContext(ctx).setType(connectorType).draw();
    },
    /**
     * Creates the Vex.Flow.Stave including barlines.
     *
     * @return undefined
     */
    createStaveBar: function (append_barline = false) {
      const barlines_on_staves = false; // in addition to barlines through both staves
      var x = this.start_x;
      var y = this.start_y;
      var width = this.width + 0; // +1 to prevent gaps from rounding errors
      /* manipulating the above setting reveals that new Vexflow is
       * rendering the staff lines with transparency */
      let style = { num_lines: 5, fill_style: "rgba(0, 0, 0, 1)" };
      var staffSegment = new Vex.Flow.Stave(x, y, width, style);

      /**
       * To show barlines, call Vex.Flow.Barline.type.SINGLE
       * unless isFirstBar (this is used for clef and staff signature
       * display).
       */
      staffSegment.setBegBarType(Vex.Flow.Barline.type.NONE);
      staffSegment.setEndBarType(Vex.Flow.Barline.type.NONE);
      if (append_barline && barlines_on_staves && !this.isFirstBar()) {
        staffSegment.setEndBarType(Vex.Flow.Barline.type.SINGLE);
      }
      // useful conditions:
      // this.isFirstBar(), this.isPenultimateBar(), this.isLastBar()

      staffSegment.clef = this.clef;
      staffSegment.setContext(this.getContext());
      if (this.isFirstBar()) {
        staffSegment.addClef(this.clef);
        staffSegment.addKeySignature(this.keySignature.getVexKey());
        if (this.timeSignature) {
          staffSegment.addTimeSignature(this.timeSignature);
        }
      }

      this.staffSegment = staffSegment;
    },
    /**
     * Creates the Vex.Flow.Voice.
     * This is where we add the notes.
     *
     * @return undefined
     */
    createStaveVoice: function () {
      var voice, formatter, time;
      if (!this.hasStaveNotes()) {
        this.staveVoice = voice;
        this.lowVoice = voice; // without this, the alto bass notes stuck on the sheet music
        return;
      }

      /**
       * Meter defined here on basis of rhythm value.
       * Follows exercise definition.
       */
      var rhythm_value = this.noteFactory.getRhythmValue();
      if (rhythm_value == null) {
        rhythm_value = DEFAULT_RHYTHM_VALUE;
      }
      if (rhythm_value === "w") {
        time = {
          num_beats: 4,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      } else if (rhythm_value === "W") {
        time = {
          num_beats: 6,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      } else if (rhythm_value === "H") {
        time = {
          num_beats: 3,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      } else if (rhythm_value === "h") {
        time = {
          num_beats: 2,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      } else if (rhythm_value === "Q") {
        time = {
          num_beats: 1.5,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      } else if (rhythm_value === "q") {
        time = {
          num_beats: 1,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      // } else if (rhythm_value === "8") {
      //   time = {
      //     num_beats: 0.5,
      //     beat_value: 4,
      //     resolution: Vex.Flow.RESOLUTION,
      //   };
      } else {
        // should be redundant
        time = {
          num_beats: 4,
          beat_value: 4,
          resolution: Vex.Flow.RESOLUTION,
        };
      }

      const create = this.createStaveNotes();

      if (create.length == 2) { // chorale format
        var low_voice, high_voice;
        low_voice = new Vex.Flow.Voice(time);
        high_voice = new Vex.Flow.Voice(time);
        low_voice.addTickables([create[0]]);
        high_voice.addTickables([create[1]]);
        this.staveVoice = high_voice;
        this.lowVoice = low_voice;
      } else {
        var voice;
        voice = new Vex.Flow.Voice(time);
        voice.addTickables(create);
        this.staveVoice = voice;
      }
    },
    /**
     * Format the Vex.Flow.Voice.
     *
     * @return undefined
     */
    formatStaveVoices: function () {
      let top_staff = [];
      const soprano_or_top_staff = this.staveVoice || false;
      const alto = this.lowVoice || false;
      if (soprano_or_top_staff) {
        top_staff.push(soprano_or_top_staff);
      }
      if (alto) {
        top_staff.push(alto);
      }

      let bottom_staff = [];
      const tenor_or_bottom_staff = this.getConnected().getStaveVoice() || false;
      const bass = this.getConnected().getLowVoice() || false;
      if (tenor_or_bottom_staff) {
        bottom_staff.push(tenor_or_bottom_staff);
      }
      if (bass) {
        bottom_staff.push(bass);
      }

      var formatter = new Vex.Flow.Formatter();
      if (top_staff.length > 0) {
        formatter.joinVoices(top_staff); // causes havoc ... why?
        formatter.formatToStave(top_staff, this.staffSegment);
      }
      if (bottom_staff.length > 0) {
        formatter.joinVoices(bottom_staff); // causes havoc ... why?
        formatter.formatToStave(bottom_staff, this.staffSegment);
      }
    },
    /**
     * Draws the Vex.Flow.Voice on the Stave.
     *
     * @return undefined
     */
    drawStaveVoice: function () {
      if (this.staveVoice) {
        this.staveVoice.draw(this.getContext(), this.staffSegment);
      }
    },
    drawLowVoice: function () {
      if (this.lowVoice) {
        this.lowVoice.draw(this.getContext(), this.staffSegment);
      }
    },
    /**
     * Draws the Stave.
     *
     * @return undefined
     */
    drawStaveBar: function () {
      var ctx = this.getContext();
      this.staffSegment.draw(ctx);
    },
    /**
     * Notates the Stave. Delegates this responsibility
     * to the StaveNotater.
     *
     * @return undefined
     */
    notate: function (exercise_midi_nums = false) {
      if (this.notater) {
        this.notater.notate(exercise_midi_nums);
      }
    },
    /**
     * Sets the starting X position.
     *
     * Note: executes this on the connected stave.
     *
     * @param {number} x
     * @return undefined
     */
    setStartX: function (x) {
      this.start_x = x;
      this.doConnected("setStartX", x);
    },
    /**
     * Sets the maximum width of the stave.
     *
     * Note: executes this on the connected stave.
     *
     * @param {number} w
     * @return undefined
     */
    setMaxWidth: function (w) {
      this.maxWidth = w;
      this.doConnected("setMaxWidth", w);
    },
    /**
     * Sets the width of the stave.
     *
     * Note: executes this on the connected stave.
     *
     * @param {number} w
     * @return undefined
     */
    setWidth: function (w) {
      this.width = w;
      this.doConnected("setWidth", w);
    },
    /**
     * Sets the StaveNoteFactory used to generate the notes that are
     * displayed on the stave.
     *
     * @param {StaveNoteFactory} noteFactory
     * @return undefined
     */
    setNoteFactory: function (noteFactory) {
      this.noteFactory = noteFactory;
    },
    /**
     * Sets the notater used to notate the stave.
     *
     * @param {StaveNotater} notater
     * @return undefined
     */
    setNotater: function (notater) {
      this.notater = notater;
      if (this.notater) {
        this.notater.bind("notated", this.onNotated);
      }
    },
    /**
     * Connects this stave to another.
     *
     * There are some methods on the stave that automatically delegate to
     * the stave they are connected to, particularly with regard to layout
     * and sizing.
     *
     * @param {Stave} stave
     * @return undefined
     */
    connect: function (stave) {
      this.connectedStave = stave;
    },
    /**
     * Returns true if this stave is connected to another, false otherwise.
     *
     * @return {boolean}
     */
    isConnected: function () {
      return this.connectedStave ? true : false;
    },
    /**
     * Executes a method on the connected stave.
     *
     * @param {string} method
     * @return {mixed} Will return undefined if not connected, otherwise it
     * returns the value of the executed method.
     */
    doConnected: function (method) {
      var args = Array.prototype.slice.call(arguments, 1);
      if (this.isConnected()) {
        return this.connectedStave[method].apply(this.connectedStave, args);
      }
      return;
    },
    /**
     * Returns the connected stave.
     *
     * @return {Stave}
     */
    getConnected: function () {
      return this.connectedStave;
    },
    /**
     * Returns the width of the stave.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.width;
    },
    /**
     * Returns the height of the stave.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.height;
    },
    /**
     * Returns the underlying Vex.Flow.Stave object.
     *
     * @return {object}
     */
    getStaveBar: function () {
      return this.staffSegment;
    },
    /**
     * Returns the underlying Vex.Flow.Voice object.
     *
     * @return {object}
     */
    getStaveVoice: function () {
      return this.staveVoice;
    },
    getLowVoice: function () {
      return this.lowVoice;
    },
    getStaffSegment: function () {
      return this.staffSegment;
    },
    /**
     * Returns the clef associated with the stave.
     *
     * @return {string}
     */
    getClef: function () {
      return this.clef;
    },
    /**
     * Returns the starting X position.
     *
     * @return
     */
    getStartX: function () {
      return this.start_x;
    },
    /**
     * Returns the top Y position of the stave.
     *
     * @return {number}
     */
    getTopY: function () {
      return this.staffSegment.getYForTopText();
    },
    /**
     * Returns the bottom Y position of the stave.
     *
     * @return {number}
     */
    getBottomY: function () {
      return this.staffSegment.getBottomY();
    },
    /**
     * Returns the canvas rendering context used by the Vex.Flow renderer.
     *
     * @return
     */
    getContext: function () {
      return this.vexRenderer.getContext();
    },
    /**
     * Creates stave notes to display on the stave. Delegates this
     * responsibility to the StaveNoteFactory.
     *
     * @return {array}
     */
    createStaveNotes: function (duration = undefined) {
      if (this.noteFactory) {
        return this.noteFactory.createStaveNotes(duration);
      }
      return [];
    },
    /**
     * Returns true if the stave has any notes, false otherwise.
     *
     * @return {boolean}
     */
    hasStaveNotes: function () {
      if (this.noteFactory) {
        return this.noteFactory.hasStaveNotes();
      }
      return false;
    },
    /**
     * Sets the key signature for the stave.
     *
     * @param {KeySignature} keySignature
     * @return undefined
     */
    setKeySignature: function (keySignature) {
      this.keySignature = keySignature;
    },
    setTimeSignature: function (timeSignature) {
      this.timeSignature = timeSignature;
    },
    setFirstBarWidth: function (staffSig, minimum = 0, hasTimeSig = false) {
      const minimize_movement = false;
      const length = Math.max(staffSig.length, minimum);

      let firstBarWidth = 65;

      if (hasTimeSig == true) {
        firstBarWidth += 15;
      }

      if (minimize_movement) {
        firstBarWidth += 40;
        if (length > 4) {
          firstBarWidth += 25;
        }
      } else {
        firstBarWidth += 9 * length;
        if (staffSig[0] === "#") {
          firstBarWidth += 1 * length;
        }
      }
      this.firstBarWidth = firstBarWidth;
    },
    /**
     * Sets the Vex.Flow renderer.
     *
     * @param renderer
     * @return undefined
     */
    setRenderer: function (renderer) {
      this.vexRenderer = renderer;
    },
    /**
     * Updates the position of the stave.
     *
     * This will have the side effect of modifying  the starting X and Y
     * positions as well as the width of the stave.
     *
     * @return undefined
     */
    updatePosition: function () {
      var start_x, width;

      if (this.isFirstBar()) {
        this.start_x = this.margin.left;
        this.width = this.firstBarWidth;
      } else {
        start_x = this.margin.left + this.firstBarWidth;
        width = Math.floor((this.maxWidth - start_x) / this.position.maxCount);
        start_x += (this.position.index - 1) * width;

        this.start_x = start_x;

        const stretch = true;
        if (this.isLastBar() && stretch) {
          this.width = this.maxWidth - this.start_x - this.margin.right;
        } else {
          this.width = width;
        }
      }

      this.start_y = this.getYForClef(this.clef);
    },
    /**
     * Updates the position of the stave.
     *
     * This will have the side effect of modifying  the starting X and Y
     * positions as well as the width of the stave.
     *
     * @return undefined
     */
    updatePositionWithRhythm: function (widthUnits, elapsedWidthUnits) {
      if (this.isFirstBar()) {
        this.start_x = this.margin.left;
        this.width = this.firstBarWidth;
      } else {
        // const avoid_gaps = false; // rounding errors
        var start_x = this.margin.left + this.firstBarWidth;
        const last_bar_buffer = 15;
        const flex_width = Math.floor(
          (this.maxWidth - start_x - last_bar_buffer) / this.position.maxCount
        );

        const basic_width = flex_width - ((flex_width + 8) % 1);

        var width = basic_width;
        if (widthUnits != null && !isNaN(widthUnits)) {
          width = basic_width * widthUnits;
        }

        start_x += basic_width * elapsedWidthUnits;

        this.start_x = start_x;

        const stretch = false;
        if (this.isLastBar() && stretch) {
          this.width = this.maxWidth - this.start_x - this.margin.right;
        } else if (this.isLastBar()) {
          this.width = width + last_bar_buffer;
        } else {
          this.width = width;
        }
      }

      this.start_y = this.getYForClef(this.clef);
    },
    updateAlterations: function (activeAlterations = Object.create(null)) {
      let factory = this.noteFactory.staveNoteFactory;

      var keys = factory.getNoteKeys();
      var alterations = factory.isolateChromatics(keys);

      let merged = { ...activeAlterations, ...alterations };

      var cancellations = factory.getCancellations(keys, activeAlterations);
      this.noteFactory.bequestCancellations = factory.getCancellations(
        keys,
        activeAlterations
      );

      for (var i = 0, len = cancellations.length; i < len; i++) {
        delete merged[cancellations[i]];
      }

      this.noteFactory.bequestAlterations = merged;
    },
    /**
     * Returns the vertical Y position associated with the given clef.
     *
     * @param {string} clef treble|bass
     * @return {number}
     */
    getYForClef: function (clef) {
      let chorale_format_bool = true; // pass this in somehow
      /**
       * Adjust vertical spacing here. For searching: distance, separation of staves
       */
      // Should not be less than 2 in order to honor the promises about legibility
      // for different staff distributions.
      // TO DO: MAKE THIS AN OPTION FOR EXERCISES
      const staff_separation_factor = chorale_format_bool ? 2.4 : 2;
      return (clef === "treble" ? 0 : 40 * staff_separation_factor) + 55;
    },
    /**
     * Returns true if this stave is the first bar in the sequence, false
     * otherwise.
     *
     * @return {boolean}
     */
    isFirstBar: function () {
      return this.position.index === 0;
    },
    /**
     * Returns true if this stave is the last bar in the sequence, false
     * otherwise.
     *
     * @return {boolean}
     */
    isPenultimateBar: function () {
      return this.position.index === this.position.count - 1;
    },
    /**
     * Returns true if this stave is the last bar in the sequence, false
     * otherwise.
     *
     * @return {boolean}
     */
    isLastBar: function () {
      return (
        this.position.index +
          (this.position.offset ? this.position.offset : 0) ===
        this.position.count
      );
    },
    /**
     * Sets the status of this stave as "banked" or not.
     *
     * @param {boolean} state
     * @return undefined
     */
    setBanked: function (state) {
      this._isBanked = state ? true : false;
    },
    /**
     * Returns true if the stave is banked or not.
     *
     * @return {boolean}
     */
    isBanked: function () {
      return this._isBanked;
    },
    /**
     * Sets the status of this stave as novel or not.
     *
     * @param {boolean} state
     * @return undefined
     */
    setNovel: function (state) {
      this._isNovel = state ? true : false;
    },
    /**
     * Returns true if the stave is novel or not.
     *
     * @return {boolean}
     */
    isNovel: function () {
      return this._isNovel;
    },
    /**
     * Handles a "notated" event.
     *
     * @fires notated
     *
     * @return undefined
     */
    onNotated: function (notater) {
      this.trigger("notated", notater);
    },
    /**
     * Destroys the stave.
     */
    destroy: function () {
      if (this.notater) {
        this.notater.unbind("notated", this.onNotated);
      }
    },
  });

  MicroEvent.mixin(Stave);

  return Stave;
});
