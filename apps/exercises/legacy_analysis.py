from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class LegacyAnalysisKey(str, Enum):
    NOTE_NAMES = "note_names"
    SCIENTIFIC_PITCH = "scientific_pitch"
    FIXED_DO = "fixed_do"
    PITCH_CLASS = "pitch_class"
    SCALE_DEGREES = "scale_degrees"
    SOLFEGE = "solfege"
    DO_BASED_SOLFEGE = "do_based_solfege"
    
    INTERVALS = "intervals"
    INTERVALS_WRAP_AFTER_OCTAVE = "intervals_wrap_after_octave"
    INTERVALS_WRAP_AFTER_OCTAVE_PLUS_DITONE = "intervals_wrap_after_octave_plus_ditone"
    GENERIC_INTERVALS = "generic_intervals"
    GENERIC_INTERVALS_WRAP_AFTER_OCTAVE = "generic_intervals_wrap_after_octave"
    GENERIC_INTERVALS_WRAP_AFTER_OCTAVE_PLUS_DITONE = "generic_intervals_wrap_after_octave_plus_ditone"
    PCI = "pci"
    
    CHORD_LABELS = "chord_labels"
    ROMAN_NUMERALS = "roman_numerals"
    SPACING = "spacing"
    SET_CLASS_SET = "set_class_set"
    SET_CLASS_NORMAL = "set_class_normal"
    SET_CLASS_PRIME = "set_class_prime"
    SET_CLASS_FORTE = "set_class_forte"
    THOROUGHBASS = "thoroughbass"
    ABBREVIATE_THOROUGHBASS = "abbreviate_thoroughbass"


class LegacyAnalysisConfig(BaseModel):
    """
    Pydantic model representing the active analysis options 
    for legacy play settings (stored in data.mode).
    """
    note_names: Optional[bool] = Field(default=False, description="Letters")
    scientific_pitch: Optional[bool] = Field(default=False, description="Scientific pitch")
    fixed_do: Optional[bool] = Field(default=False, description="Fixed-do")
    pitch_class: Optional[bool] = Field(default=False, description="Pitch class")
    scale_degrees: Optional[bool] = Field(default=False, description="Degrees")
    solfege: Optional[bool] = Field(default=False, description="Movable-do with LA- minor")
    do_based_solfege: Optional[bool] = Field(default=False, description="Movable-do with DO-minor")
    
    intervals: Optional[bool] = Field(default=False, description="Intervals")
    intervals_wrap_after_octave: Optional[bool] = Field(default=False, description="Intervals (wrap after octave)")
    intervals_wrap_after_octave_plus_ditone: Optional[bool] = Field(default=False, description="Intervals (wrap after octave plus ditone)")
    generic_intervals: Optional[bool] = Field(default=False, description="Generic intervals")
    generic_intervals_wrap_after_octave: Optional[bool] = Field(default=False, description="Generic intervals (wrap after octave)")
    generic_intervals_wrap_after_octave_plus_ditone: Optional[bool] = Field(default=False, description="Generic intervals (wrap after octave plus ditone)")
    pci: Optional[bool] = Field(default=False, description="Pitch-class intervals")
    
    chord_labels: Optional[bool] = Field(default=False, description="Chord labels (E)")
    roman_numerals: Optional[bool] = Field(default=False, description="Harmony in Roman numerals")
    spacing: Optional[bool] = Field(default=False, description="Spacing of upper voices")
    set_class_set: Optional[bool] = Field(default=False, description="Set class—set")
    set_class_normal: Optional[bool] = Field(default=False, description="Set class—normal order")
    set_class_prime: Optional[bool] = Field(default=False, description="Set class—prime form")
    set_class_forte: Optional[bool] = Field(default=False, description="Set class—Forte")
    thoroughbass: Optional[bool] = Field(default=False, description="Figured bass (G)")
    abbreviate_thoroughbass: Optional[bool] = Field(default=False, description="Abbreviate figured bass (V)")


