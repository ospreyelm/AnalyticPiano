# Efficient Bach Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repeated per-unit Bach chorale imports with an import-once, playlist-many workflow, then provide a safe cleanup path for duplicate chorale exercise rows.

**Architecture:** Build a reusable Bach phrase pool keyed by author, Riemenschneider number, phrase number, and mode. A new matrix command imports each Riemenschneider/mode combination once, stamps all requested unit tags on the source rows for compatibility, then builds per-unit playlists in playlist-only mode. A later cleanup command removes duplicate older per-unit rows only after proving they are not referenced by active playlists.

**Tech Stack:** Django management commands, PostgreSQL/ArrayField skill tags, existing UMTO factory/importers, existing `create_unit_playlist` ordering/filtering helpers, Django `TestCase` command tests.

---

## File Structure

- Modify: `apps/exercises/management/commands/create_unit_playlist.py`
  - Keep existing public CLI stable.
  - Add helper functions that can select/link unit playlists from an already-imported Bach pool.
  - Preserve `--playlist-only`, `--no-chord-filter`, and mode display labels.
- Create: `apps/exercises/management/commands/generate_bach_unit_matrix.py`
  - New high-level command that imports each mode/range once, then builds unit playlists.
  - Supports chunked/resumable execution by `--units`, `--modes`, `--riemenschneider`, `--playlist-only`, `--skip-refresh`.
- Create: `apps/exercises/management/commands/deduplicate_bach_phrases.py`
  - Audit-first cleanup command for duplicate Bach phrase rows.
  - Dry-run by default; destructive deletion requires `--execute`.
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`
  - Register both new commands per repository documentation rules.
- Modify: `docs/management_commands.md`
  - Document both new commands and recommended usage.
- Modify: `docs/neon_content_generation_runbook.md`
  - Replace the inefficient shell loop with the matrix command.
- Test: `apps/exercises/tests/test_generate_bach_unit_matrix.py`
  - Command-level tests for import-once behavior and playlist-only projection.
- Test: `apps/exercises/tests/test_deduplicate_bach_phrases.py`
  - Safety tests for dry-run, protected rows, and deletion only of unreferenced duplicates.

---

## Task 1: Add Quality Filtering and Extract Playlist Projection Helpers

**Files:**
- Modify: `apps/exercises/utils/skills_analyzer.py`
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`
- Modify: `apps/exercises/management/commands/backfill_skill_tags.py`
- Modify: `apps/exercises/management/commands/create_unit_playlist.py`
- Test: `apps/exercises/tests/test_create_unit_playlist.py`

- [ ] **Step 1: Write quality check helpers in `skills_analyzer.py`**

Add `parse_riem_and_measures(description)` and `check_wir_key_change(description)` to parse the Riemenschneider number/measures from the exercise description and lookup local keys in the When in Rome corpus.

Also, add a rest checking loop inside `analyze_chunk_skills(chunk, chunk_key, description=None)` that looks for any `Rest` element in a part's voice timeline that is strictly between its first and last sounding note.

If the phrase is rest-free, append the `"no_interior_rests"` tag. If no key change is detected via When in Rome, append the `"no_key_change"` tag.

- [ ] **Step 2: Pass `description` in callers of `analyze_chunk_skills`**

Modify `import_bach_phrases.py` and `backfill_skill_tags.py` to pass the exercise's `description` to `analyze_chunk_skills(..., description=...)` so key shift checks can run.

- [ ] **Step 3: Write failing test for Roman display label**

Add this test near the existing `CreateUnitPlaylistCommandTest` tests in `apps/exercises/tests/test_create_unit_playlist.py`:

```python
@patch("apps.exercises.management.commands.create_unit_playlist.call_command")
def test_roman_playlist_uses_display_label(self, mock_call):
    call_command(
        "create_unit_playlist",
        unit=11,
        riemenschneider="21",
        author="teacher@example.com",
        mode="roman",
    )
    self.assertTrue(
        Playlist.objects.filter(
            name="Unit 11 — Pre-dominants (Roman Numeral Analysis)",
            authored_by=self.author,
        ).exists()
    )
```

