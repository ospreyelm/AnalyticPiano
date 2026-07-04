/**
 * circle-of-thirds.js
 * ---------------------------------------------------------------------
 * A reusable, parametric SVG diagram for teaching triad/seventh-chord
 * root-finding, based on "Seventh Chords and Roman Numerals" (MUS 141,
 * Dr. Amanda Heim).
 *
 * There are two "wheels" the deck uses, and this one component renders
 * both, controlled by `mode`:
 *
 *   mode: "seconds"
 *     The reference wheel. All 7 natural letters plotted in stepwise
 *     (scale) order clockwise, C fixed at 12 o'clock, with the M2/m2
 *     interval between each neighboring pair labeled around the rim.
 *     Chord tones are simply highlighted (root color vs. non-root-color);
 *     no rotation, no boxes, no arrow. This is the "here's the idea"
 *     diagram (deck slide 2, left circle).
 *
 *   mode: "thirds"
 *     The working wheel used everywhere else. All 7 natural letters
 *     plotted in THIRDS order (C-E-G-B-D-F-A, repeating), ROTATED so the
 *     given chord's root sits at 12 o'clock. The first `chordSize` notes
 *     clockwise from the root (3 for a triad, 4 for a seventh chord) are
 *     drawn as labeled boxes: Root, Third, Fifth, (Seventh). The
 *     remaining notes are plain, unlabeled dots continuing the wheel.
 *     A curved arrow sweeps counter-clockwise from the last labeled
 *     chord tone back to the root, illustrating the "scan backward
 *     through the stack of thirds until you find where it starts"
 *     search used to locate the root (deck slide 2 right circle, and
 *     slide 12's seventh-chord root-finding diagram).
 *
 * USAGE
 * -----
 *   import { renderCircleOfThirds } from "./circle-of-thirds.js";
 *
 *   renderCircleOfThirds(document.getElementById("diagram-1"), {
 *     mode: "thirds",
 *     root: "G",
 *     chordSize: 4,                 // 3 = triad, 4 = seventh chord
 *     accidentals: { F: "#" }       // optional, letter -> "#" | "b" | "x" | "bb" | ""
 *   });
 *
 *   renderCircleOfThirds(document.getElementById("diagram-2"), {
 *     mode: "seconds",
 *     chordTones: ["C", "E", "G"],  // which of the 7 natural letters to highlight
 *   });
 *
 * No dependencies. No framework assumed (plain DOM / SVG), so it can be
 * dropped into a Django template, a Vite entry, or wrapped by a React/Vue
 * component in this project without modification.
 * ---------------------------------------------------------------------
 */

// The fixed cycle of natural letters in thirds-order. Reading forward
// (wrapping) from ANY starting letter gives the clockwise order of the
// "thirds wheel" rotated so that letter is at the top.
const THIRDS_CYCLE = ["C", "E", "G", "B", "D", "F", "A"];

// The fixed cycle of natural letters in stepwise/scale order, used only
// by "seconds" mode. C is always plotted at 12 o'clock.
const SECONDS_CYCLE = ["C", "D", "E", "F", "G", "A", "B"];

// Interval quality between each consecutive pair in SECONDS_CYCLE
// (i.e. SECONDS_CYCLE[i] -> SECONDS_CYCLE[i+1]).
const SECONDS_INTERVALS = ["M2", "M2", "m2", "M2", "M2", "M2", "m2"];

const CHORD_TONE_LABELS = ["Root", "Third", "Fifth", "Seventh"];

