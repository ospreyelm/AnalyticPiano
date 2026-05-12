from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_umto_barline_exercise
from apps.exercises.utils.barline_exercise_builder import build_barline_payload

PLAYLIST_NAME = "Unit 2 — Add Barlines"
PLAYLIST_SKILL_TAGS = [
    "unit:2",
    "unit:2_rhythm",
    "unit:2_meter_simple",
    "unit:2_meter_compound",
]

SIMPLE_METERS = {"2/4", "3/4", "4/4"}
COMPOUND_METER_BEATS = {
    "6/8": 2,
    "9/8": 3,
    "12/8": 4,
}


def _manual_notes(meter, measures):
    if measures < 1:
        raise CommandError("--measures must be at least 1")
    if meter in SIMPLE_METERS:
        beats = int(meter.split("/")[0]) * measures
        return [{"pitch": "B4", "duration": "q", "dots": 0} for _ in range(beats)]
    if meter in COMPOUND_METER_BEATS:
        beats = COMPOUND_METER_BEATS[meter] * measures
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(beats)]
    raise CommandError(f"Unsupported meter: {meter}")


class Command(BaseCommand):
    help = "Create Unit 2 add-barlines exercises"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--meter", default="3/4")
        parser.add_argument("--measures", type=int, default=2)
        parser.add_argument("--pitch-mode", default="rhythm_only")
        parser.add_argument(
            "--source",
            choices=["manual", "essen", "kern"],
            default="manual",
        )

    def handle(self, *args, **options):
        if options["count"] < 1:
            raise CommandError("--count must be at least 1")

        user_model = get_user_model()
        author_email = options["author"]
        try:
            author = user_model.objects.get(email=author_email)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {author_email}") from exc

        if options["source"] != "manual":
            raise CommandError(
                "Essen/Kern import is not implemented yet; "
                "use --source manual for deterministic dev seed"
            )

        notes = _manual_notes(options["meter"], options["measures"])

        playlist, created = Playlist.objects.get_or_create(
            name=PLAYLIST_NAME,
            authored_by=author,
            defaults=dict(
                is_dynamic=False,
                is_adaptive=False,
                is_public=options["public"],
                skill_tags=list(PLAYLIST_SKILL_TAGS),
            ),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            if options["public"]:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in PLAYLIST_SKILL_TAGS:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.save()

        exercise_is_public = playlist.is_public
        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for index in range(options["count"]):
            payload = build_barline_payload(
                time_signature=options["meter"],
                clef="treble",
                notes=list(notes),
                measures=options["measures"],
                show_time_signature=index % 2 == 0,
                pitch_mode=options["pitch_mode"],
                source="Unit 2 add barlines manual seed",
                tags=list(PLAYLIST_SKILL_TAGS),
            )
            exercise = save_umto_barline_exercise(
                description=f"Unit 2 add barlines {options['meter']} #{index + 1}",
                author=author,
                payload=payload,
                is_public=exercise_is_public,
                overwrite=True,
            )
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist,
                exercise=exercise,
                order=index + 1,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {options['count']} barline exercise(s) in '{playlist.name}'"
            )
        )
