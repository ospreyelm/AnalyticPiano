// Figured-bass hint builder — pure functions, no DOM access.
//
// Reads the generated lookup in figured_bass_hints_data.js (_SHORTHANDS and
// _REQUIRED_NUMBERS_BY_FIGURE) and the per-target fields already shipped on
// every harmonization target (figures, displayFigure, voiceCountPolicy) to
// build progressive hint arrays that match the pedagogy taught in this
// project. Figured bass names intervals ABOVE THE BASS — never use the word
// "inversion" in hint prose. See docs/music-theory-canon.md (§"Figured bass")
// and AGENTS.md (theory-sensitive changes require a distinguishing example).
//
// Notation: essential intervals plain; named-but-omittable tones in parens;
// the bass doubled at the octave as a separate [+8] marker (never a named
// requirement). Computed from the exercise's voiceCountPolicy via the same
// Python-computed required-numbers lookup the grader trusts, so a hint can
// never contradict what the grader accepts for the same target.
"use strict";

import DATA from "./figured_bass_hints_data.js";

var _SHORTHANDS = DATA._SHORTHANDS || {};
var _REQUIRED_NUMBERS_BY_FIGURE = DATA._REQUIRED_NUMBERS_BY_FIGURE || {};

// Authoritative reading-figured-bass reference (matches the canon pedagogy;
// contains no "inversion"). Rendered as a real anchor by the render layer.
var MORE_INFO_URL = "https://musictheory.sites.gettysburg.edu/unit-4-1/reading-figured-bass/";

// Static explanation page for Roman-numeral / circle-of-thirds / chord-quality
// pedagogy, built (spike §5 of plan 2026-07-04) from the Triad teaching-extract
// package. Served as a plain static file — no Django route or UMTO wiring.
var ROMAN_EXPLANATION_URL = "/static/reference/triads-circle-of-thirds/index.html";

// Voice-count policy {min,max} -> the lookup key used by the generated table.
function _policyKey(voiceCountPolicy) {
  var p = voiceCountPolicy || {};
  var lo = p.min != null ? p.min : 3;
  var hi = p.max != null ? p.max : 4;
  return lo + "-" + hi;
}

// Number (int) of a figure token like "#6", "5°", "4+", "8". 0 if unparseable.
function _tokenNumber(token) {
  var m = String(token).match(/\d+/);
  return m ? parseInt(m[0], 10) : 0;
}

