"""Import (or dry-run preview) curated factory exercises from exported JSON files.

Selection rule (mirrors export_factory_curated): exercises authored by the
factory account (settings.FACTORY_USER_EMAIL) with skill_tag 'curated' or any
tag starting with 'curated:'.

Import behaviour:
  - Exercises are upserted by id:
      * If an Exercise with that id already exists → update data, description,
        skill_tags, tags, complexity, is_public (only when --update is given).
      * If no Exercise with that id exists → create a new row with that exact
        id authored by the factory user.
  - Playlists: get_or_create by (name, authored_by), then rebuild
    ExercisePlaylistOrdered memberships to match the file (existing EPO rows
    for the playlist are deleted and recreated).
  - Exercises are NEVER deleted.
  - Without --update the command performs a dry run: it prints what would be
    created or changed but makes no DB writes.

How preset-id creation works:
  Exercise.save() derives the `id` field from the auto-increment `_id` primary
  key via set_id().  To preserve an exported id we:
    1. Create the Exercise and call save() (gets a temporary auto-assigned id).
    2. Override the `id` column with the desired value using a targeted UPDATE
       that bypasses save() and set_id().
    3. Patch the data payload's exerciseId references to match.
  This path requires the imported data to pass the UMTO guard (data["isUMTO"]
  must be truthy) — all curated factory exercises satisfy this contract.

Usage:
    # Dry run (no writes)
    python manage.py import_factory_curated

    # Apply changes
    python manage.py import_factory_curated --update

    # From a custom directory
    python manage.py import_factory_curated --dir path/to/dir --update
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

User = get_user_model()

DEFAULT_IN_DIR = Path(__file__).resolve().parents[5] / "data" / "factory_curated"


def _load_files(directory: Path) -> list[dict]:
    """Load all *.json files from directory, return list of parsed payloads."""
    payloads = []
    for path in sorted(directory.glob("*.json")):
        with open(path) as f:
            payloads.append(json.load(f))
    return payloads


def _get_or_create_factory_user(factory_email: str):
    """Look up factory user; create via ensure_factory_account if missing."""
    try:
        return User.objects.get(email=factory_email)
    except User.DoesNotExist:
        call_command("ensure_factory_account")
        return User.objects.get(email=factory_email)


def _upsert_exercise(
    ex_dict: dict, factory_user, *, dry_run: bool, stdout, style
) -> tuple[str, str]:
    """Upsert one exercise.  Returns (action, exercise_id) where action is
    'create', 'update', or 'skip' (dry_run)."""
    desired_id: str = ex_dict["id"]
    data: dict = ex_dict["data"]
    description: str | None = ex_dict.get("description")
    skill_tags: list = ex_dict.get("skill_tags") or []
    tags: list = ex_dict.get("tags") or []
    complexity: int = ex_dict.get("complexity", 1)
    is_public: bool = ex_dict.get("is_public", True)

    existing = Exercise.objects.filter(id=desired_id).first()

    if existing is not None:
        # Update existing exercise
        changed_fields = []
        if existing.data != data:
            changed_fields.append("data")
        if existing.description != description:
            changed_fields.append("description")
        if existing.skill_tags != skill_tags:
            changed_fields.append("skill_tags")
        if existing.tags != tags:
            changed_fields.append("tags")
        if existing.complexity != complexity:
            changed_fields.append("complexity")
        if existing.is_public != is_public:
            changed_fields.append("is_public")

        if not changed_fields:
            stdout.write(f"  [skip]   {desired_id} — no changes")
            return ("skip", desired_id)

        if dry_run:
            stdout.write(
                f"  [dry-run update] {desired_id} — would update: {', '.join(changed_fields)}"
            )
            return ("skip", desired_id)

        existing.data = data
        existing.description = description
        existing.skill_tags = skill_tags
        existing.tags = tags
        existing.complexity = complexity
        existing.is_public = is_public
        existing.save()
        stdout.write(style.SUCCESS(f"  [updated] {desired_id} — {', '.join(changed_fields)}"))
        return ("update", desired_id)

    else:
        # Create new exercise with the desired id
        if dry_run:
            stdout.write(f"  [dry-run create] {desired_id} — {description!r}")
            return ("skip", desired_id)

        ex = Exercise(
            description=description,
            data=data,
            authored_by=factory_user,
            skill_tags=skill_tags,
            tags=tags,
            complexity=complexity,
            is_public=is_public,
        )
        ex.save(skip_auto_playlist=True)

        # Override the auto-assigned id with the exported id.
        # Exercise.save() derives `id` from `_id` via set_id(); we bypass this
        # by issuing a targeted UPDATE on the already-saved row.
        if ex.id != desired_id:
            Exercise.objects.filter(_id=ex._id).update(id=desired_id)
            ex.id = desired_id

        # Patch exerciseId references inside the data payload and re-save data.
        needs_data_patch = False
        if (ex.data or {}).get("exerciseId") != desired_id:
            ex.data["exerciseId"] = desired_id
            needs_data_patch = True
        try:
            if ex.data["score"]["umto"]["metadata"]["exercise_id"] != desired_id:
                ex.data["score"]["umto"]["metadata"]["exercise_id"] = desired_id
                needs_data_patch = True
        except (KeyError, TypeError):
            pass
        if needs_data_patch:
            Exercise.objects.filter(_id=ex._id).update(data=ex.data)

        stdout.write(style.SUCCESS(f"  [created] {desired_id} — {description!r}"))
        return ("create", desired_id)


def _rebuild_playlist(
    pl_dict: dict, factory_user, curated_id_set: set[str], *, dry_run: bool, stdout, style
) -> str:
    """Upsert one playlist and rebuild its EPO memberships.  Returns action string."""
    name: str = pl_dict["name"]
    skill_tags: list = pl_dict.get("skill_tags") or []
    is_public: bool = pl_dict.get("is_public", True)
    members: list[dict] = pl_dict.get("members") or []

    # Validate all referenced exercises exist (or would exist after this import)
    missing = [m["exercise_id"] for m in members if m["exercise_id"] not in curated_id_set]
    if missing:
        stdout.write(
            style.WARNING(
                f"  [playlist skip] '{name}' — missing exercise ids: {missing}"
            )
        )
        return "skip"

    if dry_run:
        stdout.write(
            f"  [dry-run playlist] '{name}' — {len(members)} member(s)"
        )
        return "skip"

    playlist, created = Playlist.objects.get_or_create(
        name=name,
        authored_by=factory_user,
        defaults=dict(skill_tags=skill_tags, is_public=is_public),
    )
    if not created:
        # Update metadata
        playlist.skill_tags = skill_tags
        playlist.is_public = is_public
        playlist.save()

    # Rebuild EPO membership (delete + recreate matches create_unit_playlist pattern)
    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for member in members:
        ex = Exercise.objects.get(id=member["exercise_id"])
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=ex,
            order=member["order"],
        )

    action = "created" if created else "updated"
    stdout.write(
        style.SUCCESS(
            f"  [playlist {action}] '{name}' — {len(members)} member(s)"
        )
    )
    return action


class Command(BaseCommand):
    help = (
        "Import curated factory exercises and playlists from JSON files under "
        "data/factory_curated/ (or --dir).  Without --update, performs a dry run "
        "that prints what would change but makes no DB writes.\n\n"
        "Selection rule (mirrors export_factory_curated): exercises authored by "
        "settings.FACTORY_USER_EMAIL with skill_tag 'curated' or 'curated:*'.\n\n"
        "Exercises are upserted by id (never deleted).  Playlists are "
        "get_or_created by (name, factory_user); EPO memberships are rebuilt to "
        "match the file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            type=str,
            default=str(DEFAULT_IN_DIR),
            help=f"Directory containing exported JSON files (default: {DEFAULT_IN_DIR})",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            default=False,
            help=(
                "Apply changes to the database. Without this flag the command "
                "performs a dry run only."
            ),
        )

    def handle(self, *args, **options):
        in_dir = Path(options["dir"])
        dry_run = not options["update"]

        if not in_dir.exists():
            raise CommandError(f"Directory does not exist: {in_dir}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — pass --update to apply changes"
                )
            )

        # Resolve factory user
        factory_email = getattr(settings, "FACTORY_USER_EMAIL", None)
        if not factory_email:
            raise CommandError("settings.FACTORY_USER_EMAIL is not set.")

        if not dry_run:
            factory_user = _get_or_create_factory_user(factory_email)
        else:
            # In dry-run we still need a user object for playlist lookup; don't create
            try:
                factory_user = User.objects.get(email=factory_email)
            except User.DoesNotExist:
                factory_user = None

        # Load all JSON files
        payloads = _load_files(in_dir)
        if not payloads:
            self.stdout.write(self.style.WARNING(f"No JSON files found in {in_dir}"))
            return

        stats = {"create": 0, "update": 0, "skip": 0}
        pl_stats = {"created": 0, "updated": 0, "skip": 0}

        # Track all ids that will exist after this import (for playlist validation)
        imported_ids: set[str] = set()

        for payload in payloads:
            exercises = payload.get("exercises") or []
            playlists = payload.get("playlists") or []

            if exercises:
                self.stdout.write(f"\nExercises ({len(exercises)}):")

            with transaction.atomic():
                for ex_dict in sorted(exercises, key=lambda e: e["id"]):
                    if dry_run:
                        # Don't write, just report
                        desired_id = ex_dict["id"]
                        imported_ids.add(desired_id)
                        action, _ = _upsert_exercise(
                            ex_dict, factory_user, dry_run=True,
                            stdout=self.stdout, style=self.style,
                        )
                        stats[action if action in stats else "skip"] += 1
                    else:
                        action, exercise_id = _upsert_exercise(
                            ex_dict, factory_user, dry_run=False,
                            stdout=self.stdout, style=self.style,
                        )
                        imported_ids.add(exercise_id)
                        stats[action if action in stats else "skip"] += 1

                if playlists:
                    self.stdout.write(f"\nPlaylists ({len(playlists)}):")

                for pl_dict in playlists:
                    action = _rebuild_playlist(
                        pl_dict, factory_user, imported_ids,
                        dry_run=dry_run,
                        stdout=self.stdout,
                        style=self.style,
                    )
                    pl_stats[action if action in pl_stats else "skip"] += 1

        # Summary
        mode_label = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{mode_label}Done — exercises: "
                f"{stats['create']} created, {stats['update']} updated, "
                f"{stats['skip']} unchanged; "
                f"playlists: {pl_stats.get('created', 0)} created, "
                f"{pl_stats.get('updated', 0)} updated, "
                f"{pl_stats.get('skip', 0)} unchanged."
            )
        )
