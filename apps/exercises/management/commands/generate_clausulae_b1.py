"""Generate Branch B Units B1–B4 and B11–B12: clausulae and cadence exercises.

B1  — individual clausulae (one voice)
B2  — simple 2-voice cadences (Discant + Tenor variants)
B3  — simple 3-voice cadences (Bass + upper pair)
B4  — simple 4-voice cadences (Bass + Alto + Tenor + Discant)
B11 — compound 2-voice cadences (Discant τ=1 + Tenor τ=0)
B12 — compound 3-voice (bass τ=0 + upper pair) and 4-voice compound

Clausula triples in Z₇ (Do=0 … Ti=6):
  Discant:    (0, 6, 0)   Do–Ti–Do
  Tenor var0: (0, 1, 0)   Do–Re–Do
  Tenor var1: (0, 1, 2)   Do–Re–Mi
  Tenor var2: (2, 1, 0)   Mi–Re–Do
  Tenor var3: (2, 1, 2)   Mi–Re–Mi
  Alto var0:  (4, 4, 4)   Sol–Sol–Sol
  Alto var1:  (4, 3, 2)   Sol–Fa–Mi
  Alto var2:  (4, 5, 4)   Sol–La–Sol
  Bass:       (0, 4, 0)   Do–Sol–Do

Voice → SATB slot:
  1/2/3-voice: Discant=S, Tenor/Alto=A (treble), Bass=B (bass)
  4-voice:     Discant=S, Alto=A, Tenor=T, Bass=B (keyboard)

Compound rhythm (authentic): ANT=half, PEN=half, ULT=whole in 2/2.
Compound cadence grid: τ=0: off0/off2/off4; τ=1: off1/off3/off4 (whole note ULT).
"""
from __future__ import annotations

import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto import (
    AnalysisLayer,
    AnalysisSlice,
    GradingSlice,
    InteractionMode,
    Metadata,
    Pitch,
    UMTO,
    VoiceEvent,
    Voices,
)

_HERE = os.path.dirname(__file__)
_CLAUSULAE_ROOT = os.path.abspath(os.path.join(_HERE, "../../../../../clausulae-project"))
if _CLAUSULAE_ROOT not in sys.path:
    sys.path.insert(0, _CLAUSULAE_ROOT)

try:
    from clausulae.realize import key_realize
    from clausulae.generate import (
        enumerate_simple,
        enumerate_compound,
        enumerate_compound_3voice,
        enumerate_compound_3voice_double_tau1,
        enumerate_compound_4voice,
    )
    from clausulae.core import CLAUSULAE, CLAUSULA_COLOR, SOLFEGE
    _CLAUSULAE_AVAILABLE = True
except ImportError as _e:
    _CLAUSULAE_AVAILABLE = False
    _CLAUSULAE_IMPORT_ERROR = str(_e)

User = get_user_model()

HL_KEY = {
    "C": "jC_", "G": "jG_", "F": "jF_", "D": "jD_", "Bb": "jBb",
    "A": "jA_", "Eb": "jEb", "E": "jE_", "Ab": "jAb",
}

TARGET_KEYS = ["C", "G", "F"]

TENOR_LABELS = ["Do–Re–Do", "Do–Re–Mi", "Mi–Re–Do", "Mi–Re–Mi"]
ALTO_LABELS  = ["Sol–Sol–Sol", "Sol–Fa–Mi", "Sol–La–Sol"]
SOLFEGE_LABELS = {
    "Discant": ["Do–Ti–Do"],
    "Tenor":   TENOR_LABELS,
    "Alto":    ALTO_LABELS,
    "Bass":    ["Do–Sol–Do"],
}

# Duration: ANT=half, PEN=half, ULT=whole
_DUR_SIMPLE = [("h", 2.0), ("h", 2.0), ("w", 4.0)]

# Compound: τ=0 (early): half/half/whole over 5 beats
# τ=1 (late): qtr-rest, then qtr/qtr/whole — represented as rest+3 notes
_DUR_COMPOUND_EARLY = [("h", 2.0), ("h", 2.0), ("w", 4.0)]
_DUR_COMPOUND_LATE  = [("h", 2.0), ("q", 1.0), ("w", 4.0)]  # after leading rest; ANT=half, PEN=qtr, ULT=whole

