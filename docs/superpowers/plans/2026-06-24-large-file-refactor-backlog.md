# Large File Refactor Backlog

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce large-file maintenance risk through small, behavior-preserving refactors.

**Architecture:** Refactor by risk and responsibility, not line count alone. Keep public routes, payloads, AMD module identities, and test behavior stable unless a later task explicitly approves a behavior change.

**Tech Stack:** Django, Python, RequireJS AMD JavaScript, VexFlow, existing Django test runner.

---

## Inventory Snapshot

Generated on 2026-06-24 from the isolated worktree using first-party source files only.

### Largest Python Files

| Lines | File | Responsibility | Risk | First Safe Action |
|---:|---|---|---|---|
| 1,555 | `apps/exercises/models.py` | Core Exercise, Playlist, Course, progress, and performance models | High | Defer until model responsibility changes are explicitly needed. |
| 1,493 | `apps/student/tests/test_views.py` | Student route, player, home, challenge, and CSS tests | Low | Split by existing test classes. |
| 1,399 | `apps/student/views.py` | Student auth, home context, unit pages, course panels, player delivery | Medium/High | Extract pure home/unit helper modules after test split. |
| 1,327 | `apps/exercises/forms.py` | Exercise, playlist, course forms plus visibility helpers/widgets | Medium | Defer; when touched, extract widgets and visibility helpers first. |
| 1,307 | `apps/exercises/umto_factory.py` | UMTO payload builders and save factories | High | Defer; when touched, extract by exercise type with UMTO tests. |
| 1,237 | `lab/views.py` | Legacy RequireJS views, shared exercise context, authoring endpoints | High | Extract `generate_exercise_context` and adaptive helper into a service. |
| 985 | `apps/teacher/views.py` | Teacher course, manifest, unit suggestion, and save/transposition views | Medium | Defer; split when a teacher workflow change requires it. |

### Largest First-Party JavaScript Files

| Lines | File | Responsibility | Risk | First Safe Action |
|---:|---|---|---|---|
| 1,904 | `lab/static/js/src/components/ui/music_controls.js` | Authoring controls, save panel, MIDI controls, batch wizard, MusicXML import | Medium/High | Extract save/batch/MusicXML logic after pure model splits. |
| 1,739 | `lab/static/js/src/components/music/stave_notater.js` | Analysis label drawing, Roman/figure text, notation helpers | High | Add characterization tests before extracting theory-sensitive helpers. |
| 1,569 | `lab/static/js/src/models/exercise_definition.js` | Exercise parsing, identification problem building, key conversion, filters | High | Extract pure identification/problem/key helpers without behavior change. |
| 1,484 | `lab/static/js/src/models/exercise_context.js` | Exercise runtime state, grading flow, timers, submissions, navigation | High | Extract timer/report/state helpers after Python view split. |
| 1,453 | `lab/static/js/src/utils/analyze.js` | Music-theory analysis, pitch spelling, intervals, figures, set classes | High | Read canon, add characterization tests, then extract no-op helpers. |
| 1,340 | `lab/static/js/src/components/music/play_sheet.js` | Play-view rendering orchestration, authoring selection, barlines, save data | Medium/High | Extract query, barline, playback, and save-data helpers later. |
| 1,019 | `lab/static/js/src/components/music/stave.js` | VexFlow stave rendering, voices, connectors, positioning | Medium/High | Extract pure helper functions after rendering smoke coverage. |

## Task 1: Split Student View Tests

**Files:**
- Modify: `apps/student/tests/test_views.py`
- Create: `apps/student/tests/test_auth_views.py`
- Create: `apps/student/tests/test_player_views.py`
- Create: `apps/student/tests/test_unit_views.py`
- Create: `apps/student/tests/test_home_views.py`
- Create: `apps/student/tests/test_challenge_views.py`
- Create: `apps/student/tests/test_design_css.py`

- [x] Preserve existing test class bodies exactly.
- [x] Keep duplicated imports initially to minimize split risk.
- [x] Leave `test_views.py` as a lazy compatibility marker with no eagerly-bound `TestCase` classes.
- [x] Verify the split suite still runs 63 tests.

## Task 2: Extract Student Home/Unit Helpers

**Files:**
- Modify: `apps/student/views.py`
- Create: `apps/student/home_context.py`
- Create: `apps/student/unit_metadata.py`

- [x] Move pure helper functions only.
- [x] Keep class-based views and URL behavior unchanged.
- [x] Preserve template context keys exactly.
- [x] Run focused and split student view tests.

## Task 3: Extract Shared Exercise Context Service

**Files:**
- Modify: `lab/views.py`
- Modify: `apps/student/views.py`
- Create: `apps/exercises/services/exercise_context.py`

- [x] Move `generate_exercise_context` and `get_adaptive_exercise_for_view`.
- [x] Keep compatibility wrappers in `lab.views` for existing callers and tests.
- [x] Preserve JSON payload shape exactly.
- [x] Run student and exercise context tests.

## Task 4: Split Config Data Modules (JavaScript)

**Goal:** Reduce `general.js` (852 lines) and `instruments.js` (530 lines) by extracting zero-dependency data tables into separate UMD modules.

**Files:**
- Modify: `lab/static/js/src/config/general.js`
- Modify: `lab/static/js/src/config/instruments.js`
- Create: `lab/static/js/src/config/key_map.js`
- Create: `lab/static/js/src/config/instruments_map.js`

**Detail:** `docs/` — see Gemini plan at `.gemini/antigravity-ide/brain/7dc2c4da-9e59-464a-95bc-5648531b40ee/implementation_plan.md` Phase 1.

- [x] Create `key_map.js` with UMD wrapper — zero deps, pure data.
- [x] Create `instruments_map.js` with UMD wrapper — zero deps, pure data.
- [x] Convert `general.js` from `define({...})` to `define(['app/config/key_map'], function(keyMap) { return {...}; })` and remove inline `keyMap` literal.
- [x] Convert `instruments.js` from `define({...})` to `define(['app/config/instruments_map'], function(instrumentsMap) { return {...}; })` and remove inline `instrumentMap` literal.
- [x] Fix `chordal_umto_staff_distribution.test.js` vm mock to handle both AMD data-object and factory `define` forms.
- [x] Run full JS test suite — 34/34 passed.
- [ ] Run `pytest apps/exercises/tests/`
- [ ] Browser smoke: teacher workspace and student player load without RequireJS `enforceDefine` errors.

---

## Deferred Tasks

- Split `exercise_definition.js` after Python view refactors are stable.
- Split `exercise_context.js` after student view helpers are extracted.
- Split `analyze.js` only after reading `docs/music-theory-canon.md` and adding characterization tests. Audit Config/KEY_MAP closure deps before extracting any function — see Phase 2 notes in Gemini plan.
- Split `music_controls.js` and `stave_notater.js` after pure model and analysis modules are under test. Confirm VexFlow interface contract and CSRF handling before Phase 3.
- Defer `models.py`, `forms.py`, `umto_factory.py`, and `apps/teacher/views.py` until directly related feature work requires them.
