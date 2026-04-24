/* global define: false */

define([
  "lodash",
  "vexflow",
  "app/components/music/score_timeline",
  "app/utils/analyze",
  "app/utils/measure_engine",
], function (_, Vex, ScoreTimeline, Analyze, MeasureEngine) {
  "use strict";

  function durToVF(d) {
    var type = d.type;
    var map = { 'whole': 'w', 'half': 'h', 'quarter': 'q', 'eighth': '8', '16th': '16', '32nd': '32', 'e': '8', 's': '16' };
    return map[type] || type;
  }

  // Returns the alteration (in semitones) that the key signature applies to each step (C, D, E, F, G, A, B)
  // For example, F major (1 flat: Bb) returns { B: -1 }
  // For example, G major (1 sharp: F#) returns { F: 1 }

  function drawInlineRoman(ctx, label, columnX, stave, opts) {
    if (!ctx || !label) return;
    var text = String(label);
    var lines = text.split(/\n+/).filter(function (line) {
      return line.length > 0;
    });
    if (!lines.length) {
      return;
    }
    var yBase = (stave && stave.getBottomY) ? stave.getBottomY() : 100;
    var y = yBase + ((opts && opts.yShift) || 30);
    ctx.save();
    var color = (opts && opts.color) || "#000";
    if (typeof ctx.setFillStyle === "function") ctx.setFillStyle(color);
    ctx.fillStyle = color;
    ctx.font = "16px Arial, sans-serif";
    ctx.textAlign = "left";
    var lineHeight = (opts && opts.lineHeight) || 16;

    lines.forEach(function (line, lineIdx) {
      var glyphs = Array.from(line);
      var midIndex = glyphs.length ? Math.floor((glyphs.length - 1) / 2) : 0;
      var leftText =
        midIndex > 0 ? glyphs.slice(0, midIndex).join("") : "";
      var centerGlyph = glyphs[midIndex] || "";
      var leftWidth = leftText ? ctx.measureText(leftText).width : 0;
      var centerWidth = centerGlyph ? ctx.measureText(centerGlyph).width : 0;
      var startX = Math.round(columnX - leftWidth - centerWidth / 2);
      var lineY = y + lineIdx * lineHeight;
      ctx.fillText(line, startX, lineY);
    });

    ctx.restore();
  }

  function drawInlineRomanExp(ctx, parts, columnX, stave, opts) {
    if (!ctx || !parts || !parts.base) return;

    var yBase = (stave && stave.getBottomY) ? stave.getBottomY() : 0;
    var y = yBase + ((opts && opts.yShift) || 30);
    var figureLines = parts.figureLines || [];
    var figureCenterX = columnX + 6;

    ctx.save();
    if (typeof ctx.setFillStyle === "function") ctx.setFillStyle("#000");
    ctx.fillStyle = "#000";
    ctx.textAlign = "left";

    ctx.font = "18px JazzSerifs";
    var baseWidth = ctx.measureText(parts.base).width;
    var baseX = Math.round(figureCenterX - baseWidth - 10);
    var slashIdx = parts.base.indexOf("/");
    if (slashIdx >= 0) {
      var topPart = parts.base.slice(0, slashIdx);
      var bottomPart = parts.base.slice(slashIdx + 1);
      var topWidth = ctx.measureText(topPart).width;
      var topPartX = Math.round(figureCenterX - topWidth / 2) - 10;
      ctx.fillText(topPart, topPartX, y);
      ctx.fillText("/", topPartX + topWidth - 3, y + 9);
      ctx.fillText(bottomPart, topPartX + topWidth + 3, y + 14);
    } else {
      ctx.fillText(parts.base, baseX, y);
    }

    if (figureLines.length) {
      var figureLineHeight = (opts && opts.lineHeight) || 12;
      var figureStartY = y - 12;
      ctx.font = "13px MainSerifs";
      figureLines.forEach(function (line, index) {
        var lineWidth = ctx.measureText(line).width;
        ctx.fillText(
          line,
          Math.round(figureCenterX - lineWidth / 2),
          figureStartY + index * figureLineHeight
        );
      });
    }

    ctx.restore();
  }

  function drawInlineRomanExpRun(ctx, run, stave, opts) {
    if (!ctx || !run || !run.base || !run.columns || !run.columns.length) return;

    var yBase = (stave && stave.getBottomY) ? stave.getBottomY() : 0;
    var y = yBase + ((opts && opts.yShift) || 30);
    var lineHeight = (opts && opts.lineHeight) || 12;
    var figureStartY = y - 12;
    var firstX = run.columns[0].x + 6;
    var maxRows = run.columns.reduce(function (count, column) {
      return Math.max(count, (column.figureLines || []).length);
    }, 0);

    ctx.save();
    ctx.fillStyle = "#000";
    ctx.textAlign = "left";

    ctx.font = "18px JazzSerifs";
    var baseWidth = ctx.measureText(run.base).width;
    var runBaseX = Math.round(firstX - baseWidth - 10);
    var slashIdxRun = run.base.indexOf("/");
    if (slashIdxRun >= 0) {
      var topPartRun = run.base.slice(0, slashIdxRun);
      var bottomPartRun = run.base.slice(slashIdxRun + 1);
      var topWidthRun = ctx.measureText(topPartRun).width;
      var topPartRunX = Math.round(firstX - topWidthRun / 2) - 10;
      ctx.fillText(topPartRun, topPartRunX, y);
      ctx.fillText("/", topPartRunX + topWidthRun - 3, y + 9);
      ctx.fillText(bottomPartRun, topPartRunX + topWidthRun + 3, y + 14);
    } else {
      ctx.fillText(run.base, runBaseX, y);
    }

    if (maxRows > 0) {
      ctx.font = "13px MainSerifs";
      for (var rowIdx = 0; rowIdx < maxRows; rowIdx++) {
        var rowY = figureStartY + rowIdx * lineHeight;
        for (var colIdx = 0; colIdx < run.columns.length; colIdx++) {
          var column = run.columns[colIdx];
          var columnX = column.x + 6;
          var currentLine = (column.figureLines || [])[rowIdx] || "";
          if (colIdx > 0) {
            var previousColumn = run.columns[colIdx - 1];
            var previousLine = (previousColumn.figureLines || [])[rowIdx] || "";
            if (previousLine && currentLine) {
              var dashX = (previousColumn.x + column.x) / 2 + 6;
              var dashWidth = ctx.measureText("-").width;
              ctx.fillText("-", Math.round(dashX - dashWidth / 2), rowY);
            }
          }
          if (!currentLine) {
            continue;
          }
          var lineWidth = ctx.measureText(currentLine).width;
          ctx.fillText(currentLine, Math.round(columnX - lineWidth / 2), rowY);
        }
      }
    }

    ctx.restore();
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

  var FIGURE_TOKEN_MAP = {
    "z": "6",
    "z4": "6/4",
    "z5": "6/5",
    "u": "7",
    "u3": "6/5",
    "u5": "7/5",
    "r": "4",
    "r2": "4/2",
    "r3": "4/3",
    "i3": "3",
    "q e": "13",
  };

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

  function computeRomanLabel(midi, analyzer) {
    if (!analyzer || !midi || !midi.length) return null;
    try {
      var chordInfo = analyzer.to_chord(midi, "roman only");
      if (chordInfo && chordInfo.label) {
        var label = chordInfo.label;
        if (!label || label.indexOf("{") === -1) {
          return label;
        }
        return label.replace(/\{([^}]+)\}/g, function (_, token) {
          token = (token || "").trim();
          if (!token) return "";
          var mapped = FIGURE_TOKEN_MAP[token];
          return mapped !== undefined ? mapped : "";
        });
      }
    } catch (err) {
      return null;
    }
    return null;
  }

  function normalizeKeyForVexFlow(key) {
    if (!key) return "C";
    var k = String(key).trim();
    // Handle HarmonyLab format: iG_ -> Gm, jG_ -> G
    if (k.startsWith('i') || k.startsWith('j')) {
      var mode = k.charAt(0);
      var root = k.substring(1).replace('_', '');
      return mode === 'i' ? root + 'm' : root;
    }
    // Handle lowercase keys (music21 style): g -> Gm, c -> Cm
    if (k.length > 0 && k[0] === k[0].toLowerCase()) {
      var root = k[0].toUpperCase() + k.substring(1);
      return root.endsWith('m') ? root : root + 'm';
    }
    return k;
  }

  function getKeySignatureAlterations(key) {
    if (!key) return {};
    
    var alterations = {};
    var k = normalizeKeyForVexFlow(key);
    
    // Map key to number of sharps (positive) or flats (negative)
    var map = {
      'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
      'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
      'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
      'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5, 'Ebm': -6, 'Abm': -7
    };
    
    var accCount = map[k] || 0;
    
    // Order of sharps: F C G D A E B
    // Order of flats: B E A D G C F
    if (accCount > 0) {
      // Sharps
      var sharpOrder = ['F', 'C', 'G', 'D', 'A', 'E', 'B'];
      for (var i = 0; i < accCount && i < sharpOrder.length; i++) {
        alterations[sharpOrder[i]] = 1;
      }
    } else if (accCount < 0) {
      // Flats
      var flatOrder = ['B', 'E', 'A', 'D', 'G', 'C', 'F'];
      for (var i = 0; i < Math.abs(accCount) && i < flatOrder.length; i++) {
        alterations[flatOrder[i]] = -1;
      }
    }
    
    return alterations;
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

  function attachInlineRomanAnnotation(
    col,
    midi,
    analyzeConfig,
    analyzer,
    ctx,
    fallbackStave,
    opts,
    labelOverride
  ) {
    if (!analyzer || !ctx || !col) {
      return;
    }
    var label =
      typeof labelOverride === "string"
        ? labelOverride
        : computeRomanLabel(midi, analyzer);
    if (!label) {
      return;
    }
    var x = getColumnCenterX(col);
    if (x === null) {
      return;
    }
    var targetStave = fallbackStave || null;
    if (col && col.notes && col.notes.length) {
      for (var i = 0; i < col.notes.length; i++) {
        var stave = col.notes[i].getStave && col.notes[i].getStave();
        if (stave && stave.clef === "bass") {
          targetStave = stave;
          break;
        }
        if (!targetStave && stave) {
          targetStave = stave;
        }
      }
    }
    drawInlineRoman(ctx, label, x, targetStave, opts || { yShift: 28 });
  }

  function attachNoteNameAnnotation(
    col,
    midi,
    analyzeConfig,
    analyzer,
    ctx,
    fallbackStave,
    opts,
    labelOverride
  ) {
    if (!analyzer || !ctx || !col) {
      return;
    }
    var label =
      typeof labelOverride === "string"
        ? labelOverride
        : analyzer.to_note_name(midi);
    if (!label) {
      return;
    }
    var x = getColumnCenterX(col);
    if (x === null) {
      return;
    }
    var targetStave = fallbackStave || null;
    if (col && col.notes && col.notes.length) {
      for (var i = 0; i < col.notes.length; i++) {
        var stave = col.notes[i].getStave && col.notes[i].getStave();
        if (stave && stave.clef === "bass") {
          targetStave = stave;
          break;
        }
        if (!targetStave && stave) {
          targetStave = stave;
        }
      }
    }
    drawInlineRoman(ctx, label, x, targetStave, opts || { yShift: 28 });
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

  function itemToTickable(clef, item, octaveShift, idState, keySignatureAlterations, onset, measureIndex, showNotation) {
    if (showNotation === undefined) showNotation = true;
    if (item.kind === "rest") {
      var dur = durToVF(item.duration) + "r";
      var numDots = item.duration.dots || 0;
      var rest = new Vex.Flow.StaveNote({ clef: clef, keys: ["b/4"], duration: dur, dots: numDots });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([rest], { all: true });
      
      // Tag with musical position
      rest._onset = onset;
      rest._measureIndex = measureIndex;
      
      return rest;
    }
    if (item.kind === "note") {
      var alter = item.pitch.alter || 0;
      var acc = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "";
      var oshift = octaveShift || 0;
      var key = item.pitch.step.toLowerCase() + acc + "/" + (item.pitch.octave + oshift);
      var numDots = item.duration.dots || 0;
      var note = new Vex.Flow.StaveNote({ clef: clef, keys: [key], duration: durToVF(item.duration), dots: numDots });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([note], { all: true });

      // Tag with musical position
      note._onset = onset;
      note._measureIndex = measureIndex;

      // Only show accidental if it contradicts the key signature
      var keyAlters = keySignatureAlterations || {};
      var step = item.pitch.step.toUpperCase();
      var keyAlter = keyAlters[step] || 0;
      
      // If the note's alteration differs from the key signature, show an accidental
      if (alter !== keyAlter) {
        var accType = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "n";
        note.addModifier(new Vex.Flow.Accidental(accType), 0);
      }
      
      // Default: gray until played (will be set to black by matcher later)
      var played = idState && idState.playedNoteIds && idState.playedNoteIds.has(idState.nextId || 0);
      if (note.setStyle) {
        if (played) {
          note.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
        } else if (!showNotation) {
          note.setStyle({ fillStyle: "transparent", strokeStyle: "transparent" });
        } else {
          note.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
        }
      }
      if (idState) idState.nextId = (idState.nextId || 0) + 1;
      return note;
    }
    if (item.kind === "chord") {
      var oshift = octaveShift || 0;
      var keys = item.notes.map(function (n) {
        var alter = n.pitch.alter || 0;
        var acc = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "";
        return n.pitch.step.toLowerCase() + acc + "/" + (n.pitch.octave + oshift);
      });
      var numDots = item.duration.dots || 0;
      var chord = new Vex.Flow.StaveNote({ clef: clef, keys: keys, duration: durToVF(item.duration), dots: numDots });
      if (numDots > 0) Vex.Flow.Dot.buildAndAttach([chord], { all: true });

      // Only show accidentals that contradict the key signature
      var keyAlters = keySignatureAlterations || {};
      for (var i = 0; i < item.notes.length; i++) {
        var alter = item.notes[i].pitch.alter || 0;
        var step = item.notes[i].pitch.step.toUpperCase();
        var keyAlter = keyAlters[step] || 0;
        
        // If the note's alteration differs from the key signature, show an accidental
        if (alter !== keyAlter) {
          var accType = alter === 1 ? "#" : alter === -1 ? "b" : alter === 2 ? "##" : alter === -2 ? "bb" : "n";
          chord.addModifier(new Vex.Flow.Accidental(accType), i);
        }
      }
      
      // Tag with musical position
      chord._onset = onset;
      chord._measureIndex = measureIndex;
      
      // Default: gray until played (per notehead)
      if (chord.setStyle) {
        var playedAny = idState && idState.playedNoteIds && idState.playedNoteIds.has(idState.nextId || 0);
        if (playedAny) {
          chord.setStyle({ fillStyle: '#000000', strokeStyle: '#000000' });
        } else if (!showNotation) {
          chord.setStyle({ fillStyle: 'transparent', strokeStyle: 'transparent' });
        } else {
          chord.setStyle({ fillStyle: '#9aa0a6', strokeStyle: '#9aa0a6' });
        }
      }
      if (idState) {
        var idx = idState.nextId || 0;
        for (var h = 0; h < keys.length; h++) {
          var played = idState.playedNoteIds && idState.playedNoteIds.has(idx + h);
          if (played && chord.setKeyStyle) {
            chord.setKeyStyle(h, { fillStyle: '#000000', strokeStyle: '#000000' });
          }
        }
        idState.nextId = idx + keys.length;
      }
      return chord;
    }
    return null;
  }

  function buildVoice(time, tickables) {
    var voice = new Vex.Flow.Voice(time);
    // Allow incomplete voices (for pickup measures / anacrusis)
    voice.setMode(Vex.Flow.Voice.Mode.SOFT);
    voice.addTickables(tickables);
    return voice;
  }

  // Add a key signature with a minor->relative-major fallback for older VexFlow builds
  function addKeySignatureSafe(stave, key) {
    if (!key) return;
    var k = normalizeKeyForVexFlow(key);
    try {
      stave.addKeySignature(k);
    } catch (e) {
      // Some VexFlow versions only accept major names; try relative major for minor keys
      var minorToRelativeMajor = {
        "Am": "C",  "Em": "G",  "Bm": "D",  "F#m": "A",  "C#m": "E",
        "G#m": "B", "D#m": "F#", "A#m": "C#", "Dm": "F",   "Gm": "Bb",
        "Cm": "Eb", "Fm": "Ab", "Bbm": "Db", "Ebm": "Gb", "Abm": "Cb"
      };
      var fallback = minorToRelativeMajor[k];
      if (fallback) {
        try { stave.addKeySignature(fallback); } catch (_) { /* ignore */ }
      }
    }
  }

  function makeStave(ctx, x, y, w, clef, meta, addClef) {
    console.log("[ID] makeStave. clef:", clef, "addClef:", addClef, "meta:", meta);
    var stave = new Vex.Flow.Stave(x, y, w);
    stave.setContext(ctx);
    if (addClef) {
      stave.addClef(clef);
      if (meta && meta.key) {
        console.log("[ID] adding key:", meta.key);
        addKeySignatureSafe(stave, meta.key);
      }
      if (meta && meta.time) {
        console.log("[ID] adding time:", meta.time);
        stave.addTimeSignature(meta.time);
      }
    }
    return stave;
  }

  function render(score, renderer, opts) {
    var ctx = renderer.getContext();
    
    // Get canvas element - it's stored in ctx.canvas or ctx.element depending on VexFlow version
    var canvas = ctx.canvas || ctx.element;
    
    // Clear canvas first
    if (canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    
    ctx.save();
    try {
      var margin = { left: 20, right: 20, top: 20, bottom: 20 };
      var width = (opts && opts.width) || (canvas && canvas.width) || 800;
      var height = (opts && opts.height) || (canvas && canvas.height) || 300;
      var meta = score.meta || {};
      var analyzeConfig = (opts && opts.analyzeConfig) || { enabled: false, mode: {} };
      var keySignatureModel = (opts && opts.keySignature) || (score.meta && score.meta.key ? new KeySignature(score.meta.key) : new KeySignature("C"));
      var analysisRenderer = (opts && opts.analysisRenderer) || "notater"; // notater|adapter|none
      var inlineAnalyzer = null;
      if (analyzeConfig && analyzeConfig.enabled && analysisRenderer !== "none") {
        try {
          inlineAnalyzer = new Analyze(keySignatureModel);
        } catch (err) {
          inlineAnalyzer = null;
        }
      }
      var renderRomans = shouldRenderRoman(analyzeConfig);
      var renderFigured = !renderRomans && shouldRenderFigured(analyzeConfig);
      var renderRomanExp = !renderRomans && !renderFigured && shouldRenderRomanExp(analyzeConfig);
      var renderNoteNames = !renderRomans && !renderFigured && !renderRomanExp && shouldRenderNoteNames(analyzeConfig);
      if (!inlineAnalyzer) {
        renderRomans = false;
        renderFigured = false;
        renderRomanExp = false;
        renderNoteNames = false;
      }
      var showNotation = opts && opts.showNotation !== undefined ? opts.showNotation : true;

      var systemGap = (opts && opts.systemGap) || 150; // vertical spacing between treble and bass staves
      var staffYOffset = (opts && opts.staffYOffset) || 0;
      var baseRomanYOffset = 32;
      var baseFiguredYOffset = 18;
      var romanYOffset = baseRomanYOffset - staffYOffset;
      var figuredYOffset = baseFiguredYOffset - staffYOffset;
      
      // Calculate key signature alterations once for the entire score
      var keySignatureAlterations = getKeySignatureAlterations(meta.key);

      if (!score.measures || score.measures.length === 0) {
        return;
      }

      // Limit to first N measures for initial view (default 4)
      var maxMeasures = opts && opts.maxMeasures !== undefined ? opts.maxMeasures : 4;
      var startMeasure = opts && opts.startMeasure ? parseInt(opts.startMeasure, 10) : 0;
      if (isNaN(startMeasure) || startMeasure < 0) {
        startMeasure = 0;
      }
      var totalMeasures = score.measures.length;
      if (startMeasure >= totalMeasures) {
        startMeasure = Math.max(0, totalMeasures - 1);
      }
      var remainingMeasures = Math.max(0, totalMeasures - startMeasure);
      var numMeasures = Math.min(remainingMeasures, maxMeasures);
      if (numMeasures <= 0) {
        return;
      }
      var measuresToRender = score.measures.slice(startMeasure, startMeasure + numMeasures);
      var timeline = ScoreTimeline && ScoreTimeline.buildTimeline
        ? ScoreTimeline.buildTimeline(score, {
            startMeasure: startMeasure,
            maxMeasures: numMeasures,
          })
        : [];
      
      // Calculate absolute window offset for playhead alignment
      var absoluteWindowOffset = 0;
      if (startMeasure > 0 && ScoreTimeline && ScoreTimeline.buildTimeline) {
        var fullTimeline = ScoreTimeline.buildTimeline(score);
        var allWindows = buildAnalysisWindows(fullTimeline);
        for (var i = 0; i < allWindows.length; i++) {
          if (allWindows[i].measureIndex < startMeasure) {
            absoluteWindowOffset++;
          } else {
            break;
          }
        }
      }

      var analysisWindows = buildAnalysisWindows(timeline);
      var analysisWindowIdx = 0;
      var staffDistribution = (opts && opts.staffDistribution) || (meta && meta.staffDistribution) || "grand_staff";
      var showTreble = staffDistribution !== "bass";
      var showBass = staffDistribution !== "treble";

      var systemGap = (opts && opts.systemGap) || 150; // vertical spacing between treble and bass staves
      var staffYOffset = (opts && opts.staffYOffset) || 0;
      var trebleY = margin.top + 30 + staffYOffset;
      var bassY = showTreble ? trebleY + systemGap : trebleY;

      // Time from metadata if present; default 4/4
      var time = (function () {
        if (meta && meta.time) {
          var parts = meta.time.split("/");
          var num = parseInt(parts[0], 10) || 4;
          var den = parseInt(parts[1], 10) || 4;
          return { num_beats: num, beat_value: den, resolution: Vex.Flow.RESOLUTION };
        }
        return { num_beats: 4, beat_value: 4, resolution: Vex.Flow.RESOLUTION };
      })();

      function autoBeam(tickables, stemDirection) {
        try {
          return Vex.Flow.Beam.generateBeams(tickables, {
            beam_rests: false,
            stem_direction: stemDirection || 1,
          });
        } catch(e) {
          return [];
        }
      }

      function staffVoices(staffId, staff, clef, idState, keySignatureAlterations, measureStartTick) {
        if (!staff) return [];
        // Optional filtering: opts.selectVoices = { treble: [0], bass: [1] }
        var select = (opts && opts.selectVoices && opts.selectVoices[staffId]) || null;
        // Optional octave shift per staff: opts.octaveShift = { treble: 0, bass: -1 }
        var octaveShift = (opts && opts.octaveShift && (opts.octaveShift[staffId] || 0)) || 0;
        // Note playing state across this render; keep shared across entire piece for consistent IDs
        idState = idState || { nextId: 0, playedNoteIds: (opts && opts.playedNoteIds) || null };
        var measStartTick = measureStartTick || 0;
        return (staff.voices || [])
          .map(function (v, vIdx) {
            if (select && select.indexOf(vIdx) === -1) return null; // filter out

            var localOnset = 0;
            var tickables = v.items.map(function (it) {
              var onsetToUse = measStartTick + localOnset;
              localOnset += durationToTicks(it.duration);
              return itemToTickable(clef, it, octaveShift, idState, keySignatureAlterations, onsetToUse, absoluteMeasureIndex, showNotation);
            }).filter(Boolean);
            
            var stemDir = v.direction === "up" ? 1 : v.direction === "down" ? -1 : 1;
            if (v.direction === "up") tickables.forEach(function (t) { if (t.setStemDirection) t.setStemDirection(1); });
            if (v.direction === "down") tickables.forEach(function (t) { if (t.setStemDirection) t.setStemDirection(-1); });

            // Only beam outer voices (S=treble idx0 stems-up, B=bass idx1 stems-down).
            // Inner voices (A=treble idx1, T=bass idx0) beam toward the opposing staff — skip.
            var isOuterVoice = (stemDir === 1 && vIdx === 0) || (stemDir === -1 && vIdx === 1);
            var beams = isOuterVoice ? autoBeam(tickables, stemDir) : [];
            
            var voice = buildVoice(time, tickables);
            voice.beams = beams; // Store beams for later drawing
            return voice;
          })
          .filter(Boolean);
      }

      // Pre-calculate measure widths based on actual duration
      var measureWidths = [];
      
      // Helper to convert duration to ticks
      function durationToTicks(dur) {
        return MeasureEngine.getTicks(dur.type, dur.dots || 0);
      }
      
      // Count noteheads in a measure (respects optional voice filtering)
      function countNoteheads(meas) {
        var total = 0;
        ['treble', 'bass'].forEach(function(staffName) {
          var staff = meas.staves[staffName];
          if (!staff || !staff.voices) return;
          var select = (opts && opts.selectVoices && opts.selectVoices[staffName]) || null;
          staff.voices.forEach(function(voice, vIdx) {
            if (select && select.indexOf(vIdx) === -1) return;
            voice.items.forEach(function(item) {
              if (item.kind === 'note') total += 1;
              if (item.kind === 'chord' && item.notes && item.notes.length) total += item.notes.length;
            });
          });
        });
        return total;
      }
      
      // Number of noteheads prior to the first rendered measure (aligns note IDs with grader timeline)
      var startNoteOffset = 0;
      if (startMeasure > 0) {
        for (var pre = 0; pre < startMeasure; pre++) {
          var priorMeasure = score.measures[pre];
          if (priorMeasure) {
            startNoteOffset += countNoteheads(priorMeasure);
          }
        }
      }
      
      // Estimate key signature complexity by counting accidentals
      function getKeyAccidentalsCount(key) {
        if (!key) return 0;
        // Normalize key string (capitalize first char, keep trailing m if minor)
        var k = String(key).trim();
        var map = {
          'C': 0, 'G': 1, 'D': 2, 'A': 3, 'E': 4, 'B': 5, 'F#': 6, 'C#': 7,
          'F': -1, 'Bb': -2, 'Eb': -3, 'Ab': -4, 'Db': -5, 'Gb': -6, 'Cb': -7,
          'Am': 0, 'Em': 1, 'Bm': 2, 'F#m': 3, 'C#m': 4, 'G#m': 5, 'D#m': 6, 'A#m': 7,
          'Dm': -1, 'Gm': -2, 'Cm': -3, 'Fm': -4, 'Bbm': -5, 'Ebm': -6, 'Abm': -7
        };
        // Try exact; otherwise attempt uppercase base with optional 'm'
        if (Object.prototype.hasOwnProperty.call(map, k)) return map[k];
        return 0;
      }
      
      // Compute dynamic overhead for first measure (clef + key + time). Only applied for pickups.
      function computeFirstMeasureOverhead(meta) {
        var baseClefPx = 28;      // clef glyph
        var leftGapPx = 10;       // breathing room before first note
        var perAccidentalPx = 12; // width per sharp/flat
        var perTimeDigitPx = 8;   // width per time signature digit
        var timeGapPx = 6;        // gap after time signature
        var accCount = Math.abs(getKeyAccidentalsCount(meta && meta.key));
        var timeDigits = 0;
        if (meta && meta.time && meta.time.indexOf('/') !== -1) {
          var parts = meta.time.split('/');
          timeDigits = (parts[0] ? String(parts[0]).length : 0) + (parts[1] ? String(parts[1]).length : 0);
        }
        return leftGapPx + baseClefPx + (accCount * perAccidentalPx) + (timeDigits * perTimeDigitPx) + timeGapPx;
      }
      
      // A full measure in this time signature (e.g., 4 quarter notes in 4/4 = 4096 ticks)
      var fullMeasureTicks = time.num_beats * (4096 / time.beat_value);
      
      // Calculate duration for each measure
      var measureDurations = [];
      for (var i = 0; i < numMeasures; i++) {
        var meas = measuresToRender[i];
        var maxTicks = 0;
        
        // Calculate actual duration (max across voices)
        ['treble', 'bass'].forEach(function(staffName) {
          var staff = meas.staves[staffName];
          if (staff && staff.voices) {
            staff.voices.forEach(function(voice) {
              var voiceTicks = 0;
              voice.items.forEach(function(item) {
                voiceTicks += durationToTicks(item.duration);
              });
              maxTicks = Math.max(maxTicks, voiceTicks);
            });
          }
        });
        
        measureDurations.push(maxTicks);
      }
      
      // Calculate widths using weights and dynamic overhead for pickup
      var minPartialMeasureWidth = 80; // Minimum width for partial measures (for notes area only)
  var isPickup = measureDurations.length > 0 && (measureDurations[0] < fullMeasureTicks * 0.95);
  // For pickups, dynamicOverhead reserves space for clef/key/time before notes.
  var dynamicOverhead = isPickup ? computeFirstMeasureOverhead(meta) : 0;
  // For full first measures, compensate left padding so its notes area matches other full bars.
  var firstBarCompensation = !isPickup ? computeFirstMeasureOverhead(meta) : 0;

      // Minimum notes width for the pickup based on VexFlow's formatter (pre-calculated)
      var pickupNotesMinWidth = 0;
      if (isPickup) {
        try {
          var pickupMeasure = measuresToRender[0];
          var voicesT = staffVoices("treble", pickupMeasure.staves.treble, "treble", null, keySignatureAlterations);
          var voicesB = staffVoices("bass", pickupMeasure.staves.bass, "bass", null, keySignatureAlterations);
          var allPickupVoices = voicesT.concat(voicesB);
          if (allPickupVoices.length) {
            var fmin = new Vex.Flow.Formatter();
            // Join by staff for better alignment before measuring
            if (voicesT.length) fmin.joinVoices(voicesT);
            if (voicesB.length) fmin.joinVoices(voicesB);
            pickupNotesMinWidth = fmin.preCalculateMinTotalWidth(allPickupVoices) || 0;
          }
        } catch (e) {
          pickupNotesMinWidth = 0; // fallback silently
        }
      }

      // Helper: get minimal notes width for an arbitrary measure (used for other partials, e.g., final bar)
      function measureNotesMinWidth(mIndex) {
        try {
          var m = measuresToRender[mIndex];
          var vT = staffVoices("treble", m.staves.treble, "treble", null, keySignatureAlterations);
          var vB = staffVoices("bass", m.staves.bass, "bass", null, keySignatureAlterations);
          var all = vT.concat(vB);
          if (!all.length) return 0;
          var fm = new Vex.Flow.Formatter();
          if (vT.length) fm.joinVoices(vT);
          if (vB.length) fm.joinVoices(vB);
          return fm.preCalculateMinTotalWidth(all) || 0;
        } catch (e) { return 0; }
      }

      // Build weights: full = 1, partials < 1; pickup scales with duration and note density
      var weights = [];
      for (var wi = 0; wi < numMeasures; wi++) {
        var dur = measureDurations[wi];
        var ratio = Math.max(0, Math.min(1, dur / fullMeasureTicks));
        if (dur >= fullMeasureTicks * 0.95) {
          weights.push(1);
        } else if (wi === 0) {
          // Pickup: we've already reserved a base width (overhead + min notes width). Avoid double-allocation.
          // Give it zero proportional share so it doesn't steal space from full bars.
          weights.push(0);
        } else {
          // Other partials (rare): tie to duration with a floor
          weights.push(Math.max(0.5, ratio));
        }
      }

      // Establish base widths (fixed) and distribute the remainder proportionally via weights
      var baseWidths = new Array(numMeasures).fill(0);
      if (isPickup) {
        // Convert notes min width to whole-measure min using our notes area factor (80%)
        var pickupMinMeasureFromNotes = pickupNotesMinWidth > 0 ? (pickupNotesMinWidth / 0.8) : 0;
        baseWidths[0] = dynamicOverhead + Math.max(minPartialMeasureWidth, pickupMinMeasureFromNotes);
      } else {
        // No pickup: compensate for clef/key/time so first full bar's notesWidth is not penalized
        baseWidths[0] = firstBarCompensation;
      }

      var availableWidth = width - margin.left - margin.right;
      var requiredBase = baseWidths.reduce(function(a,b){return a+b;}, 0);
      var remaining = Math.max(0, availableWidth - requiredBase);
      var totalWeight = weights.reduce(function(a, b) { return a + b; }, 0) || 1;
      var unitWidth = remaining / totalWeight;

      for (var mw = 0; mw < numMeasures; mw++) {
        var extra = unitWidth * weights[mw];
        var widthCandidate = baseWidths[mw] + extra;
        // Enforce a minimum notes-area width for any partial measure to avoid crumpling
        if (measureDurations[mw] < fullMeasureTicks * 0.95) {
          var minFromNotes = 0;
          var notesMin = (mw === 0 ? pickupNotesMinWidth : measureNotesMinWidth(mw));
          if (notesMin > 0) minFromNotes = notesMin / 0.8; // convert to whole-measure width
          widthCandidate = Math.max(baseWidths[mw], Math.max(minPartialMeasureWidth, minFromNotes));
        }
        measureWidths.push(widthCandidate);
      }

      // Render each measure horizontally (limited to numMeasures)
      var currentX = margin.left;
      // Shared ID state across all measures and staves to match timeline IDs
      var globalIdState = { nextId: startNoteOffset, playedNoteIds: (opts && opts.playedNoteIds) || null };
      var lastTrebleStave = null;
      var lastBassStave = null;
      var pendingRomanExpRun = null;

      function flushRomanExpRun() {
        if (!pendingRomanExpRun || !pendingRomanExpRun.columns.length) {
          pendingRomanExpRun = null;
          return;
        }
        drawInlineRomanExpRun(
          ctx,
          pendingRomanExpRun,
          pendingRomanExpRun.stave || lastBassStave,
          { yShift: romanYOffset, lineHeight: 11 }
        );
        pendingRomanExpRun = null;
      }

      function queueRomanExpColumn(col, expLabel, stave) {
        if (!expLabel || !expLabel.base) {
          flushRomanExpRun();
          return;
        }

        var expX = getColumnCenterX(col);
        if (expX === null) {
          flushRomanExpRun();
          return;
        }

        var column = {
          x: expX,
          figureLines: getRomanExpDisplayFigureLines(
            expLabel,
            pendingRomanExpRun ? pendingRomanExpRun.lastLabel : null
          ).slice(),
        };

        if (pendingRomanExpRun && pendingRomanExpRun.base === expLabel.base) {
          pendingRomanExpRun.columns.push(column);
          pendingRomanExpRun.stave = stave || pendingRomanExpRun.stave;
          pendingRomanExpRun.lastLabel = expLabel;
          return;
        }

        flushRomanExpRun();
        pendingRomanExpRun = {
          base: expLabel.base,
          columns: [column],
          lastLabel: expLabel,
          stave: stave || lastBassStave,
        };
      }

      var cumulativeMeasureTick = 0;
      for (var measIdx = 0; measIdx < numMeasures; measIdx++) {
        var meas = measuresToRender[measIdx];
        var treble = meas.staves.treble;
        var bass = meas.staves.bass;

        var measureWidth = measureWidths[measIdx];
        var isFirstMeasure = measIdx === 0;
        var absoluteMeasureIndex = startMeasure + measIdx;

        var trebleStave = showTreble ? makeStave(ctx, currentX, trebleY, measureWidth, "treble", isFirstMeasure ? meta : {}, isFirstMeasure) : null;
        var bassStave = showBass ? makeStave(ctx, currentX, bassY, measureWidth, "bass", isFirstMeasure ? meta : {}, isFirstMeasure) : null;
        var activeStaveForLabel = bassStave || trebleStave;

        // Draw explicit key label beneath the bass clef (e.g., "Am:", "C:")
        function formatKeyForDisplay(k) {
          if (!k || typeof k !== 'string' || k.length < 2) return k;
          var mode = k.charAt(0);
          var tonic = k.slice(1).replace(/_/g, "");
          return tonic + (mode === 'i' ? 'm' : '');
        }

        var displayKey = (opts && opts.keySignature && typeof opts.keySignature.getKey === 'function') 
          ? formatKeyForDisplay(opts.keySignature.getKey())
          : (meta && meta.key);

        if (isFirstMeasure && displayKey && activeStaveForLabel) {
          ctx.save();
          ctx.font = "16px Arial, sans-serif";
          ctx.fillStyle = (opts && opts.color) || "#000";
          ctx.textAlign = "left";
          var labelX = currentX + 16; 
          var labelY = activeStaveForLabel.getBottomY() + 22; 
          ctx.fillText(displayKey + ":", labelX, labelY);
          ctx.restore();
        }

        // Draw system connector only on first measure and only if both staves are shown
        if (isFirstMeasure && trebleStave && bassStave) {
          var connector = new Vex.Flow.StaveConnector(trebleStave, bassStave);
          connector.setType('brace').setContext(ctx).draw();
          var leftLine = new Vex.Flow.StaveConnector(trebleStave, bassStave);
          leftLine.setType('singleLeft').setContext(ctx).draw();
        }

  var trebleVoices = staffVoices("treble", treble, "treble", globalIdState, keySignatureAlterations, cumulativeMeasureTick);
  var bassVoices = staffVoices("bass", bass, "bass", globalIdState, keySignatureAlterations, cumulativeMeasureTick);

        // Add barlines at the end of each measure
        var isLastMeasureOfPiece = (absoluteMeasureIndex === score.measures.length - 1);
        // Standard intermediate barline is 'single'. Piece end is 'end'.
        var barType = isLastMeasureOfPiece ? 'end' : 'single';
        
        console.log("[UMTO-DEBUG] rendering measure", absoluteMeasureIndex, "barType:", barType, "isLast:", isLastMeasureOfPiece);

        if (trebleStave) {
          trebleStave.setBegBarType(isFirstMeasure ? 'single' : 'none');
          trebleStave.setEndBarType(barType);
          trebleStave.draw();
          lastTrebleStave = trebleStave;
        }
        if (bassStave) {
          bassStave.setBegBarType(isFirstMeasure ? 'single' : 'none');
          bassStave.setEndBarType(barType);
          bassStave.draw();
          lastBassStave = bassStave;
        }

        // Connect staves with a vertical barline at the end of each measure
        if (trebleStave && bassStave) {
          try {
            var rightLine = new Vex.Flow.StaveConnector(trebleStave, bassStave);
            var connectorType = isLastMeasureOfPiece ? 'boldDoubleRight' : 'singleRight';
            rightLine.setType(connectorType).setContext(ctx).draw();
          } catch (e) {
            console.warn("[VexFlowAdapter] StaveConnector error:", e);
          }
        }

        // Use VexFlow 4's improved formatter for better spacing
        var allVoices = trebleVoices.concat(bassVoices);
        if (allVoices.length) {
          var formatter = new Vex.Flow.Formatter();
          if (trebleVoices.length) formatter.joinVoices(trebleVoices);
          if (bassVoices.length) formatter.joinVoices(bassVoices);

          var leftPadTreble = trebleStave ? (trebleStave.getNoteStartX() - trebleStave.getX()) : 0;
          var leftPadBass = bassStave ? (bassStave.getNoteStartX() - bassStave.getX()) : 0;
          var leftPad = Math.max(leftPadTreble, leftPadBass);
          var rightPad = (measIdx === numMeasures - 1) ? 20 : 12;
          var notesWidth = Math.max(0, measureWidth - leftPad - rightPad);
          
          formatter.format(allVoices, notesWidth);
        }

        // In VexFlow, format() calculates layout. We don't need to draw unplayed notes if showNotation is false.
        // However, some versions of VexFlow require draw() to compute absolute coordinates for tickables.
        // We will draw them inside an invisible SVG group if openGroup is available.
        var hiddenGroup = null;
        if (!showNotation) {
          ctx.save();
          if (typeof ctx.setGlobalAlpha === "function") ctx.setGlobalAlpha(0);
          ctx.globalAlpha = 0;
          if (typeof ctx.openGroup === "function") {
            hiddenGroup = ctx.openGroup("hidden_notation");
          }
        }

        if (trebleStave) {
          trebleVoices.forEach(function (v) { 
            v.draw(ctx, trebleStave); 
            if (v.beams && showNotation) {
              v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
            }
          });
        }
        if (bassStave) {
          bassVoices.forEach(function (v) { 
            v.draw(ctx, bassStave); 
            if (v.beams && showNotation) {
              v.beams.forEach(function(beam) { beam.setContext(ctx).draw(); });
            }
          });
        }

        if (!showNotation) {
          if (hiddenGroup) {
            ctx.closeGroup();
            hiddenGroup.setAttribute("opacity", "0");
            hiddenGroup.setAttribute("visibility", "hidden");
          }
          ctx.restore();
          
          // Second pass: Draw only the played notes with full opacity
          var drawPlayedNotes = function(voices, stave) {
            voices.forEach(function(v) {
              var tks = (typeof v.getTickables === 'function') ? v.getTickables() : (v.tickables || []);
              tks.forEach(function(t) {
                // If it's a played note, it will have a non-transparent fillStyle from itemToTickable
                var style = (t.getStyle ? t.getStyle() : null);
                if (style && style.fillStyle !== "transparent") {
                   t.setContext(ctx).setStave(stave).draw();
                }
              });
            });
          };
          if (trebleStave) drawPlayedNotes(trebleVoices, trebleStave);
          if (bassStave) drawPlayedNotes(bassVoices, bassStave);

          // Third pass: Draw beams if ALL notes in the beam are played
          var drawPlayedBeams = function(voices) {
            voices.forEach(function(v) {
              if (!v.beams) return;
              v.beams.forEach(function(beam) {
                var allPlayed = beam.notes.every(function(n) {
                  var style = (n.getStyle ? n.getStyle() : null);
                  return style && style.fillStyle !== "transparent";
                });
                if (allPlayed) {
                  beam.setContext(ctx).draw();
                }
              });
            });
          };
          drawPlayedBeams(trebleVoices);
          drawPlayedBeams(bassVoices);
        }


        // Analysis annotations using Notater bridge (maximum reuse)
        try {
            if ((analyzeConfig && analyzeConfig.enabled && analysisRenderer !== "none" && keySignatureModel) ||
              (opts && typeof opts.onWindowPosition === "function")) {
            // Collect all tickables in this measure after formatting to get absolute X positions
            var allTickables = [];
            function addVoiceTickables(arr) {
              arr.forEach(function(voice){
                if (!voice || !voice.tickables) return;
                var tks = Array.isArray(voice.tickables)
                  ? voice.tickables
                  : (typeof voice.getTickables === 'function' ? voice.getTickables() : []);
                tks.forEach(function(t){
                  if (!t || typeof t.getAbsoluteX !== 'function') return;
                  var dur = String(t.duration || '');
                  // Rests don't create identification columns, 
                  // but we still want their onsets for playback if needed?
                  // Actually, for id mode, we only care about columns with notes.
                  if (dur.indexOf('r') !== -1) return; 
                  allTickables.push(t);
                });
              });
            }
            addVoiceTickables(trebleVoices);
            addVoiceTickables(bassVoices);

            // Group by X position (pixel) with small tolerance
            var groups = [];
            var tol = 3; // px
            allTickables.sort(function(a,b){ return a.getAbsoluteX() - b.getAbsoluteX(); });
            allTickables.forEach(function(t){
              var x = t.getAbsoluteX();
              var g = null;
              for (var gi=0; gi<groups.length; gi++) {
                if (Math.abs(groups[gi].x - x) <= tol) { g = groups[gi]; break; }
              }
              if (!g) { g = { x: x, notes: [] }; groups.push(g); }
              g.notes.push(t);
            });

            // Helpers
            function keyToMidi(keyStr) {
              // key like 'c#/4' or 'bb/3'
              var parts = String(keyStr).split('/');
              if (parts.length !== 2) return null;
              var name = parts[0];
              var octave = parseInt(parts[1], 10);
              var step = name.charAt(0).toLowerCase();
              var acc = name.slice(1);
              var base = { c:0, d:2, e:4, f:5, g:7, a:9, b:11 }[step];
              if (typeof base !== 'number' || isNaN(octave)) return null;
              var delta = 0;
              if (acc === '#') delta = 1; else if (acc === '##') delta = 2;
              else if (acc === 'b') delta = -1; else if (acc === 'bb') delta = -2;
              else if (acc === 'n') delta = 0; // explicit natural
              var midi = 12 * (octave + 1) + base + delta;
              return midi;
            }

            // Draw per onset column
            groups.forEach(function(col){
              var midiSet = Object.create(null);
              col.notes.forEach(function(t){
                var keys = (typeof t.getKeys === 'function') ? t.getKeys() : [];
                for (var i=0;i<keys.length;i++) {
                  var m = keyToMidi(keys[i]);
                  if (m !== null) midiSet[m] = true;
                }
              });
              var attackList = Object.keys(midiSet).map(function(k){ return parseInt(k,10); }).sort(function(a,b){return a-b;});
              var midi = attackList.slice();
              if (!midi.length) return;

              var currentNote = col.notes[0];
              var noteOnset = currentNote._onset;
              var noteMeasure = currentNote._measureIndex;

              if (analysisWindows.length) {
                var matchedWindow = null;
                var matchedIndex = -1;
                
                // Find EXACT match by measure and onset
                for (var seek = 0; seek < analysisWindows.length; seek++) {
                  var win = analysisWindows[seek];
                  if (win.measureIndex === noteMeasure && Math.abs(win.onset - noteOnset) < 2) {
                    matchedWindow = win;
                    matchedIndex = seek;
                    break;
                  }
                }

                if (matchedWindow && matchedWindow.midiStack) {
                  midi = matchedWindow.midiStack.slice();
                }
              }

              var activeStaveForAnnotations = bassStave || trebleStave;
              var columnCenterX = getColumnCenterX(col);
              if (opts && typeof opts.onWindowPosition === "function" && typeof matchedIndex === "number" && columnCenterX !== null && activeStaveForAnnotations) {
                opts.onWindowPosition({
                  windowIndex: absoluteWindowOffset + matchedIndex,
                  onset: matchedWindow ? matchedWindow.onset : null,
                  measureIndex: matchedWindow ? matchedWindow.measureIndex : null,
                  x: columnCenterX,
                  y: activeStaveForAnnotations.getBottomY() + 18,
                });
              }

              if (renderRomans && activeStaveForAnnotations) {
                attachInlineRomanAnnotation(
                  col,
                  midi,
                  analyzeConfig,
                  inlineAnalyzer,
                  ctx,
                  activeStaveForAnnotations,
                  { yShift: romanYOffset }
                );
              } else if (renderFigured && activeStaveForAnnotations) {
                var figureLabel = computeFiguredLabel(
                  midi,
                  inlineAnalyzer,
                  !!(analyzeConfig &&
                    analyzeConfig.mode &&
                    analyzeConfig.mode.abbreviate_thoroughbass)
                );
                if (figureLabel) {
                  attachInlineRomanAnnotation(
                    col,
                    midi,
                    analyzeConfig,
                    inlineAnalyzer,
                    ctx,
                    activeStaveForAnnotations,
                    { yShift: figuredYOffset, lineHeight: 12 },
                    figureLabel
                  );
                }
              } else if (renderRomanExp && activeStaveForAnnotations) {
                var expLabel = computeRomanExpLabel(midi, inlineAnalyzer);
                queueRomanExpColumn(col, expLabel, activeStaveForAnnotations);
              } else if (renderNoteNames && activeStaveForAnnotations) {
                var spelling = null;
                if (matchedWindow && matchedWindow.spellingStack) {
                  spelling = matchedWindow.spellingStack;
                }
                var explicitLabel = spelling ? formatExplicitNoteNames(spelling) : null;
                attachNoteNameAnnotation(
                  col,
                  midi,
                  analyzeConfig,
                  inlineAnalyzer,
                  ctx,
                  activeStaveForAnnotations,
                  { yShift: romanYOffset },
                  explicitLabel
                );
              }


            });
          }
        } catch (e) {
          // Fail-safe: don't break rendering if analysis drawing fails
          // console.warn('[VexFlowAdapter] Analysis annotation error:', e);
        }
        
        // Move X position for next measure
        currentX += measureWidth;
        cumulativeMeasureTick += measureDurations[measIdx] || 0;
      }

      flushRomanExpRun();

        // Wrong note rendering removed - will be implemented via exercise grading system
    } finally {
      ctx.restore();
    }
  }

  return { render: render };
});
