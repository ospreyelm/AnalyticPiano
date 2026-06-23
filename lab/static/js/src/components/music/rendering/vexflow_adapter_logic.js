/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.VexflowAdapterLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function isRestTickable(tickable) {
    if (!tickable) return false;
    var methodValue = false;
    if (typeof tickable.isRest === "function") {
      methodValue = !!tickable.isRest();
    } else {
      methodValue = !!tickable.isRest;
    }
    return !!(
      tickable._isRest ||
      methodValue ||
      String(tickable.duration || "").indexOf("r") !== -1
    );
  }

  function keyToMidi(keyStr) {
    var parts = String(keyStr || "").split("/");
    if (parts.length !== 2) return null;
    var name = parts[0];
    var octave = parseInt(parts[1], 10);
    var step = name.charAt(0).toLowerCase();
    var acc = name.slice(1);
    var base = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[step];
    if (typeof base !== "number" || isNaN(octave)) return null;
    var delta = 0;
    if (acc === "#") delta = 1;
    else if (acc === "##") delta = 2;
    else if (acc === "b") delta = -1;
    else if (acc === "bb") delta = -2;
    else if (acc === "n") delta = 0;
    return 12 * (octave + 1) + base + delta;
  }

  function tickableToScaleDegreeMidi(tickable) {
    if (isRestTickable(tickable)) return null;
    var keys = tickable && typeof tickable.getKeys === "function" ? tickable.getKeys() : [];
    var midi = [];
    keys.forEach(function (key) {
      var value = keyToMidi(key);
      if (value !== null) midi.push(value);
    });
    return midi;
  }

  /**
   * Returns the functional_label from the UMTO analysis slice whose offset
   * is within 0.05 quarter-lengths of `quarterLength`, or null if none found.
   * Used by the clausula renderer to draw circled bass scale-degree numerals.
   *
   * @param {Array} analysisSlices  - score.umto.analysis array
   * @param {number} quarterLength  - noteOnset / 1024
   * @returns {string|null}
   */
  function getBassLabelAtOffset(analysisSlices, quarterLength) {
    if (!analysisSlices || !analysisSlices.length) return null;
    for (var i = 0; i < analysisSlices.length; i++) {
      var sl = analysisSlices[i];
      if (Math.abs(sl.offset - quarterLength) < 0.05 &&
          sl.content && sl.content.functional_label) {
        return sl.content.functional_label;
      }
    }
    return null;
  }

  function normalizeKeyForVexFlow(key) {
    if (!key) return "C";
    var k = String(key).trim();
    if (k.startsWith("i") || k.startsWith("j")) {
      var mode = k.charAt(0);
      var root = k.substring(1).replace("_", "");
      return mode === "i" ? root + "m" : root;
    }
    if (k.length > 0 && k[0] === k[0].toLowerCase()) {
      var lowerRoot = k[0].toUpperCase() + k.substring(1);
      return lowerRoot.endsWith("m") ? lowerRoot : lowerRoot + "m";
    }
    return k;
  }

  function getKeySignatureAlterations(key) {
    if (!key) return {};

    var alterations = {};
    var k = normalizeKeyForVexFlow(key);
    var map = {
      C: 0, G: 1, D: 2, A: 3, E: 4, B: 5, "F#": 6, "C#": 7,
      F: -1, Bb: -2, Eb: -3, Ab: -4, Db: -5, Gb: -6, Cb: -7,
      Am: 0, Em: 1, Bm: 2, "F#m": 3, "C#m": 4, "G#m": 5, "D#m": 6, "A#m": 7,
      Dm: -1, Gm: -2, Cm: -3, Fm: -4, Bbm: -5, Ebm: -6, Abm: -7,
    };
    var accCount = map[k] || 0;

    if (accCount > 0) {
      var sharpOrder = ["F", "C", "G", "D", "A", "E", "B"];
      for (var i = 0; i < accCount && i < sharpOrder.length; i++) {
        alterations[sharpOrder[i]] = 1;
      }
    } else if (accCount < 0) {
      var flatOrder = ["B", "E", "A", "D", "G", "C", "F"];
      for (var j = 0; j < Math.abs(accCount) && j < flatOrder.length; j++) {
        alterations[flatOrder[j]] = -1;
      }
    }

    return alterations;
  }

  /* ── Extractions from vexflow_adapter.js ──────────────────────────────── */

  // Decides chord notehead coloring for a multi-note chord tickable. A chord's
  // notehead ids run [baseId, baseId + keyCount). Returns the base (unplayed)
  // style for the whole chord plus the indices of individually-played
  // noteheads, which the caller applies via setKeyStyle.
  //
  // The base style must never be the played-black color: per-key playedness
  // can only ADD black to specific noteheads via setKeyStyle, never subtract
  // it from the others. If the base style were black, an unplayed notehead in
  // a partially-played chord would have no call to bring it back to gray —
  // it would render black even though it was never struck.
  function resolveChordNoteStyles(opts) {
    opts = opts || {};
    var keyCount = opts.keyCount || 0;
    var baseId = opts.baseId || 0;
    var playedNoteIds = opts.playedNoteIds;
    var hideBase = !opts.showNotation || opts.isAnalysisMatch || opts.hideForHarmonization;
    var baseStyle = hideBase
      ? { fillStyle: "transparent", strokeStyle: "transparent" }
      : { fillStyle: opts.voiceColor, strokeStyle: opts.voiceColor };
    var playedKeyIndices = [];
    for (var h = 0; h < keyCount; h++) {
      if (playedNoteIds && playedNoteIds.has(baseId + h)) {
        playedKeyIndices.push(h);
      }
    }
    return { baseStyle: baseStyle, playedKeyIndices: playedKeyIndices };
  }

  function durToVF(d) {
    var type = d.type;
    var map = { 'whole': 'w', 'half': 'h', 'quarter': 'q', 'eighth': '8', '16th': '16', '32nd': '32', 'e': '8', 's': '16' };
    return map[type] || type;
  }

  function convertRomanSymbols(text) {
    return String(text || "")
      .replace(/bb/g, "𝄫")
      .replace(/b/g, "♭")
      .replace(/##/g, "𝄪")
      .replace(/#/g, "♯")
      .replace(/n/g, "♮")
      .replace(/⌀/g, "⌀");
  }

  function getFigurePattern(figure) {
    return String(figure || "")
      .split("/")
      .map(function (line) {
        return line.replace(/[^0-9]+/g, "");
      })
      .filter(function (line) {
        return line.length > 0;
      })
      .join("/");
  }

  function getRomanExpDisplayFigureLines(current, previous) {
    if (!current) return [];

    var preserveSuspensionContext = !!(
      previous &&
      previous.base === current.base &&
      previous.fullFigureLines &&
      previous.fullFigureLines.length >= 3
    );

    return preserveSuspensionContext
      ? current.fullFigureLines
      : current.abbrevFigureLines;
  }

  function noteCenterX(note) {
    if (!note) return null;
    if (typeof note.getBoundingBox === "function") {
      var bb = note.getBoundingBox();
      if (bb) {
        if (typeof bb.getX === "function" && typeof bb.getW === "function") {
          return bb.getX() + bb.getW() / 2;
        }
        if (bb.x !== undefined && bb.w !== undefined) {
          return bb.x + bb.w / 2;
        }
      }
    }
    if (typeof note.getAbsoluteX === "function") {
      var baseX = note.getAbsoluteX();
      var width =
        typeof note.getWidth === "function" ? note.getWidth() : null;
      if (typeof width === "number" && !isNaN(width)) {
        return baseX + width / 2;
      }
      if (typeof note.getGlyph === "function" && note.getGlyph()) {
        var glyph = note.getGlyph();
        if (glyph && typeof glyph.getWidth === "function") {
          return baseX + glyph.getWidth() / 2;
        }
      }
      if (typeof note.getStemX === "function") {
        return note.getStemX();
      }
      return baseX;
    }
    return null;
  }

  function getColumnCenterX(col) {
    if (!col) return null;
    if (typeof col.centerX === "number") {
      return col.centerX;
    }
    var notes = (col && col.notes) || [];
    var bassNote = notes.find(function (note) {
      var stave = note && note.getStave && note.getStave();
      return stave && stave.clef === "bass";
    });
    var targetNote = bassNote || notes[0] || null;
    var center = noteCenterX(targetNote);
    if (center === null && typeof col.x === "number") {
      center = col.x;
    }
    if (center === null) {
      return null;
    }
    col.centerX = center;
    return col.centerX;
  }

  function shouldRenderRoman(analyzeConfig) {
    if (!analyzeConfig) return false;
    var mode = analyzeConfig.mode || {};
    return !!(analyzeConfig.roman_numerals || mode.roman_numerals);
  }

  function shouldRenderFigured(analyzeConfig) {
    if (!analyzeConfig) return false;
    var mode = analyzeConfig.mode || {};
    return !!(analyzeConfig.thoroughbass || mode.thoroughbass || mode.abbreviate_thoroughbass);
  }

  function shouldRenderRomanExp(analyzeConfig) {
    if (!analyzeConfig) return false;
    var mode = analyzeConfig.mode || {};
    return !!(analyzeConfig.roman_numerals_exp || mode.roman_numerals_exp || analyzeConfig.roman_exp || mode.roman_exp);
  }

  function shouldRenderNoteNames(analyzeConfig) {
    if (!analyzeConfig) return false;
    var mode = analyzeConfig.mode || {};
    return !!(analyzeConfig.note_names || mode.note_names);
  }

  function shouldRenderScaleDegrees(analyzeConfig) {
    if (!analyzeConfig) return false;
    var mode = analyzeConfig.mode || {};
    return !!(analyzeConfig.scale_degrees || mode.scale_degrees);
  }

  function computeRomanLabel(midi, analyzer) {
    if (!analyzer || !midi || !midi.length) return null;
    try {
      var chordInfo = analyzer.to_chord(midi, "roman only");
      if (chordInfo && chordInfo.label) {
        return chordInfo.label;
      }
    } catch (err) {
      return null;
    }
    return null;
  }

  function getStoredRomanLabel(analysisSlices, onsetTicks) {
    if (!analysisSlices || !analysisSlices.length) return null;
    var ql = onsetTicks / 1024;
    for (var i = 0; i < analysisSlices.length; i++) {
      var sl = analysisSlices[i];
      if (Math.abs(sl.offset - ql) < 0.05 && sl.content && sl.content.roman_numeral) {
        return sl.content.roman_numeral;
      }
    }
    return null;
  }

  function computeFiguredLabel(midi, analyzer, abbreviate) {
    if (!analyzer || !midi || midi.length < 2) return null;
    try {
      var figure = abbreviate
        ? analyzer.abbrev_thoroughbass_figure(midi)
        : analyzer.full_thoroughbass_figure(midi);
      if (!figure) return null;
      var lines = figure
        .split("/")
        .map(function (line) {
          return line
            .replace(/bb/g, "𝄫")
            .replace(/b/g, "♭")
            .replace(/##/g, "𝄪")
            .replace(/#/g, "♯")
            .replace(/n/g, "♮")
            .trim();
        })
        .filter(function (line) {
          return line.length > 0;
        });
      if (!lines.length) return null;
      return lines.join("\n");
    } catch (err) {
      return null;
    }
  }

  function computeRomanExpLabel(midi, analyzer) {
    if (!analyzer || !midi || !midi.length) return null;
    try {
      var chordInfo = analyzer.to_chord(midi, "roman only");
      if (!chordInfo || !chordInfo.label) return null;
      var base = chordInfo.label
        .replace(/\{[^}]*\}/g, "")
        .trim()
        .replace(/bb/g, "𝄫")
        .replace(/b/g, "♭")
        .replace(/##/g, "𝄪")
        .replace(/#/g, "♯");
      if (!base) return null;
      var figure = analyzer.full_thoroughbass_figure(midi) || "";
      var abbrevFigure = analyzer.abbrev_thoroughbass_figure(midi) || "";
      var fullFigureLines = figure
        ? figure
            .split("/")
            .map(function (line) {
              return line
                .replace(/bb/g, "𝄫")
                .replace(/b/g, "♭")
                .replace(/##/g, "𝄪")
                .replace(/#/g, "♯")
                .replace(/n/g, "♮")
                .trim();
            })
            .filter(function (line) {
              return line.length > 0;
            })
        : [];
      var abbrevFigureLines = abbrevFigure
        ? abbrevFigure
            .split("/")
            .map(function (line) {
              return line
                .replace(/bb/g, "𝄫")
                .replace(/b/g, "♭")
                .replace(/##/g, "𝄪")
                .replace(/#/g, "♯")
                .replace(/n/g, "♮")
                .trim();
            })
            .filter(function (line) {
              return line.length > 0;
            })
        : [];
      return {
        base: base,
        fullFigure: figure,
        fullFigurePattern: getFigurePattern(figure),
        fullFigureLines: fullFigureLines,
        abbrevFigure: abbrevFigure,
        abbrevFigurePattern: getFigurePattern(abbrevFigure),
        abbrevFigureLines: abbrevFigureLines,
      };
    } catch (err) {
      return null;
    }
  }

  function formatExplicitNoteNames(spellings) {
    if (!spellings || !spellings.length) return "";
    var accidentalMap = {
      1: "♯",
      "-1": "♭",
      0: "",
      2: "𝄪",
      "-2": "𝄫",
    };
    return spellings
      .map(function (s) {
        var acc = accidentalMap[s.alter] || "";
        return (s.step || "").toUpperCase() + acc;
      })
      .join(" ");
  }

  function groupTimelineByOnset(timeline) {
    var onsetMap = Object.create(null);
    var ordered = [];
    if (!timeline) return ordered;
    timeline.forEach(function (ev) {
      var onset = ev.onset;
      if (!Object.prototype.hasOwnProperty.call(onsetMap, onset)) {
        var measureIdx =
          typeof ev.measureIndex === "number" ? ev.measureIndex : 0;
        onsetMap[onset] = {
          onset: onset,
          events: [],
          measureIndex: measureIdx,
        };
        ordered.push(onsetMap[onset]);
      }
      onsetMap[onset].events.push(ev);
      if (typeof ev.measureIndex === "number") {
        if (typeof onsetMap[onset].measureIndex === "number") {
          onsetMap[onset].measureIndex = Math.min(
            onsetMap[onset].measureIndex,
            ev.measureIndex
          );
        } else {
          onsetMap[onset].measureIndex = ev.measureIndex;
        }
      }
    });
    ordered.sort(function (a, b) {
      if (a.onset !== b.onset) return a.onset - b.onset;
      return a.measureIndex - b.measureIndex;
    });
    return ordered;
  }

  function buildAnalysisWindows(timeline) {
    var windows = groupTimelineByOnset(timeline);
    var activeNotes = [];
    windows.forEach(function (win) {
      var onset = win.onset;
      activeNotes = activeNotes.filter(function (note) {
        return note.end > onset;
      });
      win.events.forEach(function (ev) {
        activeNotes.push({
          midi: ev.midi,
          step: ev.step,
          alter: ev.alter,
          end: ev.onset + ev.duration,
          measureIndex:
            typeof ev.measureIndex === "number" ? ev.measureIndex : win.measureIndex,
        });
      });
      var midiMap = Object.create(null);
      activeNotes.forEach(function (n) {
        midiMap[n.midi] = true;
      });
      win.midiStack = Object.keys(midiMap)
        .map(function (k) {
          return parseInt(k, 10);
        })
        .sort(function (a, b) {
          return a - b;
        });

      var sortedActive = activeNotes.slice().sort(function (a, b) {
        return a.midi - b.midi;
      });
      var seenSpelling = {};
      win.spellingStack = [];
      sortedActive.forEach(function (n) {
        if (n.step === undefined) return;
        var key = n.step + (n.alter || 0);
        if (!seenSpelling[key]) {
          seenSpelling[key] = true;
          win.spellingStack.push({ step: n.step, alter: n.alter || 0 });
        }
      });
      var attackMap = Object.create(null);
      win.events.forEach(function (ev) {
        attackMap[ev.midi] = true;
      });
      win.attackKey = Object.keys(attackMap)
        .map(function (k) {
          return parseInt(k, 10);
        })
        .sort(function (a, b) {
          return a - b;
        })
        .join(",");
    });
    return windows;
  }

  return {
    isRestTickable: isRestTickable,
    keyToMidi: keyToMidi,
    tickableToScaleDegreeMidi: tickableToScaleDegreeMidi,
    getBassLabelAtOffset: getBassLabelAtOffset,
    normalizeKeyForVexFlow: normalizeKeyForVexFlow,
    getKeySignatureAlterations: getKeySignatureAlterations,
    resolveChordNoteStyles: resolveChordNoteStyles,

    durToVF: durToVF,
    convertRomanSymbols: convertRomanSymbols,
    getFigurePattern: getFigurePattern,
    getRomanExpDisplayFigureLines: getRomanExpDisplayFigureLines,
    formatExplicitNoteNames: formatExplicitNoteNames,
    noteCenterX: noteCenterX,
    getColumnCenterX: getColumnCenterX,
    shouldRenderRoman: shouldRenderRoman,
    shouldRenderFigured: shouldRenderFigured,
    shouldRenderRomanExp: shouldRenderRomanExp,
    shouldRenderNoteNames: shouldRenderNoteNames,
    shouldRenderScaleDegrees: shouldRenderScaleDegrees,
    computeRomanLabel: computeRomanLabel,
    getStoredRomanLabel: getStoredRomanLabel,
    computeFiguredLabel: computeFiguredLabel,
    computeRomanExpLabel: computeRomanExpLabel,
    groupTimelineByOnset: groupTimelineByOnset,
    buildAnalysisWindows: buildAnalysisWindows,
  };
});
