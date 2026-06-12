# Phase 1: Generation & Transposition Wizard

> **Combined spec + plan** per decision D5.  
> Settled decisions: read
> [docs/superpowers/specs/2026-06-12-teacher-experience-decisions.md](../specs/2026-06-12-teacher-experience-decisions.md).  
> Prerequisite (implement first):
> [docs/superpowers/plans/2026-06-02-efficient-bach-generation.md](2026-06-02-efficient-bach-generation.md).

---

## Design

### Goal

Let a teacher or superuser take a source (Bach Riemenschneider range, played-in exercise,
or future MusicXML import) and produce a family of typed, transposed, playlist-ready
UMTO exercises **entirely from `/teacher/play/`** — no CLI, no legacy dashboard.

Phase 1 wraps existing backend commands and endpoints; it adds no new algorithms.

---

### Settled decisions that shape this design

| Decision | Impact here |
|----------|-------------|
| **D2** — transpositions are explicit UMTO copies | `generate_transpositions` logic extracted as a service; no runtime playlist transposition |
| **D3** — `is_official` field (Phase 0.5) | Wizard's "save as official" uses the field; factory account stays as convention |
| **Q3 answer** — configurable key set per run | Wizard exposes a key-set picker (all 12 / curated subset / custom list); no hardcoded per-unit map |
| **Q7 answer** — configurable variant bundle, default = play only | Wizard shows checkboxes: ☑ play □ identify □ roman □ figures; teacher opts into more |

---

### Backend command inventory

All generation logic already exists as management commands. The wizard calls
new API endpoints that invoke these commands (or extracted service functions)
synchronously for small jobs.

| Command | Role in wizard |
|---------|----------------|
| `generate_bach_unit_matrix` | Import-once + playlist-many; the bulk Bach path. **Prerequisite plan implements this.** |
| `create_unit_playlist` | Per-unit playlist projection from an imported pool. Called by the matrix command. |
| `generate_transpositions` | Produces transposed UMTO Exercise copies into a target playlist. Extract as a service for the save endpoint. |
| `generate_factory_library` | Produces the full official Bach library. The wizard's "generate official Bach content" action triggers this via the API. |

The "save as official" backend in `lab/views.py` (`saveAsOfficial` + superuser
check) already exists. Work here is verification and hardening, not construction.

---

### Generation manifest model

A `GenerationManifest` is a plain Python dataclass (not a Django model) that
captures a generation request declaratively before execution:

```python
@dataclass
class GenerationManifest:
    source: str                   # "bach_riemenschneider" | "played_in" | "musicxml"
    source_ref: str               # e.g. "1-30", exercise_id, or future file ref
    unit: int
    skill_tags: list[str]
    exercise_types: list[str]     # ["play"] or ["play","roman","figures","identify"]
    key_set: list[str]            # e.g. ["C","G","D","F","Bb","Eb"] or all 12
    playlist_target: int | None   # Playlist pk; None = create new
    is_official: bool
    author_email: str
    dry_run: bool = False
```

`manifest.execute()` calls the relevant commands/service functions idempotently.
`manifest.dry_run_summary()` returns a count estimate without writes.

---

### Transposition service

`generate_transpositions` currently lives as a management command. Extract its
core into:

```python
# apps/exercises/services/transposition_service.py
def generate_transposed_copies(
    source_exercise: Exercise,
    key_set: list[str],
    playlist: Playlist,
    author,
    is_official: bool = False,
) -> list[Exercise]:
    ...
```

The save endpoint (`lab/views.py` `AddExercise`/`saveAsOfficial`) calls this
when the `create_transpositions` flag is set in the payload. The management
command becomes a thin wrapper over the service.

---

### Wizard UI (in `/teacher/play/`)

Three entry points, all living in or launched from `/teacher/play/`:

1. **Save panel** — always visible when an exercise is loaded. Replaces the
   modal-only save flow. Fields: description, unit, mode, target playlist,
   "create transpositions" toggle + key-set picker, "save as official" (superuser
   only). Fixes the mangled "Auto-ne" label and the no-op `_onTargetChosen` call.

2. **Generate Bach content wizard** — modal or side panel launched from a
   "Generate batch" button. Exposes: Riemenschneider range, units, exercise-type
   checkboxes (Q7 answer), key-set picker (Q3 answer), target playlist, dry-run
   preview. Calls `generate_bach_unit_matrix` or `generate_factory_library` via
   the API.

3. **Results review panel** — after generation, shows created exercises with
   preview links, count by type/key, bulk accept/reject/retag.

