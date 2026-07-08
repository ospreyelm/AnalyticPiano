from music21 import key as m21_key, interval as m21_interval, pitch, scale as m21_scale, roman

# ---------------------------------------------------------------------------
# Key map: HarmonyLab key string → music21 key name
# ---------------------------------------------------------------------------
KEY_MAP = {
    "jC_": "C",  "jG_": "G",  "jD_": "D",  "jA_": "A",  "jE_": "E",  "jB_": "B",
    "jF#": "F#", "jDb": "Db", "jAb": "Ab", "jEb": "Eb", "jBb": "Bb", "jF_": "F",
    "iA_": "a",  "iE_": "e",  "iB_": "b",  "iF#": "f#", "iC#": "c#", "iG#": "g#",
    "iD_": "d",  "iG_": "g",  "iC_": "c",  "iF_": "f",  "iBb": "bb", "iEb": "eb",
}

# ---------------------------------------------------------------------------
# KEY_SPELLING: Python mirror of general.js keyMap spelling arrays.
# Each entry maps pitch class (0–11) → note name string as HarmonyLab renders it.
# Used by spelling_key_for_pitches() to find the right exercise 'key' so that
# enharmonically-sensitive notes (e.g. A# vs Bb) display correctly on the staff.
# ---------------------------------------------------------------------------
KEY_SPELLING = {
    # -- flat keys --
    "jDb": ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","Cb"],
    "jAb": ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"],
    "jEb": ["C","Db","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
    "jBb": ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
    "jF_": ["C","C#","D","Eb","E","F","F#","G","G#","A","Bb","B"],
    # -- natural / no sharps or flats --
    "jC_": ["C","C#","D","D#","E","F","F#","G","G#","A","Bb","B"],
    # -- sharp keys --
    "jG_": ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
    "jD_": ["C","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
    "jA_": ["B#","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
    "jE_": ["B#","C#","D","D#","E","E#","F#","F##","G#","A","A#","B"],
    "jB_": ["B#","C#","C##","D#","E","E#","F#","F##","G#","A","A#","B"],
    "jF#": ["B#","C#","C##","D#","E","E#","F#","F##","G#","G##","A#","B"],
    # -- minor flat keys --
    "iEb": ["C","Db","D","Eb","Fb","F","Gb","G","Ab","A","Bb","Cb"],
    "iBb": ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","Cb"],
    "iF_": ["C","Db","D","Eb","E","F","Gb","G","Ab","A","Bb","B"],
    "iC_": ["C","Db","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
    "iG_": ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"],
    "iD_": ["C","C#","D","Eb","E","F","F#","G","G#","A","Bb","B"],
    # -- minor natural / no accidentals --
    "iA_": ["C","C#","D","D#","E","F","F#","G","G#","A","Bb","B"],
    # -- minor sharp keys --
    "iE_": ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"],
    "iB_": ["C","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
    "iF#": ["B#","C#","D","D#","E","E#","F#","G","G#","A","A#","B"],
    "iC#": ["B#","C#","D","D#","E","E#","F#","F##","G#","A","A#","B"],
    "iG#": ["B#","C#","C##","D#","E","E#","F#","F##","G#","A","A#","B"],
}

# ---------------------------------------------------------------------------
# Chord quality → list of interval strings above root
# ---------------------------------------------------------------------------
QUALITY_INTERVALS = {
    "major":      ["P1", "M3", "P5"],
    "minor":      ["P1", "m3", "P5"],
    "diminished": ["P1", "m3", "d5"],
    "augmented":  ["P1", "M3", "A5"],
    "dominant":   ["P1", "M3", "P5", "m7"],
    "major7":     ["P1", "M3", "P5", "M7"],
    "minor7":     ["P1", "m3", "P5", "m7"],
    "half_dim":   ["P1", "m3", "d5", "m7"],
    "dim7":       ["P1", "m3", "d5", "d7"],
}

# ---------------------------------------------------------------------------
# Identification label definitions
# ---------------------------------------------------------------------------
LABEL_MAP = {
    "triad": {
        "quality": {
            "choices": lambda k: ["major", "minor", "diminished", "augmented"],
            "answer":  lambda quality, inv, k: quality,
        },
        "inversion": {
            "choices": lambda k: ["root position", "third in the bass", "fifth in the bass"],
            "answer":  lambda quality, inv, k: ["root position", "third in the bass", "fifth in the bass"][inv],
        },
    },
    "seventh_chord": {
        "quality": {
            "choices": lambda k: ["dominant 7", "major 7", "minor 7", "half-dim 7", "diminished 7"],
            "answer":  lambda quality, inv, k: {
                "dominant": "dominant 7", "major7": "major 7", "minor7": "minor 7",
                "half_dim": "half-dim 7", "dim7": "diminished 7",
            }.get(quality, quality),
        },
        "inversion": {
            "choices": lambda k: ["root position", "6/5", "4/3", "4/2"],
            "answer":  lambda quality, inv, k: ["root position", "6/5", "4/3", "4/2"][inv],
        },
    },
    "interval": {
        "name": {
            "choices": lambda k: ["m2", "M2", "m3", "M3", "P4", "TT", "P5", "m6", "M6", "m7", "M7", "P8"],
            "answer":  lambda quality, inv, k: quality,
        },
    },
    "diatonic_triads": {
        "roman_numeral": {
            "choices": lambda k: ["I", "ii", "iii", "IV", "V", "vi", "vii°"],
            "answer":  lambda quality, inv, k: quality,
        },
    },
    "diatonic_sevenths": {
        "roman_numeral": {
            "choices": lambda k: ["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "viiø7"],
            "answer":  lambda quality, inv, k: quality,
        },
    },
}

# ---------------------------------------------------------------------------
# Diatonic roman numeral sets
# ---------------------------------------------------------------------------
DIATONIC_TRIADS_MAJOR = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
DIATONIC_TRIADS_MINOR = ["i", "ii°", "III", "iv", "V", "VI", "VII"]

DIATONIC_SEVENTHS_MAJOR = ["Imaj7", "ii7", "iii7", "IVmaj7", "V7", "vi7", "viiø7"]
DIATONIC_SEVENTHS_MINOR = ["i7", "iiø7", "IIImaj7", "iv7", "V7", "VImaj7", "vii°7"]

# ---------------------------------------------------------------------------
# Rule of the Octave chord sequences (roman numerals, ascending & descending)
# Bass walks diatonically; upper voices follow standard ROTO voice leading.
# ---------------------------------------------------------------------------
ROTO_MAJOR_ASC = ["I", "V6/5", "I6", "V6/4/3", "V", "I6/4", "V4/3", "I"]   # sd 1-8
ROTO_MAJOR_DESC = ["I", "V4/2", "I6", "IV6", "V", "IV", "V6", "I"]            # sd 8-1
ROTO_MINOR_ASC  = ["i", "V6/5", "i6", "iv6/4/3", "V", "i6/4", "V4/3", "i"]
ROTO_MINOR_DESC = ["i", "V4/2", "i6", "iv6", "V", "iv", "V6", "i"]

# Simpler, more reliable RN strings for music21 ROTO:
ROTO_MAJOR_ASC_RN  = ["I",    "I6",   "I6",   "IV",   "V",    "I6/4", "VII6", "I"]
ROTO_MAJOR_DESC_RN = ["I",    "V7",   "I6",   "IV6",  "V",    "IV",   "V6",   "I"]
ROTO_MINOR_ASC_RN  = ["i",    "i6",   "i6",   "iv",   "V",    "i6/4", "VII6", "i"]
ROTO_MINOR_DESC_RN = ["i",    "V7",   "i6",   "iv6",  "V",    "iv",   "V6",   "i"]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _m21_key(key_str: str):
    """Return a music21 Key object for the given HarmonyLab key string."""
    return m21_key.Key(KEY_MAP[key_str])


def spelling_key_for_pitches(m21_pitches, prefer_major: bool = True) -> str:
    """
    Given a list of music21 Pitch objects (with enharmonic spelling already set
    by music21 interval/roman logic), return the HarmonyLab key string whose
    keyMap spelling array renders all those pitches with the SAME note names.

    This lets you set exercise 'key' so notes display correctly regardless of
    whether the nominal key of the exercise would give the right spelling.
    Particularly useful for interval exercises with augmented/diminished intervals,
    or for any exercise where you want explicit control over accidentals.

    Usage in the management command:
        chords = mb.interval("jC_", "A6", "matching")
        pitches = mb._get_interval_pitches("jC_", "A6")   # helper below
        ex_key = mb.spelling_key_for_pitches(pitches)      # e.g. "jB_"
        exercise_json["key"] = ex_key
        exercise_json["keySignature"] = ""   # don't show a key signature

    Returns the first key (from a preference-ordered list) where all pitches
    match. Falls back to "jC_" if no perfect match is found.
    """
    # Convert pitch names: music21 uses '-' for flat (e.g. "D-"), keyMap uses 'b'
    def normalize(name: str) -> str:
        return name.replace("-", "b")

    target_spellings = {p.pitchClass: normalize(p.name) for p in m21_pitches}

    # Preference order: fewer accidentals first, major before minor
    preference = [
        "jC_", "jG_", "jF_", "jD_", "jBb", "jA_", "jEb", "jE_", "jAb",
        "jB_", "jDb", "jF#",
        "iA_", "iE_", "iD_", "iG_", "iB_", "iC_", "iF_", "iF#", "iBb",
        "iC#", "iG#", "iEb",
    ]

    for key_str in preference:
        spellings = KEY_SPELLING.get(key_str, [])
        if all(spellings[pc] == name for pc, name in target_spellings.items()):
            return key_str

    return "jC_"   # fallback


def pitches_to_vexflow_spelling(m21_pitches) -> list:
    """
    Convert music21 Pitch objects into VexFlow key strings (``"eb/4"`` form),
    preserving the pitch's recorded enharmonic spelling and octave.

    VexFlow keys are ``<step><accidentals>/<octave>``: lowercase step letter,
    ``b`` for flat (music21's ``-``), ``#`` for sharp, then the octave. Using
    ``Pitch.name`` (not ``Pitch.nameWithOctave``) plus the separate ``.octave``
    attribute avoids any string parsing of the octave boundary — the spelling
    and octave come straight from music21, so the result always carries an
    octave (KTD2: pitch spelling without octave silently corrupts downstream
    bass/interval computation).
    """
    out = []
    for p in m21_pitches:
        name = p.name.replace("-", "b").lower()
        out.append(f"{name}/{p.octave}")
    return out


def chord_notes_key_and_spelling(key_str: str, quality: str, chord_type: str):
    """Return ``(midi_notes, display_key, spelling)`` for a root-position chord.

    Builds the chord on the key's tonic in a 4-voice keyboard voicing, then sorts
    the voiced pitches by MIDI **once** and derives both ``midi_notes`` and
    ``spelling`` from that single ordering (KTD3: sorting the two lists
    independently would risk index misalignment between them). ``display_key``
    is the HarmonyLab key whose keyMap renders these pitches correctly, via
    :func:`spelling_key_for_pitches` — kept for the call site's existing
    ``worksheet_key``/``chord_key`` use.

    ``chord_type`` ("triad"/"seventh_chord") is accepted for call-site parity
    with the prior ``_chord_notes_and_key`` helper but does not change the
    voicing here; both triads and sevenths use the same 4-voice keyboard
    voicing.
    """
    k = _m21_key(key_str)
    pitches = _pitches_for_quality(k.tonic, quality)
    voiced = _keyboard_4voice(pitches, inversion=0)
    ordered = sorted(voiced, key=lambda p: p.midi)
    midi_notes = [p.midi for p in ordered]
    spelling = pitches_to_vexflow_spelling(ordered)
    display_key = spelling_key_for_pitches(voiced)
    return midi_notes, display_key, spelling


def _get_interval_pitches(key_str: str, interval_name: str):
    """
    Return the two music21 Pitch objects for an interval exercise (root + top).
    Exposed so the management command can call spelling_key_for_pitches() on them.
    """
    k = _m21_key(key_str)
    root = k.tonic
    m21_name = "d5" if interval_name == "TT" else interval_name
    top = m21_interval.Interval(m21_name).transposePitch(root)
    return [root, top]


def _pitch_in_range(p: pitch.Pitch, midi_low: int, midi_high: int) -> pitch.Pitch:
    """
    Return a copy of `p` transposed to the nearest octave that falls within
    [midi_low, midi_high].  Raises ValueError if no such octave exists.
    """
    candidate = pitch.Pitch(p.name)          # strip octave info, keep spelling
    # start octave estimate from midi_low
    candidate.octave = (midi_low // 12) - 1  # MIDI 60 → octave 4 (C4=60)
    # step up until we're inside the window
    while candidate.midi < midi_low:
        candidate.octave += 1
    if candidate.midi > midi_high:
        raise ValueError(
            f"No spelling of {p.name} fits in MIDI range {midi_low}–{midi_high}"
        )
    return candidate


def _close_voice(pitches, inversion: int = 0):
    """
    Close voicing: all notes stacked tightly starting near MIDI 60.
    Returns list of pitch.Pitch objects.
    """
    rotated = list(pitches[inversion:]) + list(pitches[:inversion])
    bass = _pitch_in_range(rotated[0], 60, 71)
    notes = [bass]
    for p in rotated[1:]:
        note = _pitch_in_range(p, notes[-1].midi + 1, notes[-1].midi + 12)
        notes.append(note)
    return notes


def _keyboard_4voice(pitches, inversion: int = 0):
    """
    Keyboard voicing: bass in bass clef (MIDI 45–57), upper voices in
    treble clef (MIDI 60–76) close together.  For triads, doubles the root
    in the soprano.
    Returns list of pitch.Pitch objects.
    """
    root_pitch = pitches[0]
    rotated = list(pitches[inversion:]) + list(pitches[:inversion])
    bass = _pitch_in_range(rotated[0], 45, 57)

    upper = []
    prev_midi = 59
    for p in rotated[1:]:
        note = _pitch_in_range(p, prev_midi + 1, prev_midi + 12)
        upper.append(note)
        prev_midi = note.midi

    # For triads (3 distinct pitch classes) double the root in soprano
    if len(pitches) == 3:
        soprano = _pitch_in_range(root_pitch, prev_midi + 1, prev_midi + 12)
        upper.append(soprano)

    return [bass] + upper


def _voice(pitches, inversion: int, voicing_name: str):
    """Dispatch to the correct voicing strategy."""
    if voicing_name == "keyboard_4voice":
        return _keyboard_4voice(pitches, inversion)
    return _close_voice(pitches, inversion)


def _pitches_for_quality(root_pitch: pitch.Pitch, quality: str):
    """
    Build a list of pitch.Pitch objects for a chord quality rooted on
    root_pitch, using music21 intervals for correct enharmonic spelling.
    """
    ivl_names = QUALITY_INTERVALS.get(quality)
    if ivl_names is None:
        raise ValueError(f"Unknown quality: {quality!r}")
    return [m21_interval.Interval(ivl).transposePitch(root_pitch) for ivl in ivl_names]


def _pitches_from_rn(rn_str: str, k) -> list:
    """
    Return the pitches of a RomanNumeral as a list of pitch.Pitch.
    music21's roman module handles enharmonic spelling relative to the key.
    """
    rn = roman.RomanNumeral(rn_str, k)
    return list(rn.pitches)


def _apply_visibility(midi_notes: list, exercise_type: str):
    """Split midi_notes into (visible, hidden) based on exercise type."""
    if exercise_type in ("matching", "identification"):
        return midi_notes, []
    elif exercise_type == "analytical":
        return [], midi_notes
    elif exercise_type in ("figured_bass", "figured_bass_pcs"):
        return [midi_notes[0]], midi_notes[1:]
    return midi_notes, []


def _chord_dict(
    midi_notes: list,
    rhythm_value: str,
    exercise_type: str,
    identification_label: str = None,
    key_str: str = None,
    quality: str = None,
    inversion: int = 0,
    exercise_category: str = None,
    rn_answer: str = None,
) -> dict:
    """
    Build a single chord dict in the format expected by Exercise.data["chord"].
    """
    visible, hidden = _apply_visibility(sorted(midi_notes), exercise_type)
    d = {"visible": visible, "hidden": hidden, "rhythmValue": rhythm_value}

    if (
        exercise_type == "identification"
        and identification_label
        and exercise_category in LABEL_MAP
    ):
        label_info = LABEL_MAP[exercise_category].get(identification_label)
        if label_info:
            d["choices"] = label_info["choices"](key_str)
            if exercise_category in ("triad", "seventh_chord"):
                d["answer"] = label_info["answer"](quality, inversion, key_str)
            elif exercise_category == "interval":
                d["answer"] = label_info["answer"](quality, inversion, key_str)
            elif rn_answer is not None:
                d["answer"] = label_info["answer"](rn_answer, inversion, key_str)

    return d


# ---------------------------------------------------------------------------
# Public API — same signatures as the old templates.py
# ---------------------------------------------------------------------------

def triad(key_str, quality, inversion, voicing_name, exercise_type,
          identification_label=None):
    """
    Single triad.
    Returns [{"visible": [...], "hidden": [...], "rhythmValue": "w"}].
    """
    k = _m21_key(key_str)
    pitches = _pitches_for_quality(k.tonic, quality)
    voiced = _voice(pitches, inversion, voicing_name)
    midi_notes = [p.midi for p in voiced]
    return [_chord_dict(
        midi_notes, "w", exercise_type,
        identification_label, key_str, quality, inversion, "triad",
    )]


def seventh_chord(key_str, quality, inversion, voicing_name, exercise_type,
                  identification_label=None):
    """
    Single seventh chord.
    Returns [{"visible": [...], "hidden": [...], "rhythmValue": "w"}].
    """
    k = _m21_key(key_str)
    pitches = _pitches_for_quality(k.tonic, quality)
    voiced = _voice(pitches, inversion, voicing_name)
    midi_notes = [p.midi for p in voiced]
    return [_chord_dict(
        midi_notes, "w", exercise_type,
        identification_label, key_str, quality, inversion, "seventh_chord",
    )]


def interval(key_str, interval_name, exercise_type, identification_label=None):
    """
    Single harmonic interval from the tonic.
    Returns [{"visible": [bottom_midi, top_midi], "hidden": [], "rhythmValue": "h"}].

    Accepts any music21 interval name: "m2","M2","m3","M3","P4","d5"/"TT","P5",
    "m6","M6","m7","M7","P8", and augmented/diminished variants like "A2","A3",
    "A4","A5","A6","d3","d4","d7" etc.

    NOTE — enharmonic display constraint: HarmonyLab's frontend uses a 12-element
    keyMap (general.js) that assigns ONE spelling per pitch class per key. MIDI
    numbers carry no spelling information. So augmented intervals will only display
    with the expected accidental if the active key's keyMap happens to spell that
    pitch class accordingly. For example, a C→A# (A6) in key jC_ will render as
    C→Bb (m7) because jC_ spells PC 10 as "Bb". Augmented intervals intended to
    display correctly should be used only in keys where the target pitch class is
    spelled as desired, or paired with a custom key context that spells it that way.
    """
    k = _m21_key(key_str)
    root = k.tonic

    # "TT" (tritone) → diminished fifth for enharmonic-correct music21 spelling
    m21_name = "d5" if interval_name == "TT" else interval_name

    top = m21_interval.Interval(m21_name).transposePitch(root)
    p1 = _pitch_in_range(root, 60, 71)
    p2 = _pitch_in_range(top, p1.midi + 1, p1.midi + 12)

    return [_chord_dict(
        [p1.midi, p2.midi], "h", exercise_type,
        identification_label, key_str, interval_name, 0, "interval",
    )]


def diatonic_intervals(key_str, scale_type, exercise_type,
                       identification_label=None):
    """
    All 7 diatonic intervals above the tonic (M2 through P8).
    Returns list of 7 chord dicts.
    """
    k = _m21_key(key_str)
    if scale_type == "major" or key_str.startswith("j"):
        sc = m21_scale.MajorScale(k.tonic)
    else:
        sc = m21_scale.NaturalMinorScale(k.tonic)

    # sc.pitches returns 8 pitches: root through octave (inclusive)
    all_pitches = sc.pitches   # e.g. [C4, D4, E4, F4, G4, A4, B4, C5]
    root = _pitch_in_range(k.tonic, 60, 71)
    chords = []
    # Intervals: 2nd through octave = indices 1–7 (7 intervals total)
    for sp in all_pitches[1:]:
        top = _pitch_in_range(sp, root.midi + 1, root.midi + 12)
        chords.append(_chord_dict([root.midi, top.midi], "h", exercise_type))
    return chords


def scale(key_str, scale_type, direction, exercise_type):
    """
    Scale as one note per chord dict.
    Returns list of 8 chord dicts (root to octave).
    """
    k = _m21_key(key_str)
    if scale_type == "major":
        sc = m21_scale.MajorScale(k.tonic)
    elif scale_type in ("harmonic_minor", "harmonic"):
        sc = m21_scale.HarmonicMinorScale(k.tonic)
    elif scale_type in ("melodic_minor", "melodic"):
        sc = m21_scale.MelodicMinorScale(k.tonic)
    else:
        sc = m21_scale.NaturalMinorScale(k.tonic)

    # sc.pitches gives 8 pitches: root to octave inclusive
    pitches = list(sc.pitches)   # 8 notes already

    if direction in ("descending", "desc"):
        pitches = list(reversed(pitches))

    chords = []
    for p in pitches:
        placed = _pitch_in_range(p, 60, 72)
        chords.append(_chord_dict([placed.midi], "q", exercise_type))
    return chords


def diatonic_triads(key_str, scale_type, exercise_type,
                    identification_label=None):
    """
    All 7 diatonic triads in keyboard_4voice voicing.
    Returns list of 7 chord dicts.
    """
    k = _m21_key(key_str)
    is_major = key_str.startswith("j")
    rn_list = DIATONIC_TRIADS_MAJOR if is_major else DIATONIC_TRIADS_MINOR
    chords = []
    for rn_str in rn_list:
        pitches = _pitches_from_rn(rn_str, k)
        voiced = _keyboard_4voice(pitches, 0)
        midi_notes = [p.midi for p in voiced]
        chords.append(_chord_dict(
            midi_notes, "w", exercise_type,
            identification_label, key_str, None, 0,
            "diatonic_triads", rn_str,
        ))
    return chords


def diatonic_sevenths(key_str, scale_type, exercise_type,
                      identification_label=None):
    """
    All 7 diatonic seventh chords in keyboard_4voice voicing.
    Returns list of 7 chord dicts.
    """
    k = _m21_key(key_str)
    is_major = key_str.startswith("j")
    rn_list = DIATONIC_SEVENTHS_MAJOR if is_major else DIATONIC_SEVENTHS_MINOR
    chords = []
    for rn_str in rn_list:
        pitches = _pitches_from_rn(rn_str, k)
        voiced = _keyboard_4voice(pitches, 0)
        midi_notes = [p.midi for p in voiced]
        chords.append(_chord_dict(
            midi_notes, "w", exercise_type,
            identification_label, key_str, None, 0,
            "diatonic_sevenths", rn_str,
        ))
    return chords


def roto(key_str, scale_type, direction, exercise_type):
    """
    Rule of the Octave: bass walks the scale, upper voices follow ROTO.
    Returns list of 8 chord dicts.
    """
    k = _m21_key(key_str)
    is_major = key_str.startswith("j")

    if is_major:
        rn_list = ROTO_MAJOR_ASC_RN if direction in ("ascending", "asc") else ROTO_MAJOR_DESC_RN
    else:
        rn_list = ROTO_MINOR_ASC_RN if direction in ("ascending", "asc") else ROTO_MINOR_DESC_RN

    chords = []
    for rn_str in rn_list:
        pitches = _pitches_from_rn(rn_str, k)
        voiced = _keyboard_4voice(pitches, 0)
        midi_notes = [p.midi for p in voiced]
        chords.append(_chord_dict(midi_notes, "h", exercise_type))
    return chords


def progression(key_str, rn_list, exercise_type):
    """
    Chord progression expressed as roman numeral strings.
    Returns list of chord dicts, one per roman numeral.
    """
    k = _m21_key(key_str)
    chords = []
    for rn_str in rn_list:
        pitches = _pitches_from_rn(rn_str, k)
        voiced = _keyboard_4voice(pitches, 0)
        midi_notes = [p.midi for p in voiced]
        chords.append(_chord_dict(midi_notes, "w", exercise_type))
    return chords
