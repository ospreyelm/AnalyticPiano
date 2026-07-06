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
| `lab/static/js/src/components/app/exercise.js` | App module: grader selection, sheet instantiation. **Phase 2 (2026-07-05): grader selection now routes through `GraderFactory.create()` for the chorale and identification branches** (guarded; see "Phase 2 consolidated status" below), with the `else`/legacy branch and harmonization still constructing inline. Phase 3 rewrites sheet instantiation via `SheetFactory` |

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
| `lab/static/js/src/models/exercise_grader.js` | god-class (audit done, extraction paused; documented as retained legacy fallback — see header comment) | `notesMatch` (matching), `figuredBassMatch`/`figuredBassPcsMatch` (figured_bass), `analysisMatch` (analytical + latent umto_chorale+analysis_match), `analysisPcsMatch` (analytical_pcs). Switch on `exerciseType`. **2026-07-05 usage audit (see "Legacy grader retirement audit" below): none of these methods are exercised by reachable student content today.** The `mode==="harmonization"` case in the same switch is ALSO dead — live harmonization grading is owned by `ExerciseContext.computeHarmonizationGraded()`, which never calls `this.grader.grade(...)` for harmonization exercises. Per-type standalone extraction is paused pending a product decision; likely shape is one retained legacy fallback class, not five polished classes — see the audit's recommendation. |
| `lab/static/js/src/models/chorale_grader.js` | `chorale` | **Live production caller (2026-07-05):** `app/exercise.js`'s chorale branch constructs via `GraderFactory.create(resolved, { definition })` when `resolveGraderKey(resolved) === "chorale"`, else falls back to the exact pre-Phase-2 inline construction — a code-review-added guard against the `type="chorale_identification"` divergence (see "First production caller wired" below; 0 rows today, frozen type, but no live risk was assumed). Cannot be constructed via the test injection seam's fallback path under plain `node` — this file imports `app/components/music/score_timeline` (webpack-only alias) — but tests inject a fake `constructors.ChoraleGrader` instead, and the real class was confirmed to load and construct correctly in a real browser smoke test (network log shows the actual 126KB file fetched via the lazy `require()`). |
| `lab/static/js/src/models/chorale_grader_settings.js` | `chorale` | New (2026-07-05). Pure helper: `resolveChoraleGraderSettings(definition)` mirrors `app/exercise.js:145-148`'s `definition.getGrading()` + Unit-1 `octaveIndependent` override exactly, including the mutate-in-place quirk (`getGrading()` can return the definition's own stored grading object). No `app/` imports — fully testable under plain `node` (`chorale_grader_settings.test.js`), independent of the `chorale_grader.js` alias problem. |
| `lab/static/js/src/models/identification_grader.js` | `identification` + `chorale_identification` | Same class, discriminator on type/mode. **Live production caller (2026-07-05, guarded):** `app/exercise.js`'s identification branch calls `GraderFactory.create()` (always with `{}`, matching `app/exercise.js:135`) ONLY when `resolveGraderKey(resolved) === "identification"` — otherwise constructs directly, unchanged. The guard exists because out-of-scope types with `mode="identification"` (`umto_barline_placement`: 26,491 rows, `umto_key_signature`, `umto_symbolic_meter`) resolve to `"legacy_exercise"`, which `create()` throws for; see "First production caller wired" below. |
| `lab/static/js/src/models/harmonization_grader_logic.js` | `harmonization` | Pure-function module; called from `ExerciseGrader.grade()` L138 today, and from `harmonization_runtime_grader.js` (the live path, see PR A below) |
| `lab/static/js/src/models/harmonization_grader.js` | `harmonization` | Wraps `HarmonizationGraderLogic.harmonizationMatch` with the per-problem result-shape assembly and aggregate worst-state-wins scoring that `ExerciseGrader.grade()` does inline for the harmonization branch (grader.js:152-166, 210-227). **Now production-interface compatible (2026-07-05):** `grade(definition, inputChords)` matches `ExerciseContext`'s real call site (`this.grader.grade(this.definition, this.inputChords)`) — reproduces the definition/inputChords → problems/delivered-notes extraction (Set-dedupe, dummy-MIDI-109 strip, `isChorale`/empty-problems early-return guard) then delegates to the pure array-based `gradeProblems(problems, deliveredNotesPerProblem)` (renamed from `grade`, kept for standalone testing). Still NOT wired into `app/exercise.js` or `GraderFactory.create()` — production still constructs `ExerciseGrader` for harmonization, which delegates internally to `HarmonizationGraderLogic` exactly as before. Preserves the `count`/`notes`-undefined quirk (harmonizationMatch's return has no such keys) rather than fixing it. Uses the shared `grader_state.js` STATE object directly (no local copy). Tested standalone in `harmonization_grader.test.js` (plain `node`, pure CommonJS, no `app/` alias) — including characterization tests for the `grade(definition, inputChords)` adapter hand-traced against `exercise_grader.js`'s actual source (that file can't be `require()`'d under plain `node` to run a live A/B comparison — same `app/`-alias wall as `chorale_grader.test.js`). `GraderFactory.create()` can construct the class (2026-07-05), but nothing calls `create()` in production yet. **Not the live path — see PR A below; do not confuse with `harmonization_runtime_grader.js`.** |
| `lab/static/js/src/models/harmonization_runtime_grader.js` | `harmonization` | **PR A (2026-07-06): the live runtime harmonization grading path**, extracted mechanically from `ExerciseContext.computeHarmonizationGraded(activeMidi)` (the stateful, single-target-at-a-time implementation that actually runs in production — distinct from the `HarmonizationGrader`/`ExerciseGrader.grade()` dead-code path above). Exports `computeHarmonizationGraded(ctx, activeMidi)`: a byte-for-byte relocation of the prior inline method body, with `this.` → `ctx.`. State (`_harmonizationPointer`, `acceptedHarmonizationSonorities`, `_harmonizationRejected`) stays on the `ExerciseContext` instance — 6 external components (`components/music.js`, `components/input/click_note.js`, `exercise_sheet_playback.js`, `exercise_sheet_staves.js`, `exercise_sheet_status.js`, `components/app/exercise.js`) read/write those fields directly — so the module mutates the ctx passed in rather than owning its own state. Uses shared `grader_state.js` STATE instead of `ctx.grader.STATE` (proven behavior-identical: `exercise_grader.js:58` aliases `ExerciseGrader.STATE` to the same shared object). `ExerciseContext.computeHarmonizationGraded` now delegates: `return HarmonizationRuntimeGrader.computeHarmonizationGraded(this, activeMidi)`. No behavior change. Tested in `harmonization_runtime_grader.test.js` (plain `node`): empty/null activeMidi, correct/partial/incorrect per-target transitions, all-done-then-incorrect quirk, measureIndex/onset math, result shape, STATE identity — quirks (partial counts as accepted; all-done-then-incorrect still fires rejected+feedback side effects) locked as-is, not fixed. Browser-smoke-verified: harmonization exercise (Unit 9, playlist `PA03SM`) loads with the new import wired, app mounts (`#staffwrapper` + canvas), zero console/network errors. |

