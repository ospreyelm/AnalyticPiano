#!/usr/bin/env python3
"""
Fetch Bach chorales from the music21 corpus and export each as:
- score (Canonical Internal Representation - CIR)
- events (grading timeline: newOnsets vs holdsFromPrevious)

Outputs JSON files under data/corpus/bach/

Usage (from repo root):
  # ensure venv active and music21 installed
  # pip install music21
  python scripts/fetch_bach_chorales.py --limit 10

Notes:
- We collapse SATB into two staves (treble: S/A, bass: T/B) with two voices per staff.
- We support common durations (w,h,q,8,16) with dotted variants (1 dot) for v1.
- Ties: only the tie start produces a new onset; continuations are treated as holds.
"""

import argparse
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# music21 is optional at repo level; install in your venv for development use only
try:
    from music21 import corpus, stream, note, chord, meter, key
except Exception as e:
    corpus = None

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(REPO_ROOT, "data", "corpus", "bach")
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
    # round to nearest 1/16th to avoid float noise
    rq = round(ql * 16) / 16.0
    # exact match first
    for base, (t, d) in DurationMap:
        if abs(rq - base) < 1e-6:
            return t, d
    # fallback: choose closest
    closest = min(DurationMap, key=lambda x: abs(rq - x[0]))
    return closest[1]


def pitch_to_obj(p) -> Dict:
    # music21 pitch: step (A..G), accidental.alter if present, octave
    step = p.step
    alter = 0
    if p.accidental is not None and p.accidental.alter is not None:
        alter = int(p.accidental.alter)
    return {"step": step, "alter": alter, "octave": int(p.octave)}


@dataclass
class Event:
    start: int  # ticks
    perStaff: Dict[str, Dict[str, List[int]]]  # staff -> {newOnsets, holdsFromPrevious}


def build_events(cir: Dict) -> List[Event]:
    # Collect onsets with MIDI numbers per staff voice
    # We'll compute absolute positions in quarter lengths using measure index and a simple 4/4 default unless provided.
    # CIR doesn’t encode offsets; however, we can infer from durations sequentially inside a measure/voice.
    meta_time = cir.get("meta", {}).get("time", "4/4")
    num, den = [int(x) for x in (meta_time.split("/") if meta_time else [4, 4])]
    ql_per_measure = num * (4 / den)

    # Build per staff voice sequences of (startQL, durQL, midi, tieStart)
    staff_voice_sequences: Dict[Tuple[str, int], List[Tuple[float, float, int, bool]]] = {}

    measure_start_ql = 0.0
    for meas in cir.get("measures", []):
        staves = meas["staves"]
        for staff_id, staff in staves.items():
            voices = staff.get("voices", [])
            for vindex, voice in enumerate(voices):
                seq = staff_voice_sequences.setdefault((staff_id, vindex), [])
                t = measure_start_ql
                for item in voice.get("items", []):
                    dt_type = item["duration"]["type"]
                    dots = item["duration"].get("dots", 0)
                    # reverse map duration type to quarterLength
                    ql = {
                        "w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25
                    }.get(dt_type, 1.0)
                    if dots == 1:
                        ql *= 1.5
                    elif dots == 2:
                        ql *= 1.75  # rough; rarely used here

                    if item["kind"] == "rest":
                        t += ql
                        continue

                    if item["kind"] == "note":
                        midi = step_alter_octave_to_midi(
                            item["pitch"]["step"], item["pitch"]["alter"], item["pitch"]["octave"]
                        )
                        tie_start = bool(item.get("tie", {}).get("start"))
                        tie_stop = bool(item.get("tie", {}).get("stop"))
                        seq.append((t, ql, midi, tie_start))
                        t += ql
                    elif item["kind"] == "chord":
                        tie_start = bool(item.get("tie", {}).get("start"))
                        for n in item.get("notes", []):
                            midi = step_alter_octave_to_midi(
                                n["pitch"]["step"], n["pitch"]["alter"], n["pitch"]["octave"]
                            )
                            seq.append((t, ql, midi, tie_start))
                        t += ql
                # end items
        measure_start_ql += ql_per_measure

    # Collect unique onset times across all sequences
    onsets = sorted({start for seq in staff_voice_sequences.values() for (start, ql, midi, tie) in seq})

    # Track active holds per staff across events
    events: List[Event] = []
    active_by_staff: Dict[str, List[int]] = {"treble": [], "bass": []}

    for onset in onsets:
        start_ticks = int(round(onset * PPQ))
        perStaff = {"treble": {"newOnsets": [], "holdsFromPrevious": list(active_by_staff["treble"])},
                    "bass":   {"newOnsets": [], "holdsFromPrevious": list(active_by_staff["bass"])}}
        # find notes that start exactly at this onset; add as newOnsets and into active set (simplified: no release timing here)
        for (staff_id, vindex), seq in staff_voice_sequences.items():
            for (s, d, midi, tie_start) in seq:
                if abs(s - onset) < 1e-6:
                    # new onset only if not continuation of tie (CIR marks start only; safe)
                    perStaff[staff_id]["newOnsets"].append(midi)
                    if midi not in active_by_staff[staff_id]:
                        active_by_staff[staff_id].append(midi)
        # Dedup & sort
        for sid in ("treble", "bass"):
            perStaff[sid]["newOnsets"] = sorted(list(set(perStaff[sid]["newOnsets"])))
            perStaff[sid]["holdsFromPrevious"] = sorted(list(set(perStaff[sid]["holdsFromPrevious"])))
        events.append(Event(start=start_ticks, perStaff=perStaff))

    return events


