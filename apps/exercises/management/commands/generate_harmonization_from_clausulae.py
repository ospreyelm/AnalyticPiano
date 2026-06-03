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

TARGET_KEYS = ["C", "F", "G", "D", "Bb", "Eb", "E", "Ab", "A"]

_OCTAVE = {"S": 5, "A": 4, "T": 4, "B": 3}
_DUR_SIMPLE = [("h", 2.0), ("h", 2.0), ("w", 4.0)]
_CADENCE_FIGURES = [
    (0.0, "5/3", "5/3"),
    (2.0, "5/3", "5/3"),
    (4.0, "5/3", "5/3"),
]
_UNIT10_FIRST_INVERSION_SLOTS = {
    "S": ("Discant", 0, (0, 6, 0)),
    "A": ("Alto", 1, (4, 3, 2)),
    "B": ("Tenor", 3, (2, 1, 2)),
}
_UNIT10_FIGURES = [
    (0.0, "6", "6/3"),
    (2.0, "6", "6/3"),
    (4.0, "6", "6/3"),
]
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


def _tonal_valid(combo) -> bool:
    if tonal_sonority_ok is not None:
        return tonal_sonority_ok([triple for _, __, triple in combo])
    ant = {triple[0] for _, __, triple in combo}
    ult = {triple[2] for _, __, triple in combo}
    return 2 in ant and not (4 in ult and 2 not in ult)


def _slot_fingerprint(combo) -> frozenset:
    slots = _assign_slots(combo)
    return frozenset((vid, triple) for vid, (_, __, triple) in slots.items())


def _student_prompt_fingerprint(combo) -> tuple:
    """Deduplicate variants that look identical to a harmonization student.

    This command locks and displays only the bass voice, and target derivation is
    figured-bass based. Upper-voice Clausula variants are hidden and do not
    affect the accepted pitch-class set, so they should not create duplicate
    student exercises.
    """
    slots = _assign_slots(combo)
    bass = slots.get("B")
    bass_triple = bass[2] if bass else None
    figures = tuple((offset, figured, raw) for offset, figured, raw in _CADENCE_FIGURES)
    return bass_triple, figures


def _build_harmonization_payload(
    voice_events_by_id: dict[str, list[VoiceEvent]],
    key: str,
    description: str,
    unit: int,
    cadence_figures: list[tuple[float, str, str]] | None = None,
) -> dict:
    """Build a UMTO harmonization payload using the existing figured-bass path."""
    vids = set(voice_events_by_id.keys())
    cadence_figures = cadence_figures or _CADENCE_FIGURES
    offsets = [off for off, _, __ in cadence_figures]
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
            for off, figured, raw in cadence_figures
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
        Exercise.objects.filter(
            description=description,
            authored_by=author,
            skill_tags__contains=[skill_tags[0]],
        ).first()
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


def _student_facing_playlist_name(unit: int) -> str:
    if unit == 10:
        return f"Unit {unit} - First Inversions (Harmonization)"
    return f"Unit {unit} - Authentic Cadences (Harmonization)"


def _legacy_playlist_names(unit: int, voices_arg: str) -> list[str]:
    suffixes = ["all"] if voices_arg == "all" else [f"{voices_arg}-voice"]
    return [
        f"Unit {unit} - Authentic Cadences (Harmonization) {suffix}"
        for suffix in suffixes
    ]


def _rename_legacy_playlist(
    *,
    author,
    playlist_name: str,
    legacy_names: list[str],
) -> None:
    if Playlist.objects.filter(name=playlist_name, authored_by=author).exists():
        return

    legacy = (
        Playlist.objects.filter(name__in=legacy_names, authored_by=author)
        .order_by("id")
        .first()
    )
    if legacy is None:
        return

    legacy.name = playlist_name
    legacy.save(update_fields=["name"])


def _fixed_unit_slots(unit: int, n_voices: int) -> list[dict[str, tuple]]:
    if unit == 10 and n_voices == 3:
        return [_UNIT10_FIRST_INVERSION_SLOTS]
    return []


def _exercise_description(unit: int, key: str, combo_idx: int, combo_count: int) -> str:
    if unit == 10:
        return f"First-Inversion Cadence in {key}"

    prefix = f"Harmonization Cadence in {key}"
    return prefix if combo_count == 1 else f"{prefix} var{combo_idx}"


def _figures_for_unit(unit: int) -> list[tuple[float, str, str]]:
    return _UNIT10_FIGURES if unit == 10 else _CADENCE_FIGURES


def _skill_tags_for_unit(unit: int, n_voices: int) -> list[str]:
    tags = [
        "exercise_type:harmonization_from_clausulae",
        "corpus:standard_exercises_from_clausulae",
        f"unit:{unit}",
        "mode:harmonization",
        f"voices:{n_voices}",
        "Diatonic_Triads",
    ]
    if unit == 10:
        tags.append("Inversions_First")
    else:
        tags.append("Cadence_Perfect_Authentic")
    return tags


def _playlist_skill_tags_for_unit(unit: int) -> list[str]:
    tags = [
        "exercise_type:harmonization_from_clausulae",
        f"unit:{unit}",
    ]
    tags.append("Inversions_First" if unit == 10 else "Cadence_Perfect_Authentic")
    return tags


def _heading_label_for_unit(unit: int) -> str:
    return "first-inversion cadences" if unit == 10 else "authentic cadences"


def _make_exercises(
    n_voices: int,
    unit: int,
    author,
    options: dict,
    stdout,
) -> list[Exercise]:
    slot_sets = _fixed_unit_slots(unit, n_voices)
    if not slot_sets:
        seen: set[tuple] = set()
        for combo in enumerate_simple(n_voices=n_voices, require_bass=True):
            if not any(name == "Discant" for name, _, __ in combo):
                continue
            if not _tonal_valid(combo):
                continue
            fp = _student_prompt_fingerprint(combo)
            if fp in seen:
                continue
            seen.add(fp)
            slot_sets.append(_assign_slots(combo))

    exs: list[Exercise] = []
    for key in TARGET_KEYS:
        for combo_idx, slots in enumerate(slot_sets, start=1):
            vmap = {
                vid: _realize_events(triple, key, vid)
                for vid, (_, __, triple) in slots.items()
            }
            desc = _exercise_description(unit, key, combo_idx, len(slot_sets))

            payload = _build_harmonization_payload(
                vmap,
                key,
                desc,
                unit,
                cadence_figures=_figures_for_unit(unit),
            )
            skill_tags = _skill_tags_for_unit(unit, n_voices)
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
                    f"harmonization_from_clausulae - {n_voices}-voice {_heading_label_for_unit(unit)} (Unit {unit})"
                )
            )
            all_exercises.extend(
                _make_exercises(n_voices, unit, author, options, self.stdout)
            )

        playlist_name = _student_facing_playlist_name(unit)
        _rename_legacy_playlist(
            author=author,
            playlist_name=playlist_name,
            legacy_names=_legacy_playlist_names(unit, voices_arg),
        )
        playlist = _build_playlist(
            author=author,
            playlist_name=playlist_name,
            exercises=all_exercises,
            skill_tags=_playlist_skill_tags_for_unit(unit),
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