- [ ] **Step 4: Run the failing test**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_create_unit_playlist.CreateUnitPlaylistCommandTest.test_roman_playlist_uses_display_label -v 2
```

Expected before implementation is currently PASS if the local label change already exists; if it passes, keep the test as a regression guard and continue.

- [ ] **Step 5: Add reusable helper for mode display labels if missing**

Ensure `create_unit_playlist.py` contains:

```python
def _mode_display_label(mode: str) -> str:
    if mode == "roman":
        return "Roman Numeral Analysis"
    return mode
```

Ensure playlist names use:

```python
playlist_name = f"Unit {unit_num} — {title} ({_mode_display_label(mode)})"
```

- [ ] **Step 6: Extract candidate selection and apply quality filtering in helper**

In `create_unit_playlist.py`, add a module-level helper `_select_bach_candidates` that filters by quality tags:
- Require `"no_interior_rests"` for all exercises in the playlist.
- Require `"no_key_change"` if `unit_num < 16` (before secondary chord units are introduced).

```python
def _select_bach_candidates(*, author, unit_num: int, mode: str, riem_range: list[int], no_chord_filter: bool):
    unit_tag = f"unit:{unit_num}"
    mode_tag = f"mode:{mode}"
    riem_set = set(riem_range)
    candidates = Exercise.objects.filter(
        authored_by=author,
        skill_tags__contains=[unit_tag],
    ).filter(
        skill_tags__contains=[mode_tag],
    )

    # Quality exclusions:
    # 1. No key changes permitted for units before secondary chords (unit 16)
    if unit_num < 16:
        candidates = candidates.filter(skill_tags__contains=["no_key_change"])
    # 2. Avoid interior rests
    candidates = candidates.filter(skill_tags__contains=["no_interior_rests"])

    family = _mode_to_family(mode)
    require_new_chords = (
        not no_chord_filter
        and mode in ("roman", "figures", "play_figures", "matching")
    )
    selected = []
    for ex in candidates:
        riem_num, _ = Command._extract_riem_phrase(ex.description or "")
        if riem_num not in riem_set:
            continue
        if require_new_chords and not Command._has_new_chord(ex, unit_num, family):
            continue
        selected.append(ex)
    selected.sort(key=lambda ex: _exercise_order_key(ex, unit_num, family))
    return selected
```

- [ ] **Step 7: Use helper in `Command.handle`**

Replace the inline candidate loop with:

```python
selected = _select_bach_candidates(
    author=author,
    unit_num=unit_num,
    mode=mode,
    riem_range=riem_range,
    no_chord_filter=options.get("no_chord_filter", False),
)
```

Preserve the existing `ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()` and link creation block.

- [ ] **Step 8: Run focused tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_create_unit_playlist -v 2
```

Expected: all tests pass.

---

## Task 2: Add Matrix Command For Import-Once Generation

**Files:**
- Create: `apps/exercises/management/commands/generate_bach_unit_matrix.py`
- Test: `apps/exercises/tests/test_generate_bach_unit_matrix.py`

- [ ] **Step 1: Write failing tests**

Create `apps/exercises/tests/test_generate_bach_unit_matrix.py`:

```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


User = get_user_model()


class GenerateBachUnitMatrixCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    @patch("apps.exercises.management.commands.generate_bach_unit_matrix.call_command")
    def test_imports_each_mode_once_with_all_unit_tags_then_builds_playlists(self, mock_call):
        call_command(
            "generate_bach_unit_matrix",
            units="9,10,11",
            modes="roman,play",
            riemenschneider="1-2",
            author="teacher@example.com",
            public=True,
            skip_refresh=True,
        )

        import_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "import_bach_phrases"]
        playlist_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "create_unit_playlist"]

        self.assertEqual(len(import_calls), 2)
        self.assertEqual(import_calls[0].kwargs["mode"], "roman")
        self.assertEqual(import_calls[0].kwargs["riemenschneider"], "1-2")
        self.assertEqual(
            import_calls[0].kwargs["extra_tags"],
            ["unit:9", "unit:10", "unit:11", "mode:roman"],
        )
        self.assertTrue(import_calls[0].kwargs["overwrite"])
        self.assertTrue(import_calls[0].kwargs["public"])

        self.assertEqual(len(playlist_calls), 6)
        self.assertTrue(all(c.kwargs["playlist_only"] for c in playlist_calls))

    @patch("apps.exercises.management.commands.generate_bach_unit_matrix.call_command")
    def test_playlist_only_skips_imports(self, mock_call):
        call_command(
            "generate_bach_unit_matrix",
            units="9,10",
            modes="roman",
            riemenschneider="1-2",
            author="teacher@example.com",
            playlist_only=True,
            skip_refresh=True,
        )

        self.assertFalse(any(c.args and c.args[0] == "import_bach_phrases" for c in mock_call.call_args_list))
        playlist_calls = [c for c in mock_call.call_args_list if c.args and c.args[0] == "create_unit_playlist"]
        self.assertEqual(len(playlist_calls), 2)

    def test_rejects_unknown_author(self):
        with self.assertRaisesMessage(Exception, "No user with email"):
            call_command(
                "generate_bach_unit_matrix",
                units="9",
                modes="roman",
                riemenschneider="1",
                author="missing@example.com",
                skip_refresh=True,
            )
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_generate_bach_unit_matrix -v 2
```