Background jobs are deferred; Phase 1 targets synchronous execution for small
batches (≤ ~50 exercises). If a job exceeds ~10 s the response redirects to a
polling endpoint.

---

### API endpoints (new)

| Method | Path | Action |
|--------|------|--------|
| `POST` | `/teacher/play/api/generate-manifest/dry-run/` | Return count estimate; no writes |
| `POST` | `/teacher/play/api/generate-manifest/execute/` | Execute manifest; return created ids |
| `POST` | `/teacher/play/api/save-with-transpositions/` | Save single exercise + transposed copies |
| `GET`  | `/teacher/play/api/generation-results/<job_id>/` | Poll for async job status (future) |

All endpoints require `staff` or `superuser`. `is_official=True` requires `superuser`.

---

## Implementation tasks

### Sub-plan 1: `wire-play-save-transpositions`

**Prerequisite:** Phase 0.5 (`is_official` field) must be merged first.  
**Executor:** Tier 2

- [ ] **1.1** Extract `generate_transpositions` core into
  `apps/exercises/services/transposition_service.py::generate_transposed_copies`.
  Management command becomes a thin wrapper. *(Tier 2)*

- [ ] **1.2** Fix the mangled checkbox label in
  `lab/static/js/src/components/ui/target_selector.js`:
  change display string from `"Auto-ne for varied keys"` → `"Create transpositions"`;
  fix payload key from `n` → `create_transpositions`. *(Tier 1)*

- [ ] **1.3** Replace the no-op `console.log` in
  `lab/static/js/src/components/ui/music_controls.js::_onTargetChosen` with
  a real `POST` to `/teacher/play/api/save-with-transpositions/`. *(Tier 2)*

- [ ] **1.4** Implement `POST /teacher/play/api/save-with-transpositions/`
  in `lab/views.py` (or a new `apps/teacher/views.py`):
  - Validate `create_transpositions`, `key_set`, `playlist_id`, `is_official`.
  - Call `generate_transposed_copies` for each key in `key_set`.
  - Set `is_official` on all produced rows if superuser and flag set.
  - Return `{ created: [id, ...] }`. *(Tier 2)*

- [ ] **1.5** Smoke test: save a played-in exercise with transpositions checked;
  confirm correct UMTO rows appear in the target playlist; confirm superuser can
  save as official; confirm non-superuser cannot. *(Tier 2)*

- [ ] **1.6** Unit tests for `generate_transposed_copies`:
  correct key count, UMTO shape, playlist membership, `is_official` flag. *(Tier 1)*

---

### Sub-plan 2: `generation-manifest-model`

**Executor:** Tier 2

- [ ] **2.1** Create `apps/exercises/services/generation_manifest.py` with the
  `GenerationManifest` dataclass described above. *(Tier 2)*

- [ ] **2.2** Implement `manifest.dry_run_summary()` — estimate exercise count
  by type × key_set without DB writes. *(Tier 2)*

