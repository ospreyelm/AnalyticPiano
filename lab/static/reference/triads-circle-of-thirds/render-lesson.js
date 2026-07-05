/**
 * render-lesson.js
 * ---------------------------------------------------------------------
 * Turns data/lesson-content.json into DOM sections inside `root`.
 *
 * This is intentionally simple/vanilla so a coding agent can either:
 *   (a) use it as-is inside a Django template + Vite entry, or
 *   (b) treat it as a reference implementation and re-express the same
 *       JSON -> markup mapping inside your framework of choice
 *       (React/Vue/etc.), since the JSON is the real source of truth.
 *
 * Notation rendering (`renderNotationPlaceholder`) is a STUB. This site
 * already renders VexFlow elsewhere, so real integration should replace
 * that function's body with a call into your existing VexFlow wrapper,
 * passing it the same `notation` object (clef/keySignature/timeSignature
 * /voices) documented in lesson-content.json's `meta.notationFormat`.
 * A minimal illustrative VexFlow render is included behind a feature
 * check (`window.Vex`) purely so the demo page shows *something*
 * playable without you having to wire up the real renderer first.
 * ---------------------------------------------------------------------
 */

import { renderCircleOfThirds } from "./circle-of-thirds.js";
// Use this project's own VexFlow build via the vite alias (`vexflow` ->
// lab/static/js/lib/vexflow.js, 4.2.5). Same import the app's render pipeline
// uses, so the lesson draws with the exact engine students are graded on.
import Vex from "vexflow";

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
      if (typeof n === "string") continue; // cross-reference note, nothing to render here
      section.appendChild(renderNotationPlaceholder(n));
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

/**
 * STUB: replace with a call into this site's existing VexFlow renderer.
 * `n` is one of the `notation` objects from lesson-content.json.
 */
function renderNotationPlaceholder(n) {
  const wrap = el("div", "lesson-figure");
  const target = el("div", "vexflow-target");
  target.dataset.notationId = n.id;
  target.textContent = `[VexFlow renders "${n.id}" here — see data/lesson-content.json]`;

  // Draw with the project's VexFlow (imported above via the vite alias).
  if (Vex && Vex.Flow && n.voices && n.voices[0]) {
    try {
      target.textContent = "";
      drawIllustrativeVexflow(target, n);
    } catch (err) {
      console.warn("Illustrative VexFlow render skipped:", err);
      target.textContent = `[VexFlow render of "${n.id}" failed: ${err.message}]`;
    }
  }

  wrap.appendChild(target);
  if (n.purpose) wrap.appendChild(el("div", "lesson-figure-caption", escapeHtml(n.purpose)));
  if (n.derivationNote) {
    wrap.appendChild(el("div", "lesson-note", escapeHtml(n.derivationNote)));
  }
  return wrap;
}

// Label the ascending interval between two VexFlow keys as a second (M2/m2).
// Returns null for anything that isn't a stepwise second — only meant for the
// scale slides, which move by adjacent scale degrees.
const LETTER_PC = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 };
function intervalLabel(lowKey, highKey) {
  const a = String(lowKey).match(/^([a-g])([#bn]*)\/(\d+)$/);
  const b = String(highKey).match(/^([a-g])([#bn]*)\/(\d+)$/);
  if (!a || !b) return null;
  const accOff = { "#": 1, b: -1, n: 0 };
  const pcA = LETTER_PC[a[1]] + [...a[2]].reduce((s, c) => s + (accOff[c] || 0), 0);
  const pcB = LETTER_PC[b[1]] + [...b[2]].reduce((s, c) => s + (accOff[c] || 0), 0);
  const octA = parseInt(a[3], 10), octB = parseInt(b[3], 10);
  const semis = (octB - octA) * 12 + (pcB - pcA);
  // Only label diatonic seconds (1 or 2 semitones ascending).
  if (semis === 2) return "M2";
  if (semis === 1) return "m2";
  return null;
}

function drawIllustrativeVexflow(target, n) {
  // VexFlow is loaded as a classic UMD script (index.html) that sets
  // window.Vex. This file is an ES module, so the bare global `Vex` is NOT
  // in module scope — reference window.Vex explicitly or import it.
  const { Renderer, Stave, StaveNote, Voice, Formatter, Accidental, Annotation } = Vex.Flow;
  const notes = n.voices[0].notes;
  const width = Math.max(300, notes.length * 90);
  const renderer = new Renderer(target, Renderer.Backends.SVG);
  renderer.resize(width, 160);
  const context = renderer.getContext();
  const stave = new Stave(10, 20, width - 20);
  stave.addClef(n.clef === "grand-staff" ? "treble" : n.clef || "treble");
  if (n.keySignature) stave.addKeySignature(n.keySignature);
  if (n.timeSignature) stave.addTimeSignature(n.timeSignature);
  stave.setContext(context).draw();

  const vfNotes = notes.map((note) => {
    const sn = new StaveNote({
      clef: n.clef === "grand-staff" ? "treble" : n.clef || "treble",
      keys: note.keys,
      duration: note.duration || "q",
    });
    note.keys.forEach((k, i) => {
      // VexFlow key syntax: <letter a-g><accidentals #bn>/<octave>. Parse the
      // accidental run between the letter and the slash — "bb/4" is B-flat
      // (letter b, accidental b), NOT B-natural. The old `k.includes("b") &&
      // !k.startsWith("b")` check skipped every B-flat because "bb/4" starts
      // with "b", so all flats on the letter B silently dropped.
      const m = k.match(/^([a-g])([#bn]*)\//);
      const acc = m ? m[2] : "";
      if (acc) sn.addModifier(new Accidental(acc), i);
    });
    return sn;
  });

  // Scale slides set `showIntervals: true` to label the stepwise interval
  // between each consecutive note (M2 / m2). The annotation sits above the
  // note that ENDS the interval, so it reads as "the interval leading into
  // this note". Computed from pitch classes so it stays correct under any
  // key signature / accidental spelling.
  if (n.showIntervals) {
    for (let i = 1; i < vfNotes.length; i++) {
      const label = intervalLabel(notes[i - 1].keys[0], notes[i].keys[0]);
      if (label) {
        vfNotes[i].addModifier(
          new Annotation(label).setVerticalJustification(Annotation.VerticalJustify.TOP),
          0
        );
      }
    }
  }

  const totalBeats = notes.reduce((sum, note) => {
    const map = { w: 4, h: 2, q: 1, 8: 0.5 };
    return sum + (map[note.duration] || 1);
  }, 0);

  const voice = new Voice({ num_beats: totalBeats || notes.length, beat_value: 4 });
  voice.setStrict(false);
  voice.addTickables(vfNotes);
  new Formatter().joinVoices([voice]).format([voice], width - 60);
  voice.draw(context, stave);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
