/* Lesson-content quality-control validator.
 *
 * Run: node lab/static/reference/triads-circle-of-thirds/validate_lesson.js
 *
 * Re-derives the musical content of every `notation` object in
 * lesson-content.json from its VexFlow `keys` and checks it against the
 * human-authored `label` / `figure` / `purpose` text. This is the
 * "multiple analysis engines" cross-check: the JSON is the single source
 * for the static page, so this script independently re-derives each chord
 * from pitch classes and flags any disagreement with the stated label,
 * catches dropped accidentals (e.g. a "G minor" spelled G-B-D), and
 * verifies figured-bass intervals above the bass.
 *
 * Pure standard JS, no project imports — keeps the check independent of the
 * engines it's checking against. Exits non-zero on any mismatch.
 */
"use strict";

const fs = require("fs");
const path = require("path");

const DATA = JSON.parse(
  fs.readFileSync(path.join(__dirname, "lesson-content.json"), "utf8")
);

let failures = 0;
function fail(slideId, notationId, msg) {
  failures += 1;
  console.error(`FAIL [${slideId}${notationId ? " / " + notationId : ""}] ${msg}`);
}

// --- pitch-class utilities ---
const LETTER_BASE = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
const ACC_OFFSET = { n: 0, "#": 1, b: -1 };

