(function () {
  "use strict";

  var logic = window.barlinePlayerLogic;
  var CURSOR_HORIZONTAL_INSET = 10;

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
      var beams = VF.Beam.generateBeams(vfNotes);
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
    var boundaries;
    var x0;
    var x1;
    var cursorInset;

    if (!overlay) {
      overlay = document.createElement("div");
      overlay.className = "barline-cursor";
      stage.appendChild(overlay);
    }

    // Compute boundaries between notes for cursor positioning
    boundaries = logic.noteBoundaries(
      state.noteXs,
      staveLeft(stage),
      staveRight(stage, config)
    );

    x0 = boundaries[state.cursorPos] || 0;
    x1 = boundaries[state.cursorPos + 1] || x0 + 20;
    cursorInset = Math.min(CURSOR_HORIZONTAL_INSET, Math.max(0, (x1 - x0 - 12) / 2));
    overlay.style.left = x0 + cursorInset + "px";
    overlay.style.width = Math.max(12, x1 - x0 - cursorInset * 2) + "px";

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
    updateVisuals(root, state, config);

    function move(delta) {
      state.cursorPos = logic.clampCursor(state.cursorPos + delta, noteCount);
      updateVisuals(root, state, config);
    }

    function toggle() {
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
    });

    window.addEventListener("resize", function () {
      state.noteXs = drawNotation(stage, config, state.placedAt);
      updateVisuals(root, state, config);
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
