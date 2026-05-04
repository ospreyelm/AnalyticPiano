from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.symbolic_meter_questions import (
    build_symbolic_problem_set,
    load_manifest_rows,
)
from apps.exercises.umto_factory import save_umto_symbolic_exercise


class Command(BaseCommand):
    help = "Create Unit 2 symbolic meter exercises from the curated manifest"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)

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
        )
        self.stdout.write(self.style.SUCCESS(f"Created {exercise.id}"))
