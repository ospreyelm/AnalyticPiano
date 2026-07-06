// Custom ESLint rule — Phase 1.3 pipeline-isolation guard.
//
// Bans *direct pipeline-discriminator comparisons* outside the resolver,
// the grader factory, the definition/parse layer, and the two confirmed-pure
// axis modules. Forces agents to route type/mode/analysisType/staffDistribution
// reads through ResolvedMode (lab/static/js/src/models/resolved_mode.js) so a
// grep for "chorale" / "figured_bass" / etc. can no longer land in an unrelated
// axis. See docs/architecture/pipeline-registry.md and the Phase 1.3 section of
// the plan (docs/superpowers/plans/...proud-weaving-stream.md).
//
// This is NOT a blanket string-literal ban. The literals "chorale",
// "figured_bass", "identification", etc. are also analysis families, UMTO
// storage keys, taxonomy labels, and content fields. Only the four
// pipeline-discriminator comparison SHAPES are targeted:
//   - <expr>.type === "<discriminator>"            (and .mode / .analysisType)
//   - <expr>["type"] === "<discriminator>"          (computed access)
//   - getMode() === "<discriminator>"
//   - <expr>.get("mode") === "<discriminator>"
//   - staffDistribution === "<discriminator>"       (bare identifier or access)
//
// Allowed files (raw strings live here by design — see ALLOWED_FILES):
//   - resolved_mode.js: the resolver; raw strings are authoritative here.
//   - grader_factory.js: maps off resolved.pipeline, not raw strings.
//   - exercise_definition.js: parse() + helpers CONSTRUCT the data ResolvedMode
//     consumes; routing these reads through ResolvedMode would be circular.
//   - input_method_logic.js + chordal_umto_staff_distribution.js: confirmed-pure
//     axis modules (Phase 1.2 audit, pipeline-registry.md); local axis literals
//     inside their own pure functions are allowed.
//   - harmonization_targets_logic.js: pure harmonization-axis module (local
//     getMode/isHarmonization helpers, no ExerciseDefinition reference) — same
//     shape as input_method_logic.js; local axis literal kept.
//   - chord.js: confirmed-pure staff-distribution axis consumer (Phase 1.2
//     audit); reads only the uppercase STAFF_DISTRIBUTION alias from
//     Config.get("general.staffDistribution") — zero type/mode/getMode reads.
//     Same axis as chordal_umto_staff_distribution.js. Note: its comparisons
//     use the alias `STAFF_DISTRIBUTION`, which the bare-identifier branch
//     (case-sensitive to `staffDistribution`) does not match — allowlisting is
//     the honest classification (axis consumer) rather than relying on the
//     alias escaping the AST match.
//   - *.test.js: tests exercise raw strings by intent.
//
// Known intentional raw reads that are NOT in ALLOWED_FILES carry an inline
// `eslint-disable-next-line` with a justification comment. As of Phase 1.3 these
// are permanent, documented exemptions (routing them would be a behavior change):
//   - app/exercise.js chorale-play gate first clause (definition.mode === "playback")
//   - exercise_sheet_identification_logic.js _supportsTextInputMode umto_chorale guard
//   - stave_note_factory.js CHORALE_FORMAT (staffDistribution === "chorale" is a
//     DISTRIBUTION_CHORALE layout-axis literal, not a TYPE_CHORALE pipeline literal)

// Discriminator string values that select a student-facing pipeline (the six
// pipelines + their mode/type synonyms). Sourced from resolved_mode.js
// (CHORALE_MODES, CHORALE_IDENTIFICATION_MODES, CHORALE_TYPES,
// FIGURED_BASS_TYPES) plus the standalone type/mode values "matching",
// "identification", and the "play" default-fill mode.
//
// Out-of-scope "other" types — umto_symbolic_meter, umto_key_signature,
// umto_barline_placement, musicxml, analytical, analytical_pcs — are
// intentionally EXCLUDED: resolvePipeline maps them to "other" and the caller
// handles them (pipeline-registry.md). They are not pipeline discriminators for
// the six-pipeline split, so reads of them are not banned.
const DISCRIMINATORS = new Set([
  "chorale", "umto_chorale", "chorale_identification",
  "harmonization", "figured_bass", "figured_bass_pcs",
  "identification", "matching",
  "playback", "analysis_match", "play-all-voices", "analysis",
  "play",
]);

// Field names whose raw reads route a pipeline. staffDistribution is a layout
// axis distinct from pipeline, but its literal "chorale" overloads TYPE_CHORALE
// (forms.py declares DISTRIBUTION_CHORALE = "chorale" separately from
// TYPE_CHORALE = "chorale"). Reads of the staffDistribution field are matched so
// the overload is visible at the lint layer; pure axis-consumer sites carry an
// inline exemption (see stave_note_factory.js).
const FIELD_NAMES = new Set(["type", "mode", "analysisType", "staffDistribution"]);

