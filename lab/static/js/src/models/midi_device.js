define([
    'lodash',
    'microevent',
    'Tone' /* Tone.js */
], function (
    _,
    MicroEvent,
    Tone
) {

    /**
     * MidiDevice object is responsible for knowing the MIDI input/output
     * devices that are available for sending/receiving messages.
     *
     * @mixes MicroEvent
     * @fires updated when the list of devices is updated or changed
     * @fires cleared when the list of devices is cleared
     * @constructor
     */
    var MidiDevice = function () {
        this.inputs = [];
        this.outputs = [];
        this._input = false;
        this._inputidx = false;
        this._output = false;
        this._outputidx = false;
        _.bindAll(this, ['handleMIDIMessage', 'update']);
    };

    /**
     * Initialize parameters for Tone.js
     */
    document.documentElement.addEventListener(
        "mousedown", function () {
            mouse_IsDown = true;
            if (Tone.context.state !== 'running') {
                document.getElementById('audio-context').innerHTML
                    = "Audio Enabled"
                Tone.context.resume();
                polySynth.releaseAll();
            }
        });

    /* Create Polyphonic Synthesizer */
    var polySynth = new Tone.PolySynth(10, Tone.FMSynth);
    var vol = new Tone.Volume(-6).toMaster();
    polySynth.connect(vol);

    /* defaults per _header.html */
    polySynth.volume.value = -12;
    vol.mute = false;


    /* All Notes Off button */
    // if ($("all-notes-off")){
    // 	$("all-notes-off").click( function () {
    // 		polySynth.releaseAll();
    // 	});
    // }


    /* Mute button */
    if ($("#Mute").length > 0) {
        $("#Mute").click(function () {
            let mute = document.getElementById("Mute");
            if (mute.innerHTML == "Mute") {

                /* all notes off */
                polySynth.releaseAll();

                $.ajax({
                    type: "POST",
                    url: "/ajax/set-mute/",
                    dataType: 'json',
                    data: {'mute': true},
                    success: function (data) {
                    },
                    error: function (error) {
                    }
                });
                vol.mute = true;
                mute.innerHTML = "Unmute";
            } else if (mute.innerHTML == "Unmute") {
                $.ajax({
                    type: "POST",
                    url: "/ajax/set-mute/",
                    dataType: 'json',
                    data: {'mute': false},
                    success: function (data) {
                    },
                    error: function (error) {
                    }
                });
                vol.mute = false;
                mute.innerHTML = "Mute";
            }
        });
    }

    const volumeOpts = {
        "ff": 0,
        "f": -5,
        "mf": -12,
        "mp": -22,
        "p": -35,
        "pp": -50
    };
    const volumeOptsKeys = Object.keys(volumeOpts);

    /* Volume control */
    if ($("#volume").length > 0) {
        $("#volume").click(function () {
            let volumeDiv = document.getElementById("volume");
            volumeDiv.innerHTML = volumeOptsKeys[(1 + volumeOptsKeys.indexOf(volumeDiv.innerHTML)) % volumeOptsKeys.length];


            $.ajax({
                type: "POST",
                url: "/ajax/set-volume/",
                dataType: 'json',
                data: {'volume': volumeDiv.innerHTML},
                success: function (data) {
                    alert(data);
                },
                error: function (error) {
                }
            });

            polySynth.volume.value = volumeOpts[volumeDiv.innerHTML];
        });
    }


    /**
     * Sets a callback that will be called when the update() method
     * is called.
     *
     * @param {Function} callback
     * @return undefined
     */
    MidiDevice.prototype.setUpdater = function (callback) {
        this._updater = callback;
    };

    /**
     * Calls the updater callback that will update the device.
     *
     * @fires updated
     * @return undefined
     */
    MidiDevice.prototype.update = function () {
        if (this._updater) {
            this._updater();
            this.trigger("updated", this);
        }
    };

    /**
     * Sets the sources for input/output.
     *
     * @param {array} inputs
     * @param {array} outputs
     * @return undefined
     */
    MidiDevice.prototype.setSources = function (inputs, outputs) {
        this.inputs = inputs || [];
        this.outputs = outputs || [];
    };

    /**
     * Returns the inputs.
     *
     * @return array
     */
    MidiDevice.prototype.getInputs = function () {
        return this.inputs;
    };

    /**
     * Returns the outputs.
     *
     * @return array
     */
    MidiDevice.prototype.getOutputs = function () {
        return this.outputs;
    };

    /**
     * Selects an input device to be used.
     *
     * @param {number} index
     * @return array
     */
    MidiDevice.prototype.selectInput = function (index, inputs) {
        var some_valid_selection = false;
        for (i = 0, len = inputs.length; i < len; i++) {
            if (this.isValidSelection(this.inputs, i)) {
                this._inputidx = i;
                this._input = this.inputs[i];
                // this.clearInputListeners();
                /* previously selected index as input device and cleared other listeners, now selects all inputs */
                this.addInputListener();
                some_valid_selection = true;
            }
        }
        return some_valid_selection;
    };

    /**
     * Selects an output device to be used.
     *
     * @param {number} index
     * @return array
     */
    MidiDevice.prototype.selectOutput = function (index) {
        if (this.isValidSelection(this.outputs, index)) {
            this._outputidx = index;
            this._output = this.outputs[index];
            return true;
        }
        return false;
    };

    /**
     * Selects the default input/output devices.
     *
     * @return undefined
     *
     */
    MidiDevice.prototype.selectDefaults = function (input) {
        this.selectInput(0, input); /* previously selectInput(0), now sending all inputs*/
        this.selectOutput(0, input);
    };

    /**
     * Checks if the index is a valid selection from the list of sources.
     *
     * @param {number} index
     * @return {boolean}
     */
    MidiDevice.prototype.isValidSelection = function (sources, index) {
        var size = sources.length;
        return index >= 0 && (index <= size - 1) && size > 0;
    };

    /**
     * Returns the currently select input device.
     *
     * @return {object} or false if there is none
     */
    MidiDevice.prototype.getSelectedInput = function () {
        if (this._input) {
            return this.inputs[this._inputidx];
        }
        return false;
    };

    /**
     * Returns the currently select output device.
     *
     * @return {object} or false if there is none
     */
    MidiDevice.prototype.getSelectedOutput = function () {
        if (this._output) {
            return this.outputs[this._outputidx];
        }
        return false;
    };

    /**
     * Clears input listeners for midi messages over all inputs.
     *
     * @return undefined
     */
    MidiDevice.prototype.clearInputListeners = function () {
        _.each(this.inputs, function (input) {
            input.onmidimessage = null;
        });
    };

    /**
     * Adds the input listener for midi messages.
     *
     * @return undefined
     */
    MidiDevice.prototype.addInputListener = function () {
        if (this._input) {
            this._input.onmidimessage = this.handleMIDIMessage;
        }
    };

    /**
     * Receives the MIDI message from the input device and triggers it
     * so that interested subscribers can act on it.
     *
     * @return undefined
     */
    MidiDevice.prototype.handleMIDIMessage = function (msg) {
        this.trigger("midimessage", msg);
    };

    /**
     * Sends a MIDI message to the output device.
     *
     * @return undefined
     */
    MidiDevice.prototype.sendMIDIMessage = function (msg) {
        if (msg[1] == 109) {
            // midi note 109 is ignored (used for side-effect on frontend)
        } else if (false) { /* midi output */
            if (this._output) {
                this._output.send(msg);
            }
        } else { /* synth output */
            /* convert MIDI number to pitch name */
            const pitchNames = ['c', 'c#', 'd', 'eb', 'e', 'f', 'f#', 'g', 'g#', 'a', 'bb', 'b']
            let noteName = pitchNames[(msg[1] + 12) % 12]
                + (Math.floor(msg[1] / 12) - 1).toString()

            if (msg[0] == 144) { /* note on, channel 1 */
                polySynth.triggerAttack(noteName);
            } else if (msg[0] == 128) { /* note off, channel 1 */
                polySynth.triggerRelease(noteName);
            }
        }
    };

    /**
     * Clears the devices.
     *
     * @fires clear
     * @return undefined
     */
    MidiDevice.prototype.clear = function () {
        this._inputidx = 0;
        this._outputidx = 0;
        this.inputs = [];
        this.outputs = [];
        this.trigger("clear");
    };

    MicroEvent.mixin(MidiDevice);

    return MidiDevice;
});
