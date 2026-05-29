# Student Feedback System — Phased Implementation Plan

> **For agentic workers (Gemini Flash or other):** Implement task by task, in order. Each task is small. Do every step including the "run the test" steps. **Never invent student-facing strings** — every one is given verbatim here; copy it exactly (punctuation, em dashes, capitalization). Where a step references a property/function in a large *existing* file, the step tells you to `grep` for the real name first and adapt — those are the only non-exact identifiers; all *new* names and all strings are exact.

**Goal:** One feedback system for the whole app — a string **catalog** keyed by stable IDs, a **FeedbackService** routing any message to the right surface and logging it, consistent grade feedback for **every** exercise type, a single **instruction** surface, and a clean **audit** of legacy notifications. Delivered in phases, starting with a **mouse-click-input pilot**.

**Architecture:** A pure, Node-testable catalog (`feedback_catalog.js`, UMD) holds every reusable string plus a `resolveGradeFeedbackId(type, state, diagnostic)` resolver (most-specific → generic fallback). A RequireJS component (`feedback_service.js`) exposes `emit(id, opts)` and routes to five surfaces (global / inline / control / anchored / none), auto-fades, and logs analytics. The same funnel later carries universal grade feedback, instructions, and migrated legacy messages.

**Tech Stack:** Vanilla **ES5** (this codebase targets old browsers: `var`, `function`, string `+` — NO arrow functions / `let` / `const` / template literals in `lab/static/js/src/`), jQuery, lodash, RequireJS (`define`) for components, UMD wrapper for logic modules, plain Node scripts for unit tests.

**Spec:** [docs/superpowers/specs/2026-05-29-student-feedback-system-design.md](../specs/2026-05-29-student-feedback-system-design.md)

---

## Phased rollout

| Phase | Scope | Tasks | Ships on its own? |
|-------|-------|-------|-------------------|
| **1 — Click pilot** | Feedback core (catalog + service + wiring + CSS) **and** all click-input feedback: note cap, empty-Done, outside-column, Live/Click mode switch, no-MIDI device guidance | 1–12 | Yes — proves the funnel on the click surface |
| **2 — Universal grade feedback** | One `graded` hook drives per-type/per-skill feedback for every exercise type; harmonization gets a `wrong_inversion`/`wrong_quality` diagnostic | 13–17 | Yes |
| **3 — Instructions** | Every exercise type feeds the single `#instruction-panel`; defaults so none is blank | 18–21 | Yes |
| **4 — Legacy audit** | Migrate every remaining `NOTIFICATION`/`alert()` onto the funnel; prove none remain | 22–25 | Yes |

**Build Phase 1 first and stop there if needed** — it is the pilot and is independently valuable. Later phases reuse the same catalog + service with zero rework.

---

## Conventions (read once)

**1. ES5 only** in `lab/static/js/src/`.

**2. Logic modules** use this exact UMD wrapper (from `lab/static/js/src/components/input/click_note_logic.js`):

```js
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
  // body
  return { /* exports */ };
});
```

**3. Unit tests** are plain Node scripts (from `click_note_logic.test.js`), run with `node <path>`:

```js
/* Run: node <path> */
"use strict";
var mod = require("./feedback_catalog");
var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a); }
}
// assertEqual(...) ...
if (fail > 0) { console.error("\n" + fail + " test(s) failed"); process.exit(1); }
console.log("\nAll tests passed");
```

**4. Components** use RequireJS `define([...], function(){...})` with `X.prototype = new Component();` (see `notifications.js`).

**5. Only `feedback_service.js` may broadcast `EVENTS.BROADCAST.NOTIFICATION`.** Feature code calls `feedbackService.emit(id, opts)`. No `window.alert` for student messages.

**6. Strings live only in `feedback_catalog.js`.** Exception: per-exercise *authored* instruction/prompt text stays in exercise data (spec §5.1) — the catalog never duplicates authored content.

---

## Authoritative string catalog (copy exactly)

Implemented in Task 1 (system.* rows added in Task 22). `{n}` = param. `timeout=null` ⇒ sticky. `surface=none` ⇒ analytics only, no DOM.

### Click / soft constraints / mode / device (Phase 1)
| ID | category | surface | title | body | timeout |
|----|----------|---------|-------|------|---------|
| `harmonization.click.note_cap` | soft_constraint | control | `Chord is full.` | `Remove a note to add another.` | 1800 |
| `harmonization.click.outside_column` | soft_constraint | none | null | `Finish this chord first — the next one opens when you do.` | 2500 |
| `harmonization.click.empty_commit` | soft_constraint | control | null | `Add a note or two first.` | null |
| `input.mode.changed_live` | mode_state | inline | null | `Live input — play your keyboard or MIDI.` | 2000 |
| `input.mode.changed_click` | mode_state | inline | null | `Click input — tap the staff to place each note.` | 2000 |
| `input.device.none` | mode_state | inline | `No MIDI keyboard?` | `No problem — click notes onto the staff, use your computer keyboard, or play the on-screen keyboard.` | null |

### Grade feedback — universal fallback (data in Phase 1; wired in Phase 2)
| ID | category | surface | title | body | timeout |
|----|----------|---------|-------|------|---------|
| `exercise.grade.correct` | success | anchored | null | `Yes — that's right.` | 1500 |
| `exercise.grade.incorrect` | recoverable_mistake | anchored | null | `Not quite — give it another try.` | 4000 |
| `exercise.grade.partial` | mode_state | none | null | `Good so far — keep going.` | 2000 |
| `exercise.complete` | success | inline | null | `Beautifully done.` | 3000 |

### Grade feedback — per-type (override universal)
| ID | category | surface | title | body | timeout |
|----|----------|---------|-------|------|---------|
| `chorale.grade.incorrect` | recoverable_mistake | anchored | null | `That isn't the note in the score — listen, then try again.` | 4000 |
| `chorale.grade.correct` | success | anchored | null | `That's the one.` | 1500 |
| `identification.grade.incorrect` | recoverable_mistake | anchored | null | `Not the right name — take another look.` | 4000 |
| `identification.grade.correct` | success | anchored | null | `Exactly.` | 1500 |
| `harmonization.grade.incorrect` | recoverable_mistake | anchored | null | `Not quite — check the chord against the figure and try again.` | 4000 |
| `harmonization.grade.correct` | success | anchored | null | `Yes — that's it.` | 1500 |

### Grade feedback — per-skill (most specific)
| ID | category | surface | title | body | timeout |
|----|----------|---------|-------|------|---------|
| `harmonization.grade.incorrect.wrong_inversion` | recoverable_mistake | anchored | null | `Right chord — but the bass doesn't match the figure's inversion.` | 4500 |
| `harmonization.grade.incorrect.wrong_quality` | recoverable_mistake | anchored | null | `Close — check the chord quality (major, minor, diminished?).` | 4500 |
| `identification.grade.incorrect.wrong_octave` | recoverable_mistake | anchored | null | `Right letter — wrong octave.` | 4000 |

### System errors (added in Phase 4, Task 22)
| ID | category | surface | title | body | timeout |
|----|----------|---------|-------|------|---------|
| `system.exercise.load_failed` | blocking_error | global | `Couldn't load this exercise` | `Something went wrong loading it. Try refreshing the page.` | null |
| `system.history.load_failed` | blocking_error | global | `Couldn't load your history` | `We couldn't fetch this exercise's history just now. Try again in a moment.` | null |
| `system.corpus.load_failed` | blocking_error | global | `Couldn't load that piece` | `The music file couldn't be loaded. Try a different selection or refresh.` | null |
| `system.exercise.save_failed` | blocking_error | global | `Couldn't save` | `Your change wasn't saved. Check your connection and try again.` | null |

