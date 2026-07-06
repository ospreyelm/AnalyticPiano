# New Exercise Type Checklist

Use this when adding a new student exercise pipeline or modifying an existing
one. The architecture is locked in
[docs/architecture/exercise-pipeline-architecture.md](exercise-pipeline-architecture.md);
the file-by-file map is
[docs/architecture/pipeline-registry.md](pipeline-registry.md).

## Data

- [ ] UMTO only. New Exercise rows use `save_umto_exercise` or another
      sanctioned UMTO factory. Legacy `chorale`, `chorale_identification`,
      and raw-CIR shapes are frozen.
- [ ] No stored UMTO string/schema changes. If a new discriminator string is
      introduced, that is a Phase 4 (stored-string disambiguation) decision,
      not a side-effect of this work.

## Resolver (the only pipeline classifier)

- [ ] `lab/static/js/src/models/resolved_mode.js` `resolvePipeline`
      recognizes the new type/mode. Add a characterization case to
      `resolved_mode.test.js` for all six pipelines + `"other"`.
- [ ] No raw `type`/`mode`/`analysisType`/`staffDistribution` comparisons
      outside resolver/factory/axis modules. The
      `harmonylab-pipelines/no-raw-pipeline-discriminator` ESLint rule must
      stay green; if a new axis module legitimately needs a raw literal, add
      it to `ALLOWED_PATH_SUFFIXES` in the rule with a reason, or use a
      documented inline `eslint-disable-next-line`.

## Sheet (render-sheet selection)

- [ ] If the new pipeline needs a render sheet, add a per-pipeline sheet
      under `lab/static/js/src/components/music/` overriding only
      `renderStaves` (call `_renderStavesVexFlow` or `_renderStavesLegacy`
      on the base with the pipeline's cfg).
- [ ] `lab/static/js/src/models/sheet_factory.js` `SHEET_KEYS` maps the new
      pipeline to its sheet key. Add a case to `sheet_factory.test.js`.

## Grader (only if the grading path changes)

- [ ] If the new pipeline has a live grader, add it to
      `lab/static/js/src/models/grader_factory.js` `GRADER_KEYS` and wire
      `create()` to construct it. Add a case to `grader_factory.test.js`.
- [ ] Do NOT add new grader logic to `ExerciseGrader`. It is a retained
      legacy fallback, not where new live pipelines go.
- [ ] If the pipeline is harmonization: harmonization live grading is owned
      by `ExerciseContext.computeHarmonizationGraded` →
      `harmonization_runtime_grader.js`, NOT `GraderFactory`. Reconciling
      with that stateful interface is a separate, explicitly-scoped decision.

## Browser source

- [ ] No CommonJS/RequireJS in `lab/static/js/src/**`. Browser source is
      native ESM. The `harmonylab/no-cjs-in-browser` ESLint rule must stay
      green. New test files may use `require()` + the `require_esm` helper
      (they run under plain Node).

## Docs

- [ ] Update [docs/exercise_types.md](../exercise_types.md), including the
      summary table, if this is a new or modified exercise type.
- [ ] Update [docs/architecture/pipeline-registry.md](pipeline-registry.md):
      add the new file(s) to the right owner-tagged table, and note any new
      known divergence.

## Browser smoke (required for rendering changes)

- [ ] Add/confirm a browser smoke case covering the new pipeline. The smoke
      matrix in the registry documents the existing covered pipelines; a new
      pipeline must be covered. Verify: page mounts, sheet renders, zero
      console/network errors.
- [ ] If the change touches grading, verify click-to-grade interactively
      (note: the `Tone.start()` audio gate blocks headless Chromium — use a
      real browser session).

## Verify locally

- [ ] `npm run check:pipeline-architecture` green (runs `lint`, `build`,
      `test:eslint-rules`, `test:pipeline`).
- [ ] If a focused test cannot run under plain `node` due to an `app/`-alias
      issue, do NOT hide it. Exclude it from `test:pipeline`, document why
      in the registry, and cover it via browser smoke instead.

## Do not

- [ ] No incidental fixes for known divergences documented in the registry
      (the `mode="play"`/`identify`/`figures`/`roman` resolution gap,
      `type="umto_identification"` no parse branch, the `type="identification"`
      overlay issue). Each needs its own scoped decision + DB audit +
      characterization snapshot.
- [ ] No music-theory analysis / grading / taxonomy changes without
      first-principles reasoning and a distinguishing example (see
      `AGENTS.md` and `docs/music-theory-canon.md`).