/* global define: false */
define([
  "lodash",
  "vexflow",
  "microevent",
  "app/config" /* only for declaring MASK_TREBLE */,
  "app/util",
  "app/utils/analyze",
  "app/utils/fontparser",
], function (
  _,
  Vex,
  MicroEvent,
  Config /* only for declaring MASK_TREBLE */,
  util,
  Analyze,
  FontParser
) {
  "use strict";

  /* hack for bass staff only added 2020 */
  /* not ready: also masks thoroughbass figures */
  var MASK_TREBLE = Config.get("general.maskTrebleStaff");

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

  var SHOW_DIAGRAM =
    getUrlVars().hasOwnProperty("diagram") && getUrlVars()["diagram"] === "true"
      ? true
      : false;

  /**
   * Defines an image of a metronome that may be rendered to a canvas element.
   * @type {Image}
   * @const
   */
  /*var METRONOME_IMG = (function() {
		var img = new Image();
		img.src = util.staticUrl('img/filename.png');
		return img;
	})();*/

  var PRELOADED_FONT = {};

  /**
   * This is an abstract class that defines the interface for the
   * StaveNotater.
   *
   * This abstract class should provide methods to notate the following types
   * of things:
   *
   * - Note names
   * - Solfege pitch notation
   * - Helmholtz pitch notation
   * - Scale degrees
   * - Intervals (with wrapping options)
   * - Generic intervals (with wrapping options)
   * - Roman numeral analysis
   *
   * At its simplest, a Stave should configure the notater with the kinds of
   * things it wants notated, passing a reference to itself, and then call the
   * notate() method to render those things on the stave.
   *
   * @constructor
   */
  var StaveNotater = function () {};

  StaveNotater.BASS = "bass";
  StaveNotater.TREBLE = "treble";

  _.extend(StaveNotater.prototype, {
    /**
     * Defines the margin for rendering things above and below the system.
     * @type {object}
     */
  margin: { top: 50, bottom: 10 },
    /**
     * Defines the text limit used to wrap text.
     * @type {number}
     */
    textLimit: 15,
    /**
     * Defines the height of a line of text.
     * @type {number}
     */
    textLineHeight: 18,
    /**
     * Defines the default font size.
     * @type {string}
     */
    defaultFontSize: "24px",
    /**
     * Defines a horizontal offset for use with all analytical annotations.
     */
    annotateOffsetX: 8,
    /*
     * Remembers prior Roman numerals
     */
    romanNumeralsHistory: Object.create(null),
    romanNumeralsExpHistory: Object.create(null),
    /**
     * Initializes the notater.
     *
     * @param {object} config
     * @param {Stave} config.stave
     * @param {KeySignature} config.keySignature
     * @param {object} config.analyzeConfig
     * @return undefined
     */
    init: function (config) {
      this.config = config;
      this.initConfig();
      _.bindAll(this, "drawMetronomeMark");
    },
    /**
     * Initializes the config
     *
     * @return undefined
     * @throws {Error} Will throw an error if a config param is missing.
     */
    initConfig: function () {
      var required = ["stave", "keySignature", "analyzeConfig"];
      _.each(
        required,
        function (propName) {
          if (this.config.hasOwnProperty(propName)) {
            this[propName] = this.config[propName];
          } else {
            throw new Error("missing required config property: " + propName);
          }
        },
        this
      );

      // optional
      if (this.config.hasOwnProperty("chord")) {
        this.chord = this.config.chord;
      }
    },
    /**
     * Notates the Stave if the notater is enabled.
     *
     * @fires notated
     * @return undefined
     */
    notate: function (exercise_midi_nums = false) {
      var ctx = this.getContext();

      ctx.save();
      ctx.font = this.getTextFont();

      this.notateStave();

      if (this.isAnalyzerEnabled()) {
        this.updateAnalyzer();
        if (this.chord) {
          this.drawLabel(exercise_midi_nums);
        }
      }

      ctx.restore();

      this.trigger("notated", this);
    },
    /**
     * Creates an analyzer object used to return analysis information about
     * what is being played.
     *
     * @return {Analyze}
     */
    createAnalyzer: function () {
      return new Analyze(this.keySignature);
    },
    /**
     * Updates the analyzer object.
     *
     * @return undefined
     */
    updateAnalyzer: function () {
      this.analyzer = this.createAnalyzer();
    },
    /**
     * Returns the analyzer object.
     *
     * @return {Analyze}
     */
    getAnalyzer: function () {
      return this.analyzer;
    },
    /**
     * Returns the canvas rendering context.
     *
     * @return {object}
     */
    getContext: function () {
      return this.stave.getContext();
    },
    /**
     * Returns the font for annotations.
     *
     * @return {string}
     */
    getTextFont: function (size) {
      if (!size) {
        size = this.defaultFontSize;
      }
      return size + " 'MainSerifs'";
    },
    /**
     * Returns the font for rendering icons.
     *
     * @return {string}
     */
    getIconFont: function (size) {
      if (!size) {
        size = this.defaultFontSize;
      }
      return size + " Ionicons";
    },
    /**
     * Returns the font for rendering figured bass.
     *
     * @return {string}
     */
    getFiguredBassFont: function (size = "32px") {
      return size + " Sebastian";
    },
    /**
     * Preload font if it hasn't already been loaded by the browser, so
     * it's available to Canvas when needed.
     *
     * This is mostly used for loading the figured bass font "Sebastian"
     * because the first time the canvas context font is set to "Sebastian",
     * it won't render properly because it takes time to load the font, but
     * canvas must render immediately. This fixes the issue where the first
     * time the font is used, it doesn't work.
     *
     * @return undefined
     */
    preloadFont: function (fontFamily) {
      if (PRELOADED_FONT[fontFamily]) {
        return;
      }
      var div = document.createElement("div");
      div.style.fontFamily = fontFamily;
      div.innerHTML = "&nbsp;"; // doesn't seem to load the font without some text
      document.getElementsByTagName("body")[0].appendChild(div);
      PRELOADED_FONT[fontFamily] = true;
    },
    /**
     * Returns the X position for notating.
     *
     * @return {number}
     */
    getX: function () {
      return this.stave.getStartX() + 10;
    },
    /**
     * Returns the Y position for notating.
     *
     * @abstract
     * @return {number}
     */
    getY: function () {
      throw new Error("subclass responsibility");
    },
    /**
     * Returns the current tempo of the metronome.
     *
     * @return {number}
     */
    getTempo: function () {
      return this.analyzeConfig.tempo;
    },
    /**
     * Returns true if analysis is enabled, false otherwise.
     *
     * @return {boolean}
     */
    isAnalyzerEnabled: function () {
      return this.analyzeConfig.enabled;
    },
    /**
     * Draws the note name.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    /* FIX ME: the next four functions are nearly identical; consolidate them */
    drawNoteName: function (x, y) {
      var notes = this.chord.getNoteNumbers();

      var note_name = this.getAnalyzer().to_note_name(notes);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (note_name !== "" && notes.length >= 1) {
        ctx.fillText(note_name, x + StaveNotater.prototype.annotateOffsetX, y);
      }
    },
    drawFixedDo: function (x, y) {
      var notes = this.chord.getNoteNumbers();

      // copied from drawNoteName except this line
      var note_name = this.getAnalyzer().to_fixed_do(notes);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (note_name !== "" && notes.length >= 1) {
        ctx.fillText(note_name, x + StaveNotater.prototype.annotateOffsetX, y);
      }
    },
    drawPitchClass: function (x, y) {
      var notes = this.chord.getNoteNumbers();

      // copied from drawNoteName except this line
      var note_name = this.getAnalyzer().to_pitch_class(notes);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (note_name !== "" && notes.length >= 1) {
        ctx.fillText(note_name, x + StaveNotater.prototype.annotateOffsetX, y);
      }
    },
    drawChordSpacing: function (x, y) {
      var notes = this.chord.getNoteNumbers();

      // copied from drawNoteName except this line
      // note_name is a misnomer here
      var note_name = this.getAnalyzer().to_spacing(notes);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "16px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (note_name !== "" && notes.length >= 1) {
        ctx.fillText(note_name, x + StaveNotater.prototype.annotateOffsetX, y);
      }
    },
    /**
     * Draws the name of a note in helmholtz pitch notation.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawHelmholtz: function (x, y) {
      var ctx = this.getContext();
      var notes = this.chord.getNoteNumbers();
      var note_name = this.getAnalyzer().getNoteName(notes[0], notes);
      var helmholtz = this.getAnalyzer().to_helmholtz(note_name);
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (helmholtz !== "" && notes.length === 1) {
        ctx.fillText(helmholtz, x + StaveNotater.prototype.annotateOffsetX, y);
      }

      return helmholtz; /* for grading */
    },
    /**
     * Draws the name of a note in scientific pitch notation.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawScientificPitch: function (x, y) {
      var ctx = this.getContext();
      var notes = this.chord.getNoteNumbers();
      var note_name = this.getAnalyzer().getNoteName(notes[0], notes);
      var scientific_pitch =
        this.getAnalyzer()
          .to_scientific_pitch(note_name)
          .replace(/b/g, "♭")
          .replace(/#/g, "♯") || ""; // replace: true flat and sharp signs (substitution okay since letter names are uppercase here)
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (scientific_pitch !== "" && notes.length === 1) {
        ctx.fillText(
          scientific_pitch,
          x + StaveNotater.prototype.annotateOffsetX,
          y
        );
      }

      return scientific_pitch; /* for grading */
    },
    /**
     * Draws solfege.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawSolfege: function (x, y, do_based_bool = false) {
      var ctx = this.getContext();
      var notes = this.chord.getNoteNumbers();
      var solfege = this.getAnalyzer().to_solfege(notes);
      if (do_based_bool) {
        solfege = this.getAnalyzer().to_do_based_solfege(notes);
      }
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      solfege = this.convertSymbols(solfege);
      if (solfege.indexOf("<br>") !== -1) {
        solfege = solfege.split("<br>")[0];
      }

      if (solfege !== "") {
        ctx.fillText(solfege, x + StaveNotater.prototype.annotateOffsetX, y);
      }

      return solfege; /* for grading */
    },
    /**
     * Draws the scale degree.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawScaleDegree: function (x, y) {
      var ctx = this.getContext();
      var notes = this.chord.getNoteNumbers();
      var width = 0,
        caret_offset = 0,
        caret_x = x,
        text_x = x;
      var numeral = this.getAnalyzer().to_scale_degree(notes);
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (numeral !== "") {
        numeral = this.convertSymbols(numeral);
        width = ctx.measureText(numeral).width;
        //x = x + 8 + Math.floor(width/2);
        caret_offset = ctx.measureText(numeral.slice(0, -1)).width;
        text_x = x - (numeral.length > 1 ? caret_offset : 0);
        caret_x = x - 1;

        ctx.fillText(
          numeral.replace(/b/g, "♭").replace(/#/g, "♯"),
          text_x + StaveNotater.prototype.annotateOffsetX,
          y - 64
        ); // raise Roman numeral 64px
        ctx.fillText(
          "^",
          caret_x + StaveNotater.prototype.annotateOffsetX,
          y - 79
        );
      }

      return numeral; /* for grading */
    },
    drawBassFigureDegree: function (x, y) {
      var notes = this.chord.getNoteNumbers();
      if (!notes || !notes.length) return "";
      var bassNote = Math.min.apply(null, notes);
      if (!Number.isFinite(bassNote)) return "";
      var roman = this.getAnalyzer().to_chord(notes, "roman only");
      var baseNumeral = roman && roman.numeral ? roman.numeral : null;
      var circled = null;
      if (baseNumeral) {
        var numeralLower = baseNumeral.toLowerCase();
        var romanMap = { i: "①", ii: "②", iii: "③", iv: "④", v: "⑤", vi: "⑥", vii: "⑦" };
        circled = romanMap[numeralLower] || null;
      }
      if (!circled) {
        var solfege = this.getAnalyzer().to_solfege([bassNote]);
        if (!solfege) return "";
        solfege = solfege.split("<br>")[0];
        var baseMatch = solfege.match(/[A-Za-z]+/);
        if (!baseMatch) return "";
        var base = baseMatch[0].toLowerCase();
        var map = {
          do: "①",
          re: "②",
          mi: "③",
          fa: "④",
          sol: "⑤",
          so: "⑤",
          la: "⑥",
          ti: "⑦",
          si: "⑦",
        };
        circled = map[base] || null;
      }
      if (!circled) return "";
      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "18px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];
      ctx.fillText(
        circled,
        x + StaveNotater.prototype.annotateOffsetX,
        y + 28
      );
      return circled;
    },
    /**
     * Draws the thoroughbass figures.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawThoroughbass: function (x, y) {
      let keyCategory = this.keySignature.getKey()[0] || false;
      if (keyCategory === "h") {
        return false;
      } /* thoroughbass and no-key mode do not play nicely */

      var midi_nums = this.chord.getNoteNumbers();
      var figure = this.analyzeConfig.mode.abbreviate_thoroughbass
        ? this.getAnalyzer().abbrev_thoroughbass_figure(midi_nums)
        : this.getAnalyzer().full_thoroughbass_figure(midi_nums);

      var ctx = this.getContext();

      this.parseAndDraw(figure, x, y, function (text, x, y) {
        x += StaveNotater.prototype.annotateOffsetX;
        var lines = text.split("/").map(function (line) {
          if (line === "\xb07") return "/"; /* diminished seventh */
          if (line === "6+") return "&";
          if (line === "5+") return "%";
          if (line === "4+") return "$";
          if (line === "2+") return '"';
          if (line.slice(0, 2) === "##") {
            return ("x " + line.slice(2)).trim();
          } else if (line.slice(0, 1) === "#") {
            return ("# " + line.slice(1)).trim();
          }
          if (line.slice(0, 2) === "bb") {
            return ("a " + line.slice(2)).trim();
          } else if (line.slice(0, 1) === "b") {
            return ("b " + line.slice(1)).trim();
          }
          if (line.slice(0, 1) === "n") {
            return ("n " + line.slice(1)).trim();
          }
          return line;
        });

        /* ctx.fillStyle = "red"; // test to see if thoroughbass superimposes on staff: it does */
        ctx.font = this.getFiguredBassFont();
        x += ctx.measureText("6").width + 6;
        const skip = this.textLineHeight * 0.8 * (MASK_TREBLE ? -1 : 1);
        const vshift = MASK_TREBLE ? -222 : -22; // shift down another digit

        var outlineColor = "rgb(238,238,221)";
        for (var i = 0; i < lines.length; i++) {
          var lineY = i * skip + y + vshift;
          ctx.textAlign = "end";
          if (ctx.strokeText) {
            ctx.save();
            ctx.strokeStyle = outlineColor;
            ctx.lineWidth = 4;
            ctx.strokeText(lines[i], x, lineY);
            ctx.restore();
          }
          ctx.fillText(lines[i], x, lineY);
        }

        return ctx.measureText(lines[0]).width;
        /* return width of the first line */
      });

      return figure; /* for grading */
    },
    drawChordLabel: function (x, y = 35, relativize_bool = false) {
      var key = this.keySignature.getKeyShortName();
      let keyCategory = this.keySignature.getKey()[0] || false;

      var midi_nums = this.chord.getNoteNumbers();
      var chord_entry = this.getAnalyzer().to_chord(
        midi_nums,
        "chord label",
        (relativize_bool = relativize_bool)
      );

      var width = 0,
        offset = 0;
      var ctx = this.getContext();

      if (!chord_entry) return ""; /* for grading */

      var display = chord_entry.label
        .replace(/bb/g, "𝄫")
        .replace(/b/g, "♭")
        .replace(/##/g, "𝄪")
        .replace(/#/g, "♯");

      this.parseAndDraw(display, x, y, function (text, x, y) {
        text = this.convertSymbols(text).replace(
          /⌀/g,
          "⌀"
        ); /* replace: one could improve appearance of half-diminished sign with standard fonts here, but currently using custom font instead */

        var lines = this.wrapText(text);

        var fontArgs = ctx.font.split(" ");
        var newSize = "20px"; /* size for chord symbols */
        ctx.font = newSize + " JazzSerifs"; /* jazz-style chord labels */

        var first_line_width =
          this.getContext().measureText(lines[0]).width + offset;
        offset += 5 - Math.floor(first_line_width / 2.5);

        this.drawTextLines(
          lines,
          x + offset + StaveNotater.prototype.annotateOffsetX,
          y
        );
      });

      return chord_entry; /* for grading */
    },
    /**
     * Draws the roman numeral analysis.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawRoman: function (x, y) {
      var key = this.keySignature.getKeyShortName();
      let keyCategory = this.keySignature.getKey()[0] || false;

      var midi_nums = this.chord.getNoteNumbers();
      var chord_entry = this.getAnalyzer().to_chord(midi_nums, "roman only");

      var width = 0,
        offset = 0;
      var ctx = this.getContext();

      if (!chord_entry) return ""; /* for grading */

      /**
       * Initial attempt at contextual analysis
       * Alter label based on preceding one
       */
      var history = this.romanNumeralsHistory;
      var resolution_lines = false;
      var one_resolution_line = false;
      var applied_arrow = false;

      const idx = this.stave.position.index;
      var display = chord_entry.label;

      var extra_wide_figures = false;
      if (keyCategory === "j") {
        var substitutions = [
          /* cadential six-fours and five-fours*/
          [
            ["I{z4}", "V"],
            ["V{z4}", "={t3}"],
          ],
          [
            ["V{r}...", "V"],
            ["V{r}", "={e}"],
          ],
          [
            ["I{z4}", "V{u3}"],
            ["V{z4}", "={u3}"],
          ],
          [
            ["I{z4}", "V{u}"],
            ["V{z4}", "={Ut3}"],
          ],
          [
            ["i{z4}", "V"],
            ["V{B z4}", "={t3}"],
          ],
          [
            ["i{z4}", "V{u3}"],
            ["V{B z4}", "={u3}"],
          ],
          [
            ["i{z4}", "V{u}"],
            ["V{B z4}", "={Ut3}"],
          ],
        ];
      } else if (keyCategory === "i") {
        var substitutions = [
          /* cadential six-fours */
          [
            ["I{z4}", "V"],
            ["V{' z4}", "={t3}"],
          ],
          [
            ["V{r}...", "V"],
            ["V{r}", "={e}"],
          ],
          [
            ["I{z4}", "V{u3}"],
            ["V{' z4}", "={u3}"],
          ],
          [
            ["I{z4}", "V{u}"],
            ["V{' z4}", "={Ut3}"],
          ],
          [
            ["i{z4}", "V"],
            ["V{z4}", "={t3}"],
          ],
          [
            ["i{z4}", "V{u3}"],
            ["V{z4}", "={u3}"],
          ],
          [
            ["i{z4}", "V{u}"],
            ["V{z4}", "={Ut3}"],
          ],
          [
            ["ii⌀{z5}", "i"],
            ["iv{d z}", "i"],
          ],
          // [["vii°{u}", "VI{z}"], ["c.t.°{u}", "VI{z}"]],
        ];
      }

      if (["i", "j"].includes(keyCategory) && history[idx - 1]) {
        /* has precursor */
        let precursor = history[idx - 1];
        let current = history[idx];
        if (precursor == current) {
          // display = ""; // MAKE THIS A USER PREFERENCE AND EXERCISE PREFERENCE
        } else {
          let progression = [precursor, current];
          let probe = substitutions
            .map((sub_arr) => sub_arr[0].join(">"))
            .indexOf(progression.join(">"));
          if (probe !== -1) {
            display = substitutions[probe][1][1];

            /* Also, change precursor label after the fact:
             * the postcursor logic alone is flawed because
             * chords can change before banking */

            // to do ^
          }
        }
      }
      if (["i", "j"].includes(keyCategory) && history[idx + 1]) {
        /* has postcursor */
        let postcursor = history[idx + 1];
        let current = history[idx];
        let progression = [current, postcursor];
        let probe = substitutions
          .map((sub_arr) => sub_arr[0].join(">"))
          .indexOf(progression.join(">"));
        if (probe !== -1) {
          display = substitutions[probe][1][0];
          if (["V{B z4}", "V{' z4}"].includes(display)) {
            extra_wide_figures = true;
          }
          if (["iv{d z}"].includes(display)) {
          } else if (["V{r}"].includes(display)) {
            one_resolution_line = true;
          } else {
            resolution_lines = true;
          }
        } else if (key !== "" && current.split("/").length == 2) {
          if (current.split("/")[1] == postcursor.split("{")[0]) {
            display = current.split("/")[0]; // + " →"
            applied_arrow = true;
          }
        }
        if (postcursor === "" && (current === "I{z4}" || current === "i{z4}")) {
          // display = "{z4}"
        }
      } else {
        /* no postcursor */
        let current = history[idx];
        if (current === "I{z4}" || current === "i{z4}") {
          // display = "{z4}"
        }
      }

      /* TO DO: add horizontal lines */

      if (keyCategory === "h") {
        // no key
        display = display
          .replace(/bb/g, "𝄫")
          .replace(/b/g, "♭")
          .replace(/##/g, "𝄪")
          .replace(/#/g, "♯");
        y = 35;
      }

      this.parseAndDraw(display, x, y, function (text, x, y) {
        text = this.convertSymbols(text).replace(
          /⌀/g,
          "⌀"
        ); /* replace: one could improve appearance of half-diminished sign with standard fonts here, but currently using custom font instead */

        offset = ["\u266D", "\u266F"].includes(text.slice(0, 1))
          ? -ctx.measureText(text.slice(0, 1)).width
          : 0; /* horizontal alignment when label begins with flat or sharp */

        if (text == "=") {
          text =
            ""; /* hack for proper horizontal placement of figured bass without prior numeral per above substitutions */
        }

        var lines = this.wrapText(text);
        var ctx = this.getContext();
        var fontArgs = ctx.font.split(" ");
        var originalFont = ctx.font;
        var romanFontSize = 20;
        if (text.length >= 3) {
          romanFontSize = 18;
        }
        ctx.font = romanFontSize + " " + fontArgs[fontArgs.length - 1];
        var baseX = x + offset + StaveNotater.prototype.annotateOffsetX;
        var plainLen = text.replace(/\{.*?\}/g, "").replace(/\s+/g, "").length;
        var shift = 0;
        if (plainLen >= 5) {
          shift = -10;
        } else if (plainLen >= 3) {
          shift = -6;
        }
        baseX += shift;
        this.drawTextLines(lines, baseX, y);
        ctx.font = originalFont;

        var first_line_width = ctx.measureText(lines[0]).width;

        if (resolution_lines || one_resolution_line) {
          let label_width = first_line_width + 15;
          let x_start = baseX - StaveNotater.prototype.annotateOffsetX + label_width;
          let stroke_length = this.stave.width - label_width;
          if (extra_wide_figures) {
            x_start += 10;
            stroke_length += -10;
          }
          ctx.beginPath();
          if (resolution_lines) {
            ctx.moveTo(x_start, y - 3);
            ctx.lineTo(x_start + stroke_length, y - 3);
          }
          ctx.moveTo(x_start, y - 12);
          ctx.lineTo(x_start + stroke_length, y - 12);
          ctx.stroke();
        }
        resolution_lines = false;
        one_resolution_line = false;

        if (applied_arrow) {
          let width = this.stave.width;
          let x_start = baseX - StaveNotater.prototype.annotateOffsetX + first_line_width / 2;
          let x_end = this.annotateOffsetX + x + width;
          ctx.beginPath();
          ctx.lineWidth = 1.5;
          ctx.moveTo(x_start, y + 6);
          ctx.bezierCurveTo(
            x_start + 10,
            y + 16,
            x_end - 10,
            y + 16,
            x_end,
            y + 6
          );
          ctx.lineTo(x_end - 8, y + 5);
          ctx.moveTo(x_end, y + 6);
          ctx.lineTo(x_end - 3, y + 14);
          ctx.stroke();
        }
        applied_arrow = false;

        return first_line_width; // return the width of the first line for figured bass
      });

      return chord_entry; /* for grading */
    },
    normalizeAnalyticalText: function (text) {
      return String(text || "")
        .replace(/bb/g, "𝄫")
        .replace(/b/g, "♭")
        .replace(/##/g, "𝄪")
        .replace(/#/g, "♯")
        .replace(/n/g, "♮")
        .trim();
    },
    getFigurePattern: function (figure) {
      return String(figure || "")
        .split("/")
        .map(function (line) {
          return line.replace(/[^0-9]+/g, "");
        })
        .filter(function (line) {
          return line.length > 0;
        })
        .join("/");
    },
    getRomanExpDisplayFigureLines: function (current, previous) {
      if (!current) return [];

      var preserveSuspensionContext = !!(
      previous &&
      previous.base === current.base &&
      previous.fullFigureLines &&
      previous.fullFigureLines.length >= 3
    );

      return preserveSuspensionContext
        ? current.fullFigureLines
        : current.abbrevFigureLines;
    },
    getRomanExpParts: function (midi_nums) {
      if (!midi_nums || midi_nums.length < 2) return null;

      var keyCategory = this.keySignature.getKey()[0] || false;
      if (!["i", "j"].includes(keyCategory)) return null;

      var chord_entry = this.getAnalyzer().to_chord(midi_nums, "roman only");
      if (!chord_entry || !chord_entry.label) return null;

      var base = this.normalizeAnalyticalText(
        chord_entry.label.replace(/\{[^}]*\}/g, "")
      );
      if (!base) return null;

      var figure = "";
      var abbrevFigure = "";
      try {
        figure = this.getAnalyzer().full_thoroughbass_figure(midi_nums) || "";
        abbrevFigure =
          this.getAnalyzer().abbrev_thoroughbass_figure(midi_nums) || "";
      } catch (err) {
        figure = "";
        abbrevFigure = "";
      }

      var fullFigureLines = figure
        ? figure
            .split("/")
            .map(
              function (line) {
                return this.normalizeAnalyticalText(line);
              }.bind(this)
            )
            .filter(function (line) {
              return line.length > 0;
            })
        : [];

      var abbrevFigureLines = abbrevFigure
        ? abbrevFigure
            .split("/")
            .map(
              function (line) {
                return this.normalizeAnalyticalText(line);
              }.bind(this)
            )
            .filter(function (line) {
              return line.length > 0;
            })
        : [];

      return {
        base: base,
        fullFigure: figure,
        fullFigurePattern: this.getFigurePattern(figure),
        fullFigureLines: fullFigureLines,
        abbrevFigure: abbrevFigure,
        abbrevFigurePattern: this.getFigurePattern(abbrevFigure),
        abbrevFigureLines: abbrevFigureLines,
      };
    },
    drawRomanExp: function (x, y) {
      var midi_nums = this.chord.getNoteNumbers();
      var current = this.getRomanExpParts(midi_nums);
      if (!current) return "";

      var idx = this.stave.position.index;
      var previous = this.romanNumeralsExpHistory[idx - 1] || null;
      var previousPrevious = this.romanNumeralsExpHistory[idx - 2] || null;
      var continuingRun = !!(
        previous &&
        previous.base &&
        previous.base === current.base
      );
      var currentFigureLines = this.getRomanExpDisplayFigureLines(
        current,
        previous
      );
      var previousFigureLines = this.getRomanExpDisplayFigureLines(
        previous,
        previousPrevious
      );

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var originalFont = ctx.font;
      var columnCenterX = x + StaveNotater.prototype.annotateOffsetX + 6;
      var baseFont = "20px " + fontArgs[fontArgs.length - 1];
      ctx.font = baseFont;
      if (!continuingRun) {
        var baseWidth = ctx.measureText(current.base).width;
        var baseX = columnCenterX - baseWidth - 10;
        var slashIdx = current.base.indexOf("/");
        if (slashIdx >= 0) {
          var topPart = current.base.slice(0, slashIdx);
          var bottomPart = current.base.slice(slashIdx + 1);
          var topWidth = ctx.measureText(topPart).width;
          var topPartX = Math.round(columnCenterX - topWidth / 2) - 10;
          ctx.fillText(topPart, topPartX, y);
          ctx.fillText("/", topPartX + topWidth - 3, y + 9);
          ctx.fillText(bottomPart, topPartX + topWidth + 3, y + 14);
        } else {
          ctx.fillText(current.base, baseX, y);
        }
      }

      if (currentFigureLines.length) {
        var figureLineHeight = 12;
        var figureStartY = y - 12;
        ctx.font = "14px " + fontArgs[fontArgs.length - 1];
        currentFigureLines.forEach(function (line, index) {
          var lineY = figureStartY + index * figureLineHeight;
          var lineWidth = ctx.measureText(line).width;

          if (
            continuingRun &&
            previousFigureLines &&
            previousFigureLines[index]
          ) {
            ctx.fillText("-", columnCenterX - lineWidth / 2 - 10, lineY);
          }

          ctx.fillText(line, columnCenterX - lineWidth / 2, lineY);
        });
      }

      ctx.font = originalFont;

      return current.base;
    },
    drawPci: function (x, y) {
      var midi_nums = this.chord.getNoteNumbers();
      var interval = this.getAnalyzer().to_pci(midi_nums);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (interval && interval !== "") {
        ctx.fillText(
          interval,
          x + StaveNotater.prototype.annotateOffsetX + 3,
          y
        );
      }

      return interval; /* for grading */
    },
    drawSetClass: function (x, y, format = false) {
      var midi_nums = this.chord.getNoteNumbers();
      var set_class = this.getAnalyzer().to_set_class(midi_nums, format);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (set_class && set_class !== "") {
        ctx.fillText(
          set_class,
          x + StaveNotater.prototype.annotateOffsetX + 3,
          y
        );
      }

      return set_class; /* for grading */
    },
    /**
     * Draws the interval analysis.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawInterval: function (x, y, prop='name', wrap=false, wrap_mark="") {
      var midi_nums = this.chord.getNoteNumbers();
      var interval = this.getAnalyzer().to_interval(midi_nums, wrap, wrap_mark);

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");
      var newSize = "20px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      try {
        const lines = this.wrapText(interval[prop]);
        this.drawTextLines(
          lines,
          x + StaveNotater.prototype.annotateOffsetX,
          y
        );
      }
      finally {
        return interval; /* for grading */
      }
    },
    /**
     * Draws the metronome mark.
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawMetronomeMark: function (x, y) {
      var ctx = this.getContext();
      var tempo = this.getTempo();
      var fontArgs = ctx.font.split(" ");
      var newSize = "16px";
      ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];

      if (tempo) {
        ctx.fillText("M.M. = " + tempo, x, y + 25);
      }
    },
    /**
     * Draws the key name (i.e. C major, etc).
     *
     * @param {number} x
     * @param {number} y
     * @return undefined
     */
    drawKeyName: function (x, y) {
      var key = this.keySignature.getKeyShortName();

      var analysis = this.analyzeConfig.enabled;
      var thoroughbass = this.analyzeConfig.mode.thoroughbass;
      var note_names = this.analyzeConfig.mode.note_names;
      var roman_numerals = this.analyzeConfig.mode.roman_numerals;
      var chord_labels = this.analyzeConfig.mode.chord_labels;
      var spacing = this.analyzeConfig.mode.spacing;

      var ctx = this.getContext();
      var fontArgs = ctx.font.split(" ");

      // if (key === '' && !thoroughbass && harmony) {
      if (chord_labels && analysis) {
        var newSize = "16px";
        ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];
        ctx.fillText("chords", x - 18, 35);
      }
      if (spacing && analysis) {
        var newSize = "16px";
        ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];
        ctx.fillText("", x - 18, 60); // SAT sp.
      }
      if (note_names && analysis) {
        // ctx.fillText('notes', x - 18, 60);
      }
      if (roman_numerals && key !== "" && !thoroughbass && analysis) {
        var newSize = "20px";
        ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];
        ctx.fillText(this.convertSymbols(key) + ":", x - 8, y);
      }
    },
    /**
     * Draws a sequence of text lines on the canvas.
     *
     * @param {array} lines
     * @param {number} x
     * @param {number} y
     * @return
     */
    drawTextLines: function (lines, x, y) {
      var ctx = this.getContext();
      var line_height = this.textLineHeight;

      for (var i = 0; i < lines.length; i++) {
        var line_y = y + i * line_height;
        ctx.fillText(lines[i], x, line_y);
      }
    },
    /**
     * Parses a string of text to find out which font to use, and then draws
     * the resulting text tokens with the necessary font. Text that
     * should be rendered with the figured bass font should be wrapped in
     * curly brackets: "foo{text}bar"
     *
     * @param {string} str  - the string to draw
     * @param {number} x - the x coordinate to draw
     * @param {number} y - the y coordinate to draw at
     * @param {function} callback - called to draw the text once the font is activated
     * @return undefined
     */
    parseAndDraw: function (str, x, y, callback) {
      var that = this;
      var figuredBassFont = this.getFiguredBassFont();
      var ctx = this.getContext();
      var padding = ctx.measureText("n").width; // width to use for padding
      var key = this.keySignature.getKey();

      FontParser.parse(str, function (text, is_font_token) {
        if (is_font_token) {
          ctx.save();
          ctx.font = figuredBassFont;
          x += callback.call(
            that,
            text,
            x,
            y + 3
          ); /* tweak figured bass vertical position */
          x += padding / 3;
          ctx.restore();
        } else {
          var fontArgs = ctx.font.split(" ");
          var newSize =
            key == "h"
              ? "20px"
              : "24px"; /* size for chord symbols and Roman numerals; old implementation */
          ctx.font = newSize + " " + fontArgs[fontArgs.length - 1];
          if (false && key === "h" && str.length > 6) {
            /* taken out of commission: causes problems with jazz style labels */
            /* add line break to long applied-chord labels */
            x += callback.call(that, text.replace(/\//g, "\n/"), x, y);
          } else {
            x += callback.call(that, text, x, y);
          }
          x += padding / 2;
        }
      });
    },
    /**
     * Notates the stave.
     *
     * Always called, in contrast to drawLabel().
     *
     * @abstract
     * @return undefined
     */
    notateStave: function () {
      throw new Error("subclass responsibility");
    },
    /**
     * Notates the chord.
     *
     * Only called if the notater has a reference to the chord and analysis
     * is enabled.
     *
     * @abstract
     * @return undefined
     */
    drawLabel: function () {
      throw new Error("subclass responsibility");
    },
    /**
     * Wraps text. Delegates to utility method.
     *
     * @param {string} text
     * @return {array}
     */
    wrapText: function (text) {
      return util.wrapText(text, this.textLimit);
    },
    /**
     * Converts symbols to unicode. Delegates to utility method.
     *
     * @param {string} text
     * @return {string}
     */
    convertSymbols: function (text) {
      return util.convertSymbols(text);
    },
  });

  //------------------------------------------------------------

  /**
   * Creates an instance of TrebleStaveNotater.
   *
   * This object is responsible for knowing how to notate treble staves.
   *
   * @constructor
   * @param {object} config
   */
  var TrebleStaveNotater = function (config) {
    this.init(config);
    this.clef = StaveNotater.TREBLE;
  };

  /**
   * Inherits from StaveNotater.
   */
  TrebleStaveNotater.prototype = new StaveNotater();

  _.extend(TrebleStaveNotater.prototype, {
    /**
     * Set the Y position for notation above the top of the stave.
     *
     * @return {number}
     */
    getY: function () {
      return this.stave.getTopY() - this.margin.top;
    },
    /**
     * Notates the chord.
     *
     * Only called if the notater has a reference to the chord and analysis
     * is enabled.
     *
     * @return undefined
     */
    drawLabel: function (exercise_midi_nums = false) {
      /* Above the current treble staff */

      var x = this.getX();
      var y = this.getY();
      var notes = this.chord.getNoteNumbers();
      var first_row = y,
        second_row = y + 25;
      var mode = this.analyzeConfig.mode;

      if (notes.length >= 1) {
        if (mode.scale_degrees && !mode.solfege) {
          this.drawScaleDegree(x, first_row);
        } else if (
          mode.solfege &&
          !mode.scale_degrees &&
          !mode.do_based_solfege
        ) {
          this.drawSolfege(x, first_row);
        } else if (
          mode.do_based_solfege &&
          !mode.scale_degrees &&
          !mode.solfege
        ) {
          this.drawSolfege(x, first_row, true); // do-minor
        }

        var solfege = this.convertSymbols(this.getAnalyzer().to_solfege(notes));
        if (SHOW_DIAGRAM) {
          var ctx = this.getContext();
          ctx.fillStyle = "rgb(238, 238, 221)";
          ctx.beginPath();
          ctx.rect(0, 0, 14, 300);
          ctx.fill();
          ctx.fillStyle = "black";
          let y = 100;
          let w = 12;
          let arrow_pos = [
            y,
            y + 2 * w,
            y + 4 * w,
            y + 5 * w,
            y + 7 * w,
            y + 9 * w,
            y + 10 * w,
          ][["La", "So", "Fa", "Mi", "Re", "Do", "Ti"].indexOf(solfege)];
          ctx.beginPath();
          ctx.moveTo(0, arrow_pos + 6);
          ctx.lineTo(13, arrow_pos + 6);
          ctx.moveTo(10, arrow_pos + 3);
          ctx.lineTo(13, arrow_pos + 6);
          ctx.lineTo(10, arrow_pos + 9);
          ctx.stroke();
        }

        if (mode.spacing) {
          this.drawChordSpacing(x, second_row);
        } else if (mode.note_names) {
          this.drawNoteName(x, second_row);
        } else if (mode.fixed_do) {
          this.drawFixedDo(x, second_row);
        } else if (mode.pitch_class) {
          this.drawPitchClass(x, second_row);
        } else if (
          notes.length === 1 &&
          mode.scientific_pitch &&
          !mode.note_names
        ) {
          this.drawScientificPitch(x, second_row);
        }
      }
    },
    /**
     * Notates the stave.
     *
     * Always called, in contrast to drawLabel().
     *
     * @return undefined
     */
    notateStave: function (exercise_midi_nums = false) {
      var x = this.getX();
      var y = this.getY();

      if (MASK_TREBLE) {
        var ctx = this.getContext();

        ctx.fillStyle = "rgb(238, 238, 221)";
        ctx.beginPath();
        ctx.rect(0, 95, 800, 41);
        ctx.rect(0, 95, 21, 123);
        ctx.rect(22, 80, 30, 71);
        ctx.fill();

        ctx.fillStyle = "black";
      }

      if (SHOW_DIAGRAM) {
        var ctx = this.getContext();

        let y = 100;
        let w = 12;
        let l = 2;
        ctx.strokeStyle = "black";
        ctx.lineWidth = new String(l);
        ctx.beginPath();
        ctx.rect(20, y, w, w);
        ctx.rect(20, y + 2 * w, w, w);
        ctx.rect(20, y + 4 * w, w, w);
        ctx.rect(20, y + 5 * w, w, w);
        ctx.rect(20, y + 7 * w, w, w);
        ctx.rect(20, y + 9 * w, w, w);
        ctx.rect(20, y + 10 * w, w, w);
        ctx.stroke();

        ctx.lineWidth = "0";
        ctx.beginPath();
        ctx.fillStyle = "#ff6666"; // red
        ctx.rect(20 + l / 2, y + 4 * w + l / 2, w - l, w - l);
        ctx.fill();

        ctx.beginPath();
        ctx.fillStyle = "#66a3ff"; // blue
        ctx.rect(20 + l / 2, y + 5 * w + l / 2, w - l, w - l);
        ctx.fill();

        ctx.lineWidth = "0";
        ctx.beginPath();
        ctx.fillStyle = "#ffff66"; // yellow
        ctx.rect(20 + l / 2, y + 10 * w + l / 2, w - l, w - l);
        ctx.fill();

        ctx.fillStyle = "black";
      }

      if (this.stave.isFirstBar()) {
        this.drawMetronomeMark(x, y);
      }
    },
  });

  MicroEvent.mixin(TrebleStaveNotater);

  //------------------------------------------------------------

  /**
   * Creates an instance of BassStaveNotater.
   *
   * This object is responsible for knowing how to notate bass staves.
   *
   * @constructor
   * @param {object} config
   */
  var BassStaveNotater = function (config) {
    this.init(config);
    this.clef = StaveNotater.BASS;
  };

  /**
   * Inherits from StaveNotater.
   */
  BassStaveNotater.prototype = new StaveNotater();

  _.extend(BassStaveNotater.prototype, {
    /**
     * Set the Y position for notation below the bottom of the stave.
     *
     * @return {number}
     */
    getY: function () {
      return this.stave.getBottomY() + this.margin.bottom;
    },
    /**
     * Notates the chord.
     *
     * Only called if the notater has a reference to the chord and analysis
     * is enabled.
     *
     * @return undefined
     */
    drawLabel: function (exercise_midi_nums = false) {
      /* Below the current bass staff */

      var x = this.getX();
      var y = this.getY();
      var midi_nums = this.chord.getNoteNumbers();
      var num_notes = midi_nums.length;
      var mode = this.analyzeConfig.mode;

      /* stores unedited chord labels */
      if (
        exercise_midi_nums &&
        typeof this.romanNumeralsHistory[this.stave.position.index] ===
          "undefined"
      ) {
        let romanNumerals = exercise_midi_nums.map(
          (midi_arr) => this.getAnalyzer().to_chord(midi_arr).label || ""
        );
        var i, len;
        for (i = 0, len = romanNumerals.length; i < len; i += 1) {
          this.romanNumeralsHistory[i + 1] = romanNumerals[i];
        }
        // console.log(this.romanNumeralsHistory);
      } else if (!exercise_midi_nums) {
        this.romanNumeralsHistory[this.stave.position.index] =
          this.getAnalyzer().to_chord(midi_nums).label || "";
      }

      if (
        exercise_midi_nums &&
        typeof this.romanNumeralsExpHistory[this.stave.position.index] ===
          "undefined"
      ) {
        let romanExpParts = exercise_midi_nums.map(
          function (midi_arr) {
            return this.getRomanExpParts(midi_arr);
          }.bind(this)
        );
        var expIdx, expLen;
        for (expIdx = 0, expLen = romanExpParts.length; expIdx < expLen; expIdx += 1) {
          this.romanNumeralsExpHistory[expIdx + 1] = romanExpParts[expIdx];
        }
      } else if (!exercise_midi_nums) {
        this.romanNumeralsExpHistory[this.stave.position.index] =
          this.getRomanExpParts(midi_nums);
      }

      if (mode.thoroughbass) {
        if (num_notes >= 2) {
          this.drawThoroughbass(x, y);
        }
        if (mode.abbreviate_thoroughbass) {
          this.drawBassFigureDegree(x, y);
        }
        // when thoroughbass is active we skip the other label types
        if (mode.chord_labels || mode.roman_numerals || mode.roman_numerals_exp || mode.bass_scale_degrees || mode.bass_solfege || mode.bass_do_based_solfege) {
          // fall through so roman numerals/chords can still draw if desired
        } else {
          return;
        }
      } else if (num_notes == 2) {
        if (mode.intervals) {
          this.drawInterval(x, y, 'name');
        }
        if (mode.intervals_wrap_after_octave) {
          this.drawInterval(x, y, 'name', 'wrap_after_octave', '*');
        }
        if (mode.intervals_wrap_after_octave_plus_ditone) {
          this.drawInterval(x, y, 'name', 'wrap_after_octave_plus_ditone', '*');
        }
        if (mode.generic_intervals) {
          this.drawInterval(x, y, 'size');
        }
        if (mode.generic_intervals_wrap_after_octave) {
          this.drawInterval(x, y, 'size', 'wrap_after_octave', '*');
        }
        if (mode.generic_intervals_wrap_after_octave_plus_ditone) {
          this.drawInterval(x, y, 'size', 'wrap_after_octave_plus_ditone', '*');
        }
        if (mode.pci) {
          this.drawPci(x, y);
        }
      } else if (num_notes > 2) {
        if (mode.roman_numerals) {
          this.drawRoman(x, y);
        }
        if (mode.roman_numerals_exp) {
          this.drawRomanExp(x, y);
        }
        if (mode.chord_labels) {
          this.drawChordLabel(x);
        }
      }

      if (num_notes >= 2) {
        var set_format = false;
        if (mode.set_class_forte) {
          set_format = "Forte";
        } else if (mode.set_class_prime) {
          set_format = "prime";
        } else if (mode.set_class_normal) {
          set_format = "normal";
        } else if (mode.set_class_set) {
          set_format = "set";
        }
        if (set_format) {
          this.drawSetClass(x, y - 25, set_format);
        }
      }
    },
    /**
     * Notates the stave.
     *
     * Always called, in contrast to drawLabel().
     *
     * @return undefined
     */
    notateStave: function () {
      var x = this.getX();
      var y = this.getY();

      if (this.stave.isFirstBar()) {
        this.drawKeyName(x, y);
      }
    },
  });

  MicroEvent.mixin(BassStaveNotater);

  //------------------------------------------------------------

  /**
   * Factory function that returns the appropriate StaveNotater.
   *
   * @static
   * @param {string} clef
   * @param {object} config
   * @return {StaveNotater}
   */
  StaveNotater.create = function (clef, config) {
    switch (clef) {
      case "treble":
        return new TrebleStaveNotater(config);
      case "bass":
        return new BassStaveNotater(config);
      default:
        throw new Error("no such notater for clef: " + clef);
    }
  };

  return StaveNotater;
});
