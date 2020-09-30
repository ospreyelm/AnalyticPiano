define([
	'lodash', 
	'app/config',
	'app/components/events',
	'app/components/component',
	'app/models/exercise_context'
], function(
	_,
	Config,
	EVENTS,
	Component,
	ExerciseContext
) {

	/**
	 * Defines the default instrument (Acoustic Grand Piano).
	 * @type {number}
	 * @const
	 */
	var DEFAULT_INSTRUMENT = 0;
	/**
	 * Defines the default note velocity used to send NOTE ON messages. 
	 * @type {number}
	 * @const
	 */
	var DEFAULT_NOTE_VELOCITY = 64;
	/**
	 * Defines the note velocity used to reduce the volume of NOTE ON messages.
	 * @type {number}
	 * @const
	 */
	var SOFT_NOTE_VELOCITY = 32;
	/**
	 * Maps MIDI message commands to their numerical codes
	 */
	var MIDI_MSG_MAP = {
		NOTE_OFF : [0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x88,0x89,0x8A,0x8B,0x8C,0x8D,0x8E,0x8F], // 128-143
		NOTE_ON : [0x90,0x91,0x92,0x93,0x94,0x95,0x96,0x97,0x98,0x99,0x9A,0x9B,0x9C,0x9D,0x9E,0x9F], // 144-159
		POLY_PRESSURE : 0xA0, // 160
		CONTROL_CHANGE : 0xB0, // 176
		PROGRAM_CHANGE : 0xC0, // 192
	};
	/**
	 * Maps MIDI control numbers to names and vice versa for lookup
	 * @type {object}
	 * @const
	 */
	var MIDI_CONTROL_MAP = {
		'pedal': {
			'64': 'sustain',
			'66': 'sostenuto', 
			'67': 'soft',
			'sustain': 64,
			'sostenuto': 66,
			'soft': 67
		}
	};
	/**
	 * Defines the title of the midi error.
	 * @type {string} 
	 * @const
	 */
	var MIDI_ERROR_TITLE = Config.get("errorText.midiPluginError.title");
	/**
	 * Defines the content of the midi error.
	 * @type {string} 
	 * @const
	 */
	var MIDI_ERROR_CONTENT = Config.get("errorText.midiPluginError.description");

	var SUSTAINING = false;
	var SOSTENUTO_ON = false;
	var UNA_CORDA_ON = false;
	/**
	 * MidiComponent
	 *
	 * This component coordinates the interactions between the application and
	 * the MIDI device driver (i.e. browser plugin). It listens for MIDI-related
	 * messages from the application and translates them into instructions for
	 * the MIDI driver and vice versa. 
	 *
	 * @constructor
	 * @param {object} settings
	 * @param {object} settings.chords Chords object (required).
	 * @param {object} settings.midiDevice MidiDevice object (required).
	 */
	var MidiComponent = function(settings) {
		/**
		 * Configuration.
		 * @type {object}
		 * @protected
		 */
		this.settings = settings || {};
		/**
		 * The midi channel used to transmit messages.
		 * @type {number}
		 * @protected
		 */
		this.midiChannel = 1;
		/**
		 * The MIDI access object used to send/receive MIDI messages.
		 * @type {object}
		 * @protected
		 */
		this.midiAccess = null;
		/**
		 * The note velocity used to send NOTE ON midi messages. 
		 * @type {number}
		 * @protected
		 */
		this.noteVelocity = DEFAULT_NOTE_VELOCITY;
		/**
		 * The MidiDevice object that knows which MIDI input/output devices are
		 * available and how to use them.
		 * @type {object}
		 * @protected
		 */
		this.midiDevice = null;
		/**
		 * Holds a reference to the Chords object. 
		 * @type {object}
		 * @protected
		 */
		this.chords = null;

		_.bindAll(this, [
			'onMidiMessage',
			'onNoteChange',
			'onClearNotes',
			'onBankNotes',
			'onPedalChange',
			'onInstrumentChange',
			'onTransposeChange',
			'onWebMIDIInit',
			'onWebMIDIError'
		]);
	};

	MidiComponent.prototype = new Component();

	_.extend(MidiComponent.prototype, {
		/**
		 * Initializes the MidiComponent.
		 *
		 * @return undefined
		 */
		initComponent: function() {
			if(!("chords" in this.settings)) {
				throw new Error("missing settings.chords");
			} 
			if(!("midiDevice" in this.settings)) {
				throw new Error("missing settings.midiDevice");
			} 

			this.chords = this.settings.chords;
			this.midiDevice = this.settings.midiDevice;

      if (navigator.requestMIDIAccess === undefined) {
        this.onWebMIDIError();
      }
			else navigator.requestMIDIAccess().then(this.onWebMIDIInit, this.onWebMIDIError);
		},
		/**
		 * Called when WebMIDI has been initialized and is ready for access.
		 *
		 * @param {object} MIDIAccess
		 * @return undefined
		 */
		onWebMIDIInit: function(MIDIAccess) {
			this.setMIDIAccess(MIDIAccess);
			this.midiDevice.setUpdater(function() {
				var inputs = Array.from(MIDIAccess.inputs.values());
				var outputs = Array.from(MIDIAccess.outputs.values());
				this.clear();
				this.setSources(inputs, outputs);
				this.selectDefaults(inputs);
			});
			this.updateDevices();
			this.initListeners();
		},
		/**
		 * Called when WebMIDI encounters an error while it is initializing itself.
		 *
		 * @return undefined
		 */
		onWebMIDIError: function() {
			this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
				type: "error",
				title: MIDI_ERROR_TITLE,
				description: MIDI_ERROR_CONTENT
			});
			this.initListeners();
		},
		/**
		 * Initializes listeners.
		 *
		 * @return undefined
		 */
		initListeners: function() {
			this.subscribe(EVENTS.BROADCAST.NOTE, this.onNoteChange);
			this.subscribe(EVENTS.BROADCAST.CLEAR_NOTES, this.onClearNotes);
			this.subscribe(EVENTS.BROADCAST.BANK_NOTES, this.onBankNotes);
			this.subscribe(EVENTS.BROADCAST.PEDAL, this.onPedalChange);
			this.subscribe(EVENTS.BROADCAST.INSTRUMENT, this.onInstrumentChange);
			this.subscribe(EVENTS.BROADCAST.TRANSPOSE, this.onTransposeChange);
			this.midiDevice.bind("midimessage", this.onMidiMessage);
		},
		/**
		 * Sets the MIDI Access bridge.
		 *
		 * @param {object} MIDIAccess
		 * @return undefined
		 */
		setMIDIAccess: function(MIDIAccess) {
			if(MIDIAccess) {
				this.midiAccess = MIDIAccess;
			}
		},
		/**
		 * Detects the devices that are available.
		 *
		 * @return undefined
		 * @fires devices
		 */
		updateDevices: function() {
			this.midiDevice.update();
		},
		/**
		 * Returns true if the control message maps to a supported pedal.
		 *
		 * @param {number} controlNum MIDI control change number
		 * @return {boolean}
		 */
		isPedalControlChange: function(controlNum) {
			return MIDI_CONTROL_MAP.pedal.hasOwnProperty(controlNum);
		},
		/**
		 * Broadcasts a pedal change event to the application.
		 *
		 * @param {number} controlNum
		 * @param {number} controlVal
		 * @return undefined
		 */
		triggerPedalChange: function(controlNum, controlVal) {
			var pedal_name = MIDI_CONTROL_MAP.pedal[controlNum];
			// var pedal_state = 'off';

			// The Yamaha FC5 sustain pedal sends value 0 when 
			// the pedal is depressed and 127 when it is released.
		
			// if(controlVal == 0 && !SUSTAINING) {
			// 	if(pedal_name == 'sustain'){
			// 		SUSTAINING = true;
			// 	}
			// 	else {};
			// 	pedal_state = 'on';
			// } else if(controlVal == 127 && SUSTAINING) {
			// 	if(pedal_name == 'sustain'){
			// 		SUSTAINING = false;
			// 	}
			// 	else {};
			// 	pedal_state = 'off';
			// } else { pedal_state = 'null' };

			// The Yamaha Silent Piano sustain pedal sends value 0 when 
			// the pedal is released and other values when it is depressed.
		
			if(pedal_name == 'sustain') {
				if (!SUSTAINING && controlVal >= 50) {
					SUSTAINING = true;
					pedal_state = 'on';
				} else if (SUSTAINING && controlVal == 0) {
					SUSTAINING = false;
					pedal_state = 'off';
				} else {
					pedal_state = 'null';
				};
			}
			else if (pedal_name == 'soft') {
				if (!UNA_CORDA_ON && controlVal >= 50) {
					UNA_CORDA_ON = true;
					pedal_state = 'on';
				} else if (UNA_CORDA_ON && controlVal == 0) {
					UNA_CORDA_ON = false;
					pedal_state = 'off';
				} else {
					pedal_state = 'null';
				};
			}
			else if (pedal_name == 'sostenuto') {
				if (!SOSTENUTO_ON && controlVal >= 50) {
					SOSTENUTO_ON = true;
					// pedal_state = 'on';
					this.broadcast(EVENTS.BROADCAST.NEXTEXERCISE);
				} else if (SOSTENUTO_ON && controlVal == 0) {
					SOSTENUTO_ON = false;
					// pedal_state = 'off';
				} else {
					// pedal_state = 'null';
				};
			}
			else { pedal_state = 'null' };

			if(pedal_state != 'null') {
				this.broadcast(EVENTS.BROADCAST.PEDAL, pedal_name, pedal_state);
			};
		},
		/**
		 * Broadcasts a note "on" event to the application.
		 *
		 * @param {number} noteNum
		 * @param {number} noteVelocity
		 * @return undefined
		 */
		triggerNoteOn: function(noteNum, noteVelocity) {
			if(this.noteVelocity !== null) {
				noteVelocity = this.noteVelocity;
			}
			this.broadcast(EVENTS.BROADCAST.NOTE, 'on', noteNum, noteVelocity);
		},
		/**
		 * Broadcasts a note "off" event to the application.
		 *
		 * @param {number} noteNum
		 * @param {number} noteVelocity
		 * @return undefined
		 */
		triggerNoteOff: function(noteNum, noteVelocity) {
			if(this.noteVelocity !== null) {
				noteVelocity = this.noteVelocity;
			}
			this.broadcast(EVENTS.BROADCAST.NOTE, 'off', noteNum, noteVelocity);
		},
		/**
		 * Toggles a note in the chord model.
		 *
		 * @param {string} noteState on|off
		 * @param {number} noteNumber
		 * @param {extra} extra.overrideSustain true|false overrides sustain
		 * @return undefined
		 */
		toggleNote: function(noteState, noteNumber, extra) {
			var toggle = (noteState === 'on' ? 'noteOn' : 'noteOff');
			var chord = this.chords.current();
			var noteObj = {notes: [noteNumber]};
			if(extra && typeof extra === 'object') {
				_.assign(noteObj, extra);
			}
			chord[toggle](noteObj);
		},
		/**
		 * Handles a MIDI message received from the MIDI device.
		 *
		 * @param {object} msg
		 * @return undefined
		 */
		onMidiMessage: function(msg) {
			var command = msg.data[0];

			// NOTE_ON with velocity == 0 or undefined => NOTE_OFF
			if (MIDI_MSG_MAP.NOTE_ON.indexOf(command) !== -1 && (!msg.data[2] || msg.data[2] == 0)) {
				// Get NOTE_OFF command for corresponding channel
				command = MIDI_MSG_MAP.NOTE_OFF[MIDI_MSG_MAP.NOTE_ON.indexOf(command)];
			}

			if (MIDI_MSG_MAP.NOTE_ON.indexOf(command) !== -1) {
				this.triggerNoteOn(msg.data[1], msg.data[2]);
			}
			else if (MIDI_MSG_MAP.NOTE_OFF.indexOf(command) !== -1) {
				this.triggerNoteOff(msg.data[1], msg.data[2]);
			}
			else if (MIDI_MSG_MAP.CONTROL_CHANGE === command) {
				if(this.isPedalControlChange(msg.data[1])) {
					this.triggerPedalChange(msg.data[1], msg.data[2]);
				}
			}
			else {
				console.log("MIDI message not handled: ", msg);
			}
		},
		/**
		 * Handles a note change event and sends a NOTE ON/OFF message to the
		 * MIDI device.
		 *
		 * @param {string} noteState on|off
		 * @param {number} noteNumber
		 * @param {object} extra
		 * @return undefined
		 */
		onNoteChange: function(noteState, noteNumber, extra) {
			var channel_idx = this.midiChannel - 1;
			var command = (noteState === 'on' ? MIDI_MSG_MAP.NOTE_ON[channel_idx] : MIDI_MSG_MAP.NOTE_OFF[channel_idx]);
			this.toggleNote(noteState, noteNumber, extra);
			if (SUSTAINING && noteState === 'off') {
				// will be turned off by onPedalChange when sustain is released
			} else {
				this.sendMIDIMessage(command, noteNumber, this.noteVelocity);
			}
		},
		/**
		 * Clears all notes that are sounding.
		 *
		 * @return undefined
		 */
		onClearNotes: function() {
			this.sendAllNotesOff();

			if(this.chords.anySustained()) {
				this.sendMIDIPedalMessage('sustain', 'off');
				this.sendMIDIPedalMessage('sustain', 'on');
			}

			this.chords.clear();
		},
		/**
		 * Banks the current chord notes.
		 *
		 * @return undefined
		 */
		onBankNotes: function(request_origin = "unknown") {
			/* critical side-effect */
			var notes_off = this.chords.bank(request_origin);
			if (request_origin === 'ui') {
				// Lift pedal on ui-originating chord bank
				this.broadcast(EVENTS.BROADCAST.PEDAL, 'sustain', 'off', 'ui');
				this.turnOffSustainedNotesOnPedalLift(notes_off);
			}
		},
		turnOffSustainedNotesOnPedalLift: function(notes_off) {
			var i, len;
			for (i = 0, len = notes_off.length; i < len; i++) {
				let channel_idx = this.midiChannel - 1;
				let command = MIDI_MSG_MAP.NOTE_OFF[channel_idx];
				this.sendMIDIMessage(command, notes_off[i], 0);
			}
		},
		/**
		 * Handles a pedal change event. 
		 *
		 * @param {string} pedal sustain|sostenuto|soft
		 * @param {string} state on|off
		 * @return undefined
		 */
		onPedalChange: function(pedal, state, request_origin) {
			if (request_origin === 'refresh') {
				this.sendMIDIPedalMessage(pedal, state);
				SUSTAINING = false;
				return;
			}

			var chord = this.chords.current();
			switch(pedal) {
				case 'soft':
					this.noteVelocity = (state === 'off' ? DEFAULT_NOTE_VELOCITY : SOFT_NOTE_VELOCITY);
					break;
				case 'sustain':
					if (state === 'on') {
						chord.sustainNotes();
						if (request_origin !== 'ui') {
							this.chords.bank();
						}
						this.sendMIDIPedalMessage(pedal, state);
						SUSTAINING = true;
					} else if (state === 'off') {
						chord.releaseSustain();
						/* prepare to turn off notes in previous bank too */
						var prev_notes
							= this.chords.previous()._notes
							|| false;
						var prev_sustained
							= this.chords.previous()._sustained
							|| false;
						/* critical side-effect */
						var notes_off = chord.syncSustainedNotes(prev_notes, prev_sustained);
						this.turnOffSustainedNotesOnPedalLift(notes_off);

						this.sendMIDIPedalMessage(pedal, state);
						SUSTAINING = false;
					}
					break;
				default:
					break;
			}
		},
		/**
		 * Handles an instrument change event.
		 *
		 * @param {number} instrumentNum
		 * @return undefined
		 */
		onInstrumentChange: function(instrumentNum) {
			var command = MIDI_MSG_MAP.PROGRAM_CHANGE;
			instrumentNum = instrumentNum < 0 ? DEFAULT_INSTRUMENT : instrumentNum;

			this.sendMIDIMessage(command, instrumentNum, 0, this.midiChannel);
		},
		/**
		 * Handles a transpose event.
		 *
		 * @param {number} transpose
		 * @return undefined
		 */
		onTransposeChange: function(transpose) {
			var chord = this.chords.current();
			chord.setTranspose(transpose);
		},
		/**
		 * Sends MIDI messages to turn off all notes. This should stop all notes
		 * from sounding.
		 *
		 * @return undefined
		 */
		sendAllNotesOff: function() {
			var channel_idx = this.midiChannel - 1;
			var notes = this.chords.getAllNotes();
			var noteVelocity = this.noteVelocity;
			for(var i = 0, len = notes.length; i < len; i++) {
				this.sendMIDIMessage(MIDI_MSG_MAP.NOTE_OFF[channel_idx], notes[i], noteVelocity);
			}
		},
		/**
		 * Send a MIDI message to the current MIDI output.
		 *
		 * @return undefined
		 */
		sendMIDIMessage: function() {
			var msg = null, midiAccess = this.midiAccess, midiDevice = this.midiDevice;
			if(midiAccess) {
				midiDevice.sendMIDIMessage(Object.values(arguments));
			}
		},
		/**
		 * Output a MIDI message to turn a pedal on/off.
		 *
		 * @param {string} pedal sustain|sostenuto|soft
		 * @param {string} state on|off
		 * @return undefined
		 */
		sendMIDIPedalMessage: function(pedal, state) {
			var command = MIDI_MSG_MAP.CONTROL_CHANGE;
			var controlNumber = MIDI_CONTROL_MAP.pedal[pedal];
			var controlValue = (state === 'off' ? 0 : 127);
			// this.sendMIDIMessage(command, 64, 127, 1);
			this.sendMIDIMessage(command, controlNumber, controlValue, this.midiChannel);
		}
	});

	return MidiComponent;
});
