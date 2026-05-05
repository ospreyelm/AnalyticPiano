from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.symbolic_meter_questions import (
    build_symbolic_problem_set,
    load_manifest_rows,
)
from apps.exercises.umto_factory import save_umto_symbolic_exercise

PLAYLIST_NAME = "Unit 2 — Symbolic Meter Questions"
PLAYLIST_SKILL_TAGS = [
    "unit:2",
    "unit:2_rhythm",
    "unit:2_meter_simple",
    "unit:2_meter_compound",
]


class Command(BaseCommand):
    help = "Create Unit 2 symbolic meter exercises from the curated manifest"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")

    def handle(self, *args, **options):
        user_model = get_user_model()
        author_email = options["author"]
        try:
            author = user_model.objects.get(email=author_email)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {author_email}") from exc

        problems = build_symbolic_problem_set(load_manifest_rows())
        exercise = save_umto_symbolic_exercise(
            description="Unit 2 symbolic meter questions",
            author=author,
            problems=problems,
            source="Unit 2 symbolic meter questions",
            unit=2,
            is_public=options["public"],
        )

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
            if options["public"]:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in PLAYLIST_SKILL_TAGS:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            playlist.save()

        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=exercise,
            order=1,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {exercise.id} and linked it to playlist '{playlist.name}' ({playlist.id})"
            )
        )
