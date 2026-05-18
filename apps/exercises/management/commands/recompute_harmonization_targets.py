"""Recompute and overwrite stored `harmonizationTargets` for harmonization exercises.

Use after fixes to the target-derivation pipeline (e.g. NCT-slice gating)
to refresh existing rows without regenerating the whole exercise.

Default scope: every Exercise whose `data.mode == "harmonization"`.
Filter by skill tag with `--tag` to target a specific batch.

Usage:
    python manage.py recompute_harmonization_targets
    python manage.py recompute_harmonization_targets --tag qa:harm_fb_audit_2026_05_17
    python manage.py recompute_harmonization_targets --dry-run
"""
from django.core.management.base import BaseCommand

from apps.exercises.harmonization.targets import build_targets_from_umto
from apps.exercises.models import Exercise


class Command(BaseCommand):
    help = "Recompute harmonizationTargets for existing harmonization Exercise rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag",
            type=str,
            default=None,
            help="Only recompute rows whose skill_tags contain this tag.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        qs = Exercise.objects.all()
        if options["tag"]:
            qs = qs.filter(skill_tags__contains=[options["tag"]])

        updated = 0
        unchanged = 0
        skipped = 0

        for ex in qs.iterator():
            data = ex.data or {}
            if data.get("mode") != "harmonization":
                continue

            umto = (data.get("score") or {}).get("umto")
            if not umto:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  skip {ex.id}: no score.umto"
                ))
                continue

            try:
                new_targets = build_targets_from_umto(umto)
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.ERROR(
                    f"  skip {ex.id}: build_targets_from_umto failed: {e}"
                ))
                continue

            old_targets = data.get("harmonizationTargets") or []
            if old_targets == new_targets:
                unchanged += 1
                continue

            diff_msg = f"{len(old_targets)} → {len(new_targets)} targets"
            if options["dry_run"]:
                self.stdout.write(f"  WOULD UPDATE {ex.id}: {diff_msg}")
                updated += 1
                continue

            data["harmonizationTargets"] = new_targets
            ex.data = data
            ex.save(update_fields=["data"])
            updated += 1
            self.stdout.write(f"  updated {ex.id}: {diff_msg}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. updated={updated} unchanged={unchanged} skipped={skipped}"
        ))
