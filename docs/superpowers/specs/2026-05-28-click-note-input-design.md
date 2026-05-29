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

### Design invariant: input-method-agnostic

Click input MUST be indistinguishable downstream from MIDI/keyboard. It emits
the same `EVENTS.BROADCAST.NOTE` on/off + `BANK_NOTES`, and at grade time it
hands the grader the **same data shape** any source produces: a flat set of
sounding MIDI numbers (chord) or a single MIDI (melodic). No click-specific
field, flag, or branch reaches a grader. This is load-bearing for the
**future post-submission grading layer** the user plans to add: that grader
will receive committed answers as MIDI sets and must not be able to tell — and
must not need to know — whether they came from a keyboard, a controller, or a
click. Any new persisted answer structure introduced for click input must be
the structure MIDI input already produces, not a parallel one.

## Confirmed decisions

| Question | Decision |
|----------|----------|
| Scope | Empty-staff pitch entry (not displayed-notehead clicks) |
| Chromatic resolution | Sticky accidental palette (default = diatonic / key-sig) |
| Commit model | Both, per exercise: chord = accumulate-then-commit; single-voice = one-note-per-column |
| Horizontal targeting (v1) | **Sequential** — clicks build the current target only; columns ahead non-clickable until reached. Random access deferred (see Out of scope) |
| Chord size limit | **Hard cap at `voiceCountPolicy.max`** (default 4); click past the cap is a no-op with brief feedback |
| Commit model (chord) | **Snapshot-then-grade**: commit passes the held MIDI set to grading *before* releasing notes — does not rely on release-grace + settle timing |
| Voice assignment | None — grader and overlay are pitch-keyed |
| Preview | Ghost-note hover preview (approach C) |

## Architecture

Three new/changed pieces, mirroring `note_name.js`.

