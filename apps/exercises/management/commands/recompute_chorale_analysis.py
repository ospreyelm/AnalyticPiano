"""Recompute score.umto.analysis on chorale-derived exercises (those tagged
riem:N) by re-running _build_roman_analysis_overrides against the current
music21 corpus + analysis pipeline. Does NOT regenerate the Exercise row;
only overwrites the analysis array in stored UMTO.

Use after fixes to the analysis pipeline (e.g. NCT figured-bass preservation,
suspension reconciliation) to refresh existing rows without re-importing
each phrase end-to-end.

Usage:
    python manage.py recompute_chorale_analysis
    python manage.py recompute_chorale_analysis --tag qa:harm_fb_audit_2026_05_18_declared_key
    python manage.py recompute_chorale_analysis --riem 3
    python manage.py recompute_chorale_analysis --dry-run
"""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise


_DESC_MEASURES_RE = re.compile(r"mm\.(\d+)-(\d+)")
_RIEM_TAG_RE = re.compile(r"^riem:(\d+)$")


class Command(BaseCommand):
    help = (
        "Recompute score.umto.analysis on chorale-derived rows without "
        "regenerating the exercise."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag",
            type=str,
            default=None,
            help="Only refresh rows whose skill_tags contain this tag.",
        )
        parser.add_argument(
            "--riem",
            type=int,
            default=None,
            help="Only refresh rows tagged riem:<N> with this N.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing.",
        )

    def handle(self, *args, **options):
        # Imports kept inside handle() so importing this module doesn't pay
        # the music21 startup cost when other commands are loaded.
        from music21.corpus import chorales
        from apps.exercises.management.commands.import_bach_phrases import (
            _build_roman_analysis_overrides,
        )

        qs = Exercise.objects.all()
        if options["tag"]:
            qs = qs.filter(skill_tags__contains=[options["tag"]])
        if options["riem"] is not None:
            qs = qs.filter(skill_tags__contains=[f"riem:{options['riem']}"])

        # Cache loaded chorales so multi-phrase batches don't re-fetch.
        score_cache: dict[int, object] = {}
        key_cache: dict[int, object] = {}

        updated = 0
        unchanged = 0
        skipped = 0

        for ex in qs.iterator():
            riem_num = self._extract_riem(ex)
            if riem_num is None:
                skipped += 1
                continue

            measure_range = self._extract_measure_range(ex.description or "")
            if measure_range is None:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  skip {ex.id}: cannot parse measure range from description "
                    f"{ex.description!r}"
                ))
                continue
            start_m, end_m = measure_range

            try:
                score = score_cache.get(riem_num)
                if score is None:
                    iterator = chorales.Iterator(
                        riem_num, riem_num, numberingSystem="riemenschneider"
                    )
                    score = list(iterator)[0]
                    score_cache[riem_num] = score
                global_key = key_cache.get(riem_num)
                if global_key is None:
                    global_key = score.analyze("key")
                    key_cache[riem_num] = global_key
                phrase_score = score.measures(start_m, end_m)
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.ERROR(
                    f"  skip {ex.id}: music21 fetch failed ({riem_num}, "
                    f"mm.{start_m}-{end_m}): {e}"
                ))
                continue

            # Unit numbers stored as `unit:N` skill tags.
            unit_nums = []
            for tag in ex.skill_tags or []:
                m = re.match(r"^unit:(\d+)$", tag)
                if m:
                    unit_nums.append(int(m.group(1)))

            try:
                new_overrides = _build_roman_analysis_overrides(
                    phrase_score, global_key, unit_nums, riem_num
                )
            except CommandError as e:
                skipped += 1
                self.stdout.write(self.style.ERROR(
                    f"  skip {ex.id}: build_roman_analysis_overrides failed: {e}"
                ))
                continue
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.ERROR(
                    f"  skip {ex.id}: unexpected error: {e}"
                ))
                continue

            data = ex.data or {}
            umto = (data.get("score") or {}).get("umto")
            if not umto:
                skipped += 1
                continue

            old_overrides = umto.get("analysis") or []
            if old_overrides == new_overrides:
                unchanged += 1
                continue

            diff_msg = f"{len(old_overrides)} → {len(new_overrides)} slices"
            if options["dry_run"]:
                self.stdout.write(f"  WOULD UPDATE {ex.id} (R{riem_num} mm.{start_m}-{end_m}): {diff_msg}")
                updated += 1
                continue

            umto["analysis"] = new_overrides
            ex.data = data
            ex.save(update_fields=["data"])
            updated += 1
            self.stdout.write(
                f"  updated {ex.id} (R{riem_num} mm.{start_m}-{end_m}): {diff_msg}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. updated={updated} unchanged={unchanged} skipped={skipped}"
        ))

    @staticmethod
    def _extract_riem(ex: Exercise) -> int | None:
        for tag in ex.skill_tags or []:
            m = _RIEM_TAG_RE.match(tag)
            if m:
                return int(m.group(1))
        return None

    @staticmethod
    def _extract_measure_range(description: str) -> tuple[int, int] | None:
        m = _DESC_MEASURES_RE.search(description)
        if not m:
            return None
        return (int(m.group(1)), int(m.group(2)))
