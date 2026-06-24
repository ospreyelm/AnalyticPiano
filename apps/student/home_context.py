from apps.exercises.models import StudentSkillMastery
from apps.student.unit_progress import _batch_skill_levels, get_unit_progress_data


def _summarize_unit_progress(data: dict) -> dict:
    segments = data.get("bar_segments", [])
    mastered_count = sum(
        1 for segment in segments
        if segment["level"] == StudentSkillMastery.LEVEL_MASTERED
    )
    total = len(segments)
    percent = int(mastered_count / total * 100) if total else 0
    return {
        "percent": percent,
        "mastered_count": mastered_count,
        "resume_tag": None,
    }


def _empty_unit_progress_summary() -> dict:
    return {
        "percent": 0,
        "mastered_count": 0,
        "resume_tag": None,
    }


def _summarize_unit_from_skill_levels(unit: dict, skill_levels: dict[str, str]) -> dict:
    tags = unit.get("tags", [])
    mastered_count = sum(
        1 for tag in tags
        if skill_levels.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED)
        == StudentSkillMastery.LEVEL_MASTERED
    )
    total = len(tags)
    return {
        "percent": int(mastered_count / total * 100) if total else 0,
        "mastered_count": mastered_count,
        "resume_tag": None,
    }


def _batch_home_unit_summaries(user, units: list[dict], available_unit_numbers: set[str]) -> dict[str, dict]:
    """Return home-page progress summaries for all available units.

    Home cards only need the bar-segment summary (percent + mastered_count).
    For non-Unit-1 units, bar segments map directly to unit skill tags, so one
    batched mastery lookup is enough. Unit 1 remains lane-based and is handled
    once as a constant-cost special case.
    """
    unit_by_n = {str(unit.get("n")): unit for unit in units}
    non_unit1_tags = [
        tag
        for unit_n, unit in unit_by_n.items()
        if unit_n in available_unit_numbers and unit_n != "1"
        for tag in unit.get("tags", [])
    ]
    skill_levels = _batch_skill_levels(user, non_unit1_tags)

    summaries: dict[str, dict] = {}
    for unit_n in available_unit_numbers:
        unit = unit_by_n.get(str(unit_n))
        if not unit:
            continue
        if str(unit_n) == "1":
            unit1_data = get_unit_progress_data(user, "1")
            summaries["1"] = (
                _summarize_unit_progress(unit1_data)
                if unit1_data
                else _empty_unit_progress_summary()
            )
            continue
        summaries[str(unit_n)] = _summarize_unit_from_skill_levels(unit, skill_levels)
    return summaries
