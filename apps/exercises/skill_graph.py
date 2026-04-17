"""
skill_graph.py — Canonical skill taxonomy and default prerequisite DAG.

This module contains no Django dependencies — it's pure Python constants.
Used by:
  - apps/exercises/mastery.py (get_unlocked_skills)
  - apps/exercises/management/commands/seed_skill_prerequisites.py (seeder)
"""

# All skill tags usable in the MVP adaptive engine.
# Skills marked with a * are "Planned" (📋) but included so the DAG is complete.
# The mastery engine treats all tags equally — untagged exercises won't affect mastery.
ALL_SKILL_TAGS = [
    # TIER 0 — Music Literacy (Pre-Theory)
    "Read_Treble_Clef",
    "Read_Bass_Clef",
    "Ledger_Lines",
    "Note_Names",
    "Solfege_Movable",
    "Solfege_Fixed",
    "Scale_Degrees",
    "Pitch_Class",
    "Interval_Generic",
    "Interval_Specific",
    "Interval_Compound",

    # TIER 1 — Diatonic Harmony Foundation
    "Diatonic_Triads",
    "Inversions_First",
    "Inversions_Second",
    "Dominant_Seventh",
    "Diatonic_Sevenths",
    "Figured_Bass_Reading",
    "Cadence_Half",
    "Cadence_Perfect_Authentic",
    "Cadence_Imperfect_Authentic",
    "Cadence_Deceptive",
    "Cadence_Plagal",

    # TIER 2 — Chromatic Harmony
    "Secondary_Dominant",
    "Secondary_Leading_Tone",
    "Diminished_Seventh",
    "Half_Diminished_Seventh",
    "Picardy_Third",
    "Modal_Mixture",
    "Neapolitan_Sixth",
    "Augmented_Sixth",
    "Augmented_Sixth_Italian",
    "Augmented_Sixth_French",
    "Augmented_Sixth_German",
    "Modulation_Diatonic_Pivot",
    "Modulation_Chromatic",
    "Common_Tone_Dim7",
]

# Default prerequisite DAG.
# key   = skill tag
# value = list of skill tags that must be at 'familiar' or above before this skill unlocks.
# A skill not listed here has no prerequisites (always unlocked).
DEFAULT_PREREQUISITES = {
    # TIER 0 chains
    "Ledger_Lines":                  ["Note_Names"],
    "Solfege_Movable":               ["Note_Names"],
    "Solfege_Fixed":                 ["Note_Names"],
    "Scale_Degrees":                 ["Note_Names"],
    "Interval_Generic":              ["Note_Names"],
    "Interval_Specific":             ["Interval_Generic"],
    "Interval_Compound":             ["Interval_Specific"],

    # TIER 1 chains
    "Diatonic_Triads":               ["Interval_Specific"],
    "Inversions_First":              ["Diatonic_Triads"],
    "Inversions_Second":             ["Inversions_First"],
    "Dominant_Seventh":              ["Diatonic_Triads"],
    "Diatonic_Sevenths":             ["Dominant_Seventh"],
    "Figured_Bass_Reading":          ["Diatonic_Triads"],
    "Cadence_Half":                  ["Dominant_Seventh"],
    "Cadence_Perfect_Authentic":     ["Cadence_Half"],
    "Cadence_Imperfect_Authentic":   ["Cadence_Perfect_Authentic"],
    "Cadence_Deceptive":             ["Cadence_Perfect_Authentic"],
    "Cadence_Plagal":                ["Diatonic_Triads"],

    # TIER 2 chains
    "Secondary_Dominant":            ["Cadence_Perfect_Authentic"],
    "Secondary_Leading_Tone":        ["Secondary_Dominant", "Diminished_Seventh"],
    "Diminished_Seventh":            ["Dominant_Seventh"],
    "Half_Diminished_Seventh":       ["Diminished_Seventh"],
    "Picardy_Third":                 ["Cadence_Perfect_Authentic"],
    "Modal_Mixture":                 ["Secondary_Dominant"],
    "Neapolitan_Sixth":              ["Secondary_Dominant"],
    "Augmented_Sixth":               ["Neapolitan_Sixth"],
    "Augmented_Sixth_Italian":       ["Augmented_Sixth"],
    "Augmented_Sixth_French":        ["Augmented_Sixth"],
    "Augmented_Sixth_German":        ["Augmented_Sixth"],
    "Modulation_Diatonic_Pivot":     ["Secondary_Dominant"],
    "Modulation_Chromatic":          ["Augmented_Sixth", "Modulation_Diatonic_Pivot"],
    "Common_Tone_Dim7":              ["Diminished_Seventh"],
}

# Mastery level constants (ordered from lowest to highest)
MASTERY_LEVELS = ["not_started", "attempted", "familiar", "proficient", "mastered"]

# A skill is considered "acquired" (unlocks downstream nodes) once it is at this level or above
UNLOCK_THRESHOLD = "familiar"
