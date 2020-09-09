/* General configuration data */
/* Read only */

/* global define: false */
define({
	defaultKeyboardSize: 49, /* key count */
	defaultOctaveAdjustment: 0,
	maskTrebleStaff: false, /* copy this boolean as conditional on following line */
	staffDistribution: (false ? "LH" : ["keyboard", "chorale", "LH", "RH", "keyboardPlusRHBias","keyboardPlusLHBias"][0]),
	voiceCountForKeyboardStyle: [2, 3, 4],
	voiceCountForChoraleStyle: [4],
	defaultNoteColor: "rgb(180,180,180)", /* gray */
	defaultRhythmValue: "w", /* whole note (semibreve) */
	chordBank: {displaySize:9}, /* number of chords spread across the sheet music */
	defaultKeyAndSignature: "jC_",
	metronomeSettings: {defaultTempo:40,maxTempo:360},
	bankAfterMetronomeTick: 0.25, /* fraction of beat */
	keyboardShortcutsEnabled: true,

	noDoubleVision: false,

	autoExerciseAdvance: false,
	hideNextWhenAutoAdvance: false,
	repeatExercise: true,
	nextExerciseWait: 4000,
	repeatExerciseWait: 6000,

	numberedExerciseCount: 40,

	analysisSettings: {
		enabled: true,
		mode: {
			abbreviate_thoroughbass: true,
			
			/* max one of the following may be true */
			note_names: false,
			scientific_pitch: true,

			/* max one of the following may be true */
			scale_degrees: true,
			solfege: false,

			thoroughbass: true,
			roman_numerals: true,
			intervals: true
		}
	},

	highlightSettings: {
		enabled: true,
		mode: {
			roothighlight: false,
			tritonehighlight: false,
			doublinghighlight: true,
			modalmixturehighlight: true, /* minor mixture in a major key */
			loweredhighlight: false, /* shifted flatwise enharmonically */
			solobass: false,
			octaveshighlight: false /* not recommended, hidden from UI */
		}
	},

	orderOfSharps: ["F","C","G","D","A","E","B"],

	/* default spelling of chromatic scale per D-minor */
	noteNames: ["C","C#","D","Eb","E","F","F#","G","G#","A","Bb","B"],

	/* single character per pitch class */
	pitchClasses: ["0","1","2","3","4","5","6","7","8","9","y","z"],

	/* Major and minor keys are identified by unique three character strings
	 * with the following format:
	 *
	 *		[i|j] prefix for minor key or major key
	 *		[A-G] letter name from A to G
	 *		[_|#|b] natural, sharp, flat
	 */
	keyMap: {
		"h": { /* key undefined a.k.a "key is none" */
			spelling: ["C","C#","D","D#","E","F","F#","G","G#","A","Bb","B"], 
			pitchClass: 0,
			name: "No key",
			shortName: "",
			signature: ""
		},
		"iAb": {
			spelling: ["C","Db","D","Eb","Fb","F","Gb","G","Ab","Bbb","Bb","Cb"],
			pitchClass: 8,
			name: "A-flat minor",
			shortName: "a♭",
			signature: "bbbbbbb",
		},
		"jCb": {
			spelling: ["C","Db","D","Eb","Fb","F","Gb","G","Ab","Bbb","Bb","Cb"], 
			pitchClass: 11,
			name: "C-flat major",
			shortName: "C♭",
			signature: "bbbbbbb",
		},
		"iEb": {
			spelling: ["C","Db","D","Eb","Fb","F","Gb","G","Ab","A","Bb","Cb"],
			pitchClass: 3,
			name: "E-flat minor",
			shortName: "e♭",
			signature: "bbbbbb",
		},
		"jGb": {
			spelling: ["C","Db","D","Eb","Fb","F","Gb","G","Ab","A","Bb","Cb"],
			pitchClass: 6,
			name: "G-flat major",
			shortName: "G♭",
			signature: "bbbbbb",
		},
		"iBb": {
			spelling: ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","Cb"],
			pitchClass: 10,
			name: "B-flat minor",
			shortName: "b♭",
			signature: "bbbbb",
		},
		"jDb": {
			spelling: ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","Cb"],
			pitchClass: 1,
			name: "D-flat major",
			shortName: "D♭",
			signature: "bbbbb", 
		},
		"iF_":  {
			spelling: ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"],
			pitchClass: 5,
			name: "F minor",
			shortName: "f",
			signature: "bbbb",
		},
		"jAb": {
			spelling: ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"],
			pitchClass: 8,
			name: "A-flat major",
			shortName: "A♭",
			signature: "bbbb",
		},
		"iC_": {
			spelling: ["C","Db","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
			pitchClass: 0,
			name: "C minor",
			shortName: "c",
			signature: "bbb",
		},
		"jEb": {
			spelling: ["C","Db","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
			pitchClass: 3,
			name: "E-flat major",
			shortName: "E♭",
			signature: "bbb",
		},
		"iG_":  {
			spelling: ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
			pitchClass: 7,
			name: "G minor",
			shortName: "g",
			signature: "bb",
		},
		"jBb": {
			spelling: ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
			pitchClass: 10,
			name: "B-flat major",
			shortName: "B♭",
			signature: "bb",
		},
		"iD_":  {
			spelling: ["C","C#","D","Eb","E","F","F#","G","G#","A","Bb","B"],
			pitchClass: 2,
			name: "D minor",
			shortName: "d",
			signature: "b",
		},
		"jF_":  {
			spelling: ["C","C#","D","Eb","E","F","F#","G","G#","A","Bb","B"],
			pitchClass: 5,
			name: "F major",
			shortName: "F",
			signature: "b",
		},
		"iA_":  {
			spelling: ["C","C#","D","D#","E","F","F#","G","G#","A","Bb","B"],
			pitchClass: 9,
			name: "A minor",
			shortName: "a",
			signature: "",
		},
		"jC_":  {
			spelling: ["C","C#","D","D#","E","F","F#","G","G#","A","Bb","B"], 
			pitchClass: 0,
			name: "C major",
			shortName: "C",
			signature: "",
		},
		"iE_":  {
			spelling: ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
			pitchClass: 4,
			name: "E minor",
			shortName: "e",
			signature: "#",
		},
		"jG_": {
			spelling: ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
			pitchClass: 7,
			name: "G major",
			shortName: "G",
			signature: "#",
		},
		"iB_": {
			spelling: ["C","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
			pitchClass: 11,
			name: "B minor",
			shortName: "b",
			signature: "##",
		},
		"jD_": {
			spelling: ["C","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
			pitchClass: 2,
			name: "D major",
			shortName: "D",
			signature: "##",
		},
		"iF#": {
			spelling: ["B#","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
			pitchClass: 6,
			name: "F-sharp minor",
			shortName: "f♯",
			signature: "###",
		},
		"jA_": {
			spelling: ["B#","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
			pitchClass: 9,
			name: "A major",
			shortName: "A",
			signature: "###",
		},
		"iC#": {
			spelling: ["B#","C#","D","D#","E","E#","F#","F##","G#","A","A#","B"],
			pitchClass: 1,
			name: "C-sharp minor",
			shortName: "c♯",
			signature: "####",
		},
		"jE_": {
			spelling: ["B#","C#","D","D#","E","E#","F#","F##","G#","A","A#","B"],
			pitchClass: 4,
			name: "E major",
			shortName: "E",
			signature: "####",
		},
		"iG#": {
			spelling: ["B#","C#","C##","D#","E","E#","F#","F##","G#","A","A#","B"],
			pitchClass: 8,
			name: "G-sharp minor",
			shortName: "g♯",
			signature: "#####",
		},
		"jB_":  {
			spelling: ["B#","C#","C##","D#","E","E#","F#","F##","G#","A","A#","B"],
			pitchClass: 11,
			name: "B major",
			shortName: "B",
			signature: "#####",
		},
		"iD#": {
			spelling: ["B#","C#","C##","D#","E","E#","F#","F##","G#","G##","A#","B"],
			pitchClass: 3,
			name: "D-sharp minor",
			shortName: "d♯",
			signature: "######",
		},
		"jF#": {
			spelling: ["B#","C#","C##","D#","E","E#","F#","F##","G#","G##","A#","B"],
			pitchClass: 6,
			name: "F-sharp major",
			shortName: "F♯",
			signature: "######",
		},
		"iA#": {
			spelling: ["B#","C#","C##","D#","D##","E#","F#","F##","G#","G##","A#","B"],
			pitchClass: 10,
			name: "A-sharp minor",
			shortName: "a♯",
			signature: "#######",
		},
		"jC#": {
			spelling: ["B#","C#","C##","D#","D##","E#","F#","F##","G#","G##","A#","A##"],
			pitchClass: 1,
			name: "C-sharp major",
			shortName: "C♯",
			signature: "#######",
		}
	},

	/* In case the user chooses a key signature and the key-to-staff-signature lock is enabled */
	keySignatureMap: {
		"bbbbbbb": "jCb",
		"bbbbbb": "jGb",	
		"bbbbb": "jDb",
		"bbbb": "jAb",
		"bbb": "jEb",
		"bb": "jBb",
		"b": "jF_",
		"": "jC_",
		"#": "jG_",
		"##": "jD_",
		"###": "jA_",
		"####": "jE_",
		"#####": "jB_",
		"######": "jF#",
		"#######": "jC#"
	},

	keyDisplayGroups: [ /* grouping of keys on UI */
		/* [label, key1, key2, key3, ..., keyN] */
		/* To do: change to dictionary with arrays as values */
		// ["basic", "h","jC_","iA_","jG_","jF_","iD_"],
		// ["sharps", "iE_","jD_","iB_","jA_","iF#","jE_","iC#","jB_","iG#","jF#","iD#","jC#","iA#"],
		// ["flats", "jBb","iG_","jEb","iC_","jAb","iF_","jDb","iBb","jGb","iEb","jCb","iAb"],
		["basic", "h", "jC_", "iA_"],
		["major", "jCb", "jGb", "jDb", "jAb", "jEb", "jBb", "jF_", "jC_", "jG_", "jD_", "jA_", "jE_", "jB_", "jF#", "jC#"],
		["minor", "iAb", "iEb", "iBb", "iF_", "iC_", "iG_", "iD_", "iA_", "iE_", "iB_", "iF#", "iC#", "iG#", "iD#", "iA#"] 
	],

	keyWheel: [
		[ /* Chopin Preludes */
			"jC_","iA_","jG_","iE_","jD_","iB_","jA_","iF#",
			"jE_","iC#","jB_","iG#","jF#","iEb","jDb","iBb",
			"jAb","iF_","jEb","iC_","jBb","iG_","jF_","iD_"
		],
		[
			"jC_","iE_","jG_","iB_","jD_","iF#","jA_","iC#",
			"jE_","iG#","jB_","iEb","jGb","iBb","jDb","iF_",
			"jAb","iC_","jEb","iG_","jBb","iD_","jF_","iA_"
		]][0] /* choose one! */
});

