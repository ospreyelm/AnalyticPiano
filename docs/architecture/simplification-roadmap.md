# Architecture Simplification Roadmap

Durable source of truth for the ongoing architecture-simplification effort.
Captures the debt inventory, prioritization, and per-item status so any
agent or contributor can pick up the next item in a fresh context without
re-deriving the assessment.

Companion docs:
- [Engineering principles](engineering-principles.md) — the rules this effort applies.
- [Redundancy analysis report](../redundancy_analysis_report.md) — the pre-existing debt inventory.
- Per-item plans live in [`docs/superpowers/plans/`](../superpowers/plans/).

## How to use this

1. Pick the next open item by priority.
2. In a fresh context, read this doc + the relevant plan/spec + `AGENTS.md`.
3. Implement in an isolated worktree/branch; verify (tests; browser for UI work).
4. Open a PR (`--repo avnerdorman/HarmonyLab --base master`).
5. Update the item's Status line here + the Claude memory pointer after merge.

## Debt inventory

| # | Debt | Evidence |
|---|---|---|
| 1 | Three overlapping apps for course/exercise delivery (`lab`, `student`, `dashboard`, `teacher`) | `lab/views.py` still owns live routes (`playlists/`, `courses/`, `exercises/add/`, `skill-map/`) despite being labeled a compatibility surface |
| 2 | Root-directory junkyard | ~30 stray tracked files (scratch scripts, output artifacts, dumps, curriculum binaries) — largely addressed by P1 |
| 3 | Management-command sprawl (58 commands) | many one-shot backfills/generators; AGENTS.md forbids new one-off batch scripts |
| 4 | Cross-language algorithm duplication (Python ↔ JS) | figured-bass abbreviation, key normalization, pitch→MIDI, duration scale — each maintained in two languages |
| 5 | `player.html` runtime DOM surgery | 2 childList MutationObservers + 2 attribute observers + 1 capture-phase click interceptor (~130 lines) compensating for AMD modules rendering the wrong layout |
| 6 | Oversized modules | `models.py` 1578, `forms.py` 1327, `student/views.py` 1326, `umto_factory.py` 1321, `teacher/views.py` 985, `lab/views.py` ~810 |
| 7 | Half-migrated JS stack | Vite + AMD/require.js coexist; vendored jquery/jquery-ui/raphael/Tone/lodash; both `.min` and full versions shipped |
| 8 | Incomplete UMTO migration | legacy `chorale`/`chorale_identification`/raw-CIR shapes frozen; serialization fallbacks remain without removal conditions |
| 9 | Worktree/branch sprawl | 19 worktrees + 60+ stale local branches — largely addressed by P1 |

## Prioritization (impact ÷ effort)

### P1 — repo hygiene (low risk, immediate signal-to-noise)
- **#2 root junkyard** — Status: PR #185 **OPEN** (not yet merged). Removed 13 unreferenced files, moved 10 planning notes to `docs/research-notes/`, hardened `.gitignore`.
- **#9 worktree/branch prune** — Status: DONE locally (19 → 2 worktrees; 25 merged branches deleted). Not part of PR #185 (local-only git state). ⚠️ `master-run` deploy worktree was on `test/harmonization-pipeline-coverage` (12 commits ahead, dirty) — verify branch before any `fly deploy`; see Claude memory `project_master_run_deploy_branch`. `stash@{0}` holds rescued figured-bass code.

### P2 — localized, high fragility-per-line or backbone extraction
- **#6 service extraction** — Status: PARTIAL. `generate_exercise_context` extraction COMPLETE (PR #186 merged; `apps.exercises.services.exercise_context` is sole authority; `lab.views` shim deleted). Next extraction candidates: selection/progress logic out of `student/views.py` (1326 LOC) or `lab/views.py`; cohesive behavior out of `models.py` (1578) / `forms.py` (1327). JS-side `exercise_context_*_logic` module extractions are landing on master separately — coordinate.
- **#5 player.html observer removal** — Status: PARTIAL (Phase A done, PR pending). Fix at source: the AMD/ESM components now render into `#ident-toolbar-slot` / `#s-answer-bar` directly via `lab/static/js/src/components/music/identification_layout_targets.js` (slot-aware, falls back to `#identification-actions` for the legacy `lab/templates/exercise.html`). Phase A deleted the 2 childList relocation observers from `apps/student/templates/student/player.html` (net −~50 LOC). Phase B (deferred): the capture-phase submit interceptor + the 2 `syncTextFieldDisabled` attribute observers remain — behavioral, move text-field commit into the submit flow + set `.text-id-field` disabled at mode-toggle time. Needs browser verification (run via `/run-harmonylab`).
- **#3 command archiving** — Status: NOT STARTED. `list_exercise_generators.py` CATALOG registers ~43 sanctioned generators; 15 unregistered = one-shot/legacy candidates. "Archiving" a Django command = deletion (can't move out of `commands/` without breaking `manage.py`). Low safe value without the service-extraction half (commands should call services, not own the only impl — overlaps #6).

### P3 — biggest payoff, depends on #6
- **#1 lab app retirement** — Status: NOT STARTED. Audit which `lab` routes still have callers; migrate live ones into `student`/`dashboard`/`teacher` services; shrink `lab/views.py` to redirects. Blocked until enough business logic lives in services (#6). Largest single debt thread.

### P4 — largest effort, defer
- **#7 JS stack unification (AMD → Vite/ESM)** — Status: IN FLIGHT (memory: lodash vendored-1.1.1 alias, strict-mode-global ReferenceErrors). Finish the migration or explicitly freeze it; both paradigms currently maintained.

### Cross-cutting, schedule alongside related work
- **#4 cross-language dedup** — pick single source of truth per algorithm (backend derives → emits JSON, or pure JS module with Python-verified `theory_golden/` golden tests). Touched when modifying figured-bass / key-normalization / pitch code.
- **#8 UMTO backfill completion** — backfill legacy rows to UMTO or document retention policy, then delete fallback paths. Each fallback without a removal condition = permanent debt.

## Status legend
- NOT STARTED / PARTIAL / IN FLIGHT / DONE / PR #N (OPEN|MERGED)

## Done so far
- PR #186 (MERGED): `generate_exercise_context` service extraction — `lab.views` compat shim removed.
- P1 local cleanup (not a PR): 15 stale worktrees pruned, 25 merged branches deleted, real figured-bass code rescued to `stash@{0}`.
- PR #185 (OPEN): root junkyard + `.gitignore` hardening + planning notes relocation.
- #5 Phase A (pending PR): `identification_layout_targets.js` slot-aware mount helper; 2 childList relocation observers removed from `player.html`. Capture-phase submit interceptor + 2 `syncTextFieldDisabled` attribute observers deferred to Phase B.