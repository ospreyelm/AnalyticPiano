# Click-on-Staff Note Input — Design Spec

**Date:** 2026-05-28
**Status:** Approved (brainstorming) — implementation plan pending
**Scope:** Empty-staff pitch entry as a MIDI-free input fallback

## Problem

Students without a MIDI controller need a way to enter pitches into graded
exercises. Computer keyboard already works (`KeyboardShortcutsComponent`,
`NoteNameInputComponent`) by broadcasting `EVENTS.BROADCAST.NOTE` on/off — the
same channel MIDI uses. The grader (`chorale_grader.js`, `exercise_grader.js`,
the harmonization grading path in `exercise_context.js`) only consumes those
events; it does not know the input source.

This feature adds **mouse click on an empty staff position** as a third input
source feeding the same events. A click resolves to a pitch and broadcasts
`NOTE` — grader untouched.

### Scope decision

This spec covers **empty-staff entry**: the student clicks blank staff
positions to *supply* pitches (harmonization / free entry — notes are not
pre-drawn). It does **not** cover clicking pre-rendered noteheads (a separate,
simpler hit-test feature for play/identification exercises), which is
explicitly out of scope here.

## Key constraints discovered

- **Canvas backend.** `exercise_sheet.js:144` uses
  `Vex.Flow.Renderer.Backends.CANVAS`. Noteheads are pixels, not DOM elements.
  All click handling is pixel hit-testing against exported geometry, never SVG
  element listeners.
- **Event bus is the only integration seam.** `note_name.js` is the working
  template: an alternate input component that broadcasts
  `EVENTS.BROADCAST.NOTE, "on"/"off", midi`. We copy its shape.
- **Harmonization grades a pitch-class set, not voice assignment.**
  `harmonization_grader_logic.js#harmonizationMatch(target, activeMidi)` scores
  the flat set of sounding MIDI against `allowedPcs`, `requiredUpperPcs`,
  `lockedVoices.{B,S}` (checked by pitch class / MIDI), and
  `voiceCountPolicy.{min,max}`. No S/A/T/B slot is tracked.
- **Harmonization input renders as a pitch-stacked overlay, not SATB.**
  `buildHarmonizationOverlayVoice` (`vexflow_adapter.js:961`) draws a flat
  `{midiNotes, spellings}` per onset as one chord. Only the *locked* voices
  (given bass) use the SATB voice structure via `selectVoices`. Therefore a
  clicked note needs only a correct MIDI — no voice slot for grading or
  rendering. Register/staff placement follows from the MIDI octave.

## Confirmed decisions

| Question | Decision |
|----------|----------|
| Scope | Empty-staff pitch entry (not displayed-notehead clicks) |
| Chromatic resolution | Sticky accidental palette (default = diatonic / key-sig) |
| Commit model | Both, per exercise: chord = accumulate-then-commit; single-voice = one-note-per-column |
| Horizontal targeting | Click any column (x snaps to nearest known onset); random access |
| Commit-on-leave | No — **explicit-commit-only**; switching column stashes the in-progress chord |
| Voice assignment | None — grader and overlay are pitch-keyed |
| Preview | Ghost-note hover preview (approach C) |

## Architecture

Three new/changed pieces, mirroring `note_name.js`.

```
render() → adapter → onStaffLayout(layout) → exercise_sheet stores _staffLayout
mouse move → click component reads layout → snap → ghost note drawn
click → invert pixel→pitch → BROADCAST.NOTE "on" → grader (unchanged)
commit → BANK_NOTES / NOTE "off" → grade → advance → re-render → new layout
```

### New: `ClickNoteInputComponent` — `lab/static/js/src/components/input/click_note.js`
- Renders the accidental palette UI (mounted to `#piano`, like `note_name.js`).
- Owns click/mousemove/mouseleave handlers on `canvas#staff`.
- Entry state: active column, sticky accidental, held-note set (chord mode).
- Broadcasts `EVENTS.BROADCAST.NOTE` on/off and `BANK_NOTES`.
- `disable()` releases all held notes (copies `note_name.disable()` cleanup).

### New: `click_note_logic.js` (+ `.test.js`) — `lab/static/js/src/components/input/`
- Pure pixel→pitch math, no DOM. Follows the repo `*_logic.js` + `.test.js`
  convention (e.g. `computer_keyboard_ux_logic`).

### Modified: `vexflow_adapter.js`
- New `opts.onStaffLayout(layout)` callback, fired once per `render()` (same
  pattern as the existing `opts.onWindowPosition` hook).
