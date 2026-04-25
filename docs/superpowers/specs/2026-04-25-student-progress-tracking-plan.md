# Student Progress Tracking — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md`  
**Date:** 2026-04-25  
**Branch:** create from `feature/music21_builder` or a new `feature/progress-tracking`

---

## Phase 1 — TaxonomyReader utility

**File:** `apps/exercises/taxonomy_reader.py` *(new)*

### Tasks

- [ ] Create `apps/exercises/taxonomy_reader.py`
- [ ] Implement `TaxonomyReader` class with class-level `_data` cache (lazy-loaded)
- [ ] `_load()` — reads `music_theory_taxonomy.json` from the repo root; raises `FileNotFoundError` with clear message if missing
- [ ] `get_all_units()` — flattens all tiers → all units into a single list
- [ ] `get_unit(unit_n: str)` — returns unit dict where `unit["n"] == unit_n`, or `None`
- [ ] `get_tier_for_unit(unit_n: str)` — returns parent tier dict, or `None`
- [ ] `get_unit_for_tag(skill_tag: str)` — returns first unit whose `tags` list contains `skill_tag`, or `None`
- [ ] `get_skill_label(tag: str)` — converts `"Note_Names"` → `"Note Names"` (replace underscores, title-case)
- [ ] Write unit tests in `apps/exercises/tests/test_taxonomy_reader.py`:
  - `test_get_unit_returns_correct_unit`
  - `test_get_unit_for_tag_finds_unit`
  - `test_get_unit_for_unknown_tag_returns_none`
  - `test_get_all_units_includes_all_tiers`
  - `test_skill_label_formatting`

### Acceptance
`python manage.py test apps.exercises.tests.test_taxonomy_reader` — all pass, no DB required.

---

## Phase 2 — UnitProgressView service

**File:** `apps/student/unit_progress.py` *(new)*

### Tasks

- [ ] Create `apps/student/unit_progress.py`
- [ ] Implement `get_unit_progress_data(user, unit_n: str) -> dict` — see spec Section 3 for full return shape
- [ ] Sub-function `_get_skill_level(user, skill_tag: str) -> str` — queries `StudentSkillMastery` for the user + skill tag; returns `"mastered"`, `"proficient"`, `"familiar"`, `"attempted"`, or `"not_started"`
- [ ] Sub-function `_get_playlists_for_skill(skill_tag: str) -> QuerySet` — returns `Playlist.objects.filter(skill_tags__contains=[skill_tag])` (adjust for actual JSONField lookup)
- [ ] Sub-function `_get_playlist_stats(user, playlist) -> dict` — returns `{done, total, last_score_pct}`:
  - `total` = `playlist.exercise_count`
  - `done` = count of unique exercise IDs in `PerformanceData.data[]` for this (user, playlist) pair across all courses
  - `last_score_pct` = from most recent data entry with `score_numerator` key, or `None`
- [ ] Sub-function `_get_next_exercise_url(user, playlist) -> str` — URL for next uncompleted exercise_num
- [ ] Write tests in `apps/student/tests/test_unit_progress.py`:
  - `test_get_unit_progress_data_structure`
  - `test_skill_level_for_new_user_is_not_started`
  - `test_playlist_stats_counts_unique_exercises`
  - `test_last_score_pct_none_for_old_data`

### Acceptance
All tests pass. `get_unit_progress_data(user, "1")` returns correct structure for a real user fixture.

---

## Phase 3 — `record_attempt()` return value

**File:** `apps/exercises/mastery.py`

### Tasks

- [ ] Locate `record_attempt()` (currently returns `None`)
- [ ] Before updating `StudentSkillMastery`, snapshot current levels: `old_levels = {tag: _current_level(user_id, tag) for tag in exercise.skill_tags}`
- [ ] After updating, snapshot new levels: `new_levels = {tag: _current_level(user_id, tag) for tag in exercise.skill_tags}`
- [ ] Return `{tag: {"old": old, "new": new} for tag in skill_tags if old_levels[tag] != new_levels[tag]}` — empty dict if no changes
- [ ] Add private helper `_current_level(user_id, skill_tag) -> str`
- [ ] Update any callers that ignore the return value — no behavior change needed, they can continue ignoring it
- [ ] Add tests in `apps/exercises/tests/test_mastery.py`:
  - `test_record_attempt_returns_empty_dict_when_no_level_change`
  - `test_record_attempt_returns_level_change_when_threshold_crossed`

### Acceptance
All existing mastery tests pass. New tests pass.

---

## Phase 4 — Submit endpoint: score fields + mastery changes

**Files:** `apps/exercises/views.py`, `apps/exercises/models.py`

### Tasks

- [ ] Verify `PerformanceData.submit()` passes through arbitrary keys from incoming payload to `pd.data[]` (it should already — confirm with a quick test)
- [ ] In the submit view, ensure `score_numerator` and `score_denominator` from the incoming POST body reach `pd.data[]`
- [ ] Capture return value of `record_attempt()` as `mastery_changes`
- [ ] Add `mastery_changes` to the JSON response — always present, empty dict `{}` if no changes
- [ ] Guard: if `score_denominator` is 0 in the payload, store as-is (display layer handles divide-by-zero)
- [ ] Verify existing submit test suite still passes

### Acceptance
`POST /exercises/submit/` response always includes `"mastery_changes": {...}`. Existing tests green.

---

## Phase 5 — JavaScript: score fields in submission payload

**Files:** `lab/static/js/src/models/exercise_context.js` + grader files

### Tasks

