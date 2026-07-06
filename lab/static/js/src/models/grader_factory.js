"use strict";

var { resolveChoraleGraderSettings } = require("./chorale_grader_settings");

/**
 * GraderFactory — Phase 2 skeleton (M1).
 *
 * Maps a ResolvedMode to the grader class that scores it. One grader per
 * LIVE pipeline — kills the dual `analysis_match` path (today `umto_chorale` +
 * `mode=analysis_match` is graded by `ChoraleGrader` via app/exercise.js:131,
 * while `ExerciseGrader.analysisMatch` at grader.js:142 is a latent/dead
 * fallback). This factory owns the selection so there is exactly one path.
 *
 * SKELETON, PARTIALLY WIRED — no production call sites yet.
 * `app/exercise.js:119-151` still selects graders inline. `create()`
 * constructs a real grader for `"harmonization"` (backed by
 * `HarmonizationGrader`) and `"identification"` (backed by the existing
 * `IdentificationGrader` — also serves `chorale_identification`, which maps
 * to the same key). `"chorale"` now has a DESIGNED context contract (backed
 * by the existing `ChoraleGrader` + the new pure helper
 * `chorale_grader_settings.js`) but is still not callable with a real
 * `ChoraleGrader` under plain `node` — see `create()`'s docstring for the
 * injection seam that lets it be tested anyway. `"legacy_exercise"` still
 * throws outright. The resolver contract must be reviewed before this
 * factory is wired into production (per user decision 2026-07-05).
 *
 * `create()`'s second argument is NOT a uniform shape across keys yet —
 * `"harmonization"` forwards it as-is to the constructor, `"identification"`
 * ignores it, `"chorale"` reads a richer `{ definition, constructors }`
 * context object. This asymmetry is intentional and temporary: each key's
 * real constructor needs fundamentally different inputs today (a flat
 * settings blob vs. a live `ExerciseDefinition` vs. nothing), and forcing a
 * single unified shape before `app/exercise.js` wiring is designed would be
 * guessing. Resolve this before wiring a production caller.
 *
 * Testable surface: `resolveGraderKey(resolvedMode)` → string. Pure, import-free,
 * immune to the `app/` alias resolution wall that blocks full-boot tests.
 *
 * Grader keys — REVISED 2026-07-05 per the legacy-grader-usage audit in
 * docs/architecture/pipeline-registry.md ("Legacy grader retirement audit").
 * That audit found zero live student-reachable rows for `matching`,
 * `figured_bass`/`figured_bass_pcs`, and the `"other"` catch-all (27
 * dev/factory-seed-only rows). Per product direction (migrate remaining
 * legacy types to UMTO, do not expand legacy grader architecture), these
 * dead/unknown paths collapse to ONE fallback key instead of one class per
 * legacy type:
 *   "legacy_exercise"     — ExerciseGrader, kept as a single retained
 *                            compatibility fallback (NOT split into
 *                            per-type classes — matching, figured_bass,
 *                            and "other" all map here)
 *   "chorale"             — ChoraleGrader (existing, live)
 *   "harmonization"       — current behavior: ExerciseGrader constructed,
 *                            whose internal switch delegates to
 *                            HarmonizationGraderLogic (existing pure-fn
 *                            module, already extracted, live — 34
 *                            reachable rows). Kept as its own key because
 *                            it is a live pipeline, not a dead one, even
 *                            though today's *implementation* still goes
 *                            through ExerciseGrader as a pass-through.
 *   "identification"      — IdentificationGrader (existing; serves both
 *                            `identification` and `chorale_identification`
 *                            pipelines, matching current behavior)
 *
 * No per-type legacy class split (legacy_match_grader.js,
 * legacy_figured_bass_grader.js, analytical_grader.js, analytical_pcs_grader.js)
 * is planned. `create()` remains an unwired stub — wiring `app/exercise.js` to
 * this factory is deferred until it can reproduce the current branch order
 * exactly, including the `mode="chorale_identification"` and raw-mode-fallback
 * caveats below.
 */

