# Click-on-Staff Note Input — Design Spec

**Date:** 2026-05-28
**Status:** Approved (brainstorming) — implementation plan pending
**Scope:** Empty-staff pitch entry as a MIDI-free input fallback

## Problem

Students without a MIDI controller need a way to enter pitches into graded
exercises. Computer keyboard already works (`KeyboardShortcutsComponent`,
`NoteNameInputComponent`) by broadcasting `EVENTS.BROADCAST.NOTE` on/off — the
same channel MIDI uses. For harmonization, that live-note channel also triggers
the settle-timer grading path, so click input uses pending UI state while the
student is building and hands an explicit MIDI set to the same harmonization
grading logic on commit.

This feature adds **mouse click on an empty staff position** as a MIDI-free
input source. A click resolves to a pitch; in harmonization v1 it updates a
pending realization, and commit grades the same flat MIDI set shape that MIDI
input ultimately grades.

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
- **Input components integrate at the sheet/context boundary.** `note_name.js`
  remains the working template for component lifecycle and toolbar mounting. For
  harmonization, click input intentionally stops short of broadcasting live
  `NOTE` events during construction because that channel already drives
  settle-timer grading.
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

Click input MUST be indistinguishable at the grading boundary from
MIDI/keyboard. At grade time it hands the grader the **same data shape** any
source produces: a flat set of sounding MIDI numbers (chord) or a single MIDI
(melodic). For harmonization, click construction is a pending UI state until
explicit commit; it does **not** broadcast live `NOTE` events while the student
is still building the chord, because the current harmonization MIDI path grades
every `NOTE` event after the settle delay. No click-specific field, flag, or
branch reaches a grader. This is load-bearing for the
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
| Commit model | Harmonization v1: chord = accumulate pending notes, then explicit commit. Single-note click entry is deferred until an existing snapshot-compatible target is named |
| Horizontal targeting (v1) | **Sequential** — clicks build the current target only; columns ahead non-clickable until reached. Random access deferred (see Out of scope) |
| Chord size limit | **Hard cap at available student slots** = `voiceCountPolicy.max - suppliedVoiceCount` (supplied = locked voices with concrete `.midi`; default max 4); click past the cap is a no-op with brief feedback |
| Locked voices | **Generic, not bass-special-cased** — merge only `lockedVoices` with concrete `.midi`; future RN harmonization omits `lockedVoices.B` so the student clicks the bass (see §4) |
| Commit model (chord) | **Snapshot-then-grade**: commit passes `locked target MIDI + clicked MIDI` to the shared harmonization grading helper — does not rely on release-grace + settle timing |
| Voice assignment | None — grader and overlay are pitch-keyed |
| Preview | Ghost-note hover preview (approach C) |
| Source mode | **Explicit Live ↔ Click toggle.** Default chosen by MIDI availability (no device → default Click + recommend it; device present → default Live). Always overridable; persists per session. Source mode gates affordances + which component is armed |
| Click-mode harmonization grading | **All grading routes through explicit commit.** Click mode suppresses live MIDI/computer-keyboard note handling for harmonization, so a connected device can't auto-grade behind the student's deliberate build |

## Architecture

Three new/changed pieces, mirroring `note_name.js`.

```
render() → adapter → onStaffLayout(layout) → exercise_sheet stores _staffLayout
mouse move → click component reads layout → snap → ghost note drawn
click → invert pixel→pitch → update pending click set (no live NOTE event in harmonization)
commit → merge locked target MIDI + pending click set → grade explicit MIDI set → advance → re-render
```

### New: `ClickNoteInputComponent` — `lab/static/js/src/components/input/click_note.js`
- Renders the accidental palette UI (mounted to `#piano`, like `note_name.js`).
- Owns click/mousemove/mouseleave handlers on `canvas#staff`.
- Entry state: active column, sticky accidental, pending clicked-note set
  (chord mode).
- For harmonization, click/re-click mutates only the pending set and overlay;
  commit grades an explicit MIDI snapshot. It does not use live
  `EVENTS.BROADCAST.NOTE` during chord construction, avoiding the existing
  settle-timer auto-grade path.
