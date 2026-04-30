# Phase 2 — Unit Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `create_unit_playlist` management command that imports Bach phrases for a unit and creates a dynamic+adaptive playlist in one idempotent call, replacing all one-off batch scripts.

**Architecture:** Two files change: `import_bach_phrases.py` gains `--extra-tags` and skip-if-exists; a new `create_unit_playlist.py` loops over a Riemenschneider range, calls `import_bach_phrases` via `call_command`, then finds-or-creates a `Playlist`. No new models. No migrations.

**Tech Stack:** Django management commands, `call_command()`, `music_theory_taxonomy_with_branches.json` (already at repo root), `apps.exercises.models.Playlist`, `apps.exercises.management.commands.import_bach_phrases`.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `apps/exercises/management/commands/import_bach_phrases.py` | Add `--extra-tags`, skip-if-exists |
| Create | `apps/exercises/management/commands/create_unit_playlist.py` | Loop, import, playlist find-or-create |
| Create | `apps/exercises/tests/test_create_unit_playlist.py` | Unit tests (no music21 — mock `call_command`) |

---

## Task 1: Add `--extra-tags` to `import_bach_phrases`

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`

The command currently passes only `detected_skills` to `save_umto_exercise`. We need to merge in caller-supplied tags (e.g. `unit:11`).

- [ ] **Step 1.1: Add the argument**

In `add_arguments`, after the existing `--dry-run` argument, add:

```python
parser.add_argument(
    '--extra-tags',
    nargs='*',
    default=[],
    metavar='TAG',
    help='Additional skill tags stamped on every imported exercise (e.g. unit:11)',
)
```

- [ ] **Step 1.2: Merge tags before save**

Find the line (around line 203):
```python
detected_skills, detected_complexity = analyze_chunk_skills(phrase_score, m21_key.tonicPitchNameWithCase)
```

Two lines below that (after the except block), find:
```python
ex = save_umto_exercise(
    ...
    skill_tags=detected_skills,
```

Replace `skill_tags=detected_skills` with:
```python
skill_tags=list(set(detected_skills + options['extra_tags'])),
```

- [ ] **Step 1.3: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py
git commit -m "feat: add --extra-tags to import_bach_phrases"
```

---

## Task 2: Add skip-if-exists idempotency to `import_bach_phrases`

**Files:**
- Modify: `apps/exercises/management/commands/import_bach_phrases.py`

Without this, re-running the command creates duplicate exercises.

- [ ] **Step 2.1: Write the failing test**

Create `apps/exercises/tests/test_create_unit_playlist.py`:

```python
from unittest.mock import patch, call
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.exercises.models import Exercise, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()


class ImportBachPhrasesIdempotencyTest(TestCase):
    """import_bach_phrases skips exercises whose description already exists."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="teacher@example.com", password="pw"
        )

    def test_skips_existing_description(self):
        """Running import_bach_phrases twice for the same chorale creates no duplicates."""
        # Pre-create an exercise with a matching description
        make_umto_exercise(
            author=self.author,
            skill_tags=[],
            complexity=1,
            description="Bach R1 - Phrase 1 (mm.1-4)",
        )
        count_before = Exercise.objects.count()

        # Calling import_bach_phrases with riemenschneider=1 would normally
        # create phrases. With skip-if-exists, it must skip any whose
        # description already exists.
        # We can't call it for real (requires music21 corpus), so we test the
        # helper directly.
        from apps.exercises.management.commands.import_bach_phrases import (
            _description_exists,
        )
        self.assertTrue(_description_exists("Bach R1 - Phrase 1 (mm.1-4)"))
        self.assertFalse(_description_exists("Bach R1 - Phrase 99 (mm.99-200)"))

        self.assertEqual(Exercise.objects.count(), count_before)
```

- [ ] **Step 2.2: Run test — expect ImportError**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist.ImportBachPhrasesIdempotencyTest -v 2
```

Expected: `ImportError: cannot import name '_description_exists'`

- [ ] **Step 2.3: Add `_description_exists` helper and skip logic**

At the top of `import_bach_phrases.py`, after the imports, add:

```python
def _description_exists(description: str) -> bool:
    from apps.exercises.models import Exercise
    return Exercise.objects.filter(description=description).exists()
```

Inside `handle`, find the block that builds `description` (around line 225):
```python
description = f"Bach {bwv_display} - Phrase {idx+1} (mm.{start_m}-{end_m})"
```

Immediately after that line, add:
```python
if _description_exists(description[:60]):
    self.stdout.write(
        self.style.WARNING(f"  Skipping (exists): {description[:60]}")
    )
    start_m = end_m + 1
    continue
```

- [ ] **Step 2.4: Run test — expect PASS**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist.ImportBachPhrasesIdempotencyTest -v 2
```

Expected: `OK`

- [ ] **Step 2.5: Commit**

```bash
git add apps/exercises/management/commands/import_bach_phrases.py \
        apps/exercises/tests/test_create_unit_playlist.py
git commit -m "feat: skip duplicate exercises in import_bach_phrases"
```

---

## Task 3: Taxonomy lookup helper

**Files:**
- Create: `apps/exercises/management/commands/create_unit_playlist.py` (started)

The new command needs to resolve unit title from `music_theory_taxonomy_with_branches.json`. The taxonomy is a list of branches → tiers → units. Unit `n` can be an int or string (e.g. `"A1"`), so compare as strings.

- [ ] **Step 3.1: Write the failing test**

Add to `apps/exercises/tests/test_create_unit_playlist.py`:

```python
class TaxonomyLookupTest(TestCase):
    def test_finds_unit_by_number(self):
        from apps.exercises.management.commands.create_unit_playlist import (
            _lookup_unit,
        )
        unit = _lookup_unit(9)
        self.assertIsNotNone(unit)
        self.assertEqual(str(unit['n']), '9')
        self.assertIn('title', unit)
        self.assertIn('tags', unit)

    def test_returns_none_for_missing_unit(self):
        from apps.exercises.management.commands.create_unit_playlist import (
            _lookup_unit,
        )
        unit = _lookup_unit(999)
        self.assertIsNone(unit)
```

- [ ] **Step 3.2: Run test — expect ImportError**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist.TaxonomyLookupTest -v 2
```

Expected: `ImportError: cannot import name '_lookup_unit'`

- [ ] **Step 3.3: Create `create_unit_playlist.py` with `_lookup_unit`**

Create `apps/exercises/management/commands/create_unit_playlist.py`:

```python
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import Playlist

TAXONOMY_PATH = Path(__file__).resolve().parents[5] / "music_theory_taxonomy_with_branches.json"

User = get_user_model()


def _lookup_unit(unit_num: int) -> dict | None:
    """Return the taxonomy unit dict for unit_num, or None if not found."""
    with open(TAXONOMY_PATH) as f:
        taxonomy = json.load(f)
    for branch in taxonomy:
        for tier in branch.get("tiers", []):
            for unit in tier.get("units", []):
                if str(unit["n"]) == str(unit_num):
                    return unit
    return None


def _parse_range(text: str) -> list[int]:
    """Parse '21-40' or '21' into a list of integers."""
    text = text.strip()
    if "-" in text:
        start, end = text.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(text)]


