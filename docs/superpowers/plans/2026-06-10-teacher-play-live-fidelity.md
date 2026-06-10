# Teacher Play — Live Authoring Fidelity (WYSIWYG fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes.

**Goal:** Make the **live** Play view reflect authoring edits immediately (true WYSIWYG), closing the gap where duration/respell/analysis-token/meter edits only appeared on the *saved* exercise. Add the on-canvas analysis-type slot picker.

**Why:** Phase B (PR #94) wired the authoring state into `dataForSave` + the saved-exercise render only — the live mini-stave renderer (`play_sheet` → `stave` → `play_note_factory`/`stave_note_factory` + `stave_notater`) ignores `_chordDurations`/`_spellingOverrides`/`_tokenOverrides`/`_meter`. Interactive testing showed clicking toolbar options changes nothing on screen (though it saves correctly), the meter draws no time signature, and barlines computed from invisible durations look arbitrary.

**Tech stack:** RequireJS/VexFlow front end. Confirmed seams (already present, just unused):
- `stave.js:447` `this.createStaveNotes()` (no-arg → whole); `createStaveNotes(duration)` passes through to `stave_note_factory.createStaveNotes(duration)` which honors any VexFlow duration string.
- `stave.js:368` `staffSegment.addTimeSignature(this.timeSignature)` already draws a TS when `this.timeSignature` is set.
- `stave.js:339` `createStaveBar` has real per-stave barline plumbing gated by `barlines_on_staves = false`.

**Environment:** worktree `.claude/worktrees/admiring-wiles-136502`, branch `claude/admiring-wiles-136502`; `pyenv local 3.11.9`; front-end tests `node <file>_logic.test.js`; `node --check` on edited RequireJS files.

**Dropped from scope:** the "piano QWERTY overlay disappeared" report — confirmed pre-existing (returns on QWERTY toggle), unrelated to this work.

---

## Task F1: Live per-chord duration

**Files:** `play_sheet.js` (`createNoteStave`, render loop), `stave.js` (`render`/`createStaveNotes` call site ~447), small ql→VexFlow helper.

- [ ] Add a ql→`{duration, dots}` VexFlow map (reuse the `DUR_PARTS` shape already in `exercise_sheet._convertChordalUMTOToProcessedScore`; extract it into `chordal_barlines_logic.js` as `qlToVexDuration(ql) -> {duration, dots}` with a node test, then consume in both places to DRY).
- [ ] In `play_sheet.updateStaves`, compute each banked chord's `bankIndex` (the `this.chords._items` index) and pass its duration into `createNoteStave`.
- [ ] `createNoteStave` stores the VF duration on the stave (e.g. `stave.setNoteDuration(vfDur, dots)` — add a tiny setter) before render.
- [ ] `stave.js` render: change the internal `this.createStaveNotes()` (line ~447) to pass the stored duration (default unchanged when none set, so non-authoring Play views are unaffected). Verify dots render (StaveNote `addDotToAll`/`{dots}` path in `stave_note_factory`).
- [ ] Verify: clicking a duration in the micro-toolbar re-renders the selected chord at that note value live; non-authoring Play (live blackboard) unchanged. `node --check` both files.

## Task F2: Live meter time-signature glyph

**Files:** `play_sheet.js` (display stave creation / `setMeter`), `stave.js` (`createStaveBar` already calls `addTimeSignature`).

- [ ] In `createDisplayStave` (or render), when `this._meter` is non-null set the display stave's `timeSignature` so `createStaveBar` (line ~366-368) draws it; when null, draw none.
- [ ] Confirm `setMeter` re-renders (it calls `autoSuggestBarlines`→`render`). Verify the TS glyph appears/disappears as the meter selector changes. `node --check`.

## Task F3: Barline clarity (real barlines, not floating ticks)

**Files:** `play_sheet.js` (`_drawBarlineTicks` → real barlines), `stave.js` (`createStaveBar` barline gate).

- [ ] Replace the overlay-tick approach with real barlines drawn at the staves whose onset equals each `_barlineOffsets` entry (use the existing `createStaveBar` barline plumbing, or draw a full-height line at the stave's `getStartX()`). Once F1 makes durations visible, confirm barline positions read correctly (a barline sits at the left edge of the chord on the downbeat of the new bar).
- [ ] Verify against a metered example (4/4, eight quarters → barline before chord 5). `node --check`.

## Task F4: Live respell

**Files:** `play_sheet.js` (thread override into the factory), `play_note_factory.js`/`stave_note_factory.js` (consult provided spelling).

- [ ] Pass `_spellingOverrides[arrayIndex]` (when present + length matches) into `createNoteStave` → `PlayNoteFactory` so the rendered note keys use the override spelling instead of the analyzer default. Investigate how the factory currently derives pitch spelling and inject the override at that point.
- [ ] Verify: Respell re-renders the selected chord enharmonically live. `node --check`.

## Task F5: Live analysis token

**Files:** `play_sheet.js` (pass overrides to notater), `stave_notater.js` (use override when drawing below-zone label).

- [ ] Thread `_tokenOverrides[arrayIndex].below` to the per-chord `stave_notater` (via the notater config in `createNoteStave`), and in the below-zone draw (Roman/figured) use the override string instead of the MIDI-computed label when present.
- [ ] Verify: correcting a Roman/figure re-renders that chord's label live. `node --check`.

## Task F6: On-canvas analysis-type picker (Decision b)

**Files:** `play_authoring_toolbar.js` or a small zone-picker, `play_sheet.js`.

- [ ] Add an affordance to pick the analysis type per zone on-canvas (clicking the above/below baseline, or a control in the toolbar) listing `AnalysisSlots.typesForZone(zone)`; on select, set the corresponding `analyzeConfig.mode` flag (and clear the other types in that zone — ≤1 per zone) and re-render so the live analysis switches. This replaces relying solely on the legacy notation-panel checkboxes.
- [ ] Verify: a teacher can switch below-zone between Roman numerals and figured bass (and above-zone note-names/scale-degrees) from the canvas, and it persists on save (`analyzeConfig {above, below}` already serialized). `node --check`.

## Task F7: Verification

- [ ] Run all node logic tests + `node --check` on every edited file; manual browser smoke of F1–F6.
- [ ] Commit + update PR #94 (or a follow-up PR on the same branch).

---

## Self-review
- F1 must NOT change the non-authoring live blackboard (default duration when no `_chordDurations` entry) — regression-gate it.
- ql→VexFlow conversion is shared (DRY) between live and saved render.
- F3 barline reading depends on F1 (do F1 first).
