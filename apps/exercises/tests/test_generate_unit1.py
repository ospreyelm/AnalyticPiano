import json
import os
import shutil
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import User
from apps.exercises.models import Course, Exercise, ExercisePlaylistOrdered, Playlist
from apps.exercises.management.commands import generate_unit1


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

        # 4. More than 3 repeated notes in a row (same pitch + octave) should be rejected
        self._create_chorale("too_many_repeats.json", "C", [
            ("C", 4, 0, True), ("C", 4, 0, True), ("C", 4, 0, True), ("C", 4, 0, True),
            ("G", 4, 0, True), ("C", 5, 0, True), ("G", 4, 0, True)
        ])

        # 5. More than 2 rests should be rejected
        self._create_chorale(
            "too_many_rests.json",
            "C",
            [
                ("C", 4, 0, True),
                ("G", 4, 0, True),
                {"kind": "rest", "duration": {"type": "q", "dots": 0}},
                ("C", 5, 0, True),
                {"kind": "rest", "duration": {"type": "q", "dots": 0}},
                ("G", 4, 0, True),
                ("C", 4, 0, True),
                {"kind": "rest", "duration": {"type": "q", "dots": 0}},
                ("G", 4, 0, True),
            ],
        )

        # 6. SATB sample to verify alto and tenor voice extraction is supported
        self._create_satb_chorale(
            "satb_voice_coverage.json",
            "C",
            {
                "soprano": [("C", 5), ("G", 5), ("E", 5), ("C", 5), ("G", 5), ("E", 5), ("C", 5), ("G", 5)],
                "alto": [("E", 4), ("C", 5), ("G", 4), ("E", 4), ("C", 5), ("G", 4), ("E", 4), ("C", 5)],
                "tenor": [("G", 3), ("C", 3), ("E", 3), ("G", 3), ("C", 3), ("E", 3), ("G", 3), ("C", 3)],
                "bass": [("C", 3), ("G", 2), ("C", 3), ("G", 2), ("C", 3), ("G", 2), ("C", 3), ("G", 2)],
            },
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_chorale(self, name, key_name, notes):
        path = os.path.join(self.test_dir, name)
        items = []
        for item in notes:
            if isinstance(item, dict):
                items.append(item)
                continue
            s, o, a, d = item
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

    def _create_satb_chorale(self, name, key_name, voices):
        def build_items(raw_notes):
            return [
                {
                    "kind": "note",
                    "pitch": {"step": s, "octave": o, "alter": 0, "is_diatonic": True},
                    "duration": {"type": "q", "dots": 0},
                }
                for s, o in raw_notes
            ]

        sop = build_items(voices["soprano"])
        alto = build_items(voices["alto"])
        tenor = build_items(voices["tenor"])
        bass = build_items(voices["bass"])

        payload = {
            "score": {
                "meta": {"key": key_name, "time": "4/4"},
                "measures": [
                    {
                        "number": 1,
                        "staves": {
                            "treble": {"voices": [{"items": sop[:4]}, {"items": alto[:4]}]},
                            "bass": {"voices": [{"items": tenor[:4]}, {"items": bass[:4]}]},
                        },
                    },
                    {
                        "number": 2,
                        "staves": {
                            "treble": {"voices": [{"items": sop[4:]}, {"items": alto[4:]}]},
                            "bass": {"voices": [{"items": tenor[4:]}, {"items": bass[4:]}]},
                        },
                    },
                ],
            }
        }
        path = os.path.join(self.test_dir, name)
        with open(path, "w") as f:
            json.dump(payload, f)

    def test_generate_unit1_categories(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")
        
        # Verify C major simple windows are Stage 1 (complexity 10)
        ex1 = Exercise.objects.filter(description__icontains="C_MAJOR_SIMPLE")
        self.assertTrue(ex1.exists())
        # The generator now uses S1 format
        self.assertTrue(all("S1" in e.description for e in ex1))
        self.assertTrue(all(e.complexity == 10 for e in ex1))
        
        # Verify G major diatonic windows are Stage 2 (complexity 21)
        ex2 = Exercise.objects.filter(description__icontains="G_MAJOR_DIATONIC")
        self.assertTrue(ex2.exists())
        self.assertTrue(all("S2" in e.description for e in ex2))
        self.assertTrue(all(e.complexity == 21 for e in ex2))
        
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

    def test_generate_unit1_creates_all_canonical_unit1_playlists(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        expected = {
            "Unit 1 - Note Names (Treble)",
            "Unit 1 - Note Names (Bass)",
            "Unit 1 - Note Names (Treble Name)",
            "Unit 1 - Note Names (Bass Name)",
            "Unit 1 - Note Names (Treble Play)",
            "Unit 1 - Note Names (Bass Play)",
        }
        actual = set(
            Playlist.objects.filter(authored_by=self.author, name__in=expected).values_list("name", flat=True)
        )
        self.assertEqual(actual, expected)

    def test_generate_unit1_recreates_missing_playlists_from_existing_exercises(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        Playlist.objects.filter(
            authored_by=self.author,
            name__in=[
                "Unit 1 - Note Names (Treble)",
                "Unit 1 - Note Names (Bass)",
                "Unit 1 - Note Names (Treble Name)",
                "Unit 1 - Note Names (Bass Name)",
                "Unit 1 - Note Names (Treble Play)",
                "Unit 1 - Note Names (Bass Play)",
            ],
        ).delete()

        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Treble)", authored_by=self.author).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Bass)", authored_by=self.author).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Treble Name)", authored_by=self.author).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Bass Name)", authored_by=self.author).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Treble Play)", authored_by=self.author).exists())
        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Bass Play)", authored_by=self.author).exists())

    def test_generate_unit1_rejects_repeated_note_runs_and_extra_rests(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")

        repeats_exists = Exercise.objects.filter(description__icontains="TOO_MANY_REPEATS").exists()
        rests_exists = Exercise.objects.filter(description__icontains="TOO_MANY_RESTS").exists()
        self.assertFalse(repeats_exists, "Windows with >3 identical consecutive notes should be excluded")
        self.assertFalse(rests_exists, "Windows with >2 rests should be excluded")

    def test_generate_unit1_supports_alto_and_tenor_generation(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        self.assertTrue(
            Exercise.objects.filter(description__icontains="SATB_VOICE_COVERAGE")
            .filter(description__icontains="Alto")
            .exists()
        )
        self.assertTrue(
            Exercise.objects.filter(description__icontains="SATB_VOICE_COVERAGE")
            .filter(description__icontains="Tenor")
            .exists()
        )

    def test_generate_unit1_enforces_playlist_cap(self):
        call_command(
            "generate_unit1",
            author=self.author.email,
            input_dir=self.test_dir,
            clef="both",
            max_per_playlist=12,
        )

        treble = Playlist.objects.get(name="Unit 1 - Note Names (Treble)")
        bass = Playlist.objects.get(name="Unit 1 - Note Names (Bass)")

        self.assertLessEqual(treble.exerciseplaylistordered_set.count(), 12)
        self.assertLessEqual(bass.exerciseplaylistordered_set.count(), 12)

    def test_generate_unit1_creates_matching_lane_exercises(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="treble")

        ex = Exercise.objects.filter(description__icontains="(exact)").first()
        self.assertIsNotNone(ex)

        payload = ex.data
        self.assertEqual(payload.get("type"), "umto_chorale")
        self.assertEqual(payload.get("mode"), "playback")
        self.assertTrue(payload.get("isUMTO"))
        self.assertIn("score", payload)
        self.assertIn("umto", payload["score"])

    def test_rebuild_unit1_playlists_is_idempotent(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        def snapshot_playlist_exercise_ids():
            snapshot = {}
            playlists = Playlist.objects.filter(name__icontains="Unit 1").order_by("name")
            for playlist in playlists:
                rows = (
                    playlist.exerciseplaylistordered_set.order_by("order", "exercise_id")
                    .values_list("exercise__id", flat=True)
                )
                snapshot[playlist.name] = list(rows)
            return snapshot

        call_command("rebuild_unit1_playlists", author=self.author.email)
        first = snapshot_playlist_exercise_ids()

        call_command("rebuild_unit1_playlists", author=self.author.email)
        second = snapshot_playlist_exercise_ids()

        self.assertEqual(first, second)

    def test_rebuild_unit1_playlists_skips_missing_playlists(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        Playlist.objects.filter(name="Unit 1 - Note Names (Bass Play)").delete()

        call_command("rebuild_unit1_playlists", author=self.author.email)

        self.assertTrue(Playlist.objects.filter(name="Unit 1 - Note Names (Treble)").exists())
        self.assertTrue(
            ExercisePlaylistOrdered.objects.filter(
                playlist__name="Unit 1 - Note Names (Treble)"
            ).exists()
        )

    def test_rebuild_unit1_playlists_separates_identify_and_matching(self):
        call_command("generate_unit1", author=self.author.email, input_dir=self.test_dir, clef="both")

        call_command("rebuild_unit1_playlists", author=self.author.email)

        treble_identify = Playlist.objects.get(name="Unit 1 - Note Names (Treble)")
        treble_play = Playlist.objects.get(name="Unit 1 - Note Names (Treble Play)")

        # Read data.mode in Python: values_list on a JSON key transform returns
        # raw JSON bytes on this driver instead of decoded strings.
        identify_types = {
            epo.exercise.data.get("mode")
            for epo in treble_identify.exerciseplaylistordered_set.select_related("exercise")
        }
        play_types = {
            epo.exercise.data.get("mode")
            for epo in treble_play.exerciseplaylistordered_set.select_related("exercise")
        }

        self.assertNotIn("playback", identify_types)
        self.assertEqual(play_types, {"playback"})

    def test_diatonic_index_round_trip_uses_expected_span(self):
        self.assertEqual(generate_unit1._step_octave_to_diatonic_index("C", 4), 0)
        self.assertEqual(generate_unit1._step_octave_to_diatonic_index("C", 7), 21)
        self.assertEqual(generate_unit1._step_octave_to_diatonic_index("C", 1), -21)

        self.assertEqual(generate_unit1._diatonic_index_to_step_octave(21), ("C", 7))
        self.assertEqual(generate_unit1._diatonic_index_to_step_octave(-21), ("C", 1))

    def test_bass_cumulative_sets_are_exact_signed_mirror(self):
        treble = generate_unit1._treble_cumulative_step_sets()
        bass = generate_unit1._bass_cumulative_step_sets()

        for stage in [1, 2, 3, 4]:
            mirrored = {
                generate_unit1._diatonic_index_to_step_octave(
                    -generate_unit1._step_octave_to_diatonic_index(step, octave)
                )
                for step, octave in treble[stage]
            }
            self.assertEqual(bass[stage], mirrored)
            self.assertEqual(len(bass[stage]), len(treble[stage]))
