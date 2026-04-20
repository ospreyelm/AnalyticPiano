# Design: `applySkillFilter` — `UNIT_ALLOWED_ANSWERS` Map

**Date:** 2026-04-19
**Status:** Approved
**File affected:** `lab/static/js/src/models/exercise_definition.js`

## Problem

`applySkillFilter` (lines 37–67) has two paths:

1. **Unit 9 hardcoded block** (lines 43–54) — works correctly, hides all Roman numeral slots except `I`, `i`, `V`, `V7`.
2. **Generic path** (lines 56–59) — strips `unit:N_` prefix from tags and calls `answer.startsWith(cleanTag)`. Broken: `Dominant_Seventh` does not match `V7`; `V` matches `VI` and `vii`. No unit beyond 9 filters correctly.

## Goal

Replace both paths with a single `UNIT_ALLOWED_ANSWERS` map. Every unit in the map gets correct, auditable, cumulative filtering. Units outside the map (21+, or any non-roman analysis type) pass through unmodified.

## Scope

- **In scope:** `roman` analysisType only. Units 9–20.
- **Out of scope:** `figured_bass`, pitch analysis types (`note_name`, `solfege`, etc.), interval types. These pass through unchanged.
- **Not changed:** `buildChoraleIdentificationProblems`, `playlistSkillTags` data flow, anything outside `applySkillFilter`.

## The Map

Cumulative — each unit includes all Roman numeral answers introduced in prior units. Derived from `music_theory_taxonomy_with_branches.json` `feat` fields, with explicit translation to answer strings as produced by `computeWindowLabel`.

```javascript
var UNIT_ALLOWED_ANSWERS = {
  // Unit 9: Tonic & dominant — I, V, V7 root position
  9: ['I', 'i', 'V', 'V7'],

  // Unit 10: First inversions — adds I6, V6, vii°6
  10: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6'],

  // Unit 11: Pre-dominants — adds IV, ii, ii6, vi
  11: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI'],

  // Unit 12: Second inversions — adds I64, V64
  12: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64'],

  // Unit 13: Rule of the octave — adds iii, III, full diatonic set
  13: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII'],

  // Unit 14: Diatonic seventh chords — adds ii7, IV7, vi7, iii7, vii°7
  14: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII',
       'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7'],

  // Unit 15: Sequences — no new chord types, same set as 14
  15: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII',
       'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7'],

  // Unit 16: Applied (secondary) chords — adds V/x, V7/x, vii°/x, vii°7/x
  16: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII',
       'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
       'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
       'V/vi', 'V7/vi', 'V/III', 'V7/III',
       'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
       'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV'],

  // Unit 17: Modal mixture — adds iv, bVI, bVII, bIII (already have iv from unit 11)
  17: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII',
       'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
       'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
       'V/vi', 'V7/vi', 'V/III', 'V7/III',
       'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
       'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV',
       'bVI', 'bVII', 'bIII', 'ii°', 'ii°6'],

  // Unit 18: Neapolitan & augmented sixths
  18: ['I', 'i', 'V', 'V7', 'I6', 'i6', 'V6', 'vii°6',
       'IV', 'iv', 'ii', 'ii6', 'vi', 'VI',
       'I64', 'V64',
       'iii', 'III', 'VII',
       'ii7', 'ii°7', 'IV7', 'vi7', 'iii7', 'vii°7', 'viio7',
       'V/ii', 'V7/ii', 'V/IV', 'V7/IV', 'V/V', 'V7/V',
       'V/vi', 'V7/vi', 'V/III', 'V7/III',
       'vii°/ii', 'vii°7/ii', 'vii°/V', 'vii°7/V',
       'vii°/vi', 'vii°7/vi', 'vii°/IV', 'vii°7/IV',
       'bVI', 'bVII', 'bIII', 'ii°', 'ii°6',
       'N6', 'It+6', 'Ger+6', 'Fr+6'],

  // Units 19–20: Modulation — no new Roman numeral types within a key;
  // filter passes through (same allowlist as 18). Modulation exercises
  // span two keys; both keys' full diatonic + chromatic sets are visible.
  19: null,  // → pass through (modulation: show all)
  20: null,  // → pass through (modulation: show all)
};
```