const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function pointOnCircle(cx, cy, r, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

/**
 * Rotate THIRDS_CYCLE so `root` comes first, giving the clockwise
 * sequence of letters starting at the root.
 */
function thirdsSequenceFrom(root) {
  const idx = THIRDS_CYCLE.indexOf(root);
  if (idx === -1) {
    throw new Error(
      `circle-of-thirds: "${root}" is not a natural pitch letter (A-G).`
    );
  }
  return THIRDS_CYCLE.slice(idx).concat(THIRDS_CYCLE.slice(0, idx));
}

function accidentalGlyph(acc) {
  switch (acc) {
    case "#":
      return "\u266F";
    case "b":
      return "\u266D";
    case "x":
      return "\uD834\uDD2A"; // double sharp
    case "bb":
      return "\u266D\u266D";
    default:
      return "";
  }
}

/**
 * Main entry point. Clears `container` and renders the diagram into it.
 *
 * @param {HTMLElement} container
 * @param {Object} options
 * @param {"thirds"|"seconds"} [options.mode="thirds"]
 * @param {string} [options.root]         Required for mode "thirds". One of A-G.
 * @param {number} [options.chordSize=3]  3 (triad) or 4 (seventh chord). Mode "thirds" only.
 * @param {string[]} [options.chordTones] Which natural letters to highlight. Mode "seconds" only.
 * @param {Object<string,string>} [options.accidentals] letter -> "#"|"b"|"x"|"bb"
 * @param {number} [options.size=340]     Rendered pixel size (square).
 * @param {string} [options.rootColor="#c0392b"]
 * @param {string} [options.chordColor="#c0392b"]
 * @param {string} [options.dimColor="#2e86ab"]
 * @param {string[]} [options.customCycle] Optional custom list of labels for seconds mode (e.g. solfege)
 * @param {boolean} [options.hideNonChordTones] Optional flag to hide non-highlighted nodes in seconds mode
 */
export function renderCircleOfThirds(container, options = {}) {
  const {
    mode = "thirds",
    root,
    chordSize = 3,
    chordTones,
    accidentals = {},
    size = 340,
    rootColor = "#c0392b",
    chordColor = "#c0392b",
    dimColor = "#2e86ab",
    customCycle,
    hideNonChordTones = false,
  } = options;

  container.innerHTML = "";
  container.classList.add("cot-diagram");

  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.32; // radius to note nodes
  const nodeR = size * 0.055;

  const svg = svgEl("svg", {
    viewBox: `0 0 ${size} ${size}`,
    width: size,
    height: size,
    class: "cot-svg",
    role: "img",
    "aria-label":
      mode === "thirds"
        ? `Circle of thirds rooted on ${root}`
        : `Circle of seconds highlighting ${(chordTones || []).join(", ")}`,
  });

  // base ring
  svg.appendChild(
    svgEl("circle", {
      cx,
      cy,
      r,
      fill: "none",
      stroke: "currentColor",
      "stroke-width": 2,
      class: "cot-ring",
    })
  );

  if (mode === "seconds") {
    renderSecondsWheel(svg, {
      cx,
      cy,
      r,
      nodeR,
      chordTones: chordTones || [],
      chordColor,
      dimColor,
      customCycle,
      hideNonChordTones,
    });
  } else {
    if (!root) throw new Error('circle-of-thirds: mode "thirds" requires a root note.');
    if (chordSize !== 3 && chordSize !== 4) {
      throw new Error('circle-of-thirds: chordSize must be 3 (triad) or 4 (seventh chord).');
    }
    renderThirdsWheel(svg, {
      cx,
      cy,
      r,
      nodeR,
      root,
      chordSize,
      accidentals,
      rootColor,
      chordColor,
      dimColor,
      size,
    });
  }

  container.appendChild(svg);
}

function renderSecondsWheel(svg, { cx, cy, r, nodeR, chordTones, chordColor, dimColor, customCycle, hideNonChordTones }) {
  const cycle = customCycle || SECONDS_CYCLE;
  const n = cycle.length;
  const angleStep = 360 / n;
  const startAngle = -90; // 12 o'clock

  const positions = cycle.map((letter, i) => {
    const angle = startAngle + i * angleStep;
    return { letter, angle, ...pointOnCircle(cx, cy, r, angle) };
  });

  // interval labels between consecutive letters, placed just outside the rim
  positions.forEach((p, i) => {
    if (hideNonChordTones) return; // skip interval labels if we are hiding non-chord tones
    const next = positions[(i + 1) % n];
    const midAngle = p.angle + angleStep / 2;
    const labelPt = pointOnCircle(cx, cy, r * 1.32, midAngle);
    const label = svgEl("text", {
      x: labelPt.x,
      y: labelPt.y,
      "text-anchor": "middle",
      "dominant-baseline": "middle",
      class: "cot-interval-label",
    });
    label.textContent = SECONDS_INTERVALS[i] || "";
    svg.appendChild(label);
  });

  // nodes
  positions.forEach(({ letter, x, y }) => {
    const isChordTone = chordTones.includes(letter);
    if (hideNonChordTones && !isChordTone) return; // skip rendering for hidden nodes

    const g = svgEl("g", { class: "cot-node" });
    g.appendChild(
      svgEl("circle", {
        cx: x,
        cy: y,
        r: nodeR,
        fill: isChordTone ? chordColor : dimColor,
        class: "cot-node-circle",
      })
    );
    const label = svgEl("text", {
      x,
      y,
      "text-anchor": "middle",
      "dominant-baseline": "middle",
      class: "cot-node-label",
    });
    label.textContent = letter;
    g.appendChild(label);
    svg.appendChild(g);
  });
}

function renderThirdsWheel(
  svg,
  { cx, cy, r, nodeR, root, chordSize, accidentals, rootColor, chordColor, dimColor, size }
) {
  const seq = thirdsSequenceFrom(root); // clockwise order starting at root
  const n = seq.length;
  const angleStep = 360 / n;
  const startAngle = -90; // root at 12 o'clock

  const positions = seq.map((letter, i) => {
    const angle = startAngle + i * angleStep;
    return { letter, angle, index: i, ...pointOnCircle(cx, cy, r, angle) };
  });

  // curved "search" arrow: from the last chord tone back to the root,
  // sweeping counter-clockwise (i.e. backward through the stack).
  const lastIdx = chordSize - 1;
  const rootPt = positions[0];
  const lastPt = positions[lastIdx];

  // control point: pulled toward the circle's interior, biased toward
  // the counter-clockwise side so the curve visibly "sweeps backward"
  // rather than cutting a straight chord.
  const midAngle = (rootPt.angle + lastPt.angle) / 2 - angleStep * 0.4;
  const controlPt = pointOnCircle(cx, cy, r * 0.35, midAngle);

  const arrowId = `cot-arrowhead-${Math.random().toString(36).slice(2, 8)}`;
  const defs = svgEl("defs");
  const marker = svgEl("marker", {
    id: arrowId,
    viewBox: "0 0 10 10",
    refX: 8,
    refY: 5,
    markerWidth: 6,
    markerHeight: 6,
    orient: "auto-start-reverse",
  });
  marker.appendChild(svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", class: "cot-arrowhead" }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  const path = svgEl("path", {
    d: `M ${lastPt.x} ${lastPt.y} Q ${controlPt.x} ${controlPt.y} ${rootPt.x} ${rootPt.y}`,
    fill: "none",
    class: "cot-search-arrow",
    "marker-end": `url(#${arrowId})`,
  });
  svg.appendChild(path);

  // "Root" caption near the arrowhead / root node
  const rootCaptionPt = pointOnCircle(cx, cy, r * 0.62, rootPt.angle - angleStep * 0.55);
  const rootCaption = svgEl("text", {
    x: rootCaptionPt.x,
    y: rootCaptionPt.y,
    "text-anchor": "middle",
    class: "cot-root-caption",
  });
  rootCaption.textContent = "Root";
  svg.appendChild(rootCaption);

  // nodes
  positions.forEach(({ letter, x, y, index }) => {
    const isChordTone = index < chordSize;
    const acc = accidentals[letter] || "";
    const displayLetter = letter + accidentalGlyph(acc);

    if (isChordTone) {
      // labeled box (Root / Third / Fifth / Seventh)
      const boxW = size * 0.16;
      const boxH = size * 0.2;
      const g = svgEl("g", { class: "cot-node cot-node-boxed" });
      g.appendChild(
        svgEl("rect", {
          x: x - boxW / 2,
          y: y - boxH / 2,
          width: boxW,
          height: boxH,
          rx: 4,
          class: "cot-box",
          stroke: index === 0 ? rootColor : chordColor,
        })
      );
      const roleLabel = svgEl("text", {
        x,
        y: y - boxH * 0.22,
        "text-anchor": "middle",
        class: "cot-box-role",
      });
      roleLabel.textContent = CHORD_TONE_LABELS[index];
      g.appendChild(roleLabel);

      const noteLabel = svgEl("text", {
        x,
        y: y + boxH * 0.28,
        "text-anchor": "middle",
        class: "cot-box-note",
      });
      noteLabel.textContent = displayLetter;
      g.appendChild(noteLabel);

      svg.appendChild(g);
    } else {
      const g = svgEl("g", { class: "cot-node" });
      g.appendChild(
        svgEl("circle", {
          cx: x,
          cy: y,
          r: nodeR,
          fill: dimColor,
          class: "cot-node-circle",
        })
      );
      const label = svgEl("text", {
        x,
        y,
        "text-anchor": "middle",
        "dominant-baseline": "middle",
        class: "cot-node-label",
      });
      label.textContent = displayLetter;
      g.appendChild(label);
      svg.appendChild(g);
    }
  });
}

/**
 * Convenience helper: given a root letter and chord size, return the
 * clockwise letter sequence and the labeled subset. Useful if you want
 * the data without rendering anything (e.g. to also print "G-B-D-F" as
 * text next to the diagram).
 */
export function getThirdsChordTones(root, chordSize = 3) {
  const seq = thirdsSequenceFrom(root);
  return seq.slice(0, chordSize);
}
