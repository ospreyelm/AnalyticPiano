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
    this.midiDevice = this.settings.midiDevice || null;
    this.feedback = this.settings.feedback || null;

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
      if (this.exerciseContext && this.exerciseContext.getDefinition) {
        var def = this.exerciseContext.getDefinition();
        var score = def && def.getScore ? def.getScore() : null;
        if (score && score.meta && score.meta.key) return score.meta.key;
        if (def && def.getKeyName) return def.getKeyName();
      }
      if (this.keySignature && this.keySignature.getKey) return this.keySignature.getKey();
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

    _resolveAny: function (e) {
      var layout = this._layout();
      if (!layout) return null;
      return ClickNoteLogic.resolveClick(this._eventPoint(e), layout, {
        key: this._key(),
        palette: this.palette
        // no activeColumnOnset -> resolves to whatever column the pixel lands in
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
      if (!resolved) {
        // A valid-but-inactive column resolves only when the onset gate is removed.
        var any = this._resolveAny(e);
        if (any && any.column && any.column.onset !== this._activeTargetOnset() && this.feedback) {
          this.feedback.emit("harmonization.click.outside_column", { context: this._feedbackContext() });
        }
        return;
      }
      var prevOnset = this._activeTargetOnset();
      this._activeColumn = resolved.column;
      // Moving to a new column clears the rejected-state overlay.
      if (this.exerciseContext && resolved.column && resolved.column.onset !== prevOnset) {
        this.exerciseContext._harmonizationRejected = null;
      }

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
        this._showCapHint();
        return;
      }

      this._pending.push({
        midi: resolved.midi,
        step: resolved.step,
        alter: resolved.alter,
        octave: resolved.octave,
      });
      this._audition(resolved.midi);
      if (this.sheet) this.sheet.render();
    },

    _feedbackContext: function () {
      var ec = this.exerciseContext;
      // ExerciseDefinition.exercise is a PROPERTY (parsed object), not a method.
      if (!ec || !ec.definition || !ec.definition.exercise) return null;
      var ex = ec.definition.exercise;
      if (!ex) return null;
      var tags = ex.skill_tags || [], unit = null;
      for (var i = 0; i < tags.length; i++) {
        var m = /^unit:(\d+)$/.exec(tags[i]);
        if (m) { unit = parseInt(m[1], 10); break; }
      }
      return { exerciseId: ex.exerciseId || ex.id || ex.exercise_id || null, unit: unit,
        complexity: typeof ex.complexity_score === "number" ? ex.complexity_score : null, skillTags: tags };
    },

    _showCapHint: function () {
      if (!this._paletteWrap) return;
      var capEntry = this.feedback
        ? this.feedback.emit("harmonization.click.note_cap", { surface: "none", context: this._feedbackContext() })
        : null;
      var capTitle = capEntry ? capEntry.title : "Chord is full.";
      var capBody = capEntry ? capEntry.body : "Remove a note to add another.";

      var self = this;
      window.clearTimeout(this._capHintTimer);
      this._paletteWrap.removeClass("click-note-cap-shake");
      // Restart the animation even on repeated clicks.
      if (this._paletteWrap[0]) void this._paletteWrap[0].offsetWidth;
      this._paletteWrap.addClass("click-note-cap-shake");
      if (!this._capHintEl) {
        this._capHintEl = $(
          '<div class="click-note-cap-hint" role="status" aria-live="polite">' +
          '<strong>' + capTitle + '</strong><span>' + capBody + '</span>' +
          '</div>'
        );
        this._paletteWrap.append(this._capHintEl);
      }
      this._capHintEl.addClass("is-visible");
      this._capHintTimer = window.setTimeout(function () {
        if (self._capHintEl) self._capHintEl.removeClass("is-visible");
        if (self._paletteWrap) self._paletteWrap.removeClass("click-note-cap-shake");
      }, 1800);
    },

    _audition: function (midi) {
      var device = this.midiDevice;
      if (!device || typeof device.playNote !== "function") return;
      device.playNote(midi);
      if (typeof device.releaseNote === "function") {
        window.setTimeout(function () {
          device.releaseNote(midi);
        }, 450);
      }
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
      if (!this._pending || this._pending.length === 0) {
        if (this.feedback) {
          this.feedback.emit("harmonization.click.empty_commit", {
            controlEl: this._doneButton || ".click-note-done",
            context: this._feedbackContext()
          });
        }
        return;
      }

      var target = this._activeTarget() || {};
      var lockedMidi = [];
      var locked = target.lockedVoices || {};
      Object.keys(locked).forEach(function (k) {
        if (typeof locked[k].midi === "number") lockedMidi.push(locked[k].midi);
      });

      var snapshot = ClickNoteLogic.buildCommitSnapshot(lockedMidi, this.getPendingMidi());
      // Capture spellings + position before clearing, so the rejected-state render can show red notes.
      var pendingForRejected = this._pending.slice();
      var columnForRejected = this._activeColumn;
      ctx.gradeHarmonizationMidiSet(snapshot);
      // If rejected state was set, attach spellings and position from the commit.
      if (ctx._harmonizationRejected && pendingForRejected.length) {
        ctx._harmonizationRejected.spellings = pendingForRejected.map(function (n) {
          return { step: n.step, alter: n.alter || 0, octave: n.octave };
        });
        if (columnForRejected) {
          ctx._harmonizationRejected.measureIndex = columnForRejected.measureIndex || 0;
          ctx._harmonizationRejected.onset = typeof columnForRejected.onset === "number"
            ? columnForRejected.onset - ((columnForRejected.measureIndex || 0) * (this.sheet && this.sheet._measureTotalTicks ? this.sheet._measureTotalTicks() : 4096))
            : 0;
        }
      }
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
      var wrap = $('<div class="click-note-input" style="display:none;" aria-label="Click note input tools"></div>');
      var palette = $('<div class="accidental-palette input-mode-toggle"></div>');
      var defs = [
        ["diatonic", "Key", "Use the key signature"],
        ["sharp", "\u266f", "Sharp"],
        ["flat", "\u266d", "Flat"],
        ["natural", "\u266e", "Natural"],
      ];
      this._paletteBtns = {};
      defs.forEach(function (d) {
        var btn = $('<button type="button" class="input-mode-btn"></button>')
          .text(d[1])
          .attr("title", d[2]);
        btn.on("click", function (e) {
          e.preventDefault();
          self.setPalette(d[0]);
        });
        self._paletteBtns[d[0]] = btn;
        palette.append(btn);
      });
      var doneBtn = $('<button type="button" class="input-mode-btn click-note-done" title="Lock in this chord and check it — or press Enter">Lock chord <span class="click-note-done-key">⏎</span></button>');
      this._doneButton = doneBtn;
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
        this._paletteWrap.css("display", "flex");
      } else {
        this._paletteWrap.hide();
      }
    },

    render: function () {
      return this;
    },

    renderTo: function (selector) {
      $(selector).prepend(this.el);
      return this;
    },

    destroy: function () {
      this.disable();
    },
  });

  return ClickNoteInputComponent;
});
