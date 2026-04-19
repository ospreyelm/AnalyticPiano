"""
Utility to rebuild music21 Score objects from exercise JSON data.

Used by backfill_skill_tags and other analysis operations that need
to convert stored exercise data back into analyzable music21 objects.
"""

from music21 import stream, note, chord, meter, key, instrument, metadata as m21_metadata


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
    key_sig = meta.get('key', 'C')
    ts_str = meta.get('time_signature', '4/4')

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

                for item in items:
                    kind = item.get('kind', 'note')
                    dur = item.get('duration', {})
                    dur_type = dur.get('type', 'q')  # quarter default
                    dots = dur.get('dots', 0)

                    # Convert to quarter lengths
                    base_ql = _dur_to_quarter_length(dur_type)
                    if dots:
                        base_ql *= (2 - (0.5 ** dots))

                    if kind == 'rest':
                        r = note.Rest(quarterLength=base_ql)
                        part.append(r)
                    elif kind == 'note':
                        pitch_data = item.get('pitch', {})
                        midi = _pitch_to_midi(pitch_data)
                        n = note.Note(midi=midi, quarterLength=base_ql)
                        part.append(n)
                    elif kind == 'chord':
                        pitches = item.get('pitches', [])
                        midis = [_pitch_to_midi(p) for p in pitches]
                        c = chord.Chord(midis, quarterLength=base_ql)
                        part.append(c)

    # Add all parts to score
    for part in parts_by_staff.values():
        score.append(part)

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