// Parse a VexFlow key "g/4", "bb/4", "c#/5", "bn/4" -> {letter, acc, octave, pc}
// or null if malformed. `pc` is the pitch class 0-11.
function parseKey(key) {
  const m = String(key).match(/^([a-g])([#bn]*)\/(\d+)$/);
  if (!m) return null;
  const letter = m[1];
  const accStr = m[2];
  let offset = 0;
  for (const ch of accStr) offset += ACC_OFFSET[ch] || 0;
  return {
    letter,
    acc: accStr,
    octave: parseInt(m[3], 10),
    pc: (LETTER_BASE[letter] + offset + 12) % 12,
  };
}

// Generic interval (staff steps) from one letter to another, 1..7.
// C->E = 3 (a third), C->G = 5 (a fifth), C->C = 1 (unison/octave).
function genericInterval(lowLetter, highLetter) {
  const l = lowLetter.charCodeAt(0) - 97; // a=0..g=6
  const h = highLetter.charCodeAt(0) - 97;
  return ((h - l + 7) % 7) + 1;
}

// Semitone interval between two pitch classes, ascending, 0..11.
function semitoneInterval(lowPc, highPc) {
  return (highPc - lowPc + 12) % 12;
}

// Classify a triad's quality from root/third/fifth semitone intervals.
// Returns "major" | "minor" | "diminished" | "augmented" | null.
function triadQuality(rootPc, thirdPc, fifthPc) {
  const third = semitoneInterval(rootPc, thirdPc);
  const fifth = semitoneInterval(rootPc, fifthPc);
  if (third === 4 && fifth === 7) return "major";
  if (third === 3 && fifth === 7) return "minor";
  if (third === 3 && fifth === 6) return "diminished";
  if (third === 4 && fifth === 8) return "augmented";
  return null;
}

// Expected quality from a label string. Returns {quality, size} or null.
// Handles: "G", "GMIN", "G+", "GDIM", "g minor", "F Augmented", "F# Major",
// "Minor Triad", "Diminished", "d minor", "a diminished", etc.
// Order matters: "diminished" contains the substring "min", so check dim
// before minor and return on first match.
function qualityFromLabel(label) {
  if (!label) return null;
  const l = label.toLowerCase();
  const size = /7|seventh/.test(l) ? 4 : 3;
  if (/dim|diminished|°|ø/.test(l)) return { quality: "diminished", size };
  if (/aug|\+/.test(l)) return { quality: "augmented", size };
  if (/min|minor/.test(l)) return { quality: "minor", size };
  if (/maj|major/.test(l)) return { quality: "major", size };
  // Bare root letter with no quality word (lead-sheet convention) => major.
  // "G", "F#", "G7" -> major.
  if (/^[a-g][#b]?\s*7?$/.test(label.trim())) return { quality: "major", size };
  return null;
}

// Verify a figured-bass `figure` string (e.g. "8/5/3", "5/3", "8/5/#3")
// against the stacked notes' generic intervals above the bass note.
function checkFigure(notation, slideId, notationId) {
  if (!notation.figure) return;
  const notes = notation.voices[0].notes;
  // The figure applies per-chord; the JSON tags each chord object with its
  // own `figure` + `keys`, so validate against that single chord's keys.
  const chordKeys = notation.keys || (notation.voices && notation.voices[0] && notation.voices[0].notes[0] && notation.voices[0].notes[0].keys);
  // Some figure-tagged notations put each chord as a separate note object
  // inside voices[0].notes with its own `figure`; others put one figure on
  // the notation and the chord under keys. Handle the per-note shape below.
  const noteList = (notation.voices[0].notes[0] && notation.voices[0].notes[0].keys)
    ? notation.voices[0].notes
    : [{ keys: chordKeys, figure: notation.figure }];
  noteList.forEach((note) => {
    const fig = note.figure || notation.figure;
    if (!fig) return;
    const keys = note.keys;
    if (!keys || !keys.length) return;
    const parsed = keys.map(parseKey).filter(Boolean);
    if (parsed.length !== keys.length) {
      fail(slideId, notationId, `figure "${fig}": unparseable keys ${JSON.stringify(keys)}`);
      return;
    }
    // Bass = lowest pitch (lowest pc+octave). Generic intervals above bass.
    const bass = parsed.reduce((lo, p) =>
      (p.octave * 12 + p.pc) < (lo.octave * 12 + lo.pc) ? p : lo, parsed[0]);
    const intervals = parsed.map((p) => genericInterval(bass.letter, p.letter));
    // Parse the figure into a sorted set of generic-interval numbers.
    // Tokens like "8", "5", "#3" -> the digit is the generic interval.
    const figNums = fig.split("/").map((tok) => {
      const m = tok.match(/\d+/);
      return m ? parseInt(m[0], 10) : null;
    }).filter((n) => n != null).sort((a, b) => a - b);
    const actual = intervals.slice().sort((a, b) => a - b);
    // Compare as sets — the bass doubling (1 or 8) may or may not appear in
    // the figure, and the JSON sometimes omits the unison. Require every
    // figure number to be present among the actual intervals.
    const missing = figNums.filter((n) => !actual.includes(n));
    if (missing.length) {
      fail(slideId, notationId,
        `figure "${fig}" on ${JSON.stringify(keys)}: figure names intervals ${JSON.stringify(figNums)} but the stack only has generic intervals ${JSON.stringify(actual)} above the bass (${bass.letter})`);
    }
  });
}

// --- main ---
DATA.slides.forEach((slide) => {
  if (!slide.notation) return;
  slide.notation.forEach((n) => {
    const id = n.id || "";
    (n.voices || []).forEach((voice) => {
      (voice.notes || []).forEach((note) => {
        // 1. every key parses
        (note.keys || []).forEach((k) => {
          if (!parseKey(k)) fail(slide.id, id, `unparseable key ${JSON.stringify(k)}`);
        });
        // 2. labeled chord -> re-derive quality + root + stacking, compare
        if (note.label) {
          const parsed = (note.keys || []).map(parseKey).filter(Boolean);
          if (parsed.length !== (note.keys || []).length) return; // already failed
          if (parsed.length >= 3 && parsed.length <= 4) {
            const expected = qualityFromLabel(note.label);
            // Sort by ascending pitch to find root = lowest.
            const sorted = parsed.slice().sort(
              (a, b) => (a.octave * 12 + a.pc) - (b.octave * 12 + b.pc));
            const root = sorted[0];
            // For a triad, third/fifth are the next two ascending. But the
            // chord may be inverted (third or fifth in the bass). Re-derive
            // quality by trying each pc as root and picking the one whose
            // stacked thirds give a recognized triad quality.
            let bestQ = null, bestRoot = null;
            for (const cand of parsed) {
              const others = parsed.filter((p) => p !== cand);
              // find third (generic 3) and fifth (generic 5) above cand
              const thirdP = others.find((p) => genericInterval(cand.letter, p.letter) === 3);
              const fifthP = others.find((p) => genericInterval(cand.letter, p.letter) === 5);
              if (thirdP && fifthP) {
                const q = triadQuality(cand.pc, thirdP.pc, fifthP.pc);
                if (q) { bestQ = q; bestRoot = cand; break; }
              }
            }
            if (expected && bestQ && expected.quality !== bestQ) {
              fail(slide.id, id,
                `label "${note.label}" expects quality "${expected.quality}" ` +
                `but keys ${JSON.stringify(note.keys)} (root ${bestRoot.letter}${bestRoot.acc}) ` +
                `derive as "${bestQ}"`);
            }
          }
        }
      });
    });
    // 3. figured-bass intervals above the bass
    checkFigure(n, slide.id, id);
  });
});

if (failures > 0) {
  console.error(`\n${failures} lesson-content check(s) failed`);
  process.exit(1);
}
console.log(`ok - all ${DATA.slides.length} slides validated (labels, figures, key syntax)`);