class Command(BaseCommand):
    help = "Import Bach phrases for a unit and create a dynamic+adaptive playlist."

    def add_arguments(self, parser):
        parser.add_argument("--unit", type=int, required=True)
        parser.add_argument("--riemenschneider", type=str, required=True,
                            help="Range like '21-40' or single '21'")
        parser.add_argument("--author", type=str, required=True,
                            help="Email of the exercise author")
        parser.add_argument("--mode", type=str,
                            choices=["roman", "play", "figures", "matching"],
                            default="roman")
        parser.add_argument("--min-measures", type=int, default=3)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        pass  # implemented in Task 4
```

- [ ] **Step 3.4: Run test — expect PASS**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist.TaxonomyLookupTest -v 2
```

Expected: `OK`

- [ ] **Step 3.5: Commit**

```bash
git add apps/exercises/management/commands/create_unit_playlist.py \
        apps/exercises/tests/test_create_unit_playlist.py
git commit -m "feat: scaffold create_unit_playlist with taxonomy lookup"
```

---

## Task 4: Implement `handle` — import loop + playlist find-or-create

**Files:**
- Modify: `apps/exercises/management/commands/create_unit_playlist.py`

- [ ] **Step 4.1: Write the failing test**

Add to `apps/exercises/tests/test_create_unit_playlist.py`:

```python
class CreateUnitPlaylistCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            email="teacher@example.com", password="pw"
        )

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_creates_playlist(self, mock_call):
        """Command creates a dynamic+adaptive playlist tagged unit:11."""
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21-22",
            author="teacher@example.com",
            mode="roman",
        )
        playlist = Playlist.objects.get(name="Unit 11 — Pre-dominants (roman)")
        self.assertTrue(playlist.is_dynamic)
        self.assertTrue(playlist.is_adaptive)
        self.assertIn("unit:11", playlist.skill_tags)

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_calls_import_for_each_chorale(self, mock_call):
        """Command calls import_bach_phrases once per Riemenschneider number."""
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21-23",
            author="teacher@example.com",
            mode="roman",
        )
        import_calls = [c for c in mock_call.call_args_list
                        if c.args and c.args[0] == "import_bach_phrases"]
        self.assertEqual(len(import_calls), 3)

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_idempotent_playlist(self, mock_call):
        """Re-running does not create a second playlist."""
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21-22",
            author="teacher@example.com",
            mode="roman",
        )
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21-22",
            author="teacher@example.com",
            mode="roman",
        )
        self.assertEqual(
            Playlist.objects.filter(name="Unit 11 — Pre-dominants (roman)").count(), 1
        )

    @patch("apps.exercises.management.commands.create_unit_playlist.call_command")
    def test_extra_tags_passed_to_import(self, mock_call):
        """import_bach_phrases is called with extra_tags=['unit:11']."""
        call_command(
            "create_unit_playlist",
            unit=11,
            riemenschneider="21",
            author="teacher@example.com",
            mode="roman",
        )
        import_call = next(
            c for c in mock_call.call_args_list
            if c.args and c.args[0] == "import_bach_phrases"
        )
        self.assertIn("unit:11", import_call.kwargs.get("extra_tags", []))

    def test_fails_on_unknown_unit(self):
        """Command raises CommandError for a unit not in taxonomy."""
        with self.assertRaises(CommandError):
            call_command(
                "create_unit_playlist",
                unit=999,
                riemenschneider="1",
                author="teacher@example.com",
            )

    def test_fails_on_unknown_author(self):
        """Command raises CommandError when author email not found."""
        with self.assertRaises(CommandError):
            call_command(
                "create_unit_playlist",
                unit=11,
                riemenschneider="21",
                author="nobody@example.com",
            )
```

- [ ] **Step 4.2: Run tests — expect FAIL**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist.CreateUnitPlaylistCommandTest -v 2
```

Expected: multiple failures (`playlist not found`, `wrong call count`, etc.)

- [ ] **Step 4.3: Implement `handle`**

Replace `pass` in `handle` with:

```python
def handle(self, *args, **options):
    unit_num = options["unit"]
    riem_range = _parse_range(options["riemenschneider"])
    author_email = options["author"]
    mode = options["mode"]
    min_measures = options["min_measures"]
    dry_run = options["dry_run"]

    # 1. Validate unit
    unit_meta = _lookup_unit(unit_num)
    if unit_meta is None:
        raise CommandError(f"Unit {unit_num} not found in taxonomy.")
    title = unit_meta["title"]
    self.stdout.write(f"Unit {unit_num}: {title}")

    # 2. Validate author
    try:
        author = User.objects.get(email=author_email)
    except User.DoesNotExist:
        raise CommandError(f"No user with email '{author_email}'.")

    # 3. Import exercises
    unit_tag = f"unit:{unit_num}"
    self.stdout.write(
        f"Importing Riemenschneider {riem_range[0]}–{riem_range[-1]} "
        f"({len(riem_range)} chorales)..."
    )
    for riem_num in riem_range:
        self.stdout.write(f"  R{riem_num}...")
        if not dry_run:
            call_command(
                "import_bach_phrases",
                riemenschneider=riem_num,
                author=author_email,
                mode=mode,
                min_measures=min_measures,
                extra_tags=[unit_tag],
            )

    # 4. Find or create playlist
    playlist_name = f"Unit {unit_num} — {title} ({mode})"
    if dry_run:
        self.stdout.write(f"[dry-run] Would create playlist: {playlist_name}")
        return

    playlist, created = Playlist.objects.get_or_create(
        name=playlist_name,
        defaults=dict(
            authored_by=author,
            is_dynamic=True,
            is_adaptive=True,
            skill_tags=[unit_tag],
            is_public=False,
        ),
    )
    if not created:
        # Ensure flags are correct on re-run
        playlist.is_dynamic = True
        playlist.is_adaptive = True
        if unit_tag not in (playlist.skill_tags or []):
            playlist.skill_tags = list(playlist.skill_tags or []) + [unit_tag]
        playlist.save()

    action = "created" if created else "updated"
    self.stdout.write(
        self.style.SUCCESS(
            f"Playlist '{playlist_name}' ({playlist.id}) — {action}"
        )
    )