# SATB maps for voice slots
_SATB_MAP = {"treble": ["S", "A"], "bass": ["T", "B"]}

# Compact solfège abbreviations for descriptions (fit varchar(60))
_SOL_ABBR = {
    "Do–Ti–Do": "D-T-D", "Do–Re–Do": "D-R-D", "Do–Re–Mi": "D-R-M",
    "Mi–Re–Do": "M-R-D", "Mi–Re–Mi": "M-R-M",
    "Sol–Sol–Sol": "S-S-S", "Sol–Fa–Mi": "S-F-M", "Sol–La–Sol": "S-L-S",
    "Do–Sol–Do": "D-S-D",
}
_NAME_ABBR = {"Discant": "D", "Tenor": "T", "Alto": "A", "Bass": "B"}

def _abbr(sol: str) -> str:
    return _SOL_ABBR.get(sol, sol)

def _vpart(name: str, sol: str) -> str:
    """Short voice:sol token, e.g. 'B:D-S-D'."""
    return f"{_NAME_ABBR.get(name, name[0])}:{_abbr(sol)}"

# Z₇ degree (0=Do … 6=Ti) → circled Arabic numeral (Baroque bass-degree convention)
_CIRCLED = {0: "①", 1: "②", 2: "③", 3: "④", 4: "⑤", 5: "⑥", 6: "⑦"}

def _bass_labels(triple: tuple) -> list[str]:
    """Circled scale-degree label for each position in a bass triple."""
    return [_CIRCLED[z % 7] for z in triple]

def _analysis_labels_from_slots(slots: dict, n_offsets: int = 3) -> list[str]:
    """Circled-degree labels for simple cadence (offsets 0,2,4 = ANT,PEN,ULT)."""
    if "B" in slots:
        _, _, triple = slots["B"]
        labels = _bass_labels(triple)
        return (labels + [""] * n_offsets)[:n_offsets]
    return [""] * n_offsets

def _analysis_labels_compound(bass_triple: tuple) -> list[str]:
    """Circled-degree labels for compound offsets [0,1,2,4]: bass attacks at 0,2,4 only."""
    ant, pen, ult = [_CIRCLED[z % 7] for z in bass_triple]
    return [ant, "", pen, ult]

# Voice slot → octave
_OCTAVE = {"S": 5, "A": 4, "T": 4, "B": 3}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _solfege_label(clausula_name: str, var_idx: int) -> str:
    labels = SOLFEGE_LABELS.get(clausula_name, [])
    return labels[var_idx] if var_idx < len(labels) else str(var_idx)


def _m21_note_to_pitch(n) -> Pitch:
    p = n.pitch
    alter_map = {None: 0, "sharp": 1, "flat": -1, "double-sharp": 2, "double-flat": -2}
    alter = alter_map.get(p.accidental.name if p.accidental else None, 0)
    return Pitch(step=p.step, alter=alter, octave=p.octave, midi=p.midi)


def _realize_events(triple, key: str, voice_id: str,
                    dur_scheme=None) -> list[VoiceEvent]:
    """Realize Z₇ triple → VoiceEvents using given duration scheme."""
    if dur_scheme is None:
        dur_scheme = _DUR_SIMPLE
    notes = key_realize(triple, key, octave=_OCTAVE[voice_id])
    return [
        VoiceEvent(
            kind="note",
            pitch=_m21_note_to_pitch(n),
            duration=ql,
            duration_type=dt,
            dots=0,
            is_target=True,
        )
        for n, (dt, ql) in zip(notes, dur_scheme)
    ]


def _render_voice_colors(voice_events_by_id: dict, color_by_vid: dict) -> dict:
    """Map semantic voice ids → slot-indexed colors matching VexFlow compaction."""
    treble = [v for v in ["S", "A"] if voice_events_by_id.get(v)]
    bass   = [v for v in ["T", "B"] if voice_events_by_id.get(v)]
    result = {}
    for idx, vid in enumerate(treble[:2]):
        result[_SATB_MAP["treble"][idx]] = color_by_vid.get(vid, "#000000")
    for idx, vid in enumerate(bass[:2]):
        result[_SATB_MAP["bass"][idx]] = color_by_vid.get(vid, "#000000")
    return result


