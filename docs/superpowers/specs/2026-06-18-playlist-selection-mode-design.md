# Playlist selection_mode + target_length + orphan-exercise fix

> [!NOTE]
> **Superseded in part on 2026-06-19.** Do not implement the
> `selection_mode`, `target_length`, or adaptive-serving design from this
> document as the long-term assignment architecture. Those portions are
> replaced by
> [2026-06-19-individualized-assignment-recipes-design.md](2026-06-19-individualized-assignment-recipes-design.md),
> which uses bounded assignment sections and immutable student slots. The
> orphan-exercise findings remain valid independent work.

*Revised twice after Codex review — see "Revision history" at the end for what
changed and why each round. target_length kept exposing more pre-existing
adaptive-serving bugs as the audit got more thorough: slot-1 navigation pinning,
six call sites with zero adaptive awareness (one can 400 on score submission,
two had no pre-resolution guard at all so direct URLs could bypass the cap
entirely), and a course-blind PerformanceData lookup that can crash with
MultipleObjectsReturned. All confirmed by reading the running code, not taken on
faith — including pushing back on one claim (`ExerciseView`) that didn't hold
up under verification.*

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
   - `apps/exercises/tests/test_adaptive_serving.py` — constructor kwargs at
     lines 53 (`Playlist(...)` + `.save()`) and 192
     (`Playlist.objects.create(...)`), both `is_adaptive=True`. Missed by the
     first audit pass because it was excluded from the original grep (which
     skipped files matching `test`). Update both to
     `selection_mode=Playlist.SELECTION_ADAPTIVE_POOL`.
   - `scratch/batch_import_unit9.py:47-48` and
     `scratch/batch_harmonization_qa.py:136-137` — both `is_dynamic=False,
     is_adaptive=False` constructor/`get_or_create` kwargs. Explicit decision:
     **migrate both**, not declare unsupported. `batch_harmonization_qa.py` is
     a documented, intentionally re-runnable pipeline (per project memory:
     "re-runnable pipeline: import roman sources → derive harmonization →
     bundle in playlist"), not throwaway scratch code despite its directory.
     `batch_import_unit9.py` is described in `CLAUDE.md` as a superseded
     one-off, but the fix is two lines either way — leaving it broken to crash
     on next use costs more than fixing it now.

   29 kwarg/assignment blocks across 18 files total (`generate_unit2_barline_exercises.py`
   alone has 3 `get_or_create`+`if not created:` pairs = 6 blocks;
   `test_generate_exercise_context.py` and `test_adaptive_serving.py` each
   have multiple separate assignment/kwarg pairs).

   **Read-only — verified safe, no code change, but must still pass after the
   write-site conversion above** (these assert `playlist.is_adaptive`/
   `is_dynamic` via plain attribute reads on objects created by code this spec
   *does* change, so they're the closest thing to existing regression coverage
   for several write sites): `apps/exercises/tests/test_create_unit_playlist.py:130-131`,
   `apps/exercises/tests/test_play_save_chordal_umto.py:230`,
   `apps/teacher/tests/test_musicxml_import_views.py:263` (line 254's
   `"is_adaptive": "true"` is an HTTP POST field name, a separate wire-contract
   concern from the Python model field — not renamed by this spec),
   `apps/exercises/tests/test_generate_unit2_barline_exercises.py:200` (line
   204's `is_adaptive_entry` is an unrelated field on `ExercisePlaylistOrdered`,
   not `Playlist.is_adaptive` — verified as a false-positive grep match, not a
   write site).

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

**5b. Fix `get_next_exercise`'s navigation pinning — it's broken for the exact
mode this spec cares most about, and has a separate crash risk.** Verified two
distinct bugs in the pinning check (`apps/exercises/mastery.py:284-296`), on top
of the slot-threading bug in 5a:

1. **Pinning validity requires `ExercisePlaylistOrdered` linkage**
   (`ExercisePlaylistOrdered.objects.filter(playlist=playlist,
   exercise=pinned_ex).exists()`), but `adaptive_pool_scoped` mode deliberately
   selects from the *global* Exercise pool via `skill_tags__overlap`
   (`mastery.py:354`), not from manually-linked rows. A pinned exercise from a
   scoped pool will almost always fail this check, fall through to "fresh
   selection" every time, and re-roll the RNG — meaning the one mode this spec
   is actually meant to make useful (`adaptive_pool_scoped`, the "Smart
   Assignment" case) has its pinning silently disabled today. Fix: the validity
   check becomes selection-mode-aware — for `adaptive_pool_scoped`, validate
   against the same pool criteria used for selection (skill_tags overlap +
   complexity range) instead of literal `ExercisePlaylistOrdered` membership;
   for `adaptive_pool` (unscoped), any existing `Exercise` row is valid, matching
   today's de facto behavior for that mode.
2. **The `PerformanceData` lookup ignores `course` entirely**
   (`PerformanceData.objects.get(user=user_obj, playlist=playlist)`), despite
   `PerformanceData.Meta.unique_together = (("user", "playlist", "course"))`
   (`apps/exercises/models.py:1363`). A student who's accessed the same playlist
   through two different courses (or once via a course and once with no course)
   can have multiple `PerformanceData` rows for one `(user, playlist)` pair —
   this `.get()` would raise `MultipleObjectsReturned`, a crash, not just wrong
   data. Fix: thread `course` through `get_next_exercise`'s call chain and filter
   the lookup by it (`PerformanceData.objects.filter(user=user_obj,
   playlist=playlist, course=course).first()`, switching from `.get()` to
   `.filter().first()` defensively).

**5c. Keep server-side resolution as the source of truth; don't switch to
trusting a client-sent exercise ID.** `lab/views.py:204`'s existing comment is
explicit and deliberate: *"the accuracy of this database write depends on the
playlist not having changed since the call of compileExerciseReport"* — i.e. the
codebase already chose server-side re-derivation over client-supplied identity,
almost certainly to prevent a student's client from claiming credit for an
exercise it wasn't actually served (an anti-cheat boundary, not an oversight).
Switching to "client sends the ID, server validates it" would be a larger,
separate architecture change to that boundary, and isn't necessary to fix the
two confirmed bugs above — 5a (slot threading) and 5b (pinning correctness) make
server-side re-derivation reliable without needing to trust the client. Once
both are fixed, re-running the selector at submission time reproduces the
GET-rendered exercise via the same deterministic seed for the first visit to a
slot, and via the (now-fixed) pinning check for any repeat visit — which is the
existing design's own mechanism for exactly this stability problem, just
currently broken. Noted as a considered alternative, not adopted, to keep this
change scoped to fixing confirmed bugs rather than redesigning an
intentional security boundary.

**5d. Make three blind call sites adaptive-aware**, mirroring the pattern
`PlayerView` (`apps/student/views.py:1019`) already uses correctly today
(`if playlist.is_dynamic or playlist.is_adaptive: <adaptive path> else: <static
path>`):

- `PlayerDefinitionView.get` (`apps/student/views.py:1227`) — currently calls
  `get_ordered_exercise_ids_for_serving`/`get_served_exercise_id`
  unconditionally, **with no pre-resolution guard for adaptive playlists at
  all** (its `exercise_num > served_count` check at line 1252 only meaningfully
  bounds static playlists — `served_count` for adaptive is the same
  linked-row-count landmine from Problem #4). `course =
  resolve_course_for_playlist(request.user, playlist)` is already computed at
  line 1249 — reuse it. Add the same conditional `PlayerView` already has,
  *and* an explicit pre-resolution cap check (see 5f) — this view would
  otherwise happily resolve and serve exercise 999 of a 5-exercise-capped
  playlist if requested by direct URL.
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

**Checked and excluded:** `lab/views.py:ExerciseView` (line 760) does **not**
need adaptive-cap handling — verified it takes a bare `exercise_id` with no
`playlist`/`exercise_num` concept at all, and calls
`generate_exercise_context(None, exercise, request.user)` with `playlist=None`,
which routes to an entirely separate "browse my own exercises by id" code path,
unrelated to playlist serving or capping.

**5e. Add `Playlist` model helpers for adaptive-only "effective length":**

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

**5f. Apply the cap consistently, using the 5e helpers, everywhere an adaptive
"is there a next exercise" / "what's the total" question is answered or a
navigable link is generated.** This list grew twice during review — found by
tracing every reader of `served_count`/`exercise_count`/"total" tied to a
playlist, not just the navigation call sites named in the first pass:

- `apps/student/views.py:1049` — add `or (is_dynamic_or_adaptive and
  playlist.effective_length() and exercise_num > playlist.effective_length())`
  to the existing redirect guard.
- `apps/student/views.py:1088` and `:1275` — both assign
  `exercise_context["totalExercises"] = served_count`, where `served_count` is
  the linked-row count (meaningless for adaptive, per Problem #4). For adaptive
  playlists, use `playlist.effective_length()` instead (may be `None` for
  unbounded — frontend should treat `None` as "no total to show," not `0`).
- `apps/student/views.py:1131` — adaptive branch's `next_num = resolved_num + 1`
  becomes `playlist.effective_next_num(resolved_num)`.
- `apps/student/views.py:1227` (`PlayerDefinitionView`, new in 5d) — needs both
  a pre-resolution guard (`if playlist.effective_length() and exercise_num >
  playlist.effective_length(): <redirect/404>`, checked *before* calling
  `get_adaptive_exercise_for_view`, not just an adjusted `next_num` afterward —
  otherwise a direct URL past the cap still resolves and serves an exercise)
  and the same `effective_*` helpers for its redirect/total logic.
- `lab/views.py:198` (`generate_exercise_context`'s adaptive branch) — same
  `effective_next_num` substitution for `next_num`.
- `lab/views.py:257` (`exercise_list` "dots" navigation, used by the legacy
  `PlaylistView` template) — currently builds
  `range(max(1, exercise_num - 2), exercise_num + 3)` unconditionally, always
  showing 2 slots past the current one regardless of any cap. Clip the upper
  bound to `min(exercise_num + 3, playlist.effective_length() + 1)` when
  `effective_length()` is set, so the dots list never renders a clickable link
  past `target_length`.
- `lab/views.py:552` (`PlaylistView.get`) — like `PlayerDefinitionView`, has
  **no** pre-resolution guard for adaptive mode before calling
  `get_adaptive_exercise_for_view` (line 588). Add the same explicit
  `effective_length()` check before resolution, not just relying on
  `generate_exercise_context`'s `next_num` adjustment downstream — a direct URL
  to this legacy route past the cap would otherwise still serve an exercise.
- `apps/exercises/views.py:70,99` (`_build_completion_response`) — currently has
  **no** adaptive branch at all (Problem #4). Add one: when
  `playlist.selection_mode != static_ordered`, compute `next_num` via
  `playlist.effective_next_num(int(exercise_num))` and `total_exercises` via
  `playlist.effective_length()` (which may be `None` — the response should omit
  or null out `total_exercises` for unbounded adaptive playlists rather than
  reporting a misleading static count). Static playlists keep using
  `playlist.next_num()`/`playlist.exercise_count` exactly as today.
- `apps/student/unit_progress.py:285-286` (`_playlist_stats`) — `"total":
  len(served_ids)` and `"is_adaptive": bool(playlist.is_adaptive)` feed
  `apps/student/templates/student/unit_progress.html:87-114`, which currently
  forces the progress bar to a hardcoded `0%`/no-fraction display whenever
  `is_adaptive` is true (a deliberate workaround for adaptive having no real
  total today). Once `target_length` exists, this is stale: when
  `playlist.effective_length()` is set, `_playlist_stats` should report it as
  `"total"` (a real, finite number) so the progress bar shows an actual
  `done/total` fraction instead of the indeterminate display; the template's
  `is_adaptive` branch becomes `is_adaptive and total is None` (or an
  equivalent explicit "unbounded" flag) so capped adaptive playlists render
  like static ones, and only genuinely unbounded ones keep the indeterminate
  bar.

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
- Run the full management-command test suite, plus a smoke-run of any of the 18
  files in Section 1's write-site list that lack dedicated tests, after
  converting their kwargs/assignments to `selection_mode=` — catches any missed
  call site via `AttributeError`/`TypeError` at minimum. Explicitly confirm the
  4 read-only tests named in Section 1 still pass unmodified
  (`test_create_unit_playlist.py`, `test_play_save_chordal_umto.py`,
  `test_musicxml_import_views.py`, `test_generate_unit2_barline_exercises.py`).
- Slot-stability regression test (covers 5a): for an adaptive playlist, request
  the same `exercise_num` twice for the same user and assert the same exercise
  is returned both times (navigation pinning working); request two different
  `exercise_num` values and assert they can differ (not all collapsing to slot
  1's selection).
- Pinning correctness test (covers 5b): for an `adaptive_pool_scoped` playlist,
  request the same `exercise_num` twice and assert the same exercise is
  returned both times (pinning surviving the "not linked via
  ExercisePlaylistOrdered" case); create two `PerformanceData` rows for the
  same `(user, playlist)` under two different courses and assert
  `get_next_exercise` doesn't raise `MultipleObjectsReturned`.
- Adaptive submission test (covers 5d): for an adaptive/dynamic playlist with
  fewer `ExercisePlaylistOrdered`-linked rows than a configured `target_length`,
  submit a score for an exercise_num beyond the linked-row count and assert it
  succeeds (no `400 "Invalid exercise number"`) — this is the regression test
  for the landmine found in Problem #4.
- `target_length` capping end-to-end (covers 5e/5f): `target_length=None`
  behaves identically to today across every call site in 5f;
  `target_length=5` stops `next_num`/`effective_next_num` at 5 and
  redirects/responds/omits-dots-links accordingly past it, regardless of
  mastery state, in `PlayerView`, `PlayerDefinitionView`, legacy `PlaylistView`
  (including the pre-resolution guard — a direct URL to exercise_num=999 on a
  5-capped playlist must 404/redirect, not serve an exercise), the "dots"
  navigation list, `_build_completion_response`, and the unit-progress summary
  (`_playlist_stats`/`unit_progress.html` showing a real fraction instead of
  the indeterminate bar once capped).
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

**Second revision**, after a follow-up Codex review of the first revision caught
three more things, all verified before this revision:

1. Section 5a's slot-threading fix alone didn't make adaptive slots stable —
   `get_next_exercise`'s pinning check also requires `ExercisePlaylistOrdered`
   linkage (which `adaptive_pool_scoped` deliberately doesn't use, since it
   pulls from the global pool) and ignores `course` despite
   `PerformanceData`'s `(user, playlist, course)` uniqueness constraint (a
   `MultipleObjectsReturned` crash risk, not just a correctness gap, confirmed
   by reading the model's `Meta.unique_together`). Added 5b (pinning fix) and
   5c (an explicit decision to keep server-side resolution rather than adopt
   Codex's alternative suggestion of trusting a client-sent exercise id — the
   existing code has a deliberate anti-cheat comment explaining why it
   re-derives server-side; fixing pinning correctness achieves the same
   stability goal without touching that boundary).
2. The cap was enforceable as a navigation-link hider but not as a real
   server-side block: tracing every reader of `served_count`/`exercise_count`/
   "total" tied to a playlist (not just the call sites Codex named) surfaced
   three more gaps — `apps/student/views.py:1088`/`:1275` (`totalExercises`
   using the wrong count), `lab/views.py:257` (the "dots" navigation list
   exposing clickable links past the cap), `lab/views.py:552`
   (`PlaylistView`, a second legacy route with no pre-resolution guard, same
   bug as `PlayerDefinitionView`), and `apps/student/unit_progress.py:285-286`
   plus its template (`unit_progress.html`) forcing a hardcoded 0%/indeterminate
   progress bar for all adaptive playlists regardless of whether a real total
   now exists. All folded into 5f. One claim didn't hold up under
   verification and was pushed back on: `ExerciseView` (`lab/views.py:760`)
   has no `playlist`/`exercise_num` concept at all and isn't part of this
   serving path — confirmed by reading it, not assumed.
3. The write-site audit was still incomplete a second time — a broad,
   unscoped repo-wide grep (this time not excluding anything by filename
   pattern) found `apps/exercises/tests/test_adaptive_serving.py` (2 more
   constructor-kwarg sites) and two scratch scripts
   (`batch_import_unit9.py`, `batch_harmonization_qa.py`). Explicit decision
   made to migrate both scratch scripts rather than declare them unsupported
   — one is a documented, intentionally re-runnable pipeline per project
   memory, and the fix is two lines regardless. Four more files were found to
   reference `is_adaptive`/`is_dynamic` but verified as read-only (safe under
   the new properties, no code change needed) and added to the testing plan
   by name instead, since they're the closest existing regression coverage
   for several write sites this spec touches.
