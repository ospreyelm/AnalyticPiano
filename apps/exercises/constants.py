sig_to_pc = {
    "bbbbbbb": 11,
    "bbbbbb": 6,
    "bbbbb": 1,
    "bbbb": 8,
    "bbb": 3,
    "bb": 10,
    "b": 5,
    "": 0,
    "#": 7,
    "##": 2,
    "###": 9,
    "####": 4,
    "#####": 11,
    "######": 6,
    "#######": 1
}

pseudo_key_to_sig = {
    "ab": "bbbbbbb",
    "Cb": "bbbbbbb",
    "eb": "bbbbbb",
    "Gb": "bbbbbb",
    "bb": "bbbbb",
    "Db": "bbbbb",
    "f": "bbbb",
    "Ab": "bbbb",
    "c": "bbb",
    "Eb": "bbb",
    "g": "bb",
    "Bb": "bb",
    "d": "b",
    "F": "b",
    "a": "",
    "C": "",
    "e": "#",
    "G": "#",
    "b": "##",
    "D": "##",
    "f#": "###",
    "A": "###",
    "c#": "####",
    "E": "####",
    "g#": "#####",
    "B": "#####",
    "d#": "######",
    "F#": "######",
    "a#": "#######",
    "C#": "#######"
}

all_sigs = [
    "bbbbbbb",
    "bbbbbb",
    "bbbbb",
    "bbbb",
    "bbb",
    "bb",
    "b",
    "",
    "#",
    "##",
    "###",
    "####",
    "#####",
    "######",
    "#######"
]

all_keys = [
    # encoding must match keyMap in general.js
    "iAb", "jCb",
    "iEb", "jGb",
    "iBb", "jDb",
    "iF_", "jAb",
    "iC_", "jEb",
    "iG_", "jBb",
    "iD_", "jF_",
    "iA_", "jC_",
    "iE_", "jG_",
    "iB_", "jD_",
    "iF#", "jA_",
    "iC#", "jE_",
    "iG#", "jB_",
    "iD#", "jF#",
    "iA#", "jC#"
]

KEY_SIGNATURES = list(pseudo_key_to_sig.keys())
SIGNATURE_CHOICES = tuple(zip(KEY_SIGNATURES, KEY_SIGNATURES))
