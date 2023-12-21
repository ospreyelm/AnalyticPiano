/* global define: false */
define([
  "jquery",
  "jquery-ui",
  "lodash",
  "vexflow",
  "app/config",
  "app/components/component",
  "app/utils/fontparser",
  "./stave",
  "./stave_notater",
  "./exercise_note_factory",
], function (
  $,
  $UI,
  _,
  Vex,
  Config,
  Component,
  FontParser,
  Stave,
  StaveNotater,
  ExerciseNoteFactory
) {
  "use strict";

  /**
   * Defines the size of the chord bank (how many chords to display on
   * screen).
   * @type {number}
   */
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  var SETTING_HIDE_NEXT = Config.get("general.hideNextForAutoAdvance");

  var NUMBERED_EXERCISE_COUNT = Config.get("general.numberedExerciseCount");

  /**
   * ExerciseSheetComponent
   *
   * This object is responsible for knowing how to display plain sheet music
   * notation with the notes that have sounded (saved in the chord bank) and
   * are currently sounding via MIDI input or some other means. So this object
   * should know how to display the grand staff and configure it for analysis,
   * highlight, etc.
   *
   * @constructor
   * @param {object} settings
   * @param {ChordBank} settings.chords Required property.
   * @param {KeySignature} settings.keySignature Required property.
   */
  var ExerciseSheetComponent = function (settings) {
    this.settings = settings || {};

    if ("exerciseContext" in this.settings) {
      this.exerciseContext = this.settings.exerciseContext;
    } else {
      throw new Error("Missing parameter property: .exerciseContext");
    }

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("Missing parameter property: .keySignature");
    }

    if ("timeSignature" in this.settings.exerciseContext) {
      this.timeSignature = this.settings.exerciseContext.timeSignature;
    } else {
      throw new Error("Missing parameter property: .timeSignature");
    }

    _.bindAll(this, ["render", "onChordsUpdate"]);
  };

  ExerciseSheetComponent.prototype = new Component();

  _.extend(ExerciseSheetComponent.prototype, {
    /**
     * Initializes the sheet.
     *
     * @param {object} config
     * @return undefined
     */
    initComponent: function () {
      this.el = $("canvas#staff");
      this.el[0].width = this.el.width();
      this.el[0].height = this.el.height();
      this.initRenderer();
      this.initStaves();
      this.initListeners();
    },
    /**
     * Initializes the canvas renderer and dom element.
     *
     * @return
     */
    initRenderer: function () {
      var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
      this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
      this.renderExerciseInfo();
      this.renderExerciseText();
    },
    /**
     * Initializes the staves that together will form the grand staff.
     *
     * @return undefined
     */
    initStaves: function () {
      this.updateStaves();
    },
    /**
     * Initializes event listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      this.parentComponent.bind("change", this.render);
      this.keySignature.bind("change", this.render);
      //this.getInputChords().bind('change', this.render);
      this.getInputChords().bind("change", this.onChordsUpdate);
      this.getInputChords().bind("clear", this.onChordsUpdate);
      this.exerciseContext.bind("goto", this.onGoToExercise);
    },
    /**
     * Renders the grand staff and everything on it.
     *
     * @return this
     */
    render: function (exercise_midi_nums = false) {
      this.clear();
      this.renderStaves(exercise_midi_nums);
      this.renderExerciseStatus();

      return this;
    },
    /**
     * Renders textual prompt for the exercise.
     *
     * @return this
     */
    renderExerciseStatus: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $statusEl = $("#exercise-status-and-tempo");
      var $passedEl = $("#passed-status");
      var statusTpl = _.template(
        // not called: time_to_complete and more
        `<p><span id="exercise-status" class="status-pill" style="background-color:<%= status_color %>"><%= status_text %></span></p>
                <% if (typeof(tempo_mean) !== "undefined" && tempo_mean != "" && typeof(tempo_rating) !== "undefined" && typeof(tempo_display_factor) !== "undefined") { %>
                    <p>Tempo&nbsp;<%= ["", "erratic", "unsteady", "steady", "very&nbsp;steady", "perfectly&nbsp;steady"][tempo_rating.length] %> at <%= Math.round(tempo_mean * tempo_display_factor) %>&nbsp;b.p.m.</p>
                <% } %>`
      );
      var passedTpl = `<span class="status-pill" id="exercise-passed-status">Exercise Passed</span>`;
      // the tempo verbiage above should match what is separately coded for my activity
      var html = "";
      var tpl_data = {};

      var status_map = {};
      status_map[exc.STATE.READY] = {
        text: "Ready",
        color: "#333333",
      };
      status_map[exc.STATE.WAITING] = {
        text: "Keep going",
        color: "#FF7F00",
      };
      status_map[exc.STATE.INCORRECT] = {
        text: "Fix the error",
        color: "#990000",
      };
      status_map[exc.STATE.FINISHED] = {
        text: "Go again",
        color: "#FFB700",
      };
      status_map[exc.STATE.CORRECT] = {
        text: "Passed",
        color: "#4C9900",
      };

      tpl_data.exercise_list = exc.definition.getExerciseList();
      tpl_data.exercise_num = tpl_data.exercise_list.reduce(function (
        selected,
        current,
        index
      ) {
        return selected < 0 && current.selected ? index + 1 : selected;
      },
      -1);
      tpl_data.status_text = status_map[exc.state].text;
      tpl_data.status_color = status_map[exc.state].color;

      $(".playlist-nav-links").css("display", "none");
      if ( // HOW DOES THIS WORK
        $("#playlist-passed-status").length == 0 &&
        definition.settings.definition.exerciseIsPerformed &&
        definition.settings.definition.exerciseErrorCount == 0
      ) {
        $passedEl.html(passedTpl);
      } else {
        $("#exercise-passed-status").hide();
      }
      switch (exc.state) {
        case exc.STATE.CORRECT:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
            tpl_data.tempo_display_factor = 1;
            try {
              // get beat information from time signature
              const time_sig = definition.exercise.timeSignature;
              const time_sig_numerator = Number(time_sig.split("/")[0]);
              let tempo_display_factor = Number(time_sig.split("/")[1]);
              if (time_sig_numerator > 3 && time_sig_numerator % 3 == 0) {
                // compound meter
                tempo_display_factor /= 3;
              }
              if (!isNaN(tempo_display_factor)) {
                tpl_data.tempo_display_factor = tempo_display_factor;
              }
            } catch (error) {
              console.log("Unable to retrieve beat value from time signature");
            }
          }
          // If this is the last exercise, display the nav links
          if (!this.exerciseContext.definition.exercise.nextExercise)
            $(".playlist-nav-links").css("display", "inline-flex");
          break;
        case exc.STATE.FINISHED:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
          }
          break;
        case exc.STATE.READY:
        default:
          break;
      }

      html = statusTpl(tpl_data);
      $statusEl.html(html);
      return this;
    },
    renderExerciseInfo: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $infoEl = $("#exercise-info");
      var tpl = _.template(
        `<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>
          <p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>
        <% } %>`
      );
      var html = "";
      var tpl_data = {};

      if (exc.definition.exercise.performing_course) {
        tpl_data.exercise_list = exc.definition.getExerciseList();
        tpl_data.exercise_num = 1;
        for (let i = 0; i < tpl_data.exercise_list.length; i++) {
          if (tpl_data.exercise_list[i].selected) {
            tpl_data.exercise_num = i + 1;
            break;
          }
        }
      } else {
        // get ID?
      }

      html = tpl(tpl_data);
      $infoEl.html(html);

      return this;
    },
    renderExerciseText: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $textEl = $("#exercise-text");
      var tpl = _.template(
        `<% if (typeof(prompt_text) == "string") { %>
                    <%= prompt_text %>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      // Parse the text for tokens that should use the figured bass font
      tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(
        exc.definition.getIntro()
      );

      html = tpl(tpl_data);
      $textEl.html(html);

      return this;
    },
    renderExerciseHistory: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $historyEl = $("#exercise-history");
      var tpl = _.template(
        `<% if (false && is_performed && typeof(latest_err_count) == "integer" && latest_err_count == 0) { %>
                    <p>PASSED on most recent attempt</p>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      $.ajax({
        type: "GET",
        url:
          window.location.origin +
          "/ajax" +
          window.location.pathname +
          "history/",
        async: false,
        success: function (response) {
          if (!response["valid"]) {
            var exerciseData = JSON.parse(response);
            tpl_data.is_performed = exerciseData.exerciseIsPerformed;
            tpl_data.latest_err_count = exerciseData.exerciseErrorCount;
          }
        },
        error: function (error) {
          alert("An error occurred while getting the exercise history.");
        },
      });

      html = tpl(tpl_data);
      $historyEl.html(html);

      return this;
    },
    /**
     * Clears the sheet.
     *
     * @return this
     */
    clear: function () {
      this.vexRenderer.getContext().clear();
      return this;
    },
    /**
     * Renders each individual stave.
     *
     * @return this
     */
    renderStaves: function (exercise_midi_nums = false) {
      const show_barlines = true;

      var i,
        len,
        stave,
        _staves = this.staves;
      var _barlines = this.barlines;
      for (i = 0, len = _staves.length; i < len; i++) {
        stave = _staves[i];
        const exercise_view_bool = true;
        const append_barline = _barlines.indexOf(i) != -1 && show_barlines;
        stave.render(exercise_midi_nums, exercise_view_bool, append_barline);
      }
      return this;
    },
    /**
     * Resets the staves.
     *
     * @return this
     */
    resetStaves: function () {
      this.staves = [];
      this.barlines = [];
      return this;
    },
    /**
     * Adds staves.
     *
     * @param {array} staves
     * @return this
     */
    addStaves: function (staves) {
      this.staves = this.staves.concat(staves);
      return this;
    },
    timeSignatureParsed: function (timeSignature) {
      if (!timeSignature) {
        return false;
      }
      let parsedSignature = timeSignature.split("/");
      if (parsedSignature.length != 2) {
        return false;
      }
      let topNum = parsedSignature[0].trim();
      let bottomNum = parsedSignature[1].trim();
      if (
        isNaN(topNum) ||
        isNaN(bottomNum) ||
        topNum != parseInt(topNum) ||
        bottomNum != parseInt(bottomNum)
      ) {
        return false;
      }
      return [topNum, bottomNum];
    },
    getsBarline: function (timeSignature = false, elapsedWholeNotes) {
      if (!elapsedWholeNotes > 0) {
        return false;
      }
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      return barCount == parseInt(barCount);
    },
    countElapsedBars: function (timeSignature = false, elapsedWholeNotes) {
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      return parseInt(barCount);
    },
    getBarRemainder: function (timeSignature = false, elapsedWholeNotes) {
      // not used
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      if (isNaN(barCount) || barCount < 0) {
        return null;
      }
      return barCount % 1;
    },
    getWholeNoteRemainder: function (timeSignature = false, elapsedWholeNotes) {
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      if (elapsedWholeNotes <= 0) {
        return 0;
      }
      const remainder = ((elapsedWholeNotes * ts[1]) % ts[0]) / ts[1];
      if (isNaN(remainder) || remainder < 0) {
        return null;
      }
      return remainder;
    },
    /**
     * Updates and configures the staves.
     *
     * @return this
     */
    updateStaves: function () {
      var chord, treble, bass;
      var limit = 100; // arbitrary
      let bankSize = CHORD_BANK_SIZE;
      try {
        const custom_chord_bank_size = parseInt(this.getSemibrevesPerLine());
        if (
          typeof custom_chord_bank_size === "number" &&
          custom_chord_bank_size > 0
        ) {
          bankSize = custom_chord_bank_size;
        }
      } catch {
        console.log(
          "Failed to retrieve getSemibrevesPerLine property from Exercise definion."
        );
      }
      var display_items = this.getDisplayChords().items({
        limit: limit,
        reverse: false,
      });
      var exercise_items = this.getExerciseChords().items({
        limit: limit,
        reverse: false,
      });
      var staves = [];
      var barlines = [];
      var index = 0;
      var offset = 0;
      var count = display_items.length;
      var position = {
        index: index,
        count: count,
        offset: offset,
        maxCount: bankSize,
      };
      var display_chord;
      var exercise_chord;
      var treble_activeAlterations = Object.create(null);
      var bass_activeAlterations = Object.create(null);
      const timeSignature = this.getTimeSignature();
      const barlineSpace = 0.25; // relative to width of whole note

      // scrolling exercise view
      var scroll_exercise = false;
      var pageturns = [0];

      let rhythmValues = display_items.map((item) => item.chord._rhythmValue);
      let availableSpace = bankSize;

      const endOfBarWholeNoteCounts = [];
      if (timeSignature) {
        const wholeNoteSum = rhythmValues
          .map((item) => this.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        const barCount = this.countElapsedBars(timeSignature, wholeNoteSum);
        const ts = this.timeSignatureParsed(timeSignature);
        for (var i = 1, len = barCount; i <= len; i++) {
          endOfBarWholeNoteCounts.push((i * ts[0]) / ts[1]);
        }
      }

      for (var i = 0, len = rhythmValues.length; i < len; i++) {
        let neededSpace = this.getVisualWidth(rhythmValues[i]);

        let elapsedWholeNotes = rhythmValues
          .slice(0, i + 1)
          .map((item) => this.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        if (endOfBarWholeNoteCounts.includes(elapsedWholeNotes)) {
          neededSpace += barlineSpace;
        }
        if (neededSpace > availableSpace) {
          availableSpace = bankSize - neededSpace; // overlap space
          pageturns.push(i);
          scroll_exercise = true;
        }
        availableSpace -= neededSpace;
      }

      let previous_whole_note_count = 0;
      if (scroll_exercise) {
        let cursor = this.getInputChords()._currentIndex;
        var page_start = pageturns
          .filter(function (x, idx) {
            return x <= cursor;
          })
          .pop();
        var next_page =
          pageturns.filter(function (x, idx) {
            return x > cursor;
          })[0] || false;
        if (page_start > 0) {
          // create overlap (start new page with completed chord)
          page_start -= 1;
          // next_page -= 1; //unwise
        }

        position.offset = page_start;
        const previous_items = display_items.slice(0, page_start);

        if (next_page) {
          display_items = display_items.slice(page_start, next_page);
          exercise_items = exercise_items.slice(page_start, next_page);
        } else {
          display_items = display_items.slice(page_start);
          exercise_items = exercise_items.slice(page_start);
        }

        for (var i = 0, len = previous_items.length; i < len; i++) {
          let rhythm_value = null;
          if (previous_items[i].chord.settings.rhythm) {
            rhythm_value = previous_items[i].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          previous_whole_note_count += this.getWholeNoteCount(rhythm_value);
        }
      }

      // The first bar is a special case: it's reserved to show the
      // clef and key signature and nothing else.
      let first_page = true;
      if (previous_whole_note_count > 0) {
        first_page = false;
      }
      treble = this.createDisplayStave("treble", _.clone(position), first_page);
      bass = this.createDisplayStave("bass", _.clone(position), first_page);
      position.index += 1;
      treble.connect(bass);
      staves.push(treble);

      var treble_alterationHistory = Object.create(null);
      var bass_alterationHistory = Object.create(null);

      // now add the staves for showing the notes
      for (var i = 0, len = display_items.length; i < len; i++) {
        let elapsedWidthUnits = 0;
        let elapsedWholeNotes = 0;
        let extraWidth = 0;
        for (var j = 0; j < i; j++) {
          var rhythm_value = null;
          if (display_items[j].chord.settings.rhythm) {
            rhythm_value = display_items[j].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          elapsedWidthUnits += this.getVisualWidth(rhythm_value);
          elapsedWholeNotes += this.getWholeNoteCount(rhythm_value);
        }

        // spacing for barlines
        const complement_of_first_bar = this.getWholeNoteRemainder(
          timeSignature,
          previous_whole_note_count
        );
        const elapsedBarlines = this.countElapsedBars(
          timeSignature,
          elapsedWholeNotes + complement_of_first_bar - 0.01
        );
        if (elapsedBarlines) {
          elapsedWidthUnits += barlineSpace * elapsedBarlines;
        }

        // now take account of previous music for proper barring
        elapsedWholeNotes += previous_whole_note_count;

        var curr_value = null;
        if (display_items[i].chord.settings.rhythm) {
          curr_value = display_items[i].chord.settings.rhythm;
        } else {
          curr_value = DEFAULT_RHYTHM_VALUE;
        }
        if (i < len) {
          if (this.getsBarline(timeSignature, elapsedWholeNotes)) {
            if (i > 0) {
              // new bar begins here but not new system
              // draw barline at left
              barlines.push(i + 1);
              // add space to left of barline
              elapsedWidthUnits += barlineSpace;
            }
            // RESET # n b
            treble_activeAlterations = Object.create(null);
            bass_activeAlterations = Object.create(null);
          }
          if (
            this.getsBarline(
              timeSignature,
              elapsedWholeNotes + this.getWholeNoteCount(curr_value)
            )
          ) {
            // bar is completed here: add space
            extraWidth += barlineSpace;
          }
        }

        treble_alterationHistory[i] = treble_activeAlterations;
        bass_alterationHistory[i] = bass_activeAlterations;

        display_chord = display_items[i].chord;
        exercise_chord = exercise_items[i].chord;
        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          treble_activeAlterations,
          extraWidth
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          bass_activeAlterations,
          extraWidth
        );
        position.index += 1;
        treble.connect(bass);
        staves.push(treble);

        let treble_merged = {
          ...treble_activeAlterations,
          ...treble.noteFactory.bequestAlterations,
        };
        let treble_cancellations = treble.noteFactory.bequestCancellations;
        for (let j = 0, len_j = treble_cancellations.length; j < len_j; j++) {
          delete treble_merged[treble_cancellations[j]];
        }
        treble_activeAlterations = treble_merged;

        let bass_merged = {
          ...bass_activeAlterations,
          ...bass.noteFactory.bequestAlterations,
        };
        let bass_cancellations = bass.noteFactory.bequestCancellations;
        for (let j = 0, len_j = bass_cancellations.length; j < len_j; j++) {
          delete bass_merged[bass_cancellations[j]];
        }
        bass_activeAlterations = bass_merged;
      }

      treble.noteFactory.alterationHistory = treble_alterationHistory;
      bass.noteFactory.alterationHistory = bass_alterationHistory;

      this.resetStaves();
      this.addStaves(staves);
      this.barlines = barlines;

      return this;
    },
    /**
     * Creates a stave to display the clef, key signature, etc.
     *
     * @param {string} clef
     * @param {object} position
     * @return {Stave}
     */
    createDisplayStave: function (clef, position, first_page = true) {
      var stave = new Stave(clef, position);
      var stave_notater = this.createStaveNotater(clef, {
        stave: stave,
        keySignature: this.keySignature,
        analyzeConfig: this.getAnalyzeConfig(),
      });

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      if (first_page && this.timeSignatureParsed(this.timeSignature)) {
        // console.log(this.timeSignatureParsed(this.timeSignature).join('/'));
        stave.setTimeSignature(
          this.timeSignatureParsed(this.timeSignature).join("/")
        );
      } else {
        stave.setTimeSignature(false);
      }
      stave.setNotater(stave_notater);
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          this.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePosition();

      return stave;
    },
    getVisualWidth: function (rhythm_value) {
      if (rhythm_value === "w") {
        return 1;
      } else if (rhythm_value === "W") {
        return 1.25;
      } else if (rhythm_value === "H") {
        return 0.75;
      } else if (rhythm_value === "h") {
        return 0.675;
      } else if (rhythm_value === "Q") {
        return 0.5;
      } else if (rhythm_value === "q") {
        return 0.375;
        // } else if (rhythm_value === "8") {
        //   return 0.25;
      } else {
        console.log("Unknown rhythm_value passed to getVisualWidth");
        return 1;
      }
    },
    getWholeNoteCount: function (rhythm_value) {
      if (rhythm_value === "w") {
        return 1;
      } else if (rhythm_value === "W") {
        return 1.5;
      } else if (rhythm_value === "H") {
        return 0.75;
      } else if (rhythm_value === "h") {
        return 0.5;
      } else if (rhythm_value === "Q") {
        return 0.375;
      } else if (rhythm_value === "q") {
        return 0.25;
      } else if (rhythm_value === "E") {
        return 0.1875;
      } else if (rhythm_value === "8") {
        return 0.125;
      } else {
        console.log("Unknown rhythm_value passed to getWholeNoteCount");
        return 0.1; // this will prevent display of bogus barlines
      }
    },
    /**
     * Creates a stave to display notes.
     *
     * @param {string} clef
     * @param {object} position
     * @param {Chord} chord
     * @return {Stave}
     */
    createNoteStave: function (
      clef,
      position,
      displayChord,
      exerciseChord,
      elapsedWidthUnits,
      activeAlterations,
      extraWidth = 0
    ) {
      var stave = new Stave(clef, position);
      var widthUnits = null;
      if (exerciseChord.settings.rhythm) {
        var rhythm_value = exerciseChord.settings.rhythm;
        if (rhythm_value == null) {
          rhythm_value = DEFAULT_RHYTHM_VALUE;
        }
        widthUnits = this.getVisualWidth(rhythm_value) + extraWidth;
      }

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      // timeSignature not required here
      // stave.setFirstBarWidth(this.keySignature);
      stave.setNoteFactory(
        new ExerciseNoteFactory({
          clef: clef,
          chord: displayChord,
          keySignature: this.keySignature,
          highlightConfig: this.getHighlightConfig(),
          activeAlterations: activeAlterations,
        })
      );
      stave.setNotater(
        this.createStaveNotater(clef, {
          stave: stave,
          chord: exerciseChord,
          keySignature: this.keySignature,
          analyzeConfig: this.getAnalyzeConfig(),
        })
      );
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          this.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePositionWithRhythm(widthUnits, elapsedWidthUnits);
      stave.updateAlterations(activeAlterations);

      return stave;
    },
    /**
     * Creates an instance of StaveNotater.
     *
     * @param {string} clef The clef, treble|bass, to create.
     * @param {object} config The config for the StaveNotater.
     * @return {object}
     */
    createStaveNotater: function (clef, config) {
      return StaveNotater.create(clef, config);
    },
    /**
     * Returns the width of the sheet.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.el.width();
    },
    /**
     * Returns the height of the sheet.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.el.height();
    },
    /**
     * Returns the analysis settings of the sheet.
     *
     * @return {object}
     */
    getAnalyzeConfig: function () {
      return this.parentComponent.analyzeConfig;
    },
    /**
     * Returns the highlight settings of the sheet.
     *
     * @return {object}
     */
    getHighlightConfig: function () {
      return this.parentComponent.highlightConfig;
    },
    /**
     * Returns the chords for display.
     *
     * @return undefined
     */
    getDisplayChords: function () {
      return this.exerciseContext.getDisplayChords();
    },
    /**
     * Returns the chords for exercise analysis.
     *
     * @return undefined
     */
    getExerciseChords: function () {
      return this.exerciseContext.getExerciseChords();
    },
    /**
     * Returns the time signature for display.
     *
     * @return undefined
     */
    getTimeSignature: function () {
      return this.exerciseContext.getTimeSignature();
    },
    /**
     * Obtain semibreves per line for horizontal scaling.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.exerciseContext.getSemibrevesPerLine();
    },
    /**
     * Returns the input chords.
     *
     * @return undefined
     */
    getInputChords: function () {
      return this.exerciseContext.getInputChords();
    },
    /**
     * Handles a chord bank update.
     *
     * @return undefined
     */
    onChordsUpdate: function () {
      this.updateStaves();
      this.render();
    },
    /**
     * Handles navigating to the next exercise.
     *
     * @return undefined
     */
    onGoToExercise: function (target) {
      window.location = target.url;
    },
  });

  return ExerciseSheetComponent;
});
