// First character of input should be mod-12 element (0123456789yz) where 0 = pc of keynote.
// Second character of input should be mod-7 element (klmnopq) where k = note-name class of keynote.

/* global define: false */
define({
	"0k": {"numeral": "1", "solfege": "La", "do_based_solfege": "Do"},
	"1l": {"numeral": "b2", "solfege": "Te", "do_based_solfege": "Ra"},
	"2l": {"numeral": "2", "solfege": "Ti", "do_based_solfege": "Re"},
	"3m": {"numeral": "3", "solfege": "Do", "do_based_solfege": "Me"},
	"4m": {"numeral": "#3", "solfege": "Di", "do_based_solfege": "Mi"},
	"5n": {"numeral": "4", "solfege": "Re", "do_based_solfege": "Fa"},
	"6n": {"numeral": "#4", "solfege": "Ri", "do_based_solfege": "Fi"},
	"6o": {"numeral": "b5", "solfege": "Me", "do_based_solfege": "Se"},
	"7o": {"numeral": "5", "solfege": "Mi", "do_based_solfege": "So"},
	"8p": {"numeral": "6", "solfege": "Fa", "do_based_solfege": "Le"},
	"9p": {"numeral": "#6", "solfege": "Fi", "do_based_solfege": "La"},
	"yq": {"numeral": "7", "solfege": "So", "do_based_solfege": "Te"},
	"zq": {"numeral": "#7", "solfege": "Si", "do_based_solfege": "Ti"}
});
