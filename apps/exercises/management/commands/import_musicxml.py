import json
import os
import glob
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

# Import analysis and conversion utilities
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../scripts'))
try:
    from fetch_bach_chorales import m21_to_cir, build_events
except ImportError:
    m21_to_cir = None
    build_events = None

from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills

User = get_user_model()


class Command(BaseCommand):
    help = 'Import MusicXML files/directories as Exercises using music21 → CIR pipeline with Auto-Tagging'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Path to MusicXML file or directory')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--public', action='store_true', help='Make the exercises public')
        parser.add_argument('--start', type=int, default=0, help='Start measure (0-indexed, default: 0)')
        parser.add_argument('--end', type=int, default=None, help='End measure (exclusive, default: all)')

    def handle(self, *args, **options):
        path = options['path']
        author_email = options['author']
        is_public = options['public']

        # Check dependencies
        if m21_to_cir is None or build_events is None:
            raise CommandError('Could not import converter functions. Ensure scripts/fetch_bach_chorales.py exists.')

        # Find the author
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        # Determine file list
        if os.path.isfile(path):
            files = [path]
        elif os.path.isdir(path):
            files = []
            for ext in ('*.xml', '*.musicxml', '*.mxl'):
                files.extend(glob.glob(os.path.join(path, '**', ext), recursive=True))
        else:
            raise CommandError(f'Path not found: {path}')

        if not files:
            self.stdout.write(self.style.WARNING(f'No MusicXML files found in {path}'))
            return

        self.stdout.write(f'Integrating {len(files)} files into Knowledge Graph...')
        
        success_count = 0
        for f in files:
            try:
                exercise = self.process_file(f, author, is_public, options)
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f'  [SUCCESS] {os.path.basename(f)} -> ID: {exercise.id}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [FAILED] {os.path.basename(f)}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nBulk Ingestion Complete: {success_count}/{len(files)} exercises imported.'))

    def process_file(self, file_path, author, is_public, options):
        from music21 import converter
        
        start_measure = options['start']
        end_measure = options['end']

        # Load MusicXML
        score = converter.parse(file_path)

        # Detect Key
        try:
            m21_key = score.analyze('key')
            tonic = m21_key.tonic.name
            if "-" in tonic:
                hl_tonic = tonic[0] + "b"
            elif "#" in tonic:
                hl_tonic = tonic
            else:
                hl_tonic = tonic + "_"
            mode_prefix = "j" if m21_key.mode == "major" else "i"
            harmony_key = mode_prefix + hl_tonic
        except Exception:
            harmony_key = "jC_"

        # Convert to CIR
        cir = m21_to_cir(score, key_override=harmony_key)
        meta = cir.get('meta', {})
        measures = cir.get('measures', [])

        if not measures:
            raise Exception('No measures found')

        # Extract excerpt
        excerpt_measures = measures[start_measure:end_measure] if end_measure else measures[start_measure:]
        measure_range = f"mm. {start_measure+1}–{end_measure}" if end_measure else f"complete"

        basename = os.path.basename(file_path)
        title = os.path.splitext(basename)[0]

        # AUTO-ANALysis for Knowledge Graph
        # We analyze the score to get Unit tags and complexity
        detected_tags, complexity = analyze_chunk_skills(score, harmony_key)

        # Use UMTO factory for persistence
        score_data = {"meta": meta, "measures": excerpt_measures}
        
        exercise = save_umto_exercise(
            description=title,
            score_data=score_data,
            author=author,
            skill_tags=list(detected_tags),
            complexity=complexity,
            is_public=is_public,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source=f"Play {title}.",
                key=harmony_key,
                meter=meta.get("time", "4/4"),
                clef=meta.get("clef", "treble"),
                complexity_score=complexity,
                mode=InteractionMode.PLAYBACK,
            )
        )

        return exercise

