/* Run: node lab/static/js/src/config/figured_bass_hints.test.js */
"use strict";
var { requireDefault } = require("../../test/require_esm");
var mod = requireDefault(require("./figured_bass_hints"));
var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a); }
}
function assertContains(label, haystack, needle) {
  if (haystack && haystack.indexOf(needle) !== -1) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  missing: " + JSON.stringify(needle) + "\n  in:      " + JSON.stringify(haystack)); }
}

// --- expandFigure mirrors figures.py:expand_figure_string ---
assertEqual("expand 6", mod.expandFigure("6"), ["6", "3"]);
assertEqual("expand 7", mod.expandFigure("7"), ["7", "5", "3"]);
assertEqual("expand 6/4", mod.expandFigure("6/4"), ["6", "4"]);
assertEqual("expand 4/2", mod.expandFigure("4/2"), ["6", "4", "2"]);
assertEqual("expand empty -> 5/3", mod.expandFigure(""), ["5", "3"]);

// --- requiredNumbersFor: pure lookup ---
assertEqual("req 6 @ 3-4", mod.requiredNumbersFor("6", { min: 3, max: 4 }), [3, 6]);
assertEqual("req 7 @ 3-4", mod.requiredNumbersFor("7", { min: 3, max: 4 }), [3, 7]);
assertEqual("req 6/4 @ 3-4", mod.requiredNumbersFor("6/4", { min: 3, max: 4 }), [4, 6]);
assertEqual("req 4/2 @ 3-4", mod.requiredNumbersFor("4/2", { min: 3, max: 4 }), [2, 4]);
assertEqual("req unknown figure -> null", mod.requiredNumbersFor("ZZZ", { min: 3, max: 4 }), null);

// --- mock definitions ---
function harmDef(targets) {
  return {
    getHarmonizationTargets: function () { return targets; },
    getAnalysisType: function () { return "figured_bass"; },
  };
}
function identDef(answers) {
  // Mirrors the real shape buildUMTOIdentificationProblems produces: a flat
  // `answer` string per problem (already the correctly-shaped figure for
  // this exercise's analysisType), not a `.content.figured_bass` object --
  // problems never carry a `.content` key.
  return {
    getProblems: function () {
      return answers.map(function (a) { return { answer: a, hidden: !a }; });
    },
    getAnalysisType: function () { return "figured_bass"; },
  };
}

// --- Harmonization, abbreviated ---
// 6/4 at {3,4}: 6 and 4 both essential, [+8] doubling (no 2/9).
var d64 = harmDef([{ displayFigure: "6/4", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "4"] }]);
var h64 = mod.buildHarmonizationHints(d64, "figured_bass");
assertContains("harm 6/4 has essential 6-4", h64.hints[0], "6/4 → 6-4");
assertContains("harm 6/4 marks [+8] doubling", h64.hints[0], "[+8]");
assertContains("harm 6/4 has no omittable parens (5)", h64.hints[0], "6-4-[+8]");
assertEqual("harm 6/4 moreInfo flag", h64.moreInfo, true);
assertContains("harm help names intervals above the bass", h64.help, "intervals above the bass");
assertEqual("harm help never says inversion", h64.help.toLowerCase().indexOf("inversion"), -1);

// 7 at {3,4}: 7,3 essential; 5 omittable; [+8].
var d7 = harmDef([{ displayFigure: "7", voiceCountPolicy: { min: 3, max: 4 }, figures: ["7", "5", "3"] }]);
var h7 = mod.buildHarmonizationHints(d7, "figured_bass");
assertContains("harm 7 essential 7-3", h7.hints[0], "7-3");
assertContains("harm 7 omittable (5)", h7.hints[0], "(5)");
assertContains("harm 7 [+8]", h7.hints[0], "[+8]");

// 4/2 at {3,4}: 4,2 essential; 6 omittable; NO [+8] (has 2).
var d42 = harmDef([{ displayFigure: "4/2", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "4", "2"] }]);
var h42 = mod.buildHarmonizationHints(d42, "figured_bass");
assertContains("harm 4/2 essential 4-2", h42.hints[0], "4-2");
assertContains("harm 4/2 omittable (6)", h42.hints[0], "(6)");
assertEqual("harm 4/2 no [+8] (has 2)", h42.hints[0].indexOf("[+8]"), -1);

// --- Harmonization, unabbreviated: reads target.figures, parenthesizes 8 ---
var dUn = harmDef([{ displayFigure: "8/6/3", figures: ["8", "6", "3"], voiceCountPolicy: { min: 3, max: 4 } }]);
var hUn = mod.buildHarmonizationHints(dUn, "figured_bass_unabbreviated");
assertContains("unabb reads figures stack (8)-6-3", hUn.hints[0], "(8)-6-3");
assertContains("unabb help mentions octave", hUn.help, "octave (8)");

