# MIDI Playback Design

**Date:** 2026-04-18  
**Status:** Approved (revised post code-review)  
**Scope:** Add score playback to ExerciseSheetComponent and PlaySheetComponent

---

## Summary

Add audio playback of the notated score to both the exercise and play views. Students hear the reference score (how it should sound) while following along with a column-highlight playhead. Controls live in the existing toolbar. Playback is independent of grading — MIDI input continues to work during playback.

---

## Goals

- Student can hear the full score as a reference before/while practicing
- Play/Stop toggle in toolbar, tempo slider (60–160 BPM)
- Column highlight shows current beat window while playing
- Works in exercise view and in play view corpus mode (`?newvf&loadCorpus=...`); hidden in standard play-view chord-entry mode
- No playback on exercise advance / corpus reload

---

## Architecture

Three new units:

| Unit | File | Purpose |
|------|------|---------|
| `ScorePlayer` | `models/score_player.js` | Scheduling, audio, state |
| Playback controls mixin | `components/music/playback_controls.js` | Toolbar DOM injection |
| Highlight drawing | inline in each sheet component | Canvas overlay for playhead |

---

## ScorePlayer (`models/score_player.js`)

AMD module, plain constructor. Owns all playback logic — no references to UI components.

**API:**

```javascript
var player = new ScorePlayer();
player.play(timeline, tempo);   // start playback
player.stop();                  // cancel and reset
player.isPlaying();             // boolean
player.setTempo(bpm);           // update tempo (takes effect on next play())
player.on('tick', fn);          // fn(windowIndex) called at each new onset window
player.on('stopped', fn);       // called when playback ends or is cancelled
```

**Implementation:**

- Accepts `timeline` — flat array from `ScoreTimeline.buildTimeline()`
- Groups events by onset window (same grouping as `ChoraleGrader`)
- Schedules all note attacks/releases via `Tone.Transport.schedule()` before calling `Tone.Transport.start()`
- **Tick conversion:** `seconds = (ticks / 1024) * (60 / bpm)` — quarter note = 1024 ticks, so 1024 ticks at 60 BPM = 1 second. (A whole note = 4096 ticks = 4 seconds at 60 BPM.)
- Uses `midiDevice.playNote(midi)` / `midiDevice.releaseNote(midi)` — see Sampler Access below
- Fires `tick(windowIndex)` at the onset of each window via a scheduled callback
- Fires `stopped` when transport reaches end or `stop()` is called
- `stop()` calls `Tone.Transport.stop()` + `Tone.Transport.cancel()` + releases all notes via `midiDevice.releaseAllNotes()`
- No looping — single playthrough only

**Transport reset on play():** `Tone.Transport.stop()` halts but does not reset the cursor. `play()` must always call `Tone.Transport.stop()`, `Tone.Transport.cancel()`, and `Tone.Transport.position = 0` before scheduling and starting — even on first play. This ensures repeated play calls always start from the beginning.

**AudioContext resume race:** `play()` must wrap scheduling inside `Tone.start().then(function() { ... })`. `Tone.start()` returns a Promise that resolves once the AudioContext is running. Without this, clicking Play immediately after page load (before any MIDI/keyboard interaction) will silently no-op in Chrome because the AudioContext hasn't been resumed yet. `Tone.start()` is safe to call multiple times.

**Tone.js notes:**
- `Tone.Transport` is global — ScorePlayer starts and stops it. No conflict expected since nothing else uses Transport currently.
- Sampler is already loaded and warm (30 piano samples, A0–C8)

---

## Playback Controls Mixin (`components/music/playback_controls.js`)

Returns a single function: `renderPlaybackControls(container, scorePlayer, getTimeline)`.

- `container` — DOM element or jQuery selector for toolbar
- `scorePlayer` — ScorePlayer instance
- `getTimeline` — zero-argument function called at play-time to retrieve the current timeline; sheet component passes a closure returning its cached timeline. This defers timeline access to click time so the mixin doesn't need to hold a stale reference.

Injects into the toolbar DOM between nav buttons and existing exercise controls:

```
[◀] [▶] [↺]  |  [▶ Play]  ♩= [────●────]  100 bpm
```

- Separator `|` visually isolates playback from nav
- Play button text toggles: `▶ Play` ↔ `■ Stop`
- Tempo slider: range 60–160, default 100 (or last stored value from `sessionStorage`)
- BPM label updates live as slider moves
- On play: calls `scorePlayer.play(getTimeline(), tempo)`
- On stop: calls `scorePlayer.stop()`
- Listens for `stopped` event to reset button state when playback ends naturally
- **Idempotency:** `renderPlaybackControls()` checks for existing `#playback-controls` in container before injecting; if found, updates `scorePlayer` and `getTimeline` references on the existing element and returns. This prevents DOM duplication on repeated `render()` calls.

**Tempo persistence:** reads/writes `harmonylab.playback.tempo` in `sessionStorage` on slider change.

**Open question resolved:** MidiDevice volume persistence uses server-backed AJAX preferences, not sessionStorage. Playback tempo uses sessionStorage (simpler, not user-account-level preference).

---

## Playhead Highlight

**How it works:**

- Both sheet components track `_playbackWindowIndex` (null = not playing)
- On `tick(windowIndex)`: store index, call `_drawPlaybackHighlight()`
- On `stopped`: clear index, call `_clearPlaybackHighlight()`

**Drawing:**

