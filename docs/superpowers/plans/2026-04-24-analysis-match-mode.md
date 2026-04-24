# Analysis Match Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Unit 1 "analysis" exercises so students see note-name labels with invisible noteheads, play the correct pitch (any octave), and noteheads appear when correct.

**Architecture:** Three targeted fixes in two JS files. The grader (`ChoraleGrader`) and grader wiring (`exercise.js`) are already correct for `analysis_match` mode — octave-independent matching is enabled for Unit 1 exercises. Only the rendering layer needs fixes: (1) enable note-name labels for `analysis_match` mode, (2) suppress the roman-numeral fallback for `analysis_match`, and (3) render unplayed noteheads white (invisible) instead of gray.

**Tech Stack:** JavaScript (AMD/RequireJS), VexFlow canvas rendering, existing `ChoraleGrader` with `octaveIndependent` flag.

---

## File Map

| File | Change |
|------|--------|
| `lab/static/js/src/components/music/exercise_sheet.js` | Fix `wantsNoteNames` check (line ~1155) and roman-numeral fallback (line ~1171) |
| `lab/static/js/src/components/music/rendering/vexflow_adapter.js` | Render unplayed noteheads/stems white when `isAnalysisMatch` opt is set |

---

### Task 1: Enable note-name labels for `analysis_match`

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js:1155`

**Context:** Line 1155 checks `definition.mode === "analysis"` to enable note-name overlay. The actual mode string for these exercises is `"analysis_match"`. Also, the `isChorale()` fallback at line 1171 forces `wantsRomans = true` for any chorale-like exercise including `analysis_match`, which would render roman numerals instead of note names.

- [ ] **Step 1: Open the file and locate the two problem lines**

  In `lab/static/js/src/components/music/exercise_sheet.js`, find:
  ```javascript
  var wantsNoteNames = !!display.showNoteNames || definition.mode === "analysis";
  ```
  and further down:
  ```javascript
  if (!wantsAnalysis && definition.isChorale && definition.isChorale()) {
    wantsRomans = true;
    wantsAnalysis = true;
  }
  ```

- [ ] **Step 2: Fix `wantsNoteNames` to include `analysis_match`**

  Change line ~1155 from:
  ```javascript
  var wantsNoteNames = !!display.showNoteNames || definition.mode === "analysis";
  ```
  To:
  ```javascript
  var isAnalysisMatchMode = definition.mode === "analysis_match" || definition.mode === "analysis";
  var wantsNoteNames = !!display.showNoteNames || isAnalysisMatchMode;
  ```

- [ ] **Step 3: Fix the roman-numeral fallback to exclude `analysis_match`**

  Change lines ~1171-1174 from:
  ```javascript
  if (!wantsAnalysis && definition.isChorale && definition.isChorale()) {
    wantsRomans = true;
    wantsAnalysis = true;
  }
  ```
  To:
  ```javascript
  if (!wantsAnalysis && definition.isChorale && definition.isChorale() && !isAnalysisMatchMode) {
    wantsRomans = true;
    wantsAnalysis = true;
  }
  ```

- [ ] **Step 4: Verify the change looks correct**

  After the edit, lines ~1152-1175 should read:
  ```javascript
  var wantsRomans = !!display.showRomans;
  var wantsFigures = !!display.showFigures;
  var wantsChordLabels = !!display.showChordLabels;
  var isAnalysisMatchMode = definition.mode === "analysis_match" || definition.mode === "analysis";
  var wantsNoteNames = !!display.showNoteNames || isAnalysisMatchMode;

  if (this._isChoraleIdentificationExercise()) {
    wantsRomans = false;
    wantsFigures = false;
    wantsChordLabels = false;
  }

  var wantsAnalysis = wantsRomans || wantsFigures || wantsChordLabels || wantsNoteNames;

  if (!wantsAnalysis && definition.isChorale && definition.isChorale() && !isAnalysisMatchMode) {
    wantsRomans = true;
    wantsAnalysis = true;
  }
  ```

- [ ] **Step 5: Commit**

  ```bash
  git add lab/static/js/src/components/music/exercise_sheet.js
  git commit -m "fix: enable note-name overlay and suppress roman fallback for analysis_match mode"
  ```

---

### Task 2: Render unplayed noteheads white (invisible) in analysis_match

**Files:**
- Modify: `lab/static/js/src/components/music/rendering/vexflow_adapter.js:687,730`
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` (pass `isAnalysisMatch` opt)

**Context:** `itemToTickable` in `vexflow_adapter.js` sets unplayed notes to gray `#9aa0a6`. For `analysis_match`, unplayed noteheads should be white (invisible against white background) until the student plays the correct note, at which point `playedNoteIds` causes them to render black. The adapter receives an `opts` object — we add an `isAnalysisMatch` boolean flag.