def _staff_dist(vids: set) -> str:
    has_bass   = bool(vids & {"T", "B"})
    has_treble = bool(vids & {"S", "A"})
    if has_bass and has_treble:
        return "keyboard"
    return "bass" if has_bass else "treble"


def _grading(voice_events_by_id: dict, offsets: list[float]) -> list[GradingSlice]:
    slices = []
    for offset_i, offset in enumerate(offsets):
        midi = []
        for events in voice_events_by_id.values():
            if offset_i < len(events) and events[offset_i].pitch:
                midi.append(events[offset_i].pitch.midi)
        slices.append(GradingSlice(offset=offset, target_midi_pitches=sorted(midi)))
    return slices


def _build_umto(voice_events_by_id: dict[str, list[VoiceEvent]],
                key: str,
                description: str,
                voice_colors: dict | None = None,
                offsets: list[float] | None = None,
                analysis_labels: list[str] | None = None) -> dict:
    if offsets is None:
        offsets = [0.0, 2.0, 4.0]
    if analysis_labels is None:
        analysis_labels = [""] * len(offsets)
    vids = set(voice_events_by_id.keys())
    staff_dist = _staff_dist(vids)
    hl_key = HL_KEY.get(key, "jC_")

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=description,
            key=hl_key,
            meter="2/2",
            clef=staff_dist,
            complexity_score=1,
            mode=InteractionMode.PLAYBACK,
            input_mode="dropdown",
            unit=None,
        ),
        voices=Voices(
            S=voice_events_by_id.get("S", []),
            A=voice_events_by_id.get("A", []),
            T=voice_events_by_id.get("T", []),
            B=voice_events_by_id.get("B", []),
        ),
        analysis=[
            AnalysisSlice(
                offset=off,
                content=AnalysisLayer(functional_label=label),
                unit_tags=[],
            )
            for off, label in zip(offsets, analysis_labels)
        ],
        grading=_grading(voice_events_by_id, offsets),
    )

    payload = umto.to_frontend_payload(unit=None, analysis_type="clausula")
    payload["staffDistribution"] = staff_dist
    payload["display"] = {
        "showNotation": True,
        "hideKeyLabel": False,
        "showScaleDegrees": True,
        "voiceColors": voice_colors or {},
        "maxMeasures": 3 if max(offsets, default=4) > 4 else 2,
    }
    return payload


def _save_exercise(*, author, description, payload, skill_tags, complexity,
                   is_public, overwrite) -> Exercise:
    ex = Exercise.objects.filter(description=description, authored_by=author).first() if overwrite else None
    if ex is None:
        ex = Exercise(
            description=description, data=payload, authored_by=author,
            is_public=is_public, skill_tags=list(skill_tags), complexity=complexity,
        )
        ex.save()
    else:
        ex.data = payload
        ex.skill_tags = list(skill_tags)
        ex.complexity = complexity
        ex.is_public = is_public
        ex.save(update_fields=["data", "skill_tags", "complexity", "is_public"])
    ex.data["exerciseId"] = ex.id
    ex.data["score"]["umto"]["metadata"]["exercise_id"] = ex.id
    ex.save(update_fields=["data"])
    return ex


def _build_playlist(*, author, playlist_name, exercises, skill_tags, is_public):
    playlist, _ = Playlist.objects.get_or_create(
        name=playlist_name, authored_by=author,
        defaults=dict(is_dynamic=False, is_adaptive=False,
                      is_public=is_public, skill_tags=skill_tags),
    )
    playlist.skill_tags = skill_tags
    if is_public:
        playlist.is_public = True
    playlist.save()
    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for order, ex in enumerate(exercises, start=1):
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=order)
    return playlist


