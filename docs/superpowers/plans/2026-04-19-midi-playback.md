# MIDI Score Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audio playback of the notated CIR score to ExerciseSheetComponent and PlaySheetComponent, with Play/Stop toolbar controls, tempo slider, and a canvas-overlay column-highlight playhead.

**Architecture:** A new `ScorePlayer` model owns all Tone.js Transport scheduling and fires `tick`/`stopped` events. A new `playback_controls` mixin injects idempotent toolbar DOM. Both sheet components listen to player events to draw/clear a semi-transparent blue highlight on the canvas overlay without re-rendering VexFlow.

**Tech Stack:** AMD/RequireJS modules, Tone.js 14.8.3 (already loaded as `"Tone"`), jQuery, Backbone-style MicroEvent mixin

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `lab/static/js/src/models/score_player.js` | **Create** | Scheduling, audio triggering, tick/stopped events |
| `lab/static/js/src/components/music/playback_controls.js` | **Create** | Idempotent toolbar DOM injection, Play/Stop button, tempo slider |
| `lab/static/js/src/models/midi_device.js` | **Modify** | Add `playNote`, `releaseNote`, `releaseAllNotes` public methods; extract `_midiToToneName` private helper |
| `lab/static/js/src/components/music/exercise_sheet.js` | **Modify** | Add ScorePlayer init, call `renderPlaybackControls`, draw/clear highlight on tick/stopped |
| `lab/static/js/src/components/music/play_sheet.js` | **Modify** | Add ScorePlayer init, `_cachedTimeline`, `onWindowPosition` callback, call `renderPlaybackControls`, stop on re-render |
| `lab/static/js/src/components/music.js` | **Modify** | Call `sheetComponent.scorePlayer.stop()` at top of `renderPristine` |

---

## Task 1: Add public audio methods to MidiDevice

**Files:**
- Modify: `lab/static/js/src/models/midi_device.js`

The sampler is a module-level `var sampler` defined around line 30. The MIDI-to-note-name conversion is inline in `handleMIDIMessage` (lines 420–436). We extract it into `_midiToToneName` and expose three public methods.

- [ ] **Step 1: Locate the sampler var and handleMIDIMessage**

  Read lines 30–60 of `midi_device.js` to confirm `var sampler` is module-level (not inside a function), then read lines 418–445 to see the inline pitch-name array.

- [ ] **Step 2: Add `_midiToToneName` private helper after the sampler declaration**

  Immediately after the `var sampler = new Tone.Sampler(...)` block (before `MidiDevice` constructor), insert:

  ```javascript
  var PITCH_NAMES = ["c","c#","d","eb","e","f","f#","g","g#","a","bb","b"];
  function _midiToToneName(midi) {
    return PITCH_NAMES[(midi + 12) % 12] + (Math.floor(midi / 12) - 1).toString();
  }
  ```

- [ ] **Step 3: Replace inline pitch conversion in `handleMIDIMessage`**

  In `handleMIDIMessage`, replace this block (lines ~420–436):

  ```javascript
  const pitchNames = [
    "c","c#","d","eb","e","f","f#","g","g#","a","bb","b",
  ];
  let toneJsNoteName =
    pitchNames[(msg[1] + 12) % 12] +
    (Math.floor(msg[1] / 12) - 1).toString();
  ```

  With:

  ```javascript
  var toneJsNoteName = _midiToToneName(msg[1]);
  ```

  (The `if (msg[0] == 144)` / `if (msg[0] == 128)` calls below remain unchanged.)

- [ ] **Step 4: Add three public methods to `MidiDevice.prototype`**

  After `MidiDevice.prototype.clear` (or at end of the `_.extend(MidiDevice.prototype, { ... })` block), add:

  ```javascript
  playNote: function (midi) {
    sampler.triggerAttack(_midiToToneName(midi));
  },
  releaseNote: function (midi) {
    sampler.triggerRelease(_midiToToneName(midi));
  },
  releaseAllNotes: function () {
    sampler.releaseAll();
  },
  ```

- [ ] **Step 5: Manual smoke test**

  Open browser console, find `window.app` or the midiDevice instance, call `midiDevice.playNote(60)` — should hear middle C. Call `midiDevice.releaseNote(60)`. Call `midiDevice.releaseAllNotes()`. No errors.

