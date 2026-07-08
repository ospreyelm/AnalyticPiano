# HarmonyLab Repository Instructions

This is the authoritative repository-wide instruction file. Tool-specific
instruction files must point here rather than duplicate project policy.

# Before writing code always check:
1. is there code in the repo that already does this?

2. Can we use existing package or external code to do the same thing?

3. We want to remove unnecessary code and complexity to keep the repo maintainable, clean, and efficient.

## Current product direction

The previous seven-item teacher-experience priority list is complete.

The proposed Assignment Slot Foundation and individualized assignment-recipe
architecture are **under consideration, not authorized for implementation**.
They represent a substantial refactor, and the product owner wants additional
time to evaluate the direction before committing to it.

Do not write an implementation plan, add models, change routing or submission
identity, migrate playlists, or begin any assignment-architecture phase unless
the product owner explicitly reprioritizes and approves that implementation in
a later request.

The narrow Phase 1 design is retained for evaluation:

[docs/superpowers/specs/2026-06-19-assignment-slot-foundation-phase1-design.md](docs/superpowers/specs/2026-06-19-assignment-slot-foundation-phase1-design.md)

The broader assignment-recipe document is architectural exploration and roadmap
context only:

[docs/superpowers/specs/2026-06-19-individualized-assignment-recipes-design.md](docs/superpowers/specs/2026-06-19-individualized-assignment-recipes-design.md)

Neither document is a current implementation directive. The `selection_mode`
and `target_length` portions of
[docs/superpowers/specs/2026-06-18-playlist-selection-mode-design.md](docs/superpowers/specs/2026-06-18-playlist-selection-mode-design.md)
are superseded. Its orphan-exercise findings remain separate valid work.

Until a new priority is explicitly approved, work only on tasks directly
requested by the product owner. Do not infer that the next roadmap phase should
begin automatically.

## Non-negotiable architecture rules

- New Exercise rows must use UMTO. Legacy `chorale`,
  `chorale_identification`, and raw-CIR shapes are frozen.
- Create exercises through `save_umto_exercise` or another sanctioned UMTO
  factory. Never set `HARMONYLAB_ALLOW_LEGACY_EXERCISE=1` in production, CI,
  tests, or ordinary feature work.
- Work started in `/teacher/...` stays in the teacher app. Do not route normal
  teacher workflows through `/dashboard/...`.
- Student exercise delivery must converge on the modern student player.
- Do not add new business logic to `lab/views.py`; extract or use focused,
  app-neutral services.
- The taxonomy is the source of truth for curriculum and assignable musical
  concepts. Do not create parallel Python and JavaScript allowlists.
- Backend music21 boundaries must normalize stored HarmonyLab keys through
  `apps.exercises.utils.key_normalization.harmony_key_to_music21()`.
- Before modifying music-theory analysis, generation, grading, taxonomy
  analysis values, or music21 boundary code, state the relevant musical rule
  from first principles before trusting existing implementation or docs. Read
  [docs/music-theory-canon.md](docs/music-theory-canon.md). If code, tests,
  docs, generated content, or agent instructions appear to contradict either
  first-principles music theory or the canon, surface the contradiction to the
  product owner instead of silently preserving existing behavior as project
  convention. For each theory-sensitive change, add or verify at least one
  distinguishing example that would fail under the incorrect rule.
- The authoritative figured-bass **required-vs-allowed realization** table is
  [`apps/exercises/harmonization/figure_realization.py`](apps/exercises/harmonization/figure_realization.py)
  (`TABLE`). A figure names intervals; it does not require all of them. Do not re-derive required
  tones ad hoc or treat every named interval as required. Changes are music-theory changes: get
  expert sign-off, add a `theory_golden/figure_realization.json` case, and keep
  `docs/FIGURED_BASS.md` in sync.
- Before modifying features, controllers, shared algorithms, or routing, read
  [docs/redundancy_analysis_report.md](docs/redundancy_analysis_report.md).
- Pitch spelling must always carry octave (`Pitch.nameWithOctave`, never
  `Pitch.name`) through any derive/transpose/re-serialize step — losing it
  can silently pick the wrong bass and corrupt every figure/Roman numeral
  downstream. Never silently guess a missing spelling from bare pitch-class;
  raise an error instead. See "Pitch spelling and octave are load-bearing
  data" in [docs/music-theory-canon.md](docs/music-theory-canon.md).

UMTO references:

- [docs/UMTO_GUIDE.md](docs/UMTO_GUIDE.md)
- [apps/exercises/umto_schema.json](apps/exercises/umto_schema.json)
- [docs/superpowers/specs/2026-04-23-umto-consistency-design.md](docs/superpowers/specs/2026-04-23-umto-consistency-design.md)

## Replacement and retirement policy

Follow [docs/architecture/engineering-principles.md](docs/architecture/engineering-principles.md)
for architectural changes. In summary:

- Identify which existing paths a new authoritative implementation replaces.
- Include redirects, migration, and deletion conditions in the design and plan.
- Compatibility code must state its removal condition and must not become a
  second permanent source of truth.
- Prefer one shared service over parallel logic in views, commands, and
  frontend entry points.
- Do not add substantial responsibility to existing oversized modules; extract
  a focused module or service while touching them.
- A new model must replace or narrow an existing model responsibility.
- Feature completion includes retirement work when safe, not only addition.

## Read-before-modifying guide

