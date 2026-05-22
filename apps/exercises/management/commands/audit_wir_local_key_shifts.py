"""Report inferred local-key transpositions for WiR-backed Bach exercises.

The importer uses When in Rome labels for Roman numerals and local keys, but
some music21 chorales are stored in a different transposition from the WiR
source. This command audits the semitone shift needed per Riemenschneider
number for existing rows tagged `riem:N`.

Usage:
    python manage.py audit_wir_local_key_shifts
    python manage.py audit_wir_local_key_shifts --riem 17
    python manage.py audit_wir_local_key_shifts --tag unit:11
"""
from __future__ import annotations

import re
from collections import Counter

from django.core.management.base import BaseCommand

from apps.exercises.models import Exercise


_RIEM_TAG_RE = re.compile(r"^riem:(\d+)$")


class Command(BaseCommand):
    help = (
        "Scan WiR-backed Bach exercises and report inferred local-key "
        "transposition by Riemenschneider number."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag",
            type=str,
            default=None,
            help="Only audit rows whose skill_tags contain this tag.",
        )
        parser.add_argument(
            "--riem",
            type=int,
            default=None,
            help="Only audit rows tagged riem:<N> with this N.",
        )

    def handle(self, *args, **options):
        from music21.corpus import chorales
        from apps.exercises.management.commands.import_bach_phrases import (
            _infer_wir_local_key_transposition,
        )

        counts = self._riem_counts(options["tag"], options["riem"])
        if not counts:
            self.stdout.write("No WiR-backed Bach exercises found.")
            return

        for riem_num in sorted(counts):
            try:
                score = list(chorales.Iterator(
                    riem_num,
                    riem_num,
                    numberingSystem="riemenschneider",
                ))[0]
                shift = _infer_wir_local_key_transposition(score, riem_num)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"R{riem_num} ERROR rows={counts[riem_num]} {exc}"
                ))
                continue

            self.stdout.write(
                f"R{riem_num} {self._format_shift(shift)} rows={counts[riem_num]}"
            )

    @staticmethod
    def _format_shift(shift: int) -> str:
        if shift > 0:
            return f"+{shift}"
        return str(shift)

    @classmethod
    def _riem_counts(cls, tag: str | None, riem: int | None) -> Counter:
        qs = Exercise.objects.all().only("id", "skill_tags")
        if tag:
            qs = qs.filter(skill_tags__contains=[tag])
        if riem is not None:
            qs = qs.filter(skill_tags__contains=[f"riem:{riem}"])

        counts = Counter()
        for ex in qs.iterator():
            riem_num = cls._extract_riem(ex.skill_tags or [])
            if riem_num is not None:
                counts[riem_num] += 1
        return counts

    @staticmethod
    def _extract_riem(skill_tags: list[str]) -> int | None:
        for tag in skill_tags:
            match = _RIEM_TAG_RE.match(tag)
            if match:
                return int(match.group(1))
        return None

