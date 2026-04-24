import json
from django.core.management.base import BaseCommand
from apps.exercises.umto import UMTO


class Command(BaseCommand):
    help = "Generate and save the JSON schema for UMTO to apps/exercises/umto_schema.json"

    def handle(self, *args, **options):
        schema = UMTO.model_json_schema()
        target = "apps/exercises/umto_schema.json"
        with open(target, "w") as f:
            json.dump(schema, f, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Successfully saved UMTO schema to {target}"))
