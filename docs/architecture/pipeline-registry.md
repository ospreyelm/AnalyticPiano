# Exercise Pipeline Registry

## Purpose

HarmonyLab/Monteverdi ships six student-facing exercise "pipelines" through one
uniform URL (`s/units/<n>/play/`). The per-type split is **data-driven**
(`exercise.data["type"]` / `["mode"]` / `["analysisType"]` / `staffDistribution`),
not URL-driven. This registry is the human-readable map of which file belongs to
which pipeline, so an agent (or human) editing one pipeline can see what is safe
to touch and what is shared.

Owner tags:

| Tag | Meaning |
|---|---|
| `matching` | Legacy exact-match pipeline (`type=matching`) |
| `chorale` | Chorale family: playback / analysis_match / play-all-voices / analysis, or `type=chorale`/`umto_chorale` without ident/harm mode |
| `harmonization` | `mode=harmonization` on `umto_chorale` |
| `figured_bass` | Legacy `type=figured_bass` / `figured_bass_pcs` |
| `identification` | Legacy non-chorale `type=identification` |
| `chorale_identification` | `type=chorale_identification`, or `umto_chorale` with `mode=identification`/`chorale_identification` |
| `shared-base` | Cross-pipeline lifecycle / definition / context (the parts Phase 3 splits out of `exercise_sheet.js`) |
| `low-level` | Render-stack primitives (VexFlow + legacy stave); shared by all pipelines that use the stack |
| `teacher-tool` | `/teacher/play/` authoring surface — strictly teacher, not student-facing, not part of the 6-pipeline split |
| `python-shared` | Backend exercise-data preparation; not pipeline-specific unless noted |

The authoritative pipeline discriminator is
`lab/static/js/src/models/resolved_mode.js` (`resolvePipeline(exercise)`).
Raw `type`/`mode`/`analysisType`/`staffDistribution` strings must not be read
outside the resolver (Phase 1 will enforce this).

## Student delivery path (all pipelines share this)

| File | Role |
|---|---|
| `apps/student/urls.py` | `s/units/<n>/play/` → `student:player` |
| `apps/student/views.py` (`PlayerView`) | Sets `app_module = "app/components/app/exercise"`, renders `student/player.html` |
| `apps/student/templates/student/player.html` | RequireJS entry template; falls back to `qa_player.html` only for `umto_symbolic_meter`/`umto_barline_placement` |
| `lab/static/js/src/main.js` | Bootstrapper: reads `app_module`, dispatches |
| `lab/static/js/src/components/app/exercise.js` | App module: grader selection (L119-151), sheet instantiation (L408-439). Shared wiring today; Phase 2 rewrites grader selection via `GraderFactory`, Phase 3 rewrites sheet instantiation via `SheetFactory` |

## Teacher-authoring path (teacher-tool — NOT student-facing)

Confirmed separate from all student `/s/units/.../play/` traffic. Auth-guarded:
anonymous → login redirect; authenticated non-teacher → `/s/` redirect
(`apps/teacher/middleware.py`).

| File | Role |
|---|---|
| `lab/urls.py` | `teacher/play/` → `lab:play` `PlayView` |
| `lab/views.py` (`PlayView`) | `requirejs_app = "app/components/app/play"` |
| `lab/templates/play.html` | Teacher import UI template |
| `lab/static/js/src/components/app/play.js` | `AppPlayComponent` → `PlaySheetComponent` |
| `lab/static/js/src/components/music/play_sheet.js` | Legacy stave by default; VexFlow only with `?newvf` or MusicXML corpus payload |
| `lab/static/js/src/components/music/play_note_factory.js` | Wraps `StaveNoteFactory` for teacher play |
| `apps/teacher/urls.py` | `play/api/...` teacher-only endpoints |
| `apps/teacher/middleware.py` | `TeacherAccessMiddleware` — bounces non-teachers |

Shared with student pipelines only at the low-level `Stave`/`StaveNoteFactory`
primitive layer. Not part of the 6-pipeline split.

