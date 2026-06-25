"""One-off fix: transposed harmonization exercises saved with mode='playback'.

Finds exercises whose skill_tags contain a 'transposed_from:' tag AND whose
stored mode is 'playback', then rewrites them as 'harmonization' and
computes harmonizationTargets.

Safe to re-run (idempotent). Scope with --playlist to limit to one playlist.
"""
from django.core.management.base import BaseCommand

from apps.exercises.harmonization.targets import build_targets_from_umto
from apps.exercises.models import Exercise, Playlist


class Command(BaseCommand):
    help = "Fix transposed harmonization exercises incorrectly saved as playback mode."

    def add_arguments(self, parser):
        parser.add_argument("--playlist", type=str, default=None,
                            help="Limit to exercises in this playlist ID.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change without writing.")

    def handle(self, *args, **options):
        if options["playlist"]:
            try:
                pl = Playlist.objects.get(id=options["playlist"])
            except Playlist.DoesNotExist:
                self.stderr.write(f"Playlist {options['playlist']} not found.")
                return
            qs = pl.exercises.all()
        else:
            qs = Exercise.objects.all()

        fixed = 0
        skipped = 0

        for ex in qs.iterator():
            data = ex.data or {}
            if data.get("mode") != "playback":
                continue
            tags = ex.skill_tags or []
            if not any(t.startswith("transposed_from:") for t in tags):
                continue
            umto = (data.get("score") or {}).get("umto", {})
            if umto.get("metadata", {}).get("score_kind") != "chordal":
                skipped += 1
                self.stdout.write(f"  skip {ex.id}: not chordal")
                continue

            try:
                targets = build_targets_from_umto(umto)
            except Exception as e:
                skipped += 1
                self.stdout.write(self.style.ERROR(f"  skip {ex.id}: {e}"))
                continue

            if options["dry_run"]:
                self.stdout.write(f"  WOULD FIX {ex.id}: 0 → {len(targets)} targets")
                fixed += 1
                continue

            data["mode"] = "harmonization"
            umto["metadata"]["mode"] = "harmonization"
            data["harmonizationTargets"] = targets
            ex.data = data
            ex.save(update_fields=["data"])
            fixed += 1
            self.stdout.write(f"  fixed {ex.id}: {len(targets)} targets")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. fixed={fixed} skipped={skipped}"
        ))
