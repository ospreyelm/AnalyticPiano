"""
seed_skill_prerequisites.py — Populate the global default skill prerequisite DAG.

Idempotent: uses get_or_create for each edge so it is safe to re-run.

Usage:
    python manage.py seed_skill_prerequisites
    python manage.py seed_skill_prerequisites --clear  # wipe globals and re-seed
"""
from django.core.management.base import BaseCommand

from apps.exercises.models import SkillPrerequisite
from apps.exercises.skill_graph import DEFAULT_PREREQUISITES


class Command(BaseCommand):
    help = "Seed the global default skill prerequisite DAG into the SkillPrerequisite table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing global (course=None) prerequisites before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = SkillPrerequisite.objects.filter(course__isnull=True).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing global prerequisites."))

        created_count = 0
        skipped_count = 0

        for skill_tag, requires_list in DEFAULT_PREREQUISITES.items():
            for requires_tag in requires_list:
                _, created = SkillPrerequisite.objects.get_or_create(
                    course=None,
                    skill_tag=skill_tag,
                    requires_tag=requires_tag,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete. Created: {created_count} edges. "
                f"Already existed: {skipped_count} edges."
            )
        )
