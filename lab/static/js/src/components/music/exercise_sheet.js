/* global define: false */
define([
    'jquery',
    'jquery-ui',
    'lodash', 
    'vexflow',
    'app/config',
	'app/components/events',
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
	EVENTS,
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

        if("exerciseContext" in this.settings) {
            this.exerciseContext = this.settings.exerciseContext;
        } else {
            throw new Error("missing settings.exerciseContext");
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
            this.exerciseContext.bind('goto', (e) => this.onGoToExercise(e));
        },
        /**
         * Renders the grand staff and everything on it.
         *
         * @return this
         */
        render: function() {
            this.clear();
            this.renderStaves();
            this.renderExerciseText();

            return this;
        },
        /**
         * Renders intro or review text for the exercise.
         *
         * @return this
         */
        renderExerciseText: function() {
            var exc = this.exerciseContext;
            var definition = exc.getDefinition();
            var $statusEl = $("#staff-status");
            var tpl = _.template([
                '<div class="exercise-status-area">',
                    '<div class="exercise-status-col exercise-status-col1">',
                        '<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>',
                            '<p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>',
                        '<% } %>',
                        '<% if (1 == 2 && typeof(time_to_complete_series) !== "undefined" && time_to_complete_series != "" && typeof(last_exercise_id) !== "undefined") { %>',
                            '<p><%= last_exercise_id %></p>',
                        '<% } %>',
                        '<p><span class="exercise-status-state" style="background-color:<%= status_color %>"><%= status_text %> <%= status_icon %></span>',
                        '<% if (typeof(time_to_complete) !== "undefined" && time_to_complete != "" && status_text !== "finished with errors") { %>',
                            '&nbsp;in&nbsp;<%= time_to_complete %></p>',
                        '<% } %>',
                        '<% if (typeof(min_tempo) !== "undefined" && min_tempo != "" && typeof(max_tempo) !== "undefined" && max_tempo != "" && typeof(tempo_rating) !== "undefined") { %>',
                            '<p>Tempo&nbsp;<%= min_tempo %>&ndash;<%= max_tempo %> <%= tempo_rating %></p>',
                        '<% } %>',
                        '<% if (typeof(time_to_complete_series) !== "undefined" && time_to_complete_series != "") { %>',
                            '<p>All&nbsp;done&nbsp;in&nbsp;<%= time_to_complete_series %></p>',
                        '<% } %>',
                        '<% if (typeof(ex_restarts) !== "undefined" && ex_restarts > 0) { %>',
                            '<p>Made&nbsp;<%= ex_restarts %>&nbsp;restart(s)</p>',
                        '<% } %>',
                        '<% if (typeof(time_to_complete_series) !== "undefined" && time_to_complete_series != "" && typeof(group_min_tempo) !== "undefined" && group_min_tempo != "" && typeof(group_max_tempo) !== "undefined" && group_max_tempo != "" && typeof(group_tempo_rating) !== "undefined") { %>',
                            '<p>Overall tempo&nbsp;<%= group_min_tempo %>&ndash;<%= group_max_tempo %> <%= group_tempo_rating %></p>',
                        '<% } %>',
                        '<% if (typeof(next_exercise) !== "undefined" && next_exercise != "" && hide_next === false) { %>',
                            '<p><a class="exercise-status-next-btn" href="<%= next_exercise %>">Click for next</a></p>',
                        '<% } %>',
                    '</div>',
                    '<div class="exercise-status-col exercise-status-col2">',
                        '<% if (prompt_text !== "") { %>',
                            '<p><%= prompt_text %></p>',
                        '<% } %>',
                        '<% if (typeof(next_set_skip) !== "undefined" && next_set_skip != "") { %>',
                            '<a class="exercise-status-next-btn" href="<%= next_set_skip %>">SKIP TO NEXT SET</a>',
                        '<% } %>',
                        '<% if (typeof(next_set) !== "undefined" && next_set != "") { %>',
                            '<a class="exercise-status-next-btn" href="<%= next_set %>">PROCEED TO NEXT SET</a> || ',
                        '<% } %>',
                        '<% if (typeof(current_set) !== "undefined" && current_set != "" && exercise_num != 1) { %>',
                            '<a class="exercise-status-next-btn" href="<%= current_set %>">REDO CURRENT PLAYLIST</a>',
                        '<% } %>',
                    '</div>',
                '</div>'
            ].join(''));
            var html = '';
            var status_map = {};
            var tpl_data = {};
            var parsed_prompt_html;

            status_map[exc.STATE.INCORRECT] = {text:"incorrect",color:"#990000",iconCls:"ion-close"};
            status_map[exc.STATE.CORRECT] = {text:"complete",color:"#4C9900",iconCls:"ion-checkmark"};
            status_map[exc.STATE.FINISHED] = {text:"finished with errors",color:"#999900",iconCls:""};
            status_map[exc.STATE.WAITING] = {text:"in progress",color:"#999900",iconCls:""};
            status_map[exc.STATE.READY] = {text:"ready",color:"#000000",iconCls:""};

            tpl_data.exercise_list = exc.definition.getExerciseList();
            tpl_data.exercise_num = tpl_data.exercise_list.reduce(function(selected, current, index) {
               return (selected < 0 && current.selected) ? index + 1 : selected;
            }, -1);
            tpl_data.status_text = status_map[exc.state].text;
            tpl_data.status_color = status_map[exc.state].color;
            tpl_data.status_icon = status_map[exc.state].iconCls;
            if(tpl_data.status_icon) {
                tpl_data.status_icon = '<i class="'+tpl_data.status_icon+'"></i>';
            }
            if(exc.definition.getNextExercise()) {
                tpl_data.next_exercise = exc.definition.getNextExercise();
            }
            tpl_data.hide_next = false;
            if(AUTO_ADVANCE_ENABLED && SETTING_HIDE_NEXT) {
                tpl_data.hide_next = true;
            }

            tpl_data.prompt_text = "";
            switch(exc.state) {
                case exc.STATE.CORRECT:
                    if(exc.definition.hasReview()) {
                        tpl_data.prompt_text = exc.definition.getReview();
                    }else if(exc.definition.hasIntro()) {
                        tpl_data.prompt_text = exc.definition.getIntro();
                    }
                    if(exc.hasTimer()) {
                        tpl_data.time_to_complete = exc.getExerciseDuration();
                        tpl_data.min_tempo = exc.getMinTempo();
                        tpl_data.max_tempo = exc.getMaxTempo();
                        tpl_data.tempo_rating = exc.getTempoRating();
                    }
                    if(exc.hasSeriesTimer()) {
                        tpl_data.time_to_complete_series = exc.getExerciseSeriesDuration();
                        tpl_data.ex_restarts = exc.getExerciseGroupRestarts();
                        tpl_data.group_min_tempo = exc.getGroupMinTempo();
                        tpl_data.group_max_tempo = exc.getGroupMaxTempo();
                        tpl_data.group_tempo_rating = exc.getGroupTempoRating();
                        tpl_data.last_exercise_id = exc.definition.getExerciseList()[exc.definition.getExerciseList().length - 1].id;
                    }
                    if(tpl_data.last_exercise_id.split("/")[0] && tpl_data.exercise_num == tpl_data.exercise_list.length) {
                        tpl_data.current_set = "../" + tpl_data.last_exercise_id.split("/")[0];
                    }
                    if(tpl_data.time_to_complete_series && tpl_data.time_to_complete_series != "") {
                        if(tpl_data.last_exercise_id.split("/")[0].split("_")[1]) {
                            var group_id = tpl_data.last_exercise_id.split("/")[0];
                            var group_number = tpl_data.last_exercise_id.split("/")[0].split("_")[0];
                            var key_schema_number = tpl_data.last_exercise_id.split("/")[0].split("_")[1];
                            if(parseInt(group_number) != NaN && parseInt(group_number) < NUMBERED_EXERCISE_COUNT) {
                                /* Crude solution */
                                tpl_data.next_set = "../" + (parseInt(group_number) + 1) + "_" + key_schema_number + "/01";
                            }
                        }
                    }
                    break;
                case exc.STATE.FINISHED:
                    if(exc.hasTimer()) {
                        tpl_data.time_to_complete = exc.getExerciseDuration();
                        tpl_data.min_tempo = exc.getMinTempo();
                        tpl_data.max_tempo = exc.getMaxTempo();
                        tpl_data.tempo_rating = exc.getTempoRating();
                    }
                    if(exc.hasSeriesTimer()) {
                        tpl_data.group_min_tempo = exc.getGroupMinTempo();
                        tpl_data.group_max_tempo = exc.getGroupMaxTempo();
                    }
                    break;
                case exc.STATE.READY:
                default:
                    if(exc.definition.hasIntro()) {
                        tpl_data.prompt_text = exc.definition.getIntro();
                    }

                    tpl_data.last_exercise_id = exc.definition.getExerciseList()[exc.definition.getExerciseList().length - 1].id;

                    if(tpl_data.exercise_num == 1) {
                        if(tpl_data.last_exercise_id.split("/")[0].split("_")[1]) {
                            var group_id = tpl_data.last_exercise_id.split("/")[0];
                            var group_number = tpl_data.last_exercise_id.split("/")[0].split("_")[0];
                            var key_schema_number = tpl_data.last_exercise_id.split("/")[0].split("_")[1];
                            if(parseInt(group_number) != NaN && parseInt(group_number) < NUMBERED_EXERCISE_COUNT) {
                                /* Crude solution */
                                tpl_data.next_set_skip = "../" + (parseInt(group_number) + 1) + "_" + key_schema_number + "/01";
                            }
                        }
                    }
                    break;
            }
            
            // parse the prompt text in case there are any tokens that should use the figured bass font
            tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(tpl_data.prompt_text);
    
            html = tpl(tpl_data);
            $statusEl.html(html);

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
            var limit = CHORD_BANK_SIZE * 4;// Adjusted now that rhythms varied
            var display_items = this.getDisplayChords().items({limit: limit, reverse: false});
            var exercise_items = this.getExerciseChords().items({limit: limit, reverse: false});
            var staves = [];
            var index = 0;
            var count = display_items.length;
            var position = {
                index:index,
                count:count,
                maxCount:CHORD_BANK_SIZE
            };
            var display_chord;
            var exercise_chord;

            // the first stave bar is a special case: it's reserved to show the
            // clef and key signature and nothing else
            treble = this.createDisplayStave('treble', _.clone(position));
            bass = this.createDisplayStave('bass', _.clone(position));
            position.index += 1;
            treble.connect(bass);
            staves.push(treble);

            // now add the staves for showing the notes
            for(var i = 0, len = display_items.length; i < len; i++) {
                var elapsed_quarters = 0;
                for(var j = 0; j < i; j++) {
                    var duration = 4;
                    var rhythm_value = null;
                    if(display_items[j].chord.settings.rhythm) {
                        rhythm_value = display_items[j].chord.settings.rhythm;
                    }
                    if(rhythm_value == null) {
                        rhythm_value = DEFAULT_RHYTHM_VALUE;
                    }

                    if(rhythm_value === "w") {
                        duration = 4;
                    }else if(rhythm_value === "h") {
                        duration = 2;
                    }else if(rhythm_value === "q") {
                        duration = 1;
                    }
                    elapsed_quarters += duration;
                }

                display_chord = display_items[i].chord;
                exercise_chord = exercise_items[i].chord;
                treble = this.createNoteStave('treble', _.clone(position), display_chord, exercise_chord, elapsed_quarters);
                bass = this.createNoteStave('bass', _.clone(position), display_chord, exercise_chord, elapsed_quarters);
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
        createNoteStave: function(clef, position, displayChord, exerciseChord, elapsed_quarters) {
            var stave = new Stave(clef, position);
            var rhythmDivisor = null;
            if(exerciseChord.settings.rhythm) {
                var rhythm_value = exerciseChord.settings.rhythm;
                if(rhythm_value == null) {
                    rhythm_value = DEFAULT_RHYTHM_VALUE;
                }

                if(rhythm_value === "w") {
                    rhythmDivisor = 1;
                }else if(rhythm_value === "h") {
                    rhythmDivisor = 2;
                }else if(rhythm_value === "q") {
                    rhythmDivisor = 4;
                }else {// should be false
                    rhythmDivisor = 1;
                }
            }

            stave.setRenderer(this.vexRenderer);
            stave.setKeySignature(this.keySignature);
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
            stave.updatePositionWithRhythm(rhythmDivisor, elapsed_quarters);

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
            this.clear();
            this.broadcast(EVENTS.BROADCAST.EXERCISE, target);
        }
    });

    return ExerciseSheetComponent;
});
