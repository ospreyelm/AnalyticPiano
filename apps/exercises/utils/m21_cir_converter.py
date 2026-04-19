import os
import json
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    from music21 import corpus, stream, note, chord, meter, key
except ImportError:
    corpus = None

PPQ = 480  # ticks per quarter for event timing

DurationMap = [
    (4.0, ("w", 0)),  # whole
    (3.0, ("h", 1)),  # dotted half
    (2.0, ("h", 0)),  # half
    (1.5, ("q", 1)),  # dotted quarter
    (1.0, ("q", 0)),  # quarter
    (0.75, ("8", 1)), # dotted eighth
    (0.5, ("8", 0)),  # eighth
    (0.375, ("16", 1)), # dotted sixteenth
    (0.25, ("16", 0)), # sixteenth
]

VOICE_DIRECTIONS = {
    "treble": ["up", "down"],  # S up, A down
    "bass": ["up", "down"],    # T up, B down
}

def ql_to_type_dots(ql: float) -> Tuple[str, int]:
    rq = round(ql * 16) / 16.0
    for base, (t, d) in DurationMap:
        if abs(rq - base) < 1e-6:
            return t, d
    closest = min(DurationMap, key=lambda x: abs(rq - x[0]))
    return closest[1]

def pitch_to_obj(p) -> Dict:
    step = p.step
    alter = 0
    if p.accidental is not None and p.accidental.alter is not None:
        alter = int(p.accidental.alter)
    return {
        "step": step, 
        "alter": alter, 
        "octave": int(p.octave),
        "midi": int(p.midi)
    }

def step_alter_octave_to_midi(step: str, alter: int, octave: int) -> int:
    step_to_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    pc = step_to_pc[step.upper()] + int(alter)
    midi = (octave + 1) * 12 + pc
    return midi

def compute_total_ql(items: List[Dict]) -> float:
    total = 0.0
    for item in items:
        dt = item["duration"]["type"]
        dots = item["duration"].get("dots", 0)
        ql = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25}.get(dt, 1.0)
        if dots == 1:
            ql *= 1.5
        elif dots == 2:
            ql *= 1.75
        total += ql
    return total

def pad_voice_to_duration(items: List[Dict], target_ql: float, is_first_measure: bool = False) -> List[Dict]:
    current_ql = compute_total_ql(items)
    if current_ql >= target_ql - 0.01:
        return items
    if is_first_measure:
        return items
    gap = target_ql - current_ql
    rests = []
    while gap > 0.01:
        if gap >= 4.0:
            rest_type, dots = "w", 0
            rest_ql = 4.0
        elif gap >= 3.0:
            rest_type, dots = "h", 1
            rest_ql = 3.0
        elif gap >= 2.0:
            rest_type, dots = "h", 0
            rest_ql = 2.0
        elif gap >= 1.5:
            rest_type, dots = "q", 1
            rest_ql = 1.5
        elif gap >= 1.0:
            rest_type, dots = "q", 0
            rest_ql = 1.0
        elif gap >= 0.75:
            rest_type, dots = "8", 1
            rest_ql = 0.75
        elif gap >= 0.5:
            rest_type, dots = "8", 0
            rest_ql = 0.5
        elif gap >= 0.375:
            rest_type, dots = "16", 1
            rest_ql = 0.375
        else:
            rest_type, dots = "16", 0
            rest_ql = 0.25
        rests.append({"kind": "rest", "duration": {"type": rest_type, "dots": dots}})
        gap -= rest_ql
    return list(items) + rests

def pad_voice_to_duration(items: List[Dict], target_ql: float, is_first: bool = False) -> List[Dict]:
    """Ensures a voice fills the measure's total duration by adding rests if needed."""
    if not items:
        # Full measure of rest
        dt, dots = ql_to_type_dots(target_ql)
        return [{"kind": "rest", "duration": {"type": dt, "dots": dots}}]
    
    current_ql = 0.0
    for item in items:
        # Calculate duration of this item
        # Simplified: map type back to float for calculation
        rev_map = { t: d for d, (t, dots) in DurationMap }
        # Note: this is a shorthand, in production we'd use a more robust QL tracker
        # but since we just generated these items, we'll approximate.
        # Better: track QL in the part_to_voice loop.
        pass # We'll fix this properly in the implementation below
    
    # We'll use a more robust approach: the part_to_voice loop already knows the QL.
    return items

