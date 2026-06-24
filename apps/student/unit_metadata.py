import json
from pathlib import Path


TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent / "music_theory_taxonomy_with_branches.json"


def unit_sort_key(n_str: str) -> tuple[str, int]:
    """Sort unit strings alphanumerically, e.g. "1" -> ("", 1), "B2" -> ("B", 2)"""
    import re
    match = re.match(r'^([a-zA-Z]*)(\d+)$', n_str)
    if match:
        prefix, num = match.groups()
        return (prefix, int(num))
    return (n_str, 0)


def _load_unit_meta(unit_num: int) -> dict:
    """Return title/feat for a unit from taxonomy JSON."""
    try:
        with open(TAXONOMY_PATH) as f:
            taxonomy = json.load(f)
        for branch in taxonomy:
            for tier in branch.get("tiers", []):
                for unit in tier.get("units", []):
                    if str(unit["n"]) == str(unit_num):
                        return unit
    except FileNotFoundError:
        pass
    return {}


def _taxonomy_units_from_branches(branches: list[dict]) -> list[dict]:
    units = []
    for branch in branches:
        for tier in branch.get("tiers", []):
            units.extend(tier.get("units", []))
    return units


def _unit_date_labels(info: dict | None) -> dict:
    """Template-ready chip labels for one unit's course schedule info."""
    if not info:
        return {"due_label": None, "opens_label": None, "overdue": False}
    from django.utils.timezone import localtime
    from django.utils.timezone import now as tz_now

    if not info["published"] and info["publish"] is not None:
        return {
            "due_label": None,
            "opens_label": localtime(info["publish"]).strftime("Opens %a %b %-d"),
            "overdue": False,
        }
    if info["due"] is not None:
        return {
            "due_label": localtime(info["due"]).strftime("Due %a %b %-d"),
            "opens_label": None,
            "overdue": info["due"] < tz_now(),
        }
    return {"due_label": None, "opens_label": None, "overdue": False}
