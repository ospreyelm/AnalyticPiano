/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("../music/rendering/vexflow_adapter_logic"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/components/music/rendering/vexflow_adapter_logic"], factory);
  } else {
    root.ClickNoteLogic = factory(root.VexflowAdapterLogic);
  }
})(typeof self !== "undefined" ? self : this, function (VexflowAdapterLogic) {
  "use strict";

  var STEP_SEMITONE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
  var LADDER = ["C", "D", "E", "F", "G", "A", "B"];
  var LEDGER_HALF_STEPS = 12;

  function getAlterations(key) {
    if (
      VexflowAdapterLogic &&
      typeof VexflowAdapterLogic.getKeySignatureAlterations === "function"
    ) {
      return VexflowAdapterLogic.getKeySignatureAlterations(key);
    }
    return {};
  }

  function pickSystem(layout, py) {
    var systems = (layout && layout.systems) || [];
    var best = null;
    var bestDist = Infinity;

    for (var i = 0; i < systems.length; i++) {
      var system = systems[i];
      var dist = 0;
      if (py < system.yTop) {
        dist = system.yTop - py;
      } else if (py > system.yBottom) {
        dist = py - system.yBottom;
      }
      if (dist < bestDist) {
        bestDist = dist;
        best = system;
      }
    }

    return best;
  }

  function staveDistance(stave, py) {
    if (py < stave.topLineY) return stave.topLineY - py;
    if (py > stave.bottomLineY) return py - stave.bottomLineY;
    return 0;
  }

  function pickStave(system, py) {
    var staves = (system && system.staves) || [];
    var best = null;
    var bestDist = Infinity;

    for (var i = 0; i < staves.length; i++) {
      var stave = staves[i];
      var dist = staveDistance(stave, py);
      if (dist < bestDist) {
        bestDist = dist;
        best = stave;
      }
    }

    if (!best) return null;
    if (bestDist > LEDGER_HALF_STEPS * (best.lineSpacing / 2)) return null;
    return best;
  }

  function stepFromTopLine(topStep, topOctave, stepsDown) {
    var idx = LADDER.indexOf(String(topStep || "").toUpperCase());
    var octave = topOctave;
    var remaining = stepsDown;

    if (idx === -1 || typeof octave !== "number") return null;

    while (remaining > 0) {
      idx -= 1;
      if (idx < 0) {
        idx = LADDER.length - 1;
        octave -= 1;
      }
      remaining -= 1;
    }

    while (remaining < 0) {
      idx += 1;
      if (idx >= LADDER.length) {
        idx = 0;
        octave += 1;
      }
      remaining += 1;
    }

    return { step: LADDER[idx], octave: octave };
  }

  function pickColumn(layout, system, px, activeColumnOnset) {
    var columns = (layout && layout.columns) || [];
    var hit = null;
    var inSystem = [];

    for (var i = 0; i < columns.length; i++) {
      var column = columns[i];
      if (column.systemIndex !== system.systemIndex) continue;
      inSystem.push(column);
      if (column.rect && px >= column.rect.x && px <= column.rect.x + column.rect.width) {
        hit = column;
        break;
      }
    }

    if (!hit) {
      var best = null;
      var bestDist = Infinity;
      for (var j = 0; j < inSystem.length; j++) {
        var dist = Math.abs(inSystem[j].centerX - px);
        if (dist < bestDist) {
          bestDist = dist;
          best = inSystem[j];
        }
      }
      hit = best;
    }

    if (!hit) return null;
    if (typeof activeColumnOnset === "number" && hit.onset !== activeColumnOnset) {
      return null;
    }
    return hit;
  }

  function applyPalette(step, palette, keyAlterations) {
    if (palette === "natural") return 0;
    if (palette === "sharp") return 1;
    if (palette === "flat") return -1;
    return keyAlterations[step] || 0;
  }

  function pitchToMidi(pitch) {
    var base = STEP_SEMITONE[pitch.step];
    if (typeof base !== "number") return null;
    return (pitch.octave + 1) * 12 + base + pitch.alter;
  }

  function resolveClick(point, layout, opts) {
    opts = opts || {};
    if (!point || typeof point.px !== "number" || typeof point.py !== "number") {
      return null;
    }

    var system = pickSystem(layout, point.py);
    if (!system) return null;

    var column = pickColumn(layout, system, point.px, opts.activeColumnOnset);
    if (!column) return null;

    var stave = pickStave(system, point.py);
    if (!stave || !stave.lineSpacing) return null;

    var stepsFromTop = Math.round(
      (point.py - stave.topLineY) / (stave.lineSpacing / 2)
    );
    var spelling = stepFromTopLine(stave.topLineStep, stave.topLineOctave, stepsFromTop);
    if (!spelling) return null;

    var alterations = getAlterations(opts.key);
    var alter = applyPalette(spelling.step, opts.palette, alterations);
    var midi = pitchToMidi({
      step: spelling.step,
      octave: spelling.octave,
      alter: alter,
    });
    if (midi === null || midi < 21 || midi > 108) return null;

    return {
      midi: midi,
      spelling: {
        step: spelling.step,
        alter: alter,
        octave: spelling.octave,
      },
      step: spelling.step,
      alter: alter,
      octave: spelling.octave,
      stepsFromTop: stepsFromTop,
      stave: stave,
      staveClef: stave.clef,
      column: column,
      system: system,
    };
  }

  return {
    pickSystem: pickSystem,
    pickStave: pickStave,
    stepFromTopLine: stepFromTopLine,
    pickColumn: pickColumn,
    resolveClick: resolveClick,
  };
});