| Area | Required reading |
|---|---|
| Assignment delivery, adaptive selection, submissions | [Phase 1 slot design](docs/superpowers/specs/2026-06-19-assignment-slot-foundation-phase1-design.md) |
| Later assignment recipes, quotas, taxonomy metadata | [Assignment architecture roadmap](docs/superpowers/specs/2026-06-19-individualized-assignment-recipes-design.md) |
| Cross-language algorithms or legacy/modern routes | [Redundancy analysis](docs/redundancy_analysis_report.md) |
| Roman exercises from Clausulae | [Roman-from-Clausulae lesson spec](docs/superpowers/specs/2026-05-26-roman-from-clausulae-lessons.md) |
| Bach/Riemenschneider bulk generation or deduplication | [Efficient Bach generation plan](docs/superpowers/plans/2026-06-02-efficient-bach-generation.md) |
| Refresh/backfill code that passes keys to music21 | [Music21 key normalization plan](docs/superpowers/plans/2026-06-02-music21-key-normalization.md) |
| Chorale grading, timeline, or rendering | [Chorale system guide](docs/architecture/chorale-system.md) |
| Implementing in a previously solved problem area | [Solutions knowledge base](docs/solutions/) (check before re-deriving; capture new learnings via `/ce-compound`) |
| Deployment | Deployment section below |

## Documentation requirements

Every pull request must update documentation for these changes:

### Student-facing feedback

1. Add or modify the entry in
   `lab/static/js/src/config/feedback_catalog.js`.
2. Update [docs/feedback_catalog.md](docs/feedback_catalog.md).
3. Route student messages through `feedbackService.emit(id, opts)`.

Do not broadcast `EVENTS.BROADCAST.NOTIFICATION` from feature code and do not
use `window.alert` for student feedback.

### New or modified exercise type

Update [docs/exercise_types.md](docs/exercise_types.md), including the summary
table.

### New management command

1. Update [docs/management_commands.md](docs/management_commands.md).
2. Register the command in
   `apps/exercises/management/commands/list_exercise_generators.py`.

### Significant feature

For work spanning more than one file or session, create a checked-task plan
before implementation:

`docs/superpowers/plans/YYYY-MM-DD-feature-name.md`

Create a design spec when architecture or data-shape decisions are involved:

`docs/superpowers/specs/YYYY-MM-DD-feature-name-design.md`

## Pull request target

Pull requests must target `avnerdorman/HarmonyLab`, base `master`, unless the
user explicitly requests otherwise:

```bash
gh pr create --repo avnerdorman/HarmonyLab --base master
```

Do not let GitHub CLI infer the target from the `upstream` remote, which may
point to `ospreyelm/AnalyticPiano`.

## Deployment safety

Never run `fly deploy` from the main repository root. Deploy from:

```bash
cd /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/.worktrees/master-run
git pull
fly deploy
```

This prevents nested worktrees from entering the Docker build context.

For a database restore:

```bash
fly proxy 5433:5432 -a monteverdi-db

pg_restore -h localhost -p 5433 -U postgres -d postgres --clean --if-exists \
  /Users/adorman/Library/CloudStorage/Dropbox/Codebases/HarmonyLab-1/local_db.dump
```

Use port `5433` to avoid a local PostgreSQL conflict. Ignore harmless
`role adorman does not exist` warnings.

### `generate_bach_unit_matrix` / `import_bach_phrases` safety

- `import_bach_phrases` **fully replaces** `Exercise.skill_tags` on overwrite
  (`umto_factory.py` `save_umto_exercise`, `ex.skill_tags = list(skill_tags)`
  — not a merge). The full Bach corpus is tagged with every unit in a single
  `--units` list at import time; units 1-14 tags get re-detected from chord
  content on every reimport, but `unit:19`/`unit:20` (modulation) are **not**
  content-derived — they only exist because they were in the `--units` list
  passed at import time.
- Always pass the **full** unit list,
  `--units 9,10,11,12,14,16,17,18,19,20`, even when only regenerating one or
  two units' playlists. A scoped subset silently strips the missing units'
  tags from shared phrase rows (confirmed incident: scoped `--units 16,17,18`
  wiped `unit:19`/`unit:20` from ~1270 shared rows on local dev). `--modes`
  scoping is safe — each mode is a separate `Exercise` row.
- If only playlist *membership/selection* logic changed (e.g. a filter in
  `create_unit_playlist.py`) and exercise content/tags are unaffected, use
  `--playlist-only --skip-refresh` to skip the music21 reimport entirely. This
  is DB-only (no corpus parsing, no chordify, no cadence detection) and runs
  in seconds instead of the ~6 hours a full reimport takes. `--skip-refresh`
  also avoids `backfill_skill_tags`/`backfill_raw_roman_numeral`, which
  iterate every exercise platform-wide, not just the touched scope.
- See [Efficient Bach generation plan](docs/superpowers/plans/2026-06-02-efficient-bach-generation.md)
  for the full command design.

## Repository hygiene

- Preserve unrelated user changes in dirty worktrees.
- Use isolated worktrees for feature work.
- Do not add new one-off batch scripts when an approved service or management
  command plan exists.
- Keep generated profiles, dumps, console logs, and local audit output out of
  tracked source.
- Archive or mark superseded plans; do not leave competing active directions.
- Current policy belongs here. Historical implementation detail belongs in
  `docs/`, not in always-loaded agent instructions.

## Repository Architecture Guardrails

### Code Generation Rules
- **File Length Limit:** No single JavaScript/TypeScript file should exceed 400 lines of code. If a file approaches this limit, it must be broken down into sub-modules.
- **Separation of Concerns:** Keep UI components, business logic/hooks, and pure utility functions in separate files.
- **Imports:** Always use explicit, traceable imports. Avoid deeply nested relative paths where aliases are available.

### Refactoring Workflow
1. For any refactor, extract pure utility functions first into a `/utils` or `/helpers` directory.
2. Extract sub-components or local state hooks next.
3. Keep the original file as a clean "orchestrator" that imports these new modules.
4. Do not delete original code until the new modules are verified and linted.
