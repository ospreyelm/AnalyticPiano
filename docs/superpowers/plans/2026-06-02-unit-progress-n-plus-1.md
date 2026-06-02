# Unit Progress N+1 Query Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the unit progress page issue a constant number of DB queries regardless of how many playlists a unit contains, eliminating the N+1 fanout that makes unit pages slow against a remote (Neon) database.

**Architecture:** Split fetch from compute. A new `_batch_playlist_data(user, playlists)` runs 3 batched progress queries (PerformanceData, IdentificationAttempt with `select_related`, ExercisePlaylistOrdered) grouped by playlist pk, prefilling each playlist's `untransposed_exercises_ids` cached_property so the existing serving helper runs query-free. `_playlist_stats(playlist, raw)` becomes a pure function over pre-fetched data. A new `_batch_skill_levels(user, unit_tags)` collapses `2M` per-tag mastery lookups into 1 query. An `assertNumQueries` test locks the query budget so the N+1 cannot silently return.

**Tech Stack:** Django ORM, Python dataclasses, Django `TestCase.assertNumQueries`.

**Reference spec:** `docs/superpowers/specs/2026-06-02-unit-progress-n-plus-1-design.md`

**Environment note:** Work happens on `master` (or a worktree). If in a fresh worktree, run `pyenv local system` first — `.python-version` pins an uninstalled 3.10.18.

**Run tests with:** `python manage.py test apps.student.tests.test_unit_progress --settings=harmony.settings.local`

---

## File Structure

- **`apps/student/unit_progress.py`** (modify) — add `PlaylistRawData`, `_batch_playlist_data`, `_batch_skill_levels`; rewrite `_playlist_stats` as pure; rewrite `_playlist_stats_by_id`; update `get_unit_progress_data` callers (Unit-1 lane loop + non-Unit-1 path).
- **`apps/student/tests/test_unit_progress.py`** (modify) — add query-budget test, behavior-identity test, pure-fn isolation test, Unit-4 served-ids parity test.

No model/migration/infra changes.

---

## Task 0: Add shared test helpers (`_make_ident`, `_seed_unit_playlists`)

The test file already has module-level helpers: `_make_author(n)`, `_make_student(n)`,
`_make_exercise(pk, author)` (UMTO-safe — assigns `_id`), `_make_playlist(pk, author, skill_tags, name)`,
`_make_pd(user, playlist, data)`, and a `TAXONOMY_PATCH` dict patching
`TaxonomyReader.get_unit` → `STUB_GENERIC_UNIT` (unit `"2"`, tags `["Note_Names","Intervals"]`).
Tests patch taxonomy with `@patch(...)` decorators or `patch.multiple(**TAXONOMY_PATCH)`.

New tests need an IdentificationAttempt helper and a multi-playlist seeder that
generates **globally unique pks and names** (so `_dedupe_playlists_by_name` does
not collapse a second batch).

**Files:**
- Modify: `apps/student/tests/test_unit_progress.py`

- [ ] **Step 1: Add `_make_ident` and `_seed_unit_playlists` as module-level helpers**

Add after `_make_pd` (line ~99). Note `IdentificationAttempt` must be added to the
top-of-file model import.

