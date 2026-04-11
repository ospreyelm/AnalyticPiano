import random
from music21 import stream, note, interval, pitch, metadata

def generate_interval_xml(n=15, mode='all', output_file='intervals.musicxml'):
    """
    Generates a MusicXML file with n intervals.
    Modes: 'perfect', 'diatonic' (P, M, m), 'all'
    """
    # 1. Setup Pitch Range (MIDI 48-72)
    pitch_names = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B']
    valid_pitches = []
    for octave in range(3, 6): 
        for name in pitch_names:
            p = pitch.Pitch(f"{name}{octave}")
            if 48 <= p.ps <= 72:
                valid_pitches.append(p)

    # 2. Define Quality Filters
    # music21 interval names: P=Perfect, M=Major, m=minor, a=Augmented, d=Diminished
    if mode == 'perfect':
        allowed_qualities = ['P']
    elif mode == 'diatonic':
        allowed_qualities = ['P', 'M', 'm']
    else:
        allowed_qualities = ['P', 'M', 'm', 'A', 'd'] # All

    # 3. Create the MusicXML Stream
    score = stream.Score()
    part = stream.Part()
    score.insert(0, metadata.Metadata())
    score.metadata.title = f"Interval Exercise: {mode.capitalize()}"

    count = 0
    attempts = 0
    max_attempts = n * 50 # Prevent infinite loops if filter is too strict

    while count < n and attempts < max_attempts:
        p1 = random.choice(valid_pitches)
        p2 = random.choice(valid_pitches)
        
        iv = interval.Interval(noteStart=p1, noteEnd=p2)
        
        # Check if the interval quality matches our filter
        # .semiSimpleName usually returns something like 'P5' or 'm3'
        quality = iv.name[0] 
        
        if quality in allowed_qualities:
            # Create notes as a melodic interval (one after the other)
            # You could also use a Chord([p1, p2]) for harmonic intervals
            n1 = note.Note(p1)
            n2 = note.Note(p2)
            n1.quarterLength = 1.0
            n2.quarterLength = 1.0
            
            # Add a lyric to the second note identifying the interval for reference
            n2.lyric = iv.name
            
            part.append(n1)
            part.append(n2)
            
            # Add a rest between pairs for clarity
            part.append(note.Rest(quarterLength=1.0))
            
            count += 1
        attempts += 1

    score.append(part)
    
    # 4. Write to file
    score.write('musicxml', fp=output_file)
    print(f"Successfully generated {count} intervals in '{output_file}' using mode: {mode}")

# --- Examples of use ---

# 1. All intervals (Default)
generate_interval_xml(n=15, mode='all', output_file='all_intervals.musicxml')

# 2. Perfect intervals only (P1, P4, P5, P8)
# generate_interval_xml(n=10, mode='perfect', output_file='perfect_only.musicxml')

# 3. Major, Minor, and Perfect
# generate_interval_xml(n=20, mode='diatonic', output_file='diatonic_exercise.musicxml')