# Teacher Play Authoring — Phase B (In-Play Click-First UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the in-Play authoring surface that consumes the Phase A chordal-UMTO backend — serialize per-chord durations + explicit barlines + meter on Save, render the saved exercise at the teacher-placed barlines (free mode = no forced 4/4), add an analysis-slot model, a click-first micro-toolbar (duration / respell / token correction / barline place-remove), selection-scoped keyboard accelerators, Save→reviewed (no review bounce, feedback via `feedbackService`), and a post-save target-selector stub.

**Architecture:** The Play view (`play_sheet.js`) gains a per-chord **rhythm state** (palette quarter-lengths, default quarter) and a **barline-offset set**, plus a **selection** model that drives a micro-toolbar and selection-scoped shortcuts. `dataForSave` serializes that state (durations, offsets, `meter`, `barline_offsets`) plus **client-computed analysis slices** (below-zone harmonic labels from the `Analyze` widget, overlaid with teacher token overrides) so a single POST to `/exercises/add/` lands a `reviewed` exercise. `AddExerciseView` threads the new fields into the already-shipped `save_chordal_umto_exercise`. The **saved-exercise render** (`exercise_sheet.js _convertChordalUMTOToProcessedScore`) splits `score.measures` at `umto.metadata.barline_offsets` and tolerates `meter=null`. Pure, branch-heavy logic (serialization shape, barline split indices, metered-validity mirror, slot zone rules, note-entry-suspend predicate) is extracted into UMD `*_logic.js` modules and unit-tested with `node`; DOM / VexFlow / RequireJS wiring is verified manually and is already backstopped by the Phase A DB tests.

**Tech Stack:** RequireJS (AMD) front end, jQuery, lodash, VexFlow, the in-repo `Analyze`/`KeySignature` widgets, Django (`AddExerciseView`, `save_chordal_umto_exercise`). Front-end unit tests are plain Node scripts (no jest/package.json): a UMD `*_logic.js` module + a `*_logic.test.js` sibling with an inline `assertEqual` harness, run via `node <file>.test.js`.