- For non-harmonization modes that remain in scope, it may use the standard
  `EVENTS.BROADCAST.NOTE` channel only after the spec names an existing
  snapshot-compatible grade path.
- `disable()` clears pending click state and releases any notes if a future mode
  uses live `NOTE` events.

### New: `click_note_logic.js` (+ `.test.js`) — `lab/static/js/src/components/input/`
- Pure pixel→pitch math, no DOM. Follows the repo `*_logic.js` + `.test.js`
  convention (e.g. `computer_keyboard_ux_logic`).

### Modified: `vexflow_adapter.js`
- New `opts.onStaffLayout(layout)` callback, fired once per `render()` (same
  pattern as the existing `opts.onWindowPosition` hook).
- New `opts.harmonizationPending` param — the active column's pending-but-
  uncommitted notes, rendered via the existing `buildHarmonizationOverlayVoice`
  in a distinct (pending) style.

### Modified: `exercise_sheet.js`
- Stores `this._staffLayout` from `onStaffLayout` (extends the existing
  `_identWindowLayout` precedent).
- Builds `harmonizationPending` from the click component's pending clicked set
  each render.
- Draws the ghost note (top layer, after adapter render, throttled).

### Modified: `exercise.js` (only)
- `ClickNoteInputComponent` is wired into the **exercise** entrypoint only,
  beside the existing `NoteNameInputComponent` (`exercise.js:241`), gated
  identically to the keyboard components (skipped for symbolic-meter /
  key-signature exercises).
- **`play.js` is out of scope.** It is the free-play sandbox: it builds
  `PlaySheetComponent` (not `ExerciseSheetComponent`) and has no
  `exerciseContext`/harmonization targets (`play.js:124-136`). Harmonization
  exercises always route through `exercise.js`, so a click component in `play.js`
  would have nothing to grade. Click-as-free-entry in play would be a separate
  feature with its own design.
- The exercise entrypoint owns the **source-mode** state (`live` ↔ `click`) and
  passes it to the sheet + input components so each arms/disarms and shows/hides
  its affordances accordingly (see "Source mode").
- This source-mode state is separate from the existing
  `EVENTS.BROADCAST.INPUT_MODE` qwerty/notename computer-keyboard mode. Do not
  reuse that event/value space for Live/Click.

### New: shared key-signature logic (mandatory extraction)
- `getKeySignatureAlterations(key)` is currently private in
  `vexflow_adapter.js:383`. Pixel→pitch needs the same per-letter alteration
  map. Per the repo redundancy report, **extract it to a shared logic module**
  (e.g. `vexflow_adapter_logic.js` or `click_note_logic.js`) and have the
  adapter import it — do not copy the table. This extraction is required, not
  optional.

**Untouched:** event bus, chord bank, `harmonization_grader_logic.js`.
`exercise_context.js` gets a small shared harmonization helper so the existing
MIDI settle path and click commit both evaluate the same explicit MIDI-set
contract (see §4). The musical grader contract does not change.

## Source mode (Live ↔ Click)

Mouse entry is a different interaction model from live play: deliberate
placement + explicit commit, not real-time performance. An explicit mode keeps
each model's UI clean and prevents the two harmonization grading contracts
(live-settle vs commit) from running at once.

**Two source modes.** `live` (MIDI + computer keyboard — the existing
performance behavior) and `click` (mouse editor + explicit commit). Surface this
as a toolbar toggle near `#piano`, labeled in the UI as **Live** / **Click**.

**Separate axis from qwerty/notename.** `EVENTS.BROADCAST.INPUT_MODE` already
controls the computer-keyboard sub-mode with values `"qwerty"` and
`"notename"` in `note_name.js`. Live/Click is a higher-level source mode and
must not reuse that event or those values. Add a separate source-mode state or a
new event such as `EVENTS.BROADCAST.INPUT_SOURCE_MODE` with values `"live"` and
`"click"`.