var GRADER_KEYS = {
  matching: "legacy_exercise",
  chorale: "chorale",
  harmonization: "harmonization",
  figured_bass: "legacy_exercise",
  identification: "identification",
  // CAVEAT — known divergence from current production selection for one rare
  // mode value. For type=umto_chorale + mode="chorale_identification" (literal),
  // app/exercise.js:119-127 does NOT route to IdentificationGrader: the first
  // branch requires interactionMode === "identification" exactly (the literal
  // "chorale_identification" does not match), and !interactionMode is false, so
  // it falls through to the else branch → new ExerciseGrader() → switch on type
  // "umto_chorale" → mode is not "harmonization"/"analysis_match" → notesMatch.
  // This factory maps pipeline "chorale_identification" → "identification"
  // (IdentificationGrader), which matches the *intent* of the predicates
  // (isChoraleIdentification() returns true for mode "chorale_identification")
  // but DIVERGES from current production grader selection.
  //
  // DB query (2026-07-05): 0 rows carry mode="chorale_identification" (any type),
  // and 0 rows carry type=umto_chorale AND mode="chorale_identification". The
  // divergence is confirmed NOT LIVE in current data. Current-gen UMTO uses
  // mode="identification" (the InteractionMode enum has no "chorale_identification"
  // member). Mapping left as predicate-intent ("identification"); downgrade from
  // "must resolve before wiring" to "guard against future data." If a future
  // import writes mode="chorale_identification", revisit this mapping.
  chorale_identification: "identification",
  // Out-of-scope types (symbolic-meter, key-signature, musicxml, analytical,
  // analytical_pcs, umto_identification) resolve to "other" in resolved_mode.js.
  // 2026-07-05 audit: the only rows that ever reach this bucket in practice
  // (umto_chorale with an unrecognized mode — play/identify/figures/roman)
  // are dev/factory-seed fixtures, unreachable via student delivery. Default
  // to legacy_exercise — mirrors the current ExerciseGrader else-branch
  // default (which falls through to notesMatch).
  other: "legacy_exercise",
};

/**
 * Returns the grader key string for a resolved mode. Pure.
 * @param {object} resolvedMode - output of resolvePipeline()
 * @returns {string} grader key
 */
function resolveGraderKey(resolvedMode) {
  if (!resolvedMode) return "legacy_exercise";
  return GRADER_KEYS[resolvedMode.pipeline] || "legacy_exercise";
}

