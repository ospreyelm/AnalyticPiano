# MIDI Playback Design

**Date:** 2026-04-18  
**Status:** Approved  
**Scope:** Add score playback to ExerciseSheetComponent and PlaySheetComponent

---

## Summary

Add audio playback of the notated score to both the exercise and play views. Students hear the reference score (how it should sound) while following along with a column-highlight playhead. Controls live in the existing toolbar. Playback is independent of grading — MIDI input continues to work during playback.

---

## Goals

- Student can hear the full score as a reference before/while practicing
- Play/Stop toggle in toolbar, tempo slider (60–160 BPM)
- Column highlight shows current beat window while playing
- Works in both exercise view and play view
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
- Tick conversion: `seconds = (ticks / 4096) * (60 / bpm)` (quarter note = 1024 ticks)
- Uses existing `Tone.Sampler` from `MidiDevice` — ScorePlayer receives sampler reference at construction or calls notes via the existing `MidiDevice.noteOn/noteOff` interface
- Fires `tick(windowIndex)` at the onset of each window via a scheduled callback
- Fires `stopped` when transport reaches end or `stop()` is called
- `stop()` calls `Tone.Transport.stop()` + `Tone.Transport.cancel()` + `sampler.releaseAll()`
- No looping — single playthrough only

**Tone.js notes:**
- `Tone.Transport` is global — ScorePlayer starts and stops it. No conflict expected since nothing else uses Transport currently.
- Sampler is already loaded and warm (24 piano samples, A0–C8)

---

## Playback Controls Mixin (`components/music/playback_controls.js`)

Returns a single function: `renderPlaybackControls(container, scorePlayer)`.

Injects into the toolbar DOM between nav buttons and existing exercise controls:

```
[◀] [▶] [↺]  |  [▶ Play]  ♩= [────●────]  100 bpm
```

- Separator `|` visually isolates playback from nav
- Play button text toggles: `▶ Play` ↔ `■ Stop`
- Tempo slider: range 60–160, default 100 (or last stored value from `sessionStorage`)
- BPM label updates live as slider moves
- On play: calls `scorePlayer.play(timeline, tempo)`
- On stop: calls `scorePlayer.stop()`
- Listens for `stopped` event to reset button state when playback ends naturally
- Both sheet components call `renderPlaybackControls()` from their `render()` method

**Tempo persistence:** reads/writes `harmonylab.playback.tempo` in `sessionStorage` on slider change (matches existing volume persistence pattern in `midi_device.js`).

---

## Playhead Highlight

**How it works:**

- Both sheet components track `_playbackWindowIndex` (null = not playing)
- On `tick(windowIndex)`: store index, call `_drawPlaybackHighlight()`
- On `stopped`: clear index, call `_clearPlaybackHighlight()`

**Drawing:**

- `_drawPlaybackHighlight()` reads cached window x-position from `_windowPositionCache` (see below)
- Draws a semi-transparent blue column on the VexFlow canvas:
  - Fill: `rgba(79, 172, 254, 0.15)`
  - Border: `1px solid rgba(79, 172, 254, 0.35)`
  - Height: full staff system (top of treble staff to bottom of bass staff)
  - Width: window column width from cache
- Does **not** re-render VexFlow — canvas overlay only (fast, no flicker)
- Clears previous rect before drawing new one (store previous rect coords)

**Window position cache (`_windowPositionCache`):**

- Exercise sheet already caches positions in `_identWindowLayout` (keyed by `windowIndex`) via `onWindowPosition` callback from VexFlow adapter
- Play sheet needs equivalent: add `onWindowPosition` callback wiring to its render path in `vexflow_adapter.js` — small addition, same pattern
- Both sheets expose `_windowPositionCache` as `{ [windowIndex]: {x, y, width, height} }`

---

## Integration Points

### ExerciseSheetComponent

- `ScorePlayer` instantiated in `initExercise()`, timeline built from `exerciseContext.getDefinition().getScore()`
- `renderPlaybackControls()` called from `render()`
- `scorePlayer.stop()` called in `renderPristine()` before loading new exercise (already resets `scex.graded`, add stop here)
- Playback runs independently of grading — no interaction with `ChoraleGrader` or `IdentificationGrader`

### PlaySheetComponent

- `ScorePlayer` instantiated after corpus load completes
- `renderPlaybackControls()` called from `render()`
- `scorePlayer.stop()` called before corpus reload

### Sampler Access

ScorePlayer needs access to the Tone.js sampler. Two options:
1. Pass `midiDevice` reference to ScorePlayer; call `midiDevice.triggerAttack(midi)` / `midiDevice.triggerRelease(midi)`
2. ScorePlayer accesses sampler directly via the global `Tone.Sampler` instance

**Decision:** Option 1 — pass `midiDevice` reference. Reuses existing MIDI-to-note-name conversion (`_midiToTone()`) and volume/mute state. ScorePlayer calls `midiDevice.playNote(midi)` and `midiDevice.releaseNote(midi)` — two small public wrapper methods added to `MidiDevice` that delegate to the existing internal sampler calls. If student mutes audio, playback also mutes (correct behavior).

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Play clicked, no score loaded | Button disabled until timeline available |
| Exercise advances during playback | `renderPristine` calls `stop()` first |
| Corpus reloads during playback | `stop()` called before reload |
| Student plays MIDI during playback | Works normally — grading unaffected |
| Playback ends naturally | `stopped` event fires, button resets to Play |
| Tempo changed during playback | Takes effect on next play (not mid-playback) |
| Audio muted via mute button | Playback still schedules; sampler muted so silent |

---

## Files Changed

| File | Change |
|------|--------|
| `lab/static/js/src/models/score_player.js` | **New** — ScorePlayer model |
| `lab/static/js/src/components/music/playback_controls.js` | **New** — toolbar mixin |
| `lab/static/js/src/components/music/exercise_sheet.js` | Add ScorePlayer, controls, highlight drawing |
| `lab/static/js/src/components/music/play_sheet.js` | Add ScorePlayer, controls, highlight drawing |
| `lab/static/js/src/components/music/vexflow_adapter.js` | Wire `onWindowPosition` for play sheet |
| `lab/static/js/src/components/music.js` | Call `scorePlayer.stop()` in `renderPristine` |
| `lab/static/js/src/models/midi_device.js` | Add `playNote(midi)` and `releaseNote(midi)` public methods |

---

## Out of Scope

- Loop playback
- Per-voice solo/mute during playback
- Playback of student's input (answer verification)
- Progress scrubber / click-to-seek
- Play current page only (always plays full score)
