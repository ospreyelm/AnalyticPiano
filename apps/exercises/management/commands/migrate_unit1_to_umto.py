import json
from django.core.management.base import BaseCommand
from apps.exercises.models import Exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import build_umto_payload

class Command(BaseCommand):
    help = "Migrate legacy Unit 1 identification exercises to UMTO format"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        import os
        os.environ["HARMONYLAB_ALLOW_LEGACY_EXERCISE"] = "1"
        dry_run = options["dry_run"]
        limit = options["limit"]

        # Fetch and filter in Python to avoid json vs jsonb operator issues
        all_qs = Exercise.objects.filter(skill_tags__overlap=["unit:1"])
        
        if limit:
            all_qs = all_qs[:limit]

        # Filter in Python: both legacy and those already UMTO but missing mode
        qs = [ex for ex in all_qs if ex.data.get("type") == "chorale_identification" or (ex.data.get("type") == "umto_chorale" and "mode" not in ex.data)]
        total = len(qs)
        self.stdout.write(f"Found {total} legacy Unit 1 exercises to migrate.")

        count = 0
        for ex in qs:
            try:
                new_data = self.migrate_exercise(ex)
                if not dry_run:
                    ex.data = new_data
                    ex.save()
                count += 1
                if count % 100 == 0:
                    self.stdout.write(f"Migrated {count}/{total}...")
            except Exception as e:
                self.stderr.write(f"Failed to migrate {ex.id}: {str(e)}")

        self.stdout.write(f"Successfully migrated {count} exercises.")

    def migrate_exercise(self, ex):
        old = ex.data
        score = old.get("score", {})
        meta = score.get("meta", {})
        
        # Identify the primary staff
        staves = score.get("measures", [{}])[0].get("staves", {}).keys()
        primary = list(staves)[0] if staves else "treble"
        
        # For Unit 1, target the standard voice for that staff
        target_voice = "soprano" if primary == "treble" else "bass"

        return build_umto_payload(
            exercise_id=ex.id,
            source=old.get("introText", "Bach Chorale Window"),
            key=meta.get("key", "C"),
            meter=meta.get("time", "4/4"),
            clef=primary,
            complexity_score=1,
            mode=InteractionMode.IDENTIFICATION,
            score_data=score,
            target_voice=target_voice,
            unit=1,
        )
