import json
import os
import shutil
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Course, Exercise, Playlist


class GenerateUnit1Tests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="teacher@example.com", password="pw")
        self.test_dir = "data/corpus/unit1_test"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # 1. Simple C Major Diatonic (Stage 1) - Steps C, G
        self._create_chorale("c_major_simple.json", "C", [
            ("C", 4, 0, True), ("G", 4, 0, True), ("C", 5, 0, True), 
            ("G", 4, 0, True), ("C", 4, 0, True), ("G", 4, 0, True), ("C", 5, 0, True)
        ])
        
        # 2. G Major Diatonic F# (Stage 2) - Includes F# which is Step F (+ C, G, B, D)
        # G4, D4, B4, F#4, G4, D4, B4
        self._create_chorale("g_major_diatonic.json", "G", [
            ("G", 4, 0, True), ("D", 4, 0, True), ("B", 4, 0, True), 
            ("F", 4, 1, True), ("G", 4, 0, True), ("D", 4, 0, True), ("B", 4, 0, True)
        ])
        
        # 3. E Major Chromatic C Natural (Stage 5) - C is Chromatic here
        self._create_chorale("e_major_chromatic.json", "E", [
            ("E", 4, 0, True), ("B", 4, 0, True), ("C", 5, 0, False), 
            ("E", 4, 0, True), ("B", 4, 0, True), ("C", 5, 0, False), ("E", 4, 0, True)
        ])

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_chorale(self, name, key_name, notes):
        path = os.path.join(self.test_dir, name)
        items = []
        for s, o, a, d in notes:
            items.append({
                "kind": "note",
                "pitch": {"step": s, "octave": o, "alter": a, "is_diatonic": d},
                "duration": {"type": "q", "dots": 0}
            })
            
        payload = {
            "score": {
                "meta": {"key": key_name, "time": "4/4"},
                "measures": [
                    {"number": 1, "staves": {"treble": {"voices": [{"items": items[:4]}]}}},
                    {"number": 2, "staves": {"treble": {"voices": [{"items": items[4:]}]}}},
                ]
            }
        }
        with open(path, "w") as f:
            json.dump(payload, f)

    def test_generate_unit1_categories(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
        
        # Verify C major simple is Stage 1 (complexity 10)
        ex1 = Exercise.objects.get(description__icontains="C_MAJOR_SIMPLE")
        self.assertEqual(ex1.complexity, 10) # Stage 1 * 10 + 0 accidentals
        
        # Verify G major diatonic is Stage 2 (complexity 21)
        ex2 = Exercise.objects.get(description__icontains="G_MAJOR_DIATONIC")
        self.assertEqual(ex2.complexity, 21) # Stage 2 * 10 + 1 accidental
        
        # Verify E major chromatic IS GONE
        exists = Exercise.objects.filter(description__icontains="E_MAJOR_CHROMATIC").exists()
        self.assertFalse(exists, "Chromatic exercises should be excluded from Unit 1")

    def test_generate_unit1_is_idempotent(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
        count = Exercise.objects.count()
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
        self.assertEqual(count, Exercise.objects.count())

    def test_generate_unit1_links_course(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
        self.assertTrue(Course.objects.filter(title="Unit 1: Pitch & Staff Notation").exists())
        self.assertTrue(Playlist.objects.filter(name__icontains="Unit 1").exists())
