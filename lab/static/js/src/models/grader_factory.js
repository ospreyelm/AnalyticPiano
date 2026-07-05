"use strict";

/**
 * GraderFactory — Phase 2 skeleton (M1).
 *
 * Maps a ResolvedMode to the grader class that scores it. One grader per
 * LIVE pipeline — kills the dual `analysis_match` path (today `umto_chorale` +
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
 * Instantiates the grader for a resolved mode. SKELETON — NOT WIRED.
 *
 * Production wiring deferred until `app/exercise.js`'s inline selection can be
 * reproduced exactly, including the documented `mode="chorale_identification"`
 * divergence and the raw-mode-fallback ("play"/"identify"/"figures"/"roman")
 * caveats. Calling this before wiring throws. The lazy require map is sketched
 * here to document the intended class mapping; it is not executed at module load
 * so this file stays import-free and testable in plain `node`.
 *
 * @param {object} resolvedMode - output of resolvePipeline()
 * @param {object} settings - grader constructor settings
 * @returns {object} grader instance
 * @throws {Error} always, until wiring is reviewed and complete
 */
function create(resolvedMode /* , settings */) {
  throw new Error(
    "GraderFactory.create not yet implemented — production wiring requires " +
      "exact reproduction of app/exercise.js's current branch order. " +
      "Use resolveGraderKey() for the selection decision until then."
  );
}

module.exports = {
  resolveGraderKey: resolveGraderKey,
  GRADER_KEYS: GRADER_KEYS,
  create: create,
};