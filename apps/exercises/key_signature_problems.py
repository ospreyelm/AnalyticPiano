"""Key signature data and problem-set builder for Unit 3."""

# Ordered by circle of fifths (sharps ascending, then flats ascending).
# key_id uses HarmonyLab internal format: 'j'=major, 'i'=minor; '_' = natural.
KEY_TABLE = [
    {"key_id": "jC_",  "accidentals": 0, "sharps": 0, "flats": 0, "display_name": "C major",  "accepted_answers": ["C", "C major"]},
    {"key_id": "jG_",  "accidentals": 1, "sharps": 1, "flats": 0, "display_name": "G major",  "accepted_answers": ["G", "G major"]},
    {"key_id": "jD_",  "accidentals": 2, "sharps": 2, "flats": 0, "display_name": "D major",  "accepted_answers": ["D", "D major"]},
    {"key_id": "jA_",  "accidentals": 3, "sharps": 3, "flats": 0, "display_name": "A major",  "accepted_answers": ["A", "A major"]},
    {"key_id": "jE_",  "accidentals": 4, "sharps": 4, "flats": 0, "display_name": "E major",  "accepted_answers": ["E", "E major"]},
    {"key_id": "jB_",  "accidentals": 5, "sharps": 5, "flats": 0, "display_name": "B major",  "accepted_answers": ["B", "B major"]},
    {"key_id": "jF#",  "accidentals": 6, "sharps": 6, "flats": 0, "display_name": "F# major", "accepted_answers": ["F#", "F# major", "Gb", "Gb major"]},
    {"key_id": "jF_",  "accidentals": 1, "sharps": 0, "flats": 1, "display_name": "F major",  "accepted_answers": ["F", "F major"]},
    {"key_id": "jBb",  "accidentals": 2, "sharps": 0, "flats": 2, "display_name": "Bb major", "accepted_answers": ["Bb", "Bb major", "A#", "A# major"]},
    {"key_id": "jEb",  "accidentals": 3, "sharps": 0, "flats": 3, "display_name": "Eb major", "accepted_answers": ["Eb", "Eb major", "D#", "D# major"]},
    {"key_id": "jAb",  "accidentals": 4, "sharps": 0, "flats": 4, "display_name": "Ab major", "accepted_answers": ["Ab", "Ab major", "G#", "G# major"]},
    {"key_id": "jDb",  "accidentals": 5, "sharps": 0, "flats": 5, "display_name": "Db major", "accepted_answers": ["Db", "Db major", "C#", "C# major"]},
    {"key_id": "jGb",  "accidentals": 6, "sharps": 0, "flats": 6, "display_name": "Gb major", "accepted_answers": ["Gb", "Gb major", "F#", "F# major"]},
    {"key_id": "jC#",  "accidentals": 7, "sharps": 7, "flats": 0, "display_name": "C# major", "accepted_answers": ["C#", "C# major", "Db", "Db major"]},
    {"key_id": "jCb",  "accidentals": 7, "sharps": 0, "flats": 7, "display_name": "Cb major", "accepted_answers": ["Cb", "Cb major", "B", "B major"]},
]

