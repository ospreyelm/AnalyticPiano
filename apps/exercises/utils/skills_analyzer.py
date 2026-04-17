from music21 import roman, key

def analyze_chunk_skills(chunk, chunk_key):
    # Initialize the tonal context
    tonal_key = key.Key(chunk_key)
    skills = set()
    
    # Pedagogical complexity: 1-10 scale based on standard collegiate music theory sequence
    # 1: Diatonic Triads, 2: Inversions/7ths, up to 10: Adv Chromaticism/Enharmonics
    complexity = 1  
    
    # Compress the score into a sequence of chords
    chordified = chunk.chordify()
    chords = list(chordified.recurse().getElementsByClass('Chord'))
    
    roman_numerals = []
    
    # 1. Chord-by-Chord Analysis
    for c in chords:
        rn = roman.romanNumeralFromChord(c, tonal_key)
        roman_numerals.append(rn)
        
        # Check if triad is diatonic or contains altered tones
        key_pcs = {kp.pitchClass for kp in tonal_key.pitches}
        is_diatonic = all(p.pitchClass in key_pcs for p in rn.pitches)
        
        if is_diatonic and rn.isConsonant():
            skills.add("Diatonic_Triads")
            
        if rn.isDominantSeventh():
            skills.add("Dominant_Seventh")
            complexity = max(complexity, 2)
            
        # Detect applied/secondary chords via chromaticism matching dominant/leading-tone qualities
        if not is_diatonic and (rn.isDominantSeventh() or rn.isMajorTriad()):
            # Neapolitan is also a major triad not diatonic.
            # But Neapolitan is typically flat II. Let's make sure it's not a normal secondary dominant
            if not (rn.scaleDegree == 2 and rn.frontAlterationAccidental and rn.frontAlterationAccidental.name == 'flat'):
                skills.add("Secondary_Dominant")
                complexity = max(complexity, 5)
                
        elif not is_diatonic and (rn.isDiminishedSeventh() or rn.isHalfDiminishedSeventh()):
            skills.add("Secondary_Leading_Tone")
            complexity = max(complexity, 5)
            
        if rn.isAugmentedSixth():
            skills.add("Augmented_Sixth")
            complexity = max(complexity, 8)
            
        # Safely verify Neapolitan API function
        is_neapolitan = False
        if hasattr(rn, 'isNeapolitan') and rn.isNeapolitan():
            is_neapolitan = True
        else:
            # Fallback logic for Neapolitan: Major triad on the lowered 2nd scale degree (bII)
            if rn.isMajorTriad() and rn.scaleDegree == 2 and rn.frontAlterationAccidental and rn.frontAlterationAccidental.name == 'flat':
                is_neapolitan = True
                
        if is_neapolitan:
            skills.add("Neapolitan_Sixth")
            if "Secondary_Dominant" in skills and (rn.isMajorTriad() and rn.scaleDegree == 2 and rn.frontAlterationAccidental and rn.frontAlterationAccidental.name == 'flat'):
                # Handle mutually exclusive tagging if matched as both
                skills.remove("Secondary_Dominant")
            complexity = max(complexity, 7)
            
        # Inversions checks (music21 returns 0 for root pos, 1 for 1st inv, None if unknown)
        inv = rn.inversion()
        if inv == 1:
            skills.add("Inversions_First")
            complexity = max(complexity, 2)
        elif inv == 2:
            skills.add("Inversions_Second")
            complexity = max(complexity, 3)

    # 2. Sequential / Cadential Analysis
    if len(roman_numerals) >= 2:
        penult = roman_numerals[-2]
        ult = roman_numerals[-1]
        
        # Perfect Authentic Cadence: V -> I
        if penult.scaleDegree == 5 and ult.scaleDegree == 1:
            if penult.inversion() == 0 and ult.inversion() == 0:
                skills.add("Cadence_Perfect_Authentic")
                
        # Plagal Cadence: IV -> I
        if penult.scaleDegree == 4 and ult.scaleDegree == 1:
            skills.add("Cadence_Plagal")
            complexity = max(complexity, 2)
            
        # Deceptive Cadence: V -> vi
        if penult.scaleDegree == 5 and ult.scaleDegree in [6, -6]:
            # Sometimes minor 6th degree is represented as 6 in a minor key natively, or -6 if forced
            skills.add("Cadence_Deceptive")
            complexity = max(complexity, 3)
                
        # Half Cadence: phrase finishes on V
        if ult.scaleDegree == 5 and ult.isMajorTriad():
            skills.add("Cadence_Half")
            complexity = max(complexity, 2)
            
        # Picardy Third
        if tonal_key.mode == 'minor' and ult.scaleDegree == 1 and ult.isMajorTriad():
            skills.add("Picardy_Third")
            complexity = max(complexity, 6)
            
    return sorted(list(skills)), complexity
