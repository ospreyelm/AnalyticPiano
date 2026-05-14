from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.key_signature_problems import build_key_sig_problem_set
from apps.exercises.umto_factory import save_umto_key_sig_exercise

User = get_user_model()


class Command(BaseCommand):
    help = "Create Unit 3 key signature identification exercises (3 difficulty levels)"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true")

    def handle(self, *args, **options):
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        for level in [1, 2, 3]:
            desc = f"Unit 3 Key Sig — Identify, Level {level}"
            problems = build_key_sig_problem_set(level=level)

            exercise = save_umto_key_sig_exercise(
                description=desc,
                author=author,
                problems=problems,
                level=level,
                is_public=options["public"],
                overwrite=options["overwrite"],
            )

            playlist_name = f"Unit 3 — Key Signatures, Level {level}"
            playlist_tags = ["unit:3", "unit:3_key_signature", f"unit:3_L{level}"]

            playlist, created = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=False,
                    is_public=options["public"],
                    skill_tags=playlist_tags,
                ),
            )
            if not created:
                playlist.skill_tags = playlist_tags
                if options["public"]:
                    playlist.is_public = True
                playlist.save()

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist, exercise=exercise, order=1
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level}: exercise {exercise.id} → playlist '{playlist_name}'"
                )
            )
