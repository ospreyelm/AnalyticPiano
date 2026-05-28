"""Generate figured-bass harmonization exercises from Clausulae content."""
from __future__ import annotations

import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.harmonization.targets import build_targets_from_umto
from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.umto import (
    AnalysisLayer,
    AnalysisSlice,
    GradingSlice,
    HarmonizationTargetPolicy,
    InteractionMode,
    Metadata,
    UMTO,
    VoiceCountPolicy,
    VoiceEvent,
    Voices,
)

_HERE = os.path.dirname(__file__)
_CLAUSULAE_ROOT = os.path.abspath(
    os.path.join(_HERE, "../../../../../clausulae-project")
)
if _CLAUSULAE_ROOT not in sys.path:
    sys.path.insert(0, _CLAUSULAE_ROOT)

try:
    from clausulae.generate import enumerate_simple
    from clausulae.realize import key_realize

    _CLAUSULAE_AVAILABLE = True
except ImportError as _e:
    enumerate_simple = None
    key_realize = None
    _CLAUSULAE_AVAILABLE = False
    _CLAUSULAE_IMPORT_ERROR = str(_e)

try:
    from clausulae.constraints import tonal_sonority_ok
except ImportError:
    tonal_sonority_ok = None

User = get_user_model()


HL_KEY = {
    "C": "jC_", "G": "jG_", "F": "jF_", "D": "jD_", "Bb": "jBb",
    "A": "jA_", "Eb": "jEb", "E": "jE_", "Ab": "jAb",
}

TARGET_KEYS = ["C", "F", "G", "D", "Bb"]

_OCTAVE = {"S": 5, "A": 4, "T": 4, "B": 3}
_DUR_SIMPLE = [("h", 2.0), ("h", 2.0), ("w", 4.0)]
_CADENCE_FIGURES = [
    (0.0, "5/3", "5/3"),
    (2.0, "5/3", "5/3"),
    (4.0, "5/3", "5/3"),
]
_SOLFEGE_LABELS: dict[str, list[str]] = {
    "Discant": ["Do-Ti-Do"],
    "Tenor": ["Do-Re-Do", "Do-Re-Mi", "Mi-Re-Do", "Mi-Re-Mi"],
    "Alto": ["Sol-Sol-Sol", "Sol-Fa-Mi", "Sol-La-Sol"],
    "Bass": ["Do-Sol-Do"],
}
_SOL_ABBR = {
    "Do-Ti-Do": "D-Ti-D",
    "Do-Re-Do": "D-Re-D",
    "Do-Re-Mi": "D-Re-M",
    "Mi-Re-Do": "M-Re-D",
    "Mi-Re-Mi": "M-Re-M",
    "Sol-Sol-Sol": "S-S-S",
    "Sol-Fa-Mi": "S-Fa-M",
    "Sol-La-Sol": "S-La-S",
    "Do-Sol-Do": "D-Sol-D",
}


def _staff_dist(vids: set[str]) -> str:
    has_bass = bool(vids & {"T", "B"})
    has_treble = bool(vids & {"S", "A"})
    if has_bass and has_treble:
        return "keyboard"
    return "bass" if has_bass else "treble"


def _build_grading_slices(
    voice_events_by_id: dict[str, list[VoiceEvent]],
    offsets: list[float],
) -> list[GradingSlice]:
    slices = []
    for offset_i, offset in enumerate(offsets):
        midi = []
        for events in voice_events_by_id.values():
            if offset_i < len(events) and events[offset_i].pitch:
                midi.append(events[offset_i].pitch.midi)
        slices.append(GradingSlice(offset=offset, target_midi_pitches=sorted(midi)))
    return slices


def _m21_note_to_pitch(n):
    p = n.pitch
    alter_map = {
        None: 0,
        "sharp": 1,
        "flat": -1,
        "double-sharp": 2,
        "double-flat": -2,
    }
    alter = alter_map.get(p.accidental.name if p.accidental else None, 0)
    from apps.exercises.umto import Pitch

    return Pitch(step=p.step, alter=alter, octave=p.octave, midi=p.midi)