// Repo-relative paths where raw discriminator strings are authoritative.
const ALLOWED_PATH_SUFFIXES = [
  "lab/static/js/src/models/resolved_mode.js",
  "lab/static/js/src/models/grader_factory.js",
  "lab/static/js/src/models/exercise_definition.js",
  "lab/static/js/src/models/input_method_logic.js",
  "lab/static/js/src/models/harmonization_targets_logic.js",
  "lab/static/js/src/models/chord.js",
  "lab/static/js/src/components/music/chordal_umto_staff_distribution.js",
];

function isAllowedFile(filename) {
  if (!filename) return false;
  if (filename.endsWith(".test.js")) return true;
  return ALLOWED_PATH_SUFFIXES.some((suffix) => filename.endsWith(suffix));
}

function literalStringValue(node) {
  if (!node) return null;
  if (node.type === "Literal" && typeof node.value === "string") return node.value;
  return null;
}

function isDiscriminatorLiteral(node) {
  const v = literalStringValue(node);
  return v !== null && DISCRIMINATORS.has(v);
}

// True if `node` reads a raw type/mode/analysisType/staffDistribution field —
// the comparison shapes banned outside resolver/factory/axis modules.
function isDiscriminatorAccess(node) {
  if (!node) return false;
  // obj.type / obj.mode / obj.staffDistribution / obj.analysisType (any depth, non-computed)
  if (node.type === "MemberExpression" && !node.computed && node.property &&
      node.property.type === "Identifier") {
    return FIELD_NAMES.has(node.property.name);
  }
  // obj["mode"] / obj["type"] / ... (computed access with a string-literal key)
  if (node.type === "MemberExpression" && node.computed) {
    const key = literalStringValue(node.property);
    return key !== null && FIELD_NAMES.has(key);
  }
  // getMode() — bare call OR method call (this.getMode() / definition.getMode())
  if (node.type === "CallExpression" && node.callee) {
    if (node.callee.type === "Identifier" && node.callee.name === "getMode") {
      return true;
    }
    if (node.callee.type === "MemberExpression" && !node.callee.computed &&
        node.callee.property && node.callee.property.type === "Identifier" &&
        node.callee.property.name === "getMode") {
      return true;
    }
  }
  // data.get("mode") / data.get("type") / ... (Backbone-style accessor)
  if (node.type === "CallExpression" && node.callee &&
      node.callee.type === "MemberExpression" && !node.callee.computed &&
      node.callee.property && node.callee.property.type === "Identifier" &&
      node.callee.property.name === "get" &&
      node.arguments && node.arguments.length >= 1) {
    const argVal = literalStringValue(node.arguments[0]);
    return argVal !== null && FIELD_NAMES.has(argVal);
  }
  // bare staffDistribution === "<discriminator>". Known limitation: this is
  // AST-shape-based, not dataflow. Uppercase aliases (e.g. chord.js's
  // STAFF_DISTRIBUTION) and local-variable aliases (`var m = def.mode; m ===
  // "playback"`) escape the match. Allowlisted axis modules cover the known
  // aliased axis-consumer sites (chord.js); raw pipeline-routing reads that
  // alias a type/mode local outside an allowlisted file would not be caught —
  // acceptable per the plan's AST-lint scope (a dataflow rule is out of scope).
  if (node.type === "Identifier" && node.name === "staffDistribution") {
    return true;
  }
  return false;
}

const rule = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow raw pipeline-discriminator comparisons (type/mode/analysisType/staffDistribution === \"<discriminator>\") outside the resolver, factory, and confirmed-pure axis modules. Route through ResolvedMode instead.",
    },
    schema: [],
    messages: {
      raw:
        "Raw pipeline-discriminator comparison ({{lhs}} {{op}} {{rhs}}). Read the discriminator through ResolvedMode (resolved.pipeline / resolved.exerciseType / resolved.interactionMode / resolved.analysisKind / resolved.staffStyle) instead of comparing a raw type/mode/analysisType/staffDistribution string. See docs/architecture/pipeline-registry.md.",
    },
  },
  create(context) {
    const filename = (context.filename || (context.getFilename && context.getFilename()) || "");
    if (isAllowedFile(filename)) return {};
    return {
      BinaryExpression(node) {
        if (node.operator !== "==" && node.operator !== "===" &&
            node.operator !== "!=" && node.operator !== "!==") {
          return;
        }
        const leftIsDisc = isDiscriminatorLiteral(node.left);
        const rightIsDisc = isDiscriminatorLiteral(node.right);
        if (leftIsDisc && isDiscriminatorAccess(node.right)) {
          context.report({
            node,
            messageId: "raw",
            data: {
              op: node.operator,
              lhs: context.sourceCode.getText(node.left),
              rhs: context.sourceCode.getText(node.right),
            },
          });
        } else if (rightIsDisc && isDiscriminatorAccess(node.left)) {
          context.report({
            node,
            messageId: "raw",
            data: {
              op: node.operator,
              lhs: context.sourceCode.getText(node.left),
              rhs: context.sourceCode.getText(node.right),
            },
          });
        }
      },
    };
  },
};

export default rule;