Phase 2 added: `grader_factory.js`, `grader_state.js`, `harmonization_grader.js`
(harmonization-only isolation wrapper, not yet wired). The originally-planned
`legacy_match_grader.js`/`legacy_figured_bass_grader.js`/
`analysis_match_grader.js`/`analytical_grader.js`/`analytical_pcs_grader.js`
split is paused pending the 2026-07-05 usage audit below — recommendation is
one retained legacy fallback class instead of five.

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

## Phase 1.2 audit: staff-distribution axis (recorded 2026-07-05)

`chord.js`, `stave_note_factory.js`, `chordal_umto_staff_distribution.js`,
`vexflow_render_config.js`, `umto_score_converter.js`, and
`staff_distribute.js` were audited as the staff-distribution-axis segment of
Phase 1.2. **No code change made** — grep confirms none of the six hold an
`ExerciseDefinition` reference, a `definition.exercise.type`/`.mode` read, or
a `getMode()`/`isChorale()`-style predicate call:

- They consume an already-extracted plain `staffDistribution` string passed
  in via settings/config (`Chord.settings.staffDistribution`,
  `StaveNoteFactory`'s `this.chord.settings.staffDistribution`,
  `vexflow_render_config.js`'s `opts.staffDistribution`/`cfg.meta.staffDistribution`),
  or via raw UMTO score-authoring metadata (`umto_score_converter.js`'s
  `meta.staffDistribution`, sourced from the score JSON, not the exercise
  definition object).
- `chordal_umto_staff_distribution.js`'s `routeChordMidis(midis,
  staffDistribution)` is a pure function taking the axis value as a
  parameter — same shape as `input_method_logic.js` (Phase 1.2's earlier
  input-method segment): nothing to route inside a pure fields-in function,
  and its local constants (`KEYBOARD_FAMILY`, threshold values) are
  staff-distribution-axis constants, not pipeline discriminators.
- The upstream extraction points (`ExerciseDefinition.getStaffDistribution()`,
  `definition.staffDistribution` reads in `components/app/exercise.js` and
  `models/exercise_context.js`) were already covered by earlier Phase 1.2
  segments where relevant (`exercise_context.js` routed in the
  model/context segment; the `getStaffDistribution()` accessor itself is a
  passthrough to `this.exercise.staffDistribution`, not a pipeline
  discriminator — `staffDistribution` is a distinct axis from `pipeline`,
  see `resolved.staffStyle` in `resolved_mode.js`, which mirrors but does
  not replace it).

Conclusion: this segment required no commit. Move to Phase 1.3.

## Phase 1.3: ESLint guard against raw pipeline-discriminator comparisons (2026-07-05)

`eslint-rules/no-raw-pipeline-discriminator.mjs` is a custom ESLint rule
registered as `harmonylab-pipelines/no-raw-pipeline-discriminator` in
`eslint.config.mjs` and enabled under `npm run lint`. It flags the four
pipeline-discriminator comparison shapes (per the Phase 1.3 plan) outside the
resolver/factory/axis modules:

- `<expr>.type === "<discriminator>"` / `.mode` / `.analysisType` (non-computed)
- `<expr>["type"] === "<discriminator>"` / `["mode"]` / ... (computed access)
- `getMode() === "<discriminator>"` (bare call or `*.getMode()` method call)
- `<expr>.get("mode") === "<discriminator>"` / `.get("type")` / ... (Backbone-style accessor)
- `staffDistribution === "<discriminator>"` (bare identifier or field access)

with `==` / `===` / `!=` / `!==` operators. The discriminated value set is the
six-pipeline routing literals (sourced from `resolved_mode.js`'s
`CHORALE_MODES` / `CHORALE_IDENTIFICATION_MODES` / `CHORALE_TYPES` /
`FIGURED_BASS_TYPES` plus `"matching"`, `"identification"`, and the `"play"`
default-fill). Out-of-scope "other" types (`umto_symbolic_meter`,
`umto_key_signature`, `umto_barline_placement`, `musicxml`, `analytical`,
`analytical_pcs`) are intentionally NOT in the set — `resolvePipeline` maps them
to `"other"` and the caller handles them, so reads of them are not banned.

This is NOT a blanket string-literal ban (per the plan's Codex correction):
analysis-family content strings, `.includes(...)` membership tests, UMTO storage
keys, and taxonomy labels are not matched. `exercise_grader.js`'s analysis-family
content strings (analysisBool's `supported` array, `abbrev_thoroughbass` /
`full_thoroughbass`, etc.) are case-body content, not `===` comparisons against a
field access, so they are not flagged.

### File allowlist (raw strings authoritative by design)

The rule self-skips these files (`ALLOWED_PATH_SUFFIXES` in the rule):

| File | Reason |
|---|---|
| `models/resolved_mode.js` | The resolver; raw strings are authoritative here (Phase 1.3 exception #1). |
| `models/grader_factory.js` | Maps off `resolved.pipeline`, not raw strings (exception #2). |
| `models/exercise_definition.js` | `parse()` + helpers CONSTRUCT the data `ResolvedMode` consumes; routing these reads would be circular. Definition/parse axis. |
| `models/input_method_logic.js` | Confirmed-pure input-method axis module (exception #6). |
| `models/harmonization_targets_logic.js` | Pure harmonization-axis module (local `getMode`/`isHarmonization` helpers, no `ExerciseDefinition` reference) — same shape as `input_method_logic.js`; local axis literal kept. |
| `models/chord.js` | Confirmed-pure staff-distribution axis consumer (Phase 1.2 audit). Reads only the uppercase `STAFF_DISTRIBUTION` alias from `Config.get("general.staffDistribution")` — zero type/mode/`getMode` reads. Same axis as `chordal_umto_staff_distribution.js`. Its comparisons use the `STAFF_DISTRIBUTION` alias, which the rule's bare-identifier branch (case-sensitive to `staffDistribution`) does not match; allowlisting is the honest classification (axis consumer) rather than relying on the alias escaping the AST match. |
| `components/music/chordal_umto_staff_distribution.js` | Confirmed-pure staff-distribution axis module (exception #6). |
| `**/*.test.js` | Tests exercise raw strings by intent. |

### Inline `eslint-disable-next-line` exemptions (permanent, behavior-preserving)

Three sites are NOT allowlisted but carry a documented inline suppression because
routing them would change behavior (proven by the dedicated reviewer passes in
prior Phase 1.2 commits):

1. `components/app/exercise.js` chorale-play gate first clause —
   `definition.mode === "playback"` (Phase 1.2 commit `2ba7c0f9`, exception #3).
   `parse()` overrides `exercise.mode` for `type=identification` /
   `chorale_identification`, so `resolved.interactionMode` would diverge from the
   raw config mode. DB query: 0 rows carry that type/mode pairing, so the
   divergence is theoretical, but the raw clause is preserved rather than
   silently changing the gate. Second clause IS routed through `resolved.isChorale`.
2. `components/music/exercise_sheet_identification_logic.js`
   `_supportsTextInputMode` — `definition.exercise.type === "umto_chorale"`.
   Routing to `resolved.isChorale` would widen the gate from `type=umto_chorale`
   to legacy `type=chorale` (behavior change). Raw guard preserved per Phase 1.2
   no-behavior-change constraint; full routing deferred.
3. `components/music/stave_note_factory.js` `CHORALE_FORMAT` —
   `this.chord.settings.staffDistribution === "chorale"`. The literal `"chorale"`
   here is `DISTRIBUTION_CHORALE` (a layout-axis value, `forms.py:496`), NOT
   `TYPE_CHORALE` (a pipeline type, `forms.py:455`). Staff-distribution axis
   consumer, audited pure above. No `ResolvedMode` field removes this layout
   literal (`resolved.staffStyle` mirrors but does not replace the axis value).

### `exercise_context.js` error_tally (exception #4 — not flagged)

`["analytical", "figured_bass"].includes(this.definition.exercise.type)` is a
`.includes()` CallExpression, not a `===` BinaryExpression, so the rule does not
match its shape. It is also a reporting-semantics grouping, not pipeline routing
(documented inline at `exercise_context.js:601-608`). No suppression needed.

### Known limitation: AST-shape match, no dataflow

The rule is AST-shape-based, not dataflow. It matches the five comparison shapes
listed above; it does NOT track local aliases. A raw read aliased through a
local variable escapes the match:

- Uppercase aliases: `chord.js`'s `var STAFF_DISTRIBUTION = Config.get("general.staffDistribution")` then `STAFF_DISTRIBUTION === "chorale"` — not matched (bare-identifier branch is case-sensitive to `staffDistribution`). `chord.js` is allowlisted as a confirmed-pure axis consumer, so this is classification, not escape.
- Local-variable aliases: `var m = definition.exercise.mode; m === "playback"` — not matched. No such site exists in the current codebase outside allowlisted files (verified by the Phase 1.2 reviewer passes + grep). A future agent writing one would escape the rule; a dataflow-tracking rule is out of scope for the plan's AST-lint approach.

### Verification (2026-07-05)

- Permanent regression test: `eslint-rules/no-raw-pipeline-discriminator.test.mjs`
  (run via `node eslint-rules/no-raw-pipeline-discriminator.test.mjs`) locks in
  the rule's contract — 16 banned shapes flagged (the five plan targets +
  `!==`/`!=`/literal-first/deep-chain/`"play"` variants), 12 clean shapes not
  flagged (out-of-scope "other" types, non-discriminator field/value,
  analysis-content literal, `.includes()`, relational/arithmetic operators).
  28 assertions, all green.
- Rule also validated against a temporary in-tree fixture during development
  (6 banned shapes flagged, 5 allowed shapes clean); fixture deleted before
  commit. The permanent `.test.mjs` above replaces it.
- `npm run lint` passes clean on the post-Phase-1.2 codebase with the rule
  enabled (exit 0).
- Resolver + grader + logic tests green: `resolved_mode.test.js`,
  `grader_factory.test.js`, `input_method_logic.test.js`,
  `harmonization_grader_logic.test.js`.

## Legacy grader retirement audit (recorded 2026-07-05)

Before extracting `ExerciseGrader`'s per-type methods (`notesMatch`,
`figuredBassMatch`/`figuredBassPcsMatch`, `analysisMatch`, `analysisPcsMatch`)
into standalone grader classes, this audit checks whether any of them are
still live in student delivery. Queried against the local dev Postgres DB
(`analyticpiano`, same snapshot used for the prior `mode="play"` / 0-row
`chorale_identification` findings above — total exercise count matches:
79,596 rows), via `psql` (`exercises_exercise`, `exercises_playlist`,
`exercises_exerciseplaylistordered`).

**`Exercise.data->>'type'` distribution — only 5 distinct values exist in the
entire table:**

| `type` | count |
|---|---|
| `umto_chorale` | 53,024 |
| `umto_barline_placement` | 26,491 |
| `identification` | 60 |
| `umto_key_signature` | 18 |
| `umto_symbolic_meter` | 3 |

`matching`, `analytical`, `analytical_pcs`, `figured_bass`,
`figured_bass_pcs`, legacy `chorale`, and `chorale_identification` (as a
`type`) have **zero rows** — not "zero reachable," zero rows at all, of any
provenance. This is consistent with the AGENTS.md non-negotiable rule that
these shapes are frozen for new writes.

**`umto_chorale` mode breakdown** (the only type with modes outside the
resolver's known lists), cross-joined against "reachable in the real student
delivery gate" — `Playlist.is_public = true`, `playlist_family !=
'teacher_play'`, and a `unit:*` tag present (`apps/student/views.py`
`PlayerView.get` requires `user_can_access_playlist()` + a matching `unit:N`
tag; the `Course`/`PlaylistCourseOrdered.publish_date` mechanism is the
unauthorized-for-implementation Assignment Slot Foundation work, not live —
see AGENTS.md "Current product direction" — so it was excluded as a
reachability gate):

| mode | total | in public unit-tagged playlist |
|---|---|---|
| `identification` | 19,059 | 3,312 |
| `playback` | 18,993 | 2,920 |
| `analysis_match` | 14,847 | 214 |
| `harmonization` | 98 | 34 |
| `play` | 9 | 0 |
| `identify` | 6 | 0 |
| `figures` | 6 | 0 |
| `roman` | 6 | 0 |

The `play`/`identify`/`figures`/`roman` modes are three previously
undocumented siblings of the already-characterized `mode="play"` bug (see
"Known divergences" above) — same root cause (`resolveMode()` returns a
truthy string outside `CHORALE_MODES`/`CHORALE_IDENTIFICATION_MODES`, so
`isChorale`/`isChoraleIdentification`/`isHarmonization` are all false and
`resolvePipeline` falls through to `"other"` + legacy-stave). All 27 rows
across the four modes live only in playlists with empty `tags`/`skill_tags`
(no `unit:*`), authored by `factory@monteverdi.app` (teacher role, matches
the "factory seed run" test fixture referenced in the teacher-production-
roadmap work) or the local dev superuser account — i.e. dev/factory-seed
fixtures, not reachable via `/s/units/<n>/play/` regardless of `is_public`.
**Not live student content.**

**Legacy `type="identification"` (60 rows) IS live**: all 60 sit in seven
`is_public=true`, `unit:5`-tagged playlists (`PA03UH`..`PA03UN`, triad/seventh
-chord-quality identification), authored by a real student account. But this
type resolves to `resolvePipeline` pipeline `"identification"`, which
`app/exercise.js`'s inline grader selection already routes to
`IdentificationGrader` — **not** `ExerciseGrader`. Live, but outside the god
class.

**`mode="harmonization"` (98 rows, 34 reachable) does reach `ExerciseGrader`**,
but only as a thin pass-through: `app/exercise.js`'s selection falls to the
`else` branch (no dedicated harmonization branch), constructs
`ExerciseGrader`, and `ExerciseGrader.grade()`'s internal switch immediately
delegates to `HarmonizationGraderLogic` (`harmonization_grader_logic.js`) — a
module already extracted as a pure, standalone, tested unit. None of
`ExerciseGrader`'s own `notesMatch`/`figuredBassMatch`/`analysisMatch` bodies
execute for this mode.

**Conclusion: none of `ExerciseGrader`'s legacy per-type method bodies
(`notesMatch`, `figuredBassMatch`/`figuredBassPcsMatch`, `analysisMatch`,
`analysisPcsMatch`) are exercised by any currently-reachable student
content.** The only genuinely live path through `ExerciseGrader` today is the
harmonization delegate, which is already a separately-owned pure module.
Everything else that reaches `ExerciseGrader`'s legacy switch bodies is
either zero-row (matching/figured_bass/analytical/analytical_pcs) or
dev/factory-seed-only (the 27 odd-mode `umto_chorale` rows).

**Recommendation for Phase 2 shape** (supersedes the "extract each grader
key to a standalone class" framing in the "Graders" table above for the
legacy keys specifically):

- Do not build five polished, permanent legacy grader classes
  (`legacy_match_grader.js`, `legacy_figured_bass_grader.js`,
  `analytical_grader.js`, `analytical_pcs_grader.js`) for code paths with no
  live data — that is new architecture investment in dead code, and product
  direction is to migrate remaining legacy student exercise types to UMTO
  equivalents, not expand legacy surface area.
- Keep `ExerciseGrader` itself (optionally renamed `LegacyExerciseGrader` in
  a dedicated rename-only commit later) as a single retained
  compatibility/fallback wrapper preserving the current switch verbatim,
  rather than splitting it into several named legacy classes.
- Done: `GraderFactory`'s `GRADER_KEYS` now maps `matching` / `figured_bass` /
  `"other"` to one explicit fallback key, `legacy_exercise`, pointing at the
  retained `ExerciseGrader`/`LegacyExerciseGrader`, not several distinct
  legacy classes. `harmonization` stays its own key (live, 34 reachable
  rows) even though its current implementation still constructs
  `ExerciseGrader` as a pass-through to `HarmonizationGraderLogic`.
- The harmonization delegation needs no further extraction — it already
  routes to an isolated pure module; only the dispatch site
  (`app/exercise.js`'s grader selection) would need to change if/when
  `GraderFactory.create()` is wired.
- Do not "fix" the `play`/`identify`/`figures`/`roman` mode-resolution gap
  incidentally while doing this — same standing caveat as the documented
  `mode="play"` case: any behavior change needs its own decision, DB
  backfill/audit of the (dev-only, currently) affected rows, and a new
  characterization snapshot.
- This audit is a local dev DB read; no migrations or data changes were run.
  Phase 4 (stored-string disambiguation) remains deferred.

## Status (2026-07-05)

- Phase 0.3 done: `resolved_mode.js` + test committed (`0a85f0a5`). No production
  callers.
- Phase 0.2 done: this registry doc (`0a14d06a`).
- Phase 2 skeleton done: `grader_factory.js` + test (`d3e00aec`). `create()` is
  a stub; no production call sites wired.
- Phase 1.1 done: `ExerciseDefinition` predicates wired to `ResolvedMode`
  (`6e0b6850`).
- Phase 1.2 done: all listed discriminator-read sites routed through
  `ResolvedMode` (`2ba7c0f9`, `f307fc93`, `69616ca2`, `f8df38d9`, `2e370c21`);
  staff-distribution axis audited as pure, no change (`020bcb5c`).
- Phase 1.3 done: `no-raw-pipeline-discriminator` ESLint rule landed
  (`harmonylab-pipelines/no-raw-pipeline-discriminator`), allowlist + 3 inline
  exemptions documented above. `npm run lint` clean. **Phase 1 exit criteria
  met.**
- Phase 2 started: `grader_state.js` extracted (INCORRECT/CORRECT/PARTIAL +
  `STATE` map) out of `ExerciseGrader`. `ExerciseGrader.STATE` kept as a
  compatibility alias pointing at the shared object; no behavior change.
  `ChoraleGrader`/`IdentificationGrader` still define their own identical
  copies of these constants — consolidating them is a follow-up slice, not
  done in this commit.
- Phase 2 legacy-usage audit done (see "Legacy grader retirement audit"
  above): none of `ExerciseGrader`'s legacy per-type methods are exercised by
  reachable student content. Method extraction is paused pending a product
  decision on the recommended shape (single retained legacy fallback class,
  not five polished per-type classes).
- `GraderFactory` key contract updated: `matching`/`figured_bass`/`other` all
  collapse to one `legacy_exercise` fallback key; `harmonization` stays
  distinct (live, 34 reachable rows).
- `harmonization_grader.js` added: wraps `HarmonizationGraderLogic` with the
  per-problem/aggregate scoring `ExerciseGrader.grade()` does inline for the
  harmonization branch. Not wired into `app/exercise.js` yet — production
  behavior unchanged. Tested standalone (`harmonization_grader.test.js`).
- `GraderFactory.create()` partially wired (2026-07-05): constructs a real
  `HarmonizationGrader` for the `"harmonization"` key only. Every other key
  (`chorale`, `identification`, `legacy_exercise`) still throws an explicit
  "not wired yet" error. No production caller — `app/exercise.js`'s inline
  selection is unchanged; `create()` is exercised only by
  `grader_factory.test.js`.
- `GraderFactory.create()` extended (2026-07-05, same day) to also construct
  the existing `IdentificationGrader` for the `"identification"` key —
  `chorale_identification` maps to the same key, so it's covered too, no
  extra code needed. Matches `app/exercise.js:135`'s `new
  IdentificationGrader({})` call exactly (constructor settings are always
  `{}` in production, so `create()` ignores the caller-supplied `settings`
  arg for this key rather than threading through something never used).
  `"chorale"` still throws, with two open, undesigned blockers documented in
  `create()`'s docstring: (1) `ChoraleGrader` needs `definition.getGrading()`
  + a Unit-1 `octaveIndependent` override that `create(resolvedMode,
  settings)` can't derive without the live `ExerciseDefinition`; (2)
  `chorale_grader.js` imports an `app/`-aliased module, so requiring it
  breaks plain-`node` test execution — the same wall behind
  `chorale_grader.test.js`'s pre-existing failure. `"legacy_exercise"` still
  throws too — no product decision yet on constructing the retained
  `ExerciseGrader` fallback through this factory. Still no production
  caller.
- `"chorale"` given a designed context contract (2026-07-05, same day):
  `create(resolvedMode, { definition, constructors })`. New pure helper
  `chorale_grader_settings.js` (`resolveChoraleGraderSettings(definition)`)
  reproduces `app/exercise.js:145-148`'s `getGrading()` + Unit-1
  `octaveIndependent` override exactly, tested standalone under plain
  `node`. `create()`'s `"chorale"` branch requires `context.definition`
  (throws otherwise), derives settings via that helper, then constructs via
  `context.constructors.ChoraleGrader` if supplied (test injection seam) or
  falls back to a lazy `require("./chorale_grader")` (the real class,
  correct under webpack/Vite, untested under plain `node`), then calls
  `initFromDefinition(context.definition)` on the result — matching
  `app/exercise.js:145-152`'s full construction sequence. The `app/` alias
  problem itself is NOT solved (no loader, no resolution change, per
  instruction) — the seam only lets `create()`'s OWN logic (settings
  derivation + the `initFromDefinition` call) be tested without ever
  requiring the real `chorale_grader.js`. `create()`'s second argument is
  now a per-key-varying shape (documented as a known, temporary
  inconsistency to resolve before wiring a production caller). Still no
  production caller.
- **First production caller wired (2026-07-05):** `app/exercise.js`'s
  grader-selection block now calls `GraderFactory.create()` for two of its
  three live branches. Branch CONDITIONS are byte-for-byte unchanged (same
  three-way if/else-if/else, same clauses, same order) — only the
  CONSTRUCTION inside each branch changed.
  - **chorale branch: wired, with a guard added on code review.**
    `resolved.isChorale` is mode-gated (checks `CHORALE_MODES`) whenever
    mode is truthy, independent of exercise type — verified empirically
    that `resolveGraderKey()` returns `"chorale"` for every LIVE exercise
    type this branch's condition can select. That guarantee depends on one
    invariant, not the full literal domain of `type`: legacy
    `type="chorale_identification"` (distinct from `umto_chorale`) +
    `mode="playback"`/`"analysis_match"` would ALSO satisfy this branch's
    condition, but `resolvePipeline()` checks `isChoraleIdentification`
    (`type === "chorale_identification"`, no mode check) before `isChorale`,
    so it resolves to the `"chorale_identification"` pipeline →
    `"identification"` key, not `"chorale"` — and `create()`'s
    identification branch doesn't call `initFromDefinition()`, so this
    would have silently skipped it entirely under the "Selecting
    ChoraleGrader" log. `type="chorale_identification"` has 0 rows and is
    frozen for new writes (AGENTS.md non-negotiable rule), so this wasn't
    live, but a code-review pass on this commit flagged the missing
    code-level guard (identification's branch had one, chorale's didn't) —
    fixed by adding the same `resolveGraderKey(resolved) === "chorale"`
    guard, falling back to the exact pre-Phase-2 inline construction
    (including its own `initFromDefinition()` call) otherwise. Locked in
    with a permanent regression test. `create()`'s chorale branch already
    calls `initFromDefinition()` internally on the factory-path arm, so
    that arm does NOT call it again (calling it twice would have been a
    real behavior change).
  - **identification branch: partially wired, with a guard.** Discovered a
    real divergence while wiring: `app/exercise.js`'s raw
    `interactionMode === "identification"` check is type-agnostic, but
    `resolvePipeline()`'s pipeline field only recognizes literal
    `type="identification"`/`"chorale_identification"` — NOT the
    `isIdentification` mirror field. Exercise types explicitly out of scope
    for the six-pipeline split (`umto_barline_placement`: **26,491 rows**,
    the single largest exercise-type bucket in the entire DB;
    `umto_key_signature`: 18; `umto_symbolic_meter`: 3) all carry
    `mode="identification"` for some rows, resolve to pipeline `"other"`,
    and would make `GraderFactory.create()` throw
    (`resolveGraderKey → "legacy_exercise"`). Calling `create()`
    unconditionally in this branch would have broken IdentificationGrader
    selection for the largest live exercise-type bucket. Fixed by guarding:
    only call `create()` when `resolveGraderKey(resolved) === "identification"`
    (covers literal `type="identification"` and `umto_chorale` +
    `mode="identification"`, i.e. the `chorale_identification` pipeline);
    otherwise construct `IdentificationGrader` directly, exactly as before.
    Locked in as a permanent regression test in `grader_factory.test.js`.
    `create()`'s identification branch does NOT call `initFromDefinition()`
    itself, so this branch keeps that call explicit in both sub-cases
    (matches prior behavior either way).
  - **harmonization: NOT wired**, deliberately. It stays in the `else`
    branch (`ExerciseGrader`, unchanged). `HarmonizationGrader.grade()`'s
    signature (`problems, deliveredNotesPerProblem`) doesn't match
    `ExerciseContext`'s call site (`this.grader.grade(definition,
    inputChords)`) — adapting one to the other is its own slice, not forced
    here.
  - **legacy_exercise: NOT wired.** The `else` branch keeps constructing
    `ExerciseGrader` directly; `GraderFactory.create()` is never called for
    this case.
  - Verification: `npm run lint`, `grader_factory.test.js`,
    `harmonization_grader.test.js`, `resolved_mode.test.js` all green.
    Browser smoke test (local dev server + Vite, gstack `browse`):
    identification exercise (unit 5, type=identification) and chorale
    playback exercise (unit 9, umto_chorale+playback) both load with zero
    console errors; network log confirms the real `chorale_grader.js`
    (126KB) is fetched via the new lazy `require()` path at runtime,
    proving the CJS-`require()`-inside-an-ESM-served-file pattern actually
    works in the real browser, not just in tests. Full interactive
    click-to-grade verification was blocked by a pre-existing,
    unrelated-to-this-change limitation: exercise sheets show a
    "click to start audio" gate (`Tone.start()` in `midi_device.js`) whose
    promise never resolves in headless Chromium, and the identification
    input UI doesn't mount until that resolves. Confirmed via an A/B test
    (stashed the wiring change, reloaded, identical stuck state) that this
    is pre-existing and not caused by this change.
- `HarmonizationGrader` made production-interface compatible (2026-07-05):
  the signature mismatch noted above (`grade(problems,
  deliveredNotesPerProblem)` vs. `ExerciseContext`'s `grade(definition,
  inputChords)` call site) is resolved — the array-based method was
  renamed to `gradeProblems()` (kept, still directly unit-tested) and a new
  `grade(definition, inputChords)` adapter was added that reproduces
  `ExerciseGrader.grade()`'s definition/inputChords → problems/delivered-
  notes extraction (Set-dedupe, dummy-MIDI-109 strip, the `isChorale`/
  empty-problems early-return guard) before delegating to
  `gradeProblems()`. Characterized against `exercise_grader.js`'s actual
  source by hand-tracing expected values (that file can't be `require()`'d
  under plain `node` for a live A/B run — same `app/`-alias wall as
  `chorale_grader.test.js`). Still deliberately NOT wired into
  `app/exercise.js` or `GraderFactory.create()` in this commit.
  `exercise_grader.js` and `app/exercise.js` are untouched.
  **Correction found on code review of this commit (same day):** matching
  `grade(definition, inputChords)`'s signature to
  `ExerciseContext.grade()`'s call site does NOT clear a path to live
  wiring the way the commit first framed it. `ExerciseContext.grade()`
  (exercise_context.js:253-274) checks `_isHarmonizationExercise()` and, if
  true, calls `computeHarmonizationGraded(activeMidi)` — it never reaches
  the `this.grader.grade(this.definition, this.inputChords)` line for
  harmonization exercises at all. `computeHarmonizationGraded`
  (exercise_context.js:188-232) is a separate, already-live, stateful
  implementation (single target at a time via `_harmonizationPointer`,
  driven by `activeMidi` from a held-note tracker, calling
  `HarmonizationGraderLogic.harmonizationMatch` directly — it only reads
  `this.grader.STATE` constants, never `.grade()`). So
  `ExerciseGrader.grade()`'s harmonization switch case, and this
  `HarmonizationGrader.grade(definition, inputChords)` adapter matching its
  shape, are dead code paths for harmonization in production today, and
  wiring `GraderFactory`/`app/exercise.js` to construct `HarmonizationGrader`
  would not change harmonization grading at all while
  `computeHarmonizationGraded` keeps intercepting first. This work remains
  valid, tested groundwork for eventually retiring
  `ExerciseGrader`'s harmonization switch case, but is NOT a stepping stone
  to live harmonization wiring by itself. Reconciling with
  `computeHarmonizationGraded`'s stateful, single-target interface is a
  separate, larger, not-yet-scoped redesign.
- M1 = Phases 0+1+2 (resolver + grader factory). Full boot-path/render snapshots
  deferred to Phase 3's screenshot harness.
- `./run_js_tests.sh` has 9 pre-existing `app/` alias failures reproduced on
  main — NOT caused by this refactor. M1 tests are import-free/relative-only.
- Phase 3 (sheet split) is a separate project. Phase 4 (stored-string
  disambiguation) deferred.

### Phase 2 consolidated status (2026-07-05) — read this before starting further grader work

- **Live, factory-backed:** `chorale` and `identification` (covers
  `chorale_identification`) grader construction in `app/exercise.js` goes
  through `GraderFactory.create()`, guarded against the two known type-
  divergence traps (`type="chorale_identification"` for the chorale branch,
  out-of-scope UMTO types for the identification branch — both locked in
  with permanent regression tests). Branch selection conditions are
  unchanged from pre-Phase-2; only construction was touched.
- **Legacy/dead/unknown fallback:** `matching`/`figured_bass`/`"other"` all
  collapse to the `legacy_exercise` factory key, which still throws — no
  code constructs `ExerciseGrader` through the factory. `app/exercise.js`'s
  `else` branch keeps constructing `ExerciseGrader` directly, unchanged.
  `ExerciseGrader` is the retained single legacy-compatibility class (per
  the "Legacy grader retirement audit" above); it is NOT being split into
  per-type classes.
- **Harmonization is NOT wired through `GraderFactory`, and will not be
  wired without a separate, explicitly-scoped decision.** Live harmonization
  grading is owned by `ExerciseContext.computeHarmonizationGraded(activeMidi)`
  — a stateful, single-target-at-a-time implementation, unrelated to
  `ExerciseGrader`/`GraderFactory`. `ExerciseGrader`'s `mode==="harmonization"`
  switch case (grader.js:154-158) is a dead code path in production today:
  `ExerciseContext.grade()` diverts to `computeHarmonizationGraded` before
  ever reaching `this.grader.grade(...)` for harmonization exercises (see
  the "Correction found on code review" note above). Treat
  `ExerciseGrader`'s harmonization branch as a retirement candidate, not a
  live path. **As of PR A (2026-07-06), `computeHarmonizationGraded`'s
  computation itself has been extracted to `harmonization_runtime_grader.js`
  — see that file's entry above and "PR A" below — but this is a relocation
  of the live path, not a wiring of it through `GraderFactory`.**
- **`HarmonizationGrader` (`harmonization_grader.js`) stays**, but ONLY as
  characterization/retirement groundwork for `ExerciseGrader`'s dead
  harmonization switch case — it is NOT live-path isolation and must not be
  presented as such. Do not wire it into `GraderFactory`'s production call
  path or `app/exercise.js` without first explicitly scoping a reconciliation
  with `computeHarmonizationGraded`'s stateful interface — a separate,
  larger redesign, not a continuation of this Phase 2 grader-split effort.
  **Do not confuse with `harmonization_runtime_grader.js` (PR A) — that one
  IS the live path, extracted, not a characterization double.**
- **Next planned slice:** cleanly name/quarantine the `ExerciseGrader`
  fallback (either keep the class name and document it as the legacy
  compatibility fallback, or a low-risk rename to `LegacyExerciseGrader`)
  — not yet decided which.

### PR A: live harmonization runtime grading extraction (2026-07-06)

Extracted `ExerciseContext.computeHarmonizationGraded(activeMidi)` — the live,
stateful, single-target-at-a-time harmonization grading path described above —
out of `ExerciseContext` into a focused module, `harmonization_runtime_grader.js`
(see its entry in the "Graders" table above for the full contract).

- Purely a relocation: the computation body is byte-for-byte identical (only
  `this.` → `ctx.` and `this.grader.STATE.X` → shared `grader_state.js`
  `STATE.X`, proven behavior-identical via `exercise_grader.js:58`'s
  `ExerciseGrader.STATE = GRADER_STATE` alias). No pointer/accepted/rejected
  semantics changed; existing quirks (partial-counts-as-accepted,
  all-done-then-incorrect still firing rejected+feedback) are preserved, not
  fixed.
- State (`_harmonizationPointer`, `acceptedHarmonizationSonorities`,
  `_harmonizationRejected`) deliberately stays on `ExerciseContext`, not the
  new module — too many external components read/write those fields directly
  off the context instance for a clean state move to be in scope here.
- `ExerciseContext.computeHarmonizationGraded` now delegates:
  `return HarmonizationRuntimeGrader.computeHarmonizationGraded(this, activeMidi)`.
  `this` (the full context) is passed as `ctx`, so all external readers of
  those three fields see unchanged behavior.
- Characterized first: `harmonization_runtime_grader.test.js` locks the prior
  inline behavior (empty/null activeMidi, correct/partial/incorrect
  transitions, all-done-then-incorrect quirk, measureIndex/onset math, result
  shape, STATE identity) before the delegation was wired.
- Verified: `npm run lint` clean; `harmonization_runtime_grader.test.js`,
  `harmonization_grader_logic.test.js`, `harmonization_grader.test.js`,
  `resolved_mode.test.js`, `grader_factory.test.js` all green; independent
  correctness review confirmed the extraction is faithful on all four axes
  (import interop, `this`-preservation, no dropped side effects, STATE
  equivalence) with zero findings; browser smoke (real login, Unit 9
  harmonization exercise, playlist `PA03SM`) confirmed the page loads with
  zero console/network errors and the exercise sheet mounts. Interactive
  click-to-grade verification was blocked by the same pre-existing
  `Tone.start()` audio-gate limitation documented under "First production
  caller wired" above (confirmed identical, not caused by this change) — not
  fixable within this slice.
- Explicitly NOT done in this PR: no wiring through `GraderFactory`, no
  reconciliation with `HarmonizationGrader`'s `grade(definition, inputChords)`
  adapter, no state migration off `ExerciseContext`. This PR is runtime
  extraction only, per the standing rule against incidental behavior changes
  while isolating live paths.