# -*- coding: utf-8 -*-
"""Verify Z7 round-trip realization against vendored compendium notes."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.exercises.compendium_inverse import (
    compare_realized_notes,
    realize_example_from_clausulae,
)
from apps.exercises.compendium_source import load_cadence_examples


class Command(BaseCommand):
    help = "Verify that Z7 compendium realization reproduces the vendored note JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-id",
            default=None,
            help="Verify only one source id, e.g. m145-146.",
        )

    def handle(self, *args, **options):
        examples = load_cadence_examples()
        source_id = options.get("source_id")
        if source_id:
            examples = [example for example in examples if example["id"] == source_id]
            if not examples:
                raise CommandError(f"No compendium example found for --source-id {source_id!r}")

        mismatches: list[tuple[str, list[str]]] = []
        for example in examples:
            realized = realize_example_from_clausulae(example)
            differences = compare_realized_notes(example["notes"], realized)
            if differences:
                mismatches.append((example["id"], differences))

        if mismatches:
            for example_id, differences in mismatches[:10]:
                self.stderr.write(f"{example_id}: {differences[0]}")
            raise CommandError(
                f"Compendium realization mismatches={len(mismatches)} of {len(examples)}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Verified {len(examples)} compendium examples (mismatches=0)"
            )
        )