Expected: failure because command `generate_bach_unit_matrix` does not exist.

- [ ] **Step 3: Implement command skeleton and parsers**

Create `apps/exercises/management/commands/generate_bach_unit_matrix.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


DEFAULT_UNITS = "9,10,11,12,14,16,17,18,19,20"
DEFAULT_MODES = "roman,figures,play,play_figures"


def _parse_csv_ints(value: str) -> list[int]:
    out = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise CommandError("At least one unit is required.")
    return out


def _parse_csv_strings(value: str) -> list[str]:
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
                tags = [f"unit:{unit}" for unit in units] + [f"mode:{mode}"]
                self.stdout.write(self.style.MIGRATE_HEADING(f"[import] mode={mode}"))
                call_command(
                    "import_bach_phrases",
                    riemenschneider=options["riemenschneider"],
                    author=author_email,
                    mode=mode,
                    min_measures=options["min_measures"],
                    extra_tags=tags,
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
            call_command("reanalyze_knowledge_graph")

        self.stdout.write(self.style.SUCCESS("generate_bach_unit_matrix complete."))
```

- [ ] **Step 4: Run tests and fix option naming issues**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_generate_bach_unit_matrix -v 2
```

Expected: tests pass. If Django passes `--skip-refresh` as `skip_refresh`, keep using `options["skip_refresh"]`.

- [ ] **Step 5: Smoke-test dry command with mocked DB avoided**

Run a tiny real command locally only after tests pass:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_bach_unit_matrix --units 9 --modes roman --riemenschneider 1 --author avner-local2025@localhost --public --skip-refresh
```

Expected: one import pass for R1 roman, then one playlist projection.

---

## Task 3: Add Audit-First Deduplication Command

**Files:**
- Create: `apps/exercises/management/commands/deduplicate_bach_phrases.py`
- Test: `apps/exercises/tests/test_deduplicate_bach_phrases.py`

- [ ] **Step 1: Write failing tests**

Create `apps/exercises/tests/test_deduplicate_bach_phrases.py`:

```python
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise


User = get_user_model()


class DeduplicateBachPhrasesCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    def test_dry_run_does_not_delete_duplicates(self):
        make_umto_exercise(self.author, ["unit:9", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")
        make_umto_exercise(self.author, ["unit:10", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")

        call_command("deduplicate_bach_phrases", author="teacher@example.com")

        self.assertEqual(Exercise.objects.filter(description="Bach R1 - Phrase 1 (mm.1-4) [roman]").count(), 2)

    def test_execute_deletes_unreferenced_duplicate(self):
        keep = make_umto_exercise(self.author, ["unit:9", "unit:10", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")
        remove = make_umto_exercise(self.author, ["unit:10", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")

        call_command("deduplicate_bach_phrases", author="teacher@example.com", execute=True)

        self.assertTrue(Exercise.objects.filter(pk=keep.pk).exists())
        self.assertFalse(Exercise.objects.filter(pk=remove.pk).exists())

    def test_execute_preserves_referenced_duplicate(self):
        make_umto_exercise(self.author, ["unit:9", "unit:10", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")
        referenced = make_umto_exercise(self.author, ["unit:10", "mode:roman"], 1, "Bach R1 - Phrase 1 (mm.1-4) [roman]")
        playlist = Playlist.objects.create(name="Unit 10 Test", authored_by=self.author, skill_tags=["unit:10"])
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=referenced, order=1)

        call_command("deduplicate_bach_phrases", author="teacher@example.com", execute=True)

        self.assertTrue(Exercise.objects.filter(pk=referenced.pk).exists())
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_deduplicate_bach_phrases -v 2
```

