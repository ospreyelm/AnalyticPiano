"""Generate Branch B Units B1–B2: formal clausulae and simple 2-voice cadences.

B1 — individual clausulae as playback/identification exercises (one voice at a time).
B2 — 2-voice cadence combinations (Discant + Tenor variant) as playback exercises.

Clausula triples in Z₇ (Do=0 … Ti=6):
  Discant:    (0, 6, 0)   Do–Ti–Do
  Tenor var0: (0, 1, 0)   Do–Re–Do
  Tenor var1: (0, 1, 2)   Do–Re–Mi
  Tenor var2: (2, 1, 0)   Mi–Re–Do
  Tenor var3: (2, 1, 2)   Mi–Re–Mi
  Alto var0:  (4, 4, 4)   Sol–Sol–Sol (Fa position)
  Alto var1:  (4, 3, 2)   Sol–Fa–Mi
  Alto var2:  (4, 5, 4)   Sol–La–Sol
  Bass:       (0, 4, 0)   Do–Sol–Do

Voices map to SATB: Discant=S, Tenor=A (treble staff), Alto=A, Bass=B.
For 2-voice (Discant+Tenor), both voices on treble staff (S+A). Bass clausula always bass staff.
Compound rhythm (authentic): ANT=half, PEN=half, ULT=whole in 2/2.
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

# Locate clausulae library (one level up from HarmonyLab-1)
_HERE = os.path.dirname(__file__)
_CLAUSULAE_ROOT = os.path.abspath(os.path.join(_HERE, "../../../../../clausulae-project"))
if _CLAUSULAE_ROOT not in sys.path:
    sys.path.insert(0, _CLAUSULAE_ROOT)

try:
    from clausulae.realize import key_realize
    from clausulae.generate import enumerate_simple
    from clausulae.core import CLAUSULAE, CLAUSULA_COLOR
    _CLAUSULAE_AVAILABLE = True
except ImportError as _e:
    _CLAUSULAE_AVAILABLE = False
    _CLAUSULAE_IMPORT_ERROR = str(_e)

User = get_user_model()

# HarmonyLab key string for each key center
HL_KEY = {
    "C": "jC_", "G": "jG_", "F": "jF_", "D": "jD_", "Bb": "jBb",
    "A": "jA_", "Eb": "jEb", "E": "jE_", "Ab": "jAb",
}

# Keys to generate exercises in (C and G cover the pedagogical basics for B1/B2)
TARGET_KEYS = ["C", "G", "F"]

# Clausula label → SATB voice id + display name
# Tenor goes to A (alto slot, treble staff) — it's a middle voice, not bass clef.
# Bass is the only clausula that belongs on the bass staff.
CLAUSULA_VOICE = {
    "Discant": ("S", "Discant"),
    "Tenor":   ("A", "Tenor"),
    "Alto":    ("A", "Alto"),
    "Bass":    ("B", "Bass"),
}

# Variant index → solfège label for display
TENOR_LABELS = ["Do–Re–Do", "Do–Re–Mi", "Mi–Re–Do", "Mi–Re–Mi"]
ALTO_LABELS  = ["Sol–Sol–Sol", "Sol–Fa–Mi", "Sol–La–Sol"]

# Duration values: ANT=half (2.0 ql), PEN=half, ULT=whole (4.0 ql)
_DUR = [("h", 2.0), ("h", 2.0), ("w", 4.0)]

# SATB_MAP mirrors vexflow_adapter.js: treble[0]="S", treble[1]="A", bass[0]="T", bass[1]="B"
_SATB_MAP = {"treble": ["S", "A"], "bass": ["T", "B"]}


def _render_voice_colors(voice_events_by_id: dict, clausula_color_by_vid: dict) -> dict:
    """
    Compute voiceColors keyed by the SATB labels that _convertUMTOToProcessedScore
    (exercise_sheet.js) assigns at render time.  It compacts voices: non-empty
    voices are pushed in [S,A] / [T,B] order so the first present voice always
    lands at index 0 regardless of its semantic name.
    """
    treble_present = [v for v in ["S", "A"] if voice_events_by_id.get(v)]
    bass_present   = [v for v in ["T", "B"] if voice_events_by_id.get(v)]
    result = {}
    for idx, vid in enumerate(treble_present[:2]):
        result[_SATB_MAP["treble"][idx]] = clausula_color_by_vid[vid]
    for idx, vid in enumerate(bass_present[:2]):
        result[_SATB_MAP["bass"][idx]] = clausula_color_by_vid[vid]
    return result


def _scale_degree_label(pitch: Pitch, key: str) -> str:
    """Return scale degree numeral (e.g. '3', '#4', 'b7') for a Pitch in the given key."""
    from music21 import key as m21key, pitch as m21pitch
    acc_str = {1: "#", -1: "b", 2: "##", -2: "bb", 0: ""}.get(pitch.alter, "")
    m21p = m21pitch.Pitch(f"{pitch.step}{acc_str}{pitch.octave}")
    k = m21key.Key(key)
    degree, accidental = k.getScaleDegreeAndAccidentalFromPitch(m21p)
    if degree is None:
        return ""
    acc_label = ""
    if accidental is not None:
        # music21 modifier: "-" = flat, "--" = double-flat, "#" = sharp, "##" = double-sharp
        acc_label = accidental.modifier.replace("-", "b")
    return f"{acc_label}{degree}"


def _m21_note_to_pitch(n) -> Pitch:
    """Convert a music21 Note to a UMTO Pitch."""
    p = n.pitch
    alter_map = {None: 0, "sharp": 1, "flat": -1, "double-sharp": 2, "double-flat": -2}
    alter = alter_map.get(p.accidental.name if p.accidental else None, 0)
    midi = p.midi
    return Pitch(step=p.step, alter=alter, octave=p.octave, midi=midi)


def _clausula_to_voice_events(triple, key: str, voice_id: str) -> list[VoiceEvent]:
    """Realize a Z₇ triple in the given key and return UMTO VoiceEvents (ANT, PEN, ULT)."""
    # Choose octave by voice: Bass=3, Tenor=4, Alto=4, Soprano/Discant=5
    octave_map = {"B": 3, "T": 4, "A": 4, "S": 5}
    octave = octave_map.get(voice_id, 4)
    notes = key_realize(triple, key, octave=octave)
    events = []
    for n, (dur_type, dur_ql) in zip(notes, _DUR):
        pitch = _m21_note_to_pitch(n)
        events.append(VoiceEvent(
            kind="note",
            pitch=pitch,
            duration=dur_ql,
            duration_type=dur_type,
            dots=0,
            is_target=True,
        ))
    return events


def _grading_and_analysis(voice_events_by_id: dict[str, list[VoiceEvent]],
                           labels: dict[str, str],
                           unit_tags: list[int],
                           key: str = "C") -> tuple[list[GradingSlice], list[AnalysisSlice]]:
    """Build grading + analysis slices from realized voice events."""
    # Offsets: ANT=0.0, PEN=2.0, ULT=4.0 (half=2 ql in 2/2)
    offsets = [0.0, 2.0, 4.0]
    pos_names = ["ANT", "PEN", "ULT"]

    grading = []
    analysis = []
    for pos_i, (offset, pos_name) in enumerate(zip(offsets, pos_names)):
        midi_pitches = []
        scale_degrees = []
        for vid, events in voice_events_by_id.items():
            if pos_i < len(events) and events[pos_i].pitch:
                p = events[pos_i].pitch
                midi_pitches.append(p.midi)
                label = _scale_degree_label(p, key)
                if label:
                    scale_degrees.append({"midi": p.midi, "label": label})

        grading.append(GradingSlice(offset=offset, target_midi_pitches=sorted(midi_pitches)))

        label_parts = [f"{name}: {pos_name}" for name, _ in labels.items()]
        analysis.append(AnalysisSlice(
            offset=offset,
            content=AnalysisLayer(
                functional_label=" / ".join(label_parts),
                scale_degrees=scale_degrees or None,
            ),
            unit_tags=unit_tags,
        ))

    return grading, analysis


def _build_umto(voice_events_by_id: dict[str, list[VoiceEvent]],
                labels: dict[str, str],
                key: str,
                description: str,
                voice_colors: dict[str, str] | None = None) -> dict:
    """Assemble a complete UMTO frontend payload for a clausulae exercise."""
    voices = Voices(
        S=voice_events_by_id.get("S", []),
        A=voice_events_by_id.get("A", []),
        T=voice_events_by_id.get("T", []),
        B=voice_events_by_id.get("B", []),
    )

    grading, analysis = _grading_and_analysis(voice_events_by_id, labels, unit_tags=[], key=key)

    vids = set(voice_events_by_id.keys())
    has_bass = "B" in vids
    has_treble = vids & {"S", "A"}
    if has_bass and has_treble:
        staff_dist = "keyboard"
    elif has_bass:
        staff_dist = "bass"
    else:
        staff_dist = "treble"

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
        voices=voices,
        analysis=analysis,
        grading=grading,
    )

    payload = umto.to_frontend_payload(unit=None, analysis_type="clausula")
    payload["staffDistribution"] = staff_dist
    payload["display"] = {
        "showNotation": True,
        "hideKeyLabel": False,
        "showScaleDegrees": True,
        "voiceColors": voice_colors or {},
        "maxMeasures": 2,
    }
    return payload


def _save_exercise(*, author, description, payload, skill_tags, complexity,
                   is_public, overwrite) -> Exercise:
    ex = Exercise.objects.filter(description=description, authored_by=author).first() if overwrite else None
    if ex is None:
        ex = Exercise(
            description=description,
            data=payload,
            authored_by=author,
            is_public=is_public,
            skill_tags=list(skill_tags),
            complexity=complexity,
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
        name=playlist_name,
        authored_by=author,
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


class Command(BaseCommand):
    help = "Generate Branch B Units B1–B2: clausulae playback exercises."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Email of exercise author")
        parser.add_argument("--public", action="store_true", help="Make exercises public")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exercises")
        parser.add_argument(
            "--unit", choices=["B1", "B2", "both"], default="both",
            help="Which units to generate (default: both)",
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

        unit = options["unit"]
        if unit in ("B1", "both"):
            self._generate_b1(author, options)
        if unit in ("B2", "both"):
            self._generate_b2(author, options)

    # ── B1: individual clausulae ──────────────────────────────────────────────

    def _generate_b1(self, author, options):
        self.stdout.write(self.style.MIGRATE_HEADING("Generating B1 — Formal Clausulae"))
        all_exercises = []

        for key in TARGET_KEYS:
            for clausula_name, variants in CLAUSULAE.items():
                voice_id, display_name = CLAUSULA_VOICE[clausula_name]
                for var_idx, triple in enumerate(variants):
                    var_labels = {
                        "Discant": ["Do–Ti–Do"],
                        "Tenor":   TENOR_LABELS,
                        "Alto":    ALTO_LABELS,
                        "Bass":    ["Do–Sol–Do"],
                    }[clausula_name]
                    solfege = var_labels[var_idx] if var_idx < len(var_labels) else str(triple)

                    desc = f"B1 — {display_name} clausula ({solfege}) in {key}"
                    events = _clausula_to_voice_events(triple, key, voice_id)
                    labels = {display_name: solfege}
                    clausula_color = CLAUSULA_COLOR.get(clausula_name, "#9aa0a6")
                    payload = _build_umto(
                        voice_events_by_id={voice_id: events},
                        labels=labels,
                        key=key,
                        description=desc,
                        voice_colors=_render_voice_colors(
                            {voice_id: events},
                            {voice_id: clausula_color},
                        ),
                    )
                    skill_tags = [
                        "branch_b", "unit:B1",
                        f"clausula_{clausula_name.lower()}",
                        f"clausula_var{var_idx}",
                    ]
                    ex = _save_exercise(
                        author=author,
                        description=desc,
                        payload=payload,
                        skill_tags=skill_tags,
                        complexity=1,
                        is_public=options["public"],
                        overwrite=options["overwrite"],
                    )
                    all_exercises.append(ex)
                    self.stdout.write(f"  {desc}")

        playlist = _build_playlist(
            author=author,
            playlist_name="B1 — One-Part Clausulae",
            exercises=all_exercises,
            skill_tags=["branch_b", "unit:B1", "one_part_clausulae"],
            is_public=options["public"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"B1: {len(all_exercises)} exercises → playlist '{playlist.name}'"
        ))

    # ── B2: 2-voice Discant + Tenor combinations ──────────────────────────────

    def _generate_b2(self, author, options):
        self.stdout.write(self.style.MIGRATE_HEADING("Generating B2 — Simple Cadence (2 parts)"))
        all_exercises = []

        discant_triple = CLAUSULAE["Discant"][0]  # (0, 6, 0)
        tenor_variants = list(enumerate(CLAUSULAE["Tenor"]))

        for key in TARGET_KEYS:
            for var_idx, tenor_triple in tenor_variants:
                tenor_labels = TENOR_LABELS
                solfege = tenor_labels[var_idx] if var_idx < len(tenor_labels) else str(tenor_triple)

                desc = f"B2 — Discant + Tenor {solfege} in {key}"
                d_events = _clausula_to_voice_events(discant_triple, key, "S")
                t_events = _clausula_to_voice_events(tenor_triple, key, "A")

                labels = {"Discant": "Do–Ti–Do", "Tenor": solfege}
                payload = _build_umto(
                    voice_events_by_id={"S": d_events, "A": t_events},
                    labels=labels,
                    key=key,
                    description=desc,
                    voice_colors=_render_voice_colors(
                        {"S": d_events, "A": t_events},
                        {"S": CLAUSULA_COLOR.get("Discant", "#F9141B"),
                         "A": CLAUSULA_COLOR.get("Tenor", "#108040")},
                    ),
                )
                skill_tags = [
                    "branch_b", "unit:B2",
                    "clausula_discant", "clausula_tenor",
                    "cadence_simple_2pt", "clausula_combination",
                    f"clausula_tenor_var{var_idx}",
                ]
                ex = _save_exercise(
                    author=author,
                    description=desc,
                    payload=payload,
                    skill_tags=skill_tags,
                    complexity=2,
                    is_public=options["public"],
                    overwrite=options["overwrite"],
                )
                all_exercises.append(ex)
                self.stdout.write(f"  {desc}")

        playlist = _build_playlist(
            author=author,
            playlist_name="B2 — Simple Cadence (2 parts)",
            exercises=all_exercises,
            skill_tags=["branch_b", "unit:B2", "cadence_simple_2pt",
                        "clausula_combination"],
            is_public=options["public"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"B2: {len(all_exercises)} exercises → playlist '{playlist.name}'"
        ))