- [ ] **Step 6: Commit**

  ```bash
  git add lab/static/js/src/models/midi_device.js
  git commit -m "feat(midi): extract _midiToToneName helper and add playNote/releaseNote/releaseAllNotes"
  ```

---

## Task 2: Create ScorePlayer model

**Files:**
- Create: `lab/static/js/src/models/score_player.js`

`ScorePlayer` groups a flat timeline by onset window (identical logic to `ChoraleGrader.groupByOnset`), schedules all note events via `Tone.Transport`, and fires `tick(windowIndex)` and `stopped` events via MicroEvent.

**Tick formula:** `seconds = (ticks / 1024) * (60 / bpm)` — quarter note = 1024 ticks.

- [ ] **Step 1: Create the file**

  ```javascript
  /* global define: false */
  define(["microevent", "Tone"], function (MicroEvent, Tone) {
    "use strict";

    var ScorePlayer = function (midiDevice) {
      this._midiDevice = midiDevice;
      this._bpm = 100;
      this._playing = false;
    };

    MicroEvent.mixin(ScorePlayer);

    function groupByOnset(timeline) {
      var map = {};
      var order = [];
      for (var i = 0; i < timeline.length; i++) {
        var ev = timeline[i];
        var key = ev.onset;
        if (!map[key]) { map[key] = []; order.push(key); }
        map[key].push(ev);
      }
      order.sort(function (a, b) { return a - b; });
      return order.map(function (onset) { return { onset: onset, events: map[onset] }; });
    }

    function ticksToSeconds(ticks, bpm) {
      return (ticks / 1024) * (60 / bpm);
    }

    _.extend(ScorePlayer.prototype, {
      play: function (timeline, bpm) {
        if (!timeline || !timeline.length) return;
        var self = this;
        var device = this._midiDevice;
        bpm = bpm || this._bpm;
        this._bpm = bpm;

        Tone.start().then(function () {
          Tone.Transport.stop();
          Tone.Transport.cancel();
          Tone.Transport.position = 0;

          var windows = groupByOnset(timeline);
          if (!windows.length) return;

          // Schedule note attacks and releases
          windows.forEach(function (win) {
            var attackTime = ticksToSeconds(win.onset, bpm);
            win.events.forEach(function (ev) {
              var releaseTime = ticksToSeconds(win.onset + ev.duration, bpm);
              Tone.Transport.schedule(function () {
                device.playNote(ev.midi);
              }, attackTime);
              Tone.Transport.schedule(function () {
                device.releaseNote(ev.midi);
              }, releaseTime);
            });
          });

          // Schedule tick callbacks (one per window)
          windows.forEach(function (win, idx) {
            Tone.Transport.schedule(function () {
              self.trigger("tick", idx);
            }, ticksToSeconds(win.onset, bpm));
          });

          // Schedule stopped event after last note release
          var lastWin = windows[windows.length - 1];
          var lastRelease = Math.max.apply(null, lastWin.events.map(function (ev) {
            return ticksToSeconds(lastWin.onset + ev.duration, bpm);
          }));
          Tone.Transport.schedule(function () {
            self._playing = false;
            device.releaseAllNotes();
            self.trigger("stopped");
          }, lastRelease + 0.05);

          self._playing = true;
          Tone.Transport.start();
        });
      },

      stop: function () {
        Tone.Transport.stop();
        Tone.Transport.cancel();
        this._midiDevice.releaseAllNotes();
        this._playing = false;
        this.trigger("stopped");
      },

      isPlaying: function () {
        return this._playing;
      },

      setTempo: function (bpm) {
        this._bpm = bpm;
      },
    });

    return ScorePlayer;
  });
  ```

  **Note:** `lodash` is not listed in the define deps above — replace `_.extend` with a manual property copy or add `"lodash"` to deps. Use lodash for consistency with the rest of the codebase:

  ```javascript
  define(["lodash", "microevent", "Tone"], function (_, MicroEvent, Tone) {
  ```

- [ ] **Step 2: Manual smoke test in browser console**

  After adding the file, test via the AMD loader:
  ```javascript
  require(["app/models/score_player"], function(ScorePlayer) {
    // midiDevice is accessible via app globals
    var player = new ScorePlayer(window._midiDevice || app.midiDevice);
    console.log("ScorePlayer created:", player);
  });
  ```
  No errors expected.

