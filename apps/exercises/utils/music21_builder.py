"""
Utility to rebuild music21 Score objects from exercise JSON data.

Used by backfill_skill_tags and other analysis operations that need
to convert stored exercise data back into analyzable music21 objects.
"""

try:
    from music21 import stream, note, chord, meter, key, instrument, metadata as m21_metadata
    _MUSIC21_AVAILABLE = True
except ImportError:
    _MUSIC21_AVAILABLE = False

from apps.exercises.utils.key_normalization import harmony_key_to_music21


def _serialize_key_name(k_obj):
    tonic = k_obj.tonic.name.replace("-", "b")
    mode = (getattr(k_obj, "mode", "") or "").lower()
    if mode.startswith("minor"):
        return f"{tonic}m"
    return tonic


def build_score_from_data(exercise_data):
    """
    Convert exercise JSON data back into a music21 Score object.

    Args:
        exercise_data: dict containing 'score' key with CIR format
                      (Canonical Internal Representation):
                      {
                        'meta': {'key': 'C', 'time_signature': '4/4'},
                        'measures': [...]
                      }

    Returns:
        music21.stream.Score object ready for analysis
    """

    # Extract score structure
    score_data = exercise_data.get('score', {})
    meta = score_data.get('meta', {})
    measures = score_data.get('measures', [])

    if not measures:
        raise ValueError("No measures found in exercise data")

    # Create root score
    score = stream.Score()

    # Set metadata
    # Normalize now so future music21 key insertion cannot receive HarmonyLab's
    # `j...` / `i...` pseudo-key tokens.
    key_sig = harmony_key_to_music21(meta.get('key', 'C'))
    ts_str = meta.get('time_signature') or meta.get('time') or '4/4'

    # Get staves from first measure to determine structure
    first_measure = measures[0]
    staves = first_measure.get('staves', {})

    # Create parts for each staff (treble, bass, etc.)
    parts_by_staff = {}

    for staff_name in ['treble', 'bass']:
        if staff_name in staves:
            part = stream.Part()
            part.id = staff_name

            # Add instrument
            if staff_name == 'treble':
                part.append(instrument.Soprano())
            else:
                part.append(instrument.Bass())

            parts_by_staff[staff_name] = part

    # Build measures
    for measure_idx, measure_data in enumerate(measures):
        staves_in_measure = measure_data.get('staves', {})

        for staff_name, staff_data in staves_in_measure.items():
            if staff_name not in parts_by_staff:
                continue

            part = parts_by_staff[staff_name]
            voices = staff_data.get('voices', [])

            # Merge all voices in this measure into single timeline
            # (music21 doesn't require separate voice objects for analysis)
            for voice_idx, voice_data in enumerate(voices):
                items = voice_data.get('items', [])
                current_offset = 0.0 # offset WITHIN the measure

                for item in items:
                    kind = item.get('kind', 'note')
                    dur = item.get('duration', {})
                    dur_type = dur.get('type', 'q')  # quarter default
                    dots = dur.get('dots', 0)

                    # Convert to quarter lengths
                    base_ql = _dur_to_quarter_length(dur_type)
                    if dots:
                        base_ql *= (2 - (0.5 ** dots))

                    el = None
                    if kind == 'rest':
                        el = note.Rest(quarterLength=base_ql)
                    elif kind == 'note':
                        pitch_data = item.get('pitch', {})
                        midi = _pitch_to_midi(pitch_data)
                        el = note.Note(midi=midi, quarterLength=base_ql)
                    elif kind == 'chord':
                        pitches = item.get('pitches')
                        if pitches is None:
                            notes = item.get('notes', [])
                            pitches = [n.get('pitch') for n in notes if n.get('pitch')]
                        midis = [_pitch_to_midi(p) for p in pitches]
                        el = chord.Chord(midis, quarterLength=base_ql)
                    
                    if el:
                        # Insert at correct absolute offset (measure_idx * num_beats + current_offset)
                        # Actually, music21 Part.append() in a measure loop is tricky.
                        # It's better to insert into the PART at the absolute offset.
                        # We need num_beats (default 4.0)
                        num_beats = 4.0
                        try:
                            ts = meta.get('time_signature') or meta.get('time') or '4/4'
                            _n, _d = map(int, ts.split('/'))
                            num_beats = _n * (4.0 / _d)  # quarter-lengths per measure
                        except Exception:
                            pass
                        
                        part.insert(measure_idx * num_beats + current_offset, el)
                        current_offset += base_ql

    # Add all parts to score
    for part in parts_by_staff.values():
        score.insert(0.0, part)

    return score


