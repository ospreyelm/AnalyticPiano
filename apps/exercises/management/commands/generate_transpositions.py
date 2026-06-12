"""generate_transpositions — batch-create transposed UMTO chordal Exercise copies.

Usage
-----
python manage.py generate_transpositions \\
    --exercise EA0001 \\
    --keys C,G,Bb,F#m \\
    [--playlist "My Playlist"] \\
    [--author teacher@example.com] \\
    [--overwrite]

Runtime playlist transposition (transpose_requests) does NOT work for UMTO
chordal rows — they lack the legacy top-level data["chord"] + keySignature
fields that transpose() mutates.  This command creates explicit Exercise copies
instead.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, Playlist
from apps.exercises.services.transposition_service import generate_transposed_copies

User = get_user_model()


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Batch-create transposed Exercise copies of a UMTO chordal exercise. "
        "Analysis slices are copied as-is (they are key-relative). "
        "Each copy is tagged transposed_from:<source_id>."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--exercise",
            required=True,
            metavar="EXERCISE_ID",
            help="Source Exercise ID (must be UMTO chordal, e.g. EA0001).",
        )
        parser.add_argument(
            "--keys",
            required=True,
            metavar="C,G,Bb,F#m",
            help=(
                "Comma-separated list of target keys in clean notation "
                "(e.g. C, G, Bb, F#m, Am).  The source key is always included "
                "implicitly; supply it to include a same-key copy in the playlist."
            ),
        )
        parser.add_argument(
            "--playlist",
            default=None,
            metavar="PLAYLIST_NAME",
            help="Get-or-create a playlist by this name and append copies in key order.",
        )
        parser.add_argument(
            "--author",
            default=None,
            metavar="EMAIL",
            help="Author email for created exercises/playlist.  Defaults to source author.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            default=False,
            help=(
                "If an exercise with the same description+author already exists, "
                "update it instead of skipping."
            ),
        )

    def handle(self, *args, **options):
        # ---- resolve source exercise ----
        try:
            source = Exercise.objects.get(id=options["exercise"])
        except Exercise.DoesNotExist as exc:
            raise CommandError(
                f"Exercise not found: {options['exercise']}"
            ) from exc

        # ---- resolve author ----
        if options["author"]:
            try:
                author = User.objects.get(email=options["author"])
            except User.DoesNotExist as exc:
                raise CommandError(f"Author not found: {options['author']}") from exc
        else:
            author = source.authored_by

        # ---- parse keys ----
        raw_keys = [k.strip() for k in options["keys"].split(",") if k.strip()]
        if not raw_keys:
            raise CommandError("--keys must be a non-empty comma-separated list.")

        # ---- get or create playlist if requested ----
        playlist = None
        if options["playlist"]:
            playlist, pl_created = Playlist.objects.get_or_create(
                name=options["playlist"],
                authored_by=author,
                defaults={"is_public": source.is_public},
            )
            if pl_created:
                self.stdout.write(f"  Created playlist '{playlist.name}' ({playlist.id})")
            else:
                self.stdout.write(f"  Using existing playlist '{playlist.name}' ({playlist.id})")

        # ---- call service to generate transposed copies ----
        try:
            created = generate_transposed_copies(
                source_exercise=source,
                key_set=raw_keys,
                playlist=playlist,
                author=author,
                is_official=False,
                overwrite=options["overwrite"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        # ---- print result summary ----
        self.stdout.write("")
        self.stdout.write(f"Source: {source.id} — {source.description}")
        self.stdout.write(f"Created/updated: {len(created)} exercise(s)")
        for ex in created:
            self.stdout.write(f"  {ex.id} — {ex.description}")
        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {len(created)} exercise(s) ready."
            )
        )