def _interleave_key_blocks(items: list, key_count: int) -> list:
    """Convert key-major ordering into pattern-major ordering.

    Generators build rows as all patterns in key 1, then all patterns in key 2.
    For student playlists, cycle keys before moving to the next pattern so early
    exercises do not all feel like duplicates in C.
    """
    if key_count <= 1 or len(items) % key_count != 0:
        return items

    block_size = len(items) // key_count
    out = []
    for pattern_idx in range(block_size):
        for key_idx in range(key_count):
            out.append(items[(key_idx * block_size) + pattern_idx])
    return out


# ── Voice assignment helpers ──────────────────────────────────────────────────

def _assign_slots_simple(combo: tuple) -> dict[str, tuple]:
    """
    Assign SATB slots for a simple-cadence combo (2–4 voices).
    Returns {voice_id: (clausula_name, var_idx, triple)}.
    1/2/3-voice: Discant=S, Tenor/Alto=A, Bass=B
    4-voice: Discant=S, Alto=A, Tenor=T, Bass=B
    """
    by_name = {}
    for name, idx, triple in combo:
        by_name.setdefault(name, []).append((idx, triple))

    n = len(combo)
    result = {}
    names_present = {c[0] for c in combo}

    _simple_vid = {"Discant": "S", "Tenor": "A", "Alto": "A", "Bass": "B"}

    if n == 1:
        name, idx, triple = combo[0]
        result[_simple_vid[name]] = (name, idx, triple)

    elif n <= 3:
        for name, idx, triple in combo:
            vid = _simple_vid[name]
            result[vid] = (name, idx, triple)

    elif n == 4:
        # Full SATB: Discant=S, Alto=A, Tenor=T, Bass=B
        for name, idx, triple in combo:
            vid = {"Discant": "S", "Alto": "A", "Tenor": "T", "Bass": "B"}[name]
            # Handle duplicate Tenor — second one goes to A if A free
            if vid in result and vid == "T":
                vid = "A"
            result[vid] = (name, idx, triple)

    return result


# ── B1: individual clausulae ──────────────────────────────────────────────────