## Resolver (single source of truth — new)

| File | Role |
|---|---|
| `lab/static/js/src/models/resolved_mode.js` | `resolvePipeline(exercise)` → frozen `{pipeline, exerciseType, interactionMode, analysisKind, staffStyle, stack, isChorale, isChoraleIdentification, isHarmonization, isAnalysisMatch, isIdentification, isSymbolicMeter}`. Mirrors current predicates exactly. No production callers yet. |
| `lab/static/js/src/models/resolved_mode.test.js` | Resolver characterization: all 6 pipelines + "play" default-fill finding + out-of-scope + null safety |

## Definition + predicates (`shared-base`, to read `ResolvedMode` in Phase 1)

| File | Role |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | `isChorale()` (L667), `isChoraleIdentification()` (L679), `isHarmonization()` (L709), `isAnalysisMatch()` (L719), `isIdentification()` (L735), `getMode()` (L659), default-mode fill `"play"` (L893), `getInputMethod()`/`usesNoteEntry()` (L744/756) |
| `lab/static/js/src/models/input_method_logic.js` | `resolveInputMethod()` — single source of truth for input method. Not a collision. |

## Sheet (Phase 3 split target — currently `shared-base` with one fork)

| File | Owner | Notes |
|---|---|---|
| `lab/static/js/src/components/music/exercise_sheet.js` | `shared-base` | Sheet root; mixes in staves/playback/status/identification. Phase 3 splits into `BaseExerciseSheet` + per-pipeline sheets. |
| `lab/static/js/src/components/music/exercise_sheet_staves.js` | `shared-base` (fork) | The `isChoraleLike && hasMeasures` fork at L45. Phase 3 deletes it; each pipeline sheet owns its render stack. |
| `lab/static/js/src/components/music/exercise_sheet_playback.js` | `chorale` | Playback component |
| `lab/static/js/src/components/music/exercise_sheet_status.js` | `shared-base` | Status bus; mode-gated branches L314-318 (Phase 1 routes through `ResolvedMode`) |
| `lab/static/js/src/components/music/exercise_sheet_identification.js` | `identification` + `chorale_identification` + `figured_bass` | Shared overlay |
| `lab/static/js/src/components/music/exercise_sheet_identification_logic.js` | `identification` + `chorale_identification` + `figured_bass` | Shared |
| `lab/static/js/src/components/music/exercise_sheet_identification_canvas.js` | `identification` + `chorale_identification` + `figured_bass` | Shared |
| `lab/static/js/src/components/music/exercise_sheet_identification_controls.js` | `identification` + `chorale_identification` + `figured_bass` | Shared |
| `lab/static/js/src/components/music/exercise_sheet_identification_input_mode.js` | `identification` + `chorale_identification` + `figured_bass` | Shared |

## Render stacks (`low-level`)

VexFlow stack — used by `chorale`, `harmonization`, `chorale_identification`:

| File | Role |
|---|---|
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | VexFlow entry |
| `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js` | Adapter logic |
| `lab/static/js/src/components/music/rendering/vexflow_tickable_builder.js` | Builds Vex.Flow tickables (replaces `StaveNoteFactory` for this stack) |
| `lab/static/js/src/components/music/rendering/vexflow_render_config.js` | Layout config driven by `staffDistribution` |
| `lab/static/js/src/utils/umto_score_converter.js` | UMTO → processed score (VexFlow stack input) |

Legacy stave stack — used by `matching`, `figured_bass`, `identification`:

| File | Role |
|---|---|
| `lab/static/js/src/components/music/stave.js` | `Stave` class |
| `lab/static/js/src/components/music/stave_note_factory.js` | `StaveNoteFactory` base (also subclasses by `ExerciseNoteFactory`/`PlayNoteFactory`) |
| `lab/static/js/src/components/music/exercise_note_factory.js` | Wraps `StaveNoteFactory` for student exercises |

Cross-stack:

