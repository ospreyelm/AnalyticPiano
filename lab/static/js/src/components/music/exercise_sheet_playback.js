import $ from "jquery";
import $UI from "jquery-ui";
import _ from "lodash";
import Vex from "vexflow";
import Config from "app/config";
import Analyze from "app/utils/analyze";
import EVENTS from "app/components/events";
import Component from "app/components/component";
import FontParser from "app/utils/fontparser";
import Stave from "./stave";
import StaveNotater from "./stave_notater";
import ExerciseNoteFactory from "./exercise_note_factory";
import VexFlowAdapter from "./rendering/vexflow_adapter";
import ScoreTimeline from "./score_timeline";
import TextInput from "app/components/input/text_input";
import ScorePlayer from "app/models/score_player";
import IdentificationSubmitFlow from "app/models/identification_submit_flow_logic";
import KeyContext from "app/models/key_context_logic";
import renderPlaybackControls from "app/components/music/playback_controls";
import MeasureEngine from "app/utils/measure_engine";
import HarmonizationRealizationLogic from "app/models/harmonization_realization_logic";
import IdentificationLabelLayoutLogic from "app/components/music/identification_label_layout_logic";
import ChordalProblemsLogic from "app/models/chordal_problems_logic";
import ChordalUMTOStaffDistribution from "./chordal_umto_staff_distribution";
import KeySignature from "app/models/key_signature";
import ChordalSpelling from "./chordal_spelling";
import ChordalBarlinesLogic from "app/utils/chordal_barlines_logic";
import UMTOScoreConverter from "app/utils/umto_score_converter";
import BarlineSpacingUtils from "app/utils/barline_spacing_utils";

