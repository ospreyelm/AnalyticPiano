import copy
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.exercises.models import Exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()


class Command(BaseCommand):
    help = "Duplicate an existing chorale exercise as a UMTO identification exercise"

    def add_arguments(self, parser):
        parser.add_argument("exercise_id", type=str, help="ID of the source chorale exercise")
        parser.add_argument("--author", type=str, required=True, help="Email of the exercise author")
        parser.add_argument(
            "--public",
            action="store_true",
            help="Set new exercise as public (defaults to source visibility)",
        )

    def handle(self, *args, **options):
        exercise_id = options["exercise_id"]
        author_email = options["author"]
        force_public = options["public"]

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        try:
            source = Exercise.objects.get(id=exercise_id)
        except Exercise.DoesNotExist:
            raise CommandError(f'Exercise with id "{exercise_id}" not found')

        source_data = source.data or {}
        if source_data.get("type") not in ("chorale", "umto_chorale"):
            raise CommandError("Source exercise must have data.type='chorale' or 'umto_chorale'")

        score = copy.deepcopy(source_data.get("score", {}))
        if not score:
            raise CommandError("Source exercise is missing score data")

        # Use the factory to create a guaranteed-valid UMTO exercise
        new_exercise = save_umto_exercise(
            description=f"{source.description or source.id} (identification)",
            score_data=score,
            author=author,
            skill_tags=source.skill_tags,
            complexity=source.complexity,
            is_public=True if force_public else source.is_public,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source=f"Duplicate of {source.id}",
                key=source_data.get("key") or score.get("meta", {}).get("key", "C"),
                meter=score.get("meta", {}).get("time", "4/4"),
                clef=source_data.get("clef") or "keyboard",
                complexity_score=source.complexity or 1,
                mode=InteractionMode.IDENTIFICATION,
                unit=1,
            ),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created UMTO identification exercise {new_exercise.id} from source {source.id}"
            )
        )