def step_alter_octave_to_midi(step: str, alter: int, octave: int) -> int:
    step_to_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    pc = step_to_pc[step.upper()] + int(alter)
    midi = (octave + 1) * 12 + pc
    return midi


def compute_total_ql(items: List[Dict]) -> float:
    """Compute total quarterLength of a voice's items."""
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
    """Pad a voice with rests if it's shorter than target duration.
    VexFlow 4.x can handle pickup measures naturally, so we skip padding for first measure.
    For other measures, append rests to fill."""
    current_ql = compute_total_ql(items)
    if current_ql >= target_ql - 0.01:  # allow small rounding error
        return items
    
    # VexFlow 4.x handles pickup measures (anacrusis) naturally - don't pad the first measure
    if is_first_measure:
        return items
    
    # Add rests to fill the gap for non-first measures
    gap = target_ql - current_ql
    rests = []
    
    # Use largest possible rest values
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
    
    # Append rests to end of non-first measures
    return list(items) + rests


def m21_to_cir(s: stream.Score) -> Dict:
    # Assume 4/4 if missing
    ts = s.recurse().getElementsByClass(meter.TimeSignature).first()
    time_str = f"{ts.numerator}/{ts.denominator}" if ts else "4/4"
    num, den = [int(x) for x in time_str.split("/")]
    target_ql_per_measure = num * (4.0 / den)
    
    ks = s.recurse().getElementsByClass(key.KeySignature).first()
    vex_key = None
    if ks is not None:
        # music21: sharps positive, flats negative. We'll translate to VexFlow-like triad (e.g., "C", "G", "F").
        try:
            vex_key = ks.asKey().tonic.name.replace("-", "b")
            if ks.mode:
                # VexFlow expects a string like "C" or "Cm"; keep major only for now
                if ks.mode.lower().startswith("minor"):
                    vex_key = vex_key + "m"
        except Exception:
            pass

    # Parts to staves: S,A -> treble; T,B -> bass
    parts = list(s.parts)

    def role_from_name(p: stream.Part) -> Optional[str]:
        """Infer SATB role from part/long name when available."""
        try:
            name = str(p.partName or p.partAbbreviation or p.id or "").lower()
        except Exception:
            name = str(getattr(p, 'id', '') or '').lower()
        # common variants
        if any(k in name for k in ["sopr", "sopran", "cantus", "discant"]):
            return 'S'
        if any(k in name for k in ["alto", "altus"]):
            return 'A'
        if any(k in name for k in ["tenor", "ten.", "ten "]):
            return 'T'
        if any(k in name for k in ["bass", "basso", "bassus"]):
            return 'B'
        return None

    def mean_midi_for_part(p: stream.Part) -> float:
        """Rough pitch center for the part to help classify roles when names are missing/misordered."""
        try:
            mids = []
            for n in p.recurse().notes[:200]:
                if isinstance(n, note.Note):
                    mids.append(step_alter_octave_to_midi(n.pitch.step, int(n.pitch.accidental.alter) if n.pitch.accidental and n.pitch.accidental.alter is not None else 0, int(n.pitch.octave)))
                elif isinstance(n, chord.Chord):
                    # take chord's lowest note for voice center
                    m = min(step_alter_octave_to_midi(nn.pitch.step, int(nn.pitch.accidental.alter) if nn.pitch.accidental and nn.pitch.accidental.alter is not None else 0, int(nn.pitch.octave)) for nn in n.notes)
                    mids.append(m)
            return sum(mids) / len(mids) if mids else 0.0
        except Exception:
            return 0.0

    # Build role map using names first
    role_map: Dict[str, stream.Part] = {}
    unnamed_parts = []
    for p in parts:
        r = role_from_name(p)
        if r and r not in role_map:
            role_map[r] = p
        else:
            unnamed_parts.append(p)

    # Fill remaining roles by pitch center ordering (high->S, then A, then T, then B)
    remaining_roles = [r for r in ['S','A','T','B'] if r not in role_map]
    if remaining_roles and unnamed_parts:
        by_pitch = sorted([(mean_midi_for_part(p), p) for p in unnamed_parts], key=lambda x: x[0], reverse=True)
        for role, (_, part_obj) in zip(remaining_roles, by_pitch):
            role_map[role] = part_obj

    # Fallback: if still missing, fall back to original order but warn via tags/meta (not printed here)
    treble_parts = [role_map.get('S', parts[0] if parts else None), role_map.get('A', parts[1] if len(parts) > 1 else None)]
    bass_parts = [role_map.get('T', parts[2] if len(parts) > 2 else None), role_map.get('B', parts[3] if len(parts) > 3 else None)]
    treble_parts = [p for p in treble_parts if p is not None]
    bass_parts = [p for p in bass_parts if p is not None]
    
    # Special case: if we only have 2 parts and they're both on treble, distribute them
    if len(parts) == 2 and len(treble_parts) == 2 and len(bass_parts) == 0:
        # Move the lower voice to bass staff
        bass_parts = [treble_parts[1]]
        treble_parts = [treble_parts[0]]

    measures = []
    # Align measures by index
    max_measures = max(len(p.getElementsByClass(stream.Part).measures(0, None) or p.getElementsByClass(stream.Measure)) if hasattr(p, 'getElementsByClass') else 0 for p in parts) if parts else 0
    # Simpler: iterate measures per part and zip by index
    by_index: Dict[int, Dict[str, List[stream.Measure]]] = {}
    for p in parts:
        for i, m in enumerate(p.getElementsByClass(stream.Measure)):
            by_index.setdefault(i+1, {}).setdefault(p.id or str(id(p)), []).append(m)

    # Instead, use .parts measures directly by index count
    part_measures: List[List[stream.Measure]] = []
    for p in parts:
        part_measures.append(list(p.getElementsByClass(stream.Measure)))
    max_len = max((len(x) for x in part_measures), default=0)

    for mi in range(max_len):
        treble_voices = []
        bass_voices = []

        def part_to_voice(part_obj: stream.Part) -> List[Dict]:
            # Return items for this measure index
            items: List[Dict] = []
            if mi >= len(list(part_obj.getElementsByClass(stream.Measure))):
                return items
            m: stream.Measure = list(part_obj.getElementsByClass(stream.Measure))[mi]
            # Flatten measure contents in time order
            offset = 0.0
            for el in m.flat:
                if isinstance(el, note.Rest):
                    t, d = el.offset, el.quarterLength
                    dt, dots = ql_to_type_dots(d)
                    items.append({"kind": "rest", "duration": {"type": dt, "dots": dots}})
                elif isinstance(el, note.Note):
                    dt, dots = ql_to_type_dots(el.quarterLength)
                    tie = el.tie.type if el.tie else None
                    item = {
                        "kind": "note",
                        "pitch": pitch_to_obj(el.pitch),
                        "duration": {"type": dt, "dots": dots},
                    }
                    if tie in ("start", "continue"):
                        item["tie"] = {"start": True}
                    if tie in ("stop", "continue"):
                        item.setdefault("tie", {})["stop"] = True
                    items.append(item)
                elif isinstance(el, chord.Chord):
                    dt, dots = ql_to_type_dots(el.quarterLength)
                    ch = {"kind": "chord", "notes": [], "duration": {"type": dt, "dots": dots}}
                    tie_any = False
                    for n in el.notes:
                        tie = n.tie.type if n.tie else None
                        nobj = {"pitch": pitch_to_obj(n.pitch)}
                        ch["notes"].append(nobj)
                        if tie in ("start", "continue"):
                            ch.setdefault("tie", {})["start"] = True
                            tie_any = True
                        if tie in ("stop", "continue"):
                            ch.setdefault("tie", {})["stop"] = True
                            tie_any = True
                    items.append(ch)
            return items

        # Build voices for treble (two parts if present) - PAD TO MEASURE DURATION
        # For pickup measure (mi == 0), prepend rests; otherwise append
        is_first = (mi == 0)
        if len(treble_parts) >= 1:
            v_items = part_to_voice(treble_parts[0])
            v_items = pad_voice_to_duration(v_items, target_ql_per_measure, is_first)
            treble_voices.append({"direction": VOICE_DIRECTIONS["treble"][0], "items": v_items})
        if len(treble_parts) >= 2:
            v_items = part_to_voice(treble_parts[1])
            v_items = pad_voice_to_duration(v_items, target_ql_per_measure, is_first)
            treble_voices.append({"direction": VOICE_DIRECTIONS["treble"][1], "items": v_items})
        # Build voices for bass - PAD TO MEASURE DURATION
        if len(bass_parts) >= 1:
            v_items = part_to_voice(bass_parts[0])
            v_items = pad_voice_to_duration(v_items, target_ql_per_measure, is_first)
            bass_voices.append({"direction": VOICE_DIRECTIONS["bass"][0], "items": v_items})
        if len(bass_parts) >= 2:
            v_items = part_to_voice(bass_parts[1])
            v_items = pad_voice_to_duration(v_items, target_ql_per_measure, is_first)
            bass_voices.append({"direction": VOICE_DIRECTIONS["bass"][1], "items": v_items})

        measures.append({
            "number": mi + 1,
            "staves": {
                "treble": {"clef": "treble", "voices": treble_voices},
                "bass": {"clef": "bass", "voices": bass_voices},
            },
        })

    cir = {"meta": {"key": vex_key, "time": time_str}, "measures": measures}
    return cir


