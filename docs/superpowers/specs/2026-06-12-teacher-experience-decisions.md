# Teacher Experience Decisions

> **Purpose:** Single source of settled product/architecture decisions for the
> teacher experience meta-plan
> ([docs/superpowers/plans/2026-06-12-teacher-experience-meta-plan.md](../plans/2026-06-12-teacher-experience-meta-plan.md)).
> Child specs and plans MUST read this doc and MUST NOT re-ask settled
> decisions. Open questions are listed at the bottom, each owned by exactly
> one phase.

Decided with Avner on 2026-06-11.

## Settled decisions

### D1. Execution order: generation first, organization later

The curation bottleneck is **producing** content (variants, transpositions,
imports), not organizing existing content. After Phase 0 navigation fixes:

1. Generation & transposition wizard
2. MusicXML import
3. Curation workbench (content library / playlist / exercise editors)

The curation workbench moves after generation/import, even though the launch
followups doc lists the backend editor first.

### D2. Play-save transpositions: explicit UMTO Exercise copies

When saving from `/teacher/play/` with the transpose option checked, the
server generates explicit transposed UMTO Exercise rows into the target
playlist by reusing `generate_transpositions` logic extracted as a service
function.

- We are **not** fixing runtime playlist transposition
  (`Playlist.transpose_requests`) for UMTO rows now. Per the
  `generate_transpositions.py` docstring, UMTO chordal rows lack the legacy
  `data["chord"]`/`keySignature` fields that `transpose()` mutates.
- Accepted cost: row multiplication, managed by the existing dedup/audit
  direction (see
  [2026-06-02-efficient-bach-generation.md](../plans/2026-06-02-efficient-bach-generation.md)).

Verified broken state (2026-06-11): the "create transpositions" checkbox in
`lab/static/js/src/components/ui/target_selector.js` (label string-mangled to
"Auto-ne for varied keys", payload key `n`) reaches `_onTargetChosen` in
`lab/static/js/src/components/ui/music_controls.js`, which only
`console.log`s the payload. Nothing transposes.

### D3. Official content: explicit model field

Add an explicit `is_official` (or status) field on Exercise and Playlist,
backfilled from `authored_by=factory@monteverdi.app` ownership. All reports,
wizards, and editors filter on the field, not on factory-account inference.
Small migration, scheduled early (Phase 0.5) because it unblocks filtering in
every later phase.

### D4. Student home: course-first

Joined students see their assigned course (next due work, progress, direct
links) on top; the full curriculum remains available below as exploration.

### D5. Process: lightweight, one combined doc per phase

- One combined spec+plan document per phase, not separate spec → approval →
  plan → approval cycles.
- Question gates only for genuine pedagogy, official-content policy, or
  visual-identity calls. Default UI follows existing teacher-app conventions.
- This decisions doc is the single place settled answers live.

### D6. Cost routing: cheapest capable executor per task

Both `gemini` (0.37.1) and `codex` (0.137.0) CLIs are installed and verified.
Every child prompt/task carries an executor tier tag:

| Tier | Work | Executor |
|------|------|----------|
| 1 | Mechanical/bulk: doc rewrites from explicit instructions, audits/inventories, label fixes, test scaffolds, backfill scripts | `gemini -m gemini-2.5-flash` or Codex CLI at low reasoning effort |
| 2 | Implementation against a complete written spec: transpose service wiring, `is_official` migration, wizard CRUD pages, MusicXML upload plumbing | Codex CLI default model, or `claude --model haiku` |
| 3 | Combined spec+plan docs needing judgment: generation manifest design, grading policy, MusicXML conversion edge cases | `claude --model sonnet` or main session |
| 4 | Pedagogy, visual identity, policy decisions | Avner + main session only. Never delegated. |

Rules: default every task to Tier 1; escalate only when the task demands
judgment the lower tier lacks. Review of delegated output happens in the
dispatching session, not by another expensive agent.

## Open questions (each owned by one phase)

Ask these once, at the owning phase's kickoff, and record the answer here.

| # | Question | Owning phase |
|---|----------|--------------|
| Q1 | Should non-superuser teachers be able to submit content for official review, or only save personal content? | Phase 3 (curation workbench) |
| Q2 | What is the minimum useful MusicXML import scope for v1: chorales, keyboard reductions, single-line melodies, or arbitrary scores? | Phase 2 (MusicXML import) |
| Q3 | Which transposition sets are pedagogically appropriate by unit (all keys, selected keys, pedagogical key set)? **Answer (2026-06-12): Configurable per generation run. Wizard exposes a key-set picker; no hardcoded default set. Teacher chooses all 12, a curated subset, or a custom list at run time.** | Phase 1 (generation wizard) |
| Q4 | What does "forgiving MIDI grading" mean for each play exercise type (timing, extra notes, re-attacks, octave equivalence, correction behavior)? | Phase 4 (grading reform) |
| Q5 | What visual qualities make Monteverdi distinct from Artusi (colors, typography, density, icons)? Academic, studio/tool-like, modern SaaS, or conservatory feel? | Phase 5 (CSS identity) |
| Q6 | Which legacy dashboard functions are genuinely still needed by normal teachers (vs. advanced/admin escape hatches)? | Phase 3 (curation workbench) |
| Q7 | Which generation variants should be produced together by default from one source? **Answer (2026-06-12): Configurable via wizard checkboxes; default selection is play only. Teacher opts into identify, roman, figures individually.** | Phase 1 (generation wizard) |
| Q8 | ~~Should assigned course work hide non-course playlists or merely prioritize them?~~ **Decided: prioritize** — course content surfaces first; full curriculum remains below. | Phase 0 (student home) |
