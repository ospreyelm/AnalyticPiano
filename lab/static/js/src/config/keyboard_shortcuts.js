define({
	// Application note on/off keyboard shortcuts.

	// Maps a key to an integer relative to the C *one octave below* 
	// middle C (MIDI note number 48).
	//
	// To find the MIDI note number that will be output when a key is pressed,
	// add the relative offset from the note mapping section to this note anchor.
	"noteAnchor": 0,
	
	// Uused letters to avoid mishaps: 3, 6, and g.
	"keyMap": {
		"GRAVE":  {msg:"toggleNote", data:43}, // G
		"1":      {msg:"toggleNote", data:44}, // GA
		"q":      {msg:"toggleNote", data:45}, // A
		"2":      {msg:"toggleNote", data:46}, // AB
		"w":      {msg:"toggleNote", data:47}, // B
		"e":      {msg:"toggleNote", data:48}, // C3
		"4":      {msg:"toggleNote", data:49}, // CD
		"r":      {msg:"toggleNote", data:50}, // D
		"5":      {msg:"toggleNote", data:51}, // DE
		"t":      {msg:"toggleNote", data:52}, // E
		"y":      {msg:"toggleNote", data:53}, // F
		"7":      {msg:"toggleNote", data:54}, // FG
		"u":      {msg:"toggleNote", data:55}, // G
		"8":      {msg:"toggleNote", data:56}, // GA
		"i":      {msg:"toggleNote", data:57}, // A
		"9":      {msg:"toggleNote", data:58}, // AB
		"o":      {msg:"toggleNote", data:59}, // B
		"p":      {msg:"toggleNote", data:60}, // C4
		"-":      {msg:"toggleNote", data:61}, // CD
		"[":      {msg:"toggleNote", data:62}, // D
		"=":      {msg:"toggleNote", data:63}, // DE
		"]":      {msg:"toggleNote", data:64}, // E
		"z":      {msg:"toggleNote", data:65}, // F
		"s":      {msg:"toggleNote", data:66}, // FG
		"x":      {msg:"toggleNote", data:67}, // G
		"d":      {msg:"toggleNote", data:68}, // GA
		"c":      {msg:"toggleNote", data:69}, // A
		"f":      {msg:"toggleNote", data:70}, // AB
		"v":      {msg:"toggleNote", data:71}, // B
		"b":      {msg:"toggleNote", data:72}, // C5
		"h":      {msg:"toggleNote", data:73}, // CD
		"n":      {msg:"toggleNote", data:74}, // D
		"j":      {msg:"toggleNote", data:75}, // DE
		"m":      {msg:"toggleNote", data:76}, // E
		",":      {msg:"toggleNote", data:77}, // F
		"'":      {msg:"depressSustain"},
		";":      {msg:"retakeSustain"},
		"l":      {msg:"releaseSustain"},
		"DOWN":   {msg:"rotateKeyFlatward"},
		"UP":     {msg:"rotateKeySharpward"},
		"RIGHT":  {msg:"setKeyToC"},
		"LEFT":   {msg:"setKeyToNone"},  
		"BACKSL": {msg:"toggleMetronome"},
		"ESC":    {msg:"toggleMode"},
		"BACKSP": {msg:"clearNotes"},
		"SPACE":  {msg:"bankChord"},
		"ENTER":  {msg:"bankChord"},
		// "/":      {msg:"toggleAnalysis"}, // not created yet
		// "":       {msg:"advanceExercise"} // not connected yet 
	},

	// Defines javascript key code -> key name mappings.
	// This is not intended to be comprehensive. These key names
	// should be used in the note and control shortcut mappings.
	"keyCode": {
		"8": "BACKSP",
		"13": "ENTER",
		"27": "ESC",
		"32": "SPACE",
		"37": "LEFT",
		"38": "UP",
		"39": "RIGHT",
		"40": "DOWN",
		"48": "0",
		"49": "1",
		"50": "2",
		"51": "3",
		"52": "4",
		"53": "5",
		"54": "6",
		"55": "7",
		"56": "8",
		"57": "9",
		"65": "a",
		"66": "b",
		"67": "c",
		"68": "d",
		"69": "e",
		"70": "f",
		"71": "g",
		"72": "h",
		"73": "i",
		"74": "j",
		"75": "k",
		"76": "l",
		"77": "m",
		"78": "n",
		"79": "o",
		"80": "p",
		"81": "q",
		"82": "r",
		"83": "s",
		"84": "t",
		"85": "u",
		"86": "v",
		"87": "w",
		"88": "x",
		"89": "y",
		"90": "z",
		"186": ";",
		"187": "=",
		"188": ",",
		"189": "-",
		"190": ".",
		"191": "/",
		"192": "GRAVE",
		"219": "[",
		"220": "BACKSL",
		"221": "]",
		"222": "'"
	}
});
