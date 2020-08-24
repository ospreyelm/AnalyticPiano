/* Analysis functions */
/* global define: false */

define([
    'lodash',
    'vexflow',
    'app/config'
], function(
    _, 
    Vex, 
    Config
) {

/* Wraps all the analysis methods and configuration data. */
var Analyze = function(keySignature, options) {

    if (!keySignature) {
        throw new Error("Missing key signature!");
    }

    var KEY = keySignature.getKey();
    var KEYNOTE_PC = keySignature.getKeyPitchClass();
    var KEY_OF_SIGNATURE = keySignature.getKeyOfSignature();
    var HIGHLIGHT_OPTS = (options ? options.highlightMode || {} : {});

    this.Piano = {
        key: KEY,
        keynotePC: KEYNOTE_PC,
        keyOfSignature: KEY_OF_SIGNATURE,
        highlightMode: HIGHLIGHT_OPTS,
    };
};

var NOTE_NAMES = Config.get('general.noteNames');
var PITCH_CLASSES = Config.get('general.pitchClasses');
var KEY_MAP = Config.get('general.keyMap');
var SPELLING_TABLE = _.reduce(KEY_MAP, function(result, value, key) {
    result[key] = value.spelling;
    return result;
}, {});

_.extend(Analyze.prototype, {
    noteNames: NOTE_NAMES,
    pitchClasses: PITCH_CLASSES,
    spelling: SPELLING_TABLE
});

var ANALYSIS_CONFIG = Config.get('analysis');

_.extend(Analyze.prototype, ANALYSIS_CONFIG);



var spellingAndAnalysisFunctions = {

    /* note_names_of_scale makes a call to vexflow */

    mod_7: function (note_name) {
        return "abcdefg".indexOf(note_name.slice(0,1).toLowerCase());
    },
    mod_12: function (note_name) {
        var dict1 = {"a":9, "b":11, "c":0, "d":2, "e":4, "f":5, "g":7};
        var anchor = dict1[note_name.slice(0,1).toLowerCase()];
        var dict2 = {"":0, "n":0, "bb":-2, "b":-1, "##":2, "#":1};
        var offset = dict2[note_name.slice(1)];
        return (12 + anchor + offset) % 12;
    },
    pcs_order_of_lowest_appearance: function (notes) {
        var dict = {}, stripped = [];
        var i, len;
        for (i = 0, len = notes.length; i < len; i++) {
            var pc = notes[i] % 12;
            if ( !dict.hasOwnProperty(pc) ) {
                dict[pc] = true;
                stripped.push( notes[i] );
            }
        }
        return stripped; /* lowest instance of each pitch class */
    },
    rel_pc: function (note, ref) {
        while (note < ref) { note += 12; }
        return (note - ref) % 12; /* % in js gives remainder not modulo */
    },
    key_is_none: function () {
        return this.Piano.key.indexOf('h') !== -1;
    },
    key_is_minor: function () {
        return this.Piano.key.indexOf('i') !== -1;
    },
    key_is_major: function () {
        return this.Piano.key.indexOf('j') !== -1;
    },
    note_name: function (mod_7, mod_12) {
        var letter = "abcdefg"[mod_7];

        /* change this calculation at your peril! */
        var displ = (5 + mod_12 - this.mod_12(letter)) % 12 - 5;

        if (displ > 0) return letter + "#".repeat(displ);
        if (displ < 0) return letter + "b".repeat(-1*displ);
        return letter;
    },
    upper_note_name: function (bass_pc, bass_name, semitones, steps) {
        var eval_mod_7 = (this.mod_7(bass_name) + steps) % 7;
        var eval_mod_12 = (bass_pc + semitones) % 12;
        return this.note_name(eval_mod_7, eval_mod_12);
    },
    accidental: function(vexnote) {
        var regex = /^([cdefgab])(b|bb|n|#|##)?\/.*$/;
        var match = regex.exec(vexnote.toLowerCase());
        if ( match[2] == undefined ) return "n";
        return match[2];
    },
    semitones_steps_str: function (note, ref) {
        /* per its interaction with other functions, this returns correct results for dyads only */
        var note_name = this.getNoteName(note, [ref, note]).split('/')[0].toLowerCase();
        var ref_name = this.getNoteName(ref, [ref, note]).split('/')[0].toLowerCase();

        var steps = (7 + this.mod_7(note_name) - this.mod_7(ref_name)) % 7;
        var semitones = note - ref;
        steps += Math.floor(semitones / 12) * 7; /* factor octaves back in */
        while (semitones < 0) {
            /* address negative values */
            semitones += 12;
            if (steps != 6) steps += 7; // ?
        }

        return semitones.toString() + '/' + steps.toString();
    },
    bare_octave_or_unison: function(notes) {
        if (notes.length == 1) return true;
        if (notes.length > 1) {
            var i, len;
            for (i = 1, len = notes.length; i < len; i++) {
                if(notes[i] % 12 != notes[0] % 12) {
                    return false;
                }
            }
        }
        return true;
    },
    get_chord_code: function (notes) {
        var chord = this.pcs_order_of_lowest_appearance(notes)
            .map(note => this.rel_pc(note, this.Piano.keynotePC)); /* n.b. relative to keynote */
        
        if ( this.key_is_none() ) var bass = "";
        else var bass = this.pitchClasses[chord[0]] + "/";
        
        chord = chord.slice(1); /* exclude bass */
        chord = chord.sort(function(a,b){return a-b});
        /* order of upper parts is irrelevant */

        return bass + chord.map(n => this.pitchClasses[n]).join('');
        /* e.g. "y/047" for C7/Bb */
    },
    intervals_above_bass: function (notes) {
        var chord = this.pcs_order_of_lowest_appearance(notes);

        var intervals = [], i, len;
        for (i = 1, len = chord.length; i < len; i++) {
            intervals.push(this.rel_pc(chord[i], chord[0]));
        }
        intervals.sort(function(a,b){return a-b});
        for (i = 0, len = intervals.length; i < len; i++) {
            intervals[i] = this.pitchClasses[intervals[i]];
        }
        
        return intervals.join('');
    },

    /* enharmonic spelling */
    push_flat: function (note, name) {
        var eval_mod_7 = (1 + this.mod_7(name)) % 7;
        return this.note_name(eval_mod_7, note % 12);
    },
    push_sharp: function (note, name) {
        var eval_mod_7 = (-1 + this.mod_7(name)) % 7;
        return this.note_name(eval_mod_7, note % 12);
    },
    getNoteName: function (note, chord) {
        var name = this.spelling[this.Piano.key][note % 12].toLowerCase();

        if ( this.key_is_major() ) {
            name = this.jEnharmonicAlterations(note, name, chord).toLowerCase();
        }
        if ( this.key_is_none() ) {
            name = this.hEnharmonicAlterations(note, name, chord).toLowerCase();
        }

        var octave = Math.floor(note/12) - 1;

        if (name == "cb" || name == "cbb") octave += 1;
        if (name == "b#" || name == "b##") octave -= 1;

        return name + "/" + octave;
    },
    jEnharmonicAlterations: function (midi, name, chord) {
        /* Changes the spelling of some chords in major keys */

        /* param {chord} is a list of midi numbers */
        /* param {name} is a string e.g. "c#" */

        if ( this.key_is_minor() || this.key_is_none() ) return name;

        /* options used for the conditionals below */
        var include_tonic = true;
        var include_predominants = true;

        /* relativize pitch class integers to keynote */
        var rpcs = [];
        var i, len;
        for (i = 0, len = chord.length; i < len; i++) {
            rpcs.push(this.rel_pc(chord[i], this.Piano.keynotePC));
        }
        var rel_pc = this.rel_pc(midi, this.Piano.keynotePC);

        /** call enharmonic changes **/
        if (rel_pc == 1 && _.contains(rpcs,8)) {
            return this.push_flat(midi,name);
            /* Neapolitan chords */
        }
        if (rel_pc == 3
        && (_.contains(rpcs,8)
            || (include_tonic === true
                && _.contains(rpcs,0) && _.contains(rpcs,7))
        )) {
            return this.push_flat(midi,name);
            /* tonic triads of the parallel minor */
        }
        if (rel_pc == 8
        && (_.contains(rpcs,1)
            || (_.contains(rpcs,0) && _.contains(rpcs,6))
            || (_.contains(rpcs,3) && !_.contains(rpcs,1) && !_.contains(rpcs,6))
            || (include_predominants === true && _.contains(rpcs,0) && _.contains(rpcs,5) && !_.contains(rpcs,11))
            || (include_predominants === true && _.contains(rpcs,2) && _.contains(rpcs,5) && !_.contains(rpcs,11))
        )) {
            return this.push_flat(midi,name);
            /* augmented sixths and other pre-dominant chords */
        }

        return name;
    },
    hEnharmonicAlterations: function (midi, name, chord) {
        /* Aggressively re-spells chords when key is none */

        /* param {chord} is a list of midi numbers */
        /* param {name} is a string e.g. "c#" */

        if ( this.key_is_major() || this.key_is_minor() ) return name;

        chord = chord.sort(function(a,b){return a-b});

        var bass_pc = (12 + chord[0]) % 12;
        
        if (chord.length == 2) {
            var semitones = this.rel_pc(midi, bass_pc); /* register is irrelevant */
            if (!this.hIntervals[semitones]) {
                return this.noteNames[midi % 12]; /** return default spelling **/
            }

            /* how the bass is spelled according to the type of interval */
            /* expressed as a minor key */
            var scale = this.hIntervals[semitones]["spellbass"];

            if (scale === "___") {
                return this.noteNames[midi % 12]; /** return default spelling **/
            }

            var bass_name = this.spelling[scale][bass_pc].toLowerCase();
            var steps = this.hIntervals[semitones]["stepwise"];
            if (midi % 12 == bass_pc) {
                /* ?!! as function is currently called, never true ?!! */
                /* make M3 below Eb and above G3 to see the difference */
                return bass_name;
            } else {
                return this.upper_note_name(parseInt(bass_pc), bass_name, parseInt(semitones), parseInt(steps));
            }
        }
        if (chord.length >= 3) {
            var profile = this.intervals_above_bass(chord);
            if (!this.hChords[profile]) {
                return this.noteNames[midi % 12]; /** return default spelling **/
            }

            /* how the bass is spelled according to the type of interval */
            /* expressed as a minor key */
            var scale = this.hChords[profile]["spellbass"];

            if (scale === "___") {
                return this.noteNames[midi % 12]; /** return default spelling **/
            }

            var all_steps = this.hChords[profile]["stepwise"];
            var bass_name = this.spelling[scale][bass_pc].toLowerCase();
            var semitones = this.rel_pc(midi, bass_pc);
            var idx = profile.indexOf(this.pitchClasses[semitones]);
            var steps = (idx === -1 ? 0 : parseInt(all_steps[idx])); /* parseInt is critical */
            return this.upper_note_name(chord[0], bass_name, semitones, steps);
        }

        return this.noteNames[midi % 12]; /** return default spelling **/
    },

    /* analytical labels */
    to_note_name: function(notes) {
        if ( notes.length < 1 ) return "";
        if ( !this.bare_octave_or_unison(notes) ) return "";

        if (typeof notes == 'number') var midi = notes;
        else var midi = notes[0];
        if ( this.key_is_none() ) var scale = this.noteNames; /* per D minor */
        else var scale = this.spelling[this.Piano.key];

        return scale[midi % 12].replace(/b/g,'♭').replace(/#/g,'♯');
    },
    to_helmholtz: function (note) {
        var noteParts = note.split('/');
        var octave = parseInt(noteParts[1], 10);
        var noteName = noteParts[0];
        noteName = noteName[0].toUpperCase() + noteName.slice(1);
        if (octave < 2)
            return noteName + ' ' + ','.repeat(2 - octave);
        if (octave == 2) return noteName;
        if (octave == 3) return noteName.toLowerCase();
        if (octave > 3)
            return noteName.toLowerCase() + ' ' + "'".repeat(octave - 2);
        return ''; /* should never be reached */
    },
    to_scientific_pitch: function (note) {
        var noteParts = note.split('/');
        if (noteParts.length == 2) {
            var noteName = noteParts[0];
            var octave = parseInt(noteParts[1], 10);
            return noteName[0].toUpperCase() + noteName.slice(1) + octave;
        }
        return ''; /* should never be reached */
    },
    get_label: function(notes, label_type) {
        /* used by to_solfege and to_scale_degree */
        if ( this.key_is_none() ) return "";
        if (notes.length < 1) return "";
        if (notes.length > 1 && !this.bare_octave_or_unison(notes)) return "";

        if ( this.key_is_minor() ) var labels = this.iDegrees;
        else var labels = this.jDegrees;

        var dist = this.semitones_steps_str(notes[0] % 12, this.Piano.keynotePC);
        if ( !labels[dist] ) return "";
        return labels[dist][label_type];
    },
    to_solfege: function(notes) {
        return this.get_label(notes, "solfege");
    },
    to_scale_degree: function(notes) {
        return this.get_label(notes, "numeral");
    },
    to_interval: function (notes) {
        var anon = {"name": ""}
        
        if (notes.length !== 2) return anon;

        if ( this.key_is_none() ) {
            var profile = notes[1] - notes[0];
            var all_labels = this.hIntervals;
        } else {
            var profile = this.semitones_steps_str(notes[1], notes[0]);
            var all_labels = this.ijIntervals
        }
        
        if (!all_labels[profile]) return anon;
        if (!all_labels[profile]["label"]) return anon;

        return {"name": all_labels[profile]["label"]};
    },
    to_chord: function(notes) {
        if (notes.length < 2) return "";
        if (notes.length == 2) return this.to_interval(notes);

        if ( this.key_is_none() ) {
            return this.hFindChord(notes);
        } else {
            return this.ijFindChord(notes);
        }
    },
    hFindChord: function (notes) {
        var profile = this.intervals_above_bass(notes);
        var chordEntry = _.cloneDeep(this.hChords[profile]);
        if (!chordEntry) return "";

        if (chordEntry["spellbass"] === "___") {
            return chordEntry;
        }

        var bassName = this.spelling[chordEntry["spellbass"]][notes[0] % 12];

        var rootName = "";
        if (chordEntry["root"] != "_") {
            let bass_pc = parseInt(notes[0])
            let bass_name = bassName
            let semitones = parseInt(chordEntry["root"])
            let steps = parseInt(chordEntry["rootstepwise"])
            rootName = this.upper_note_name(bass_pc, bass_name, semitones, steps);  
        }

        var label = chordEntry["label"];
        if (rootName !== "") {
            if (label.indexOf("&R") != -1) label = label.replace(/\&R/,rootName[0].toUpperCase() + rootName.slice(1));
            if (label.indexOf("&r") != -1) label = label.replace(/\&r/,rootName.toLowerCase());
        }
        if (bassName !== "") {
            if (label.indexOf("&X") != -1) label = label.replace(/\&X/,bassName[0].toUpperCase() + bassName.slice(1));
            if (label.indexOf("&x") != -1) label = label.replace(/\&x/,bassName.toLowerCase());
        }
        chordEntry["label"] = label;

        return chordEntry;
    },
    ijFindChord: function (notes) {
        if ( this.key_is_minor() ) {
            var labels = this.iChords;
        } else {
            var labels = this.jChords;
        }
        var chord_code = this.get_chord_code(notes);
        if ( !labels[chord_code] ) return "";
        return labels[chord_code];
    },

    /* staff notation colors */
    instances_of_root: function(notes) {
        var roots = [], root, is_valid_root; 
        var entry, chords, note, i, len;

        var is_valid_root = function(root) {
            return ( !isNaN(root) && typeof root !== 'undefined' && root !== null && root !== '_' );
        };

        notes.sort(function(a,b){return a-b});

        if ( this.key_is_none() ) {
            var profile = this.intervals_above_bass(notes);
            if ( this.hChords[profile] ) {
                root = parseInt(this.hChords[profile]["root"], 10);
                /* grabs a relative pc of root above bass */
            }
            if ( !is_valid_root(root) ) return [];
            var roots = []
            for (i = 0, len = notes.length; i < len; i++) {
                if ( this.rel_pc(notes[i], notes[0]) == root ) roots.push(notes[i]);
            }
            return roots;
        }

        if ( this.key_is_major() || this.key_is_none() )  chords = this.jChords;
        if ( this.key_is_minor() )  chords = this.iChords;

        entry = this.get_chord_code(notes);
        if ( chords[entry] )  root = chords[entry]["root"];

        if ( is_valid_root(root) && this.pitchClasses.indexOf(root) != -1 ) {
            root = (this.pitchClasses.indexOf(root) + this.Piano.keynotePC) % 12;
            for (i = 0, len = notes.length; i < len; i++) {
                note = notes[i];
                if(root == (note % 12)) {
                    roots.push(note);
                }
            }
        }
        return roots;
    },
    is_lowered: function (note, notes) {
        if ( this.key_is_minor()
             && this.rel_pc(note, this.Piano.keynotePC) == 1
        ) { /* lowered second scale degree in minor */
            return true;
        }
        var auto = this.spelling[this.Piano.key][note % 12].toLowerCase();
        var name = this.getNoteName(note, notes).split("/")[0];
        return name == this.push_flat(note, auto);
    },
    is_minor_mixture: function (note, notes) {
        if ( !this.key_is_major() ) return false;
        var name = this.getNoteName(note, notes).split("/")[0];

        var maj_scale = this.note_names_of_scale(this.Piano.key);
        if ( maj_scale.indexOf(name) !== -1 ) return false; /* diatonic to major */
        
        var min_key = "i"+this.Piano.key.slice(1);
        var min_scale = this.note_names_of_scale(min_key);
        if ( min_scale.indexOf(name) === -1 ) return false; /* not diatonic to minor */
        
        var auto_min = this.spelling[min_key][note % 12].toLowerCase();
        return name == auto_min;
    },
    get_color: function (note, notes) {
        /* Color in pitches on the sheet music to highlight musical phenomena. */

        var i, len;
        if (this.Piano.highlightMode["solobass"]) {
            if (note == notes[0]) {
                return "";
            } else {
                return "white";
            }
        }
        if (this.Piano.highlightMode["roothighlight"]) {
            if ( _.contains(this.instances_of_root(notes), note) ) return "red";
        }
        if (this.Piano.highlightMode["tritonehighlight"]) {
            for (i = 0, len = notes.length; i < len; i++) {
                other = notes[i];
                if (this.rel_pc(other, note) == 6) return "#d29";
            }
        }
        if (this.Piano.highlightMode["doublinghighlight"]) {
            var key_pc = this.Piano.keynotePC;
            if ( (this.key_is_minor() && _.contains( [4,6,11], this.rel_pc(note, key_pc) )) /* tendency tones in minor */
            || (this.key_is_major() && _.contains( [1,6,8,11],this.rel_pc(note, key_pc) )) /* tendency tones in major */
            ) {
                for (i = 0, len = notes.length; i < len; i++) {
                    other = notes[i];
                    if (other != note && this.rel_pc(other, note) === 0) return "orange";
                }
            }
        }
        if (this.Piano.highlightMode["loweredhighlight"]) {
            if (this.is_lowered(note, notes)) return "green";
        }
        if (this.Piano.highlightMode["modalmixturehighlight"]) {
            if (this.is_minor_mixture(note, notes)) return "green";
        }
        if (this.Piano.highlightMode["octaveshighlight"]) {
            var color = "";
            var i, len;
            for (i = 1, len = notes.length; i < len; i++) {
                itvl = (-1 + note - notes[i]) % 12 + 1; /* remainder operator: NOT inversionally equivalent */
                if (itvl == 7) color = "green"; /* higher note of P5 interval */
                if (itvl == 12) {
                    if (color == "green") return "#099"; /* higher note of both P5 and P8 intervals */
                    else color = "blue"; /* higher note of P8 interval */
                }
            }
            if (color !== "") return color;
        } 
        return "";
    },

    /* thoroughbass a.k.a. figured bass */
    note_names_of_scale: function(key) {
        var vfmus = new Vex.Flow.Music();
        var vfrts = Vex.Flow.Music.roots;

        var keynote = ( key == "h" ?
                        "c" : /* should never be called */
                        key.slice(1).replace('_','').toLowerCase() );
        try { var key_pc = vfmus.getNoteValue(keynote) } catch(e) {
            keynote = "c"; var key_pc = vfmus.getNoteValue(keynote);
        }
        
        var intervals = (key.indexOf('i') !== -1 ? /* minor */
                         [2, 1, 2, 2, 1, 2, 2] :
                         [2, 2, 1, 2, 2, 2, 1])
        
        var key_mod7 = vfrts.indexOf(keynote[0]);
        var scale_pcs = vfmus.getScaleTones(key_pc, intervals);

        var note_names = [];
        var i;
        for (i = 0; i < 7; i++) {
            letter = vfrts[(i + key_mod7) % 7];
            pc = scale_pcs[i];
            note_names.push(vfmus.getRelativeNoteName(letter, pc));
        }
        return note_names;
        /* e.g. [ "eb", "f", "g", "ab", "bb", "c", "d" ] */
    },
    is_diatonic: function (note_name) {
        var scale = (this.key_is_none() ?
                     this.note_names_of_scale(this.Piano.keyOfSignature) :
                     this.note_names_of_scale(this.Piano.key))
        return scale.indexOf(note_name) !== -1;
    },
    inflect: function (note_name, num) {
        /* return name of note altered chromatically per {num} */
        return this.note_name(this.mod_7(note_name), (this.mod_12(note_name) + parseInt(num)) % 12);
    },
    get_offset: function (note_name) {
        /* return displacement from the diatonic scale in semitones */
        offset = null;
        [0, 1, -1, 2, -2, 3, -3].some(n => {
            var probe_name = this.inflect(note_name, n);
            return (this.is_diatonic(probe_name) ? offset = -1*n : false);
        });
        return (offset === -0 ? 0 : offset);
    },
    full_thoroughbass_figure: function(midi_nums) {
        if (midi_nums.length < 2) return "";
        var stack = this.thoroughbass_stack(midi_nums).map(item => item[0]);
        return stack.join('/');
    },
    full_thoroughbass_figure_minus_octave: function(midi_nums) {
        if (midi_nums.length < 2) return "";
        var stack = this.thoroughbass_stack(midi_nums).map(item => item[0]).filter(function(interval){return interval !== "8"});
        return stack.join('/');
    },
    abbrev_thoroughbass_figure: function(midi_nums) {
        if (midi_nums.length < 2) return "";
        var stack = this.abbreviate_thoroughbass(this.thoroughbass_stack(midi_nums));
        return stack.join('/');
    },
    thoroughbass_stack: function(midi_nums) {
        var bass_midi = midi_nums[0];
        var bass_name = this.getNoteName(bass_midi, midi_nums);

        var intervals = [];
        var i, len;
        for (i = 1, len = midi_nums.length; i < len; i++) {
            var midi = midi_nums[i];
            var name = this.getNoteName(midi, midi_nums);

            /* three lines copied from semitones_steps_str */
            var steps = (7 + this.mod_7(name) - this.mod_7(bass_name)) % 7;
            var semitones = midi - bass_midi;
            steps += Math.floor(semitones / 12) * 7; /* factor octaves back in */
            
            var number = steps % 7 === 0 ? 8 : 1 + (steps % 7);
            if (number == 2 && String(intervals).match(/3/)) number = 9;
            
            var offset = this.get_offset(name.split("/")[0]);
            if (number == 8) {
                if (name.split("/")[0] == bass_name.split("/")[0]) prefix = "";
                else prefix = this.accidental(name);
            } else if (number == 7 && this.rel_pc(midi, bass_midi) == 9) {
                prefix = "\xb0" /* diminished seventh */
            } else {
                prefix = (offset === 0 ? "" : this.accidental(name))
            }
            
            var itv = [prefix + String(number), offset];
            if ( !intervals.some(x => itv[0] == x[0] && itv[1] == x[1]) ) {
                intervals.push(itv);
            }
        }

        var stack = intervals.sort(function(a,b){
            return a[0].replace(/[^0-9]+/g, '') - b[0].replace(/[^0-9]+/g, '')
        }).reverse();

        return stack;
    },
    currently_first_inversion_dominant_tetrad: function() {
        var midi_nums = []; /* GET CURRENT MIDI NUMBERS: NOT WIRED IN YET */
        /* see app/models/chord */
        return [0,3,6,8] == this.pcs_order_of_lowest_appearance(midi_nums)
            .map(midi => this.rel_pc(midi, midi_nums[i])) /* n.b. relative to bass */
            .sort(function(a,b){return a-b});
    },
    abbreviate_thoroughbass: function (intervals) {

        var french_thoroughbass = false;

        class Stack {
            constructor(stack) {
                if (typeof stack == 'string') stack = Array(stack);
                this.stack = stack;
            }
            length() {
                return this.stack.length;
            }
            extract_nums(arr) {
                return arr.map( item => item.replace(/[^0-9]+/g, "") );
            }
            matches(ref_stack, match_type=null) {
                if (typeof ref_stack == 'string') ref_stack = Array(ref_stack);

                if (match_type == "nums") {
                    var arr1 = this.extract_nums(this.stack);
                    var arr2 = this.extract_nums(ref_stack);
                } else {
                    var arr1 = this.stack;
                    var arr2 = ref_stack;
                }

                if (arr1.length != arr2.length) return false;
                var i, len;
                for (i = 0, len = arr1.length; i < len; i++) {
                    if ( arr1[i] != arr2[i] ) return false;
                }
                return true;
            }
            parenth(find, also_present=false) {
                if (also_present) {
                    var idx1 = this.stack.indexOf(find);
                    var idx2 = this.stack.indexOf(also_present);
                    if (idx1 !== -1 && idx2 !== -1) this.stack[idx1] = "[" + find + "]";
                } else {
                    var idx = this.stack.indexOf(find);
                    if (idx !== -1) this.stack[idx] = "[" + find + "]";
                }
            }
            third_as_accidental() {
                var i, len;
                for (i = 0, len = this.stack.length; i < len; i++) {
                    this.stack[i] = this.stack[i].replace(/^([#|n|b]+)3$/, "$1");
                }
            }
            relativize(num, offset, prefix=null, suffix=null) {
                var i, len;
                for (i = 0, len = this.stack.length; i < len; i++) {
                    /* takes intervals from outside scope */
                    if (this.stack[i].replace(/[^0-9]+/g, "") !== String(num)) continue;
                    if (intervals[i][1] !== offset) continue;
                    if (!prefix) prefix = "";
                    if (!suffix) suffix = (offset >= 0 ? "+".repeat(offset) : "-".repeat(-1*offset));
                    this.stack[i] = prefix + String(num) + suffix;
                }
            }
            rewrite(arr) {
                this.stack = arr;
            }
            expunge_parenthesized() {
                var i;
                for (i = this.stack.length-1; i >= 0; i--) {
                    if (this.stack[i].match(/^\[.+\]$/)) {
                        this.stack.splice(i,1);
                    }
                }
            }
        }

        /*---------*/
        var stack = new Stack(intervals.map(item => item[0]));
        /*---------*/

        stack.parenth("8");
        stack.expunge_parenthesized();
        
        stack.relativize(4, 1);
        stack.relativize(5, 1);
        stack.relativize(6, 1);

        if (stack.matches(["7","5","3"], "nums")) {
            stack.parenth("5");
            stack.parenth("3","[5]");
        }
        else if (stack.matches(["6","5","3"], "nums")) {
            stack.parenth("3");
        }
        else if (stack.matches(["6","4","3"], "nums")) {
            stack.parenth("6");
        }
        else if (stack.matches(["6","4","2"], "nums")) {
            stack.parenth("6");
        }
        else if (stack.matches(["6","3"], "nums")) {
            stack.parenth("3");
        }
        else if (stack.matches(["5","3"], "nums")) {
            stack.parenth("5");
            stack.parenth("3","[5]");
        }
        else if (stack.matches(["5","4"], "nums")) {
            stack.parenth("5","4");
        }
        else if (stack.matches(["9","5","3"], "nums")) {
            stack.parenth("5");
            stack.parenth("3","[5]");
        }
        else if (stack.matches(["7","3"], "nums")) {
            stack.parenth("3");
        }

        if (stack.length() > 1) {
            stack.third_as_accidental();
        }

        if (french_thoroughbass) {
            if (stack.matches(['[6]','4+','2'])) {
                stack.parenth("2");
            }
            if (stack.matches(['[6]','4','2'])) {
                stack.parenth("4");
            }
            if (false && this.currently_first_inversion_dominant_tetrad() // disabled
            && (stack.matches(['6','5','[3]'])
            || stack.matches(['6','5','n'])
            || stack.matches(['6','5','b'])
            || stack.matches(['6','5','#'])
            )) {
                stack.rewrite(["/5"]);
            }
        }

        stack.expunge_parenthesized()

        /*---------*/

        return stack["stack"];
    },
};

_.extend(Analyze.prototype, spellingAndAnalysisFunctions);



return Analyze;
});
