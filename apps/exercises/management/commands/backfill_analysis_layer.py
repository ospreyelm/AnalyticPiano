"""Backfill analytics fields on existing UMTO chordal analysis slices."""

from django.core.management.base import BaseCommand

from apps.exercises.models import Exercise
from apps.exercises.utils.umto_import_router import build_chordal_analysis_slices


ANALYTICS_FIELDS = (
    "set_class_prime",
    "set_class_forte",
    "set_class_normal",
    "set_class_set",
    "spacing",
    "interval_specific",
    "interval_generic",
)


class Command(BaseCommand):
    help = "Populate set_class_* and interval_* fields in UMTO chordal AnalysisLayer slices."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Overwrite existing analytics fields.")
        parser.add_argument("--dry-run", action="store_true", help="Report counts without writing.")

    def handle(self, *args, **options):
        overwrite = options["all"]
        dry_run = options["dry_run"]
        updated = skipped = errors = 0

        qs = Exercise.objects.all().only("id", "data")
        for ex in qs.iterator(chunk_size=100):
            data = ex.data
            if not isinstance(data, dict) or data.get("isUMTO") is not True:
                continue
            score = data.get("score", {})
            umto = score.get("umto", {}) if isinstance(score, dict) else {}
            metadata = umto.get("metadata", {}) if isinstance(umto, dict) else {}
            if metadata.get("score_kind") != "chordal":
                continue

            analysis = umto.get("analysis", [])
            chords = umto.get("chords", [])
            if not analysis or not chords:
                skipped += 1
                continue

            if not overwrite:
                first_content = analysis[0].get("content", {}) if isinstance(analysis[0], dict) else {}
                if first_content.get("set_class_prime") is not None:
                    skipped += 1
                    continue

            try:
                new_slices = build_chordal_analysis_slices(
                    chords,
                    harmony_key=metadata.get("key", "C"),
                )
            except Exception as exc:
                self.stderr.write(f"[{ex.id}] {exc}")
                errors += 1
                continue

            for index, old_slice in enumerate(analysis):
                if index >= len(new_slices) or not isinstance(old_slice, dict):
                    break
                new_content = new_slices[index].get("content", {})
                old_content = old_slice.setdefault("content", {})
                for field in ANALYTICS_FIELDS:
                    if overwrite or field not in old_content:
                        old_content[field] = new_content.get(field)

            if not dry_run:
                ex.data = data
                ex.save(update_fields=["data"])
            updated += 1

        suffix = " (dry-run)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"updated={updated} skipped={skipped} errors={errors}{suffix}"
        ))
