from django.core.management.base import BaseCommand

from apps.exercises.models import Exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_umto_payload


def _needs_backfill(analysis_slices: list[dict]) -> bool:
    if not analysis_slices:
        return False
    return any(
        (slice_dict.get("content", {}).get("raw_roman_numeral") is None)
        for slice_dict in analysis_slices
    )


class Command(BaseCommand):
    help = "Backfill raw_roman_numeral for UMTO exercises that do not already store it"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--unit", type=int, help="Filter by unit")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        unit_filter = options.get("unit")

        updated = 0
        skipped = 0

        for ex in Exercise.objects.all().iterator():
            score = ex.data.get("score", {})
            umto_data = score.get("umto", {})
            metadata = umto_data.get("metadata", {})
            analysis = umto_data.get("analysis", [])

            if not ex.data.get("isUMTO") or not umto_data:
                skipped += 1
                continue

            unit = metadata.get("unit")
            if unit_filter is not None and unit != unit_filter:
                skipped += 1
                continue

            if not _needs_backfill(analysis):
                skipped += 1
                continue

            self.stdout.write(f"{ex.id}: backfilling raw_roman_numeral")
            if not dry_run:
                payload = build_umto_payload(
                    exercise_id=metadata.get("exercise_id", ex.id),
                    source=metadata.get("source", ex.description or ""),
                    key=metadata.get("key", "C"),
                    meter=metadata.get("meter", "4/4"),
                    clef=metadata.get("clef", "treble"),
                    complexity_score=metadata.get("complexity_score", ex.complexity or 1),
                    mode=InteractionMode(metadata.get("mode", "playback")),
                    score_data=score,
                    input_mode=metadata.get("input_mode", "dropdown"),
                    unit=unit,
                )
                ex.data = payload
                ex.save()
            updated += 1

        self.stdout.write(f"Done. Updated: {updated}, skipped: {skipped}")