/**
 * Instantiates the grader for a resolved mode. PARTIALLY WIRED —
 * harmonization, identification, and (test-seam-only) chorale (2026-07-05).
 *
 * `"harmonization"` constructs `HarmonizationGrader` (landed and reviewed
 * clean in a prior commit); `context` is forwarded to it as-is as
 * constructor settings.
 *
 * `"identification"` constructs the existing `IdentificationGrader` — this
 * also covers `chorale_identification`, which maps to the same key (see the
 * CAVEAT on `GRADER_KEYS.chorale_identification` above). Always constructed
 * with `{}`, matching `app/exercise.js:135`'s `new IdentificationGrader({})`
 * exactly — that call site never passes constructor settings for this
 * grader, so `context` is intentionally ignored for this key.
 *
 * `"chorale"` reproduces `app/exercise.js:143-150`'s construction exactly:
 *   var gradingSettings = definition.getGrading();
 *   if (definition.isUnit(1)) { gradingSettings.octaveIndependent = true; }
 *   models.exerciseGrader = new ChoraleGrader(gradingSettings);
 *   models.exerciseGrader.initFromDefinition(models.exerciseDefinition);
 * via `context.definition` (required — throws if missing) fed through the
 * pure `resolveChoraleGraderSettings()` helper (`chorale_grader_settings.js`,
 * tested standalone), then `initFromDefinition(context.definition)` is
 * called on the constructed instance, matching production's second step.
 *
 * Test-safe injection seam: `chorale_grader.js` imports an `app/`-aliased
 * module (`app/components/music/score_timeline`), so requiring it throws
 * `ERR_MODULE_NOT_FOUND` under plain `node` — the same wall behind
 * `chorale_grader.test.js`'s pre-existing failure. To keep `create()`
 * testable anyway, the `"chorale"` branch accepts an optional
 * `context.constructors.ChoraleGrader` override: if supplied (as tests do,
 * with a fake stub class), it's used directly and `chorale_grader.js` is
 * NEVER required. If omitted (as real production wiring would leave it),
 * `create()` falls back to a lazy `require("./chorale_grader")` — correct
 * under webpack/Vite bundling (the alias resolves), but that fallback path
 * itself remains untested under plain `node` until the alias issue has an
 * independent resolution. Per user instruction, this file does NOT attempt
 * to solve the `app/` alias problem itself (no loader, no module-resolution
 * change) — the seam only sidesteps it for testing this branch's OWN logic
 * (settings derivation + initFromDefinition call), not for constructing a
 * real `ChoraleGrader` in tests.
 *
 * `"legacy_exercise"` (matching/figured_bass/other, all dead or
 * dev-fixture-only per the usage audit) is intentionally left unwired — no
 * product decision yet on whether/how to construct the retained
 * `ExerciseGrader` fallback through this factory.
 *
 * Each grader module is required lazily, inside the branch that needs it,
 * not at module top level, so a still-unwired or alias-carrying grader
 * (like `ChoraleGrader`, absent an injected override) can never be pulled in
 * just by loading this file — keeping `grader_factory.js` itself always
 * requirable under plain `node`. `chorale_grader_settings.js` is required at
 * module top level instead, since it has no imports of its own and is safe.
 *
 * @param {object} resolvedMode - output of resolvePipeline()
 * @param {object} context - shape depends on the resolved key (see above):
 *   "harmonization" → forwarded as-is as constructor settings;
 *   "identification" → ignored;
 *   "chorale" → `{ definition, constructors }`, where `definition` is
 *     required (an ExerciseDefinition or test double exposing
 *     getGrading()/isUnit()/and, on the constructed grader,
 *     initFromDefinition()) and `constructors.ChoraleGrader` is an optional
 *     class override for tests.
 * @returns {object} grader instance
 * @throws {Error} for "chorale" without `context.definition`, or for
 *   "legacy_exercise", until wiring is designed, reviewed, and complete
 */
function create(resolvedMode, context) {
  var key = resolveGraderKey(resolvedMode);

  if (key === "harmonization") {
    var HarmonizationGrader = require("./harmonization_grader");
    return new HarmonizationGrader(context);
  }

  if (key === "identification") {
    var identificationModule = require("./identification_grader");
    var IdentificationGrader = identificationModule.default || identificationModule;
    return new IdentificationGrader({});
  }

  if (key === "chorale") {
    if (!context || !context.definition) {
      throw new Error(
        "GraderFactory.create requires context.definition to construct " +
          "ChoraleGrader (needed for resolveChoraleGraderSettings() and " +
          "initFromDefinition()). Received: " +
          (context ? "a context without .definition" : "no context") + "."
      );
    }

    var gradingSettings = resolveChoraleGraderSettings(context.definition);
    var ChoraleGraderCtor =
      (context.constructors && context.constructors.ChoraleGrader) ||
      require("./chorale_grader");
    var grader = new ChoraleGraderCtor(gradingSettings);
    grader.initFromDefinition(context.definition);
    return grader;
  }

  throw new Error(
    "GraderFactory.create not yet implemented for grader key \"" + key + "\" — " +
      "only \"harmonization\", \"identification\", and \"chorale\" are wired " +
      "so far. Production wiring for the remaining keys requires exact " +
      "reproduction of app/exercise.js's current branch order. Use " +
      "resolveGraderKey() for the selection decision until then."
  );
}

module.exports = {
  resolveGraderKey: resolveGraderKey,
  GRADER_KEYS: GRADER_KEYS,
  create: create,
};