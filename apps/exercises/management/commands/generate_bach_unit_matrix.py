from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


DEFAULT_UNITS = "9,10,11,12,14,16,17,18,19,20"
DEFAULT_MODES = "roman,figures,play,play_figures"


def _parse_csv_ints(value):
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if part:
            out.append(int(part))
    if not out:
        raise CommandError("At least one unit is required.")
    return out


def _parse_csv_strings(value):
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if part:
            out.append(part)
    if not out:
        raise CommandError("At least one mode is required.")
    return out


class Command(BaseCommand):
    help = "Import Bach Riemenschneider phrases once per mode, then project them into per-unit playlists."

    def add_arguments(self, parser):
        parser.add_argument("--units", default=DEFAULT_UNITS)
        parser.add_argument("--modes", default=DEFAULT_MODES)
        parser.add_argument("--riemenschneider", required=True)
        parser.add_argument("--author", required=True)
        parser.add_argument("--min-measures", type=int, default=3)
        parser.add_argument("--public", action="store_true")
        parser.add_argument("--overwrite", action="store_true", default=True)
        parser.add_argument("--playlist-only", action="store_true")
        parser.add_argument("--no-chord-filter", action="store_true")
        parser.add_argument("--skip-refresh", action="store_true")

    def handle(self, *args, **options):
        units = _parse_csv_ints(options["units"])
        modes = _parse_csv_strings(options["modes"])
        author_email = options["author"]

        User = get_user_model()
        try:
            User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{author_email}'.")

        self.stdout.write(f"Units: {units}")
        self.stdout.write(f"Modes: {modes}")
        self.stdout.write(f"Riemenschneider: {options['riemenschneider']}")

        if not options["playlist_only"]:
            for mode in modes:
                extra_tags = [f"unit:{u}" for u in units] + [f"mode:{mode}"]
                self.stdout.write(self.style.MIGRATE_HEADING(f"[import] mode={mode}"))
                call_command(
                    "import_bach_phrases",
                    riemenschneider=options["riemenschneider"],
                    author=author_email,
                    mode=mode,
                    min_measures=options["min_measures"],
                    extra_tags=extra_tags,
                    public=options["public"],
                    overwrite=options["overwrite"],
                )

        for unit in units:
            for mode in modes:
                self.stdout.write(self.style.MIGRATE_HEADING(f"[playlist] unit={unit} mode={mode}"))
                call_command(
                    "create_unit_playlist",
                    unit=unit,
                    riemenschneider=options["riemenschneider"],
                    author=author_email,
                    mode=mode,
                    min_measures=options["min_measures"],
                    public=options["public"],
                    playlist_only=True,
                    no_chord_filter=options["no_chord_filter"],
                )

        if not options["skip_refresh"]:
            call_command("refresh_all_exercises")
            call_command("backfill_skill_tags", all=True)
            call_command("backfill_raw_roman_numeral")

        self.stdout.write(self.style.SUCCESS("generate_bach_unit_matrix complete."))
