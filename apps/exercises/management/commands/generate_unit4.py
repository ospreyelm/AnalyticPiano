"""Generate Unit 4 synthetic interval identification worksheets.

Each worksheet is a score-backed UMTO identification exercise: two visible
treble voices, one whole-note interval per measure, and clickable answer slots.
"""

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

User = get_user_model()

WORKSHEETS_PER_STAGE = 6
INTERVALS_PER_WORKSHEET = 8

ROOTS = [
    ("C4", "C"),
    ("D4", "D"),
    ("E4", "E"),
    ("F4", "F"),
    ("G4", "G"),
    ("A4", "A"),
]

GENERIC_DISPLAY = {
    "m2": "2",
    "M2": "2",
    "m3": "3",
    "M3": "3",
    "P4": "4",
    "A4": "4",
    "d5": "5",
    "P5": "5",
    "m6": "6",
    "M6": "6",
    "m7": "7",
    "M7": "7",
    "P8": "8",
}

SPECIFIC_STAGES = [
    (1, ["P5", "P8"], ["P5", "P8"]),
    (2, ["P5", "P8", "M3", "m3", "M6", "m6"], ["M3", "m3", "M6", "m6", "P5", "P8"]),
    (3, ["P5", "P8", "M3", "m3", "M6", "m6", "M2", "m2", "M7", "m7"], ["M2", "m2", "M7", "m7", "M3", "m3"]),
    (4, ["P5", "P8", "M3", "m3", "M6", "m6", "M2", "m2", "M7", "m7", "P4", "A4", "d5"], ["A4", "d5", "P4", "P5", "M3", "m6"]),
]

GENERIC_STAGES = [
    (1, ["5", "8"], ["P5", "P8"]),
    (2, ["3", "5", "6", "8"], ["M3", "m3", "M6", "m6", "P5", "P8"]),
    (3, ["2", "3", "5", "6", "7", "8"], ["M2", "m2", "M7", "m7", "M3", "m6"]),
    (4, ["2", "3", "4", "5", "6", "7", "8"], ["A4", "d5", "P4", "P5", "M3", "m6"]),
]

LANES = {
    "generic": {
        "analysis_type": "interval_generic",
        "playlist_prefix": "Unit 4 - Generic Intervals",
        "skill_tags": ["unit:4", "Interval_Generic"],
        "stages": GENERIC_STAGES,
    },
    "specific": {
        "analysis_type": "interval_specific",
        "playlist_prefix": "Unit 4 - Specific Intervals",
        "skill_tags": ["unit:4", "Interval_Specific", "interval_quality"],
        "stages": SPECIFIC_STAGES,
    },
}


def _pitch_from_m21(m21_pitch):
    return Pitch(
        step=m21_pitch.step,
        alter=int(m21_pitch.accidental.alter) if m21_pitch.accidental else 0,
        octave=int(m21_pitch.octave),
        midi=int(m21_pitch.midi),
    )


def _interval_pitches(root_scientific, interval_label):
    from music21 import interval, note

    lower = note.Note(root_scientific)
    upper = lower.transpose(interval.Interval(interval_label))
    return _pitch_from_m21(lower.pitch), _pitch_from_m21(upper.pitch)


def _build_worksheet_payload(*, problems, choices, analysis_type, stage):
    lower_events = []
    upper_events = []
    analysis = []
    grading = []

    for idx, problem in enumerate(problems):
      offset = idx * 4.0
      lower_events.append(
          VoiceEvent(
              kind="note",
              pitch=problem["lower_pitch"],
              duration=4.0,
              duration_type="w",
              is_target=True,
          )
      )
      upper_events.append(
          VoiceEvent(
              kind="note",
              pitch=problem["upper_pitch"],
              duration=4.0,
              duration_type="w",
              is_target=True,
          )
      )
      analysis.append(
          AnalysisSlice(
              offset=offset,
              content=AnalysisLayer(functional_label=problem["answer"]),
              unit_tags=[4],
              is_target=True,
          )
      )
      grading.append(
          GradingSlice(
              offset=offset,
              target_midi_pitches=[problem["lower_pitch"].midi, problem["upper_pitch"].midi],
              rhythmic_flexibility=True,
          )
      )

    umto = UMTO(
        metadata=Metadata(
            exercise_id="TEMP",
            source="Identify each interval.",
            key="jC_",
            meter="4/4",
            clef="treble",
            complexity_score=stage,
            mode=InteractionMode.IDENTIFICATION,
            input_mode="dropdown",
            unit=4,
        ),
        voices=Voices(S=upper_events, A=lower_events),
        analysis=analysis,
        grading=grading,
    )

    payload = umto.to_frontend_payload(unit=4, analysis_type=analysis_type)
    payload["identMode"] = "practice"
    payload["inputMode"] = "dropdown"
    payload["staffDistribution"] = "treble"
    payload["disableComputerKeyboardInput"] = True
    payload["display"] = {
        "showNotation": True,
        "hideKeyLabel": True,
        "maxMeasures": len(problems),
        "firstMeasureExtraWidth": 28,
        "noteXShift": 8,
    }
    payload["allowed_answers"] = list(choices)
    payload["analysisPolicy"] = {"allowedValues": list(choices)}
    return payload


