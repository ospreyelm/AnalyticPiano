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
| `lab/static/js/src/models/exercise_grader.js` | god-class (audit done, extraction paused) | `notesMatch` (matching), `figuredBassMatch`/`figuredBassPcsMatch` (figured_bass), `analysisMatch` (analytical + latent umto_chorale+analysis_match), `analysisPcsMatch` (analytical_pcs). Switch at L135. **2026-07-05 usage audit (see "Legacy grader retirement audit" below): none of these methods are exercised by reachable student content today.** Per-type standalone extraction is paused pending a product decision; likely shape is one retained legacy fallback class, not five polished classes — see the audit's recommendation. |
| `lab/static/js/src/models/chorale_grader.js` | `chorale` | Selected by `app/exercise.js:131` for playback/analysis_match |
| `lab/static/js/src/models/identification_grader.js` | `identification` + `chorale_identification` | Same class, discriminator on type/mode |
| `lab/static/js/src/models/harmonization_grader_logic.js` | `harmonization` | Pure-function module; called from `ExerciseGrader.grade()` L138 today |
| `lab/static/js/src/models/harmonization_grader.js` | `harmonization` | New (2026-07-05). Wraps `HarmonizationGraderLogic.harmonizationMatch` with the per-problem result-shape assembly and aggregate worst-state-wins scoring that `ExerciseGrader.grade()` does inline for the harmonization branch (grader.js:152-166, 210-227). Not wired into `app/exercise.js` yet — production still constructs `ExerciseGrader` for harmonization, which delegates internally to `HarmonizationGraderLogic` exactly as before. Preserves the `count`/`notes`-undefined quirk (harmonizationMatch's return has no such keys) rather than fixing it. Uses the shared `grader_state.js` STATE object directly (no local copy). Tested standalone in `harmonization_grader.test.js` (plain `node`, pure CommonJS, no `app/` alias). `GraderFactory.create()` can construct it (2026-07-05), but nothing calls `create()` in production yet. |

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
- M1 = Phases 0+1+2 (resolver + grader factory). Full boot-path/render snapshots
  deferred to Phase 3's screenshot harness.
- `./run_js_tests.sh` has 9 pre-existing `app/` alias failures reproduced on
  main — NOT caused by this refactor. M1 tests are import-free/relative-only.
- Phase 3 (sheet split) is a separate project. Phase 4 (stored-string
  disambiguation) deferred.