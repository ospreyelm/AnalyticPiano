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
        # Canonical-save defaults: one unit, one mode, no playlist fields.
        payload.setdefault("skillTags", ["unit:11"])
        payload.setdefault("mode", "roman")
        payload.pop("playlistId", None)
        payload.pop("playlistName", None)
        payload.pop("modes", None)
        return self.client.post("/exercises/add/", data={"data": json.dumps(payload)})

    # ── Canonical-save contract ────────────────────────────────────────────────

    def test_save_creates_canonical_playlist_without_playlist_payload(self):
        response = self._post({"chord": self._chords(), "description": "First"})
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertIn("playlistId", body)
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")
        self.assertEqual(playlist.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
        self.assertEqual(playlist.canonical_unit, 11)
        self.assertEqual(playlist.canonical_mode, "roman")

    def test_different_descriptions_reuse_one_playlist(self):
        first = self._post({"chord": self._chords(), "description": "First"})
        second = self._post({"chord": self._chords(), "description": "Second"})
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(first.json()["playlistId"], second.json()["playlistId"])
        self.assertEqual(
            Playlist.objects.filter(
                authored_by=self.user,
                playlist_family=Playlist.FAMILY_TEACHER_PLAY,
                canonical_unit=11,
                canonical_mode="roman",
            ).count(),
            1,
        )

    def test_different_modes_use_different_playlists(self):
        roman = self._post({"chord": self._chords(), "mode": "roman"})
        play = self._post({"chord": self._chords(), "mode": "play"})
        self.assertEqual(roman.status_code, 201, roman.content)
        self.assertEqual(play.status_code, 201, play.content)
        self.assertNotEqual(roman.json()["playlistId"], play.json()["playlistId"])

    def test_multiple_modes_are_rejected(self):
        payload = {"chord": self._chords()}
        payload.pop("modes", None)
        payload["modes"] = ["play", "roman"]
        # Override _post defaults by posting directly so modes isn't popped.
        payload.setdefault("skillTags", ["unit:11"])
        response = self.client.post("/exercises/add/", data={"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)
        self.assertIn("exactly one", response.json()["error"].lower())

    def test_playlist_override_fields_are_rejected(self):
        payload = {
            "chord": self._chords(),
            "skillTags": ["unit:11"],
            "mode": "roman",
            "playlistId": "PA0001",
        }
        response = self.client.post("/exercises/add/", data={"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400)
        self.assertIn("automatic", response.json()["error"].lower())

    # ── Core field validation ──────────────────────────────────────────────────

    def test_default_behavior_unchanged(self):
        response = self._post({"chord": self._chords(), "key": "C", "staffDistribution": "keyboard"})
        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertEqual(exercise.description, "Play view chordal exercise")
        self.assertEqual(exercise.authored_by, self.user)
        self.assertFalse(exercise.is_public)
        self.assertEqual(exercise.skill_tags, ["unit:11"])

    def test_description_persisted(self):
        response = self._post({
            "chord": self._chords(),
            "description": "Unit 11 tonic triads",
        })
        self.assertEqual(response.status_code, 201, response.content)
        exercise = Exercise.objects.get(id=response.json()["id"])
        self.assertEqual(exercise.description, "Unit 11 tonic triads")

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

    def test_multiple_unit_tags_returns_400(self):
        payload = {
            "chord": self._chords(),
            "skillTags": ["unit:9", "unit:13"],
            "mode": "roman",
        }
        response = self.client.post("/exercises/add/", data={"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("unit", response.json()["error"].lower())

    def test_no_unit_tag_returns_400(self):
        payload = {
            "chord": self._chords(),
            "skillTags": ["Note_Names"],
            "mode": "roman",
        }
        response = self.client.post("/exercises/add/", data={"data": json.dumps(payload)})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("unit", response.json()["error"].lower())

    # ── Official / superuser saves ─────────────────────────────────────────────

    def test_save_as_official_superuser_uses_factory_author(self):
        self.client.force_login(self.superuser)
        response = self._post({
            "chord": self._chords(),
            "isPublic": True,
            "saveAsOfficial": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        exercise = Exercise.objects.get(id=body["id"])
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertEqual(exercise.authored_by, self.factory_user)
        self.assertEqual(playlist.authored_by, self.factory_user)
        self.assertTrue(exercise.is_public)
        self.assertTrue(playlist.is_public)

    def test_save_as_official_private_respects_editable_public_checkbox(self):
        """Official save with isPublic=False must not force exercise or playlist public."""
        self.client.force_login(self.superuser)
        response = self._post({
            "chord": self._chords(),
            "isPublic": False,
            "saveAsOfficial": True,
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        exercise = Exercise.objects.get(id=body["id"])
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertEqual(exercise.authored_by, self.factory_user)
        self.assertFalse(exercise.is_public)
        self.assertFalse(playlist.is_public)

    def test_save_as_official_sets_official_flag(self):
        self.client.force_login(self.superuser)
        response = self._post({
            "chord": self._chords(),
            "saveAsOfficial": True,
            "isPublic": True,
            "skillTags": ["unit:13", "Note_Names"],
        })
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        playlist = Playlist.objects.get(id=body["playlistId"])
        self.assertTrue(playlist.is_official)
        self.assertEqual(playlist.skill_tags, ["unit:13"])

    def test_save_as_official_non_superuser_returns_403(self):
        response = self._post({"chord": self._chords(), "saveAsOfficial": True})
        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.json())

    # ── Authoring meta ─────────────────────────────────────────────────────────

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
            [{"id": user_playlist.id, "name": "My Drafts", "locked": True, "skillTags": []}],
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