class Command(BaseCommand):
    help = "Create Unit 4 interval identification exercises and playlists."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Email of exercise author")
        parser.add_argument("--public", action="store_true", help="Make exercises public")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exercises")
        parser.add_argument("--lane", choices=["generic", "specific", "both"], default="both")
        parser.add_argument(
            "--max-per-stage",
            type=int,
            default=WORKSHEETS_PER_STAGE,
            help="Number of worksheet exercises to create per stage",
        )
        parser.add_argument(
            "--intervals-per-exercise",
            type=int,
            default=INTERVALS_PER_WORKSHEET,
            help="Number of interval prompts in each worksheet exercise",
        )
        # Kept for compatibility with the earlier Unit 4 plan/admin form.
        parser.add_argument("--voice-pair", default="soprano-alto")
        parser.add_argument("--riemenschneider", default=None)
        parser.add_argument("--measures", type=int, default=4)

    def handle(self, *args, **options):
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc
        if options["max_per_stage"] < 1:
            raise CommandError("--max-per-stage must be at least 1")
        if options["intervals_per_exercise"] < 1:
            raise CommandError("--intervals-per-exercise must be at least 1")

        lanes = ["generic", "specific"] if options["lane"] == "both" else [options["lane"]]
        for lane in lanes:
            self._handle_lane(author, lane, options)

    def _handle_lane(self, author, lane, options):
        lane_def = LANES[lane]
        for stage, choices, interval_pool in lane_def["stages"]:
            skill_tags = lane_def["skill_tags"] + [f"unit:4_L{stage}"]
            created_exercises = []

            for worksheet_idx in range(options["max_per_stage"]):
                problems = []
                descriptions = []
                for prompt_idx in range(options["intervals_per_exercise"]):
                    global_idx = worksheet_idx * options["intervals_per_exercise"] + prompt_idx
                    interval_label = interval_pool[global_idx % len(interval_pool)]
                    root_scientific, root_label = ROOTS[global_idx % len(ROOTS)]
                    lower_pitch, upper_pitch = _interval_pitches(root_scientific, interval_label)
                    answer = GENERIC_DISPLAY[interval_label] if lane == "generic" else interval_label
                    problem = {
                        "lower_pitch": lower_pitch,
                        "upper_pitch": upper_pitch,
                        "answer": answer,
                    }
                    problems.append(problem)
                    descriptions.append(f"{root_label} {interval_label}->{answer}")

                desc = f"Unit 4 {lane.title()} Intervals Worksheet - Stage {stage} Set {worksheet_idx + 1}"
                ex = self._save_exercise(
                    author=author,
                    description=desc,
                    payload=_build_worksheet_payload(
                        problems=problems,
                        choices=choices,
                        analysis_type=lane_def["analysis_type"],
                        stage=stage,
                    ),
                    skill_tags=skill_tags,
                    complexity=stage * 10,
                    is_public=options["public"],
                    overwrite=options["overwrite"],
                )
                created_exercises.append(ex)
                self.stdout.write(
                    f"  {desc}: {len(problems)} prompts ({', '.join(descriptions[:4])}...) (id={ex.id})"
                )

            self._build_playlist(
                author=author,
                playlist_name=f"{lane_def['playlist_prefix']}: Stage {stage}",
                exercises=created_exercises,
                skill_tags=lane_def["skill_tags"] + [f"unit:4_L{stage}"],
                is_public=options["public"],
                stage=stage,
                choices=choices,
            )

    def _save_exercise(self, *, author, description, payload, skill_tags, complexity, is_public, overwrite):
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

    def _build_playlist(self, *, author, playlist_name, exercises, skill_tags, is_public, stage, choices):
        playlist, created = Playlist.objects.get_or_create(
            name=playlist_name,
            authored_by=author,
            defaults=dict(is_dynamic=False, is_adaptive=False, is_public=is_public, skill_tags=skill_tags),
        )
        if not created:
            playlist.skill_tags = skill_tags
            if is_public:
                playlist.is_public = True
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            playlist.save()

        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for order, ex in enumerate(exercises, start=1):
            ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=ex, order=order)
        self.stdout.write(self.style.SUCCESS(
            f"Stage {stage} ({len(choices)} choices): {len(exercises)} exercises -> playlist '{playlist_name}'"
        ))