Expected: failure because command does not exist.

- [ ] **Step 3: Implement audit-first deletion**

Create `apps/exercises/management/commands/deduplicate_bach_phrases.py`:

```python
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Exercise, ExercisePlaylistOrdered


class Command(BaseCommand):
    help = "Audit or delete unreferenced duplicate Bach phrase exercises for one author."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{options['author']}'.")

        rows = Exercise.objects.filter(
            authored_by=author,
            description__startswith="Bach R",
        ).order_by("description", "-created", "_id")

        groups = defaultdict(list)
        for ex in rows:
            groups[ex.description].append(ex)

        duplicate_groups = {desc: xs for desc, xs in groups.items() if len(xs) > 1}
        delete_ids = []
        protected_ids = set(
            ExercisePlaylistOrdered.objects.filter(
                exercise_id__in=[ex.pk for xs in duplicate_groups.values() for ex in xs]
            ).values_list("exercise_id", flat=True)
        )

        for desc, xs in duplicate_groups.items():
            keep = xs[0]
            for ex in xs[1:]:
                if ex.pk in protected_ids:
                    self.stdout.write(self.style.WARNING(f"protected referenced duplicate {ex.id}: {desc}"))
                    continue
                delete_ids.append(ex.pk)

        self.stdout.write(f"Duplicate descriptions: {len(duplicate_groups)}")
        self.stdout.write(f"Unreferenced duplicates to delete: {len(delete_ids)}")

        if options["execute"] and delete_ids:
            deleted, _ = Exercise.objects.filter(pk__in=delete_ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} rows."))
        elif not options["execute"]:
            self.stdout.write("Dry run only. Pass --execute to delete unreferenced duplicates.")
```

- [ ] **Step 4: Run tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_deduplicate_bach_phrases -v 2
```

Expected: tests pass.

---

## Task 4: Register Commands And Update Docs

**Files:**
- Modify: `apps/exercises/management/commands/list_exercise_generators.py`
- Modify: `docs/management_commands.md`
- Modify: `docs/neon_content_generation_runbook.md`

- [ ] **Step 1: Register command catalog entries**

In `list_exercise_generators.py`, add under “Bach chorale phrases (Riemenschneider)”:

```python
(
    "generate_bach_unit_matrix",
    "Import Bach Riemenschneider phrases once per mode, then project them into per-unit playlists.",
    "python manage.py generate_bach_unit_matrix --riemenschneider 1-30 --units 9,10,11,12,14,16,17,18,19,20 --modes roman,figures,play,play_figures --author admin@example.com --public",
),
(
    "deduplicate_bach_phrases",
    "Audit or delete unreferenced duplicate Bach phrase rows after switching to import-once generation.",
    "python manage.py deduplicate_bach_phrases --author admin@example.com",
),
```

- [ ] **Step 2: Update `docs/management_commands.md`**

Add entries in the Bach/Riemenschneider section:

```markdown
**`generate_bach_unit_matrix`** — Efficient Bach generation path: imports each Riemenschneider/mode combination once, stamps requested unit tags, and builds each unit playlist from the shared pool.
```

```bash
python manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author admin@example.com \
  --public
```

```markdown
**`deduplicate_bach_phrases`** — Audit duplicate Bach phrase rows for one author. Dry-run by default; pass `--execute` only after verifying playlist links are safe.
```

```bash
python manage.py deduplicate_bach_phrases --author admin@example.com
python manage.py deduplicate_bach_phrases --author admin@example.com --execute
```

- [ ] **Step 3: Update Neon runbook**

In `docs/neon_content_generation_runbook.md`, replace the current nested `for unit` loop with:

```bash
python3 manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author "$AUTHOR" \
  --public
