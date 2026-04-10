# Chorale Harmonic Analysis — How It Works

This document explains how Roman numeral and figured-bass annotations are generated for chorale exercises. The short answer: **analysis is computed on the fly from raw pitch content and the key signature. No pre-computed labels are stored anywhere in the CIR score files.**

---

## What the CIR JSON files contain

Bach chorale source files (`data/corpus/bach/*.json`) have four top-level keys:

| Key | Contents |
|-----|----------|
| `source` | Provenance / attribution metadata |
| `score` | Raw music: `meta` (key, time signature) + `measures` (staves, voices, pitches, durations) |
| `events` | Per-onset MIDI numbers grouped by staff (used by the grader) |
| `tags` | Generic string tags (e.g. `"corpus:bach-chorales"`) |

There are **no stored Roman numerals, chord labels, or figured-bass annotations** in these files. The `meta` object only carries `key` and `time` (e.g. `{ "key": "F", "time": "4/4" }`).

---

## Where analysis labels come from

Analysis is produced at render time by two collaborating modules:

### 1. `vexflow_adapter.js` — builds harmonic windows

`buildAnalysisWindows(timeline)` (line ~302) groups the score timeline by onset. For each window it:

1. Filters out notes whose duration has expired at the current onset (tracking "held" notes).
2. Collects all MIDI pitches that are **sounding** (new attacks + held-overs) into `win.midiStack`.
3. Stores the attack-only pitch list as `win.attackKey` for column matching during rendering.

The window's `midiStack` therefore represents the full harmonic stack (not just the new notes), which is what gets analysed.

### 2. `utils/analyze.js` — identifies the chord

An `Analyze` instance is created with the exercise's key signature (from `score.meta.key`). Two entry points are used:

- **Roman numerals** — `computeRomanLabel(midi, analyzer)` calls `analyzer.to_chord(midi, "roman only")` → `analyzer.ijFindChord(notes)`. This performs a lookup in `config/analysis/jChords.js` (major keys) or `config/analysis/iChords.js` (minor keys), keyed by the chord's diatonic interval profile above the bass.

- **Figured bass / thoroughbass** — `computeFiguredLabel(midi, analyzer)` calls `analyzer.full_thoroughbass_figure(midi)` or `analyzer.abbrev_thoroughbass_figure(midi)`, which compute intervals above the bass arithmetically and format them as stacked numerals.

Both functions return a text label (or `null` if the chord is unrecognised) that is then drawn below the bass stave as a VexFlow `TextNote` annotation.

---

## The `display` flags are render toggles only

`import_chorale.py` stores `showRomans: false` and `showFigures: false` in the exercise's `display` object. These are **display-only switches** — they do not affect how analysis data is stored or computed. When either flag is true (or when `exercise_sheet.js` force-enables them for chorale mode), the adapter runs the analysis pipeline above on each rendered onset column.

```javascript
// exercise_sheet.js (excerpt)
if (wantsRomans || isChorale) {
    analyzeConfig.enabled = true;
    analyzeConfig.mode.roman_numerals = true;   // computed from pitch content
}
if (wantsFigures) {
    analyzeConfig.mode.thoroughbass = true;      // computed from intervals
}
```

Toggling these flags costs nothing in terms of stored data — the labels are always regenerated from the score on each render.

---

## Summary of the pipeline

```
score.meta.key  ──────────────────────────────────────────┐
                                                           ▼
score.measures  →  vexflow_adapter buildAnalysisWindows   →  midiStack per onset
                                                           ▼
                                                   Analyze(keySignature)
                                                   .to_chord(midiStack)   →  Roman numeral label
                                                   .full_thoroughbass_figure(midiStack) → Figured-bass label
                                                           ▼
                                                   VexFlow TextNote drawn below bass stave
```

---

## Key source files

| File | Role |
|------|------|
| `lab/static/js/src/utils/analyze.js` | `Analyze` class — all chord/interval identification |
| `lab/static/js/src/config/analysis/jChords.js` | Roman numeral lookup table (major keys) |
| `lab/static/js/src/config/analysis/iChords.js` | Roman numeral lookup table (minor keys) |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | `buildAnalysisWindows`, `computeRomanLabel`, `computeFiguredLabel`, render loop |
| `lab/static/js/src/components/music/exercise_sheet.js` | Enables analysis for chorale mode via `analyzeConfig` |
| `apps/exercises/management/commands/import_chorale.py` | Stores `display.showRomans` / `display.showFigures` flags (defaults `false`) |