**Default + recommendation.** `midi.js` already detects zero MIDI inputs
(`midi.js:183`, which today broadcasts the "no MIDI" guidance), but that is only
a notification side effect. Add a small structured availability signal, e.g.
`EVENTS.BROADCAST.MIDI_INPUTS_CHANGED` with `{ inputCount }`, emitted on initial
MIDI access, WebMIDI error (`inputCount: 0`), and device state changes. Source
mode defaults from that signal: no device → default to **Click** and surface the
existing guidance as a "using click input" recommendation; device present →
default to **Live**. The toggle is always manually overridable; selection
persists per session (client-side, e.g. `localStorage` — no exercise/DB change).

**What the mode gates.**
- `click` mode arms `ClickNoteInputComponent` and shows the accidental palette,
  ghost preview, and **Done** commit button. For harmonization it **suppresses
  live MIDI/computer-keyboard note handling and live-settle auto-grade** so all
  grading goes through click commit (§4) — even if a device is plugged in.
  Physical MIDI and computer-keyboard note events are ignored for harmonization
  in Click mode v1; they do not add to the pending clicked set.
- `live` mode hides the palette/ghost/Done and restores the existing
  MIDI/computer-keyboard live-settle path unchanged. `ClickNoteInputComponent`
  is disarmed (no canvas hit-testing).

**Mid-session device change.** WebMIDI `onstatechange` (plug/unplug) emits the
structured MIDI availability signal but does **not** force a mode switch — it
only updates the recommendation (e.g. offer "switch to click input?" when the
last device disappears). Never yank the student out of a mode mid-build.

**Mode switch clears in-flight state.** Switching modes clears any pending
clicked notes and removes the pending overlay (same as disable, §4) so a
half-built chord never leaks across models.

This mode is a UI/arming + grade-routing layer only. The grading boundary stays
input-agnostic: whichever path runs hands the grader the same flat MIDI set.

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

Mode chosen from `definition`. Harmonization is the only v1 commit mode; the
single-note branch is documented below as deferred.

