import unittest
from music21 import stream, chord, pitch

from apps.exercises.utils.skills_analyzer import analyze_chunk_skills


class SkillsAnalyzerTests(unittest.TestCase):
    def build_chunk(self, pitches_list):
        s = stream.Score()
        p = stream.Part()
        for pitches in pitches_list:
            c = chord.Chord(pitches)
            c.quarterLength = 1.0
            p.append(c)
        s.append(p)
        return s

    def test_diatonic_triads_and_pac(self):
        # C Major: I - IV - V - I
        chunk = self.build_chunk([
            ['C4', 'E4', 'G4'], 
            ['F4', 'A4', 'C5'], 
            ['G4', 'B4', 'D5'], 
            ['C4', 'E4', 'G4']
        ])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Diatonic_Triads', skills)
        self.assertIn('Cadence_Perfect_Authentic', skills)
        self.assertEqual(complexity, 9)

    def test_inversions(self):
        # C Major: I6 - V6/4
        chunk = self.build_chunk([
            ['E4', 'G4', 'C5'], 
            ['D4', 'G4', 'B4']
        ])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Inversions_First', skills)
        self.assertIn('Inversions_Second', skills)
        self.assertEqual(complexity, 12)

    def test_dominant_seventh(self):
        # C Major: V7
        chunk = self.build_chunk([['G4', 'B4', 'D5', 'F5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Dominant_Seventh', skills)
        self.assertEqual(complexity, 9)

    def test_secondary_dominant(self):
        # C Major: V/V (D major triad) -> V
        chunk = self.build_chunk([['D4', 'F#4', 'A4'], ['G4', 'B4', 'D5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Secondary_Dominant', skills)
        self.assertEqual(complexity, 16)

    def test_secondary_leading_tone(self):
        # C Major: vii°7/V (F# fully dim 7)
        chunk = self.build_chunk([['F#4', 'A4', 'C5', 'E-5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Secondary_Leading_Tone', skills)
        self.assertEqual(complexity, 16)

    def test_neapolitan(self):
        # C Major: N6 (Db major triad in first inversion)
        chunk = self.build_chunk([['F4', 'A-4', 'D-5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Neapolitan_Sixth', skills)
        self.assertNotIn('Secondary_Dominant', skills)
        self.assertEqual(complexity, 18)

    def test_augmented_sixth(self):
        # C Major: It+6 (Ab C F#)
        chunk = self.build_chunk([['A-3', 'C4', 'F#4']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Augmented_Sixth', skills)
        self.assertEqual(complexity, 18)

    def test_cadence_plagal(self):
        # C Major: IV - I
        chunk = self.build_chunk([['F4', 'A4', 'C5'], ['C4', 'E4', 'G4']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Cadence_Plagal', skills)

    def test_cadence_deceptive(self):
        # C Major: V - vi
        chunk = self.build_chunk([['G4', 'B4', 'D5'], ['A4', 'C5', 'E5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Cadence_Deceptive', skills)

    def test_cadence_half(self):
        # C Major: phrase finishes on V
        chunk = self.build_chunk([['C4', 'E4', 'G4'], ['G4', 'B4', 'D5']])
        skills, complexity = analyze_chunk_skills(chunk, 'C')
        self.assertIn('Cadence_Half', skills)

    def test_picardy_third(self):
        # C minor ending on C major triad
        chunk = self.build_chunk([['G4', 'B4', 'D5'], ['C4', 'E4', 'G4']])
        skills, complexity = analyze_chunk_skills(chunk, 'c')
        self.assertIn('Picardy_Third', skills)
        self.assertEqual(complexity, 6)
