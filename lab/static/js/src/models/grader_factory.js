"use strict";

/**
 * GraderFactory — Phase 2 skeleton (M1).
 *
 * Maps a ResolvedMode to the grader class that scores it. One grader per
 * pipeline — kills the dual `analysis_match` path (today `umto_chorale` +
 * `mode=analysis_match` is graded by `ChoraleGrader` via app/exercise.js:131,
 * while `ExerciseGrader.analysisMatch` at grader.js:142 is a latent/dead
 * fallback). This factory owns the selection so there is exactly one path.
 *
 * SKELETON ONLY — no production call sites wired yet. `app/exercise.js:119-151`
 * still selects graders inline. `create()` is a documented stub that is NOT
 * exercised by tests; the resolver contract must be reviewed before this factory
 * is wired into production (per user decision 2026-07-05).
 *
 * Testable surface: `resolveGraderKey(resolvedMode)` → string. Pure, import-free,
 * immune to the `app/` alias resolution wall that blocks full-boot tests.
 *
 * Grader keys:
 *   "legacy_match"         — LegacyMatchGrader (Phase 2.1 extraction from
 *                            ExerciseGrader.notesMatch)
 *   "chorale"             — ChoraleGrader (existing)
 *   "harmonization"       — HarmonizationGraderLogic (existing, pure-fn)
 *   "legacy_figured_bass"  — LegacyFiguredBassGrader (Phase 2.1 extraction from
 *                            ExerciseGrader.figuredBassMatch/figuredBassPcsMatch)
 *   "identification"      — IdentificationGrader (existing; serves both
 *                            `identification` and `chorale_identification`
 *                            pipelines, matching current behavior)
 *
 * The Phase 2.1 extraction (legacy_match, legacy_figured_bass, analysis_match,
 * analytical, analytical_pcs) is deferred until the resolver contract is reviewed
 * and `create()` is wired. Until then, the KEY resolution is the contract.
 */

var GRADER_KEYS = {
  matching: "legacy_match",
  chorale: "chorale",
  harmonization: "harmonization",
  figured_bass: "legacy_figured_bass",
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
  // Default to legacy_match — mirrors the current ExerciseGrader else-branch
  // default (which falls through to notesMatch). Phase 2 may specialize these.
  other: "legacy_match",
};

/**
 * Returns the grader key string for a resolved mode. Pure.
 * @param {object} resolvedMode - output of resolvePipeline()
 * @returns {string} grader key
 */
function resolveGraderKey(resolvedMode) {
  if (!resolvedMode) return "legacy_match";
  return GRADER_KEYS[resolvedMode.pipeline] || "legacy_match";
}

/**
 * Instantiates the grader for a resolved mode. SKELETON — NOT WIRED.
 *
 * Production wiring deferred until the resolver contract (resolved_mode.js) is
 * reviewed. Calling this before wiring throws. The lazy require map is sketched
 * here to document the intended class mapping; it is not executed at module load
 * so this file stays import-free and testable in plain `node`.
 *
 * @param {object} resolvedMode - output of resolvePipeline()
 * @param {object} settings - grader constructor settings
 * @returns {object} grader instance
 * @throws {Error} always, until Phase 2.1 extraction + wiring is complete
 */
function create(resolvedMode /* , settings */) {
  throw new Error(
    "GraderFactory.create not yet implemented — resolver contract under review. " +
      "Use resolveGraderKey() for the selection decision; production wiring " +
      "lands in Phase 2.1 after legacy grader extraction."
  );
}

module.exports = {
  resolveGraderKey: resolveGraderKey,
  GRADER_KEYS: GRADER_KEYS,
  create: create,
};