---

# PHASE 1 — Click-input pilot

Builds the core funnel and routes all click-input feedback through it. The note-cap hint already exists ad hoc (commit `5b5b1b6f`, `_showCapHint`); this phase makes its strings come from the catalog and adds the rest.

### Task 1: Catalog module (strings + grade-ID resolver)

**Files:**
- Create: `lab/static/js/src/config/feedback_catalog.js`
- Test: `lab/static/js/src/config/feedback_catalog.test.js`

- [ ] **Step 1: Write the failing test**

Create `lab/static/js/src/config/feedback_catalog.test.js`:

```js
/* Run: node lab/static/js/src/config/feedback_catalog.test.js */
"use strict";
var mod = require("./feedback_catalog");
var fail = 0;
function assertEqual(label, actual, expected) {
  var a = JSON.stringify(actual), e = JSON.stringify(expected);
  if (a === e) { console.log("ok - " + label); }
  else { fail += 1; console.error("FAIL - " + label + "\n  expected: " + e + "\n  actual:   " + a); }
}

assertEqual("get type", mod.get("harmonization.click.note_cap").category, "soft_constraint");
assertEqual("get unknown null", mod.get("nope.nope"), null);

assertEqual("fmt none", mod.format("Hi", null), "Hi");
assertEqual("fmt one", mod.format("Up to {n} notes", { n: 4 }), "Up to 4 notes");
assertEqual("fmt missing kept", mod.format("Hi {who}", {}), "Hi {who}");

var r = mod.render("exercise.grade.correct", null);
assertEqual("render surface", r.surface, "anchored");
assertEqual("render body", r.body, "Yes — that's right.");
assertEqual("render timeout", r.timeoutMs, 1500);
assertEqual("render unknown null", mod.render("nope", null), null);

assertEqual("resolve universal", mod.resolveGradeFeedbackId("unknownType", "incorrect", null), "exercise.grade.incorrect");
assertEqual("resolve per-type", mod.resolveGradeFeedbackId("chorale", "incorrect", null), "chorale.grade.incorrect");
assertEqual("resolve per-skill", mod.resolveGradeFeedbackId("harmonization", "incorrect", "wrong_inversion"), "harmonization.grade.incorrect.wrong_inversion");
assertEqual("resolve per-skill missing -> per-type", mod.resolveGradeFeedbackId("harmonization", "incorrect", "no_such"), "harmonization.grade.incorrect");
assertEqual("resolve per-type missing -> universal", mod.resolveGradeFeedbackId("identification", "partial", null), "exercise.grade.partial");
assertEqual("resolve unknown state null", mod.resolveGradeFeedbackId("chorale", "bogus", null), null);

var ev = mod.buildEvent("harmonization.grade.incorrect", { exerciseId: "EX1", unit: 9, complexity: 3, skillTags: ["V7"] }, 123);
assertEqual("ev id", ev.feedbackId, "harmonization.grade.incorrect");
assertEqual("ev category", ev.category, "recoverable_mistake");
assertEqual("ev unit", ev.unit, 9);
assertEqual("ev ts", ev.ts, 123);

if (fail > 0) { console.error("\n" + fail + " test(s) failed"); process.exit(1); }
console.log("\nAll tests passed");
```

- [ ] **Step 2: Run — expect failure**

Run: `node lab/static/js/src/config/feedback_catalog.test.js`
Expected: FAIL — `Cannot find module './feedback_catalog'`.

- [ ] **Step 3: Write the module**

Create `lab/static/js/src/config/feedback_catalog.js`:

```js
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

    // grade — per-skill (most specific)
    "harmonization.grade.incorrect.wrong_inversion": { category: "recoverable_mistake", surface: "anchored", title: null, body: "Right chord — but the bass doesn't match the figure's inversion.", detail: null, defaultTimeoutMs: 4500 },
    "harmonization.grade.incorrect.wrong_quality":   { category: "recoverable_mistake", surface: "anchored", title: null, body: "Close — check the chord quality (major, minor, diminished?).", detail: null, defaultTimeoutMs: 4500 },
    "identification.grade.incorrect.wrong_octave":   { category: "recoverable_mistake", surface: "anchored", title: null, body: "Right letter — wrong octave.", detail: null, defaultTimeoutMs: 4000 }

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
```

- [ ] **Step 4: Run — expect pass**

Run: `node lab/static/js/src/config/feedback_catalog.test.js`
Expected: PASS, "All tests passed", exit 0.

- [ ] **Step 5: Commit**

```bash
git add lab/static/js/src/config/feedback_catalog.js lab/static/js/src/config/feedback_catalog.test.js
git commit -m "feat(feedback): pure catalog with grade-id resolver + tests"
```

---

### Task 2: Add FEEDBACK broadcast id

**Files:** Modify: `lab/static/js/src/components/events.js`

- [ ] **Step 1:** In the `BROADCAST: { ... }` object, after `LABEL_SELECTED: "labelselected",` add:

```js
    FEEDBACK: "feedback",
```

- [ ] **Step 2:** Run: `grep -n 'FEEDBACK: "feedback"' lab/static/js/src/components/events.js` — expect one line.
- [ ] **Step 3:** Commit:

```bash
git add lab/static/js/src/components/events.js
git commit -m "feat(feedback): add FEEDBACK broadcast id"
```

---

### Task 3: FeedbackService component

**Files:** Create: `lab/static/js/src/components/feedback_service.js`

- [ ] **Step 1: Write the component**

Create `lab/static/js/src/components/feedback_service.js`:

