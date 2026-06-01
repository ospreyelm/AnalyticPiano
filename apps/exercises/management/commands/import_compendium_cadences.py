# -*- coding: utf-8 -*-
"""Import Roman-numeral identification exercises from the Galant compendium.

Each templated compendium cadence is transposed to multiple keys (same mode) and
saved as one identification exercise per (example, key), grouped into per-unit
playlists.

Usage (preview — no DB writes):
    python manage.py import_compendium_cadences --preview

Usage (real import):
    python manage.py import_compendium_cadences \\
        --author admin@example.com --public --overwrite

Options:
    --author      Email of exercise author (required unless --preview)
    --public      Mark exercises as public (store_true)
    --overwrite   Replace existing exercises with matching descriptions
    --unit N      Only emit exercises that bin to this unit
    --all-units  Emit all generated unit bins (default)
    --preview     Compute everything, print table + histogram, no DB writes
    --keys K ...  Override target tonics (applied per mode)
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.exercises.compendium_prep import prepare_compendium_exercise
from apps.exercises.compendium_source import load_cadence_examples

# ── Target keys per mode ──────────────────────────────────────────────────────

KEYS_BY_MODE: dict[str, list[str]] = {
    "major": ["C", "G", "D", "F", "Bb"],
    "minor": ["A", "E", "B", "D", "G"],
}


# ── Core loop (shared by preview and real run) ────────────────────────────────

def _run_core_loop(options: dict) -> tuple[dict[int, list], int]:
    """Iterate all (example, tonic) pairs and return (by_unit, skipped).

    Returns ``(by_unit, skipped)`` where:
      - ``by_unit`` maps unit number → list of prep payload dicts (as returned
        by ``prepare_compendium_exercise``).  Both preview and real paths receive
        the same raw dicts; DB writes are the caller's (``handle()``) responsibility.
      - ``skipped`` is the count of (example, tonic) pairs that produced ``None``
        (untemplated or note-alignment mismatch).

    This function is pure-prep; no DB access occurs here.
    """
    examples = load_cadence_examples()
    by_unit: dict[int, list] = {}
    skipped = 0
    filter_unit = options.get("unit")
    override_keys = options.get("keys") or []

    for e in examples:
        tonics = override_keys if override_keys else KEYS_BY_MODE[e["mode"]]
        for tonic in tonics:
            prep = prepare_compendium_exercise(e, tonic)
            if prep is None:
                skipped += 1
                continue
            if filter_unit is not None and prep["unit"] != filter_unit:
                continue
            unit = prep["unit"]
            by_unit.setdefault(unit, []).append(prep)

    return by_unit, skipped


# ── Preview printer ───────────────────────────────────────────────────────────

def _extract_rns(prep: dict) -> str:
    """Extract Roman numerals from prep's analysis_overrides as a joined string."""
    overrides = prep.get("umto_kwargs", {}).get("analysis_overrides", [])
    rns = [s["content"]["roman_numeral"] for s in overrides if s.get("content", {}).get("roman_numeral")]
    return " ".join(rns)


def _print_preview(stdout, style, by_unit: dict, skipped: int) -> None:
    """Print a markdown-ish table (2 rows per unit) + bin histogram."""
    stdout.write(style.MIGRATE_HEADING("\nCompendium Cadences — Preview"))
    stdout.write("")

    # Table header
    header = f"{'unit':>4} | {'page_title':<46} | {'mode':<6} | {'key':<4} | {'RNs':<28} | description"
    stdout.write(header)
    stdout.write("-" * len(header))

    for unit in sorted(by_unit):
        preps = by_unit[unit]
        # Print up to 2 rows per unit as a sample
        for prep in preps[:2]:
            pt = prep.get("umto_kwargs", {}).get("source", "")[:46]
            # Extract mode from skill_tags
            mode = "major"
            for tag in prep.get("skill_tags", []):
                if tag.startswith("page:"):
                    # peek at the key to infer mode: minor keys have 'm' suffix in description
                    pass
            # Infer mode from HL key string (starts with 'i' for minor, 'j' for major)
            hl_key = prep.get("umto_kwargs", {}).get("key", "jC_")
            mode = "minor" if hl_key.startswith("i") else "major"
            # Extract tonic from hl_key: strip leading j/i and trailing _
            raw = hl_key[1:]  # drop 'j' or 'i'
            tonic = raw.rstrip("_")

            rns = _extract_rns(prep)[:28]
            desc = prep.get("description", "")[:30]
            stdout.write(
                f"{unit:>4} | {pt:<46} | {mode:<6} | {tonic:<4} | {rns:<28} | {desc}"
            )
        if len(preps) > 2:
            stdout.write(f"{'':>4}   ... ({len(preps) - 2} more in unit {unit})")

    # Histogram
    stdout.write("")
    stdout.write(style.MIGRATE_HEADING("Bin histogram"))
    for unit in sorted(by_unit):
        count = len(by_unit[unit])
        stdout.write(f"  unit {unit}: {count} exercises")
    stdout.write(f"  skipped (untemplated/misaligned): {skipped}")
    stdout.write("")


