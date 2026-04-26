from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist


User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class Unit1CurriculumIntegrationTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            id=36001,
            email="unit1-integration-student@test.com",
            password="testpass123",
            is_staff=False,
        )
        self.author = User.objects.create_user(
            id=36002,
            email="unit1-integration-author@test.com",
            password="x",
            is_staff=True,
        )
        self.client.force_login(self.student)
        self.identify_treble = self._create_canonical_lane(36100, "Unit 1 - Identify the Notes (Treble)")
        self.identify_bass = self._create_canonical_lane(36200, "Unit 1 - Identify the Notes (Bass)")
        self.play_from_name_treble = self._create_canonical_lane(36300, "Unit 1 - Play from Name (Treble)")
        self.play_from_name_bass = self._create_canonical_lane(36400, "Unit 1 - Play from Name (Bass)")
        self.play_the_notes_treble = self._create_canonical_lane(36500, "Unit 1 - Play the Notes (Treble)")
        self.play_the_notes_bass = self._create_canonical_lane(36600, "Unit 1 - Play the Notes (Bass)")
        self.legacy_identify_treble = self._create_canonical_lane(36700, "Unit 1 - Note Names (Treble)")
        self.legacy_play_from_name_treble = self._create_canonical_lane(36800, "Unit 1 - Note Names (Treble Name)")
        self.legacy_play_the_notes_treble = self._create_canonical_lane(36900, "Unit 1 - Note Names (Treble Play)")

    def _create_canonical_lane(self, pk, name):
        playlist = Playlist.objects.create(
            _id=pk,
            name=name,
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
            tags=["unit:1", "Note_Names"],
        )
        exercise = Exercise.objects.create(
            _id=pk + 50,
            description=name,
            data={"chord": []},
            authored_by=self.author,
            is_public=True,
            skill_tags=["unit:1", "Note_Names"],
        )
        ExercisePlaylistOrdered.objects.create(
            _id=pk + 100,
            playlist=playlist,
            exercise=exercise,
            order=1,
        )
        return playlist

    def test_unit1_page_shows_all_skill_lanes(self):
        response = self.client.get(
            reverse("student:unit-progress", kwargs={"unit_n": "1"})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identify")
        self.assertContains(response, "Play from Name")
        self.assertContains(response, "Play the Notes")
        self.assertContains(response, "Treble", count=3)
        self.assertContains(response, "Bass", count=3)
        self.assertContains(response, 'class="skill-card"', count=3, html=False)
        self.assertContains(response, 'class="playlist-row"', count=6, html=False)
        self.assertContains(
            response,
            f'playlist={self.identify_treble.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertContains(
            response,
            f'playlist={self.identify_bass.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertContains(
            response,
            f'playlist={self.play_from_name_treble.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertContains(
            response,
            f'playlist={self.play_from_name_bass.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertContains(
            response,
            f'playlist={self.play_the_notes_treble.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertContains(
            response,
            f'playlist={self.play_the_notes_bass.id}&amp;exercise_num=1',
            html=False,
        )
        self.assertNotContains(response, f"playlist={self.legacy_identify_treble.id}")
        self.assertNotContains(response, f"playlist={self.legacy_play_from_name_treble.id}")
        self.assertNotContains(response, f"playlist={self.legacy_play_the_notes_treble.id}")
        self.assertNotContains(response, "Ledger Lines")
        self.assertNotContains(response, "Clefs")
        self.assertNotContains(response, "Enharmonics")
