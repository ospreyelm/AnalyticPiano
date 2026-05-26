# Branch B Bass Scale-Degree Labels Below Staff — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display circled Arabic scale-degree numerals (①②③④⑤⑥⑦) below the bass staff in Branch B clausulae exercises, and suppress the erroneous treble-above scale-degree rendering those exercises currently produce.

**Architecture:** Add a pure `getBassLabelAtOffset()` helper to `vexflow_adapter_logic.js` (Node-testable, no DOM). In `vexflow_adapter.js`, gate treble-above scale-degree drawing on `!isClausula` and add a new `drawBassScaleDegreeBelow()` call for clausula exercises. Pass `analysisType` from `exercise_sheet.js` into `VexFlowAdapter.render()` so the adapter knows it's in clausula mode.

**Tech Stack:** Vanilla JS (AMD/RequireJS modules), VexFlow canvas rendering, Node.js for unit tests (`node file.test.js`).

---

## File Map

| File | Change |
|---|---|
| `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js` | Add `getBassLabelAtOffset()` pure function; export it |
| `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js` | Add 4 unit tests for `getBassLabelAtOffset()` |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | Read `analysisType` opt; add `drawBassScaleDegreeBelow()`; suppress treble-above for clausula; call bass-below draw |
| `lab/static/js/src/components/music/exercise_sheet.js` | Pass `analysisType` to `VexFlowAdapter.render()` at line 1852 |

---

## Task 1: Add `getBassLabelAtOffset()` to logic module

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js`

- [ ] **Step 1.1: Add the function before the `return` statement**

Open `vexflow_adapter_logic.js`. Before the final `return { ... };` block, insert:

```javascript
  /**
   * Returns the functional_label from the UMTO analysis slice whose offset
   * is within 0.05 quarter-lengths of `quarterLength`, or null if none found.
   * Used by the clausula renderer to draw circled bass scale-degree numerals.
   *
   * @param {Array} analysisSlices  - score.umto.analysis array
   * @param {number} quarterLength  - noteOnset / 1024
   * @returns {string|null}
   */
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

- [ ] **Step 1.2: Export the new function**

The `return` block at the end of the file currently reads:

```javascript
  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
  };
```

Add `getBassLabelAtOffset`:

```javascript
  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
    getBassLabelAtOffset: getBassLabelAtOffset,
  };
```

---

## Task 2: Unit-test `getBassLabelAtOffset()`

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js`

- [ ] **Step 2.1: Add 4 test functions at the end of the file, before the final `console.log` line**

The file currently ends with:

```javascript
testRestPlacementKeysDoNotBecomeScaleDegrees();
testNotesStillBecomeScaleDegreeMidi();
testVexFlowIsRestMethodFalseDoesNotFilterNotes();

console.log("vexflow_adapter_logic tests passed");
```

Insert the four new tests before `console.log`:

```javascript
function testGetBassLabelAtOffsetReturnsLabel() {
  var slices = [
    { offset: 0.0, content: { functional_label: "①" } },
    { offset: 2.0, content: { functional_label: "⑤" } },
    { offset: 4.0, content: { functional_label: "①" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 2.0), "⑤");
}

function testGetBassLabelAtOffsetToleratesSmallDrift() {
  var slices = [
    { offset: 2.0, content: { functional_label: "⑤" } },
  ];
  // 0.04 is within the 0.05 tolerance
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 2.04), "⑤");
}

