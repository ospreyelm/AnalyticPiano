import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone

import music21

# Import the converter from the fetch_bach_chorales script for CIR mapping
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../scripts'))
try:
    from fetch_bach_chorales import m21_to_cir
except ImportError:
    m21_to_cir = None


def split_score_into_chunks(score):
    """
    Splits a music21 score into multiple smaller score chunks, separated by
    measures where all parts have no notes (only rests/metadata).
    """
    parts = score.parts
    if not parts:
        return []

    # Get the measures from the first part to determine the bounds
    first_part_measures = list(parts[0].getElementsByClass('Measure'))
    num_measures = len(first_part_measures)
    
    chunks = []
    current_chunk_measures = []
    
    for idx in range(num_measures):
        measure_has_notes = False
        
        # Check if ANY part has notes in this measure index
        for part in parts:
            measures = list(part.getElementsByClass('Measure'))
            if idx < len(measures):
                m = measures[idx]
                if len(m.notes) > 0:
                    measure_has_notes = True
                    break
                    
        if measure_has_notes:
            current_chunk_measures.append(idx)
        else:
            if current_chunk_measures:
                chunks.append(current_chunk_measures)
                current_chunk_measures = []
                
    if current_chunk_measures:
        chunks.append(current_chunk_measures)
        
    extracted_scores = []
    for chunk_indices in chunks:
        start_idx = chunk_indices[0]
        end_idx = chunk_indices[-1]
        
        start_m_num = first_part_measures[start_idx].number
        end_m_num = first_part_measures[end_idx].number
        
        # Extract the score for these measure bounds
        sub_score = score.measures(start_m_num, end_m_num)
        extracted_scores.append(sub_score)
        
    return extracted_scores


class Command(BaseCommand):
    help = 'Mass import performance data from MusicXML, auto-splitting by rests.'

    def add_arguments(self, parser):
        parser.add_argument('musicxml_file', type=str, help='Path to the MusicXML file')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--course', type=str, help='Optional Title of the course to add these to')

    def handle(self, *args, **options):
        file_path = options['musicxml_file']
        author_email = options['author']
        course_title = options.get('course')

        # 1. Validate Author
        User = get_user_model()
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        # 2. Validate File
        if not os.path.exists(file_path):
            raise CommandError(f'MusicXML file not found: {file_path}')

        self.stdout.write(f"Author validated: {author.email}")
        self.stdout.write(f"Loading {file_path} via music21...")

        # 3. Parse with music21
        try:
            score = music21.converter.parse(file_path)
            self.stdout.write(self.style.SUCCESS('Successfully loaded MusicXML.'))
        except Exception as e:
            raise CommandError(f"Failed to parse MusicXML: {e}")

        if m21_to_cir is None:
            raise CommandError("Could not import m21_to_cir. Check script path.")

        # 4. Auto-Split
        self.stdout.write("Analyzing gaps and splitting...")
        extracted_chunks = split_score_into_chunks(score)
        
        self.stdout.write(self.style.SUCCESS(f"Identified {len(extracted_chunks)} distinct exercises."))
        
        # We will optionally tie these to a playlist if a course is specified
        playlist = None
        if course_title:
            from apps.exercises.models import Playlist
            name = f"Recent Imports ({timezone.now().strftime('%Y-%m-%d')}) - {course_title}"
            playlist = Playlist.objects.create(name=name, authored_by=author)
            self.stdout.write(f"Created/Using Playlist: {name}")

        # 5. The Translation & DB Injection logic
        from apps.exercises.models import Exercise, ExercisePlaylistOrdered
        
        for idx, chunk in enumerate(extracted_chunks):
            # Evaluate base properties
            measures = list(chunk.parts[0].getElementsByClass('Measure'))
            m_start = measures[0].number
            m_end = measures[-1].number
            self.stdout.write(f"  Processing Chunk {idx + 1}: mm. {m_start}-{m_end}")

            # Extract key signature if possible, or analyze
            key_sig = chunk.flatten().getElementsByClass(music21.key.KeySignature)
            if key_sig:
                chunk_key = key_sig[0].asKey().name
            else:
                chunk_key = chunk.analyze('key').name
            
            # Convert to our CIR representation
            try:
                cir_data = m21_to_cir(chunk)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error converting to CIR: {e}"))
                continue
            
            # Build base exercise JSON payload
            exercise_data = {
                "type": "musicxml",  # Use the generic CIR-capable type
                "mode": "play-all-voices",
                "score": {
                    "meta": cir_data.get('meta', {}),
                    "measures": cir_data.get('measures', [])
                },
                "source": {
                    "type": "mass_import",
                    "filename": os.path.basename(file_path),
                    "chunk": idx + 1
                },
                "targetVoices": "all",
                "display": {
                    "showFigures": False,
                    "showRomans": False,
                    "transpose": 0,
                    "tempo": 60
                },
                "introText": "Play the exercise as written.",
                "staffDistribution": "keyboard"
            }

            # Create Database Record
            description = f"Auto-Import: {os.path.basename(file_path)} (Chunk {idx+1}, mm.{m_start}-{m_end})"
            
            ex = Exercise(
                description=description,
                data=exercise_data,
                authored_by=author,
                is_public=False
            )
            ex.save()
            
            if playlist:
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=idx
                )
                
        self.stdout.write(self.style.SUCCESS('Mass Import Complete.'))
