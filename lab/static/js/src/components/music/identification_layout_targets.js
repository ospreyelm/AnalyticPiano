import $ from "jquery";

// Slot-aware mount targets for the identification UI.
//
// The modern student player (`apps/student/templates/student/player.html`)
// wants the identification controls split across two slots:
//   • #ident-toolbar-slot  — the Click/Type · Practice/Submit toggle row
//   • #s-answer-bar         — the text-input pill + progress bar
// The legacy lab player (`lab/templates/exercise.html`) has a single
// #identification-actions container and no slots. The identification
// components are shared between both templates, so every mount decision falls
// back to #identification-actions when the modern slot is absent. This is the
// same node set the legacy template already uses — no second source of truth,
// just a slot-aware parent choice.

function toolbarSlot() {
  var $slot = $("#ident-toolbar-slot");
  return $slot.length ? $slot : $("#identification-actions");
}

function answerBar() {
  var $bar = $("#s-answer-bar");
  return $bar.length ? $bar : $("#identification-actions");
}

function answerBarPresent() {
  return $("#s-answer-bar").length > 0;
}

function showAnswerBarIfNeeded() {
  var $bar = $("#s-answer-bar");
  if ($bar.length) {
    $bar.css("display", "flex");
  }
}

function showToolbarSepIfNeeded() {
  var $sep = $("#ident-toolbar-sep");
  if ($sep.length) {
    $sep.css("display", "");
  }
}

// Text-input pill: inside #s-answer-bar before #identification-submit (modern),
// or as a sibling after #identification-actions (legacy).
function mountInputContainer($container) {
  var $bar = $("#s-answer-bar");
  if ($bar.length) {
    $container.insertBefore($("#identification-submit"));
  } else {
    $("#identification-actions").after($container);
  }
  showAnswerBarIfNeeded();
}

// Progress bar: front of #s-answer-bar (modern), or prepended into
// #identification-actions (legacy).
function mountProgressContainer($prog) {
  var $bar = $("#s-answer-bar");
  if ($bar.length) {
    $prog.prependTo($bar);
  } else {
    $prog.prependTo($("#identification-actions"));
  }
  showAnswerBarIfNeeded();
}

export {
  toolbarSlot,
  answerBar,
  answerBarPresent,
  showAnswerBarIfNeeded,
  showToolbarSepIfNeeded,
  mountInputContainer,
  mountProgressContainer,
};