- [ ] Add `getScore() -> {numerator, denominator}` to `ExerciseGrader`: `denominator = total chords`; `numerator = total chords - error_tally`
- [ ] Add `getScore()` to `ChoraleGrader`: `denominator = total onset windows`; `numerator = onset windows hit correctly` (already tracked internally)
- [ ] Add `getScore()` to `IdentificationGrader`: `denominator = total slots`; `numerator = correct slots` (already tracked)
- [ ] In `submitExerciseReport()` (or its caller in `exercise_context.js`), call `grader.getScore()` and include `score_numerator`, `score_denominator` in the POST payload
- [ ] Confirm payload keys match what the Python submit view expects

### Acceptance
Network tab shows POST payload with `score_numerator` and `score_denominator`. Values appear in `PerformanceData.data[]` in DB.

---

## Phase 6 — `exercise_score_card.js` component

**File:** `lab/static/js/src/components/exercise_score_card.js` *(new)*

### Tasks

- [ ] Create module; export `ExerciseScoreCard` class
- [ ] `init(containerEl)` — injects card HTML into container, hidden by default (CSS `transform: translateY(100%)`)
- [ ] `show(data)` where `data = {score_numerator, score_denominator, mastery_changes, skill_name, exercise_num, total_exercises, unit_name, unit_bar_segments}`:
  - Compute `score_pct`; guard for `denominator === 0` → show "—"
  - Determine display badge label from `score_pct` thresholds
  - If `mastery_changes` has entries, set level-up banner content
  - Render circular arc using `conic-gradient` CSS or inline SVG `stroke-dashoffset`
  - Render mini unit segmented bar from `unit_bar_segments`
  - Animate card: `transform: translateY(0)` with CSS transition
- [ ] `hide()` — slide card back down; reset content
- [ ] "Try Again" button: `hide()` + trigger exercise reset (call existing reset mechanism)
- [ ] "Next Exercise →" button: `hide()` + navigate to next exercise URL
- [ ] "Start [Next Skill] →" button (mastered state only): navigate to `/student/units/<unit_n>/`
- [ ] Suppress entirely if `identMode === "test"` (check exercise config)
- [ ] Wire into `exercise_context.js`: after `submitExerciseReport()` resolves successfully, call `scoreCard.show(responseData)`
- [ ] Design rules: no emoji; blue banner for level-up; gold banner for mastered; amber circle for low score

### Acceptance
Manual test across all exercise types. Score card appears after submission. All buttons work. Test mode suppresses card.

---

## Phase 7 — Unit progress page

**Files:**
- `apps/student/views.py`
- `apps/student/templates/student/unit_progress.html` *(new)*
- `apps/student/urls.py`
- CSS (extend existing student stylesheet)

### Tasks

**View:**
- [ ] Add `UnitProgressView(LoginRequiredMixin, View)` to `apps/student/views.py`
- [ ] `get(request, unit_n)`: call `get_unit_progress_data(request.user, unit_n)`; return 404 if unit not found
- [ ] Pass data to template context

**Template:**
- [ ] Extend base student template
- [ ] Breadcrumb: "← Back to Course" (link to referring page or default course URL)
- [ ] Unit header: tier badge + unit number + title + feat description
- [ ] Segmented mastery bar: one `<div>` per `bar_segments` entry, colored by level
  - CSS classes: `.tier-mastered`, `.tier-proficient`, `.tier-familiar`, `.tier-not-started`
  - Hover tooltip showing skill name and tier
- [ ] Skill cards: one per `skill_cards` entry
  - Header row: skill label + mastery level badge (right-aligned)
  - Playlist sub-rows: name, mini progress bar `(done/total)`, `last_score_pct` if available
  - Entire row is an `<a>` linking to next exercise URL
  - "Coming soon" placeholder if `playlists` list is empty
- [ ] CSS: colors and layout consistent with existing student UI

**URL:**
- [ ] `path("units/<str:unit_n>/", UnitProgressView.as_view(), name="unit-progress")` in `apps/student/urls.py`

### Acceptance
`/student/units/1/` renders without errors for a logged-in student. Segmented bar, skill cards, and playlist rows all render correctly. Clicking a playlist row goes to the exercise player.

---

## Phase 8 — Navigation wiring

**Files:** Course page template, exercise player template

### Tasks

- [ ] **Course page → Unit page**: group playlists by unit using `TaxonomyReader.get_unit_for_tag()`. Add unit headings above each playlist group with a link to `/student/units/<unit_n>/`
- [ ] **Score card → Unit page**: in `exercise_score_card.js`, when mastered, make "Start [Next Skill] →" navigate to `/student/units/<unit_n>/`
- [ ] **Exercise player breadcrumb** (optional): make the "Unit 1" portion of the breadcrumb a link to `/student/units/1/`

### Acceptance
Full user journey: Course → Unit page → Exercise player → Score card → Unit page shows updated mastery bar.

---

## End-to-End Testing Checklist

- [ ] Complete a MIDI exercise — score card appears with correct %, tier, and "Next Exercise →"
- [ ] Complete an identification exercise — score card appears (not in test mode)
- [ ] identMode = "test" — score card is suppressed, exercise advances normally
- [ ] First completion in a skill — "not_started" → "attempted", no level-up banner
- [ ] Threshold crossing — "familiar" → "proficient", blue banner: "Level up! Familiar → Proficient in Note Names"
- [ ] All exercises mastered — gold banner, CTA: "Start Ledger Lines →"
- [ ] Unit progress page: correct bar segments for student with mixed mastery across skills
- [ ] Old PerformanceData entries (no `score_numerator`) show "—" without JS errors
- [ ] Unit 1 page accessible at `/student/units/1/` with correct data for Unit 1 taxonomy entry

---

## Out of Scope

- Teacher gradebook
- Skill decay / "review due" indicators
- Mastery Challenges
- UnitDefinition DB model
- First-visit animations on unit progress bar
- PDF transcript export
