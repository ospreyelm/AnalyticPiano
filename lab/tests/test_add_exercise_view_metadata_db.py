import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, PerformanceData, Playlist


User = get_user_model()


class AddExerciseViewMetadataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="metadata@example.com", password="x")
        self.other_user = User.objects.create_user(email="other-metadata@example.com", password="x")
        self.superuser = User.objects.create_superuser(email="super-metadata@example.com", password="x")
        self.factory_user = User.objects.create_user(email=settings.FACTORY_USER_EMAIL, password="x")
        self.client.force_login(self.user)

    def _chords(self):
        return [
            {"offset": float(i), "duration": 1.0, "visible": [60, 64, 67], "hidden": []}
            for i in range(4)
        ]

    def _post(self, payload):
        return self.client.post("/exercises/add/", data={"data": json.dumps(payload)})

    def test_default_behavior_unchanged(self):
        response = self._post({"chord": self._chords(), "key": "C", "staffDistribution": "keyboard"})

        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertEqual(exercise.description, "Play view chordal exercise")
        self.assertEqual(exercise.authored_by, self.user)
        self.assertFalse(exercise.is_public)
        self.assertEqual(exercise.skill_tags, [])

    def test_description_persisted(self):
        response = self._post({
            "chord": self._chords(),
            "description": "Unit 1 tonic triads",
        })

        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertEqual(exercise.description, "Unit 1 tonic triads")

    def test_valid_skill_tags_persist(self):
        response = self._post({
            "chord": self._chords(),
            "skillTags": ["unit:1", "Note_Names", "cadence/authentic#1"],
        })

        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertEqual(exercise.skill_tags, ["unit:1", "Note_Names", "cadence/authentic#1"])

    def test_invalid_skill_tag_format_returns_400(self):
        response = self._post({"chord": self._chords(), "skillTags": ["bad tag"]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_unknown_unit_tag_returns_400(self):
        response = self._post({"chord": self._chords(), "skillTags": ["unit:99999"]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("unit", response.json()["error"])

    def test_is_public_persisted(self):
        response = self._post({"chord": self._chords(), "isPublic": True})

        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertTrue(exercise.is_public)

    def test_playlist_name_creates_playlist_and_appends_at_order_one(self):
        response = self._post({"chord": self._chords(), "playlistName": "Unit 1 Drafts"})

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        playlist = Playlist.objects.get(id=body["playlistId"])
        exercise = Exercise.objects.get(id=body["id"])
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, exercise=exercise)
        self.assertEqual(body["playlistName"], "Unit 1 Drafts")
        self.assertEqual(playlist.name, "Unit 1 Drafts")
        self.assertEqual(playlist.authored_by, self.user)
        self.assertEqual(link.order, 1)

    def test_multi_mode_new_playlist_splits_into_one_playlist_per_mode(self):
        response = self._post({
            "chord": self._chords(),
            "modes": ["play", "roman"],
            "playlistName": "Unit 13 Drafts",
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(len(body["ids"]), 2)
        self.assertIn("playlists", body)
        self.assertEqual(len(body["playlists"]), 2)

        play_playlist = Playlist.objects.get(name="Unit 13 Drafts (play)")
        roman_playlist = Playlist.objects.get(name="Unit 13 Drafts (roman)")
        self.assertNotEqual(play_playlist.id, roman_playlist.id)

        play_exercise = Exercise.objects.get(id=body["ids"][0])
        roman_exercise = Exercise.objects.get(id=body["ids"][1])
        self.assertTrue(
            ExercisePlaylistOrdered.objects.filter(playlist=play_playlist, exercise=play_exercise).exists()
        )
        self.assertTrue(
            ExercisePlaylistOrdered.objects.filter(playlist=roman_playlist, exercise=roman_exercise).exists()
        )
        self.assertFalse(
            ExercisePlaylistOrdered.objects.filter(playlist=play_playlist, exercise=roman_exercise).exists()
        )

    def test_single_mode_new_playlist_uses_plain_name(self):
        response = self._post({
            "chord": self._chords(),
            "modes": ["play"],
            "playlistName": "Unit 13 Drafts Solo",
        })

        self.assertEqual(response.status_code, 201, response.content)
        playlist = Playlist.objects.get(name="Unit 13 Drafts Solo")
        self.assertEqual(response.json()["playlistName"], "Unit 13 Drafts Solo")
        self.assertEqual(playlist.name, "Unit 13 Drafts Solo")

    def test_multi_mode_existing_playlist_id_shares_one_playlist(self):
        playlist = Playlist.objects.create(name="Shared Existing", authored_by=self.user)

        response = self._post({
            "chord": self._chords(),
            "modes": ["play", "roman"],
            "playlistId": playlist.id,
        })

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(
            ExercisePlaylistOrdered.objects.filter(playlist=playlist).count(), 2
        )

    def test_playlist_id_appends_at_next_order(self):
        playlist = Playlist.objects.create(name="Existing Drafts", authored_by=self.user)
        existing = self._post({"chord": self._chords()}).json()["id"]
        ExercisePlaylistOrdered.objects.create(
            playlist=playlist,
            exercise=Exercise.objects.get(id=existing),
            order=3,
        )

        response = self._post({"chord": self._chords(), "playlistId": playlist.id})

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["playlistId"], playlist.id)
        self.assertEqual(body["playlistName"], "Existing Drafts")
        link = ExercisePlaylistOrdered.objects.get(playlist=playlist, exercise__id=body["id"])
        self.assertEqual(link.order, 4)

    def test_wrong_owner_playlist_id_returns_400(self):
        playlist = Playlist.objects.create(name="Someone Else", authored_by=self.other_user)

        response = self._post({"chord": self._chords(), "playlistId": playlist.id})

        self.assertEqual(response.status_code, 400)
        self.assertIn("playlist", response.json()["error"])

    def test_locked_playlist_id_returns_400(self):
        playlist = Playlist.objects.create(name="Performed", authored_by=self.user)
        PerformanceData.objects.create(user=self.other_user, playlist=playlist, data=[])

        response = self._post({"chord": self._chords(), "playlistId": playlist.id})

        self.assertEqual(response.status_code, 400)
        self.assertIn("locked", response.json()["error"])

    def test_playlist_id_and_name_returns_400(self):
        playlist = Playlist.objects.create(name="Existing Drafts", authored_by=self.user)

        response = self._post({
            "chord": self._chords(),
            "playlistId": playlist.id,
            "playlistName": "New Drafts",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("playlistId", response.json()["error"])

    def test_save_as_official_superuser_uses_factory_author_and_forces_public(self):
        self.client.force_login(self.superuser)

        response = self._post({
            "chord": self._chords(),
            "isPublic": False,
            "saveAsOfficial": True,
            "playlistName": "Factory Unit 1",
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        exercise = Exercise.objects.get(id=body["id"])
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertEqual(exercise.authored_by, self.factory_user)
        self.assertTrue(exercise.is_public)
        self.assertEqual(playlist.authored_by, self.factory_user)
        self.assertTrue(playlist.is_public)

    def test_save_as_official_new_playlist_sets_official_and_skill_tags(self):
        self.client.force_login(self.superuser)

        response = self._post({
            "chord": self._chords(),
            "saveAsOfficial": True,
            "playlistName": "Factory Unit 13",
            "skillTags": ["unit:13", "Note_Names"],
        })

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertTrue(playlist.is_official)
        self.assertEqual(playlist.skill_tags, ["unit:13", "Note_Names"])

    def test_save_as_official_non_superuser_returns_403(self):
        response = self._post({"chord": self._chords(), "saveAsOfficial": True})

        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

    def test_authoring_meta_returns_units_playlists_and_superuser_flag(self):
        user_playlist = Playlist.objects.create(name="My Drafts", authored_by=self.user)
        factory_playlist = Playlist.objects.create(name="Factory Drafts", authored_by=self.factory_user)
        PerformanceData.objects.create(user=self.other_user, playlist=user_playlist, data=[])

        response = self.client.get("/exercises/authoring-meta/")

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertFalse(body["isSuperuser"])
        self.assertTrue(any(unit["n"] == 1 and unit["title"] for unit in body["units"]))
        self.assertEqual(
            body["playlists"],
            [{"id": user_playlist.id, "name": "My Drafts", "locked": True}],
        )

        self.client.force_login(self.superuser)
        response = self.client.get("/exercises/authoring-meta/")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["isSuperuser"])
        playlist_ids = {playlist["id"] for playlist in body["playlists"]}
        self.assertIn(factory_playlist.id, playlist_ids)

    def test_authoring_meta_anonymous_requires_login(self):
        self.client.logout()

        response = self.client.get("/exercises/authoring-meta/")

        self.assertIn(response.status_code, (302, 403))
