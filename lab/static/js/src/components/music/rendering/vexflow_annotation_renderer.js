/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./vexflow_adapter_logic"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/components/music/rendering/vexflow_adapter_logic"], factory);
  } else {
    root.VexflowAnnotationRenderer = factory(root.VexflowAdapterLogic);
  }
})(typeof self !== "undefined" ? self : this, function (VexflowAdapterLogic) {
  "use strict";

  // Sebastian is a zero-width figured-bass font. Each character's vertical position
  // is baked into its glyph metrics (main-row, lower-row, upper-row). Drawing a
  // token string like "z4" as a single fillText call renders a stacked 6/4 figure.
  // measureText returns ~0, so we use a fixed advance width based on the "6" reference.

  function drawInlineRoman(ctx, label, columnX, stave, opts) {
    if (!ctx || !label) return;
    var raw = String(label);

    // Split into alternating plain / {figured-bass} tokens
    var tokenRe = /([^{}]+)|(\{([^{}]+)\})/g;
    var tokens = [];
    var m;
    while ((m = tokenRe.exec(raw)) !== null) {
      if (m[2]) {
        tokens.push({ text: m[3], figured: true });
      } else if (m[1]) {
        tokens.push({ text: m[1], figured: false });
      }
    }
    if (!tokens.length) return;

    var yBase = (stave && stave.getBottomY) ? stave.getBottomY() : 100;
    var y = yBase + ((opts && opts.yShift) || 30);
    var color = (opts && opts.color) || "#000";

    // Adapt sizes to available column gap so labels don't collide.
    var colGap = (opts && opts.colGap) || null;
    var ROMAN_SIZE = (colGap && colGap < 36) ? 14 : (colGap && colGap < 50) ? 16 : 20;
    var SEB_SIZE   = (colGap && colGap < 36) ? 20 : (colGap && colGap < 50) ? 26 : 32;
    // Figure advance width: Sebastian glyphs are zero-width, so proxy via
    // MainSerifs digit width at ~60% of ROMAN_SIZE (figures are superscript-sized).
    var FIG_REF_SIZE = Math.round(ROMAN_SIZE * 0.62);

    ctx.save();
    if (typeof ctx.setFillStyle === "function") ctx.setFillStyle(color);
    ctx.fillStyle = color;

    // Compute per-token widths up front so we can center the full label.
    var SUP_SIZE  = Math.round(ROMAN_SIZE * 0.65);
    var SUP_YOFF  = -Math.round(ROMAN_SIZE * 0.40);
    var SUP_RE    = /(°|⌀)/g;
    ctx.font = ROMAN_SIZE + "px MainSerifs";
    var tokenWidths = tokens.map(function (token) {
      if (!token.figured) {
        // Measure char-by-char: °/⌀ draw at SUP_SIZE, rest at ROMAN_SIZE.
        var text = VexflowAdapterLogic.convertRomanSymbols(token.text);
        var parts = text.split(SUP_RE);
        var total = 0;
        parts.forEach(function(part) {
          if (!part) return;
          if (part === "°" || part === "⌀") {
            ctx.font = SUP_SIZE + "px MainSerifs";
            total += ctx.measureText(part).width;
            ctx.font = ROMAN_SIZE + "px MainSerifs";
          } else {
            total += ctx.measureText(part).width;
          }
        });
        return total;
      }
      // Proxy width: measure the digit equivalent in a small MainSerifs font.
      // Map Sebastian codes to their digit strings for measurement.
      var digits = token.text
        .replace(/[zuZU]/g, "6")   // main/upper-row 6-ish
        .replace(/[u]/g,    "7")   // main-row 7
        .replace(/r/g,      "4")   // main-row 4
        .replace(/e/g,      "3")   // main-row 3
        .replace(/t/g,      "5")   // main-row 5
        .replace(/[CKBd']/g, "b")  // accidentals — narrowish
        .replace(/\s/g,     "");   // strip spaces
      ctx.font = FIG_REF_SIZE + "px MainSerifs";
      var w = ctx.measureText(digits).width;
      ctx.font = ROMAN_SIZE + "px MainSerifs";
      return Math.max(w, 5); // minimum 5px
    });

    var totalWidth = tokenWidths.reduce(function(a, b) { return a + b; }, 0);
    var curX = Math.round(columnX - totalWidth / 2);

    tokens.forEach(function (token, i) {
      var w = tokenWidths[i];
      if (!token.figured) {
        var text = VexflowAdapterLogic.convertRomanSymbols(token.text);
        // Draw °/⌀ as raised superscript; all other chars at normal size.
        var parts = text.split(SUP_RE);
        var px = curX;
        parts.forEach(function(part) {
          if (!part) return;
          if (part === "°" || part === "⌀") {
            ctx.font = SUP_SIZE + "px MainSerifs";
            ctx.textAlign = "left";
            ctx.fillText(part, px, y + SUP_YOFF);
            px += ctx.measureText(part).width;
          } else {
            ctx.font = ROMAN_SIZE + "px MainSerifs";
            ctx.textAlign = "left";
            ctx.fillText(part, px, y);
            px += ctx.measureText(part).width;
          }
        });
      } else {
        // Sebastian: draw at left edge of reserved figure slot, baseline y+3.
        ctx.font = SEB_SIZE + "px Sebastian";
        ctx.textAlign = "left";
        ctx.fillText(token.text, curX + 6, y + 3);
      }
      curX += w;
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

  function _drawScaleDegreeList(ctx, midiNotes, columnX, anchorY, stackDir, analyzer, sdMap) {
    // stackDir: -1 = stack upward (above anchor), +1 = stack downward (below anchor)
    var sorted = midiNotes.slice().sort(function(a, b) { return stackDir === -1 ? b - a : a - b; });
    ctx.save();
    ctx.textAlign = 'center';
    ctx.fillStyle = '#000';
    sorted.forEach(function(midi, i) {
      var numeral = (sdMap && sdMap[midi] !== undefined)
        ? sdMap[midi]
        : (analyzer ? analyzer.to_scale_degree([midi]) : '');
      if (!numeral) return;
      numeral = numeral.replace(/b/g, '♭').replace(/#/g, '♯');
      var numeralY = anchorY + stackDir * (16 + i * 20);
      var caretY   = numeralY - 13;
      ctx.font = '17px MainSerifs';
      ctx.fillText(numeral, columnX, numeralY);
      ctx.font = '13px MainSerifs';
      ctx.fillText('^', columnX, caretY);
    });
    ctx.restore();
  }

  function drawScaleDegreeAbove(ctx, midiNotes, columnX, trebleStave, analyzer, colNotes, bassStave, sdMap) {
    if (!ctx || !analyzer || !trebleStave || !midiNotes || !midiNotes.length) return;

    // Split notes by voice when two voices share the treble staff.
    // Top voice (voiceIdx 0, stems up) -> labels above stave top line.
    // Bottom voice (voiceIdx 1, stems down) -> labels below stave bottom line.
    var topVoiceMidi = [];
    var bottomVoiceMidi = [];
    var hasSplit = false;

    if (colNotes && colNotes.length) {
      colNotes.forEach(function(t) {
        if (VexflowAdapterLogic && VexflowAdapterLogic.isRestTickable(t)) return;
        var vIdx = t._sdVoiceIdx;
        var sId  = t._sdStaffId;
        if (sId !== 'treble' && sId !== undefined) return; // skip bass staff tickables
        var midiValues = VexflowAdapterLogic
          ? VexflowAdapterLogic.tickableToScaleDegreeMidi(t)
          : [];
        (midiValues || []).forEach(function(m) {
          if (vIdx === 1) { bottomVoiceMidi.push(m); hasSplit = true; }
          else topVoiceMidi.push(m);
        });
      });
    }

    if (!hasSplit) {
      // Single voice — labels above stave, cleared past stem tips.
      // Use treble-filtered list if colNotes was provided (avoids drawing bass note above treble).
      var singleVoiceMidi = topVoiceMidi.length ? topVoiceMidi : midiNotes;
      var topY = (trebleStave.getYForLine ? trebleStave.getYForLine(0) : trebleStave.getY()) - 30;
      _drawScaleDegreeList(ctx, singleVoiceMidi, columnX, topY, -1, analyzer, sdMap);
      return;
    }

    if (topVoiceMidi.length) {
      var topY = (trebleStave.getYForLine ? trebleStave.getYForLine(0) : trebleStave.getY()) - 30;
      _drawScaleDegreeList(ctx, topVoiceMidi, columnX, topY, -1, analyzer, sdMap);
    }
    if (bottomVoiceMidi.length) {
      var botY = trebleStave.getBottomY ? trebleStave.getBottomY() : (trebleStave.getY() + 40);
      _drawScaleDegreeList(ctx, bottomVoiceMidi, columnX, botY, 1, analyzer, sdMap);
    }
  }

  function drawBassScaleDegreeBelow(ctx, bassStave, label, columnX) {
    if (!ctx || !bassStave || !label) return;
    var y = bassStave.getBottomY() + 22;
    ctx.save();
    ctx.textAlign = 'center';
    ctx.fillStyle = '#000';
    ctx.font = '18px MainSerifs';
    ctx.fillText(label, columnX, y);
    ctx.restore();
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
        : VexflowAdapterLogic.computeRomanLabel(midi, analyzer);
    if (!label) {
      return;
    }
    var x = VexflowAdapterLogic.getColumnCenterX(col);
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
    if (
      col.notes &&
      col.notes.length &&
      col.notes.every(function (note) {
        return note && (note._isRest || String(note.duration || "").indexOf("r") !== -1);
      })
    ) {
      return;
    }
    var label =
      typeof labelOverride === "string"
        ? labelOverride
        : analyzer.to_note_name(midi);
    if (!label) {
      return;
    }
    var x = VexflowAdapterLogic.getColumnCenterX(col);
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

  return {
    drawInlineRoman: drawInlineRoman,
    drawInlineRomanExp: drawInlineRomanExp,
    drawInlineRomanExpRun: drawInlineRomanExpRun,
    _drawScaleDegreeList: _drawScaleDegreeList,
    drawScaleDegreeAbove: drawScaleDegreeAbove,
    drawBassScaleDegreeBelow: drawBassScaleDegreeBelow,
    attachInlineRomanAnnotation: attachInlineRomanAnnotation,
    attachNoteNameAnnotation: attachNoteNameAnnotation,
  };
});
