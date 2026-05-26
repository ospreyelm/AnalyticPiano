# Branch B: Bass Scale-Degree Labels Below Staff

**Date:** 2026-05-26  
**Scope:** Branch B clausulae exercises only (`analysisType === "clausula"`)  
**Files changed:**
- `lab/static/js/src/components/music/rendering/vexflow_adapter.js` — 1 helper added, ~15 lines in existing branch
- `lab/static/js/src/components/music/exercise_sheet.js` — pass `analysisType` opt to `VexFlowAdapter.render()`

---

## Goal

When a Branch B clausulae exercise has a bass voice, display circled Arabic scale-degree numerals (①②③④⑤⑥⑦) **below the bass staff** — one label per onset column where the bass attacks. This is the Baroque convention for bass-degree labeling and must not affect core-sequence exercises.

---

## Context

### Data already in place

`generate_clausulae_b1.py` already computes circled numerals and stores them in `AnalysisLayer.functional_label` for each analysis slice:

- Simple cadences (B2–B4): labels at ANT/PEN/ULT offsets (e.g. `["①", "⑤", "①"]`)
- Compound cadences (B11–B12): labels at offsets 0/2/4; offset 1 (no bass attack) is `""`

The generator already sets `display.showScaleDegrees = True` and `analysisType = "clausula"` on Branch B exercises.

### Current rendering problem — two issues

1. **Treble-above leakage:** `renderScaleDegrees` → `drawScaleDegreeAbove` → `_drawScaleDegreeList` falls back to `analyzer.to_scale_degree()` when no `scale_degrees` map exists. Branch B has no `scale_degrees` entries, so the analyzer derives and draws labels above the treble staff. These are unwanted.

2. **No bass-below draw:** There is no code path that reads `functional_label` and places a label below the bass staff.

### `analysisType` flow

`to_frontend_payload(analysis_type="clausula")` puts `analysisType: "clausula"` in the top-level exercise payload. `exercise_sheet.js` calls `definition.getAnalysisType()` to read it, but does **not** currently pass it into `VexFlowAdapter.render()`. The adapter needs it to gate Branch-B-specific behavior.

---

## Design

### Fix 1: Pass `analysisType` into `VexFlowAdapter.render()`

In `exercise_sheet.js`, add `analysisType` to the opts object passed to `VexFlowAdapter.render()`:

```javascript
VexFlowAdapter.render(score, this.vexRenderer, {
  // ... existing opts ...
  analysisType: definition.getAnalysisType ? definition.getAnalysisType() : null,
});
```

Inside the adapter's `render` function, read it from opts:

```javascript
var analysisType = (opts && opts.analysisType) || null;
var isClausula = analysisType === "clausula";
```

### Fix 2: Suppress treble-above draw for clausula exercises

In the `else if (renderScaleDegrees)` block, gate `drawScaleDegreeAbove` on `!isClausula`:

```javascript
} else if (renderScaleDegrees) {
  var degStave = trebleStave || activeStaveForAnnotations;
  if (degStave && !isClausula) {           // ← add !isClausula guard
    // ... existing sdMap build ...
    drawScaleDegreeAbove(ctx, attackList, columnCenterX, degStave, inlineAnalyzer, col.notes, bassStave, sdMap);
  }
  // ... new bass-below draw (Fix 3) ...
}
```

### Fix 3: New `drawBassScaleDegreeBelow` helper + call site

```javascript
function drawBassScaleDegreeBelow(ctx, bassStave, label, columnX) {
  if (!ctx || !bassStave || !label) return;
  var y = bassStave.getBottomY() + 22;
  ctx.save();
  ctx.textAlign = 'center';
  ctx.fillStyle = '#000';
  ctx.font = '18px MainSerifs';
  ctx.fillText(label, columnX, y);
  ctx.restore();
}
```

Call site — inside `else if (renderScaleDegrees)`, after Fix 2:

```javascript
if (isClausula && bassStave && score && score.umto && score.umto.analysis) {
  var absQL = noteOnset / 1024;
  var flabel = getBassLabelAtOffset(score.umto.analysis, absQL);
  if (flabel) {
    drawBassScaleDegreeBelow(ctx, bassStave, flabel, columnCenterX);
  }
}
```

### Extracted helper (testable in Node)

```javascript
function getBassLabelAtOffset(analysisSlices, quarterLength) {
  if (!analysisSlices || !analysisSlices.length) return null;
  for (var i = 0; i < analysisSlices.length; i++) {
    var sl = analysisSlices[i];
    if (Math.abs(sl.offset - quarterLength) < 0.05 &&
        sl.content && sl.content.functional_label) {
      return sl.content.functional_label;
    }
  }
  return null;
}
```

This function has no DOM/canvas dependencies and can be unit-tested directly.

---

## Guard conditions — label is drawn only when

- `isClausula` is true (`analysisType === "clausula"`)
- `bassStave` is non-null (bass staff is rendered)
- `getBassLabelAtOffset()` returns a non-empty string at that onset

### B1 behavior

B1 bass clausula (Do–Sol–Do on bass staff alone): `bassStave` exists, `functional_label` is set → label draws below. ✓  
B1 treble clausula (Discant/Tenor/Alto, no bass staff): `bassStave` is null → no label. ✓

---

## What does NOT change

- `generate_clausulae_b1.py` — already correct
- `AnalysisLayer` / `umto.py` schema
- Core-sequence exercises: `analysisType !== "clausula"` → all guards fail → no change

---

## Testing

### Unit tests (Node-testable, no browser)

- `getBassLabelAtOffset` returns the circled numeral when offset matches within 0.05
- `getBassLabelAtOffset` returns null when `functional_label` is empty string
- `getBassLabelAtOffset` returns null when no slice matches
- `getBassLabelAtOffset` returns null on empty/null analysis array

### Browser tests

1. B2 2-voice exercise: ①⑤① appear below bass staff at ANT/PEN/ULT columns; nothing above treble
2. B11 compound exercise: ①⑤① at offsets 0/2/4; offset 1 (τ=1 rest) shows nothing
3. B1 bass clausula (Do–Sol–Do): ①⑤① below bass staff
4. B1 treble clausula (e.g. Discant): no labels anywhere
5. B4 4-voice exercise: labels below bass, nothing above treble
6. Core-sequence exercise (Unit 9 or harmonization): no change to existing rendering