- `_drawPlaybackHighlight()` reads cached window center-x from `_windowPositionCache`
- Draws a semi-transparent blue column on the VexFlow canvas:
  - Fill: `rgba(79, 172, 254, 0.15)`
  - Border: `1px solid rgba(79, 172, 254, 0.35)`
  - Height: full staff system (top of treble staff to bottom of bass staff — derive from stored y + fixed offset)
  - **Width:** fixed 30px centered on cached x (adapter emits center x only, no column width)
- Does **not** re-render VexFlow — canvas overlay only (fast, no flicker)
- Clears previous rect before drawing new one (store previous rect coords)

**Window position cache (`_windowPositionCache`):**

The VexFlow adapter emits `onWindowPosition({windowIndex, onset, x, y})` where `x` is the column center X and `y` is `bassStave.getBottomY() + 18`. Width is not emitted — use fixed 30px.

- **Exercise sheet:** already caches via `_identWindowLayout` in `onWindowPosition` callback ([exercise_sheet.js:1125](lab/static/js/src/components/music/exercise_sheet.js#L1125)). Reuse this cache as `_windowPositionCache` (alias).
- **Play sheet:** does NOT currently pass `onWindowPosition` to the adapter ([play_sheet.js:206](lab/static/js/src/components/music/play_sheet.js#L206)). Add this callback in play sheet's render options — no adapter changes needed. The adapter already supports the callback ([vexflow_adapter.js:1241](lab/static/js/src/components/music/rendering/vexflow_adapter.js#L1241)).
- Both sheets store cache as `{ [windowIndex]: {x, y} }`

---

## Integration Points

### ExerciseSheetComponent

- `ScorePlayer` instantiated in `initComponent()` ([exercise_sheet.js:137](lab/static/js/src/components/music/exercise_sheet.js#L137)) — there is no `initExercise()` method; lifecycle entry is `initComponent`
- Timeline built from `exerciseContext.getDefinition().getScore()` at play-time (not init), so score is available
- `renderPlaybackControls()` called from `render()` (idempotent — safe to call repeatedly)
- `scorePlayer.stop()` called in `music.js renderPristine()` before loading new exercise
- Playback runs independently of grading — no interaction with `ChoraleGrader` or `IdentificationGrader`

### PlaySheetComponent

- **Scope:** Play sheet playback is only active in corpus mode (`?newvf` + `?loadCorpus` in URL). In standard chord-entry mode there is no CIR score/timeline — the Play button is hidden (not just disabled) when `corpusFile` is absent.
- `ScorePlayer` instantiated in play sheet's `initComponent()`
- `renderPlaybackControls()` called from `render()` (idempotent); passes `getTimeline` closure returning `ScoreTimeline.buildTimeline(self._corpusPayload.score)` — rebuilt from the cached payload each time play is clicked
- **Stop on corpus reload:** Corpus loading happens inside `renderWithState()` in `play_sheet.js:render()`. Call `scorePlayer.stop()` at the top of `renderWithState()` before re-rendering — this covers both first load and subsequent re-renders triggered by UI changes (voice filter, key signature)
- Playback plays full score regardless of active voice filters (voices, octave-shift) — always uses raw timeline from full CIR score

### Sampler Access

ScorePlayer needs access to the Tone.js sampler. Pass `midiDevice` reference to ScorePlayer constructor.

ScorePlayer calls three new public methods added to `MidiDevice`:
- `midiDevice.playNote(midi)` — triggers attack via internal sampler (wraps existing inline logic at [midi_device.js:438](lab/static/js/src/models/midi_device.js#L438))
- `midiDevice.releaseNote(midi)` — triggers release
- `midiDevice.releaseAllNotes()` — calls `sampler.releaseAll()`

These delegate to the existing sampler calls. Midi-to-note-name conversion is inline in MidiDevice around line 420 — extract into a small private `_midiToToneName(midi)` helper as part of this work (no behavior change, just DRY).

Benefit: volume and mute state are respected automatically — if student mutes audio, playback is also silent.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Play clicked, no score loaded | Button disabled until timeline available |
| Exercise advances during playback | `renderPristine` in music.js calls `stop()` first |
| Key signature change or other re-render | `renderPristine` path covers this; no additional stop needed |
| Corpus reloads during playback | `stop()` called before reload |
| Student plays MIDI during playback | Works normally — grading unaffected |
| Playback ends naturally | `stopped` event fires, button resets to Play |
| Tempo changed during playback | Takes effect on next play (not mid-playback) |
| Audio muted via mute button | Playback still schedules; sampler muted so silent |
| `render()` called during playback | Controls re-use existing DOM (idempotent), highlight redraws on next tick |

---

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/models/score_player.js` | **New** — ScorePlayer model |
| `lab/static/js/src/components/music/playback_controls.js` | **New** — toolbar mixin (idempotent) |
| `lab/static/js/src/components/music/exercise_sheet.js` | Add ScorePlayer init, controls, highlight drawing |
| `lab/static/js/src/components/music/play_sheet.js` | Add ScorePlayer init, controls, highlight, `onWindowPosition` callback |
| `lab/static/js/src/components/music.js` | Call `scorePlayer.stop()` in `renderPristine` |
| `lab/static/js/src/models/midi_device.js` | Add `playNote`, `releaseNote`, `releaseAllNotes` public methods; extract `_midiToToneName` helper |

Note: `vexflow_adapter.js` requires **no changes** — adapter already supports `onWindowPosition`. Only play sheet needs to pass the callback.

---

## Out of Scope

- Loop playback
- Per-voice solo/mute during playback
- Playback of student's input (answer verification)
- Progress scrubber / click-to-seek
- Play current page only (always plays full score)
- Voice filter / octave-shift applied to playback audio
