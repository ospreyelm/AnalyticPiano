# Unit 1 Curriculum Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Unit 1’s tag-driven student experience with a curated six-lane curriculum backed by six canonical playlists, while retiring redundant Unit 1 categories and duplicate student-facing playlist rows.

**Architecture:** Resolve six canonical Unit 1 playlists first, then use an explicit Unit 1 lane-mapping helper as the single source of truth for student rendering and resume behavior. Update the Unit 1 student entry surface to consume that curated model, align or redirect the parallel surface, and retire the old tag-overlap assumptions in views, seed content, and tests.

**Tech Stack:** Django views/templates, Django ORM, Django management commands, Django test client, Python unit tests

---

## File Structure

### Canonical Unit 1 mapping and data cleanup

- `apps/student/views.py`
  - Contains `HomeView`, `UnitView`, `PlayerView`, current `UNIT_1_TAGS`, and the old Unit 1 resume/category logic that must stop using tag overlap.
- `apps/student/unit_progress.py`
  - Current service layer for the Unit 1 progress page; likely best place to consume a curated Unit 1 view-model.
- `apps/student/management/commands/seed_unit1_content.py`
  - Currently seeds the retired four-tag Unit 1 structure and must be updated or retired.
- `apps/exercises/models.py`
  - Read-only context for playlist IDs, `skill_tags`, and playlist exercise lists if needed during discovery.
- New helper module, likely `apps/student/unit1_curriculum.py`
  - Recommended home for the canonical six-lane mapping and curated Unit 1 builder.

### Student rendering

- `apps/student/templates/student/unit_progress.html`
  - Current richer unit surface; likely candidate for canonical Unit 1 rendering.
- `apps/student/templates/student/unit.html`
  - Parallel Unit 1 surface; must be aligned or redirected so it cannot continue showing the old structure.

### Tests

- `apps/student/tests/test_unit_progress.py`
  - Best home for curated Unit 1 service/view-model tests.
- `apps/student/tests/test_unit1_curriculum_integration.py`
  - Best home for student-facing Unit 1 integration checks.
- `apps/student/tests/test_views.py`
  - Best home for route-level assertions and resume behavior checks.

---

### Task 1: Resolve Canonical Unit 1 Playlists And Freeze The Mapping

**Files:**
- Create: `apps/student/unit1_curriculum.py`
- Modify: `docs/superpowers/specs/2026-04-25-unit1-curriculum-cleanup-design.md`
- Inspect: `apps/exercises/models.py`
- Inspect via shell: live/dev Playlist rows for Unit 1

- [ ] **Step 1: Query the database for current Unit 1 playlists**

Run an explicit Django shell query to enumerate candidate Unit 1 playlists by `unit:1` tagging, not by fragile name prefix:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "from django.db.models import Q; from apps.exercises.models import Playlist; rows=Playlist.objects.filter(Q(skill_tags__contains=['unit:1']) | Q(tags__contains=['unit:1'])).values_list('id','name','skill_tags'); [print(r) for r in rows]"
```

Expected: a printable list of current Unit 1 playlist IDs/names/tags that includes the duplicate variants the spec is trying to retire. If `tags` is not a real field on `Playlist`, simplify the query to the actual Unit 1 tagging field rather than falling back to name matching.

- [ ] **Step 2: Record the six canonical playlists**

From the query output, choose exactly one playlist for each lane:

```python
UNIT1_CANONICAL_LANES = {
    "identify": {
        "title": "Identify",
        "rows": [
            {"slug": "treble", "label": "Treble", "playlist_id": "PA____"},
            {"slug": "bass", "label": "Bass", "playlist_id": "PA____"},
        ],
    },
    "play_from_name": {
        "title": "Play from Name",
        "rows": [
            {"slug": "treble", "label": "Treble", "playlist_id": "PA____"},
            {"slug": "bass", "label": "Bass", "playlist_id": "PA____"},
        ],
    },
    "play_the_notes": {
        "title": "Play the Notes",
        "rows": [
            {"slug": "treble", "label": "Treble", "playlist_id": "PA____"},
            {"slug": "bass", "label": "Bass", "playlist_id": "PA____"},
        ],
    },
}
```

Do not leave placeholders in the implementation. Use the actual six playlist IDs discovered in Step 1.

- [ ] **Step 3: Create the Unit 1 curriculum helper**

Create `apps/student/unit1_curriculum.py` with the canonical mapping and helper accessors:

```python
from __future__ import annotations

UNIT1_CANONICAL_LANES = {
    # fill with actual playlist IDs from discovery
}


