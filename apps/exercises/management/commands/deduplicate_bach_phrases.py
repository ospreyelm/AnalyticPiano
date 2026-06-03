from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, ExercisePlaylistOrdered


class Command(BaseCommand):
    help = "Audit or delete unreferenced duplicate Bach phrase exercises for one author."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{options['author']}'.")

        rows = Exercise.objects.filter(
            authored_by=author,
            description__startswith="Bach R",
        ).order_by("description", "-created", "_id")

        groups = defaultdict(list)
        for ex in rows:
            groups[ex.description].append(ex)

        duplicate_groups = {desc: xs for desc, xs in groups.items() if len(xs) > 1}
        delete_ids = []
        protected_ids = set(
            ExercisePlaylistOrdered.objects.filter(
                exercise_id__in=[ex.pk for xs in duplicate_groups.values() for ex in xs]
            ).exclude(
                playlist__is_auto=True
            ).values_list("exercise_id", flat=True)
        )

        for desc, xs in duplicate_groups.items():
            keep = xs[0]
            for ex in xs[1:]:
                if ex.pk in protected_ids:
                    self.stdout.write(self.style.WARNING(f"protected referenced duplicate {ex.id}: {desc}"))
                    continue
                delete_ids.append(ex.pk)

        self.stdout.write(f"Duplicate descriptions: {len(duplicate_groups)}")
        self.stdout.write(f"Unreferenced duplicates to delete: {len(delete_ids)}")

        if options["execute"] and delete_ids:
            deleted, _ = Exercise.objects.filter(pk__in=delete_ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} rows."))
        elif not options["execute"]:
            self.stdout.write("Dry run only. Pass --execute to delete unreferenced duplicates.")