```

- [ ] **Step 4.4: Run tests — expect PASS**

```bash
python manage.py test apps.exercises.tests.test_create_unit_playlist -v 2
```

Expected: all tests `OK`

- [ ] **Step 4.5: Commit**

```bash
git add apps/exercises/management/commands/create_unit_playlist.py \
        apps/exercises/tests/test_create_unit_playlist.py
git commit -m "feat: implement create_unit_playlist command"
```

---

## Task 5: Smoke test end-to-end (dry-run)

**Files:** None changed — manual verification only.

- [ ] **Step 5.1: Run dry-run against real taxonomy**

```bash
python manage.py create_unit_playlist \
  --unit 11 \
  --riemenschneider 21-22 \
  --author YOUR_LOCAL_AUTHOR_EMAIL \
  --mode roman \
  --dry-run
```

Expected output:
```
Unit 11: Pre-dominants
Importing Riemenschneider 21–22 (2 chorales)...
[dry-run] Would create playlist: Unit 11 — Pre-dominants (roman)
```

If `CommandError: Unit 11 not found` — verify `TAXONOMY_PATH` resolves correctly:
```bash
python -c "from pathlib import Path; p = Path('apps/exercises/management/commands/create_unit_playlist.py').resolve().parents[4] / 'music_theory_taxonomy_with_branches.json'; print(p, p.exists())"
```

- [ ] **Step 5.2: Run full suite to check no regressions**

```bash
python manage.py test apps.exercises.tests -v 1
```

Expected: all existing tests still pass.

- [ ] **Step 5.3: Commit if any fixes needed, then tag**

```bash
git add -p  # stage only relevant fixes
git commit -m "fix: correct taxonomy path resolution in create_unit_playlist"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `--extra-tags` arg added to `import_bach_phrases` → Task 1
- [x] Skip-if-exists idempotency in `import_bach_phrases` → Task 2
- [x] Taxonomy lookup for unit title+tags → Task 3
- [x] Loop over range, call `import_bach_phrases` per chorale → Task 4
- [x] Playlist find-or-create, `is_dynamic=True`, `is_adaptive=True`, `skill_tags=['unit:N']` → Task 4
- [x] One playlist per mode (name includes mode) → Task 4
- [x] Idempotent on re-run (playlist) → Task 4 test
- [x] `--dry-run` flag → Task 4 handle + Task 5
- [x] Fail fast on unknown unit → Task 4 test + handle
- [x] Fail fast on unknown author → Task 4 test + handle

**Type consistency:**
- `_lookup_unit` returns `dict | None` — used in Task 3 tests and Task 4 handle ✓
- `_parse_range` returns `list[int]` — used in Task 4 handle ✓
- `extra_tags` kwarg passed to `call_command("import_bach_phrases", ...)` matches `options['extra_tags']` in Task 1 ✓
- `playlist.skill_tags` is an `ArrayField` — assigned as `list` throughout ✓