- New `opts.harmonizationPending` param — the active column's held-but-
  uncommitted notes, rendered via the existing `buildHarmonizationOverlayVoice`
  in a distinct (pending) style.

### Modified: `exercise_sheet.js`
- Stores `this._staffLayout` from `onStaffLayout` (extends the existing
  `_identWindowLayout` precedent).
- Builds `harmonizationPending` from the click component's held set each render.
- Draws the ghost note (top layer, after adapter render, throttled).

### Modified: `exercise.js`
- Instantiates `ClickNoteInputComponent`, gated like the keyboard components
  (skipped for symbolic-meter / key-signature exercises).

**Untouched:** event bus, chord bank, all graders.

## 1. Staff layout export (adapter → sheet)

New `opts.onStaffLayout` callback fired after measures are laid out and staves
drawn (geometry is valid only after `draw()`; the annotation loop already runs
post-draw, so capture goes there). Payload:

```javascript
{
  systems: [
    {
      staves: [
        {
          clef: "treble",
          x: 60, width: 740,        // clickable x-range
          topLineY: 95,             // y of top staff line (line 0)
          lineSpacing: 10,          // px between adjacent lines
          topLineStep: "F", topLineOctave: 5   // treble top line = F5; bass = A3
        },
        { clef: "bass", /* topLineStep: "A", topLineOctave: 3 */ }
      ]
    }
  ],
  columns: [
    { onset: 0,    measureIndex: 0, centerX: 92 },
    { onset: 1024, measureIndex: 0, centerX: 168 }
  ]
}
```

Source data already exists in `render()`:
- staves: `getYForLine(0)` / `getYForLine(1)` (→ spacing), `getNoteStartX()`,
  `getX()`, width.
- `topLineStep`/`topLineOctave`: fixed per clef (treble top line F5, bass A3).
- columns: reuse `analysisWindows` + `getColumnCenterX(col)` already computed
  for annotations; push `{onset, measureIndex, centerX}`.

## 2. Pixel→pitch inversion (`click_note_logic.js`)

Pure functions. Click at `(px, py)` relative to canvas:

**Pick stave.** For each stave, playable zone =
`topLineY - N*spacing … bottomLineY + N*spacing` (N≈6, covers ledger lines).
Click assigned to the stave whose zone contains `py`; in the inter-stave gap,
nearest `topLineY` wins.

**y → staff-position (diatonic steps below top line).**
```
stepsFromTop = round((py - topLineY) / (lineSpacing / 2))
```
Each `lineSpacing/2` = one diatonic position (line or space). Positive =
downward = lower pitch; negative = above top line (ledger).

**staff-position → step + octave.** Walk the diatonic ladder
(C-D-E-F-G-A-B, octave decrements crossing C downward) down from
`(topLineStep, topLineOctave)` by `stepsFromTop` letters; negative walks up.
Pure letter arithmetic.

**Apply key signature, then palette accidental.**
- Base `alter` = key-signature alteration for that letter (reuse the
  `getKeySignatureAlterations(key)` logic from the adapter; share via the logic
  module or pass the key in).
- Palette override: `♯`→+1, `♭`→−1, `♮`→0 (force natural),
  default/"diatonic"→keep key-sig `alter`.

**→ MIDI.** `(octave+1)*12 + STEP_SEMITONE[step] + alter` — same formula as
`note_name.js:179`. Clamp to 21–108; out-of-range → `null`.

**x → column.** Nearest `columns[i].centerX`; returns the column
(`onset`, `measureIndex`) for grader targeting and ghost x.

**Output:** `{ midi, step, alter, octave, column }` or `null`.

## 3. Accidental palette

Mounted in the input toolbar area (`#piano`, where `note_name.js` mounts).

Buttons: **diatonic** (default) · **♯** · **♭** · **♮**. Sticky — persists
across clicks until changed. Active-state styling like note_name's mode buttons
(`input-mode-btn-active`).

- **diatonic** (default): click takes the key-signature pitch
  (G-major F-space → F♯). Common case = one click.
- **♯ / ♭**: that alteration regardless of key sig.
- **♮**: force natural even if the key sig alters that letter.

Keyboard parity: ↑/↓ nudge the sticky accidental (reuses note_name's
KEY_UP/KEY_DOWN feel), so the palette is not mouse-only.

Deferred (YAGNI): double accidentals 𝄪 𝄫.

## 4. Commit modes (per exercise definition)

Mode chosen from `definition` (`isHarmonization()`, single-voice), the same
dispatch the graders use.

