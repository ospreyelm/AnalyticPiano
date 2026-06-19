# Teacher Play exercise-mode unification — design

## Problem

`/teacher/play/` has two separate exercise-type pickers that each speak a different,
partially-broken vocabulary:

- **Manual editor** (`SUPPORTED_TEACHER_PLAY_MODES` in
  [apps/exercises/utils/playlist_naming.py](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/exercises/utils/playlist_naming.py)):
  `play, roman, figures, identify, harmonization`.
- **Batch wizard** (Bach-corpus auto-generation, checkboxes in
  [music_controls.js](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/ui/music_controls.js)):
  `play, identify, roman, figures`.

Neither matches what the underlying Bach matrix generator
(`generate_bach_unit_matrix` → `import_bach_phrases`) actually supports:
`play, play_figures, roman, figures, figures_unabbreviated, matching`.

Three concrete bugs follow from this mismatch:

1. **Manual editor's `"roman"` produces the wrong UI.** In
   [lab/views.py `AddExerciseView.post`](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/views.py),
   `_mode_map` has no entry for `"roman"`, so it falls back to
   `InteractionMode.PLAYBACK`, and a separate block force-sets
   `display.showRomans = True`. Net effect: Roman numerals render as permanent
   static labels instead of the hidden `?`-slot quiz the matrix generator's
   `"roman"` mode produces. Verified directly against production data
   (exercise `EB91IC`, playlist `Unit 13 — Exercises (Roman)`).
2. **Batch wizard is unreachable dead code.** Its `"identify"` checkbox
   would POST `exercise_types: ["identify"]` through to
   `generate_bach_unit_matrix --modes identify` → `import_bach_phrases --mode
   identify`, whose `argparse` `choices` doesn't include `"identify"` — but
   this never happens in practice, because the batch wizard's HTML
   (`#batch-wizard-overlay`, `#batch-type-*`) doesn't exist in any template.
   Out of scope here — see "Scope correction" below.
3. **`analysisType` was never wired for chordal (manual editor) exercises.**
   [`build_chordal_umto_payload`](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/apps/exercises/umto_factory.py)
   never sets a top-level `analysisType` key, unlike the phrase-based factory
   (`UMTO.to_frontend_payload`, which does). The frontend
   ([exercise_definition.js `getAnalysisType()`](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/models/exercise_definition.js))
   defaults to `"roman"` whenever that field is absent. So even after fixing
   bug 1, picking `"figures"` in the manual editor would still quiz Roman
   numerals, not figured bass.

## Scope correction: the batch wizard has no UI

