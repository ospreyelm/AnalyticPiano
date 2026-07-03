/* Run: node lab/static/js/src/config/feedback_catalog.test.js */
"use strict";
var mod = require("./feedback_catalog");
mod = mod.default || mod;
var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a); }
}

assertEqual("get type", mod.get("harmonization.click.note_cap").category, "soft_constraint");
assertEqual("get unknown null", mod.get("nope.nope"), null);

assertEqual("fmt none", mod.format("Hi", null), "Hi");
assertEqual("fmt one", mod.format("Up to {n} notes", { n: 4 }), "Up to 4 notes");
assertEqual("fmt missing kept", mod.format("Hi {who}", {}), "Hi {who}");

var r = mod.render("exercise.grade.correct", null);
assertEqual("render surface", r.surface, "anchored");
assertEqual("render body", r.body, "Yes — that's right.");
assertEqual("render timeout", r.timeoutMs, 1500);
assertEqual("render unknown null", mod.render("nope", null), null);

assertEqual("resolve universal", mod.resolveGradeFeedbackId("unknownType", "incorrect", null), "exercise.grade.incorrect");
assertEqual("resolve per-type", mod.resolveGradeFeedbackId("chorale", "incorrect", null), "chorale.grade.incorrect");
assertEqual("resolve per-skill", mod.resolveGradeFeedbackId("harmonization", "incorrect", "wrong_inversion"), "harmonization.grade.incorrect.wrong_inversion");
assertEqual("resolve per-skill missing -> per-type", mod.resolveGradeFeedbackId("harmonization", "incorrect", "no_such"), "harmonization.grade.incorrect");

// R3: figured-bass feedback body names intervals above the bass, never "inversion".
var wi = mod.render("harmonization.grade.incorrect.wrong_inversion", null);
assertEqual("wrong_inversion body has no 'inversion'",
  wi && wi.body.toLowerCase().indexOf("inversion") === -1, true);
assertEqual("wrong_inversion body names intervals above the bass",
  wi && wi.body.indexOf("intervals above the bass") !== -1, true);
assertEqual("resolve per-type missing -> universal", mod.resolveGradeFeedbackId("identification", "partial", null), "exercise.grade.partial");
assertEqual("resolve unknown state null", mod.resolveGradeFeedbackId("chorale", "bogus", null), null);

var ev = mod.buildEvent("harmonization.grade.incorrect", { exerciseId: "EX1", unit: 9, complexity: 3, skillTags: ["V7"] }, 123);
assertEqual("ev id", ev.feedbackId, "harmonization.grade.incorrect");
assertEqual("ev category", ev.category, "recoverable_mistake");
assertEqual("ev unit", ev.unit, 9);
assertEqual("ev ts", ev.ts, 123);

// play.save.* entries (Task 2 — Play authoring feedback catalog)
var ps = mod.render("play.save.success", null);
assertEqual("play.save.success truthy", !!ps, true);

var pim = mod.render("play.save.invalid_meter", { bar: 3, beats: 5, expected: 4 });
assertEqual("play.save.invalid_meter truthy", !!pim, true);
assertEqual("play.save.invalid_meter interpolates bar", pim && pim.body.indexOf("3") !== -1, true);

var pe = mod.render("play.save.empty", null);
assertEqual("play.save.empty truthy", !!pe, true);

if (fail > 0) { console.error("\n" + fail + " test(s) failed"); process.exit(1); }
console.log("\nAll tests passed");