- [ ] **Step 3: Commit**

  ```bash
  git add lab/static/js/src/models/score_player.js
  git commit -m "feat(playback): add ScorePlayer model with Tone.Transport scheduling"
  ```

---

## Task 3: Create playback_controls mixin

**Files:**
- Create: `lab/static/js/src/components/music/playback_controls.js`

Returns a single function. Idempotent: checks for `#playback-controls` before injecting. If found, updates references on the existing element's data store and returns. Reads/writes tempo in `sessionStorage` key `harmonylab.playback.tempo`.

- [ ] **Step 1: Create the file**

  ```javascript
  /* global define: false */
  define(["jquery"], function ($) {
    "use strict";

    var STORAGE_KEY = "harmonylab.playback.tempo";
    var DEFAULT_TEMPO = 100;

    function getSavedTempo() {
      try {
        var v = sessionStorage.getItem(STORAGE_KEY);
        if (v !== null) {
          var n = parseInt(v, 10);
          if (n >= 60 && n <= 160) return n;
        }
      } catch (e) {}
      return DEFAULT_TEMPO;
    }

    function saveTempo(bpm) {
      try { sessionStorage.setItem(STORAGE_KEY, String(bpm)); } catch (e) {}
    }

    /**
     * Inject playback controls into container (idempotent).
     *
     * @param {Element|jQuery} container  Toolbar element to inject into
     * @param {ScorePlayer}    scorePlayer
     * @param {Function}       getTimeline  Zero-arg closure → current timeline array
     */
    function renderPlaybackControls(container, scorePlayer, getTimeline) {
      var $container = $(container);
      var $existing = $container.find("#playback-controls");

      if ($existing.length) {
        // Already injected — update live references and return
        $existing.data("scorePlayer", scorePlayer);
        $existing.data("getTimeline", getTimeline);
        return;
      }

      var tempo = getSavedTempo();

      var html = [
        '<span id="playback-controls" style="display:inline-flex;align-items:center;gap:6px;margin-left:10px;">',
        '  <span style="border-left:1px solid #aaa;height:18px;margin-right:4px;"></span>',
        '  <button id="playback-play-btn" style="font-size:13px;padding:2px 8px;">&#9654; Play</button>',
        '  <input id="playback-tempo-slider" type="range" min="60" max="160" value="' + tempo + '" style="width:80px;">',
        '  <span id="playback-tempo-label" style="font-size:12px;min-width:50px;">' + tempo + ' bpm</span>',
        '</span>',
      ].join('');

      $container.append(html);

      var $ctrl = $container.find("#playback-controls");
      $ctrl.data("scorePlayer", scorePlayer);
      $ctrl.data("getTimeline", getTimeline);

      var $btn = $container.find("#playback-play-btn");
      var $slider = $container.find("#playback-tempo-slider");
      var $label = $container.find("#playback-tempo-label");

      function setButtonPlaying(playing) {
        $btn.html(playing ? "&#9632; Stop" : "&#9654; Play");
      }

      $btn.on("click", function () {
        var sp = $ctrl.data("scorePlayer");
        var gt = $ctrl.data("getTimeline");
        if (sp.isPlaying()) {
          sp.stop();
        } else {
          var tl = gt();
          if (!tl || !tl.length) return;
          var bpm = parseInt($slider.val(), 10);
          sp.play(tl, bpm);
          setButtonPlaying(true);
        }
      });

      $slider.on("input", function () {
        var bpm = parseInt($(this).val(), 10);
        $label.text(bpm + " bpm");
        saveTempo(bpm);
        var sp = $ctrl.data("scorePlayer");
        if (sp) sp.setTempo(bpm);
      });

      // Wire stopped event to reset button
      scorePlayer.bind("stopped", function () {
        setButtonPlaying(false);
      });
    }

    return renderPlaybackControls;
  });
  ```

- [ ] **Step 2: Verify idempotency logic**

  Read through: calling `renderPlaybackControls(container, sp, gt)` a second time with the same container must NOT create a second `#playback-controls` element. The `$existing.length` guard handles this. Confirm by inspection.

- [ ] **Step 3: Commit**

  ```bash
  git add lab/static/js/src/components/music/playback_controls.js
  git commit -m "feat(playback): add idempotent renderPlaybackControls toolbar mixin"
  ```

---

