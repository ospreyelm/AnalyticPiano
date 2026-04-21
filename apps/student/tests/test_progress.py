# apps/student/tests/test_progress.py
import pytest
from django.contrib.auth import get_user_model
from apps.exercises.models import StudentSkillMastery
from apps.student.progress import get_unit_progress

User = get_user_model()


@pytest.fixture
def student(db):
    return User.objects.create_user(
        email="student@test.com",
        password="testpass",
    )



def test_all_not_started_returns_zero_percent(student):
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["percent"] == 0
    assert result["mastered_count"] == 0
    assert len(result["skills"]) == 4
    for skill in result["skills"]:
        assert skill["level"] == "not_started"


def test_one_mastered_returns_25_percent(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Note_Names",
        level=StudentSkillMastery.LEVEL_MASTERED,
    )
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["percent"] == 25
    assert result["mastered_count"] == 1


def test_skill_level_returned_for_each_tag(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Ledger_Lines",
        level=StudentSkillMastery.LEVEL_PROFICIENT,
    )
    tags = ["Note_Names", "Ledger_Lines"]
    result = get_unit_progress(student, tags)
    levels = {s["tag"]: s["level"] for s in result["skills"]}
    assert levels["Ledger_Lines"] == "proficient"
    assert levels["Note_Names"] == "not_started"


def test_resume_skill_is_first_non_mastered(student):
    StudentSkillMastery.objects.create(
        user=student,
        skill_tag="Note_Names",
        level=StudentSkillMastery.LEVEL_MASTERED,
    )
    tags = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
    result = get_unit_progress(student, tags)
    assert result["resume_tag"] == "Ledger_Lines"


def test_resume_skill_is_none_when_all_mastered(student):
    tags = ["Note_Names", "Ledger_Lines"]
    for tag in tags:
        StudentSkillMastery.objects.create(
            user=student,
            skill_tag=tag,
            level=StudentSkillMastery.LEVEL_MASTERED,
        )
    result = get_unit_progress(student, tags)
    assert result["resume_tag"] is None
    assert result["percent"] == 100
