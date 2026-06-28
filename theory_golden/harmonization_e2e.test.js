"use strict";

var fs = require("fs");
var path = require("path");
var grader = require("../lab/static/js/src/models/harmonization_grader_logic");

var failed = 0;

function fail(label, detail) {
  console.log("FAIL:", label);
  if (detail) console.log("  " + detail);
  failed += 1;
}
function pass(label) { console.log("PASS:", label); }

function reasonsContainAll(reasons, expected) {
  for (var i = 0; i < expected.length; i += 1) {
    if (reasons.indexOf(expected[i]) === -1) return false;
  }
  return true;
}

var golden = JSON.parse(
  fs.readFileSync(path.join(__dirname, "harmonization_e2e.json"), "utf8")
);

golden.cases.forEach(function (c) {
  var targets = c.expected.targets;
  var canon = c.expected.canonical_realization || [];
  var wrongs = c.expected.wrong_realizations || [];

  // Non-vacuity guards: a case with empty arrays must NOT pass silently.
  if (targets.length === 0) fail(c.id + " has no targets");
  if (canon.length === 0) fail(c.id + " has no canonical_realization (cannot prove JS accepts)");
  if (wrongs.length === 0) fail(c.id + " has no wrong_realizations (cannot prove JS rejects)");
  targets.forEach(function (t) {
    var covered = canon.some(function (r) { return r.offset === t.offset; });
    if (!covered) fail(c.id + " target offset " + t.offset + " has no canonical_realization");
  });

  canon.forEach(function (real) {
    var target = targets.filter(function (t) { return t.offset === real.offset; })[0];
    if (!target) { fail(c.id + " canonical: no target at offset " + real.offset); return; }
    var res = grader.harmonizationMatch(target, real.midis);
    if (res.accepted) pass(c.id + " canonical accepted @offset " + real.offset);
    else fail(c.id + " canonical should be accepted @offset " + real.offset, "reasons: " + JSON.stringify(res.reasons));
  });

  wrongs.forEach(function (real, idx) {
    var target = targets.filter(function (t) { return t.offset === real.offset; })[0];
    if (!target) { fail(c.id + " wrong[" + idx + "]: no target at offset " + real.offset); return; }
    var res = grader.harmonizationMatch(target, real.midis);
    var rejected = res.accepted === false;
    var hasReasons = reasonsContainAll(res.reasons, real.expected_reasons);
    if (rejected && hasReasons) pass(c.id + " wrong[" + idx + "] rejected with expected reasons");
    else fail(c.id + " wrong[" + idx + "] should be rejected with " + JSON.stringify(real.expected_reasons),
              "accepted=" + res.accepted + " reasons=" + JSON.stringify(res.reasons));
  });
});

if (failed > 0) { console.log("\n" + failed + " test(s) FAILED"); process.exit(1); }
else { console.log("\nAll tests passed."); }