MINOR_KEY_TABLE = [
    {"key_id": "iA_",  "accidentals": 0, "sharps": 0, "flats": 0, "display_name": "A minor",  "accepted_answers": ["Am", "A minor", "a minor", "a"]},
    {"key_id": "iE_",  "accidentals": 1, "sharps": 1, "flats": 0, "display_name": "E minor",  "accepted_answers": ["Em", "E minor", "e minor", "e"]},
    {"key_id": "iB_",  "accidentals": 2, "sharps": 2, "flats": 0, "display_name": "B minor",  "accepted_answers": ["Bm", "B minor", "b minor", "b"]},
    {"key_id": "iF#",  "accidentals": 3, "sharps": 3, "flats": 0, "display_name": "F# minor", "accepted_answers": ["F#m", "F# minor", "f# minor", "f#"]},
    {"key_id": "iC#",  "accidentals": 4, "sharps": 4, "flats": 0, "display_name": "C# minor", "accepted_answers": ["C#m", "C# minor", "c# minor", "c#"]},
    {"key_id": "iG#",  "accidentals": 5, "sharps": 5, "flats": 0, "display_name": "G# minor", "accepted_answers": ["G#m", "G# minor", "g# minor", "g#"]},
    {"key_id": "iD#",  "accidentals": 6, "sharps": 6, "flats": 0, "display_name": "D# minor", "accepted_answers": ["D#m", "D# minor", "d# minor", "d#", "Ebm", "Eb minor"]},
    {"key_id": "iD_",  "accidentals": 1, "sharps": 0, "flats": 1, "display_name": "D minor",  "accepted_answers": ["Dm", "D minor", "d minor", "d"]},
    {"key_id": "iG_",  "accidentals": 2, "sharps": 0, "flats": 2, "display_name": "G minor",  "accepted_answers": ["Gm", "G minor", "g minor", "g"]},
    {"key_id": "iC_",  "accidentals": 3, "sharps": 0, "flats": 3, "display_name": "C minor",  "accepted_answers": ["Cm", "C minor", "c minor", "c"]},
    {"key_id": "iF_",  "accidentals": 4, "sharps": 0, "flats": 4, "display_name": "F minor",  "accepted_answers": ["Fm", "F minor", "f minor", "f"]},
    {"key_id": "iBb",  "accidentals": 5, "sharps": 0, "flats": 5, "display_name": "Bb minor", "accepted_answers": ["Bbm", "Bb minor", "bb minor", "bb", "A#m", "A# minor"]},
    {"key_id": "iEb",  "accidentals": 6, "sharps": 0, "flats": 6, "display_name": "Eb minor", "accepted_answers": ["Ebm", "Eb minor", "eb minor", "eb", "D#m", "D# minor"]},
    {"key_id": "iA#",  "accidentals": 7, "sharps": 7, "flats": 0, "display_name": "A# minor", "accepted_answers": ["A#m", "A# minor", "a# minor", "a#", "Bbm", "Bb minor"]},
    {"key_id": "iAb",  "accidentals": 7, "sharps": 0, "flats": 7, "display_name": "Ab minor", "accepted_answers": ["Abm", "Ab minor", "ab minor", "ab", "G#m", "G# minor"]},
]

LEVEL_ACCIDENTAL_LIMIT = {1: 3, 2: 5, 3: 7}

# Enharmonic pairs where one duplicate is excluded per level to avoid asking
# the same key signature twice. The value is the max level at which to exclude.
_ENHARMONIC_EXCLUDE = {
    "jGb": 2,   # Gb (6 flats) excluded at level ≤2; F# (6 sharps) covers it
    "jCb": 2,   # Cb (7 flats) excluded at level ≤2; B  (5 sharps) covers it
    "jC#": 2,   # C# (7 sharps) excluded at level ≤2; Db (5 flats) covers it
    "iD#": 2,   # D# (6 sharps) excluded at level ≤2; Eb minor covers it
    "iA#": 2,   # A# (7 sharps) excluded at level ≤2; Bb minor covers it
    "iAb": 2,   # Ab (7 flats)  excluded at level ≤2; G# minor covers it
}


def _distractor_keys(correct_key_id: str, pool: list[dict]) -> list[str]:
    """Return 3 distractor display_names from pool."""
    correct_acc = next(k["accidentals"] for k in pool if k["key_id"] == correct_key_id)
    others = [k for k in pool if k["key_id"] != correct_key_id]
    same = [k for k in others if k["accidentals"] == correct_acc]
    diff = [k for k in others if k["accidentals"] != correct_acc]
    return [k["display_name"] for k in (same + diff)[:3]]


def build_key_sig_problem_set(level: int = 1, mode: str = "major") -> list[dict]:
    """Return problem dicts for the given difficulty level (1-3) and mode ('major'|'minor')."""
    table = KEY_TABLE if mode == "major" else MINOR_KEY_TABLE
    limit = LEVEL_ACCIDENTAL_LIMIT[level]
    eligible = [
        k for k in table
        if k["accidentals"] <= limit
        and level > _ENHARMONIC_EXCLUDE.get(k["key_id"], 0)
    ]
    problems = []
    for k in eligible:
        prompt = {"kind": "key_signature", "sharps": k["sharps"], "flats": k["flats"]}
        distractors = _distractor_keys(k["key_id"], eligible)
        choices = [k["display_name"]] + distractors
        problems.append({
            "prompt": prompt,
            "answer": k["display_name"],
            "accepted_answers": k["accepted_answers"],
            "key_id": k["key_id"],
            "accidentals": k["accidentals"],
            "choices": choices,
        })
    return problems
