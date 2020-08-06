/* global define: false */
define([
	'jquery',
	'lodash', 
	'vexflow',
	'file-saver',
	'app/config',
	'app/components/component',
	'./stave',
	'./stave_notater',
	'./play_note_factory'
], function(
	$,
	_, 
	Vex, 
	FileSaver,
	Config,
	Component,
	Stave, 
	StaveNotater,
	PlayNoteFactory
) {
	"use strict";

	/**
	 * Defines the size of the chord bank (how many chords to display on
	 * screen).
	 * @type {number}
	 */
	var CHORD_BANK_SIZE = Config.get('general.chordBank.displaySize');

	/**
	 * PlaySheetComponent
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
	var PlaySheetComponent = function(settings) {
		this.settings = settings || {};

		if("chords" in this.settings) {
			this.chords = this.settings.chords;
		} else {
			throw new Error("missing settings.chords");
		}

		if("keySignature" in this.settings) {
			this.keySignature = this.settings.keySignature;
		} else {
			throw new Error("missing settings.keySignature");
		}

		_.bindAll(this, [
			'render',
			'onChordsUpdate'
		]);
	};

	PlaySheetComponent.prototype = new Component();

	_.extend(PlaySheetComponent.prototype, {
		/**
		 * Initializes the sheet.
		 *
		 * @param {object} config
		 * @return undefined
		 */
		initComponent: function() {
			this.el = $("canvas#staff");
			this.el[0].width= this.el.width();
			this.el[0].height= this.el.height();
			this.initRenderer();
			this.initStaves();
			this.initListeners();
		},
		/**
		 * Initializes the canvas renderer and dom element.
		 *
		 * @return
		 */
		initRenderer: function() {
			var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
			this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
		},
		/**
		 * Initializes the staves that together will form the grand staff.
		 *
		 * @return undefined
		 */
		initStaves: function() {
			this.updateStaves();
		},
		/**
		 * Initializes event listeners.
		 *
		 * @return undefined
		 */
		initListeners: function() {
			this.parentComponent.bind('change', this.render);
			this.keySignature.bind('change', this.render);
			this.chords.bind('change', this.render);
			this.chords.bind('clear', this.onChordsUpdate);
			this.chords.bind('bank', this.onChordsUpdate);
		},
		/**
		 * Renders the grand staff and everything on it.
		 *
		 * @return this
		 */
		render: function() { 
			this.clear();
			this.renderStaves();
			return this;
		},
		/**
		 * Clears the sheet.
		 *
		 * @return this
		 */
		clear: function() {
			this.vexRenderer.getContext().clear();
			return this;
		},
		/**
		 * Renders each individual stave.
		 *
		 * @return this
		 */
		renderStaves: function() {
			var i, len, stave, _staves = this.staves;
			for(i = 0, len = _staves.length; i < len; i++) {
				stave = _staves[i];
				stave.render();
			}
			return this;
		},
		/**
		 * Resets the staves.
		 *
		 * @return this
		 */
		resetStaves: function() {
			_.invoke(this.staves, "destroy");
			this.staves = [];
			return this;
		},
		/**
		 * Adds staves.
		 *
		 * @param {array} staves
		 * @return this
		 */
		addStaves: function(staves) {
			this.staves = this.staves.concat(staves);
			return this;
		},
		/**
		 * Updates and configures the staves.
		 *
		 * @return this
		 */
		updateStaves: function() {
			var limit = CHORD_BANK_SIZE;
			var items = this.chords.items({limit: limit, reverse: true});
			var position = {
				index: 0,
				count: items.length,
				maxCount: CHORD_BANK_SIZE
			};
			var staves = []; /* the successive items of this array will correspond to measures */

			/* the first vexflow measure is a special case: it is reserved to
			 * show the clef and key signature and nothing else */
			var treble = this.createDisplayStave('treble', _.clone(position));
			var bass = this.createDisplayStave('bass', _.clone(position));
			position.index += 1;
			treble.connect(bass);
			staves.push(treble);

			/* add the subsequent measures */
			for(var i = 0; i < items.length; i++) {
				let chord = items[i].chord;
				let isBanked = items[i].isBanked;
				let isNovel = items[i].isNovel;
				treble = this.createNoteStave('treble', _.clone(position), chord, isBanked, isNovel);
				bass = this.createNoteStave('bass', _.clone(position), chord, isBanked, isNovel);
				position.index += 1;
				treble.connect(bass);
				staves.push(treble);
			}

			this.resetStaves();
			this.addStaves(staves);

			return this;
		},
		/**
		 * Creates a stave to display the clef, key signature, etc.
		 *
		 * @param {string} clef
		 * @param {object} position
		 * @return {Stave}
		 */
		createDisplayStave: function(clef, position) {
			var stave = new Stave(clef, position);
			var stave_notater = this.createStaveNotater(clef, {
				stave: stave,
				keySignature: this.keySignature,
				analyzeConfig: this.getAnalyzeConfig()
			});

			stave.setRenderer(this.vexRenderer);
			stave.setKeySignature(this.keySignature);
			stave.setNotater(stave_notater);
			stave.setMaxWidth(this.getWidth());
			stave.updatePosition();

			return stave;
		},
		/**
		 * Creates a stave to display notes.
		 *
		 * @param {string} clef
		 * @param {object} position
		 * @param {Chord} chord
		 * @return {Stave}
		 */
		createNoteStave: function(clef, position, chord, isBanked, isNovel) {
			var stave = new Stave(clef, position);

			stave.setRenderer(this.vexRenderer);
			stave.setKeySignature(this.keySignature);
			stave.setNoteFactory(new PlayNoteFactory({
				clef: clef,
				chord: chord,
				isBanked: isBanked,
				isNovel: isNovel,
				keySignature: this.keySignature,
				highlightConfig: this.getHighlightConfig()
			}));
			stave.setNotater(this.createStaveNotater(clef, {
				stave: stave,
				chord: chord,
				keySignature: this.keySignature,
				analyzeConfig: this.getAnalyzeConfig()
			}));
			stave.setMaxWidth(this.getWidth());
			stave.updatePosition();
			stave.setBanked(isBanked);
			stave.setNovel(isNovel);

			return stave;
		},
		/**
		 * Creates an instance of StaveNotater.
		 *
		 * @param {string} clef The clef, treble|bass, to create.
		 * @param {object} config The config for the StaveNotater.
		 * @return {object}
		 */
		createStaveNotater: function(clef, config) {
			return StaveNotater.create(clef, config);
		},
		/**
		 * Returns the width of the sheet.
		 *
		 * @return {number}
		 */
		getWidth: function() {
			return this.el.width();
		},
		/**
		 * Returns the height of the sheet.
		 *
		 * @return {number}
		 */
		getHeight: function() {
			return this.el.height();
		},
		/**
		 * Returns the analysis settings of the sheet.
		 *
		 * @return {object}
		 */
		getAnalyzeConfig: function() {
			return this.parentComponent.analyzeConfig;
		},
		/**
		 * Returns the highlight settings of the sheet.
		 *
		 * @return {object}
		 */
		getHighlightConfig: function() {
			return this.parentComponent.highlightConfig;
		},
		/**
		 * Handles a chord bank update.
		 *
		 * @return undefined
		 */
		onChordsUpdate: function() {
			this.dataForSave(); /* for development */
			this.updateStaves();
			this.render();
		},
		
		/* For development only: these are the properties to save with MusicControlsComponent.onClickDownloadJSON and .onClickUploadJSON */
		dataForSave: function() {
			const objs = this.chords._items.map(items => items._notes);
			let chords = [];
			let i, len;
			for (i = 0, len = objs.length-1; i < len; i++) {
				let obj = objs[i]
				let keys = Object.keys(obj);
				let visible = keys.filter(function(key) {
				    return obj[key]
				}).map(key => parseInt(key));
				let hidden = [];
				chords.unshift({"visible":visible,"hidden":hidden});
			}

			const save_me = JSON.stringify({
				"tempo": this.parentComponent.analyzeConfig.tempo,
				"keySignature": this.keySignature.signatureSpec,
				"key": this.keySignature.key,
				"chord": chords,
				"type": "matching",
				"introText": "",
				"reviewText": "",
				// "staffDistribution": Config.__config.general.staffDistribution,
				"analysis": this.parentComponent.analyzeConfig,
				"highlight": this.parentComponent.highlightConfig
			}, null, 2);
			// console.log(save_me);

			var blob = new Blob([save_me], {type: "application/json;charset=utf-8"});
			return true;
		},
	});

	return PlaySheetComponent;
});