def m21_to_cir(s: stream.Score, key_override: Optional[str] = None) -> Dict:
    # Explicitly calculate beams based on time signature rules
    try:
        s.makeBeams(inPlace=True)
    except Exception:
        pass

    ts = s.recurse().getElementsByClass(meter.TimeSignature).first()
    time_str = f"{ts.numerator}/{ts.denominator}" if ts else "4/4"
    num, den = [int(x) for x in time_str.split("/")]
    target_ql_per_measure = num * (4.0 / den)
    
    vex_key = None
    if key_override:
        # HarmonyLab keys like 'iG_', 'jC_'
        # Convert to VexFlow style: Gm, C
        if key_override.startswith('i'):
            # minor
            vex_key = key_override[1:].replace('_', '') + 'm'
        elif key_override.startswith('j'):
            # major
            vex_key = key_override[1:].replace('_', '')
        else:
            # Fallback for plain 'Gm' or 'C'
            vex_key = key_override
    else:
        ks = s.recurse().getElementsByClass(key.KeySignature).first()
        if ks is not None:
            try:
                vex_key = ks.asKey().tonic.name.replace("-", "b")
                if ks.mode:
                    if ks.mode.lower().startswith("minor"):
                        vex_key = vex_key + "m"
            except Exception:
                pass

    # ALIGNMENT FIX: Shift ALL offsets so the exercise starts at global offset 0.
    lowest = s.lowestOffset
    if lowest != 0:
        for el in s.elements:
            el.offset -= lowest
    
    parts = list(s.parts)

    def role_from_name(p: stream.Part) -> Optional[str]:
        try:
            name = str(p.partName or p.partAbbreviation or p.id or "").lower()
        except Exception:
            name = str(getattr(p, 'id', '') or '').lower()
        if any(k in name for k in ["sopr", "sopran", "cantus", "discant"]): return 'S'
        if any(k in name for k in ["alto", "altus"]): return 'A'
        if any(k in name for k in ["tenor", "ten.", "ten "]): return 'T'
        if any(k in name for k in ["bass", "basso", "bassus"]): return 'B'
        return None

    def mean_midi_for_part(p: stream.Part) -> float:
        try:
            mids = []
            for n in p.recurse().notes[:200]:
                if isinstance(n, note.Note):
                    mids.append(step_alter_octave_to_midi(n.pitch.step, int(n.pitch.accidental.alter) if n.pitch.accidental and n.pitch.accidental.alter is not None else 0, int(n.pitch.octave)))
                elif isinstance(n, chord.Chord):
                    m = min(step_alter_octave_to_midi(nn.pitch.step, int(nn.pitch.accidental.alter) if nn.pitch.accidental and nn.pitch.accidental.alter is not None else 0, int(nn.pitch.octave)) for nn in n.notes)
                    mids.append(m)
            return sum(mids) / len(mids) if mids else 0.0
        except Exception:
            return 0.0

    role_map: Dict[str, stream.Part] = {}
    unnamed_parts = []
    for p in parts:
        r = role_from_name(p)
        if r and r not in role_map:
            role_map[r] = p
        else:
            unnamed_parts.append(p)

    remaining_roles = [r for r in ['S','A','T','B'] if r not in role_map]
    if remaining_roles and unnamed_parts:
        by_pitch = sorted([(mean_midi_for_part(p), p) for p in unnamed_parts], key=lambda x: x[0], reverse=True)
        for role, (_, part_obj) in zip(remaining_roles, by_pitch):
            role_map[role] = part_obj

    treble_parts = [role_map.get('S', parts[0] if parts else None), role_map.get('A', parts[1] if len(parts) > 1 else None)]
    bass_parts = [role_map.get('T', parts[2] if len(parts) > 2 else None), role_map.get('B', parts[3] if len(parts) > 3 else None)]
    treble_parts = [p for p in treble_parts if p is not None]
    bass_parts = [p for p in bass_parts if p is not None]
    
    if len(parts) == 2 and len(treble_parts) == 2 and len(bass_parts) == 0:
        bass_parts = [treble_parts[1]]
        treble_parts = [treble_parts[0]]

    part_measures: List[List[stream.Measure]] = []
    for p in parts:
        part_measures.append(list(p.getElementsByClass(stream.Measure)))
    max_len = max((len(x) for x in part_measures), default=0)

    measures = []
    for mi in range(max_len):
        treble_voices = []
        bass_voices = []

        def part_to_voice(part_obj: stream.Part) -> Tuple[List[Dict], float]:
            items: List[Dict] = []
            total_ql = 0.0
            ms = list(part_obj.getElementsByClass(stream.Measure))
            if mi >= len(ms):
                return items, 0.0
            m = ms[mi]
            for el in m.flat:
                if isinstance(el, note.Rest):
                    dt, dots = ql_to_type_dots(el.quarterLength)
                    items.append({"kind": "rest", "duration": {"type": dt, "dots": dots}})
                    total_ql += el.quarterLength
                elif isinstance(el, note.Note):
                    dt, dots = ql_to_type_dots(el.quarterLength)
                    tie = el.tie.type if el.tie else None
                    item = {"kind": "note", "pitch": pitch_to_obj(el.pitch), "duration": {"type": dt, "dots": dots}}
                    if tie in ("start", "continue"): item["tie"] = {"start": True}
                    if tie in ("stop", "continue"): item.setdefault("tie", {})["stop"] = True
                    items.append(item)
                    total_ql += el.quarterLength
                elif isinstance(el, chord.Chord):
                    dt, dots = ql_to_type_dots(el.quarterLength)
                    ch = {"kind": "chord", "notes": [], "duration": {"type": dt, "dots": dots}}
                    for n in el.notes:
                        tie = n.tie.type if n.tie else None
                        nobj = {"pitch": pitch_to_obj(n.pitch)}
                        ch["notes"].append(nobj)
                        if tie in ("start", "continue"): ch.setdefault("tie", {})["start"] = True
                        if tie in ("stop", "continue"): ch.setdefault("tie", {})["stop"] = True
                    items.append(ch)
                    total_ql += el.quarterLength
            return items, total_ql

        def pad_items(items, current_ql, target_ql, is_first_m=False):
            # NO PADDING ON FIRST MEASURE: Avoid "padded rests" after the music in upbeat/anacrusis starts.
            if is_first_m:
                return items
            if current_ql < target_ql - 0.01:
                diff = target_ql - current_ql
                dt, dots = ql_to_type_dots(diff)
                items.append({"kind": "rest", "duration": {"type": dt, "dots": dots}})
            return items

        is_first_m = (mi == 0)
        if len(treble_parts) >= 1:
            v_items, v_ql = part_to_voice(treble_parts[0])
            v_items = pad_items(v_items, v_ql, target_ql_per_measure, is_first_m)
            treble_voices.append({"direction": VOICE_DIRECTIONS["treble"][0], "items": v_items})
        if len(treble_parts) >= 2:
            v_items, v_ql = part_to_voice(treble_parts[1])
            v_items = pad_items(v_items, v_ql, target_ql_per_measure, is_first_m)
            treble_voices.append({"direction": VOICE_DIRECTIONS["treble"][1], "items": v_items})
        if len(bass_parts) >= 1:
            v_items, v_ql = part_to_voice(bass_parts[0])
            v_items = pad_items(v_items, v_ql, target_ql_per_measure, is_first_m)
            bass_voices.append({"direction": VOICE_DIRECTIONS["bass"][0], "items": v_items})
        if len(bass_parts) >= 2:
            v_items, v_ql = part_to_voice(bass_parts[1])
            v_items = pad_items(v_items, v_ql, target_ql_per_measure, is_first_m)
            bass_voices.append({"direction": VOICE_DIRECTIONS["bass"][1], "items": v_items})

        measures.append({
            "number": mi + 1,
            "staves": {
                "treble": {"clef": "treble", "voices": treble_voices},
                "bass": {"clef": "bass", "voices": bass_voices},
            },
        })

    # Generate Legacy 'chord' flat list for engine compatibility (transposition, grading)
    flat_chord_list = []
    try:
        # Use chordify to get all concurrent events as a single stream
        cf = s.chordify()
        for c in cf.recurse().getElementsByClass('Chord'):
            # Extract MIDI numbers
            pitches = [p.midi for p in c.pitches]
            flat_chord_list.append({
                "visible": sorted(pitches),
                "hidden": []
            })
    except Exception as e:
        # Fallback if chordify fails (unlikely for chorales)
        pass

    return {
        "meta": {"key": vex_key, "time": time_str}, 
        "measures": measures,
        "chord": flat_chord_list
    }
