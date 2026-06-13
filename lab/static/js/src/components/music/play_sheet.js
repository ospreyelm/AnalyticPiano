/* global define: false */
define([
  "jquery",
  "lodash",
  "vexflow",
  "file-saver",
  "app/config",
  "app/components/component",
  "./stave",
  "./stave_notater",
  "./play_note_factory",
  "./score_model",
  "./rendering/vexflow_adapter",
  "app/components/music/score_timeline",
  "app/models/score_player",
  "app/components/music/playback_controls",
  "app/utils/analyze",
  "./chordal_spelling",
  "./play_save_logic",
  "app/utils/chordal_barlines_logic",
  "app/config/analysis_slots",
  "./play_authoring_toolbar",
], function (
  $,
  _,
  Vex,
  FileSaver,
  Config,
  Component,
  Stave,
  StaveNotater,
  PlayNoteFactory,
  ScoreModel,
  VexflowAdapter,
  ScoreTimeline,
  ScorePlayer,
  renderPlaybackControls,
  Analyze,
  ChordalSpelling,
  PlaySaveLogic,
  ChordalBarlinesLogic,
  AnalysisSlots,
  PlayAuthoringToolbar
) {
  "use strict";

  /**
   * Defines the size of the chord bank (how many chords to display on
   * screen).
   * @type {number}
   */
  var CHORD_BANK_SIZE = Config.get("general.chordBank.displaySize");

  /**
   * PlaySheetComponent
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
  var PlaySheetComponent = function (settings) {
    this.settings = settings || {};
    this._corpusFile = null;         // last loaded file name
    this._corpusPayload = null;      // cached JSON payload
    this._vfState = {                // renderer UI state bridge
      selectVoices: null,
      octaveShift: null,
    };
    this._cachedTimeline = null;
    this._windowPositionCache = {};
    this._playbackWindowIndex = null;

    if ("chords" in this.settings) {
      this.chords = this.settings.chords;
    } else {
      throw new Error("missing settings.chords");
    }

    // Authoring state (Play teacher authoring). Default note value = quarter (1.0).
    // All authoring overrides are keyed by the chord's STABLE id (chord._cid),
    // never by a positional index — the bank unshifts new chords so indices shift.
    this._chordDurations = {};   // chord._cid -> quarter-length (palette)
    this._spellingOverrides = {}; // chord._cid -> [spelling strings]
    this._barlineOffsets = [];   // quarter-length offsets, sorted/unique, on chord onsets
    this._meter = null;          // null = free/open mode
    this._tokenOverrides = {};   // chord._cid -> { below: <string> } teacher analysis corrections
    this._selection = null;      // { kind: "chord", chord: <Chord> } or null
    this._toolbar = null;        // PlayAuthoringToolbar instance (lazy)

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("missing settings.keySignature");
    }

    _.bindAll(this, ["render", "onChordsUpdate", "_onAuthoringKeydown"]);
  };

  PlaySheetComponent.prototype = new Component();

  _.extend(PlaySheetComponent.prototype, {
    _getQueryParam: function (name) {
      // Backward-compat wrapper; prefer _getAllQueryParams.
      var all = this._getAllQueryParams();
      return all && name in all ? all[name] : null;
    },
    _getAllQueryParams: function () {
      // Robust, regex-free query parser (URLSearchParams where available)
      var out = {};
      try {
        if (typeof URLSearchParams !== 'undefined') {
          var sp = new URLSearchParams(window.location.search || "");
          sp.forEach(function(v, k){ out[k] = v; });
          return out;
        }
      } catch (_) {}
      try {
        var qs = window.location.search || "";
        if (qs.charAt(0) === '?') qs = qs.slice(1);
        if (!qs) return out;
        var parts = qs.split('&');
        for (var i = 0; i < parts.length; i++) {
          if (parts[i] === '') continue;
          var kv = parts[i].split('=');
          var k = decodeURIComponent(kv[0] || "");
          var v = decodeURIComponent(kv.slice(1).join('=') || "");
          if (k) out[k] = v;
        }
      } catch (_) {}
      return out;
    },
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
      this._initClickHandler();
      document.addEventListener("keydown", this._onAuthoringKeydown);

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

      // Wire the meter selector in the toolbar to setMeter.
      // The <select id="play-meter-select"> is rendered in play.html's #staff-toolbar.
      $("#play-meter-select").on("change", function () {
        var val = $(this).val();
        self.setMeter(val || null);
      });
    },
    /**
     * Initializes the canvas renderer and dom element.
     *
     * @return
     */
    initRenderer: function () {
      var CANVAS = Vex.Flow.Renderer.Backends.CANVAS;
      this.vexRenderer = new Vex.Flow.Renderer(this.el[0], CANVAS);
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
      this.chords.bind("change", this.render);
      this.chords.bind("clear", this.onChordsUpdate);
      this.chords.bind("bank", this.onChordsUpdate);
    },
    /**
     * Renders the grand staff and everything on it.
     *
     * @return this
     */
    render: function () {
      this.clear();

      // Feature flag: render a sample polyphonic measure using the new adapter when '?newvf' is present or an imported score is loaded
      var useNewAdapter = window.location.search.indexOf("newvf") !== -1 || !!this._corpusPayload;

      if (useNewAdapter) {
        var width = this.getWidth();
        var height = this.getHeight();
        var params = this._getAllQueryParams ? this._getAllQueryParams() : {};
        var corpusFile = params.loadCorpus || this._getQueryParam('loadCorpus') || (this._corpusPayload ? "imported.xml" : null);
        var self = this;
        
        if (corpusFile) {
          console.log('Loading corpus file:', corpusFile);
          // Change "DISPLAY OPTIONS" to "CHORALE STYLE" for corpus mode
          $('.js-btn-menu').text('CHORALE STYLE');
          
          // Cache payload to avoid re-fetching on every UI change
          var renderWithState = function(payload){
            if (self.scorePlayer) { self.scorePlayer.stop(); }
            self._cachedTimeline = null;
            self._windowPositionCache = {};
            try {
              if (payload && payload.score) {
                // If corpus provides a key, sync the KeySignature model and header widget
                // (only update if different to avoid infinite render loop)
                if (payload.score.meta && payload.score.meta.key) {
                  var mapped = self._mapMetaKeyToModelKey(payload.score.meta.key);
                  if (mapped && self.keySignature.getKey() !== mapped) {
                    try { 
                      // Temporarily unbind to prevent re-render loop
                      self.keySignature.unbind("change", self.render);
                      self.keySignature.changeKey(mapped, true);
                      self.keySignature.bind("change", self.render);
                    } catch (e) { /* ignore */ }
                  }
                }
                // Build selectVoices/octaveShift from URL or UI widgets
                var q = self._getAllQueryParams ? self._getAllQueryParams() : {};
                var voicesParam = q.voices || null;
                var b8vb = q.b8vb || null;

                var selectVoices = self._buildSelectVoices(voicesParam);
                var octaveShift = b8vb ? { bass: -1 } : null;

                // Remember state for subsequent re-renders
                self._vfState.selectVoices = selectVoices;
                self._vfState.octaveShift = octaveShift;

                self._corpusPayload = payload;
                self._corpusFile = corpusFile;

                self._cachedTimeline = ScoreTimeline.buildTimeline(payload.score);

                VexflowAdapter.render(payload.score, self.vexRenderer, {
                  width: width,
                  height: height,
                  maxMeasures: 4,
                  selectVoices: selectVoices,
                  octaveShift: octaveShift,
                  onWindowPosition: function (slot) {
                    if (slot && typeof slot.windowIndex === "number") {
                      self._windowPositionCache[slot.windowIndex] = slot;
                    }
                  },
                });

                // Playback controls (corpus mode only, idempotent)
                var $toolbar = $("#staff-toolbar");
                if ($toolbar.length) {
                  renderPlaybackControls($toolbar, self.scorePlayer, function () {
                    return self._cachedTimeline;
                  });
                  $("#playback-controls").show();
                }
              } else {
                alert('Corpus file loaded but missing .score');
              }
            } catch (e) {
              alert('Error rendering corpus: ' + e.message);
              console.error(e);
            }
          };

          if (self._corpusPayload && self._corpusFile === corpusFile) {
            renderWithState(self._corpusPayload);
          } else {
            $.getJSON('/ajax/dev/corpus/bach/' + encodeURIComponent(corpusFile))
              .done(function(payload){
                console.log('Corpus loaded:', payload);
                renderWithState(payload);
              })
              .fail(function(xhr, status, error){
                alert('Failed to load corpus: ' + xhr.status + ' ' + error);
                console.error('AJAX error:', xhr, status, error);
              });
          }
        } else {
          $("#playback-controls").hide();
          try {
            var sample = this.samplePolyphonicScore();
            VexflowAdapter.render(sample, this.vexRenderer, { width: width, height: height, maxMeasures: 4 });
          } catch (e) {
            alert("Error in new renderer: " + e.message);
            throw e;
          }
        }
      } else {
        this.renderStaves();
        this._drawBarlineTicks();
      }

      /* save data for retrieval by MusicControlsComponent.onClickSaveJSON; this may not be the optimal or most professional solution */
      sessionStorage.setItem("current_state", this.dataForSave());
      sessionStorage.setItem("current_state_validity", JSON.stringify(this.checkSaveValidity()));

      return this;
    },
    // Map corpus meta.key (e.g., "F", "Bbm") to the KeySignature model key id (e.g., "jF_", "iBb")
    _mapMetaKeyToModelKey: function(metaKey){
      if (!metaKey || typeof metaKey !== 'string') return null;
      // Normalize e.g., 'bb' to 'b', '##' stays '##'
      var mk = metaKey.trim();
      var isMinor = /m$/.test(mk);
      var root = isMinor ? mk.slice(0, -1) : mk;
      // Standardize symbols: 'Bb' stays, 'Cb' stays, 'F#' stays
      // Build code: prefix i=minor, j=major; natural underscore for naturals
      var accidental = '';
      if (root.length > 1) accidental = root.slice(1); // '#', 'b'
      var letter = root.charAt(0).toUpperCase();
      var suffix = accidental === '' ? '_' : accidental; // '_' for natural
      var code = (isMinor ? 'i' : 'j') + letter + suffix;
      return code;
    },
    // Compute selectVoices from URL override or current UI state
    _buildSelectVoices: function(voicesParam){
      // URL override for quick testing
      if (voicesParam === 'sb') {
        return { treble: [0], bass: [1] };
      }
      // Use menu settings when available
      try {
        var pc = this.parentComponent; // MusicComponent
        if (pc && pc.highlightConfig && pc.highlightConfig.enabled) {
          if (pc.highlightConfig.mode && pc.highlightConfig.mode.solobass) {
            return { treble: [], bass: [1] };
          }
        }
        if (pc && pc.staffDistributionConfig && pc.staffDistributionConfig.staffDistribution) {
          var dist = pc.staffDistributionConfig.staffDistribution;
          if (dist === 'LH') return { treble: [], bass: [0,1] };
          if (dist === 'RH') return { treble: [0,1], bass: [] };
        }
      } catch (e) {}
      return null; // no filtering
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
    renderStaves: function () {
      var i,
        len,
        stave,
        _staves = this.staves;
      for (i = 0, len = _staves.length; i < len; i++) {
        stave = _staves[i];
        stave.render();
      }
      return this;
    },
    /**
     * Resets the staves.
     *
     * @return this
     */
    resetStaves: function () {
      _.invoke(this.staves, "destroy");
      this.staves = [];
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
    /**
     * Updates and configures the staves.
     *
     * @return this
     */
    updateStaves: function () {
      var limit = CHORD_BANK_SIZE;
      var items = this.chords.items({ limit: limit, reverse: true });
      var position = {
        index: 0,
        count: items.length,
        maxCount: CHORD_BANK_SIZE,
      };
      var staves =
        []; /* the successive items of this array will correspond to measures */
      var treble_activeAlterations = Object.create(null);
      var bass_activeAlterations = Object.create(null);

      /* the first vexflow measure is a special case: it is reserved to
       * show the clef and key signature and nothing else */
      var treble = this.createDisplayStave("treble", _.clone(position));
      var bass = this.createDisplayStave("bass", _.clone(position));
      position.index += 1;
      treble.connect(bass);
      staves.push(treble);

      var treble_alterationHistory = Object.create(null);
      var bass_alterationHistory = Object.create(null);

      /* add the subsequent measures */
      for (var i = 0; i < items.length; i++) {
        let chord = items[i].chord;
        let isBanked = items[i].isBanked;
        let isNovel = items[i].isNovel;

        treble_alterationHistory[i] = treble_activeAlterations;
        bass_alterationHistory[i] = bass_activeAlterations;

        // Live per-chord duration (play-authoring). Look up by the chord's stable id
        // (positional indices shift on bank). Only banked chords carry an authored
        // duration; the live/working chord keeps the default note value.
        let noteDuration = null;
        if (isBanked) {
          let ql = this.getChordDuration(chord);
          let dp = ChordalBarlinesLogic.qlToVexDuration(ql);
          noteDuration = { duration: dp.duration, dots: dp.dots, quarterLength: ql };
        }

        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          chord,
          isBanked,
          isNovel,
          treble_activeAlterations,
          noteDuration
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          chord,
          isBanked,
          isNovel,
          bass_activeAlterations,
          noteDuration
        );
        position.index += 1;
        treble.connect(bass);
        staves.push(treble);

        // TO DO: compress code (see also exercise sheet)

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

      return this;
    },
    /**
     * Creates a stave to display the clef, key signature, etc.
     *
     * @param {string} clef
     * @param {object} position
     * @return {Stave}
     */
    createDisplayStave: function (clef, position) {
      var stave = new Stave(clef, position);
      var stave_notater = this.createStaveNotater(clef, {
        stave: stave,
        keySignature: this.keySignature,
        analyzeConfig: this.getAnalyzeConfig(),
      });

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      stave.setNotater(stave_notater);
      stave.setMaxWidth(this.getWidth());

      // Live time-signature glyph (play-authoring): when a meter is set the display
      // stave (the first bar) draws it; in free mode (_meter null) no glyph appears.
      if (this._meter) {
        stave.setTimeSignature(this._meter);
      }

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        // Reserve extra first-bar width for the time-signature glyph when a meter
        // is set, otherwise the glyph is clipped/overlapped and never shows.
        stave.setFirstBarWidth(staffSig, 4, !!this._meter);
      }
      stave.updatePosition();

      return stave;
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
      chord,
      isBanked,
      isNovel,
      activeAlterations,
      noteDuration
    ) {
      var stave = new Stave(clef, position);
      if (noteDuration) {
        stave.setNoteDuration(
          noteDuration.duration,
          noteDuration.dots,
          noteDuration.quarterLength
        );
      }

      stave.setRenderer(this.vexRenderer);
      stave.setKeySignature(this.keySignature);
      // stave.setFirstBarWidth(this.keySignature);
      stave.setNoteFactory(
        new PlayNoteFactory({
          clef: clef,
          chord: chord,
          isBanked: isBanked,
          isNovel: isNovel,
          keySignature: this.keySignature,
          highlightConfig: this.getHighlightConfig(),
          activeAlterations: activeAlterations,
        })
      );
      stave.setNotater(
        this.createStaveNotater(clef, {
          stave: stave,
          chord: chord,
          keySignature: this.keySignature,
          analyzeConfig: this.getAnalyzeConfig(),
        })
      );
      stave.setMaxWidth(this.getWidth());
      stave.updatePosition();
      stave.setBanked(isBanked);
      stave.setNovel(isNovel);

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        stave.setFirstBarWidth(staffSig, 4);
      }
      stave.updatePosition();
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
     * Handles a chord bank update.
     *
     * @return undefined
     */
    onChordsUpdate: function () {
      this.updateStaves();
      this.render();
    },

    // Build a minimal polyphonic example for the adapter prototype
    samplePolyphonicScore: function () {
      var meta = { key: this.keySignature.getVexKey ? this.keySignature.getVexKey() : undefined, time: "4/4" };

      // Measure 1: Treble - quarter + quarter + half (4 beats)
      var m1Treble = ScoreModel.voice([
        ScoreModel.note("C", 0, 5, "q", 0),
        ScoreModel.note("D", 0, 5, "q", 0),
        ScoreModel.note("E", 0, 5, "h", 0)
      ], "up");

      // Measure 1: Bass - dotted half + quarter (4 beats, different rhythm!)
      var m1Bass = ScoreModel.voice([
        ScoreModel.note("C", 0, 3, "h", 1),  // dotted half = 3 beats
        ScoreModel.note("G", 0, 2, "q", 0)   // quarter = 1 beat
      ], "down");

      var treble1 = ScoreModel.staff("treble", [m1Treble]);
      var bass1 = ScoreModel.staff("bass", [m1Bass]);
      var meas1 = ScoreModel.measure(1, { treble: treble1, bass: bass1 });

      // Measure 2: Treble - half + half (4 beats)
      var m2Treble = ScoreModel.voice([
        ScoreModel.note("G", 0, 5, "h", 0),
        ScoreModel.note("F", 0, 5, "h", 0)
      ], "up");

      // Measure 2: Bass - four quarters (4 beats, busier rhythm!)
      var m2Bass = ScoreModel.voice([
        ScoreModel.note("E", 0, 3, "q", 0),
        ScoreModel.note("D", 0, 3, "q", 0),
        ScoreModel.note("C", 0, 3, "q", 0),
        ScoreModel.note("B", 0, 2, "q", 0)
      ], "down");

      var treble2 = ScoreModel.staff("treble", [m2Treble]);
      var bass2 = ScoreModel.staff("bass", [m2Bass]);
      var meas2 = ScoreModel.measure(2, { treble: treble2, bass: bass2 });

      return ScoreModel.score(meta, [meas1, meas2]);
    },

    _drawPlaybackHighlight: function () {
      var idx = this._playbackWindowIndex;
      if (idx === null || idx === undefined) return;
      var slot = this._windowPositionCache[idx];
      if (!slot) return;

      var canvas = this.el[0];
      var canvasOffset = $(canvas).offset();
      var w = 30;
      var h = slot.y;
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
     * Draw a thin vertical tick at each barline position on the canvas.
     * Maps each barline offset → the banked-chord whose onset equals it →
     * that chord's stave getStartX(), then draws a short vertical line.
     * Only active in regular stave mode.
     */
    _drawBarlineTicks: function () {
      if (!this._barlineOffsets || !this._barlineOffsets.length) return;
      if (window.location.search.indexOf("newvf") !== -1) return;

      var staves = this.staves;
      if (!staves || staves.length < 2) return;

      // Build onset → stave index map. Display is chronological (oldest left):
      // staves[k] (k>=1) is the k-th banked chord in chronological order, whose
      // onset is offsetsFromDurations(_bankedDurations())[k-1]. Both the offsets
      // and the staves are chronological, so they line up.
      var durations = this._bankedDurations();
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      var onsetToStaveIdx = {};
      for (var k = 1; k < staves.length; k++) {
        var onset = offsets[k - 1];
        if (onset !== undefined) {
          onsetToStaveIdx[Math.round(onset * 1e6) / 1e6] = k;
        }
      }

      // Get the raw 2D context directly from the canvas element (Vex.Flow may
      // wrap it; accessing the element directly is the most reliable path).
      var canvas = this.el[0];
      var raw = canvas ? canvas.getContext("2d") : null;
      if (!raw) return;

      raw.save();
      raw.strokeStyle = "rgba(60, 120, 220, 0.85)";
      raw.lineWidth = 2;

      var canvasHeight = canvas.height || this.getHeight();

      for (var i = 0; i < this._barlineOffsets.length; i++) {
        var o = Math.round(this._barlineOffsets[i] * 1e6) / 1e6;
        var si = onsetToStaveIdx[o];
        if (si === undefined) continue;
        var stave = staves[si];
        var x = stave.getStartX ? stave.getStartX() : 0;
        // Draw a vertical line from canvas top to bottom at this x
        raw.beginPath();
        raw.moveTo(x, 0);
        raw.lineTo(x, canvasHeight);
        raw.stroke();
      }

      raw.restore();
    },

    /**
     * Banked chords in CHRONOLOGICAL order (oldest first). The bank stores
     * _items[0] = live chord and _items[1..N] = banked NEWEST-first (unshift),
     * so drop the live chord and reverse. This order matches the on-screen
     * display (staves left→right) and the saved-exercise chord order.
     */
    _bankedChrono: function () {
      return this.chords._items.slice(1).reverse();
    },

    // Duration keyed by the chord's STABLE id (positional indices shift on bank).
    getChordDuration: function (chord) {
      var d = chord ? this._chordDurations[chord._cid] : undefined;
      return typeof d === "number" ? d : 1.0; // default quarter
    },

    setChordDuration: function (chord, quarterLength) {
      if (!chord) return;
      this._chordDurations[chord._cid] = quarterLength;
      this.onChordsUpdate(); // rebuild staves (render() alone repaints stale staves)
    },

    setMeter: function (meter) {
      this._meter = meter || null;
      if (this._meter) this.autoSuggestBarlines(); // seeds barlines; teacher then edits
      else { this._barlineOffsets = []; this.onChordsUpdate(); }
    },

    placeBarline: function (offset) {
      var o = Math.round(offset * 1e6) / 1e6;
      if (this._barlineOffsets.indexOf(o) === -1) {
        this._barlineOffsets.push(o);
        this._barlineOffsets.sort(function (a, b) { return a - b; });
        this.onChordsUpdate();
      }
    },
    removeBarline: function (offset) {
      var o = Math.round(offset * 1e6) / 1e6;
      this._barlineOffsets = this._barlineOffsets.filter(function (b) { return b !== o; });
      this.onChordsUpdate();
    },
    _bankedDurations: function () {
      var self = this;
      return this._bankedChrono().map(function (c) { return self.getChordDuration(c); });
    },
    toggleBarlineAtChord: function (chord) {
      // A barline sits at the onset of `chord` (between it and the previous chord).
      if (!chord) return;
      var chrono = this._bankedChrono();
      var idx = chrono.indexOf(chord);
      if (idx <= 0) return; // index 0 is the stream start — no barline there
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(this._bankedDurations());
      var onset = offsets[idx];
      if (onset === undefined || onset === 0) return;
      if (this._barlineOffsets.indexOf(Math.round(onset * 1e6) / 1e6) === -1) this.placeBarline(onset);
      else this.removeBarline(onset);
    },
    autoSuggestBarlines: function () {
      var durations = this._bankedDurations();
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      this._barlineOffsets = ChordalBarlinesLogic.suggestBarlines(offsets, durations, this._meter);
      this.onChordsUpdate();
    },

    _analyzeSlots: function () {
      var cfg = this.getAnalyzeConfig() || {};
      return AnalysisSlots.normalizeSlots(cfg);
    },

    checkSaveValidity: function () {
      if (this.chords._items.length < 2) return { ok: false, code: "empty" };
      var durations = this._bankedDurations();
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      var res = ChordalBarlinesLogic.checkRhythm(offsets, durations, this._meter, this._barlineOffsets);
      return res.ok ? { ok: true } : { ok: false, code: "invalid_meter", error: res.error };
    },

    /**
     * Lazily construct and return the PlayAuthoringToolbar, wiring callbacks.
     * @private
     */
    _getToolbar: function () {
      if (!this._toolbar) {
        var self = this;
        this._toolbar = new PlayAuthoringToolbar({
          onSetDuration: function (ql) {
            if (self._selection) {
              self.setChordDuration(self._selection.chord, ql);
            }
          },
          onRespell: function () {
            self._respellSelected();
          },
          onClose: function () {
            self._clearSelection();
          },
          onSetToken: function (value) {
            if (self._selection) {
              self.setToken(self._selection.chord, "below", value);
            }
          },
        });
      }
      return this._toolbar;
    },

    /**
     * Compute the current below-zone label for the given banked chord
     * (for pre-filling the token correction input in the toolbar).
     * Returns the override value if set, otherwise the computed label, or
     * null if no below-zone is active.
     *
     * @param {Chord} chord  the banked chord object.
     * @return {string|null}
     */
    _getCurrentTokenLabel: function (chord) {
      var slots = this._analyzeSlots();
      if (!slots || !slots.below) return null;
      if (!chord) return null;
      // Return stored override if present (keyed by stable chord id)
      if (this._tokenOverrides[chord._cid] &&
          typeof this._tokenOverrides[chord._cid].below !== "undefined") {
        return this._tokenOverrides[chord._cid].below;
      }
      var obj = chord._notes;
      var visible = Object.keys(obj)
        .filter(function (k) { return obj[k]; })
        .map(function (k) { return parseInt(k, 10); });
      if (!visible.length) return null;
      try {
        var analyzer = new Analyze(this.keySignature);
        if (slots.below === "thoroughbass") {
          return analyzer.full_thoroughbass_figure(visible) || "";
        } else {
          var rn = analyzer.to_chord(visible, "roman only");
          return (rn && rn.numeral) ? rn.numeral : "";
        }
      } catch (e) {
        return null;
      }
    },

    /**
     * Clear the current chord selection and hide the toolbar.
     */
    _clearSelection: function () {
      this._selection = null;
      if (this._toolbar) {
        this._toolbar.hide();
      }
    },

    /**
     * Flip the enharmonic spelling of the currently selected banked chord and
     * store it in _spellingOverrides so dataForSave picks it up.
     *
     * Algorithm: for each note in the chord, read the current spelling string
     * (from _spellingOverrides if already overridden, else the key-aware
     * default from ChordalSpelling/Analyze). Then apply a minimal enharmonic
     * flip: sharp -> flat, flat -> sharp, natural -> no change. Specifically:
     *   - alter > 0 (sharps): raise the letter step by one, apply flats
     *     (e.g. C# -> Db, F# -> Gb, D# -> Eb)
     *   - alter < 0 (flats): lower the letter step by one, apply sharps
     *     (e.g. Db -> C#, Bb -> A#, Eb -> D#)
     *   - alter == 0 (natural): leave unchanged
     *
     * The result is stored keyed by the chord's stable id (this._spellingOverrides),
     * which dataForSave reads back per chord (positional indices shift on bank).
     */
    _respellSelected: function () {
      if (!this._selection || this._selection.kind !== "chord") return;
      var chord = this._selection.chord;
      if (!chord) return;
      var obj = chord._notes;
      var visible = Object.keys(obj)
        .filter(function (k) { return obj[k]; })
        .map(function (k) { return parseInt(k, 10); });
      var hidden = [];
      try { hidden = chord._hidden_notes ? chord._hidden_notes.slice() : []; } catch (e) {}
      var allMidis = visible.concat(hidden);
      if (allMidis.length === 0) return;

      // Determine the current spelling strings (override already stored, or recompute)
      var currentSpellings;
      if (this._spellingOverrides[chord._cid] &&
          this._spellingOverrides[chord._cid].length === allMidis.length) {
        currentSpellings = this._spellingOverrides[chord._cid].slice();
      } else {
        // Recompute key-aware defaults (same logic as dataForSave)
        var analyzer = new Analyze(this.keySignature);
        currentSpellings = allMidis.map(function (m) {
          return ChordalSpelling.vexKeyToSpellingString(analyzer.getNoteName(m, visible));
        });
      }

      // Letter steps in order (for enharmonic flip)
      var STEPS = ["C", "D", "E", "F", "G", "A", "B"];

      // Flip each spelling string
      var flipped = currentSpellings.map(function (str, idx) {
        var midi = allMidis[idx];
        var parsed = ChordalSpelling.pitchFromSpellingString(str);
        if (!parsed) return str; // can't parse, leave unchanged

        var alter = parsed.alter;
        if (alter === 0) return str; // natural — no enharmonic equivalent at same MIDI pitch

        // Compute new step and alter
        var stepIdx = STEPS.indexOf(parsed.step.toUpperCase());
        if (stepIdx === -1) return str;
        var newStep, newAlter;
        if (alter > 0) {
          // Sharp(s) -> raise letter by one step, apply flats
          newStep = STEPS[(stepIdx + 1) % 7];
          newAlter = -(alter); // e.g. C# (alter=1) -> Db (alter=-1)
        } else {
          // Flat(s) -> lower letter by one step, apply sharps
          newStep = STEPS[(stepIdx + 6) % 7]; // -1 mod 7
          newAlter = -(alter); // e.g. Db (alter=-1) -> C# (alter=1)
        }

        // Recompute octave from MIDI for the new spelling
        var pc = ((midi % 12) + 12) % 12;
        var STEP_PC = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
        var naturalPc = STEP_PC[newStep];
        var octave = Math.floor(midi / 12) - 1;
        if (pc - naturalPc > 6) octave += 1;
        else if (naturalPc - pc > 6) octave -= 1;

        // Build accidental suffix string
        var acc = "";
        var i;
        if (newAlter > 0) {
          for (i = 0; i < newAlter; i++) acc += "#";
        } else if (newAlter < 0) {
          for (i = 0; i < -newAlter; i++) acc += "b";
        }

        return newStep + acc + octave;
      });

      // Only store if lengths match (guard against backend spelling-length rejection)
      if (flipped.length !== allMidis.length) return;
      this._spellingOverrides[chord._cid] = flipped;
      this.onChordsUpdate();
    },

    /**
     * Store a teacher-override for the below-zone token (Roman numeral /
     * figured bass label) for the given chord, keyed by its stable id.
     * dataForSave maps these back onto the chronological banked-chord order.
     *
     * @param {Chord} chord  the selected banked chord object.
     * @param {string} zone  Which zone to override — "below" is the only
     *   supported zone currently (Roman numeral or figured bass depending on
     *   analyzeConfig.slots.below).
     * @param {string} value  The override label (plain text, e.g. "V7", "I6").
     */
    setToken: function (chord, zone, value) {
      if (!chord) return;
      this._tokenOverrides[chord._cid] = this._tokenOverrides[chord._cid] || {};
      this._tokenOverrides[chord._cid][zone] = value;
      this.onChordsUpdate();
    },

    /**
     * Attach a click handler on the canvas to hit-test against rendered stave
     * slots and select the corresponding banked chord, OR toggle a barline when
     * clicking near a stave boundary (gap).
     *
     * Hit-test strategy (regular stave mode):
     *   - After updateStaves(), this.staves[0] is the display stave,
     *     this.staves[k] (k >= 1) is the treble stave for items[k-1].
     *   - items are chords.items({ limit, reverse:true }), so items[k-1] maps
     *     to this.chords._items[ items.length - k ] (raw bank index).
     *
     * Gap vs chord discrimination:
     *   - GAP_TOL = 8px. For each banked stave k >= 2, the left edge
     *     staves[k].getStartX() is a potential gap (boundary between chord k-1
     *     and chord k). If the click is within GAP_TOL px of that left edge,
     *     treat it as a gap click and toggle the barline for bank index k.
     *   - Otherwise, perform the normal chord-body hit-test (chord body = full
     *     stave column width minus the gap band on the left edge). The chord
     *     body starts at sx + GAP_TOL and ends at sx + sw.
     *
     * @private
     */
    _initClickHandler: function () {
      var self = this;
      // Gap tolerance in canvas pixels: clicks within this band on the LEFT
      // edge of a banked stave (k>=2) are treated as barline-toggle clicks.
      var GAP_TOL = 8;

      this.el.on("click.play-authoring", function (e) {
        // Only active in regular stave mode (not corpus mode)
        if (window.location.search.indexOf("newvf") !== -1) return;

        var canvas = self.el[0];
        var rect = canvas.getBoundingClientRect();
        // Canvas-relative click coordinates
        var cx = e.clientX - rect.left;
        var cy = e.clientY - rect.top;

        var staves = self.staves;
        if (!staves || staves.length < 2) {
          self._clearSelection();
          return;
        }

        // Build the items list in the same order as updateStaves
        var limit = CHORD_BANK_SIZE;
        var items = self.chords.items({ limit: limit, reverse: true });

        // --- Gap check: staves[k] for k >= 2 have a left-edge gap band ---
        // Display is chronological (oldest left): stave gk == items[gk-1].chord.
        // The gap on stave gk's left edge sits at that chord's onset; toggling
        // there places/removes a barline before the chord.
        for (var gk = 2; gk < staves.length; gk++) {
          var gStave = staves[gk];
          var gsx = gStave.getStartX ? gStave.getStartX() : 0;
          if (cx >= gsx - GAP_TOL && cx < gsx + GAP_TOL) {
            var gItem = items[gk - 1];
            if (gItem && gItem.isBanked) {
              self.toggleBarlineAtChord(gItem.chord);
            }
            return; // consumed — do not also select a chord
          }
        }

        // --- Chord body hit-test ---
        var hitStaveIdx = -1;

        for (var k = 1; k < staves.length; k++) {
          var stave = staves[k];
          var sx = stave.getStartX();
          var sw = stave.getWidth ? stave.getWidth() : stave.width;
          // For k >= 2, the chord body starts at sx + GAP_TOL (left edge is gap band).
          // For k == 1 (first banked stave), there is no gap to the left.
          var bodyLeft = (k >= 2) ? sx + GAP_TOL : sx;
          if (cx >= bodyLeft && cx < sx + sw) {
            hitStaveIdx = k;
            break;
          }
        }

        if (hitStaveIdx < 1) {
          self._clearSelection();
          return;
        }

        // items[hitStaveIdx - 1] is the chord at this stave
        var itemIdx = hitStaveIdx - 1;
        if (itemIdx >= items.length) {
          self._clearSelection();
          return;
        }

        // Only allow selection of banked (not current/novel) chords
        if (!items[itemIdx].isBanked) {
          self._clearSelection();
          return;
        }

        // Select the chord OBJECT (stable across banking, unlike a positional index).
        var selectedChord = items[itemIdx].chord;
        self._selection = { kind: "chord", chord: selectedChord };

        // Compute page-coordinate rect for the chord column
        var hitStave = staves[hitStaveIdx];
        var sx2 = hitStave.getStartX();
        var sw2 = hitStave.getWidth ? hitStave.getWidth() : hitStave.width;
        // Bottom of bass stave: staves[k] is treble, bass is connected but
        // not separately tracked — use canvas bottom edge as a safe fallback
        var staveHeight = rect.height;
        var pageRect = {
          left:   rect.left + sx2,
          top:    rect.top,
          width:  sw2,
          height: staveHeight,
        };

        var toolbar = self._getToolbar();
        var currentToken = self._getCurrentTokenLabel(selectedChord);
        toolbar.showAt(pageRect, self.getChordDuration(selectedChord), currentToken);
      });
    },

    /* solution for saving data as exercise; called by render() and saved to sessionStorage */
    dataForSave: function () {
      const objs = this.chords._items.map((items) => items._notes);
      if (objs.length < 2) return null;

      var analyzer = new Analyze(this.keySignature);
      var notes = [];
      var durations = [];
      // Iterate banked chords CHRONOLOGICALLY (oldest first) so the saved chord
      // order matches what the teacher sees; key all overrides by the chord's
      // stable id (positional indices shift on bank).
      var chrono = this._bankedChrono();
      var tokenOverridesArr = {}; // 0-based chronological index -> { below: str }
      for (var i = 0; i < chrono.length; i++) {
        var chordObj = chrono[i];
        var obj = chordObj._notes;
        var visible = Object.keys(obj)
          .filter((k) => obj[k])
          .map((k) => parseInt(k, 10));
        var hidden = [];
        var unison_idx = null;
        try { unison_idx = chordObj._unison_idx; } catch (e) {}
        var allMidisForSpell = visible.concat(hidden);
        var spelling = allMidisForSpell.map((m) =>
          ChordalSpelling.vexKeyToSpellingString(analyzer.getNoteName(m, visible)));
        if (this._spellingOverrides[chordObj._cid] &&
            this._spellingOverrides[chordObj._cid].length === allMidisForSpell.length) {
          spelling = this._spellingOverrides[chordObj._cid];
        }
        notes.push({ visible: visible, hidden: hidden, spelling: spelling, unison_idx: unison_idx });
        durations.push(this.getChordDuration(chordObj));
        if (this._tokenOverrides[chordObj._cid]) {
          tokenOverridesArr[i] = this._tokenOverrides[chordObj._cid];
        }
      }

      var slots = this._analyzeSlots();
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);

      // Persist the teacher's analysis DISPLAY choices so the saved exercise renders
      // what they saw (not just the below-zone reviewed slices). exercise_sheet reads
      // these display.show* flags via definition.getDisplay().
      var liveCfg = this.getAnalyzeConfig() || {};
      var liveMode = liveCfg.mode || {};
      var display = {
        showRomans: !!liveMode.roman_numerals,
        showFigures: !!liveMode.thoroughbass,
        showChordLabels: !!liveMode.chord_labels,
        showScaleDegrees: !!liveMode.scale_degrees,
        showNoteNames: !!liveMode.note_names,
      };
      if (liveMode.abbreviate_thoroughbass) display.figureStyle = "figures_abbrev";

      var labels = [];
      if (slots.below) {
        for (var j = 0; j < notes.length; j++) {
          var midis = notes[j].visible;
          if (slots.below === "thoroughbass") {
            labels.push(analyzer.full_thoroughbass_figure(midis) || "");
          } else {
            var rn = analyzer.to_chord(midis, "roman only");
            labels.push(rn && rn.numeral ? rn.numeral : "");
          }
        }
      }

      var chordRows = PlaySaveLogic.buildChordRows(notes, durations);
      var analysisSlices = PlaySaveLogic.buildAnalysisSlices(
        offsets, slots, labels, tokenOverridesArr);

      var json_data = {
        keySignature: this.keySignature.signatureSpec,
        key: this.keySignature.key,
        type: "matching",
        staffDistribution: this.parentComponent.staffDistributionConfig.staffDistribution,
        introText: "",
        reviewText: "",
        analyzeConfig: slots,
        display: display,
        highlight: this.parentComponent.highlightConfig,
        chord: chordRows,
        meter: this._meter,
        barline_offsets: this._barlineOffsets.slice(),
        analysisSlices: slots.below ? analysisSlices : null,
      };

      return JSON.stringify(json_data, null, 0);
    },

    /**
     * Keyboard accelerators scoped to the current chord selection.
     * This handler is a NO-OP when _selection is null, so note entry is
     * completely unaffected with no selection active.
     *
     * Duration mapping (pragmatic choice matching toolbar palette):
     *   1 = quarter  (1.0 quarter-lengths)
     *   2 = half     (2.0 quarter-lengths)
     *   3 = dotted half (3.0 quarter-lengths)
     *   4 = whole    (4.0 quarter-lengths)
     *   r/R = respell selected chord enharmonically
     *   Escape = deselect
     *
     * No global authoring keys are registered here — these accelerators
     * only fire when a chord is selected (selection-scoped).
     */
    _onAuthoringKeydown: function (e) {
      if (!this._selection) return; // selection-scoped only; note entry unaffected
      // Don't act if a text field is focused (let typing happen).
      var ae = document.activeElement;
      if (ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA" || ae.isContentEditable)) return;
      var chord = this._selection.chord;
      switch (e.key) {
        case "1": this.setChordDuration(chord, 1.0); e.preventDefault(); break;   // quarter
        case "2": this.setChordDuration(chord, 2.0); e.preventDefault(); break;   // half
        case "3": this.setChordDuration(chord, 3.0); e.preventDefault(); break;   // dotted half
        case "4": this.setChordDuration(chord, 4.0); e.preventDefault(); break;   // whole
        case "r": case "R": this._respellSelected(); e.preventDefault(); break;
        case "Escape": this._clearSelection(); e.preventDefault(); break;
        case "default": break;
      }
    },
    setCorpusPayload: function (payload) {
      this._corpusPayload = payload;
      this._corpusFile = "imported.xml";
    },
    clearCorpusPayload: function () {
      this._corpusPayload = null;
      this._corpusFile = null;
    },
  });

  return PlaySheetComponent;
});
