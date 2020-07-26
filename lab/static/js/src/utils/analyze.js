/* Analysis functions
 *
 * Ported from the old harmony prototype with minimal changes. */

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


var ANALYSIS_CONFIG = Config.get('analysis');
var PITCH_CLASSES = Config.get('general.pitchClasses');
var NOTE_NAMES = Config.get('general.noteNames');
var KEY_MAP = Config.get('general.keyMap');
var SPELLING_TABLE = _.reduce(KEY_MAP, function(result, value, key) {
    result[key] = value.spelling;
    return result;
}, {});



var analyzing = {
    keynotePC: {
        "h":   0,
        "jC_": 0,
        "iC_": 0,
        "jC#": 1,
        "iC#": 1,
        "jDb": 1,
        "jD_": 2,
        "iD_": 2,
        "iD#": 3,
        "jEb": 3,
        "iEb": 3,
        "jE_": 4,
        "iE_": 4,
        "jF_": 5,
        "iF_": 5,
        "jF#": 6,
        "iF#": 6,
        "jGb": 6,
        "jG_": 7,
        "iG_": 7,
        "iG#": 8,
        "jAb": 8,
        "iAb": 8,
        "jA_": 9,
        "iA_": 9,
        "iA#": 10,
        "jBb": 10,
        "iBb": 10,
        "jB_": 11,
        "iB_": 11,
        "jCb": 11 
    },
    AtoGindices: {
        /* the names of these dictionary keys follow VexFlow */
        /* A */
        'a':   { root_index: 0, int_val: 9 },
        'an':  { root_index: 0, int_val: 9 },
        'a#':  { root_index: 0, int_val: 10 },
        'a##': { root_index: 0, int_val: 11 },
        'ab':  { root_index: 0, int_val: 8 },
        'abb': { root_index: 0, int_val: 7 },
        /* B */
        'b':   { root_index: 1, int_val: 11 },
        'bn':  { root_index: 1, int_val: 11 },
        'b#':  { root_index: 1, int_val: 0 },
        'b##': { root_index: 1, int_val: 1 },
        'bb':  { root_index: 1, int_val: 10 },
        'bbb': { root_index: 1, int_val: 9 },
        /* C */
        'c':   { root_index: 2, int_val: 0 },
        'cn':  { root_index: 2, int_val: 0 },
        'c#':  { root_index: 2, int_val: 1 },
        'c##': { root_index: 2, int_val: 2 },
        'cb':  { root_index: 2, int_val: 11 },
        'cbb': { root_index: 2, int_val: 10 },
        /* D */
        'd':   { root_index: 3, int_val: 2 },
        'dn':  { root_index: 3, int_val: 2 },
        'd#':  { root_index: 3, int_val: 3 },
        'd##': { root_index: 3, int_val: 4 },
        'db':  { root_index: 3, int_val: 1 },
        'dbb': { root_index: 3, int_val: 0 },
        /* E */
        'e':   { root_index: 4, int_val: 4 },
        'en':  { root_index: 4, int_val: 4 },
        'e#':  { root_index: 4, int_val: 5 },
        'e##': { root_index: 4, int_val: 6 },
        'eb':  { root_index: 4, int_val: 3 },
        'ebb': { root_index: 4, int_val: 2 },
        /* F */
        'f':   { root_index: 5, int_val: 5 },
        'fn':  { root_index: 5, int_val: 5 },
        'f#':  { root_index: 5, int_val: 6 },
        'f##': { root_index: 5, int_val: 7 },
        'fb':  { root_index: 5, int_val: 4 },
        'fbb': { root_index: 5, int_val: 3 },
        /* G */
        'g':   { root_index: 6, int_val: 7 },
        'gn':  { root_index: 6, int_val: 7 },
        'g#':  { root_index: 6, int_val: 8 },
        'g##': { root_index: 6, int_val: 9 },
        'gb':  { root_index: 6, int_val: 6 },
        'gbb': { root_index: 6, int_val: 5 }
    },
    mod_7: function (note_name) {
        /* slice because accidental is irrelevant */
        return this.AtoGindices[note_name.slice(0,1).toLowerCase()].root_index;
        /* A is 0 ... G is 6 */
    },
    mod_12: function (note_name) {
        return this.AtoGindices[note_name.toLowerCase()].int_val;
        /* C is 0 */
    },
    key_is_minor: function () {
        if (this.Piano.key.indexOf('i') !== -1) return true;
        else return false;
    },
    key_is_major: function () {
        if (this.Piano.key.indexOf('j') !== -1) return true;
        else return false;
    },
    key_is_none: function () {
        if (this.Piano.key.indexOf('h') !== -1) return true;
        else return false;
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
        for (var i in chord) {
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
    is_lowered: function (note, notes) {
        var name = this.spelling[this.Piano.key][note % 12].toLowerCase();
        if (name == this.push_flat(note, name)) {
            return true;
        }
        if (this.Piano.key.indexOf('i') == 0 && this.rel_pc(note, this.Piano.keynotePC) == 1) {
            return true;
            /* lowered second scale degree in minor */
        }
        return false;
    },
    has_modal_mixture: function (note, notes) {
        if (this.rel_pc(note, this.Piano.keynotePC) !== 1 && this.is_lowered(note, notes)) {
            return true;
        }
        return false;
    },
    push_flat: function (note, name) {
        let eval_mod_7 = (1 + this.mod_7(name)) % 7;
        return this.note_name(eval_mod_7, note % 12);
    },
    push_sharp: function (note, name) {
        let eval_mod_7 = (-1 + this.mod_7(name)) % 7;
        return this.note_name(eval_mod_7, note % 12);
    },
    getRelativeNoteName: function (mod_7, mod_12) {
        /* This function name is the same as in VexFlow */
        // possibly obsolete
        return this.note_name(parseInt(mod_7), parseInt(mod_12));
    },
    note_name: function (mod_7, mod_12) {
        var letter = "abcdefg"[mod_7];

        /* change this calculation at your peril! */
        var displ = (5 + mod_12 - this.mod_12(letter)) % 12 - 5;

        if (displ > 0) return letter + "#".repeat(displ);
        if (displ < 0) return letter + "b".repeat(-1*displ);
        return letter;
    },
    note_above_name: function (bass_pc, bass_name, semitones, steps) {
        let eval_mod_7 = (this.mod_7(bass_name) + steps) % 7;
        let eval_mod_12 = (bass_pc + semitones) % 12;
        return this.note_name(eval_mod_7, eval_mod_12);
    },
    rel_pc: function (note, ref) {
        while (note < ref) { note += 12; }
        return (note - ref) % 12; /* % gives remainder not modulo */
    },
    get_color: function (note, notes) {
        /* Color in pitches on the sheet music to highlight musical phenomena. */

        if (this.Piano.highlightMode["roothighlight"]) {
            if ( _.contains(this.instances_of_root(notes), note) ) return "red";
        }
        if (this.Piano.highlightMode["tritonehighlight"]) {
            for (var i = 0; i < notes.length; i++) {
                other = notes[i];
                if (this.rel_pc(other, note) == 6) return "#d29";
            }
        }
        if (this.Piano.highlightMode["doublinghighlight"]) {
            var key_pc = this.Piano.keynotePC;
            if ( (this.key_is_minor() && _.contains( [4,6,11], this.rel_pc(note, key_pc) )) /* tendency tones in minor */
            || (this.key_is_major() && _.contains( [1,6,8,11],this.rel_pc(note, key_pc) )) /* tendency tones in major */
            ) {
                for (var i = 0; i < notes.length; i++) {
                    other = notes[i];
                    if (other != note && this.rel_pc(other, note) === 0) return "orange";
                }
            }
        }
        if (this.Piano.highlightMode["loweredhighlight"]) {
            if (this.is_lowered(note, notes) === true) return "green";
        }
        if (this.Piano.highlightMode["modalmixturehighlight"]) {
            if (this.has_modal_mixture(note, notes) === true) return "green";
        }
        if (this.Piano.highlightMode["octaveshighlight"]) {
            var color = ""
            for (var i = 1; i < notes.length; i++) {
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
    pcs_order_of_lowest_appearance: function (notes) {
        var dict = {}, stripped = [];
        for(i = 0, len = notes.length; i < len; i++) {
            var pc = notes[i] % 12;
            if ( !dict.hasOwnProperty(pc) ) {
                dict[pc] = true;
                stripped.push( notes[i] );
            }
        }
        return stripped; /* lowest instance of each pitch class */
    },
    instances_of_root: function(notes) {
        var roots = [], root, is_valid_root; 
        var entry, chords, note, i, len;

        var is_valid_root = function(root) {
            return ( !isNaN(root) && typeof root !== 'undefined' && root !== null && root !== '_' );
        };

        notes.sort(function(a,b){return a-b});

        if ( this.key_is_none() ) {
            var profile = this.getIntervalsAboveBass(notes);
            if ( this.hChords[profile] ) {
                root = parseInt(this.hChords[profile]["root"], 10);
                /* grabs a relative pc of root above bass */
            }
            if ( !is_valid_root(root) ) return [];
            var roots = []
            for (i = 0; i < notes.length; i++) {
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
            for(i = 0, len = notes.length; i < len; i++) {
                note = notes[i];
                if(root == (note % 12)) {
                    roots.push(note);
                }
            }
        }
        return roots;
    },
    get_chord_code: function (notes) {
        var chord = this.pcs_order_of_lowest_appearance(notes)
            .map(note => this.rel_pc(note, this.Piano.keynotePC)); /* n.b. relative to keynote */
        
        if (this.Piano.key == "h") var bass = "";
        else var bass = "0123456789yz"[chord[0]] + "/";
        /* same pc designations used elsewhere */
        
        chord = chord.slice(1); /* exclude bass */
        chord.sort(function(a,b){return a-b}); /* order of upper parts is irrelevant */

        return bass + chord.map(n => "0123456789yz"[n]).join('');
        /* e.g. "y/047" for C7/Bb */
    },
    getIntervalsAboveBass: function (notes) {
        var chord = this.pcs_order_of_lowest_appearance(notes);
        var intervals = [];
        var bass, i, len, entry;
        
        bass = chord[0] % 12;
        chord = chord.slice(1);

        for (i = 0, len = chord.length; i < len; i++) {
            intervals.push(this.rel_pc(chord[i], bass));
        }
        
        intervals.sort(function(a,b){return a-b});
        
        for(i = 0, len = intervals.length; i < len; i++) {
            intervals[i] = this.pitchClasses[intervals[i]];
        }
        
        entry = intervals.join('');
        return entry;
    },
    accidental: function(vexnote) {
        var regex = /^([cdefgab])(b|bb|n|#|##)?\/.*$/;
        var match = regex.exec(vexnote.toLowerCase());
        if ( match[2] == undefined ) return "";
        return match[2];
    },
    semitones_steps_str: function (note, ref) {
        // convoluted
        var note_name = this.getNoteName(note, [ref, note]).split('/')[0].toLowerCase();
        var ref_name = this.getNoteName(ref, [ref, note]).split('/')[0].toLowerCase();

        var steps = (7 + this.mod_7(note_name) - this.mod_7(ref_name)) % 7;
        var semitones = note - ref;
        steps += Math.floor(semitones / 12) * 7; /* this factors octaves back in */
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
            for (let i = 1; i < notes.length; i++) {
                if(notes[i] % 12 != notes[0] % 12) {
                    return false;
                }
            }
        }
        return null;
    },
    get_note_name: function(notes) {
        if ( !this.bare_octave_or_unison(notes) ) return "";

        if (typeof notes == 'number') var midi = notes;
        else var midi = notes[0]; // array
        if ( this.key_is_none() ) var scale = this.noteNames; /* per D minor */
        else var scale = this.spelling[this.Piano.key];

        return scale[midi % 12].replace(/b/g,'♭').replace(/#/g,'♯');
    },
    to_solfege: function(notes) {
        return this.get_label(notes, "solfege");
    },
    to_scale_degree: function(notes) {
        return this.get_label(notes, "numeral");
    },
    get_label: function(notes, label_type) {
        if ( this.key_is_none() ) return "";
        if (notes.length < 1) return "";
        if (notes.length > 1 && !this.bare_octave_or_unison(notes)) return "";

        if ( this.key_is_minor() ) var labels = this.iDegrees;
        else var labels = this.jDegrees;

        var dist = this.semitones_steps_str(notes[0] % 12, this.Piano.keynotePC);
        if ( !labels[dist] ) return "";
        return labels[dist][label_type];
    },

    /* See the customizable listings of `jDegrees` `iDegrees` `iChords` and `jChords` */
    ijNameDegree: function (notes) {
        if (notes.length == 2) {
            var dist = this.semitones_steps_str(notes[1], notes[0]);
            if (this.ijIntervals[dist])
                return {"name": this.ijIntervals[dist]["label"], "numeral": null };
        }
        return {"name": "", "numeral": null};
    },
    findChord: function(notes) {
        if (this.Piano.key === 'h') return this.hFindChord(notes);
        return this.ijFindChord(notes);
    },
    ijFindChord: function (notes) {
        if (notes.length == 1) {
            return this.to_helmholtz(this.getNoteName(notes[0],notes));
            // when is this activated?
        } else if (notes.length == 2) {
            var dist = this.semitones_steps_str(notes[1], notes[0]);
            if (this.ijIntervals[dist]) {
                return this.ijIntervals[dist]["label"];
            }
        } else {
            if ( this.key_is_minor() ) {
                var labels = this.iChords;
            } else {
                var labels = this.jChords;
            }
            chord_code = this.get_chord_code(notes);
            if ( !labels[chord_code] ) return "";
            return labels[chord_code];
        }
        return;
    },
    hFindChord: function (notes) {
        var i, name, entry, chordEntry;
        var bassName = "", rootName = "";
        if (notes.length == 1) {
            name = this.to_helmholtz(this.getNoteName(notes[0],notes));
        } else if (notes.length == 2) {
            i = notes[1] - notes[0];
            if (this.hIntervals[i]) {
                name = {"label": this.hIntervals[i]};
            }
        } else {
            entry = this.getIntervalsAboveBass(notes);
            chordEntry = _.cloneDeep(this.hChords[entry]);
            if (chordEntry) {
                name = chordEntry["label"];
                if (chordEntry["spellbass"] === "___") {
                    return chordEntry;
                } else {        // fully diminished seventh
                    bassName = this.spelling[chordEntry["spellbass"]][notes[0] % 12];
                }

                if (chordEntry["root"] != "_") {
                    let bass_pc = parseInt(notes[0])
                    let bass_name = bassName
                    let semitones = parseInt(chordEntry["root"])
                    let steps = parseInt(chordEntry["rootstepwise"])
                    rootName = this.note_above_name(bass_pc, bass_name, semitones, steps);  
                }

                if (rootName !== '') {
                    if (name.indexOf("&R") != -1) name = name.replace(/\&R/,rootName[0].toUpperCase() + rootName.slice(1));
                    if (name.indexOf("&r") != -1) name = name.replace(/\&r/,rootName.toLowerCase());
                }
                if (bassName !== '') {
                    if (name.indexOf("&X") != -1) name = name.replace(/\&X/,bassName[0].toUpperCase() + bassName.slice(1));
                    if (name.indexOf("&x") != -1) name = name.replace(/\&x/,bassName.toLowerCase());
                }
                chordEntry["label"] = name;
                name = chordEntry;
            }
        }
        return name;
    },
    note_names_of_scale: function(key) {
        var vfmus = new Vex.Flow.Music()
        var vfrts = Vex.Flow.Music.roots

        var keynote = ( key == "h" ? "c" : key.slice(1).replace('_','').toLowerCase() );
        try { var key_pc = vfmus.getNoteValue(keynote) } catch(e) {
            keynote = "c"; var key_pc = vfmus.getNoteValue(keynote);
        }
        
        if (key.indexOf('i') != -1) var intervals = [2, 1, 2, 2, 1, 2, 2]; /* minor */
        else var intervals = [2, 2, 1, 2, 2, 2, 1]; /* major */
        
        var key_mod7 = vfrts.indexOf(keynote[0]);
        var scale_pcs = vfmus.getScaleTones(key_pc, intervals)

        var note_names = []
        for (var i = 0; i < 7; i++) {
            letter = vfrts[(i + key_mod7) % 7];
            pc = scale_pcs[i];
            note_names.push(vfmus.getRelativeNoteName(letter, pc));
        }
        return note_names;
        /* e.g. [ "eb", "f", "g", "ab", "bb", "c", "d" ] */
    },
    getNoteName: function (note, chord, called) {
        var name = this.spelling[this.Piano.key][note % 12].toLowerCase();

        if (this.key_is_major) {
            name = this.jEnharmonicAlterations(note, name, chord).toLowerCase();
        }
        if (this.key_is_none) {
            name = this.hEnharmonicAlterations(note, name, chord).toLowerCase();
        }

        var octave = Math.floor(note/12) - 1;

        if (name == "cb" || name == "cbb") octave += 1;
        if (name == "b#" || name == "b##") octave -= 1;

        return name + "/" + octave;
    },
    is_diatonic: function (note_name) {
        return this.Piano.diatonicNotes.indexOf(note_name) !== -1;
    },
    inflect: function (note_name, num) {
        /* name of note altered chromatically per {num} */
        return this.note_name(this.mod_7(note_name), (this.mod_12(note_name) + parseInt(num)) % 12);
    },
    get_offset: function (note_name) {
        /* returns displacement from the diatonic scale in semitones */
        offset = null;
        [0, 1, -1, 2, -2, 3, -3].some(n => {
            var probe_name = this.inflect(note_name, n);
            return (this.is_diatonic(probe_name) ? offset = -1*n : false);
        });
        return (offset === -0 ? 0 : offset);
    },
    thoroughbass_figure: function(midi_nums) {
        var bass_midi = midi_nums[0];
        var bass_name = this.getNoteName(bass_midi, midi_nums);

        Array.prototype.unique = function() {
            return this.filter(function (value, index, self) { 
                return self.indexOf(value) === index;
            });
        }

        intervals = [];
        for (var i = 1; i < midi_nums.length; i++) {
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
                else prefix = this.accidental(name).replace(/^$/, "n");
            } else if (number == 7 && this.rel_pc(midi, bass_midi) == 9) {
                prefix = "\xb0" /* diminished seventh */
            } else {
                prefix = (offset === 0 ? "" : this.accidental(name))
            }
            
            var interval = [prefix + String(number), offset];
            if (!intervals.includes(interval)) intervals.push(interval);
        }

        // .sort(function(a,b){return a-b})
        var stack = this.abbreviate_thoroughbass(intervals.reverse());

        return stack.join('/');
    },
    currently_first_inversion_dominant_tetrad: function() {
        var midi_nums = []; /* GET CURRENT MIDI NUMBERS: NOT WIRED IN YET */
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
                for (var i = 0; i < arr1.length; i++) {
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
                for (var i = 0; i < this.stack.length; i++) {
                    this.stack[i] = this.stack[i].replace(/^([#|n|b]+)3$/, /\1/);
                }
            }
            relativize(num, offset, prefix=null, suffix=null) {
                for (var i = 0; i < this.stack.length; i++) {
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
                for (var i = this.stack.length - 1; i >= 0; i--) {
                    if (this.stack[i].match(/^\[.+\]$/)) {
                        this.stack.splice(i,1);
                    }
                }
            }
        }

        /*---------*/
        var stack = new Stack(intervals.map(item => item[0]));
        /*---------*/

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

        if (stack.length > 1) {
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
                /*??? as called, this function never meets the condition ???*/
                /* make M3 below Eb and above G3 to see the difference */
                return bass_name;
            } else {
                return this.note_above_name(parseInt(bass_pc), bass_name, parseInt(semitones), parseInt(steps));
            }
        }
        if (chord.length >= 3) {
            var profile = this.getIntervalsAboveBass(chord);
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
            var idx = profile.indexOf("0123456789yz"[semitones]);
            var steps = (idx === -1 ? 0 : parseInt(all_steps[idx])); /* parseInt is critical */
            return this.note_above_name(chord[0], bass_name, semitones, steps);
        }

        return this.noteNames[midi % 12]; /** return default spelling **/
    },
};


// Constructor for an object that wrap all the analysis methods and
// configuration data.
var Analyze = function(keySignature, options) {
    options = options || {};
    if(!keySignature) {
        throw new Erorr("missing key signature");
    }

    var keynotePC = keySignature.getKeyPitchClass();
    var key = keySignature.getKey();

    // There used to be a global variable "Piano" in the old harmony prototype
    // that contained various properties and global settings. In order to keep
    // the analysis methods relatively intact when porting from the old
    // prototype app to the new one, a decision was made to provide a local object to 
    // stand in for the old one. Eventually, this should be completely
    // refactored.

    var Piano = {
        key: key,
        keynotePC: keynotePC,
        diatonicNotes: this.note_names_of_scale(key),
        highlightMode: {
            "octaveshighlight": false,
            "doublinghighlight": false,
            "tritonehighlight": false,
            "fifthshighlight": false
        }
    };

    if(options.highlightMode) {
        _.extend(Piano.highlightMode, options.highlightMode);
    }

    this.Piano = Piano;
};


// Augment prototype with methods and configuration data shared by all instances
_.extend(Analyze.prototype, {
    noteNames: NOTE_NAMES,
    pitchClasses: PITCH_CLASSES,
    spelling: SPELLING_TABLE
});
_.extend(Analyze.prototype, ANALYSIS_CONFIG);
_.extend(Analyze.prototype, analyzing);

return Analyze;
});
