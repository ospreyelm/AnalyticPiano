"""
Unit suggestion service for suggesting curriculum units based on detected skill tags.

When a teacher creates an exercise via /teacher/play/, this service helps identify
which units the exercise belongs to by matching detected skill tags against the
curriculum taxonomy.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Load taxonomy at module init time
_TAXONOMY = None
_TAG_TO_UNITS_CACHE = None


def _load_taxonomy():
    """Load the curriculum taxonomy from disk."""
    global _TAXONOMY
    if _TAXONOMY is not None:
        return _TAXONOMY

    taxonomy_path = Path(__file__).resolve().parents[3] / "music_theory_taxonomy_with_branches.json"
    try:
        with open(taxonomy_path) as f:
            _TAXONOMY = json.load(f)
        return _TAXONOMY
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load taxonomy from {taxonomy_path}: {e}")
        return []


def build_tag_to_units_map() -> dict[str, list[int]]:
    """
    Return a mapping from tag string (canonical or unit-prefixed) → list of unit numbers
    that include it (as integers, in the core branch).

    Example:
        {"Dominant_Seventh": [9], "Diatonic_Triads": [5, 9], ...}
    """
    global _TAG_TO_UNITS_CACHE
    if _TAG_TO_UNITS_CACHE is not None:
        return _TAG_TO_UNITS_CACHE

    result = {}
    taxonomy = _load_taxonomy()

    if not taxonomy:
        _TAG_TO_UNITS_CACHE = {}
        return result

    # Only scan the "core" branch (standard sequence)
    for branch in taxonomy:
        if branch.get("id") != "core":
            continue

        for tier in branch.get("tiers", []):
            for unit in tier.get("units", []):
                unit_n = unit.get("n")
                if not unit_n:
                    continue

                try:
                    unit_num = int(unit_n)
                except (ValueError, TypeError):
                    continue

                tags = unit.get("tags", [])
                for tag in tags:
                    if tag not in result:
                        result[tag] = []
                    if unit_num not in result[tag]:
                        result[tag].append(unit_num)

    _TAG_TO_UNITS_CACHE = result
    return result


def suggest_units_from_tags(detected_tags: list[str], top_n: int = 5) -> list[int]:
    """
    Rank units by intersection size with detected_tags.

    Args:
        detected_tags: List of skill tag strings (e.g. ["Dominant_Seventh", "Diatonic_Triads"])
        top_n: Maximum number of units to return (default 5)

    Returns:
        List of unit numbers (as ints) ranked by match count, descending.
        Units with 0 matches are excluded.
        Example: [9, 11, 5]
    """
    if not detected_tags:
        return []

    tag_to_units = build_tag_to_units_map()

    # Count how many detected tags match each unit
    unit_counts = {}
    for tag in detected_tags:
        units = tag_to_units.get(tag, [])
        for unit in units:
            unit_counts[unit] = unit_counts.get(unit, 0) + 1

    # Sort by count descending, then by unit number ascending (for stability)
    sorted_units = sorted(
        unit_counts.items(),
        key=lambda x: (-x[1], x[0])
    )

    # Return top_n unit numbers
    return [unit for unit, count in sorted_units[:top_n]]
