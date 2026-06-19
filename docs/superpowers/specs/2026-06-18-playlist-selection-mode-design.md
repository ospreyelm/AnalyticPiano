# Playlist selection_mode + target_length + orphan-exercise fix

## Problem

Three related issues surfaced while brainstorming the Exercise/Playlist/Unit/Course
structure:

1. **Flag soup.** `Playlist.is_adaptive` and `Playlist.is_dynamic` are two booleans
   standing in for what's actually 3 distinct serving strategies. `is_adaptive` is
   near-vestigial at runtime — `apps/exercises/mastery.py:get_next_exercise` never
   checks it directly; only the OR'd dispatch flag `is_dynamic_or_adaptive`
   (`apps/student/views.py:1045`) does. Reading the two flags together doesn't tell
   you what kind of playlist you're looking at without also reading the serving
   code.

2. **Adaptive playlists are genuinely endless.** Static playlists terminate via
   `exercise_num > served_count` (`apps/student/views.py:1049`). Adaptive/dynamic
   playlists skip that check entirely — `get_next_exercise`
   (`apps/exercises/mastery.py:259`) returns a candidate as long as the pool isn't
   empty, with no concept of "done." The "next" button never disables
   (`apps/student/views.py:1131`, `lab/views.py:198`). This makes adaptive playlists
   unusable as a bounded course unit — the whole point of the mastery system (a
   large reusable exercise pool) only pays off if a teacher can carve a
   reasonably-sized course out of it.

3. **Orphan exercises.** The `/teacher/play/` Save dialog allows "Target playlist:
   None." `_append_to_playlist` (`lab/views.py:982`) returns `None` in that case —
   the exercise is created but attached to nothing. No student-facing code path
   ever lists bare `Exercise` rows; every student surface reaches exercises through
   `Playlist.exercises` (confirmed: `apps/student/views.py` only does direct
   `Exercise.objects.filter(id=...)` lookups when given an explicit ID, never as a
   browse listing). An exercise saved with no playlist is invisible to normal
   student browsing — reachable only if someone has its direct URL.

## Goals

- Replace the `is_adaptive`/`is_dynamic` flag pair with one explicit field that
  names the actual serving strategy.
- Give adaptive/dynamic playlists an optional hard cap on how many exercises get
  served, so teachers can build a predictably-sized course from the mastery pool.
- Make sure every exercise saved through `/teacher/play/` ends up in at least one
  playlist, so nothing becomes silently unreachable.

## Non-goals

- Not splitting `Playlist` into separate model classes (rejected approach — touches
  ~20 files for a distinction the runtime already mostly collapses into one
  boolean; see brainstorm discussion).
- Not changing `Course` or making it gate availability — confirmed current design
  intentionally keeps Course as a scheduling/due-date overlay only
  (`apps/student/views.py:213` docstring), and that's out of scope here.
- Not turning `unit:N` tags into a real `Unit` model. Noted as a separate possible
  follow-up, not addressed in this spec.
- Not changing the mastery-scoring algorithm itself (`score_exercise`,
  `MASTERY_LEVELS` thresholds) — only when serving stops.

## Design

### 1. `Playlist.selection_mode`

New `CharField` with choices, replacing `is_adaptive` + `is_dynamic` as the source
of truth:

```python
class Playlist(...):
    SELECTION_STATIC_ORDERED = "static_ordered"
    SELECTION_ADAPTIVE_POOL = "adaptive_pool"
    SELECTION_ADAPTIVE_POOL_SCOPED = "adaptive_pool_scoped"
    SELECTION_MODE_CHOICES = (
        (SELECTION_STATIC_ORDERED, "Static ordered list"),
        (SELECTION_ADAPTIVE_POOL, "Adaptive (full exercise pool)"),
        (SELECTION_ADAPTIVE_POOL_SCOPED, "Adaptive (scoped to playlist tags/complexity)"),
    )
    selection_mode = models.CharField(
        max_length=24,
        choices=SELECTION_MODE_CHOICES,
        default=SELECTION_STATIC_ORDERED,
        db_index=True,
    )
```

Mapping from today's flags:

| `is_adaptive` | `is_dynamic` | → `selection_mode` |
|---|---|---|
| False | False | `static_ordered` |
| True | False | `adaptive_pool` |
| any | True | `adaptive_pool_scoped` |

The existing `is_adaptive`/`is_dynamic` `BooleanField`s are **removed** in this
same change (not deferred — see correction below) and replaced with read-only
properties:

```python
@property
def is_adaptive(self):
    return self.selection_mode != self.SELECTION_STATIC_ORDERED

@property
def is_dynamic(self):
    return self.selection_mode == self.SELECTION_ADAPTIVE_POOL_SCOPED
```