def _dur_to_quarter_length(dur_type):
    """Convert duration type string to quarter length."""
    mapping = {
        'w': 4.0,      # whole
        'h': 2.0,      # half
        'q': 1.0,      # quarter
        '8': 0.5,      # eighth
        '16': 0.25,    # sixteenth
        '32': 0.125,   # thirty-second
    }
    return mapping.get(dur_type, 1.0)


def _pitch_to_midi(pitch_data):
    """Convert CIR pitch dict to MIDI number."""
    step = pitch_data.get('step', 'C')
    alter = pitch_data.get('alter', 0)  # -1=flat, 0=natural, 1=sharp
    octave = pitch_data.get('octave', 4)

    # C4 = MIDI 60
    step_semitones = {
        'C': 0, 'D': 2, 'E': 4, 'F': 5,
        'G': 7, 'A': 9, 'B': 11
    }

    semitone = step_semitones.get(step, 0)
    midi = (octave + 1) * 12 + semitone + alter
    return midi


DUR_TO_TYPE = {
    4.0: ("w", 0),
    3.0: ("h", 1),
    2.0: ("h", 0),
    1.5: ("q", 1),
    1.0: ("q", 0),
    0.75: ("8", 1),
    0.5: ("8", 0),
    0.375: ("16", 1),
    0.25: ("16", 0),
    0.125: ("32", 0),
}


def _ql_to_duration(quarter_length):
    ql = round(float(quarter_length), 5)
    if ql in DUR_TO_TYPE:
        t, d = DUR_TO_TYPE[ql]
        return {"type": t, "dots": d}
    # conservative fallback
    return {"type": "q", "dots": 0}


def _pitch_to_cir(p, diatonic_alters=None):
    alter = 0
    if p.accidental is not None and p.accidental.alter is not None:
        alter = int(p.accidental.alter)
    data = {
        "step": p.step,
        "alter": alter,
        "octave": int(p.octave),
    }
    if diatonic_alters is not None:
        data["is_diatonic"] = (diatonic_alters.get(p.step) == alter)
    return data


def _element_to_item(el, diatonic_alters=None):
    if isinstance(el, note.Rest):
        return {"kind": "rest", "duration": _ql_to_duration(el.quarterLength)}
    if isinstance(el, note.Note):
        return {
            "kind": "note",
            "pitch": _pitch_to_cir(el.pitch, diatonic_alters),
            "duration": _ql_to_duration(el.quarterLength),
        }
    if isinstance(el, chord.Chord):
        return {
            "kind": "chord",
            "pitches": [_pitch_to_cir(p, diatonic_alters) for p in el.pitches],
            "duration": _ql_to_duration(el.quarterLength),
        }
    return None


def score_to_cir(score):
    parts = list(score.parts)
    if len(parts) < 4:
        raise ValueError("Expected SATB score with 4 parts")

    part_map = {
        "soprano": parts[0],
        "alto": parts[1],
        "tenor": parts[2],
        "bass": parts[3],
    }

    ts = score.recurse().getElementsByClass(meter.TimeSignature).first()
    ks = score.recurse().getElementsByClass(key.Key).first()
    if ks is None:
        ks_sig = score.recurse().getElementsByClass(key.KeySignature).first()
        k_obj = ks_sig.asKey() if ks_sig else key.Key("C")
    else:
        k_obj = ks
    key_name = _serialize_key_name(k_obj)

    diatonic_alters = {p.step: p.alter for p in k_obj.pitches}

    measures_by_part = {
        name: list(part.getElementsByClass(stream.Measure))
        for name, part in part_map.items()
    }
    measure_count = max(len(m) for m in measures_by_part.values())

    out_measures = []
    for idx in range(measure_count):
        treble_voices = []
        bass_voices = []

        for voice_name in ["soprano", "alto"]:
            items = []
            voice_measures = measures_by_part[voice_name]
            if idx < len(voice_measures):
                for el in voice_measures[idx].notesAndRests:
                    item = _element_to_item(el, diatonic_alters)
                    if item is not None:
                        items.append(item)
            treble_voices.append({"items": items})

        for voice_name in ["tenor", "bass"]:
            items = []
            voice_measures = measures_by_part[voice_name]
            if idx < len(voice_measures):
                for el in voice_measures[idx].notesAndRests:
                    item = _element_to_item(el, diatonic_alters)
                    if item is not None:
                        items.append(item)
            bass_voices.append({"items": items})

        out_measures.append(
            {
                "number": idx + 1,
                "staves": {
                    "treble": {"voices": treble_voices},
                    "bass": {"voices": bass_voices},
                },
            }
        )

    return {
        "meta": {
            "key": key_name,
            "time": str(ts.ratioString if ts else "4/4"),
        },
        "measures": out_measures,
    }
