# Teacher Experience — Design Brief & Discovery Context (2026-06-08)

> **Status: DISCOVERY / DESIGN-FIRST.** This is *not* a plan. It seeds a brainstorming + design session. The goal of the session is to conceptualize the teacher experience before any implementation. Start with `superpowers:brainstorming` (or `compound-engineering:ce-brainstorm`). Resist jumping to tasks.

## The ask (in the author's words)

> Bring all of [the analysis review / approval / override / respelling flow] into the Play view after Save is pressed — so it's all in one place and easily manageable. This coincides with designing the teacher dashboard. It's really a design-first task: conceptualize the teacher experience, and also help curate the core curriculum and make it easily accessible to teachers.

Three intertwined threads:
1. **Unify authoring + review in the Play view** — after Save, the teacher reviews/approves/corrects/respells *in place*, instead of being bounced to a separate workbench panel.
2. **Design the teacher dashboard** — the home base for authoring, curating, and assigning.
3. **Curriculum curation & access** — make the core curriculum legible and easy for teachers to adopt, sequence, and assign.

## Why now

We just shipped the *mechanics* of analysis approval/override/respelling (PR #90), but the *experience* is split across surfaces and bolted onto a bulk-import workbench. Before building more, design the unified teacher flow so the plumbing serves a coherent experience rather than the reverse.

## The central reframe: from power-user tooling to any-teacher product

> The current dashboard for exercises and playlists is quite complex and was built by and for [the author] and Rowland. This needs to become something that works for **any** teacher.

This is the defining constraint of the whole effort. The existing dashboard is **expert tooling shaped by its two original users** — it assumes deep knowledge of the data model, the taxonomy, exercise types, and the import pipeline. The redesign targets a fundamentally different user: a music teacher who knows pedagogy but not the internals.

Implications to hold throughout the session:
- **Design for the median teacher, not the power user.** The power-user workflows (bulk MusicXML import, projection engine, raw analysis editing) should still be reachable, but must not define the default surface or the mental model.
- **Progressive disclosure.** Lead with curriculum + assignment; reveal authoring/import depth on demand.
- **Pedagogical vocabulary over system vocabulary.** "Unit," "skill," "lesson," "assignment" — not "UMTO row," "projection," "score_kind," "analysis slice."
- **Sane defaults that hide the data model.** A teacher should get a usable exercise/assignment without choosing exercise types, input modes, or analysis settings.
- Treat the existing complex dashboard as **prior art and a power-user fallback**, not the thing to incrementally simplify. Design the any-teacher experience first; then decide what of the old surface survives, gets demoted, or retires.

---

## Current state (what exists today)

### What PR #90 just added (the mechanics to be re-homed)
- **Chordal note spelling** is now key-aware and override-able; Play-save captures spelling. Roman figures render stacked (braced legacy tokens).
- **Soft approval gate:** on Save, analysis is auto-generated, `analysis_review_status = "generated"`, and the teacher is *routed to a separate review panel*; the edit page shows a "Needs review" / "Reviewed" badge.
- **Review/override/respell UI** lives in the **dashboard workbench review panel** (`/dashboard/workbench/?review=<id>`): edit Roman numerals (with a figure-token picker), figured bass, local key; respell notes per chord; Save marks `reviewed`.
- Key files: `apps/dashboard/views/api_workbench.py` (`api_chordal_analysis_review`), `apps/dashboard/templates/dashboard/workbench.html` (review panel JS), `lab/static/js/src/components/ui/music_controls.js` (save → route), `lab/static/js/src/components/music/play_sheet.js` (`dataForSave`), `apps/exercises/umto_factory.py` (`save_chordal_umto_exercise`).
- Behavioral doc: `docs/exercise_types.md` → "Chordal Play-saved exercises". Plan: `docs/superpowers/plans/2026-06-08-chordal-analysis-approval-respelling.md`.

### The surfaces a teacher touches today (fragmented)
| Surface | URL | Purpose | Notes |
|---|---|---|---|
| Teacher Play view | `/teacher/play/` (`lab.views.PlayView`) | Author chords, Save as exercise | The natural authoring home. Route history: `docs/superpowers/specs/2026-06-07-teacher-play-route-design.md`. |
| Dashboard exercises list | `/dashboard/exercises/` | Browse/manage authored exercises | |
| Edit exercise | `/dashboard/exercises/<id>/` | Metadata + "Review/Edit Analysis" link + status badge | |
| Workbench | `/dashboard/workbench/` | Bulk MusicXML import → project to types; **also hosts the analysis review panel** | `docs/dashboard_workbench.md`; review design `docs/superpowers/specs/2026-06-07-workbench-chordal-analysis-review-design.md`. |
| Playlists | (dashboard) | Group exercises into units/assignments | |

The review panel currently lives in the *bulk-import* tool — an awkward home for single-exercise post-save review.

### Prior design docs to read before the session
- **Dashboard/workbench:** `docs/dashboard_workbench.md`; review design `docs/superpowers/specs/2026-06-07-workbench-chordal-analysis-review-design.md`.
- **The author's existing "simplify the dashboard" doc** — *(author: link the exact file here; not located during this brief. Likely a candidate to fold into this effort.)*
- **Teacher Play route:** `docs/superpowers/specs/2026-06-07-teacher-play-route-design.md`; backlog `docs/superpowers/plans/2026-06-07-chordal-umto-backlog.md`.
- **Curriculum:** `docs/superpowers/specs/2026-04-18-curriculum-architecture.md`, `docs/superpowers/specs/2026-05-19-curriculum-roadmap.md`, `docs/unit_*_*.md`, `music_theory_taxonomy_with_branches.json` (+ `build_unit_allowed_answers`). Note CLAUDE.md's `create_unit_playlist` blocker (no end-to-end unit-playlist command yet).
- **UMTO canonical model:** `docs/UMTO_GUIDE.md` — all new exercises are UMTO.

---

## Design questions to drive the session (not requirements)

### Thread 1 — Unify authoring + review in Play view
- After Save, what's the right *moment and form* for review? Inline panel under the staff? A right rail? A modal? A staged "draft → review → publish" state machine on the Play surface itself?
- Should "Save" even be the trigger, or should authoring be continuous (autosave draft) with an explicit "Approve/Publish" step that is the real gate?
- Live preview: the dashboard page lacks the RequireJS/VexFlow stack (why PR #90 used text preview). The Play view *already has* the full renderer — does re-homing review into Play unlock true live notation preview "for free"? (Likely yes — worth validating early; it may be the strongest argument for the move.)
- What happens to the standalone workbench review panel — retire it, or keep it for bulk-import review while Play handles single-exercise authoring?
- Respelling UX in-context: per-note click-to-respell on the actual notation (now feasible in Play) vs. the text field stopgap.
- Override UX: the figure-token picker exists; in Play, could the teacher click a chord to set/correct its Roman numeral against live notation?

### Thread 2 — Teacher dashboard
- What is the teacher's primary job-to-be-done on landing? (Author? Assign? Monitor? Curate?) Design the dashboard around that verb.
- Information architecture: how do "my exercises," "the core curriculum," "my playlists/assignments," and "student progress" relate and nest?
- How does the authored-then-reviewed exercise flow into a playlist/unit without the current manual steps?
- Where does bulk import (workbench) sit in a simplified IA — power-user corner vs. first-class?

### Thread 3 — Curriculum curation & accessibility
- What *is* the "core curriculum" as a teacher-facing object? (Units 1–N with goals, skills, sample exercises?) Source of truth: `music_theory_taxonomy_with_branches.json` + unit docs.
- How does a teacher browse, preview, adopt, reorder, and assign curriculum without CLI/management commands? (Ties to the missing `create_unit_playlist` command — a design-level requirement, not just a backend chore.)
- How do teacher-authored exercises (Play view) and curated curriculum coexist — extend, override, supplement?
- Skill tags / taxonomy: surface them to teachers for filtering/assembly, or keep internal?

---

## Constraints & non-negotiables (carry into design)
- **UMTO is the canonical exercise representation** — all new exercises are UMTO (see CLAUDE.md). Design within it.
- **Agent-native parity** (CLAUDE.md): any action a teacher can take, an agent should be able to take too.
- **Student-facing messaging** routes through `feedbackService.emit` + the feedback catalog; **never `window.alert` for students.** (Teacher tooling currently uses alerts — revisit as part of the experience design.)
- **No new legacy exercise shapes.** Review/approval state already lives at `umto.metadata.analysis_review_status`.
- Performance: the dashboard had an N+1 history (see MEMORY / PR #74); per-row status/progress on lists needs batching (why PR #90 scoped the review badge to the edit page only).

## Explicit non-goals for the *design* session
- Don't write implementation tasks. Produce a design spec + prioritized concept, then a plan in a follow-up.
- Don't pick component libraries / pixel specs before the experience and IA are agreed.

## Suggested outputs of the session
1. A teacher-experience concept (the unified Play-centric authoring→review→publish flow + dashboard IA + curriculum surface), captured as a design spec under `docs/superpowers/specs/`.
2. A short decision log on the open questions above.
3. Only then: a phased implementation plan (likely separable: (a) re-home review into Play, (b) dashboard IA, (c) curriculum browser + `create_unit_playlist`).

---

## Ready-to-paste kickoff prompt for the new session

> I want to design the teacher experience for Monteverdi Music — design-first, no implementation yet. The defining constraint: the current dashboard for exercises and playlists is complex and was built by and for me and Rowland (two power users); the redesign must work for **any** music teacher — pedagogy-fluent, internals-naive. Read `docs/superpowers/specs/2026-06-08-teacher-experience-design-brief.md` and the prior-art docs it links (dashboard_workbench, the 2026-06-07 workbench chordal-analysis-review design, teacher-play-route design, curriculum architecture/roadmap, UMTO_GUIDE). Then use the brainstorming skill to explore three intertwined threads: (1) bringing analysis approval/override/respelling into the Play view after Save so authoring+review live in one place, (2) redesigning the teacher dashboard for the median teacher (progressive disclosure; pedagogical vocabulary; the existing dashboard is power-user prior art, not the thing to incrementally simplify), and (3) making the core curriculum legible and easy for teachers to adopt and assign. Challenge my premises, surface the key decisions, and help me converge on a teacher-experience concept. Output a design spec, not a task list. Context: we just shipped the review/respell *mechanics* in PR #90 but they're split across surfaces (the review UI lives in the bulk-import workbench), which is what prompted this.
