/* global define: false */

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(
      require("vexflow"),
      require("./vexflow_adapter_logic")
    );
  } else if (typeof define === "function" && define.amd) {
    define(
      [
        "vexflow",
        "app/components/music/rendering/vexflow_adapter_logic",
      ],
      factory
    );
  } else {
    root.VexflowStaveFactory = factory(root.Vex, root.VexflowAdapterLogic);
  }
})(typeof self !== "undefined" ? self : this, function (Vex, VexflowAdapterLogic) {
  "use strict";

  // Add a key signature with a minor->relative-major fallback for older VexFlow builds
  function addKeySignatureSafe(stave, key) {
    if (!key) return;
    var k = VexflowAdapterLogic.normalizeKeyForVexFlow(key);
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

  return {
    addKeySignatureSafe: addKeySignatureSafe,
    makeStave: makeStave,
  };
});
