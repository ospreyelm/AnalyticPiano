"""One-stop command that builds the complete official Monteverdi exercise library.

Usage
-----
# Full run (produces all generated exercises for all units):
python manage.py generate_factory_library --author factory@monteverdi.app

# Subset by unit range:
python manage.py generate_factory_library --units 1,2,9-20 --author factory@monteverdi.app

# Dry-run (print planned call_command invocations without executing):
python manage.py generate_factory_library --dry-run

# Coverage report (shows every taxonomy unit vs factory playlist count):
python manage.py generate_factory_library --report

# Verify manifest integrity (each unit has >=1 non-empty factory playlist):
python manage.py generate_factory_library --verify

# Pass --skip-refresh to generate_bach_unit_matrix (skip backfill/refresh):
python manage.py generate_factory_library --units 9-20 --skip-refresh
"""
from __future__ import annotations

import re

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.factory_manifest import MANIFEST, SHARED_COMMANDS, FactoryUnitEntry
from apps.exercises.taxonomy_reader import TaxonomyReader


def _parse_units_arg(value: str) -> set[str]:
    """Parse a comma-separated, range-supporting unit string.

    Accepts integers and branch-B strings (e.g. "B1", "B2").
    Ranges (e.g. "9-20") expand integers only.

    Examples
    --------
    "1,2,9-20" -> {"1", "2", "9", "10", ..., "20"}
    "B1,B2"    -> {"B1", "B2"}
    "1,9-11,B1" -> {"1", "9", "10", "11", "B1"}
    """
    result: set[str] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        # Integer range "9-20"
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if range_match:
            lo, hi = int(range_match.group(1)), int(range_match.group(2))
            if lo > hi:
                raise CommandError(f"Invalid range {part!r}: start > end.")
            result.update(str(n) for n in range(lo, hi + 1))
        elif re.fullmatch(r"\d+", part):
            result.add(part)
        elif re.fullmatch(r"[A-Za-z]\d*", part):
            # Branch-B style
            result.add(part.upper())
        else:
            raise CommandError(f"Cannot parse unit specifier {part!r}.")
    return result


def _unit_key(entry: FactoryUnitEntry) -> tuple:
    """Sort key: integers first (numerically), strings after (lexically)."""
    u = entry.unit
    if isinstance(u, int):
        return (0, u, "")
    try:
        return (0, int(u), "")
    except (ValueError, TypeError):
        return (1, 0, str(u))


def _unit_str(unit: int | str) -> str:
    return str(unit)


