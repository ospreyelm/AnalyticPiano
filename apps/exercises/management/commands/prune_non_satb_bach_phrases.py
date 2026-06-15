import re

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from apps.exercises.management.commands.import_bach_phrases import (
    NON_SATB_RIEMENSCHNEIDER_NUMBERS,
    _parse_riemenschneider_arg,
)
from apps.exercises.models import Exercise, ExercisePlaylistOrdered


RIEM_RE = re.compile(r"\bBach\s+R(\d+)\s+-\s+Phrase\b")


def _extract_riemenschneider(description: str | None) -> int | None:
    match = RIEM_RE.search(description or "")
    if not match:
        return None
    return int(match.group(1))


def _target_exercises(author, riem_numbers: set[int]):
    candidates = Exercise.objects.filter(
        authored_by=author,
        description__startswith="Bach R",
    ).order_by("description", "id")
    return [
        ex for ex in candidates
        if _extract_riemenschneider(ex.description) in riem_numbers
    ]


class Command(BaseCommand):
    help = "Dry-run or delete Bach phrase exercises imported from non-four-part Riemenschneider sources."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument(
            "--riemenschneider",
            default=",".join(str(n) for n in sorted(NON_SATB_RIEMENSCHNEIDER_NUMBERS)),
            help="Riemenschneider number/range/list to prune. Defaults to known non-four-part sources.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Delete matching Exercise rows. Dry-run only without this flag.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Print every matching exercise and linked playlist count.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{options['author']}'.")

        riem_numbers = set(_parse_riemenschneider_arg(options["riemenschneider"]))
        targets = _target_exercises(author, riem_numbers)
        target_pks = [ex.pk for ex in targets]
        link_count = ExercisePlaylistOrdered.objects.filter(exercise_id__in=target_pks).count()
        playlist_count = (
            ExercisePlaylistOrdered.objects
            .filter(exercise_id__in=target_pks)
            .values("playlist_id")
            .distinct()
            .count()
        )

        self.stdout.write(f"Author: {author.email}")
        self.stdout.write(f"Riemenschneider sources: {', '.join(str(n) for n in sorted(riem_numbers))}")
        self.stdout.write(f"Target exercises: {len(targets)}")
        self.stdout.write(f"Playlist links to remove: {link_count}")
        self.stdout.write(f"Affected playlists: {playlist_count}")

        if options["list"]:
            link_counts = {
                row["exercise_id"]: row["count"]
                for row in (
                    ExercisePlaylistOrdered.objects
                    .filter(exercise_id__in=target_pks)
                    .values("exercise_id")
                    .annotate(count=Count("_id"))
                )
            }
            for ex in targets:
                self.stdout.write(f"  {ex.id}: {ex.description} ({link_counts.get(ex.pk, 0)} links)")

        if not options["execute"]:
            self.stdout.write("Dry run only. Pass --execute to delete matching exercises.")
            return

        with transaction.atomic():
            deleted, detail = Exercise.objects.filter(pk__in=target_pks).delete()

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} rows."))
        if detail:
            for model, count in sorted(detail.items()):
                self.stdout.write(f"  {model}: {count}")
