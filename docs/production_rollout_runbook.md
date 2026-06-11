# Production Rollout Runbook — Teacher Experience (2026-06)

Order of operations for taking the course wizard + factory library to
production (Fly app `monteverdi`, Neon Postgres). Seeding never runs in the
Fly release command — it stays in GitHub Actions / manual runs.

## 1. Merge + deploy code

1. Merge the feature branch PR to `master` (CI must be green — includes the
   Django-runner step and the factory dry-check).
2. Deploy to Fly as usual (manual `flyctl deploy`). The release command only
   runs `migrate` + `createcachetable`; migration `exercises.0065` adds
   nullable `Course.start_date/end_date` — safe, no backfill needed.
3. Confirm `SENTRY_DSN` secret is set on Fly (`flyctl secrets list`) —
   `harmony/settings/fly.py` wires Sentry when present.

## 2. Seed the factory library (Neon)

1. **Snapshot first:** create a Neon branch of the production database
   (dashboard → Branches) — this is the rollback point.
2. Run the `Generate factory library (Neon)` workflow (workflow_dispatch)
   against the **Neon branch** connection string first if you want a rehearsal,
   or directly against prod after the snapshot:
   - inputs: `units` empty (all) or a chunk like `1-5`, `skip_refresh: true`
     for the first pass, `author: factory@monteverdi.app`.
   - Steps run: `ensure_factory_account` → `import_factory_curated --update`
     → `generate_factory_library`.
3. Verify: re-run the workflow with `dry_run: true` … or locally against the
   prod DATABASE_URL run:
   ```bash
   python manage.py generate_factory_library --report
   python manage.py generate_factory_library --verify
   ```
4. Optional refresh pass (key-normalization fix makes this safe):
   `skip_refresh: false` re-run, or `backfill_skill_tags` via console.

## 3. Smoke checklist (production)

- [ ] `/teacher/courses/new/` as teacher account: wizard lists units with
      factory playlist counts (non-zero after seeding).
- [ ] Create a test course with 2 units + a student group → lands on course
      page; PCO rows have expected publish/due dates.
- [ ] `/teacher/courses/<id>/`: reorder a row, edit a date, re-spread — all
      persist after reload. Dashboard course edit page still renders the same
      course.
- [ ] Student account joins via `/s/join/?code=...` from the roster panel
      copy-link.
- [ ] Student home shows due chips on the course's units; unpublished unit
      shows "Opens …".
- [ ] Student plays one exercise from a course playlist → mark appears in the
      course activity view (and `performance_dict`).
- [ ] `/teacher/play/` save dialog: save an exercise with description + unit
      tag into a new playlist; superuser sees "Save as official".
- [ ] Old dashboard pages unchanged (spot check `/dashboard/courses/`).

## 4. Hand-authored (curated) content loop

Author in `/teacher/play/` (Save as official) or `import_musicxml` locally →
`generate_transpositions` if needed → `export_factory_curated` → commit
`data/factory_curated/` → the seeding workflow imports it on prod.

## 5. Rollback

- Code: `flyctl releases` → roll back image.
- Data: restore the Neon branch snapshot taken in step 2.1 (content tables
  only touched by seeding: exercises_exercise, exercises_playlist,
  exercises_exerciseplaylistordered + factory user row).

## Known deferred items

- Browser-level smoke of the wizard/management pages pre-merge (dev server
  serves the main checkout, not the worktree) — covered by the prod checklist.
- Dedupe of avnerdorman-authored generator content after factory copies are
  confirmed in use (`deduplicate_bach_phrases`-style audit).
- Local full seed run (hours of music21) — chunk with `--units`.
