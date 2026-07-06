# Exercise Pipeline Architecture (Phase 5 lock)

Status: **Accepted** (2026-07-06, Phase 5). Locks in the Phase 0–3 pipeline
isolation work. This is the authoritative short statement of the architecture;
the full file-by-file map lives in
[docs/architecture/pipeline-registry.md](pipeline-registry.md).

## Decision

HarmonyLab/Monteverdi ships six student-facing exercise pipelines
(`matching`, `chorale`, `harmonization`, `figured_bass`, `identification`,
`chorale_identification`) through one uniform URL (`s/units/<n>/play/`).
Pipeline selection is **data-driven**, never URL-driven. Three selection
seams own all pipeline routing; nothing else reads raw pipeline
discriminators.

### Authorities

1. **`ResolvedMode` is the only pipeline classifier.**
   `lab/static/js/src/models/resolved_mode.js` `resolvePipeline(exercise)`
   is the single source of truth for `{pipeline, exerciseType,
   interactionMode, analysisKind, staffStyle, stack, isChorale,
   isChoraleIdentification, isHarmonization, isAnalysisMatch,
   isIdentification, isSymbolicMeter}`. Raw `type`/`mode`/`analysisType`/
   `staffDistribution` strings must not be compared outside the resolver,
   factory, or approved axis modules. The `harmonylab-pipelines/
   no-raw-pipeline-discriminator` ESLint rule enforces this.

2. **`GraderFactory` owns live grader selection where wired.**
   `lab/static/js/src/models/grader_factory.js` selects the grader key from
   `resolved.pipeline`. `app/components/app/exercise.js` routes the `chorale`
   and `identification` (covers `chorale_identification`) branches through
   `GraderFactory.create()`, guarded against the two known type-divergence
   traps. The `else`/legacy/`matching`/`figured_bass`/`other` branch still
   constructs `ExerciseGrader` directly — that is the retained fallback, not
   a place to add new live pipelines.

3. **`SheetFactory` owns render-sheet selection.**
   `lab/static/js/src/models/sheet_factory.js` `resolveSheetKey(resolvedMode)`
   selects the sheet class from `resolved.pipeline`; `create()` instantiates
   it. `app/components/app/exercise.js` routes all sheet instantiation through
   `SheetFactory`. The six per-pipeline sheet classes override only
   `renderStaves` to call the right stack method with their pipeline's cfg.

### Retained / out of scope for the factory seams

- **`ExerciseGrader` is a retained legacy fallback**, not where new live
  pipelines go. Its per-type method bodies (`notesMatch`,
  `figuredBassMatch`, `analysisMatch`, …) are not exercised by any
  currently-reachable student content (see the "Legacy grader retirement
  audit" in the registry). New exercise types must not add grader logic here;
  route through `GraderFactory` instead.
- **Harmonization live runtime grading is separate** and owned by
  `ExerciseContext.computeHarmonizationGraded(activeMidi)` →
  `lab/static/js/src/models/harmonization_runtime_grader.js`
  (`computeHarmonizationGraded(ctx, activeMidi)`). It is a stateful,
  single-target-at-a-time implementation, unrelated to `ExerciseGrader` /
  `GraderFactory`. `HarmonizationGrader` (`harmonization_grader.js`) is
  characterization/retirement groundwork for `ExerciseGrader`'s dead
  harmonization switch case — **not** the live path and not wired through
  `GraderFactory`. Do not confuse the two.

### Browser source

- Browser source under `lab/static/js/src/**` must be **native ESM**. No
  CommonJS/RequireJS (`require`/`module.exports`/`define` as module system)
  in browser-served source. The `harmonylab/no-cjs-in-browser` ESLint rule
  enforces this. (Test files under `**/*.test.js` run under plain Node and
  are exempt; they use a `require_esm` helper to load ESM peers.)
- The custom ESLint rules themselves are `.mjs` Node modules under
  `eslint-rules/`, not browser source.

### Tests required when adding or modifying an exercise pipeline

Add or update focused tests (all run under plain `node`):

- `lab/static/js/src/models/resolved_mode.test.js` — resolver
  characterization for the new/changed pipeline.
- `lab/static/js/src/models/sheet_factory.test.js` — sheet-key mapping.
- `lab/static/js/src/models/grader_factory.test.js` — if the grading path
  changes.
- `lab/static/js/src/models/harmonization_runtime_grader.test.js` /
  `harmonization_grader_logic.test.js` — only if harmonization runtime logic
  changes.
- `docs/exercise_types.md` — if this is a new or modified exercise type.
- A browser smoke case for any rendering change (see the smoke matrix in the
  registry).

## Enforcement

`npm run check:pipeline-architecture` runs the full local gate:

```
npm run lint
npm run build
npm run test:eslint-rules
npm run test:pipeline
```

- `test:eslint-rules` — contract tests for the two custom ESLint rules.
- `test:pipeline` — the focused pipeline tests that pass under plain `node`.

There is **no Node/JS CI** today (`.github/workflows/test.yml` is Python-only
and `workflow_dispatch`-only). The local command is the required gate until
Node CI is added. See "Phase 5 status" in the registry for the exact commands
and the list of tests excluded from `test:pipeline` with reasons.

## Known divergences (documented, intentionally not fixed in Phase 5)

Recorded in the registry's "Known divergences + open questions" section. None
are touched by Phase 5. Each requires its own scoped decision, DB audit, and
characterization snapshot before any behavior change:

1. `mode="chorale_identification"` literal on `umto_chorale` (0 rows, guard
   against future data).
2. `mode="play"` (and `play`/`identify`/`figures`/`roman`) on `umto_chorale`
   resolves to `"other"` not `"chorale"` (9 + 27 dev/factory-seed rows, not
   live student content).
3. `type="umto_identification"` has no parse branch (0 rows).
4. `type="identification"` overlay does not render — pre-existing
   identification-answers-endpoint issue, not a pipeline regression.

## Non-negotiables

- New Exercise rows must use UMTO. Legacy `chorale`,
  `chorale_identification`, and raw-CIR shapes are frozen.
- No stored UMTO string/schema changes.
- No raw discriminator comparisons outside resolver/factory/axis modules.
- No CommonJS/RequireJS in `lab/static/js/src/**`.
- No incidental fixes for the known divergences above mid-refactor.