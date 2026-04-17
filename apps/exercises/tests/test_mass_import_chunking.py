import unittest
import music21
from apps.exercises.management.commands.mass_import_performance import split_score_into_chunks

class MassImportChunkingTests(unittest.TestCase):
    def test_split_score_with_rest_gap(self):
        # Create a simple stream with a gap in the middle
        score = music21.stream.Score()
        part = music21.stream.Part()
        
        # Measure 1: Notes
        m1 = music21.stream.Measure(number=1)
        m1.append(music21.note.Note('C4', type='whole'))
        part.append(m1)
        
        # Measure 2: Empty (Rest)
        m2 = music21.stream.Measure(number=2)
        m2.append(music21.note.Rest(type='whole'))
        part.append(m2)
        
        # Measure 3: Notes
        m3 = music21.stream.Measure(number=3)
        m3.append(music21.note.Note('D4', type='whole'))
        part.append(m3)
        
        score.append(part)
        
        # Run splitting algorithm
        chunks = split_score_into_chunks(score)
        
        # Assertions
        self.assertEqual(len(chunks), 2, "Score should be split into 2 chunks")
        
        # Chunk 1 should contain just measure 1
        chunk_1_measures = list(chunks[0].parts[0].getElementsByClass('Measure'))
        self.assertEqual(len(chunk_1_measures), 1)
        self.assertEqual(chunk_1_measures[0].number, 1)
        
        # Chunk 2 should contain just measure 3
        chunk_2_measures = list(chunks[1].parts[0].getElementsByClass('Measure'))
        self.assertEqual(len(chunk_2_measures), 1)
        self.assertEqual(chunk_2_measures[0].number, 3)

    def test_split_score_multiple_parts(self):
        score = music21.stream.Score()
        
        part1 = music21.stream.Part()
        part2 = music21.stream.Part()
        
        # M1: P1 has notes, P2 has rest. This is NOT an empty measure.
        m1_1 = music21.stream.Measure(number=1)
        m1_1.append(music21.note.Note('C4'))
        part1.append(m1_1)
        
        m1_2 = music21.stream.Measure(number=1)
        m1_2.append(music21.note.Rest(type='whole'))
        part2.append(m1_2)
        
        # M2: Both have rests. This IS an empty measure.
        m2_1 = music21.stream.Measure(number=2)
        m2_1.append(music21.note.Rest(type='whole'))
        part1.append(m2_1)
        
        m2_2 = music21.stream.Measure(number=2)
        m2_2.append(music21.note.Rest(type='whole'))
        part2.append(m2_2)
        
        # M3: Both have notes.
        m3_1 = music21.stream.Measure(number=3)
        m3_1.append(music21.note.Note('D4'))
        part1.append(m3_1)
        
        m3_2 = music21.stream.Measure(number=3)
        m3_2.append(music21.note.Note('F3'))
        part2.append(m3_2)
        
        score.append(part1)
        score.append(part2)
        
        chunks = split_score_into_chunks(score)
        
        self.assertEqual(len(chunks), 2, "Should split on the fully empty measure 2")
        self.assertEqual(list(chunks[0].parts[0].getElementsByClass('Measure'))[0].number, 1)
        self.assertEqual(list(chunks[1].parts[0].getElementsByClass('Measure'))[0].number, 3)
