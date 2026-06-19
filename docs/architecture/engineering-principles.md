# HarmonyLab Engineering Principles

## Purpose

HarmonyLab is not unusually large, but it has accumulated parallel routes,
overloaded models, and compatibility layers that make changes harder to reason
about. These principles keep new work from increasing that architectural
density.

`AGENTS.md` contains the short mandatory rules. This document explains how to
apply them in designs, plans, and implementation reviews.

## One authoritative path

Every user-facing capability should have one authoritative implementation.

When replacing an old path:

1. name the new authority;
2. list every known caller of the old path;
3. migrate callers or add compatibility redirects;
4. state the condition for removing compatibility code; and
5. delete the old implementation when that condition is met.

Compatibility adapters may translate inputs or redirect requests. They must not
grow independent business logic.

For student exercise delivery, the target authority is the modern student
player. Legacy `lab` delivery views are compatibility surfaces, not places for
new behavior.

## Replacement budget

Significant architecture work must include a replacement budget:

- responsibilities added;
- responsibilities removed or narrowed;
- files, routes, models, flags, and services to retire;
- temporary compatibility code;
- observable removal conditions; and
- the phase in which deletion occurs.

A feature that only adds another permanent path is incomplete unless parallel
operation is an explicit product requirement.

## Model responsibility

Each model should represent one durable domain concept.

Before adding a model:

- identify the responsibility it owns;
- identify the existing model responsibility it replaces or narrows;
- define its identity and uniqueness;
- define its lifecycle and deletion policy; and
- identify the authoritative service that mutates it.

Do not use boolean combinations to encode an expanding state machine. Prefer an
explicit concept or typed state when behaviors and lifecycle differ.

Do not allow two models to remain indefinite sources of truth for the same
identity, ordering, progress, or assignment state.

## Service boundaries

Business rules shared by views, management commands, jobs, or APIs belong in a
focused service with a defined interface.

Views should:

- authenticate and authorize;
- validate transport-level input;
- call a service; and
- format the response.

Views should not independently select exercises, calculate assignment progress,
normalize musical data, or reconstruct submission identity.

Management commands should call services rather than contain the only
implementation of reusable generation or migration behavior.

## Oversized modules

Large files are a navigation and review cost, not an automatic defect. However,
do not add substantial new responsibility to an already oversized module.

When changing a large module:

- extract the new cohesive behavior first when practical;
- avoid unrelated whole-file rewrites;
- leave existing behavior stable behind a narrow interface; and
- add focused tests around the extracted boundary.

Current concentration points include:

- `apps/exercises/models.py`
- `apps/exercises/forms.py`
- `apps/student/views.py`
- `lab/views.py`
- `lab/static/js/src/components/music/exercise_sheet.js`
- `lab/static/js/src/components/music/rendering/vexflow_adapter.js`
- `lab/static/js/src/components/ui/music_controls.js`

## Legacy code policy

Legacy means supported for compatibility, not available for extension.

For each compatibility layer, document:

- why it still exists;
- who or what still calls it;
- what telemetry or migration proves it can be removed; and
- the removal target.

Do not repair a legacy path by duplicating a fix already implemented in the
authority. Redirect or delegate to the authority when possible.

## Documentation lifecycle

Always-loaded instruction files contain current policy only.

- `AGENTS.md`: authoritative repository rules and current priority.
- Tool-specific files such as `CLAUDE.md`: minimal operational wrappers.
- `docs/architecture/`: durable architecture and engineering rationale.
- `docs/superpowers/specs/`: approved feature and architecture decisions.
- `docs/superpowers/plans/`: executable implementation plans.
- Archived or superseded documents: clearly marked and excluded from current
  routing.

When priorities change, replace the priority section. Do not append a new list
while retaining an obsolete list as if both were active.

## Definition of retired

A path is retired only when:

- internal links and callers are migrated;
- persisted data has a documented migration or retention policy;
- compatibility redirects have served their purpose;
- relevant tests target the new authority;
- obsolete code and flags are deleted; and
- documentation no longer directs contributors to the old path.

## Review checklist

For significant work, reviewers should ask:

- What becomes authoritative?
- What old behavior is replaced?
- Is compatibility translating or duplicating logic?
- Is there one source of truth for identity and progress?
- Does new logic belong in a shared service?
- Is an oversized module gaining another responsibility?
- What is the concrete removal condition?
- Which tests prove both migration and retirement behavior?