def export_chorale(identifier: str, s: stream.Score, out_dir: str) -> Optional[str]:
    cir = m21_to_cir(s)
    events = [e.__dict__ for e in build_events(cir)]
    payload = {
        "source": {"type": "musicxml-corpus", "corpusId": "music21-bach-chorales", "workId": identifier},
        "score": cir,
        "events": events,
        "tags": ["corpus:bach-chorales", "chorale", "polyphonic", "4-part"],
    }
    out_path = os.path.join(out_dir, f"{identifier.replace('/', '_')}.json")
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="max chorales to export")
    args = parser.parse_args()

    if corpus is None:
        raise SystemExit("music21 is not installed. Activate your venv and pip install music21.")

    os.makedirs(OUT_DIR, exist_ok=True)

    exported = 0
    # Use music21's chorales bundle directly; parse each via the bundle path
    try:
        # Get all bach chorales via the corpus search
        from music21 import corpus as m21corpus
        bundle = m21corpus.corpora.CoreCorpus().search('bach', fileExtensions='xml')
        
        for work in bundle:
            if exported >= args.limit:
                break
            try:
                # Parse via the corpus work reference
                sc = work.parse()
                if not isinstance(sc, stream.Score):
                    # some entries may be parts; try to get score
                    try:
                        sc = sc.score
                    except Exception:
                        continue
                
                # Get a clean identifier from the filename
                filename = os.path.basename(work.sourcePath or work.corpusFilepath or "chorale")
                ident = filename.replace(".xml", "").replace(".mxl", "").replace(".musicxml", "")
                
                path = export_chorale(ident, sc, OUT_DIR)
                exported += 1
                print(f"Exported {ident} -> {path}")
            except Exception as e:
                print(f"Skipping {work}: {e}")
                continue
                
    except Exception as e:
        print(f"Error accessing corpus: {e}")
        # Fallback: try direct bach/bwv paths
        for i in range(1, 100):
            if exported >= args.limit:
                break
            try:
                bwv = f"bwv{i:03d}.{i}.mxl"
                sc = corpus.parse(f"bach/{bwv}")
                ident = f"bwv{i:03d}_{i}"
                path = export_chorale(ident, sc, OUT_DIR)
                exported += 1
                print(f"Exported {ident} -> {path}")
            except Exception:
                continue

    print(f"Done. Exported {exported} chorales to {OUT_DIR}")


if __name__ == "__main__":
    main()
