# Student Progress Tracking — Implementation Prompts

**Spec:** `docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md`  
**Plan:** `docs/superpowers/specs/2026-04-25-student-progress-tracking-plan.md`

Run each prompt in a fresh session in the order listed. Each is self-contained.

---

## Prompt 1 — TaxonomyReader utility
**Recommended model:** Gemini Flash 3  
**Risk:** Low — pure Python, no DB, fully spec'd

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 2: TaxonomyReader Utility)

Then read:
music_theory_taxonomy.json  (the source data this utility wraps)

Create the file apps/exercises/taxonomy_reader.py implementing the TaxonomyReader class exactly as described in Section 2 of the spec. Requirements:
- Stateless class with class-level lazy-loaded _data cache
- Methods: get_all_units(), get_unit(unit_n), get_tier_for_unit(unit_n), get_unit_for_tag(skill_tag), get_skill_label(tag)
- get_skill_label converts "Note_Names" → "Note Names" (replace underscores, title-case)
- No Django imports — must be importable without a database
- Reads music_theory_taxonomy.json from the repo root (BASE_DIR or __file__-relative path)

Also create apps/exercises/tests/test_taxonomy_reader.py with these tests:
- test_get_unit_returns_correct_unit
- test_get_unit_for_tag_finds_unit
- test_get_unit_for_unknown_tag_returns_none
- test_get_all_units_includes_all_tiers
- test_skill_label_formatting

Acceptance: python manage.py test apps.exercises.tests.test_taxonomy_reader — all pass.

Stage and commit:
  git add apps/exercises/taxonomy_reader.py apps/exercises/tests/test_taxonomy_reader.py
  git commit -m "feat: add TaxonomyReader utility (Phase 1)"
```

---

## Prompt 2 — UnitProgressView service
**Recommended model:** Gemini Pro / Claude Sonnet  
**Risk:** Medium-high — complex ORM queries, JSONField deduplication

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 3: UnitProgressView Service)

Then read these files to understand the data models:
- apps/exercises/models.py  (focus on: PerformanceData, StudentSkillMastery, Playlist, ExercisePlaylistOrdered)
- apps/exercises/taxonomy_reader.py  (the utility you will call — must exist from Phase 1)
- apps/student/progress.py  (existing progress logic to understand patterns)

Create apps/student/unit_progress.py implementing get_unit_progress_data(user, unit_n) as described in the spec. 

Key implementation details:
- Use TaxonomyReader.get_unit(unit_n) and TaxonomyReader.get_tier_for_unit(unit_n) for unit/tier data
- Match playlists to skill tags via set intersection: set(playlist.skill_tags or []) & set(unit["tags"])
- skill level: query StudentSkillMastery.objects.filter(user=user, skill=skill_tag) — if no record, return "not_started"
- Completion count (done): count UNIQUE exercise IDs across ALL PerformanceData rows for this (user, playlist) pair. PerformanceData has a JSONField called "data" which is a list of dicts, each with an "id" key. Aggregate: {id for pd in PerformanceData.objects.filter(user=user, playlist=playlist) for entry in (pd.data or []) if "id" in entry}
- Last score pct: most recent data entry with "score_numerator" key present, compute round(score_numerator / score_denominator * 100)
- Return 404-ready None if unit_n not found

Also write tests in apps/student/tests/test_unit_progress.py:
- test_get_unit_progress_data_structure (check required keys present)
- test_skill_level_for_new_user_is_not_started
- test_playlist_stats_counts_unique_exercises (not total attempts)
- test_last_score_pct_none_for_old_data

Run: python manage.py test apps.student.tests.test_unit_progress

Stage and commit:
  git add apps/student/unit_progress.py apps/student/tests/test_unit_progress.py
  git commit -m "feat: add UnitProgressView service (Phase 2)"
```

---

## Prompt 3 — `record_attempt()` return value
**Recommended model:** Gemini Flash 3  
**Risk:** Low — small, targeted change

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 4: Mastery Level-Up Notifications)

Then read:
apps/exercises/mastery.py  (find record_attempt() — currently returns None)

Modify record_attempt() so it returns a dict of skill-level changes:
- Before updating StudentSkillMastery, snapshot current levels for each skill tag on the exercise
- After updating, snapshot new levels
- Return {tag: {"old": old_level, "new": new_level}} for any tag where the level changed
- Return empty dict {} if no levels changed
- The return value must never break existing callers (they currently discard the return value)

Add a private helper _current_level(user_id, skill_tag) -> str if one doesn't already exist.