def _generate_b1(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B1 — Formal Clausulae (one voice)"))
    exs = []
    for key in TARGET_KEYS:
        for clausula_name, variants in CLAUSULAE.items():
            color = CLAUSULA_COLOR.get(clausula_name, "#000000")
            vid = {"Discant": "S", "Tenor": "A", "Alto": "A", "Bass": "B"}[clausula_name]
            for var_idx, triple in enumerate(variants):
                sol = _solfege_label(clausula_name, var_idx)
                desc = f"B1 — {clausula_name} clausula ({sol}) in {key}"
                events = _realize_events(triple, key, vid)
                vmap = {vid: events}
                payload = _build_umto(
                    vmap, key, desc,
                    voice_colors=_render_voice_colors(vmap, {vid: color}),
                )
                ex = _save_exercise(
                    author=author, description=desc, payload=payload,
                    skill_tags=["branch_b", "unit:B1",
                                f"clausula_{clausula_name.lower()}",
                                f"clausula_var{var_idx}"],
                    complexity=1, is_public=options["public"], overwrite=options["overwrite"],
                )
                exs.append(ex)
                stdout.write(f"  {desc}")
    pl = _build_playlist(
        author=author, playlist_name="B1 — Formal Clausulae",
        exercises=_interleave_key_blocks(exs, len(TARGET_KEYS)),
        skill_tags=["branch_b", "unit:B1"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B1: {len(exs)} exercises → '{pl.name}'"))


# ── B2: 2-voice simple cadences ───────────────────────────────────────────────

def _generate_b2(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B2 — Simple Cadence (2 voices)"))
    exs = []
    combos = [c for c in enumerate_simple(n_voices=2)
              if any(n == "Discant" for n, i, t in c)
              and not any(n == "Bass" for n, i, t in c)]
    for key in TARGET_KEYS:
        for combo in combos:
            slots = _assign_slots_simple(combo)
            parts = []
            colors = {}
            vmap = {}
            for vid, (name, var_idx, triple) in slots.items():
                sol = _solfege_label(name, var_idx)
                parts.append(_vpart(name, sol))
                vmap[vid] = _realize_events(triple, key, vid)
                colors[vid] = CLAUSULA_COLOR.get(name, "#000000")
            desc = f"B2 — {' '.join(parts)} [{key}]"
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B2", "cadence_simple_2pt"],
                complexity=2, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            stdout.write(f"  {desc}")
    pl = _build_playlist(
        author=author, playlist_name="B2 — Simple Cadence (2 parts)",
        exercises=_interleave_key_blocks(exs, len(TARGET_KEYS)),
        skill_tags=["branch_b", "unit:B2", "cadence_simple_2pt"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B2: {len(exs)} exercises → '{pl.name}'"))


# ── B3: 3-voice simple cadences (with bass) ───────────────────────────────────

def _generate_b3(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B3 — Simple Cadence (3 voices, with bass)"))
    exs = []
    combos = [c for c in enumerate_simple(n_voices=3, require_bass=True)
              if any(n == "Discant" for n, i, t in c)]
    for key in TARGET_KEYS:
        for combo in combos:
            slots = _assign_slots_simple(combo)
            parts = []
            colors = {}
            vmap = {}
            for vid, (name, var_idx, triple) in slots.items():
                sol = _solfege_label(name, var_idx)
                parts.append(_vpart(name, sol))
                vmap[vid] = _realize_events(triple, key, vid)
                colors[vid] = CLAUSULA_COLOR.get(name, "#000000")
            desc = f"B3 — {' '.join(parts)} [{key}]"
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
                analysis_labels=_analysis_labels_from_slots(slots),
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B3", "cadence_simple_3pt",
                            "clausula_bass"],
                complexity=3, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            stdout.write(f"  {desc}")
    pl = _build_playlist(
        author=author, playlist_name="B3 — Simple Cadence (3 parts)",
        exercises=_interleave_key_blocks(exs, len(TARGET_KEYS)),
        skill_tags=["branch_b", "unit:B3", "cadence_simple_3pt"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B3: {len(exs)} exercises → '{pl.name}'"))


# ── B4: 4-voice simple cadences ───────────────────────────────────────────────

def _generate_b4(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B4 — Simple Cadence (4 voices)"))
    exs = []
    combos = [c for c in enumerate_simple(n_voices=4, require_bass=True)
              if any(n == "Discant" for n, i, t in c)]
    for key in TARGET_KEYS:
        for combo in combos:
            slots = _assign_slots_simple(combo)
            parts = []
            colors = {}
            vmap = {}
            for vid, (name, var_idx, triple) in slots.items():
                sol = _solfege_label(name, var_idx)
                parts.append(_vpart(name, sol))
                vmap[vid] = _realize_events(triple, key, vid)
                colors[vid] = CLAUSULA_COLOR.get(name, "#000000")
            desc = f"B4 — {' '.join(parts)} [{key}]"
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
                analysis_labels=_analysis_labels_from_slots(slots),
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B4", "cadence_4pt",
                            "clausula_alto"],
                complexity=4, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            stdout.write(f"  {desc}")
    pl = _build_playlist(
        author=author, playlist_name="B4 — Simple Cadence (4 parts)",
        exercises=_interleave_key_blocks(exs, len(TARGET_KEYS)),
        skill_tags=["branch_b", "unit:B4", "cadence_4pt"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B4: {len(exs)} exercises → '{pl.name}'"))


# ── B11: compound 2-voice cadences ────────────────────────────────────────────

def _compound_events(triple, key: str, vid: str, tau: int) -> list[VoiceEvent]:
    """
    Build VoiceEvents for a compound cadence voice.
    τ=0 (early): half/half/whole, starting beat 0.
    τ=1 (late):  quarter rest + quarter/quarter/whole, starting beat 0.
    """
    if tau == 0:
        return _realize_events(triple, key, vid, dur_scheme=_DUR_COMPOUND_EARLY)
    else:
        rest = VoiceEvent(kind="rest", duration=1.0, duration_type="q", dots=0, is_target=False)
        notes = _realize_events(triple, key, vid, dur_scheme=_DUR_COMPOUND_LATE)
        return [rest] + notes


def _generate_b11(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B11 — Compound Cadence (2 voices)"))
    exs = []
    # enumerate_compound: c_early=τ=0, c_late=τ=1. Corpus always has Discant as τ=1.
    combos = [(e, l, pi) for e, l, pi in enumerate_compound(require_discant=True)
              if l[0] == "Discant"]
    for key in TARGET_KEYS:
        for c_early, c_late, _ in combos:
            e_name, e_idx, e_triple = c_early
            l_name, l_idx, l_triple = c_late
            e_sol = _solfege_label(e_name, e_idx)
            l_sol = _solfege_label(l_name, l_idx)
            # τ=0 voice: Bass=B, others=A (treble)
            e_vid = "B" if e_name == "Bass" else "A"
            # τ=1 Discant always S
            l_vid = "S"

            desc = f"B11 — τ0 {_vpart(e_name, e_sol)} τ1 {_vpart(l_name, l_sol)} [{key}]"
            e_events = _compound_events(e_triple, key, e_vid, tau=0)
            l_events = _compound_events(l_triple, key, l_vid, tau=1)
            vmap = {e_vid: e_events, l_vid: l_events}
            colors = {
                e_vid: CLAUSULA_COLOR.get(e_name, "#000000"),
                l_vid: CLAUSULA_COLOR.get(l_name, "#000000"),
            }
            # Compound offsets: τ=0 attacks at 0,2,4; τ=1 rest+attacks at 0,1,2,4 (rest=0)
            offsets = [0.0, 1.0, 2.0, 4.0]
            b11_labels = _analysis_labels_compound(e_triple) if e_name == "Bass" else [""] * 4
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
                offsets=offsets,
                analysis_labels=b11_labels,
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B11", "cadence_compound_2pt"],
                complexity=5, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            stdout.write(f"  {desc}")
    pl = _build_playlist(
        author=author, playlist_name="B11 — Compound Cadence (2 parts)",
        exercises=_interleave_key_blocks(exs, len(TARGET_KEYS)),
        skill_tags=["branch_b", "unit:B11", "cadence_compound_2pt"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B11: {len(exs)} exercises → '{pl.name}'"))


# ── B12: compound 3-voice and 4-voice cadences ────────────────────────────────

def _generate_b12(author, options, stdout, style):
    stdout.write(style.MIGRATE_HEADING("B12 — Compound Cadence (3–4 voices)"))
    exs = []
    exs_3v = []
    exs_4v = []

    # 3-voice standard: bass(τ=0) + upper-τ=0 + Discant(τ=1)
    combos_3v = [(b, e, l, pi) for b, e, l, pi in enumerate_compound_3voice(
                     require_discant=True, require_bass=True)
                 if l[0] == "Discant"]
    for key in TARGET_KEYS:
        for c_bass, c_early, c_late, _ in combos_3v:
            b_name, b_idx, b_triple = c_bass
            e_name, e_idx, e_triple = c_early
            l_name, l_idx, l_triple = c_late
            b_sol = _solfege_label(b_name, b_idx)
            e_sol = _solfege_label(e_name, e_idx)
            l_sol = _solfege_label(l_name, l_idx)

            b_vid = "B"
            e_vid = "A"
            l_vid = "S"

            desc = f"B12 — {_vpart(b_name, b_sol)} τ0 {_vpart(e_name, e_sol)} τ1 {_vpart(l_name, l_sol)} [{key}]"
            vmap = {
                b_vid: _compound_events(b_triple, key, b_vid, tau=0),
                e_vid: _compound_events(e_triple, key, e_vid, tau=0),
                l_vid: _compound_events(l_triple, key, l_vid, tau=1),
            }
            colors = {
                b_vid: CLAUSULA_COLOR.get(b_name, "#000000"),
                e_vid: CLAUSULA_COLOR.get(e_name, "#000000"),
                l_vid: CLAUSULA_COLOR.get(l_name, "#000000"),
            }
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
                offsets=[0.0, 1.0, 2.0, 4.0],
                analysis_labels=_analysis_labels_compound(b_triple),
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B12", "cadence_compound_3pt"],
                complexity=6, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            exs_3v.append(ex)
            stdout.write(f"  {desc}")

    # 4-voice compound: bass(τ=0) + 2 upper(τ=0) + Discant(τ=1)
    for key in TARGET_KEYS:
        for c_bass, c_u1, c_u2, c_late in enumerate_compound_4voice(
                require_discant=True, require_bass=True):
            b_name, b_idx, b_triple = c_bass
            u1_name, u1_idx, u1_triple = c_u1
            u2_name, u2_idx, u2_triple = c_u2
            l_name, l_idx, l_triple = c_late

            b_sol  = _solfege_label(b_name, b_idx)
            u1_sol = _solfege_label(u1_name, u1_idx)
            u2_sol = _solfege_label(u2_name, u2_idx)
            l_sol  = _solfege_label(l_name, l_idx)

            # 4-voice slots: Bass=B, lower-upper=T, upper-upper=A, Discant=S
            b_vid  = "B"
            u1_vid = "T"
            u2_vid = "A"
            l_vid  = "S"

            desc = (f"B12 4v — {_vpart(b_name, b_sol)} {_vpart(u1_name, u1_sol)}"
                    f" {_vpart(u2_name, u2_sol)} τ1 {_vpart(l_name, l_sol)} [{key}]")
            vmap = {
                b_vid:  _compound_events(b_triple,  key, b_vid,  tau=0),
                u1_vid: _compound_events(u1_triple, key, u1_vid, tau=0),
                u2_vid: _compound_events(u2_triple, key, u2_vid, tau=0),
                l_vid:  _compound_events(l_triple,  key, l_vid,  tau=1),
            }
            colors = {
                b_vid:  CLAUSULA_COLOR.get(b_name,  "#000000"),
                u1_vid: CLAUSULA_COLOR.get(u1_name, "#000000"),
                u2_vid: CLAUSULA_COLOR.get(u2_name, "#000000"),
                l_vid:  CLAUSULA_COLOR.get(l_name,  "#000000"),
            }
            payload = _build_umto(
                vmap, key, desc,
                voice_colors=_render_voice_colors(vmap, colors),
                offsets=[0.0, 1.0, 2.0, 4.0],
                analysis_labels=_analysis_labels_compound(b_triple),
            )
            ex = _save_exercise(
                author=author, description=desc, payload=payload,
                skill_tags=["branch_b", "unit:B12", "cadence_compound_4pt"],
                complexity=7, is_public=options["public"], overwrite=options["overwrite"],
            )
            exs.append(ex)
            exs_4v.append(ex)
            stdout.write(f"  {desc}")

    pl = _build_playlist(
        author=author, playlist_name="B12 — Compound Cadence (3–4 parts)",
        exercises=(
            _interleave_key_blocks(exs_3v, len(TARGET_KEYS)) +
            _interleave_key_blocks(exs_4v, len(TARGET_KEYS))
        ),
        skill_tags=["branch_b", "unit:B12", "cadence_compound_3pt",
                    "cadence_compound_4pt"],
        is_public=options["public"],
    )
    stdout.write(style.SUCCESS(f"B12: {len(exs)} exercises → '{pl.name}'"))


# ── Management command ────────────────────────────────────────────────────────

ALL_UNITS = ["B1", "B2", "B3", "B4", "B11", "B12"]
_GENERATORS = {
    "B1":  _generate_b1,
    "B2":  _generate_b2,
    "B3":  _generate_b3,
    "B4":  _generate_b4,
    "B11": _generate_b11,
    "B12": _generate_b12,
}


class Command(BaseCommand):
    help = "Generate Branch B clausulae exercises: B1–B4 (simple) and B11–B12 (compound)."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Email of exercise author")
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument(
            "--unit",
            choices=ALL_UNITS + ["all"],
            default="all",
            help="Which unit to generate (default: all)",
        )

    def handle(self, *args, **options):
        if not _CLAUSULAE_AVAILABLE:
            raise CommandError(
                f"clausulae library not importable from {_CLAUSULAE_ROOT}.\n"
                f"Error: {_CLAUSULAE_IMPORT_ERROR}\n"
                "Run: pip install -e ../clausulae-project"
            )
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        units = ALL_UNITS if options["unit"] == "all" else [options["unit"]]
        for unit in units:
            _GENERATORS[unit](author, options, self.stdout, self.style)
