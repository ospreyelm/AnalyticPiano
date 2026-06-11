from django.test import SimpleTestCase


class KeyNormalizationTest(SimpleTestCase):
    def test_harmony_key_to_music21_major_natural(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("jC_"), "C")
        self.assertEqual(harmony_key_to_music21("jG_"), "G")

    def test_harmony_key_to_music21_major_accidentals(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("jBb"), "Bb")
        self.assertEqual(harmony_key_to_music21("jF#"), "F#")

    def test_harmony_key_to_music21_minor(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("iA_"), "A minor")
        self.assertEqual(harmony_key_to_music21("iF#"), "F# minor")
        self.assertEqual(harmony_key_to_music21("iBb"), "Bb minor")

    def test_harmony_key_to_music21_accepts_clean_existing_names(self):
        from apps.exercises.utils.key_normalization import harmony_key_to_music21

        self.assertEqual(harmony_key_to_music21("C"), "C")
        self.assertEqual(harmony_key_to_music21("F#m"), "F# minor")
        self.assertEqual(harmony_key_to_music21("A minor"), "A minor")
        self.assertEqual(harmony_key_to_music21(None), "C")
        self.assertEqual(harmony_key_to_music21(""), "C")