## Task 4: Integrate ScorePlayer into ExerciseSheetComponent

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js`

Changes:
1. Add `"app/models/score_player"` and `"app/components/music/playback_controls"` to the AMD `define` deps.
2. Instantiate `ScorePlayer` at end of `initComponent()`.
3. Call `renderPlaybackControls` from `render()` (idempotent).
4. Add `_drawPlaybackHighlight()` and `_clearPlaybackHighlight()`.
5. Wire `tick` and `stopped` events to highlight methods.
6. Alias `_identWindowLayout` as `_windowPositionCache` (they are the same object — just use `_identWindowLayout` directly in highlight methods).

- [ ] **Step 1: Add deps to `define([...], function(...)`**

  Current first two lines:
  ```javascript
  /* global define: false */
  define([
    "jquery",
    ...
    "./score_timeline",
    "app/components/input/label_input",
  ], function (
    $,
    ...
    ScoreTimeline,
    LabelInput
  ) {
  ```

  Add at the end of the dep arrays:
  ```javascript
  // In the string array:
  "app/models/score_player",
  "app/components/music/playback_controls",

  // In the function params:
  ScorePlayer,
  renderPlaybackControls,
  ```

- [ ] **Step 2: Instantiate ScorePlayer in `initComponent`**

  At the end of `initComponent` (after the existing chorale/identification init blocks), add:

  ```javascript
  // Playback
  var self = this;
  this.scorePlayer = new ScorePlayer(this.exerciseContext.midiDevice || window.midiDevice);
  this.scorePlayer.bind("tick", function (windowIndex) {
    self._playbackWindowIndex = windowIndex;
    self._drawPlaybackHighlight();
  });
  this.scorePlayer.bind("stopped", function () {
    self._playbackWindowIndex = null;
    self._clearPlaybackHighlight();
  });
  this._playbackWindowIndex = null;
  this._playbackHighlightRect = null;
  ```

  **Note:** `midiDevice` must be accessible. Check how it's reached in `exercise_sheet.js` — it flows through `exerciseContext`. Search for `midiDevice` usage in the file. If not present, the global `window.midiDevice` is the fallback (it is set in app bootstrap). Prefer `this.exerciseContext.midiDevice` if available, else `window.midiDevice`.

- [ ] **Step 3: Call `renderPlaybackControls` from `render()`**

  In the `render` method, after the canvas/VexFlow rendering section (but before returning `this`), locate a suitable toolbar container. The exercise toolbar is typically `.js-sheet-toolbar` or the parent component's toolbar. Inspect `exercise_sheet.js`'s `render` method for where `renderExerciseInfo` or exercise nav buttons are injected to find the container selector. Add:

  ```javascript
  // Playback controls (idempotent)
  var self = this;
  var definition = this.exerciseContext.getDefinition();
  if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
    var $toolbar = $(".js-sheet-toolbar");
    if ($toolbar.length) {
      renderPlaybackControls($toolbar, this.scorePlayer, function () {
        var score = definition.getScore ? definition.getScore() : null;
        if (!score) return null;
        var opts = {};
        if (self._chorale) {
          opts.startMeasure = self._chorale.startMeasure || 0;
          opts.maxMeasures = self._chorale.maxMeasures || 4;
        }
        return ScoreTimeline.buildTimeline(score, opts);
      });
    }
  }
  ```

  **Note:** `getScore()` retrieves the CIR score from the definition. Check if this method exists by searching `exercise_definition.js` for `getScore`. If the method is named differently, adjust accordingly.

- [ ] **Step 4: Add `_drawPlaybackHighlight` and `_clearPlaybackHighlight` methods**

  Add to `ExerciseSheetComponent.prototype` (in the `_.extend(ExerciseSheetComponent.prototype, { ... })` block):

  ```javascript
  _drawPlaybackHighlight: function () {
    var idx = this._playbackWindowIndex;
    if (idx === null || idx === undefined) return;
    var slot = this._identWindowLayout && this._identWindowLayout[idx];
    if (!slot) return;

    var canvas = this.el[0];
    var ctx = canvas.getContext("2d");

    // Clear previous highlight
    this._clearPlaybackHighlight();

    var x = slot.x;
    var y = 0;             // top of canvas
    var w = 30;
    var h = slot.y;        // slot.y = bassStave.getBottomY() + 18

    ctx.save();
    ctx.fillStyle = "rgba(79, 172, 254, 0.15)";
    ctx.strokeStyle = "rgba(79, 172, 254, 0.35)";
    ctx.lineWidth = 1;
    ctx.fillRect(x - w / 2, y, w, h);
    ctx.strokeRect(x - w / 2, y, w, h);
    ctx.restore();

    this._playbackHighlightRect = { x: x - w / 2, y: y, w: w, h: h };
  },

  _clearPlaybackHighlight: function () {
    if (!this._playbackHighlightRect) return;
    var r = this._playbackHighlightRect;
    var canvas = this.el[0];
    var ctx = canvas.getContext("2d");
    // Expand by 1px on each side to fully erase the stroke border
    ctx.clearRect(r.x - 1, r.y - 1, r.w + 2, r.h + 2);
    this._playbackHighlightRect = null;
  },
  ```

- [ ] **Step 5: Verify `_identWindowLayout` is already populated**

  The `onWindowPosition` callback in `render()` (around line 1125) already writes into `self._identWindowLayout`. Confirm `_identWindowLayout` is initialized to `{}` before `VexFlowAdapter.render(...)` is called (it is, in the chorale render block). No additional init needed.

- [ ] **Step 6: Test manually in browser**

  1. Open exercise view with a chorale exercise.
  2. Verify Play button appears in toolbar.
  3. Click Play — should hear piano audio and see blue highlight moving across columns.
  4. Click Stop — audio stops, highlight clears.
  5. Playback continues during MIDI input — grade normally.

- [ ] **Step 7: Commit**

  ```bash
  git add lab/static/js/src/components/music/exercise_sheet.js
  git commit -m "feat(exercise-sheet): add ScorePlayer init, playback controls, and highlight drawing"
  ```

---

## Task 5: Integrate ScorePlayer into PlaySheetComponent

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js`

Changes:
1. Add `"app/models/score_player"`, `"app/components/music/playback_controls"`, `"app/components/music/score_timeline"` to deps.
2. Add `this._cachedTimeline = null` to constructor.
3. Instantiate `ScorePlayer` in `initComponent()`.
4. In `renderWithState()`: call `scorePlayer.stop()` at top, build and cache timeline, add `onWindowPosition` callback, call `renderPlaybackControls`.
5. Add `_windowPositionCache`, `_drawPlaybackHighlight`, `_clearPlaybackHighlight` analogous to exercise sheet.
6. Play button hidden (not disabled) when not in corpus mode.

- [ ] **Step 1: Add deps**

  Current define array starts with `"jquery", "lodash", "vexflow", ...`. Add:
  ```javascript
  // String array:
  "app/components/music/score_timeline",
  "app/models/score_player",
  "app/components/music/playback_controls",

  // Function params:
  ScoreTimeline,
  ScorePlayer,
  renderPlaybackControls,
  ```

- [ ] **Step 2: Add `_cachedTimeline` and `_windowPositionCache` to constructor**

  In the `PlaySheetComponent` constructor function body, after the existing field initializations (`_corpusFile`, `_corpusPayload`, `_vfState`), add:

  ```javascript
  this._cachedTimeline = null;
  this._windowPositionCache = {};
  this._playbackWindowIndex = null;
  this._playbackHighlightRect = null;
  ```

- [ ] **Step 3: Instantiate ScorePlayer in `initComponent`**

  At end of `initComponent`, add:

  ```javascript
  var self = this;
  this.scorePlayer = new ScorePlayer(window.midiDevice);
  this.scorePlayer.bind("tick", function (windowIndex) {
    self._playbackWindowIndex = windowIndex;
    self._drawPlaybackHighlight();
  });
  this.scorePlayer.bind("stopped", function () {
    self._playbackWindowIndex = null;
    self._clearPlaybackHighlight();
  });
  ```

- [ ] **Step 4: Modify `renderWithState` to stop player, cache timeline, pass `onWindowPosition`**

  Find `renderWithState` (defined inside `render()`, starting around line 175). At the very top of the `renderWithState` function body (before the `try {` block), add:

  ```javascript
  self.scorePlayer.stop();
  self._cachedTimeline = null;
  self._windowPositionCache = {};
  ```

  After the key-signature sync block and before `VexflowAdapter.render(...)`, build the timeline:

  ```javascript
  // Cache timeline for playback
  self._cachedTimeline = ScoreTimeline.buildTimeline(payload.score);
  ```

  In the `VexflowAdapter.render(...)` call options object (currently `{ width, height, maxMeasures: 4, selectVoices, octaveShift }`), add the `onWindowPosition` callback:

  ```javascript
  onWindowPosition: function (slot) {
    if (slot && typeof slot.windowIndex === "number") {
      self._windowPositionCache[slot.windowIndex] = slot;
    }
  },
  ```

- [ ] **Step 5: Call `renderPlaybackControls` in `render()` (corpus mode only)**

  In `play_sheet.js render()`, after the `if (corpusFile) { ... }` block resolves (or after `renderWithState` is called), add the controls call. Place it after `renderWithState` is invoked (both in the cache-hit branch and the AJAX success callback):

  Inside the `renderWithState` function itself, at the end (after VexflowAdapter.render succeeds), add:

  ```javascript
  // Playback controls (corpus mode only, idempotent)
  var $toolbar = $(".js-sheet-toolbar");
  if ($toolbar.length) {
    renderPlaybackControls($toolbar, self.scorePlayer, function () {
      return self._cachedTimeline;
    });
  }
  ```

  For the non-corpus path (`useNewAdapter` but no `corpusFile`), the Play button must be hidden. After calling `renderPlaybackControls` above, this naturally doesn't happen in non-corpus path (since `renderPlaybackControls` is only called inside the `corpusFile` branch). Verify the `#playback-controls` element is NOT present when navigating away from corpus mode (since `render()` calls `this.clear()` which wipes the canvas but NOT the toolbar — check if toolbar is wiped by `clear()`). If toolbar persists, add explicit hide logic:

  ```javascript
  // In the non-corpus branch (else branch after if (corpusFile)):
  $("#playback-controls").hide();
  ```

  And show it in the corpus branch after `renderPlaybackControls`:
  ```javascript
  $("#playback-controls").show();
  ```

- [ ] **Step 6: Add highlight methods to PlaySheetComponent.prototype**

  Add to `_.extend(PlaySheetComponent.prototype, { ... })`:

  ```javascript
  _drawPlaybackHighlight: function () {
    var idx = this._playbackWindowIndex;
    if (idx === null || idx === undefined) return;
    var slot = this._windowPositionCache[idx];
    if (!slot) return;

    var canvas = this.el[0];
    var ctx = canvas.getContext("2d");

    this._clearPlaybackHighlight();

    var x = slot.x;
    var y = 0;
    var w = 30;
    var h = slot.y;  // bassStave.getBottomY() + 18

    ctx.save();
    ctx.fillStyle = "rgba(79, 172, 254, 0.15)";
    ctx.strokeStyle = "rgba(79, 172, 254, 0.35)";
    ctx.lineWidth = 1;
    ctx.fillRect(x - w / 2, y, w, h);
    ctx.strokeRect(x - w / 2, y, w, h);
    ctx.restore();

    this._playbackHighlightRect = { x: x - w / 2, y: y, w: w, h: h };
  },

  _clearPlaybackHighlight: function () {
    if (!this._playbackHighlightRect) return;
    var r = this._playbackHighlightRect;
    var canvas = this.el[0];
    var ctx = canvas.getContext("2d");
    ctx.clearRect(r.x - 1, r.y - 1, r.w + 2, r.h + 2);
    this._playbackHighlightRect = null;
  },
  ```

- [ ] **Step 7: Test manually**

  1. Navigate to play view with `?newvf&loadCorpus=bwv1.6.json`.
  2. Play button visible in toolbar.
  3. Click Play — audio plays, highlight moves across columns.
  4. Navigate to play view WITHOUT `loadCorpus` — Play button hidden.
  5. Change key signature during playback — highlight clears on re-render, resumes on next tick.

- [ ] **Step 8: Commit**

  ```bash
  git add lab/static/js/src/components/music/play_sheet.js
  git commit -m "feat(play-sheet): add ScorePlayer init, timeline caching, onWindowPosition, and playback controls"
  ```

---

## Task 6: Stop playback on exercise advance in music.js

**Files:**
- Modify: `lab/static/js/src/components/music.js`

`renderPristine` loads new exercises. Playback must stop before the new exercise renders.

- [ ] **Step 1: Locate `renderPristine`**

  `renderPristine` starts at line 177. It begins with:
  ```javascript
  renderPristine: function (exerciseAction = "reload") {
    var sheetComponent = this.getComponent("sheet");
    if (!sheetComponent.hasOwnProperty("exerciseContext")) {
      /* play view */
      sheetComponent.chords.clear();
    } else {
  ```

- [ ] **Step 2: Add `scorePlayer.stop()` at top of `renderPristine`**

  Insert immediately after `var sheetComponent = this.getComponent("sheet");`:

  ```javascript
  // Stop any in-progress playback before loading new exercise
  if (sheetComponent.scorePlayer && sheetComponent.scorePlayer.isPlaying()) {
    sheetComponent.scorePlayer.stop();
  }
  ```

- [ ] **Step 3: Verify no double-stop**

  `stop()` is idempotent (it calls Transport.stop/cancel regardless of state) so calling it when not playing is safe. The `isPlaying()` guard is a belt-and-suspenders check, not strictly required.

- [ ] **Step 4: Commit**

  ```bash
  git add lab/static/js/src/components/music.js
  git commit -m "feat(music): stop scorePlayer before exercise advance in renderPristine"
  ```

---

## Task 7: End-to-end verification

- [ ] **Step 1: Exercise sheet — full playback flow**

  1. Load any chorale exercise (e.g., BWV 1.6 measures 1–4).
  2. Play button appears in toolbar.
  3. Click Play at default 100 BPM — piano audio plays, blue column highlight advances.
  4. Tempo slider to 60 BPM — drag slider, label updates. Stop and re-play — slower.
  5. Click Stop mid-playback — audio stops, highlight clears.
  6. Playback ends naturally — button reverts to "▶ Play".
  7. Press MIDI key during playback — notes still grade normally.
  8. Advance to next exercise — audio stops.
  9. Key-signature change — highlight clears, playback resumes correctly on next play.

- [ ] **Step 2: Play sheet — corpus mode**

  1. Load `?newvf&loadCorpus=bwv1.6.json`.
  2. Play button visible, audio plays, highlight works.
  3. Change voice filter (URL param `?voices=...`) — page re-renders, stop fires, timeline re-caches, highlight resets.
  4. Navigate to play view WITHOUT `loadCorpus` — no Play button visible.

- [ ] **Step 3: AudioContext resume (first-click test)**

  1. Hard-reload the page (Cmd+Shift+R).
  2. Immediately click Play without touching any other UI.
  3. Audio should play (not silently fail) — verifies `Tone.start().then(...)` wrapping.

- [ ] **Step 4: Repeated play clicks**

  1. Click Play.
  2. Immediately click Play again (before audio ends) — playback restarts from beginning (no double-scheduling).
  3. Verifies `Tone.Transport.stop()` + `cancel()` + `position = 0` reset before scheduling.

- [ ] **Step 5: Final commit / PR**

  ```bash
  git log --oneline -6
  # Should show 6 commits from this work
  ```

---

## Spec Coverage Self-Review

| Spec Requirement | Covered by Task |
|-----------------|----------------|
| Play/Stop toggle button in toolbar | Task 3 (controls), Tasks 4+5 (integration) |
| Tempo slider 60–160 BPM, default 100 | Task 3 |
| Tempo persisted in sessionStorage | Task 3 |
| Column highlight — blue, 30px, canvas overlay | Tasks 4+5 |
| `_drawPlaybackHighlight` reads `_windowPositionCache` | Tasks 4+5 |
| Highlight clears on stopped | Tasks 4+5 |
| `Tone.start().then(...)` AudioContext race fix | Task 2 |
| Transport reset before each play | Task 2 |
| `onWindowPosition` callback in play sheet | Task 5 |
| Exercise sheet uses existing `_identWindowLayout` | Task 4 |
| `_cachedTimeline` built in `renderWithState` | Task 5 |
| `scorePlayer.stop()` on corpus reload | Task 5 |
| `scorePlayer.stop()` on exercise advance | Task 6 |
| Play button hidden (not disabled) in non-corpus play view | Task 5 |
| `playNote/releaseNote/releaseAllNotes` on MidiDevice | Task 1 |
| `_midiToToneName` extracted | Task 1 |
| No vexflow_adapter changes needed | — (confirmed: adapter already has onWindowPosition) |
| `renderPlaybackControls` idempotent | Task 3 |
| getTimeline is a closure called at click-time | Tasks 3+4+5 |