```js
define([
  "lodash",
  "jquery",
  "app/components/events",
  "app/components/component",
  "app/config/feedback_catalog"
], function (_, $, EVENTS, Component, FeedbackCatalog) {
  "use strict";

  /**
   * FeedbackService — single funnel for student-facing feedback.
   * emit(id, opts): params, surface(override), anchorRect, controlEl, inlineEl, context
   */
  var FeedbackService = function (settings) {
    this.settings = _.extend({}, settings || {});
    this.exerciseContext = this.settings.exerciseContext || null;
    this._untilNextAttempt = [];
    _.bindAll(this, ["_onGraded"]);
  };
  FeedbackService.prototype = new Component();

  FeedbackService.prototype.initComponent = function () {
    this.$bubble = $('<div class="feedback-bubble" role="status" aria-live="polite"></div>').hide();
    $("body").append(this.$bubble);
    if (this.exerciseContext && typeof this.exerciseContext.bind === "function") {
      this.exerciseContext.bind("graded", this._onGraded);
    }
  };

  FeedbackService.prototype.renderTo = function () { /* surfaces self-position */ };

  FeedbackService.prototype.emit = function (id, opts) {
    opts = opts || {};
    var entry = FeedbackCatalog.render(id, opts.params || null);
    if (!entry) { if (window.console && console.warn) console.warn("[feedback] unknown id: " + id); return null; }
    this._logAnalytics(id, opts.context);
    var surface = opts.surface || entry.surface;
    if (surface === "global") this._routeGlobal(entry);
    else if (surface === "inline") this._routeInline(entry, opts);
    else if (surface === "control") this._routeControl(entry, opts);
    else if (surface === "anchored") this._routeAnchored(entry, opts);
    // "none" => analytics only
    return entry;
  };

  FeedbackService.prototype._routeGlobal = function (entry) {
    this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {
      type: entry.category === "blocking_error" ? "error"
          : entry.category === "recoverable_mistake" ? "warning" : "info",
      title: entry.title || entry.body,
      description: entry.detail || (entry.title ? entry.body : undefined)
    });
  };

  FeedbackService.prototype._routeInline = function (entry, opts) {
    var $el = opts.inlineEl ? $(opts.inlineEl) : null;
    if (!$el || !$el.length) return;
    var html = "";
    if (entry.title) html += "<strong>" + entry.title + "</strong> ";
    html += "<span>" + entry.body + "</span>";
    $el.html(html).addClass("is-visible");
    this._scheduleFade($el, entry.timeoutMs);
  };

  FeedbackService.prototype._routeControl = function (entry, opts) {
    var $el = opts.controlEl ? $(opts.controlEl) : null;
    if (!$el || !$el.length) return;
    $el.attr("title", (entry.title ? entry.title + " " : "") + entry.body);
    $el.addClass("feedback-control-flash");
    if ($el[0]) void $el[0].offsetWidth;
    window.setTimeout(function () { $el.removeClass("feedback-control-flash"); }, 600);
  };

  FeedbackService.prototype._routeAnchored = function (entry, opts) {
    var rect = opts.anchorRect;
    if (!rect) return;
    this.$bubble
      .text((entry.title ? entry.title + " " : "") + entry.body)
      .removeClass("feedback-bubble--mistake feedback-bubble--success")
      .addClass(entry.category === "recoverable_mistake" ? "feedback-bubble--mistake"
              : entry.category === "success" ? "feedback-bubble--success" : "")
      .css({ position: "absolute", top: rect.top + (rect.height || 0) + 6 + "px", left: rect.left + "px" })
      .stop(true, true).show();
    if (entry.category === "recoverable_mistake") this._untilNextAttempt.push(this.$bubble);
    this._scheduleFade(this.$bubble, entry.timeoutMs);
  };

  FeedbackService.prototype._scheduleFade = function ($el, timeoutMs) {
    if (timeoutMs == null) return;
    window.setTimeout(function () {
      $el.removeClass("is-visible");
      if ($el.is(".feedback-bubble")) $el.fadeOut(200);
    }, timeoutMs);
  };

  FeedbackService.prototype._onGraded = function () {
    for (var i = 0; i < this._untilNextAttempt.length; i++) {
      var $el = this._untilNextAttempt[i];
      $el.removeClass("is-visible");
      if ($el.is(".feedback-bubble")) $el.hide();
    }
    this._untilNextAttempt = [];
  };

  FeedbackService.prototype._logAnalytics = function (id, context) {
    var ev = FeedbackCatalog.buildEvent(id, context || this._contextFromExercise(), Date.now());
    this.broadcast(EVENTS.BROADCAST.FEEDBACK, ev);
    if (window.console && console.debug) console.debug("[feedback]", ev.feedbackId, ev.category);
  };

  FeedbackService.prototype._contextFromExercise = function () {
    var ctx = { exerciseId: null, unit: null, complexity: null, skillTags: [] };
    var ec = this.exerciseContext;
    // NOTE: ExerciseDefinition stores the parsed exercise as a PROPERTY (this.exercise),
    // not a method. Access it directly — do NOT call it.
    if (!ec || !ec.definition || !ec.definition.exercise) return ctx;
    var ex = ec.definition.exercise;
    if (!ex) return ctx;
    ctx.exerciseId = ex.exerciseId || ex.id || ex.exercise_id || null;
    ctx.complexity = typeof ex.complexity_score === "number" ? ex.complexity_score : null;
    ctx.skillTags = ex.skill_tags || [];
    for (var i = 0; i < ctx.skillTags.length; i++) {
      var m = /^unit:(\d+)$/.exec(ctx.skillTags[i]);
      if (m) { ctx.unit = parseInt(m[1], 10); break; }
    }
    return ctx;
  };

  return FeedbackService;
});
```

- [ ] **Step 2: Syntax check**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/feedback_service.js','utf8')); console.log('parse ok')"`
Expected: `parse ok`.

- [ ] **Step 3: Commit**

```bash
git add lab/static/js/src/components/feedback_service.js
git commit -m "feat(feedback): FeedbackService component (5 surfaces + analytics + graded-clear)"
```

---

### Task 4: Wire FeedbackService into the exercise app (first)

**Files:** Modify: `lab/static/js/src/components/app/exercise.js`

- [ ] **Step 1: Add dependencies** — in the top `define([...], function(...)`, after `"app/components/notifications",` add two lines:

```js
  "app/components/feedback_service",
  "app/config/feedback_catalog",
```

and in the function args, after `NotificationsComponent,` add:

```js
  FeedbackService,
  FeedbackCatalog,
```

(Keep the dependency array and the argument list aligned — insert at the same relative position in both.)

- [ ] **Step 2: Instantiate first** — in `getComponentMethods` (~`exercise.js:196`), make this the **first** function in the returned array (before the Notifications block):

```js
      function () {
        var c = new FeedbackService({ exerciseContext: this.models.exerciseContext });
        c.init(this);
        this.models.feedback = c;
        if (this.models.exerciseContext) {
          this.models.exerciseContext.feedback = c;
          this.models.exerciseContext._feedbackCatalog = FeedbackCatalog;
        }
        this.addComponent(c);
      },
```

> If `this.models.exerciseContext` is not assigned yet here, run `grep -n "this.models.exerciseContext\s*=" lab/static/js/src/components/app/exercise.js` and place this function just **after** the context is created but **before** Notifications/MIDI/ClickNote/NoteName. Requirement: `this.models.feedback` exists before anything that uses it.

- [ ] **Step 3: Syntax check**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/app/exercise.js','utf8')); console.log('parse ok')"`
Then: `grep -n "this.models.feedback = c" lab/static/js/src/components/app/exercise.js` — expect one line.

- [ ] **Step 4: Commit**

```bash
git add lab/static/js/src/components/app/exercise.js
git commit -m "feat(feedback): wire FeedbackService as models.feedback + context refs"
```

---

### Task 5: CSS for surfaces (both templates)

**Files:** Modify: `lab/static/css/harmony.css`; `apps/student/templates/student/player.html`

- [ ] **Step 1:** Append to `lab/static/css/harmony.css`:

```css
/* Feedback system surfaces */
.feedback-bubble { position: absolute; z-index: 1000; max-width: 280px; padding: 8px 12px; border-radius: 6px; background: #2b2f36; color: #fff; font-size: 13px; line-height: 1.35; box-shadow: 0 2px 10px rgba(0,0,0,.25); pointer-events: none; }
.feedback-bubble--mistake { background: #8a3324; }
.feedback-bubble--success { background: #2f6b3a; }
.feedback-control-flash { animation: feedback-shake .4s ease; }
@keyframes feedback-shake { 0%,100% { transform: translateX(0); } 25% { transform: translateX(-3px); } 75% { transform: translateX(3px); } }
.feedback-inline { font-size: 13px; color: #444; opacity: 0; transition: opacity .2s ease; }
.feedback-inline.is-visible { opacity: 1; }
.feedback-inline strong { color: #1f2937; }
```