**Correction from an earlier draft of this spec:** the first pass of this design
proposed keeping the boolean columns around and adding properties "on top," to be
dropped in a follow-up. That doesn't work — a Django model can't have a real
field and a `@property` share one name, and more importantly, a property has no
setter, so any code constructing a `Playlist` with `is_adaptive=`/`is_dynamic=` as
a keyword argument breaks immediately. A repo-wide check found these flags are
used in three distinct ways, only one of which is safe to leave alone:

1. **Plain attribute reads** (`playlist.is_adaptive`, `getattr(playlist,
   "is_dynamic", False)`) — safe under read-only properties, no changes needed.
   Found in `apps/exercises/mastery.py`, `apps/student/views.py`,
   `apps/student/unit_progress.py`, `lab/views.py` (lines 195, 253, 531-532, 587,
   696).
2. **`ModelForm` field declarations** — `apps/exercises/admin.py:537-538` and
   `apps/exercises/forms.py:1293-1294` list `is_adaptive`/`is_dynamic` as form
   fields, which requires them to be real model fields. These two files are
   updated to use `selection_mode` instead (see UI changes section — this is now
   a required part of this spec, not optional polish).
3. **Constructor/`get_or_create(defaults=...)` keyword arguments** — these break
   outright once the booleans are properties. Every write site is updated to pass
   `selection_mode=` instead, computed inline from whatever `is_adaptive`/
   `is_dynamic` values it used to pass (mapping table above). Full list:
   - `lab/views.py:_append_to_playlist` (the `get_or_create(defaults=...)` block
     already touched in the orphan-exercise fix above — same edit, same place)
   - `apps/teacher/views_musicxml.py:345`
   - `apps/exercises/management/commands/create_smart_playlist.py:32-33`
   - `apps/exercises/management/commands/create_unit_playlist.py:221`
   - `apps/exercises/management/commands/generate_clausulae_b1.py:281`
   - `apps/exercises/management/commands/generate_roman_from_clausulae.py:446-447`
   - `apps/exercises/management/commands/generate_harmonization_from_clausulae.py:291-292`
   - `apps/exercises/management/commands/generate_unit2_barline_exercises.py:132-133,217-218,287-288`
   - `apps/exercises/management/commands/generate_unit2_meter_exercises.py:49-50`
   - `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py:52-53`
   - `apps/exercises/management/commands/generate_unit3_scale_exercises.py:403-404`
   - `apps/exercises/management/commands/generate_unit4.py:295`
   - `apps/exercises/management/commands/generate_unit5.py:180-181`
   - `apps/exercises/management/commands/import_compendium_cadences.py:141-142`

  This is mechanical (every site already says `is_dynamic=False, is_adaptive=True`
  or similar — the mapping table above gives the exact `selection_mode` value for
  every combination that appears), but it's real scope: 14 call sites across 13
  files, not 2.

Serving code (`mastery.py:350`, `apps/student/views.py:1045`) is left reading the
new properties as-is — no logic changes there, only the attribute's backing
storage changes.

### 2. `Playlist.target_length`

```python
target_length = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    help_text="Adaptive/dynamic playlists only: stop serving new exercises once "
               "this many have been served, even if mastery isn't complete. "
               "Leave blank for unbounded (current behavior).",
)
```

Only meaningful when `selection_mode != static_ordered`. `None` preserves today's
endless behavior — this is purely additive, no existing playlist changes behavior
on migration.

**Cap semantics (hard stop):** once `served_count >= target_length`, serving stops
regardless of mastery state. This was chosen over a "soft cap" (keep serving past
the target) and over "stop only on already-unlocked skills" — a hard stop gives
teachers a predictable, schedulable course length, which is the actual goal. Fast
learners may finish without full mastery on a skill or two; that's an accepted
tradeoff favoring predictability.

Three call sites need the cap:

- `apps/student/views.py:1049` — the redirect-to-unit-page guard currently only
  fires `if not is_dynamic_or_adaptive and exercise_num > served_count`. Add:
  `or (playlist.target_length and exercise_num > playlist.target_length)`.
- `apps/student/views.py:1131` — `next_num = resolved_num + 1` for the adaptive
  branch becomes `None` once `resolved_num >= playlist.target_length` (when set).