- [ ] **Step 1: Pass `isAnalysisMatch` flag from `exercise_sheet.js` to the adapter**

  In `lab/static/js/src/components/music/exercise_sheet.js`, find the `VexFlowAdapter.render(...)` call (around line 1220). It already passes an opts object. Add the flag:

  ```javascript
  VexFlowAdapter.render(score, this.vexRenderer, {
    width: canvas.width,
    height: canvas.height,
    maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,
    startMeasure: startMeasure,
    playedNoteIds: playedNoteIdsForRender,
    showNotation: display.showNotation !== undefined ? display.showNotation : true,
    analyzeConfig: analyzeConfig,
    keySignature: this.keySignature,
    analysisRenderer: display.analysisRenderer || "notater",
    staffYOffset: staffYOffset,
    isAnalysisMatch: isAnalysisMatchMode,   // <-- add this line
    onWindowPosition: function (slot) {
      // ... existing handler unchanged
    },
  });
  ```

- [ ] **Step 2: Read `isAnalysisMatch` from opts in the adapter render function**

  In `lab/static/js/src/components/music/rendering/vexflow_adapter.js`, find where `opts` fields are read near the top of the main `render` function (around line 832). Add:

  ```javascript
  var isAnalysisMatch = !!(opts && opts.isAnalysisMatch);
  ```

  Place it alongside the other `var` declarations from `opts` (e.g. near `var showNotation = ...`).

- [ ] **Step 3: Use white instead of gray for unplayed notes in analysis_match**

  In `vexflow_adapter.js`, find the `itemToTickable` function — it has two places that set gray `#9aa0a6` for unplayed notes. Both follow the same pattern:

  **First occurrence (single note, around line 687):**
  ```javascript
  if (played) {
    note.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
  } else if (!showNotation) {
    note.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
  } else {
    note.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
  }
  ```
  Change to:
  ```javascript
  if (played) {
    note.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
  } else if (!showNotation) {
    note.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
  } else if (isAnalysisMatch) {
    note.setStyle({ fillStyle: '#ffffff', strokeStyle: '#ffffff' });
  } else {
    note.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
  }
  ```

  **Second occurrence (chord notes, around line 726-731):**
  ```javascript
  if (playedAny) {
    chord.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
  } else if (!showNotation) {
    chord.setStyle({ fillStyle: 'transparent', strokeStyle: 'transparent' });
  } else {
    chord.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
  }
  ```
  Change to:
  ```javascript
  if (playedAny) {
    chord.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
  } else if (!showNotation) {
    chord.setStyle({ fillStyle: 'transparent', strokeStyle: 'transparent' });
  } else if (isAnalysisMatch) {
    chord.setStyle({ fillStyle: '#ffffff', strokeStyle: '#ffffff' });
  } else {
    chord.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
  }
  ```

- [ ] **Step 4: Verify `isAnalysisMatch` is in scope inside `itemToTickable`**

  `itemToTickable` is a closure defined inside the main render function. Confirm `isAnalysisMatch` declared in Step 2 is accessible in its scope. If `itemToTickable` is defined before `isAnalysisMatch` is declared, move the declaration earlier (before the function definition). Check by searching for `function itemToTickable` in the file and confirming `isAnalysisMatch` is declared before it.

- [ ] **Step 5: Commit**

  ```bash
  git add lab/static/js/src/components/music/rendering/vexflow_adapter.js \
          lab/static/js/src/components/music/exercise_sheet.js
  git commit -m "fix: render analysis_match noteheads white until played"
  ```

---

### Task 3: Manual verification

**Files:** None — browser test only.

- [ ] **Step 1: Start the dev server**

  ```bash
  python manage.py runserver
  ```

- [ ] **Step 2: Open an analysis exercise**

  In the dashboard, find exercise `EA96YW` (BWV96.6 mm.11-12 - Bass (analysis) Stage 3) or any exercise with description containing `(analysis)`. Open it in the lab.

- [ ] **Step 3: Verify note-name labels appear**

  The score should show note names (e.g. `"D"`, `"F"`, `"A"`) above or below each note position. No `?` slots — those are for identification mode.

- [ ] **Step 4: Verify noteheads are invisible**

  The score staff lines should be visible but no gray or black noteheads, stems, or beams should appear before any note is played.

- [ ] **Step 5: Play a correct note (any octave)**

  Using a MIDI keyboard or the on-screen piano, play the pitch matching the first label (any octave). Verify:
  - The notehead, stem, and beam (if any) appear in black
  - The exercise advances to the next note

- [ ] **Step 6: Play a wrong note**

  Play a wrong pitch class. Verify:
  - The exercise does NOT advance
  - No notehead appears
  - The label is still visible

- [ ] **Step 7: Complete the exercise**

  Play all notes in order. Verify the exercise completes and advances to the next exercise in the playlist.

- [ ] **Step 8: Verify exact and identification exercises still work**

  Open an `(exact)` exercise and an `(identification)` exercise for the same chorale. Confirm they still work correctly — noteheads visible gray for exact, `?` slots for identification.

- [ ] **Step 9: Final commit if any tweaks were made**

  ```bash
  git add -p
  git commit -m "fix: analysis_match rendering tweaks from manual verification"
  ```