class Command(BaseCommand):
    help = (
        "Build the complete official exercise library under the factory account. "
        "Delegates to per-unit generators declared in apps.exercises.factory_manifest."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--units",
            default=None,
            metavar="SPEC",
            help=(
                "Comma-separated list / ranges of units to process, e.g. '1,2,9-20,B1'. "
                "Omit to process all manifest entries."
            ),
        )
        parser.add_argument(
            "--author",
            default=None,
            help=(
                "Email of the factory account.  Defaults to settings.FACTORY_USER_EMAIL. "
                "Passed as --author to each sub-command."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned call_command invocations without executing anything.",
        )
        parser.add_argument(
            "--report",
            action="store_true",
            help=(
                "Coverage map: every taxonomy unit vs factory playlist count.  "
                "Read-only; does not call ensure_factory_account."
            ),
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help=(
                "Assert each selected manifest unit has >=1 non-empty factory "
                "playlist tagged unit:N.  Exits with code 1 on failure.  "
                "Read-only."
            ),
        )
        parser.add_argument(
            "--skip-refresh",
            action="store_true",
            help=(
                "Pass --skip-refresh to generate_bach_unit_matrix, suppressing the "
                "post-run refresh_all_exercises / backfill passes."
            ),
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        do_report: bool = options["report"]
        do_verify: bool = options["verify"]
        skip_refresh: bool = options["skip_refresh"]

        author_email: str = options.get("author") or getattr(
            settings, "FACTORY_USER_EMAIL", None
        )
        if not author_email and not do_report and not do_verify:
            raise CommandError(
                "--author is required (or set settings.FACTORY_USER_EMAIL)."
            )

        # Parse unit filter
        units_filter: set[str] | None = None
        if options.get("units"):
            units_filter = _parse_units_arg(options["units"])

        # Select manifest entries
        selected = self._select_entries(units_filter)

        if do_report:
            self._handle_report(selected, author_email)
            return

        if do_verify:
            self._handle_verify(selected, author_email)
            return

        # Normal run
        if not dry_run:
            self._log_step("ensure_factory_account", {"email": author_email})
            call_command("ensure_factory_account", email=author_email)

        # Run shared commands (once each)
        shared_needed = self._shared_commands_needed(selected)
        self._run_shared_commands(
            shared_needed, author_email, dry_run=dry_run, skip_refresh=skip_refresh
        )

        # Run per-entry commands
        summary_rows: list[dict] = []
        for entry in selected:
            row = self._run_entry(entry, author_email, dry_run=dry_run)
            summary_rows.append(row)

        self._print_summary(summary_rows, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_entries(
        self, units_filter: set[str] | None
    ) -> list[FactoryUnitEntry]:
        entries = sorted(MANIFEST, key=_unit_key)
        if units_filter is None:
            return entries
        result = []
        for e in entries:
            if _unit_str(e.unit) in units_filter:
                result.append(e)
        if not result:
            raise CommandError(
                f"No manifest entries matched --units filter {units_filter!r}. "
                "Check unit numbers against apps.exercises.factory_manifest.MANIFEST."
            )
        return result

    # ------------------------------------------------------------------
    # Shared commands
    # ------------------------------------------------------------------

    def _shared_commands_needed(
        self, selected: list[FactoryUnitEntry]
    ) -> list[tuple[str, dict]]:
        """Return SHARED_COMMANDS that are referenced by any selected entry."""
        if any(e.uses_shared_commands for e in selected):
            return list(SHARED_COMMANDS)
        return []

    def _run_shared_commands(
        self,
        shared: list[tuple[str, dict]],
        author_email: str,
        *,
        dry_run: bool,
        skip_refresh: bool,
    ) -> None:
        for cmd_name, kwargs in shared:
            final_kwargs = dict(kwargs)
            final_kwargs["author"] = author_email
            if skip_refresh and cmd_name == "generate_bach_unit_matrix":
                final_kwargs["skip_refresh"] = True
            self._log_step(cmd_name, final_kwargs)
            if not dry_run:
                call_command(cmd_name, **final_kwargs)

    # ------------------------------------------------------------------
    # Per-entry execution
    # ------------------------------------------------------------------

    def _run_entry(
        self, entry: FactoryUnitEntry, author_email: str, *, dry_run: bool
    ) -> dict:
        unit_label = _unit_str(entry.unit)
        if entry.kind == "curated":
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"  [curated] unit {unit_label} — skipping (managed via "
                    "import_factory_curated)"
                )
            )
            return {"unit": unit_label, "kind": "curated", "status": "skipped"}

        if entry.uses_shared_commands and not entry.commands:
            # Handled entirely by SHARED_COMMANDS; nothing more to do here.
            return {"unit": unit_label, "kind": "generated", "status": "via_shared"}

        for cmd_name, kwargs in entry.commands:
            final_kwargs = dict(kwargs)
            # Inject author if the sub-command accepts it
            final_kwargs.setdefault("author", author_email)
            self._log_step(cmd_name, final_kwargs)
            if not dry_run:
                call_command(cmd_name, **final_kwargs)

        return {"unit": unit_label, "kind": "generated", "status": "ok"}

    # ------------------------------------------------------------------
    # --report
    # ------------------------------------------------------------------

    def _handle_report(
        self, selected: list[FactoryUnitEntry], author_email: str | None
    ) -> None:
        from apps.exercises.models import Playlist

        self.stdout.write(self.style.MIGRATE_HEADING("\nFactory Library Coverage Report"))
        header = f"{'unit':>6} | {'title':<40} | {'playlists':>9} | {'exercises':>9} | coverage"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        for entry in sorted(selected, key=_unit_key):
            unit_label = _unit_str(entry.unit)

            # Taxonomy title
            taxonomy_unit = TaxonomyReader.get_unit(unit_label)
            title = (taxonomy_unit or {}).get("title", "(no taxonomy entry)")[:40]

            playlist_count = 0
            exercise_count = 0

            if author_email:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                try:
                    factory_user = User.objects.get(email=author_email)
                    tag = f"unit:{unit_label}"
                    playlists = Playlist.objects.filter(
                        authored_by=factory_user,
                        skill_tags__contains=[tag],
                    )
                    playlist_count = playlists.count()
                    for pl in playlists:
                        exercise_count += pl.exercises.count()
                except User.DoesNotExist:
                    pass

            flag = "" if playlist_count > 0 else " *** NO COVERAGE ***"
            self.stdout.write(
                f"{unit_label:>6} | {title:<40} | {playlist_count:>9} | "
                f"{exercise_count:>9} |{flag}"
            )

        self.stdout.write("")

    # ------------------------------------------------------------------
    # --verify
    # ------------------------------------------------------------------

    def _handle_verify(
        self, selected: list[FactoryUnitEntry], author_email: str | None
    ) -> None:
        from apps.exercises.models import Playlist
        from django.contrib.auth import get_user_model

        if not author_email:
            raise CommandError(
                "--author (or settings.FACTORY_USER_EMAIL) is required for --verify."
            )

        User = get_user_model()
        try:
            factory_user = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(
                f"Factory user {author_email!r} not found.  "
                "Run ensure_factory_account first."
            )

        failures: list[str] = []
        self.stdout.write(self.style.MIGRATE_HEADING("\nFactory Library Verify"))

        for entry in sorted(selected, key=_unit_key):
            unit_label = _unit_str(entry.unit)
            tag = f"unit:{unit_label}"

            if entry.kind == "curated":
                # Curated: playlist must exist and be non-empty
                playlists = Playlist.objects.filter(
                    authored_by=factory_user,
                    skill_tags__contains=[tag],
                )
                if not playlists.exists():
                    msg = f"unit {unit_label} [curated]: no playlist found"
                    failures.append(msg)
                    self.stdout.write(self.style.ERROR(f"  FAIL  {msg}"))
                    continue
                empty = [pl for pl in playlists if pl.exercises.count() == 0]
                if empty:
                    names = ", ".join(pl.name for pl in empty)
                    msg = f"unit {unit_label} [curated]: empty playlist(s): {names}"
                    failures.append(msg)
                    self.stdout.write(self.style.ERROR(f"  FAIL  {msg}"))
                    continue
                self.stdout.write(
                    self.style.SUCCESS(f"  OK    unit {unit_label} [curated]")
                )

            else:
                # Generated: >=1 non-empty playlist tagged unit:N
                playlists = Playlist.objects.filter(
                    authored_by=factory_user,
                    skill_tags__contains=[tag],
                )
                if not playlists.exists():
                    msg = f"unit {unit_label}: no factory playlist with tag {tag!r}"
                    failures.append(msg)
                    self.stdout.write(self.style.ERROR(f"  FAIL  {msg}"))
                    continue
                has_exercises = any(pl.exercises.count() > 0 for pl in playlists)
                if not has_exercises:
                    msg = f"unit {unit_label}: all factory playlists are empty"
                    failures.append(msg)
                    self.stdout.write(self.style.ERROR(f"  FAIL  {msg}"))
                    continue
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK    unit {unit_label} "
                        f"({playlists.count()} playlist(s), "
                        f"{sum(pl.exercises.count() for pl in playlists)} exercises)"
                    )
                )

        self.stdout.write("")
        if failures:
            raise CommandError(
                f"Verify failed ({len(failures)} unit(s)):\n"
                + "\n".join(f"  - {f}" for f in failures)
            )
        self.stdout.write(self.style.SUCCESS("All selected units verified OK."))

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------

    def _print_summary(self, rows: list[dict], *, dry_run: bool) -> None:
        self.stdout.write("")
        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.MIGRATE_HEADING(f"{prefix}Factory Library Summary"))
        header = f"{'unit':>6} | {'kind':^9} | status"
        self.stdout.write(header)
        self.stdout.write("-" * 40)
        for row in rows:
            self.stdout.write(
                f"{row['unit']:>6} | {row['kind']:^9} | {row['status']}"
            )
        ok_count = sum(1 for r in rows if r["status"] in ("ok", "via_shared"))
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{prefix}Done. {ok_count}/{len(rows)} units processed."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_step(self, cmd_name: str, kwargs: dict) -> None:
        kw_str = " ".join(
            f"--{k.replace('_', '-')} {v}"
            for k, v in sorted(kwargs.items())
            if v is not True and v is not False and v is not None
        )
        flags = " ".join(
            f"--{k.replace('_', '-')}"
            for k, v in sorted(kwargs.items())
            if v is True
        )
        parts = [f"call_command({cmd_name!r}"]
        if kw_str:
            parts.append(kw_str)
        if flags:
            parts.append(flags)
        self.stdout.write(self.style.HTTP_INFO(f"  >> {' '.join(parts)})"))
