---
name: debug-exercise-type
description: Guide debugging of a HarmonyLab/Monteverdi student exercise bug by classifying its delivery pipeline, pointing at the exact files that own the affected behavior, then handing off to superpowers:systematic-debugging with context pre-loaded. Use when the user reports a broken exercise (wrong grading, render not mounting, overlay missing, wrong notes, stuck state) and wants the right starting point instead of grepping blind.
---

Debug a student exercise bug by first classifying which pipeline owns the
behavior, then handing off to `superpowers:systematic-debugging` with the
context already loaded. Do NOT run the fix loop yourself — that is
systematic-debugging's lane.

This skill is HarmonyLab-specific. Read before starting:
- `docs/architecture/exercise-pipeline-map.md` (the map)
- `docs/architecture/pipeline-registry.md` (file-by-file owners)
- `docs/architecture/chorale-system.md` (chorale-family debugging invariants)

## Step 1 — Capture the starting signal

Accept any of these from the user; normalize:

- **Exercise ID** (e.g. `EB81WJ`, `PA03SM`): look it up in the dev DB
  (`psql analyticpiano`) to read `Exercise.data->>'type'`, `->>'mode'`,
  `->>'analysisType'`, `staffDistribution`. Note: the `dump_exercise`
  management command reads real exercise data offline
  (`--settings=harmony.settings.local`); `getExerciseDefinition()` returns raw
  config with empty `.exercise` — use `this.models.exerciseDefinition`.
- **Live URL** (`/s/units/<n>/play/?playlist=...&exercise_num=...`): the URL is
  uniform; the pipeline is data-driven, NOT route-driven. Trace
  `apps/student/urls.py` → `PlayerView` (`apps/student/views.py`) → template
  fork (`qa_player.html` for `umto_symbolic_meter`/`umto_barline_placement`,
  else `student/player.html`) → `app/components/app/exercise.js`.
- **Symptom only** (e.g. "overlay doesn't render", "grading wrong", "stuck on
  click to start audio"): ask for an exercise ID or URL until you can
  classify the pipeline. A screenshot is also fine.

If the user gives a `type="identification"` overlay symptom, note the known
pre-existing divergence: `/ajax/identification-answers/` returns `[]` for
some exercises — confirm against `docs/architecture/pipeline-registry.md`
"Known divergences" item 4 before treating as a new bug.

## Step 2 — Classify the pipeline via `ResolvedMode`

Do NOT grep raw `type`/`mode`/`staffDistribution` strings — they collide across
axes (the `"chorale"` literal means three different things). Run the
classifier:

```
codegraph_explore "resolvePipeline ResolvedMode CHORALE_MODES"
```

`lab/static/js/src/models/resolved_mode.js` `resolvePipeline(exercise)` is the
only classifier. Map the exercise to one of:

`matching`, `chorale`, `harmonization`, `figured_bass`, `identification`,
`chorale_identification`, or `other` (symbolic-meter / key-signature /
barline / musicxml / analytical — bypass-style).

Record: `pipeline`, `stack` (`vexflow` vs `legacy-stave`), and which boolean
flags are set (`isChorale`, `isChoraleIdentification`, `isHarmonization`,
`isAnalysisMatch`, `isIdentification`, `isSymbolicMeter`).

Known traps to flag if they apply:
- `umto_chorale + mode="play"` → `other`/legacy-stave (latent bug, 9 dev rows).
- `mode="chorale_identification"` literal (0 rows, guarded).
- Out-of-scope UMTO types with `mode="identification"` (e.g.
  `umto_barline_placement`, 26k rows) → `other`, not `identification`.

## Step 3 — Point at the exact files that own the affected behavior

Use the pipeline → file table in
`docs/architecture/exercise-pipeline-map.md` §3 and §4. For the classified
pipeline, list the owning files for each axis:

- **Render:** per-pipeline sheet class (`components/music/<pipeline>_sheet.js`)
  + stack (`_renderStavesVexFlow` on `base_exercise_sheet.js` for vexflow, or
  `_renderStavesLegacy` for legacy). Bypass types: `symbolic_question_sheet.js`
  or `models/key_sig_exercise.js` (intercepted before `SheetFactory`).
- **Grading:** `GraderFactory` key → grader class, OR for harmonization the
  live path `ExerciseContext.computeHarmonizationGraded` →
  `harmonization_runtime_grader.js` (NOT `GraderFactory`).
- **State:** `ExerciseContext` fields + localStorage restore path (see map §6).
- **Boot/wiring:** `components/app/exercise.js` `getModels` (grader) and
  `getComponentMethods` (sheet).

Read the owning files with `codegraph_explore` (cheaper than opening 20 files).
Pull the verbatim source for the specific methods the symptom implicates. Do
NOT reason about correctness yet.

## Step 4 — Summarize current expected behavior vs the symptom

Produce a short, written summary:

- Pipeline + stack + grader path for THIS exercise.
- The exact `file:line` anchors that own the implicated behavior (from
  codegraph's line-numbered output).
- What the code currently does at those anchors, stated plainly.
- Where the symptom would manifest in that chain.
- Any known divergence from the registry that matches the symptom (so
  systematic-debugging doesn't "fix" a documented latent bug by accident).

This summary is the hand-off context. Keep it tight — anchors + behavior, not
a theory of the bug.

## Step 5 — Theory-canon gate (scoped to theory-sensitive changes)

If the symptom lands in **grading / analysis / taxonomy** (not render
plumbing), enforce the AGENTS.md non-negotiable: before trusting existing
implementation or proposing a fix, state the relevant musical rule from first
principles and produce a distinguishing example that would fail under the
incorrect rule. Read `docs/music-theory-canon.md` and the figured-bass
required-vs-allowed table (`apps/exercises/harmonization/figure_realization.py`).
If code/tests/docs contradict first-principles theory, surface the
contradiction to the product owner — do NOT silently preserve existing
behavior as convention.

If the symptom is render/plumbing (overlay not mounting, wrong sheet
selected, stuck audio gate), skip the theory gate.

## Step 6 — Hand off to `superpowers:systematic-debugging`

Invoke `superpowers:systematic-debugging` (via the Skill tool) with:

- The exercise ID/URL.
- The classified pipeline + stack + grader path.
- The file:line anchors from Step 3.
- The Step 4 summary.
- The theory-canon note from Step 5 (if applicable).
- A note on any known divergences that match the symptom (do not fix
  incidentally — each needs its own scoped decision + DB audit + snapshot).

STOP here. Do not form hypotheses, do not propose fixes, do not edit. The
fix → verify → browser-smoke loop is systematic-debugging's responsibility.

## What this skill does NOT do

- Does not run the fix loop (systematic-debugging owns that).
- Does not edit code.
- Does not "fix" the documented divergences in the registry.
- Does not add CommonJS to `lab/static/js/src/**` or bypass the
  `no-raw-pipeline-discriminator` ESLint rule.
- Does not reason about grading correctness beyond pointing at the grader
  path + applying the theory gate.