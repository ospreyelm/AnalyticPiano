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
from apps.exercises.umto import InteractionMode

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

    def test_unauthenticated_requests_redirect(self):
        """Unauthenticated requests to preview and save should redirect to login."""
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

        # Preview redirect
        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

        # Save redirect
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {"musicxml_file": uploaded, "description": "Test"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_staff_teacher_forbidden(self):
        """Teachers without staff status should receive a 403 Forbidden."""
        self.client.login(email="regular_teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

        # Preview Forbidden
        response = self.client.post(
            reverse("teacher:import-musicxml-preview"),
            {"musicxml_file": uploaded}
        )
        self.assertEqual(response.status_code, 403)

        # Save Forbidden
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {"musicxml_file": uploaded, "description": "Test"}
        )
        self.assertEqual(response.status_code, 403)

    def test_preview_monophonic_chordal_route(self):
        """1-part score should parse, auto-detect C major, and route to chordal."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

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
        uploaded = SimpleUploadedFile("test.xml", self.voices_xml_bytes, content_type="text/xml")

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

    def test_save_chordal_exercise_success(self):
        """Saving a chordal score creates the Exercise, tags, and links to target playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

        # Create playlist
        playlist = Playlist.objects.create(
            name="My Playlist",
            authored_by=self.staff_teacher,
            is_public=True,
        )

        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded,
                "description": "My Chordal Import",
                "unit": "11",
                "tags": "Cadence_Half, custom_tag",
                "mode": "roman",
                "playlist_id": playlist.id,
                "harmony_key": "jC_",
                "complexity": 2,
            }
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["success"])

        # Check database
        exercise = Exercise.objects.get(id=data["id"])
        self.assertEqual(exercise.description, "My Chordal Import")
        self.assertEqual(exercise.complexity, 2)
        self.assertIn("unit:11", exercise.skill_tags)
        self.assertIn("Cadence_Half", exercise.skill_tags)
        self.assertIn("custom_tag", exercise.skill_tags)

        # Confirm score kind is chordal and display mode set
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["score_kind"], "chordal")
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["mode"], "roman")
        self.assertEqual(exercise.data["display"]["showRomans"], True)

        # Confirm playlist mapping
        mapping = ExercisePlaylistOrdered.objects.get(playlist=playlist, exercise=exercise)
        self.assertEqual(mapping.order, 1)

    def test_save_voices_exercise_success(self):
        """Saving a multipart score creates a voices UMTO exercise."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.voices_xml_bytes, content_type="text/xml")

        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded,
                "description": "My Voices Import",
                "unit": "9, 10",
                "mode": "play",
                "harmony_key": "jC_",
                "complexity": 5,
            }
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["success"])

        # Check database
        exercise = Exercise.objects.get(id=data["id"])
        self.assertEqual(exercise.description, "My Voices Import")
        self.assertEqual(exercise.complexity, 5)
        self.assertIn("unit:9", exercise.skill_tags)
        self.assertIn("unit:10", exercise.skill_tags)
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["score_kind"], "voices")
        self.assertEqual(exercise.data["score"]["umto"]["metadata"]["mode"], "playback")

    def test_save_new_playlist_creation_and_adaptive(self):
        """Saving to a new playlist should create the playlist and respect adaptive flag."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded,
                "description": "Adaptive test",
                "playlist_name": "New Adaptive Playlist",
                "is_adaptive": "true",
                "harmony_key": "jC_",
            }
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()

        playlist = Playlist.objects.get(id=data["playlistId"])
        self.assertEqual(playlist.name, "New Adaptive Playlist")
        self.assertTrue(playlist.is_adaptive)
        self.assertEqual(playlist.authored_by, self.staff_teacher)

    def test_save_official_requires_superuser(self):
        """Only superusers can save official exercises, authored by the factory user."""
        uploaded1 = SimpleUploadedFile("test1.xml", self.chordal_xml_bytes, content_type="text/xml")
        uploaded2 = SimpleUploadedFile("test2.xml", self.chordal_xml_bytes, content_type="text/xml")
 
        # Staff user gets 403
        self.client.login(email="teacher@example.com", password="testpass123")
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded1,
                "description": "Official attempt",
                "save_as_official": "true",
            }
        )
        self.assertEqual(response.status_code, 403)
 
        # Superuser succeeds
        self.client.login(email="super@example.com", password="testpass123")
        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded2,
                "description": "Official success",
                "save_as_official": "true",
            }
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()

        exercise = Exercise.objects.get(id=data["id"])
        self.assertTrue(exercise.is_official)
        self.assertEqual(exercise.authored_by, self.factory_user)

    def test_save_with_transpositions(self):
        """Saving with create_transpositions=true should create transpositions in the playlist."""
        self.client.login(email="teacher@example.com", password="testpass123")
        uploaded = SimpleUploadedFile("test.xml", self.chordal_xml_bytes, content_type="text/xml")

        playlist = Playlist.objects.create(
            name="Transposition Playlist",
            authored_by=self.staff_teacher,
        )

        response = self.client.post(
            reverse("teacher:import-musicxml-save"),
            {
                "musicxml_file": uploaded,
                "description": "Transposition base",
                "playlist_id": playlist.id,
                "harmony_key": "jC_",
                "create_transpositions": "true",
                "key_set": "G, Am",
            }
        )
        self.assertEqual(response.status_code, 201)

        # Base plus 2 transposed exercises = 3 exercises total in playlist
        mappings = ExercisePlaylistOrdered.objects.filter(playlist=playlist)
        self.assertEqual(mappings.count(), 3)

        # Check description and keys
        exercises = [m.exercise for m in mappings]
        descriptions = [ex.description for ex in exercises]
        self.assertIn("Transposition base", descriptions)
        self.assertIn("Transposition base (G)", descriptions)
        self.assertIn("Transposition base (Am)", descriptions)
