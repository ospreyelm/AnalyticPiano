define([
  "jquery",
  "lodash",
  "app/components/events",
  "app/components/component",
  "app/components/input/click_note_logic",
], function ($, _, EVENTS, Component, ClickNoteLogic) {
  var ClickNoteInputComponent = function (settings) {
    this.settings = settings || {};
    this.sheet = this.settings.sheet || null;
    this.exerciseContext = this.settings.exerciseContext || null;
    this.keySignature = this.settings.keySignature || null;

    this.enabled = false;
    this.palette = "diatonic";
    this._pending = [];
    this._lastGhostKey = null;
    this._activeColumn = null;
  };

  ClickNoteInputComponent.prototype = new Component();

  _.extend(ClickNoteInputComponent.prototype, {
    initComponent: function () {
      _.bindAll(this, [
        "_onCanvasClick",
        "_onCanvasMove",
        "_onCanvasLeave",
        "_onSourceModeChange",
        "_onNextChord",
        "_commit",
      ]);
      this.el = this._buildEl();
      if (this.sheet && typeof this.sheet.setClickNoteComponent === "function") {
        this.sheet.setClickNoteComponent(this);
      }
      this.subscribe(EVENTS.BROADCAST.INPUT_SOURCE_MODE, this._onSourceModeChange);
      this.subscribe(EVENTS.BROADCAST.NEXT_CHORD, this._onNextChord);
      this.subscribe(EVENTS.BROADCAST.BANK_NOTES, this._commit);
    },

    getPending: function () {
      return this._pending.slice();
    },

    getPendingMidi: function () {
      return this._pending.map(function (n) { return n.midi; });
    },

    getPendingSpellings: function () {
      return this._pending.map(function (n) {
        var acc = n.alter === 1 ? "#" : n.alter === -1 ? "b" : "";
        return n.step + acc + "/" + n.octave;
      });
    },

    getActiveColumn: function () {
      return this._activeColumn || null;
    },

    _onSourceModeChange: function (mode) {
      if (mode === "click") {
        this.enable();
      } else {
        this.disable();
      }
      this._syncPalettePanel();
    },

    enable: function () {
      if (this.enabled) return;
      this.enabled = true;
      var canvas = this._canvas();
      if (canvas) {
        canvas.addEventListener("click", this._onCanvasClick);
        canvas.addEventListener("mousemove", this._onCanvasMove);
        canvas.addEventListener("mouseleave", this._onCanvasLeave);
      }
    },

    disable: function () {
      if (!this.enabled) return;
      this.enabled = false;
      var canvas = this._canvas();
      if (canvas) {
        canvas.removeEventListener("click", this._onCanvasClick);
        canvas.removeEventListener("mousemove", this._onCanvasMove);
        canvas.removeEventListener("mouseleave", this._onCanvasLeave);
      }
      this._clearPending();
    },

    _clearPending: function () {
      this._pending = [];
      this._activeColumn = null;
      if (this.sheet && typeof this.sheet.clearGhostNote === "function") this.sheet.clearGhostNote();
      if (this.sheet && typeof this.sheet.render === "function") this.sheet.render();
    },

    _onNextChord: function () {
      this._pending = [];
      this._activeColumn = null;
    },

    _canvas: function () {
      if (this.sheet && this.sheet.el) {
        var c = this.sheet.el[0] || null;
        if (!c && this.sheet.el.querySelector) c = this.sheet.el.querySelector("canvas");
        if (c) return c;
      }
      return document.querySelector("#staff canvas, canvas#staff, #staff-canvas");
    },

    _layout: function () {
      return this.sheet && this.sheet.getStaffLayout ? this.sheet.getStaffLayout() : null;
    },

    _key: function () {
      if (this.keySignature && this.keySignature.getKey) return this.keySignature.getKey();
      if (this.exerciseContext && this.exerciseContext.getDefinition) {
        var def = this.exerciseContext.getDefinition();
        if (def && def.getKeyName) return def.getKeyName();
      }
      return "C";
    },

    _activeTargetOnset: function () {
      var ctx = this.exerciseContext;
      if (!ctx || !ctx.getDefinition) return null;
      var def = ctx.getDefinition();
      var targets = def && def.getHarmonizationTargets ? def.getHarmonizationTargets() : [];
      var target = targets[ctx._harmonizationPointer || 0];
      return target && typeof target.offset === "number" ? Math.round(target.offset * 1024) : null;
    },

    _eventPoint: function (e) {
      var canvas = this._canvas();
      var rect = canvas.getBoundingClientRect();
      return {
        px: e.clientX - rect.left + canvas.scrollLeft,
        py: e.clientY - rect.top,
      };
    },

    _resolve: function (e) {
      var layout = this._layout();
      if (!layout) return null;
      return ClickNoteLogic.resolveClick(this._eventPoint(e), layout, {
        key: this._key(),
        palette: this.palette,
        activeColumnOnset: this._activeTargetOnset(),
      });
    },

    _onCanvasMove: function (e) {
      if (!this.enabled) return;
      var resolved = this._resolve(e);
      var key = resolved ? (resolved.midi + ":" + resolved.column.onset) : null;
      if (key === this._lastGhostKey) return;
      this._lastGhostKey = key;
      if (!resolved) {
        if (this.sheet) this.sheet.clearGhostNote();
        return;
      }
      this._activeColumn = resolved.column;
      if (this.sheet) this.sheet.drawGhostNote(resolved);
    },

    _onCanvasLeave: function () {
      this._lastGhostKey = null;
      if (this.sheet) this.sheet.clearGhostNote();
    },

    _onCanvasClick: function (e) {
      if (!this.enabled) return;
      var resolved = this._resolve(e);
      if (!resolved) return;
      this._activeColumn = resolved.column;

      var existing = -1;
      for (var i = 0; i < this._pending.length; i++) {
        if (this._pending[i].midi === resolved.midi) {
          existing = i;
          break;
        }
      }
      if (existing !== -1) {
        this._pending.splice(existing, 1);
        if (this.sheet) this.sheet.render();
        return;
      }

      var cap = this._capRemaining();
      if (this._pending.length >= cap) {
        this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
          type: "info",
          title: "Maximum notes",
          description: "This chord allows up to " + cap + " note(s).",
        });
        return;
      }

      this._pending.push({
        midi: resolved.midi,
        step: resolved.step,
        alter: resolved.alter,
        octave: resolved.octave,
      });
      if (this.sheet) this.sheet.render();
    },

    _capRemaining: function () {
      var policy = null;
      var suppliedCount = 0;
      var target = this._activeTarget();
      if (target) {
        policy = target.voiceCountPolicy || null;
        var locked = target.lockedVoices || {};
        suppliedCount = Object.keys(locked).filter(function (k) {
          return typeof locked[k].midi === "number";
        }).length;
      }
      return ClickNoteLogic.capRemaining(policy, suppliedCount);
    },

    _activeTarget: function () {
      var ctx = this.exerciseContext;
      if (!ctx || !ctx.getDefinition) return null;
      var def = ctx.getDefinition();
      var targets = def && def.getHarmonizationTargets ? def.getHarmonizationTargets() : [];
      return targets[ctx._harmonizationPointer || 0] || null;
    },

    _commit: function () {
      if (!this.enabled) return;
      var ctx = this.exerciseContext;
      if (!ctx || typeof ctx.gradeHarmonizationMidiSet !== "function") return;
      if (!this._pending.length) return;

      var target = this._activeTarget() || {};
      var lockedMidi = [];
      var locked = target.lockedVoices || {};
      Object.keys(locked).forEach(function (k) {
        if (typeof locked[k].midi === "number") lockedMidi.push(locked[k].midi);
      });

      var snapshot = ClickNoteLogic.buildCommitSnapshot(lockedMidi, this.getPendingMidi());
      ctx.gradeHarmonizationMidiSet(snapshot);
      this._pending = [];
      this._activeColumn = null;
      if (this.sheet) this.sheet.render();
    },

    setPalette: function (palette) {
      this.palette = palette;
      this._syncPaletteButtons();
    },

    _buildEl: function () {
      var self = this;
      var wrap = $('<div class="click-note-input" style="display:none;"></div>');
      var palette = $('<div class="accidental-palette input-mode-toggle"></div>');
      var defs = [
        ["diatonic", "Key"],
        ["sharp", "\u266f"],
        ["flat", "\u266d"],
        ["natural", "\u266e"],
      ];
      this._paletteBtns = {};
      defs.forEach(function (d) {
        var btn = $('<button class="input-mode-btn"></button>').text(d[1]);
        btn.on("click", function (e) {
          e.preventDefault();
          self.setPalette(d[0]);
        });
        self._paletteBtns[d[0]] = btn;
        palette.append(btn);
      });
      var doneBtn = $('<button class="input-mode-btn click-note-done">Done</button>');
      doneBtn.on("click", function (e) {
        e.preventDefault();
        self._commit();
      });
      wrap.append(palette).append(doneBtn);
      this._paletteWrap = wrap;
      this._syncPaletteButtons();
      return wrap;
    },

    _syncPaletteButtons: function () {
      var self = this;
      Object.keys(this._paletteBtns || {}).forEach(function (k) {
        self._paletteBtns[k]
          .toggleClass("input-mode-btn-active", k === self.palette)
          .toggleClass("input-mode-btn-inactive", k !== self.palette);
      });
    },

    _syncPalettePanel: function () {
      if (!this._paletteWrap) return;
      if (this.enabled) {
        this._paletteWrap.show();
      } else {
        this._paletteWrap.hide();
      }
    },

    render: function () {
      return this;
    },

    renderTo: function (selector) {
      $(selector).append(this.el);
      return this;
    },

    destroy: function () {
      this.disable();
    },
  });

  return ClickNoteInputComponent;
});
