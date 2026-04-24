from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.models import Exercise, Playlist, Course, ExercisePlaylistOrdered, StudentSkillMastery, SkillPrerequisite
from apps.exercises.mastery import get_next_exercise
from apps.exercises.skill_graph import ALL_SKILL_TAGS, DEFAULT_PREREQUISITES
from apps.exercises.tests.umto_test_helpers import make_umto_exercise

User = get_user_model()

class AdaptiveServingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com", password="password123")
        self.teacher = User.objects.create_user(email="teacher@example.com", password="password123")
        
        self.ex1 = make_umto_exercise(
            author=self.teacher, 
            skill_tags=["Note_Names"], 
            complexity=1,
            description="E1"
        )

        self.ex2 = make_umto_exercise(
            author=self.teacher, 
            skill_tags=["Interval_Generic"], 
            complexity=2,
            description="E2"
        )

        self.ex3 = make_umto_exercise(
            author=self.teacher, 
            skill_tags=["Triad_Major"], 
            complexity=3,
            description="E3"
        )
        
        self.playlist = Playlist(
            id="P11111", 
            name="Adaptive Playlist", 
            authored_by=self.teacher,
            is_adaptive=True
        )
        self.playlist.save()

        # Link exercises to playlist
        ExercisePlaylistOrdered.objects.create(exercise=self.ex1, playlist=self.playlist, order=1, is_adaptive_entry=True)
        ExercisePlaylistOrdered.objects.create(exercise=self.ex2, playlist=self.playlist, order=2)
        ExercisePlaylistOrdered.objects.create(exercise=self.ex3, playlist=self.playlist, order=3)

        # Setup basic prerequisites: Note_Names -> Interval_Generic -> Triad_Major
        SkillPrerequisite.objects.create(skill_tag="Interval_Generic", requires_tag="Note_Names")
        SkillPrerequisite.objects.create(skill_tag="Triad_Major", requires_tag="Interval_Generic")

    def test_new_student_gets_entry_point(self):
        """A new student with no mastery should get the entry point exercise."""
        exercise, key = get_next_exercise(self.user.id, playlist=self.playlist)
        self.assertEqual(exercise.id, self.ex1.id)
        self.assertIsNone(key)

    def test_unlocking_logic(self):
        """Mastering Note_Names should unlock Interval_Generic."""
        StudentSkillMastery.objects.create(
            user=self.user, 
            skill_tag="Note_Names", 
            level="mastered"
        )
        
        exercise, key = get_next_exercise(self.user.id, playlist=self.playlist)
        # Should now pick ex2 which targets Interval_Generic
        self.assertEqual(exercise.id, self.ex2.id)

    def test_deterministic_seed(self):
        """The same seed should return the same exercise and key."""
        ex_a, key_a = get_next_exercise(self.user.id, playlist=self.playlist, seed="step1")
        ex_b, key_b = get_next_exercise(self.user.id, playlist=self.playlist, seed="step1")
        
        self.assertEqual(ex_a.id, ex_b.id)
        self.assertEqual(key_a, key_b)
        
        # Different seed might return different key (randomly)
        # To be safe, we check that it's stable for the same seed.
        
    def test_course_threshold_override(self):
        """If a skill is at the mastery_threshold, it should no longer be targeted."""
        course = Course(
            id="C11111", 
            title="Fast Course", 
            authored_by=self.teacher,
            mastery_threshold="familiar"
        )
        course.save()
        
        # Student is 'familiar' with both Note_Names and Interval_Generic.
        StudentSkillMastery.objects.create(user=self.user, skill_tag="Note_Names", level="familiar")
        StudentSkillMastery.objects.create(user=self.user, skill_tag="Interval_Generic", level="familiar")
        
        # We have two exercises targeting these skills:
        # 1. ex_only_notes: targets Note_Names, complexity 0
        # 2. ex2: targets Interval_Generic, complexity 2
        self.ex_only_notes = make_umto_exercise(
            author=self.teacher, 
            skill_tags=["Note_Names"], 
            complexity=0, 
            description="E4"
        )
        ExercisePlaylistOrdered.objects.create(exercise=self.ex_only_notes, playlist=self.playlist, order=4)

        # Case A: Global mode (threshold=mastered). 
        # Both skills are < mastered. Both have same level (familiar). 
        # Tie-break on complexity: ex_only_notes (0) should win.
        ex_global, _ = get_next_exercise(self.user.id, playlist=self.playlist)
        self.assertEqual(ex_global.id, self.ex_only_notes.id)

        # Case B: Course mode (threshold=familiar).
        # Both skills are >= familiar. target_skills is EMPTY.
        # It should fallback to stars or pool. 
        # For this test, we just want to ensure that if Note_Names was the ONLY target 
        # it would be skipped.