```python
from apps.exercises.models import (
    Exercise,
    ExercisePlaylistOrdered,
    IdentificationAttempt,   # add this
    PerformanceData,
    Playlist,
    StudentSkillMastery,
)


def _make_ident(user, playlist, exercise, score) -> IdentificationAttempt:
    return IdentificationAttempt.objects.create(
        user=user, playlist=playlist, exercise=exercise,
        is_page_submit=True, score=score,
    )


# Monotonic pk source so every seeded row across batches is unique.
_PK_SEQ = [100000]

def _next_pk() -> int:
    _PK_SEQ[0] += 1
    return _PK_SEQ[0]


def _seed_unit_playlists(author, student, unit_n, count, primary_tag):
    """Create `count` public playlists for the unit, each with one exercise, a
    PerformanceData row (score 1/1) and a completed IdentificationAttempt.

    Unique pks AND unique names so _dedupe_playlists_by_name keeps them all.
    Returns the created playlists.
    """
    playlists = []
    for _ in range(count):
        ex = _make_exercise(_next_pk(), author)
        pl = _make_playlist(
            _next_pk(), author,
            skill_tags=[primary_tag, f"unit:{unit_n}"],
            name=f"PL-{unit_n}-{_PK_SEQ[0]}",
        )
        ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=0)
        _make_pd(student, pl, [{"id": ex.id, "score_numerator": 1, "score_denominator": 1}])
        _make_ident(student, pl, ex, {"correct": 1, "incorrect": 0, "unanswered": 0})
        playlists.append(pl)
    return playlists
```

- [ ] **Step 2: Commit the helpers**

```bash
git add apps/student/tests/test_unit_progress.py
git commit -m "test: add _make_ident + unique-name _seed_unit_playlists helper"
```

---

## Task 1: Query-budget regression test (write next, must FAIL)

**Files:**
- Test: `apps/student/tests/test_unit_progress.py`

- [ ] **Step 1: Write the failing query-budget test**

