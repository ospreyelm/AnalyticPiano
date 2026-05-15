"""One-shot: add taxonomy tags to existing Unit 3 playlists and delete legacy ones."""
from django.core.management.base import BaseCommand
from apps.exercises.models import Playlist


class Command(BaseCommand):
    help = "Fix Unit 3 playlist taxonomy tags and remove legacy unlabeled playlists"

    def handle(self, *args, **options):
        # Delete old playlists that have no major/minor label
        old_names = [
            "Unit 3 — Key Signatures, Level 1",
            "Unit 3 — Key Signatures, Level 2",
            "Unit 3 — Key Signatures, Level 3",
        ]
        for name in old_names:
            deleted, _ = Playlist.objects.filter(name=name).delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f"Deleted: {name}"))
            else:
                self.stdout.write(f"Not found (already gone): {name}")

        # Add taxonomy tag 'key_signature' to key sig playlists missing it
        key_sig_qs = Playlist.objects.filter(
            skill_tags__contains=["unit:3"],
            name__contains="Key Signatures",
        )
        for pl in key_sig_qs:
            if "key_signature" not in (pl.skill_tags or []):
                pl.skill_tags = ["key_signature"] + [t for t in pl.skill_tags if t != "key_signature"]
                pl.save(update_fields=["skill_tags"])
                self.stdout.write(self.style.SUCCESS(f"Tagged key_signature: {pl.name}"))

        # Add taxonomy tag 'major_scale' to major scale playlists missing it
        scale_qs = Playlist.objects.filter(
            skill_tags__contains=["unit:3"],
            name__contains="Major Scales",
        )
        for pl in scale_qs:
            if "major_scale" not in (pl.skill_tags or []):
                pl.skill_tags = ["major_scale"] + [t for t in pl.skill_tags if t != "major_scale"]
                pl.save(update_fields=["skill_tags"])
                self.stdout.write(self.style.SUCCESS(f"Tagged major_scale: {pl.name}"))

        self.stdout.write(self.style.SUCCESS("Done."))
