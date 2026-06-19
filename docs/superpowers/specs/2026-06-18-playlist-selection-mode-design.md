# Playlist selection_mode + target_length + orphan-exercise fix

*Revised after Codex review — see "Revision history" at the end for what changed
and why. The scope grew significantly: target_length exposed pre-existing
adaptive-serving bugs (slot-1 navigation pinning, three call sites with zero
adaptive awareness, one of which can 400 on score submission) that have to be
fixed for target_length to work correctly, not just bolted around.*

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
   `Playlist.exercises`. An exercise saved with no playlist is invisible to normal
   student browsing — reachable only if someone has its direct URL.

4. **(Found while designing #2) Adaptive serving has pre-existing correctness gaps
   that target_length would make worse.** Three things, all verified against
   current code:
   - `get_adaptive_exercise_for_view` (`lab/views.py:163`) never passes
     `exercise_num` to `get_next_exercise`, even though `get_next_exercise` uses it
     for navigation pinning and RNG seeding. Every adaptive request resolves
     internally as if it were slot 1. Pinning and anti-repeat logic are silently
     broken for every slot beyond the first, today, independent of this spec.
   - Three call sites resolve "what exercise is at this slot" with **zero**
     adaptive/dynamic awareness — `PlayerDefinitionView`
     (`apps/student/views.py:1227`), `_submit_exercise_performance`
     (`apps/exercises/views.py:186`), and `identification_answers_view`
     (`apps/exercises/views.py:254`). All three call `get_served_exercise_id`
     unconditionally, which only resolves against `ExercisePlaylistOrdered`-linked
     rows. For an adaptive/dynamic playlist this is a coincidence-dependent
     ceiling, not a real "served count" — locally, `PA00AZ` ("Unit 1 - Identify
     the Notes (Bass)", `is_adaptive=True`) has 36 manually-linked rows and a
     sampled student's actual usage only reached 8, which is why this hasn't
     visibly broken yet. A `target_length` set higher than a playlist's linked
     row count would make `_submit_exercise_performance` return
     `400 "Invalid exercise number"` on score submission — a hard error, not a
     display glitch. `PlayerView` (`apps/student/views.py:1019`) already branches
     correctly for this; the other three don't.
   - `_build_completion_response` (`apps/exercises/views.py:36`) computes
     `next_exercise_url` and `total_exercises` from `playlist.next_num()` /
     `playlist.exercise_count` unconditionally — same blindness, used after every
     exercise submission regardless of playlist type.

## Goals

- Replace the `is_adaptive`/`is_dynamic` flag pair with one explicit field that
  names the actual serving strategy.
- Give adaptive/dynamic playlists an optional hard cap on how many exercises get
  served, so teachers can build a predictably-sized course from the mastery pool —
  and make that cap actually safe to set, by fixing the adaptive-serving gaps in
  problem #4 first.
- Make sure every exercise saved through `/teacher/play/` (including via MusicXML
  import) ends up in at least one playlist, so nothing becomes silently
  unreachable.

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
  `MASTERY_LEVELS` thresholds) — only when serving stops and which exercise a
  given slot number resolves to.
- Not touching `get_ordered_exercise_ids_for_serving`'s static-playlist behavior,
  including the Unit-4-personalized-shuffle special case (truncates served count
  below `exercise_count` for one specific playlist type,
  `player_progression.py:46-59`). All new logic in this spec is gated to
  `selection_mode != static_ordered`; static playlists keep their exact current
  code paths untouched.

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
same change and replaced with read-only properties:

```python
@property
def is_adaptive(self):
    return self.selection_mode != self.SELECTION_STATIC_ORDERED

@property
def is_dynamic(self):
    return self.selection_mode == self.SELECTION_ADAPTIVE_POOL_SCOPED
```

**Full write-site audit** (revised — the first draft of this spec only grepped
constructor kwargs and missed direct attribute assignment, which a read-only
property can't support at all). Three usage patterns found, two of which need
code changes:

1. **Plain attribute reads** (`playlist.is_adaptive`, `getattr(playlist,
   "is_dynamic", False)`) — safe under read-only properties, no changes needed.
   `apps/exercises/mastery.py`, `apps/student/views.py`,
   `apps/student/unit_progress.py`, `lab/views.py` (lines 195, 253, 531-532, 587,
   696).
2. **`ModelForm` field declarations** — `apps/exercises/admin.py:537-538` and
   `apps/exercises/forms.py:1293-1294` list `is_adaptive`/`is_dynamic` as form
   fields, which requires real model fields. Updated to use `selection_mode`
   instead (see UI changes section).
3. **Writes — constructor kwargs AND direct attribute assignment.** Both forms
   break outright once the booleans are read-only properties (assignment raises
   `AttributeError: can't set attribute`; constructor kwargs raise `TypeError`).
   Every site converts to setting `selection_mode=`/`playlist.selection_mode = `
   directly, computed from the mapping table above. Full list, by file:

   - `lab/views.py:_append_to_playlist` — `get_or_create(defaults=...)` kwarg
     (same block already touched by the orphan-exercise fix below).
   - `apps/teacher/views_musicxml.py:345` — `get_or_create(defaults=...)` kwarg.
   - `apps/exercises/management/commands/create_unit_playlist.py` — kwarg at
     line 221 **and** direct assignment at lines 225-226 (`if not created:`
     branch).
   - `apps/exercises/management/commands/generate_unit2_barline_exercises.py` —
     kwargs at lines 132-133, 217-218, 287-288 **and** matching direct
     assignments at lines 139-140, 223-224, 293-294 (three separate
     `get_or_create` + `if not created:` pairs in this file).
   - `apps/exercises/management/commands/generate_unit2_meter_exercises.py` —
     kwarg at lines 49-50 **and** direct assignment at lines 63-64.
   - `apps/exercises/management/commands/generate_unit4.py` — kwarg at line 295
     **and** direct assignment at lines 301-302.
   - `apps/exercises/management/commands/create_smart_playlist.py:32-33` — kwarg
     only.
   - `apps/exercises/management/commands/generate_clausulae_b1.py:281` — kwarg
     only.
   - `apps/exercises/management/commands/generate_roman_from_clausulae.py:446-447`
     — kwarg only.
   - `apps/exercises/management/commands/generate_harmonization_from_clausulae.py:291-292`
     — kwarg only.
   - `apps/exercises/management/commands/generate_unit3_key_sig_exercises.py:52-53`
     — kwarg only.
   - `apps/exercises/management/commands/generate_unit3_scale_exercises.py:403-404`
     — kwarg only.
   - `apps/exercises/management/commands/generate_unit5.py:180-181` — kwarg only.
   - `apps/exercises/management/commands/import_compendium_cadences.py:141-142` —
     kwarg only.
   - `apps/exercises/tests/test_generate_exercise_context.py` — direct
     assignment in test setup at lines 74-75, 276-277, 347-348 (not a
     constructor kwarg; missed entirely by the first audit pass). Update to set
     `pl.selection_mode = Playlist.SELECTION_STATIC_ORDERED`.

   25 kwarg/assignment blocks across 15 files total (`generate_unit2_barline_exercises.py`
   alone has 3 `get_or_create`+`if not created:` pairs = 6 blocks;
   `test_generate_exercise_context.py` has 3 separate assignment pairs).

Serving code (`mastery.py:350`, `apps/student/views.py:1045`) is left reading the
new properties as-is — no logic changes there, only the attribute's backing
storage changes.

### 2. `Playlist.target_length`

```python
target_length = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    validators=[MinValueValidator(1)],
    help_text="Adaptive/dynamic playlists only: stop serving new exercises once "
               "this many have been served, even if mastery isn't complete. "
               "Leave blank for unbounded (current behavior).",
)
```

`MinValueValidator(1)` added because `PositiveSmallIntegerField` permits `0`
despite the name, and truthiness checks elsewhere (`if playlist.target_length:`)
would treat `0` as "uncapped" — silently wrong if a teacher (or a buggy script)
ever sets it to `0`. Validated at the model/form level, not the DB level (no DB
constraint added — consistent with how `min_complexity`/`max_complexity` are
validated today).

**Cap semantics (hard stop):** once a student would be served exercise number
`target_length + 1`, serving stops regardless of mastery state. Fast learners may
finish without full mastery on a skill or two; that's an accepted tradeoff
favoring predictable course length over completionism. `target_length=None`
preserves today's endless behavior exactly — purely additive, no existing
playlist's behavior changes on migration.

This section originally listed three call sites that needed the cap. That's now
folded into Section 5 below, because making the cap *safe* to ship required fixing
adaptive-serving gaps that touch more call sites than just "where does next_num
get computed" — see Section 5 for the complete, corrected list.

### 3. Orphan-exercise fix

**Both save paths, not just `/exercises/add/`:**

- `lab/templates/play.html:135` — remove the `<option value="">None</option>`
  entry from the `play-save-playlist` select.
- `lab/static/js/src/components/ui/music_controls.js:560` — `_loadAuthoringMeta()`
  rebuilds the playlist `<select>` from scratch on every load
  (`playlistSelect.html('<option value="">None</option>')`), silently
  reinserting "None" regardless of the template change above. This line is
  changed to omit the "None" option (`playlistSelect.html('<option value="__new__">New playlist...</option>')`
  as the only initial entry, before the fetched playlist list is appended).
- `lab/views.py` — `_append_to_playlist`: when neither `playlist_id` nor
  `playlist_name` is given, fall through into the *existing* `else` branch
  (which already does `Playlist.objects.get_or_create(name=playlist_name, ...)`)
  by setting `playlist_name = "My Drafts"` first, rather than writing a second,
  separate `get_or_create` call:

  ```python
  def _append_to_playlist(self, *, exercise, author, playlist_id=None,
                           playlist_name=None, is_public=False, is_adaptive=False,
                           is_official=False, skill_tags=None):
      if not playlist_id and not playlist_name:
          playlist_name = "My Drafts"
      if playlist_id:
          ...
      else:
          playlist, created = Playlist.objects.get_or_create(
              name=playlist_name,
              authored_by=author,
              defaults={..., "selection_mode": Playlist.SELECTION_STATIC_ORDERED},
          )
          ...
  ```

  (An earlier draft of this spec wrote a separate `get_or_create` call inside the
  new branch with a comment saying "fall through to the existing append logic" —
  that doesn't work, since the pre-existing `else` branch would still run
  afterward with `playlist_name` still `None`, calling `get_or_create(name=None,
  ...)`. Reassigning `playlist_name` before the existing branch runs is the
  actual fix.)

- `apps/teacher/views_musicxml.py:333` — this view has its **own**, independent
  playlist-linking block (`if playlist_id or playlist_name: ... else: (orphan)`),
  not shared with `lab/views.py:_append_to_playlist`. Same fallback applied here:
  if neither is given, set `playlist_name = "My Drafts"` before the existing
  `get_or_create` call, mirroring the fix above.

  Note: when `save_as_official=True`, `author` is the factory user in both
  views, so superusers saving official exercises with no playlist picked get a
  shared "My Drafts" under the factory account, not a personal one — consistent
  with how official saves already work for every other field.

### 4. Migration plan

Two Django migrations, both run as part of normal `manage.py migrate` on deploy —
no separate management command or manual backfill step:

**Migration A (schema + data, in order):**
1. Add `selection_mode` (`default="static_ordered"`) and `target_length`
   (`null=True`, with `MinValueValidator(1)`).
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
of truth and every write site (Section 1's list) uses it instead. Both migrations
ship in the same PR/deploy; they're split into two only so the data backfill in A
runs against a database that still has the old boolean columns to read from.

`target_length` needs no backfill; it defaults to `NULL` for every existing row,
which preserves current (endless) behavior exactly.

Local DB counts for scale (informational, not a target for any other environment):
147 playlists total, 58 `is_adaptive=True`, 0 `is_dynamic=True`, 89 neither.

### 5. Adaptive serving/submission correctness (prerequisite to target_length)

This section exists because target_length can't be safely shipped without it —
see Problem #4. All changes here are gated to `selection_mode != static_ordered`;
static-playlist code paths are untouched.

**5a. Fix slot threading in `get_adaptive_exercise_for_view`.**
`lab/views.py:163` currently calls:

```python
exercise_obj, target_key = get_next_exercise(
    request.user.id, playlist=playlist, course=course_obj, seed=seed
)
```

`get_next_exercise`'s signature is `(user, playlist=None, course=None,
exercise_num=1, seed=None)` — `exercise_num` is never passed, so every call
defaults to `1` internally, breaking navigation pinning (`perf.data[exercise_num
- 1]` always checks slot 1) and anti-repeat logic for every slot beyond the
first. Fix: pass `exercise_num=exercise_num` through. One-line fix, but it's the
thing that makes "served exercise N" a coherent, stable concept at all — without
it, "stop after target_length exercises" is capping a sequence that isn't
reliably sequential to begin with.

**5b. Make three blind call sites adaptive-aware**, mirroring the pattern
`PlayerView` (`apps/student/views.py:1019`) already uses correctly today
(`if playlist.is_dynamic or playlist.is_adaptive: <adaptive path> else: <static
path>`):

- `PlayerDefinitionView.get` (`apps/student/views.py:1227`) — currently calls
  `get_ordered_exercise_ids_for_serving`/`get_served_exercise_id`
  unconditionally. `course = resolve_course_for_playlist(request.user,
  playlist)` is already computed at line 1249 — reuse it. Add the same
  conditional `PlayerView` already has.
- `_submit_exercise_performance` (`apps/exercises/views.py:186`) — currently
  calls `get_served_exercise_id` unconditionally at line 207. `data_course_id`
  is already available from the POST payload; resolve a `Course` object from it
  (the function currently only keeps `course_id = Course.objects.get(...)._id`,
  not the object — needs a small adjustment to also keep the `Course` instance
  for the adaptive branch). When adaptive, resolve via
  `get_adaptive_exercise_for_view(request, playlist_obj, int(data_exercise_num),
  course.id if course else None)` instead, and use the resolved exercise's `id`
  for scoring/`PerformanceData.submit`.
- `identification_answers_view` (`apps/exercises/views.py:254`) — same fix;
  `course` is already resolved as an object at line 262, directly usable.

  **Transposition interaction, verified:** `get_adaptive_exercise_for_view`
  applies transposition (`target_key`/`transpose_exercise`) before returning,
  but `apps/exercises/utils/transpose.py:transpose()` does `exercise =
  deepcopy(exercise)` and only mutates the copy's `.data` — `.id` is untouched,
  no new DB row is created. So `get_adaptive_exercise_for_view(...).id` is
  always the canonical base exercise id regardless of whether transposition was
  applied, identical to what `get_served_exercise_id` would have returned for
  the static path. Safe to use directly for `PerformanceData`/mastery scoring at
  the two new call sites — no special-casing needed.

**5c. Add `Playlist` model helpers for adaptive-only "effective length":**

```python
def effective_length(self):
    """Adaptive/dynamic playlists only. None = unbounded (today's behavior)."""
    if self.selection_mode == self.SELECTION_STATIC_ORDERED:
        return None  # callers must use served_count/exercise_count for static
    return self.target_length

def effective_next_num(self, current_num):
    """Adaptive/dynamic playlists only. None = no next exercise (capped)."""
    total = self.effective_length()
    if total is None:
        return current_num + 1
    return current_num + 1 if current_num < total else None
```

These are deliberately *not* used for static playlists, to avoid disturbing the
Unit-4-personalized-shuffle special case (see Non-goals) — static playlists keep
using `served_count`/`playlist.exercise_count`/`playlist.next_num()` exactly as
today.

**5d. Apply the cap consistently, using the 5c helpers, everywhere an adaptive
"is there a next exercise" / "what's the total" question is answered:**

- `apps/student/views.py:1049` — add `or (is_dynamic_or_adaptive and
  playlist.effective_length() and exercise_num > playlist.effective_length())`
  to the existing redirect guard.
- `apps/student/views.py:1131` — adaptive branch's `next_num = resolved_num + 1`
  becomes `playlist.effective_next_num(resolved_num)`.
- `lab/views.py:198` (`generate_exercise_context`'s adaptive branch) — same
  `effective_next_num` substitution.
- `apps/exercises/views.py:70,99` (`_build_completion_response`) — currently has
  **no** adaptive branch at all (Problem #4). Add one: when
  `playlist.selection_mode != static_ordered`, compute `next_num` via
  `playlist.effective_next_num(int(exercise_num))` and `total_exercises` via
  `playlist.effective_length()` (which may be `None` — the response should omit
  or null out `total_exercises` for unbounded adaptive playlists rather than
  reporting a misleading static count). Static playlists keep using
  `playlist.next_num()`/`playlist.exercise_count` exactly as today.
- `PlayerDefinitionView` (new adaptive branch from 5b) — same `effective_*`
  helpers for its redirect/total logic.

## UI changes

`apps/exercises/forms.py:1293-1298` and `apps/exercises/admin.py:537-543` currently
expose `is_dynamic`, `is_adaptive`, `min_complexity`, `max_complexity` as separate
form fields. These become a single `selection_mode` choice field plus
`target_length` (shown/enabled only when `selection_mode != static_ordered`).
`min_complexity`/`max_complexity` stay as-is, scoped to `adaptive_pool_scoped` only
(matches current `mastery.py:368` usage).

`/teacher/play/` Save dialog: `play-save-playlist` select drops the "None" option
in both the template and the JS that rebuilds it (see Orphan-exercise fix above).
No other `/teacher/play/` UI changes.

## Testing plan

- Migration test: create playlists with each of the 4 flag combinations
  (`is_adaptive`/`is_dynamic` × True/False), run the data migration, assert
  resulting `selection_mode` matches the mapping table above.
- `is_adaptive`/`is_dynamic` property tests: assert the derived properties return
  correct values for all 3 `selection_mode` values.
- `target_length` validation: assert `target_length=0` is rejected
  (`MinValueValidator(1)`), `target_length=None` is accepted.
- Run the full management-command test suite, plus a smoke-run of any of the 15
  files in Section 1's write-site list that lack dedicated tests, after
  converting their kwargs/assignments to `selection_mode=` — catches any missed
  call site via `AttributeError`/`TypeError` at minimum.
- Slot-stability regression test (covers 5a): for an adaptive playlist, request
  the same `exercise_num` twice for the same user and assert the same exercise
  is returned both times (navigation pinning working); request two different
  `exercise_num` values and assert they can differ (not all collapsing to slot
  1's selection).
- Adaptive submission test (covers 5b): for an adaptive/dynamic playlist with
  fewer `ExercisePlaylistOrdered`-linked rows than a configured `target_length`,
  submit a score for an exercise_num beyond the linked-row count and assert it
  succeeds (no `400 "Invalid exercise number"`) — this is the regression test
  for the landmine found in Problem #4.
- `target_length` capping end-to-end (covers 5c/5d): `target_length=None` behaves
  identically to today across all four call sites in 5d; `target_length=5` stops
  `next_num`/`effective_next_num` at 5 and redirects/responds accordingly past
  it, regardless of mastery state, in `PlayerView`, `PlayerDefinitionView`, and
  `_build_completion_response`.
- Orphan-exercise fix: extend `lab/tests/test_add_exercise_view_metadata_db.py`
  with a test posting no `playlistId`/`playlistName` and asserting the exercise
  lands in an auto-created "My Drafts" playlist instead of no playlist at all.
  Cover both the personal-author and `saveAsOfficial=True` (factory-author)
  paths. Add an equivalent test for `apps/teacher/views_musicxml.py`'s save
  endpoint.
- Manual: confirm `/teacher/play/` Save dialog no longer offers "None" as a
  playlist target, including after a page reload (verifies the JS fix, not just
  the template fix).

## Open questions

- `min_complexity`/`max_complexity` are currently always present on every
  `Playlist` (defaults 1/10) even for `static_ordered` mode where they're unused.
  This spec leaves them as-is (no model cleanup) since they're harmless dead
  weight for static playlists and removing them is out of scope.

## Revision history

**Original draft → this revision**, after external (Codex) review caught:
incomplete write-site audit (missed direct attribute assignment, not just
constructor kwargs, across 4 management commands and a test file); orphan-fix
only covering `/exercises/add/`, missing the MusicXML save path and the JS that
resets the playlist dropdown on every load; a factually wrong claim that
`get_next_exercise` has no position concept (it does — the bug is the caller not
passing it); and cap enforcement only patching 3 of what turned out to be ~6 call
sites, one of which (`_submit_exercise_performance`) can return a hard 400 error
on score submission rather than just a display glitch. All six points were
verified against the running code before this revision (see git history of this
file / PR discussion for the verification trail), not taken on faith. Section 5
(Adaptive serving/submission correctness) is new in this revision — the original
draft incorrectly claimed `get_next_exercise` "has no concept of exercise_num or
position."
