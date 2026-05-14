(function () {
  "use strict";

  var logic = window.barlinePlayerLogic;

  function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length === 2) {
      return parts.pop().split(";").shift();
    }
    return "";
  }

  function vex() {
    return window.Vex && (window.Vex.Flow || window.Vex);
  }

  function vfKey(pitch) {
    var match = String(pitch || "B4").match(/^([A-Ga-g])([#b]?)(\d)$/);
    if (!match) {
      return "b/4";
    }
    return match[1].toLowerCase() + match[2] + "/" + match[3];
  }

  function renderShell(root) {
    root.innerHTML =
      '<div class="qa-card barline-card">' +
      '<div class="qa-stem">Add barlines where they are needed.</div>' +
      '<div class="barline-hint">Use arrows and Enter, or the on-screen buttons.</div>' +
      '<div class="barline-stage"></div>' +
      '<div class="barline-pips" aria-label="Note positions"></div>' +
      '<div class="barline-actions">' +
      '<button type="button" class="barline-icon-btn" data-action="left" aria-label="Move left">&larr;</button>' +
      '<button type="button" class="barline-toggle-btn" data-action="toggle">Place / Remove</button>' +
      '<button type="button" class="barline-icon-btn" data-action="right" aria-label="Move right">&rarr;</button>' +
      '<button type="button" class="barline-submit-btn" data-action="submit">Submit</button>' +
      "</div>" +
      '<div class="barline-feedback" aria-live="polite"></div>' +
      "</div>";
  }

  function makeStaveNote(VF, config, item) {
    var note = new VF.StaveNote({
      clef: config.clef || "treble",
      keys: [vfKey(item.pitch)],
      duration: item.duration || "q",
    });
    if (item.dots) {
      VF.Dot.buildAndAttach([note], { all: true });
    }
    return note;
  }

  // Returns array of X center per note index (same order as config.notes).
  function noteXCenters(vfNotes) {
    return vfNotes.map(function (note) {
      var x = note.getAbsoluteX && note.getAbsoluteX();
      return (typeof x === "number" && !isNaN(x)) ? x : null;
    });
  }

  // Duration in units of an eighth note (so we can do integer arithmetic).
  // Returns null for note types that are never beamed (quarter and longer).
  var BEAMABLE_EIGHTHS = { "8": 1, "16": 0.5, "32": 0.25 };
  var DUR_EIGHTHS = { "w": 8, "h": 4, "q": 2, "8": 1, "16": 0.5, "32": 0.25 };

  function durEighths(duration, dots) {
    var base = DUR_EIGHTHS[duration] || 2;
    var add = base;
    var i;
    for (i = 0; i < (dots || 0); i++) { add /= 2; base += add; }
    return base;
  }

  // Beat size in eighths. Compound meters (6/8, 9/8, 12/8, 6/4, 9/4, 12/4):
  // beat = dotted quarter = 3 denominator units. Simple: beat = 1 denominator unit.
  // Compound detection: numerator divisible by 3 (covers 6, 9, 12).
  function beatEighths(timeSig) {
    var parts = (timeSig || "4/4").split("/");
    var num = parseInt(parts[0], 10);
    var den = parseInt(parts[1], 10);
    if (num % 3 === 0 && num > 3) {
      return 3 * (8 / den);
    }
    return 8 / den;
  }

  // Build beams manually to work around VexFlow generateBeams bug (issue #467):
  // generateBeams fails when a non-beamable note (e.g. dotted-quarter) doesn't
  // fill a complete beat group — it loses track of remaining time, causing
  // subsequent eighth notes to be left unbeamed. We scan notes ourselves,
  // track elapsed eighths, and group consecutive beamable notes within one beat.
  function buildBeams(VF, vfNotes, configNotes, timeSig) {
    var beat = beatEighths(timeSig);
    var beams = [];
    var groupNotes = [];
    var elapsed = 0;

    function flushGroup() {
      if (groupNotes.length >= 2) {
        beams.push(new VF.Beam(groupNotes.slice()));
      }
      groupNotes = [];
    }

    var i, item, noteEighths, posInBeat;

    for (i = 0; i < configNotes.length; i++) {
      item = configNotes[i];
      noteEighths = durEighths(item.duration, item.dots);

      // Beat boundary: flush if this note starts at a new beat.
      posInBeat = Math.round((elapsed % beat) * 10000) / 10000;
      if (posInBeat < 1e-9 && groupNotes.length > 0) {
        flushGroup();
      }

      if (BEAMABLE_EIGHTHS.hasOwnProperty(item.duration)) {
        groupNotes.push(vfNotes[i]);
      } else {
        flushGroup();
      }

      elapsed = Math.round((elapsed + noteEighths) * 10000) / 10000;
    }
    flushGroup();
    return beams;
  }

  function drawPlacedBarlines(VF, stave, noteXs, placedAt) {
    logic.barlineXPositions(noteXs, Array.from(placedAt || [])).forEach(function (x) {
      var barline = new VF.Barline(VF.Barline.type.SINGLE);
      barline.setX(x);
      barline.draw(stave);
    });
  }

  function drawNotation(stage, config, placedAt) {
    var VF = vex();
    var width;
    var renderer;
    var context;
    var stave;
    var vfNotes;
    var voice;
    var centers;

    if (!VF) {
      throw new Error("VexFlow is not loaded");
    }

    stage.innerHTML = "";
    width = Math.max(stage.clientWidth || 600, 360);
    renderer = new VF.Renderer(stage, VF.Renderer.Backends.SVG);
    renderer.resize(width, 170);
    context = renderer.getContext();
    stave = new VF.Stave(20, 30, width - 40);
    stave.addClef(config.clef || "treble");
    if (config.show_time_signature) {
      stave.addTimeSignature(config.time_signature);
    }
    stave.setBegBarType(VF.Barline.type.SINGLE);
    stave.setEndBarType(VF.Barline.type.SINGLE);
    stave.setContext(context).draw();

    vfNotes = (config.notes || []).map(function (item) {
      return makeStaveNote(VF, config, item);
    });

    if (vfNotes.length) {
      var tsParts = (config.time_signature || "4/4").split("/");
      var measures = parseInt(config.measures, 10) || 1;
      voice = new VF.Voice({ num_beats: parseInt(tsParts[0], 10) * measures, beat_value: parseInt(tsParts[1], 10) });
      voice.setMode(VF.Voice.Mode.SOFT);
      voice.addTickables(vfNotes);
      new VF.Formatter().joinVoices([voice]).formatToStave([voice], stave);
      var beams = buildBeams(VF, vfNotes, config.notes || [], config.time_signature);
      voice.draw(context, stave);
      beams.forEach(function (b) { b.setContext(context).draw(); });
    }

    centers = noteXCenters(vfNotes);
    drawPlacedBarlines(VF, stave, centers, placedAt);
    return centers;
  }

  function renderPips(root, state, config) {
    var pipRoot = root.querySelector(".barline-pips");
    var noteCount = (config.notes || []).length;
    var html = "";
    var i;

    for (i = 0; i < Math.max(0, noteCount - 1); i++) {
      html += '<span class="barline-pip' + (i === state.cursorPos ? " is-active" : "") + '"></span>';
    }
    pipRoot.innerHTML = html;
  }

  function updateVisuals(root, state, config) {
    var stage = root.querySelector(".barline-stage");
    var feedback = root.querySelector(".barline-feedback");
    var submitButton = root.querySelector('[data-action="submit"]');
    var overlay = stage.querySelector(".barline-cursor");
    var noteCount = (config.notes || []).length;

    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "barline-cursor";
      stage.appendChild(overlay);
    }

    // Position cursor line at midpoint between note cursorPos and cursorPos+1,
    // exactly where the barline would be drawn.
    var nx0 = state.noteXs[state.cursorPos];
    var nx1 = state.noteXs[state.cursorPos + 1];
    var lineX = (typeof nx0 === "number" && typeof nx1 === "number")
      ? Math.round((nx0 + nx1) / 2)
      : 0;
    overlay.style.left = (lineX - 1) + "px";
    overlay.style.width = "2px";

    renderPips(root, state, config);
    if (submitButton) {
      submitButton.disabled = !!state.submitted;
    }
    if (!state.lastGrade) {
      feedback.textContent = "";
      feedback.className = "barline-feedback";
      return;
    }

    feedback.textContent = state.lastGrade.correct ? "Correct" : "Try again";
    feedback.className =
      "barline-feedback " + (state.lastGrade.correct ? "is-correct" : "is-incorrect");
  }

  function staveLeft(stage) {
    // Approximate stave note area left edge (after clef/time sig)
    var svg = stage.querySelector("svg");
    return svg ? 65 : 65;
  }

  function staveRight(stage, config) {
    var svg = stage.querySelector("svg");
    if (svg) {
      return parseInt(svg.getAttribute("width"), 10) - 20;
    }
    return (stage.clientWidth || 600) - 20;
  }

  function submit(config, state) {
    var grade = logic.gradeBarlines(
      Array.from(state.placedAt),
      config.correct_barline_positions || []
    );
    var payload;

    state.lastGrade = grade;
    payload = logic.buildResultPayload({
      config: config,
      placedAt: Array.from(state.placedAt),
      correct: grade.correct,
    });

    fetch("/ajax/identification-answers/", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: "data=" + encodeURIComponent(JSON.stringify(payload)),
    }).catch(function () {
      return;
    });
    return grade;
  }

  function boot() {
    var config = window.__EXERCISE_CONFIG__;
    var root;
    var stage;
    var state;
    var noteCount;

    if (!config || config.type !== "umto_barline_placement") {
      return;
    }
    if (!logic) {
      throw new Error("barlinePlayerLogic is not loaded");
    }

    root = document.getElementById("qa-root");
    if (!root) {
      return;
    }

    noteCount = (config.notes || []).length;

    renderShell(root);
    stage = root.querySelector(".barline-stage");
    state = {
      cursorPos: 0,
      placedAt: new Set(),
      noteXs: [],
      lastGrade: null,
      submitted: false,
    };
    state.noteXs = drawNotation(stage, config, state.placedAt);
    console.log("[BARLINE] id=" + config.exerciseId + " ts=" + config.time_signature + " measures=" + config.measures + " correct=" + JSON.stringify(config.correct_barline_positions) + " notes=" + (config.notes||[]).map(function(n){return n.duration+(n.dots?'.':'')}));
    updateVisuals(root, state, config);

    var history = []; // stack of {placedAt: Set, cursorPos}

    function saveHistory() {
      history.push({ placedAt: new Set(state.placedAt), cursorPos: state.cursorPos });
    }

    function undo() {
      if (history.length === 0) return;
      var prev = history.pop();
      state.placedAt = prev.placedAt;
      state.cursorPos = prev.cursorPos;
      state.lastGrade = null;
      state.submitted = false;
      state.noteXs = drawNotation(stage, config, state.placedAt);
      updateVisuals(root, state, config);
    }

    function move(delta) {
      state.cursorPos = logic.clampCursor(state.cursorPos + delta, noteCount);
      updateVisuals(root, state, config);
    }

    function toggle() {
      saveHistory();
      if (state.placedAt.has(state.cursorPos)) {
        state.placedAt.delete(state.cursorPos);
      } else {
        state.placedAt.add(state.cursorPos);
      }
      state.lastGrade = null;
      state.submitted = false;
      state.noteXs = drawNotation(stage, config, state.placedAt);
      updateVisuals(root, state, config);
    }

    root.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) {
        return;
      }
      if (button.dataset.action === "left") move(-1);
      if (button.dataset.action === "right") move(1);
      if (button.dataset.action === "toggle") toggle();
      if (button.dataset.action === "submit") {
        if (state.submitted) {
          return;
        }
        submit(config, state);
        state.submitted = state.lastGrade && state.lastGrade.correct;
        updateVisuals(root, state, config);
        if (state.submitted && config.nextExercise) {
          window.setTimeout(function () {
            window.location.href = config.nextExercise;
          }, 1000);
        }
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        move(-1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        move(1);
      }
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
      if (event.key === "z" && (event.metaKey || event.ctrlKey) && !event.shiftKey) {
        event.preventDefault();
        undo();
      }
    });

    window.addEventListener("resize", function () {
      state.noteXs = drawNotation(stage, config, state.placedAt);
      updateVisuals(root, state, config);
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
