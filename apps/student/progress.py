# apps/student/progress.py
from apps.exercises.models import StudentSkillMastery

# TAG_ALIASES map legacy display tags to canonical mastery tags.
# When fetching mastery for a display tag, we aggregate across all canonical tags.
TAG_ALIASES = {
    "clefs": ["Read_Treble_Clef", "Read_Bass_Clef", "clefs"],
    "enharmonic": ["Enharmonic_Reading", "enharmonic"],
    "Note_Names": ["Note_Names"],
    "Ledger_Lines": ["Ledger_Lines"],
}


def get_unit_progress(user, skill_tags: list[str]) -> dict:
    """
    Returns mastery summary for a list of skill tags for a given user.

    Aggregates canonical mastery tags under legacy display tags using TAG_ALIASES.

    Returns:
        {
            "percent": int (0-100),
            "mastered_count": int,
            "resume_tag": str | None,  # first non-mastered tag
            "skills": [
                {"tag": str, "level": str},  # level matches LEVEL_* constants
                ...
            ]
        }
    """
    # Expand requested tags to canonical tags
    canonical_tags = set()
    for tag in skill_tags:
        canonical_tags.update(TAG_ALIASES.get(tag, [tag]))

    # Fetch all mastery data for canonical tags
    mastery_rows = StudentSkillMastery.objects.filter(user=user, skill_tag__in=canonical_tags)
    mastery_map = {m.skill_tag: m.level for m in mastery_rows}

    def best_level(tag_list):
        """Return the best (highest) mastery level across a list of canonical tags."""
        levels = [mastery_map.get(t, StudentSkillMastery.LEVEL_NOT_STARTED) for t in tag_list]
        if not levels:
            return StudentSkillMastery.LEVEL_NOT_STARTED
        # Order levels from best to worst
        level_order = [
            StudentSkillMastery.LEVEL_MASTERED,
            StudentSkillMastery.LEVEL_PROFICIENT,
            StudentSkillMastery.LEVEL_FAMILIAR,
            StudentSkillMastery.LEVEL_ATTEMPTED,
            StudentSkillMastery.LEVEL_NOT_STARTED,
        ]
        for level in level_order:
            if level in levels:
                return level
        return StudentSkillMastery.LEVEL_NOT_STARTED

    skills = []
    mastered_count = 0
    resume_tag = None

    for tag in skill_tags:
        # Get canonical tags for this display tag
        canonical_list = TAG_ALIASES.get(tag, [tag])
        # Get best level across all canonical tags
        level = best_level(canonical_list)
        skills.append({"tag": tag, "level": level})
        if level == StudentSkillMastery.LEVEL_MASTERED:
            mastered_count += 1
        elif resume_tag is None:
            resume_tag = tag

    total = len(skill_tags)
    percent = int(mastered_count / total * 100) if total else 0

    return {
        "percent": percent,
        "mastered_count": mastered_count,
        "resume_tag": resume_tag,
        "skills": skills,
    }
