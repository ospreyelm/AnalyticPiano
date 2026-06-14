from enum import Enum
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
import json

VoiceName = Literal["S", "A", "T", "B"]

class VoiceID(str, Enum):
    SOPRANO = "S"
    ALTO = "A"
    TENOR = "T"
    BASS = "B"

class InteractionMode(str, Enum):
    IDENTIFICATION = "identification"
    PLAYBACK = "playback"
    ANALYSIS_MATCH = "analysis_match"
    SYMBOLIC_IDENTIFICATION = "symbolic_identification"
    HARMONIZATION = "harmonization"

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

class ChordEvent(BaseModel):
    offset: float = Field(ge=0.0)          # quarter-lengths from start
    duration: float = Field(gt=0.0)         # quarter-lengths
    visible: List[int] = Field(default_factory=list)  # MIDI pitches sounding
    hidden: List[int] = Field(default_factory=list)   # MIDI pitches not shown
    spelling: Optional[List[str]] = None    # positional: visible then hidden

    @model_validator(mode="after")
    def validate_spelling_length(self):
        if self.spelling is not None:
            expected = len(self.visible) + len(self.hidden)
            if len(self.spelling) != expected:
                raise ValueError(
                    f"spelling length {len(self.spelling)} must equal "
                    f"visible+hidden length {expected}"
                )
        return self

class Voices(BaseModel):
    S: List[VoiceEvent] = Field(default_factory=list)
    A: List[VoiceEvent] = Field(default_factory=list)
    T: List[VoiceEvent] = Field(default_factory=list)
    B: List[VoiceEvent] = Field(default_factory=list)

class AnalysisLayer(BaseModel):
    roman_numeral: Optional[str] = None
    raw_roman_numeral: Optional[str] = None  # unfiltered music21 output; durable record
    local_key: Optional[str] = None  # active key at this slice, e.g. "G", "d"
    raw_figured_bass: Optional[str] = None   # unabbreviated stack: "8/5/3", "7/5/3"
    figured_bass: Optional[str] = None       # abbreviated per Kellner: "", "7", "4/2"
    pop_symbol: Optional[str] = None
    functional_label: Optional[str] = None # e.g. "Predominant", "Dominant"
    scale_degrees: Optional[List[Dict[str, Any]]] = None  # [{"midi": 71, "label": "3"}, ...]
    # Analytics fields are stored at save time; identification graders still live-compute them.
    set_class_prime: Optional[str] = None
    set_class_forte: Optional[str] = None
    set_class_normal: Optional[str] = None
    set_class_set: Optional[str] = None
    spacing: Optional[str] = None
    interval_specific: Optional[str] = None
    interval_generic: Optional[str] = None

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
    is_target: bool = False  # set at request time by targeting layer

class GradingSlice(BaseModel):
    offset: float
    target_midi_pitches: List[int]
    rhythmic_flexibility: bool = False

class VoiceCountPolicy(BaseModel):
    expected: Optional[int] = Field(default=None, ge=0)
    min: int = Field(default=3, ge=0)
    max: Optional[int] = Field(default=4, ge=0)

    @model_validator(mode="after")
    def validate_range(self):
        if self.max is not None and self.max < self.min:
            raise ValueError("max must be greater than or equal to min")
        return self

class HarmonizationTargetPolicy(BaseModel):
    source: Literal["figured_bass", "roman", "analysis_slice"] = "figured_bass"
    written_spelling_required: bool = False
    midi_uses_pitch_class: bool = True

