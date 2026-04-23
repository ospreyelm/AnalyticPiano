from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
import json

class VoiceID(str, Enum):
    SOPRANO = "S"
    ALTO = "A"
    TENOR = "T"
    BASS = "B"

class Pitch(BaseModel):
    step: str
    alter: int
    octave: int
    midi: int

    def to_scientific(self) -> str:
        acc = {1: "#", -1: "b", 0: "", 2: "##", -2: "bb"}.get(self.alter, "")
        return f"{self.step}{acc}{self.octave}"
    
    def to_short(self) -> str:
        """e.g. C#4, Eb3"""
        acc = {1: "#", -1: "b", 0: "", 2: "##", -2: "bb"}.get(self.alter, "")
        return f"{self.step.lower()}{acc}{self.octave}"

    def to_long_name(self) -> str:
        """e.g. C, F#, Bb"""
        acc = {1: "#", -1: "b", 0: "", 2: "##", -2: "bb"}.get(self.alter, "")
        return f"{self.step}{acc}"

class VoiceEvent(BaseModel):
    kind: str = "note" # "note" or "rest"
    pitch: Optional[Pitch] = None
    duration: float # quarter lengths (e.g. 1.0 = quarter, 0.5 = eighth)
    duration_type: str # "w", "h", "q", "8", "16", etc.
    dots: int = 0
    is_tied_start: bool = False
    is_tied_stop: bool = False
    is_target: bool = True # False if this note is just context/accompaniment

class Voices(BaseModel):
    S: List[VoiceEvent] = Field(default_factory=list)
    A: List[VoiceEvent] = Field(default_factory=list)
    T: List[VoiceEvent] = Field(default_factory=list)
    B: List[VoiceEvent] = Field(default_factory=list)

class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    figured_bass: Optional[str] = None
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None # e.g. "Predominant", "Dominant"

class VisualMetadata(BaseModel):
    """
    Coordinates or hints for the rendering engine to place 
    'hand-written' style analysis on the page.
    """
    x_hint: Optional[float] = None # Relative coordinate or offset
    y_hint: Optional[float] = None # Vertical offset (e.g. -40 for RN)
    anchor: Optional[str] = "slice" # "measure", "note", "slice"
    style: Optional[str] = "handwritten" # e.g. "handwritten", "engraved"

class AnalysisSlice(BaseModel):
    offset: float # Quarter-lengths from start of exercise
    content: AnalysisLayer
    visual: Optional[VisualMetadata] = None
    unit_tags: List[int] = Field(default_factory=list) # e.g. [1, 9, 12] for unit focus

class GradingSlice(BaseModel):
    offset: float
    target_midi_pitches: List[int]
    rhythmic_flexibility: bool = False

class Metadata(BaseModel):
    exercise_id: str
    source: str # e.g. "Bach Chorale BWV 269", "Sonata K.331"
    key: str # e.g. "G Major", "c minor"
    meter: str # e.g. "4/4", "3/4"
    clef: str = "treble" # "treble", "bass", "alto", "tenor"
    complexity_score: int = Field(ge=1, le=12, description="Unit 1-12 ranking system")

