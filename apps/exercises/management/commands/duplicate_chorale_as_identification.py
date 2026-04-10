import copy

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise

User = get_user_model()


class Command(BaseCommand):
    help = "Duplicate an existing chorale exercise as a chorale_identification exercise"

    def add_arguments(self, parser):
        parser.add_argument("exercise_id", type=str, help="ID of the source chorale exercise")
        parser.add_argument("--author", type=str, required=True, help="Email of the exercise author")
        parser.add_argument(
            "--analysis",
            choices=["roman", "figured_bass"],
            default="roman",
            help="Analysis label type for the new identification exercise",
        )
        parser.add_argument(
            "--public",
            action="store_true",
            help="Set new exercise as public (defaults to source visibility)",
        )

    def handle(self, *args, **options):
        exercise_id = options["exercise_id"]
        author_email = options["author"]
        analysis = options["analysis"]
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
        if source_data.get("type") != "chorale":
            raise CommandError("Source exercise must have data.type='chorale'")

        score = copy.deepcopy(source_data.get("score", {}))
        if not score:
            raise CommandError("Source exercise is missing score data")

        new_data = {
            "type": "chorale_identification",
            "identMode": "submit",
            "analysisType": analysis,
            "score": score,
            "key": source_data.get("key") or score.get("meta", {}).get("key", "C"),
            "staffDistribution": "chorale",
            "introText": source_data.get("introText") or "Label the harmony for each onset.",
            "reviewText": source_data.get("reviewText") or "Well done!",
        }

        # Exercise.save() performs a custom two-step save; avoid objects.create(force_insert=True).
        new_exercise = Exercise(
            description=f"{source.description or source.id} (identification)",
            data=new_data,
            authored_by=author,
            is_public=True if force_public else source.is_public,
        )
        new_exercise.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Created chorale_identification exercise {new_exercise.id} from source {source.id}"
            )
        )