def _realize_events(triple, key: str, voice_id: str) -> list[VoiceEvent]:
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
        for n, (dt, ql) in zip(notes, _DUR_SIMPLE)
    ]


def _solfege_label(clausula_name: str, var_idx: int) -> str:
    labels = _SOLFEGE_LABELS.get(clausula_name, [])
    return labels[var_idx] if var_idx < len(labels) else str(var_idx)


def _assign_slots(combo: tuple) -> dict[str, tuple]:
    if len(combo) <= 3:
        vid_map = {"Discant": "S", "Tenor": "A", "Alto": "A", "Bass": "B"}
    else:
        vid_map = {"Discant": "S", "Alto": "A", "Tenor": "T", "Bass": "B"}

    result: dict[str, tuple] = {}
    for name, idx, triple in combo:
        vid = vid_map[name]
        if vid in result and vid == "T" and "A" not in result:
            vid = "A"
        result[vid] = (name, idx, triple)
    return result


def _combo_label(slots: dict[str, tuple]) -> str:
    parts = []
    for vid in ["S", "A", "T", "B"]:
        if vid not in slots:
            continue
        name, var_idx, _ = slots[vid]
        sol = _solfege_label(name, var_idx)
        parts.append(f"{name[0]}:{_SOL_ABBR.get(sol, sol)}")
    return " ".join(parts)


def _tonal_valid(combo) -> bool:
    if tonal_sonority_ok is not None:
        return tonal_sonority_ok([triple for _, __, triple in combo])
    ant = {triple[0] for _, __, triple in combo}
    ult = {triple[2] for _, __, triple in combo}
    return 2 in ant and not (4 in ult and 2 not in ult)


def _slot_fingerprint(combo) -> frozenset:
    slots = _assign_slots(combo)
    return frozenset((vid, triple) for vid, (_, __, triple) in slots.items())


def _build_harmonization_payload(
    voice_events_by_id: dict[str, list[VoiceEvent]],
    key: str,
    description: str,
    unit: int,
) -> dict:
    """Build a UMTO harmonization payload using the existing figured-bass path."""
    vids = set(voice_events_by_id.keys())
    offsets = [off for off, _, __ in _CADENCE_FIGURES]
    hl_key = HL_KEY.get(key, "jC_")

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source=description,
            key=hl_key,
            meter="2/2",
            clef=_staff_dist(vids),
            complexity_score=unit,
            mode=InteractionMode.HARMONIZATION,
            input_mode="dropdown",
            unit=unit,
            locked_voices=["B"],
            voice_count_policy=VoiceCountPolicy(expected=None, min=3, max=4),
            harmonization_target_policy=HarmonizationTargetPolicy(
                source="figured_bass",
                written_spelling_required=False,
                midi_uses_pitch_class=True,
            ),
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
                content=AnalysisLayer(
                    local_key=key,
                    figured_bass=figured,
                    raw_figured_bass=raw,
                ),
                unit_tags=[unit],
                is_target=False,
            )
            for off, figured, raw in _CADENCE_FIGURES
        ],
        grading=_build_grading_slices(voice_events_by_id, offsets),
    )

    payload = umto.to_frontend_payload(unit=unit, analysis_type="figured_bass")
    payload["analysisType"] = "figured_bass"
    payload["display"] = {
        "showNotation": True,
        "hideKeyLabel": False,
        "showScaleDegrees": False,
        "maxMeasures": 2,
    }
    payload["harmonizationTargets"] = build_targets_from_umto(
        payload["score"]["umto"]
    )
    return payload


def _save_exercise(
    *,
    author,
    description: str,
    payload: dict,
    skill_tags: list[str],
    complexity: int,
    is_public: bool,
    overwrite: bool,
) -> Exercise:
    ex = (
        Exercise.objects.filter(description=description, authored_by=author).first()
        if overwrite else None
    )
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


