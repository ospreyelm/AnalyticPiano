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
        ).order_by("description", "created", "_id")

        groups = defaultdict(list)
        for ex in rows:
            groups[ex.description].append(ex)

        duplicate_groups = {desc: xs for desc, xs in groups.items() if len(xs) > 1}
        all_dup_ids = [ex.pk for xs in duplicate_groups.values() for ex in xs]
        # Only protect exercises referenced by real (non-auto) playlists.
        # Auto-playlists are per-exercise scratch pads — safe to lose.
        protected_ids = set(
            ExercisePlaylistOrdered.objects.filter(
                exercise_id__in=all_dup_ids,
                playlist__is_auto=False,
            ).values_list("exercise_id", flat=True)
        )

        delete_pks = []
        for desc, xs in duplicate_groups.items():
            for ex in xs[1:]:
                if ex.pk in protected_ids:
                    self.stdout.write(
                        self.style.WARNING(
                            f"protected (playlist-referenced) duplicate {ex.id}: {desc}"
                        )
                    )
                    continue
                delete_pks.append(ex.pk)

        self.stdout.write(f"Duplicate descriptions: {len(duplicate_groups)}")
        self.stdout.write(f"Unreferenced duplicates to delete: {len(delete_pks)}")

        if options["execute"] and delete_pks:
            deleted, _ = Exercise.objects.filter(pk__in=delete_pks).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} rows."))
        elif not options["execute"]:
            self.stdout.write("Dry run only. Pass --execute to delete unreferenced duplicates.")
