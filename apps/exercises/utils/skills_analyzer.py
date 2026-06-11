try:
    from music21 import roman, key
    _MUSIC21_AVAILABLE = True
except ImportError:
    _MUSIC21_AVAILABLE = False
import re

# Maps internal unit-prefixed tags → canonical skill tag vocabulary.
# Canonical tags are used by adaptive pool queries and SKILL_CHORD_PATTERNS.
# Both forms are emitted so legacy unit:X queries still work.
_CANONICAL_MAP = {
    "unit:9_diatonic_triads":             "Diatonic_Triads",
    "unit:10_inversions_first":           "Inversions_First",
    "unit:12_inversions_second":          "Inversions_Second",
    "unit:9_Dominant_Seventh":            "Dominant_Seventh",
    "unit:16_diminished_seventh":         "Diminished_Seventh",
    "unit:16_half_diminished_seventh":    "Half_Diminished_Seventh",
    "unit:7_cadence_half":                "Cadence_Half",
    "unit:7_Cadence_Perfect_Authentic":   "Cadence_Perfect_Authentic",
    "unit:7_cadence_deceptive":           "Cadence_Deceptive",
    "unit:7_cadence_plagal":              "Cadence_Plagal",
    "unit:16_secondary_dominant":         "Secondary_Dominant",
    "unit:16_secondary_leading_tone":     "Secondary_Leading_Tone",
    "unit:18_neapolitan_sixth":           "Neapolitan_Sixth",
    "unit:18_augmented_sixth":            "Augmented_Sixth",
    "unit:17_picardy_third":              "Picardy_Third",
}
def parse_riem_and_measures(description: str) -> tuple[int | None, int | None, int | None]:
    if not description:
        return None, None, None
    m = re.search(r"R(\d+)\s*-\s*Phrase\s*\d+\s*\(mm\.(\d+)-(\d+)\)", description)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None, None, None


def check_wir_key_change(description: str) -> bool:
    riem, start_m, end_m = parse_riem_and_measures(description)
    if riem is None or start_m is None or end_m is None:
        return False
    from apps.exercises.utils import wir_corpus
    if not wir_corpus.has_chorale(riem):
        return False
    chorale = wir_corpus._CHORALES.get(str(riem))
    if not chorale:
        return False
    keys = []
    for entry in chorale.get("labels", []):
        m = entry.get("measure")
        if m is not None and start_m <= m <= end_m:
            lk = entry.get("local_key")
            if lk:
                keys.append(lk)
    if not keys:
        return False
    return len(set(keys)) > 1


def _normalize_key_token(chunk_key):
    """Convert a HarmonyLab pseudo-key token (e.g. 'jC_', 'iA_', 'jBb_') into a
    music21 key.Key. Plain conventional names ('C', 'a', 'Bb') pass through.

    HarmonyLab stores pseudo-key tokens where a leading 'j' means major and 'i'
    means minor, trailing '_' is a separator, and 'b' is a flat. music21 cannot
    parse these directly ("Cannot make a step out of 'J'"), so normalize here at
    the boundary before constructing the Key.
    """
    text = (chunk_key or "jC_").strip()
    if text and text[0] in {"i", "j"}:
        tonic = text[1:].replace("_", "").replace("b", "-") or "C"
        mode = "minor" if text[0] == "i" else "major"
        return key.Key(tonic, mode)
    return key.Key(text.replace("b", "-") or "C")