export default  {
    _ghostCanvas: function () {
      var base = this.el && this.el[0] ? this.el[0] : null;
      if (!base) return null;
      var overlay = this._ghostCanvasEl;
      if (!overlay) {
        overlay = document.createElement("canvas");
        overlay.className = "js-ghost-overlay";
        overlay.style.position = "absolute";
        overlay.style.pointerEvents = "none";
        overlay.style.left = base.offsetLeft + "px";
        overlay.style.top = base.offsetTop + "px";
        if (base.parentNode) {
          var ps = window.getComputedStyle(base.parentNode);
          if (ps.position === "static") base.parentNode.style.position = "relative";
          base.parentNode.appendChild(overlay);
        }
        this._ghostCanvasEl = overlay;
      }
      if (overlay.width !== base.width) overlay.width = base.width;
      if (overlay.height !== base.height) overlay.height = base.height;
      overlay.style.width = base.style.width || (base.width + "px");
      overlay.style.height = base.style.height || (base.height + "px");
      overlay.style.left = base.offsetLeft + "px";
      overlay.style.top = base.offsetTop + "px";
      return overlay;
    },

    drawGhostNote: function (resolved) {
      this._ghost = resolved || null;
      var overlay = this._ghostCanvas();
      if (!overlay) return;
      var c2d = overlay.getContext("2d");
      if (!c2d) return;
      c2d.clearRect(0, 0, overlay.width, overlay.height);
      if (this._ghost && this._staffLayout) this._drawGhostGlyph(c2d, this._ghost);
    },

    clearGhostNote: function () {
      this._ghost = null;
      if (!this._ghostCanvasEl) return;
      var c2d = this._ghostCanvasEl.getContext("2d");
      if (c2d) c2d.clearRect(0, 0, this._ghostCanvasEl.width, this._ghostCanvasEl.height);
    },

    _drawGhostGlyph: function (c2d, ghost) {
      if (!c2d || !this._staffLayout || !ghost || !ghost.column) return;
      var sys = (this._staffLayout.systems || [])[ghost.column.systemIndex]
        || (this._staffLayout.systems || [])[0];
      if (!sys) return;
      var stave = (sys.staves || []).filter(function (s) { return s.clef === ghost.staveClef; })[0]
        || sys.staves[0];
      if (!stave) return;
      var y = stave.topLineY + ghost.stepsFromTop * (stave.lineSpacing / 2);
      c2d.save();
      c2d.fillStyle = "#b0b8c4";
      c2d.beginPath();
      c2d.ellipse(ghost.column.centerX, y, 6, 4.5, 0, 0, 2 * Math.PI);
      c2d.fill();
      c2d.restore();
    },
    
    /**
     * Handles a chord bank update.
     *
     * @return undefined
     */
    onChordsUpdate: function () {
      var definition = this.exerciseContext.getDefinition();
      // Chorale exercises don't use chord bank, so skip this
      if (definition.isChorale()) return;
      
      this.updateStaves();
      this.render();
    },
    /**
     * Calculates onset-to-measure mapping and page-start offsets for the current score.
     * Populate _playbackMeasureTickOffset so autoScroll and highlights work reliably.
     */
    _calculatePlaybackOffsets: function () {
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore ? definition.getScore() : null;
      if (!score) return null;

      var tl = ScoreTimeline.buildTimeline(score);
      var measureStarts = ScoreTimeline.buildMeasureOffsets
        ? ScoreTimeline.buildMeasureOffsets(score)
        : [];
      var onsetSeen = {};
      var order = [];
      var measureOffset = {};

      for (var i = 0; i < tl.length; i++) {
        var ev = tl[i];
        if (!onsetSeen[ev.onset]) {
          onsetSeen[ev.onset] = { measureIndex: ev.measureIndex };
          order.push(ev.onset);
        }
      }
      order.sort(function (a, b) { return a - b; });

      if (measureStarts && measureStarts.length) {
        for (var measureIndex = 0; measureIndex < measureStarts.length; measureIndex++) {
          measureOffset[measureIndex] = measureStarts[measureIndex];
        }
      }

      this._playbackWindowOnsets = order.slice();
      this._playbackWindowMeasures = order.map(function (onset) { return onsetSeen[onset].measureIndex; });
      this._playbackMeasureTickOffset = measureOffset;

      return tl;
    },
    /**
     * Handle MIDI note events in chorale and harmonization modes.
     */
    onMidiNote: function (state, noteNum) {
      var definition = this.exerciseContext.getDefinition();
      var isChorale = definition.isChorale && definition.isChorale();
      var isHarmonization = definition.isHarmonization && definition.isHarmonization();
      if (!isChorale && !isHarmonization) return;
      if (this.exerciseContext && this.exerciseContext._reviewDisplayOnly) return;

      // Start timer on first interaction
      if (state === "on") {
        this.exerciseContext.triggerTimer();
      }

      if (isHarmonization) {
        if (this._inputSourceMode === "click") {
          return;
        }
        // New noteOn clears any red rejected-state overlay from a prior incorrect attempt.
        if (state === "on" && this.exerciseContext._harmonizationRejected) {
          this.exerciseContext._harmonizationRejected = null;
        }
        var ctx = this.exerciseContext;
        var tracker = ctx._harmonizationHeldTracker;
        if (tracker) {
          if (state === "on") {
            tracker.noteOn(noteNum);
          } else if (state === "off") {
            tracker.noteOff(noteNum, Date.now());
          }
        }
        var self = this;
        var settleMs = ctx._harmonizationChordSettleMs || 150;
        if (ctx._harmonizationSettleTimer) {
          clearTimeout(ctx._harmonizationSettleTimer);
        }
        ctx._harmonizationSettleTimer = setTimeout(function () {
          ctx._harmonizationSettleTimer = null;
          ctx.grade();
          self.render();
        }, settleMs);
        return;
      }

      var grader = this.exerciseContext.grader;
      if (!grader) return;
      if (state === "on" && typeof grader.noteOn === "function") {
        grader.noteOn(noteNum);
      } else if (state === "off" && typeof grader.noteOff === "function") {
        grader.noteOff(noteNum);
      }

      // Run the standard grading pipeline (handles state + auto-advance)
      this.exerciseContext.grade();

      // Persist played-note progress so a page reload can restore it — this
      // exercise type otherwise has no reload-survival path at all (unlike
      // identification's saveIdentState/localStorage, or harmonization's
      // server-side review).
      if (state === "on") {
        this.exerciseContext.saveChoraleState();
      }

      // Repaint with updated highlights
      this.render();
      this.autoScroll();
    },

    /**
     * Automatically scrolls the sheet horizontally to keep the current active note in view.
     */
    autoScroll: function () {
      var grader = this.exerciseContext.grader;
      if (!grader || typeof grader.getActiveIndex !== "function") return;
      
      var windowIdx = grader.getActiveIndex();
      if (windowIdx === null || windowIdx === undefined) return;

      var globalOnset = grader.timeline && grader.timeline[windowIdx] && grader.timeline[windowIdx].onset;
      if (globalOnset === undefined) return;

      // Use the same coordinate mapping as playback highlight
      var measureIdx = grader.getMeasureIndexForWindow ? grader.getMeasureIndexForWindow(windowIdx) : 0;
      var targetStart = Math.floor(measureIdx / 4) * 4;
      var pageStartTick = (this._playbackMeasureTickOffset && this._playbackMeasureTickOffset[targetStart]) || 0;
      var pageLocalOnset = globalOnset - pageStartTick;
      var cacheKey = measureIdx + ":" + pageLocalOnset;

      var slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
      if (slot && slot.x) {
        var $container = $("#staffwrapper");
        if (!$container.length) {
          $container = this.el.parent();
        }
        
        var scrollLeft = $container.scrollLeft();
        var containerWidth = $container.width();
        var noteX = slot.x;

        // padding to keep some context
        var padding = 100;
        
        // If note is near the right edge or beyond, scroll it into view
        if (noteX > scrollLeft + containerWidth - padding) {
          $container.stop().animate({ scrollLeft: noteX - containerWidth + padding + 200 }, 300);
        } else if (noteX < scrollLeft + padding) {
          $container.stop().animate({ scrollLeft: Math.max(0, noteX - padding) }, 300);
        }
      }
    },
    /**
     * Handles navigating to the next exercise.
     *
     * @return undefined
     */
    onGoToExercise: function (target) {
      window.location = target.url;
    },
    /**
     * Handles the pristine/refresh button click.
     * Resets chorale state and exercise context.
     *
     * @return undefined
     */
    onClickPristine: function () {
      var definition = this.exerciseContext.getDefinition();

      // Reset chorale state if in chorale mode
      if (definition.isChorale()) {
        this.initChoraleMode();
      }

      // Reset harmonization state
      if (definition.isHarmonization && definition.isHarmonization()) {
        var ctx = this.exerciseContext;
        if (ctx._harmonizationSettleTimer) {
          clearTimeout(ctx._harmonizationSettleTimer);
          ctx._harmonizationSettleTimer = null;
        }
        if (ctx._harmonizationHeldTracker) {
          ctx._harmonizationHeldTracker.reset();
        }
        ctx._harmonizationPointer = 0;
        ctx.acceptedHarmonizationSonorities = [];
        ctx._harmonizationRejected = null;
        ctx.harmonizationVLScore = null;
        ctx.harmonizationTier = null;
      }

      // Reset exercise context state
      this.exerciseContext.done = false;
      this.exerciseContext.sealed = false;
      this.exerciseContext.state = this.exerciseContext.STATE.READY;

      // Re-render
      this.render();
      this.renderExerciseStatus();
    },

    _drawPlaybackHighlight: function () {
      var idx = this._playbackWindowIndex;
      if (idx === null || idx === undefined) return;
      if (!this._playbackWindowOnsets) return;

      var globalOnset = this._playbackWindowOnsets && this._playbackWindowOnsets[idx];
      if (globalOnset === undefined) return;
      var measureIdx = this._playbackWindowMeasures && this._playbackWindowMeasures[idx];
      if (measureIdx === undefined) return;

      var maxMeasures = (this._chorale && this._chorale.maxMeasures) || 4;
      var targetStart = Math.floor(measureIdx / maxMeasures) * maxMeasures;

      // Convert global onset → page-local onset by subtracting the tick at page start.
      var pageStartTick = this._playbackMeasureTickOffset && this._playbackMeasureTickOffset[targetStart];
      if (pageStartTick === undefined) return;
      var pageLocalOnset = globalOnset - pageStartTick;
      var cacheKey = measureIdx + ":" + pageLocalOnset;

      // Navigate to the correct page if this window is not on the current rendered page.
      var slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
      if (!slot && this._chorale) {
        if (targetStart !== this._chorale.startMeasure) {
          // Set flag so _updateChoraleViewport doesn't clobber our target page.
          this._playbackOverridePage = targetStart;
          this._chorale.startMeasure = targetStart;
          this.render(); // synchronously repopulates _identWindowLayoutByOnset
          this._playbackOverridePage = null;
          slot = this._identWindowLayoutByOnset && this._identWindowLayoutByOnset[cacheKey];
        }
      }
      if (!slot) return;

      var canvas = this.el[0];
      var canvasOffset = $(canvas).offset();
      var w = 30;
      var h = slot.y;  // bassStave.getBottomY() + 18
      var left = canvasOffset.left + slot.x - w / 2;
      var top = canvasOffset.top;

      var $hl = $("#playback-highlight");
      if (!$hl.length) {
        $hl = $('<div id="playback-highlight">').css({
          position: "fixed",
          pointerEvents: "none",
          background: "rgba(79, 172, 254, 0.15)",
          border: "1px solid rgba(79, 172, 254, 0.35)",
          boxSizing: "border-box",
          zIndex: 10,
        });
        $("body").append($hl);
      }

      $hl.css({ left: left, top: top, width: w, height: h }).show();
    },

    _clearPlaybackHighlight: function () {
      $("#playback-highlight").hide();
    },
  };
