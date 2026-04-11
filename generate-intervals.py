import json
from music21 import pitch, interval

def generate_midi_interval_map(start_midi=48, end_midi=72):
    # Defining names to ensure we catch naturals, sharps, and flats
    # music21 will handle the logic of which one to use for the interval name
    pitch_names = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B']
    
    # Collect all valid pitch objects within our MIDI range
    valid_pitches = []
    for octave in range(2, 7):  # Wide octave range to ensure we find all MIDI 48-72
        for name in pitch_names:
            p = pitch.Pitch(f"{name}{octave}")
            if start_midi <= p.ps <= end_midi:
                valid_pitches.append(p)

    interval_data = {}

    for p1 in valid_pitches:
        # We use nameWithOctave as the key (e.g., "C4", "C#4")
        p1_key = p1.nameWithOctave
        if p1_key not in interval_data:
            interval_data[p1_key] = []
        
        for p2 in valid_pitches:
            # Calculate interval
            iv = interval.Interval(noteStart=p1, noteEnd=p2)
            
            # Appending data for every possible pairing
            interval_data[p1_key].append({
                "to_pitch": p2.nameWithOctave,
                "midi_to": int(p2.ps),
                "interval_nice_name": iv.niceName,      # "Augmented Fourth"
                "interval_short_name": iv.name,         # "A4"
                "semitones": int(iv.semitones),
                "is_enharmonic": p1.ps == p2.ps and p1.name != p2.name
            })

    return interval_data

# Execute and export
midi_range_data = generate_midi_interval_map(48, 72)

with open('midi_intervals_48_72.json', 'w', encoding='utf-8') as f:
    json.dump(midi_range_data, f, indent=4)

print(f"Generated interval map for {len(midi_range_data)} distinct pitch names.")