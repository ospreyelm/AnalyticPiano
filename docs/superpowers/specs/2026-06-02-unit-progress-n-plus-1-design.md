# Unit Progress Page — N+1 Query Fix (Design Spec)

**Date:** 2026-06-02
**Status:** Approved (brainstorm), pending implementation plan
**Scope:** Query performance only. No data cleanup, no infra, no schema changes.

## Problem

Loading a unit page (`get_unit_progress_data`) is slow on the deployed app
(Fly `ord` ↔ Neon `us-east-1`). Measured: cold TTFB ~21s, warm ~0.16s. The
slowness is not a one-time cold start — clicking into a unit immediately after
login (DB already warm) still takes "forever."

Root cause: **N+1 query fanout**. `get_unit_progress_data` loops over every
playlist in a unit and calls `_playlist_stats(user, playlist)` once per
playlist. Each call issues ~6 queries:

- `PerformanceData.filter(user, playlist)` — re-evaluated 3× (lines 142, 165, 196)
- `IdentificationAttempt.filter(user, playlist)` — re-evaluated 2× (lines 143, 183)
- `attempt.exercise` lazy-loaded per attempt (no `select_related`) — N+1 inside N+1
- `get_ordered_exercise_ids_for_serving` → `playlist.untransposed_exercises_ids`
  (`cached_property`) → `ExercisePlaylistOrdered.filter(playlist=self)` — 1 query/playlist

Cost = `queries × playlists × latency`. Local Postgres (~0.1ms) hid this; Neon
cross-region (~20ms+) reveals it. A unit with ~13 playlists ≈ 80+ sequential
round-trips.

### Why "fast locally" was the wrong measurement

The schema/model is fine. The query *patterns* were never sustainable — N+1 is
visible in code review regardless of runtime. Performance must be verified by
**query count**, not felt latency. This spec adds an `assertNumQueries` guard so
the regression cannot silently return.

## Current data shape (verified)

- `Playlist._id` = AutoField pk (numeric). `Playlist.id` = string "P…" public id.
- Related models' `playlist_id` FK = numeric pk (`_id`). Group raw data by `playlist.pk`.
- `untransposed_exercises_ids` is a per-instance `cached_property`; values are
  string E-IDs ordered by `ExercisePlaylistOrdered.order`.

## Architecture

Split fetch from compute. Batch all progress reads into a constant number of
queries, then make `_playlist_stats` a pure function over pre-fetched data.

```text
_batch_playlist_data(user, playlists) → {playlist_pk: PlaylistRawData}
  Guard: if not playlists → return {} (no queries fired).
  3 progress queries, all filtered via playlist FK __in:
    1. PerformanceData.filter(user, playlist_id__in=pks).order_by("playlist_id","created")
    2. IdentificationAttempt.filter(user, playlist_id__in=pks)
                            .select_related("exercise")
                            .order_by("playlist_id","submitted_at")
    3. ExercisePlaylistOrdered.filter(playlist_id__in=pks)
                              .order_by("playlist_id","order")
                              .values_list("playlist_id","exercise__id")
  Grouped in Python by playlist.pk. Default empty entry for playlists with no rows.

_playlist_stats(playlist, raw) → stats dict.  PURE. Zero DB.
  Receives pre-sorted perf rows, ident attempts (exercise preloaded), and
  the playlist's SERVED exercise ids (Unit-4 shuffle already applied — see below).

_playlist_stats_by_id(user, playlist_id):
  fetch playlist → _batch_playlist_data(user, [playlist])
                → _playlist_stats(playlist, raw[playlist.pk])

_batch_skill_levels(user, unit_tags) → {display_tag: level}
  ONE query: StudentSkillMastery.filter(user, skill_tag__in=all_canonical_tags).
  Resolves TAG_ALIASES in Python (same precedence as _get_skill_level), returns a
  level per display tag. Reused for BOTH bar_segments and skill_cards.

Total per unit page (stats phase): 3 progress queries + 1 skill-levels query.
Constant in playlist count and in unit_tags count.
```

## Data flow

### `PlaylistRawData`

```python
@dataclass
class PlaylistRawData:
    perf_rows: list[PerformanceData]            # ordered by created ASC
    ident_attempts: list[IdentificationAttempt] # exercise preloaded, submitted_at ASC
    served_exercise_ids: list[str]              # serving order, Unit-4 shuffle applied
```

