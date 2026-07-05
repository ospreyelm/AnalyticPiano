/**
 * render-lesson.js
 * ---------------------------------------------------------------------
 * Turns data/lesson-content.json into DOM sections inside `root`.
 *
 * Notation is rendered with the project's real VexFlow engine — the same
 * pipeline students are graded on (`VexflowAdapter` →
 * `VexflowRenderPipeline`) — so the lesson draws identically to exercise
 * and teacher/play views. Each `notation` object is converted into a
 * renderer-agnostic score model (via `ScoreModel`), then drawn on a
 * `<canvas>`. Figured-bass symbols ride the engine's harmonization-target
 * path (matched to each bass note by musical offset). Interval labels
 * (M2/m2) for the scale slides are post-drawn over the canvas using the
 * staff-layout callback's column X positions.
 * ---------------------------------------------------------------------
 */

import { renderCircleOfThirds } from "./circle-of-thirds.js";
import Vex from "vexflow";
import VexflowAdapter from "app/components/music/rendering/vexflow_adapter";
import ScoreModel from "app/components/music/score_model";

const BEATS = { w: 4, h: 2, q: 1, "8": 0.5, "16": 0.25 };

// The app's KeySignature model expects a 3-char code `[i|j][A-G][_|#|b]`
// (i = minor, j = major); e.g. "jC", "jG", "jBb". Lesson JSON uses plain
// letters ("G", "Bb", undefined). Convert, defaulting to C major (no
// accidentals) when the slide carries no key signature.
function keyToCode(key) {
  if (!key) return "jC_";
  const m = String(key).match(/^([A-Ga-g])([#b]?)$/);
  if (!m) return "jC_";
  const mode = m[1] === m[1].toLowerCase() ? "i" : "j";
  const letter = m[1].toUpperCase();
  const acc = m[2] || "_";
  return mode + letter + acc;
}

export function renderLesson(root, data) {
  root.innerHTML = "";
  for (const slide of data.slides) {
    root.appendChild(renderSlide(slide));
  }
}

function el(tag, className, html) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function renderSlide(slide) {
  const section = el("section", "lesson-section");
  section.id = slide.id;

  if (slide.type === "title") {
    section.appendChild(el("h1", "lesson-title", escapeHtml(slide.title)));
    for (const line of slide.subtitle || []) {
      section.appendChild(el("p", "lesson-subtitle", escapeHtml(line)));
    }
    return section;
  }

  if (slide.eyebrow) {
    section.appendChild(el("div", "lesson-eyebrow", escapeHtml(slide.eyebrow)));
  }
  if (slide.title) {
    section.appendChild(el("h2", "lesson-title", escapeHtml(slide.title)));
  }
  if (slide.bullets) {
    section.appendChild(renderBullets(slide.bullets));
  }
  if (slide.icon) {
    section.appendChild(renderWarningIcon());
  }
  if (slide.tables) {
    for (const t of slide.tables) section.appendChild(renderTable(t));
  }
  if (slide.diagrams) {
    for (const d of slide.diagrams) section.appendChild(renderDiagram(d));
  }
  if (slide.notation) {
    for (const n of slide.notation) {
      if (typeof n === "string") continue; // cross-reference note, nothing to render
      section.appendChild(renderNotation(n));
    }
  }

  return section;
}

function renderBullets(bullets) {
  const ul = el("ul", "lesson-bullets");
  for (const b of bullets) {
    const li = el("li");
    if (typeof b === "string") {
      li.appendChild(document.createTextNode(b));
    } else {
      li.appendChild(document.createTextNode(b.text));
      if (b.children) li.appendChild(renderBullets(b.children));
    }
    ul.appendChild(li);
  }
  return ul;
}

function renderTable(t) {
  const wrap = el("div", "lesson-figure");
  const table = el("table", "lesson-table");
  const thead = el("thead");
  const headRow = el("tr");
  for (const col of t.columns) headRow.appendChild(el("th", null, escapeHtml(col)));
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = el("tbody");
  for (const row of t.rows) {
    const tr = el("tr");
    const values = "symbols" in row
      ? [row.qualityPair, row.symbols.join(", ")]
      : Object.values(row);
    for (const v of values) tr.appendChild(el("td", null, escapeHtml(String(v))));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  if (t.purpose) wrap.appendChild(el("div", "lesson-figure-caption", escapeHtml(t.purpose)));
  return wrap;
}

function renderDiagram(d) {
  const wrap = el("div", "lesson-figure");
  const target = el("div");
  wrap.appendChild(target);
  renderCircleOfThirds(target, d.options);
  if (d.purpose) wrap.appendChild(el("div", "lesson-figure-caption", escapeHtml(d.purpose)));
  return wrap;
}

function renderWarningIcon() {
  const wrap = el("div", "lesson-warning");
  wrap.innerHTML = `
    <svg class="lesson-warning-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M1 21h22L12 2 1 21z" fill="#f1c40f"/>
      <rect x="11" y="9" width="2" height="6" fill="#111"/>
      <rect x="11" y="16.5" width="2" height="2" fill="#111"/>
    </svg>
  `;
  return wrap;
}

// --- notation -> score model -------------------------------------------------

// Parse a VexFlow key "g/4", "bb/4", "c#/5" -> {step:"A"-"G", alter, octave}.
// `bb/4` is B-flat (letter b, accidental b), NOT B-natural — the accidental run
// between the letter and the slash accumulates (#=+1, b=-1, n=0).
function parseKeyToPitch(key) {
  const m = String(key).match(/^([a-g])([#bn]*)\/(\d+)$/);
  if (!m) throw new Error(`lesson notation: unparseable key ${JSON.stringify(key)}`);
  const step = m[1].toUpperCase();
  let alter = 0;
  for (const c of m[2]) alter += (c === "#" ? 1 : c === "b" ? -1 : 0);
  return { step, alter, octave: parseInt(m[3], 10) };
}

const LETTER_PC = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
// Absolute pitch (octave*12 + pitch class). Middle C = c/4 = 48; the grand-staff
// register split sends notes < 48 to the bass voice, >= 48 to treble.
function keyPitch(key) {
  const p = parseKeyToPitch(key);
  const pc = LETTER_PC[p.step.toLowerCase()] + p.alter;
  return p.octave * 12 + pc;
}

// Build one score-model item (rest | note | chord) from a list of pitches.
// Chord notes are wrapped as `{pitch: {...}}` — the shape the render pipeline
// and timeline builder read (`item.notes[i].pitch`), matching umto_score_converter.
function itemFromPitches(pitches, duration) {
  if (!pitches || !pitches.length) return ScoreModel.rest(duration, 0);
  if (pitches.length === 1) {
    const p = pitches[0];
    return ScoreModel.note(p.step, p.alter, p.octave, duration, 0);
  }
  return ScoreModel.chord(pitches.map((p) => ({ pitch: p })), duration, 0);
}

// Convert one lesson `notation` object into a score model + the list of
// figured-bass targets (one per chord that carries a `figure`). Bass-note
// onsets accumulate in quarter-beats; each target's `offset` is the bass
// voice's cumulative quarter-beat position at that chord, which the engine
// matches back to the note column (offset_qb = note_onset_ticks / 1024).
function buildScore(n) {
  const notes = (n.voices && n.voices[0] && n.voices[0].notes) || [];
  const timeSig = n.timeSignature || "4/4";
  const parts = timeSig.split("/").map((x) => parseInt(x, 10) || 4);
  const beatsPerMeasure = parts[0] * (4 / parts[1]); // quarter-beats per measure
  const clef = n.clef || "treble";
  const isGrand = clef === "grand-staff";
  const staffDistribution = isGrand ? "grand_staff" : clef;
  const meta = {
    key: keyToCode(n.keySignature),
    time: timeSig,
    staffDistribution,
  };

  const measures = [];
  const targets = [];
  let trebleItems = [], bassItems = [];
  let beatsInMeasure = 0;
  let globalOffsetQb = 0;
  let measureNumber = 1;

  for (const note of notes) {
    const duration = note.duration || "q";
    const beats = BEATS[duration] || 1;
    if (note.figure) {
      targets.push({ offset: globalOffsetQb, displayFigure: note.figure });
    }
    const keys = note.keys || [];
    if (isGrand) {
      // Register split at middle C (>=48 -> treble, below -> bass), except the
      // chord's lowest note always anchors the bass staff — a grand-staff
      // figured-bass example needs a bass line under every chord, even one
      // stacked entirely at/above middle C (e.g. c/4-g/4-e/5-c/6).
      const sortedByPitch = keys.map((k, i) => ({ i, pitch: keyPitch(k) })).sort((a, b) => a.pitch - b.pitch);
      const lowestIdx = sortedByPitch[0].i;
      const treblePitches = [], bassPitches = [];
      keys.forEach((k, i) => {
        const p = parseKeyToPitch(k);
        if (i !== lowestIdx && keyPitch(k) >= 48) treblePitches.push(p);
        else bassPitches.push(p);
      });
      trebleItems.push(itemFromPitches(treblePitches, duration));
      bassItems.push(itemFromPitches(bassPitches, duration));
    } else if (clef === "bass") {
      bassItems.push(itemFromPitches(keys.map(parseKeyToPitch), duration));
    } else {
      trebleItems.push(itemFromPitches(keys.map(parseKeyToPitch), duration));
    }
    beatsInMeasure += beats;
    globalOffsetQb += beats;
    if (beatsInMeasure >= beatsPerMeasure) {
      measures.push(mkMeasure(measureNumber++, trebleItems, bassItems, isGrand, clef));
      trebleItems = []; bassItems = []; beatsInMeasure = 0;
    }
  }
  if (trebleItems.length || bassItems.length) {
    measures.push(mkMeasure(measureNumber++, trebleItems, bassItems, isGrand, clef));
  }

  return { score: ScoreModel.score(meta, measures), targets, staffDistribution };
}

function mkMeasure(num, trebleItems, bassItems, isGrand, clef) {
  if (isGrand) {
    return ScoreModel.measure(num, {
      treble: ScoreModel.staff("treble", [ScoreModel.voice(trebleItems, "up")]),
      bass: ScoreModel.staff("bass", [ScoreModel.voice(bassItems, "down")]),
    });
  }
  if (clef === "bass") {
    return ScoreModel.measure(num, {
      bass: ScoreModel.staff("bass", [ScoreModel.voice(bassItems, "down")]),
    });
  }
  return ScoreModel.measure(num, {
    treble: ScoreModel.staff("treble", [ScoreModel.voice(trebleItems, "up")]),
  });
}

// Max item count across a measure's staves/voices — used to size measure
// width (a whole-note-only measure needs far less horizontal room than one
// full of quarter notes).
function measureItemCount(meas) {
  let max = 0;
  for (const staff of Object.values(meas.staves)) {
    for (const voice of staff.voices) max = Math.max(max, voice.items.length);
  }
  return max;
}

// --- interval labels (scale slides) ------------------------------------------

// Label the ascending interval between two VexFlow keys as a second (M2/m2).
// Returns null for anything that isn't a stepwise second.
function intervalLabel(lowKey, highKey) {
  const a = String(lowKey).match(/^([a-g])([#bn]*)\/(\d+)$/);
  const b = String(highKey).match(/^([a-g])([#bn]*)\/(\d+)$/);
  if (!a || !b) return null;
  const accOff = { "#": 1, b: -1, n: 0 };
  const pcA = LETTER_PC[a[1]] + [...a[2]].reduce((s, c) => s + (accOff[c] || 0), 0);
  const pcB = LETTER_PC[b[1]] + [...b[2]].reduce((s, c) => s + (accOff[c] || 0), 0);
  const semis = (parseInt(b[3], 10) - parseInt(a[3], 10)) * 12 + (pcB - pcA);
  if (semis === 2) return "M2";
  if (semis === 1) return "m2";
  return null;
}

// Post-draw M2/m2 labels between consecutive scale notes, horizontally
// centered between the two note columns they span. `columns` come from the
// engine's onStaffLayout callback (sorted by centerX, each carrying its
// onset in ticks). `notes` is the original scale note list (one key each).
function drawIntervalLabels(ctx, notes, columns, topLineY) {
  if (!notes.length || columns.length < 2) return;
  // Map each note's onset (ticks; 1024 = 1 quarter) -> column centerX.
  // Onsets accumulate per note: 0, beats[0]*1024, (beats0+beats1)*1024, ...
  const onsetToX = new Map();
  let acc = 0;
  for (const c of columns) onsetToX.set(c.onset, c.centerX);
  const xs = [];
  let onset = 0;
  for (const note of notes) {
    xs.push(onsetToX.get(onset) || null);
    onset += (BEATS[note.duration || "q"] || 1) * 1024;
  }
  ctx.save();
  ctx.setFont("bold 11px Arial, sans-serif");
  ctx.setFillStyle("#c0392b");
  const y = topLineY - 6;
  for (let i = 1; i < notes.length; i++) {
    const label = intervalLabel(notes[i - 1].keys[0], notes[i].keys[0]);
    if (!label) continue;
    if (xs[i - 1] == null || xs[i] == null) continue;
    const midX = (xs[i - 1] + xs[i]) / 2;
    const w = ctx.measureText(label).width;
    ctx.fillText(label, midX - w / 2, y);
  }
  ctx.restore();
}

// --- notation render ---------------------------------------------------------

function renderNotation(n) {
  const wrap = el("div", "lesson-figure");
  const target = el("div", "vexflow-target");
  target.dataset.notationId = n.id;

  try {
    renderNotationWithEngine(target, n);
  } catch (err) {
    console.warn(`Lesson notation "${n.id}" render failed:`, err);
    target.textContent = `[notation render of "${n.id}" failed: ${err.message}]`;
  }

  wrap.appendChild(target);
  if (n.purpose) wrap.appendChild(el("div", "lesson-figure-caption", escapeHtml(n.purpose)));
  if (n.derivationNote) {
    wrap.appendChild(el("div", "lesson-note", escapeHtml(n.derivationNote)));
  }
  return wrap;
}

function renderNotationWithEngine(target, n) {
  const { score, targets, staffDistribution } = buildScore(n);
  const numMeasures = score.measures.length;
  if (!numMeasures) throw new Error("no measures");

  const isGrand = staffDistribution === "grand_staff";
  // Figured-bass symbols draw below the bass staff (getBottomY() + 16, up to
  // 3 stacked lines) — extra height keeps them from clipping the canvas edge.
  const height = isGrand ? (targets.length ? 420 : 260) : 170;
  // The engine's Formatter stretches each measure to fill its allotted width
  // regardless of note count, so a measure holding a single whole note gets
  // the same width as one with 4 quarter notes — wasted space that pushes
  // later measures off-screen. Narrow the per-measure budget when every
  // measure here holds at most one event (the common figured-bass-example
  // case: one whole-note chord per bar).
  const maxItemsPerMeasure = Math.max(...score.measures.map(measureItemCount));
  const perMeasureWidth = maxItemsPerMeasure <= 1 ? 105 : 230;
  const width = Math.max(280, numMeasures * perMeasureWidth);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  // Render at native pixel size (matches teacher/play's notation scale) —
  // `.lesson-figure` scrolls horizontally rather than shrinking wide scores
  // down to fit the 900px lesson column.
  canvas.style.display = "block";
  target.appendChild(canvas);

  const renderer = new Vex.Flow.Renderer(canvas, Vex.Flow.Renderer.Backends.CANVAS);
  const notes = (n.voices && n.voices[0] && n.voices[0].notes) || [];

  // Default note styling is exercise UX: gray until played, black once the
  // student plays it. A static lesson figure has no "played" state — force
  // every voice slot to black so notation reads as normal engraved music.
  const opts = {
    width, height, maxMeasures: numMeasures, staffDistribution,
    voiceColors: { S: "#000000", A: "#000000", T: "#000000", B: "#000000" },
  };
  if (targets.length) {
    opts.isHarmonization = true;
    opts.harmonizationTargets = targets;
    // isHarmonization normally hides voices the student hasn't unlocked yet
    // (exercise grading UX). This is a static lesson figure, not a graded
    // exercise — every voice should always be visible, so lock them all.
    opts.lockedVoices = ["S", "A", "T", "B"];
    // The annotation pass (figures, romans, etc.) only runs when analysis is
    // "enabled" — without this, harmonizationTargets are collected into cfg
    // but drawMeasureAnnotations never runs, so no figure ever draws.
    opts.analyzeConfig = { enabled: true, mode: {} };
  }

  // Collect staff-layout columns for post-drawn interval labels.
  let layoutInfo = null;
  if (n.showIntervals) {
    opts.onStaffLayout = (info) => { layoutInfo = info; };
  }

  VexflowAdapter.render(score, renderer, opts);

  if (n.showIntervals && layoutInfo) {
    const sys = layoutInfo.systems && layoutInfo.systems[0];
    const trebleStave = sys && sys.staves.find((s) => s.clef === "treble");
    const topLineY = trebleStave ? trebleStave.topLineY : 40;
    drawIntervalLabels(renderer.getContext(), notes, layoutInfo.columns, topLineY);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}