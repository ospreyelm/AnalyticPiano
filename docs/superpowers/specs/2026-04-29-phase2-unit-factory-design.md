# Phase 2 — Unit Factory: `create_unit_playlist` Command

**Date:** 2026-04-29  
**Status:** Ready for implementation  
**Depends on:** Phase 1 (done)  
**Blocks:** Phase 3 workbench "Generate Unit" button

---

## Problem

Creating a new unit playlist requires:
1. Running `batch_import_unit9.py` (hand-edited copy per unit)
2. Manually resetting DB sequences
3. Manually linking exercises to playlists

Each one-off script is a liability. This command replaces all of them.

---

## Goal

Single idempotent command that imports Bach phrases for a unit and creates a dynamic+adaptive playlist, tagged correctly for the adaptive engine to serve.

```bash
python manage.py create_unit_playlist \
  --unit 11 \
  --riemenschneider 21-40 \
  --author admin@example.com \
  --mode roman
```

---

## Design

### Command: `create_unit_playlist`

**File:** `apps/exercises/management/commands/create_unit_playlist.py`

**Arguments:**

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--unit` | int | yes | Unit number (must exist in taxonomy JSON) |
| `--riemenschneider` | str | yes | Range like `21-40` or single `21` |
| `--author` | str | yes | Author email |
| `--mode` | str | no | `roman` (default), `play`, `figures`, `matching` |
| `--min-measures` | int | no | Min measures per phrase (default 3, passed to `import_bach_phrases`) |
| `--dry-run` | flag | no | Show what would be created without writing |

**Steps:**

1. **Validate unit** — read `music_theory_taxonomy_with_branches.json`, find unit N, extract `title` and `tags`. Fail fast if unit not found.

2. **Parse range** — split `--riemenschneider` into list of integers.

3. **Import exercises** — for each Riemenschneider number, call `import_bach_phrases` management command with:
   - `--riemenschneider N`
   - `--author`
   - `--mode`
   - `--min-measures`
   - `--extra-tags unit:N` ← new arg added to `import_bach_phrases`
   
   Idempotency: `import_bach_phrases` skips exercises whose `description` already exists (implement skip-if-exists check inside `import_bach_phrases`).

4. **Create/update playlist** — find or create `Playlist` with `name="Unit {N} — {title} ({mode})"`. Set:
   - `is_dynamic=True`
   - `is_adaptive=True`
   - `skill_tags=['unit:N']`
   - No `ExercisePlaylistOrdered` rows — dynamic playlist serves by tag at runtime.
   
   One playlist per mode. Running the command with `--mode roman` and `--mode play` creates two separate playlists. The pool for each is the same exercises (tagged `unit:N`), but assignment intent differs — the engine doesn't filter by mode, so separate playlists is what keeps a student from receiving a play exercise inside a Roman numeral assignment.
   
   Idempotency: if playlist with that name exists, update `skill_tags` and flags but do not duplicate.

5. **Report** — print count of exercises created/skipped, playlist ID.

---

## Changes to `import_bach_phrases`

**File:** `apps/exercises/management/commands/import_bach_phrases.py`

Two additions:

### 1. `--extra-tags` argument

```python
parser.add_argument('--extra-tags', nargs='*', default=[], 
                    help='Additional skill tags to add to every imported exercise')
```

Merged into `detected_skills` before calling `save_umto_exercise`:

```python
all_tags = list(set(detected_skills + options['extra_tags']))
```

### 2. Skip-if-exists idempotency

Before creating each exercise, check:

```python
if Exercise.objects.filter(description=description[:60]).exists():
    self.stdout.write(f"  Skipping (exists): {description[:60]}")
    start_m = end_m + 1
    continue
```

---

## Taxonomy lookup

**File:** `music_theory_taxonomy_with_branches.json`

The command reads this file at runtime to resolve unit title and tags. Walk structure:

```python
for branch in taxonomy:
    for tier in branch.get('tiers', []):
        for unit in tier.get('units', []):
            if unit['n'] == unit_num:
                return unit  # has 'title', 'tags'
```

---

## Playlist model fields used

| Field | Value |
|-------|-------|
| `name` | `"Unit {N} — {title} ({mode})"` e.g. `"Unit 11 — Pre-dominants (roman)"` |
| `is_dynamic` | `True` |
| `is_adaptive` | `True` |
| `skill_tags` | `['unit:N']` |
| `authored_by` | resolved from `--author` email |
| `is_public` | `False` (teacher controls visibility) |

No `ExercisePlaylistOrdered` rows created. The dynamic playlist engine finds exercises at serve-time via `skill_tags__contains=['unit:N']` query on `Exercise`.

---

## Idempotency guarantees

| Operation | Guard |
|-----------|-------|
| Exercise already exists | Skip by `description` match in `import_bach_phrases` |
| Playlist already exists | Find-or-create by `name` in `create_unit_playlist` |
| Re-running with wider range | New chorales imported, existing skipped, playlist unchanged |

---

## Example output

```
Loading taxonomy for Unit 11 (Pre-dominants)...
Riemenschneider range: 21–40 (20 chorales)

--- Riemenschneider 21 ---
Loading Riemenschneider Chorale #21...
Detected 4 phrases.
  Created UMTO Exercise E-abc123 (mm.1-6)
  Created UMTO Exercise E-def456 (mm.7-12)
  Skipping (exists): Bach R21 - Phrase 3 (mm.13-18)
  Created UMTO Exercise E-ghi789 (mm.19-24)

[...20 chorales...]

Playlist: Unit 11 — Pre-dominants (roman) (P-xyz999) — created
Total exercises created: 67 / skipped: 3
```

---

## What this does NOT do

- Does not wire mastery updates (Phase 3 concern)
- Does not import exercises in multiple modes in a single run — run once per mode
- Does not support MusicXML upload (Phase 3)
- Does not generate help text (Phase 5)