- [ ] **Step 2:** Paste the same rules into the existing inline `<style>` block in `apps/student/templates/student/player.html` (the block already containing `.click-note-cap-hint`).
- [ ] **Step 3:** `grep -rn "feedback-bubble" lab/static/css/harmony.css apps/student/templates/student/player.html` — expect ≥1 match in each.
- [ ] **Step 4:** Commit:

```bash
git add lab/static/css/harmony.css apps/student/templates/student/player.html
git commit -m "feat(feedback): CSS for bubble/control/inline surfaces (both templates)"
```

---

### Task 6: Route the click-note cap hint through the catalog

**Files:** Modify: `lab/static/js/src/components/input/click_note.js`; `lab/static/js/src/components/app/exercise.js`

Keep the existing `_showCapHint` local DOM hint (shake + element) — only source its strings from the catalog and log the event.

- [ ] **Step 1: Pass feedback into the click component** — in `exercise.js`, find `new ClickNoteInputComponent({ ... })` (~`exercise.js:378`) and add `feedback: this.models.feedback,` to its settings.

- [ ] **Step 2: Read it in the constructor** — in `click_note.js` constructor (where `this.sheet = settings.sheet;` etc. are set), add (mirror the existing style):

```js
    this.feedback = settings.feedback || null;
```

- [ ] **Step 3: Add a feedback-context helper** — add to `click_note.js` prototype (e.g. after `_capRemaining`):

```js
    _feedbackContext: function () {
      var ec = this.exerciseContext;
      // ExerciseDefinition.exercise is a PROPERTY (parsed object), not a method.
      if (!ec || !ec.definition || !ec.definition.exercise) return null;
      var ex = ec.definition.exercise;
      if (!ex) return null;
      var tags = ex.skill_tags || [], unit = null;
      for (var i = 0; i < tags.length; i++) {
        var m = /^unit:(\d+)$/.exec(tags[i]);
        if (m) { unit = parseInt(m[1], 10); break; }
      }
      return { exerciseId: ex.exerciseId || ex.id || ex.exercise_id || null, unit: unit,
        complexity: typeof ex.complexity_score === "number" ? ex.complexity_score : null, skillTags: tags };
    },
```

- [ ] **Step 4: Source cap-hint strings from the catalog AND log every time**

`_showCapHint` reuses `this._capHintEl` after first creation, so the emit must NOT live inside the `if (!this._capHintEl)` creation branch (that would log only once). Emit at the **top** of `_showCapHint` on every call, capture the returned strings, and use them when first building the element.

At the very top of `_showCapHint`, right after `if (!this._paletteWrap) return;`, add:

```js
      var capEntry = this.feedback
        ? this.feedback.emit("harmonization.click.note_cap", { surface: "none", context: this._feedbackContext() })
        : null;
      var capTitle = capEntry ? capEntry.title : "Chord is full.";
      var capBody = capEntry ? capEntry.body : "Remove a note to add another.";
```

Then change the element-build line inside the `if (!this._capHintEl)` branch from the hardcoded:

```js
        this._capHintEl = $(
          '<div class="click-note-cap-hint" role="status" aria-live="polite">' +
          '<strong>Chord is full.</strong><span>Remove a note to add another.</span>' +
          '</div>'
        );
```

to use the captured strings:

```js
        this._capHintEl = $(
          '<div class="click-note-cap-hint" role="status" aria-live="polite">' +
          '<strong>' + capTitle + '</strong><span>' + capBody + '</span>' +
          '</div>'
        );
```

(`surface: "none"` ⇒ the service only logs analytics + returns the strings on every cap click; the existing local hint DOM does the showing/shaking.)

- [ ] **Step 5: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/input/click_note.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/components/input/click_note.js lab/static/js/src/components/app/exercise.js
git commit -m "refactor(feedback): source click cap-hint strings from catalog + log analytics"
```

---

### Task 7: Empty-Done soft constraint

**Files:** Modify: `lab/static/js/src/components/input/click_note.js`

- [ ] **Step 1: Store a reference to the Done button**

The Done button is currently a **local** variable in the element-builder (around `click_note.js:315`):

```js
      var doneBtn = $('<button type="button" class="input-mode-btn click-note-done" title="Grade the notes you clicked">Done</button>');
```

There is no stored reference or id. Right after that line, add:

```js
      this._doneButton = doneBtn;
```

(It has class `click-note-done`, so `.click-note-done` is the correct fallback selector — there is no `#click-note-done` id.)

- [ ] **Step 2: Find the commit handler** — `grep -n "doneBtn.on\|commit\|_commit\|BANK_NOTES\|onCommit\|snapshot" lab/static/js/src/components/input/click_note.js | head`. The Done button's click handler is wired at ~`click_note.js:316` (`doneBtn.on("click", ...)`); follow it to the function that builds the commit snapshot and grades.

- [ ] **Step 3: Guard the empty case** — at the very top of that commit function, before it builds a snapshot, add:

```js
      if (!this._pending || this._pending.length === 0) {
        if (this.feedback) {
          this.feedback.emit("harmonization.click.empty_commit", {
            controlEl: this._doneButton || ".click-note-done",
            context: this._feedbackContext()
          });
        }
        return;
      }
```

- [ ] **Step 4: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/input/click_note.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/components/input/click_note.js
git commit -m "feat(feedback): empty-commit soft constraint on click Done"
```

---

### Task 8: Outside-active-column soft constraint (analytics)

**Files:** Modify: `lab/static/js/src/components/input/click_note.js`

A click outside the active target column is already a no-op — but the rejection is **invisible** to the click handler. `ClickNoteLogic.pickColumn()` returns `null` when the hit column's `onset !== activeColumnOnset`, so `resolveClick()` returns `null`, and `_onCanvasClick` only sees `if (!resolved) return;` — identical to an off-staff/no-hit click. To distinguish "valid column, just not the active one" from "nothing there," resolve a **second time without the active-onset gate**. `surface: "none"` keeps it silent but measurable — this is how we learn if students are confused about column ordering.

- [ ] **Step 1: Add a gate-free resolve helper** — `_resolve` (at `click_note.js:148`) passes `activeColumnOnset: this._activeTargetOnset()`. Add a sibling that omits it, right after `_resolve`:

```js
    _resolveAny: function (e) {
      var layout = this._layout();
      if (!layout) return null;
      return ClickNoteLogic.resolveClick(this._eventPoint(e), layout, {
        key: this._key(),
        palette: this.palette
        // no activeColumnOnset -> resolves to whatever column the pixel lands in
      });
    },
```

- [ ] **Step 2: Detect outside-column on the no-resolve path** — in `_onCanvasClick`, change the existing early bail (`click_note.js:180`):

```js
      var resolved = this._resolve(e);
      if (!resolved) return;
```

to:

```js
      var resolved = this._resolve(e);
      if (!resolved) {
        // A valid-but-inactive column resolves only when the onset gate is removed.
        var any = this._resolveAny(e);
        if (any && any.column && any.column.onset !== this._activeTargetOnset() && this.feedback) {
          this.feedback.emit("harmonization.click.outside_column", { context: this._feedbackContext() });
        }
        return;
      }
