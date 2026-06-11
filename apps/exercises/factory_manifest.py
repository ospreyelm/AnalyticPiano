"""Declarative manifest of the official Monteverdi exercise library.

Every entry maps one logical curriculum unit to either:
- ``generated``: commands that (re-)build exercise rows from code/data.
- ``curated``:   hand-authored exercises managed via export_factory_curated /
                  import_factory_curated.  These entries are NEVER regenerated;
                  the wrapper skips their generator step.

Usage (from generate_factory_library)::

    from apps.exercises.factory_manifest import MANIFEST, SHARED_COMMANDS

``MANIFEST`` is a flat list ordered by ascending unit number (B-units at the
end).  ``SHARED_COMMANDS`` holds de-duplicated invocations that must run once
globally (not once per manifest entry).

A ``FactoryUnitEntry`` with ``kind="generated"`` may reference items from
``SHARED_COMMANDS`` by storing them as ``None`` entries in the ``commands``
list — the wrapper skips those and instead ensures SHARED_COMMANDS have been
dispatched once before any per-unit step.

Design note: ``generate_bach_unit_matrix`` covers all units 9-20 in a single
invocation.  Rather than repeat that entry 12 times, we place it in
``SHARED_COMMANDS`` and let units 9-20 reference it.  The generate_factory_library
wrapper runs each SHARED_COMMANDS entry once, then runs each entry's own commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FactoryUnitEntry:
    """A single manifest entry for one curriculum unit.

    Attributes
    ----------
    unit:
        Integer unit number (e.g. 1, 9) or string for branch-B units (e.g.
        "B1").
    kind:
        ``"generated"`` — rows are (re-)buildable from code; commands are run.
        ``"curated"``   — rows are hand-authored; commands list is empty.
    commands:
        List of ``(command_name, kwargs_dict)`` tuples that produce this unit's
        exercise rows + playlists.  For units that delegate entirely to a shared
        command, this list is empty (the wrapper handles SHARED_COMMANDS).
    uses_shared_commands:
        ``True`` when this entry relies on one or more entries in
        ``SHARED_COMMANDS`` rather than its own commands list.  The wrapper
        ensures those shared commands are run before this entry's own commands.
    playlist_name:
        Expected playlist name pattern (used by --verify).  May be ``None`` for
        units whose playlists are named by sub-commands.
    tag_query:
        Skill-tag filter identifying this unit's factory exercises (for
        --verify and export_factory_curated).
    exercise_ids:
        Explicit exercise-ID override list (curated entries may pin IDs).
    """

    unit: int | str
    kind: str  # "generated" | "curated"
    commands: list[tuple[str, dict]] = field(default_factory=list)
    uses_shared_commands: bool = False
    playlist_name: str | None = None
    tag_query: list[str] | None = None
    exercise_ids: list[str] | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("generated", "curated"):
            raise ValueError(f"kind must be 'generated' or 'curated', got {self.kind!r}")


# ---------------------------------------------------------------------------
# Shared commands
#
# These are invocations that cover multiple units in a single call (e.g.
# generate_bach_unit_matrix imports all Riemenschneider phrases for units 9-20
# at once).  The generate_factory_library wrapper dispatches each entry here
# exactly once, before processing per-unit manifest entries.
#
# Each element: (command_name, kwargs_dict).
# The ``--author`` value is filled in at runtime by the wrapper.
# ---------------------------------------------------------------------------

SHARED_COMMANDS: list[tuple[str, dict]] = [
    # Bach Riemenschneider phrases (units 9-20): import each mode once and
    # project into per-unit playlists.  Uses the full default riemenschneider
    # range and all four standard modes.
    (
        "generate_bach_unit_matrix",
        {
            "riemenschneider": "1-371",
            "units": "9,10,11,12,14,16,17,18,19,20",
            "modes": "roman,figures,play,play_figures",
            "public": True,
            "overwrite": True,
            # author is injected at runtime
        },
    ),
    # Galant Compendium Roman-numeral exercises (units 9-20).
    (
        "import_compendium_cadences",
        {
            "all_units": True,
            "public": True,
            "overwrite": True,
            # author is injected at runtime
        },
    ),
]


# ---------------------------------------------------------------------------
# MANIFEST
# ---------------------------------------------------------------------------

MANIFEST: list[FactoryUnitEntry] = [
    # ── Unit 1: Pitch identification ─────────────────────────────────────────
    FactoryUnitEntry(
        unit=1,
        kind="generated",
        commands=[
            (
                "generate_unit1",
                # generate_unit1 has no --public flag (its playlists are public
                # by construction); author injected at runtime
                {},
            ),
        ],
        tag_query=["unit:1"],
    ),

    # ── Unit 2: Rhythm and meter ─────────────────────────────────────────────
    FactoryUnitEntry(
        unit=2,
        kind="generated",
        commands=[
            ("generate_unit2_meter_exercises", {"public": True}),
            ("generate_unit2_barline_exercises", {"public": True}),
            # generate_unit2_meter_reference has no --author and is display-only
        ],
        tag_query=["unit:2"],
    ),

    # ── Unit 3: Scales and key signatures ───────────────────────────────────
    FactoryUnitEntry(
        unit=3,
        kind="generated",
        commands=[
            ("generate_unit3_key_sig_exercises", {"public": True}),
            ("generate_unit3_scale_exercises", {"public": True}),
        ],
        tag_query=["unit:3"],
    ),

    # ── Unit 4: Intervals ────────────────────────────────────────────────────
    FactoryUnitEntry(
        unit=4,
        kind="generated",
        commands=[
            ("generate_unit4", {"public": True}),
        ],
        tag_query=["unit:4"],
    ),

    # ── Unit 5: Triads and seventh chords ────────────────────────────────────
    FactoryUnitEntry(
        unit=5,
        kind="generated",
        commands=[
            ("generate_unit5", {"type": "both", "public": True}),
        ],
        tag_query=["unit:5"],
    ),

    # ── Units 9-20: Bach Riemenschneider + Compendium ────────────────────────
    # All handled by SHARED_COMMANDS (generate_bach_unit_matrix +
    # import_compendium_cadences).  Per-unit entries carry no own commands but
    # allow --verify and --report to check each unit individually.
    *[
        FactoryUnitEntry(
            unit=u,
            kind="generated",
            commands=[],
            uses_shared_commands=True,
            tag_query=[f"unit:{u}"],
        )
        for u in [9, 10, 11, 12, 14, 16, 17, 18, 19, 20]
    ],

    # ── Branch B: Clausulae ──────────────────────────────────────────────────
    FactoryUnitEntry(
        unit="B1",
        kind="generated",
        commands=[
            (
                "generate_clausulae_b1",
                {"public": True, "unit": "B1"},
                # author injected at runtime
            ),
        ],
        tag_query=["unit:B1"],
    ),

    # ── Curated entries ──────────────────────────────────────────────────────
    # Hand-authored content managed via export_factory_curated /
    # import_factory_curated.  Add entries here as curated exercises land.
    # Example (do not activate until exercises exist):
    #
    # FactoryUnitEntry(
    #     unit=6,
    #     kind="curated",
    #     playlist_name="Unit 6 — Voice Leading",
    #     tag_query=["unit:6", "curated:voice_leading"],
    # ),
]
