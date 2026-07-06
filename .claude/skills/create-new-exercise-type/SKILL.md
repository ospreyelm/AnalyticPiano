---
name: create-new-exercise-type
description: Guide creating a new HarmonyLab/Monteverdi student exercise type end-to-end (backend UMTO factory + frontend pipeline wiring + docs + browser smoke) WITHOUT modifying existing pipelines. Asks scoping questions, fills the new-exercise-type-checklist, drafts a plan, and drives implementation. Use when the user wants to add a new exercise type/mode to the student player.
---

Create a new student exercise type end-to-end — backend UMTO factory,
frontend pipeline wiring, docs, browser smoke — **without modifying existing
pipelines** (add-only). The architecture is locked; follow the checklist.

Required reading before starting:
- `docs/architecture/exercise-pipeline-architecture.md` (locked statement)
- `docs/architecture/new-exercise-type-checklist.md` (the checklist this skill
  drives)
- `docs/architecture/pipeline-registry.md` (file-by-file owners)
- `docs/architecture/exercise-pipeline-map.md` (the map)
- `docs/UMTO_GUIDE.md` + `apps/exercises/umto_schema.json`
- `AGENTS.md` non-negotiable rules

## Step 1 — Scoping questions

Ask the user these before writing anything. Do not infer.

1. **What musical concept does this exercise teach?** (One sentence. This is
   theory-sensitive — Step 5 gate applies.)
2. **Is the new type a new `type` string, a new `mode` on an existing type
   (e.g. a new `umto_chorale` mode), or a new `analysisType`?**
3. **Does it fit one of the 6 pipelines** (`matching`, `chorale`,
   `harmonization`, `figured_bass`, `identification`, `chorale_identification`)
   **or is it a bypass-style type** (like `umto_symbolic_meter` /
   `umto_key_signature` — custom sheet, intercepted before `SheetFactory`)?
   Default: 6-pipeline. Escalate to bypass only if it genuinely cannot fit,
   with a warning that bypass means custom state + custom grader + no factory
   seam.
4. **Input method?** (MIDI / click-on-staff / computer keyboard / dropdown /
   text / choice buttons — read `models/input_method_logic.js`
   `resolveInputMethod` for the canonical discriminator.)
5. **Render stack?** VexFlow (multi-voice, measures) or legacy stave
   (chord-based). Bypass types may use their own renderer.
6. **Grading model?** Onset-timeline (chorale), answer-match
   (identification/harmonization-targets), exact-match (matching), custom
   (bypass).
7. **Reuse or new files?** Reuse an existing sheet/grader class where the new
   type shares behavior (e.g. a new `umto_chorale` mode reuses
   `ChoraleSheet`); add new per-pipeline files only when behavior genuinely
   differs. Add-only rule: never edit an existing per-pipeline sheet/grader
   class — only the shared seams (`resolved_mode.js`, `sheet_factory.js`,
   `grader_factory.js`) get new keys/entries.

Record the answers. They drive the plan.

## Step 2 — Theory-canon gate (theory-sensitive, mandatory)

Before authoring any grading/analysis/taxonomy logic, enforce the AGENTS.md
non-negotiable:

- State the relevant musical rule from first principles.
- Read `docs/music-theory-canon.md`.
- For figured-bass: the required-vs-allowed realization table in
  `apps/exercises/harmonization/figure_realization.py` is the source of truth;
  do not re-derive required tones ad hoc.
- Pitch spelling must carry octave (`Pitch.nameWithOctave`, never
  `Pitch.name`) through every derive/transpose/re-serialize step.
- Produce a distinguishing example that would fail under the incorrect rule.
- If existing code/tests/docs contradict first-principles theory, surface the
  contradiction to the product owner — do NOT silently preserve existing
  behavior as convention. Do NOT add a silent fallback for music theory.

This gate blocks Step 4 if the new type introduces any grading/analysis.

## Step 3 — Draft the plan

Write the plan to `docs/superpowers/plans/YYYY-MM-DD-<name>.md` (date today).
For architecture/data-shape decisions, also write
`docs/superpowers/specs/YYYY-MM-DD-<name>-design.md`.

The plan must cover, in order:

### Backend (UMTO only)

- New Exercise rows MUST use UMTO via `save_umto_exercise` or another
  sanctioned UMTO factory. Never set `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1`.
- Legacy `chorale`, `chorale_identification`, and raw-CIR shapes are frozen —
  do not extend them.
- If a new `type`/`mode` discriminator string is introduced, that is a
  **Phase 4 (stored-string disambiguation)** decision, not a side-effect —
  flag it and get explicit approval. No stored UMTO string/schema changes
  without it.