function testGetBassLabelAtOffsetReturnsNullForEmptyLabel() {
  var slices = [
    { offset: 1.0, content: { functional_label: "" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 1.0), null);
}

function testGetBassLabelAtOffsetReturnsNullForNoMatch() {
  var slices = [
    { offset: 0.0, content: { functional_label: "①" } },
  ];
  assert.strictEqual(Logic.getBassLabelAtOffset(slices, 9.0), null);
}

testGetBassLabelAtOffsetReturnsLabel();
testGetBassLabelAtOffsetToleratesSmallDrift();
testGetBassLabelAtOffsetReturnsNullForEmptyLabel();
testGetBassLabelAtOffsetReturnsNullForNoMatch();
```

- [ ] **Step 2.2: Run tests — expect all pass**

```bash
node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
```

Expected output:
```
vexflow_adapter_logic tests passed
```

- [ ] **Step 2.3: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter_logic.js \
        lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
git commit -m "feat: add getBassLabelAtOffset() to adapter logic; 4 unit tests"
```

---

## Task 3: Wire `analysisType` into `VexFlowAdapter.render()`

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` (around line 1852)
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js` (near top of `render()`)

- [ ] **Step 3.1: Pass `analysisType` in `exercise_sheet.js`**

In `exercise_sheet.js`, the `VexFlowAdapter.render(score, this.vexRenderer, { ... })` call starts around line 1852. Add `analysisType` to the opts object:

```javascript
          VexFlowAdapter.render(score, this.vexRenderer, {
            width: canvas.width,
            height: canvas.height,
            maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,
            startMeasure: startMeasure,
            playedNoteIds: playedNoteIdsForRender,
            showNotation: display.showNotation !== undefined ? display.showNotation : true,
            hideKeyLabel: !!display.hideKeyLabel,
            firstMeasureExtraWidth: parseInt(display.firstMeasureExtraWidth, 10) || 0,
            noteXShift: parseInt(display.noteXShift, 10) || 0,
            voiceColors: display.voiceColors || null,
            analyzeConfig: analyzeConfig,
            keySignature: this.keySignature,
            analysisRenderer: display.analysisRenderer || "notater",
            staffYOffset: staffYOffset,
            isAnalysisMatch: isAnalysisMatchMode,
            isHarmonization: isHarmonization,
            harmonizationTargets: isHarmonization ? (definition.getHarmonizationTargets ? definition.getHarmonizationTargets() : []) : null,
            harmonizationRealization: isHarmonization ? harmonizationRealizationPayload : null,
            lockedVoices: isHarmonization && definition.exercise && definition.exercise.score && definition.exercise.score.umto
              ? (definition.exercise.score.umto.metadata.locked_voices || ["B"])
              : null,
            selectVoices: harmonizationSelectVoices,
            analysisType: definition.getAnalysisType ? definition.getAnalysisType() : null,
            onWindowPosition: function (slot) {
```

(Add `analysisType: definition.getAnalysisType ? definition.getAnalysisType() : null,` — the line just before `onWindowPosition`.)

- [ ] **Step 3.2: Read `analysisType` near the top of `render()` in `vexflow_adapter.js`**

Inside the `render` function, after the existing opts destructuring (around line 1136 where `showNotation` is read), add:

```javascript
      var analysisType = (opts && opts.analysisType) || null;
      var isClausula = analysisType === "clausula";
```

Place these two lines immediately after the line:
```javascript
      var showNotation = opts && opts.showNotation !== undefined ? opts.showNotation : true;
```

- [ ] **Step 3.3: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js \
        lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "feat: pass analysisType opt into VexFlowAdapter.render; read isClausula flag"
```

---

## Task 4: Add `drawBassScaleDegreeBelow()` helper to adapter

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js`

- [ ] **Step 4.1: Add helper function near `drawScaleDegreeAbove`**

In `vexflow_adapter.js`, `drawScaleDegreeAbove` is defined at line ~497. Add the new helper immediately after it (after line ~548):

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

- [ ] **Step 4.2: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "feat: add drawBassScaleDegreeBelow() canvas helper"
```

---

## Task 5: Modify `renderScaleDegrees` branch — suppress treble, add bass-below

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js` (lines ~1960–1981)

- [ ] **Step 5.1: Replace the existing `renderScaleDegrees` block**

Find the current block (around line 1960):

```javascript
              } else if (renderScaleDegrees) {
                var degStave = trebleStave || activeStaveForAnnotations;
                if (degStave) {
                  // Build MIDI→label map from stored scale_degrees in UMTO analysis slices.
                  var sdMap = null;
                  if (score && score.umto && score.umto.analysis && score.umto.analysis.length) {
                    var absQL = noteOnset / 1024;
                    for (var sdi = 0; sdi < score.umto.analysis.length; sdi++) {
                      var sdSlice = score.umto.analysis[sdi];
                      if (Math.abs(sdSlice.offset - absQL) < 0.05 &&
                          sdSlice.content && sdSlice.content.scale_degrees && sdSlice.content.scale_degrees.length) {
                        sdMap = Object.create(null);
                        sdSlice.content.scale_degrees.forEach(function(sd) {
                          sdMap[sd.midi] = sd.label;
                        });
                        break;
                      }
                    }
                  }
                  drawScaleDegreeAbove(ctx, attackList, columnCenterX, degStave, inlineAnalyzer, col.notes, bassStave, sdMap);
                }
              }
```

Replace it with:

```javascript
              } else if (renderScaleDegrees) {
                var degStave = trebleStave || activeStaveForAnnotations;
                if (degStave && !isClausula) {
                  // Build MIDI→label map from stored scale_degrees in UMTO analysis slices.
                  var sdMap = null;
                  if (score && score.umto && score.umto.analysis && score.umto.analysis.length) {
                    var absQL = noteOnset / 1024;
                    for (var sdi = 0; sdi < score.umto.analysis.length; sdi++) {
                      var sdSlice = score.umto.analysis[sdi];
                      if (Math.abs(sdSlice.offset - absQL) < 0.05 &&
                          sdSlice.content && sdSlice.content.scale_degrees && sdSlice.content.scale_degrees.length) {
                        sdMap = Object.create(null);
                        sdSlice.content.scale_degrees.forEach(function(sd) {
                          sdMap[sd.midi] = sd.label;
                        });
                        break;
                      }
                    }
                  }
                  drawScaleDegreeAbove(ctx, attackList, columnCenterX, degStave, inlineAnalyzer, col.notes, bassStave, sdMap);
                }
                if (isClausula && bassStave && score && score.umto && score.umto.analysis) {
                  var bassQL = noteOnset / 1024;
                  var bassLabel = VexflowAdapterLogic
                    ? VexflowAdapterLogic.getBassLabelAtOffset(score.umto.analysis, bassQL)
                    : null;
                  if (bassLabel) {
                    drawBassScaleDegreeBelow(ctx, bassStave, bassLabel, columnCenterX);
                  }
                }
              }
```

- [ ] **Step 5.2: Run the Node logic tests to confirm no regressions**

```bash
node lab/static/js/src/components/music/rendering/vexflow_adapter_logic.test.js
```

Expected:
```
vexflow_adapter_logic tests passed
```

- [ ] **Step 5.3: Commit**

```bash
git add lab/static/js/src/components/music/rendering/vexflow_adapter.js
git commit -m "feat: draw circled bass scale-degrees below staff in clausula exercises"
```

---

## Task 6: Browser verification

**No code changes — verification only.**

- [ ] **Step 6.1: Start dev server**

```bash
python manage.py runserver
```

- [ ] **Step 6.2: B2 2-voice exercise**

Load a B2 exercise (Discant + Bass in two voices). Confirm:
- ①⑤① appear below the bass staff at ANT/PEN/ULT chord columns
- Nothing spurious appears above the treble staff

- [ ] **Step 6.3: B11 compound exercise**

Load a B11 compound exercise. Confirm:
- ①⑤① at offsets 0/2/4 (ANT/PEN/ULT)
- Offset 1 (τ=1 rest position) shows no label below bass

- [ ] **Step 6.4: B1 bass clausula**

Load a B1 exercise where the single voice is the Bass (Do–Sol–Do on bass staff). Confirm:
- ①⑤① appear below bass staff

- [ ] **Step 6.5: B1 treble clausula**

Load a B1 exercise where the single voice is Discant/Tenor/Alto (treble staff, no bass staff). Confirm:
- No labels appear anywhere

- [ ] **Step 6.6: B4 4-voice exercise**

Load a B4 4-voice exercise. Confirm:
- ①⑤① below bass staff
- Nothing above treble staff (no spurious treble-above labels)

- [ ] **Step 6.7: Core-sequence exercise (any Unit 1–9 exercise)**

Load any standard exercise. Confirm no visible change.

- [ ] **Step 6.8: Final commit**

```bash
git add -p  # confirm no accidental changes
git commit -m "fix: suppress treble-above scale degrees in clausula; add bass-below circled labels

Clausula exercises now show ①②③⑤⑦ below the bass staff (Baroque
convention). The erroneous treble-above labels drawn by the fallback
analyzer path are suppressed via isClausula flag.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
