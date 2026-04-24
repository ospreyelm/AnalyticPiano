/* global define: false */
define([
  "jquery",
  "jquery-ui",
  "lodash",
  "vexflow",
  "app/config",
  "app/utils/analyze",
  "app/components/events",
  "app/components/component",
  "app/utils/fontparser",
  "./stave",
  "./stave_notater",
  "./exercise_note_factory",
  "./rendering/vexflow_adapter",
  "./score_timeline",
  "app/components/input/label_input",
  "app/models/score_player",
  "app/components/music/playback_controls",
  "app/utils/measure_engine",
], function (
  $,
  $UI,
  _,
  Vex,
  Config,
  Analyze,
  EVENTS,
  Component,
  FontParser,
  Stave,
  StaveNotater,
  ExerciseNoteFactory,
  VexFlowAdapter,
  ScoreTimeline,
  LabelInput,
  ScorePlayer,
  renderPlaybackControls,
  MeasureEngine
) {
  "use strict";

  /**
   * Defines the size of the chord bank (how many chords to display on
   * screen).
   * @type {number}
   */
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize") - 1;

  var DEFAULT_RHYTHM_VALUE = Config.get("general.defaultRhythmValue");

  var SETTING_HIDE_NEXT = Config.get("general.hideNextForAutoAdvance");

  var NUMBERED_EXERCISE_COUNT = Config.get("general.numberedExerciseCount");

  /**
   * ExerciseSheetComponent
   *
   * This object is responsible for knowing how to display plain sheet music
   * notation with the notes that have sounded (saved in the chord bank) and
   * are currently sounding via MIDI input or some other means. So this object
   * should know how to display the grand staff and configure it for analysis,
   * highlight, etc.
   *
   * @constructor
   * @param {object} settings
   * @param {ChordBank} settings.chords Required property.
   * @param {KeySignature} settings.keySignature Required property.
   */
  var ExerciseSheetComponent = function (settings) {
    this.settings = settings || {};

    if ("exerciseContext" in this.settings) {
      this.exerciseContext = this.settings.exerciseContext;
    } else {
      throw new Error("Missing parameter property: .exerciseContext");
    }

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("Missing parameter property: .keySignature");
    }

    if ("timeSignature" in this.settings.exerciseContext) {
      this.timeSignature = this.settings.exerciseContext.timeSignature;
    } else {
      throw new Error("Missing parameter property: .timeSignature");
    }

    _.bindAll(this, ["render", "onChordsUpdate", "onMidiNote", "onClickPristine", "onSubmitIdentification", "onToggleMode", "_onIdentKeyDown"]);
  };

  ExerciseSheetComponent.prototype = new Component();

  _.extend(ExerciseSheetComponent.prototype, {
    /**
     * Initializes the sheet.
     *
     * @param {object} config
     * @return undefined
     */
    initComponent: function () {
      this.el = $("canvas#staff");
      this.el[0].width = this.el.width();
      this.el[0].height = this.el.height();
      this.initRenderer();
      this.initStaves();
      this.initListeners();
      var definition = this.exerciseContext.getDefinition();
      // Chorale-specific init
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        this.initChoraleMode();
      }
      if (this._isIdentificationLikeExercise()) {
        this.initIdentificationMode();
      }

      // Playback
      var self = this;
      this.scorePlayer = new ScorePlayer(this.settings.midiDevice);
      this.scorePlayer.bind("tick", function (windowIndex) {
        self._playbackWindowIndex = windowIndex;
        self._drawPlaybackHighlight();
      });
      this.scorePlayer.bind("stopped", function () {
        self._playbackWindowIndex = null;
        self._clearPlaybackHighlight();
      });
      this._playbackWindowIndex = null;
    },
    /**
     * Initializes the canvas renderer and dom element.
     *
     * @return
     */
    initRenderer: function () {
      var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
      this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
      this.renderExerciseInfo();
      this.renderExerciseText();
    },
    /**
     * Initializes the staves that together will form the grand staff.
     *
     * @return undefined
     */
    initStaves: function () {
      this.updateStaves();
    },
    /**
     * Initializes event listeners.
     *
     * @return undefined
     */
    initListeners: function () {
      this.parentComponent.bind("change", this.render);
      this.keySignature.bind("change", this.render);
      //this.getInputChords().bind('change', this.render);
      this.getInputChords().bind("change", this.onChordsUpdate);
      this.getInputChords().bind("clear", this.onChordsUpdate);
      this.exerciseContext.bind("goto", this.onGoToExercise);
      // Re-render when ident page changes (goToIdentPage fires "graded")
      this.exerciseContext.bind("graded", this.render);
      // Listen for MIDI notes globally
      this.subscribe(EVENTS.BROADCAST.NOTE, this.onMidiNote);
      // Listen for pristine/refresh button
      this.subscribe(EVENTS.BROADCAST.PRISTINE, this.onClickPristine);
      // Arrow key page navigation for identification exercises
      window.removeEventListener("keydown", this._onIdentKeyDown, true);
      window.addEventListener("keydown", this._onIdentKeyDown, true);
    },
    _isIdentificationLikeExercise: function () {
      var definition = this.exerciseContext.getDefinition();
      var isIdent = (definition.isIdentification && definition.isIdentification()) ||
             (definition.isChoraleIdentification && definition.isChoraleIdentification());
      console.log("[ID] _isIdentificationLikeExercise result:", isIdent, "type:", definition.getType());
      return isIdent;
    },
    _isChoraleIdentificationExercise: function () {
      var definition = this.exerciseContext.getDefinition();
      return !!(definition.isChoraleIdentification && definition.isChoraleIdentification());
    },
    /**
     * Set up identification mode.  No DOM selects are created here —
     * answers are drawn on the canvas and editing happens via a position:fixed
     * popup that appears at the cursor when the student clicks near a label.
     *
     * Three modes (set via exercise data.identMode):
     *   "submit"   — pick all answers, press Submit, then see results (default)
     *   "practice" — correct/incorrect shown immediately after each selection
     *   "test"     — answers locked after choosing, no feedback ever shown
     */
    initIdentificationMode: function () {
      var self = this;
      var definition = this.exerciseContext.getDefinition();
      var grader = this.exerciseContext.grader;
      if (grader && grader.initFromDefinition) {
        grader.initFromDefinition(definition);
      }

      this._identActiveIndex = null;
      this._identPopupEl = null;
      this._currentMode = this.exerciseContext.settings.identMode || "submit";
      this._modeLocked = this.exerciseContext.settings.modeLocked || false;

      this.renderModeToggle();

      var identMode = this._currentMode;

      // Show Submit button only in submit mode
      if (identMode === 'submit') {
        $('#identification-actions').show();
        var $submitBtn = $('#identification-submit');
        $submitBtn.attr('type', 'button');
        // Use direct DOM property to ensure the handler cannot be removed by
        // subsequent .off('click') calls or overridden by other jQuery bindings.
        var submitBtnEl = $submitBtn[0];
        if (submitBtnEl) {
          submitBtnEl.onclick = null; // clear any prior handler
          submitBtnEl.onclick = _.bind(this.onSubmitIdentification, this);
        }
      } else {
        $('#identification-actions').hide();
      }

      // Canvas click: open popup only inside the label hit zone below bass staff
      this.el.off('click.identification').on('click.identification', function (e) {
        if (!self._isIdentificationLikeExercise()) { return; }

        // Lock individual correct items so users can still modify incorrect choices or finish a new page
        var currentMode = self._currentMode;

        var offset = self.el.offset();
        var clickX = e.pageX - offset.left;
        var clickY = e.pageY - offset.top;

        var hitIndex = -1;
        var slots = self._getIdentificationSlots();
        for (var i = 0; i < slots.length; i++) {
          var slot = slots[i];
          if (!slot) { continue; }
          
          var problems = self.exerciseContext.getVisibleProblems
            ? self.exerciseContext.getVisibleProblems()
            : definition.getProblems();
          var problem = problems[slot.index];
          if (problem && problem.hidden) { continue; } // Skip hidden slots

          if (
            clickX >= slot.x - 20 && clickX <= slot.x + 20 &&
            clickY >= slot.y - 20 && clickY <= slot.y + 46
          ) {
            hitIndex = slot.index;
            break;
          }
        }
        // Lock slots that already have an answer in test mode, or are already graded correct in submit mode.
        var grdr = self.exerciseContext.grader;
        var pageOffset = self.exerciseContext.getIdentPageOffset
          ? self.exerciseContext.getIdentPageOffset() : 0;
        var absoluteHitIndex = pageOffset + hitIndex;
        
        var limits = { practice: 3, submit: 2, test: 1 };
        var limit = limits[self._currentMode] || 3;
        var graderCounts = (self.exerciseContext.grader && self.exerciseContext.grader.attemptCounts) || {};
        var count = graderCounts[absoluteHitIndex] || 0;

        if (count >= limit) {
          return;
        }

        if (currentMode === 'test' && grdr && grdr.answers && grdr.answers.hasOwnProperty(absoluteHitIndex)) {
          return;
        }

        if (self.exerciseContext.graded && currentMode !== 'practice') {
            var gp = self.exerciseContext.graded.problems ? self.exerciseContext.graded.problems[hitIndex] : null;
            if (gp && gp.correct) {
                return; // Lock only correctly graded items so users can still modify mistakes
            }
        }

        var problems = self.exerciseContext.getVisibleProblems
          ? self.exerciseContext.getVisibleProblems()
          : definition.getProblems();
        var problem = problems[hitIndex];
        if (!problem) { return; }

        self._showIdentPopup(absoluteHitIndex, problem.choices, e.clientX, e.clientY);
      });

      // Change cursor to pointer when hovering over a label zone
      this.el.off('mousemove.identification').on('mousemove.identification', function (e) {
        if (!self._isIdentificationLikeExercise()) { return; }
        var offset = self.el.offset();
        var cx = e.pageX - offset.left;
        var cy = e.pageY - offset.top;
        var slots = self._getIdentificationSlots();
        var over = false;
        for (var i = 0; i < slots.length; i++) {
          var slot = slots[i];
          if (!slot) { continue; }

          var problems = self.exerciseContext.getVisibleProblems
            ? self.exerciseContext.getVisibleProblems()
            : definition.getProblems();
          var problem = problems[slot.index];
          if (problem && problem.hidden) { continue; } // Skip hidden slots

          if (
            cx >= slot.x - 20 && cx <= slot.x + 20 &&
            cy >= slot.y - 20 && cy <= slot.y + 46
          ) {
            over = true;
            break;
          }
        }
        self.el.css('cursor', over ? 'pointer' : '');
      });
    },

    /**
     * Shows a position:fixed popup list of choices at the cursor.
     */
    _showIdentPopup: function (problemIndex, choices, clientX, clientY) {
      var self = this;
      this._closeIdentPopup();

      var popup = $('<div id="ident-popup"></div>');
      _.each(choices, function (choice) {
        var btn = $('<button></button>').addClass('ident-popup-btn').text(choice);
        btn.on('click', function (e) {
          e.stopPropagation();
          var grdr = self.exerciseContext.grader;
          grdr.setAnswer(problemIndex, choice);
          self._closeIdentPopup();

          var currentMode = self._currentMode;

          if (currentMode === 'practice') {
            // Show colour feedback immediately
            var visibleProblems = self.exerciseContext.getVisibleProblems
              ? self.exerciseContext.getVisibleProblems()
              : null;
            var practicePageOffset = self.exerciseContext.getIdentPageOffset
              ? self.exerciseContext.getIdentPageOffset()
              : 0;
            var graded = grdr.grade(self.exerciseContext.getDefinition(), visibleProblems, practicePageOffset);
            self.exerciseContext.graded = graded;
            self.render();
            if (graded.result === 'correct') {
              setTimeout(function () { self.exerciseContext.grade(); }, 500);
            }
          } else if (currentMode === 'test') {
            // No colour feedback; auto-submit silently when all slots answered
            self.exerciseContext.graded = null;
            self.render();
            var allProblems = self.exerciseContext.getDefinition().getProblems();
            var allAnswered = true;
            for (var i = 0; i < allProblems.length; i++) {
              if (!grdr.answers || !grdr.answers.hasOwnProperty(i)) {
                allAnswered = false;
                break;
              }
            }
            if (allAnswered) {
              var silentGrade = grdr.grade(self.exerciseContext.getDefinition());
              setTimeout(function () { self.exerciseContext.grade(); }, 500);
            }
          } else {
            // submit mode: label goes dark, awaiting Submit click
            self.render();
          }
        });
        popup.append(btn);
      });

      // Position popup to the right of cursor; shift left if near viewport edge
      var winW = $(window).width();
      var left = clientX + 8;
      popup.css({ top: clientY - 10, left: left });
      $('body').append(popup);
      var popupW = popup.outerWidth();
      if (left + popupW > winW - 10) {
        popup.css('left', clientX - popupW - 8);
      }

      this._identPopupEl = popup;

      // Close on any outside click
      setTimeout(function () {
        $(document).one('click.identpopup', function () {
          self._closeIdentPopup();
        });
      }, 0);
    },

    _closeIdentPopup: function () {
      if (this._identPopupEl) {
        this._identPopupEl.remove();
        this._identPopupEl = null;
      }
      $(document).off('click.identpopup');
    },

    /**
     * Draws the current answer (or a "?" placeholder) below the bass staff,
     * plus a ✓ or ✗ symbol when graded.
     * Called from renderStaves() after all staves are drawn.
     */
    _getIdentificationSlots: function () {
      var definition = this.exerciseContext.getDefinition();
      var problems = this.exerciseContext.getVisibleProblems
        ? this.exerciseContext.getVisibleProblems()
        : (definition.getProblems ? definition.getProblems() : []);
      console.log("[ID] _getIdentificationSlots problems count:", problems.length);
      if ((this._isChoraleIdentificationExercise() || definition.getScore()) && !_.isEmpty(this._identWindowLayout)) {
        var layout = this._identWindowLayout || {};
        console.log("[ID] UMTO layout keys:", Object.keys(layout));
        return _.map(problems, function (_problem, idx) {
          var slot = layout[idx];
          if (!slot) { return null; }
          return { index: idx, x: slot.x, y: slot.y };
        }).filter(Boolean);
      }

      var noteStaves = this.staves.slice(1);
      console.log("[ID] noteStaves count:", noteStaves.length);
      return _.map(noteStaves, function (treble, idx) {
        var bass = treble.connectedStave;
        console.log("[ID] Slot", idx, "bass:", !!bass, "bass.staffSegment:", !!(bass && bass.staffSegment));
        if (!bass || !bass.staffSegment) {
          return null;
        }
        return {
          index: idx,
          x: bass.getStartX() + 8,
          y: bass.getBottomY() + 18,
        };
      }).filter(Boolean);
    },

    drawIdentificationLabels: function () {
      var slots = this._getIdentificationSlots();
      console.log("[ID] drawIdentificationLabels slots count:", slots.length);
      if (!slots.length) { return; }

      var grader = this.exerciseContext.grader;
      var definition = this.exerciseContext.getDefinition();
      var identMode = this._currentMode;
      var ctx = this.vexRenderer.getContext();
      var lastGraded = this.exerciseContext.graded;

      var origFont = ctx.font;
      var origFillStyle = ctx.fillStyle;
      var origTextAlign = ctx.textAlign;
      var origTextBaseline = ctx.textBaseline;
      var origLineWidth = ctx.lineWidth;

      // Center labels on slot.x so visual position and click target match.
      ctx.textAlign = 'center';
      ctx.textBaseline = 'alphabetic';
      var answeredCount = 0;
      var visibleSlotCount = 0;

      for (var i = 0; i < slots.length; i++) {
        var slot = slots[i];
        var lx = slot.x;
        var ly = slot.y;

        var localIndex = slot.index;
        var pageOffset = this.exerciseContext && this.exerciseContext.getIdentPageOffset
          ? this.exerciseContext.getIdentPageOffset() : 0;
        var absoluteIndex = pageOffset + localIndex;

        var problems = definition.getProblems ? definition.getProblems() : [];
        var problem = problems[absoluteIndex];
        if (problem && problem.hidden) { continue; } // LEAVE A SPACE
        visibleSlotCount++;

        // AUTO-SCROLL LOGIC: Scroll the active problem into view
        var activeIndex = grader && grader.activeIndex !== undefined ? grader.activeIndex : 0;
        console.log("[ID] Slot", i, "absIdx:", absoluteIndex, "lx:", lx, "ly:", ly, "label:", (grader && grader.answers && grader.answers[absoluteIndex]) || '?');
        if (absoluteIndex === activeIndex && this.el && this.el.parent) {
          var container = this.el.parent();
          if (container.length) {
            var scrollX = lx - container.width() / 2;
            container.stop().animate({ scrollLeft: Math.max(0, scrollX) }, 200);
          }
        }

        var chosen = grader && grader.answers && grader.answers.hasOwnProperty(absoluteIndex)
          ? grader.answers[absoluteIndex] : null;
        var label = chosen || '?';

        var fillStyle = '#888888'; // unanswered
        if (chosen) { fillStyle = '#444444'; answeredCount++; } // answered
        var showCheck = false;
        var showCross = false;

        // Show colour feedback when graded (never in test mode)
        if (lastGraded && lastGraded.problems && lastGraded.problems[localIndex] && identMode !== 'test') {
          var gp = lastGraded.problems[localIndex];
          if (gp.correct === true)  { fillStyle = '#28a745'; showCheck = true; }
          if (gp.correct === false) { fillStyle = '#dc3545'; showCross = true; }
        }

        var labelY = ly;
        var markerY = ly + 18;
        if (ctx.canvas && typeof ctx.canvas.height === 'number') {
          var maxMarkerY = ctx.canvas.height - 6;
          if (markerY > maxMarkerY) {
            var delta = markerY - maxMarkerY;
            labelY -= delta;
            markerY -= delta;
          }
        }

        // ✓ or ✗ drawn below the label text
        var markerYOffset = showCheck || showCross ? 22 : 0;
        
        if (!chosen) {
          // Draw a clear, clickable pill background for unanswered items
          ctx.beginPath();
          ctx.font = 'bold 18px sans-serif';
          var textWidth = ctx.measureText(label).width;
          var w = Math.max(32, textWidth + 12);
          var h = 28;
          var rx = lx - w/2;
          var ry = labelY - 20;
          var rConfig = 6;
          ctx.moveTo(rx + rConfig, ry);
          ctx.lineTo(rx + w - rConfig, ry);
          ctx.quadraticCurveTo(rx + w, ry, rx + w, ry + rConfig);
          ctx.lineTo(rx + w, ry + h - rConfig);
          ctx.quadraticCurveTo(rx + w, ry + h, rx + w - rConfig, ry + h);
          ctx.lineTo(rx + rConfig, ry + h);
          ctx.quadraticCurveTo(rx, ry + h, rx, ry + h - rConfig);
          ctx.lineTo(rx, ry + rConfig);
          ctx.quadraticCurveTo(rx, ry, rx + rConfig, ry);
          ctx.closePath();
          
          ctx.fillStyle = '#fefce8';
          ctx.fill();
          ctx.strokeStyle = '#facc15';
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.fillStyle = '#ca8a04';
          ctx.fillText(label, lx, labelY);
        } else {
          // Answered slot — render properly based on analysis type
          var analysisType = definition.getAnalysisType ? definition.getAnalysisType() : 'roman';
          if (analysisType === 'figured_bass') {
            // Convert to Sebastian font display format (mirrors stave_notater.drawThoroughbass)
            var lines = label.split('/').map(function(line) {
              if (line === '\u00b07') return '/';
              if (line === '6+') return '&';
              if (line === '5+') return '%';
              if (line === '4+') return '$';
              if (line === '2+') return '"';
              if (line.slice(0, 2) === '##') return ('x ' + line.slice(2)).trim();
              if (line.slice(0, 1) === '#') return ('# ' + line.slice(1)).trim();
              if (line.slice(0, 2) === 'bb') return ('a ' + line.slice(2)).trim();
              if (line.slice(0, 1) === 'b') return ('b ' + line.slice(1)).trim();
              if (line.slice(0, 1) === 'n') return ('n ' + line.slice(1)).trim();
              return line;
            });
            ctx.font = '28px Sebastian';
            ctx.fillStyle = fillStyle;
            ctx.textAlign = 'center';
            var skip = 14;
            var topY = labelY - (lines.length - 1) * skip;
            for (var li = 0; li < lines.length; li++) {
              ctx.fillText(lines[li], lx, topY + li * skip);
            }
          } else {
            ctx.font = '18px JazzSerifs';
            ctx.fillStyle = fillStyle;
            ctx.fillText(label, lx, labelY);
          }
        }

        if (showCheck || showCross) {
          ctx.font = 'bold 15px sans-serif';
          ctx.fillText(showCheck ? '✓' : '✗', lx, markerY);
        }
      }

      if (identMode === 'submit' && typeof this._updateIdentificationProgressUI === 'function') {
         this._updateIdentificationProgressUI(answeredCount, visibleSlotCount);
      }

      ctx.font = origFont;
      ctx.fillStyle = origFillStyle;
      ctx.textAlign = origTextAlign;
      ctx.textBaseline = origTextBaseline;
      ctx.lineWidth = origLineWidth;
    },

    _updateIdentificationProgressUI: function(answeredCount, totalCount) {
      var $btn = $('#identification-submit');
      if ($btn.length === 0) return;

      var $progContainer = $('#ident-progress-container');
      if ($progContainer.length === 0) {
          $progContainer = $('<div id="ident-progress-container" style="width: 250px; margin: 0 auto 15px; background: #e2e8f0; border-radius: 9999px; height: 6px; overflow: hidden; display: none;">' +
                           '<div id="ident-progress-bar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); transition: width 0.3s ease;"></div>' +
                           '</div>');
          $('#identification-actions').prepend($progContainer);
          
          if ($('#ident-premium-css').length === 0) {
              $('<style id="ident-premium-css">' +
                '#identification-submit {' +
                '  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);' +
                '  color: white;' +
                '  border: none;' +
                '  border-radius: 22px;' +
                '  padding: 10px 36px;' +
                '  font-size: 16px;' +
                '  font-weight: 600;' +
                '  cursor: default;' +
                '  opacity: 0.45;' +
                '  letter-spacing: 0.02em;' +
                '} ' +
                '#identification-submit.ready {' +
                '  cursor: pointer;' +
                '  opacity: 1;' +
                '  box-shadow: 0 4px 12px rgba(0, 198, 255, 0.45);' +
                '  transition: box-shadow 0.2s, opacity 0.2s;' +
                '} ' +
                '#identification-submit.ready:not(.hint-pulse):hover {' +
                '  box-shadow: 0 6px 18px rgba(0, 198, 255, 0.65);' +
                '}' +
                '#identification-submit.hint-pulse {' +
                '  animation: ident-hint-pulse 1.4s ease-in-out infinite !important;' +
                '  transition: none !important;' +
                '}' +
                '@keyframes ident-hint-pulse {' +
                '  0%,100% { box-shadow: 0 4px 12px rgba(0,198,255,0.45); opacity:1; }' +
                '  50% { box-shadow: 0 0 28px 6px rgba(0,198,255,0.85); opacity:1; }' +
                '}' +
                '</style>').appendTo('head');
          }
      }

      // Hide progress bar only after the exercise is fully completed (sealed)
      if (totalCount === 0 || this.exerciseContext.sealed) {
          $progContainer.hide();
          $btn.hide(); // Hide button when completed/sealed
          return;
      }

      var allProblems = this.exerciseContext.getDefinition().getProblems() || [];
      var visibleProblems = _.filter(allProblems, function(p) { return !p.hidden; });
      var globalTotal = visibleProblems.length;
      var answers = (this.exerciseContext.grader && this.exerciseContext.grader.answers) ? this.exerciseContext.grader.answers : {};
      var globalAnswered = 0;
      for (var i = 0; i < allProblems.length; i++) {
          if (allProblems[i] && !allProblems[i].hidden && answers && typeof answers.hasOwnProperty === 'function' && answers.hasOwnProperty(i) && answers[i] !== null && answers[i] !== '') {
              globalAnswered++;
          }
      }

      $progContainer.show();
      var progressPct = globalTotal > 0 ? (globalAnswered / globalTotal) * 100 : 0;
      $('#ident-progress-bar').css('width', progressPct + '%');

      var isLastPage = this.exerciseContext.getIdentPage && this.exerciseContext.getTotalIdentPages
         ? (this.exerciseContext.getIdentPage() >= this.exerciseContext.getTotalIdentPages() - 1)
         : true;

      // The button only cares if the CURRENT page is complete
      if (answeredCount >= totalCount) {
          $btn.addClass('ready').text(isLastPage ? 'Check' : 'Next Page');
          if (!isLastPage) {
            $btn.addClass('hint-pulse');
          } else {
            $btn.removeClass('hint-pulse');
          }
      } else {
          $btn.removeClass('ready hint-pulse').text('Complete Analysis');
      }
    },

    /**
     * Called when the student clicks Submit (submit mode only).
     */
    onSubmitIdentification: function () {
      var graded = this.exerciseContext.submitIdentPage({ fromUI: true, mode: this._currentMode });
      if (graded && graded.completedExercise && graded.result === 'correct') {
        this._launchConfetti();
      }
    },

    _launchConfetti: function () {
      var canvas = document.createElement('canvas');
      canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:9999;';
      document.body.appendChild(canvas);
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      var ctx = canvas.getContext('2d');
      var particles = [];
      var colors = ['#4facfe','#00f2fe','#f6d365','#fda085','#84fab0','#8fd3f4','#a18cd1','#fbc2eb'];
      for (var i = 0; i < 120; i++) {
        particles.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height * 0.4,
          r: Math.random() * 7 + 3,
          color: colors[Math.floor(Math.random() * colors.length)],
          vx: (Math.random() - 0.5) * 4,
          vy: Math.random() * 3 + 2,
          alpha: 1,
          rot: Math.random() * 360,
          rotV: (Math.random() - 0.5) * 6,
        });
      }
      var startTime = Date.now();
      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        var elapsed = Date.now() - startTime;
        particles.forEach(function(p) {
          p.x += p.vx; p.y += p.vy; p.vy += 0.08; p.rot += p.rotV;
          p.alpha = Math.max(0, 1 - elapsed / 2000);
          ctx.save();
          ctx.globalAlpha = p.alpha;
          ctx.translate(p.x, p.y);
          ctx.rotate(p.rot * Math.PI / 180);
          ctx.fillStyle = p.color;
          ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.5);
          ctx.restore();
        });
        if (elapsed < 2200) {
          requestAnimationFrame(draw);
        } else {
          document.body.removeChild(canvas);
        }
      }
      draw();
    },

    _onIdentKeyDown: function (e) {
      if (!this._isIdentificationLikeExercise()) return;
      if ($(e.target).is("input, textarea, select") || e.target.isContentEditable) return;
      if (e.key === "ArrowRight") {
        e.preventDefault();
        this.exerciseContext.goToIdentPage(this.exerciseContext.getIdentPage() + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        this.exerciseContext.goToIdentPage(this.exerciseContext.getIdentPage() - 1);
      }
    },

    renderModeToggle: function () {
      if (this._modeLocked || this._currentMode === "test") {
        $("#ident-mode-container").remove();
        return;
      }

      var $container = $("#ident-mode-container");
      if ($container.length === 0) {
        $container = $('<div id="ident-mode-container" class="ident-mode-toggle"></div>');
        $("#identification-actions").append($container);

        if ($("#ident-toggle-css").length === 0) {
          $("<style id='ident-toggle-css'>" +
            ".ident-mode-toggle { display: flex; justify-content: center; margin-top: 15px; font-family: sans-serif; }" +
            ".mode-switch { position: relative; display: inline-flex; background: #f1f5f9; border-radius: 999px; padding: 4px; border: 1px solid #e2e8f0; }" +
            ".mode-option { padding: 6px 16px; font-size: 13px; font-weight: 500; color: #64748b; cursor: pointer; transition: all 0.2s; border-radius: 999px; z-index: 1; }" +
            ".mode-option.active { color: #0f172a; background: white; shadow: 0 1px 3px rgba(0,0,0,0.1); }" +
            ".mode-option:hover:not(.active) { color: #475569; }" +
            "</style>").appendTo("head");
        }
      }

      var self = this;
      $container.empty();
      var $switch = $('<div class="mode-switch"></div>');
      
      var modes = [
        { id: "practice", label: "Practice" },
        { id: "submit", label: "Submit" }
      ];

      _.each(modes, function (m) {
        var $opt = $('<div class="mode-option"></div>').text(m.label).data("mode", m.id);
        if (self._currentMode === m.id) {
          $opt.addClass("active");
        }
        $opt.on("click", function () {
          self.onToggleMode(m.id);
        });
        $switch.append($opt);
      });

      $container.append($switch);
    },

    onToggleMode: function (newMode) {
      if (this._modeLocked || this._currentMode === "test" || this._currentMode === newMode) {
        return;
      }
      this._currentMode = newMode;
      this.exerciseContext.sessionMode = newMode;
      
      // Toggle Submit button visibility
      if (newMode === 'submit') {
        $('#identification-submit').show();
      } else {
        $('#identification-submit').hide();
        $('#ident-progress-container').hide();
      }

      this.renderModeToggle();
      this.render(); // Re-render to update UI elements
    },
    /**
     * Chorale mode setup: ensure grader is initialized; keep display settings
     */
    initChoraleMode: function () {
      var maxMeasures = 4;
      this._chorale = { maxMeasures: maxMeasures, startMeasure: 0 };
      try {
        var def = this.exerciseContext.getDefinition();
        if (def.isChorale && def.isChorale() && this.exerciseContext.grader && this.exerciseContext.grader.initFromDefinition) {
          this.exerciseContext.grader.initFromDefinition(def);
        }
      } catch (e) {
        console.warn("[Chorale] initChoraleMode: failed to init grader", e);
      }
    },
    /**
     * Renders the grand staff and everything on it.
     *
     * @return this
     */
    render: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;
      this.clear();
      this.renderStaves(exercise_midi_nums);
      this.renderExerciseStatus();
      if (this._isIdentificationLikeExercise()) {
        this.renderExerciseText();
      }

      // Playback controls — only for chorale exercise types (idempotent)
      var definition = this.exerciseContext.getDefinition();
      if (definition.isChorale() || (definition.isChoraleIdentification && definition.isChoraleIdentification())) {
        var $toolbar = $("#staff-toolbar");
        if ($toolbar.length) {
          var self = this;
          renderPlaybackControls($toolbar, this.scorePlayer, function () {
            return self._calculatePlaybackOffsets();
          });
        }
      }
      this._calculatePlaybackOffsets();
      this.autoScroll();

      // Simple Debug Overlay
      if (window.location.search.indexOf('debug=1') !== -1) {
        this._renderDebugOverlay();
      }

      return this;
    },
    
    _renderDebugOverlay: function () {
      $('#id-debug-overlay').remove();
      var problems = this.exerciseContext.getDefinition().getProblems();
      var overlay = $('<div id="id-debug-overlay" style="position:fixed; top:10px; right:10px; background:rgba(0,0,0,0.8); color:white; padding:10px; font-size:10px; z-index:9999; max-height:80vh; overflow-y:auto; border-radius:5px; font-family:monospace;"></div>');
      overlay.append('<h3 style="margin:0 0 10px 0;">UMTO Logic Auditor</h3>');
      var table = $('<table border="1" style="border-collapse:collapse; width:100%;"><tr><th>Idx</th><th>Off</th><th>Ans</th><th>Tgt</th></tr></table>');
      _.each(problems, function(p, i) {
        var row = $('<tr></tr>');
        row.append('<td style="padding:2px;">'+i+'</td>');
        row.append('<td style="padding:2px;">'+p.onset.toFixed(2)+'</td>');
        row.append('<td style="padding:2px;">'+p.answer+'</td>');
        row.append('<td style="padding:2px;">'+(p.hidden?'No':'Yes')+'</td>');
        table.append(row);
      });
      overlay.append(table);
      $('body').append(overlay);
    },
    /**
     * Renders textual prompt for the exercise.
     *
     * @return this
     */
    renderExerciseStatus: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $statusEl = $("#exercise-status-and-tempo");
      var $passedEl = $("#passed-status");
      var statusTpl = _.template(
        // not called: time_to_complete and more
        `<p><span id="exercise-status" class="status-pill" style="background-color:<%= status_color %>"><%= status_text %></span></p>
                <% if (typeof(tempo_mean) !== "undefined" && tempo_mean != "" && typeof(tempo_rating) !== "undefined" && typeof(tempo_display_factor) !== "undefined") { %>
                    <p>Tempo&nbsp;<%= ["", "erratic", "unsteady", "steady", "very&nbsp;steady", "perfectly&nbsp;steady"][tempo_rating.length] %> at <%= Math.round(tempo_mean * tempo_display_factor) %>&nbsp;b.p.m.</p>
                <% } %>`
      );
      var passedTpl = `<span class="status-pill" id="exercise-passed-status">Exercise Passed</span>`;
      // the tempo verbiage above should match what is separately coded for my activity
      var html = "";
      var tpl_data = {};

      var status_map = {};
      status_map[exc.STATE.READY] = {
        text: "Ready",
        color: "#333333",
      };
      status_map[exc.STATE.WAITING] = {
        text: "Keep going",
        color: "#FF7F00",
      };
      status_map[exc.STATE.INCORRECT] = {
        text: "Fix the error",
        color: "#990000",
      };
      status_map[exc.STATE.FINISHED] = {
        text: "Go again",
        color: "#FFB700",
      };
      status_map[exc.STATE.CORRECT] = {
        text: "Passed",
        color: "#4C9900",
      };

      tpl_data.exercise_list = exc.definition.getExerciseList();
      tpl_data.exercise_num = tpl_data.exercise_list.reduce(function (
        selected,
        current,
        index
      ) {
        return selected < 0 && current.selected ? index + 1 : selected;
      },
      -1);
      tpl_data.status_text = status_map[exc.state].text;
      tpl_data.status_color = status_map[exc.state].color;

      $(".playlist-nav-links").css("display", "none");
      if ( // HOW DOES THIS WORK
        $("#playlist-passed-status").length == 0 &&
        definition.settings.definition.exerciseIsPerformed &&
        definition.settings.definition.exerciseErrorCount == 0
      ) {
        $passedEl.html(passedTpl);
      } else {
        $("#exercise-passed-status").hide();
      }
      switch (exc.state) {
        case exc.STATE.CORRECT:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
            tpl_data.tempo_display_factor = 1;
            try {
              // get beat information from time signature
              const time_sig = definition.exercise.timeSignature;
              const time_sig_numerator = Number(time_sig.split("/")[0]);
              let tempo_display_factor = Number(time_sig.split("/")[1]);
              if (time_sig_numerator > 3 && time_sig_numerator % 3 == 0) {
                // compound meter
                tempo_display_factor /= 3;
              }
              if (!isNaN(tempo_display_factor)) {
                tpl_data.tempo_display_factor = tempo_display_factor;
              }
            } catch (error) {
              console.log("Unable to retrieve beat value from time signature");
            }
          }
          // If this is the last exercise, display the nav links
          if (!this.exerciseContext.definition.exercise.nextExercise)
            $(".playlist-nav-links").css("display", "inline-flex");
          break;
        case exc.STATE.FINISHED:
          if (exc.hasTimer()) {
            tpl_data.time_to_complete = exc.getExerciseDuration();
            tpl_data.min_tempo = exc.getMinTempo();
            tpl_data.max_tempo = exc.getMaxTempo();
            tpl_data.tempo_mean = exc.getTempoMean();
            tpl_data.tempo_rating = exc.getTempoRating();
          }
          break;
        case exc.STATE.READY:
        default:
          break;
      }

      html = statusTpl(tpl_data);
      $statusEl.html(html);
      return this;
    },
    renderExerciseInfo: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $infoEl = $("#exercise-info");
      var tpl = _.template(
        `<% if (typeof(exercise_list) !== "undefined" && exercise_list.length > 0) { %>
          <p>Exercise <%= exercise_num %> of <%= exercise_list.length %></p>
        <% } %>`
      );
      var html = "";
      var tpl_data = {};

      if (exc.definition.exercise.performing_course) {
        tpl_data.exercise_list = exc.definition.getExerciseList();
        tpl_data.exercise_num = 1;
        for (let i = 0; i < tpl_data.exercise_list.length; i++) {
          if (tpl_data.exercise_list[i].selected) {
            tpl_data.exercise_num = i + 1;
            break;
          }
        }
      } else {
        // get ID?
      }

      html = tpl(tpl_data);
      $infoEl.html(html);

      return this;
    },
    renderExerciseText: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $textEl = $("#exercise-text");
      var tpl = _.template(
        `<% if (typeof(prompt_text) == "string") { %>
                    <%= prompt_text %>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      tpl_data.prompt_text = FontParser.parseHTMLFiguredBass(
        exc.definition.getExerciseText
          ? exc.definition.getExerciseText()
          : (exc.definition.getIntro ? exc.definition.getIntro() : "")
      );

      html = tpl(tpl_data);

      // Append page indicator for paged identification exercises
      if (this._isIdentificationLikeExercise && this._isIdentificationLikeExercise()) {
        var totalPages = exc.getTotalIdentPages ? exc.getTotalIdentPages() : 1;
        if (totalPages > 1) {
          var currentPage = exc.getIdentPage ? exc.getIdentPage() : 0;
          html += '<span class="page-indicator" style="margin-left:1em;color:#888;font-size:0.9em;">Page ' + (currentPage + 1) + ' of ' + totalPages + '</span>';
        }
      }

      $textEl.html(html);

      return this;
    },
    renderExerciseHistory: function () {
      var exc = this.exerciseContext;
      var definition = exc.getDefinition();
      var $historyEl = $("#exercise-history");
      var tpl = _.template(
        `<% if (false && is_performed && typeof(latest_err_count) == "integer" && latest_err_count == 0) { %>
                    <p>PASSED on most recent attempt</p>
                <% } %>`
      );
      var html = "";
      var tpl_data = {};

      $.ajax({
        type: "GET",
        url:
          window.location.origin +
          "/ajax" +
          window.location.pathname +
          "history/",
        async: false,
        success: function (response) {
          if (!response["valid"]) {
            var exerciseData = JSON.parse(response);
            tpl_data.is_performed = exerciseData.exerciseIsPerformed;
            tpl_data.latest_err_count = exerciseData.exerciseErrorCount;
          }
        },
        error: function (error) {
          alert("An error occurred while getting the exercise history.");
        },
      });

      html = tpl(tpl_data);
      $historyEl.html(html);

      return this;
    },
    /**
     * Clears the sheet.
     *
     * @return this
     */
    clear: function () {
      this.vexRenderer.getContext().clear();
      return this;
    },
    /**
     * Renders each individual stave.
     *
     * @return this
     */
    renderStaves: function (exercise_midi_nums) {
      exercise_midi_nums = exercise_midi_nums || false;
      var definition = this.exerciseContext.getDefinition();
      var score = definition.getScore();
      var isChoraleLike = (definition.isChorale() || definition.isChoraleIdentification());
      
      // If it's a UMTO chorale, always re-convert to ensure splitting is fresh and uses MeasureEngine.
      // This fixes cases where the database might have a single 'blob' measure.
      if (isChoraleLike && score && score.umto) {
        console.log("[ID] Forcing UMTO conversion for consistent measure splitting");
        score = this._convertUMTOToProcessedScore(score.umto);
      }

      var hasMeasures = !!(score && score.measures && score.measures.length > 0);
      
      // Ensure score has metadata for VexFlowAdapter
      if (score && hasMeasures) {
        score.metadata = score.metadata || {};
        if (score.metadata.meter && !score.metadata.time) score.metadata.time = score.metadata.meter;
        if (!score.metadata.time) score.metadata.time = "4/4";
      }

      console.log("[ID] renderStaves. isChoraleLike:", isChoraleLike, "type:", definition.getType(), "hasMeasures:", hasMeasures);
      
      // Use VexFlow adapter for chorale exercises
      if (isChoraleLike && hasMeasures) {
        console.log("[ID] Using VexFlowAdapter (Chorale Model) for rendering");
        if (score && score.measures && score.measures.length > 0) {
          var self = this;
          this._identWindowLayout = {};
          this._identWindowLayoutByOnset = {};
          this._updateChoraleViewport(score);
          var canvas = this.el[0];
          console.log("[ID] Canvas:", canvas, "Width:", canvas.width, "Height:", canvas.height);
          var ctx = this.vexRenderer.getContext();
          console.log("[ID] Context:", ctx);
          
          var display = definition.getDisplay() || {};
          var analyzeConfig = _.cloneDeep(this.getAnalyzeConfig() || {});
          var wantsRomans = !!display.showRomans;
          var wantsFigures = !!display.showFigures;
          var wantsChordLabels = !!display.showChordLabels;
          var isAnalysisMatchMode = !!(definition.isAnalysisMatch && definition.isAnalysisMatch());
          var wantsNoteNames = !!display.showNoteNames || isAnalysisMatchMode;


          // In chorale identification mode the figures/Romans ARE the student's
          // answers — rendering them via VexFlow would spoil the exercise.
          // The identification overlay draws "?" slots instead.
          if (this._isChoraleIdentificationExercise()) {
            wantsRomans = false;
            wantsFigures = false;
            wantsChordLabels = false;
            wantsNoteNames = false;
          }

          var wantsAnalysis = wantsRomans || wantsFigures || wantsChordLabels || wantsNoteNames;

          // Preserve legacy chorale behavior that force-enables roman numerals,
          // but do not force overlays for chorale_identification.
          if (!wantsAnalysis && definition.isChorale && definition.isChorale() && !isAnalysisMatchMode) {
            wantsRomans = true;
            wantsAnalysis = true;
          }
          // Ensure analysis renderer is not suppressed
          if (!display.analysisRenderer) {
            display.analysisRenderer = 'notater';
          }
          if (wantsAnalysis) {
            analyzeConfig.enabled = true;
            analyzeConfig.mode = analyzeConfig.mode || {};
            if (wantsRomans) {
              analyzeConfig.mode.roman_numerals = true;
            }
            if (wantsFigures) {
              analyzeConfig.mode.thoroughbass = true;
              if (display.figureStyle === "figures_abbrev") {
                analyzeConfig.mode.abbreviate_thoroughbass = true;
              }
            }
            if (wantsChordLabels) {
              analyzeConfig.mode.chord_labels = true;
            }
            if (wantsNoteNames) {
              analyzeConfig.mode.note_names = true;
            }
          }

          var startMeasure =
            (this._chorale && typeof this._chorale.startMeasure === "number"
              ? this._chorale.startMeasure
              : 0);
          var staffYOffset = 20;
          var playedNoteIdsForRender =
            (this.exerciseContext && this.exerciseContext.grader && this.exerciseContext.grader.getPlayedNoteIds)
              ? this.exerciseContext.grader.getPlayedNoteIds()
              : null;

          // In chorale-identification mode we want notation rendered in black from the start.
          if (this._isChoraleIdentificationExercise()) {
            playedNoteIdsForRender = new Set();
            _.each(ScoreTimeline.buildTimeline(score) || [], function (ev) {
              if (ev && typeof ev.id === 'number') {
                playedNoteIdsForRender.add(ev.id);
              }
            });
          }

          console.log("[ID] Calling VexFlowAdapter.render with score:", score, "analyzeConfig:", analyzeConfig);
          VexFlowAdapter.render(score, this.vexRenderer, {
            width: canvas.width,
            height: canvas.height,
            maxMeasures: (this._chorale && this._chorale.maxMeasures) || 4,
            startMeasure: startMeasure,
            playedNoteIds: playedNoteIdsForRender,
            showNotation: display.showNotation !== undefined ? display.showNotation : true,
            // Analysis wiring for chorale path (Notater bridge inside adapter)
            analyzeConfig: analyzeConfig,

            keySignature: this.keySignature,
            analysisRenderer: display.analysisRenderer || "notater", // notater|adapter|none
            staffYOffset: staffYOffset,
            isAnalysisMatch: isAnalysisMatchMode,
            onWindowPosition: function (slot) {
              if (!slot || typeof slot.windowIndex !== "number") {
                return;
              }
              console.log("[ID] onWindowPosition received:", slot.windowIndex, slot.x, slot.y);
              self._identWindowLayout[slot.windowIndex] = slot;
              // Index by "measureIndex:pageLocalOnset" for cross-page playback highlight lookup.
              // The adapter emits absolute measureIndex and page-local onset.
              if (slot.measureIndex !== null && slot.measureIndex !== undefined && slot.onset !== null && slot.onset !== undefined) {
                self._identWindowLayoutByOnset[slot.measureIndex + ":" + slot.onset] = slot;
              }
            },
          });
          console.log("[ID] VexFlowAdapter.render finished.");



          if (this._isIdentificationLikeExercise()) {
            this.drawIdentificationLabels();
          }
        }
        return this;
      }
      
      // Legacy rendering for non-chorale exercises
      console.log("[ID] Using Legacy Renderer (FALLBACK)");
      const show_barlines = true;

      var i,
        len,
        stave,
        _staves = this.staves;
      var _barlines = this.barlines;
      for (i = 0, len = _staves.length; i < len; i++) {
        stave = _staves[i];
        const exercise_view_bool = true;
        const append_barline = _barlines.indexOf(i) != -1 && show_barlines;
        stave.render(exercise_midi_nums, exercise_view_bool, append_barline);
      }

      if (this._isIdentificationLikeExercise()) {
        this.drawIdentificationLabels();
      }

      return this;
    },
    /**
     * Adjusts which measures are displayed for chorale exercises as the user advances.
     */
    _updateChoraleViewport: function (score) {
      if (
        !this._chorale ||
        !score ||
        !score.measures ||
        !score.measures.length
      ) {
        return;
      }
      // During playback page turns, honour the override and skip grader-based calculation.
      if (this._playbackOverridePage !== null && this._playbackOverridePage !== undefined) {
        this._chorale.startMeasure = this._playbackOverridePage;
        return;
      }
      var totalMeasures = score.measures.length;
      var maxMeasures = this._chorale.maxMeasures || 4;
      if (totalMeasures <= maxMeasures) {
        this._chorale.startMeasure = 0;
        return;
      }
      var activeMeasure = 0;
      // For chorale_identification, page index comes from exerciseContext directly.
      // For chorale (play-through), it comes from the grader.
      var context = this.exerciseContext;
      if (context && typeof context.getIdentPageOffset === "function" && this._isChoraleIdentificationExercise()) {
        if (typeof context.getIdentPage === "function") {
          var page = context.getIdentPage();
          activeMeasure = Math.max(0, Math.min(page * maxMeasures, totalMeasures - 1));
        }
      } else {
        var grader = context && context.grader;
        if (grader && typeof grader.getActiveMeasureIndex === "function") {
          var idx = grader.getActiveMeasureIndex();
          if (typeof idx === "number" && !isNaN(idx)) {
            activeMeasure = Math.max(0, Math.min(idx, totalMeasures - 1));
          }
        }
      }
      var block = Math.floor(activeMeasure / maxMeasures);
      var desiredStart = block * maxMeasures;
      var lastPossibleStart = Math.max(0, totalMeasures - maxMeasures);
      if (desiredStart > lastPossibleStart) {
        desiredStart = lastPossibleStart;
      }
      if (desiredStart < 0) {
        desiredStart = 0;
      }
      if (this._chorale.startMeasure !== desiredStart) {
        this._chorale.startMeasure = desiredStart;
      }
    },
    /**
     * Resets the staves.
     *
     * @return this
     */
    resetStaves: function () {
      this.staves = [];
      this.barlines = [];
      return this;
    },
    /**
     * Adds staves.
     *
     * @param {array} staves
     * @return this
     */
    addStaves: function (staves) {
      this.staves = this.staves.concat(staves);
      return this;
    },
    timeSignatureParsed: function (timeSignature) {
      if (!timeSignature) {
        return false;
      }
      let parsedSignature = timeSignature.split("/");
      if (parsedSignature.length != 2) {
        return false;
      }
      let topNum = parsedSignature[0].trim();
      let bottomNum = parsedSignature[1].trim();
      if (
        isNaN(topNum) ||
        isNaN(bottomNum) ||
        topNum != parseInt(topNum) ||
        bottomNum != parseInt(bottomNum)
      ) {
        return false;
      }
      return [topNum, bottomNum];
    },
    getsBarline: function (timeSignature = false, elapsedWholeNotes) {
      if (!elapsedWholeNotes > 0) {
        return false;
      }
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      return barCount == parseInt(barCount);
    },
    countElapsedBars: function (timeSignature = false, elapsedWholeNotes) {
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      return parseInt(barCount);
    },
    getBarRemainder: function (timeSignature = false, elapsedWholeNotes) {
      // not used
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      const barCount = (elapsedWholeNotes * ts[1]) / ts[0];
      if (isNaN(barCount) || barCount < 0) {
        return null;
      }
      return barCount % 1;
    },
    getWholeNoteRemainder: function (timeSignature = false, elapsedWholeNotes) {
      const ts = this.timeSignatureParsed(timeSignature);
      if (!ts) {
        return false;
      }
      if (elapsedWholeNotes <= 0) {
        return 0;
      }
      const remainder = ((elapsedWholeNotes * ts[1]) % ts[0]) / ts[1];
      if (isNaN(remainder) || remainder < 0) {
        return null;
      }
      return remainder;
    },
    /**
     * Updates and configures the staves.
     *
     * @return this
     */
    updateStaves: function () {
      var chord, treble, bass;
      var limit = 100; // arbitrary
      let bankSize = CHORD_BANK_SIZE;
      try {
        const custom_chord_bank_size = parseInt(this.getSemibrevesPerLine());
        if (
          typeof custom_chord_bank_size === "number" &&
          custom_chord_bank_size > 0
        ) {
          bankSize = custom_chord_bank_size;
        }
      } catch {
        console.log(
          "Failed to retrieve getSemibrevesPerLine property from Exercise definion."
        );
      }
      var display_items = this.getDisplayChords().items({
        limit: limit,
        reverse: false,
      });
      var exercise_items = this.getExerciseChords().items({
        limit: limit,
        reverse: false,
      });
      var staves = [];
      var barlines = [];
      var index = 0;
      var offset = 0;
      var count = display_items.length;
      var position = {
        index: index,
        count: count,
        offset: offset,
        maxCount: bankSize,
      };
      var display_chord;
      var exercise_chord;
      var treble_activeAlterations = Object.create(null);
      var bass_activeAlterations = Object.create(null);
      const timeSignature = this.getTimeSignature();
      const barlineSpace = 0.25; // relative to width of whole note

      // scrolling exercise view
      var scroll_exercise = false;
      var pageturns = [0];

      let rhythmValues = display_items.map((item) => item.chord._rhythmValue);
      let availableSpace = bankSize;

      const endOfBarWholeNoteCounts = [];
      if (timeSignature) {
        const wholeNoteSum = rhythmValues
          .map((item) => this.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        const barCount = this.countElapsedBars(timeSignature, wholeNoteSum);
        const ts = this.timeSignatureParsed(timeSignature);
        for (var i = 1, len = barCount; i <= len; i++) {
          endOfBarWholeNoteCounts.push((i * ts[0]) / ts[1]);
        }
      }

      for (var i = 0, len = rhythmValues.length; i < len; i++) {
        let neededSpace = this.getVisualWidth(rhythmValues[i]);

        let elapsedWholeNotes = rhythmValues
          .slice(0, i + 1)
          .map((item) => this.getWholeNoteCount(item))
          .reduce((x, y) => x + y);
        if (endOfBarWholeNoteCounts.includes(elapsedWholeNotes)) {
          neededSpace += barlineSpace;
        }
        if (neededSpace > availableSpace) {
          availableSpace = bankSize - neededSpace; // overlap space
          pageturns.push(i);
          scroll_exercise = true;
        }
        availableSpace -= neededSpace;
      }

      let previous_whole_note_count = 0;
      if (scroll_exercise) {
        let cursor = this.getInputChords()._currentIndex;
        var page_start = pageturns
          .filter(function (x, idx) {
            return x <= cursor;
          })
          .pop();
        var next_page =
          pageturns.filter(function (x, idx) {
            return x > cursor;
          })[0] || false;
        if (page_start > 0) {
          // create overlap (start new page with completed chord)
          page_start -= 1;
          // next_page -= 1; //unwise
        }

        position.offset = page_start;
        const previous_items = display_items.slice(0, page_start);

        if (next_page) {
          display_items = display_items.slice(page_start, next_page);
          exercise_items = exercise_items.slice(page_start, next_page);
        } else {
          display_items = display_items.slice(page_start);
          exercise_items = exercise_items.slice(page_start);
        }

        for (var i = 0, len = previous_items.length; i < len; i++) {
          let rhythm_value = null;
          if (previous_items[i].chord.settings.rhythm) {
            rhythm_value = previous_items[i].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          previous_whole_note_count += this.getWholeNoteCount(rhythm_value);
        }
      }

      // The first bar is a special case: it's reserved to show the
      // clef and key signature and nothing else.
      let first_page = true;
      if (previous_whole_note_count > 0) {
        first_page = false;
      }
      treble = this.createDisplayStave("treble", _.clone(position), first_page);
      bass = this.createDisplayStave("bass", _.clone(position), first_page);
      position.index += 1;
      treble.connect(bass);
      staves.push(treble);

      var treble_alterationHistory = Object.create(null);
      var bass_alterationHistory = Object.create(null);

      // now add the staves for showing the notes
      for (var i = 0, len = display_items.length; i < len; i++) {
        let elapsedWidthUnits = 0;
        let elapsedWholeNotes = 0;
        let extraWidth = 0;
        for (var j = 0; j < i; j++) {
          var rhythm_value = null;
          if (display_items[j].chord.settings.rhythm) {
            rhythm_value = display_items[j].chord.settings.rhythm;
          } else {
            rhythm_value = DEFAULT_RHYTHM_VALUE;
          }
          elapsedWidthUnits += this.getVisualWidth(rhythm_value);
          elapsedWholeNotes += this.getWholeNoteCount(rhythm_value);
        }

        // spacing for barlines
        const complement_of_first_bar = this.getWholeNoteRemainder(
          timeSignature,
          previous_whole_note_count
        );
        const elapsedBarlines = this.countElapsedBars(
          timeSignature,
          elapsedWholeNotes + complement_of_first_bar - 0.01
        );
        if (elapsedBarlines) {
          elapsedWidthUnits += barlineSpace * elapsedBarlines;
        }

        // now take account of previous music for proper barring
        elapsedWholeNotes += previous_whole_note_count;

        var curr_value = null;
        if (display_items[i].chord.settings.rhythm) {
          curr_value = display_items[i].chord.settings.rhythm;
        } else {
          curr_value = DEFAULT_RHYTHM_VALUE;
        }
        if (i < len) {
          if (this.getsBarline(timeSignature, elapsedWholeNotes)) {
            if (i > 0) {
              // new bar begins here but not new system
              // draw barline at left
              barlines.push(i + 1);
              // add space to left of barline
              elapsedWidthUnits += barlineSpace;
            }
            // RESET # n b
            treble_activeAlterations = Object.create(null);
            bass_activeAlterations = Object.create(null);
          }
          if (
            this.getsBarline(
              timeSignature,
              elapsedWholeNotes + this.getWholeNoteCount(curr_value)
            )
          ) {
            // bar is completed here: add space
            extraWidth += barlineSpace;
          }
        }

        treble_alterationHistory[i] = treble_activeAlterations;
        bass_alterationHistory[i] = bass_activeAlterations;

        display_chord = display_items[i].chord;
        exercise_chord = exercise_items[i].chord;
        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          treble_activeAlterations,
          extraWidth
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          display_chord,
          exercise_chord,
          elapsedWidthUnits,
          bass_activeAlterations,
          extraWidth
        );
        position.index += 1;
        treble.connect(bass);
        staves.push(treble);

        let treble_merged = {
          ...treble_activeAlterations,
          ...treble.noteFactory.bequestAlterations,
        };
        let treble_cancellations = treble.noteFactory.bequestCancellations;
        for (let j = 0, len_j = treble_cancellations.length; j < len_j; j++) {
          delete treble_merged[treble_cancellations[j]];
        }
        treble_activeAlterations = treble_merged;

        let bass_merged = {
          ...bass_activeAlterations,
          ...bass.noteFactory.bequestAlterations,
        };
        let bass_cancellations = bass.noteFactory.bequestCancellations;
        for (let j = 0, len_j = bass_cancellations.length; j < len_j; j++) {
          delete bass_merged[bass_cancellations[j]];
        }
        bass_activeAlterations = bass_merged;
      }

      treble.noteFactory.alterationHistory = treble_alterationHistory;
      bass.noteFactory.alterationHistory = bass_alterationHistory;

      this.resetStaves();
      this.addStaves(staves);
      this.barlines = barlines;

      return this;
    },
    /**
     * Creates a stave to display the clef, key signature, etc.
     *
     * @param {string} clef
     * @param {object} position
     * @return {Stave}
     */
    createDisplayStave: function (clef, position, first_page = true) {
      var stave = new Stave(clef, position);
      var stave_notater = this.createStaveNotater(clef, {
        stave: stave,
        keySignature: this.keySignature,
        analyzeConfig: this.getAnalyzeConfig(),
      });

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      if (first_page && this.timeSignatureParsed(this.timeSignature)) {
        // console.log(this.timeSignatureParsed(this.timeSignature).join('/'));
        stave.setTimeSignature(
          this.timeSignatureParsed(this.timeSignature).join("/")
        );
      } else {
        stave.setTimeSignature(false);
      }
      stave.setNotater(stave_notater);
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          this.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePosition();

      return stave;
    },
    getVisualWidth: function (rhythm_value) {
      if (rhythm_value === "w") {
        return 1;
      } else if (rhythm_value === "W") {
        return 1.25;
      } else if (rhythm_value === "H") {
        return 0.75;
      } else if (rhythm_value === "h") {
        return 0.675;
      } else if (rhythm_value === "Q") {
        return 0.5;
      } else if (rhythm_value === "q") {
        return 0.375;
      } else if (rhythm_value === "8") {
        return 0.25;
      } else {
        console.log("Unknown rhythm_value passed to getVisualWidth");
        return 1;
      }
    },
    getWholeNoteCount: function (rhythm_value) {
      if (!rhythm_value) return 0.25;
      // Use MeasureEngine if it understands the format, otherwise fallback
      if (typeof rhythm_value === 'string') {
        return MeasureEngine.getWholeNoteCount(rhythm_value, 0);
      }
      return 0.25;
    },
    /**
     * Creates a stave to display notes.
     *
     * @param {string} clef
     * @param {object} position
     * @param {Chord} chord
     * @return {Stave}
     */
    createNoteStave: function (
      clef,
      position,
      displayChord,
      exerciseChord,
      elapsedWidthUnits,
      activeAlterations,
      extraWidth = 0
    ) {
      var stave = new Stave(clef, position);
      var widthUnits = null;
      if (exerciseChord.settings.rhythm) {
        var rhythm_value = exerciseChord.settings.rhythm;
        if (rhythm_value == null) {
          rhythm_value = DEFAULT_RHYTHM_VALUE;
        }
        widthUnits = this.getVisualWidth(rhythm_value) + extraWidth;
      }

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      // timeSignature not required here
      // stave.setFirstBarWidth(this.keySignature);
      stave.setNoteFactory(
        new ExerciseNoteFactory({
          clef: clef,
          chord: displayChord,
          keySignature: this.keySignature,
          highlightConfig: this.getHighlightConfig(),
          activeAlterations: activeAlterations,
        })
      );
      stave.setNotater(
        this.createStaveNotater(clef, {
          stave: stave,
          chord: exerciseChord,
          keySignature: this.keySignature,
          analyzeConfig: this.getAnalyzeConfig(),
        })
      );
      stave.setMaxWidth(this.getWidth());

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        const minimum = 0;
        const hasTimeSig =
          this.timeSignatureParsed(this.timeSignature) != false;
        stave.setFirstBarWidth(staffSig, minimum, hasTimeSig);
      }
      stave.updatePositionWithRhythm(widthUnits, elapsedWidthUnits);
      stave.updateAlterations(activeAlterations);

      return stave;
    },
    /**
     * Creates an instance of StaveNotater.
     *
     * @param {string} clef The clef, treble|bass, to create.
     * @param {object} config The config for the StaveNotater.
     * @return {object}
     */
    createStaveNotater: function (clef, config) {
      return StaveNotater.create(clef, config);
    },
    /**
     * Returns the width of the sheet.
     *
     * @return {number}
     */
    getWidth: function () {
      return this.el.width();
    },
    /**
     * Returns the height of the sheet.
     *
     * @return {number}
     */
    getHeight: function () {
      return this.el.height();
    },
    /**
     * Returns the analysis settings of the sheet.
     *
     * @return {object}
     */
    getAnalyzeConfig: function () {
      return this.parentComponent.analyzeConfig;
    },
    /**
     * Returns the highlight settings of the sheet.
     *
     * @return {object}
     */
    getHighlightConfig: function () {
      return this.parentComponent.highlightConfig;
    },
    /**
~     * Returns the chords for display.
     *
     * @return undefined
     */
    getDisplayChords: function () {
      return this.exerciseContext.getDisplayChords();
    },
    /**
     * Returns the chords for exercise analysis.
     *
     * @return undefined
     */
    getExerciseChords: function () {
      return this.exerciseContext.getExerciseChords();
    },
    /**
     * Returns the time signature for display.
     *
     * @return undefined
     */
    getTimeSignature: function () {
      return this.exerciseContext.getTimeSignature();
    },
    /**
     * Obtain semibreves per line for horizontal scaling.
     *
     * @return {integer}
     */
    getSemibrevesPerLine: function () {
      return this.exerciseContext.getSemibrevesPerLine();
    },
    /**
     * Returns the input chords.
     *
     * @return undefined
     */
    getInputChords: function () {
      return this.exerciseContext.getInputChords();
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
      var onsetSeen = {};
      var order = [];
      var measureOffset = {};

      for (var i = 0; i < tl.length; i++) {
        var ev = tl[i];
        if (!onsetSeen[ev.onset]) {
          onsetSeen[ev.onset] = { measureIndex: ev.measureIndex };
          order.push(ev.onset);
        }
        if (!(ev.measureIndex in measureOffset)) {
          measureOffset[ev.measureIndex] = ev.onset;
        }
      }
      order.sort(function (a, b) { return a - b; });

      this._playbackWindowOnsets = order.slice();
      this._playbackWindowMeasures = order.map(function (onset) { return onsetSeen[onset].measureIndex; });
      this._playbackMeasureTickOffset = measureOffset;

      return tl;
    },
    /**
     * Handle MIDI note events in chorale mode by delegating to the ChoraleGrader
     */
    onMidiNote: function (state, noteNum) {
      var definition = this.exerciseContext.getDefinition();
      if (!definition.isChorale()) return;

      // Start timer on first interaction
      if (state === "on") {
        this.exerciseContext.triggerTimer();
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

      // Repaint with updated highlights
      var playedIds = grader.getPlayedNoteIds ? grader.getPlayedNoteIds() : new Set();
      var idArray = [];
      playedIds.forEach(function(id) { idArray.push(id); });
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
    /**
     * Converts raw UMTO data into the "Processed Score" format that VexFlowAdapter expects.
     * @param {object} umto 
     * @returns {object} Processed score
     */
    _convertUMTOToProcessedScore: function (umto) {
      if (!umto || !umto.voices) {
        console.error("[ID] UMTO or voices missing", umto);
        return null;
      }
      
      var meta = _.cloneDeep(umto.metadata || {});
      if (meta.meter && !meta.time) meta.time = meta.meter;
      if (!meta.time) meta.time = "4/4";
      
      // Use the MeasureEngine to split each voice into measures
      var voiceKeys = ['S', 'A', 'T', 'B'];
      var splitVoices = {};
      var maxMeasures = 0;
      
      _.each(voiceKeys, function(vk) {
        var voiceItems = umto.voices[vk] || [];
        var processedItems = _.map(voiceItems, function(ev) {
          var item = _.cloneDeep(ev);
          item.kind = ev.kind || 'note';
          item.duration = {
            type: ev.duration_type || 'q',
            dots: ev.dots || 0
          };
          if (ev.pitch) {
            item.notes = [{ pitch: _.cloneDeep(ev.pitch) }];
          }
          return item;
        });
        
        splitVoices[vk] = MeasureEngine.splitIntoMeasures(processedItems, meta.time);
        maxMeasures = Math.max(maxMeasures, splitVoices[vk].length);
      });
      
      var measures = [];
      for (var mIdx = 0; mIdx < maxMeasures; mIdx++) {
        var m = { staves: { treble: { voices: [] }, bass: { voices: [] } } };
        
        _.each(voiceKeys, function(vk) {
          var items = (splitVoices[vk][mIdx]) || [];
          if (items.length === 0) return;
          
          var staffName = (vk === 'S' || vk === 'A') ? 'treble' : 'bass';
          // Override if staffDistribution is specific
          if (meta.staffDistribution === 'bass') staffName = 'bass';
          else if (meta.staffDistribution === 'treble') staffName = 'treble';
          
          if (!m.staves[staffName]) m.staves[staffName] = { voices: [] };
          
          var dir = 'auto';
          if (staffName === 'treble') {
            dir = (vk === 'S' && umto.voices.A && umto.voices.A.length > 0) ? 'up' : 'auto';
            if (vk === 'A') dir = 'down';
          } else {
            dir = (vk === 'T' && umto.voices.B && umto.voices.B.length > 0) ? 'up' : 'auto';
            if (vk === 'B') dir = 'down';
          }
          
          m.staves[staffName].voices.push({ items: items, direction: dir });
        });
        
        // Clean up empty staves
        if (m.staves.treble && m.staves.treble.voices.length === 0) delete m.staves.treble;
        if (m.staves.bass && m.staves.bass.voices.length === 0) delete m.staves.bass;
        
        measures.push(m);
      }
      
      var processed = {
        meta: meta,
        measures: measures
      };
      console.log("[ID] Processed score built via MeasureEngine:", processed);
      return processed;
    },
  });

  return ExerciseSheetComponent;
});