def get_unit1_lane_groups() -> list[dict]:
    return [
        {"slug": slug, "title": group["title"], "rows": list(group["rows"])}
        for slug, group in UNIT1_CANONICAL_LANES.items()
    ]


def get_unit1_playlist_ids() -> list[str]:
    return [
        row["playlist_id"]
        for group in UNIT1_CANONICAL_LANES.values()
        for row in group["rows"]
    ]
```

Keep this file data-focused. No ORM work should live here.

- [ ] **Step 4: Update the spec with the resolved IDs**

Replace the placeholder example in the spec with the final chosen IDs or append a short “Resolved canonical playlists” section listing them explicitly.

Expected outcome: the spec and code agree on the six playlists being curated.

- [ ] **Step 5: Run a minimal import/syntax check**

Run:

```bash
python -m py_compile apps/student/unit1_curriculum.py
```

Expected: exit `0`.

- [ ] **Step 6: Commit**

```bash
git add apps/student/unit1_curriculum.py docs/superpowers/specs/2026-04-25-unit1-curriculum-cleanup-design.md
git commit -m "Define canonical Unit 1 curriculum mapping"
```

---

### Task 2: Curate Unit 1 Student Rendering And Resume Behavior

**Files:**
- Modify: `apps/student/unit_progress.py`
- Modify: `apps/student/views.py`
- Modify: `apps/student/templates/student/unit_progress.html`
- Modify: `apps/student/templates/student/unit.html`
- Create or modify tests: `apps/student/tests/test_unit_progress.py`, `apps/student/tests/test_unit1_curriculum_integration.py`, `apps/student/tests/test_views.py`
- Read: `apps/student/unit1_curriculum.py`

- [ ] **Step 1: Write failing service tests for the curated Unit 1 shape**

Before writing the full assertion block, make sure `apps/student/unit_progress.py` exposes an importable `get_unit1_lane_groups` symbol at module scope, even if the first implementation branch is still incomplete. This keeps the red test failure about behavior rather than a patch-target/import error.

Add a focused test in `apps/student/tests/test_unit_progress.py` that expects exactly three groups and six rows for Unit 1:

```python
    @patch("apps.student.unit_progress.get_unit1_lane_groups")
    def test_unit1_returns_three_curated_activity_cards(self, mock_groups):
        mock_groups.return_value = [
            {"slug": "identify", "title": "Identify", "rows": [{"slug": "treble", "label": "Treble", "playlist_id": "PA1"}, {"slug": "bass", "label": "Bass", "playlist_id": "PA2"}]},
            {"slug": "play_from_name", "title": "Play from Name", "rows": [{"slug": "treble", "label": "Treble", "playlist_id": "PA3"}, {"slug": "bass", "label": "Bass", "playlist_id": "PA4"}]},
            {"slug": "play_the_notes", "title": "Play the Notes", "rows": [{"slug": "treble", "label": "Treble", "playlist_id": "PA5"}, {"slug": "bass", "label": "Bass", "playlist_id": "PA6"}]},
        ]

        result = get_unit_progress_data(self.student, "1")

        self.assertEqual(len(result["activity_cards"]), 3)
        self.assertEqual(sum(len(card["rows"]) for card in result["activity_cards"]), 6)
```

Also add negative assertions that retired Unit 1 categories are absent from the returned labels.

Expected initial failure mode: the test should fail because `activity_cards` behavior is not implemented yet, not because the patch target cannot be imported.

- [ ] **Step 2: Add curated Unit 1 support to the service layer**

In `apps/student/unit_progress.py`, branch on `unit_n == "1"` and build a curated Unit 1 model from `get_unit1_lane_groups()` instead of `_get_playlists_for_unit(unit_tags)`:

```python
from apps.student.unit1_curriculum import get_unit1_lane_groups


def _playlist_stats_by_id(user, playlist_id: str) -> dict:
    playlist = Playlist.objects.get(id=playlist_id)
    return _playlist_stats(user, playlist)
```

Then build:

```python
    if unit_n == "1":
        activity_cards = []
        for group in get_unit1_lane_groups():
            rows = []
            for row in group["rows"]:
                stats = _playlist_stats_by_id(user, row["playlist_id"])
                rows.append({
                    "slug": row["slug"],
                    "label": row["label"],
                    "playlist_id": row["playlist_id"],
                    "playlist_name": stats["name"],
                    "done": stats["done"],
                    "total": stats["total"],
                    "last_score_pct": stats["last_score_pct"],
                    "url": stats["url"],
                })
            activity_cards.append({
                "slug": group["slug"],
                "title": group["title"],
                "rows": rows,
            })
