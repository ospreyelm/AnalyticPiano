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
    ],
    moreInfo: true,
  };
}

export default {
  MORE_INFO_URL: MORE_INFO_URL,
  expandFigure: expandFigure,
  requiredNumbersFor: requiredNumbersFor,
  buildHarmonizationHints: buildHarmonizationHints,
  buildIdentificationHints: buildIdentificationHints,
};