File-mapping during planning found that `#batch-wizard-overlay` and the
`#batch-type-*` checkboxes referenced in `music_controls.js` don't exist in
any template. `initBatchWizard()` itself guards on this:
`if (!overlay.length) { return; }` ([music_controls.js:1229](file:///Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/lab/static/js/src/components/ui/music_controls.js)).
A code comment marks it `"sub-plans 3.2–4.3"` — a planned-but-never-shipped
feature. The batch wizard is currently unreachable by any teacher; its
`"identify"` checkbox bug is dead code, not a live one. **This plan covers
the manual editor only.** Building the batch wizard's missing HTML is a
separate, larger project, out of scope here.

## Goal

One correct mode vocabulary for the manual editor, with no duplicate mapping
logic against the matrix generator:

- **Manual editor**: `play, play_figures, roman, figures,
  figures_unabbreviated, matching, harmonization` (7 modes).
- `"identify"` is removed. Its job — a hidden-answer quiz — is now done
  correctly by `roman` / `figures` / `figures_unabbreviated`.

## Non-goals

- No batch wizard UI work (see scope correction above).
- No batch-generation support for harmonization exercises from Bach phrases.
- No retroactive fix for exercises already saved with the old broken
  `"roman"` semantics (static, always-visible labels) — this only changes
  behavior for exercises saved *after* the fix. Existing exercises keep
  their current (wrong) rendering until manually regenerated.
- No change to the `matching` / `harmonization` exercise *grading* logic —
  only to how the mode gets selected and routed.

## Design

### Shared mode resolver

New module `apps/exercises/utils/teacher_play_modes.py`, sitting next to the
existing `playlist_naming.py` (already the single shared source of truth for
`SUPPORTED_TEACHER_PLAY_MODES` consumed by both `lab/views.py` and
`create_unit_playlist.py`):

```python
from apps.exercises.umto import InteractionMode

def resolve_mode(mode: str) -> dict:
    """Map a teacher-play mode string to its InteractionMode, analysis_type,
    and any mode-driven display overrides. Single source of truth, shared by
    import_bach_phrases.py (Bach corpus) and lab/views.py (manual editor)."""
    if mode in ("play", "play_figures"):
        interaction_mode = InteractionMode.PLAYBACK
    elif mode == "matching":
        interaction_mode = InteractionMode.ANALYSIS_MATCH
    elif mode == "harmonization":
        interaction_mode = InteractionMode.HARMONIZATION
    else:  # roman, figures, figures_unabbreviated
        interaction_mode = InteractionMode.IDENTIFICATION

    display = None
    if mode == "figures":
        analysis_type = "figured_bass"
    elif mode == "figures_unabbreviated":
        analysis_type = "figured_bass_unabbreviated"
    elif mode == "play_figures":
        analysis_type = "figured_bass"
        display = {
            "showFigures": True,
            "figureStyle": "figures_abbrev",
            "analysisRenderer": "notater",
        }
    else:
        analysis_type = "roman"

    return {
        "interaction_mode": interaction_mode,
        "analysis_type": analysis_type,
        "display": display,
    }
```

This is a verbatim extraction of the logic already in
`import_bach_phrases.py` (lines 685-739), with one addition (`harmonization`
→ `InteractionMode.HARMONIZATION`) that's inert for the Bach pipeline since
its own `--mode` `argparse` `choices` list still excludes `"harmonization"`.

### Backend changes

- **`import_bach_phrases.py`**: replace the inline `if/elif` blocks at lines
  685-739 with a single call to `resolve_mode(mode)`. Behavior must be
  byte-for-byte identical — covered by the command's existing test suite,
  which should pass unchanged.
- **`apps/exercises/umto_factory.py`**:
  - `build_chordal_umto_payload` gains an `analysis_type: Optional[str] =
    None` param (default `"roman"`, matching the phrase factory's default)
    and adds `"analysisType": analysis_type` to its returned payload dict.
  - `save_chordal_umto_exercise` gains the same param and threads it
    through to `build_chordal_umto_payload`.
- **`lab/views.py` `AddExerciseView.post`**: replace `_mode_map` and the
  `showRomans`/`showFigures` force-set block with a call to
  `resolve_mode(mode)`. Pass `interaction_mode` into
  `save_chordal_umto_exercise(mode=...)` and `analysis_type` into the new
  param. Merge the resolver's `display` overrides as defaults underneath
  the teacher's own explicit `display` payload (teacher's explicit flags —
  e.g. `showChordLabels`, `showScaleDegrees` — win on conflict; mode-driven
  flags like `showFigures` fill in only what the teacher didn't set).
- **`apps/exercises/utils/playlist_naming.py`**: `SUPPORTED_TEACHER_PLAY_MODES`
  becomes `("play", "play_figures", "roman", "figures",
  "figures_unabbreviated", "matching", "harmonization")`. `_MODE_LABELS`
  gains entries for the 3 new modes (e.g. `"play_figures": "Play + figures"`,
  `"figures_unabbreviated": "Figures (unabbreviated)"`,
  `"matching": "Matching"`); `"identify"` entry removed.

### Frontend changes

- **Manual editor** (`#play-save-mode` `<select>` in
  `lab/templates/play.html:93-100`): replace the current 5 `<option>`s with
  7, matching the new `SUPPORTED_TEACHER_PLAY_MODES`. There is no
  `"identify"`-specific toggle logic to remove — that mode was simply a
  static `<option>` with no JS behavior tied to it. Separately,
  `music_controls.js:1616-1630` already disables/hides `roman`/`figures`/
  `harmonization` options when a MusicXML import isn't routed as
  `"chordal"`; extend that same list to also cover `figures_unabbreviated`,
  `matching`, and `play_figures`, since they need the same chordal-specific
  analysis support.

### Validation / safety net

`SUPPORTED_TEACHER_PLAY_MODES` (7 modes) is enforced by
`AddExerciseView._single_mode`.

## Testing

- `import_bach_phrases` / `generate_bach_unit_matrix` existing test suites
  must pass unchanged after the `resolve_mode` extraction (regression check
  that the refactor is behavior-preserving).
- New test: manual editor save with `mode="roman"` produces
  `InteractionMode.IDENTIFICATION` and `analysisType: "roman"`, and the
  saved exercise's `isChoraleIdentification()` check (frontend) would
  evaluate true — assert on the stored `data["mode"]` and
  `data["analysisType"]` values directly.
- New test: manual editor save with `mode="figures"` produces
  `analysisType: "figured_bass"`.
- New test: manual editor save with `mode="figures_unabbreviated"` produces
  `analysisType: "figured_bass_unabbreviated"`.
- New test: manual editor save with `mode="matching"` produces
  `InteractionMode.ANALYSIS_MATCH`.
- New test: manual editor rejects `mode="identify"` (no longer in
  `SUPPORTED_TEACHER_PLAY_MODES`).
- Manual smoke test (per repo's verification standard for Roman/identify
  exercises, `docs/superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md`):
  save a `"roman"` exercise via the manual editor, open it in the student
  app, confirm `?` slots appear and are answerable.
