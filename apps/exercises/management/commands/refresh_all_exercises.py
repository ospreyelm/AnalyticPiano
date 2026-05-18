"""Dispatcher that refreshes every UMTO exercise in the DB after an
analysis-pipeline change. Runs:

  1. recompute_chorale_analysis   — rebuilds score.umto.analysis on
                                     rows tagged riem:N (chorale-derived)
  2. recompute_harmonization_targets — rebuilds harmonizationTargets
                                       on every harmonization row

Both sub-commands are idempotent; this command is too. Pass --tag to
restrict scope.

Usage:
    python manage.py refresh_all_exercises
    python manage.py refresh_all_exercises --tag qa:harm_fb_audit_2026_05_18_declared_key
    python manage.py refresh_all_exercises --dry-run

Skipped categories (no automatic refresh — regenerate via their
generator if the pipeline changed):
  - Unit 1 pitch identification (generate_unit1)
  - Unit 2 meter / barline (generate_unit2_*)
  - Unit 3 key sig / scales (generate_unit3_*)
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Refresh chorale analysis + harmonization targets across all UMTO "
        "exercises. Wraps recompute_chorale_analysis and "
        "recompute_harmonization_targets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag",
            type=str,
            default=None,
            help="Restrict refresh to rows whose skill_tags contain this tag.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n[1/2] recompute_chorale_analysis"
        ))
        chorale_kwargs = {"dry_run": options["dry_run"]}
        if options["tag"]:
            chorale_kwargs["tag"] = options["tag"]
        try:
            call_command("recompute_chorale_analysis", **chorale_kwargs)
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"recompute_chorale_analysis failed: {e}"
            ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n[2/2] recompute_harmonization_targets (with --resync-from-source)"
        ))
        # Resync from source so harmonization rows pick up refreshed analysis
        # from step [1/2] before rebuilding targets.
        harm_kwargs = {
            "dry_run": options["dry_run"],
            "resync_from_source": True,
        }
        if options["tag"]:
            harm_kwargs["tag"] = options["tag"]
        try:
            call_command("recompute_harmonization_targets", **harm_kwargs)
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"recompute_harmonization_targets failed: {e}"
            ))

        self.stdout.write(self.style.SUCCESS(
            "\nrefresh_all_exercises complete. See per-step output above."
        ))
        self.stdout.write(self.style.WARNING(
            "Note: Unit 1/2/3 generator-produced exercises are not refreshed "
            "automatically. Re-run their generators if those pipelines changed."
        ))
