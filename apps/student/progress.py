# apps/student/progress.py
from apps.exercises.models import StudentSkillMastery


def get_unit_progress(user, skill_tags: list[str]) -> dict:
    """
    Returns mastery summary for a list of skill tags for a given user.

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
    mastery_map = {
        m.skill_tag: m.level
        for m in StudentSkillMastery.objects.filter(user=user, skill_tag__in=skill_tags)
    }

    skills = []
    mastered_count = 0
    resume_tag = None

    for tag in skill_tags:
        level = mastery_map.get(tag, StudentSkillMastery.LEVEL_NOT_STARTED)
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
