"""Export curated factory exercises and their playlists to JSON files.

Selection rule: an exercise is "curated" when it is authored by the factory
account (settings.FACTORY_USER_EMAIL) AND carries the skill_tag "curated" or
any tag starting with "curated:".

Playlists are exported when they are authored by the factory user AND every
member exercise is in the curated set.

Export format: one JSON file per unit (keyed by "unit:N" skill_tag), with
exercises lacking a unit tag written to "misc.json".  Exercises are sorted by
id for stable git diffs.

Usage:
    python manage.py export_factory_curated
    python manage.py export_factory_curated --out-dir path/to/dir
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

User = get_user_model()

DEFAULT_OUT_DIR = Path(__file__).resolve().parents[5] / "data" / "factory_curated"


def _is_curated(exercise: Exercise) -> bool:
    """Return True when the exercise carries the 'curated' or 'curated:*' tag."""
    for tag in (exercise.skill_tags or []):
        if tag == "curated" or tag.startswith("curated:"):
            return True
    return False


def _unit_from_skill_tags(skill_tags: list[str]) -> str | None:
    """Return the unit number string from skill_tags (e.g. 'unit:9' → '9'), or None."""
    for tag in (skill_tags or []):
        if tag.startswith("unit:"):
            suffix = tag[len("unit:"):]
            if suffix.isdigit():
                return suffix
    return None


def _exercise_to_dict(ex: Exercise) -> dict:
    return {
        "id": ex.id,
        "description": ex.description,
        "data": ex.data,
        "skill_tags": list(ex.skill_tags or []),
        "tags": list(ex.tags or []),
        "complexity": ex.complexity,
        "is_public": ex.is_public,
    }


class Command(BaseCommand):
    help = (
        "Export curated factory exercises and their playlists to JSON files under "
        "data/factory_curated/ (one file per unit, 'misc.json' for untagged).\n\n"
        "Selection rule: exercises authored by the factory user "
        "(settings.FACTORY_USER_EMAIL) that carry the skill_tag 'curated' or any "
        "tag starting with 'curated:'.  Playlists authored by the factory user "
        "whose every member exercise is in the curated set are also exported."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out-dir",
            type=str,
            default=str(DEFAULT_OUT_DIR),
            help=f"Directory to write JSON files into (default: {DEFAULT_OUT_DIR})",
        )

    def handle(self, *args, **options):
        out_dir = Path(options["out_dir"])

        # Resolve factory author
        factory_email = getattr(settings, "FACTORY_USER_EMAIL", None)
        if not factory_email:
            raise CommandError(
                "settings.FACTORY_USER_EMAIL is not set. "
                "Run ensure_factory_account first."
            )
        try:
            factory_user = User.objects.get(email=factory_email)
        except User.DoesNotExist:
            raise CommandError(
                f"Factory user '{factory_email}' does not exist. "
                "Run manage.py ensure_factory_account first."
            )

        # Collect curated exercises authored by factory user
        all_factory_exercises = Exercise.objects.filter(authored_by=factory_user)
        curated_exercises = [ex for ex in all_factory_exercises if _is_curated(ex)]
        curated_ids = {ex.id for ex in curated_exercises}

        # Collect playlists authored by factory user whose every member is curated
        factory_playlists = Playlist.objects.filter(authored_by=factory_user)
        curated_playlists = []
        for pl in factory_playlists:
            member_ids = list(
                ExercisePlaylistOrdered.objects.filter(playlist=pl)
                .order_by("order")
                .values_list("exercise__id", flat=True)
            )
            if member_ids and all(eid in curated_ids for eid in member_ids):
                curated_playlists.append((pl, member_ids))

        # Group exercises by unit
        unit_map: dict[str, list[Exercise]] = {}  # unit string or "misc" → exercises
        for ex in curated_exercises:
            unit = _unit_from_skill_tags(ex.skill_tags) or "misc"
            unit_map.setdefault(unit, []).append(ex)

        # Sort each unit's exercises by id for stable diffs
        for exercises in unit_map.values():
            exercises.sort(key=lambda e: e.id or "")

        # Group playlists by unit (use first unit tag from playlist skill_tags, else misc)
        playlist_unit_map: dict[str, list] = {}
        for pl, member_ids in curated_playlists:
            unit = _unit_from_skill_tags(pl.skill_tags) or "misc"
            playlist_unit_map.setdefault(unit, []).append((pl, member_ids))

        # Collect all units to write
        all_units = set(unit_map.keys()) | set(playlist_unit_map.keys())

        out_dir.mkdir(parents=True, exist_ok=True)
        exported_at = datetime.now(tz=timezone.utc).isoformat()

        files_written = []
        for unit in sorted(all_units, key=lambda u: (u == "misc", int(u) if u != "misc" else 0)):
            exercises = unit_map.get(unit, [])
            playlists_for_unit = playlist_unit_map.get(unit, [])

            playlist_dicts = []
            for pl, member_ids in sorted(playlists_for_unit, key=lambda t: t[0].name or ""):
                playlist_dicts.append({
                    "name": pl.name,
                    "skill_tags": list(pl.skill_tags or []),
                    "is_public": pl.is_public,
                    "members": [
                        {"exercise_id": eid, "order": idx + 1}
                        for idx, eid in enumerate(member_ids)
                    ],
                })

            payload = {
                "version": 1,
                "exported_at": exported_at,
                "author_email": factory_email,
                "exercises": [_exercise_to_dict(ex) for ex in exercises],
                "playlists": playlist_dicts,
            }

            filename = f"{unit}.json" if unit == "misc" else f"unit{unit}.json"
            out_path = out_dir / filename
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            files_written.append((filename, len(exercises), len(playlist_dicts)))

        # Summary
        total_ex = sum(len(unit_map.get(u, [])) for u in all_units)
        total_pl = sum(len(playlist_unit_map.get(u, [])) for u in all_units)
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {total_ex} exercise(s) and {total_pl} playlist(s) "
                f"to {out_dir}/"
            )
        )
        for fname, ex_count, pl_count in sorted(files_written):
            self.stdout.write(f"  {fname}: {ex_count} exercise(s), {pl_count} playlist(s)")