Taxonomy is patched (unit `"2"`, primary tag `"Note_Names"`). Author and student
are distinct users (matches the file's fixture convention).

```python
class UnitProgressQueryBudgetTests(TestCase):
    QUERY_BUDGET = 15  # generous ceiling first; tightened in Task 5 to the real count

    def setUp(self):
        self.author = _make_author(60001)
        self.student = _make_student(60002)

    @patch("apps.student.unit_progress.TaxonomyReader.get_unit", return_value=STUB_GENERIC_UNIT)
    @patch("apps.student.unit_progress.TaxonomyReader.get_tier_for_unit", return_value=STUB_TIER)
    @patch(
        "apps.student.unit_progress.TaxonomyReader.get_skill_label",
        side_effect=lambda tag: tag.replace("_", " ").title(),
    )
    def test_query_count_constant_in_playlist_count(self, *_mocks):
        _seed_unit_playlists(self.author, self.student, "2", 20, "Note_Names")
        with self.assertNumQueries(self.QUERY_BUDGET):
            get_unit_progress_data(self.student, "2")

        # Doubling playlists must NOT increase the count.
        _seed_unit_playlists(self.author, self.student, "2", 20, "Note_Names")  # 40 total
        with self.assertNumQueries(self.QUERY_BUDGET):
            get_unit_progress_data(self.student, "2")
```

- [ ] **Step 2: Run the test, confirm it FAILS on current code**

Run: `python manage.py test apps.student.tests.test_unit_progress.UnitProgressQueryBudgetTests --settings=harmony.settings.local -v 2`
Expected: FAIL — the 40-playlist `assertNumQueries` blows `QUERY_BUDGET` because today's code is N+1. (If the 20-playlist case already exceeds 15, the first assertion fails — also acceptable proof.) This confirms the test catches the regression.

- [ ] **Step 3: Commit the failing test**

```bash
git add apps/student/tests/test_unit_progress.py
git commit -m "test: add unit-progress query-budget guard (currently failing)"
```

---

## Task 2: Add `PlaylistRawData` and `_batch_playlist_data`

**Files:**
- Modify: `apps/student/unit_progress.py`

- [ ] **Step 1: Add imports and the dataclass**

At the top of `apps/student/unit_progress.py`, extend imports and add the dataclass. Current imports (lines 11-23) already pull `PerformanceData, Playlist, StudentSkillMastery` and `get_ordered_exercise_ids_for_serving, is_completed_identification_attempt`. Add `IdentificationAttempt`, `ExercisePlaylistOrdered`, and `dataclass`/`field`.

```python
from dataclasses import dataclass, field

from apps.exercises.models import (
    ExercisePlaylistOrdered,
    IdentificationAttempt,
    PerformanceData,
    Playlist,
    StudentSkillMastery,
)
```

Add near the top of the module body (after imports):

```python
@dataclass
class PlaylistRawData:
    perf_rows: list = field(default_factory=list)        # PerformanceData, created ASC
    ident_attempts: list = field(default_factory=list)   # IdentificationAttempt, exercise preloaded, submitted_at ASC
    served_exercise_ids: list = field(default_factory=list)  # serving order, Unit-4 shuffle applied
```

- [ ] **Step 2: Add `_batch_playlist_data`**

Add this function above `_playlist_stats`. It prefills each playlist's
`untransposed_exercises_ids` cached_property from the batched ordered-id query,
then calls the existing serving helper (which now runs query-free) so the Unit-4
shuffle stays in exactly one place.

```python
def _batch_playlist_data(user, playlists) -> dict:
    """Fetch all per-playlist progress data in a constant number of queries.

    Returns {playlist_pk: PlaylistRawData}. Fires no queries when `playlists`
    is empty.
    """
    pks = [pl.pk for pl in playlists]
    if not pks:
        return {}

    # 1. PerformanceData, pre-sorted so callers never re-order/re-query.
    perf_by_pk: dict[int, list] = {pk: [] for pk in pks}
    for pd in (
        PerformanceData.objects
        .filter(user=user, playlist_id__in=pks)
        .order_by("playlist_id", "created")
    ):
        perf_by_pk[pd.playlist_id].append(pd)

    # 2. IdentificationAttempt with exercise preloaded (kills lazy N+1).
    ident_by_pk: dict[int, list] = {pk: [] for pk in pks}
    for attempt in (
        IdentificationAttempt.objects
        .filter(user=user, playlist_id__in=pks)
        .select_related("exercise")
        .order_by("playlist_id", "submitted_at")
    ):
        ident_by_pk[attempt.playlist_id].append(attempt)

    # 3. Ordered exercise ids per playlist (one query for all).
    ordered_by_pk: dict[int, list] = {pk: [] for pk in pks}
    for playlist_pk, exercise_id in (
        ExercisePlaylistOrdered.objects
        .filter(playlist_id__in=pks)
        .order_by("playlist_id", "order")
        .values_list("playlist_id", "exercise__id")
    ):
        ordered_by_pk[playlist_pk].append(exercise_id)

    raw: dict[int, PlaylistRawData] = {}
    for pl in playlists:
        # Prefill the cached_property so get_ordered_exercise_ids_for_serving()
        # (which applies the Unit-4 shuffle) runs without hitting the DB.
        pl.__dict__["untransposed_exercises_ids"] = ordered_by_pk[pl.pk]
        served = get_ordered_exercise_ids_for_serving(user, pl)
        raw[pl.pk] = PlaylistRawData(
            perf_rows=perf_by_pk[pl.pk],
            ident_attempts=ident_by_pk[pl.pk],
            served_exercise_ids=served,
        )
    return raw
```

- [ ] **Step 3: Commit (no behavior change yet)**

```bash
git add apps/student/unit_progress.py
git commit -m "feat: add _batch_playlist_data + PlaylistRawData (unused so far)"
```

---

## Task 3: Unit-4 served-ids parity test

**Files:**
- Test: `apps/student/tests/test_unit_progress.py`

- [ ] **Step 1: Write the parity test**

Confirms the batch fn's `served_exercise_ids` equals the old per-playlist helper
output for the same (user, playlist), including the Unit-4 shuffle+truncate. This
test needs no taxonomy patch — `_is_unit4_personalized_playlist` reads only the
playlist's tags. Build a playlist with tags `["unit:4", "Interval_Specific"]` and
10 ordered exercises so the shuffle+truncate to `UNIT4_SERVED_EXERCISE_COUNT` (6)
fires.

```python
class BatchPlaylistDataParityTests(TestCase):
    def setUp(self):
        self.author = _make_author(61001)
        self.student = _make_student(61002)

    def test_served_ids_match_serving_helper(self):
        from apps.student.player_progression import get_ordered_exercise_ids_for_serving
        from apps.student.unit_progress import _batch_playlist_data

        pl = _make_playlist(
            _next_pk(), self.author,
            skill_tags=["unit:4", "Interval_Specific"], name="U4-parity",
        )
        for order in range(10):
            ex = _make_exercise(_next_pk(), self.author)
            ExercisePlaylistOrdered.objects.create(playlist=pl, exercise=ex, order=order)

        expected = get_ordered_exercise_ids_for_serving(self.student, pl)

        # Fresh instance so the cached_property is not already populated by the
        # call above (get_ordered_exercise_ids_for_serving cached it on `pl`).
        pl_fresh = Playlist.objects.get(pk=pl.pk)
        raw = _batch_playlist_data(self.student, [pl_fresh])
        self.assertEqual(raw[pl.pk].served_exercise_ids, expected)
        self.assertEqual(len(raw[pl.pk].served_exercise_ids), 6)  # truncated
```

- [ ] **Step 2: Run it, expect PASS**

Run: `python manage.py test apps.student.tests.test_unit_progress.BatchPlaylistDataParityTests --settings=harmony.settings.local -v 2`
Expected: PASS — both paths use the same RNG seed `f"{user.id}:{playlist.id}:unit4"` and `UNIT4_SERVED_EXERCISE_COUNT`, so the lists match.

- [ ] **Step 3: Commit**

```bash
git add apps/student/tests/test_unit_progress.py
git commit -m "test: assert batch served-ids match serving helper (Unit-4 parity)"
```

---

## Task 4: Make `_playlist_stats` pure

**Files:**
- Modify: `apps/student/unit_progress.py` (current `_playlist_stats` is lines 129-244)

- [ ] **Step 1: Rewrite `_playlist_stats` to take `(playlist, raw)` and do zero DB**

Replace the existing `def _playlist_stats(user, playlist)` body. Logic is byte-for-byte the same computation; only the data source changes (pre-fetched `raw` instead of queries). Keep `is_completed_identification_attempt` and `reverse` usage.

```python
def _playlist_stats(playlist: Playlist, raw: "PlaylistRawData") -> dict:
    """Pure compute of per-playlist completion stats from pre-fetched data.

    No DB access. `raw` is produced by _batch_playlist_data.
    """
    perf_rows = raw.perf_rows                # pre-sorted created ASC
    ident_attempts = raw.ident_attempts      # pre-sorted submitted_at ASC, exercise preloaded
    served_ids = raw.served_exercise_ids

    completed_ids: set[str] = {
        entry["id"]
        for pd in perf_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    completed_ids.update(
        attempt.exercise.id
        for attempt in ident_attempts
        if attempt.exercise and is_completed_identification_attempt(attempt)
    )
    done = len(completed_ids)

    # Last score: most recent perf data entry with score_numerator present.
    last_score_pct = None
    all_scored_entries = [
        entry
        for pd in perf_rows
        for entry in (pd.data or [])
        if "score_numerator" in entry
    ]
    if all_scored_entries:
        last_entry = all_scored_entries[-1]
        try:
            numerator = last_entry["score_numerator"]
            denominator = last_entry["score_denominator"]
            if denominator and denominator > 0:
                last_score_pct = round(numerator / denominator * 100)
        except (KeyError, TypeError, ZeroDivisionError):
            pass

    # Identification scores.
    submitted_ident_attempts = [a for a in ident_attempts if a.is_page_submit]
    ident_scores = []
    for attempt in submitted_ident_attempts:
        score_data = attempt.score or {}
        correct = score_data.get("correct", 0)
        incorrect = score_data.get("incorrect", 0)
        unanswered = score_data.get("unanswered", 0)
        tot = correct + incorrect + unanswered
        if tot > 0:
            ident_scores.append(round(correct / tot * 100))

    if ident_scores:
        last_pd_date = perf_rows[-1].created if perf_rows else None
        last_id_date = submitted_ident_attempts[-1].submitted_at if submitted_ident_attempts else None
        if last_id_date and (not last_pd_date or last_id_date > last_pd_date):
            last_score_pct = ident_scores[-1]
        elif last_score_pct is None:
            last_score_pct = ident_scores[-1]

    # Resolve the unit number for the player URL (no DB; reads tags on instance).
    unit_num = "1"
    playlist_tags = list(playlist.tags or []) + list(playlist.skill_tags or [])
    for tag in playlist_tags:
        if isinstance(tag, str) and tag.startswith("unit:"):
            unit_num = tag.split(":", 1)[1]
            break
    else:
        for tag in playlist_tags:
            unit = TaxonomyReader.get_unit_for_tag(tag)
            if unit:
                unit_num = str(unit.get("n", "1"))
                break

    next_exercise_num = 1
    for idx, ex_id in enumerate(served_ids, 1):
        if ex_id not in completed_ids:
            next_exercise_num = idx
            break

    url = reverse(
        "student:player",
        kwargs={"unit_num": unit_num},
    ) + f"?playlist={playlist.id}&exercise_num={next_exercise_num}"

    return {
        "id": playlist.id,
        "name": playlist.name,
        "done": done,
        "total": len(served_ids),
        "is_adaptive": bool(playlist.is_adaptive),
        "last_score_pct": last_score_pct,
        "url": url,
    }
```

Remove the now-dead `from apps.exercises.models import IdentificationAttempt` local import inside the old function, the `from apps.exercises.taxonomy_reader import TaxonomyReader` local import (module already imports it at top), and the old `get_ordered_exercise_ids_for_serving(user, playlist)` call.

- [ ] **Step 2: Rewrite `_playlist_stats_by_id` to feed pre-fetched data**

```python
def _playlist_stats_by_id(user, playlist_id: str) -> dict:
    playlist = Playlist.objects.get(id=playlist_id)
    raw = _batch_playlist_data(user, [playlist])
    return _playlist_stats(playlist, raw[playlist.pk])
```

- [ ] **Step 3: Update the non-Unit-1 caller in `get_unit_progress_data`**

In the `else` branch (current lines 538-561), batch once before the loop and feed each `_playlist_stats` from `raw`.

```python
        matching_playlists = _dedupe_playlists_by_name(
            _get_playlists_for_unit(user, unit_tags, unit_n=unit_n),
            user,
        )
        explicit_unit_tag = f"unit:{unit_n}"
        raw_by_pk = _batch_playlist_data(user, matching_playlists)

        tag_to_playlists: dict[str, list[dict]] = {tag: [] for tag in unit_tags}
        for playlist in matching_playlists:
            primary_tag = _playlist_primary_tag(playlist, unit_tags)
            if primary_tag is None and unit_tags:
                if (
                    explicit_unit_tag in (playlist.skill_tags or [])
                    or explicit_unit_tag in (playlist.tags or [])
                ):
                    primary_tag = unit_tags[0]
            if primary_tag is None:
                continue
            stats = _playlist_stats(playlist, raw_by_pk[playlist.pk])
            tag_to_playlists[primary_tag].append(stats)
```

- [ ] **Step 4: Update the Unit-1 lane caller**

In the `if unit_n == "1":` branch, the loop calls `_playlist_stats_by_id(user, lane["playlist_id"])` (current line 503). That now internally batches a single playlist — leave the call as-is; it works through the rewritten `_playlist_stats_by_id`. No edit needed beyond confirming it still imports.

- [ ] **Step 5: Add a behavior-identity test (stats numbers unchanged)**

Pins `done` / `total` / `last_score_pct` / `url` to known values so the refactor
cannot silently change grading output.

```python
class PlaylistStatsIdentityTests(TestCase):
    def setUp(self):
        self.author = _make_author(62001)
        self.student = _make_student(62002)

    def test_known_perf_and_ident_yield_expected_stats(self):
        from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
        pl = _seed_unit_playlists(self.author, self.student, "2", 1, "Note_Names")[0]
        raw = _batch_playlist_data(self.student, [pl])
        stats = _playlist_stats(pl, raw[pl.pk])
        self.assertEqual(stats["done"], 1)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["last_score_pct"], 100)
        self.assertIn(f"playlist={pl.id}", stats["url"])
        self.assertIn("exercise_num=", stats["url"])
```

- [ ] **Step 6: Run the existing unit-progress suite + identity test**

Run: `python manage.py test apps.student.tests.test_unit_progress --settings=harmony.settings.local -v 2`
Expected: existing behavior tests + `PlaylistStatsIdentityTests` PASS (stats unchanged). The Task-1 budget test may still exceed budget until Task 5 batches skill lookups — expected.

- [ ] **Step 7: Commit**

```bash
git add apps/student/unit_progress.py apps/student/tests/test_unit_progress.py
git commit -m "refactor: make _playlist_stats pure over batched data"
```

---

## Task 5: Batch skill-level lookups

**Files:**
- Modify: `apps/student/unit_progress.py` (`_get_skill_level` is lines 26-55; callers at 485 and 572)

- [ ] **Step 1: Add `_batch_skill_levels`**

Add below `_get_skill_level` (keep `_get_skill_level` for any other callers). Mirror its alias resolution and level precedence, but in one query.

```python
def _batch_skill_levels(user, display_tags: list[str]) -> dict[str, str]:
    """Resolve mastery level for each display tag in a single query.

    Mirrors _get_skill_level's TAG_ALIASES expansion and level precedence.
    """
    level_order = [
        StudentSkillMastery.LEVEL_MASTERED,
        StudentSkillMastery.LEVEL_PROFICIENT,
        StudentSkillMastery.LEVEL_FAMILIAR,
        StudentSkillMastery.LEVEL_ATTEMPTED,
        StudentSkillMastery.LEVEL_NOT_STARTED,
    ]
    # Collect every canonical tag we need, query once.
    canonical_by_display = {t: TAG_ALIASES.get(t, [t]) for t in display_tags}
    all_canonical = {c for tags in canonical_by_display.values() for c in tags}
    mastery_map = dict(
        StudentSkillMastery.objects
        .filter(user=user, skill_tag__in=all_canonical)
        .values_list("skill_tag", "level")
    )

    result: dict[str, str] = {}
    for display_tag, canon in canonical_by_display.items():
        levels = [mastery_map.get(t, StudentSkillMastery.LEVEL_NOT_STARTED) for t in canon]
        result[display_tag] = next(
            (lvl for lvl in level_order if lvl in levels),
            StudentSkillMastery.LEVEL_NOT_STARTED,
        )
    return result
```

- [ ] **Step 2: Use it for bar_segments and skill_cards**

In `get_unit_progress_data`, build the level map once near the top of the function (after `unit_tags` is known, before `bar_segments`):

```python
    skill_levels = _batch_skill_levels(user, unit_tags)
```

Then replace `_get_skill_level(user, tag)` at the bar_segments comprehension (line 485):

```python
            "level": skill_levels.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED),
```

and at the skill_cards comprehension (line 572):

```python
            "level": skill_levels.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED),
```

Note: the Unit-1 branch builds its own `bar_segments` from lane mastery and does not use `skill_levels`; leave it untouched.

- [ ] **Step 3: Run the budget test — now expect PASS at both sizes**

Run: `python manage.py test apps.student.tests.test_unit_progress.UnitProgressQueryBudgetTests --settings=harmony.settings.local -v 2`
Expected: PASS — query count for 20 and 40 playlists is identical and within `QUERY_BUDGET`.

- [ ] **Step 4: Tighten the budget to the real number**

Read the actual count from a temporary `print` or from the failure message if you lower `QUERY_BUDGET`. Set `QUERY_BUDGET` to `actual` (the steady-state count). Keep a 1-2 query margin only if auth/session queries vary across runs. Re-run to confirm PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/student/unit_progress.py apps/student/tests/test_unit_progress.py
git commit -m "perf: batch skill-level lookups (2M -> 1 query) and tighten budget"
```

---

## Task 6: Pure-fn isolation test

**Files:**
- Test: `apps/student/tests/test_unit_progress.py`

- [ ] **Step 1: Write the zero-query test**

```python
class PlaylistStatsPurityTests(TestCase):
    def setUp(self):
        self.author = _make_author(63001)
        self.student = _make_student(63002)

    def test_playlist_stats_does_no_db_io(self):
        from apps.student.unit_progress import _batch_playlist_data, _playlist_stats
        pl = _seed_unit_playlists(self.author, self.student, "2", 1, "Note_Names")[0]
        pl = Playlist.objects.get(pk=pl.pk)  # fetched instance, tags loaded
        raw = _batch_playlist_data(self.student, [pl])
        with self.assertNumQueries(0):
            _playlist_stats(pl, raw[pl.pk])
```

`_seed_unit_playlists` is a module-level helper (Task 0), callable from any test class.

- [ ] **Step 2: Run it, expect PASS**

Run: `python manage.py test apps.student.tests.test_unit_progress.PlaylistStatsPurityTests --settings=harmony.settings.local -v 2`
Expected: PASS — `_playlist_stats` touches only pre-fetched data + `reverse()` + in-memory tag reads.

- [ ] **Step 3: Run the FULL student test suite for regressions**

Run: `python manage.py test apps.student --settings=harmony.settings.local`
Expected: all PASS. Pay attention to `test_views.py`, `test_progress.py`, `test_player_progression.py`, `test_unit1_curriculum*`.

- [ ] **Step 4: Commit**

```bash
git add apps/student/tests/test_unit_progress.py
git commit -m "test: assert _playlist_stats does zero DB I/O"
```

---

## Task 7: Verify against the symptom + clean up

**Files:**
- Modify: `apps/student/unit_progress.py` (remove dead code if any remains)

- [ ] **Step 1: Confirm no remaining per-playlist queries**

Run: `grep -n "get_ordered_exercise_ids_for_serving\|PerformanceData.objects.filter\|IdentificationAttempt.objects.filter\|_get_skill_level(" apps/student/unit_progress.py`
Expected: `_playlist_stats` no longer calls any of these in a loop; the only `PerformanceData`/`IdentificationAttempt` queries are inside `_batch_playlist_data`. `_get_skill_level` may remain defined but should have no caller inside `get_unit_progress_data` (the Unit-1 branch uses lane mastery, not `_get_skill_level`). If `_get_skill_level` is now unused anywhere in the repo, delete it.

Run: `grep -rn "_get_skill_level" apps/` to check for other callers before deleting.

- [ ] **Step 2: Full suite once more**

Run: `python manage.py test apps.student --settings=harmony.settings.local`
Expected: all PASS.

- [ ] **Step 3: Commit any cleanup**

```bash
git add apps/student/unit_progress.py
git commit -m "chore: drop unused _get_skill_level after batching"
```

(Skip this commit if `_get_skill_level` still has callers elsewhere.)

---

## Done criteria

- `UnitProgressQueryBudgetTests` passes: query count identical for 20 vs 40 playlists, within a tight budget (~5 + fixed overhead).
- `_playlist_stats` does zero DB I/O (`PlaylistStatsPurityTests`).
- Unit-4 served-ids parity holds (`BatchPlaylistDataParityTests`).
- Full `apps.student` suite green.
- No behavior change to `done` / `total` / `last_score_pct` / `url`.
