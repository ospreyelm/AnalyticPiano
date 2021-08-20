define([
	'lodash', 
	'vexflow',
	'app/utils/analyze',
	'./stave_note_factory'
], function(
	_, 
	Vex, 
	Analyze,
	StaveNoteFactory
) {
	"use strict";

	/**
	 * PlayNoteFactory class.
	 *
	 * This class knows how to create Vex.Flow.StaveNote objects for play sheet.
	 *
	 * @constructor
	 * @param {object} settings
	 * @param {object} settings.clef
	 * @param {object} settings.chord 
	 * @param {object} settings.keySignature
	 * @param {object} settings.highlightConfig
	 * @param {object} settings.isBanked
	 * @return
	 */
	var PlayNoteFactory = function(settings) {
		this.settings = settings || {};

		_.each(['chord','keySignature','clef','highlightConfig','isBanked','isNovel','activeAlterations'], function(prop) {
			if(prop in this.settings) {
				this[prop] = this.settings[prop];
			} else {
				throw new Error("missing required settings."+prop);
			}
		}, this);

		this.init();
	};

	_.extend(PlayNoteFactory.prototype, {
		/**
		 * Initializes the object.
		 *
		 * @param {object} config
		 * @return
		 */
		init: function(config) {
			/**
			 * Color for banked notes. 
			 * @type {string}
			 */
			this.bankedColor = 'rgb(0,0,0)';
			this.unchangedColor = 'rgba(0,0,0,0)';

			_.bindAll(this, ['createModifiers']);

			this.staveNoteFactory = new StaveNoteFactory({
				chord: this.chord,
				keySignature: this.keySignature,
				clef: this.clef,
				highlightConfig: this.highlightConfig,
				modifierCallback: this.createModifiers,
				activeAlterations: Object.create(null)
			});
		},
		/**
		 * Creates one more Vex.Flow.StaveNote's.
		 *
		 * @public
		 * @return {array}
		 */
		createStaveNotes: function(duration = undefined) {
			return this.staveNoteFactory.createStaveNotes(duration);
		},
		/**
		 * Returns true if there are any stave notes to create, false otherwise.
		 *
		 * @public
		 * @return {boolean}
		 */
		hasStaveNotes: function() {
			return this.staveNoteFactory.hasStaveNotes();
		},
		/**
		 * Returns rhythm value.
		 *
		 */
		getRhythmValue: function() {
			return this.staveNoteFactory.getRhythmValue();
		},
		/**
		 * Returns an array of modifer functions to modify a Vex.Flow.StaveNote.
		 *
		 * @return {array}
		 */
		createModifiers: function() {
			var keys = this.staveNoteFactory.getNoteKeys();
			var accidentals = this.staveNoteFactory.getAccidentalsOf(keys);
			var allMidiKeys = this.chord.getNoteNumbers(); // for highlightConfig across stave boundaries
			var clefMidiKeys = this.chord.getNoteNumbers(this.clef);
			var modifiers = [];
			var note, noteStyle;

			this.staveNoteFactory.resetHighlight();

			for(var i = 0, len = keys.length; i < len; i++) {
				note = clefMidiKeys[i];

				// Apply accidentals (if any)
				if(accidentals[i]) {
					modifiers.push(this.staveNoteFactory.makeAccidentalModifier(i, accidentals[i]));
				}

				// Set highlight colors on notes
				if(this.isBanked) {
					this.staveNoteFactory.highlightNote(i, this.getBankedColorStyle(), 1);
				}
				if(this.highlightConfig.enabled) {
					noteStyle = this.staveNoteFactory.getAnalysisHighlightOf(note, allMidiKeys);
					if(noteStyle !== false) {
						this.staveNoteFactory.highlightNote(i, noteStyle, 2);
					}
				}
				// NOT WORKING YET: adding isNovel property
				// if the set of active notes matches the most recent bank
				if(!this.isBanked) {
					if(true) {
						if(this.isNovel === false) {
							this.staveNoteFactory.highlightNote(i, this.getUnchangedColorStyle(), 1);
						}
					}
				}

				noteStyle = this.staveNoteFactory.getHighlightOf(i);
				modifiers.push(this.staveNoteFactory.makeHighlightModifier(i, noteStyle));
			}

			if (noteStyle.strokeStyle === 'rgba(0,0,0,0)') {
				/* Hide ledger lines, stems from treble staff in bass solo mode
				 * See Analyze.spellingAndAnalysisFunctions.get_color
				 * which depends on this.Piano.highlightMode["solobass"] */
				modifiers.push(this.staveNoteFactory.setStemStyle(noteStyle));
				modifiers.push(this.staveNoteFactory.setLedgerLineStyle(noteStyle));
			}

			return modifiers;
		},
		/**
		 * Returns the highlight color styles for banked notes.
		 *
		 * @protected
		 * @return {object}
		 */
		getBankedColorStyle: function() {
			return {fillStyle:this.bankedColor, strokeStyle:this.bankedColor};
		},
		getUnchangedColorStyle: function() {
			return {fillStyle:this.unchangedColor, strokeStyle:this.unchangedColor};
		}
	});

	return PlayNoteFactory;
});
