"""
Management command to import a single chorale as an exercise.

Usage:
  python manage.py import_chorale <corpus_file> --author=<email>

Example:
  python manage.py import_chorale bwv1.6.json --author=admin@example.com
"""
import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()


PITCH_ANALYSIS_TYPES = (
    'note_name',
    'solfege',
    'do_based_solfege',
    'scale_degree',
    'fixed_do',
    'pitch_class',
)


class Command(BaseCommand):
    help = 'Import a chorale from data/corpus/bach as an Exercise'

    def add_arguments(self, parser):
        parser.add_argument('corpus_file', type=str, help='Filename in data/corpus/bach/')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--start', type=int, default=0, help='Start measure (0-indexed)')
        parser.add_argument('--end', type=int, default=4, help='End measure (exclusive)')
        parser.add_argument('--mode', choices=['play', 'identify'], default='play', help='Exercise creation mode')
        parser.add_argument(
            '--analysis',
            choices=['roman', 'figured_bass', 'interval_generic', 'interval_specific', *PITCH_ANALYSIS_TYPES],
            default='roman',
            help='Analysis label type for identify mode',
        )
        parser.add_argument('--voice', choices=['soprano', 'alto', 'tenor', 'bass'], help='Voice to isolate for pitch-based identify mode')
        parser.add_argument('--compound', action='store_true', default=False, help='Allow compound intervals (default: reduce to within octave). Only applies to interval analysis types.')
        parser.add_argument('--public', action='store_true', help='Make the exercise public')

    def handle(self, *args, **options):
        corpus_file = options['corpus_file']
        author_email = options['author']
        start_measure = options['start']
        end_measure = options['end']
        mode = options['mode']
        analysis_type = options['analysis']
        voice_name = options.get('voice')
        compound = options['compound']
        is_public = options['public']

        # Find the author
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        # Load the corpus JSON
        corpus_path = os.path.join('data', 'corpus', 'bach', corpus_file)
        if not os.path.exists(corpus_path):
            raise CommandError(f'Corpus file not found: {corpus_path}')

        with open(corpus_path, 'r') as f:
            corpus_data = json.load(f)

        score = corpus_data.get('score', {})
        meta = score.get('meta', {})
        measures = score.get('measures', [])

        if not measures:
            raise CommandError('No measures found in corpus file')

        # Extract excerpt
        excerpt_measures = measures[start_measure:end_measure]
        if not excerpt_measures:
            raise CommandError(f'No measures in range [{start_measure}:{end_measure}]')

        def count_voices(selected_measures):
            if not selected_measures:
                return 0
            first = selected_measures[0].get('staves', {})
            return sum(len(stave.get('voices', [])) for stave in first.values())

        if analysis_type in ('interval_generic', 'interval_specific'):
            voice_count = count_voices(excerpt_measures)
            if voice_count != 2:
                raise CommandError(
                    f'Interval identification requires exactly 2 voices; '
                    f'found {voice_count} in {corpus_file}.'
                )

        # Build exercise data
        bwv = corpus_file.replace('.json', '').upper()
        title = f"{bwv} (mm. {start_measure+1}–{end_measure})"

        # Build UMTO Interaction Mode
        if mode == 'play':
            umto_mode = InteractionMode.PLAYBACK
        elif analysis_type in ('roman', 'figured_bass'):
            umto_mode = InteractionMode.ANALYSIS_MATCH
        else:
            umto_mode = InteractionMode.IDENTIFICATION

        # Build intro text
        if umto_mode == InteractionMode.PLAYBACK:
            intro = f"Play all four voices of {bwv}, mm. {start_measure+1}–{end_measure}."
        elif analysis_type in ('interval_generic', 'interval_specific'):
            intro = f"Identify the {analysis_type.replace('_', ' ')} in this excerpt of {bwv}, mm. {start_measure+1}–{end_measure}."
        else:
            intro = f"Label the {analysis_type.replace('_', ' ')} for {bwv}, mm. {start_measure+1}–{end_measure}."

        score_for_umto = {
            'meta': meta,
            'measures': excerpt_measures,
        }

        # Detect skill tags via music21 analysis
        from apps.exercises.utils.skills_analyzer import analyze_chunk_skills
        from apps.exercises.utils.music21_builder import build_score_from_data

        detected_skills = []
        detected_complexity = 1
        try:
            # Build music21 score from the chorale data
            chunk_score = build_score_from_data({
                'score': {
                    'meta': meta,
                    'measures': excerpt_measures
                }
            })
            detected_skills, detected_complexity = analyze_chunk_skills(chunk_score, meta.get("key", "C"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Warning: Skills analysis failed: {e}'))

        # Determine primary clef for UMTO metadata
        # If it's a single voice, use its clef. Otherwise assume keyboard/chorale layout.
        primary_clef = meta.get("clef", "treble")
        
        # Create the Exercise via UMTO factory
        exercise = save_umto_exercise(
            description=title,
            score_data=score_for_umto,
            author=author,
            skill_tags=detected_skills,
            complexity=detected_complexity,
            is_public=is_public,
            umto_kwargs=dict(
                exercise_id="TEMP",
                source=intro,
                key=meta.get("key", "C"),
                meter=meta.get("time", "4/4"),
                clef=primary_clef,
                complexity_score=detected_complexity,
                mode=umto_mode,
                target_voice=voice_name,
            )
        )

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created UMTO exercise {exercise.id}: {title}'
        ))
        self.stdout.write(f'  Mode: {umto_mode}')
        self.stdout.write(f'  Measures: {len(excerpt_measures)}')
        self.stdout.write(f'  Key: {meta.get("key", "?")}')
        self.stdout.write(f'  Time: {meta.get("time", "?")}')
