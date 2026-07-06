"use strict";

/**
 * Canonical exercise-pipeline resolver.
 *
 * Single source of truth for "which rendering/grading pipeline does this
 * exercise use?" Encodes the mapping that today is scattered across
 * ExerciseDefinition.isChorale() / isChoraleIdentification() / isHarmonization()
 * / isAnalysisMatch() / isIdentification() plus the `isChoraleLike` render fork
 * in exercise_sheet_staves.js.
 *
 * Why this exists: the literals "chorale", "figured_bass", "identification",
 * "matching", "play" each mean independent things on different fields
 * (exercise.type vs exercise.mode vs exercise.analysisType vs
 * staffDistribution). Agents grep a string and land in an unrelated axis.
 * Routing every read through resolvePipeline() eliminates that confusion —
 * the raw discriminator strings live ONLY in this file.
 *
 * Input: the PARSED exercise object (ExerciseDefinition.prototype.exercise),
 * i.e. the shape read by the predicates — `{ type, mode, score: { umto: {
 * metadata: { mode } } }, analysisType, staffDistribution }`. NOT the raw
 * definition config.
 *
 * Output: a frozen ResolvedMode object. Predicates on ExerciseDefinition will
 * read these fields instead of re-deriving from raw strings (Phase 1.1).
 *
 * Pipeline values (the six canonical student-facing pipelines):
 *   "matching"               — legacy exact-match (type=matching)
 *   "chorale"                — playback / analysis_match / play-all-voices /
 *                              analysis, or legacy type=chorale/umto_chorale
 *   "harmonization"          — mode=harmonization (on umto_chorale)
 *   "figured_bass"           — legacy type=figured_bass / figured_bass_pcs
 *   "identification"         — legacy non-chorale type=identification
 *   "chorale_identification" — type=chorale_identification, or umto_chorale
 *                              with mode=identification/chorale_identification
 *   "other"                  — symbolic-meter, key-signature, barline-placement,
 *                              musicxml, analytical, analytical_pcs (out of
 *                              scope for the six-pipeline split; caller handles)
 *
 * NOTE on the "play" default-fill (exercise_definition.js:893): once parse()
 * default-fills exercise.mode = "play", getMode() returns "play" (truthy), so
 * isChorale()'s `if (mode)` branch fires FIRST and runs the mode check. "play"
 * is NOT in {playback, analysis_match, play-all-voices, analysis}, so isChorale()
 * returns FALSE — the type-fallback branch (`type === "chorale" || "umto_chorale"`)
 * NEVER runs when mode is any truthy string, including "play". A legacy
 * type=chorale exercise that received the "play" default therefore resolves to
 * pipeline "other" + legacy-stave, NOT "chorale". This resolver mirrors that
 * behavior faithfully (isChorale returns false). This may be a latent bug in
 * current code, but the resolver must NOT "fix" it — investigate separately with
 * a Phase 0 snapshot proving the desired behavior first. Do NOT drop the type
 * axis from isChorale() without auditing every "play"-mode chorale exercise AND
 * deciding whether "play"-defaulted chorales should route as chorale.
 */

var CHORALE_MODES = ["playback", "analysis_match", "play-all-voices", "analysis"];
var CHORALE_IDENTIFICATION_MODES = ["identification", "chorale_identification"];
var CHORALE_TYPES = ["chorale", "umto_chorale"];
var FIGURED_BASS_TYPES = ["figured_bass", "figured_bass_pcs"];

/**
 * Resolves the interaction mode the same way ExerciseDefinition.getMode() does:
 * exercise.mode, falling back to score.umto.metadata.mode, then null.
 */
function resolveMode(exercise) {
  if (!exercise) return null;
  if (exercise.mode) return exercise.mode;
  var umtoMeta = exercise.score && exercise.score.umto && exercise.score.umto.metadata;
  return (umtoMeta && umtoMeta.mode) || null;
}

/**
 * Pure pipeline resolver. Mirrors ExerciseDefinition predicates exactly —
 * do not diverge. When a predicate changes, change it here AND in
 * exercise_definition.js (Phase 1.1 will make the predicates read from this
 * module, eliminating the duplication).
 */
function resolvePipeline(exercise) {
  var type = (exercise && exercise.type) || null;
  var mode = resolveMode(exercise);
  var analysisKind = (exercise && exercise.analysisType) || null;
  var staffStyle = (exercise && exercise.staffDistribution) || null;

  // Predicate re-implementations (must match exercise_definition.js:667-735).
  var isSymbolicMeter = type === "umto_symbolic_meter";
  var isChorale = mode
    ? CHORALE_MODES.indexOf(mode) !== -1
    : CHORALE_TYPES.indexOf(type) !== -1;
  var isChoraleIdentification = !isSymbolicMeter && (
    type === "chorale_identification" ||
    (type === "umto_chorale" && CHORALE_IDENTIFICATION_MODES.indexOf(mode) !== -1)
  );
  var isHarmonization = mode === "harmonization";
  var isAnalysisMatch = mode === "analysis_match";
  var isIdentification = type === "identification" ||
    type === "chorale_identification" ||
    isSymbolicMeter;

  // The render-stack fork in exercise_sheet_staves.js:45.
  var isChoraleLike = isChorale || isChoraleIdentification || isHarmonization;
  var stack = isChoraleLike ? "vexflow" : "legacy-stave";

  // Pipeline derivation. Order matters: chorale_identification and harmonization
  // are subsets of isChorale() (both true for umto_chorale), so check them first.
  var pipeline;
  if (isChoraleIdentification) {
    pipeline = "chorale_identification";
  } else if (isHarmonization) {
    pipeline = "harmonization";
  } else if (isChorale) {
    pipeline = "chorale";
  } else if (type === "matching") {
    pipeline = "matching";
  } else if (FIGURED_BASS_TYPES.indexOf(type) !== -1) {
    pipeline = "figured_bass";
  } else if (type === "identification") {
    pipeline = "identification";
  } else {
    pipeline = "other";
  }

  return Object.freeze({
    pipeline: pipeline,
    exerciseType: type,
    interactionMode: mode,
    analysisKind: analysisKind,
    staffStyle: staffStyle,
    stack: stack,
    // Predicate mirrors — exposed so Phase 1.1 predicate bodies can read
    // these instead of re-deriving from raw strings.
    isChorale: isChorale,
    isChoraleIdentification: isChoraleIdentification,
    isHarmonization: isHarmonization,
    isAnalysisMatch: isAnalysisMatch,
    isIdentification: isIdentification,
    isSymbolicMeter: isSymbolicMeter,
  });
}

var exports = {
  resolvePipeline: resolvePipeline,
  resolveMode: resolveMode,
  CHORALE_MODES: CHORALE_MODES,
  CHORALE_IDENTIFICATION_MODES: CHORALE_IDENTIFICATION_MODES,
  CHORALE_TYPES: CHORALE_TYPES,
  FIGURED_BASS_TYPES: FIGURED_BASS_TYPES,
};

export default exports;