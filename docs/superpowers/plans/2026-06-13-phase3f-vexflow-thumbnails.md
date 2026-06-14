# Phase 3F: VexFlow Thumbnails — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent spec:** [docs/superpowers/plans/2026-06-13-phase3-curation-workbench.md](2026-06-13-phase3-curation-workbench.md)

**Prerequisite:** Plans 3C and 3D must be merged first. The `exercise-preview` endpoint (`GET /teacher/library/exercises/<id>/preview/ → {score_data: ...}`) must exist.

**Goal:** Render a score preview thumbnail (first 2 measures, treble staff only) on the exercise editor page using VexFlow. The preview loads lazily after the page renders via `fetch` → VexFlow canvas draw.

**Architecture:** VexFlow is loaded from its published UMD bundle on npm CDN (no build-system changes). A standalone `<script>` in `exercise_editor.html` fetches `score_data` from the existing preview endpoint, extracts the first 2 measures of the treble staff, and renders them onto a `<canvas>` using VexFlow's `Renderer`, `Stave`, `StaveNote`, and `Formatter` APIs. The teacher app does not use require.js, so VexFlow must be loaded as a plain `<script src>` tag — the UMD build at `https://unpkg.com/vexflow/build/cjs/vexflow.js` exposes `window.Vex`.

**Important scope constraints:**
- Render treble staff only, first 2 measures, notes only (no beams, no ties, no figured bass overlay)
- Skip gracefully if `score_data` is null, malformed, or has no treble staff
- No retry on failure — show "Preview unavailable" text and stop
- Do not reuse `vexflow_adapter.js` — it is an AMD module and incompatible with this context

**Tech Stack:** VexFlow UMD bundle (loaded inline), `fetch`, `<canvas>`.

**Run tests with:**
No automated test for canvas output — verify manually in browser.

---

## File map

| File | Action |
|---|---|
| `apps/teacher/templates/teacher/exercise_editor.html` | Add canvas element + thumbnail script |
| `apps/teacher/views_library.py` | No changes (endpoint exists from Plan 3C) |

---

## Task 1: Add canvas and thumbnail script to exercise editor

**Files:**
- Modify: `apps/teacher/templates/teacher/exercise_editor.html`

- [ ] **Add VexFlow CDN script tag to `{% block head_extra %}`**

In `exercise_editor.html`, inside `{% block head_extra %}`, after the existing `<script>` block, add:

```html
<script src="https://unpkg.com/vexflow@4/build/cjs/vexflow.js"></script>
```

- [ ] **Add canvas element to the sidebar card**

Replace the current sidebar in `exercise_editor.html`. Find the `t-detail-side` div. Add a new card at the top:

```html
  <!-- Sidebar: score preview -->
  <div class="t-detail-side">
    <div class="t-card" id="preview-card">
      <div class="t-card-title">Score preview</div>
      <div id="preview-container" style="width:100%;min-height:100px;overflow:hidden;">
        <p class="t-muted" id="preview-msg" style="font-size:0.78rem;">Loading preview…</p>
        <canvas id="preview-canvas" style="display:none;max-width:100%;border-radius:4px;border:1px solid var(--border);"></canvas>
      </div>
    </div>
    <!-- … existing in-playlists card … -->
```

- [ ] **Add thumbnail rendering script to `{% block body_extra %}`**

In `{% block body_extra %}`, before the closing `</script>` of the existing block (or add a new `<script>` block):