- Backend music21 boundaries must normalize keys via
  `apps/exercises/utils/key_normalization.harmony_key_to_music21()`.
- Add/extend a generator management command only if needed; register it in
  `apps/exercises/management/commands/list_exercise_generators.py` and update
  `docs/management_commands.md`.

### Frontend pipeline wiring (add-only)

- `lab/static/js/src/models/resolved_mode.js` `resolvePipeline`: recognize
  the new type/mode. Add a characterization case to
  `resolved_mode.test.js` for all six pipelines + `"other"` (and the new one).
- `lab/static/js/src/models/sheet_factory.js` `SHEET_KEYS`: map the new
  pipeline to its sheet key. Add a case to `sheet_factory.test.js`.
- `lab/static/js/src/models/grader_factory.js` `GRADER_KEYS` + `create()`:
  only if the grading path changes. Add a case to `grader_factory.test.js`.
  Do NOT add new grader logic to `ExerciseGrader` — it is the retained legacy
  fallback.
- If bypass-style: add the early-return in
  `components/app/exercise.js` `getComponentMethods` BEFORE `SheetFactory`
  (mirroring `SymbolicQuestionSheet` / `KeySigExercise`). Document why it
  cannot fit the 6-pipeline split.
- Add a per-pipeline sheet under `lab/static/js/src/components/music/`
  overriding only `renderStaves` (call `_renderStavesVexFlow` or
  `_renderStavesLegacy` on `base_exercise_sheet.js` with the pipeline's cfg).
  Do NOT edit existing per-pipeline sheet classes.
- New live grader class under `lab/static/js/src/models/` if needed.
- If harmonization-family: harmonization live grading is owned by
  `ExerciseContext.computeHarmonizationGraded` →
  `harmonization_runtime_grader.js`, NOT `GraderFactory`. Reconciling with
  that stateful interface is a separate, explicitly-scoped decision — flag it.

### Browser source

- Native ESM only under `lab/static/js/src/**`. No CommonJS/RequireJS
  (`harmonylab/no-cjs-in-browser` ESLint rule). Test files (`**/*.test.js`)
  may use `require()` + the `require_esm` helper.

### Docs

- Update `docs/exercise_types.md` including the summary table.
- Update `docs/architecture/pipeline-registry.md`: add new files to the right
  owner-tagged table; note any new known divergence.

### Browser smoke (required for rendering changes)

- Add a browser smoke case covering the new pipeline. Use a real browser
  session (the `Tone.start()` audio gate blocks headless Chromium). The
  project's `/browse` skill (gstack) drives it.
- Verify: page mounts, sheet renders, zero console/network errors, and (if
  the change touches grading) click-to-grade interactively.

## Step 4 — Implement against the plan

Use `superpowers:executing-plans` / `superpowers:subagent-driven-development`
as appropriate. Isolation: add-only. Never modify an existing per-pipeline
sheet/grader class. Only the shared seams (`resolved_mode.js`,
`sheet_factory.js`, `grader_factory.js`) receive new keys/entries, and only
additively.

Worktree: use an isolated git worktree for the implementation (per CLAUDE.md).
Note `.python-version` pins 3.10.18 (not installed) — run `pyenv local system`
first in any new worktree.

## Step 5 — Verify

Run the local gate (no Node/JS CI exists today — this is the required gate):

```
npm run check:pipeline-architecture
```

This runs `lint` → `build` → `test:eslint-rules` → `test:pipeline`.

If a focused test cannot run under plain `node` due to an `app/`-alias issue,
do NOT hide it. Exclude it from `test:pipeline`, document why in the
registry, and cover it via browser smoke instead.

Then the browser smoke (Step 3). Confirm zero console/network errors.

Inspect the final diff and worktree status before reporting completion (per
CLAUDE.md).

## Step 6 — PR

PR target (per AGENTS.md):
```
gh pr create --repo avnerdorman/HarmonyLab --base master
```
Do not let `gh` infer the target from the `upstream` remote.

## What this skill does NOT do

- Does not modify existing per-pipeline sheets/graders (add-only).
- Does not add legacy `chorale`/`chorale_identification`/raw-CIR shapes
  (frozen).
- Does not change stored UMTO strings/schemas (Phase 4 decision, separate).
- Does not "fix" the documented known divergences (`mode="play"`/`identify`/
  `figures`/`roman` resolution gap, `type="umto_identification"` no parse
  branch, `type="identification"` overlay issue). Each needs its own scoped
  decision + DB audit + characterization snapshot.
- Does not add CommonJS to browser source or bypass the
  `no-raw-pipeline-discriminator` ESLint rule.
- Does not write music-theory analysis/grading/taxonomy without the Step 2
  first-principles gate.