- `lab/views.py:198` (`generate_exercise_context`'s adaptive branch) — same
  `next_num` capping logic, used for the "next exercise" link generation.

No change needed inside `get_next_exercise` itself (`apps/exercises/mastery.py`) —
it has no concept of "exercise_num" or position, it just returns one candidate per
call. The cap is enforced entirely by the caller refusing to ask for exercise N+1
once N == target_length.

### 3. Orphan-exercise fix

- `lab/templates/play.html:135` — remove the implicit "no playlist" path. The
  `play-save-playlist` select keeps "New playlist..." as an option but the
  `<option value="">None</option>` entry is removed.
- `lab/views.py` — if a save POST arrives with no `playlistId` and no
  `playlistName` (defensive: old clients, API callers bypassing the dropdown),
  `_append_to_playlist` falls back to a per-author "My Drafts" playlist instead of
  returning `None`:

  ```python
  if not playlist_id and not playlist_name:
      playlist, _ = Playlist.objects.get_or_create(
          name="My Drafts",
          authored_by=author,
          defaults={"selection_mode": Playlist.SELECTION_STATIC_ORDERED, "is_public": False},
      )
      # fall through to the existing append logic below
  ```

  Note: when `save_as_official=True`, `author` is the factory user
  (`_resolve_author`), so superusers saving official exercises with no playlist
  picked get a shared "My Drafts" under the factory account, not a personal one.
  That's consistent with how official saves already work for every other field.

### 4. Migration plan

Two Django migrations, both run as part of normal `manage.py migrate` on deploy —
no separate management command or manual backfill step:

**Migration A (schema + data, in order):**
1. Add `selection_mode` (`default="static_ordered"`) and `target_length`
   (`null=True`).
2. `RunPython` data migration, no manual judgment required:

   ```python
   def backfill_selection_mode(apps, schema_editor):
       Playlist = apps.get_model("exercises", "Playlist")
       Playlist.objects.filter(is_dynamic=True).update(
           selection_mode="adaptive_pool_scoped")
       Playlist.objects.filter(is_dynamic=False, is_adaptive=True).update(
           selection_mode="adaptive_pool")
       Playlist.objects.filter(is_dynamic=False, is_adaptive=False).update(
           selection_mode="static_ordered")
   ```

**Migration B (same deploy, after all code call sites are updated):** remove the
`is_adaptive`/`is_dynamic` `BooleanField`s now that `selection_mode` is the source
of truth and every write site (listed above) uses it instead. Both migrations ship
in the same PR/deploy — there's no reason to split them across releases once every
call site is already converted; the only reason to keep them as two migrations
(rather than one) is so the data backfill in A runs against a database that still
has the old boolean columns to read from.

`target_length` needs no backfill; it defaults to `NULL` for every existing row,
which preserves current (endless) behavior exactly.

Local DB counts for scale (informational, not a target for any other environment):
147 playlists total, 58 `is_adaptive=True`, 0 `is_dynamic=True`, 89 neither.

## UI changes

`apps/exercises/forms.py:1293-1298` and `apps/exercises/admin.py:537-543` currently
expose `is_dynamic`, `is_adaptive`, `min_complexity`, `max_complexity` as separate
form fields. These become a single `selection_mode` choice field plus
`target_length` (shown/enabled only when `selection_mode != static_ordered`).
`min_complexity`/`max_complexity` stay as-is, scoped to `adaptive_pool_scoped` only
(matches current `mastery.py:368` usage).

`/teacher/play/` Save dialog: `play-save-playlist` select drops the "None" option
(see Orphan-exercise fix above). No other `/teacher/play/` UI changes — this spec
doesn't touch playlist *creation* UI from that surface, only the "must pick or
default" requirement.

## Testing plan

- Migration test: create playlists with each of the 4 flag combinations
  (`is_adaptive`/`is_dynamic` × True/False), run the data migration, assert
  resulting `selection_mode` matches the mapping table above.
- `is_adaptive`/`is_dynamic` property tests: assert the derived properties return
  correct values for all 3 `selection_mode` values.
- Run the full management-command test suite (and any smoke-run of the 13 files
  listed in the constructor-kwarg call-site list above, for commands without
  dedicated tests) after converting their `is_adaptive=`/`is_dynamic=` kwargs to
  `selection_mode=`, to catch any missed call site via `TypeError` at minimum.
- `target_length` capping: extend existing adaptive-serving tests (wherever
  `apps/student/views.py`'s player view or `get_next_exercise` is tested today) to
  cover: `target_length=None` behaves identically to today; `target_length=5`
  stops `next_num` at 5 and redirects past it regardless of mastery state.
- Orphan-exercise fix: extend
  `lab/tests/test_add_exercise_view_metadata_db.py` with a test posting no
  `playlistId`/`playlistName` and asserting the exercise lands in an
  auto-created "My Drafts" playlist instead of no playlist at all. Cover both
  the personal-author and `saveAsOfficial=True` (factory-author) paths.
- Manual: confirm `/teacher/play/` Save dialog no longer offers "None" as a
  playlist target.

## Open questions

- `min_complexity`/`max_complexity` are currently always present on every
  `Playlist` (defaults 1/10) even for `static_ordered` mode where they're unused.
  This spec leaves them as-is (no model cleanup) since they're harmless dead
  weight for static playlists and removing them is out of scope.
