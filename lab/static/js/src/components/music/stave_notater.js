/* global define: false */ 
define([
	'lodash', 
	'vexflow',
	'microevent',
	'app/config', /* only for declaring MASK_TREBLE */
	'app/util',
	'app/utils/analyze',
	'app/utils/fontparser'
], function(
	_, 
	Vex, 
	MicroEvent,
	Config, /* only for declaring MASK_TREBLE */
	util, 
	Analyze,
	FontParser
) {
	"use strict";

	/* hack for bass staff only added 2020 */
	/* not ready: also masks thoroughbass figures */
	var MASK_TREBLE = Config.get('general.maskTrebleStaff');

    var getUrlVars = function() {
        var vars = {};
        var parts = window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) {
            vars[key] = value;
        });
        return vars;
    };
    // console.log('URL variables', getUrlVars());

    var SHOW_DIAGRAM = (getUrlVars().hasOwnProperty('diagram') && getUrlVars()['diagram'] === 'true' ? true : false );


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
	 * - Intervals
	 * - Roman numeral analysis
	 *
	 * At its simplest, a Stave should configure the notater with the kinds of
	 * things it wants notated, passing a reference to itself, and then call the
	 * notate() method to render those things on the stave.
	 *
	 * @constructor
	 */
	var StaveNotater = function() {
	};

	StaveNotater.BASS = 'bass';
	StaveNotater.TREBLE = 'treble';

	_.extend(StaveNotater.prototype, {
		/**
		 * Defines the margin for rendering things above and below the stave.
		 * @type {object}
		 */
		margin: {'top': 50, 'bottom': 25},
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
		/**
		 * Initializes the notater.
		 *
		 * @param {object} config
		 * @param {Stave} config.stave
		 * @param {KeySignature} config.keySignature
		 * @param {object} config.analyzeConfig
		 * @return undefined
		 */
		init: function(config) {
			this.config = config;
			this.initConfig();
			_.bindAll(this, 'drawMetronomeMark');
		},
		/**
		 * Initializes the config
		 *
		 * @return undefined
		 * @throws {Error} Will throw an error if a config param is missing.
		 */
		initConfig: function() {
			var required = ['stave', 'keySignature', 'analyzeConfig'];
			_.each(required, function(propName) {
				if(this.config.hasOwnProperty(propName)) {
					this[propName] = this.config[propName];
				} else {
					throw new Error("missing required config property: "+propName);
				}
			}, this);

			// optional
			if(this.config.hasOwnProperty('chord')) {
				this.chord = this.config.chord;
			}
		},
		/**
		 * Notates the Stave if the notater is enabled.
		 *
		 * @fires notated
		 * @return undefined
		 */
		notate: function(exercise_midi_nums = false) {
			var ctx = this.getContext();

			ctx.save();
			ctx.font = this.getTextFont();

			this.notateStave();

			if(this.isAnalyzerEnabled()) {
				this.updateAnalyzer();
				if(this.chord) {
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
		createAnalyzer: function() {
			return new Analyze(this.keySignature); 
		},
		/**
		 * Updates the analyzer object.
		 *
		 * @return undefined
		 */
		updateAnalyzer: function() {
			this.analyzer = this.createAnalyzer();
		},
		/**
		 * Returns the analyzer object.
		 *
		 * @return {Analyze}
		 */
		getAnalyzer: function() {
			return this.analyzer;
		},
		/**
		 * Returns the canvas rendering context.
		 *
		 * @return {object}
		 */
		getContext: function() {
			return this.stave.getContext();
		},
		/**
		 * Returns the font for annotations.
		 *
		 * @return {string}
		 */
		getTextFont: function(size) {
			if(!size) {
				size = this.defaultFontSize; 
			}
			return size + " 'MainSerifs'";
		},
		/**
		 * Returns the font for rendering icons.
		 *
		 * @return {string}
		 */
		getIconFont: function(size) {
			if(!size) {
				size = this.defaultFontSize;
			}
			return size + " Ionicons";
		},
		/**
		 * Returns the font for rendering figured bass.
		 *
		 * @return {string}
		 */
		getFiguredBassFont: function(size) {
			if(!size) {
				size = "32px";
			}
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
		preloadFont: function(fontFamily) {
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
		getX: function() {
			return this.stave.getStartX() + 10;
		},
		/**
		 * Returns the Y position for notating.
		 *
		 * @abstract
		 * @return {number}
		 */
		getY: function() {
			throw new Error("subclass responsibility");
		},
		/**
		 * Returns the current tempo of the metronome.
		 *
		 * @return {number}
		 */
		getTempo: function() {
			return this.analyzeConfig.tempo;
		},
		/**
		 * Returns true if analysis is enabled, false otherwise.
		 *
		 * @return {boolean}
		 */
		isAnalyzerEnabled: function() {
			return this.analyzeConfig.enabled;
		},
		/**
		 * Draws the note name.
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawNoteName: function(x, y) {
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var note_name = this.getAnalyzer().to_note_name(notes);
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if(note_name !== '' && notes.length >= 1) {
				ctx.fillText(note_name, x + StaveNotater.prototype.annotateOffsetX, y);
			}
		},
		drawFixedDo: function(x, y) { // mostly copied from drawNoteName
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var note_name = this.getAnalyzer().to_fixed_do(notes);
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if(note_name !== '' && notes.length >= 1) {
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
		drawHelmholtz: function(x, y) {
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var note_name = this.getAnalyzer().getNoteName(notes[0],notes);
			var helmholtz = this.getAnalyzer().to_helmholtz(note_name);
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if(helmholtz !== '' && notes.length === 1) {
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
		drawScientificPitch: function(x, y) {
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var note_name = this.getAnalyzer().getNoteName(notes[0],notes);
			var scientific_pitch = this.getAnalyzer().to_scientific_pitch(note_name).replace(/b/g,'♭').replace(/#/g,'♯') || ''; // replace: true flat and sharp signs (substitution okay since letter names are uppercase here)
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if (scientific_pitch !== '' && notes.length === 1) {
				ctx.fillText(scientific_pitch, x + StaveNotater.prototype.annotateOffsetX, y);
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
		drawSolfege: function(x, y) {
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var solfege = this.getAnalyzer().to_solfege(notes);
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			solfege = this.convertSymbols(solfege);
			if (solfege.indexOf("<br>") !== -1) {
				solfege = solfege.split("<br>")[0];
			}

			if(solfege !== '') {
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
		drawScaleDegree: function(x, y) {
			var ctx = this.getContext();
			var notes = this.chord.getNoteNumbers();
			var width = 0, caret_offset = 0, caret_x = x, text_x = x;
			var numeral = this.getAnalyzer().to_scale_degree(notes);
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if(numeral !== '') {
				numeral = this.convertSymbols(numeral);
				width = ctx.measureText(numeral).width;
				//x = x + 8 + Math.floor(width/2);
				caret_offset = ctx.measureText(numeral.slice(0,-1)).width;
				text_x = x - (numeral.length > 1 ? caret_offset : 0);
				caret_x = x - 1;

				ctx.fillText(numeral.replace(/b/g,'♭').replace(/#/g,'♯'), text_x + StaveNotater.prototype.annotateOffsetX, y); // replace: true flat and sharp signs
				ctx.fillText("^", caret_x + StaveNotater.prototype.annotateOffsetX, y - 15);
			}

			return numeral; /* for grading */
		},
		/**
		 * Draws the thoroughbass figures.
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawThoroughbass: function(x, y) {
			let keyCategory = this.keySignature.getKey()[0] || false;
			if (keyCategory === "h") { return false; } /* thoroughbass and no-key mode do not play nicely */

			var midi_nums = this.chord.getNoteNumbers();
			var figure = (this.analyzeConfig.mode.abbreviate_thoroughbass ?
				this.getAnalyzer().abbrev_thoroughbass_figure(midi_nums) :
				this.getAnalyzer().full_thoroughbass_figure(midi_nums)
			);

			var ctx = this.getContext();

			this.parseAndDraw(figure, x, y, function(text, x, y) {
				x += StaveNotater.prototype.annotateOffsetX
				var lines = text.split("/").map(function(line) {
					if (line === "\xb07") return "/"; /* diminished seventh */
					if (line === "6+") return "&";
					if (line === "5+") return "%";
					if (line === "4+") return "$";
					if (line === "2+") return "\"";
					if (line.slice(0,2) === "##") {
						return ("x " + line.slice(2)).trim();
					} else if (line.slice(0,1) === "#") {
						return ("# " + line.slice(1)).trim();
					}
					if (line.slice(0,2) === "bb") {
						return ("a " + line.slice(2)).trim();
					} else if (line.slice(0,1) === "b") {
						return ("b " + line.slice(1)).trim();
					}
					if (line.slice(0,1) === "n") {
						return ("n " + line.slice(1)).trim();
					}
					return line;
				});

				/* ctx.fillStyle = "red"; // test to see if thoroughbass superimposes on staff: it does */
				ctx.font = this.getFiguredBassFont();
				x += ctx.measureText("6").width + 6;
				const skip = this.textLineHeight*0.8*(MASK_TREBLE ? -1 : 1);
				const vshift = (MASK_TREBLE ? -158 : -18);

				for(var i = 0; i < lines.length; i++) {
					ctx.textAlign = "end";
					ctx.fillText(lines[i], x, i*skip+y+vshift);
				}

				return ctx.measureText(lines[0]).width;
				/* return width of the first line */
			});

			return figure; /* for grading */
		},
		/**
		 * Draws the roman numeral analysis.
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawRoman: function(x, y) {
			var key = this.keySignature.getKeyShortName();
			let keyCategory = this.keySignature.getKey()[0] || false;

			var midi_nums = this.chord.getNoteNumbers();
			var chord_entry = this.getAnalyzer().to_chord(midi_nums);

			var width = 0, offset = 0;
			var ctx = this.getContext();

			if (!chord_entry) return ""; /* for grading */

			/**
			 * Initial attempt at contextual analysis
			 * Alter label based on preceding one
			 */
			var history = this.romanNumeralsHistory;
			var resolution_lines = false;
			var applied_arrow = false;

			const idx = this.stave.position.index;
			var display = chord_entry.label;

			var extra_wide_figures = false;
			if (keyCategory === "j") {
				var substitutions = [
					/* cadential six-fours */
					[["I{z4}", "V"], ["V{z4}", "{t3}"]],
					[["I{z4}", "V{u3}"], ["V{z4}", "{u3}"]],
					[["I{z4}", "V{u}"], ["V{z4}", "{Ut3}"]],
					[["i{z4}", "V"], ["V{B z4}", "{t3}"]],
					[["i{z4}", "V{u3}"], ["V{B z4}", "{u3}"]],
					[["i{z4}", "V{u}"], ["V{B z4}", "{Ut3}"]],
				];
			} else if (keyCategory === "i") {
				var substitutions = [
					/* cadential six-fours */
					[["I{z4}", "V"], ["V{' z4}", "{t3}"]],
					[["I{z4}", "V{u3}"], ["V{' z4}", "{u3}"]],
					[["I{z4}", "V{u}"], ["V{' z4}", "{Ut3}"]],
					[["i{z4}", "V"], ["V{z4}", "{t3}"]],
					[["i{z4}", "V{u3}"], ["V{z4}", "{u3}"]],
					[["i{z4}", "V{u}"], ["V{z4}", "{Ut3}"]],
					// [["vii°{u}", "VI{z}"], ["c.t.°{u}", "VI{z}"]],
				];
			}

			if ( ["i","j"].includes(keyCategory) && history[idx-1] ) { /* has precursor */
				let precursor = history[idx-1];
				let current = history[idx]
				if (precursor == current) display = "";
				else {
					let progression = [precursor, current];
					let probe = substitutions.map(sub_arr => sub_arr[0].join(">")).indexOf(progression.join(">"));
					if (probe !== -1) {
						display = substitutions[probe][1][1];

						/* Also, change precursor label after the fact:
						 * the postcursor logic alone is flawed because
						 * chords can change before banking */

						// to do ^
					}
				}
			}
			if ( ["i","j"].includes(keyCategory) && history[idx+1] ) { /* has postcursor */
				let postcursor = history[idx+1];
				let current = history[idx]
				let progression = [current, postcursor];
				let probe = substitutions.map(sub_arr => sub_arr[0].join(">")).indexOf(progression.join(">"));
				if (probe !== -1) {
					display = substitutions[probe][1][0];
					if (["V{B z4}","V{' z4}"].includes(display)) {
						extra_wide_figures = true;
					}
					resolution_lines = true;
				} else if (key !== "" && current.split("/").length == 2) {
					if (current.split("/")[1] == postcursor.split("{")[0]) {
						display = current.split("/")[0]; // + " →"
						applied_arrow = true;
					}
				}
				if (postcursor === "" && (current === "I{z4}" || current === "i{z4}")) {
					display = "{z4}"
				}
			} else { /* no postcursor */
				let current = history[idx]
				if (current === "I{z4}" || current === "i{z4}") {
					display = "{z4}"
				}
			}

			/* TO DO: add horizontal lines */

			if (keyCategory === "h") { // no key
				/* there should be no double-sharp or double-flat roots */
				display = display.replace(/b/g,'♭').replace(/#/g,'♯');
				y = 35;
			}

			this.parseAndDraw(display, x, y, function(text, x, y) {

				text = this.convertSymbols(text).replace(/⌀/g,'⌀'); /* replace: one could improve appearance of half-diminished sign with standard fonts here, but currently using custom font instead */

				offset = 0 - (['\u266D','\u266F','='].includes(text.slice(0,1)) ? ctx.measureText(text.slice(0,1)).width : 0); /* horizontal alignment when label begins with flat, sharp, or equals in lieu of resolution lines */

				var lines = this.wrapText(text);
				this.drawTextLines(lines, x + offset + StaveNotater.prototype.annotateOffsetX, y);

				var first_line_width = this.getContext().measureText(lines[0]).width + offset;

				if (resolution_lines) {
					var x_start = this.annotateOffsetX+x+first_line_width+15;
					var stroke_length = 38; /* should not be hard coded */
					if (extra_wide_figures) {
						x_start += 10;
						stroke_length += -10;
					}
					ctx.beginPath();
						ctx.moveTo(x_start, y-3);
						ctx.lineTo(x_start+stroke_length, y-3);
						ctx.moveTo(x_start, y-12);
						ctx.lineTo(x_start+stroke_length, y-13);
					ctx.stroke();
				}
				resolution_lines = false;

				if (applied_arrow) {
					var x_start = this.annotateOffsetX+x+(first_line_width/2);
					var x_end = this.annotateOffsetX+x+80; /* should not be hard coded */
					ctx.beginPath();
						ctx.lineWidth = 1.5;
						ctx.moveTo(x_start,y+6);
						ctx.bezierCurveTo(x_start+10,y+16,x_end-10,y+16,x_end,y+6);
						ctx.lineTo(x_end-8,y+5);
						ctx.moveTo(x_end,y+6);
						ctx.lineTo(x_end-3,y+14);
					ctx.stroke(); 
				}
				applied_arrow = false;

				return first_line_width; // return the width of the first line for figured bass
			});


			return chord_entry; /* for grading */
		},
		/**
		 * Draws the interval analysis.
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawInterval: function(x, y) {
			var midi_nums = this.chord.getNoteNumbers();
			var interval = this.getAnalyzer().to_interval(midi_nums);

			var ctx = this.getContext();
			var fontArgs = ctx.font.split(' ');
			var newSize = '20px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];
			
			if (interval && interval.name !== '') {
				var lines = this.wrapText(interval.name);
				this.drawTextLines(lines, x + StaveNotater.prototype.annotateOffsetX, y);
			}

			return interval; /* for grading */
		},
		/**
		 * Draws the metronome mark.
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawMetronomeMark: function(x, y) {
			var ctx = this.getContext();
			var tempo = this.getTempo();
			var fontArgs = ctx.font.split(' ');
			var newSize = '16px';
			ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];

			if(tempo) {
				ctx.fillText('M.M. = ' + tempo, x, y + 25);
			}
		},
		/**
		 * Draws the key name (i.e. C major, etc).
		 *
		 * @param {number} x
		 * @param {number} y
		 * @return undefined
		 */
		drawKeyName: function(x, y) {
			var key = this.keySignature.getKeyShortName();
			var thoroughbass = this.analyzeConfig.mode.thoroughbass;
			var letters = this.analyzeConfig.mode.note_names;
			var harmony = this.analyzeConfig.mode.roman_numerals;
			var ctx = this.getContext();
			var fontArgs = ctx.font.split(' ');
			if (key === '' && !thoroughbass && harmony) {
				var newSize = '16px';
				ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];
				ctx.fillText('chords', x - 18, 35);
				if (letters) {
					ctx.fillText('notes', x - 18, 60);
				}
			} else if (key !== '' && !thoroughbass) {
				var newSize = '20px';
				ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];
				ctx.fillText(this.convertSymbols(key) + ':', x - 8, y);
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
		drawTextLines: function(lines, x, y) {
			var ctx = this.getContext(); 
			var line_height = this.textLineHeight;

			for(var i = 0; i < lines.length; i++) {
				var line_y = y + (i * line_height);
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
		parseAndDraw: function(str, x, y, callback) {
			var that = this;
			var figuredBassFont = this.getFiguredBassFont();
			var ctx = this.getContext();
			var padding = ctx.measureText("n").width; // width to use for padding
			var key = this.keySignature.getKey();
			
			FontParser.parse(str, function(text, is_font_token) {
				if (is_font_token) {
					ctx.save();
					ctx.font = figuredBassFont;
					x += callback.call(that, text, x, y + 3); /* tweak figured bass vertical position */
					x += padding / 3;
					ctx.restore();
				} else {
					var fontArgs = ctx.font.split(' ');
					var newSize = ( key == 'h' ? '20px' : '24px'); /* size for chord symbols and Roman numerals */
					ctx.font = newSize + ' ' + fontArgs[fontArgs.length - 1];
					if ( key === "h" && str.length > 6 ) {
						/* add line break to long applied-chord labels */
						x += callback.call(that, text.replace(/\//g,'\n/'), x, y);
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
		notateStave: function() {
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
		drawLabel: function() {
			throw new Error("subclass responsibility");
		},
		/**
		 * Wraps text. Delegates to utility method.
		 *
		 * @param {string} text
		 * @return {array}
		 */
		wrapText: function(text) {
			return util.wrapText(text, this.textLimit);
		},
		/**
		 * Converts symbols to unicode. Delegates to utility method. 
		 *
		 * @param {string} text
		 * @return {string}
		 */
		convertSymbols: function(text) {
			return util.convertSymbols(text);
		}
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
	var TrebleStaveNotater = function(config) {
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
		getY: function() {
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
		drawLabel: function(exercise_midi_nums = false) {
			/* Above the current treble staff */

			var x = this.getX();
			var y = this.getY();
			var notes = this.chord.getNoteNumbers();
			var first_row = y, second_row = y + 25;
			var mode = this.analyzeConfig.mode;

			if(notes.length >= 1) {
				if(mode.scale_degrees && !mode.solfege) {
					this.drawScaleDegree(x, first_row);
				} else if(mode.solfege && !mode.scale_degrees) {
					this.drawSolfege(x, first_row);
				}

				var solfege = this.convertSymbols(this.getAnalyzer().to_solfege(notes));
				if (SHOW_DIAGRAM) {
					var ctx = this.getContext();
					ctx.fillStyle = 'rgb(238, 238, 221)';
					ctx.beginPath();
					ctx.rect(0, 0, 14, 300);
					ctx.fill();
					ctx.fillStyle = 'black';
					let y = 100;
					let w = 12;
					let arrow_pos = [y,y+2*w,y+4*w,y+5*w,y+7*w,y+9*w,y+10*w][['La','So','Fa','Mi','Re','Do','Ti'].indexOf(solfege)]
					ctx.beginPath();
					ctx.moveTo(0, arrow_pos+6);
					ctx.lineTo(13, arrow_pos+6);
					ctx.moveTo(10, arrow_pos+3);
					ctx.lineTo(13, arrow_pos+6);
					ctx.lineTo(10, arrow_pos+9);
					ctx.stroke();
				}

				if(mode.note_names) {
					this.drawNoteName(x, second_row);
				} else if (mode.fixed_do) {
					this.drawFixedDo(x, second_row);
				} else if(notes.length === 1 && mode.scientific_pitch && !mode.note_names) {
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
		notateStave: function(exercise_midi_nums = false) {
			var x = this.getX();
			var y = this.getY();

			if (MASK_TREBLE) {
				var ctx = this.getContext();

				ctx.fillStyle = 'rgb(238, 238, 221)';
				ctx.beginPath();
				ctx.rect(0, 95, 800, 41);
				ctx.rect(0, 95, 21, 123);
				ctx.rect(22, 80, 30, 71);
				ctx.fill();

				ctx.fillStyle = 'black';
			}

			if (SHOW_DIAGRAM) {
				var ctx = this.getContext();

				let y = 100;
				let w = 12;
				let l = 2
				ctx.strokeStyle = 'black';
				ctx.lineWidth = new String(l);
				ctx.beginPath();
				ctx.rect(20, y, w, w);
				ctx.rect(20, y+2*w, w, w);
				ctx.rect(20, y+4*w, w, w);
				ctx.rect(20, y+5*w, w, w);
				ctx.rect(20, y+7*w, w, w);
				ctx.rect(20, y+9*w, w, w);
				ctx.rect(20, y+10*w, w, w);
				ctx.stroke();

				ctx.lineWidth = '0';
				ctx.beginPath();
				ctx.fillStyle = '#ff6666'; // red
				ctx.rect(20+l/2, y+4*w+l/2, w-l, w-l);
				ctx.fill();

				ctx.beginPath();
				ctx.fillStyle = '#66a3ff'; // blue
				ctx.rect(20+l/2, y+5*w+l/2, w-l, w-l);
				ctx.fill();

				ctx.lineWidth = '0';
				ctx.beginPath();
				ctx.fillStyle = '#ffff66'; // yellow
				ctx.rect(20+l/2, y+10*w+l/2, w-l, w-l);
				ctx.fill();

				ctx.fillStyle = 'black';
			}

			if(this.stave.isFirstBar()) {
				this.drawMetronomeMark(x, y);
			}
		}
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
	var BassStaveNotater = function(config) {
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
		getY: function() {
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
		drawLabel: function(exercise_midi_nums = false) {
			/* Below the current bass staff */

			var x = this.getX();
			var y = this.getY(); 
			var midi_nums = this.chord.getNoteNumbers();
			var num_notes = midi_nums.length;
			var mode = this.analyzeConfig.mode;

			/* stores unedited chord labels */
			if (exercise_midi_nums && typeof this.romanNumeralsHistory[this.stave.position.index] === 'undefined') {
				let romanNumerals = exercise_midi_nums.map(midi_arr => this.getAnalyzer().to_chord(midi_arr).label || "");
				var i, len;
				for (i = 0, len = romanNumerals.length; i < len; i += 1) {
					this.romanNumeralsHistory[i+1] = romanNumerals[i];
				}
				// console.log(this.romanNumeralsHistory);
			} else if (!exercise_midi_nums) {
				this.romanNumeralsHistory[this.stave.position.index] = this.getAnalyzer().to_chord(midi_nums).label || "";
			}

			if(num_notes >= 2 && mode.thoroughbass) {
				this.drawThoroughbass(x, y);
			} else if(num_notes == 2 && mode.intervals) {
				this.drawInterval(x, y);
			} else if(num_notes > 2 && mode.roman_numerals) {
				this.drawRoman(x, y);
			}
		},
		/**
		 * Notates the stave.
		 *
		 * Always called, in contrast to drawLabel().
		 *
		 * @return undefined
		 */
		notateStave: function() {
			var x = this.getX();
			var y = this.getY();

			if(this.stave.isFirstBar()) {
				this.drawKeyName(x, y);
			}
		}
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
	StaveNotater.create = function(clef, config) {
		switch(clef) {
			case 'treble':
				return new TrebleStaveNotater(config);
			case 'bass':
				return new BassStaveNotater(config);
			default:
				throw new Error("no such notater for clef: " + clef);
		}
	};

	return StaveNotater;
});