```

Return `activity_cards` alongside or instead of the old `skill_cards` for Unit 1. Do not try to make the generic tag-driven path express the curated structure.

- [ ] **Step 3: Update the canonical Unit 1 template to render activity cards**

Modify `apps/student/templates/student/unit_progress.html` so Unit 1 renders `activity_cards` instead of `skill_cards`:

```django
  {% if unit.n == "1" and activity_cards %}
    <div class="skill-cards-container">
      {% for card in activity_cards %}
        <div class="skill-card">
          <div class="skill-card-header">
            <h2 class="skill-card-title">{{ card.title }}</h2>
          </div>
          <div class="skill-playlists">
            {% for row in card.rows %}
              <a href="{{ row.url }}" class="playlist-row">
                <span class="playlist-name">{{ row.label }}</span>
                <div class="playlist-progress-info">
                  <div class="mini-progress-bar">
                    <div class="mini-progress-fill" style="width: {% if row.total > 0 %}{% widthratio row.done row.total 100 %}{% else %}0{% endif %}%"></div>
                  </div>
                  <span class="playlist-count">{{ row.done }}/{{ row.total }}</span>
                  {% if row.last_score_pct is not None %}
                    <span class="playlist-score">· Last: {{ row.last_score_pct }}%</span>
                  {% endif %}
                </div>
              </a>
            {% endfor %}
          </div>
        </div>
      {% endfor %}
    </div>
  {% else %}
```

Preserve the generic rendering path for non-Unit-1 units.

- [ ] **Step 4: Pick the canonical Unit 1 entry route and align the other route**

In `apps/student/views.py`, choose one authoritative Unit 1 student route. Recommended:

- `UnitProgressView` / `student/unit_progress.html` becomes canonical
- `UnitView` for Unit 1 redirects to the curated Unit 1 progress surface

Implement the redirect in `UnitView.get()`:

```python
        if str(unit_num) == "1":
            return redirect(reverse("student:unit-progress", kwargs={"unit_n": "1"}))
```

This prevents the old `unit.html` tag-driven view from continuing to expose the retired structure.

- [ ] **Step 5: Update HomeView resume logic to use the curated mapping**

In `apps/student/views.py`, replace the old Unit 1 resume flow that depends on `_get_playlists_for_tag(...)` / `UNIT_1_TAGS`.

Recommended helper shape, using the same completion-query pattern already present in `_playlist_stats()` rather than inventing a new undefined function:

```python
from apps.student.unit1_curriculum import get_unit1_playlist_ids
from apps.exercises.models import IdentificationAttempt, PerformanceData


def _user_completed_exercise_ids(user, playlist):
    pd_rows = PerformanceData.objects.filter(user=user, playlist=playlist)
    ident_attempts = IdentificationAttempt.objects.filter(user=user, playlist=playlist)

    completed_ids = {
        entry["id"]
        for pd in pd_rows
        for entry in (pd.data or [])
        if "id" in entry
    }
    completed_ids.update(
        attempt.exercise.id
        for attempt in ident_attempts
        if attempt.exercise
    )
    return completed_ids


def _get_unit1_resume_url(user):
    for playlist_id in get_unit1_playlist_ids():
        playlist = Playlist.objects.get(id=playlist_id)
        completed_ids = _user_completed_exercise_ids(user, playlist)
        for idx, exercise_id in enumerate(playlist.untransposed_exercises_ids, 1):
            if exercise_id not in completed_ids:
                return reverse("student:player", kwargs={"unit_num": 1}) + f"?playlist={playlist.id}&exercise_num={idx}"
    return reverse("student:unit-progress", kwargs={"unit_n": "1"})
