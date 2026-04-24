from django.utils.safestring import mark_safe

def get_ticks(dur_type, dots=0):
    base = {
        'w': 4096, 'whole': 4096, '1': 4096,
        'h': 2048, 'half': 2048, '2': 2048,
        'q': 1024, 'quarter': 1024, '4': 1024,
        '8': 512, 'eighth': 512, 'e': 512,
        '16': 256, '16th': 256, 's': 256,
        '32': 128, '32nd': 128, 't': 128,
        'W': 6144, 'H': 3072, 'Q': 1536, 'E': 768
    }.get(dur_type, 1024)
    
    total = base
    add = base / 2
    for _ in range(dots):
        total += add
        add /= 2
    return int(total)

def parse_time_sig(time_sig):
    if not time_sig: return 4096
    try:
        num, den = map(int, str(time_sig).split('/'))
        return int(num * (4096 / den))
    except:
        return 4096

def generate_abc_preview(exercise):
    data = exercise.data
    if not data:
        return "No data"
    
    # Exhaustive search for voices
    voices = data.get("voices")
    if not voices and isinstance(data.get("score"), dict):
        voices = data["score"].get("voices")
        if not voices and isinstance(data["score"].get("umto"), dict):
            voices = data["score"]["umto"].get("voices")
    if not voices and isinstance(data.get("umto"), dict):
        voices = data["umto"].get("voices")
        
    # Exhaustive search for metadata
    metadata = data.get("metadata") or {}
    if not metadata and isinstance(data.get("score"), dict):
        metadata = data["score"].get("meta") or data["score"].get("metadata") or {}
        if not metadata and isinstance(data["score"].get("umto"), dict):
            metadata = data["score"]["umto"].get("metadata") or data["score"]["umto"].get("meta") or {}
    if not metadata and isinstance(data.get("umto"), dict):
        metadata = data["umto"].get("metadata") or data["umto"].get("meta") or {}
    
    if voices:
        time_sig = metadata.get("time") or metadata.get("meter") or data.get("timeSignature") or data.get("meter") or "4/4"
        measure_ticks = parse_time_sig(time_sig)
        
        output = []
        voice_labels = [('S', 'Soprano'), ('A', 'Alto'), ('T', 'Tenor'), ('B', 'Bass')]
        
        for vk, label in voice_labels:
            voice_items = voices.get(vk, [])
            if not voice_items:
                output.append(f"<strong>{label}</strong>: None (empty for this exercise)")
                continue
            
            pitches_out = []
            rhythms_out = []
            current_ticks = 0
            
            for item in voice_items:
                # Handle Pitch
                p = item.get("pitch")
                if not p:
                    kind = item.get("kind")
                    p_str = "R" if kind == "rest" else "?"
                else:
                    step = p.get("step", "C")
                    alter = p.get("alteration") or p.get("alter", 0)
                    octave = p.get("octave", 4)
                    alt_map = {1: "#", -1: "b", 2: "##", -2: "bb", 0: ""}
                    p_str = f"{step}{alt_map.get(alter, '')}{octave}"
                
                pitches_out.append(p_str)
                
                # Handle Rhythm
                dur_type = item.get("duration_type") or item.get("duration", {}).get("type" if isinstance(item.get("duration"), dict) else None) or "q"
                dots = item.get("dots", 0)
                if isinstance(item.get("duration"), dict):
                    dots = item["duration"].get("dots", dots)
                
                ticks = get_ticks(dur_type, dots)
                
                if current_ticks > 0 and current_ticks + ticks > measure_ticks:
                    rhythms_out.append("|")
                    current_ticks = 0
                
                kind = item.get("kind", "note")
                prefix = "-" if kind == "rest" else ""
                dots_str = "." * dots
                rhythms_out.append(f"{prefix}{dur_type}{dots_str}")
                
                current_ticks += ticks
                if current_ticks >= measure_ticks:
                    rhythms_out.append("|")
                    current_ticks = 0
            
            if rhythms_out and rhythms_out[-1] != "|":
                rhythms_out.append("|")
            rhythms_out.append("]")
            
            output.append(f"<strong>{label}</strong>:")
            output.append(f"Pitches - {' '.join(pitches_out)}")
            output.append(f"Rhythms - {' '.join(rhythms_out)}<br>")
            
        return mark_safe("<br>".join(output))
    
    # Fallback for legacy 'chord' format
    if "chord" in data and isinstance(data["chord"], list):
        output = ["<strong>Legacy Chord Exercise</strong> (No explicit voices):<br>"]
        all_pitches = []
        all_rhythms = []
        
        # Convert MIDI to pitch names for legacy
        def midi_to_pitch(m):
            notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            return f"{notes[m % 12]}{m // 12 - 1}"

        for c in data["chord"]:
            # Visible pitches
            ps = c.get("visible", [])
            p_str = "(" + " ".join(midi_to_pitch(m) for m in ps) + ")" if len(ps) > 1 else (midi_to_pitch(ps[0]) if ps else "R")
            all_pitches.append(p_str)
            all_rhythms.append(c.get("rhythmValue", "q"))
            
        output.append(f"Pitches - {' '.join(all_pitches)}")
        output.append(f"Rhythms - {' '.join(all_rhythms)}")
        return mark_safe("<br>".join(output))

    return "No recognizable musical data (voices or chords) found in JSON."