def analyze_chunk_skills(chunk, chunk_key, description=None):
    """
    Analyzes a music chunk and returns a list of pedagogical tags (unit:X_...)
    and a complexity rating (1-51, based on the curriculum unit).
    """
    tonal_key = _normalize_key_token(chunk_key)
    skills = set()
    
    # 0. Literacy Check (Tier 1 Units 1-4)
    # We can detect these globally for any valid score
    skills.add("unit:1_pitch_reading")
    skills.add("unit:2_rhythm")
    skills.add("unit:3_key_signature")
    skills.add("unit:4_interval_quality")

    # Quality Exclusions checks
    has_interior_rests = False
    for part in chunk.parts:
        elements = list(part.flatten().notesAndRests)
        if not elements:
            continue
        note_indices = [i for i, el in enumerate(elements) if el.isNote or el.isChord]
        if not note_indices:
            continue
        for i in range(note_indices[0] + 1, note_indices[-1]):
            if elements[i].isRest:
                has_interior_rests = True
                break
        if has_interior_rests:
            break

    if not has_interior_rests:
        skills.add("no_interior_rests")

    if description:
        if not check_wir_key_change(description):
            skills.add("no_key_change")
    
    # 1. Chord-by-Chord Analysis
    chordified = chunk.chordify()
    chords = list(chordified.recurse().getElementsByClass('Chord'))
    roman_numerals = []
    
    unique_degrees = set()
    
    for c in chords:
        rn = roman.romanNumeralFromChord(c, tonal_key)
        roman_numerals.append(rn)
        
        deg = rn.scaleDegree
        unique_degrees.add(deg)
        
        # Diatonic Foundation (Triads/Sevenths)
        key_pcs = {kp.pitchClass for kp in tonal_key.pitches}
        is_diatonic = all(p.pitchClass in key_pcs for p in rn.pitches)
        
        # Only treat as a harmonic 'triad' skill if there are 3+ distinct notes.
        # This prevents simple pitch-reading (Unit 1) or intervals (Unit 4) 
        # from polluting higher-tier harmonic analysis playlists.
        if is_diatonic and len(rn.pitches) >= 3:
            skills.add("unit:5_triad_quality")
            skills.add("unit:9_diatonic_triads")
            
        if rn.containsSeventh():
            skills.add("unit:14_diatonic_sevenths")
            
        if rn.isDominantSeventh():
            skills.add("unit:9_Dominant_Seventh")
            
        # Inversions
        inv = rn.inversion()
        if inv == 1:
            skills.add("unit:10_inversions_first")
        elif inv == 2:
            skills.add("unit:12_inversions_second")
            
        # Chromaticism (Tier 2/3)
        if not is_diatonic:
            # Neapolitan Sixth first: a bII major triad must not be
            # mis-tagged as a secondary dominant below.
            is_n6 = False
            if hasattr(rn, 'isNeapolitan') and rn.isNeapolitan(): is_n6 = True
            elif rn.isMajorTriad() and deg == 2 and rn.frontAlterationAccidental and rn.frontAlterationAccidental.name == 'flat':
                is_n6 = True
            if is_n6:
                skills.add("unit:18_neapolitan_sixth")

            if not is_n6 and (rn.isDominantSeventh() or (rn.isMajorTriad() and deg not in [1, 4, 5])):
                skills.add("unit:16_secondary_dominant")
            if rn.isDiminishedSeventh():
                skills.add("unit:16_diminished_seventh")
                skills.add("unit:16_secondary_leading_tone")
            elif rn.isHalfDiminishedSeventh():
                skills.add("unit:16_half_diminished_seventh")
                skills.add("unit:16_secondary_leading_tone")

            if rn.isAugmentedSixth():
                skills.add("unit:18_augmented_sixth")

    # 2. Functional Exclusivity (Unit 9 vs Unit 11)
    # Unit 9: Tonic and Dominant exclusively
    if unique_degrees.issubset({1, 5}):
        skills.add("unit:9_tonic_dominant_exclusively")
    # Unit 11: Pre-Dominants (II or IV)
    if unique_degrees.intersection({2, 4, 6}):
        skills.add("unit:11_diatonic_predominant")
        
    # 3. Rule of the Octave (Unit 13)
    # ROTO if we have a significant scalar bass segment (at least 4 notes in a row)
    bass_line = [rn.bass().pitchClass for rn in roman_numerals]
    if len(bass_line) >= 4:
        is_roto_candidate = True
        for i in range(len(bass_line) - 1):
            interval = (bass_line[i+1] - bass_line[i]) % 12
            if interval not in [1, 2, 10, 11]: # Semi-tone or whole-tone step
                is_roto_candidate = False
                break
        if is_roto_candidate:
            skills.add("unit:13_rule_of_the_octave")

    # 4. Cadential Analysis (Unit 7)
    if len(roman_numerals) >= 2:
        penult, ult = roman_numerals[-2], roman_numerals[-1]
        p_deg, u_deg = penult.scaleDegree, ult.scaleDegree
        
        if p_deg == 5 and u_deg == 1:
            if penult.inversion() == 0 and ult.inversion() == 0:
                skills.add("unit:7_cadence_authentic")
                skills.add("unit:7_Cadence_Perfect_Authentic")
        elif p_deg == 4 and u_deg == 1:
            skills.add("unit:7_cadence_plagal")
        elif p_deg == 5 and u_deg == 6:
            skills.add("unit:7_cadence_deceptive")
        
        if u_deg == 5 and ult.isMajorTriad():
            skills.add("unit:7_cadence_half")

        # Picardy Third: minor-key phrase ending on a major tonic triad
        if tonal_key.mode == 'minor' and u_deg == 1 and ult.isMajorTriad():
            skills.add("unit:17_picardy_third")
            skills.add("unit:17_Picardy_Third")

    # 5. Determine Complexity (The lead unit number)
    unit_nums = []
    for s in skills:
        match = re.search(r'unit:(\w?\d+)', s)
        if match:
            raw_num = match.group(1)
            # Handle Branch A/B/C/D prefixes for complexity
            num_only = re.sub(r'[^0-9]', '', raw_num)
            if num_only:
                unit_nums.append(int(num_only))
    
    complexity = max(unit_nums) if unit_nums else 1
    
    # Add the primary unit numbers as tags too e.g. "unit:7"
    for s in list(skills):
        match = re.search(r'unit:(\w?\d+)', s)
        if match:
            skills.add(f"unit:{match.group(1)}")

    # Emit canonical tags alongside unit-prefixed forms
    for internal, canonical in _CANONICAL_MAP.items():
        if internal in skills:
            skills.add(canonical)

    return sorted(list(skills)), complexity

