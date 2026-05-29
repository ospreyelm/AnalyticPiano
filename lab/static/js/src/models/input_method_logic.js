/* global define: false */

/*
 * Single source of truth for "how does the student answer this exercise?"
 *
 * Returns one of:
 *   "note_entry" - notes via MIDI / computer keyboard / click-on-staff
 *                  (harmonization, chorale play). Shows the Live/Click source
 *                  toggle and the click-on-staff input component.
 *   "dropdown"   - mouse-driven ? slots (identification / harmonic analysis).
 *   "text"       - typed answers.
 *
 * Gate the source toggle / click-on-staff component on `resolveInputMethod(...) === "note_entry"`.
 * Do not re-derive this from scattered type/mode/analysisType checks elsewhere.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.InputMethodLogic = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /*
   * fields:
   *   inputModeFixed     {string|null}  exercise.inputModeFixed (authoritative when set)
   *   inputMode          {string|null}  exercise.inputMode
   *   metaInputMode      {string|null}  score.umto.metadata.input_mode
   *   mode               {string|null}  interaction mode (getMode())
   *   isIdentification   {boolean}
   *   isChoraleIdentification {boolean}
   */
  function resolveInputMethod(fields) {
    fields = fields || {};
    var im = fields.inputModeFixed || fields.inputMode || fields.metaInputMode || null;
    if (im === "dropdown") return "dropdown";
    if (im === "text") return "text";

    // No explicit input mode: fall back to interaction mode / predicates.
    var mode = fields.mode || null;
    if (
      mode === "identification" ||
      mode === "chorale_identification" ||
      mode === "analysis_match" ||
      mode === "analysis"
    ) {
      return "dropdown";
    }
    if (fields.isIdentification || fields.isChoraleIdentification) {
      return "dropdown";
    }
    return "note_entry";
  }

  function usesNoteEntry(fields) {
    return resolveInputMethod(fields) === "note_entry";
  }

  return {
    resolveInputMethod: resolveInputMethod,
    usesNoteEntry: usesNoteEntry,
  };
});