Add two tests to apps/exercises/tests/test_mastery.py (or a new test file if that's cleaner):
- test_record_attempt_returns_empty_dict_when_no_level_change
- test_record_attempt_returns_level_change_when_threshold_crossed

Run existing tests to confirm nothing is broken: python manage.py test apps.exercises.tests

Stage and commit:
  git add apps/exercises/mastery.py apps/exercises/tests/test_mastery.py
  git commit -m "feat: record_attempt() returns mastery level changes (Phase 3)"
```

---

## Prompt 4 — Submit endpoint: score fields + mastery changes
**Recommended model:** Gemini Flash 3  
**Risk:** Low — mechanical passthrough

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 1: Score Storage, Section 4: Mastery Level-Up Notifications)

Then read:
apps/exercises/views.py  (find the exercise submission endpoint — look for "submit" in URL patterns or view names)
apps/exercises/models.py  (find PerformanceData.submit() to confirm JSONField passthrough)

Tasks:
1. Verify that PerformanceData.submit() (or the submit view) already passes arbitrary keys from the incoming payload into pd.data[] entries. If it filters keys, update it to also pass through "score_numerator" and "score_denominator".

2. In the submit view, capture the return value of record_attempt() as mastery_changes (it now returns a dict — see Phase 3).

3. Add "mastery_changes" to the JSON response:
   {"status": "ok", "mastery_changes": {...}}
   The key must always be present (use {} if no changes).

4. Guard: if score_denominator is 0 in the incoming payload, store it as-is (display layer handles divide-by-zero).

Run the existing exercise submission tests to confirm nothing is broken.

Stage and commit:
  git add apps/exercises/views.py apps/exercises/models.py
  git commit -m "feat: submit endpoint returns mastery_changes in JSON response (Phase 4)"
```

---

## Prompt 5 — JavaScript grader score fields
**Recommended model:** Gemini Pro / Claude Sonnet  
**Risk:** Medium-high — requires reading unfamiliar JS files to find internal state

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 1: Score Storage, Section 5: Exercise Score Card — the "score_numerator/denominator" part)

Then read these JavaScript files carefully:
- lab/static/js/src/models/exercise_context.js  (find submitExerciseReport() or equivalent)
- lab/static/js/src/  (look for grader files — ExerciseGrader, ChoraleGrader, IdentificationGrader or similar names)

Tasks:
1. Add a getScore() method to each grader class that returns {numerator, denominator}:
   - MIDI/matching/analytical (ExerciseGrader): denominator = total chords/notes; numerator = total - error_tally
   - ChoraleGrader: denominator = total onset windows; numerator = onset windows hit correctly
   - IdentificationGrader: denominator = total slots; numerator = correct slots
   Each grader already tracks these numbers internally — expose them via getScore().

2. In submitExerciseReport() (or wherever the POST payload is assembled), call grader.getScore() and add score_numerator and score_denominator to the payload before submission.

Do NOT change the submission URL or response handling — just add the two fields to the outgoing payload.

Manual acceptance test: complete any exercise in the browser, open DevTools Network tab, confirm the POST payload includes score_numerator and score_denominator as integers.

Stage and commit:
  git add lab/static/js/src/  (only the grader files you modified)
  git commit -m "feat: add score_numerator/denominator to exercise submission payload (Phase 5)"
```

---

## Prompt 6 — `exercise_score_card.js` component
**Recommended model:** Gemini Pro / Claude Sonnet  
**Risk:** High — complex JS component, animation, multiple states, event wiring

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 5: Exercise Score Card — read the full section carefully including the anatomy diagram, design rules, and state variants table)

Then read:
- lab/static/js/src/models/exercise_context.js  (find where submitExerciseReport() resolves — this is where you wire the score card)
- lab/static/js/src/  (look for any existing overlay/modal components to follow the same pattern)
- lab/templates/ or lab/static/  (understand the exercise player HTML structure so you know what element to append the card to)

Create lab/static/js/src/components/exercise_score_card.js implementing ExerciseScoreCard:

class ExerciseScoreCard:
  init(containerEl)      — inject hidden card HTML into containerEl
  show(data)             — data = {score_numerator, score_denominator, mastery_changes, skill_name, exercise_num, total_exercises, unit_name, unit_bar_segments, next_exercise_url, next_skill_name, unit_n}
  hide()                 — slide card down, reset content

Score display:
- Circular arc: use SVG with stroke-dashoffset to show score_pct (guard: denominator=0 → show "—")
- Display label thresholds: 100%=Mastered, 80-99%=Proficient, 60-79%=Familiar, 40-59%=Attempted, <40%=Needs Practice

State variants (NO emoji — use color and text only):
- Normal: no banner; blue circle; tier badge; "Next Exercise →" primary CTA
- Level-up (not mastered): blue banner "Level up! [Old] → [New] in [Skill]"; "Next Exercise →"  
- Mastered: gold banner "You've mastered [Skill]"; green circle; "MASTERED" badge; "Start [Next Skill] →" in green
- Low score (<60%): amber circle; "Needs Practice"; "Try Again" as primary CTA
- test mode (check window.HarmonyLab?.identMode === "test" or equivalent config): do not show card at all

Mini unit bar: render one colored div per entry in unit_bar_segments (each has {tag, label, level}).
Colors: mastered=green, proficient=blue, familiar=amber, not_started=light gray.

After show() is done, wire into exercise_context.js: after submitExerciseReport() resolves with success, call scoreCard.show(responseData).

Make sure the component is imported/registered correctly for the existing JS build system (check if there's a webpack config, an index.js barrel file, or a simple script tag in the template).

Stage and commit:
  git add lab/static/js/src/components/exercise_score_card.js lab/static/js/src/models/exercise_context.js
  git commit -m "feat: add exercise score card overlay component (Phase 6)"
```