# ── Playlist builder ──────────────────────────────────────────────────────────

def _build_playlist(*, author, unit: int, exercises, is_public: bool) -> "Playlist":
    from apps.exercises.models import ExercisePlaylistOrdered, Playlist

    name = f"Unit {unit} — Roman Numerals from the Galant Compendium"
    skill_tags = ["exercise_type:roman_from_compendium", f"unit:{unit}"]

    playlist, _ = Playlist.objects.get_or_create(
        name=name,
        authored_by=author,
        defaults=dict(
            is_dynamic=False,
            is_adaptive=False,
            is_public=is_public,
            skill_tags=skill_tags,
        ),
    )
    playlist.skill_tags = skill_tags
    if is_public:
        playlist.is_public = True
    playlist.save()

    # Replace existing ordering with freshly saved set (deterministic order).
    ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
    for order, ex in enumerate(exercises, start=1):
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist, exercise=ex, order=order
        )
    return playlist


# ── Management command ────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Import Roman-numeral identification exercises from the Galant compendium. "
        "Transposes each templated cadence to multiple keys and groups into per-unit playlists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--author",
            default=None,
            help="Email of the exercise author (required unless --preview).",
        )
        parser.add_argument(
            "--public",
            action="store_true",
            help="Mark imported exercises as public.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing exercises with matching descriptions.",
        )
        parser.add_argument(
            "--unit",
            type=int,
            default=None,
            help="Only emit exercises that bin to this unit number.",
        )
        parser.add_argument(
            "--all-units",
            action="store_true",
            help="Emit all generated unit bins. This is the default when --unit is omitted.",
        )
        parser.add_argument(
            "--preview",
            action="store_true",
            help="Compute everything and print a table + histogram; no DB writes (author not required).",
        )
        parser.add_argument(
            "--keys",
            nargs="+",
            default=None,
            metavar="KEY",
            help="Override target tonic letters (e.g. C G D).  Applied to whichever mode each example is.",
        )

    def handle(self, *args, **options):
        preview = options["preview"]
        if options.get("unit") is not None and options.get("all_units"):
            raise CommandError("--unit and --all-units are mutually exclusive.")

        if preview:
            # Pure preview: no DB access at all.
            by_unit, skipped = _run_core_loop(options)
            _print_preview(self.stdout, self.style, by_unit, skipped)
            return

        # Real run — require author.
        author_email = options.get("author")
        if not author_email:
            raise CommandError("--author is required unless --preview is set.")

        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist as exc:
            raise CommandError(f'User with email "{author_email}" not found.') from exc

        from apps.exercises.umto_factory import save_umto_exercise

        # Run core loop to collect prep dicts.
        by_unit_preps, skipped = _run_core_loop(options)

        by_unit_exercises: dict[int, list] = {}
        total_created = 0
        total_skipped_dup = 0

        for unit in sorted(by_unit_preps):
            preps = by_unit_preps[unit]
            exs = []
            for prep in preps:
                description = prep["description"]

                # Idempotency check (skip unless --overwrite)
                if not options["overwrite"]:
                    from apps.exercises.models import Exercise
                    ex_existing = Exercise.objects.filter(
                        description=description, authored_by=author
                    ).first()
                    if ex_existing is not None:
                        total_skipped_dup += 1
                        # Still collect the existing exercise for playlist ordering.
                        exs.append(ex_existing)
                        continue

                ex = save_umto_exercise(
                    description=description,
                    score_data=prep["score_data"],
                    author=author,
                    skill_tags=prep["skill_tags"],
                    complexity=prep["complexity"],
                    is_public=options["public"],
                    umto_kwargs=prep["umto_kwargs"],
                    overwrite=options["overwrite"],
                )
                exs.append(ex)
                total_created += 1
                self.stdout.write(f"  Saved: {description}")

            by_unit_exercises[unit] = exs

        # Build playlists.
        for unit, exercises in by_unit_exercises.items():
            if not exercises:
                continue
            playlist = _build_playlist(
                author=author,
                unit=unit,
                exercises=exercises,
                is_public=options["public"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Playlist '{playlist.name}' → {len(exercises)} exercises"
                )
            )

        # Final histogram.
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Bin histogram"))
        for unit in sorted(by_unit_preps):
            count = len(by_unit_preps[unit])
            self.stdout.write(f"  unit {unit}: {count} exercises")
        self.stdout.write(f"  skipped (untemplated/misaligned): {skipped}")
        self.stdout.write(f"  skipped (duplicates, not overwritten): {total_skipped_dup}")
        self.stdout.write(
            self.style.SUCCESS(f"\nTotal created/updated: {total_created} exercises")
        )
        self.stdout.write(
            "\nVerify one exercise per unit in the student app before bulk use:\n"
            "  Confirm score renders, ? slots appear, student can answer and complete."
        )