// True for an altered token (carries #, b, n, °, or +) — altered tones are
// always required, but this is only used here to short-circuit omit-marking.
function _isAlteredToken(token) {
  return /[#bn°+]/.test(String(token));
}

// Abbreviated figure -> interval token list, via _SHORTHANDS.
// Mirrors figures.py:expand_figure_string.
function expandFigure(abbrev) {
  var text = (abbrev || "").trim();
  if (_SHORTHANDS.hasOwnProperty(text)) {
    return _SHORTHANDS[text].slice();
  }
  if (text === "#" || text === "b" || text === "n") {
    return [text + "3", "5"];
  }
  var tokens = text.split("/").map(function (t) { return t.trim(); }).filter(Boolean);
  return tokens.length ? tokens : _SHORTHANDS[""].slice();
}

// Required generic-interval numbers for (figure, voiceCountPolicy).
// Pure lookup into the generated table; returns null when the figure or
// policy shape is not in the table (caller falls back to static hints).
function requiredNumbersFor(figureString, voiceCountPolicy) {
  var byFigure = _REQUIRED_NUMBERS_BY_FIGURE[figureString];
  if (!byFigure) return null;
  var arr = byFigure[_policyKey(voiceCountPolicy)];
  return arr || null;
}

// Render one figure's essential/omittable/[+8] line.
// Grouping: essential (plain) first, then omittable (parens), then [+8].
function _renderNotationLine(figure, voiceCountPolicy) {
  var expanded = expandFigure(figure);
  var required = requiredNumbersFor(figure, voiceCountPolicy);
  if (!required) return null;
  var requiredSet = {};
  required.forEach(function (n) { requiredSet[n] = true; });

  var has2or9 = false;
  expanded.forEach(function (tok) {
    var n = _tokenNumber(tok);
    if (n === 2 || n === 9) has2or9 = true;
  });

  var essential = [], omittable = [];
  expanded.forEach(function (tok) {
    var n = _tokenNumber(tok);
    if (n === 8) return; // 8 is the doubling marker, handled separately
    if (requiredSet[n] || _isAlteredToken(tok)) {
      essential.push(tok);
    } else {
      omittable.push(tok);
    }
  });

  var parts = [];
  if (essential.length) parts.push(essential.join("-"));
  omittable.forEach(function (tok) { parts.push("(" + tok + ")"); });
  // The bass doubled at the octave is an optional doubling, never a named
  // requirement. A chord containing 2 or 9 never doubles the bass at the
  // octave (figure_realization TABLE invariant) -> no [+8] there.
  if (!has2or9) parts.push("[+8]");

  return parts.join("-");
}

function _distinctDisplayFigures(targets) {
  var seen = {}, out = [];
  targets.forEach(function (t) {
    var f = t && t.displayFigure;
    if (f && !seen.hasOwnProperty(f)) {
      seen[f] = true;
      out.push({ figure: f, voiceCountPolicy: t.voiceCountPolicy || null });
    }
  });
  return out;
}

// Harmonization hints. Returns {help, hints, moreInfo} or null (fallback).
function buildHarmonizationHints(definition, analysisType) {
  var targets = definition && definition.getHarmonizationTargets
    ? definition.getHarmonizationTargets()
    : (definition && definition.harmonizationTargets) || [];
  if (!targets.length) return null;

  if (analysisType === "figured_bass_unabbreviated") {
    // Unabbreviated: each target's `figures` already carries the raw stack
    // (idempotent-expanded, includes the 8). Parenthesize the doubling 8.
    var lines = [];
    targets.forEach(function (t) {
      var figs = (t && t.figures) || [];
      if (!figs.length) return;
      var rendered = figs.map(function (tok) {
        return _tokenNumber(tok) === 8 ? "(8)" : tok;
      }).join("-");
      lines.push(rendered);
    });
    if (!lines.length) return null;
    return {
      help: "This exercise uses unabbreviated figures — every interval above the bass is written, including the octave (8). The figures appear below the staff. Read each number as a generic interval from the bass and play those pitches.",
      hints: [
        "Per chord: " + lines.join("  |  ") + ". The (8) is the bass doubled at the octave — optional.",
        "The 8 is the bass doubled at the octave — optional. The other numbers are the intervals above the bass you must sound.",
      ],
      moreInfo: true,
    };
  }

  // Abbreviated (figured_bass): per-figure essential/omittable/[+8] line.
  var figures = _distinctDisplayFigures(targets);
  var figureLines = [];
  for (var i = 0; i < figures.length; i++) {
    var figureEntry = figures[i];
    var policy = figureEntry.voiceCountPolicy || null;
    var line = _renderNotationLine(figureEntry.figure, policy);
    if (!line) return null; // figure not in lookup -> whole-exercise fallback
    figureLines.push(figureEntry.figure + " → " + line);
  }
  if (!figureLines.length) return null;

  return {
    help: "Each measure shows a figured-bass symbol below the staff. The figures name intervals above the bass — count up from the bass note to find those pitches, then press Lock Chord. Parentheses mark tones you may drop in sparse texture or double in four.",
    hints: [
      "Per figure: " + figureLines.join("  |  ") + ".",
      "Count from the bass: 3 = two staff steps up, 5 = four steps, 6 = five steps, 7 = six steps. The plain numbers are the ones you must keep; the parenthesized ones you may drop or double.",
      // F2 — alteration rule. Paraphrased from Triad deck slide 16 `figured-bass-alterations`.
      "Alterations: an accidental next to a number adds that accidental to that generic interval above the bass; a '+' (or strikethrough) raises the interval, a '-' lowers it. Otherwise the note comes from the key signature.",
    ],
    moreInfo: true,
  };
}

// Identification / chorale_identification hints. Returns {help, hints, moreInfo} or null.
function buildIdentificationHints(definition, analysisType) {
  var problems = definition && definition.getProblems
    ? definition.getProblems()
    : (definition && definition.problems) || [];
  if (!problems.length) return null;

  var unabbreviated = analysisType === "figured_bass_unabbreviated";
  // Problems built by buildUMTOIdentificationProblems (and the older
  // chord-array identification path) never carry a `.content` object on the
  // final problem — figured_bass/raw_figured_bass are read from the analysis
  // slice's `.content` only while computing `answer`, upstream, at parse
  // time. `p.answer` is already the correctly-shaped figure string for this
  // exercise's analysisType (abbreviated or raw/unabbreviated, matching the
  // same branch this function was gated on) — read that directly instead of
  // a `.content` shape that doesn't exist on the built problem objects.
  var seen = {}, distinct = [];
  problems.forEach(function (p) {
    if (!p || p.hidden) return;
    var fig = p.answer;
    if (fig && !seen.hasOwnProperty(fig)) { seen[fig] = true; distinct.push(fig); }
  });
  if (!distinct.length) return null;

  if (unabbreviated) {
    return {
      help: "Choose the unabbreviated figure — list every generic interval above the bass, including the octave (8). A triad with the third in the bass is 8/6/3, not 6.",
      hints: [
        "Distinct figures in this exercise: " + distinct.join("  |  ") + ".",
        // F2 — alteration rule (Triad deck slide 16).
        "Alterations: an accidental next to a number adds that accidental to that generic interval above the bass; a '+' (or strikethrough) raises it, a '-' lowers it. Otherwise the note comes from the key signature.",
      ],
      moreInfo: true,
    };
  }

  // Abbreviated: plain expansion table for the distinct figures present.
  var expansions = distinct.map(function (fig) {
    return fig + " → " + expandFigure(fig).join("-");
  });
  return {
    help: "Choose the abbreviated figure. Abbreviations drop redundant intervals — 6 stands for 6-3, 7 for 7-5-3, 6/4 for 6-4, 4/2 (or 2) for 6-4-2. The figure names intervals above the bass, not a chord name.",
    hints: [
      "Expansions: " + expansions.join("  |  ") + ".",
      // F2 — alteration rule (Triad deck slide 16).
      "Alterations: an accidental next to a number adds that accidental to that generic interval above the bass; a '+' (or strikethrough) raises it, a '-' lowers it. Otherwise the note comes from the key signature.",
    ],
    moreInfo: true,
  };
}

// Root-position tone set for each diatonic major-key triad, root-third-fifth
// order. Verified digit-by-digit against this app's own analysis tables
// (config/analysis/jChords.js chord-tone sets against jDegreesNew.js
// degree->solfege) — not a hand-guessed table. Chromatic/secondary/minor-key
// numerals (V/V, vii°/vi, i, iv, Ger, ...) are deliberately absent: their
// scale-degree spelling depends on key-mode context this builder doesn't
// have, and a wrong worked example is worse than none.
var _MAJOR_DIATONIC_TRIADS = {
  "I": { degrees: "1, 3, 5", solfege: "Do-Mi-So" },
  "ii": { degrees: "2, 4, 6", solfege: "Re-Fa-La" },
  "iii": { degrees: "3, 5, 7", solfege: "Mi-So-Ti" },
  "IV": { degrees: "4, 6, 1", solfege: "Fa-La-Do" },
  "V": { degrees: "5, 7, 2", solfege: "So-Ti-Re" },
  "vi": { degrees: "6, 1, 3", solfege: "La-Do-Mi" },
  "vii°": { degrees: "7, 2, 4", solfege: "Ti-Re-Fa" },
};

// Diatonic seventh chords on each major-key scale degree, root-third-fifth-
// seventh order, with the triad-quality / seventh-quality pairing taught in
// the MUS 141 "RN and Seventh Chord" deck (slide 16 `seventh-chord-quality-1`,
// notation id `s16-scale-degree-seventh-qualities`). Verified against the
// app's analysis tables the same way the triad table is. The grader already
// distinguishes half-diminished (viiø7, hChords.js `36y`) from fully-
// diminished (vii°7, hChords.js `369`) — different structures, both handled.
// Same major-only conservatism as the triad table.
var _MAJOR_DIATONIC_SEVENTHS = {
  "I":     { degrees: "1, 3, 5, 7", solfege: "Do-Mi-So-Ti", qualityPair: "Major-Major" },
  "ii":    { degrees: "2, 4, 6, 1", solfege: "Re-Fa-La-Do", qualityPair: "minor-minor" },
  "iii":   { degrees: "3, 5, 7, 2", solfege: "Mi-So-Ti-Re", qualityPair: "minor-minor" },
  "IV":    { degrees: "4, 6, 1, 3", solfege: "Fa-La-Do-Mi", qualityPair: "Major-Major" },
  "V":     { degrees: "5, 7, 2, 4", solfege: "So-Ti-Re-Fa", qualityPair: "Major-minor" },
  "vi":    { degrees: "6, 1, 3, 5", solfege: "La-Do-Mi-So", qualityPair: "minor-minor" },
  "vii°":  { degrees: "7, 2, 4, 6", solfege: "Ti-Re-Fa-La", qualityPair: "diminished-minor" },
};

// Strip a trailing figured-bass suffix (e.g. "V6/5" -> "V", "I6" -> "I") to
// get the base numeral. Roman-numeral names never end in a digit themselves.
function _baseRomanNumeral(label) {
  return String(label).replace(/[0-9/]+$/, "").trim();
}

// Trailing figured-bass suffix of a Roman-numeral label (digits, slashes, and
// the quality marks °/+ that travel with the figure). Used to detect whether
// a numeral carries a seventh-chord figure (7, 6/5, 4/3, 4/2) vs a triad
// figure (6, 6/4, or none). 6/4 is a triad inversion; 6/5, 4/3, 4/2 are
// seventh-chord inversions.
function _figureSuffix(label) {
  var m = String(label).match(/[0-9/°+]+$/);
  return m ? m[0] : "";
}
function _isSeventhNumeral(label) {
  var s = _figureSuffix(label);
  return /7/.test(s) || /6\/5/.test(s) || /4\/3/.test(s) || /4\/2/.test(s);
}

// Roman-numeral identification / chorale_identification hints. Returns
// {help, hints} or null (fallback to static instructions). Lists the actual
// Roman numerals used in THIS exercise (via the same p.answer/p.hidden shape
// the figured-bass builder reads) instead of a fixed textbook catalog.
//
// Mental model (per product-owner sign-off on plan
// docs/superpowers/plans/2026-07-04-roman-numeral-chord-hints-from-teaching-extracts.md):
// lead with the **circle of thirds** wheel (always the same order
// C-E-G-B-D-F-A; root = furthest counter-clockwise before the large gap of a
// fourth) — paraphrased from the MUS 141 "RN and Seventh Chord" deck slide 15
// `seventh-chords-root-finding` and the "Triad Intro" deck slide 8. The wheel
// is NOT the "stacked-thirds" construction commit 9ed9442e removed; it is a
// different, memorable framing, and it yields the same root the grader's
// syllable-pattern logic (analyze.js) rewards. Solfège stays as a secondary
// step.
function buildRomanIdentificationHints(definition) {
  var problems = definition && definition.getProblems
    ? definition.getProblems()
    : (definition && definition.problems) || [];
  if (!problems.length) return null;

  var seen = {}, distinct = [];
  problems.forEach(function (p) {
    if (!p || p.hidden) return;
    var rn = p.answer;
    if (rn && !seen.hasOwnProperty(rn)) { seen[rn] = true; distinct.push(rn); }
  });
  if (!distinct.length) return null;

  var seenBase = {}, examples = [];
  distinct.forEach(function (rn) {
    var base = _baseRomanNumeral(rn);
    var entry = _MAJOR_DIATONIC_TRIADS[base];
    if (entry && !seenBase.hasOwnProperty(base)) {
      seenBase[base] = true;
      examples.push("A " + base + " chord = " + entry.degrees + " of the key = " + entry.solfege + ".");
    }
  });

  // Seventh-chord worked examples (plan Item S1) — only for numerals that
  // actually carry a seventh figure in THIS exercise, and only for the safe
  // major-diatonic table. Mirrors deck slide 16 qualityPair values.
  var seenBase7 = {}, sevenExamples = [];
  distinct.forEach(function (rn) {
    if (!_isSeventhNumeral(rn)) return;
    var base = _baseRomanNumeral(rn);
    var entry = _MAJOR_DIATONIC_SEVENTHS[base];
    if (entry && !seenBase7.hasOwnProperty(base)) {
      seenBase7[base] = true;
      sevenExamples.push("A " + base + "7 chord = " + entry.degrees + " of the key = " + entry.solfege + " = " + entry.qualityPair + ".");
    }
  });

  // Help = the lead idea only: name the RN by scale-degree slot, with a
  // worked triad example per numeral in THIS exercise, and the symbol legend.
  // Seventh worked examples live in the seventh hint step (not help) so the
  // help stays short. The circle-of-thirds wheel, full quality derivation, and
  // figure/seventh detail live on the explanation page (moreInfoUrl) — the
  // hint panel keeps 3-4 short steps then links there.
  var help = "Name the Roman numeral by where the chord sits in the key.";
  if (examples.length) help += " " + examples.join(" ");
  help += " Uppercase = major, lowercase = minor, ° = diminished, + = augmented.";

  // 3-4 hints max, one idea each, no repeats, conditional on what's in the
  // exercise. Order: orient → key → solfège quality → (figure | seventh).
  var hints = [
    "This exercise uses: " + distinct.join(", ") + ".",
    // R1 — identify the key first (RN deck slide 9).
    "First identify the key — Roman numerals have no meaning without one.",
    // Solfège quality — the grader's syllable-pattern mental model.
    "Quality comes from which syllables are present: Do-Mi-So = major, Do-Me-So = minor, Do-Me-Se = diminished, Do-Mi-Si = augmented.",
  ];

  // 4th step — only the most-relevant extra tip, conditional on the exercise.
  // Position (6, 6/4) comes from the FIGURE (intervals above the bass), not a
  // solfège permutation — per docs/music-theory-canon.md §"Figured bass".
  if (sevenExamples.length) {
    hints.push("A seventh chord adds a seventh above the root to a triad; name its quality in two parts — the triad quality, then the seventh (root→seventh). " + sevenExamples.join(" "));
  } else {
    var hasFigure = distinct.some(function (rn) { return _figureSuffix(rn) !== ""; });
    if (hasFigure) {
      hints.push("The figure after the numeral names intervals above the bass, like figured bass: 6 = 6/3 (third in the bass), 6/4 = a 4th and 6th above the bass, 7 = 7/5/3, 6/5 = 6/5/3.");
    }
  }

  return {
    help: help,
    hints: hints,
    // Link to the explanation page (the static circle-of-thirds + qualities
    // lesson built from the Triad teaching-extract package). The render layer
    // appends this as the final hint step.
    moreInfo: true,
    moreInfoUrl: ROMAN_EXPLANATION_URL,
  };
}

export default {
  MORE_INFO_URL: MORE_INFO_URL,
  expandFigure: expandFigure,
  requiredNumbersFor: requiredNumbersFor,
  buildHarmonizationHints: buildHarmonizationHints,
  buildIdentificationHints: buildIdentificationHints,
  buildRomanIdentificationHints: buildRomanIdentificationHints,
};