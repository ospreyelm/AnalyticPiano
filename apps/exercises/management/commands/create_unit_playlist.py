import json
import re
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from apps.exercises.models import Playlist, Exercise, ExercisePlaylistOrdered

# parents[4] from this file = repo root
TAXONOMY_PATH = Path(__file__).resolve().parents[4] / "music_theory_taxonomy_with_branches.json"

User = get_user_model()


def _lookup_unit(unit_num: int) -> dict | None:
    with open(TAXONOMY_PATH) as f:
        taxonomy = json.load(f)
    for branch in taxonomy:
        for tier in branch.get("tiers", []):
            for unit in tier.get("units", []):
                if str(unit["n"]) == str(unit_num):
                    return unit
    return None


def _parse_range(text: str) -> list[int]:
    text = text.strip()
    if "-" in text:
        start, end = text.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(text)]


class Command(BaseCommand):
    help = "Import Bach phrases for a unit and create an adaptive (non-dynamic) playlist with explicit exercise ordering."

    @staticmethod
    def _extract_riem_phrase(description: str) -> tuple[int, int]:
        # Expected shape: "Bach R22 - Phrase 3 (mm.11-15) [play]"
        m = re.search(r"R(\d+)\s*-\s*Phrase\s*(\d+)", description or "")
        if not m:
            return (0, 0)
        return (int(m.group(1)), int(m.group(2)))

    def add_arguments(self, parser):
        parser.add_argument("--unit", type=int, required=True)
        parser.add_argument("--riemenschneider", type=str, required=True)
        parser.add_argument("--author", type=str, required=True)
        parser.add_argument("--mode", type=str,
                            choices=["roman", "play", "figures", "matching"], default="roman")
        parser.add_argument("--min-measures", type=int, default=3)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        unit_num = options["unit"]
        riem_range = _parse_range(str(options["riemenschneider"]))
        author_email = options["author"]
        mode = options["mode"]
        min_measures = options["min_measures"]
        make_public = options["public"]
        dry_run = options["dry_run"]

        unit_meta = _lookup_unit(unit_num)
        if unit_meta is None:
            raise CommandError(f"Unit {unit_num} not found in taxonomy.")
        title = unit_meta["title"]
        self.stdout.write(f"Unit {unit_num}: {title}")

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{author_email}'.")

        unit_tag = f"unit:{unit_num}"
        mode_tag = f"mode:{mode}"
        unit_skill_tags = list(unit_meta.get("tags", []))
        playlist_skill_tags = [unit_tag, mode_tag] + [
            tag for tag in unit_skill_tags if tag not in (unit_tag, mode_tag)
        ]
        self.stdout.write(f"Importing Riemenschneider {riem_range[0]}–{riem_range[-1]} ({len(riem_range)} chorales)...")
        for riem_num in riem_range:
            self.stdout.write(f"  R{riem_num}...")
            if not dry_run:
                call_command("import_bach_phrases",
                             riemenschneider=riem_num, author=author_email,
                             mode=mode, min_measures=min_measures,
                             extra_tags=[unit_tag, mode_tag], public=make_public)

        playlist_name = f"Unit {unit_num} — {title} ({mode})"
        if dry_run:
            self.stdout.write(f"[dry-run] Would create playlist: {playlist_name}")
            return

        # Scope by authored_by to prevent cross-teacher collision on same name
        playlist, created = Playlist.objects.get_or_create(
            name=playlist_name,
            authored_by=author,
            defaults=dict(is_dynamic=False, is_adaptive=True,
                          skill_tags=playlist_skill_tags, is_public=make_public),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = True
            if make_public:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in playlist_skill_tags:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.save()

        # Build static ordered exercise membership from imported corpus subset.
        # This preserves deterministic sequencing like the original Unit 9 flow.
        if not dry_run:
            riem_set = set(riem_range)
            candidates = Exercise.objects.filter(
                authored_by=author,
                skill_tags__contains=[unit_tag],
            ).filter(
                skill_tags__contains=[mode_tag],
            )

            selected = [
                ex for ex in candidates
                if Command._extract_riem_phrase(ex.description)[0] in riem_set
            ]
            selected.sort(key=lambda ex: Command._extract_riem_phrase(ex.description))

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for idx, ex in enumerate(selected, start=1):
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=idx,
                    is_adaptive_entry=(idx == 1),
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Linked {len(selected)} exercises to playlist '{playlist_name}' in static order."
                )
            )

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Playlist '{playlist_name}' ({playlist.id}) — {action}"))