def _build_playlist(
    *,
    author,
    playlist_name: str,
    exercises: list[Exercise],
    skill_tags: list[str],
    is_public: bool,
) -> Playlist:
    playlist, _ = Playlist.objects.get_or_create(
        name=playlist_name,
        authored_by=author,
        defaults={
            "is_dynamic": False,
            "is_adaptive": False,
            "is_public": is_public,
            "skill_tags": skill_tags,
        },
    )
    playlist.skill_tags = skill_tags
    if is_public:
        playlist.is_public = True
    playlist.save()

    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for order, ex in enumerate(exercises, start=1):
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=ex,
            order=order,
        )
    return playlist


def _make_exercises(
    n_voices: int,
    unit: int,
    author,
    options: dict,
    stdout,
) -> list[Exercise]:
    seen: set[frozenset] = set()
    combos = []
    for combo in enumerate_simple(n_voices=n_voices, require_bass=True):
        if not any(name == "Discant" for name, _, __ in combo):
            continue
        if not _tonal_valid(combo):
            continue
        fp = _slot_fingerprint(combo)
        if fp in seen:
            continue
        seen.add(fp)
        combos.append(combo)

    exs: list[Exercise] = []
    voice_str = f"{n_voices}-part"
    for key in TARGET_KEYS:
        for combo_idx, combo in enumerate(combos, start=1):
            slots = _assign_slots(combo)
            vmap = {
                vid: _realize_events(triple, key, vid)
                for vid, (_, __, triple) in slots.items()
            }
            label = _combo_label(slots)
            prefix = f"{voice_str} Harmonization Cadence in {key}"
            candidate = f"{prefix} [{label}]"
            desc = candidate if len(candidate) <= 60 else f"{prefix} var{combo_idx}"

            payload = _build_harmonization_payload(vmap, key, desc, unit)
            skill_tags = [
                "exercise_type:harmonization_from_clausulae",
                "corpus:standard_exercises_from_clausulae",
                f"unit:{unit}",
                "mode:harmonization",
                f"voices:{n_voices}",
                "Cadence_Perfect_Authentic",
                "Diatonic_Triads",
            ]
            exs.append(
                _save_exercise(
                    author=author,
                    description=desc,
                    payload=payload,
                    skill_tags=skill_tags,
                    complexity=unit,
                    is_public=options["public"],
                    overwrite=options["overwrite"],
                )
            )
            stdout.write(f"  {desc}")
    return exs


class Command(BaseCommand):
    help = "Generate figured-bass harmonization exercises from Clausulae content."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--unit", type=int, default=9)
        parser.add_argument("--voices", choices=["3", "4", "all"], default="3")
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

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
        voices_arg = options["voices"]
        voice_list = [3, 4] if voices_arg == "all" else [int(voices_arg)]

        all_exercises: list[Exercise] = []
        for n_voices in voice_list:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"harmonization_from_clausulae - {n_voices}-voice authentic cadences (Unit {unit})"
                )
            )
            all_exercises.extend(
                _make_exercises(n_voices, unit, author, options, self.stdout)
            )

        playlist_suffix = "all" if voices_arg == "all" else f"{voices_arg}-voice"
        playlist = _build_playlist(
            author=author,
            playlist_name=f"Unit {unit} - Authentic Cadences (Harmonization) {playlist_suffix}",
            exercises=all_exercises,
            skill_tags=[
                "exercise_type:harmonization_from_clausulae",
                f"unit:{unit}",
                "Cadence_Perfect_Authentic",
            ],
            is_public=options["public"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal: {len(all_exercises)} exercises -> playlist '{playlist.name}'"
            )
        )
        self.stdout.write(
            "\nRemember to verify one exercise in the student app before bulk use.\n"
            "Check: bass + figures render, upper voices grade, completion saves."
        )
