# apps/exercises/utils/wir_corpus.py
"""When in Rome corpus lookup for Bach chorales.

Loads data/when_in_rome/chorales.json and bwv_to_riemenschneider.json
once at module level. Provides exact-match lookup by (riemenschneider, measure, beat).
"""
from __future__ import annotations
import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "when_in_rome"


def _load_json(name: str) -> dict:
    path = _DATA_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


_CHORALES: dict[str, dict] = _load_json("chorales.json")
_BWV_MAP: dict[str, int] = _load_json("bwv_to_riemenschneider.json")


def has_chorale(riemenschneider: int) -> bool:
    """Return True if WiR corpus contains data for this Riemenschneider number."""
    return str(riemenschneider) in _CHORALES


def lookup(riemenschneider: int, measure: int, beat: float) -> dict | None:
    """Return {label, local_key} for exact (measure, beat) match.

    Exact match: abs(stored_beat - beat) < 1e-6.
    Returns None if chorale unknown, or no label at this exact position.
    """
    chorale = _CHORALES.get(str(riemenschneider))
    if chorale is None:
        return None
    for entry in chorale["labels"]:
        if entry["measure"] == measure and abs(entry["beat"] - beat) < 1e-6:
            if entry.get("label") is None:
                # variant-only entry — no main label, treat as NCT
                return None
            return {"label": entry["label"], "local_key": entry["local_key"]}
    return None


def bwv_to_riemenschneider(bwv: str) -> int | None:
    """Return Riemenschneider number for a BWV string, or None if not found."""
    return _BWV_MAP.get(str(bwv))
