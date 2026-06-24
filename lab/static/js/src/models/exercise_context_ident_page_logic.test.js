"use strict";

var IdentPageLogic = require("./exercise_context_ident_page_logic");

var pass = 0, fail = 0;
function eq(label, actual, expected) {
  var ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (ok) { console.log("  PASS: " + label); pass++; }
  else { console.log("  FAIL: " + label + "\n    got:  " + JSON.stringify(actual) + "\n    want: " + JSON.stringify(expected)); fail++; }
}

// --- getChoralePageMeasureCount ---
eq("maxMeasures=4 → 4",      IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 4 }), 4);
eq("maxMeasures=8 → 8",      IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 8 }), 8);
eq("maxMeasures=0 → default 4",
  IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: 0 }), 4);
eq("maxMeasures='bad' → default 4",
  IdentPageLogic.getChoralePageMeasureCount({ maxMeasures: "notanumber" }), 4);
eq("null display → default 4",  IdentPageLogic.getChoralePageMeasureCount(null), 4);
eq("empty display → default 4", IdentPageLogic.getChoralePageMeasureCount({}), 4);

// --- computeTotalIdentPages (non-chorale) ---
var p5 = [{}, {}, {}, {}, {}];
eq("5 probs pageSize=4 → 2",   IdentPageLogic.computeTotalIdentPages(p5, false, 0, 0, 4), 2);
eq("4 probs pageSize=4 → 1",   IdentPageLogic.computeTotalIdentPages([{},{},{},{}], false, 0, 0, 4), 1);
eq("0 probs → 0",              IdentPageLogic.computeTotalIdentPages([], false, 0, 0, 4), 0);
eq("1 prob pageSize=4 → 1",    IdentPageLogic.computeTotalIdentPages([{}], false, 0, 0, 4), 1);

// --- computeTotalIdentPages (chorale) ---
eq("chorale 8 measures max=4 → 2", IdentPageLogic.computeTotalIdentPages(p5, true, 8, 4, 4), 2);
eq("chorale 0 probs → 1 (special)", IdentPageLogic.computeTotalIdentPages([], true, 8, 4, 4), 1);
eq("chorale 3 measures max=4 → 1", IdentPageLogic.computeTotalIdentPages(p5, true, 3, 4, 4), 1);
eq("chorale 9 measures max=4 → 3", IdentPageLogic.computeTotalIdentPages(p5, true, 9, 4, 4), 3);

// --- computeIdentPageOffset (non-chorale) ---
eq("page=0 size=4 → 0", IdentPageLogic.computeIdentPageOffset(0, 4, false, [], 0, 0), 0);
eq("page=1 size=4 → 4", IdentPageLogic.computeIdentPageOffset(1, 4, false, [], 0, 0), 4);
eq("page=2 size=4 → 8", IdentPageLogic.computeIdentPageOffset(2, 4, false, [], 0, 0), 8);

// --- computeIdentPageOffset (chorale) ---
// problems: measureIndex 0,1,4,5; totalMeasures=8, maxMeasures=4
var cp = [
  { measureIndex: 0 }, { measureIndex: 1 },
  { measureIndex: 4 }, { measureIndex: 5 },
];
// page=0: targetMeasure=0, lastPossibleStart=4; first prob measureIndex>=0 → index 0
eq("chorale page=0 → 0", IdentPageLogic.computeIdentPageOffset(0, 4, true, cp, 8, 4), 0);
// page=1: targetMeasure=4, lastPossibleStart=4; first prob measureIndex>=4 → index 2
eq("chorale page=1 → 2", IdentPageLogic.computeIdentPageOffset(1, 4, true, cp, 8, 4), 2);
// page=3: targetMeasure=12>lastPossibleStart=4 → clamp to 4 → same as page=1 → 2
eq("chorale page=3 clamped → 2", IdentPageLogic.computeIdentPageOffset(3, 4, true, cp, 8, 4), 2);
// no problem has measureIndex >= targetMeasure → returns problems.length
var cpShort = [{ measureIndex: 0 }];
eq("no matching problem → problems.length",
  IdentPageLogic.computeIdentPageOffset(1, 4, true, cpShort, 8, 4), 1);

// --- filterVisibleProblems (non-chorale) ---
var ap = [{id:0},{id:1},{id:2},{id:3},{id:4},{id:5}];
var vis0 = IdentPageLogic.filterVisibleProblems(ap, false, 0, 4, 0, 0);
eq("page=0 size=4: 4 visible", vis0.length, 4);
eq("page=0 first id=0", vis0[0].id, 0);
var vis1 = IdentPageLogic.filterVisibleProblems(ap, false, 1, 4, 0, 0);
eq("page=1 size=4: 2 visible", vis1.length, 2);
eq("page=1 first id=4", vis1[0].id, 4);

// --- filterVisibleProblems (chorale) ---
// measures 0,1,3 on page 0 (0–3); measures 4,5,7 on page 1 (4–7)
var cap = [
  { measureIndex: 0 }, { measureIndex: 1 }, { measureIndex: 3 },
  { measureIndex: 4 }, { measureIndex: 5 }, { measureIndex: 7 },
];
var chVis0 = IdentPageLogic.filterVisibleProblems(cap, true, 0, 4, 8, 4);
eq("chorale page=0: 3 probs (measures 0–3)", chVis0.length, 3);
var chVis1 = IdentPageLogic.filterVisibleProblems(cap, true, 1, 4, 8, 4);
eq("chorale page=1: 3 probs (measures 4–7)", chVis1.length, 3);

console.log("\n" + pass + " passed, " + fail + " failed");
if (fail > 0) process.exit(1);
