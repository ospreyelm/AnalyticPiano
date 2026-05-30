"""Single source of truth for per-unit Roman-numeral answer sets.

Derived from music_theory_taxonomy_with_branches.json (analysis.roman.cumulative),
with a checked-in overrides file for units the taxonomy does not enumerate
(e.g. modulation units 19-20, which are null pass-through).
"""
from __future__ import annotations

import json
import os

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TAXONOMY_PATH = os.path.join(_REPO_ROOT, "music_theory_taxonomy_with_branches.json")
_OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), "data", "unit_allowed_answers.overrides.json")


def _walk_units(node):
    """Yield every dict that looks like a unit (has 'n' and dict 'analysis')."""
    if isinstance(node, dict):
        if "n" in node and isinstance(node.get("analysis"), dict):
            yield node
        for value in node.values():
            yield from _walk_units(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_units(item)


def compute_unit_allowed_answers() -> dict:
    """Return {unit_int: [rn, ...] | None} merged from taxonomy then overrides."""
    with open(_TAXONOMY_PATH) as fh:
        taxonomy = json.load(fh)

    table: dict = {}
    for unit in _walk_units(taxonomy):
        roman = unit["analysis"].get("roman")
        if not isinstance(roman, dict):
            continue
        cumulative = roman.get("cumulative")
        if not cumulative:
            continue
        try:
            n = int(str(unit["n"]).strip())
        except (TypeError, ValueError):
            continue
        table[n] = [entry["value"] for entry in cumulative]

    with open(_OVERRIDES_PATH) as fh:
        overrides = json.load(fh)
    for key, value in overrides.items():
        table[int(key)] = value  # overrides win (including explicit null)

    return table