```
render() → adapter → onStaffLayout(layout) → exercise_sheet stores _staffLayout
mouse move → click component reads layout → snap → ghost note drawn
click → invert pixel→pitch → BROADCAST.NOTE "on" → grader (unchanged)
commit → snapshot held set → grade (notes still held) → NOTE "off" + BANK_NOTES → advance → re-render
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

### Modified: `exercise.js` **and** `play.js`
- Both instantiate the keyboard input components (`exercise.js:241`,
  `play.js:92`). `ClickNoteInputComponent` is wired into **both** entrypoints,
  gated identically to the keyboard components (skipped for symbolic-meter /
  key-signature exercises). Not wiring `play.js` would leave click input dead in
  half the app — both are in scope.

### New: shared key-signature logic (mandatory extraction)
- `getKeySignatureAlterations(key)` is currently private in
  `vexflow_adapter.js:383`. Pixel→pitch needs the same per-letter alteration
  map. Per the repo redundancy report, **extract it to a shared logic module**
  (e.g. `vexflow_adapter_logic.js` or `click_note_logic.js`) and have the
  adapter import it — do not copy the table. This extraction is required, not
  optional.

**Untouched:** event bus, chord bank, all graders. (No grader contract change —
v1 is sequential; see §4.)

## 1. Staff layout export (adapter → sheet)

New `opts.onStaffLayout` callback fired after measures are laid out and staves
drawn (geometry is valid only after `draw()`; the annotation loop already runs
post-draw, so capture goes there). Payload:

A score wraps onto multiple **systems** (rows). A column's `centerX` is not
unique across rows, and the same x can fall in different measures on different
rows — so every clickable element carries the system it belongs to and an
explicit pixel rect. Hit-testing picks the system by `py` first, then the
column by `px` within that system.

```javascript
{
  systems: [
    {
      systemIndex: 0,
      yTop: 80, yBottom: 240,    // vertical bounds of this row (all its staves)
      staves: [
        {
          clef: "treble",
          x: 60, width: 740,        // clickable x-range
          topLineY: 95,             // y of top staff line (line 0)
          bottomLineY: 135,         // y of bottom staff line (line 4)
          lineSpacing: 10,          // px between adjacent lines
          topLineStep: "F", topLineOctave: 5   // treble top line = F5; bass = A3
        },
        { clef: "bass", /* topLineStep: "A", topLineOctave: 3 */ }
      ]
    }
  ],
  columns: [
    // one entry per onset PER system it appears on
    { systemIndex: 0, onset: 0,    measureIndex: 0, measureX: 60, measureWidth: 180,
      centerX: 92,  rect: { x: 60, width: 64 } },
    { systemIndex: 0, onset: 1024, measureIndex: 0, measureX: 60, measureWidth: 180,
      centerX: 168, rect: { x: 124, width: 56 } }
  ]
}
```

`rect.x`/`rect.width` give each column a hit-zone (midpoint between adjacent
column centers, clamped to its measure bounds) so a click maps to exactly one
column without ambiguity at row edges.

Source data already exists in `render()`:
- systems: the per-row layout loop already tracks each system's stave set and y
  extents; expose `systemIndex`, `yTop`, `yBottom`.
- staves: `getYForLine(0)` / `getYForLine(4)` (→ `topLineY`/`bottomLineY`,
  spacing), `getNoteStartX()`, `getX()`, width.
- `topLineStep`/`topLineOctave`: fixed per clef (treble top line F5, bass A3).
- columns: reuse `analysisWindows` + `getColumnCenterX(col)` already computed
  for annotations; push `{systemIndex, onset, measureIndex, measureX,
  measureWidth, centerX, rect}`. The same onset on a wrapped row gets its own
  entry with that row's `systemIndex`.

## 2. Pixel→pitch inversion (`click_note_logic.js`)

Pure functions. Click at `(px, py)` relative to canvas:

**Pick system (row) first.** Choose the system whose `[yTop, yBottom]` contains
`py` (nearest by edge if `py` is between rows). All later lookups use that
system's staves and columns only — this is what disambiguates wrapped rows.

**Pick stave** within the chosen system. For each stave, playable zone =
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
- Base `alter` = key-signature alteration for that letter, from the
  **shared-extracted** `getKeySignatureAlterations(key)` (see Architecture —
  this module imports the same function the adapter uses; the table is never
  copied).
- Palette override: `♯`→+1, `♭`→−1, `♮`→0 (force natural),
  default/"diatonic"→keep key-sig `alter`.

**→ MIDI.** `(octave+1)*12 + STEP_SEMITONE[step] + alter` — same formula as
`note_name.js:179`. Clamp to 21–108; out-of-range → `null`.

**x → column** (within the already-chosen system). Pick the column whose `rect`
contains `px` (fallback: nearest `centerX` in that system). Returns the column
(`systemIndex`, `onset`, `measureIndex`) for grader targeting and ghost x.

**v1 gate:** for harmonization (sequential), a click resolving to a column
other than the current target onset is rejected (no `NOTE`, no ghost) — only
the active target column is clickable.

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

### Chord mode (harmonization) — accumulate → commit (sequential, v1)
- The active column is always the **current grading target** (the harmonization
  pointer's onset). Only that column is clickable; later columns are inert until
  the pointer reaches them. No random access in v1.
- Click empty pitch in active column → `NOTE "on"`; note stays held, added to
  the current chord, drawn pending.
- Re-click same pitch → `NOTE "off"`; removed.
- **Hard size cap.** While held count == `voiceCountPolicy.max` (default 4), a
  click on a *new* pitch is a no-op (no `NOTE on`, brief "max N notes" hint);
  toggling an already-held pitch off still works. Keeps the grader from ever
  seeing `too_many_voices` from click input. (Locked given-bass voices count
  toward neither the click cap nor the held set — they're score-supplied.)

**Commit — snapshot-then-grade (fixes the release-grace/settle race).**
The existing MIDI path relies on a ~150ms settle timer
(`exercise_sheet.onMidiNote`) firing *after* note-offs, while
`createHeldNoteTracker` only keeps released notes alive for `releaseGraceMs`
(120ms) — so a commit that releases first can grade an already-emptied set.
Click commit avoids the race entirely:

1. Commit gesture = existing bank key (SPACE/ENTER) or a **Done** button.
2. On commit, the component captures the current held MIDI set as a
   **snapshot** and drives grading with that snapshot **while the notes are
   still held** — it does not depend on the tracker's release window. Concretely:
   feed the snapshot to the same harmonization grade entry point the settle
   timer uses, synchronously, before any `NOTE "off"`.
3. *Then* release all held (`NOTE "off"` each) for audio/UI cleanup.

This keeps the grader contract identical (it receives a flat active-MIDI set)
while removing the timing dependency. No change to
`harmonization_grader_logic.js`; the only change is that click commit calls the
grade path with an explicit snapshot rather than waiting on release+settle.

### Single-note mode (melodic / one-voice) — one note per column
Scope for v1: single-voice exercises whose answer is one pitch per onset
(melodic identification / dictation-style entry). Pitch-name *identification*
exercises (`isPitchAnalysisType`) keep their existing `?`-slot click flow and
are **not** in scope here.

- Click pitch in the active column → commit that column's single answer as a
  **snapshot** (same mechanism as chord mode: hand the single MIDI to the grade
  path, then emit the `NOTE "on"`/`"off"` pair for audio). This avoids the
  `chord.js:224` issue where a quick on/off clears the pitch before grading
  reads it — grading reads the snapshot, not the live chord model.
- Re-click the active column with a different pitch → replaces that column's
  answer (snapshot overwrites).
- Advance is sequential (current target only, like chord mode); submit uses the
  exercise's normal flow.

### Held-note safety
On component disable, exercise change, or advance — release all held
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

**Wiring (`exercise.js` and `play.js`).** Instantiate `ClickNoteInputComponent`
beside `NoteNameInputComponent` in **both** entrypoints (`exercise.js:241`,
`play.js:92`), gated identically. Inject the sheet so the component can read
`_staffLayout` + held set and request the ghost draw. Mount the palette to
`#piano`.