**Unit-4 shuffle stays in the batch fn (it needs `user`).** Current serving logic
seeds a per-user RNG: `f"{user.id}:{playlist.id}:unit4"` (player_progression.py).
`_batch_playlist_data` fetches the untransposed ordered ids, then for Unit-4
personalized playlists applies the same shuffle+truncate in-memory (no query) and
stores the result in `served_exercise_ids`. This keeps `_playlist_stats` pure with
no `user` argument while preserving Unit-4 `total` and next-index behavior. To
avoid drift, `_batch_playlist_data` reuses the existing serving helpers
(`_is_unit4_personalized_playlist`, the RNG seed, `UNIT4_SERVED_EXERCISE_COUNT`)
rather than re-deriving the shuffle.

### Batch fn

1. `pks = [p.pk for p in playlists]`; if empty, return `{}`.
2. PerformanceData query (ordered by playlist_id, created) → group by `playlist_id`.
   **Sorted once here** — eliminates the 3× re-evaluation.
3. IdentificationAttempt query (`select_related("exercise")`, ordered) → group.
4. ExercisePlaylistOrdered values_list → group `exercise__id` by `playlist_id`.
5. Build `{pk: PlaylistRawData(...)}`, defaulting empties.

### Collapsing redundant work in `_playlist_stats`

- `pd_rows` (was queried/ordered 3×) → one pre-sorted `raw.perf_rows`, iterated
  in memory for `completed_ids`, scored entries (last), `last_pd_date`.
- `ident_attempts` (was queried 2×) → one `raw.ident_attempts`; `attempt.exercise`
  already loaded (no lazy N+1).
- `pd_rows.last().created` + `.exists()` → `raw.perf_rows[-1].created if raw.perf_rows else None`.
- `get_ordered_exercise_ids_for_serving` → `raw.served_exercise_ids` (Unit-4
  shuffle already applied in the batch fn).

### Behavior preserved

Same `completed_ids`, same `last_score_pct` logic (perf-vs-ident date compare),
same `done` / `total` / `url`. Pure refactor of *where data comes from*, not
*what is computed*. `url` still calls `reverse()` and reads `playlist.tags` — no DB.

## Testing

Write the query-budget test first (TDD): it fails on current code, passes after fix.

**Test 1 — query budget (regression guard).** Seed a user and 20 playlists in
one unit (each with exercises + perf + ident rows). `assertNumQueries(budget)`
around `get_unit_progress_data(user, "9")`. Then seed 40 playlists and assert the
**same** count. The budget covers the whole function:

- 1 playlist-discovery query (`_get_playlists_for_unit` → `accessible_playlist_queryset`)
- 3 progress queries (batch fn)
- 1 skill-levels query (`_batch_skill_levels`)

≈ 5 fixed queries, **constant in both playlist count and unit_tags count**. Assert
`<= budget` rather than a brittle exact number (auth/session queries may add a
small fixed overhead depending on test setup).

**Test 2 — behavior identity.** Seed a playlist with known perf + ident data.
Assert `_playlist_stats` returns the same `done` / `total` / `last_score_pct` /
`url` as a captured golden, guarding that the refactor changed no grading numbers.

**Test 3 — pure fn isolation.** `assertNumQueries(0)` around
`_playlist_stats(playlist, raw)` to prove zero DB inside (pass a fetched instance
so `playlist.tags` does not lazy-load).

### Edge cases

1. Playlist with no perf and no ident rows → `done=0`, `last_score_pct=None`.
2. Ident-only playlist → last score from ident path.
3. Perf + ident both, ident newer → ident score wins.
4. Unit 1 path — `_playlist_stats_by_id` per lane works via single-item batch.
5. Empty unit (no matching playlists) → batch with `[]` fires no queries.
6. Unit-4 shuffle playlist → `served_exercise_ids` (shuffled+truncated in the
   batch fn) yields `total` + next-index matching old
   `get_ordered_exercise_ids_for_serving`. Add a direct test asserting batch-fn
   served ids equal the old helper's output for the same (user, playlist).

## Files touched

- `apps/student/unit_progress.py` — `_batch_playlist_data`, pure `_playlist_stats`,
  `_playlist_stats_by_id`, `_batch_skill_levels` (replaces per-tag `_get_skill_level`
  calls in `bar_segments` and `skill_cards`).
- `apps/student/tests/test_unit_progress.py` — new tests.
- `apps/exercises/models.py` — added `Playlist.prime_untransposed_exercises_ids(ids)`
  helper method (no migration) so the batch fetch can seed the
  `untransposed_exercises_ids` cached_property without poking `__dict__` from another module.
- No migration changes. No infra.

## Out of scope (explicit)

- Duplicate playlist cleanup (34 dupe-name playlists on Neon) — separate data task.
- Fly always-on / region co-location — separate infra task.
- DB-side playlist filtering (`_get_playlists_for_unit` Python filter) — the
  per-playlist fanout, not the 267-row haul, is the dominant cost; array-op
  portability is its own risk. Revisit only if profiling shows the haul matters.
- Caching — premature at 42 performance rows.
