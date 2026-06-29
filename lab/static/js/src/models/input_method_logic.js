

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

    // Interaction mode takes priority over inputMode for note-entry modes.
    // harmonization/playback/play-all-voices always require the piano/click
    // input — a stale "dropdown" in inputMode must not override this.
    var mode = fields.mode || null;
    if (
      mode === "harmonization" ||
      mode === "playback" ||
      mode === "play-all-voices"
    ) {
      return "note_entry";
    }

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

export default {
  resolveInputMethod: resolveInputMethod,
    usesNoteEntry: usesNoteEntry,
};
