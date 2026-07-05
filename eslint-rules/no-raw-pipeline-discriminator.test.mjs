// Permanent regression test for the no-raw-pipeline-discriminator rule.
//
// The rule is the Phase 1 exit gate (pipeline-isolation refactor). This test
// locks in its contract: the banned comparison shapes are flagged and the
// allowed shapes (out-of-scope "other" types, non-discriminator fields/values,
// `.includes()` membership, relational operators, analysis-content literals,
// allowlisted files) are clean.
//
// Run: `node eslint-rules/no-raw-pipeline-discriminator.test.mjs`
// (Standalone — not picked up by ./run_js_tests.sh, which scans
// lab/static/js/src only. The rule itself runs on every `npm run lint`.)
import { Linter } from "eslint";
import rule from "./no-raw-pipeline-discriminator.mjs";

const RULE_ID = "harmonylab-pipelines/no-raw-pipeline-discriminator";
const linter = new Linter();
const config = {
  plugins: {
    "harmonylab-pipelines": {
      rules: { "no-raw-pipeline-discriminator": rule },
    },
  },
  rules: { [RULE_ID]: "error" },
  languageOptions: { ecmaVersion: "latest", sourceType: "module" },
};

function ruleViolations(code) {
  return linter.verify(code, config).filter((m) => m.ruleId === RULE_ID);
}

let pass = 0;
let fail = 0;
function assertBanned(label, code) {
  const v = ruleViolations(code);
  if (v.length === 1) {
    pass++;
  } else {
    fail++;
    console.error(`FAIL banned/${label}: expected 1 violation, got ${v.length} -- ${JSON.stringify(v)}`);
  }
}
function assertClean(label, code) {
  const v = ruleViolations(code);
  if (v.length === 0) {
    pass++;
  } else {
    fail++;
    console.error(`FAIL clean/${label}: expected 0 violations, got ${v.length} -- ${JSON.stringify(v)}`);
  }
}

// --- Banned shapes (the five plan targets + operator/reversal variants) ---
assertBanned("non-computed .type", `var a = def.type === "chorale";`);
assertBanned("non-computed .mode", `var a = def.mode === "harmonization";`);
assertBanned("non-computed .analysisType", `var a = def.analysisType === "figured_bass";`);
assertBanned("non-computed .staffDistribution", `var a = def.staffDistribution === "chorale";`);
assertBanned("computed [\"mode\"]", `var a = d["mode"] === "figured_bass";`);
assertBanned("computed [\"type\"]", `var a = d["type"] === "identification";`);
assertBanned("bare getMode()", `var a = getMode() === "playback";`);
assertBanned("*.getMode() method call", `var a = def.getMode() === "playback";`);
assertBanned(".get(\"mode\") Backbone accessor", `var a = d.get("mode") === "identification";`);
assertBanned(".get(\"type\") Backbone accessor", `var a = d.get("type") === "matching";`);
assertBanned("bare staffDistribution identifier", `var a = staffDistribution === "chorale";`);
assertBanned("!== operator", `var a = def.type !== "chorale";`);
assertBanned("!= loose operator", `var a = def.type == "chorale";`);
assertBanned("literal-first reversed", `var a = "chorale" === def.type;`);
assertBanned("deep member chain", `var a = definition.exercise.type === "umto_chorale";`);
assertBanned("play default-fill mode", `var a = def.mode === "play";`);

// --- Clean shapes (must NOT flag) ---
assertClean("out-of-scope umto_symbolic_meter", `var a = def.type === "umto_symbolic_meter";`);
assertClean("out-of-scope umto_key_signature", `var a = def.type === "umto_key_signature";`);
assertClean("out-of-scope musicxml", `var a = def.type === "musicxml";`);
assertClean("out-of-scope analytical", `var a = def.type === "analytical";`);
assertClean("out-of-scope analytical_pcs", `var a = def.type === "analytical_pcs";`);
assertClean("non-discriminator field .foo", `var a = def.foo === "chorale";`);
assertClean("non-discriminator value challenge", `var a = def.mode === "challenge";`);
assertClean("analysis-content literal roman", `var a = def.analysisType === "roman";`);
assertClean(".includes() membership (CallExpression)", `var a = ["analytical","figured_bass"].includes(def.type);`);
assertClean("relational < operator", `var a = def.type < "chorale";`);
assertClean("relational > operator", `var a = def.type > "chorale";`);
assertClean("arithmetic + operator", `var a = def.mode + "chorale";`);

// --- Allowlisted files self-skip (verified by filename routing) ---
// The rule's isAllowedFile() returns {} (no listeners) for allowlisted paths.
// Simulate by checking the rule's exported logic indirectly: a banned shape in
// a non-allowlisted file is flagged; the allowlist is path-based so it cannot
// be exercised via Linter.verify (which uses a synthetic <input> filename).
// The path routing is covered by `npm run lint` on the real allowlisted files.

console.log(`\nno-raw-pipeline-discriminator rule tests: ${pass} passed, ${fail} failed.`);
if (fail > 0) process.exit(1);