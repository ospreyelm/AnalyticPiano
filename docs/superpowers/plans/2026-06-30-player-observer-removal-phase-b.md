# #5 player.html observer removal — Phase B (behavior commit + field-disabled)

**Goal:** Remove the last 3 behavioral DOM hacks from `apps/student/templates/student/player.html` (1 capture-phase submit interceptor + 2 `syncTextFieldDisabled` attribute observers) by moving the behavior into the JS identification components.

**Architecture:** (1) Move the text-field commit into the submit flow: the external `#identification-submit` button's `onclick` becomes a component method that flushes the pending field value (Type mode) before submitting, or submits committed answers directly (Click mode). (2) Make the text field persist visible-but-disabled in Click mode (matching the intended UX), and toggle `disabled`+placeholder at the point of state change inside `_syncIdentificationInputComponent` instead of via attribute observers.

**Tech Stack:** jQuery, lodash, AMD/ESM via Vite, Django template. No test harness covers this DOM code — verification is browser-only via `/run-harmonylab`.

**Worktree:** `worktree-player-observer-phase-b` off `master`.

---

## Context

Phase A (PR #192) removed the 2 childList relocation observers and made the identification components render directly into `#ident-toolbar-slot` / `#s-answer-bar` via `lab/static/js/src/components/music/identification_layout_targets.js`. Three behavioral pieces remained in `player.html`:

1. **Capture-phase submit interceptor** (`player.html`): `#identification-submit`'s `onclick` was `onSubmitIdentification` (set in `exercise_sheet_identification_controls.js`), which reads answers already committed to the grader. But `TextInputComponent` (`text_input.js`) only commits on Enter / internal `.text-id-check` click — not on keystroke. So the template intercepted the external Check click in **capture phase**, clicked the hidden `.text-id-check` to force a commit, and `stopImmediatePropagation`-blocked the outer `onclick`. DOM-capture glue compensating for component behavior.

2. **Two `syncTextFieldDisabled` attribute observers** (`player.html`): a `MutationObserver` on `#ident-toolbar-slot` class mutations + one on `#s-answer-bar` childList, both calling `syncTextFieldDisabled`, which toggled `.text-id-field[disabled]` + placeholder based on Click vs Type mode.

**Key finding from tracing the code:** `_syncIdentificationInputComponent` (`exercise_sheet_identification_input_mode.js`) previously **destroyed/hid** the text field in Click mode. So the observer's disable-branch was dead (fires async *after* destroy, finds no field) and its enable-branch was redundant (field is enabled-by-default from `render()`). The verify list expects the field **visible-but-disabled** in Click mode with placeholder `"Click the ? labels on the score"` — which was NOT the previous behavior. **User decision: match the verify list** — keep the field mounted in Click mode, disabled, with the hint placeholder.

**Constraint (Phase A, still live):** legacy `lab/templates/exercise.html` has no slots and no observer — it already runs without these hacks. The components are shared; do not regress legacy. `symbolic_question_sheet.js` uses button choices + a jQuery `submitIdentPage` binding (no `.text-id-check`/`.text-id-field`), so the removed interceptor (a no-op for it) and the new `onclick` (different exercise type) don't affect it.

**Idempotency note (makes flush safe):** `_applyIdentificationAnswer` early-returns when the stored answer already equals the new label, so re-emitting unchanged answers via `_emitAllAnswers` is harmless. BUT `_emitAllAnswers` clears answers present in `_prevAnswers` but absent from the new tokens — so flushing an **empty/disabled** field would wipe grader answers. The flush therefore only runs when the field is **enabled** (Type mode), never when disabled (Click mode).

All three JS modules are mixed into `ExerciseSheetComponent.prototype` via `_.extend` (`exercise_sheet.js`), so `this._inputComponent`, `this.onSubmitIdentification`, `this._supportsTextInputMode`, `this._syncIdentificationInputComponent` all live on the same `this`.

---

## Changes

| File | Change |
|---|---|
| `lab/static/js/src/components/input/text_input.js` | Add `_placeholderText()`, `setDisabled(disabled)`, `flushAndSubmitIfActive()`; refactor `render()` placeholder to use `_placeholderText()`. |
| `lab/static/js/src/components/music/exercise_sheet_identification_controls.js` | Rebind `#identification-submit` `onclick` to `_onExternalSubmitClick`; add `_onExternalSubmitClick` (Type mode flushes via `flushAndSubmitIfActive`, else direct `onSubmitIdentification`). |
| `lab/static/js/src/components/music/exercise_sheet_identification_input_mode.js` | Refactor `_syncIdentificationInputComponent` to keep the field mounted for supported exercises (disable in Click mode instead of destroy); add `_syncIdentificationInputDisabled`. |
| `apps/student/templates/student/player.html` | Delete capture interceptor + `getCurrentInputMode`/`syncTextFieldDisabled` + 2 observers + now-unused local vars; update comment. |
| `docs/architecture/simplification-roadmap.md` | Update #5 Status → DONE. |

### `TextInputComponent` additions

- `_placeholderText()` — analysisType-specific placeholder for the enabled field.
- `setDisabled(disabled)` — `prop("disabled", !!disabled)` + placeholder (`"Click the ? labels on the score"` when disabled, else `_placeholderText()`).
- `flushAndSubmitIfActive()` — returns false if no enabled field; else `_commitSubmitValue(field.val())` (emit + `onSubmit`) and returns true. Guards on `!disabled` so Click mode never flushes an empty field that would wipe grader answers.

### `exercise_sheet_identification_controls.js`

`#identification-submit` `onclick` → `_.bind(this._onExternalSubmitClick, this)`:

```js
_onExternalSubmitClick: function () {
  var input = this._inputComponent;
  if (input && input.flushAndSubmitIfActive && input.flushAndSubmitIfActive()) {
    return;
  }
  this.onSubmitIdentification();
},
```

### `exercise_sheet_identification_input_mode.js`

`_syncIdentificationInputComponent` now: if `!problems.length || !this._supportsTextInputMode(definition)` → hide+empty+destroy (no toggle for this exercise). Else build (or reuse) the component in BOTH Click and Type mode and call `_syncIdentificationInputDisabled(inputMode)`:

```js
_syncIdentificationInputDisabled: function (inputMode) {
  var component = this._inputComponent;
  if (!component || !component.setDisabled) {
    return;
  }
  component.setDisabled(inputMode !== "text");
},
```

`inputMode` stays in the rebuild signature so the existing rebuild-on-toggle behavior (the toggle handler nulls `_identInputSignature` before `render()`) is unchanged; after rebuild the disabled state is applied.

---

## Verification

No Django/JS unit test covers this DOM behavior. Verify by running the app in a browser.

### Setup (worktree Vite dev server)

Per memory `project_architecture_simplification_effort`: Vite dev runs per-checkout on `:5173`. To browser-verify from this worktree:
1. Symlink `node_modules`: `ln -s <main-checkout>/node_modules node_modules` (from worktree root).
2. Kill any Vite already on `:5173` in the main checkout.
3. From the worktree root run the project's Vite dev command on `:5173`, with `DJANGO_SETTINGS_MODULE=harmony.settings.local` for any `manage.py`.
4. Test student: `test-student@local.test` / `test-student-local-only` (get_or_create).
5. Restore the main checkout's Vite after verification.

### Browser checks (via `/run-harmonylab`)

Open a Type-mode identification exercise (e.g. a Roman/figured-bass/note-name identification unit) in the **modern student player**:

- **Type mode submit:** type an answer (do NOT press Enter), click external **Check** → answer submits correctly (capture-phase gone; commit-in-flow works). Matches pressing Enter.
- **Click mode field:** toggle to Click → `.text-id-field` is present, **disabled**, placeholder = `"Click the ? labels on the score"`. Answer via score labels (popup), click Check → submits.
- **Type mode field:** toggle to Type → `.text-id-field` enabled, placeholder = `"e.g. C D E F"` (note_name) / analysisType-specific for intervals.
- **Toggle Click↔Type:** disabled state flips immediately on toggle (no observer, set at state-change).
- **Practice/Submit toggle:** no regression (button shows/hides; field persists disabled/enabled correctly).
- **Next/Previous navigation:** ident nodes rebuild in the right slots; field disabled state re-applies per current mode.
- **Legacy player:** hit a `lab/views.py` route rendering `lab/templates/exercise.html` (identification exercise) → toggles/progress/input render inline in `#identification-actions` as before; no regression, slots absent so fallback path. No console errors from these changes.
- **Console errors:** only pre-existing `AudioContext autoplay` + `keyboard.js "require is not defined"` (unrelated, per spec).

### Lint + build

- `npm run lint` (eslint `no-undef` guards strict-mode globals — memory `project_vite_strict_mode_globals`).
- `npm run build`.

### PR + memory

- `gh pr create --repo avnerdorman/HarmonyLab --base master` (per AGENTS.md; never let gh infer upstream).
- After merge: update memory `project_architecture_simplification_effort` pointer (Phase B done; #5 → DONE).