// --- no targets -> null (fallback signal) ---
assertEqual("harm no targets -> null", mod.buildHarmonizationHints(harmDef([]), "figured_bass"), null);

// --- figure absent from lookup -> null (whole-exercise fallback) ---
var dBad = harmDef([{ displayFigure: "ZZZ", voiceCountPolicy: { min: 3, max: 4 }, figures: ["Z"] }]);
assertEqual("harm unknown figure -> null", mod.buildHarmonizationHints(dBad, "figured_bass"), null);

// --- distinct figures collapse; one line per distinct figure ---
var dMulti = harmDef([
  { displayFigure: "6", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "3"] },
  { displayFigure: "6/4", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "4"] },
  { displayFigure: "6", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "3"] },
]);
var hMulti = mod.buildHarmonizationHints(dMulti, "figured_bass");
// "6" should appear once as a figure key, "6/4" once.
var sixCount = (hMulti.hints[0].match(/6 → /g) || []).length;
assertEqual("harm dedupes 6 to one line", sixCount, 1);
assertContains("harm multi has 6/4 line", hMulti.hints[0], "6/4 →");

// --- each distinct figure uses its OWN target's voiceCountPolicy, not targets[0] ---
// Two targets with different figures and different policies. The fix ensures
// each figure's required-numbers line reflects the policy from the target
// that actually has that figure, not from targets[0].
var dDiffPolicies = harmDef([
  { displayFigure: "6", voiceCountPolicy: { min: 3, max: 4 }, figures: ["6", "3"] },
  { displayFigure: "7", voiceCountPolicy: { min: 3, max: 4 }, figures: ["7", "5", "3"] },
]);
var hDiffPolicies = mod.buildHarmonizationHints(dDiffPolicies, "figured_bass");
// Both figures should render successfully with their respective policies.
assertContains("harm diff-policy 6 renders", hDiffPolicies.hints[0], "6 →");
assertContains("harm diff-policy 7 renders", hDiffPolicies.hints[0], "7 →");
// Verify the essential/omittable breakdown is correct for each.
assertContains("harm diff-policy 6 shows essential 6-3", hDiffPolicies.hints[0], "6 → 6-3");
assertContains("harm diff-policy 7 shows essential 7-3 and omittable (5)", hDiffPolicies.hints[0], "7 → 7-3-(5)");

// --- Identification, abbreviated: dedupes distinct figures, plain expansion ---
var dI = identDef(["6", "7", "6"]);
var iH = mod.buildIdentificationHints(dI, "figured_bass");
var sixExpansions = (iH.hints[0].match(/6 → 6-3/g) || []).length;
assertEqual("ident dedupes 6 expansion", sixExpansions, 1);
assertContains("ident has 7 expansion", iH.hints[0], "7 → 7-5-3");
assertContains("ident help says abbreviated", iH.help, "abbreviated");
assertEqual("ident help never says inversion", iH.help.toLowerCase().indexOf("inversion"), -1);

// --- Identification, unabbreviated ---
var dIu = identDef(["8/6/3", "8/5/3"]);
var iHu = mod.buildIdentificationHints(dIu, "figured_bass_unabbreviated");
assertContains("ident unabb lists 8/6/3", iHu.hints[0], "8/6/3");
assertContains("ident unabb help mentions octave", iHu.help, "octave (8)");

// --- hidden problems (non-target slices) excluded from distinct figures ---
var dHidden = identDef(["6"]);
dHidden.getProblems = function () {
  return [{ answer: "6", hidden: false }, { answer: "7", hidden: true }];
};
var iHHidden = mod.buildIdentificationHints(dHidden, "figured_bass");
assertEqual("ident excludes hidden problem's figure", iHHidden.hints[0].indexOf("7 →"), -1);

// --- no FB slices -> null ---
assertEqual("ident no slices -> null", mod.buildIdentificationHints(identDef([]), "figured_bass"), null);
assertEqual("ident no answer field -> null",
  mod.buildIdentificationHints(identDef([null]), "figured_bass"), null);

// --- Roman-numeral identification: distinct-numeral list from p.answer ---
function romanDef(answers) {
  return {
    getProblems: function () {
      return answers.map(function (a) { return { answer: a, hidden: !a }; });
    },
  };
}
var dRoman = romanDef(["I", "V", "I"]);
var iRoman = mod.buildRomanIdentificationHints(dRoman);
assertEqual("roman dedupes and lists distinct numerals in exercise order", iRoman.hints[0], "This exercise uses: I, V.");
assertContains("roman help worked example uses I from this exercise", iRoman.help, "A I chord = 1, 3, 5 of the key = Do-Mi-So.");
assertContains("roman help worked example uses V from this exercise", iRoman.help, "A V chord = 5, 7, 2 of the key = So-Ti-Re.");
assertEqual("roman help excludes unused IV example", iRoman.help.indexOf("A IV chord"), -1);
assertEqual("roman help never says inversion", iRoman.help.toLowerCase().indexOf("inversion"), -1);

