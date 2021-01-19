/* global define: false */
define([
    'jquery',
    'jquery-ui',
    'lodash', 
    'vexflow',
    'app/config',
    'app/components/component',
    'app/utils/fontparser',
    './stave',
    './stave_notater',
    './exercise_note_factory'
], function(
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
    var CHORD_BANK_SIZE = Config.get('general.chordBank.displaySize');

    var DEFAULT_RHYTHM_VALUE = Config.get('general.defaultRhythmValue');

    var AUTO_ADVANCE_ENABLED = Config.get('general.autoExerciseAdvance');

    var SETTING_HIDE_NEXT = Config.get('general.hideNextWhenAutoAdvance');

    var NUMBERED_EXERCISE_COUNT = Config.get('general.numberedExerciseCount');

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
    var ExerciseSheetComponent = function(settings) {
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

        _.bindAll(this, [
            'render',
            'onChordsUpdate'
        ]);
    };

    ExerciseSheetComponent.prototype = new Component();

    _.extend(ExerciseSheetComponent.prototype, {
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
            this.renderExerciseInfo();
            this.renderExerciseText();
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
            //this.getInputChords().bind('change', this.render);
            this.getInputChords().bind('change', this.onChordsUpdate);
            this.getInputChords().bind('clear', this.onChordsUpdate);
            this.exerciseContext.bind('goto', this.onGoToExercise);
        },
        /**
         * Renders the grand staff and everything on it.
         *
         * @return this
         */
        render: function(exercise_midi_nums = false) {
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
        renderExerciseStatus: function() {
            var exc = this.exerciseContext;
            var definition = exc.getDefinition();
            var $statusEl = $("#exercise-status-and-tempo");
            var tpl = _.template(
                // not called: time_to_complete and more; seriesTimer obsolete
                `<p><span class="exercise-status" style="background-color:<%= status_color %>"><%= status_text %></span></p>
                <% if (typeof(tempo_mean) !== "undefined" && tempo_mean != "" && typeof(tempo_rating) !== "undefined") { %>
                    <p><a onclick="window.alert('PERFORMANCE DATA: This shows your average (mean) tempo in whole notes per minute, plus a star rating for the consistency of your tempo.')">Tempo&nbsp;<%= Math.round(tempo_mean) %> <%= tempo_rating %></a></p>
                <% } %>`
            );
            var html = '';
            var tpl_data = {};

            var status_map = {};
            status_map[exc.STATE.INCORRECT] = {
                text: "incorrect",
                color:"#990000"
            };
            status_map[exc.STATE.CORRECT] = {
                text: "complete",
                color:"#4C9900"
            };
            status_map[exc.STATE.FINISHED] = {
                text: "finished with errors",
                color:"#999900"
            };
            status_map[exc.STATE.WAITING] = {
                text: "in progress",
                color:"#999900"
            };
            status_map[exc.STATE.READY] = {
                text: "ready",
                color:"#000000"
            };

            tpl_data.exercise_list = exc.definition.getExerciseList();
            tpl_data.exercise_num = tpl_data.exercise_list.reduce(function(selected, current, index) { return (selected < 0 && current.selected) ? index + 1 : selected; }, -1);
            tpl_data.status_text = status_map[exc.state].text;
            tpl_data.status_color = status_map[exc.state].color;

            switch(exc.state) {
                case exc.STATE.CORRECT:
                    if (exc.hasTimer()) {
                        tpl_data.time_to_complete = exc.getExerciseDuration();
                        tpl_data.min_tempo = exc.getMinTempo();
                        tpl_data.max_tempo = exc.getMaxTempo();
                        tpl_data.tempo_mean = exc.getTempoMean();
                        tpl_data.tempo_rating = exc.getTempoRating();
                    }
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
            
            html = tpl(tpl_data);
            $statusEl.html(html);

            return this;
        },
        renderExerciseInfo: function() {
            var exc = this.exerciseContext;
            var definition = exc.getDefinition();
            var $infoEl = $("#exercise-info");
            var tpl = _.template(
                `<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>
                    <p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>
                <% } %>`
            );
            var html = '';
            var tpl_data = {};

            tpl_data.exercise_list = exc.definition.getExerciseList();
            tpl_data.exercise_num = tpl_data.exercise_list.reduce(function(selected, current, index) { return (selected < 0 && current.selected) ? index + 1 : selected; }, -1);

            html = tpl(tpl_data);
            $infoEl.html(html);

            return this;
        },
        renderExerciseText: function() {
            var exc = this.exerciseContext;
            var definition = exc.getDefinition();
            var $textEl = $("#exercise-text");
            var tpl = _.template(
                `<% if (typeof(prompt_text) == "string") { %>
                    <%= prompt_text %>
                <% } %>`
            );
            var html = '';
            var tpl_data = {};

            // Parse the text for tokens that should use the figured bass font
            tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(exc.definition.getIntro());

            html = tpl(tpl_data);
            $textEl.html(html);

            return this;
        },
        renderExerciseHistory: function() {
            var exc = this.exerciseContext;
            var definition = exc.getDefinition();
            var $historyEl = $("#exercise-history");
            var tpl = _.template(
                `<% if (false && is_performed && typeof(latest_err_count) == "integer" && latest_err_count == 0) { %>
                    <p>PASSED on most recent attempt</p>
                <% } %>`
            );
            var html = '';
            var tpl_data = {};

            // Not the correct data
            tpl_data.is_performed = exc.settings.definition.settings.definition.exerciseIsPerformed;
            tpl_data.latest_err_count = exc.settings.definition.settings.definition.exerciseErrorCount;
            // console.log('This should be the history for this exercise', tpl_data.is_performed, tpl_data.latest_err_count);

            html = tpl(tpl_data);
            $historyEl.html(html);

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
        renderStaves: function(exercise_midi_nums = false) {
            var i, len, stave, _staves = this.staves;
            for (i = 0, len = _staves.length; i < len; i++) {
                stave = _staves[i];
                stave.render(exercise_midi_nums);
            }
            return this;
        },
        /**
         * Resets the staves.
         *
         * @return this
         */
        resetStaves: function() {
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
            var chord, treble, bass;
            var limit = 100; // arbitrary
            var display_items = this.getDisplayChords().items({limit: limit, reverse: false});
            var exercise_items = this.getExerciseChords().items({limit: limit, reverse: false});
            var staves = [];
            var index = 0;
            var offset = 0;
            var count = display_items.length;
            var position = {
                index:index,
                count:count,
                offset:offset,
                maxCount:CHORD_BANK_SIZE
            };
            var display_chord;
            var exercise_chord;

            // scrolling exercise view
            var scroll_exercise = false;
            let rhythmValues = display_items.map( item => item.chord._rhythmValue );
            var availableSpace = CHORD_BANK_SIZE;
            var pageturns = [0];
            for (var i = 0, len = rhythmValues.length; i < len; i++) {
                let neededSpace = this.getVisualWidth(rhythmValues[i]);
                if (neededSpace + 1 > availableSpace) {
                    availableSpace = CHORD_BANK_SIZE;
                    pageturns.push(i);
                    scroll_exercise = true;
                }
                availableSpace -= this.getVisualWidth(rhythmValues[i]);
            }
            if (scroll_exercise) {
                let cursor = this.getInputChords()._currentIndex;
                var page_start = pageturns.filter(function(x,idx){return x <= cursor}).pop();
                var next_page = pageturns.filter(function(x,idx){return x > cursor})[0] || false;
                if (page_start > 0) page_start -= 1;
                display_items = display_items.slice(page_start);
                exercise_items = exercise_items.slice(page_start);
                position.offset = page_start;
            }

            // the first stave bar is a special case: it's reserved to show the
            // clef and key signature and nothing else
            treble = this.createDisplayStave('treble', _.clone(position));
            bass = this.createDisplayStave('bass', _.clone(position));
            position.index += 1;
            treble.connect(bass);
            staves.push(treble);

            // now add the staves for showing the notes
            for(var i = 0, len = display_items.length; i < len; i++) {
                var elapsedWidthUnits = 0;
                for(var j = 0; j < i; j++) {
                    var rhythm_value = null;
                    if(display_items[j].chord.settings.rhythm) {
                        rhythm_value = display_items[j].chord.settings.rhythm;
                    }
                    if(rhythm_value == null) {
                        rhythm_value = DEFAULT_RHYTHM_VALUE;
                    }
                    elapsedWidthUnits += this.getVisualWidth(rhythm_value);
                }

                display_chord = display_items[i].chord;
                exercise_chord = exercise_items[i].chord;
                treble = this.createNoteStave('treble', _.clone(position), display_chord, exercise_chord, elapsedWidthUnits);
                bass = this.createNoteStave('bass', _.clone(position), display_chord, exercise_chord, elapsedWidthUnits);
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

            if (typeof this.keySignature.signatureSpec === 'string') {
                const staffSig = this.keySignature.signatureSpec;
                stave.setFirstBarWidth(staffSig);
            }
            stave.updatePosition();

            return stave;
        },
        getVisualWidth: function(rhythm_value) {
            if (rhythm_value === "w") {
                return 1;
            } else if (rhythm_value === "H") {
                return 0.75;
            } else if (rhythm_value === "h") {
                return 0.675;
            } else if (rhythm_value === "q") {
                return 0.375;
            } else {
                console.log('Unknown rhythm_value passed to getVisualWidth');
                return 1;
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
        createNoteStave: function(clef, position, displayChord, exerciseChord, elapsedWidthUnits) {
            var stave = new Stave(clef, position);
            var widthUnits = null;
            if (exerciseChord.settings.rhythm) {
                var rhythm_value = exerciseChord.settings.rhythm;
                if (rhythm_value == null) {
                    rhythm_value = DEFAULT_RHYTHM_VALUE;
                }
                widthUnits = this.getVisualWidth(rhythm_value);
            }

            stave.setRenderer(this.vexRenderer);
            stave.setKeySignature(this.keySignature);
            // stave.setFirstBarWidth(this.keySignature);
            stave.setNoteFactory(new ExerciseNoteFactory({
                clef: clef,
                chord: displayChord,
                keySignature: this.keySignature,
                highlightConfig: this.getHighlightConfig()
            }));
            stave.setNotater(this.createStaveNotater(clef, {
                stave: stave,
                chord: exerciseChord,
                keySignature: this.keySignature,
                analyzeConfig: this.getAnalyzeConfig()
            }));
            stave.setMaxWidth(this.getWidth());

            if (typeof this.keySignature.signatureSpec === 'string') {
                const staffSig = this.keySignature.signatureSpec;
                stave.setFirstBarWidth(staffSig);
            }
            stave.updatePositionWithRhythm(widthUnits, elapsedWidthUnits);

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
            return this.el.width()
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
         * Returns the chords for display.
         *
         * @return undefined
         */
        getDisplayChords: function() {
            return this.exerciseContext.getDisplayChords();
        },
        /**
         * Returns the chords for exercise analysis.
         *
         * @return undefined
         */
        getExerciseChords: function() {
            return this.exerciseContext.getExerciseChords();
        },
        /**
         * Returns the input chords.
         *
         * @return undefined
         */
        getInputChords: function() {
            return this.exerciseContext.getInputChords();
        },
        /**
         * Handles a chord bank update.
         *
         * @return undefined
         */
        onChordsUpdate: function() {
            this.updateStaves();
            this.render();
        },
        /**
         * Handles navigating to the next exercise.
         *
         * @return undefined
         */
        onGoToExercise: function(target) {
            window.location = target.url;
        }
    });

    return ExerciseSheetComponent;
});
