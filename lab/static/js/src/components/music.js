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

    var getUrlVars = function() {
        var vars = {};
        var parts = window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function(m,key,value) {
            vars[key] = value;
        });
        return vars;
    };
    // console.log('URL variables', getUrlVars());

    var STAFF_DISTRIBUTION = Config.get('general.staffDistribution');
    var VOICE_COUNT_FOR_KEYBOARD_STYLE = Config.get('general.voiceCountForKeyboardStyle');

    let url_staff_dist = getUrlVars().hasOwnProperty('staffDistribution');
    let storage_staff_dist = sessionStorage.getItem('staffDistribution');
    let valid_staff_dists = ["keyboard", "chorale", "LH", "RH", "keyboardPlusRHBias", "keyboardPlusLHBias", "grandStaff"];
    if (storage_staff_dist && valid_staff_dists.includes(url_staff_dist)) {
        STAFF_DISTRIBUTION = storage_staff_dist;
    } else if (url_staff_dist && valid_staff_dists.includes(url_staff_dist)) {
        STAFF_DISTRIBUTION = url_staff_dist;
    }

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
        this.staffDistributionConfig = _.extend({}, STAFF_DISTRIBUTION, this.settings.sheet.chords.settings);


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
            'onRedrawRequest',
            'onNextExerciseRequest',
            'onPreviousExerciseRequest',
            'onFirstExerciseRequest'
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
            this.subscribe(EVENTS.BROADCAST.HIGHLIGHT_NOTES, this.onStaffDistributionChange); // not working?
            this.subscribe(EVENTS.BROADCAST.METRONOME, this.onMetronomeChange);
            this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onRedrawRequest);
            this.subscribe(EVENTS.BROADCAST.NEXTEXERCISE, this.onNextExerciseRequest);
            this.subscribe(EVENTS.BROADCAST.PREVIOUSEXERCISE, this.onPreviousExerciseRequest);
            this.subscribe(EVENTS.BROADCAST.FIRSTEXERCISE, this.onFirstExerciseRequest);
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
            if (sheetComponent.hasOwnProperty('exerciseContext')) {
                var exercise_midi_nums = sheetComponent.exerciseContext.exerciseChords._items.map(item => Object.keys(item._notes));
                sheetComponent.render(exercise_midi_nums);
            } else {
                sheetComponent.render();
            }
            return this;
        },
        renderPristine: function(exerciseAction = 'refresh') {
            var sheetComponent = this.getComponent('sheet');

            if (!sheetComponent.hasOwnProperty('exerciseContext')) {

                /* play view */
                sheetComponent.chords.clear();

            } else {

                /* exercise view */
                let scex = sheetComponent.exerciseContext;

                let setdef = scex.settings.definition;

                // The following was used to generate newData as we built this function
                // let currentData = JSON.stringify(setdef.settings.definition, null, 0);
                let newData = {};

                // var testing = (window.location.href.split(".")[0].slice(-5) == "-beta" ? true : false);

                if (exerciseAction === 'reload') {

                    $.ajax({
                        type: "GET",
                        url: 'definition',
                        async: false,
                        data: {
                            'playlist_name': setdef.settings.definition.playlistName,
                            'exercise_id': setdef.settings.definition.exerciseId,
                            'exercise_num': setdef.settings.definition.exerciseNum
                        },
                        dataType: 'json',
                        success: function (data) {
                            newData = data;
                        }
                    });

                    if (!Object.keys(newData).length) {
                        console.log('Error reloading exercise data!');
                        return null;
                    }

                } else if (exerciseAction === 'next') {

                    $.ajax({
                        type: "GET",
                        url: 'definition',
                        async: false,
                        data: {
                            'playlist_name': setdef.settings.definition.playlistName,
                            'exercise_id': setdef.settings.definition.nextExerciseId,
                            'exercise_num': setdef.settings.definition.nextExerciseNum
                        },
                        dataType: 'json',
                        success: function (data) {
                            if (setdef.settings.definition.nextExerciseId) {
                                newData = data;
                            }
                        }
                    });

                    if (!Object.keys(newData).length) {
                        console.log('No next exercise; end of playlist');
                        return null;
                    }

                } else if (exerciseAction === 'previous') {

                    $.ajax({
                        type: "GET",
                        url: 'definition',
                        async: false,
                        data: {
                            'playlist_name': setdef.settings.definition.playlistName,
                            'exercise_id': setdef.settings.definition.previousExerciseId,
                            'exercise_num': setdef.settings.definition.previousExerciseNum
                        },
                        dataType: 'json',
                        success: function (data) {
                            if (setdef.settings.definition.previousExerciseId) {
                                newData = data;
                            }
                        }
                    });

                    if (!Object.keys(newData).length) {
                        console.log('No previous exercise; start of playlist');
                        return null;
                    }

                } else if (exerciseAction === 'first') {

                    $.ajax({
                        type: "GET",
                        url: 'definition',
                        async: false,
                        data: {
                            'playlist_name': setdef.settings.definition.playlistName,
                            'exercise_id': setdef.settings.definition.firstExerciseId,
                            'exercise_num': 1
                        },
                        dataType: 'json',
                        success: function (data) {
                            newData = data;
                        }
                    });

                    if (!Object.keys(newData).length) {
                        console.log('Error finding first exercise!');
                        return null;
                    }

                }

                // rough fix for stuck notes on exercise advance
                this.broadcast(EVENTS.BROADCAST.CLEAR_NOTES);

                scex.inputChords.clear();
                scex.inputChords.goTo(0);

                if (Object.keys(newData).length) {

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
                    /* could add use of listeners here to update the menu */

                    scex.inputChords.staffDistribution = newData.staffDistribution;
                    scex.displayChords = scex.createDisplayChords();
                    scex.exerciseChords = scex.createExerciseChords();

                    this.trigger('change');
                }

                // sheetComponent.renderExerciseText(); // not necessary
                scex.sealed = false;
                scex.done = false;
                scex.timer = null;
                scex.timepoints = [];

                window.console.dir('send dummy note');
                this.broadcast(EVENTS.BROADCAST.NOTE, 'on', 109, 0);
                this.broadcast(EVENTS.BROADCAST.NOTE, 'off', 109, 0);
                this.broadcast(EVENTS.BROADCAST.PEDAL, 'sustain', 'off', 'refresh');

                scex.state = "ready"; // READY
            }

            sheetComponent.clear();
            sheetComponent.render();

            return this;
        },
        renderNextExercise: function() {
            this.renderPristine('next');
        },
        renderPreviousExercise: function() {
            this.renderPristine('previous');
        },
        renderFirstExercise: function() {
            this.renderPristine('first');
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
        onStaffDistributionChange: function(value) {
            this['staffDistributionConfig'].staffDistribution = value;
            this.settings.sheet.chords._items[0].settings.staffDistribution = value;
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
        onNextExerciseRequest: function() {
            this.renderNextExercise();
        },
        onPreviousExerciseRequest: function() {
            this.renderPreviousExercise();
        },
        onFirstExerciseRequest: function() {
            this.renderFirstExercise();
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
