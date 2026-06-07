from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise
from apps.exercises.utils.umto_import_router import (
    iter_legacy_chord_csv_rows,
    legacy_csv_row_to_chordal_payload,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Import legacy CSV data.chord rows as chordal UMTO exercises."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to legacy exercises CSV")
        parser.add_argument("--author", type=str, required=True, help="Author email for new exercises")
        parser.add_argument("--public", action="store_true", help="Make imported exercises public")
        parser.add_argument("--dry-run", action="store_true", help="Parse and validate without writing")
        parser.add_argument("--limit", type=int, default=None, help="Maximum rows to process")

    def handle(self, *args, **options):
        path = options["path"]
        dry_run = options["dry_run"]
        limit = options["limit"]

        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f'User with email "{options["author"]}" not found') from exc

        parsed = 0
        imported = 0
        with open(path, newline="") as handle:
            for row in iter_legacy_chord_csv_rows(handle):
                if limit is not None and parsed >= limit:
                    break
                parsed += 1
                payload = legacy_csv_row_to_chordal_payload(row)
                if dry_run:
                    continue
                exercise = Exercise(
                    description=row.description or row.exercise_id,
                    data=payload,
                    authored_by=author,
                    is_public=options["public"],
                    skill_tags=[],
                    complexity=payload["score"]["umto"]["metadata"].get("complexity_score", 1),
                    time_signature=payload["meter"],
                )
                exercise.save()
                exercise.data["score"]["umto"]["metadata"]["exercise_id"] = exercise.id
                exercise.save(update_fields=["data"])
                imported += 1

        self.stdout.write(f"Parsed {parsed} legacy chord rows.")
        if dry_run:
            self.stdout.write("Dry run: no exercises written.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Imported {imported} chordal UMTO exercises."))