```html
<script>
(function() {
  var previewUrl = "{% url 'teacher:exercise-preview' exercise.id %}";
  var canvas     = document.getElementById("preview-canvas");
  var msg        = document.getElementById("preview-msg");

  function showError(text) {
    msg.textContent = text || "Preview unavailable.";
    msg.style.display = "";
    canvas.style.display = "none";
  }

  function extractMeasures(scoreData, maxMeasures) {
    // Returns flat array of note dicts: {pitch: str, duration: str, dots: int}[][]
    // One inner array per measure, representing treble voice 0 items.
    if (!scoreData || !scoreData.measures) return null;
    var measures = scoreData.measures.slice(0, maxMeasures);
    return measures.map(function(m) {
      try {
        return m.staves.treble.voices[0].items || [];
      } catch(e) {
        return [];
      }
    });
  }

  var DUR_MAP = { "w": "w", "h": "h", "q": "q", "8": "8", "16": "16", "32": "32" };

  function pitchToVex(step, alter, octave) {
    // Convert CIR pitch to VexFlow key string, e.g. "C#/4"
    var acc = alter === 1 ? "#" : alter === -1 ? "b" : "";
    return step + acc + "/" + octave;
  }

  function renderThumbnail(scoreData) {
    var measureItems = extractMeasures(scoreData, 2);
    if (!measureItems || !measureItems.length) {
      showError("No treble staff found.");
      return;
    }

    var VF = window.Vex.Flow;
    if (!VF) { showError("VexFlow unavailable."); return; }

    var W = 300, H = 120;
    canvas.width  = W;
    canvas.height = H;
    canvas.style.display = "block";
    msg.style.display = "none";

    var renderer = new VF.Renderer(canvas, VF.Renderer.Backends.CANVAS);
    renderer.resize(W, H);
    var ctx = renderer.getContext();
    ctx.clearRect(0, 0, W, H);

    var staveWidth = Math.floor((W - 20) / measureItems.length);
    var staves = [];
    var noteGroups = [];

    measureItems.forEach(function(items, idx) {
      var x = 10 + idx * staveWidth;
      var stave = new VF.Stave(x, 10, staveWidth - 4);
      if (idx === 0) stave.addClef("treble");
      stave.setContext(ctx).draw();
      staves.push(stave);

      var notes = [];
      (items || []).forEach(function(item) {
        try {
          var dur = DUR_MAP[item.duration && item.duration.type] || "q";
          if (item.kind === "rest") {
            notes.push(new VF.StaveNote({keys: ["b/4"], duration: dur + "r"}));
            return;
          }
          var keys;
          if (item.kind === "chord" && item.pitches) {
            keys = item.pitches.map(function(p) {
              return pitchToVex(p.step, p.alter || 0, p.octave);
            });
          } else if (item.pitch) {
            keys = [pitchToVex(item.pitch.step, item.pitch.alter || 0, item.pitch.octave)];
          } else {
            return;
          }
          var n = new VF.StaveNote({keys: keys, duration: dur});
          if (item.duration && item.duration.dots) {
            for (var d = 0; d < item.duration.dots; d++) VF.Dot.buildAndAttach([n]);
          }
          notes.push(n);
        } catch(e) { /* skip malformed note */ }
      });

      if (!notes.length) return;
      noteGroups.push({stave: stave, notes: notes});
    });

    noteGroups.forEach(function(g) {
      try {
        var voice = new VF.Voice({num_beats: g.notes.length, beat_value: 4}).setStrict(false);
        voice.addTickables(g.notes);
        new VF.Formatter().joinVoices([voice]).format([voice], g.stave.getWidth() - 24);
        voice.draw(ctx, g.stave);
      } catch(e) { /* skip measure on error */ }
    });
  }

  fetch(previewUrl)
    .then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); })
    .then(function(j) {
      if (!j.score_data) { showError("No score data."); return; }
      renderThumbnail(j.score_data);
    })
    .catch(function() { showError("Preview unavailable."); });
})();
</script>
```

- [ ] **Browser smoke test — exercise with score data**

1. Start dev server: `DJANGO_SETTINGS_MODULE=harmony.settings.local python manage.py runserver`
2. Open `/teacher/library/?tab=exercises`
3. Click any exercise that was imported from a Bach chorale or created via `/teacher/play/`
4. Confirm score preview renders the first 1-2 measures on the canvas
5. Open DevTools → Console — confirm no uncaught errors

- [ ] **Browser smoke test — exercise without score data**

6. Open an exercise whose `score` key is missing or `null`
7. Confirm "No score data." message appears instead of a broken canvas

- [ ] **Commit**

```bash
git add apps/teacher/templates/teacher/exercise_editor.html
git commit -m "feat: VexFlow score thumbnail on exercise editor (first 2 treble measures)"
```

---

## Known limitations

- VexFlow loaded from CDN; no offline/air-gapped support. Acceptable for teacher authoring workflow.
- Accidentals on `alter` values other than +1/-1 (double sharp, double flat) are not handled — the note renders without an accidental. Low frequency in practice.
- Beams and ties are not rendered. Notes display as unbeamed.
- Only the first voice of the treble staff is rendered. Multi-voice staves show only voice 0.
- If the CDN is unreachable, canvas stays blank and `showError` fires.

## Self-review checklist

- [ ] No `require()` call — VexFlow loaded via `<script src>` UMD
- [ ] Renders without error when `score_data` has ≥1 treble measure
- [ ] Renders "No score data." when score is null
- [ ] Renders "Preview unavailable." on fetch error (network / 404)
- [ ] Canvas does not overflow the sidebar card on small viewports
- [ ] No errors in DevTools Console for typical chorale exercise