```

> If the helper names differ (`_activeTargetOnset`, `_layout`, `_eventPoint`, `_key`), `grep -n "_activeTargetOnset\|_layout\|_eventPoint\|_key\b" lab/static/js/src/components/input/click_note.js` and mirror exactly what `_resolve` uses.

- [ ] **Step 3: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/input/click_note.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/components/input/click_note.js
git commit -m "feat(feedback): log outside-active-column clicks via gate-free re-resolve"
```

---

### Task 9: Live/Click source-mode switch feedback

**Files:** Modify: `lab/static/js/src/components/app/exercise.js`

The source-mode toggle (`$live`/`$click` buttons, ~`exercise.js:388+`) already exists. Emit an inline message on switch.

- [ ] **Step 1: Find the apply/switch function** — `grep -n "input-source-mode-toggle\|persistMode\|\\$live\|\\$click\|applyMode\|setMode" lab/static/js/src/components/app/exercise.js`.

- [ ] **Step 2: Add an inline region** — in the toggle-building block, after `$wrap` is inserted, add:

```js
        var $modeMsg = $('<div class="feedback-inline" role="status" aria-live="polite"></div>');
        $wrap.after($modeMsg);
```

- [ ] **Step 3: Emit on switch** — inside the function that applies a mode (where the `mode` variable is `"live"` or `"click"`), after persisting, add:

```js
          if (self.models.feedback) {
            self.models.feedback.emit(
              mode === "click" ? "input.mode.changed_click" : "input.mode.changed_live",
              { inlineEl: $modeMsg }
            );
          }
```

(`self` is defined at the top of the toggle block; `$modeMsg` is in the same closure.)

- [ ] **Step 4: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/app/exercise.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/components/app/exercise.js
git commit -m "feat(feedback): inline message on Live/Click source-mode switch"
```

---

### Task 10: No-MIDI device guidance (the click-input recommendation)

**Files:** Modify: `lab/static/js/src/components/midi.js`; `lab/static/js/src/components/app/exercise.js`; `lab/templates/exercise.html`; `apps/student/templates/student/player.html`

Replace the direct `NOTIFICATION` broadcasts in `midi.js` (no device + WebMIDI error) with an inline, non-global message that points students at click / computer keyboard / on-screen keyboard.

- [ ] **Step 1: Inject feedback into MIDI** — in `exercise.js`, where the MIDI component is created, add `feedback: this.models.feedback` to its settings (ensure FeedbackService is created earlier — Task 4). In `midi.js` constructor add `this.feedback = settings.feedback || null;`.

- [ ] **Step 2: Add the inline target** — in BOTH templates, just before the `#piano` region, add:

```html
<div id="midi-fallback-message" class="feedback-inline" role="status" aria-live="polite"></div>
```

- [ ] **Step 3: Replace the no-device broadcast** — `grep -n "inputCount === 0\|onWebMIDIError\|NOTIFICATION" lab/static/js/src/components/midi.js`. In the `if (inputCount === 0) {` block, replace `this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {...})` with:

```js
        if (this.feedback) { this.feedback.emit("input.device.none", { inlineEl: "#midi-fallback-message" }); }
```

- [ ] **Step 4: Replace `onWebMIDIError` broadcast** — replace its `this.broadcast(EVENTS.BROADCAST.NOTIFICATION, {...})` with:

```js
      if (this.feedback) { this.feedback.emit("input.device.none", { inlineEl: "#midi-fallback-message" }); }
```

Keep the existing `this.initListeners();` call in `onWebMIDIError`.

- [ ] **Step 5: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/midi.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/components/midi.js lab/static/js/src/components/app/exercise.js lab/templates/exercise.html apps/student/templates/student/player.html
git commit -m "refactor(feedback): no-MIDI guidance via inline funnel (recommend click input)"
```

---

### Task 11: Phase 1 documentation

**Files:** Create: `docs/feedback_catalog.md`; Modify: `CLAUDE.md`

- [ ] **Step 1: Create `docs/feedback_catalog.md`**

```markdown
# Feedback Catalog

Source of truth for reusable student-facing strings: `lab/static/js/src/config/feedback_catalog.js`.
This doc mirrors it for content review. Emit with
`feedbackService.emit("<id>", { params, anchorRect, controlEl, inlineEl, context })`.

Grade feedback resolves via `FeedbackCatalog.resolveGradeFeedbackId(type, state, diagnostic)`
(most specific → `<type>.grade.<state>` → `exercise.grade.<state>`).

Only `feedback_service.js` may broadcast `EVENTS.BROADCAST.NOTIFICATION`. No `window.alert`
for student messages. Per-exercise authored instructions/prompts live in exercise data, NOT here.

## Adding feedback for a new exercise type
1. Classify into one taxonomy category (spec §1).
2. Pick the lightest surface (spec §2): global / inline / control / anchored / none.
3. Grade feedback: the universal `exercise.grade.<state>` already covers you. Add
   `<type>.grade.<state>` only for type-specific wording, and
   `<type>.grade.<state>.<diagnostic>` only if your grader reports that diagnostic.
4. Add the catalog entry + a row below.
5. Emit via the service; never inline strings or alerts.

Feedback id convention: `<domain>.<context>.<event>`. IDs are STABLE (analytics primary key).

## Registry
| Feedback ID | Category | Surface | Copy | Persistence | Emitted by |
|-------------|----------|---------|------|-------------|-----------|
| harmonization.click.note_cap | soft_constraint | control | "Chord is full. Remove a note to add another." | 1800ms | click_note.js |
| harmonization.click.outside_column | soft_constraint | none | "Finish this chord first — the next one opens when you do." | 2500ms | click_note.js |
| harmonization.click.empty_commit | soft_constraint | control | "Add a note or two first." | sticky | click_note.js |
| input.mode.changed_live | mode_state | inline | "Live input — play your keyboard or MIDI." | 2000ms | exercise.js toggle |
| input.mode.changed_click | mode_state | inline | "Click input — tap the staff to place each note." | 2000ms | exercise.js toggle |
| input.device.none | mode_state | inline | "No MIDI keyboard? No problem — …" | sticky | midi.js |

(Phase 2 adds the grade.* rows; Phase 4 adds the system.* rows.)
```

- [ ] **Step 2: Add to `CLAUDE.md`** under "Documentation Requirements":

```markdown
**New or modified student-facing feedback** — do both:
1. Add/modify the entry in `lab/static/js/src/config/feedback_catalog.js`
2. Add/update the row in `docs/feedback_catalog.md`
Route all student-facing messages through `feedbackService.emit(id, opts)`. Never broadcast
`EVENTS.BROADCAST.NOTIFICATION` from feature code; never use `window.alert` for students.
```

- [ ] **Step 3: Commit**

```bash
git add docs/feedback_catalog.md CLAUDE.md
git commit -m "docs(feedback): catalog registry + CLAUDE.md requirement (phase 1)"
```

---

### Task 12: Phase 1 manual verification

**Files:** none.

- [ ] **Step 1:** `node lab/static/js/src/config/feedback_catalog.test.js` → "All tests passed".
- [ ] **Step 2:** In Chrome (DevTools console open), open a harmonization exercise and switch to Click input:
  - **note_cap:** fill a chord to its cap, click another pitch → local hint appears + palette shakes; console logs `[feedback] harmonization.click.note_cap soft_constraint`; strings read "Chord is full." / "Remove a note to add another."
  - **empty_commit:** with nothing selected press Done → no grade; Done flashes; logs `harmonization.click.empty_commit`.
  - **outside_column:** click a non-active column → nothing added; logs `harmonization.click.outside_column`.
  - **mode switch:** toggle Live↔Click → inline message appears; logs `input.mode.changed_*`.
- [ ] **Step 3:** Load in Safari/Firefox (or with no device) → `#midi-fallback-message` shows "No MIDI keyboard? …"; **no** global alert-icon panel for this.
- [ ] **Step 4:** `grep -rn "EVENTS.BROADCAST.NOTIFICATION" lab/static/js/src/components/midi.js` → no active (non-commented) match.
- [ ] **Step 5:** Commit any fixups:

```bash
git add -A && git commit -m "test(feedback): phase 1 verification fixups"
```

**END OF PHASE 1 — the pilot. Funnel + all click-input feedback live. Independently shippable.**

---

# PHASE 2 — Universal grade feedback (all exercise types)

The exercise context fires `this.trigger("graded")` after grading every type; `grade()` returns a state in `{correct, incorrect, partial, finished}` (STATE ~`exercise_context.js:130`, branches ~222/~868/~1142). One path turns each grade into a catalog emit via `resolveGradeFeedbackId`.

### Task 13: Expose feedback type + normalized grade state on the context

**Files:** Modify: `lab/static/js/src/models/exercise_context.js`

- [ ] **Step 1: Find type predicates** — `grep -n "isChorale\|isHarmonization\|isIdentification\|isPitchAnalysis" lab/static/js/src/models/exercise_definition.js | head`.

- [ ] **Step 2: Add a type-string helper** to the context prototype (adapt predicate names to Step 1):

```js
    _feedbackType: function () {
      var d = this.definition;
      if (!d) return "exercise";
      if (typeof d.isHarmonization === "function" && d.isHarmonization()) return "harmonization";
      if (typeof d.isChorale === "function" && d.isChorale()) return "chorale";
      if (typeof d.isIdentification === "function" && d.isIdentification()) return "identification";
      return "exercise";
    },
```

- [ ] **Step 3: Normalize + record the grade state** — add:

```js
    _setLastGradeState: function (stateRaw) {
      var s = String(stateRaw || "").toLowerCase();
      if (s === "finished") s = "incorrect"; // complete-with-errors = a mistake for feedback
      this._lastGradeState = (s === "correct" || s === "incorrect" || s === "partial") ? s : null;
    },
```

In each grading branch, where the local result/state is known (the `result:` value or `matchResult.state`), call `this._setLastGradeState(<that value>)` just before `this.trigger("graded")`. Also set `this._lastGradeDiagnostic = null;` there (overridden for harmonization in Task 16) so no stale diagnostic leaks.

- [ ] **Step 4: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/models/exercise_context.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat(feedback): expose feedback type + normalized grade state on context"
```

---

### Task 14: Universal graded → feedback emit

**Files:** Modify: `lab/static/js/src/models/exercise_context.js`

- [ ] **Step 1: Add the emit helper** (the catalog + feedback refs were set on the context in Task 4 Step 2):

```js
    _emitGradeFeedback: function () {
      if (!this.feedback || !this._lastGradeState) return;
      var FeedbackCatalog = this._feedbackCatalog;
      if (!FeedbackCatalog) return;
      var type = this._feedbackType();
      var diagnostic = this._lastGradeDiagnostic || null;
      var resolved = FeedbackCatalog.resolveGradeFeedbackId(type, this._lastGradeState, diagnostic);
      if (!resolved) return;
      this.feedback.emit(resolved, { anchorRect: this._activeColumnRect ? this._activeColumnRect() : null });
    },
```

- [ ] **Step 2: Add the anchor-rect helper**:

```js
    _activeColumnRect: function () {
      var sheet = this.settings && this.settings.sheet ? this.settings.sheet : null;
      if (!sheet || !sheet._staffLayout) return null;
      var layout = sheet._staffLayout;
      var onset = (typeof this._currentTargetOnset === "function") ? this._currentTargetOnset() : null;
      var cols = layout.columns || [], col = null;
      for (var i = 0; i < cols.length; i++) { if (onset != null && cols[i].onset === onset) { col = cols[i]; break; } }
      if (!col) col = cols.length ? cols[0] : null;
      if (!col) return null;
      var canvas = (sheet.el && sheet.el.find) ? sheet.el.find("canvas")[0] : null;
      var base = canvas ? canvas.getBoundingClientRect() : { top: 0, left: 0 };
      var sys = (layout.systems && layout.systems[col.systemIndex]) ? layout.systems[col.systemIndex] : { yBottom: 0 };
      return { top: base.top + window.scrollY + sys.yBottom, left: base.left + window.scrollX + col.centerX - 20, width: 40, height: 0 };
    },
```

> `this.settings.sheet`, `_currentTargetOnset`, `_staffLayout` names may differ — `grep -n "_staffLayout\|settings.sheet\|onset\|Pointer" lab/static/js/src/models/exercise_context.js lab/static/js/src/components/music/exercise_sheet.js` and adapt. Returning `null` is safe: the bubble no-ops, score coloring still conveys correctness.

- [ ] **Step 3: Call it** — immediately after each `this.trigger("graded");` that follows a real grade decision (same sites as Task 13 Step 3), add:

```js
      this._emitGradeFeedback();
```

- [ ] **Step 4: Syntax check + commit**

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/models/exercise_context.js','utf8')); console.log('parse ok')"`

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat(feedback): universal graded->feedback emit for all exercise types"
```

---

### Task 15: Exercise-complete feedback

**Files:** Modify: `lab/static/js/src/models/exercise_context.js`

- [ ] **Step 1:** `grep -n "completedExercise\|allDone\|isComplete\|finished" lab/static/js/src/models/exercise_context.js | head`.
- [ ] **Step 2:** Where full completion is detected (e.g. `graded.completedExercise = true` ~line 1177), add:

```js
        if (this.feedback) { this.feedback.emit("exercise.complete", { inlineEl: "#instruction-panel" }); }
```

- [ ] **Step 3:** Syntax check + commit:

```bash
git add lab/static/js/src/models/exercise_context.js
git commit -m "feat(feedback): emit exercise.complete on full completion"
```

---

### Task 16: Harmonization per-skill diagnostic (worked example)

**Files:** Modify: `lab/static/js/src/models/harmonization_grader_logic.js`; `lab/static/js/src/models/exercise_context.js`; Test: `lab/static/js/src/models/harmonization_grader_logic.test.js`

- [ ] **Step 1: Inspect the matcher** — `grep -n "function harmonizationMatch\|return\|inversion\|bass\|pc\|quality" lab/static/js/src/models/harmonization_grader_logic.js | head -40`. Find `harmonizationMatch(target, activeMidi)` and its mismatch return shape.

- [ ] **Step 2: Write the failing test** — add to `harmonization_grader_logic.test.js` (match its assert style):

```js
(function () {
  var target = { allowedPcs: [0,4,7], lockedVoices: { B: { pc: 0 } }, voiceCountPolicy: { min: 3, max: 4 } };
  var activeMidi = [64, 67, 72]; // valid triad pcs but lowest sounding pc = 4 (E), not required bass pc 0 (C)
  var res = mod.harmonizationMatch(target, activeMidi);
  assertEqual("wrong bass -> wrong_inversion", res.diagnostic, "wrong_inversion");
})();
```

> Adjust `target`/`activeMidi` to the real shape after Step 1. Contract: valid chord but lowest pitch-class ≠ required bass pc ⇒ `diagnostic: "wrong_inversion"`; wrong required-pc set ⇒ `diagnostic: "wrong_quality"`; else `diagnostic: null`. Accept/reject behavior unchanged.

- [ ] **Step 3: Run — expect fail**

Run: `node lab/static/js/src/models/harmonization_grader_logic.test.js`
Expected: FAIL (`res.diagnostic` undefined).

- [ ] **Step 4: Add the diagnostic** — in `harmonizationMatch`, populate a `diagnostic` field on the mismatch result per the contract above. Do not change accept logic.

- [ ] **Step 5: Run — expect pass**

Run: `node lab/static/js/src/models/harmonization_grader_logic.test.js`
Expected: PASS.

- [ ] **Step 6: Surface it to the context** — in `exercise_context.js`, in the harmonization grade branch where `harmonizationMatch(...)` is read, add (use the real result variable):

```js
        this._lastGradeDiagnostic = (matchRes && matchRes.diagnostic) ? matchRes.diagnostic : null;