| File | Role |
|---|---|
| `lab/static/js/src/components/music/stave_notater.js` | Analysis annotations; used by both stacks (VexFlow bridge + legacy) |

## Graders (Phase 2 split target)

| File | Owner | Notes |
|---|---|---|
| `lab/static/js/src/models/exercise_grader.js` | god-class (to split) | `notesMatch` (matching), `figuredBassMatch`/`figuredBassPcsMatch` (figured_bass), `analysisMatch` (analytical + latent umto_chorale+analysis_match), `analysisPcsMatch` (analytical_pcs). Switch at L135. Phase 2 extracts each to standalone grader; decommissions this file. |
| `lab/static/js/src/models/chorale_grader.js` | `chorale` | Selected by `app/exercise.js:131` for playback/analysis_match |
| `lab/static/js/src/models/identification_grader.js` | `identification` + `chorale_identification` | Same class, discriminator on type/mode |
| `lab/static/js/src/models/harmonization_grader_logic.js` | `harmonization` | Pure-function module; called from `ExerciseGrader.grade()` L138 today |

Phase 2 adds: `grader_factory.js`, `grader_state.js`, `legacy_match_grader.js`,
`legacy_figured_bass_grader.js`, `analysis_match_grader.js`, `analytical_grader.js`,
`analytical_pcs_grader.js`.

## Models + logic

| File | Owner | Notes |
|---|---|---|
| `lab/static/js/src/models/chord.js` | `shared-base` | `staffDistribution` axis (L535, L700, L709) — layout, not type |
| `lab/static/js/src/models/exercise_context.js` | `shared-base` | Mode-gated reads L246-247, L391, L598 (Phase 1 routes through `ResolvedMode`) |
| `lab/static/js/src/models/harmonization_realization_logic.js` | `harmonization` | |
| `lab/static/js/src/models/harmonization_targets_logic.js` | `harmonization` | |
| `lab/static/js/src/components/music/chordal_umto_staff_distribution.js` | `shared-base` | Layout axis |
| `lab/static/js/src/config/figured_bass_hints.js` | `figured_bass` + `chorale_identification` | Figured-bass hint config |
| `lab/static/js/src/config/figured_bass_hints_data.js` | `figured_bass` + `chorale_identification` | |
| `lab/static/js/src/widgets/staff_distribute.js` | `shared-base` | UI picker for `staffDistribution` |

## Python (`python-shared` unless noted)

| File | Role | Notes |
|---|---|---|
| `apps/exercises/forms.py` | `TYPE_*`/`MODE_*`/`DISTRIBUTION_*` constants | L455-496. `TYPE_CHORALE` and `DISTRIBUTION_CHORALE` both equal `"chorale"` — collision (Phase 4, deferred). Phase 1 narrows: only delivery-behavior reads go through `resolve_pipeline()`. |
| `apps/exercises/umto.py` | `InteractionMode` enum (L15-19), `HarmonizationTargetPolicy.source` (L127) | `"figured_bass"` overload: enum value vs policy source vs field name (Phase 4) |
| `apps/exercises/services/exercise_context.py` | Server-side mode reads (L238-371) | Phase 1 routes through `resolve_pipeline()` |
| `apps/exercises/utils/teacher_play_modes.py` | Teacher-play-mode → `InteractionMode` resolution | Phase 1 routes through `resolve_pipeline()` |
| `apps/exercises/harmonization/targets.py` | `harmonization` | Server-side target derivation; `figured_bass` field-name reads (L81-82, L203, L287-288) |
| `apps/dashboard/views/api_workbench.py` | Workbench `target_type` map | Workbench axis (Phase 4) |
| `apps/student/views.py` | `PlayerView` delivery | Phase 1 routes mode reads through `resolve_pipeline()` |

Phase 1 adds: `apps/exercises/services/resolved_mode.py` (Python port).

## Out of scope for the 6-pipeline split

