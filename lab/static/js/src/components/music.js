define([
	'jquery',
	'lodash', 
	'app/config',
	'app/components/events',
	'app/components/component',
	'app/models/key_signature',
	'./music/play_sheet'
], function(
	$, 
	_, 
	Config,
	EVENTS,
	Component,
	KeySignature,
	PlainSheetComponent
) {
	/**
	 * This is a map of analysis modes to booleans indicating whether the mode
	 * is enabled or disabled by default.
	 * @type {object}
	 */
	var ANALYSIS_SETTINGS = Config.get('general.analysisSettings');
	/**
	 * This is a map of highlight modes to booleans indicating whether the mode
	 * is enabled or disabled by default.
	 * @type {object}
	 */
	var HIGHLIGHT_SETTINGS = Config.get('general.highlightSettings');

	var STAFF_DISTRIBUTION = Config.get('general.staffDistribution');

	/**
	 * Creates an instance of MusicComponent.
	 *
	 * This object is responsible for displaying the sheet music and
	 * handling runtime configuration changes.
	 *
	 * @constructor
	 * @param {object} settings
	 * @param {Sheet} settings.sheet Required property.
	 */
	var MusicComponent = function(settings) {
		this.settings = settings || {};
		this.settings.analysisSettings = this.settings.analysisSettings || {};
		this.settings.highlightSettings = this.settings.highlightSettings || {};

		/**
		 * Defines the music element.
		 * @type {jQuery}
		 */
		this.el = $('<div></div>');
		/**
		 * Configuration settings for highlighting notes on the sheet music.
		 * @type {object}
		 */
		this.highlightConfig = _.extend({}, HIGHLIGHT_SETTINGS, this.settings.highlightSettings);
		/**
		 * Configuration settings for analyzing notes on the sheet music.
		 * @type {object}
		 */
		this.analyzeConfig = _.extend({tempo:false}, ANALYSIS_SETTINGS, this.settings.analysisSettings);
		/**
		 * Configuration settings for staff distribution on the sheet music.
		 * @type {object}
		 */
		this.staffDistributionConfig = _.extend({}, STAFF_DISTRIBUTION, this.settings);
		

		if(!("sheet" in this.settings)) {
			throw new Error("missing settings.sheet parameter");
		}

		// this.setComponent("pristine", this.settings.pristine);
		this.setComponent("sheet", this.settings.sheet);

		_.bindAll(this, [
			'onAnalyzeChange',
			'onHighlightChange',
			'onStaffDistributionChange',
			'onMetronomeChange',
			'onRedrawRequest'
		]);
	};

	MusicComponent.prototype = new Component();

	_.extend(MusicComponent.prototype, {
		/**
		 * Initializes the music.
		 *
		 * @return undefined
		 */
		initComponent: function() {
			this.initListeners();
		},
		/**
		 * Initializes event listeners.
		 *
		 * @return undefined
		 */
		initListeners: function() {
			this.subscribe(EVENTS.BROADCAST.HIGHLIGHT_NOTES, this.onHighlightChange);
			this.subscribe(EVENTS.BROADCAST.ANALYZE_NOTES, this.onAnalyzeChange);
			this.subscribe(EVENTS.BROADCAST.ANALYZE_NOTES, this.onStaffDistributionChange); // ?
			this.subscribe(EVENTS.BROADCAST.METRONOME, this.onMetronomeChange);
			this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onRedrawRequest);
		},
		/**
		 * Renders the music.
		 *
		 * @return this
		 */
		render: function() { 
			this.renderSheet();
			return this;
		},
		/**
		 * Renders the sheet.
		 *
		 * @return this
		 */
		renderSheet: function() {
			var sheetComponent = this.getComponent('sheet');
			sheetComponent.clear();
			sheetComponent.render();
			return this;
		},
		renderPristine: function() {
			var sheetComponent = this.getComponent('sheet');

			if (!sheetComponent.hasOwnProperty('exerciseContext')) {

				/* play view */
				sheetComponent.chords.clear();

			} else {

				/* exercise view */
				let scex = sheetComponent.exerciseContext;

				scex.inputChords.clear();
				scex.inputChords.goTo(0);

				let setdef = scex.settings.definition;

				// Used to generate new data
				// let currentData = setdef.settings.definition;
				// console.log(JSON.stringify(currentData, null, 0));

				var testing = false;
				if (testing) {

					/* MAKE THE AJAX CALL AND PREPARE NEEDED PROPERTIES HERE */

					// The following variable was pasted from the console output above on a different exercise
					var newData = {"type":"analytical_pcs","staffDistribution":"chorale","introText":"TEST OF REFRESH BUTTON WITH NEW DATA!!! Should show key signature of one flat and letter names, feature chorale distribution of four parts if played, and grade analytically.","keySignature":"b","key":"h","chord":[{"visible":[53,60,65,69],"hidden":[]},{"visible":[67],"hidden":[]},{"visible":[69],"hidden":[]}],"reviewText":"","analysis":{"enabled":true,"mode":{"note_names":true,"scientific_pitch":false,"scale_degrees":false,"solfege":false,"roman_numerals":true,"intervals":false}},"highlight":{"enabled":true,"mode":{"roothighlight":true,"tritonehighlight":false}},"id":"Easy_Notes/03","name":"03","url":"/lab/exercises/Easy_Notes/03","group_name":"Easy_Notes","selected":true,"nextExercise":"/lab/exercises/Easy_Notes/04","previousExercise":"/lab/exercises/Easy_Notes/02","exerciseList":[{"id":"Easy_Notes/01","name":"01","url":"/lab/exercises/Easy_Notes/01","selected":false},{"id":"Easy_Notes/02","name":"02","url":"/lab/exercises/Easy_Notes/02","selected":false},{"id":"Easy_Notes/03","name":"03","url":"/lab/exercises/Easy_Notes/03","selected":true},{"id":"Easy_Notes/04","name":"04","url":"/lab/exercises/Easy_Notes/04","selected":false}]};

					scex.definition.exercise
						= scex.definition.parse(newData);

					scex.definition.settings.definition
						= newData;

					scex.settings.definition.exercise
						= scex.definition.parse(newData);

					scex.settings.definition.settings.definition
						= newData;

					sheetComponent.keySignature
						= new KeySignature(newData.key, newData.keySignature);

					sheetComponent.settings.keySignature
						= new KeySignature(newData.key, newData.keySignature);

					// DOES NOT HAVE EXPECTED EFFECT
					this.settings.staffDistribution
						= newData.staffDistribution;

					this.staffDistributionConfig.staffDistribution
						= newData.staffDistribution;

					/* similar to updateSettings */
					// is there a way to do these things once each?
					Object.assign(this.analyzeConfig, newData.analysis);
					Object.assign(this.settings.analysisSettings, newData.analysis);
					Object.assign(this.staffDistributionConfig.analysisSettings, newData.analysis);

					Object.assign(this.highlightConfig, newData.highlight);
					Object.assign(this.settings.highlightSettings, newData.highlight);
					Object.assign(this.staffDistributionConfig.highlightSettings, newData.highlight);
					/* add use of listeners here to update the menu */

					scex.inputChords.staffDistribution = newData.staffDistribution;
					scex.displayChords = scex.createDisplayChords();
					scex.exerciseChords = scex.createExerciseChords();

					this.trigger('change');
				}

				scex.state = "ready"; // READY
				// sheetComponent.renderExerciseText(); // not necessary
				scex.sealed = false;
				scex.done = false;
				scex.timer = null;
				scex.timepoints = [];

				window.console.dir('send dummy note');
				this.broadcast(EVENTS.BROADCAST.NOTE, 'on', 109, 0);
				this.broadcast(EVENTS.BROADCAST.NOTE, 'off', 109, 0);
			}

			sheetComponent.clear();
			sheetComponent.render();

			return this;
		},
		/**
		 * Returns the width.
		 *
		 * @return {number}
		 */
		getWidth: function() {
			return this.el.width(); 
		},
		/**
		 * Returns the height.
		 *
		 * @return {number}
		 */
		getHeight: function() {
			return this.el.height();
		},
		/**
		 * Handles a change to the highlight settings.
		 *
		 * @param {object} settings
		 * @return undefined
		 */
		onHighlightChange: function(settings) {
			this.updateSettings('highlightConfig', settings);
			this.trigger('change');
		},
		/**
		 * Handles a change to the analyze settings.
		 *
		 * @param {object} settings
		 * @return undefined
		 */
		onAnalyzeChange: function(settings) {
			this.updateSettings('analyzeConfig', settings);
			this.trigger('change');
		},
		/**
		 * Handles a change to the staff distribution setting.
		 *
		 * @param {object} settings
		 * @return undefined
		 */
		onStaffDistributionChange: function(settings) {
			this.updateSettings('staffDistributionConfig', settings);
			this.trigger('change');
		},
		/**
		 * Handles a change to the metronome settings.
		 *
		 * @param {object} settings
		 * @return undefined
		 */
		onMetronomeChange: function(metronome) {
			if(metronome.isPlaying()) {
				this.analyzeConfig.tempo = metronome.getTempo();
			} else {
				this.analyzeConfig.tempo = false;
			}
			this.render();
		},
		onRedrawRequest: function() {
			this.renderPristine();
		},
		/**
		 * Updates settings.
		 *
		 * @param {string} prop
		 * @param {object} setting
		 * @return this
		 */
		updateSettings: function(prop, setting) {
			var mode = _.cloneDeep(this[prop].mode);
			switch(setting.key) {
				case "enabled":
					this[prop].enabled = setting.value; 
					break;
				case "mode":
					_.assign(mode, setting.value);	
					this[prop].mode = mode;
					break;
				default:
					throw new Error("Invalid setting key");
			}
			return this;
		},
	});

	return MusicComponent;
});