```

Use the canonical lane order (Identify/Treble first, then Identify/Bass, then Play from Name/Treble, etc.) rather than old tag overlap.

- [ ] **Step 6: Remove or stop relying on the old Unit 1 tag scaffolding**

Delete or neutralize Unit 1-only legacy assumptions in `apps/student/views.py`:

- `UNIT_1_TAGS`
- `skill_display_names` entries for retired categories
- the `enharmonic` compatibility label override

Keep generic code for other units intact, but Unit 1 should no longer depend on those structures.

- [ ] **Step 7: Run targeted tests for the curated service and views**

Run:

```bash
python manage.py test apps.student.tests.test_unit_progress apps.student.tests.test_unit1_curriculum_integration apps.student.tests.test_views -v 2
```

Expected: PASS, assuming local DB/test settings are configured.

- [ ] **Step 8: Commit**

```bash
git add apps/student/unit_progress.py apps/student/views.py apps/student/templates/student/unit_progress.html apps/student/templates/student/unit.html apps/student/tests/test_unit_progress.py apps/student/tests/test_unit1_curriculum_integration.py apps/student/tests/test_views.py
git commit -m "Curate Unit 1 student curriculum surface"
```

---

### Task 3: Update Or Retire The Old Unit 1 Seeder

**Files:**
- Modify or retire: `apps/student/management/commands/seed_unit1_content.py`
- Test: command behavior by inspection or targeted command run if safe
- Read: `apps/student/unit1_curriculum.py`

- [ ] **Step 1: Write the intended seeder behavior in a docstring/comment**

At the top of `seed_unit1_content.py`, add or update the module/command comment so it states the new contract:

```python
"""
Seed the curated Unit 1 student curriculum lanes.
This command must not recreate the retired tag/category-based Unit 1 structure.
"""
```

- [ ] **Step 2: Either update the command to seed canonical lanes or retire it**

Preferred outcome: update it so the seeded Unit 1 content aligns to the canonical mapping.

If updated, the command should seed exactly the six canonical Unit 1 playlists represented in `UNIT1_CANONICAL_LANES`, not recreate the old tag/category structure.

If the command is not authoritative anymore, make it fail loudly with guidance instead of silently creating obsolete content:

```python
raise CommandError(
    "seed_unit1_content is retired. Use the curated Unit 1 playlist mapping in apps.student.unit1_curriculum instead."
)
```

Do not leave the command able to regenerate `Note_Names`, `Ledger_Lines`, `clefs`, and `enharmonic` as the student-facing Unit 1 structure.

- [ ] **Step 3: Verify the command cannot recreate the deprecated structure**

If retired:

```bash
python manage.py seed_unit1_content
```

Expected: explicit `CommandError` explaining the command is retired.

If updated:

```bash
python manage.py seed_unit1_content --help
```

Expected: help/output describing the curated Unit 1 behavior, not the old tag structure.

- [ ] **Step 4: Commit**

```bash
git add apps/student/management/commands/seed_unit1_content.py
git commit -m "Retire legacy Unit 1 seeding path"
```

---

### Task 4: Final Verification And Cleanup

**Files:**
- Inspect all files changed in Tasks 1-3

- [ ] **Step 1: Run a playlist-visibility sanity query**

Run a shell query that confirms only the six canonical playlists are being used by the curated Unit 1 surface:

```bash
DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py shell -c "from apps.student.unit1_curriculum import get_unit1_playlist_ids; print(get_unit1_playlist_ids())"
```

Expected: exactly six playlist IDs in the intended order.

- [ ] **Step 2: Run the Django test subset again**

Run:

```bash
python manage.py test apps.student.tests.test_unit_progress apps.student.tests.test_unit1_curriculum_integration apps.student.tests.test_views -v 2
```

Expected: PASS.

- [ ] **Step 3: Manually verify the student-facing Unit 1 page**

Check:

1. exactly three cards render
2. each card has `Treble` then `Bass`
3. no `Pitch Reading`, `Clefs`, `Ledger Lines`, `Enharmonics`, or `Extended Range` cards appear
4. row links land in the intended canonical playlists
5. Home resume lands in a canonical Unit 1 lane

Expected: Unit 1 reads like a curated curriculum, not a raw playlist dump.

- [ ] **Step 4: Commit verification-safe cleanup if needed**

If tiny follow-up fixes were needed:

```bash
git add apps/student/unit1_curriculum.py apps/student/unit_progress.py apps/student/views.py apps/student/templates/student/unit_progress.html apps/student/templates/student/unit.html apps/student/management/commands/seed_unit1_content.py apps/student/tests/test_unit_progress.py apps/student/tests/test_unit1_curriculum_integration.py apps/student/tests/test_views.py
git commit -m "Polish curated Unit 1 student flow"
```

If no cleanup was needed, skip this step.

---

## Self-Review

### Spec coverage

- Canonical playlist ID blocker: Task 1.
- Curated six-lane Unit 1 structure: Task 2.
- Canonical route / parallel surface alignment: Task 2.
- HomeView resume update: Task 2.
- Seeder update/retirement: Task 3.
- Concrete testing files: Tasks 2 and 4.

### Placeholder scan

- The only placeholders are the actual playlist IDs in the Task 1 example, and the plan explicitly requires resolving them before implementation.
- All commands are concrete.
- Each code-changing task includes concrete snippets or explicit behavior.

### Type consistency

- Uses `Playlist.id`, `playlist.untransposed_exercises_ids`, `get_unit_progress_data`, `UnitView`, `HomeView`, and template names consistent with the current codebase.
- Keeps Unit 1 special-casing isolated instead of pretending the old generic tag system can model the new curated structure.
