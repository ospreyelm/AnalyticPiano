"use strict";

function normalizeAccidentals(value) {
  return String(value || "")
    .replace(/♭/g, "b")
    .replace(/♯/g, "#")
    .replace(/-/g, "b");
}

function getKeyContext(key) {
  if (!key || typeof key !== "string" || key === "?") {
    return null;
  }

  var k = normalizeAccidentals(key.trim());
  if (!k) {
    return null;
  }

  var isMinor = false;
  var note = k;

  if ((k.charAt(0) === "i" || k.charAt(0) === "j") && k.length >= 2 && /^[A-Ga-g]/.test(k.charAt(1))) {
    isMinor = k.charAt(0) === "i";
    note = k.substring(1).replace(/_/g, "");
  } else {
    isMinor = /m$/.test(k) || (k.length > 0 && k.charAt(0) === k.charAt(0).toLowerCase());
    note = isMinor && /m$/.test(k) ? k.slice(0, -1) : k;
  }

  if (!/^[A-Ga-g](#{1,2}|b{1,2})?$/.test(note)) {
    return null;
  }

  note = note.charAt(0).toUpperCase() + note.slice(1);
  var tonicLetter = note.charAt(0);
  var accidental = note.slice(1);
  var prefix = (isMinor ? tonicLetter.toLowerCase() : tonicLetter.toUpperCase()) + accidental + ":";
  var naturalSuffix = accidental ? "" : "_";

  return {
    displayName: note + " " + (isMinor ? "minor" : "major"),
    prefix: prefix,
    harmonyLabKey: (isMinor ? "i" : "j") + note + naturalSuffix,
  };
}

function sameKeyContext(a, b) {
  var contextA = getKeyContext(a);
  var contextB = getKeyContext(b);
  if (!contextA || !contextB) {
    return false;
  }
  return contextA.harmonyLabKey === contextB.harmonyLabKey;
}

var exportsObj = {
  getKeyContext: getKeyContext,
  sameKeyContext: sameKeyContext,
};

if (typeof define === "function" && define.amd) {
  define(function () {
    return exportsObj;
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = exportsObj;
}