### Chord mode (harmonization) — accumulate → commit (sequential, v1)
- The active column is always the **current grading target** (the harmonization
  pointer's onset). Only that column is clickable; later columns are inert until
  the pointer reaches them. No random access in v1.
- Click empty pitch in active column → add it to the component's pending clicked
  set and draw it pending. Do **not** broadcast `NOTE "on"` in harmonization:
  `exercise_sheet.onMidiNote` currently schedules grading after every `NOTE`
  event, so live NOTE construction would violate explicit commit.
- Re-click same pitch → remove it from the pending clicked set.
- **Hard size cap.** Compute `suppliedVoiceCount` from the target's
  `lockedVoices` entries that carry a concrete `.midi` (the given notes the
  student does not click), then cap student-clicked notes at
  `max(0, voiceCountPolicy.max - suppliedVoiceCount)` (default policy max 4). A
  click on a *new* pitch past that cap is a no-op (brief "max N notes" hint);
  toggling an already-pending pitch off still works. This keeps the complete
  submitted MIDI set from ever exceeding the grader's `voiceCountPolicy.max`.

- **Treat `lockedVoices` generically — do not special-case bass.** Merge only
  the voices present in `target.lockedVoices` with a concrete `.midi`; that same
  set reduces the click cap. The given bass is included in the graded
  `activeMidi` (so `harmonizationMatch()` sees `lockedVoices.B.pc`) but the
  student never re-clicks it. This generalizes cleanly to **future Roman-numeral
  harmonization**: omit `lockedVoices.B`, and the student must click the bass
  (it counts toward `voiceCountPolicy.max`), with the bass graded through a
  different target contract (e.g. `requiredBassPc`, `bassChoices`, or
  "lowest note must be the inversion bass") rather than `lockedVoices.B`. A
  pc-only locked voice (no `.midi`) is a *constraint* the student satisfies by
  clicking, so it does not reduce slots and is not merged.

**Commit — snapshot-then-grade (fixes the release-grace/settle race).**
The existing MIDI path relies on a ~150ms settle timer
(`exercise_sheet.onMidiNote`) firing *after* note-offs, while
`createHeldNoteTracker` only keeps released notes alive for `releaseGraceMs`
(120ms) — so a commit that releases first can grade an already-emptied set.
Click commit avoids the race entirely:

1. Commit gesture = existing bank key (SPACE/ENTER) or a **Done** button.
2. On commit, the component captures the pending clicked MIDI set and asks
   `exercise_context` to build the complete active MIDI snapshot for the current
   harmonization target:
   `activeMidi = lockedTargetMidi + pendingClickedMidi`.
   This is the same flat active-MIDI set that MIDI input must eventually produce;
   it includes locked bass/soprano requirements because
   `harmonizationMatch()` validates `lockedVoices` against `activeMidi`.
3. `exercise_context` exposes a shared helper, e.g.
   `_gradeHarmonizationMidiSet(activeMidi, options)`, that contains the current
   harmonization acceptance logic now embedded in `grade()`:
   `harmonizationMatch(targets[ptr], activeMidi)`, append accepted sonority,
   advance `_harmonizationPointer`, update `graded/state`, broadcast
   `NEXT_CHORD` if needed, and render/update display. The existing MIDI settle
   timer calls this helper with `tracker.activeMidi(Date.now())`; click commit
   calls it synchronously with the snapshot.
4. After grading, clear the pending clicked set. There are no click-generated
   harmonization `NOTE` events to release in v1; MIDI/keyboard live notes remain
   handled by their existing paths.

This keeps the musical grader contract identical (it receives a flat
active-MIDI set) while removing the timing dependency. No change to
`harmonization_grader_logic.js`; the change is in `exercise_context.js`, where
the existing harmonization grade branch is factored into an explicit MIDI-set
helper shared by MIDI settle and click commit.

**In `click` source mode the MIDI live-settle auto-grade is suppressed** (see
"Source mode"): the settle timer that calls the helper with
`tracker.activeMidi(Date.now())` does not fire for harmonization, so a connected
device never auto-grades behind the student's deliberate build. The same helper
still runs — only its trigger changes from settle-timer to explicit commit.
In Click mode v1, physical MIDI and computer-keyboard note events are ignored
for harmonization rather than converted into pending clicked notes. Live
performance input remains available by switching back to Live mode.

### Single-note mode (deferred until an existing target is named)
The earlier "one note per column" idea is not v1 until the implementation plan
names an existing exercise type and grade path that accepts a one-MIDI snapshot
per onset. Pitch-name *identification* exercises (`isPitchAnalysisType`) keep
their existing `?`-slot click flow and are **not** in scope here.

Do not implement a quick `NOTE "on"`/`"off"` single-note path as a substitute:
`chord.js:224` clears the pitch on note-off before normal grading reads the
chord model. A future single-note click mode must either use an existing
snapshot-compatible grade path or first define one in a separate spec.

### Pending-state safety
On component disable, exercise change, or advance — clear pending clicked notes
and remove the pending overlay. If a future non-harmonization mode uses live
`NOTE` events, it must also release those notes on disable.

## 5. Rendering student input

Student notes never touch the score's SATB voices. Two pitch-keyed layers:

### Pending-realization overlay (accumulated chord)
- New `opts.harmonizationPending = { measureIndex, onset, midiNotes, spellings }`
  for the active column's pending-but-uncommitted clicked notes.
- Reuses `buildHarmonizationOverlayVoice` — same chord-stack builder as the
  accepted realization.
- Styled distinct from committed: accepted = black, pending = blue/gray
  (`#5b8def`), so "building" reads differently from "locked in."
- `exercise_sheet` builds this from the click component's pending clicked set each
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
Deferred for v1. A future single-note mode can reuse the overlay approach, but
only after a concrete exercise type and snapshot-compatible grading path are
specified.

## 6. Event wiring & edge cases

**Wiring (`exercise.js` only).** Instantiate `ClickNoteInputComponent` beside
`NoteNameInputComponent` in the exercise entrypoint (`exercise.js:241`), gated
identically. The `ExerciseSheetComponent` is currently built inline inside the
`MusicComponent` initializer (`exercise.js:346-356`); hoist it to
`this.models.exerciseSheet` so the click component receives the **same** sheet
instance. Because initializers run in array order and the click component reads
the hoisted sheet, append the click-component initializer (and then the
source-mode bootstrap) to the **end** of the methods array, after the
`MusicComponent` initializer. Inject the sheet so the component can read
`_staffLayout` + pending clicked set and request the ghost draw. Mount the
palette to `#piano`. The entrypoint owns source-mode state, applies an initial
mode synchronously after components exist, then refines it from the structured
MIDI availability signal, and arms/disarms the click component + palette/Done UI
on toggle (see "Source mode"). `play.js` is out of scope (see "Modified:
`exercise.js` (only)" under Architecture, and "Out of scope").

**Events.** Harmonization click/re-click mutates only pending click state; it
does not broadcast `BROADCAST.NOTE` while building. Chord-mode commit calls the
shared explicit-MIDI-set harmonization helper (§4). `BANK_NOTES` may still be
used as the UI gesture source, but the click component must intercept/handle
that gesture so it does not rely on chord-bank live-note state.

**Edge cases.**
- Out-of-range click (no system/stave / MIDI <21 or >108) → no-op, no ghost.
- Click outside the active target column (sequential v1) → no-op, no ghost (§2).
- Click a new pitch when pending count has reached available student slots
  (`voiceCountPolicy.max - lockedVoiceCount`) → no-op + hint (§4).
- Inter-row gap → nearest system by `py`; inter-stave gap → nearest `topLineY` (§2).
- Re-render mid-entry rebuilds `_staffLayout`; pending clicked set is component
  state and survives until commit/advance; pending overlay redraws from it.
- Disable / exercise change / advance / **mode switch** → clear pending clicked
  state + remove pending overlay.
- Source mode = `click`: physical MIDI/computer-keyboard note input ignored for
  harmonization and live-settle auto-grade suppressed; all grading via commit.
  Source mode = `live`: existing MIDI/computer-keyboard path unchanged, click
  disarmed.
- Device plugged/unplugged mid-session (`onstatechange`) → emit structured MIDI
  availability and update the mode recommendation only; never force-switch
  mid-build.
- Duplicate pending pitch → re-click toggles off.

## 7. Testing

- `click_note_logic.test.js` (cold unit, no DOM): layout + pixel → pitch.
  Cover system (row) pick from `py` incl. inter-row gap, treble/bass boundary,
  ledger lines above & below, key-sig diatonic default (shared-extracted map),
  ♯/♭/♮ palette override, x→column via `rect` (incl. same onset on two systems
  resolving to the correct row), out-of-range → null, click outside active
  target column → null (sequential gate).
- Extraction test: shared `getKeySignatureAlterations` returns identical maps to
  the adapter's prior private version for a few keys (guards the refactor).
- Snapshot/cap logic (pure, if factored out): clicked notes at available student
  slot cap reject a new pitch but allow toggle-off; commit yields
  `lockedTargetMidi + pendingClickedMidi`.
- Source-mode logic (pure, if factored out): default resolves to `click` when
  input count is 0 and `live` when ≥1; a stored preference overrides the
  default; switching modes returns "clear pending." Verify this is independent
  from the existing qwerty/notename `INPUT_MODE` keyboard sub-mode.
- Manual browser pass (per CLAUDE.md UI rule): harmonization exercise —
  click-build a chord, hit the cap, commit, verify grade fires on
  `lockedTargetMidi + pendingClickedMidi` and not an empty set; verify ghost
  tracks the cursor; verify columns ahead of the target are inert; verify
  pending state clears on advance. Test from the `exercise.js` entrypoint
  (the only wired entrypoint). Source mode: with no MIDI device, verify the app
  defaults to Click and recommends it; with a device, defaults to Live; toggle
  both ways and confirm palette/Done show only in Click, qwerty/notename still
  works as a separate Live-mode keyboard sub-toggle, and a connected device does
  not add notes or auto-grade harmonization while in Click mode; switching modes
  mid-build clears the pending chord.

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
- **Click input in `play.js` (free-play sandbox).** It uses `PlaySheetComponent`
  with no `exerciseContext`/grading targets, so there is nothing to commit
  against. Click-as-free-entry there is a distinct feature needing its own design.