**Events.** Click → `BROADCAST.NOTE "on"` (and `"off"` on re-click/commit).
Chord-mode commit → snapshot-grade, then release all held + `BANK_NOTES` (§4).
Identical channel to MIDI/keyboard; `midi.js` and `exercise_sheet.onMidiNote`
already subscribe.

**Edge cases.**
- Out-of-range click (no system/stave / MIDI <21 or >108) → no-op, no ghost.
- Click outside the active target column (sequential v1) → no-op, no ghost (§2).
- Click a new pitch when held count == `voiceCountPolicy.max` → no-op + hint (§4).
- Inter-row gap → nearest system by `py`; inter-stave gap → nearest `topLineY` (§2).
- Re-render mid-entry (advance) rebuilds `_staffLayout`; held set is component
  state and survives; pending overlay redrawn from it.
- Disable / exercise change / advance → release all held.
- MIDI + click both active → same event bus, coexist; no exclusivity mode.
- Duplicate pitch already held → re-click toggles off (no double `NOTE on`).

## 7. Testing

- `click_note_logic.test.js` (cold unit, no DOM): layout + pixel → pitch.
  Cover system (row) pick from `py` incl. inter-row gap, treble/bass boundary,
  ledger lines above & below, key-sig diatonic default (shared-extracted map),
  ♯/♭/♮ palette override, x→column via `rect` (incl. same onset on two systems
  resolving to the correct row), out-of-range → null, click outside active
  target column → null (sequential gate).
- Extraction test: shared `getKeySignatureAlterations` returns identical maps to
  the adapter's prior private version for a few keys (guards the refactor).
- Snapshot/cap logic (pure, if factored out): chord at `voiceCountPolicy.max`
  rejects a new pitch but allows toggle-off; commit yields the held MIDI set.
- Manual browser pass (per CLAUDE.md UI rule): harmonization exercise —
  click-build a chord, hit the cap, commit, verify grade fires on the snapshot
  (not an empty set); single-note exercise — click a melody; verify no stuck
  notes on advance; verify ghost tracks the cursor; verify columns ahead of the
  target are inert. Test from **both** `exercise.js` and `play.js` entrypoints.

## 8. Documentation impact

- No new exercise type or management command → no `exercise_types.md` /
  `management_commands.md` change.
- Significant multi-file feature → this spec + an implementation plan
  (writing-plans, next step).

## Out of scope (YAGNI)

- **Random-access column targeting** (clicking ahead/behind to edit any onset
  out of order). v1 is sequential — only the current grading target is
  clickable. Random access needs a selected-target-index model plus
  grade/render contract changes (`exercise_context.js:224` is pointer-only);
  deferred to a follow-up if students actually want non-linear entry.
- Double accidentals 𝄪 𝄫.
- Drag/glissando.
- Clicking pre-rendered noteheads (the other scope branch); pitch-name
  identification `?`-slot exercises keep their existing click flow.
- Free-x composition with no preset onsets.
- Touch/mobile gestures.