class UMTO(BaseModel):
    """
    Universal Music Theory Object (UMTO)
    
    A modular schema acting as a bridge between Analysis Logic (theory engine)
    and Rendering/Grading Logic (VexFlow and MIDI).
    """
    model_config = ConfigDict(
        title="Universal Music Theory Object",
        json_schema_extra={
            "examples": [
                {
                    "metadata": {
                        "exercise_id": "EA01",
                        "source": "Bach Chorale",
                        "key": "C Major",
                        "meter": "4/4",
                        "complexity_score": 1
                    },
                    "voices": {"S": [], "A": [], "T": [], "B": []},
                    "analysis": [],
                    "grading": []
                }
            ]
        }
    )

    metadata: Metadata
    voices: Voices
    analysis: List[AnalysisSlice] = Field(default_factory=list)
    grading: List[GradingSlice] = Field(default_factory=list)

    def get_chord_at_offset(self, offset: float) -> List[Pitch]:
        """
        Calculates the vertical sonority (pitches sounding) at a specific offset.
        Useful for Analysis Logic to cross-reference theoretical labels with actual notes.
        """
        pitches = []
        for voice_id in ["S", "A", "T", "B"]:
            events = getattr(self.voices, voice_id)
            current_time = 0.0
            for event in events:
                # Use a small epsilon for float comparison
                if current_time <= offset < (current_time + event.duration - 0.001):
                    if event.kind == "note" and event.pitch:
                        pitches.append(event.pitch)
                    break
                current_time += event.duration
        return pitches

    def get_allowed_answers(self, unit: Optional[int] = None) -> List[str]:
        """
        Returns a list of unique analysis labels applicable to this exercise,
        optionally filtered by a specific pedagogical Unit.
        """
        labels = set()
        for slice in self.analysis:
            if unit is None or unit in slice.unit_tags:
                # Priority of labels
                if slice.content.roman_numeral:
                    labels.add(slice.content.roman_numeral)
                elif slice.content.pop_symbol:
                    labels.add(slice.content.pop_symbol)
                elif slice.content.figured_bass:
                    labels.add(slice.content.figured_bass)
                elif slice.content.functional_label:
                    labels.add(slice.content.functional_label)

        # Unit 1 Bridge: If no theory labels found and it's Unit 1, 
        # use the Pitch names sounding at those offsets.
        if not labels and unit == 1:
            for slice in self.analysis:
                if 1 in slice.unit_tags:
                    pitches = self.get_chord_at_offset(slice.offset)
                    for p in pitches:
                        labels.add(p.to_long_name())

        return sorted(list(labels))

    def to_frontend_payload(self, unit: Optional[int] = None) -> Dict[str, Any]:
        """
        Generates a payload ready for the ExerciseDefinition JS parser.
        """
        return {
            "type": "umto_chorale",
            "isUMTO": True,
            "exerciseId": self.metadata.exercise_id,
            "key": self.metadata.key,
            "meter": self.metadata.meter,
            "clef": self.metadata.clef,
            "allowed_answers": self.get_allowed_answers(unit),
            "score": {
                "meta": {"key": self.metadata.key, "time": self.metadata.meter, "clef": self.metadata.clef},
                # We can transform UMTO voices into the measure-based structure 
                # expected by VexFlowAdapter if needed, or update the adapter.
                "umto": self.model_dump()
            },
            "grading": [s.model_dump() for s in self.grading]
        }

    def flatten_to_artusi(self) -> str:
        """
        'Flattens' this data into a simple string for quick dashboard debugging.
        Format: [chord] | ans: [label] (Units: [tags])
        Example: c4 e4 g4 | ans: I (Units: 1, 9)
        """
        if not self.grading and not self.analysis:
            return f"Empty UMTO: {self.metadata.exercise_id}"

        # 1. Identify the first significant slice
        first_grading = sorted(self.grading, key=lambda x: x.offset)[0] if self.grading else None
        target_offset = first_grading.offset if first_grading else 0.0
        
        # 2. Get the actual pitches sounding at this offset
        sounding_pitches = self.get_chord_at_offset(target_offset)
        if sounding_pitches:
            # Sort by MIDI to keep it predictable (Bass to Soprano)
            sounding_pitches.sort(key=lambda p: p.midi)
            chord_str = " ".join([p.to_short() for p in sounding_pitches])
        elif first_grading:
            # Fallback to MIDI if voices are empty but grading exists
            chord_str = " ".join([str(m) for m in first_grading.target_midi_pitches])
        else:
            chord_str = "N/A"
        
        # 3. Get analysis and unit info
        ans_str = "none"
        unit_str = ""
        if self.analysis:
            closest_analysis = min(self.analysis, key=lambda x: abs(x.offset - target_offset))
            
            parts = []
            if closest_analysis.content.roman_numeral:
                parts.append(closest_analysis.content.roman_numeral)
            if closest_analysis.content.figured_bass:
                parts.append(closest_analysis.content.figured_bass)
            if closest_analysis.content.pop_symbol:
                parts.append(closest_analysis.content.pop_symbol)
            
            if parts:
                ans_str = " ".join(parts)
            elif closest_analysis.content.functional_label:
                ans_str = closest_analysis.content.functional_label
            
            if closest_analysis.unit_tags:
                unit_str = f" (Units: {', '.join(map(str, closest_analysis.unit_tags))})"

        return f"{chord_str} | ans: {ans_str}{unit_str}"

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "UMTO":
        return cls.model_validate_json(json_str)

    @classmethod
    def generate_schema(cls) -> Dict[str, Any]:
        """Returns the JSON Schema for UMTO."""
        return cls.model_json_schema()
