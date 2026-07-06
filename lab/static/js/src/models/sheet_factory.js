/**
 * SheetFactory — Phase 3 foundation.
 *
 * Mirrors GraderFactory's shape (see ./grader_factory.js): a pure
 * `resolveSheetKey(resolvedMode)` selection function plus a `create()` that
 * instantiates the per-pipeline sheet class. Phase 3 splits the single
 * `ExerciseSheetComponent` (which forked on an `isChoraleLike && hasMeasures`
 * resolved-mode check inside its `renderStaves`) into a `BaseExerciseSheet` +
 * six per-pipeline sheet classes, each owning its render stack. This factory
 * owns the SELECTION so `app/exercise.js` never reads a raw pipeline
 * discriminator to pick a sheet.
 *
 * One sheet per LIVE pipeline, plus an `other` fallback:
 *   "matching"               — MatchingSheet (legacy-stave stack, no ID overlay)
 *   "chorale"                — ChoraleSheet (VexFlow stack)
 *   "harmonization"          — HarmonizationSheet (VexFlow stack + harmonization cfg)
 *   "figured_bass"           — FiguredBassSheet (legacy-stave stack + ID overlay)
 *   "identification"         — IdentificationSheet (legacy-stave stack + ID overlay)
 *   "chorale_identification" — ChoraleIdentificationSheet (VexFlow stack + ID overlay)
 *   "other"                  — maps to "matching" (the plain legacy-stave sheet).
 *                              Out-of-scope types (umto_barline_placement, musicxml,
 *                              analytical, etc.) render through the legacy stack
 *                              today with no identification overlay, identical to
 *                              matching. (umto_symbolic_meter / umto_key_signature
 *                              are intercepted by earlier early-returns in
 *                              app/exercise.js and never reach this factory.)
 *
 * Unlike GraderFactory (which deliberately leaves `legacy_exercise` and
 * `harmonization` unwired), every sheet key here IS wired: the sheet is a
 * single unconditional instantiation site in `app/exercise.js`, so it cannot
 * be partially wired the way the grader-selection block can. The incremental
 * discipline is reflected in the commit slicing (factory skeleton first, then
 * base + per-pipeline sheets, then production wiring), not in partial
 * production wiring.
 *
 * Testable surface: `resolveSheetKey(resolvedMode)` → string. Pure, import-free,
 * immune to the `app/` alias resolution wall that blocks full-boot tests —
 * same property GraderFactory's `resolveGraderKey` relies on.
 *
 * Injection seam (mirrors GraderFactory's `"chorale"` branch): the per-pipeline
 * sheet classes import `app/`-aliased modules (jquery, vexflow, app/component,
 * app/config, ...), which do not resolve under plain `node`. So `create()`
 * does NOT statically import any sheet class — it requires the caller to
 * inject them via `context.constructors[<SheetKey>]`. `app/exercise.js`
 * (which statically imports the real classes for its own fallback path)
 * passes them through; tests inject fakes. This keeps `sheet_factory.js` free
 * of any `app/`-aliased import and fully requirable under plain `node`.
 *
 * `create()`'s second argument is a uniform shape across keys (unlike
 * GraderFactory's per-key-varying context): every sheet takes the same
 * `{ exerciseContext, keySignature, midiDevice }` constructor settings, plus
 * the `constructors` injection map.
 */

var SHEET_KEYS = {
  matching: "matching",
  chorale: "chorale",
  harmonization: "harmonization",
  figured_bass: "figured_bass",
  identification: "identification",
  chorale_identification: "chorale_identification",
  // Out-of-scope types (symbolic-meter, key-signature, barline-placement,
  // musicxml, analytical, analytical_pcs, umto_identification) resolve to
  // "other" in resolved_mode.js. symbolic-meter + key-signature are intercepted
  // by earlier early-returns in app/exercise.js and never reach this factory.
  // The rest render through the plain legacy-stave stack with no identification
  // overlay today (ExerciseSheetComponent's legacy-render fall-through), which
  // is identical to the matching sheet. Map "other" → "matching" rather than a
  // separate dead class — mirrors GraderFactory's collapse of dead/unknown
  // pipelines into one fallback key.
  other: "matching",
};

/**
 * Returns the sheet key string for a resolved mode. Pure.
 * @param {object} resolvedMode - output of resolvePipeline()
 * @returns {string} sheet key
 */
function resolveSheetKey(resolvedMode) {
  if (!resolvedMode) return "matching";
  return SHEET_KEYS[resolvedMode.pipeline] || "matching";
}

/**
 * Instantiates the per-pipeline sheet for a resolved mode. Every key is wired
 * (see the file-level comment for why — unlike GraderFactory, the sheet site
 * cannot be partially wired).
 *
 * `context.constructors[<sheetKey>]` is REQUIRED for the resolved key — this
 * factory does not import any sheet class itself (each carries `app/`-aliased
 * imports, and this file must stay free of that alias to remain requirable
 * under plain `node`). `app/exercise.js` passes the real classes; tests inject
 * fakes. Mirrors GraderFactory's `"chorale"` injection seam exactly.
 *
 * The constructed sheet is always `new Ctor({ exerciseContext, keySignature,
 * midiDevice })` — the same constructor signature `BaseExerciseSheet` exposes
 * and the same shape `app/exercise.js`'s pre-Phase-3 `new ExerciseSheetComponent(...)`
 * used. No per-key context-shape variation.
 *
 * @param {object} resolvedMode - output of resolvePipeline()
 * @param {object} context - `{ exerciseContext, keySignature, midiDevice,
 *   constructors }`, where `constructors` maps each sheet key to its class
 *   (e.g. `{ ChoraleSheet, MatchingSheet, ... }`). The entry for the resolved
 *   sheet key is required.
 * @returns {object} sheet instance
 * @throws {Error} if `context.constructors` is missing or lacks the entry for
 *   the resolved sheet key.
 */
function create(resolvedMode, context) {
  var key = resolveSheetKey(resolvedMode);
  var ctors = (context && context.constructors) || null;
  var Ctor = ctors && ctors[key];
  if (typeof Ctor !== "function") {
    throw new Error(
      "SheetFactory.create requires context.constructors[" + JSON.stringify(key) +
        "] to construct the sheet for pipeline \"" +
        (resolvedMode && resolvedMode.pipeline) + "\". This factory does not import " +
        "the sheet classes themselves (they carry app/-aliased imports, and this " +
        "file must stay free of that alias). Pass the real class (already statically " +
        "imported by the caller) via context.constructors[" + JSON.stringify(key) + "]."
    );
  }
  return new Ctor({
    exerciseContext: context.exerciseContext,
    keySignature: context.keySignature,
    midiDevice: context.midiDevice,
  });
}

var exports = {
  resolveSheetKey: resolveSheetKey,
  SHEET_KEYS: SHEET_KEYS,
  create: create,
};

export default exports;