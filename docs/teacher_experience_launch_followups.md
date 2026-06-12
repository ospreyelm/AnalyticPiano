# Teacher Experience Launch Follow-ups

Observed during the June 2026 production rollout of the course wizard, factory
library, and student join flow.

Meta-plan for addressing these follow-ups:
[docs/superpowers/plans/2026-06-12-teacher-experience-meta-plan.md](docs/superpowers/plans/2026-06-12-teacher-experience-meta-plan.md)

## P0/P1 fixes before public launch

1. **Build a new backend content editor for official curriculum.**
   - The old dashboard edit screens are still usable but not aligned with the
     new teacher experience.
   - Needed capabilities:
     - edit course/playlists/exercises without dropping into legacy dashboard
     - inspect factory ownership and unit tags
     - manage official vs. teacher-authored content
     - review playlist membership/order, mode, unit, and public visibility
     - expose safe bulk operations such as promote-to-factory and retag

2. **Build a curriculum generation wizard.**
   - Teachers/admins should be able to choose one curriculum target and generate
     the needed exercise variants from it.
   - Wizard should support:
     - exercise type selection (identify, play, figures, Roman numerals,
       harmonization, analysis-match, etc.)
     - unit/skill target selection
     - mode variants from one source
     - transposition generation
     - playlist creation and ordering
     - dry-run preview before writes
     - factory/save-as-official ownership path for superusers

3. **Make transpositions first-class in the authoring workflow.**
   - Current hand-authored loop requires knowing when to run
     `generate_transpositions`.
   - Desired behavior: after authoring/import, the UI can generate, preview,
     and attach transposed variants to the correct official playlist.

4. **Add a course-focused student home section.**
   - Current behavior: joined students still see the full curriculum first.
   - Desired behavior: show "My courses" or "Assigned by your teacher" above
     the curriculum, with course title, current/next due work, and direct links
     to assigned playlists.
   - Keep the full curriculum available below as optional exploration.

5. **Add an explicit "View as student" workflow for teachers.**
   - From `/teacher/courses/<id>/`, teachers should be able to preview the
     student-facing course path without creating a separate test account.
   - Preview should show exactly what enrolled students see: open/locked units,
     due dates, playlist order, and links.

6. **Make roster/group creation available after course creation.**
   - Current issue: if the wizard course is created without a group, the course
     detail page only says "No groups linked to this course."
   - Add controls to create a group, attach an existing group, copy join link,
     and remove/unlink groups directly from the new teacher course page.

7. **Show the join code/link prominently on the course page.**
   - The teacher should not need to know old dashboard navigation.
   - Roster panel should show:
     - join code
     - copyable `/s/join/?code=...` URL
     - student count
     - recent joins

8. **Improve course creation landing and edit flow.**
   - Fixed during rollout: wizard now redirects to `/teacher/courses/<id>/`
     instead of legacy `/dashboard/courses/<id>/`.
   - Follow-up: remove remaining legacy-dashboard escape hatches unless they
     are explicitly labeled as advanced/admin-only.

9. **Fix mode labeling for generated playlists.**
   - Some Unit 1 playlists show mode `other` because they lack `mode:*` tags and
     name heuristics only catch Roman/figures/play.
   - Add explicit mode tags during generation or expand `_mode_from_tags()` to
     classify note-name/name/play/identification lanes cleanly.

## Rollout and operations improvements

1. **Clarify factory seeding vs. existing copied content.**
   - `generate_factory_library --report` only counts playlists owned by
     `factory@monteverdi.app`.
   - Existing production-ready playlists under `avnerdorman@gmail.com` can be
     valid but invisible to the factory report/wizard.
   - Add a management command for "promote existing official playlists to
     factory" instead of running the expensive Bach generator.

2. **Add a preflight report for playlist ownership.**
   - Command should report unit-tagged playlist counts by author, e.g.:
     `unit:9 -> avnerdorman@gmail.com: 6, factory@...: 0`.
   - This would have prevented confusing "0 coverage" output when content
     existed under a different owner.

