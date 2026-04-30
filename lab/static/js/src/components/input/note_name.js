define([
  "jquery",
  "lodash",
  "app/components/events",
  "app/components/component",
], function ($, _, EVENTS, Component) {

  // Key code → diatonic step name (letters a–g only)
  var STEP_FOR_CODE = {
    65: "a", 66: "b", 67: "c", 68: "d", 69: "e", 70: "f", 71: "g"
  };

  // Key code → octave number (digit keys 1–8)
  var OCTAVE_FOR_CODE = {
    49: 1, 50: 2, 51: 3, 52: 4, 53: 5, 54: 6, 55: 7, 56: 8
  };

  // Semitone offset from C for each diatonic step
  var STEP_SEMITONE = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };

  var KEY_UP   = 38;
  var KEY_DOWN = 40;

  /**
   * NoteNameInputComponent — an alternative keyboard-input mode.
   *
   * When enabled, physical keys a–g set the pitch name, digit keys 1–8 set
   * the octave, and UP/DOWN arrows toggle a sharp/flat accidental.  When
   * both a step AND an octave are set (either in sequence or simultaneously)
   * a MIDI noteOn/noteOff pair is broadcast on EVENTS.BROADCAST.NOTE — the
   * same channel used by physical MIDI and the piano-layout QWERTY mode.
   *
   * The component uses a capture-phase document listener so that, while
   * enabled, the keys it handles are intercepted before they reach the
   * piano-layout KeyboardShortcutsComponent.  Non-note shortcuts (SPACE,
   * ENTER, ESC, PAGEUP/DOWN …) are not intercepted and continue to work.
   *
   * Mode switching is controlled by broadcasting EVENTS.BROADCAST.INPUT_MODE
   * with value "notename" or "qwerty".  The same event is broadcast by the
   * toggle buttons rendered inside this component's el.
   *
   * @constructor
   */
  var NoteNameInputComponent = function (settings) {
    this.settings = settings || {};

    this.enabled       = false;
    this.pendingStep   = null;  // null or 'a'–'g'
    this.pendingOctave = 4;     // sensible default; survives between notes
    this.pendingAlter  = 0;     // -1 = flat, 0 = natural, +1 = sharp
    this._heldNotes    = {};    // keyCode → midi number currently sounding
  };

  NoteNameInputComponent.prototype = new Component();

  _.extend(NoteNameInputComponent.prototype, {

    initComponent: function () {
      _.bindAll(this, ["_onKeyCapture", "_onKeyUpCapture", "_onModeChange"]);
      this.el = this._buildEl();
      this.subscribe(EVENTS.BROADCAST.INPUT_MODE, this._onModeChange);

      if (this.settings.defaultMode) {
        this.broadcast(EVENTS.BROADCAST.INPUT_MODE, this.settings.defaultMode);
      }
    },

    // ------------------------------------------------------------------
    // Public API

    enable: function () {
      if (this.enabled) { return; }
      this.enabled = true;
      document.addEventListener("keydown", this._onKeyCapture, true);
      document.addEventListener("keyup",   this._onKeyUpCapture, true);
      this._syncPanels();
    },

    disable: function () {
      if (!this.enabled) { return; }
      this.enabled = false;
      document.removeEventListener("keydown", this._onKeyCapture, true);
      document.removeEventListener("keyup",   this._onKeyUpCapture, true);
      // Release any notes still sounding
      var self = this;
      Object.keys(this._heldNotes).forEach(function (code) {
        self.broadcast(EVENTS.BROADCAST.NOTE, "off", self._heldNotes[code]);
      });
      this._heldNotes = {};
      this._syncPanels();
    },

    // ------------------------------------------------------------------
    // Event bus handler

    _onModeChange: function (mode) {
      if (mode === "notename") {
        this.enable();
      } else {
        this.disable();
      }
      this._syncButtons(mode);
    },

    // ------------------------------------------------------------------
    // Capture-phase key handler

    _onKeyCapture: function (e) {
      if (!this.enabled) { return; }
      if (e.altKey || e.ctrlKey || e.metaKey) { return; }

      var target = e.target;
      if (target && (
            target.nodeName === "INPUT"    ||
            target.nodeName === "TEXTAREA" ||
            target.nodeName === "SELECT")) {
        return;
      }

      var code = e.which || e.keyCode;

      // --- Pitch letter (a–g) -----------------------------------------
      if (STEP_FOR_CODE.hasOwnProperty(code)) {
        e.preventDefault();
        e.stopImmediatePropagation();
        // Skip auto-repeat if this key is already holding a note
        if (this._heldNotes[code] !== undefined) { return; }
        this.pendingStep = STEP_FOR_CODE[code];
        // do NOT reset pendingAlter here — accidental set before the letter must survive into _fireNote
        if (this.pendingOctave !== null) {
          this._fireNote(code);
        } else {
          this._syncStatus();
        }
        return;
      }

      // --- Octave digit (1–8) -----------------------------------------
      if (OCTAVE_FOR_CODE.hasOwnProperty(code)) {
        e.preventDefault();
        e.stopImmediatePropagation();
        // Skip auto-repeat if this key is already holding a note
        if (this._heldNotes[code] !== undefined) { return; }
        this.pendingOctave = OCTAVE_FOR_CODE[code];
        if (this.pendingStep !== null) {
          this._fireNote(code);
        } else {
          this._syncStatus();
        }
        return;
      }

      // --- UP arrow: toggle sharp / back to natural -------------------
      if (code === KEY_UP) {
        e.preventDefault();
        e.stopImmediatePropagation();
        this.pendingAlter = (this.pendingAlter === 0) ? 1 : 0;
        this._syncStatus();
        return;
      }

      // --- DOWN arrow: toggle flat / back to natural ------------------
      if (code === KEY_DOWN) {
        e.preventDefault();
        e.stopImmediatePropagation();
        this.pendingAlter = (this.pendingAlter === 0) ? -1 : 0;
        this._syncStatus();
        return;
      }
    },

    // ------------------------------------------------------------------
    // Note firing

    _fireNote: function (triggerCode) {
      var step   = this.pendingStep;
      var octave = this.pendingOctave;
      var alter  = this.pendingAlter;
      var midi   = (octave + 1) * 12 + STEP_SEMITONE[step] + alter;

      // MIDI piano range A0=21 … C8=108
      if (midi < 21 || midi > 108) {
        this.pendingStep  = null;
        this.pendingAlter = 0;
        this._syncStatus();
        return;
      }

      // Track which key is holding this note; release on keyup
      this._heldNotes[triggerCode] = midi;
      this.broadcast(EVENTS.BROADCAST.NOTE, "on", midi);

      // Keep octave (convenience — next letter re-uses last octave).
      // Reset step and accidental.
      this.pendingStep  = null;
      this.pendingAlter = 0;
      this._syncStatus();
    },

    // ------------------------------------------------------------------
    // Keyup — release the note that was triggered by this key

    _onKeyUpCapture: function (e) {
      if (!this.enabled) { return; }
      var code = e.which || e.keyCode;
      if (this._heldNotes[code] !== undefined) {
        this.broadcast(EVENTS.BROADCAST.NOTE, "off", this._heldNotes[code]);
        delete this._heldNotes[code];
      }
    },

    // ------------------------------------------------------------------
    // UI sync helpers

    _alterSymbol: function (alter) {
      if (alter ===  1) { return "\u266f"; }   // ♯
      if (alter === -1) { return "\u266d"; }   // ♭
      return "";
    },

    _syncStatus: function () {
      if (!this._statusEl) { return; }
      var step   = this.pendingStep !== null
                   ? this.pendingStep.toUpperCase()
                   : "\u00b7";   // ·
      var octave = this.pendingOctave !== null
                   ? String(this.pendingOctave)
                   : "\u00b7";
      var alter  = this._alterSymbol(this.pendingAlter);
      this._statusEl.text(step + alter + octave);
    },

    _syncButtons: function (mode) {
      if (!this._btnQwerty || !this._btnNoteName) { return; }
      if (mode === "notename") {
        this._btnNoteName
            .addClass("input-mode-btn-active")
            .removeClass("input-mode-btn-inactive");
        this._btnQwerty
            .addClass("input-mode-btn-inactive")
            .removeClass("input-mode-btn-active");
      } else {
        this._btnQwerty
            .addClass("input-mode-btn-active")
            .removeClass("input-mode-btn-inactive");
        this._btnNoteName
            .addClass("input-mode-btn-inactive")
            .removeClass("input-mode-btn-active");
      }
    },

    _syncPanels: function () {
      if (!this._qwertyPanel || !this._noteNamePanel) { return; }
      if (this.enabled) {
        this._noteNamePanel.show();
        this._qwertyPanel.hide();
      } else {
        this._qwertyPanel.show();
        this._noteNamePanel.hide();
        this._syncStatus();   // reset display for next time note-name activates
      }
    },

    // ------------------------------------------------------------------
    // DOM construction

    _buildEl: function () {
      var self = this;

      // ---- Mode toggle buttons ----------------------------------------
      var btnQwerty   = $(
        '<button class="input-mode-btn input-mode-btn-active"' +
        ' title="Use the computer keyboard like a piano (QWERTY layout)">' +
        'QWERTY</button>'
      );
      var btnNoteName = $(
        '<button class="input-mode-btn input-mode-btn-inactive"' +
        ' title="Type note names: letter (a\u2013g) sets pitch, digit (1\u20138) sets octave">' +
        'Note&nbsp;Name</button>'
      );

      btnQwerty.on("click", function (e) {
        e.preventDefault();
        self.broadcast(EVENTS.BROADCAST.INPUT_MODE, "qwerty");
      });
      btnNoteName.on("click", function (e) {
        e.preventDefault();
        self.broadcast(EVENTS.BROADCAST.INPUT_MODE, "notename");
      });

      this._btnQwerty   = btnQwerty;
      this._btnNoteName = btnNoteName;

      var modeToggle = $('<div class="input-mode-toggle"></div>')
        .append(btnQwerty)
        .append(btnNoteName);

      // ---- QWERTY key guide (visible in QWERTY mode) ------------------
      var qwertyPanel  = $('<div class="qwerty-help-panel"></div>');
      var helpToggle   = $('<button class="qwerty-help-toggle">\u25b8 Key guide</button>');
      var helpContent  = $('<div class="qwerty-help-content"></div>').hide();

      // Two rows of the piano layout
      var topKeys = [
        ["`","G2","w"],  ["1","G\u266f2","b"], ["q","A2","w"],  ["2","B\u266d2","b"],
        ["w","B2","w"],  ["e","C3","w"],        ["4","C\u266f3","b"], ["r","D3","w"],
        ["5","E\u266d3","b"], ["t","E3","w"],   ["y","F3","w"],  ["7","F\u266f3","b"],
        ["u","G3","w"],  ["8","A\u266d3","b"],  ["i","A3","w"],  ["9","B\u266d3","b"],
        ["o","B3","w"],  ["p","C4","w"],        ["-","D\u266d4","b"], ["[","D4","w"],
        ["=","E\u266d4","b"], ["]","E4","w"]
      ];
      var botKeys = [
        ["z","F4","w"], ["s","F\u266f4","b"], ["x","G4","w"], ["d","A\u266d4","b"],
        ["c","A4","w"], ["f","B\u266d4","b"], ["v","B4","w"], ["b","C5","w"],
        ["h","C\u266f5","b"], ["n","D5","w"],  ["j","E\u266d5","b"], ["m","E5","w"],
        [",","F5","w"]
      ];

      function buildKeyRow(keys) {
        var row = $('<div class="qwerty-key-row"></div>');
        _.each(keys, function (k) {
          row.append(
            $('<span class="qk ' + (k[2] === "b" ? "qk-black" : "qk-white") + '">' +
              '<kbd>' + k[0] + '</kbd>' +
              '<span class="qk-note">' + k[1] + '</span>' +
              '</span>')
          );
        });
        return row;
      }

      var caption = $(
        '<div class="qwerty-help-caption">' +
        'ESC: on/off &nbsp;&middot;&nbsp; SPC/\u21b5: bank &nbsp;&middot;&nbsp;' +
        ' &apos;: sustain &nbsp;&middot;&nbsp; l: release' +
        '</div>'
      );

      helpContent
        .append(buildKeyRow(topKeys))
        .append(buildKeyRow(botKeys))
        .append(caption);

      helpToggle.on("click", function () {
        helpContent.toggle();
        helpToggle.text(
          helpContent.is(":visible") ? "\u25be Key guide" : "\u25b8 Key guide"
        );
      });

      qwertyPanel.append(helpToggle).append(helpContent);
      this._qwertyPanel = qwertyPanel;

      // ---- Note-name status panel (visible in note-name mode) ---------
      var noteNamePanel  = $('<div class="notename-panel"></div>');
      var statusEl       = $('<span class="notename-pending">\u00b74</span>');
      var instructions   = $(
        '<span class="notename-instr">' +
        'a\u2013g\u2009 pitch &nbsp; 1\u20138\u2009 octave &nbsp; \u2191 \u266f &nbsp; \u2193 \u266d' +
        '</span>'
      );

      noteNamePanel
        .append($('<span class="notename-label">Next: </span>'))
        .append(statusEl)
        .append(instructions)
        .hide();

      this._statusEl      = statusEl;
      this._noteNamePanel = noteNamePanel;

      // ---- Assemble ---------------------------------------------------
      return $('<div class="keyboard-input-mode"></div>')
        .append(modeToggle)
        .append(qwertyPanel)
        .append(noteNamePanel);
    },

    render: function () { return this; },

    renderTo: function (selector) {
      $(selector).append(this.el);
      return this;
    },

    destroy: function () {
      this.disable();
    },

  });

  return NoteNameInputComponent;
});