LEGACY_ANALYSIS_REGISTRY: Dict[LegacyAnalysisKey, Dict[str, Any]] = {
    LegacyAnalysisKey.NOTE_NAMES: {
        "label": "Letters",
        "column": 1,
        "description": "Letter names of pitches (e.g. C, F#, Bb)"
    },
    LegacyAnalysisKey.SCIENTIFIC_PITCH: {
        "label": "Scientific pitch",
        "column": 1,
        "description": "Note names with octaves (e.g. C4, F#3)"
    },
    LegacyAnalysisKey.FIXED_DO: {
        "label": "Fixed-do",
        "column": 1,
        "description": "Fixed-do solfege syllables (e.g. do, fa diesis)"
    },
    LegacyAnalysisKey.PITCH_CLASS: {
        "label": "Pitch class",
        "column": 1,
        "description": "Pitch class integers 0-11 (C = 0)"
    },
    LegacyAnalysisKey.SCALE_DEGREES: {
        "label": "Degrees",
        "column": 1,
        "description": "Scale degree numbers relative to local key (e.g. ^1, ^3)"
    },
    LegacyAnalysisKey.SOLFEGE: {
        "label": "Movable-do with LA- minor",
        "column": 1,
        "description": "Movable-do solfege with minor key tonic mapped to la"
    },
    LegacyAnalysisKey.DO_BASED_SOLFEGE: {
        "label": "Movable-do with DO-minor",
        "column": 1,
        "description": "Movable-do solfege with minor key tonic mapped to do"
    },
    LegacyAnalysisKey.INTERVALS: {
        "label": "Intervals",
        "column": 2,
        "description": "Specific intervals between adjacent voices"
    },
    LegacyAnalysisKey.INTERVALS_WRAP_AFTER_OCTAVE: {
        "label": "Intervals (wrap after octave)",
        "column": 2,
        "description": "Specific intervals compound-reduced to a single octave"
    },
    LegacyAnalysisKey.INTERVALS_WRAP_AFTER_OCTAVE_PLUS_DITONE: {
        "label": "Intervals (wrap after octave plus ditone)",
        "column": 2,
        "description": "Specific intervals compound-reduced with 9th-inversion wrap"
    },
    LegacyAnalysisKey.GENERIC_INTERVALS: {
        "label": "Generic intervals",
        "column": 2,
        "description": "Generic diatonic intervals (e.g. 3rd, 5th)"
    },
    LegacyAnalysisKey.GENERIC_INTERVALS_WRAP_AFTER_OCTAVE: {
        "label": "Generic intervals (wrap after octave)",
        "column": 2,
        "description": "Generic intervals reduced to a single octave"
    },
    LegacyAnalysisKey.GENERIC_INTERVALS_WRAP_AFTER_OCTAVE_PLUS_DITONE: {
        "label": "Generic intervals (wrap after octave plus ditone)",
        "column": 2,
        "description": "Generic intervals compound-reduced with 9th-inversion wrap"
    },
    LegacyAnalysisKey.PCI: {
        "label": "Pitch-class intervals",
        "column": 2,
        "description": "Ordered pitch-class intervals (semitones 0-11)"
    },
    LegacyAnalysisKey.CHORD_LABELS: {
        "label": "Chord labels (E)",
        "column": 3,
        "description": "Textual chord names/qualities (e.g. C Major Triad)"
    },
    LegacyAnalysisKey.ROMAN_NUMERALS: {
        "label": "Harmony in Roman numerals",
        "column": 3,
        "description": "Roman numeral analysis in local key (e.g. I, IV6)"
    },
    LegacyAnalysisKey.SPACING: {
        "label": "Spacing of upper voices",
        "column": 3,
        "description": "Spacing/distribution of SAT voices (e.g. close, open)"
    },
    LegacyAnalysisKey.SET_CLASS_SET: {
        "label": "Set class—set",
        "column": 3,
        "description": "Pitch class set content (e.g. {C,E,G})"
    },
    LegacyAnalysisKey.SET_CLASS_NORMAL: {
        "label": "Set class—normal order",
        "column": 3,
        "description": "Pitch classes in normal order (e.g. [0, 4, 7])"
    },
    LegacyAnalysisKey.SET_CLASS_PRIME: {
        "label": "Set class—prime form",
        "column": 3,
        "description": "Prime form of the pitch class set (e.g. <037>)"
    },
    LegacyAnalysisKey.SET_CLASS_FORTE: {
        "label": "Set class—Forte",
        "column": 3,
        "description": "Forte number classification (e.g. 3-11)"
    },
    LegacyAnalysisKey.THOROUGHBASS: {
        "label": "Figured bass (G)",
        "column": 3,
        "description": "Diatonic figured bass numerals (e.g. 6, 6/4)"
    },
    LegacyAnalysisKey.ABBREVIATE_THOROUGHBASS: {
        "label": "Abbreviate figured bass (V)",
        "column": 3,
        "description": "Kellner/Common-practice abbreviations for figures"
    }
}
