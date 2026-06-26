"use strict";

// Test-only adapter. Drives the REAL production JS spelling path from a
// (key, midis) input so it can be compared against the Python engine.
// It does NOT re-implement spelling: it loads the production key spelling
// table (key_map_data, same data KeySignature.keyToSpelling returns) and
// the production speller (chordal_spelling.keyAwarePitch).

var KeyMapData = require("../lab/static/js/src/config/key_map_data");
var ChordalSpelling = require("../lab/static/js/src/components/music/chordal_spelling");

function alterToSuffix(alter) {
  if (alter > 0) return new Array(alter + 1).join("#");
  if (alter < 0) return new Array(-alter + 1).join("b");
  return "";
}

// spellMidisInKey(key, midis) -> { "<midi>": "<name>", ... }
function spellMidisInKey(key, midis) {
  var entry = KeyMapData[key];
  if (!entry) throw new Error("Unknown key token: " + key);
  var table = entry.spelling;
  var out = {};
  for (var i = 0; i < midis.length; i += 1) {
    var m = midis[i];
    var p = ChordalSpelling.keyAwarePitch(m, table); // { step, alter, octave }
    out[String(m)] = p.step + alterToSuffix(p.alter);
  }
  return out;
}

module.exports = { spellMidisInKey: spellMidisInKey };
