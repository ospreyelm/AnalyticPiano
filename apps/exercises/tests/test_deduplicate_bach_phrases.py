from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.tests.umto_test_helpers import make_umto_exercise


User = get_user_model()


class DeduplicateBachPhrasesCommandTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")

    def test_dry_run_does_not_delete_duplicates(self):
        make_umto_exercise(author=self.author, skill_tags=["unit:9", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")
        make_umto_exercise(author=self.author, skill_tags=["unit:10", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")

        call_command("deduplicate_bach_phrases", author="teacher@example.com")

        self.assertEqual(Exercise.objects.filter(description="Bach R1 - Phrase 1 (mm.1-4) [roman]").count(), 2)

    def test_execute_deletes_unreferenced_duplicate(self):
        keep = make_umto_exercise(author=self.author, skill_tags=["unit:9", "unit:10", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")
        remove = make_umto_exercise(author=self.author, skill_tags=["unit:10", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")

        call_command("deduplicate_bach_phrases", author="teacher@example.com", execute=True)

        self.assertTrue(Exercise.objects.filter(pk=keep.pk).exists())
        self.assertFalse(Exercise.objects.filter(pk=remove.pk).exists())

    def test_execute_preserves_referenced_duplicate(self):
        make_umto_exercise(author=self.author, skill_tags=["unit:9", "unit:10", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")
        referenced = make_umto_exercise(author=self.author, skill_tags=["unit:10", "mode:roman"], complexity=1, description="Bach R1 - Phrase 1 (mm.1-4) [roman]")
        playlist = Playlist.objects.create(name="Unit 10 Test", authored_by=self.author, skill_tags=["unit:10"])
        ExercisePlaylistOrdered.objects.create(playlist=playlist, exercise=referenced, order=1)

        call_command("deduplicate_bach_phrases", author="teacher@example.com", execute=True)

        self.assertTrue(Exercise.objects.filter(pk=referenced.pk).exists())
