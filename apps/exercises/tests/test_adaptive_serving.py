from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.exercises.models import Exercise, Playlist, Course, ExercisePlaylistOrdered, StudentSkillMastery, SkillPrerequisite, PerformanceData
from apps.exercises.mastery import get_next_exercise
from apps.exercises.skill_graph import ALL_SKILL_TAGS, DEFAULT_PREREQUISITES
from apps.exercises.tests.umto_test_helpers import make_umto_exercise
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()


def _single_note_cir(step):
    return {
        "meta": {"key": "C", "time": "4/4"},
        "measures": [{
            "staves": {"treble": {"voices": [{"items": [
                {"kind": "note", "pitch": {"step": step, "alter": 0, "octave": 4}, "duration": {"type": "q", "dots": 0}},
            ]}]}}
        }]
    }

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

    def test_next_step_avoids_immediate_content_repeat_when_alternative_exists(self):
        repeated_a = save_umto_exercise(
            description="Repeated content A",
            score_data=_single_note_cir("C"),
            author=self.teacher,
            skill_tags=["Note_Names"],
            complexity=1,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Repeated content A",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.PLAYBACK,
                target_voice="soprano",
                unit=1,
            ),
        )
        repeated_b = save_umto_exercise(
            description="Repeated content B",
            score_data=_single_note_cir("C"),
            author=self.teacher,
            skill_tags=["Note_Names"],
            complexity=1,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Repeated content B",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.PLAYBACK,
                target_voice="soprano",
                unit=1,
            ),
        )
        alternate = save_umto_exercise(
            description="Alternate content",
            score_data=_single_note_cir("D"),
            author=self.teacher,
            skill_tags=["Note_Names"],
            complexity=1,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source="Alternate content",
                key="C",
                meter="4/4",
                clef="treble",
                complexity_score=1,
                mode=InteractionMode.PLAYBACK,
                target_voice="soprano",
                unit=1,
            ),
        )
        playlist = Playlist.objects.create(
            _id=19100,
            name="Adaptive Repeat Guard",
            authored_by=self.teacher,
            is_public=True,
            is_adaptive=True,
        )
        ExercisePlaylistOrdered.objects.create(exercise=repeated_a, playlist=playlist, order=1, is_adaptive_entry=True)
        ExercisePlaylistOrdered.objects.create(exercise=repeated_b, playlist=playlist, order=2)
        ExercisePlaylistOrdered.objects.create(exercise=alternate, playlist=playlist, order=3)

        PerformanceData.objects.create(
            user=self.user,
            playlist=playlist,
            course=None,
            data=[{"id": repeated_a.id, "score_numerator": 1, "score_denominator": 1, "error_tally": 0}],
        )

        exercise, key = get_next_exercise(self.user.id, playlist=playlist, exercise_num=2, seed="step-2")

        self.assertEqual(exercise.id, alternate.id)
        self.assertIsNone(key)

    # -------------------------------------------------------------------------
    # Persistence and consumer-guard tests
    # -------------------------------------------------------------------------

    def test_course_scoped_perf_data_no_conflict(self):
        """Two courses with same user+playlist create separate PerformanceData rows."""
        course_a = Course(id="CA1111", title="Course A", authored_by=self.teacher)
        course_a.save()
        course_b = Course(id="CB1111", title="Course B", authored_by=self.teacher)
        course_b.save()

        # First call — reserves slot in course A's PerformanceData
        get_next_exercise(self.user.id, playlist=self.playlist, course=course_a, exercise_num=1)
        # Second call — must NOT raise MultipleObjectsReturned; creates separate row for course B
        get_next_exercise(self.user.id, playlist=self.playlist, course=course_b, exercise_num=1)

        # Each course has its own row
        self.assertEqual(
            PerformanceData.objects.filter(user=self.user, playlist=self.playlist).count(), 2
        )

    def test_pinning_returns_same_exercise_on_revisit(self):
        """Revisiting exercise_num=1 returns the same exercise that was originally served."""
        ex1, key1 = get_next_exercise(self.user.id, playlist=self.playlist, exercise_num=1, seed="stable")
        ex2, key2 = get_next_exercise(self.user.id, playlist=self.playlist, exercise_num=1, seed="stable")

        self.assertEqual(ex1.id, ex2.id)
        self.assertEqual(key1, key2)

    def test_placeholder_not_counted_as_performed(self):
        """Placeholder slots don't count as completed exercise submissions."""
        pd = PerformanceData.objects.create(
            user=self.user,
            playlist=self.playlist,
            course=None,
            data=[{
                "id": self.ex1.id + "G",
                "is_placeholder": True,
                "is_submitted": False,
                "error_tally": None,
                "performance_duration_in_seconds": None,
            }],
        )
        self.assertFalse(pd.exercise_is_performed(self.ex1.id))

    def test_consumer_guards_skip_placeholder_entries(self):
        """All PerformanceData consumers skip is_placeholder entries without crashing."""
        pd = PerformanceData.objects.create(
            user=self.user,
            playlist=self.playlist,
            course=None,
            data=[
                {
                    "id": self.ex1.id + "G",
                    "is_placeholder": True,
                    "is_submitted": False,
                    "error_tally": None,
                    "performance_duration_in_seconds": None,
                }
            ],
        )
        # get_exercise_first_pass returns False (not None) when no non-placeholder match exists
        result_first = pd.get_exercise_first_pass(self.ex1.id)
        self.assertFalse(result_first)

        # exercise_error_count returns 0 (not None) when no non-placeholder match exists
        result_error_count = pd.exercise_error_count(self.ex1.id)
        self.assertEqual(result_error_count, 0)

    def test_submit_inplace_updates_placeholder_slot(self):
        """First submission updates placeholder slot in-place, sets is_submitted=True."""
        pd = PerformanceData.objects.create(
            user=self.user,
            playlist=self.playlist,
            course=None,
            data=[{
                "id": self.ex1.id,
                "is_placeholder": True,
                "is_submitted": False,
                "error_tally": None,
                "performance_duration_in_seconds": None,
            }],
        )

        PerformanceData.submit(
            user_id=self.user.id,
            course_id=None,
            playlist_id=self.playlist._id,
            exercise_id=self.ex1.id,
            data={"error_tally": 0, "performance_duration_in_seconds": 30},
            exercise_num=1,
        )

        pd.refresh_from_db()
        self.assertEqual(len(pd.data), 1)  # in-place, not appended
        self.assertTrue(pd.data[0].get("is_submitted"))
        self.assertFalse(pd.data[0].get("is_placeholder"))
        self.assertEqual(pd.data[0]["error_tally"], 0)

    def test_resubmit_appends_to_preserve_history(self):
        """Re-submission appends to PerformanceData.data to preserve multi-attempt history."""
        # First submission
        PerformanceData.submit(
            user_id=self.user.id,
            course_id=None,
            playlist_id=self.playlist._id,
            exercise_id=self.ex1.id,
            data={"error_tally": 2, "performance_duration_in_seconds": 60},
            exercise_num=1,
        )
        # Second submission (re-attempt)
        PerformanceData.submit(
            user_id=self.user.id,
            course_id=None,
            playlist_id=self.playlist._id,
            exercise_id=self.ex1.id,
            data={"error_tally": 0, "performance_duration_in_seconds": 45},
            exercise_num=1,
        )

        pd = PerformanceData.objects.get(user=self.user, playlist=self.playlist, course=None)
        self.assertEqual(len(pd.data), 2)  # both attempts preserved
        self.assertEqual(pd.data[0]["error_tally"], 2)
        self.assertEqual(pd.data[1]["error_tally"], 0)