- [ ] **2.3** Implement `manifest.execute()`:
  - `source == "bach_riemenschneider"` → calls `generate_bach_unit_matrix`
    (which is the prerequisite plan's command) for each exercise type in
    `exercise_types`.
  - `source == "played_in"` → calls `generate_transposed_copies` for the
    source exercise.
  - Sets `is_official` on all produced rows when `manifest.is_official` and
    author is superuser. *(Tier 2)*

- [ ] **2.4** Implement
  `POST /teacher/play/api/generate-manifest/dry-run/` and
  `POST /teacher/play/api/generate-manifest/execute/`
  in `apps/teacher/views.py` (create file if absent). *(Tier 2)*

- [ ] **2.5** Implement
  `POST /teacher/play/api/suggest-units/` in `apps/teacher/views.py`:
  - Accept a CIR score (or an existing `exercise_id`) in the request body.
  - Run `analyze_chunk_skills` (from `skills_analyzer.py`) on the score to get
    detected skill tags.
  - Load `apps/exercises/data/music_theory_taxonomy_with_branches.json`; for
    each unit entry collect its expected skill tags; rank units by intersection
    size with detected tags descending.
  - Return `{ skill_tags: [...], suggested_units: [9, 11, 16, ...] }` — ordered
    by match score, top ~3–5.
  - Caller (wizard UI) pre-checks the top suggestions; teacher confirms or
    edits before save. *(Tier 2)*

- [ ] **2.6** Unit tests for `suggest-units`: known skill-tag set → expected
  unit ranking; empty score → empty suggestions (no crash). *(Tier 1)*

- [ ] **2.7** Unit tests for manifest dry run and execute paths. *(Tier 1)*

---

### Sub-plan 3: `generation-wizard-ui`

**Executor:** Tier 2 (implementation); Tier 3 (component design if judgment needed)

- [ ] **3.1** Add a persistent **save panel** section to `/teacher/play/` replacing
  the modal-only save flow. Fields: description, unit tag(s), mode, target playlist
  (existing or new), "Create transpositions" toggle + key-set multi-select,
  "Save as official" (superuser only, reads `is_official` from Phase 0.5).
  Unit field is a required multi-select (not optional). Follows existing
  teacher-app UI conventions (D5 — no design gate). *(Tier 2)*

- [ ] **3.1a** When a score is loaded or a played-in exercise is ready to save,
  call `POST /teacher/play/api/suggest-units/` automatically. Pre-check
  suggested units in the unit multi-select with a subtle "(suggested)" label.
  Teacher can accept, add, or remove units before saving. Unit field must have
  at least one value to enable the save button. *(Tier 2)*

- [ ] **3.2** Add a **"Generate batch" button** to `/teacher/play/` launching a
  modal wizard with:
  - Source: Bach Riemenschneider range (text input with validation)
  - Unit: number input
  - Exercise types: checkboxes `[☑ Play] [□ Identify] [□ Roman] [□ Figured bass]`
    (Q7: play default)
  - Key set: multi-select or text input for comma-separated keys; presets
    "All 12", "Flat keys (C,F,Bb,Eb,Ab,Db)", "Sharp keys (C,G,D,A,E,B)"
    (Q3: configurable)
  - Target playlist: select existing or create new
  - Dry-run estimate shown before submit *(Tier 2)*

- [ ] **3.3** Wire "Generate batch" submit to
  `POST /teacher/play/api/generate-manifest/dry-run/` on change,
  then `POST /teacher/play/api/generate-manifest/execute/` on confirm. *(Tier 2)*

- [ ] **3.4** Show inline validation: non-superuser cannot set "Save as official";
  empty key set blocked; Riemenschneider range validated client-side. *(Tier 1)*

---

### Sub-plan 4: `generation-results-review`

**Executor:** Tier 2

- [ ] **4.1** After execute returns, render a **results panel** in `/teacher/play/`
  showing: exercise count by type, count by key, list of created exercise
  descriptions with preview links (opens in `/teacher/play/?exercise=<id>`). *(Tier 2)*

- [ ] **4.2** Add bulk-action controls: "Accept all", "Reject all" (delete),
  per-row retag (unit/mode), per-row delete. Bulk actions call existing
  exercise CRUD endpoints. *(Tier 2)*

- [ ] **4.3** "Regenerate selected" calls the manifest execute endpoint again
  with `overwrite=True` for the selected subset. *(Tier 2)*

---

### Sub-plan 5: docs and registration

**Executor:** Tier 1

- [ ] **5.1** Register `generate_manifest` API endpoints in
  `apps/exercises/management/commands/list_exercise_generators.py` if applicable,
  or add to `docs/management_commands.md` under a new "Generation wizard" section. *(Tier 1)*

- [ ] **5.2** Update `docs/neon_content_generation_runbook.md` to note that
  the wizard UI supersedes the manual shell loop for standard runs; keep the
  CLI as the escape hatch. *(Tier 1)*

- [ ] **5.3** Document the `GenerationManifest` dataclass and the two API
  endpoints in a new section of `docs/UMTO_GUIDE.md` or a new
  `docs/generation_wizard.md`. *(Tier 1)*

---

## Prerequisite execution order

1. **Phase 0.5 merged** (`is_official` field live) — gates sub-plans 1.4 and 3.1.
2. **2026-06-02-efficient-bach-generation.md tasks complete** (`generate_bach_unit_matrix`
   and `deduplicate_bach_phrases` implemented, tested, registered) — gates sub-plan 2.3.
3. Sub-plans 1, 2, 3, 4 can proceed in parallel once prerequisites are met.
4. Sub-plan 5 (docs) last, after implementation smoke tests pass.

---

## Completion definition

Phase 1 is complete when:
- A teacher at `/teacher/play/` can save a played-in exercise with transpositions and see the
  transposed UMTO copies land in the target playlist, without CLI.
- A superuser can mark those rows as official from the same panel.
- A superuser can trigger Bach batch generation (Riemenschneider range, units, exercise types,
  key set) from the wizard, see a dry-run estimate, confirm, and review generated exercises with
  preview links — no CLI, no legacy dashboard.