```

- [ ] **Step 7: Commit**

```bash
git add lab/static/js/src/models/harmonization_grader_logic.js lab/static/js/src/models/harmonization_grader_logic.test.js lab/static/js/src/models/exercise_context.js
git commit -m "feat(feedback): harmonization wrong_inversion/wrong_quality diagnostics for per-skill copy"
```

---

### Task 17: Phase 2 verification + docs

**Files:** Modify: `docs/feedback_catalog.md`

- [ ] **Step 1:** `node lab/static/js/src/config/feedback_catalog.test.js` and `node lab/static/js/src/models/harmonization_grader_logic.test.js` → both pass.
- [ ] **Step 2:** In Chrome, for chorale, identification, and harmonization exercises: wrong answer → anchored bubble with per-type copy (`[feedback] <type>.grade.incorrect`); correct → success bubble; harmonization wrong-inversion → "Right chord — but the bass doesn't match the figure's inversion." (`...wrong_inversion`); completion → "Beautifully done."
- [ ] **Step 3:** Add the `*.grade.*` and `exercise.complete` rows to the `docs/feedback_catalog.md` registry table.
- [ ] **Step 4:** Commit:

```bash
git add docs/feedback_catalog.md
git commit -m "docs(feedback): register grade feedback ids (phase 2)"
```

**END OF PHASE 2 — every exercise type gets consistent grade feedback.**

---

# PHASE 3 — Instruction standardization

One `#instruction-panel` (in `exercise.html` + `player.html`, rendered by `exercise_sheet.js:1557`). Make every type feed it from authored data, with defaults so none is blank.

### Task 18: Audit current instruction rendering

