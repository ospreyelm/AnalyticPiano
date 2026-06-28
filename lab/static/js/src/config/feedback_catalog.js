/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define([], factory);
  } else {
    root.FeedbackCatalog = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // entry: { category, surface, title, body, detail, defaultTimeoutMs }
  var CATALOG = {
    // click / soft constraints / mode / device (Phase 1)
    "harmonization.click.note_cap":       { category: "soft_constraint", surface: "control", title: "Chord is full.", body: "Remove a note to add another.", detail: null, defaultTimeoutMs: 1800 },
    "harmonization.click.outside_column": { category: "soft_constraint", surface: "none",    title: null, body: "Finish this chord first — the next one opens when you do.", detail: null, defaultTimeoutMs: 2500 },
    "harmonization.click.empty_commit":   { category: "soft_constraint", surface: "control", title: null, body: "Add a note or two first.", detail: null, defaultTimeoutMs: null },
    "input.mode.changed_live":  { category: "mode_state", surface: "inline", title: null, body: "Live input — play your keyboard or MIDI.", detail: null, defaultTimeoutMs: 2000 },
    "input.mode.changed_click": { category: "mode_state", surface: "inline", title: null, body: "Click input — tap the staff to place each note.", detail: null, defaultTimeoutMs: 2000 },
    "input.device.none":        { category: "mode_state", surface: "inline", title: "No MIDI keyboard?", body: "No problem — click notes onto the staff, use your computer keyboard, or play the on-screen keyboard.", detail: null, defaultTimeoutMs: null },

    // grade — universal fallback (wired in Phase 2)
    "exercise.grade.correct":   { category: "success",             surface: "anchored", title: null, body: "Yes — that's right.",            detail: null, defaultTimeoutMs: 1500 },
    "exercise.grade.incorrect": { category: "recoverable_mistake", surface: "anchored", title: null, body: "Not quite — give it another try.", detail: null, defaultTimeoutMs: 4000 },
    "exercise.grade.partial":   { category: "mode_state",          surface: "none",     title: null, body: "Good so far — keep going.",      detail: null, defaultTimeoutMs: 2000 },
    "exercise.complete":        { category: "success",             surface: "inline",   title: null, body: "Beautifully done.",              detail: null, defaultTimeoutMs: 3000 },

    // grade — per-type
    "chorale.grade.incorrect":        { category: "recoverable_mistake", surface: "anchored", title: null, body: "That isn't the note in the score — listen, then try again.", detail: null, defaultTimeoutMs: 4000 },
    "chorale.grade.correct":          { category: "success",             surface: "anchored", title: null, body: "That's the one.", detail: null, defaultTimeoutMs: 1500 },
    "identification.grade.incorrect": { category: "recoverable_mistake", surface: "anchored", title: null, body: "Not the right name — take another look.", detail: null, defaultTimeoutMs: 4000 },
    "identification.grade.correct":   { category: "success",             surface: "anchored", title: null, body: "Exactly.", detail: null, defaultTimeoutMs: 1500 },
    "harmonization.grade.incorrect":  { category: "recoverable_mistake", surface: "anchored", title: null, body: "Not quite — check the chord against the figure and try again.", detail: null, defaultTimeoutMs: 4000 },
    "harmonization.grade.correct":    { category: "success",             surface: "anchored", title: null, body: "Yes — that's it.", detail: null, defaultTimeoutMs: 1500 },
    "harmonization.hint.fifth_optional":   { category: "mode_state", surface: "inline", title: null, body: "The 5th is optional here — you can double the bass instead.", detail: null, defaultTimeoutMs: 3500 },
    "harmonization.hint.missing_required": { category: "recoverable_mistake", surface: "anchored", title: null, body: "A required tone is missing — check which intervals the figure must include.", detail: null, defaultTimeoutMs: 4000 },

    // grade — per-skill (most specific)
    "harmonization.grade.incorrect.wrong_inversion": { category: "recoverable_mistake", surface: "anchored", title: null, body: "Right chord — but the bass doesn't match the figure's inversion.", detail: null, defaultTimeoutMs: 4500 },
    "harmonization.grade.incorrect.wrong_quality":   { category: "recoverable_mistake", surface: "anchored", title: null, body: "Close — check the chord quality (major, minor, diminished?).", detail: null, defaultTimeoutMs: 4500 },
    "identification.grade.incorrect.wrong_octave":   { category: "recoverable_mistake", surface: "anchored", title: null, body: "Right letter — wrong octave.", detail: null, defaultTimeoutMs: 4000 },

    // play authoring — save feedback (Phase B)
    "play.save.success":       { category: "success",        surface: "inline", title: "Saved.",          body: "Your exercise is saved and reviewed.",                                                                 detail: null, defaultTimeoutMs: 2500 },
    "play.save.invalid_meter": { category: "blocking_error", surface: "inline", title: "Can't save yet.", body: "Bar {bar} has {beats} beats, expected {expected}. Fix a duration or move a barline.",                detail: null, defaultTimeoutMs: null },
    "play.save.empty":              { category: "blocking_error", surface: "inline", title: "Nothing to save.",     body: "Bank at least two chords first.",                                                                    detail: null, defaultTimeoutMs: 2500 },
    "play.save.invalid_tags":       { category: "blocking_error", surface: "inline", title: "Invalid tags.",         body: "One or more tags are not recognised. Use letters, digits, and : _ # / - only (max 40 chars each).", detail: null, defaultTimeoutMs: null },
    "play.save.playlist_locked":    { category: "blocking_error", surface: "inline", title: "Playlist is locked.",   body: "That playlist is locked and can't accept new exercises. Choose a different playlist.",              detail: null, defaultTimeoutMs: null },
    "play.save.forbidden_official": { category: "blocking_error", surface: "inline", title: "Not allowed.",          body: "Only superusers can save exercises to the official factory library.",                              detail: null, defaultTimeoutMs: null }

    // system.* errors are appended in Phase 4 (Task 22)
  };

  function get(id) {
    return Object.prototype.hasOwnProperty.call(CATALOG, id) ? CATALOG[id] : null;
  }
  function format(template, params) {
    if (!template || !params) return template;
    return template.replace(/\{(\w+)\}/g, function (m, key) {
      return Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : m;
    });
  }
  function render(id, params) {
    var e = get(id);
    if (!e) return null;
    return { id: id, category: e.category, surface: e.surface,
      title: format(e.title, params), body: format(e.body, params),
      detail: format(e.detail, params), timeoutMs: e.defaultTimeoutMs };
  }
  // <type>.grade.<state>.<diagnostic> -> <type>.grade.<state> -> exercise.grade.<state>
  function resolveGradeFeedbackId(type, state, diagnostic) {
    var c = [];
    if (type && state && diagnostic) c.push(type + ".grade." + state + "." + diagnostic);
    if (type && state) c.push(type + ".grade." + state);
    if (state) c.push("exercise.grade." + state);
    for (var i = 0; i < c.length; i++) { if (get(c[i])) return c[i]; }
    return null;
  }
  function buildEvent(id, ctx, ts) {
    var e = get(id); ctx = ctx || {};
    return { feedbackId: id, category: e ? e.category : null,
      exerciseId: ctx.exerciseId || null,
      unit: typeof ctx.unit === "number" ? ctx.unit : null,
      complexity: typeof ctx.complexity === "number" ? ctx.complexity : null,
      skillTags: ctx.skillTags || [], ts: typeof ts === "number" ? ts : null };
  }

  return { get: get, format: format, render: render, resolveGradeFeedbackId: resolveGradeFeedbackId, buildEvent: buildEvent };
});