3. **Document Neon branch targeting clearly.**
   - The child branch rollback point and production branch have different
     connection strings.
   - Add a checklist item: verify `factory@monteverdi.app` and unit playlist
     counts from inside the Fly container before testing the site.

4. **Avoid full Bach regeneration when not needed.**
   - Full `generate_factory_library` triggers `generate_bach_unit_matrix` over
     Riemenschneider `1-371` and four modes.
   - This is expensive in time and Neon network transfer.
   - Add documented recovery paths:
     - promote/copy existing playlists
     - run light units only (`1-5`, `B1`)
     - run Bach matrix manually with smaller Riemenschneider ranges

5. **Make `import_factory_curated` tolerate a missing directory.**
   - Current behavior: it errors if `data/factory_curated/` is absent.
   - For fresh deployments with no curated exports yet, it should warn and
     return success, or the runbook should explicitly skip it.

6. **Improve deploy instructions.**
   - `master-run` was referenced but did not exist.
   - Add a documented setup command:
     `git worktree add --detach .worktrees/master-run origin/master`
   - Clarify that commits happen in the main checkout, while deploy happens
     from the clean worktree.

7. **Add a production smoke command bundle.**
   - From Fly shell, one command should check:
     - factory user exists
     - factory unit coverage
     - sample teacher course has PCO rows
     - sample group has members
     - student is enrolled in the group

## Bugs found and fixed during rollout

1. **Wizard inline JSON was HTML-escaped.**
   - Symptom: browser console `Unexpected token '&'`.
   - Cause: `units_json` embedded without `|safe`.
   - Fixed by rendering `unitsJson: {{ units_json|safe }}` and adding a test.

2. **Course detail inline data had the same serialization risk.**
   - Course page could render but JS data could be malformed.
   - Fixed by serializing `groups_json`, marking JSON blobs safe, and quoting
     string fields with `escapejs`.

3. **Wizard success redirected to legacy dashboard.**
   - Fixed redirect to `/teacher/courses/<id>/`.

4. **Factory playlists existed but under the wrong owner.**
   - Production had unit-tagged playlists under `avnerdorman@gmail.com`.
   - The new wizard/report only counted `factory@monteverdi.app`.
   - Resolved by reassigning official public curriculum playlists to the
     factory account.

5. **`/teacher/play/` save-dialog smoke remains required.**
   - Checklist item still to verify:
     `/teacher/play/` save dialog can save an exercise with description +
     unit tag into a new playlist, and a superuser sees "Save as official".
   - This should be part of the backend-editor/authoring smoke suite because it
     is the entry point for hand-authored official content.

## Data and generator quality follow-ups

1. **Investigate `Skills analysis failed: Cannot make a step out of '-'`.**
   - The importer catches this warning and continues, so it is not
     deployment-blocking.
   - Still add logging for the exact Riemenschneider number, phrase, key, and
     mode so the malformed music21 key/pitch source can be fixed.

2. **Audit old local/dev content.**
   - Production contains unit playlists under `avner-local2025@localhost`.
   - Decide whether to delete, archive, or leave them as non-factory content.

3. **Define official content ownership policy.**
   - Is "official" determined by factory owner, public flag, skill tags, or a
     future explicit field?
   - Today it is inferred from `authored_by=factory@monteverdi.app`, which works
     but is easy to miss during database restores.

4. **Add tests for production-like special characters in embedded JSON.**
   - Course/playlist names include em dashes, ampersands, and accented symbols.
   - Keep regression coverage for safe script embedding in wizard/detail pages.

## UX polish

1. **Teacher course detail should provide direct student links.**
   - Add "Open student view" links for each playlist/unit.
   - Add "Copy assignment link" per row.

2. **Make empty states actionable.**
   - Roster empty state should include "Create a group" and "Attach existing
     group."
   - Activity empty state should explain it will populate after students play
     assigned exercises.

3. **Student join success should be explicit.**
   - After joining, show "You joined <course/group>" and a direct link to first
     assigned work.
   - Avoid dropping students onto the generic curriculum with no confirmation.

4. **Course dashboard should distinguish assigned vs. exploratory work.**
   - Use visual chips or sections so students can tell what is required for a
     course versus general curriculum access.
