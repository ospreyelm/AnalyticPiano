"""Audit which figured-bass figures in the corpus map to a realization
prototype vs fail-safe (all-required). Re-run after curriculum changes to catch
new figures the table doesn't yet model.

Usage:
    python manage.py audit_figure_realization_coverage
    python manage.py audit_figure_realization_coverage --limit 20
"""
import collections

from django.core.management.base import BaseCommand

from apps.exercises.harmonization import figure_realization as fr


class Command(BaseCommand):
    help = "Report figured-bass figures not covered by the realization table."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=40)

    def handle(self, *args, **options):
        from apps.exercises.models import Exercise

        covered = collections.Counter()
        failsafe = collections.Counter()
        for ex in Exercise.objects.all().iterator(chunk_size=2000):
            umto = ((ex.data or {}).get("score") or {}).get("umto") or {}
            for a in umto.get("analysis", []) or []:
                raw = (a.get("content") or {}).get("raw_figured_bass")
                if not raw:
                    continue
                proto, _ = fr.normalize(raw)
                (covered if proto else failsafe)[raw] += 1
        tot = sum(covered.values()) + sum(failsafe.values())
        self.stdout.write(f"total figure occurrences: {tot}")
        self.stdout.write(f"covered by prototype: {sum(covered.values())}")
        self.stdout.write(f"fail-safe (all required): {sum(failsafe.values())}")
        self.stdout.write("--- top fail-safe figures (consider adding rows) ---")
        for raw, n in failsafe.most_common(options["limit"]):
            self.stdout.write(f"  {raw!r:14} {n}")
