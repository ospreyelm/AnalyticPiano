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

from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.umto import InteractionMode


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
            playlist = Playlist.objects.create(name=name, authored_by=author, is_public=True)
            self.stdout.write(f"Created/Using Playlist: {name}")

        # 5. The Translation & DB Injection logic
        from apps.exercises.models import Exercise, ExercisePlaylistOrdered
        
        for idx, chunk in enumerate(extracted_chunks):
            # Evaluate base properties
            measures = list(chunk.parts[0].getElementsByClass('Measure'))
            m_start = measures[0].number
            m_end = measures[-1].number
            self.stdout.write(f"  Processing Chunk {idx + 1}: mm. {m_start}-{m_end}")

            # Algorithmically determine the true tonal center and mode (e.g. "a" minor vs "C" major)
            # using music21's Krumhansl-Schmuckler analysis rather than blindly trusting the key signature.
            try:
                m21_key_obj = chunk.analyze('key')
                tonic = m21_key_obj.tonic.name.replace('-', 'b')
                mode_prefix = 'j' if m21_key_obj.mode == 'major' else 'i'
                chunk_key = f"{mode_prefix}{tonic}{'_' if len(tonic) == 1 else ''}"
            except Exception:
                # Absolute fallback if it's completely empty
                chunk_key = "jC_"
            
            # Convert to our CIR representation
            try:
                cir_data = m21_to_cir(chunk, key_override=chunk_key)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error converting to CIR: {e}"))
                continue
            
            meta_data = cir_data.get('meta', {})
            meta_data['key'] = chunk_key

            # Create Database Record
            description = f"Auto-Import: {os.path.basename(file_path)} (Chunk {idx+1}, mm.{m_start}-{m_end})"
            
            from apps.exercises.utils.skills_analyzer import analyze_chunk_skills
            try:
                detected_skills, detected_complexity = analyze_chunk_skills(chunk, chunk_key)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Warning: Skills analysis failed for chunk {idx+1}: {e}"))
                detected_skills, detected_complexity = [], 1

            # Build UMTO-specific kwargs
            umto_kwargs = {
                "exercise_id": "TEMP",
                "source": "mass_import",
                "key": chunk_key,
                "meter": chunk.getTimeSignatures()[0].ratioString if chunk.getTimeSignatures() else "4/4",
                "clef": "keyboard",
                "complexity_score": detected_complexity,
                "mode": InteractionMode.PLAYBACK,
            }

            # Create/Save via Factory
            ex = save_umto_exercise(
                description=description,
                score_data=cir_data,
                author=author,
                skill_tags=detected_skills,
                complexity=detected_complexity,
                is_public=False,
                umto_kwargs=umto_kwargs,
                overwrite=True
            )
            
            if playlist:
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=idx
                )
                
        self.stdout.write(self.style.SUCCESS('Mass Import Complete.'))