**Spec:** `docs/superpowers/specs/2026-06-08-teacher-play-authoring-design.md` (Decisions a–e; "v1 cut" Phase A/B).
**Builds on:** `docs/superpowers/plans/2026-06-09-teacher-play-authoring-backend.md` (PR #93, merged) — its "Deferred to Plan 2" list is this plan's scope.

---

> **Environment & process (read first):**
> - **Worktree only.** All work + commits happen in this worktree (`.claude/worktrees/admiring-wiles-136502`). The repo ROOT has `master` checked out — never commit there.
> - **Python:** run `pyenv local 3.11.9` once in the worktree before any `manage.py`/`pytest` (the worktree `.python-version` is `system` with no python shim).
> - **Two Python test runners (unchanged from Phase A):**
>   - Pure-logic bare-function tests → `python -m pytest <file>`.
>   - DB-backed Django `TestCase` → `python manage.py test <module> --settings=harmony.settings.local --noinput` (pytest-django is NOT installed; never run DB `TestCase` under bare pytest).
> - **Front-end tests:** `node lab/static/js/src/.../<name>_logic.test.js`. There is no test bundler; each `*_logic.js` is a UMD module (`module.exports` in Node, `define` under RequireJS). Do **not** `require` a RequireJS component (`define([...])`) from Node — only `_logic.js` modules.
> - **PRs:** `gh pr create` fails (phantom "main" default). Create via `gh api repos/avnerdorman/HarmonyLab/pulls -f base=master -f head=<branch> -f title=... -f body=...`.
> - **Branch:** continue on the current worktree branch (`claude/admiring-wiles-136502`).

---

## Phasing (sequence; each phase is independently shippable/testable)

- **B0 — Save = reviewed, no bounce.** Thread `barline_offsets`/`meter`/analysis through `AddExerciseView`; collapse the generated-review bounce in `music_controls.js`; route Save feedback through `feedbackService`; add catalog entries. (Tasks 1–3)
- **B1 — Durations, barlines, render.** Per-chord rhythm + barline state + `dataForSave` serialization; metered-validity mirror that blocks Save; barline-aware saved-exercise render + `meter=null` + dotted palette. (Tasks 4–8)
- **B2 — Analysis-slot model.** `analysis_slots.js` config + zone rules; consume in `stave_notater.js`/`exercise_sheet.js`; persist `analyzeConfig {above, below}`; serialize below-zone slices on Save. (Tasks 9–11)
- **B3 — Click-first authoring + shortcuts.** Selection + micro-toolbar (duration palette, respell, token correction with figure picker), click-between-chords barline place/remove + meter auto-suggest, selection-scoped accelerators + suspend note-entry on text focus. (Tasks 12–15)
- **B4 — Post-save target selector stub + docs.** Emit `{ exerciseId, targetIntent, sectionId?, autoTranspose }`, library default wired; docs. (Tasks 16–17)

---

## File Structure

**New files:**
- `lab/static/js/src/components/music/play_save_logic.js` (+ `.test.js`) — pure serialization: build `chord[]` (offset/duration/visible/hidden/spelling), `barline_offsets`, and analysis-slice list from authoring state. UMD.
- `lab/static/js/src/utils/chordal_barlines_logic.js` (+ `.test.js`) — pure: cumulative offsets from durations, barline auto-suggest from meter, measure split-index computation, and a JS mirror of the metered-validity check. UMD.
- `lab/static/js/src/config/analysis_slots.js` (+ `analysis_slots.test.js`) — analysis-slot type descriptors + zone rules (single source of truth). UMD.
- `lab/static/js/src/components/input/note_entry_gate_logic.js` (+ `.test.js`) — pure predicate: should note-entry be suspended given the active element / selection. UMD.
- `lab/static/js/src/components/music/play_authoring_toolbar.js` — micro-toolbar + barline-gap + selection rendering (RequireJS component; manual-verify).
- `lab/static/js/src/components/ui/target_selector.js` — post-save target-selector stub (RequireJS component; manual-verify).

**Modified files:**
- `lab/static/js/src/components/music/play_sheet.js` — rhythm/barline/selection state; `dataForSave` via `play_save_logic`; wire toolbar; emit save-intent.
- `lab/static/js/src/components/ui/music_controls.js` — `onClickSaveJSON`: meter/barlines/analysis in payload; Save→reviewed; delete bounce; `feedbackService`; block on invalid metered bars; trigger target selector.
- `lab/static/js/src/components/music/exercise_sheet.js` — `_convertChordalUMTOToProcessedScore`: barline-aware split, `meter=null`, dotted `DUR_TYPE`; consume `analysis_slots`.
- `lab/static/js/src/components/music/stave_notater.js` — consume `analysis_slots` for zone placement; expose `analyzeConfig {above, below}`.
- `lab/static/js/src/components/input/shortcuts.js` — `isEnabled` suspends on text focus; selection-scoped accelerators.
- `lab/static/js/src/config/feedback_catalog.js` + `docs/feedback_catalog.md` — new Play authoring messages.
- `lab/views.py` (`AddExerciseView.post`) — accept `barline_offsets`, `analysisSlices`; pass to `save_chordal_umto_exercise`; return `{ id, reviewStatus }` (reviewed).
- `docs/exercise_types.md` — note the Play-authored chordal `PLAYBACK`/reviewed flow.

---

# PHASE B0 — Save = reviewed, no bounce

## Task 1: `AddExerciseView` threads barlines + analysis; returns reviewed

**Files:**
- Modify: `lab/views.py:904` (`AddExerciseView.post`)
- Test: `lab/tests/test_add_exercise_view_db.py` (NEW — DB-backed `TestCase`)

The backend `save_chordal_umto_exercise` already accepts `barline_offsets` and `analysis` (PR #93). The view ignores both and synthesizes a `reviewUrl`. Thread them through and return the real review status.

- [x] **Step 1: Write the failing test**

Create `lab/tests/test_add_exercise_view_db.py`:

```python
import json
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class AddExerciseViewChordalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="add@example.com", password="x")
        self.client.force_login(self.user)

    def _post(self, payload):
        return self.client.post(
            "/exercises/add/",
            data={"data": json.dumps(payload)},
        )

    def _chords(self):
        # Two 4/4 bars of quarters, with explicit per-chord duration.
        return [
            {"offset": float(i), "duration": 1.0, "visible": [60, 64, 67], "hidden": []}
            for i in range(8)
        ]

    def test_free_mode_no_meter_saves_reviewed_none_when_no_analysis(self):
        payload = {"chord": self._chords(), "key": "C", "staffDistribution": "keyboard"}
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertIn("id", body)
        self.assertEqual(body["reviewStatus"], "none")

    def test_metered_with_barlines_and_analysis_saves_reviewed(self):
        payload = {
            "chord": self._chords(),
            "key": "C",
            "meter": "4/4",
            "staffDistribution": "keyboard",
            "barline_offsets": [4.0],
            "analysisSlices": [
                {"offset": 0.0, "content": {"roman_numeral": "I"}, "is_target": True, "unit_tags": []}
            ],
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["reviewStatus"], "reviewed")

    def test_invalid_metered_bars_rejected(self):
        payload = {
            "chord": [{"offset": float(i), "duration": 1.0, "visible": [60], "hidden": []} for i in range(3)],
            "key": "C",
            "meter": "4/4",
            "staffDistribution": "keyboard",
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 400)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python manage.py test lab.tests.test_add_exercise_view_db --settings=harmony.settings.local --noinput -v 2`
Expected: FAIL — `barline_offsets`/`analysisSlices` ignored; metered test #2 returns `generated` (auto-gen) not `reviewed`; no review of bars (status 201 not 400).

- [x] **Step 3: Update `AddExerciseView.post`**

In `lab/views.py`, replace the body from `key = payload.get("key", "C")` through the final `return JsonResponse(...)` (currently lines ~924-955) with:

```python
        key = payload.get("key", "C")
        meter = payload.get("meter")  # None = free/open mode (no metric validation)
        clef = payload.get("clef", "keyboard")
        staff_distribution = payload.get("staffDistribution", "keyboard")
        barline_offsets = payload.get("barline_offsets") or []
        analysis_slices = payload.get("analysisSlices")  # None => backend may auto-generate

        try:
            exercise = save_chordal_umto_exercise(
                description="Play view chordal exercise",
                author=request.user,
                chords=chords,
                key=key,
                meter=meter,
                clef=clef,
                staff_distribution=staff_distribution,
                is_public=False,
                barline_offsets=barline_offsets,
                analysis=analysis_slices,
            )
        except (NonUMTOExerciseError, ValueError, KeyError):
            return HttpResponse(status=400)

        review_status = (
            (exercise.data or {})
            .get("score", {})
            .get("umto", {})
            .get("metadata", {})
            .get("analysis_review_status", "none")
        )
        return JsonResponse(status=201, data={
            "id": exercise.id,
            "reviewStatus": review_status,
        })
```

(The `reviewUrl` field is intentionally dropped — the Play path no longer bounces to the workbench. The `generated → workbench` review path survives only for bulk MusicXML imports, which never POST here.)

- [x] **Step 4: Run test to verify it passes**

Run: `python manage.py test lab.tests.test_add_exercise_view_db --settings=harmony.settings.local --noinput -v 2`
Expected: PASS (3 tests).

- [x] **Step 5: Commit**

```bash
git add lab/views.py lab/tests/test_add_exercise_view_db.py
git commit -m "feat(play-save): AddExerciseView threads barlines+analysis, returns reviewed status"
```

---

## Task 2: Feedback catalog entries for Play authoring

**Files:**
- Modify: `lab/static/js/src/config/feedback_catalog.js`
- Modify: `lab/static/js/src/config/feedback_catalog.test.js`
- Modify: `docs/feedback_catalog.md`

Add the messages the Save flow (Task 3) and authoring (Phase B3) emit. Routing CLAUDE.md rule: student-facing feedback goes through `feedbackService.emit(id, opts)` + a catalog entry + a docs row.

- [x] **Step 1: Add a failing assertion**

In `lab/static/js/src/config/feedback_catalog.test.js`, append before the final `process.exit` block (match the file's existing `assertEqual`/`assert` harness — read the top of the file first to reuse its helper names):

```javascript
// --- Play authoring feedback ------------------------------------------------
assert("play.save.success entry exists", !!mod.render("play.save.success", null));
assert("play.save.invalid_meter entry exists", !!mod.render("play.save.invalid_meter", { bar: 3, beats: 5, expected: 4 }));
assertEqual("play.save.invalid_meter interpolates the bar",
  mod.render("play.save.invalid_meter", { bar: 3, beats: 5, expected: 4 }).body.indexOf("3") !== -1, true);
```

- [x] **Step 2: Run to verify it fails**

Run: `node lab/static/js/src/config/feedback_catalog.test.js`
Expected: FAIL — unknown ids `play.save.success` / `play.save.invalid_meter`.

- [x] **Step 3: Add the catalog entries**

In `lab/static/js/src/config/feedback_catalog.js`, add to the `CATALOG` map (placement: alongside the other namespaced groups). Confirm the param interpolation syntax by reading an existing entry that uses `params` (e.g. search the file for `<%` or `{` token usage) and match it exactly. Using the catalog's existing `{bar}`-style placeholder convention:

```javascript
    "play.save.success":       { category: "success",        surface: "inline",  title: "Saved.", body: "Your exercise is saved and reviewed.", detail: null, defaultTimeoutMs: 2500 },
    "play.save.invalid_meter": { category: "blocking_error", surface: "inline",  title: "Can’t save yet.", body: "Bar {bar} has {beats} beats, expected {expected}. Fix a duration or move a barline.", detail: null, defaultTimeoutMs: null },
    "play.save.empty":         { category: "blocking_error", surface: "inline",  title: "Nothing to save.", body: "Bank at least two chords first.", detail: null, defaultTimeoutMs: 2500 },
```

> If the catalog's `render(id, params)` uses a different placeholder delimiter (e.g. `<%= bar %>`), use that delimiter instead — match the existing entries verbatim. The test in Step 1 asserts interpolation, so it will catch a delimiter mismatch.

- [x] **Step 4: Run to verify it passes**

Run: `node lab/static/js/src/config/feedback_catalog.test.js`
Expected: PASS.

- [x] **Step 5: Update the docs catalog**

In `docs/feedback_catalog.md`, add rows (match the existing table columns):

```markdown
| `play.save.success` | success | inline | Confirms a Play exercise saved as reviewed. |
| `play.save.invalid_meter` | blocking_error | inline | Metered Save blocked: a bar does not sum to the meter. |
| `play.save.empty` | blocking_error | inline | Save blocked: fewer than two banked chords. |
```

- [x] **Step 6: Commit**

```bash
git add lab/static/js/src/config/feedback_catalog.js lab/static/js/src/config/feedback_catalog.test.js docs/feedback_catalog.md
git commit -m "feat(feedback): Play authoring save messages (success/invalid_meter/empty)"
```

---

## Task 3: `music_controls` Save → reviewed, no bounce, feedbackService

**Files:**
- Modify: `lab/static/js/src/components/ui/music_controls.js` (`onClickSaveJSON`, ~425-606; bounce ~560-580)
- Manual verification (RequireJS component; no node unit test)

Collapse the generated/reviewUrl bounce (`window.alert` + `window.open(reviewUrl)`), route feedback through `feedbackService`, and hand the saved `{ id }` to the post-save target selector (wired in Task 16; until then, log + emit success).

> **feedbackService access:** `MusicControlsComponent` is constructed with `settings`. The Play bootstrap must pass a `feedback` instance. Check where `MusicControlsComponent` is instantiated (grep `new MusicControlsComponent` under `lab/static/js/src/`) and confirm a `feedback` service is available there; if not, construct/pass one (the `FeedbackService` from `app/components/feedback_service`, `exerciseContext` optional/null for Play). Store it as `this.feedback = settings.feedback || null` in the constructor.

- [x] **Step 1: Add feedback to the constructor**

In `music_controls.js`, in `MusicControlsComponent` (the `function (settings)` body, ~67-90), after `this.midiDevice = settings.midiDevice;` add:

```javascript
    this.feedback = settings.feedback || null;
```

- [x] **Step 2: Replace the upload success branch**

In `onClickSaveJSON`, replace the entire `success:` callback of the upload `$.ajax` (currently the `function (data) { ... }` containing `reviewUrl`/`needsReview`/`window.alert`/`window.open`, ~560-580) with:

```javascript
          success: (data) => {
            const exerciseID = data.id;
            if (this.feedback) {
              this.feedback.emit("play.save.success", { inlineEl: "#save-feedback" });
            }
            this.broadcast(EVENTS.BROADCAST.PLAY_SAVED, {
              exerciseId: exerciseID,
              reviewStatus: data.reviewStatus,
            });
          },
```

And replace the `error:` callback with one that surfaces a blocking-error code on HTTP 400 (invalid metered bars rejected server-side):

```javascript
          error: (xhr) => {
            console.log(xhr);
            if (this.feedback) {
              this.feedback.emit("play.save.invalid_meter", {
                inlineEl: "#save-feedback",
                params: { bar: "?", beats: "?", expected: "?" },
              });
            }
          },
```

> The precise bar/beats come from the **client-side** metered-validity pre-check (Task 8), which blocks Save before POST and emits the specific message. The server 400 is the backstop; "?" placeholders are only hit if the client check is bypassed (e.g. an agent path).

- [x] **Step 3: Add the `PLAY_SAVED` event constant**

Confirm the events module (grep `BROADCAST` in `lab/static/js/src/components/events.js`). Add `PLAY_SAVED: "play:saved"` to the `BROADCAST` map (match the file's existing key style).

- [x] **Step 4: Add the inline feedback anchor**

The Play template needs `<div id="save-feedback" class="feedback-inline" aria-live="polite"></div>` near the Save controls. Grep for the Play template (e.g. `grep -rn "js-btn-upload-json" lab/templates lab/static`) and add the anchor adjacent to the upload button. (Manual; record the file path touched in the commit.)

- [x] **Step 5: Manual verification**

Run the app (`/run` or the project's dev server), open `/`, bank ≥2 chords, click the Save (upload) control. Verify:
- No `window.alert`, no new tab to the workbench.
- An inline "Saved." message appears.
- Network tab: POST `/exercises/add/` returns `201 { id, reviewStatus: "none" }` (free mode, no analysis yet).

Capture a screenshot for the PR.

- [x] **Step 6: Commit**

```bash
git add lab/static/js/src/components/ui/music_controls.js lab/static/js/src/components/events.js <play_template_touched>
git commit -m "feat(play-save): Save->reviewed, drop generated-review bounce, route via feedbackService"
```

---

# PHASE B1 — Durations, barlines, render

## Task 4: `chordal_barlines_logic.js` — offsets, auto-suggest, split indices, validity mirror

**Files:**
- Create: `lab/static/js/src/utils/chordal_barlines_logic.js`
- Test: `lab/static/js/src/utils/chordal_barlines_logic.test.js`

One UMD module of pure functions reused by serialization (Task 6), render split (Task 7), the Save validity gate (Task 8), and barline auto-suggest (Task 14). It mirrors the backend `validate_chordal_rhythm` (`apps/exercises/umto_factory.py:89`) and `_chordal_to_measures` split contract so the UI never offers a Save the server will reject.

- [x] **Step 1: Write the failing test**

Create `lab/static/js/src/utils/chordal_barlines_logic.test.js`:

```javascript
"use strict";
var mod = require("./chordal_barlines_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}
function assertThrows(name, fn) {
  try { fn(); fail++; console.error("FAIL - " + name + " (no throw)"); }
  catch (e) { pass++; console.log("ok - " + name); }
}

// PALETTE
assertEqual("palette is the eight authoring values",
  mod.PALETTE, [4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25]);
assertEqual("isPaletteDuration accepts 1.5", mod.isPaletteDuration(1.5), true);
assertEqual("isPaletteDuration rejects 1.25", mod.isPaletteDuration(1.25), false);

// CUMULATIVE OFFSETS
assertEqual("offsetsFromDurations cumulative",
  mod.offsetsFromDurations([1, 1, 2, 0.5]), [0, 1, 2, 4]);

// AUTO-SUGGEST BARLINES (4/4, eight quarters -> barline at 4.0; excludes 0 and end=8)
assertEqual("suggestBarlines 4/4 eight quarters",
  mod.suggestBarlines([0,1,2,3,4,5,6,7], [1,1,1,1,1,1,1,1], "4/4"), [4]);
assertEqual("suggestBarlines free mode (null meter) -> none",
  mod.suggestBarlines([0,1,2], [1,1,1], null), []);

// SPLIT INDICES: item counts per measure, given chord onsets + barline offsets
assertEqual("splitCounts 6 quarters, barlines [2,4] -> [2,2,2]",
  mod.measureItemCounts([0,1,2,3,4,5], [2,4]), [2, 2, 2]);
assertEqual("splitCounts free single measure",
  mod.measureItemCounts([0,1,1.5], []), [3]);

// VALIDITY MIRROR (returns {ok, error?} — never throws; UI gates on .ok)
assertEqual("validity free mode ok",
  mod.checkRhythm([0,1,1.75], [1,0.75,0.25], null, []).ok, true);
assertEqual("validity free rejects off-palette",
  mod.checkRhythm([0], [1.25], null, []).ok, false);
assertEqual("validity metered exact tiling ok",
  mod.checkRhythm([0,1,2,3,4,5,6,7], [1,1,1,1,1,1,1,1], "4/4", [4]).ok, true);
var short = mod.checkRhythm([0,1,2], [1,1,1], "4/4", []);
assertEqual("validity metered short bar not ok", short.ok, false);
assertEqual("validity metered short bar names the bar",
  /bar/i.test(short.error), true);
assertEqual("validity barline off-onset not ok",
  mod.checkRhythm([0,1,2,3], [1,1,1,1], "4/4", [2.5]).ok, false);
assertEqual("validity overlap not ok (free)",
  mod.checkRhythm([0,1], [4,1], null, []).ok, false);

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll chordal_barlines_logic assertions passed (" + pass + ")."); }
```

- [x] **Step 2: Run to verify it fails**

Run: `node lab/static/js/src/utils/chordal_barlines_logic.test.js`
Expected: FAIL — `Cannot find module './chordal_barlines_logic'`.

- [x] **Step 3: Implement the module**

Create `lab/static/js/src/utils/chordal_barlines_logic.js`:

```javascript
/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else if (typeof define === "function" && define.amd) { define([], factory); }
  else { root.ChordalBarlinesLogic = factory(); }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var EPS = 1e-6;
  var PALETTE = [4, 3, 2, 1.5, 1, 0.75, 0.5, 0.25];
  var PALETTE_SET = {}; PALETTE.forEach(function (v) { PALETTE_SET[v] = true; });

  function r6(x) { return Math.round(Number(x) * 1e6) / 1e6; }
  function isPaletteDuration(ql) { return PALETTE_SET[r6(ql)] === true; }

  function meterQuarterLength(meter) {
    if (!meter) return 0;
    var parts = String(meter).split("/");
    var num = parseInt(parts[0], 10) || 4;
    var den = parseInt(parts[1], 10) || 4;
    return num * (4 / den);
  }

  function offsetsFromDurations(durations) {
    var offs = []; var cur = 0;
    for (var i = 0; i < durations.length; i++) { offs.push(r6(cur)); cur = r6(cur + Number(durations[i])); }
    return offs;
  }

  // Auto-suggest barlines at meter boundaries that coincide with a chord onset.
  function suggestBarlines(offsets, durations, meter) {
    if (!meter) return [];
    var barLen = meterQuarterLength(meter);
    var total = offsets.length ? r6(offsets[offsets.length - 1] + Number(durations[durations.length - 1])) : 0;
    var onsetSet = {}; offsets.forEach(function (o) { onsetSet[r6(o)] = true; });
    var out = []; var b = r6(barLen);
    while (b < total - EPS) { if (onsetSet[b]) out.push(b); b = r6(b + barLen); }
    return out;
  }

  // Item count per measure given chord onsets and barline offsets (split contract).
  function measureItemCounts(offsets, barlineOffsets) {
    var splits = (barlineOffsets || []).map(r6).sort(function (a, b) { return a - b; });
    if (!splits.length) return offsets.length ? [offsets.length] : [];
    var counts = []; var si = 0; var count = 0;
    for (var i = 0; i < offsets.length; i++) {
      while (si < splits.length && r6(offsets[i]) >= splits[si] - EPS) {
        counts.push(count); count = 0; si++;
      }
      count++;
    }
    counts.push(count);
    return counts;
  }

  // Mirror of backend validate_chordal_rhythm. Returns {ok:bool, error?:string}.
  function checkRhythm(offsets, durations, meter, barlineOffsets) {
    var i;
    for (i = 0; i < durations.length; i++) {
      if (!isPaletteDuration(durations[i])) {
        return { ok: false, error: "Duration " + durations[i] + " is not in the palette." };
      }
    }
    if (!offsets.length) return { ok: true };

    // Non-overlap / monotonic.
    var cursor = null;
    var onsetSet = {};
    for (i = 0; i < offsets.length; i++) {
      var off = r6(offsets[i]);
      onsetSet[off] = true;
      if (cursor !== null && off < cursor - EPS) {
        return { ok: false, error: "Chord at " + off + " overlaps the previous chord." };
      }
      cursor = r6(off + Number(durations[i]));
    }
    var bars = barlineOffsets || [];
    for (i = 0; i < bars.length; i++) {
      if (onsetSet[r6(bars[i])] !== true) {
        return { ok: false, error: "Barline at " + bars[i] + " is not on a chord onset." };
      }
    }
    if (!meter) return { ok: true };

    var barLen = meterQuarterLength(meter);
    var total = r6(offsets[offsets.length - 1] + Number(durations[durations.length - 1]));
    var bounds = [0].concat(bars.map(r6).sort(function (a, b) { return a - b; })).concat([total]);
    for (var bi = 0; bi < bounds.length - 1; bi++) {
      var start = bounds[bi], end = bounds[bi + 1];
      var span = r6(end - start);
      if (Math.abs(span - barLen) > EPS) {
        return { ok: false, error: "Bar " + (bi + 1) + " has " + span + " beats, expected " + barLen + "." };
      }
      var c = start;
      for (i = 0; i < offsets.length; i++) {
        var o = r6(offsets[i]);
        if (o >= start - EPS && o < end - EPS) {
          if (Math.abs(o - c) > EPS) {
            return { ok: false, error: "Bar " + (bi + 1) + " has a gap/overlap at " + o + "." };
          }
          c = r6(c + Number(durations[i]));
        }
      }
      if (Math.abs(c - end) > EPS) {
        return { ok: false, error: "Bar " + (bi + 1) + " has " + r6(c - start) + " beats, expected " + barLen + "." };
      }
    }
    return { ok: true };
  }

  return {
    PALETTE: PALETTE,
    isPaletteDuration: isPaletteDuration,
    meterQuarterLength: meterQuarterLength,
    offsetsFromDurations: offsetsFromDurations,
    suggestBarlines: suggestBarlines,
    measureItemCounts: measureItemCounts,
    checkRhythm: checkRhythm,
  };
});
```

- [x] **Step 4: Run to verify it passes**

Run: `node lab/static/js/src/utils/chordal_barlines_logic.test.js`
Expected: PASS (all assertions).

- [x] **Step 5: Cross-check against the backend validator**

The JS `checkRhythm` must agree with `apps/exercises/umto_factory.py:validate_chordal_rhythm` on the same cases. Eyeball the bar-message text (the JS uses "has N beats, expected M" matching the spec AC4 example "Bar 3 has 5 beats, expected 4"). No code change expected; if a case disagrees, fix the JS to match the Python (the Python is the contract).

- [x] **Step 6: Commit**

```bash
git add lab/static/js/src/utils/chordal_barlines_logic.js lab/static/js/src/utils/chordal_barlines_logic.test.js
git commit -m "feat(play): pure chordal barline/duration/validity logic mirroring backend"
```

---

## Task 5: Per-chord rhythm + barline state on the Play view

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js`
- Manual verification (RequireJS state; the serialization it feeds is node-tested in Task 6)

Add authoring state: a default-quarter rhythm per banked chord and a set of barline offsets. Keyed by the banked-chord index so it survives re-render. No reflow: durations are absolute; offsets derive from `offsetsFromDurations`.

- [x] **Step 1: Initialize state**

In `play_sheet.js`, near the other instance fields set in the constructor/`init` (where `this.chords` is assigned, ~73), add:

```javascript
      // Authoring state (Play teacher authoring). Default note value = quarter (1.0).
      this._chordDurations = {};   // bankIndex -> quarter-length (palette)
      this._barlineOffsets = [];   // quarter-length offsets, sorted/unique, on chord onsets
      this._meter = null;          // null = free/open mode
      this._tokenOverrides = {};   // offset -> { below: <string> } teacher analysis corrections
      this._selection = null;      // { kind: "chord"|"gap", index } or null
```

- [x] **Step 2: Add duration accessors**

Add methods on the prototype (near `dataForSave`):

```javascript
    getChordDuration: function (bankIndex) {
      var d = this._chordDurations[bankIndex];
      return typeof d === "number" ? d : 1.0; // default quarter
    },

    setChordDuration: function (bankIndex, quarterLength) {
      this._chordDurations[bankIndex] = quarterLength;
      this.render();
    },

    setMeter: function (meter) {
      this._meter = meter || null;
      this.render();
    },
```

- [x] **Step 3: Manual verification**

Reload the Play view; in the console confirm `window`-reachable instance has `_chordDurations`/`_barlineOffsets`/`_meter` initialized and `getChordDuration(0) === 1`. (No behavior change yet — wiring lands in Tasks 6/12.)

- [x] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js
git commit -m "feat(play): per-chord rhythm + barline + selection authoring state"
```

---

## Task 6: `play_save_logic.js` + `dataForSave` serialization

**Files:**
- Create: `lab/static/js/src/components/music/play_save_logic.js`
- Test: `lab/static/js/src/components/music/play_save_logic.test.js`
- Modify: `lab/static/js/src/components/music/play_sheet.js` (`dataForSave`, 679-749)

Stop flattening to `rhythmValue:"w"`. Build `chord[]` with explicit `offset`/`duration`/`visible`/`hidden`/`spelling`, plus top-level `meter`, `barline_offsets`, and `analysisSlices` (below-zone harmonic labels). The pure shape-building is in `play_save_logic`; `dataForSave` supplies the live data (notes, spelling via `Analyze`).

- [x] **Step 1: Write the failing test**

Create `lab/static/js/src/components/music/play_save_logic.test.js`:

```javascript
"use strict";
var mod = require("./play_save_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}

// buildChordRows: per-chord offset+duration from a durations array, preserving notes.
var rows = mod.buildChordRows(
  [{ visible: [60, 64, 67], hidden: [], spelling: ["C4", "E4", "G4"] },
   { visible: [62, 65, 69], hidden: [], spelling: ["D4", "F4", "A4"] }],
  [1, 2]
);
assertEqual("row 0 offset/duration", [rows[0].offset, rows[0].duration], [0, 1]);
assertEqual("row 1 offset/duration", [rows[1].offset, rows[1].duration], [1, 2]);
assertEqual("row 0 keeps visible+spelling",
  [rows[0].visible, rows[0].spelling], [[60, 64, 67], ["C4", "E4", "G4"]]);

// buildAnalysisSlices: below-zone harmonic labels -> slices; empty when no below zone.
assertEqual("no below zone -> no slices",
  mod.buildAnalysisSlices([0, 1], { above: "scale_degrees", below: null }, [], {}), []);
var slices = mod.buildAnalysisSlices(
  [0, 1],
  { above: null, below: "roman_numerals" },
  ["I", "V"],          // computed labels per chord
  {}                    // no overrides
);
assertEqual("roman slices count", slices.length, 2);
assertEqual("roman slice 0 content", slices[0].content, { roman_numeral: "I" });
assertEqual("roman slice is_target", slices[0].is_target, true);
// thoroughbass zone uses figured_bass content key
var fb = mod.buildAnalysisSlices([0], { above: null, below: "thoroughbass" }, ["6"], {});
assertEqual("thoroughbass content key", fb[0].content, { figured_bass: "6" });
// teacher override wins over computed label
var ov = mod.buildAnalysisSlices([0, 1], { above: null, below: "roman_numerals" },
  ["I", "V"], { 1: { below: "V7" } });
assertEqual("override applied", ov[1].content, { roman_numeral: "V7" });

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll play_save_logic assertions passed (" + pass + ")."); }
```

- [x] **Step 2: Run to verify it fails**

Run: `node lab/static/js/src/components/music/play_save_logic.test.js`
Expected: FAIL — module not found.

- [x] **Step 3: Implement the module**

Create `lab/static/js/src/components/music/play_save_logic.js`:

```javascript
/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("../../utils/chordal_barlines_logic"));
  } else if (typeof define === "function" && define.amd) {
    define(["app/utils/chordal_barlines_logic"], factory);
  } else { root.PlaySaveLogic = factory(root.ChordalBarlinesLogic); }
})(typeof self !== "undefined" ? self : this, function (Barlines) {
  "use strict";

  // Map a below-zone type id to its AnalysisLayer content key.
  var BELOW_CONTENT_KEY = {
    roman_numerals: "roman_numeral",
    roman_numerals_exp: "roman_numeral",
    thoroughbass: "figured_bass",
  };

  // notes: [{visible, hidden, spelling}]; durations: parallel quarter-lengths.
  function buildChordRows(notes, durations) {
    var offsets = Barlines.offsetsFromDurations(durations);
    return notes.map(function (n, i) {
      var row = {
        offset: offsets[i],
        duration: durations[i],
        visible: (n.visible || []).slice(),
        hidden: (n.hidden || []).slice(),
      };
      if (n.spelling) row.spelling = n.spelling.slice();
      if (typeof n.unison_idx !== "undefined" && n.unison_idx !== null) row.unison_idx = n.unison_idx;
      return row;
    });
  }

  // offsets: chord onsets; slots: {above, below}; labels: computed below-zone label per chord;
  // overrides: { offsetIndex: { below: str } }. Returns AnalysisSlice-shaped objects.
  function buildAnalysisSlices(offsets, slots, labels, overrides) {
    if (!slots || !slots.below) return [];
    var key = BELOW_CONTENT_KEY[slots.below];
    if (!key) return [];
    var out = [];
    for (var i = 0; i < offsets.length; i++) {
      var ov = overrides && overrides[i] && typeof overrides[i].below !== "undefined"
        ? overrides[i].below : null;
      var value = ov !== null ? ov : (labels[i] != null ? labels[i] : "");
      var content = {}; content[key] = value;
      out.push({ offset: offsets[i], content: content, is_target: true, unit_tags: [] });
    }
    return out;
  }

  return { buildChordRows: buildChordRows, buildAnalysisSlices: buildAnalysisSlices };
});
```

- [x] **Step 4: Run to verify it passes**

Run: `node lab/static/js/src/components/music/play_save_logic.test.js`
Expected: PASS.

- [x] **Step 5: Rewrite `dataForSave`**

In `play_sheet.js`, require the two logic modules at the top of the `define([...])` dependency list (add `"./play_save_logic"` and `"app/utils/chordal_barlines_logic"`, with matching params `PlaySaveLogic, ChordalBarlinesLogic`). Replace the `dataForSave` body (679-749) so it:
1. Builds `notes` from `this.chords._items` (skipping index 0, the live/working chord, exactly as today's loop does — preserve the existing `i = 1` start, `visible`/`hidden`/`unison_idx`/`spelling` derivation).
2. Builds a parallel `durations` array via `this.getChordDuration(bankIndex)` for each banked chord (same order as `notes`).
3. Computes below-zone labels per chord with the `Analyze` widget when `analyzeConfig.below` is set (roman → `analyzer.to_chord(visible, "roman only").numeral`; thoroughbass → `analyzer.full_thoroughbass_figure(visible)`).
4. Assembles the payload.

```javascript
    dataForSave: function () {
      const objs = this.chords._items.map((items) => items._notes);
      if (objs.length < 2) return null;

      var analyzer = new Analyze(this.keySignature);
      var notes = [];
      var durations = [];
      for (var i = 1, len = objs.length; i < len; i++) {
        var obj = objs[i];
        var visible = Object.keys(obj)
          .filter((k) => obj[k])
          .map((k) => parseInt(k, 10));
        var hidden = [];
        var unison_idx = null;
        try { unison_idx = this.chords._items[i]._unison_idx; } catch (e) {}
        var spelling = visible.concat(hidden).map((m) =>
          ChordalSpelling.vexKeyToSpellingString(analyzer.getNoteName(m, visible)));
        notes.push({ visible: visible, hidden: hidden, spelling: spelling, unison_idx: unison_idx });
        durations.push(this.getChordDuration(i));
      }

      var slots = this._analyzeSlots(); // {above, below} — Task 10
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);

      // Compute below-zone labels for analysis slices (reviewed-on-save).
      var labels = [];
      if (slots.below) {
        for (var j = 0; j < notes.length; j++) {
          var midis = notes[j].visible;
          if (slots.below === "thoroughbass") {
            labels.push(analyzer.full_thoroughbass_figure(midis) || "");
          } else {
            var rn = analyzer.to_chord(midis, "roman only");
            labels.push(rn && rn.numeral ? rn.numeral : "");
          }
        }
      }

      var chordRows = PlaySaveLogic.buildChordRows(notes, durations);
      var analysisSlices = PlaySaveLogic.buildAnalysisSlices(
        offsets, slots, labels, this._tokenOverrides);

      var json_data = {
        keySignature: this.keySignature.signatureSpec,
        key: this.keySignature.key,
        type: "matching",
        staffDistribution: this.parentComponent.staffDistributionConfig.staffDistribution,
        introText: "",
        reviewText: "",
        analyzeConfig: slots,                 // {above, below} slot directive (Task 10)
        highlight: this.parentComponent.highlightConfig,
        chord: chordRows,
        meter: this._meter,                   // null = free/open
        barline_offsets: this._barlineOffsets.slice(),
        analysisSlices: slots.below ? analysisSlices : null,
      };

      return JSON.stringify(json_data, null, 0);
    },
```

> If `this._analyzeSlots()` is not yet defined (Phase B2 lands it), add a temporary stub `_analyzeSlots: function () { return { above: null, below: null }; }` now and replace it in Task 10. Note this stub in the commit message so Task 10 removes it.

- [x] **Step 6: Verify the existing play-save DB suite still round-trips**

Run: `python manage.py test apps.exercises.tests.test_play_save_chordal_umto --settings=harmony.settings.local --noinput -v 2`
Expected: PASS — the backend reads `chord[].duration`/`offset`; default-quarter rows are valid in free mode. If any test asserted `rhythmValue`, update it to assert `duration`.

- [x] **Step 7: Manual verification**

Bank 3 chords, Save; in the Network tab inspect the POST body: `chord[]` entries carry `offset`+`duration` (no `rhythmValue:"w"`), `meter:null`, `barline_offsets:[]`. Saved exercise opens.

- [x] **Step 8: Commit**

```bash
git add lab/static/js/src/components/music/play_save_logic.js lab/static/js/src/components/music/play_save_logic.test.js lab/static/js/src/components/music/play_sheet.js
git commit -m "feat(play): dataForSave serializes per-chord duration/offset/barlines/meter/analysis slices"
```

---

## Task 7: Barline-aware saved-exercise render + null meter + dotted palette

**Files:**
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` (`_convertChordalUMTOToProcessedScore`, 2987-3058)
- Manual verification (VexFlow render)

Split `score.measures` at `umto.metadata.barline_offsets` (not by `meta.time`), tolerate `meta.time = null` (no forced 4/4, no time-signature glyph), and extend `DUR_TYPE` to cover the dotted palette values (3, 1.5, 0.75) instead of collapsing them to `"q"`.

- [x] **Step 1: Extend `DUR_TYPE` and derive dots**

In `_convertChordalUMTOToProcessedScore`, replace:

```javascript
      var DUR_TYPE = { 4: "w", 2: "h", 1: "q", 0.5: "8", 0.25: "16", 0.125: "32" };
      var durType = function (ql) { return DUR_TYPE[ql] || "q"; };
```

with a palette-aware type+dots map:

```javascript
      var DUR_PARTS = {
        4: { type: "w", dots: 0 }, 3: { type: "h", dots: 1 }, 2: { type: "h", dots: 0 },
        1.5: { type: "q", dots: 1 }, 1: { type: "q", dots: 0 }, 0.75: { type: "8", dots: 1 },
        0.5: { type: "8", dots: 0 }, 0.25: { type: "16", dots: 0 }, 0.125: { type: "32", dots: 0 }
      };
      var durParts = function (ql) { return DUR_PARTS[Number(ql)] || { type: "q", dots: 0 }; };
```

Then in the `_.each(umto.chords, ...)` loop replace:

```javascript
        var dur = { type: durType(Number(c.duration)), dots: 0 };
```

with:

```javascript
        var dp = durParts(Number(c.duration));
        var dur = { type: dp.type, dots: dp.dots };
```

- [x] **Step 2: Null-meter handling**

Replace the top of the function:

```javascript
      var meta = _.cloneDeep(umto.metadata || {});
      if (meta.meter && !meta.time) meta.time = meta.meter;
      if (!meta.time) meta.time = "4/4";
```

with (preserve `null` = free mode; do NOT force 4/4):

```javascript
      var meta = _.cloneDeep(umto.metadata || {});
      if (meta.meter && !meta.time) meta.time = meta.meter;
      // meta.time may be null/undefined => free/open mode (no time signature glyph).
      var hasMeter = !!meta.time;
```

- [x] **Step 3: Split at explicit barlines**

Add `"app/utils/chordal_barlines_logic"` to the `exercise_sheet.js` `define([...])` deps (param `ChordalBarlinesLogic`). Replace:

```javascript
      var trebleMeasures = MeasureEngine.splitIntoMeasures(trebleItems, meta.time);
      var bassMeasures = MeasureEngine.splitIntoMeasures(bassItems, meta.time);
```

with barline-aware slicing when explicit offsets are present, falling back to the meter engine only when no barlines exist AND a meter is set:

```javascript
      var barlineOffsets = (umto.metadata && umto.metadata.barline_offsets) || [];
      var chordOffsets = (umto.chords || []).map(function (c) { return Number(c.offset); });
      var trebleMeasures, bassMeasures;
      if (barlineOffsets.length || !hasMeter) {
        // Explicit barlines (or free mode): split by item counts at chord onsets.
        var counts = ChordalBarlinesLogic.measureItemCounts(chordOffsets, barlineOffsets);
        var sliceByCounts = function (items) {
          var out = []; var idx = 0;
          for (var k = 0; k < counts.length; k++) { out.push(items.slice(idx, idx + counts[k])); idx += counts[k]; }
          if (!out.length) out.push(items.slice());
          return out;
        };
        trebleMeasures = sliceByCounts(trebleItems);
        bassMeasures = sliceByCounts(bassItems);
      } else {
        trebleMeasures = MeasureEngine.splitIntoMeasures(trebleItems, meta.time);
        bassMeasures = MeasureEngine.splitIntoMeasures(bassItems, meta.time);
      }
```

- [x] **Step 4: Don't synthesize a time signature in free mode**

In the `return` block, replace:

```javascript
      return {
        meta: { key: meta.key, time: meta.time, clef: meta.clef,
                staffDistribution: dist },
        metadata: { time: meta.time, meter: meta.time },
        measures: measures,
        umto: umto,
      };
```

with (carry `null` time through so the adapter draws no TS glyph; verify the VexFlow adapter tolerates a null/absent `meta.time` — grep `tsRaw`/`time` in `vexflow_adapter.js` and confirm it guards `null`; if it hard-defaults to 4/4, add a `noTimeSignature: !hasMeter` flag here and honor it in the adapter):

```javascript
      return {
        meta: { key: meta.key, time: hasMeter ? meta.time : null, clef: meta.clef,
                staffDistribution: dist, noTimeSignature: !hasMeter },
        metadata: { time: hasMeter ? meta.time : null, meter: hasMeter ? meta.time : null },
        measures: measures,
        umto: umto,
      };
```

- [x] **Step 5: Manual verification**

- Free mode: save a free-mode exercise (no meter) with uneven durations, open it. Expect a single running measure, no time-signature glyph, durations rendered (half/dotted-quarter etc.), no forced 4/4 re-barring.
- Metered: save a 4/4 exercise with `barline_offsets:[4.0]`, open it. Expect barlines exactly at the placed offsets; 8 quarters → 2 bars.

Capture before/after screenshots.

- [x] **Step 6: Commit**

```bash
git add lab/static/js/src/components/music/exercise_sheet.js
git commit -m "feat(play-render): split saved measures at explicit barlines; null meter; dotted palette"
```

---

## Task 8: Metered-validity gate blocks Save with specific feedback

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js` (expose a validity check)
- Modify: `lab/static/js/src/components/ui/music_controls.js` (`onClickSaveJSON` pre-check)
- Manual verification

Before POST, run the JS validity mirror (Task 4). Free mode always passes. Metered invalid bars block the Save and emit `play.save.invalid_meter` with the offending bar.

- [x] **Step 1: Add a validity method to the Play sheet**

In `play_sheet.js`, add:

```javascript
    checkSaveValidity: function () {
      const objs = this.chords._items.map((items) => items._notes);
      if (objs.length < 2) return { ok: false, code: "empty" };
      var durations = [];
      for (var i = 1; i < objs.length; i++) durations.push(this.getChordDuration(i));
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      var res = ChordalBarlinesLogic.checkRhythm(offsets, durations, this._meter, this._barlineOffsets);
      return res.ok ? { ok: true } : { ok: false, code: "invalid_meter", error: res.error };
    },
```

- [x] **Step 2: Expose validity through the save bridge**

The current flow stores `dataForSave()` output in `sessionStorage` (`play_sheet.js:293`) and `music_controls` reads it back. Add the validity result to that bridge: in the `render`/save-prep path where `sessionStorage.setItem("current_state", this.dataForSave())` runs (~293), also set:

```javascript
      sessionStorage.setItem("current_state_validity", JSON.stringify(this.checkSaveValidity()));
```

- [x] **Step 3: Pre-check in `onClickSaveJSON`**

In `music_controls.js onClickSaveJSON`, immediately after reading `json_data` from sessionStorage (and before the `$.ajax` upload), add a guard for the `"upload"` destination:

```javascript
      if (destination === "upload") {
        var validity = JSON.parse(sessionStorage.getItem("current_state_validity") || "null");
        if (validity && !validity.ok) {
          if (this.feedback) {
            if (validity.code === "empty") {
              this.feedback.emit("play.save.empty", { inlineEl: "#save-feedback" });
            } else {
              // Parse "Bar N has B beats, expected E." for params.
              var m = /Bar (\d+) has (\S+) beats, expected (\S+)/.exec(validity.error || "");
              this.feedback.emit("play.save.invalid_meter", {
                inlineEl: "#save-feedback",
                params: m ? { bar: m[1], beats: m[2], expected: m[3] } : { bar: "?", beats: "?", expected: "?" },
              });
            }
          }
          return false;
        }
      }
```

- [x] **Step 4: Manual verification**

- Set meter 4/4, bank 3 quarters (3 beats), click Save → blocked, inline "Bar 1 has 3 beats, expected 4."
- Extend to 4 quarters → Save proceeds, exercise saved reviewed/none.
- Free mode (no meter) with uneven durations → Save always proceeds.

- [x] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js lab/static/js/src/components/ui/music_controls.js
git commit -m "feat(play-save): client metered-validity gate blocks invalid Save with specific feedback"
```

---

# PHASE B2 — Analysis-slot model

## Task 9: `analysis_slots.js` config + zone rules

**Files:**
- Create: `lab/static/js/src/config/analysis_slots.js`
- Test: `lab/static/js/src/config/analysis_slots.test.js`

Single source of truth for analysis-type descriptors and the two-zone (above/below), ≤1-type-per-zone rule (spec Decision b).

- [x] **Step 1: Write the failing test**

Create `lab/static/js/src/config/analysis_slots.test.js`:

```javascript
"use strict";
var mod = require("./analysis_slots");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  var g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + "\n  got:  " + g + "\n  want: " + w); }
}

assertEqual("roman_numerals allowed below only",
  mod.allowedZones("roman_numerals"), ["below"]);
assertEqual("thoroughbass allowed below only",
  mod.allowedZones("thoroughbass"), ["below"]);
assertEqual("scale_degrees allowed above only",
  mod.allowedZones("scale_degrees"), ["above"]);
assertEqual("note_names allowed above only",
  mod.allowedZones("note_names"), ["above"]);

assertEqual("typesForZone below excludes above-only",
  mod.typesForZone("below").indexOf("scale_degrees"), -1);
assertEqual("typesForZone above includes note_names",
  mod.typesForZone("above").indexOf("note_names") >= 0, true);

// canPlace enforces allowedZones
assertEqual("can place roman below", mod.canPlace("roman_numerals", "below"), true);
assertEqual("cannot place roman above", mod.canPlace("roman_numerals", "above"), false);

// normalizeSlots: legacy analyzeConfig.mode -> {above, below}
assertEqual("normalize legacy roman mode",
  mod.normalizeSlots({ mode: { roman_numerals: true } }), { above: null, below: "roman_numerals" });
assertEqual("normalize legacy thoroughbass+scale",
  mod.normalizeSlots({ mode: { thoroughbass: true, scale_degrees: true } }),
  { above: "scale_degrees", below: "thoroughbass" });
assertEqual("normalize already-slots passthrough",
  mod.normalizeSlots({ above: "note_names", below: "roman_numerals" }),
  { above: "note_names", below: "roman_numerals" });
assertEqual("normalize empty",
  mod.normalizeSlots({}), { above: null, below: null });

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll analysis_slots assertions passed (" + pass + ")."); }
```

- [x] **Step 2: Run to verify it fails**

Run: `node lab/static/js/src/config/analysis_slots.test.js`
Expected: FAIL — module not found.

- [x] **Step 3: Implement the module**

Create `lab/static/js/src/config/analysis_slots.js`:

```javascript
/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else if (typeof define === "function" && define.amd) { define([], factory); }
  else { root.AnalysisSlots = factory(); }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // descriptor: { id, label, allowedZones, anchor }
  var TYPES = [
    { id: "roman_numerals",     label: "Roman numerals",      allowedZones: ["below"], anchor: "slice" },
    { id: "roman_numerals_exp", label: "Roman numerals (exp)", allowedZones: ["below"], anchor: "slice" },
    { id: "thoroughbass",       label: "Figured bass",         allowedZones: ["below"], anchor: "slice" },
    { id: "scale_degrees",      label: "Scale degrees",        allowedZones: ["above"], anchor: "note" },
    { id: "solfege",            label: "Solfège",              allowedZones: ["above"], anchor: "note" },
    { id: "note_names",         label: "Note names",           allowedZones: ["above"], anchor: "note" },
  ];
  var BY_ID = {}; TYPES.forEach(function (t) { BY_ID[t.id] = t; });

  // Legacy analyzeConfig.mode flags, in zone-priority order, mapped to type ids.
  var BELOW_MODES = ["roman_numerals_exp", "roman_numerals", "thoroughbass"];
  var ABOVE_MODES = ["scale_degrees", "solfege", "note_names"];

  function descriptor(id) { return BY_ID[id] || null; }
  function allowedZones(id) { var d = BY_ID[id]; return d ? d.allowedZones.slice() : []; }
  function canPlace(id, zone) { return allowedZones(id).indexOf(zone) >= 0; }
  function typesForZone(zone) {
    return TYPES.filter(function (t) { return t.allowedZones.indexOf(zone) >= 0; })
      .map(function (t) { return t.id; });
  }

  // Accept either a {above, below} object or a legacy analyzeConfig with .mode flags.
  function normalizeSlots(cfg) {
    cfg = cfg || {};
    if (Object.prototype.hasOwnProperty.call(cfg, "above") ||
        Object.prototype.hasOwnProperty.call(cfg, "below")) {
      return { above: cfg.above || null, below: cfg.below || null };
    }
    var mode = cfg.mode || {};
    var below = null, above = null, i;
    for (i = 0; i < BELOW_MODES.length; i++) { if (mode[BELOW_MODES[i]]) { below = BELOW_MODES[i]; break; } }
    for (i = 0; i < ABOVE_MODES.length; i++) { if (mode[ABOVE_MODES[i]]) { above = ABOVE_MODES[i]; break; } }
    return { above: above, below: below };
  }

  return {
    TYPES: TYPES,
    descriptor: descriptor,
    allowedZones: allowedZones,
    canPlace: canPlace,
    typesForZone: typesForZone,
    normalizeSlots: normalizeSlots,
  };
});
```

- [x] **Step 4: Run to verify it passes**

Run: `node lab/static/js/src/config/analysis_slots.test.js`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add lab/static/js/src/config/analysis_slots.js lab/static/js/src/config/analysis_slots.test.js
git commit -m "feat(analysis): analysis_slots config — two zones, <=1 type each, zone rules"
```

---

## Task 10: Consume slots in the Play view; persist `analyzeConfig {above, below}`

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js` (`_analyzeSlots`, replace Task 6 stub)
- Manual verification

Derive `{above, below}` from the live `analyzeConfig` via `AnalysisSlots.normalizeSlots`, so `dataForSave` (Task 6) serializes a real slot directive and below-zone slices.

- [x] **Step 1: Add the deps + method**

Add `"app/config/analysis_slots"` to `play_sheet.js` `define([...])` (param `AnalysisSlots`). Replace the temporary `_analyzeSlots` stub from Task 6 with:

```javascript
    _analyzeSlots: function () {
      var cfg = this.getAnalyzeConfig() || {};
      return AnalysisSlots.normalizeSlots(cfg);
    },
```

- [x] **Step 2: Manual verification**

- Enable Roman numerals in the Play notation panel, bank chords, Save. POST body: `analyzeConfig:{above:null, below:"roman_numerals"}`, `analysisSlices` present with `{roman_numeral: ...}` per chord, `reviewStatus:"reviewed"`.
- Enable figured bass instead → `below:"thoroughbass"`, slices carry `{figured_bass: ...}`.
- Disable all analysis → `analyzeConfig:{above:null,below:null}`, `analysisSlices:null`, `reviewStatus:"none"`.

- [x] **Step 3: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js
git commit -m "feat(play): derive {above,below} slots from analyzeConfig for save serialization"
```

---

## Task 11: Consume slots in `stave_notater.js` / `exercise_sheet.js` placement

**Files:**
- Modify: `lab/static/js/src/components/music/stave_notater.js` (placement decisions, ~1226-1230 area)
- Modify: `lab/static/js/src/components/music/exercise_sheet.js` (where it normalizes `analyzeConfig`)
- Manual verification

Replace scattered "is this mode enabled" conditionals that decide above/below placement with `AnalysisSlots` so the zone rule has one owner. This is a **refactor with no behavior change** for existing exercises (the normalized slots reproduce today's placement); it makes the Play `{above, below}` directive authoritative.

- [x] **Step 1: Make stave_notater zone-aware**

Add `"app/config/analysis_slots"` to `stave_notater.js` deps (param `AnalysisSlots`). In `init`/config handling, compute `this.slots = AnalysisSlots.normalizeSlots(this.analyzeConfig)` once. Where the notater currently decides whether to draw roman/figured below vs. scale-degrees/note-names above (search the draw dispatch around lines 1226-1320 reading `this.analyzeConfig.mode.*`), gate each draw on `this.slots.below === <id>` / `this.slots.above === <id>` instead of the raw mode flags. Keep the actual drawing code; only change the guard expressions.

> Preserve backward compatibility: `normalizeSlots` maps legacy `mode` flags to the same placement, so exercises that don't carry `{above, below}` render identically. Verify with an existing chordal exercise (below = roman) before and after.

- [x] **Step 2: Honor `{above, below}` in exercise_sheet normalization**

In `exercise_sheet.js`, where `analyzeConfig` is cloned/derived for chordal rendering (~1859-1944), if `umto.metadata` or the definition carries `analyzeConfig {above, below}`, set the corresponding `mode.*` flags from the slots (so the downstream notater/adapter, which still reads `mode`, lights up the right zones). Use `AnalysisSlots` to translate `{above, below}` → `mode` flags:

```javascript
      // If the exercise stored explicit slots, project them onto mode flags.
      var storedSlots = (definition.exercise && definition.exercise.analyzeConfig) || null;
      if (storedSlots && (storedSlots.above || storedSlots.below)) {
        analyzeConfig.mode = analyzeConfig.mode || {};
        if (storedSlots.below === "roman_numerals") analyzeConfig.mode.roman_numerals = true;
        if (storedSlots.below === "roman_numerals_exp") analyzeConfig.mode.roman_numerals = true;
        if (storedSlots.below === "thoroughbass") analyzeConfig.mode.thoroughbass = true;
        if (storedSlots.above === "scale_degrees") analyzeConfig.mode.scale_degrees = true;
        if (storedSlots.above === "note_names") analyzeConfig.mode.note_names = true;
      }
```

(Place this after the existing `analyzeConfig` is assembled, before it's handed to the adapter.)

- [x] **Step 3: Manual verification**

- Open an existing roman-numeral chordal exercise → renders identically (regression check).
- Open a Play-saved exercise authored with `below:"thoroughbass"` → figures render below, nothing above.
- Author one with `above:"note_names"` + `below:"roman_numerals"` → note names above, romans below.

- [x] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/stave_notater.js lab/static/js/src/components/music/exercise_sheet.js
git commit -m "refactor(analysis): single-source zone placement via analysis_slots (above/below)"
```

---

# PHASE B3 — Click-first authoring + shortcuts

## Task 12: Selection + micro-toolbar (duration palette, respell)

**Files:**
- Create: `lab/static/js/src/components/music/play_authoring_toolbar.js`
- Modify: `lab/static/js/src/components/music/play_sheet.js` (selection wiring + render hook)
- Manual verification

Clicking a rendered chord selects it and opens a micro-toolbar at the cursor: a duration palette (the eight values) and a respell control. Selection is the gate for keyboard accelerators (Task 15). This is on-canvas WYSIWYG (spec "quiet until invoked").

- [x] **Step 1: Build the toolbar component**

Create `play_authoring_toolbar.js` as a RequireJS component that renders a small floating element with:
- Duration buttons for `ChordalBarlinesLogic.PALETTE` (label them w / h. / h / q. / q / 8. / 8 / 16), calling back `onSetDuration(ql)`.
- A "Respell" button calling back `onRespell()` (delegates to `ChordalSpelling` on the selected chord — reuse the workbench respell editor logic; grep `respell` in `workbench.html`/`chordal_spelling.js` and reuse the same key-aware spelling cycle).
- A close/`Esc` affordance calling `onClose()`.

Expose `showAt(rect, context)` / `hide()`. Keep DOM minimal; style via an existing toolbar class if one exists (grep `micro-toolbar`/`toolbar` in the Play CSS).

- [x] **Step 2: Wire selection in play_sheet**

In `play_sheet.js`:
- Add the toolbar to the component tree (`addComponent`) and keep a reference.
- After render, attach click handlers to each rendered chord's hit area. The renderer already caches per-chord positions (grep `_windowPositionCache`/`createNoteStave` for the x/y of each banked chord). On click, set `this._selection = { kind: "chord", index: bankIndex }`, compute the chord's screen rect, and call `toolbar.showAt(rect, { index })`.
- Toolbar callbacks: `onSetDuration(ql)` → `this.setChordDuration(this._selection.index, ql)`; `onRespell()` → respell the selected chord's spelling and re-render; `onClose()` → `this._selection = null; toolbar.hide()`.

- [x] **Step 3: Manual verification**

- Click a banked chord → toolbar appears at the chord; pick "h" → that chord renders as a half note; Save → POST shows that chord's `duration: 2`.
- Respell a chord → enharmonic spelling flips; Save → `spelling` reflects it.
- Click empty space / `Esc` → toolbar closes, selection cleared.

Capture a screenshot.

- [x] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/play_authoring_toolbar.js lab/static/js/src/components/music/play_sheet.js
git commit -m "feat(play-authoring): click-to-select chord + micro-toolbar (duration palette, respell)"
```

---

## Task 13: Token correction (Roman / figure) reusing the workbench figure picker

**Files:**
- Modify: `lab/static/js/src/components/music/play_authoring_toolbar.js`
- Modify: `lab/static/js/src/components/music/play_sheet.js` (`_tokenOverrides`)
- Manual verification

Clicking a below-zone analysis token opens a correction control. For figured bass, reuse the workbench figure-token picker. Corrections live in `this._tokenOverrides[bankIndex] = { below: value }` and win over computed labels in `dataForSave` (already supported by `play_save_logic.buildAnalysisSlices`).

- [x] **Step 1: Locate and extract the workbench figure picker**

Grep the workbench template/JS for the figure-token picker (e.g. `grep -rn "figure" lab/templates/**/workbench.html lab/static/js/**`). Identify the picker widget (a prioritized option list / token input). If it is inline in `workbench.html`, extract its option-list builder into a small reusable function/module so both surfaces share it (DRY — the redundancy report calls out duplicated figure logic). If extraction is large, wrap it behind a thin adapter the toolbar calls; note the decision in the commit.

- [x] **Step 2: Wire token correction**

In the toolbar, add an `onSetToken(value)` callback shown when the selection has an active below zone. For Roman numerals use a text input (validated against the existing answer/normalization helpers); for figured bass use the reused picker. In `play_sheet.js`:

```javascript
    setToken: function (bankIndex, zone, value) {
      this._tokenOverrides[bankIndex] = this._tokenOverrides[bankIndex] || {};
      this._tokenOverrides[bankIndex][zone] = value;
      this.render();
    },
```

Selecting a token wires `onSetToken(v)` → `this.setToken(this._selection.index, "below", v)`.

- [x] **Step 3: Manual verification**

- With Roman numerals on, click a chord's roman token → correct `V` to `V7` → it re-renders and Save's `analysisSlices` carries `{roman_numeral:"V7"}` at that offset.
- With figured bass on, open the figure picker, choose `6/5` → slice carries `{figured_bass:"6/5"}`.
- Save remains `reviewed` (teacher-approved in place; no per-token accept step — spec Decision d).

- [x] **Step 4: Commit**

```bash
git add lab/static/js/src/components/music/play_authoring_toolbar.js lab/static/js/src/components/music/play_sheet.js <extracted_picker_files>
git commit -m "feat(play-authoring): in-place Roman/figure token correction reusing workbench picker"
```

---

## Task 14: Click-between-chords barline place/remove + meter auto-suggest

**Files:**
- Modify: `lab/static/js/src/components/music/play_sheet.js`
- Modify: `lab/static/js/src/components/music/play_authoring_toolbar.js` (or a thin gap-affordance)
- Manual verification

Clicking the gap between two chords toggles a barline at the right chord's onset. Setting a meter auto-suggests barlines (`ChordalBarlinesLogic.suggestBarlines`) the teacher can then move/add/remove.

- [x] **Step 1: Barline toggle ops**

In `play_sheet.js`:

```javascript
    placeBarline: function (offset) {
      var o = Math.round(offset * 1e6) / 1e6;
      if (this._barlineOffsets.indexOf(o) === -1) {
        this._barlineOffsets.push(o);
        this._barlineOffsets.sort(function (a, b) { return a - b; });
        this.render();
      }
    },
    removeBarline: function (offset) {
      var o = Math.round(offset * 1e6) / 1e6;
      this._barlineOffsets = this._barlineOffsets.filter(function (b) { return b !== o; });
      this.render();
    },
    toggleBarlineAtChord: function (bankIndex) {
      // Barline sits at the onset of the chord at bankIndex (between it and the previous).
      var durations = [];
      for (var i = 1; i < this.chords._items.length; i++) durations.push(this.getChordDuration(i));
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      var onset = offsets[bankIndex - 1]; // bankIndex starts at 1 for first banked chord
      if (onset === undefined || onset === 0) return; // no barline at stream start
      if (this._barlineOffsets.indexOf(onset) === -1) this.placeBarline(onset);
      else this.removeBarline(onset);
    },
```

- [x] **Step 2: Gap hit areas + barline render**

In `updateStaves`/render, draw a light vertical tick at each `_barlineOffsets` position between the corresponding banked-chord mini-staves, and add a clickable gap zone between adjacent chords that calls `toggleBarlineAtChord(rightIndex)`. (Live-view barlines are lightweight indicators; full ABC fidelity is the saved-exercise render from Task 7.)

- [x] **Step 3: Meter auto-suggest**

When the teacher sets a meter (a meter control in the Play notation panel — add a simple select `none / 2/4 / 3/4 / 4/4 / 6/8` bound to `this.setMeter`), call:

```javascript
    autoSuggestBarlines: function () {
      var durations = [];
      for (var i = 1; i < this.chords._items.length; i++) durations.push(this.getChordDuration(i));
      var offsets = ChordalBarlinesLogic.offsetsFromDurations(durations);
      this._barlineOffsets = ChordalBarlinesLogic.suggestBarlines(offsets, durations, this._meter);
      this.render();
    },
```

Call `autoSuggestBarlines()` from `setMeter` when a non-null meter is chosen (only as a starting point — teacher edits override).

- [x] **Step 4: Manual verification**

- Set 4/4 with eight quarters → a barline auto-appears at offset 4; the saved exercise has two bars.
- Click the gap to remove/add a barline → validity re-checks; an invalid configuration blocks Save (Task 8) with the bar message.
- Free mode (meter none) → no auto barlines; manual barlines still allowed; Save always proceeds.

- [x] **Step 5: Commit**

```bash
git add lab/static/js/src/components/music/play_sheet.js lab/static/js/src/components/music/play_authoring_toolbar.js
git commit -m "feat(play-authoring): click-to-place barlines + meter auto-suggest"
```

---

## Task 15: Selection-scoped accelerators; suspend note-entry on text focus

**Files:**
- Create: `lab/static/js/src/components/input/note_entry_gate_logic.js`
- Test: `lab/static/js/src/components/input/note_entry_gate_logic.test.js`
- Modify: `lab/static/js/src/components/input/shortcuts.js` (`isEnabled`, ~181-186)
- Modify: `lab/static/js/src/components/music/play_sheet.js` (selection-scoped key handling)
- Manual verification

Note-entry must suspend when a text field is focused (so typing a Roman numeral / figure doesn't play notes). Authoring accelerators (`1–4` duration, `R` respell, `Esc` deselect) fire only with a selection. No new global shortcuts (spec Decision c).

- [x] **Step 1: Write the failing test**

Create `lab/static/js/src/components/input/note_entry_gate_logic.test.js`:

```javascript
"use strict";
var mod = require("./note_entry_gate_logic");

var pass = 0, fail = 0;
function assertEqual(name, got, want) {
  if (got === want) { pass++; console.log("ok - " + name); }
  else { fail++; console.error("FAIL - " + name + " got:" + got + " want:" + want); }
}

assertEqual("suspend when INPUT focused", mod.shouldSuspendNoteEntry("INPUT", "text"), true);
assertEqual("suspend when TEXTAREA focused", mod.shouldSuspendNoteEntry("TEXTAREA", null), true);
assertEqual("suspend when contenteditable", mod.shouldSuspendNoteEntry("DIV", null, true), true);
assertEqual("do not suspend for checkbox input", mod.shouldSuspendNoteEntry("INPUT", "checkbox"), false);
assertEqual("do not suspend for body", mod.shouldSuspendNoteEntry("BODY", null), false);
assertEqual("do not suspend when nothing focused", mod.shouldSuspendNoteEntry(null, null), false);

if (fail > 0) { console.error("\n" + fail + " failed."); process.exit(1); }
else { console.log("\nAll note_entry_gate_logic assertions passed (" + pass + ")."); }
```

- [x] **Step 2: Run to verify it fails**

Run: `node lab/static/js/src/components/input/note_entry_gate_logic.test.js`
Expected: FAIL — module not found.

- [x] **Step 3: Implement the predicate**

Create `lab/static/js/src/components/input/note_entry_gate_logic.js`:

```javascript
/* global define: false */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else if (typeof define === "function" && define.amd) { define([], factory); }
  else { root.NoteEntryGateLogic = factory(); }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var TEXT_INPUT_TYPES = { text: true, search: true, email: true, url: true, tel: true, password: true, number: true };

  // tagName: activeElement.tagName (or null); inputType: <input type> (or null);
  // isContentEditable: boolean.
  function shouldSuspendNoteEntry(tagName, inputType, isContentEditable) {
    if (isContentEditable) return true;
    if (!tagName) return false;
    var t = String(tagName).toUpperCase();
    if (t === "TEXTAREA") return true;
    if (t === "INPUT") {
      if (inputType == null) return true; // default <input> is text
      return TEXT_INPUT_TYPES[String(inputType).toLowerCase()] === true;
    }
    return false;
  }

  return { shouldSuspendNoteEntry: shouldSuspendNoteEntry };
});
```

- [x] **Step 4: Run to verify it passes**

Run: `node lab/static/js/src/components/input/note_entry_gate_logic.test.js`
Expected: PASS.

- [x] **Step 5: Gate `isEnabled` in shortcuts.js**

Add `"app/components/input/note_entry_gate_logic"` to `shortcuts.js` deps (param `NoteEntryGate`). Change `isEnabled` (~181-186) from returning `this.enabled` to also checking the active element:

```javascript
    isEnabled: function () {
      if (!this.enabled) return false;
      if (typeof document !== "undefined" && document.activeElement) {
        var el = document.activeElement;
        if (NoteEntryGate.shouldSuspendNoteEntry(
              el.tagName, el.getAttribute && el.getAttribute("type"),
              el.isContentEditable)) {
          return false;
        }
      }
      return true;
    },
```

- [x] **Step 6: Selection-scoped accelerators in play_sheet**

In `play_sheet.js`, add a keydown listener (scoped to the Play surface) that acts **only when `this._selection` is set**:
- `1`→quarter(1.0), `2`→half(2.0), `3`→dotted-half(3.0), `4`→whole(4.0) on the selected chord via `setChordDuration` (a pragmatic mapping of the `1–4` accelerators in spec Decision c; document the mapping in a comment).
- `r`/`R`→respell selected chord.
- `Escape`→clear selection + hide toolbar (returns all keys to note entry).
When `this._selection` is null, the listener does nothing (keys fall through to note entry). Do not bind any global authoring keys.

- [x] **Step 7: Manual verification**

- Focus the Roman-numeral text input, type letters → no notes play (note-entry suspended); blur → note entry resumes.
- Select a chord, press `2` → becomes a half note; `Esc` → deselects; now `2` plays a note again (note entry).
- No selection → all letters/numbers drive note entry as before.

- [x] **Step 8: Commit**

```bash
git add lab/static/js/src/components/input/note_entry_gate_logic.js lab/static/js/src/components/input/note_entry_gate_logic.test.js lab/static/js/src/components/input/shortcuts.js lab/static/js/src/components/music/play_sheet.js
git commit -m "feat(play-authoring): suspend note-entry on text focus; selection-scoped accelerators"
```

---

# PHASE B4 — Post-save target selector stub + docs

## Task 16: Post-save target-selector stub

**Files:**
- Create: `lab/static/js/src/components/ui/target_selector.js`
- Modify: `lab/static/js/src/components/ui/music_controls.js` (handle `PLAY_SAVED`)
- Manual verification

After Save returns `{ id }`, show a small selector that emits the seam contract `{ exerciseId, targetIntent: "library"|"assign", sectionId?, autoTranspose }`. `library` is the default and only wired target; `assign`/curriculum are Threads 2/3 (disabled, labeled "coming soon"). Auto-transpose is a toggle (default off; contract only).

- [x] **Step 1: Build the selector component**

Create `target_selector.js` (RequireJS component) rendering:
- Heading "Where should this go?"
- A radio: "My library" (selected, enabled) / "Assign to a class" (disabled, "coming soon").
- An "Auto-transpose for varied keys" checkbox (default off).
- A "File it" button that emits via callback `onChoose({ exerciseId, targetIntent, sectionId: null, autoTranspose })`.

`open(exerciseId)` shows it; `close()` hides.

- [x] **Step 2: Wire it to PLAY_SAVED**

In `music_controls.js`, subscribe to `EVENTS.BROADCAST.PLAY_SAVED` and call `this.targetSelector.open(payload.exerciseId)`. On `onChoose`, for `targetIntent === "library"`: navigate to the saved exercise (`window.open('/dashboard/exercises/' + exerciseId + '/', '_blank')` or in-place per current UX) and emit `feedback "play.save.success"`. Log the full seam contract object to the console (the durable handoff for Threads 2/3). Construct `this.targetSelector` in `initComponent`.

- [x] **Step 3: Manual verification**

- Save a valid exercise → selector appears; "My library" preselected; "Assign" disabled.
- Toggle auto-transpose, click "File it" → console logs `{ exerciseId, targetIntent:"library", sectionId:null, autoTranspose:true }`; you land on the new exercise.

- [x] **Step 4: Commit**

```bash
git add lab/static/js/src/components/ui/target_selector.js lab/static/js/src/components/ui/music_controls.js
git commit -m "feat(play-save): post-save target-selector stub (library default, auto-transpose toggle)"
```

---

## Task 17: Docs + full verification

**Files:**
- Modify: `docs/exercise_types.md`
- Verification only otherwise

- [x] **Step 1: Document the Play-authored chordal flow**

In `docs/exercise_types.md`, under the Play types section, add/update the chordal `PLAYBACK` entry: Play authoring produces a chordal UMTO exercise; free mode (no meter) saves any rhythm as a single running measure; metered mode validates exact bar tiling and renders barlines where placed; analysis slots persist as `analyzeConfig {above, below}`; Save sets `analysis_review_status = reviewed` (or `none` with no analysis slot). Update the "All exercise types at a glance" table accordingly.

- [x] **Step 2: Run every new front-end logic test**

```bash
node lab/static/js/src/utils/chordal_barlines_logic.test.js
node lab/static/js/src/components/music/play_save_logic.test.js
node lab/static/js/src/config/analysis_slots.test.js
node lab/static/js/src/components/input/note_entry_gate_logic.test.js
node lab/static/js/src/config/feedback_catalog.test.js
```
Expected: all PASS.

- [x] **Step 3: Run the touched Python suites**

```bash
python manage.py test lab.tests.test_add_exercise_view_db apps.exercises.tests.test_play_save_chordal_umto apps.exercises.tests.test_chordal_authoring_backend --settings=harmony.settings.local --noinput -v 1
```
Expected: PASS. (Phase A's `test_chordal_authoring_backend` includes `ReviewEndpointRhythmTests` — confirm still green since the endpoint is untouched here.)

- [x] **Step 4: End-to-end manual smoke (the acceptance criteria)**

Walk the spec's acceptance criteria 1–8 and 9 (Phase B target selector):
1. Bank N chords + Save → `reviewed` (or `none`), no redirect, no `window.alert`.
2. `dataForSave` round-trips per-chord `duration` + barline offsets; saved measures split at those offsets.
3. Free mode `meter:null` saves any stream; one measure when no barlines; no TS glyph.
4. Metered Save blocked on non-tiling bars with the specific message; auto-suggest works (4a); palette-only durations, no reflow (4b); barline offsets sorted/unique on onsets (4c); ≥1 slot → reviewed slices, no slot → `none` (4d).
5. Each zone ≤1 type; types restricted to allowed zones; persists as `{above, below}`.
6. Accelerators only with a selection; text focus suspends note entry.
8. No-interaction blackboard shows no authoring chrome.
9. Save surfaces the target selector emitting the seam contract.

Record results + screenshots in the PR body.

- [x] **Step 5: Commit + open PR**

```bash
git add docs/exercise_types.md
git commit -m "docs(play): document click-first chordal authoring flow + acceptance verification"
```

Open the PR:

```bash
gh api repos/avnerdorman/HarmonyLab/pulls \
  -f base=master -f head=claude/admiring-wiles-136502 \
  -f title="Teacher Play authoring Phase B — in-Play click-first UI" \
  -f body="$(cat <<'EOF'
Implements Plan 2 (Phase B) of teacher Play authoring — the in-Play frontend over the Phase A backend (PR #93).

- B0: Save = reviewed; AddExerciseView threads barlines/meter/analysis; bounce removed; feedbackService.
- B1: per-chord durations + explicit barlines in dataForSave; barline-aware saved render; null-meter; dotted palette; client metered-validity gate.
- B2: analysis_slots config (two zones, <=1 type each); {above, below} persistence; below-zone reviewed slices.
- B3: click-first micro-toolbar (duration/respell/token correction); click-to-place barlines + meter auto-suggest; selection-scoped accelerators; note-entry suspended on text focus.
- B4: post-save target-selector stub (library default + auto-transpose toggle).

Front-end pure-logic node tests + Python DB tests green; manual acceptance walk in the comments.
EOF
)"
```

---

## Self-Review (spec coverage)

- **Decision a (durations/barlines/meter-gated Save):** dataForSave per-chord duration + barline_offsets + meter (Task 6); client palette + metered-tiling gate mirroring backend (Tasks 4, 8); barline place/remove + auto-suggest (Task 14); saved render splits at explicit barlines + null meter (Task 7). No-reflow is a UI property of `setChordDuration` (Task 5) preserving later offsets (durations are independent; offsets derive from the array).
- **Decision b (analysis slots):** `analysis_slots.js` two zones / ≤1 type / allowedZones (Task 9); consumed in stave_notater + exercise_sheet (Task 11); persisted as `{above, below}` (Tasks 6, 10).
- **Decision c (selection-scoped shortcuts):** note-entry suspended on text focus via `isEnabled` + predicate (Task 15); accelerators fire only with a selection; no new global keys.
- **Decision d (Save = approval, no bounce):** AddExerciseView returns reviewed (Task 1); music_controls drops the generated/reviewUrl bounce + routes feedback (Task 3); ≥1 slot → reviewed slices, no slot → none (Tasks 6, 10); validity precondition (Task 8).
- **Decision e (agent parity):** the UI ops map to the add-endpoint payload + the Phase A review endpoint; no UI-only data path (every toolbar action writes `chord[]`/`barline_offsets`/`meter`/`analysisSlices`, the same shapes an agent posts).
- **Post-save seam:** target-selector emits `{ exerciseId, targetIntent, sectionId?, autoTranspose }`, library wired (Task 16).
- **Zero-friction blackboard:** authoring chrome is click-invoked only; free mode + no interaction = today's view (Tasks 12, verified Task 17 AC8).
- **Deferred (unchanged):** MusicXML-onto-canvas (spec Phase B item 5) is **not** in this plan's task list — it is explicitly "may phase after the core authoring loop"; flag to the reviewer whether to include it now or as a follow-up. Cross-barline ties, tuplets, explicit rests, full power-user shortcut layer, real assign/curriculum, auto-transpose per-key recompute — all deferred per spec.

> **Open item for reviewer:** the spec's Phase B lists MusicXML-import-onto-canvas alongside the target selector. This plan scopes the six items the user enumerated (durations, render, slots, click-first, Save→reviewed, target stub) and treats MusicXML-onto-canvas as a follow-up plan. Confirm that split.
