"""Retired legacy Unit 1 seeding command.

This command used to create the deprecated four-category Unit 1 student
structure (for example, "1.1 Note Names"). That structure is retired and must
not be recreated. Use the curated Unit 1 mapping workflow instead.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Retired: this legacy Unit 1 seeding path no longer creates student "
        "content. Use the curated Unit 1 mapping workflow instead."
    )

    def handle(self, *args, **options):
        raise CommandError(
            "seed_unit1_content is retired because it can recreate the "
            'deprecated four-category Unit 1 structure (for example, "1.1 '
            'Note Names"). Use the curated Unit 1 mapping workflow instead.'
        )