---

## Prompt 7 — Unit progress page (template + view + URL)
**Recommended model:** Gemini Flash 3  
**Risk:** Low-medium — Django template work, well-specified

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 6: Unit Progress Page, Section 7: URL and Navigation Wiring)

Then read:
- apps/student/views.py  (understand existing view patterns — LoginRequiredMixin, etc.)
- apps/student/urls.py  (understand URL patterns)
- apps/student/templates/student/  (find the base template to extend)
- apps/student/unit_progress.py  (the service you will call — must exist from Phase 2)

Tasks:

1. Add UnitProgressView(LoginRequiredMixin, View) to apps/student/views.py:
   - get(request, unit_n): call get_unit_progress_data(request.user, unit_n)
   - Return 404 if unit_n not found (get_unit_progress_data returns None for unknown unit_n)
   - Pass data dict to template context

2. Create apps/student/templates/student/unit_progress.html:
   - Extend the appropriate base template
   - Breadcrumb: "← Back" (link to referring URL or course list)
   - Unit header: tier badge (T1, T2 etc) + "Unit N · Title" + feat description
   - Segmented mastery bar: one div per bar_segments entry, CSS class based on level
     (.tier-mastered=green, .tier-proficient=blue, .tier-familiar=amber, .tier-not-started=light gray)
   - Skill cards: one per skill_cards entry
     - Header: skill label left, mastery badge right
     - Playlist sub-rows: name, mini progress bar (done/total), last_score_pct if not None
     - Entire row is an <a> to the playlist URL
     - "Coming soon" placeholder if playlists list is empty
   - CSS: add styles inline or to existing student stylesheet; match existing design tokens

3. Add URL to apps/student/urls.py:
   path("units/<str:unit_n>/", UnitProgressView.as_view(), name="unit-progress")

Manual acceptance: visit /student/units/1/ as a logged-in student — page renders without errors.

Stage and commit:
  git add apps/student/views.py apps/student/urls.py apps/student/templates/student/unit_progress.html
  git commit -m "feat: add unit progress page (Phase 7)"
```

---

## Prompt 8 — Navigation wiring
**Recommended model:** Gemini Flash 3  
**Risk:** Low — link additions across templates and JS

```
Read the design spec at:
docs/superpowers/specs/2026-04-25-student-progress-tracking-design.md
(Section 7: URL and Navigation Wiring)

Then read:
- apps/student/templates/student/  (find the course/playlist page template)
- apps/student/views.py  (find the course or playlist list view to understand context data)
- apps/exercises/taxonomy_reader.py  (you will call this to group playlists by unit)

Tasks:

1. Course page → Unit page:
   In the student course or playlist-list template, group playlists by their unit using
   TaxonomyReader.get_unit_for_tag(tag) on each playlist's skill_tags.
   Add a unit heading (e.g. "Unit 1 · Pitch & Staff Notation") above each group,
   with the heading as a link to /student/units/<unit_n>/.
   If a playlist has no matching unit, show it ungrouped at the bottom.
   Do this grouping in the view (not in the template) and pass grouped_playlists to the context.

2. Exercise player breadcrumb (if the exercise player template shows "Unit 1 // Playlist Name"):
   Make the "Unit 1" portion a clickable link to /student/units/1/.
   Find the breadcrumb in the lab template and wrap the unit portion in an <a> tag.

3. Score card → Unit page (JS):
   In lab/static/js/src/components/exercise_score_card.js, when the mastered state is active,
   the "Start [Next Skill] →" button should navigate to /student/units/<unit_n>/.
   The unit_n must be passed in the show(data) call — make sure the submit endpoint response
   (or exercise config) includes unit_n, or derive it client-side from the skill tag if needed.

Manual acceptance: full journey works — Course page → click unit heading → Unit progress page → 
click playlist row → Exercise player → complete exercise → Score card appears → click Next →
return to exercise → Unit page now shows updated mastery bar.

Stage and commit all changed files:
  git add -A
  git commit -m "feat: wire unit progress navigation across course, player, and score card (Phase 8)"
```

---

## Notes for all prompts

- Always run the existing test suite after each phase: `python manage.py test`
- Commit each phase separately with a clear message, e.g. `feat: add TaxonomyReader utility (Phase 1)`
- If a phase depends on a previous one, confirm the dependency file exists before starting
- The spec is the source of truth — if a prompt and the spec conflict, follow the spec