`null` entries = pass through unmodified. Modulation exercises span tonal centres; filtering by a single key's allowlist would incorrectly hide legitimate chords in the new key.

## Updated `applySkillFilter` Logic

```javascript
function applySkillFilter(problems, skillTags, analysisType) {
  if (!skillTags || skillTags.length === 0) return problems;

  // Only filter roman numeral exercises — all other types pass through
  if ((analysisType || 'roman') !== 'roman') return problems;

  // Extract unit number from any 'unit:N' tag
  var unitNum = null;
  _.each(skillTags, function(t) {
    var m = t.match(/^unit:(\d+)/);
    if (m) unitNum = parseInt(m[1], 10);
  });

  // No unit tag → pass through
  if (unitNum === null) return problems;

  // Unit not in map → pass through (safe fallback for units 21+)
  if (!UNIT_ALLOWED_ANSWERS.hasOwnProperty(unitNum)) return problems;

  var allowed = UNIT_ALLOWED_ANSWERS[unitNum];

  // null entry (e.g. units 19–20) → pass through
  if (allowed === null) return problems;

  return _.map(problems, function(p) {
    if (p.hidden) return p;
    if (allowed.indexOf(p.answer) === -1) {
      p = _.clone(p);
      p.hidden = true;
    }
    return p;
  });
}
```

`analysisType` is passed as third argument. Call site (line 762) passes `exercise.analysisType`.

Key differences from current code:
- Third `analysisType` arg guards non-roman exercises at entry — nothing filtered, nothing hidden
- Extracts unit number via regex — handles `unit:9`, `unit:9_diatonic_triads`, `unit:9_Dominant_Seventh` all equally
- Uses `indexOf` exact match — no `startsWith` false matches (`V` no longer matches `VI`, `vii`)
- Clones problem before mutating (defensive)
- Single unified path for all units

## Fallback Behaviour Summary

| Condition | Result |
|---|---|
| `analysisType` ≠ `roman` | Pass through — show all problems |
| No `unit:N` tag on playlist | Pass through — show all problems |
| Unit in map with array | Hide problems not in allowlist |
| Unit in map with `null` (units 19–20) | Pass through — show all problems |
| Unit not in map (21+) | Pass through — show all problems |

## Answer String Conventions

Answer strings must match exactly what `computeWindowLabel` produces. Key conventions:

- Degree symbol: `°` (not `o` or `0`)
- Half-diminished: `ø` (not `%`)
- Slash chords: `V/V`, `V7/V` (slash, no spaces)
- Augmented sixths: `It+6`, `Ger+6`, `Fr+6`
- Neapolitan: `N6`
- Flat prefix: `b` (ASCII, not `♭`)

**Note:** The exact strings depend on what `computeWindowLabel` / `Analyze` emits. The map entries above are based on taxonomy descriptions and must be **verified against real exercise output** during implementation. The testing step below covers this.

## Testing

1. **Unit 9 regression:** Load existing Unit 9 playlist → confirm only `I/i/V/V7` visible. Identical behaviour to current code.
2. **Unit 11 smoke test:** Tag a test playlist `unit:11`, load a phrase with `IV` and `V/V` → `IV` slot visible, `V/V` slot hidden.
3. **Pass-through:** Tag playlist `unit:22` → all slots visible.
4. **Non-roman pass-through:** Tag playlist `unit:9`, use `figured_bass` exercise → all slots visible (analysisType guard fires).
5. **Answer string verification:** During implementation, `console.log(p.answer)` for a Unit 16 exercise to confirm secondary chord format matches map entries. Adjust map if needed.

## Files Changed

| File | Change |
|---|---|
| `lab/static/js/src/models/exercise_definition.js` | Replace `applySkillFilter` (lines 37–67) with new implementation; add `UNIT_ALLOWED_ANSWERS` map above it; update call site at line 762 to pass `exercise.analysisType` as third arg |
