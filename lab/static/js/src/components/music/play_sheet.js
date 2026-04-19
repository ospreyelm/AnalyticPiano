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
  renderPlaybackControls
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
    this._playbackHighlightRect = null;

    if ("chords" in this.settings) {
      this.chords = this.settings.chords;
    } else {
      throw new Error("missing settings.chords");
    }

    if ("keySignature" in this.settings) {
      this.keySignature = this.settings.keySignature;
    } else {
      throw new Error("missing settings.keySignature");
    }

    _.bindAll(this, ["render", "onChordsUpdate"]);
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

      // Feature flag: render a sample polyphonic measure using the new adapter when '?newvf' is present
      // Using simple string indexOf to avoid CSP issues with URLSearchParams
      var useNewAdapter = window.location.search.indexOf("newvf") !== -1;

      if (useNewAdapter) {
        var width = this.getWidth();
        var height = this.getHeight();
        var params = this._getAllQueryParams ? this._getAllQueryParams() : {};
        var corpusFile = params.loadCorpus || this._getQueryParam('loadCorpus');
        var self = this;
        
        if (corpusFile) {
          console.log('Loading corpus file:', corpusFile);
          // Change "DISPLAY OPTIONS" to "CHORALE STYLE" for corpus mode
          $('.js-btn-menu').text('CHORALE STYLE');
          
          // Cache payload to avoid re-fetching on every UI change
          var renderWithState = function(payload){
            self.scorePlayer.stop();
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
      }

      /* save data for retrieval by MusicControlsComponent.onClickSaveJSON; this may not be the optimal or most professional solution */
      sessionStorage.setItem("current_state", this.dataForSave());

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

        treble = this.createNoteStave(
          "treble",
          _.clone(position),
          chord,
          isBanked,
          isNovel,
          treble_activeAlterations
        );
        bass = this.createNoteStave(
          "bass",
          _.clone(position),
          chord,
          isBanked,
          isNovel,
          bass_activeAlterations
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

      if (typeof this.keySignature.signatureSpec === "string") {
        const staffSig = this.keySignature.signatureSpec;
        stave.setFirstBarWidth(staffSig, 4);
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
      activeAlterations
    ) {
      var stave = new Stave(clef, position);

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
      var ctx = canvas.getContext("2d");

      this._clearPlaybackHighlight();

      var x = slot.x;
      var y = 0;
      var w = 30;
      var h = slot.y;

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

    /* solution for saving data as exercise; called by render() and saved to sessionStorage */
    dataForSave: function () {
      const objs = this.chords._items.map((items) => items._notes);
      if (objs.length < 2) return null;

      let chords = [];
      let i, len;
      for (i = 1, len = objs.length; i < len; i++) {
        let obj = objs[i];
        let keys = Object.keys(obj);
        let visible = keys
          .filter(function (key) {
            return obj[key];
          })
          .map((key) => parseInt(key));
        let hidden = [];
        let unison_idx = null;
        try {
          unison_idx = this.chords._items[i]._unison_idx;
        } catch {
          console.log('PlaySheetComponent.dataForSave failed to retrieve unison_idx')
        }
        chords.unshift({ rhythmValue: "w", visible: visible, hidden: hidden, unison_idx: unison_idx });
      }

      /* simplify for testing */
      // chords = chords.map(chord => chord["visible"]);

      let json_data = {
        keySignature: this.keySignature.signatureSpec,
        key: this.keySignature.key,
        type: "matching" /* provide options */,
        staffDistribution:
          this.parentComponent.staffDistributionConfig.staffDistribution,
        introText: "",
        reviewText: "",
        analysis: this.parentComponent.analyzeConfig,
        highlight: this.parentComponent.highlightConfig,
        chord: chords,
      };

      /*
			// These properties should also be included once we start changing these presets per user.
			json_data["bankAfterMetronomeTick"]
				= Config.__config.general.bankAfterMetronomeTick;
			json_data["defaultKeyboardSize"]
				= Config.__config.general.defaultKeyboardSize;
			json_data["defaultOctaveAdjustment"]
				= Config.__config.general.defaultOctaveAdjustment;
			json_data["defaultRhythmValue"]
				= Config.__config.general.defaultRhythmValue;
			json_data["hideNextForAutoAdvance"]
				= Config.__config.general.hideNextForAutoAdvance;
			json_data["highlightSettings"]
				= Config.__config.general.highlightSettings;
			json_data["keyboardShortcutsEnabled"]
				= Config.__config.general.keyboardShortcutsEnabled;
			json_data["noDoubleVision"]
				= Config.__config.general.noDoubleVision;
			json_data["voiceCountForChoraleStyle"]
				= Config.__config.general.voiceCountForChoraleStyle;
			json_data["voiceCountForKeyboardStyle"]
				= Config.__config.general.voiceCountForKeyboardStyle;
			*/

      const save_me = JSON.stringify(json_data, null, 0);

      return save_me;
    },
  });

  return PlaySheetComponent;
});