### Chord mode (harmonization) — accumulate → commit
- Click empty pitch in active column → `NOTE "on"`; note stays held, added to
  current chord, drawn pending.
- Re-click same pitch → `NOTE "off"`; removed.
- Click a different column → switch active column (random access). The leaving
  column's in-progress chord is **stashed** (explicit-commit-only — not graded
  on leave).
- Commit gesture = existing bank (SPACE/ENTER) or a **Done** button → release
  all held (`NOTE "off"` each) → harmonization settle timer fires
  (`exercise_sheet.onMidiNote`, ~150ms) → `exercise_context.grade()` → advance.

Maps onto the existing `_harmonizationHeldTracker` + settle path — no grader
change.

### Single-note mode (melodic / one-voice) — one note per column
- Click pitch in a column → `NOTE "on"`+`"off"` quick pair → that column's
  single answer.
- Re-click column with a different pitch → replaces it.
- No commit gesture; random access via column click. Advance/submit uses the
  exercise's normal flow.

### Held-note safety
On component disable, exercise change, or column switch — release all held
(`NOTE "off"`). Prevents stuck sounding notes.

## 5. Rendering student input

Student notes never touch the score's SATB voices. Two pitch-keyed layers:

### Pending-realization overlay (accumulated chord)
- New `opts.harmonizationPending = { measureIndex, onset, midiNotes, spellings }`
  for the active column's held-but-uncommitted notes.
- Reuses `buildHarmonizationOverlayVoice` — same chord-stack builder as the
  accepted realization.
- Styled distinct from committed: accepted = black, pending = blue/gray
  (`#5b8def`), so "building" reads differently from "locked in."
- `exercise_sheet` builds this from the click component's held set each
  re-render, alongside the existing accepted `harmonizationRealization`.

### Ghost-note preview (single pitch under cursor)
- On mousemove, `click_note_logic` resolves snapped `{midi, step, alter,
  column}`; `exercise_sheet` draws one faint notehead (`#b0b8c4`) at that
  column's `centerX` and the pitch's y.
- Cleared on mouseleave. Drawn last (on top), after adapter render; a
  lightweight notehead glyph draw, throttled — no full re-render per mousemove.

### Spelling
`click_note_logic` already yields `{step, alter, octave}`, so `spellings` for
the overlay come free — no re-deriving enharmonics.

### Single-note mode
Same overlay path, one notehead per column instead of a stack. No SATB
assignment — click input always produces an overlay of student pitches, never
mutates the CIR.

## 6. Event wiring & edge cases

**Wiring (`exercise.js`).** Instantiate `ClickNoteInputComponent` beside
`NoteNameInputComponent`, gated identically. Inject the sheet so the component
can read `_staffLayout` + held set and request the ghost draw. Mount the palette
to `#piano`.

**Events.** Click → `BROADCAST.NOTE "on"` (and `"off"` on re-click/commit).
Chord-mode commit → release all held + `BANK_NOTES`. Identical channel to
MIDI/keyboard; `midi.js` and `exercise_sheet.onMidiNote` already subscribe.

**Edge cases.**
- Out-of-range click (no stave / MIDI <21 or >108) → no-op, no ghost.
- Inter-stave gap → nearest `topLineY` wins (§2).
- Re-render mid-entry (scroll/advance) rebuilds `_staffLayout`; held set is
  component state and survives; pending overlay redrawn from it.
- Disable / exercise change / column switch → release all held.
- MIDI + click both active → same event bus, coexist; no exclusivity mode.
- Duplicate pitch already held → re-click toggles off (no double `NOTE on`).

## 7. Testing

- `click_note_logic.test.js` (cold unit, no DOM): layout + pixel → pitch.
  Cover treble/bass boundary, ledger lines above & below, key-sig diatonic
  default, ♯/♭/♮ palette override, x→column snap, out-of-range → null. Mirrors
  `computer_keyboard_ux_logic.test.js`.
- Manual browser pass (per CLAUDE.md UI rule): harmonization exercise —
  click-build a chord, commit, verify grade; single-note exercise — click a
  melody; verify no stuck notes on advance; verify ghost tracks the cursor.

## 8. Documentation impact

- No new exercise type or management command → no `exercise_types.md` /
  `management_commands.md` change.
- Significant multi-file feature → this spec + an implementation plan
  (writing-plans, next step).

## Out of scope (YAGNI)

Double accidentals 𝄪 𝄫; drag/glissando; clicking pre-rendered noteheads (the
other scope branch); free-x composition with no preset onsets; touch/mobile
gestures.
