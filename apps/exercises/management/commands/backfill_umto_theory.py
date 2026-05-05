import json
from django.core.management.base import BaseCommand
from apps.exercises.models import Exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_umto_payload

class Command(BaseCommand):
    help = "Backfill theory analysis (roman numerals/pitch names) for UMTO exercises"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--unit", type=int, help="Filter by unit")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        unit_filter = options["unit"]

        # Only process UMTO exercises. We filter in Python to avoid Postgres json/jsonb type mismatch.
        qs = Exercise.objects.all().iterator()
        
        count = 0
        processed = 0
        self.stdout.write("Iterating through exercises...")

        for ex in qs:
            if ex.data.get("type") != "umto_chorale":
                continue
            
            processed += 1
            umto_data = ex.data.get("score", {}).get("umto", {})
            metadata = umto_data.get("metadata", {})
            
            # Infer unit from skill_tags if missing from metadata
            unit = metadata.get("unit")
            if unit is None:
                for tag in ex.skill_tags:
                    if tag.startswith("unit:"):
                        try:
                            unit = int(tag.split(":")[1])
                            break
                        except:
                            pass
            
            if unit_filter and unit_filter != unit:
                continue
            
            try:
                # Rebuild payload using the factory (which now generates theory)
                new_payload = build_umto_payload(
                    exercise_id=ex.id,
                    source=metadata.get("source", ""),
                    key=metadata.get("key", "C"),
                    meter=metadata.get("meter", "4/4"),
                    clef=metadata.get("clef", "treble"),
                    complexity_score=metadata.get("complexity_score", 1),
                    mode=InteractionMode(metadata.get("mode", "playback")),
                    score_data=ex.data.get("score", {}),
                    input_mode=metadata.get("input_mode", "dropdown"),
                    unit=unit
                )
                
                if not dry_run:
                    ex.data = new_payload
                    ex.save()
                
                count += 1
                if count % 10 == 0:
                    self.stdout.write(f"Processed {count}...")
            except Exception as e:
                self.stderr.write(f"Failed {ex.id}: {e}")

        self.stdout.write(f"Successfully processed {count} exercises.")
