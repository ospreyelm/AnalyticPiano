define([
	'module',
	'lodash',
	'jquery',
	'app/components/component',
	'app/components/app',
	'app/components/events',
	'app/components/piano',
	'app/components/music',
	'app/components/music/exercise_sheet',
	'app/components/midi',
	'app/components/notifications',
	'app/components/input/shortcuts',
	'app/components/ui/main_menu',
	'app/components/ui/music_controls',
	'app/models/key_signature',
	'app/models/midi_device',
	'app/models/exercise_chord_bank',
	'app/models/exercise_definition',
	'app/models/exercise_grader',
	'app/models/exercise_context'
], function(
	module,
	_,
	$,
	Component,
	AppComponent,
	EVENTS,
	PianoComponent,
	MusicComponent,
	ExerciseSheetComponent,
	MidiComponent,
	NotificationsComponent,
	KeyboardShortcutsComponent,
	MainMenuComponent,
	MusicControlsComponent,
	KeySignature,
	MidiDevice,
	ExerciseChordBank,
	ExerciseDefinition,
	ExerciseGrader,
	ExerciseContext
) {

	/**
	 * AppExerciseComponent class.
	 *
	 * Creates the sandbox environment for playing and experimenting
	 * with chords and chord sequences. This is the basic mode of the
	 * application for students to just play around and try things.
	 *
	 * @constructor
	 */
	var AppExerciseComponent = function(settings) {
		AppComponent.call(this, settings);
	};

	AppExerciseComponent.prototype = new AppComponent();

	AppExerciseComponent.prototype.initListeners = function() {
		this.subscribe(EVENTS.BROADCAST.EXERCISE, (target) => {
			$.ajax({
				"url": target.url,
				"method": "POST",
				"data": {getExercise: true, csrfmiddlewaretoken:$('input[name=csrfmiddlewaretoken]').val()},
			}).then((res) => {
				window.history.pushState("", "", target.url)
				reloadApp(res);
			})
		});
	}

	var reloadApp = function(payload) {
		/**
		 * Returns the models used by the app.
		 */
		AppExerciseComponent.prototype.getModels = function() {
			var models = {};
			var definition = this.getExerciseDefinition()
			models.midiDevice = new MidiDevice();
			models.exerciseDefinition = new ExerciseDefinition({
				definition: definition
			});
			// push exercise-wide features through here
			models.inputChords = new ExerciseChordBank({
				staffDistribution: definition.staffDistribution
			});
			models.exerciseGrader = new ExerciseGrader({
				keySignature: new KeySignature(models.exerciseDefinition.getKey(), models.exerciseDefinition.getKeySignature())
			});
			models.exerciseContext = new ExerciseContext({
				inputChords: models.inputChords,
				grader: models.exerciseGrader,
				definition: models.exerciseDefinition
			});
			models.keySignature = new KeySignature(models.exerciseDefinition.getKey(), models.exerciseDefinition.getKeySignature());
			return models;
		};
	
		/**
		 * Returns the exercise definition.
		 */
		AppExerciseComponent.prototype.getExerciseDefinition = function() {
			var exercise_config = payload? payload : module.config();
			if(!exercise_config) { 
				throw new Error("getExerciseDefinition(): missing exercise configuration data"); 
			}
			return exercise_config; //$.extend(true, {}, exercise_config); // Return deep copy of the config
		};
	
		/**
		 * Returns an array of functions that will create and initialize
		 * each sub-component of the application.
		 *
		 * @return {array} of functions
		 */
		AppExerciseComponent.prototype.getComponentMethods = function() {
			var methods = [
				function () {
					$("#notifications").html('')
					$("#notificationAlerts").html('')
					var c = new NotificationsComponent();
					c.init(this);
					c.renderTo("#notifications", "#notificationAlerts");
					this.addComponent(c);
				},
				function() {
					$("#piano").html('')
					var c = new PianoComponent({
						toolbarConfig: {metronome: false}
					});
					c.init(this);
					c.renderTo("#piano");
					this.addComponent(c);
				},
				function() {
					var c = new MidiComponent({
						chords: this.models.inputChords,
						midiDevice: this.models.midiDevice
					});
					c.init(this);
					this.addComponent(c);
				},
				function() {
					var c = new KeyboardShortcutsComponent({
						keySignature: this.models.keySignature
					});
					c.init(this);
					this.addComponent(c);
				},
				function() {
					var c = new MainMenuComponent({
						headerEl: "#header",
						menuEl: "#mainmenu",
						menuSelector: ".js-btn-menu"
					});
					c.init(this);
					this.addComponent(c);
				},
				function() {
					$("#header .js-keysignature-widget").html('')
					// $("#mainmenu").html('')
					var c = new MusicControlsComponent({
						headerEl: "#header",
						containerEl: "#mainmenu",
						keySignature: this.models.keySignature,
						midiDevice: this.models.midiDevice,
						exerciseContext: this.models.exerciseContext
					});
					c.init(this);
					this.addComponent(c);
				},
				function() {
					var definition = this.models.exerciseContext.getDefinition();
					var c = new MusicComponent({
						el: $("#staff-area"),
						sheet: new ExerciseSheetComponent({
							exerciseContext: this.models.exerciseContext,
							keySignature: this.models.keySignature
						}),
						analysisSettings: definition.getAnalysisSettings(),
						staffDistribution: definition.getStaffDistribution(),
						highlightSettings: definition.getHighlightSettings()
					});
					c.init(this);
					c.render();
					this.addComponent(c);
				}
			];
			return methods;
		};

		app = new AppExerciseComponent();
		app.initListeners();
		app.init();

	};

	/**
	 * Initializes the application.
	 * Intended to be called $(document).ready().
	 * 
	 * @return undefined
	 */
	AppExerciseComponent.ready = function() {
		reloadApp();
		app.log("App ready");
		/**
		 * The following on-off instruction is meant to stimulate a new call
		 * of StaveNotater.prototype.drawRoman so that contextual
		 * analysis modifications within that function become active.
		 * In ExerciseContext, this note is given special treatment not
		 * to generate exercise errors.
		 */
		window.console.dir('send dummy note');
		MidiComponent.prototype.broadcast(EVENTS.BROADCAST.NOTE, 'on', 86, 0);
		MidiComponent.prototype.broadcast(EVENTS.BROADCAST.NOTE, 'off', 86, 0);
		// Ineffective. Try something else
	};

	return AppExerciseComponent;
});