// --- inverted numeral (I6) maps to base triad's worked example, once ---
var dRomanInv = romanDef(["I", "I6"]);
var iRomanInv = mod.buildRomanIdentificationHints(dRomanInv);
var iCount = (iRomanInv.help.match(/A I chord/g) || []).length;
assertEqual("roman collapses I and I6 to one worked example", iCount, 1);

// --- chromatic/secondary numeral not in the safe table -> no fabricated example ---
var dRomanChromatic = romanDef(["V/V"]);
var iRomanChromatic = mod.buildRomanIdentificationHints(dRomanChromatic);
assertEqual("roman omits example for unrecognized numeral", iRomanChromatic.help.indexOf(" chord = "), -1);
assertContains("roman still names quality symbols generically", iRomanChromatic.help, "Uppercase = major");

// --- hidden problems excluded from distinct numerals ---
var dRomanHidden = {
  getProblems: function () {
    return [{ answer: "I", hidden: false }, { answer: "V", hidden: true }];
  },
};
var iRomanHidden = mod.buildRomanIdentificationHints(dRomanHidden);
assertEqual("roman excludes hidden problem's numeral", iRomanHidden.hints[0].indexOf("V"), -1);

// --- no problems -> null ---
assertEqual("roman no problems -> null", mod.buildRomanIdentificationHints(romanDef([])), null);
assertEqual("roman no answer field -> null", mod.buildRomanIdentificationHints(romanDef([null])), null);

// --- MORE_INFO_URL exported ---
assertContains("more-info url exported", mod.MORE_INFO_URL, "gettysburg");

// --- RN help leads with key-first + circle of thirds (plan R1, W1) ---
assertContains("roman help says identify the key first", iRoman.help, "identify the key");
assertContains("roman help introduces the circle of thirds", iRoman.help, "circle of thirds");
assertContains("roman help names the wheel order", iRoman.help, "C-E-G-B-D-F-A");
assertEqual("roman help never says third-stacking (stacked thirds)", iRoman.help.toLowerCase().indexOf("stacked third"), -1);
// Solfège scale degrees come BEFORE the circle of thirds (product-owner order).
assertEqual("roman help: solfege Do-Mi-So precedes circle of thirds",
  iRoman.help.indexOf("Do-Mi-So") < iRoman.help.indexOf("circle of thirds"), true);
assertEqual("roman hints: solfege position step precedes wheel step",
  iRoman.hints.join("\n").indexOf("Do-Mi-So = I") < iRoman.hints.join("\n").indexOf("Find the root with the circle of thirds"), true);

// --- Seventh-chord RN (plan S1, S2): worked example + seventh hint step ---
var dRoman7 = romanDef(["I", "V7", "vii°7"]);
var iRoman7 = mod.buildRomanIdentificationHints(dRoman7);
assertContains("roman7 help has V7 worked example with qualityPair", iRoman7.help, "A V7 chord = 5, 7, 2, 4 of the key = So-Ti-Re-Fa = Major-minor.");
assertContains("roman7 help has vii°7 worked example (half-diminished)", iRoman7.help, "A vii°7 chord = 7, 2, 4, 6 of the key = Ti-Re-Fa-La = diminished-minor.");
assertContains("roman7 hints list the exercise's numerals incl. sevenths", iRoman7.hints[0], "This exercise uses: I, V7, vii°7.");
assertContains("roman7 has a seventh-chord hint step", iRoman7.hints.join(" "), "A seventh chord adds a seventh above the root");

// --- Triad-only exercise does NOT fabricate a seventh example ---
var dRomanTriadOnly = romanDef(["I", "V"]);
var iTriadOnly = mod.buildRomanIdentificationHints(dRomanTriadOnly);
assertEqual("roman triad-only help has no seventh worked example", iTriadOnly.help.indexOf("7 chord = "), -1);

// --- 6/5 figure is detected as a seventh chord; 6/4 is not ---
var dInv7 = romanDef(["V6/5"]);
var iInv7 = mod.buildRomanIdentificationHints(dInv7);
assertContains("roman V6/5 detected as seventh -> worked example", iInv7.help, "A V7 chord = ");
var dTriadInv = romanDef(["V6/4"]);
var iTriadInv = mod.buildRomanIdentificationHints(dTriadInv);
assertEqual("roman V6/4 not treated as seventh", iTriadInv.help.indexOf("7 chord = "), -1);

// --- F2: alteration rule present in figured-bass hints ---
assertContains("harm hints state the alteration rule", h64.hints.join(" "), "Alterations:");
assertContains("ident hints state the alteration rule", iH.hints.join(" "), "Alterations:");
assertContains("ident unabb hints state the alteration rule", iHu.hints.join(" "), "Alterations:");

if (fail > 0) { console.error("\n" + fail + " test(s) failed"); process.exit(1); }
console.log("\nAll tests passed");