```

Add the resume-only command:

```bash
python3 manage.py generate_bach_unit_matrix \
  --riemenschneider 1-30 \
  --units 9,10,11,12,14,16,17,18,19,20 \
  --modes roman,figures,play,play_figures \
  --author "$AUTHOR" \
  --public \
  --playlist-only \
  --skip-refresh
```

- [ ] **Step 4: Run catalog command**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py list_exercise_generators
```

Expected: output includes `generate_bach_unit_matrix` and `deduplicate_bach_phrases`.

---

## Task 5: Optional GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/generate-neon-content.yml`

- [ ] **Step 1: Add manual workflow**

Create `.github/workflows/generate-neon-content.yml`:

```yaml
name: Generate Neon Content

on:
  workflow_dispatch:
    inputs:
      author:
        description: "Author email"
        required: true
        default: "avnerdorman@gmail.com"
      riemenschneider:
        description: "Riemenschneider range"
        required: true
        default: "1-30"
      units:
        description: "Comma-separated units"
        required: true
        default: "9,10,11,12,14,16,17,18,19,20"
      modes:
        description: "Comma-separated modes"
        required: true
        default: "roman,figures,play,play_figures"
      playlist_only:
        description: "Only rebuild playlists from existing rows"
        type: boolean
        required: true
        default: false

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    env:
      DJANGO_SETTINGS_MODULE: harmony.settings.common
      DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Verify database
        run: |
          python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute('select 1'); print(c.fetchone())"

      - name: Migrate
        run: python manage.py migrate

      - name: Generate Bach unit matrix
        run: |
          ARGS=""
          if [ "${{ inputs.playlist_only }}" = "true" ]; then
            ARGS="--playlist-only --skip-refresh"
          fi
          python manage.py generate_bach_unit_matrix \
            --riemenschneider "${{ inputs.riemenschneider }}" \
            --units "${{ inputs.units }}" \
            --modes "${{ inputs.modes }}" \
            --author "${{ inputs.author }}" \
            --public \
            $ARGS
```

- [ ] **Step 2: Document required secret**

Add to `docs/neon_content_generation_runbook.md`:

```markdown
For GitHub Actions, store the direct Neon URL as repository secret `NEON_DATABASE_URL`.
```

- [ ] **Step 3: Run YAML syntax check by inspection**

Run:

```bash
git diff -- .github/workflows/generate-neon-content.yml
```

Expected: workflow uses only `workflow_dispatch`, has `timeout-minutes`, and references `secrets.NEON_DATABASE_URL`.

---

## Task 6: Verification And Migration Procedure

**Files:**
- No production code changes.

- [ ] **Step 1: Verify command tests**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py test apps.exercises.tests.test_create_unit_playlist apps.exercises.tests.test_generate_bach_unit_matrix apps.exercises.tests.test_deduplicate_bach_phrases -v 2
```

Expected: all tests pass.

- [ ] **Step 2: Run a small local matrix**

Run:

```bash
unset DATABASE_URL
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py generate_bach_unit_matrix \
  --riemenschneider 1-2 \
  --units 9,10 \
  --modes roman,play \
  --author avner-local2025@localhost \
  --public \
  --skip-refresh
```

Expected: imports happen once for `roman` and once for `play`; playlists are built for Unit 9 and Unit 10.

- [ ] **Step 3: Audit duplicates**

Run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py deduplicate_bach_phrases --author avner-local2025@localhost
```

Expected: prints duplicate description count and deletion candidate count without deleting rows.

- [ ] **Step 4: Do not execute deletion until playlists are verified**

Only after testing student playlist playback for several Bach playlists, run:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python3 manage.py deduplicate_bach_phrases --author avner-local2025@localhost --execute
```

Expected: deletes only unreferenced duplicate Bach rows.

---

## Self-Review

- Spec coverage: The plan covers import-once generation, playlist projection, deduplication, documentation, command catalog registration, and optional GitHub Actions execution.
- Placeholder scan: No TBD/TODO placeholders remain; all tasks contain exact file paths, commands, and expected behavior.
- Type consistency: The plan consistently uses `generate_bach_unit_matrix`, `deduplicate_bach_phrases`, `units`, `modes`, `riemenschneider`, `playlist_only`, and `skip_refresh`.
