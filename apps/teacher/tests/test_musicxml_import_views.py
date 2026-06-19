"""Tests for the MusicXML import API views."""

import json
import os
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings

from music21 import stream, note, chord, meter

from apps.accounts.models import ROLE_TEACHER
from apps.exercises.models import Exercise, Playlist, ExercisePlaylistOrdered

User = get_user_model()


def make_test_musicxml_bytes(parts_data):
    """
    Generate valid MusicXML bytes using music21.
    parts_data is a list of lists of note names, e.g. [["C4", "E4"], ["G4", "B4"]]
    """
    score = stream.Score()
    score.append(meter.TimeSignature("4/4"))
    for idx, notes in enumerate(parts_data):
        part = stream.Part()
        part.id = f"part_{idx}"
        part.partName = f"Part {idx}"
        measure = stream.Measure(number=1)
        ql = 4.0 / len(notes) if notes else 4.0
        for n in notes:
            measure.append(note.Note(n, quarterLength=ql))
        part.append(measure)
        score.append(part)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
        tmp_path = tmp.name
    try:
        score.write("musicxml", fp=tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return data


class MusicXMLImportViewsTest(TestCase):
    """Test both preview and save MusicXML endpoints."""

    def setUp(self):
        self.client = Client()

        # Create a teacher user who is staff
        self.staff_teacher = User.objects.create_user(
            email="teacher@example.com",
            password="testpass123",
            role=ROLE_TEACHER,
            is_staff=True,
        )

        # Create a non-staff teacher user
        self.regular_teacher = User.objects.create_user(
            email="regular_teacher@example.com",
            password="testpass123",
            role=ROLE_TEACHER,
            is_staff=False,
        )

        # Create a superuser
        self.superuser = User.objects.create_superuser(
            email="super@example.com",
            password="testpass123",
        )

        # Ensure factory user exists for official tests
        factory_email = getattr(settings, "FACTORY_USER_EMAIL", "factory@example.com")
        self.factory_user, _ = User.objects.get_or_create(
            email=factory_email,
            defaults={"is_staff": True, "is_superuser": True}
        )

        # Pre-generate simple 1-part (chordal) and 4-part (voices) xml bytes
        self.chordal_xml_bytes = make_test_musicxml_bytes([["C4", "E4", "G4", "C5"]])
        self.voices_xml_bytes = make_test_musicxml_bytes([["C5"], ["G4"], ["E4"], ["C3"]])

    def _make_uploaded(self, data=None):
        return SimpleUploadedFile("test.xml", data or self.chordal_xml_bytes, content_type="text/xml")

    def _post_save(self, extra=None, xml_data=None):
        """POST to the save endpoint with canonical-save defaults."""
        payload = {
            "musicxml_file": self._make_uploaded(xml_data),
            "description": "Imported cadence",
            "unit": "11",
            "mode": "roman",
            "harmony_key": "jC_",
        }
        if extra:
            payload.update(extra)
        return self.client.post(reverse("teacher:import-musicxml-save"), payload)

    # ── Auth/permission ────────────────────────────────────────────────────────

    def test_unauthenticated_requests_redirect(self):
        """Unauthenticated requests to preview and save should redirect to login."""
        uploaded = self._make_uploaded()
        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

        uploaded = self._make_uploaded()
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {"musicxml_file": uploaded, "description": "Test"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_teacher_forbidden(self):
        """Teachers without staff status should receive a 403 Forbidden."""
        self.client.login(email="regular_teacher@example.com", password="testpass123")

        uploaded = self._make_uploaded()
        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 403)

        uploaded = self._make_uploaded()
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {"musicxml_file": uploaded, "description": "Test"}
        )
        self.assertEqual(response.status_code, 403)

    # ── Preview ────────────────────────────────────────────────────────────────

    def test_preview_monophonic_chordal_route(self):
        """1-part score should parse, auto-detect C major, and route to chordal."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = self._make_uploaded()

        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["route"], "chordal")
        self.assertEqual(data["key"], "jC_")
        self.assertEqual(data["title"], "test")
        self.assertIn("payload", data)
        self.assertEqual(data["payload"]["score"]["umto"]["metadata"]["score_kind"], "chordal")

    def test_preview_multipart_voices_route(self):
        """4-part score should parse, detect key, and route to voices."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = self._make_uploaded(self.voices_xml_bytes)

        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["route"], "voices")
        self.assertEqual(data["title"], "test")
        self.assertIn("payload", data)
        self.assertEqual(data["payload"]["isUMTO"], True)

    # ── Canonical-save contract ────────────────────────────────────────────────

    def test_save_automatically_creates_canonical_playlist(self):
        """Saving without a playlist target creates the canonical playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({"description": "Imported cadence"})
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertTrue(data["success"])
        playlist = Playlist.objects.get(id=data["playlistId"])
        self.assertEqual(playlist.name, "Unit 11 — Exercises (Roman)")
        self.assertEqual(playlist.playlist_family, Playlist.FAMILY_TEACHER_PLAY)
        self.assertEqual(playlist.canonical_unit, 11)
        self.assertEqual(playlist.canonical_mode, "roman")

    def test_repeated_musicxml_saves_reuse_destination(self):
        """Saving twice with the same unit+mode reuses the canonical playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        first = self._post_save({"description": "First import"})
        second = self._post_save({"description": "Second import"})
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(first.json()["playlistId"], second.json()["playlistId"])

    def test_musicxml_and_composed_save_share_destination_identity(self):
        """MusicXML save and composed (AddExerciseView) save land in the same canonical playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")

        # Composed save via AddExerciseView
        import json as _json
        composed_payload = {
            "chord": [
                {"offset": float(i), "duration": 1.0, "visible": [60, 64, 67], "hidden": []}
                for i in range(4)
            ],
            "skillTags": ["unit:11"],
            "mode": "roman",
        }
        composed_resp = self.client.post(
            "/exercises/add/",
            data={"data": _json.dumps(composed_payload)},
        )
        self.assertEqual(composed_resp.status_code, 201, composed_resp.content)

        # MusicXML save
        imported_resp = self._post_save({"description": "Imported"})
        self.assertEqual(imported_resp.status_code, 201, imported_resp.content)

        self.assertEqual(composed_resp.json()["playlistId"], imported_resp.json()["playlistId"])

    def test_musicxml_rejects_multiple_modes(self):
        """Sending multiple modes must return 400 with 'exactly one' message."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": self._make_uploaded(),
                "description": "Multi-mode attempt",
                "unit": "11",
                "modes": ["play", "roman"],
                "harmony_key": "jC_",
            },
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("exactly one", response.json()["error"].lower())

    def test_musicxml_rejects_playlist_id_override(self):
        """Sending playlist_id must return 400 with 'automatic' message."""
        self.client.login(email="teacher@example.com", password="testpass123")
        playlist = Playlist.objects.create(name="Existing", authored_by=self.staff_teacher)
        response = self._post_save({"playlist_id": playlist.id})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("automatic", response.json()["error"].lower())

    def test_save_voices_exercise_canonical(self):
        """Saving a multipart score creates a voices UMTO exercise in the canonical playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save(
            {"description": "My Voices Import", "mode": "play", "complexity": 5},
            xml_data=self.voices_xml_bytes,
        )
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertTrue(data["success"])
        exercise = Exercise.objects.get(id=data["id"])
        self.assertEqual(exercise.description, "My Voices Import")
        self.assertEqual(exercise.complexity, 5)
        self.assertIn("unit:11", exercise.skill_tags)
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["score_kind"], "voices")
        playlist = Playlist.objects.get(id=data["playlistId"])
        self.assertEqual(playlist.name, "Unit 11 — Exercises (Play)")

    def test_save_chordal_exercise_with_tags_and_key(self):
        """Saving a chordal score persists extra skill_tags, key, complexity, and display mode."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({
            "description": "My Chordal Import",
            "tags": "Cadence_Half, custom_tag",
            "mode": "roman",
            "complexity": 2,
        })
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        exercise = Exercise.objects.get(id=data["id"])
        self.assertEqual(exercise.description, "My Chordal Import")
        self.assertEqual(exercise.complexity, 2)
        self.assertIn("unit:11", exercise.skill_tags)
        self.assertIn("Cadence_Half", exercise.skill_tags)
        self.assertIn("custom_tag", exercise.skill_tags)
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["score_kind"], "chordal")
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["mode"], "roman")
        self.assertEqual(exercise.data["display"]["showRomans"], True)

    # ── Official saves ─────────────────────────────────────────────────────────

    def test_save_official_requires_superuser(self):
        """Only superusers can save official exercises, authored by the factory user."""
        # Staff user gets 403
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({"save_as_official": "true"})
        self.assertEqual(response.status_code, 403)

        # Superuser succeeds
        self.client.login(email="super@example.com", password="testpass123")
        response = self._post_save({"save_as_official": "true", "is_public": "true"})
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        exercise = Exercise.objects.get(id=data["id"])
        self.assertTrue(exercise.is_official)
        self.assertEqual(exercise.authored_by, self.factory_user)

    def test_save_official_sets_playlist_official(self):
        """Official save propagates is_official onto the canonical playlist."""
        self.client.login(email="super@example.com", password="testpass123")
        response = self._post_save({
            "save_as_official": "true",
            "is_public": "true",
            "unit": "13",
        })
        self.assertEqual(response.status_code, 201, response.content)
        playlist = Playlist.objects.get(id=response.json()["playlistId"])
        self.assertTrue(playlist.is_official)
        self.assertEqual(playlist.skill_tags, ["unit:13"])

    def test_save_official_private_respects_editable_public_checkbox(self):
        """Official save with is_public=false must not force exercise or playlist public."""
        self.client.login(email="super@example.com", password="testpass123")
        response = self._post_save({"save_as_official": "true", "is_public": "false"})
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        exercise = Exercise.objects.get(id=data["id"])
        playlist = Playlist.objects.get(id=data["playlistId"])
        self.assertFalse(exercise.is_public)
        self.assertFalse(playlist.is_public)

    def test_multiple_modes_rejects_with_400(self):
        """Canonical API requires exactly one mode; multi-mode is not supported."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": self._make_uploaded(),
                "description": "Multi mode",
                "unit": "11",
                "modes": ["play", "roman"],
                "harmony_key": "jC_",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("exactly one", response.json()["error"].lower())

    # ── Transpositions ─────────────────────────────────────────────────────────

    def test_save_with_transpositions(self):
        """Saving with create_transpositions=true creates transposed copies in the canonical playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self._post_save({
            "description": "Transposition base",
            "create_transpositions": "true",
            "key_set": "G, Am",
        })
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        playlist = Playlist.objects.get(id=data["playlistId"])

        # Base plus 2 transposed exercises = 3 exercises total in playlist
        mappings = ExercisePlaylistOrdered.objects.filter(playlist=playlist)
        self.assertEqual(mappings.count(), 3)
        descriptions = [m.exercise.description for m in mappings]
        self.assertIn("Transposition base", descriptions)
        self.assertIn("Transposition base (G)", descriptions)
        self.assertIn("Transposition base (Am)", descriptions)