- `umto_symbolic_meter`, `umto_barline_placement`, `umto_key_signature`,
  `musicxml`, `analytical`, `analytical_pcs` → `resolvePipeline` returns
  `"other"`. Handled by caller; not part of M1.
- `umto_identification` (`apps/exercises/forms.py:458`,
  `TYPE_UMTO_IDENTIFICATION = "umto_identification"`) — teacher-selectable type,
  but `exercise_definition.js` parse() has no branch for it and no predicate
  recognizes it, so `resolvePipeline` returns `"other"`. Currently unresolved;
  add a parse branch or accept "other" deliberately (open question for Phase 1).
- `/teacher/play/` teacher-authoring surface (see above).
- URL/template split per type — uniform URL is correct; mode is data, not route.
- `chorale_identification` type↔mode alias — intentional, kept explicit in
  resolver.

## Known divergences + open questions (recorded 2026-07-05, pre-push review)

1. **`mode="chorale_identification"` literal on `umto_chorale`** —
   `grader_factory.js` maps pipeline `chorale_identification` →
   `IdentificationGrader` (predicate intent), but current production
   `app/exercise.js:119-127` does NOT route this literal to
   `IdentificationGrader`; it falls through to `ExerciseGrader`/`notesMatch`.
   **DB query (2026-07-05): 0 rows carry `mode="chorale_identification"` (any
   type).** The divergence is confirmed NOT LIVE in current data. Current-gen
   UMTO uses `mode="identification"` (the `InteractionMode` enum has no
   `chorale_identification` member). Mapping left as predicate-intent;
   downgraded from "must resolve before wiring" to "guard against future data."
   If a future import writes `mode="chorale_identification"`, revisit. See the
   CAVEAT in `grader_factory.js`.
2. **`mode="play"` on `umto_chorale`** — once `parse()` default-fills
   `exercise.mode = "play"` (or a row stores it explicitly), `isChorale()`
   returns false (truthy mode → mode check → "play" not in the chorale mode
   list; type fallback never runs). **DB query (2026-07-05): 9 persisted rows
   carry `type="umto_chorale" AND mode="play"` (out of 79,596 total; 0
   `type=chorale` rows exist).** These 9 resolve to pipeline `"other"` +
   legacy-stave, NOT `"chorale"` — almost certainly a latent bug (umto_chorale
   exercises expect the VexFlow stack + a chorale grader). Production follows
   the same predicates: `ExerciseGrader`/`notesMatch` + legacy-stave render.
   `resolvePipeline` mirrors this faithfully. A characterization test in
   `resolved_mode.test.js` locks the current resolver output for this live
   case. Do NOT "fix" in the resolver without: (a) a decision that these 9
   should route as chorale, (b) a DB backfill of the 9 rows, and (c) a new
   snapshot proving the desired behavior. See the NOTE in `resolved_mode.js`.
3. **`type="umto_identification"`** (`forms.py:458`, `TYPE_UMTO_IDENTIFICATION`)
   — teacher-selectable but `exercise_definition.js` parse() has no branch for
   it and no predicate recognizes it, so `resolvePipeline` returns `"other"`.
   **DB query: 0 rows.** Not live. Add a parse branch or accept "other"
   deliberately (open question for Phase 1).

## Status (2026-07-05)

- Phase 0.3 done: `resolved_mode.js` + test committed (`0a85f0a5`). No production
  callers.
- Phase 0.2 done: this registry doc (`0a14d06a`).
- Phase 2 skeleton done: `grader_factory.js` + test (`d3e00aec`). `create()` is
  a stub; no production call sites wired.
- M1 = Phases 0+1+2 (resolver + grader factory). Full boot-path/render snapshots
  deferred to Phase 3's screenshot harness.
- `./run_js_tests.sh` has 9 pre-existing `app/` alias failures reproduced on
  main — NOT caused by this refactor. M1 tests are import-free/relative-only.
- Phase 3 (sheet split) is a separate project. Phase 4 (stored-string
  disambiguation) deferred.