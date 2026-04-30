# HarmonyLab Platform Roadmap

**Date:** 2026-04-29  
**Goal:** Scalable, disciplined path from one-off scripts to a fully authoring-capable, adaptive, mobile-ready music theory platform.

---

## Design decisions

- **Teacher is the primary author** — workbench is the canonical UI, CLI is for automation/CI
- **Adaptive serving is the point** — dynamic playlists + mastery engine, not fixed sequences
- **MusicXML import covers both corpus (music21) and uploaded files (Sibelius/Finale/MuseScore)**
- **Mobile = student player only** — teacher tools stay desktop
- **Help text** = UMTO field + AI-drafted placeholder + human override in workbench

---

## Phase overview

| Phase | What | Status | Spec |
|-------|------|--------|------|
| 1 | Fix `applySkillFilter` unit map | **Done** (already implemented in `exercise_definition.js`) | — |
| 2 | `create_unit_playlist` management command | **Next** | [Phase 2 spec](2026-04-29-phase2-unit-factory-design.md) |
| 3 | Teacher Workbench (HTMX + Alpine.js) | Pending Phase 2 | TBD |
| 4 | Responsive student player | Parallel after Phase 2 | TBD |
| 5 | Help text system + AI draft | Additive | TBD |

---

## Phase 1 — `applySkillFilter` (Done)

`UNIT_ALLOWED_ANSWERS` map covers units 9–20 in `exercise_definition.js`. `applySkillFilter` reads the highest `unit:N` tag and filters Roman numeral answers to that unit's cumulative allowlist. Units 19–20 pass through unfiltered (modulation spans tonal centres). Units 21+ pass through (no map entry = safe fallback).

---

## Phase 2 — Unit factory command

Single idempotent management command replaces all one-off batch scripts.

```bash
python manage.py create_unit_playlist \
  --unit 11 \
  --riemenschneider 21-40 \
  --author admin@example.com \
  --mode roman
```

Creates a dynamic+adaptive playlist tagged `unit:11`, imports Bach phrases from the Riemenschneider range as UMTO exercises, idempotent on re-run. Teacher controls corpus range per unit.

See [Phase 2 spec](2026-04-29-phase2-unit-factory-design.md).

---

## Phase 3 — Teacher Workbench

Builds on existing `workbench.html` stub. Three panels:

- **Import** — MusicXML file upload or music21 corpus picker; also "Generate Unit N" button that calls `create_unit_playlist` via HTMX POST with live progress stream
- **Preview** — rendered score + exercise test-play before publishing
- **Publish** — unit assignment, mode selection, key propagation

Stack: Django + HTMX (server-rendered fragments) + Alpine.js (panel state only). No SPA rewrite.

Spec to be written after Phase 2 ships.

---

## Phase 4 — Responsive student player

Student-facing only. Score renders at mobile viewport. Piano keyboard becomes touch-friendly horizontal strip. Identification slots stack vertically. Pure CSS breakpoints + touch event handlers — no new JS framework.

Target: iPhone 14, iPad. Not in scope: dashboard, workbench, admin.

Spec to be written. Can run in parallel with Phase 3.

---

## Phase 5 — Help text system

- `help_text` field added to UMTO schema
- Auto-generated placeholder at exercise creation via Claude Haiku (reads score + tags → proposes text)
- Editable in workbench
- Displayed in player as collapsible hint panel

Spec to be written after Phase 3 workbench exists (editable UI depends on it).