class Metadata(BaseModel):
    exercise_id: str
    source: str # e.g. "Bach Chorale BWV 269", "Sonata K.331"
    key: str # e.g. "G Major", "c minor"
    meter: Optional[str] = None # e.g. "4/4", "3/4"; None = free/open (no time signature)
    barline_offsets: List[float] = Field(default_factory=list)  # explicit chordal barlines (quarter-lengths, on chord onsets, excludes 0.0 and stream end)
    clef: str = "treble" # "treble", "bass", "alto", "tenor"
    complexity_score: int = Field(ge=1, le=20, description="Curriculum unit ranking (1-20)")
    mode: InteractionMode = InteractionMode.PLAYBACK
    is_umto: bool = True
    input_mode: Literal["dropdown", "text"] = "dropdown"
    score_kind: Literal["voices", "chordal"] = "voices"
    analysis_review_status: Literal["none", "generated", "reviewed"] = "none"
    unit: Optional[int] = None
    locked_voices: List[VoiceName] = Field(default_factory=lambda: ["B"])
    voice_count_policy: VoiceCountPolicy = Field(default_factory=VoiceCountPolicy)
    harmonization_target_policy: HarmonizationTargetPolicy = Field(
        default_factory=HarmonizationTargetPolicy
    )
    chord_settle_ms: int = 150
    release_grace_ms: int = 120
    max_voice_displacement: int = 4

    @model_validator(mode="after")
    def _meter_required_for_voices(self):
        if self.score_kind == "voices" and not self.meter:
            raise ValueError("meter is required for voices-kind scores")
        return self

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
    voices: Voices = Field(default_factory=Voices)
    chords: List[ChordEvent] = Field(default_factory=list)
    analysis: List[AnalysisSlice] = Field(default_factory=list)
    grading: List[GradingSlice] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_score_kind(self):
        if self.metadata.score_kind == "chordal":
            if not self.chords:
                raise ValueError("score_kind 'chordal' requires non-empty chords")
        else:  # "voices"
            if "voices" not in self.model_fields_set:
                raise ValueError("score_kind 'voices' requires an explicit voices field")
        return self

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

    def to_frontend_payload(self, unit: Optional[int] = None, analysis_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a payload ready for the ExerciseDefinition JS parser.
        """
        if analysis_type is None:
            analysis_type = "note_name" if self.metadata.complexity_score == 1 else "roman"
        return {
            "type": "umto_chorale",
            "isUMTO": True,
            "mode": self.metadata.mode.value if hasattr(self.metadata.mode, 'value') else self.metadata.mode,
            "staffDistribution": self.metadata.clef,
            "complexity_score": self.metadata.complexity_score,
            "exerciseId": self.metadata.exercise_id,
            "key": self.metadata.key,
            "meter": self.metadata.meter,
            "clef": self.metadata.clef,
            "semibrevesPerLine": 4,
            "analysisType": analysis_type,
            "introText": self.metadata.source,
            "reviewText": "Well done!",
            "inputMode": self.metadata.input_mode,
            "allowed_answers": self.get_allowed_answers(unit),
            "score": {
                "meta": {
                    "key": self.metadata.key, 
                    "time": self.metadata.meter, 
                    "clef": self.metadata.clef,
                    "staffDistribution": self.metadata.clef
                },
                "measures": self._to_legacy_measures(),
                "umto": self.model_dump(mode='json')
            },
            "grading": [s.model_dump(mode='json') for s in self.grading]
        }

    def _to_legacy_measures(self) -> List[Dict[str, Any]]:
        """
        Converts UMTO voices into measure-based structures for the legacy VexFlow adapter.
        Splits events across measures based on the meter.
        """
        import math
        try:
            num, denom = map(int, self.metadata.meter.split("/"))
            num_beats = num * (4.0 / denom)  # quarter-lengths per measure
            # e.g. 4/4 → 4.0, 3/4 → 3.0, 2/2 → 4.0, 6/8 → 3.0
        except Exception:
            num_beats = 4.0
        
        staff_mode = self.metadata.clef # "treble", "bass", or "keyboard"
        
        # 1. Collect all events per voice with their absolute timeline
        voice_streams = {}
        for vid in ["S", "A", "T", "B"]:
            events = getattr(self.voices, vid)
            if not events: continue
            
            if staff_mode in ["treble", "bass"]:
                target_staff = staff_mode
                # Treble mode: S→0, A→1; Bass mode: T→0, B→1 (matches SATB_MAP in vexflow_adapter)
                v_idx = {"S": 0, "A": 1, "T": 0, "B": 1}[vid]
            else:
                target_staff = "treble" if vid in ["S", "A"] else "bass"
                v_idx = 0 if vid in ["S", "T"] else 1
            
            key = (target_staff, v_idx)
            if key not in voice_streams: voice_streams[key] = []
            
            t = 0.0
            for ev in events:
                voice_streams[key].append((t, ev))
                t += ev.duration

        # 2. Determine max duration
        max_t = 0.0
        for stream in voice_streams.values():
            if stream:
                last_start, last_ev = stream[-1]
                max_t = max(max_t, last_start + last_ev.duration)
        
        num_measures = math.ceil((max_t - 0.001) / num_beats)
        if num_measures < 1: num_measures = 1
        
        measures = []
        for m_idx in range(num_measures):
            m_start = m_idx * num_beats
            m_end = (m_idx + 1) * num_beats
            measure = {
                "staves": {
                    "treble": {"clef": "treble", "voices": []},
                    "bass": {"clef": "bass", "voices": []}
                }
            }
            for (staff_name, v_idx), stream in voice_streams.items():
                items = []
                for t, ev in stream:
                    # Does this event fall (even partially) in this measure?
                    ev_end = t + ev.duration
                    if ev_end <= m_start + 0.001 or t >= m_end - 0.001: continue
                    
                    # If it starts in this measure, add it.
                    if t >= m_start - 0.001 and t < m_end - 0.001:
                        if ev.kind == "note" and ev.pitch:
                            items.append({
                                "kind": "note",
                                "pitch": {"step": ev.pitch.step, "alter": ev.pitch.alter, "octave": ev.pitch.octave},
                                "duration": {"type": ev.duration_type, "dots": ev.dots}
                            })
                        else:
                            items.append({
                                "kind": "rest",
                                "duration": {"type": ev.duration_type, "dots": ev.dots}
                            })
                    # Note: We don't handle ties/splitting across measures here yet, 
                    # as Unit 1 exercises are designed to fit measure boundaries.
                
                if items:
                    voice_list = measure["staves"][staff_name]["voices"]
                    while len(voice_list) <= v_idx:
                        voice_list.append({"items": [], "direction": "auto"})
                    voice_list[v_idx]["items"] = items
            measures.append(measure)
        return measures
        return measures

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
