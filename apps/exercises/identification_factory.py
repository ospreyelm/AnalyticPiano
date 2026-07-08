"""Factory for chord-quality identification exercises.

Extracted from the oversized ``umto_factory.py`` (see the "Oversized modules"
entry in ``docs/architecture/engineering-principles.md``). This module has a
single responsibility: build and persist the ``identification``-type payload
used by Unit 5 chord-quality exercises (triad / seventh-chord identification).

``Exercise.clean()``'s UMTO guard checks ``data["isUMTO"]``, not the calling
module, so this extraction needs no special-casing — the payload still sets
``isUMTO: True`` exactly as before.
"""
from __future__ import annotations

from apps.exercises.models import Exercise
from apps.exercises.umto import (
    UMTO,
    Metadata,
    Voices,
    InteractionMode,
)


def save_umto_chord_id_exercise(
    *,
    description: str,
    author,
    chord_key: str,
    midi_notes: list = None,
    answer: str = None,
    choices: list = None,
    chords: list = None,
    skill_tags: list,
    complexity: int,
    is_public: bool = True,
    overwrite: bool = False,
) -> "Exercise":
    """Save a root-position chord quality identification exercise.

    The exercise can contain either a single chord (via midi_notes/answer/choices)
    or a worksheet of multiple chords (via chords). When chords is supplied it
    takes precedence and each entry must be a dict with:
        notes: list of MIDI integers
        answer: quality display label (e.g. "major", "dominant 7")
        choices: ordered list of answer choices shown to the student
        spelling: optional list of VexFlow key strings ("eb/4") — the chord's
            recorded enharmonic spelling, carried through to the frontend so the
            stave renderer does not re-derive spelling from MIDI.

    chord_key: HarmonyLab key string (e.g. "jG_") used for staff rendering/accidental display.

    Payload additions for the chord-spelling/barline fix:
        - ``chord[i].spelling``: per-chord recorded spelling (None when absent —
          legacy exercises keep the existing frontend ``Analyze`` fallback, R4).
        - ``timeSignature``: top-level "4/4" so the frontend can place barlines
          (R2). NOTE: this key alone is not sufficient for R2 — the frontend
          must also read it inside the isUMTO/identification branch (KTD4).
    """
    if chords is None:
        if midi_notes is None or answer is None or choices is None:
            raise ValueError("save_umto_chord_id_exercise requires either chords or midi_notes+answer+choices")
        chords = [
            {
                "notes": sorted(midi_notes),
                "answer": answer,
                "choices": choices,
                "rhythmValue": "w",
            }
        ]

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source="Identify the chord quality.",
            key=chord_key,
            meter="4/4",
            clef="keyboard",
            complexity_score=complexity,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="dropdown",
            unit=5,
        ),
        voices=Voices(),
        analysis=[],
        grading=[],
    )

    payload = {
        "type": "identification",
        "isUMTO": True,
        "mode": InteractionMode.IDENTIFICATION.value,
        "analysisType": "chord_quality",
        "inputMode": "dropdown",
        "identMode": "practice",
        "staffDistribution": "keyboard",
        "key": chord_key,
        "meter": "4/4",
        "timeSignature": "4/4",
        "complexity_score": complexity,
        "introText": "Identify the chord quality.",
        "reviewText": "Well done!",
        "chord": [
            {
                "notes": sorted(c["notes"]),
                "answer": c["answer"],
                "choices": c["choices"],
                "rhythmValue": c.get("rhythmValue", "w"),
                "spelling": c.get("spelling"),
            }
            for c in chords
        ],
        "score": {
            "meta": {
                "key": chord_key,
                "time": "4/4",
                "clef": "keyboard",
                "staffDistribution": "keyboard",
            },
            "measures": [],
            "umto": umto.model_dump(mode="json"),
        },
        "grading": [],
    }

    UMTO.model_validate(payload["score"]["umto"])

    ex = None
    if overwrite:
        ex = Exercise.objects.filter(description=description, authored_by=author).first()

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