**Files:** none (record findings for Task 19's commit body).

- [ ] **Step 1:** Read `exercise_sheet.js:1557` and around it: `grep -n "instruction\|prompt\|description" lab/static/js/src/components/music/exercise_sheet.js`. Note (a) the authored field read (`.description`/`.instructions`/UMTO `.source`), (b) which types reach it, (c) which render nothing.
- [ ] **Step 2:** `grep -rn "instruction-panel" lab/templates/exercise.html apps/student/templates/student/player.html` — confirm panel markup in both.
- [ ] **Step 3:** Write a 5–10 line summary (for Task 19's commit body).

---

### Task 19: One instruction renderer for all types

**Files:** Modify: `lab/static/js/src/components/music/exercise_sheet.js`

- [ ] **Step 1:** In the `exercise_sheet.js:1557` function, read a single authored value with precedence and render into the panel for **every** type (adapt field names to Task 18):

```js
      var ex = (this.exerciseContext && this.exerciseContext.definition)
        ? this.exerciseContext.definition.exercise : null; // PROPERTY, not a method
      var text = ex ? (ex.instructions || ex.description || ex.source || "") : "";
      var $panel = $("#instruction-panel .instruction-panel-content").first();
      if (!$panel.length) { $panel = $("#instruction-panel").first(); }
      if ($panel.length) {
        if (text) { $panel.html("<p>" + text + "</p>").show(); }
        else { $panel.empty(); }
      }
```

> If a type already renders richer column markup, keep that path and only ADD this fallback for types that show nothing. Do not regress existing rich instructions.

- [ ] **Step 2:** Syntax check:

Run: `node -e "new Function(require('fs').readFileSync('lab/static/js/src/components/music/exercise_sheet.js','utf8')); console.log('parse ok')"`

- [ ] **Step 3:** Commit (paste Task 18 summary into the body):

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(feedback): render authored instructions in #instruction-panel for all types"
```

---

### Task 20: Default instruction fallback

**Files:** Modify: `lab/static/js/src/components/music/exercise_sheet.js`

- [ ] **Step 1:** In the Task 19 render, when `text` is empty, fall back by type:

```js
      if (!text) {
        var DEFAULTS = {
          chorale: "Play each note as it appears in the score.",
          harmonization: "Build each chord under the figured bass, then press Done.",
          identification: "Click each ❓ and choose the correct answer.",
          exercise: "Follow the prompts to complete this exercise."
        };
        var t = (ex && ex.analysisType) ? "identification" : "exercise"; // refine with real predicates if reachable
        text = DEFAULTS[t] || DEFAULTS.exercise;
      }
```

(These defaults are reusable UI chrome, not per-exercise graded feedback, so they may live here; or add them to the catalog under `instructions.default.<type>` if you prefer one home.)

- [ ] **Step 2:** Syntax check + commit:

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(feedback): default instruction text so no exercise is blank"
```

---

### Task 21: Phase 3 verification

**Files:** none.

- [ ] **Step 1:** In Chrome, open one exercise of each type → each shows instruction text in `#instruction-panel` (authored or default); none blank; existing rich instructions unchanged.
- [ ] **Step 2:** Commit any fixups: `git add -A && git commit -m "test(feedback): phase 3 instruction fixups"`.

**END OF PHASE 3.**

---

# PHASE 4 — Legacy audit & migration

Move every active `NOTIFICATION`/`alert()` student-facing call onto the funnel. Inventory (verified): `exercise_form.js:174`; `exercise_sheet.js:1772`; `music_controls.js:563,568`; `play_sheet.js:253,256,270,280`. (`midi.js` done in Phase 1; `notifications.js` is the global surface — keep it.)

### Task 22: Add system.* error strings to the catalog

**Files:** Modify: `lab/static/js/src/config/feedback_catalog.js`; `lab/static/js/src/config/feedback_catalog.test.js`

- [ ] **Step 1:** Add a test assertion:

```js
assertEqual("system load surface", mod.get("system.exercise.load_failed").surface, "global");
```

- [ ] **Step 2: Run — expect fail.** `node lab/static/js/src/config/feedback_catalog.test.js` → FAIL.

- [ ] **Step 3:** In `feedback_catalog.js`, append these entries to `CATALOG` (note: the entry before them needs a trailing comma):

```js
    "system.exercise.load_failed": { category: "blocking_error", surface: "global", title: "Couldn't load this exercise", body: "Something went wrong loading it. Try refreshing the page.", detail: null, defaultTimeoutMs: null },
    "system.history.load_failed":  { category: "blocking_error", surface: "global", title: "Couldn't load your history", body: "We couldn't fetch this exercise's history just now. Try again in a moment.", detail: null, defaultTimeoutMs: null },
    "system.corpus.load_failed":   { category: "blocking_error", surface: "global", title: "Couldn't load that piece", body: "The music file couldn't be loaded. Try a different selection or refresh.", detail: null, defaultTimeoutMs: null },
    "system.exercise.save_failed": { category: "blocking_error", surface: "global", title: "Couldn't save", body: "Your change wasn't saved. Check your connection and try again.", detail: null, defaultTimeoutMs: null }
```

- [ ] **Step 4: Run — expect pass.** `node lab/static/js/src/config/feedback_catalog.test.js` → PASS.

- [ ] **Step 5:** Commit:

```bash
git add lab/static/js/src/config/feedback_catalog.js lab/static/js/src/config/feedback_catalog.test.js
git commit -m "feat(feedback): add system error catalog entries"
```

---

### Task 23: Migrate alert()/NOTIFICATION call sites

**Files:** Modify: `lab/static/js/src/components/music/exercise_sheet.js`; `lab/static/js/src/components/ui/music_controls.js`; `lab/static/js/src/components/music/play_sheet.js`; `lab/static/js/src/components/form/exercise_form.js`; `lab/static/js/src/components/app/exercise.js`

Each component must reach `feedback`. If it lacks a ref, inject `feedback:` into its settings at its instantiation site in `exercise.js` and add `this.feedback = settings.feedback || null;` in its constructor (mirror existing assignments).

- [ ] **Step 1: exercise_sheet.js:1772** — replace `alert("An error occurred while getting the exercise history.");` with:

```js
          if (this.feedback) { this.feedback.emit("system.history.load_failed"); }
          else if (window.console) { console.error("exercise history load failed"); }
```

Ensure the sheet gets `feedback` (settings + constructor as above).

- [ ] **Step 2: music_controls.js:563,568** — read what each `window.alert(...)` reports; replace each with `if (this.feedback) { this.feedback.emit("system.exercise.save_failed"); }` (use `system.exercise.load_failed` instead if it's a load failure). Inject `feedback` into `music_controls`.

- [ ] **Step 3: play_sheet.js:253,256,270,280** — replace each `alert(...)` with:

```js
              if (this.feedback) { this.feedback.emit("system.corpus.load_failed"); }
              else if (window.console) { console.error("corpus load failed"); }
```

> `play_sheet` belongs to the `play.js` sandbox. If `play.js` has no FeedbackService, either add one mirroring Task 4 (Notifications is already registered there) or leave the `console.error` fallback + a `// TODO: wire feedback in play sandbox` comment. The `if (this.feedback)` guard keeps it safe.

- [ ] **Step 4: exercise_form.js:174** — determine what its `NOTIFICATION` broadcast reports. If a save failure → `system.exercise.save_failed`. If a success → add a new catalog id `system.exercise.saved` (category `success`, surface `global`, title `Saved`, body `Your changes are saved.`, timeout `3000`) in Task 22's catalog block + test, then emit it. Replace the broadcast with `if (this.feedback) { this.feedback.emit("<chosen id>"); }`. Inject `feedback` into the form component.

- [ ] **Step 5:** Syntax-check each modified JS file; commit:

```bash
git add lab/static/js/src/components/music/exercise_sheet.js lab/static/js/src/components/ui/music_controls.js lab/static/js/src/components/music/play_sheet.js lab/static/js/src/components/form/exercise_form.js lab/static/js/src/components/app/exercise.js
git commit -m "refactor(feedback): migrate alert()/NOTIFICATION call sites onto funnel"
```

---

### Task 24: Prove no stray student-facing emits remain

**Files:** none.

- [ ] **Step 1:** Run:
```
grep -rn "EVENTS.BROADCAST.NOTIFICATION" lab/static/js/src | grep -v "feedback_service.js" | grep -v "notifications.js" | grep -v "//"
```
Expected: no output.

- [ ] **Step 2:** Run:
```
grep -rn "window.alert\|[^.]\balert(" lab/static/js/src | grep -v "//" | grep -v "\.test\.js"
```
Expected: no active student-facing `alert(` (any survivor must be inside an `if (this.feedback) {...} else { console... }` guard with a documented reason).

- [ ] **Step 3:** Migrate anything remaining; re-run; commit fixups:

```bash
git add -A && git commit -m "refactor(feedback): migrate remaining stray notifications"
```

---

### Task 25: Final docs + verification

**Files:** Modify: `docs/feedback_catalog.md`

- [ ] **Step 1:** Add the `system.*` (and `system.exercise.saved` if created) rows to the registry table.
- [ ] **Step 2:** Browser pass: trigger a load/save error → warm global notification (not a raw `alert`).
- [ ] **Step 3:** Commit:

```bash
git add docs/feedback_catalog.md
git commit -m "docs(feedback): register system error ids (phase 4)"
```

**END OF PHASE 4 — all legacy messaging on the funnel.**

---

## Future nice-to-haves (not scoped)

Low-priority polish, captured so it isn't lost. None blocks any phase.

- **Dim/disable the Live (MIDI) toggle when WebMIDI is unavailable.** In Safari/Firefox/iOS
  or with no device, the Live button still shows fully enabled. Not a bug — mode is always
  overridable by design (spec §"Source mode") and the student can switch — but dimming it
  (still clickable) would signal that Click is the recommended path. Driven by the existing
  `EVENTS.BROADCAST.MIDI_INPUTS_CHANGED` / `{inputCount}` signal.
- **`aria-live` mirror for anchored bubbles** so cat. 2/5 grade messages reach assistive
  tech (spec open question #3).
- **First-occurrence-only hint variants** for soft constraints (e.g. show the
  outside-column text once, silent thereafter) — currently `surface: "none"` logs silently.

---

## Self-review notes (for the implementer)

- **Verified facts (do not "fix" these):** `ExerciseDefinition.exercise` is a PROPERTY (parsed object), not a method — access `definition.exercise`, never `definition.exercise()`. The exercise id field is `exerciseId` (fall back to `id`/`exercise_id`). The Done button is a local `doneBtn` with class `click-note-done` (no id) — Task 7 stores `this._doneButton`. Outside-column rejection is swallowed inside `pickColumn`/`resolveClick` (returns null) — Task 8 re-resolves without the onset gate to detect it. The cap hint reuses `_capHintEl`, so Task 6 emits at the top of `_showCapHint`, not in the creation branch.
- **Non-exact identifiers** (grep first, adapt): type predicates (`isChorale`/`isHarmonization`/`isIdentification`), `_staffLayout`, `_currentTargetOnset`, `harmonizationMatch` result shape, the per-type instruction render path, the alert call sites, and each component's settings-assignment style. Every **string** and every **new** function/id name is exact.
- **Phases are independently shippable.** Stop after any phase. Phase 1 (the pilot) alone makes click-input feedback consistent and proves the funnel.
- **Generality is in the resolver, not in per-type wiring.** Phase 2's single `graded` path serves all types; per-type/per-skill copy is data in the catalog. A new exercise type needs zero new wiring — only optional catalog rows.
- **Fallbacks are load-bearing:** `resolveGradeFeedbackId` degrades to `exercise.grade.<state>`; `_activeColumnRect` → null makes the bubble no-op (score color still informs); `if (this.feedback)` guards keep every migration safe even where a sandbox isn't wired.
- **Do not delete** the existing `_showCapHint` local hint or existing rich instruction markup — feed them, don't replace.
- **Analytics is broadcast-only in v1** (`EVENTS.BROADCAST.FEEDBACK` + console). No backend.
