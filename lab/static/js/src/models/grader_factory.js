"use strict";

var { resolveChoraleGraderSettings } = require("./chorale_grader_settings");

/**
 * GraderFactory — Phase 2 foundation (M1).
 *
 * Maps a ResolvedMode to the grader class that scores it. One grader per
 * LIVE pipeline — kills the dual `analysis_match` path (today `umto_chorale` +
 * `mode=analysis_match` is graded by `ChoraleGrader` via app/exercise.js,
 * while `ExerciseGrader.analysisMatch` is a latent/dead fallback). This
 * factory owns the selection so there is exactly one path.
 *
 * PRODUCTION STATUS (2026-07-05): `"chorale"` and `"identification"` are LIVE
 * production keys — `app/exercise.js`'s grader-selection block calls
 * `create()` for both, each guarded by `resolveGraderKey(resolved) ===
 * "chorale"`/`"identification"` (falling back to the exact pre-Phase-2
 * inline construction otherwise; see the guard-specific comments in
 * `app/exercise.js` and docs/architecture/pipeline-registry.md's "Phase 2
 * consolidated status" for the two type-divergence traps those guards
 * exist for). `"harmonization"` constructs a real `HarmonizationGrader` but
 * has NO production caller: live harmonization grading is owned by
 * `ExerciseContext.computeHarmonizationGraded()`, a separate stateful
 * implementation `app/exercise.js`'s wiring does not touch — see
 * `harmonization_grader.js`'s header comment. `"legacy_exercise"` still
 * throws outright; no product decision yet on wiring the retained
 * `ExerciseGrader` fallback through this factory.
 *
 * `create()`'s second argument is NOT a uniform shape across keys —
 * `"harmonization"` forwards it as-is to the constructor, `"identification"`
 * ignores it, `"chorale"` reads a richer `{ definition, constructors }`
 * context object. This asymmetry is intentional: each key's real
 * constructor needs fundamentally different inputs (a flat settings blob
 * vs. a live `ExerciseDefinition` vs. nothing). Unifying this shape is a
 * separate, not-yet-scoped decision.
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
 *   "chorale"             — ChoraleGrader, LIVE production caller
 *   "harmonization"       — HarmonizationGrader can be constructed, but
 *                            has no production caller; live harmonization
 *                            grading happens in
 *                            ExerciseContext.computeHarmonizationGraded(),
 *                            not through this factory or ExerciseGrader.
 *   "identification"      — IdentificationGrader, LIVE production caller
 *                            (serves both `identification` and
 *                            `chorale_identification` pipelines)
 *
 * No per-type legacy class split (legacy_match_grader.js,
 * legacy_figured_bass_grader.js, analytical_grader.js, analytical_pcs_grader.js)
 * is planned.
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
 * Instantiates the grader for a resolved mode. `"chorale"` and
 * `"identification"` are LIVE production keys, called from
 * `app/exercise.js`'s grader-selection block (each guarded by
 * `resolveGraderKey(resolved) === <key>`, falling back to inline
 * construction otherwise). `"harmonization"` constructs a real grader but
 * has no production caller (see the class-level comment at the top of this
 * file and in `harmonization_grader.js`). `"legacy_exercise"` still throws.
 *
 * `"harmonization"` constructs `HarmonizationGrader`; `context` is
 * forwarded to it as-is as constructor settings.
 *
 * `"identification"` constructs the existing `IdentificationGrader` — this
 * also covers `chorale_identification`, which maps to the same key (see the
 * CAVEAT on `GRADER_KEYS.chorale_identification` above). Always constructed
 * with `{}`, matching `app/exercise.js`'s `new IdentificationGrader({})`
 * exactly — that call site never passes constructor settings for this
 * grader, so `context` is intentionally ignored for this key.
 *
 * `"chorale"` reproduces `app/exercise.js`'s construction exactly:
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