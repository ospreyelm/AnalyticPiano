import json
import os

class TaxonomyReader:
    # Lazily loaded, cached at class level
    _data: list | None = None

    @classmethod
    def _load(cls) -> list:
        if cls._data is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(os.path.dirname(current_dir))
            file_path = os.path.join(root_dir, "music_theory_taxonomy.json")
            with open(file_path, "r") as f:
                cls._data = json.load(f)
        return cls._data

    @classmethod
    def get_all_units(cls) -> list[dict]:
        """Returns all unit dicts across all tiers."""
        data = cls._load()
        units = []
        for taxonomy in data:
            for tier in taxonomy.get("tiers", []):
                units.extend(tier.get("units", []))
        return units

    @classmethod
    def get_unit(cls, unit_n: str) -> dict | None:
        """Returns a single unit by its 'n' key (e.g. '1', '9')."""
        unit_n_str = str(unit_n)
        for unit in cls.get_all_units():
            if str(unit.get("n")) == unit_n_str:
                return unit
        return None

    @classmethod
    def get_unit_for_tag(cls, skill_tag: str) -> dict | None:
        """Returns the unit that contains this skill_tag, or None."""
        for unit in cls.get_all_units():
            if skill_tag in unit.get("tags", []):
                return unit
        return None

    @classmethod
    def get_tier_for_unit(cls, unit_n: str) -> dict | None:
        """Returns the tier dict containing the given unit."""
        data = cls._load()
        unit_n_str = str(unit_n)
        for taxonomy in data:
            for tier in taxonomy.get("tiers", []):
                for unit in tier.get("units", []):
                    if str(unit.get("n")) == unit_n_str:
                        return tier
        return None

    @classmethod
    def get_skill_label(cls, tag: str) -> str:
        """Converts "Note_Names" -> "Note Names" (replace underscores, title-case)."""
        return tag.replace("_", " ").title()

    @classmethod
    def get_unit_analysis(cls, unit_n: str, family: str) -> dict | None:
        """Returns {"cumulative": [...], "new": [...]} for the given unit and analysis family, or None."""
        unit = cls.get_unit(unit_n)
        if unit is None:
            return None
        return unit.get("analysis", {}).get(family)

    @classmethod
    def get_cumulative_values(cls, unit_n: str, family: str) -> set[str]:
        """Returns the set of 'value' strings from the cumulative list for this unit/family."""
        analysis = cls.get_unit_analysis(unit_n, family)
        if analysis is None:
            return set()
        return {entry["value"] for entry in analysis.get("cumulative", [])}

    @classmethod
    def get_new_values(cls, unit_n: str, family: str) -> set[str]:
        """Returns the set of 'value' strings from the new list for this unit/family."""
        analysis = cls.get_unit_analysis(unit_n, family)
        if analysis is None:
            return set()
        return {entry["value"] for entry in analysis.get("new", [])}
