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
from apps.exercises.models import Exercise

User = get_user_model()


class Command(BaseCommand):
    help = 'Import a chorale from data/corpus/bach as an Exercise'

    def add_arguments(self, parser):
        parser.add_argument('corpus_file', type=str, help='Filename in data/corpus/bach/')
        parser.add_argument('--author', type=str, required=True, help='Email of the exercise author')
        parser.add_argument('--start', type=int, default=0, help='Start measure (0-indexed)')
        parser.add_argument('--end', type=int, default=4, help='End measure (exclusive)')
        parser.add_argument('--mode', choices=['play', 'identify'], default='play', help='Exercise creation mode')
        parser.add_argument('--analysis', choices=['roman', 'figured_bass'], default='roman', help='Analysis label type for identify mode')
        parser.add_argument('--public', action='store_true', help='Make the exercise public')

    def handle(self, *args, **options):
        corpus_file = options['corpus_file']
        author_email = options['author']
        start_measure = options['start']
        end_measure = options['end']
        mode = options['mode']
        analysis_type = options['analysis']
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

        # Build exercise data
        bwv = corpus_file.replace('.json', '').upper()
        title = f"{bwv} (mm. {start_measure+1}–{end_measure})"

        if mode == 'identify':
            analysis_label = 'Roman numerals' if analysis_type == 'roman' else 'figured bass'
            exercise_data = {
                "type": "chorale_identification",
                "identMode": "submit",
                "analysisType": analysis_type,
                "score": {
                    "meta": meta,
                    "measures": excerpt_measures
                },
                "introText": f"Label the {analysis_label} for {bwv}, measures {start_measure+1}–{end_measure}.",
                "reviewText": f"Well done! You labeled all chords for {bwv}, measures {start_measure+1}–{end_measure}.",
                "key": meta.get("key", "C"),
                "staffDistribution": "chorale"
            }
            title = f"{bwv} identification ({analysis_type}, mm. {start_measure+1}–{end_measure})"
        else:
            exercise_data = {
                "type": "chorale",
                "mode": "play-all-voices",
                "score": {
                    "meta": meta,
                    "measures": excerpt_measures
                },
                "targetVoices": "all",
                "display": {
                    "showFigures": False,
                    "showRomans": False,
                    "transpose": 0,
                    "tempo": 60
                },
                "grading": {
                    "onsetWindowMs": 150,
                    "releaseTolerancePct": 40,
                    "octaveFlexible": False
                },
                "excerpt": {
                    "startMeasure": start_measure,
                    "endMeasure": end_measure
                },
                "introText": f"Play all four voices of {bwv}, measures {start_measure+1}–{end_measure}. Use the keyboard or MIDI controller to play each note as it appears. Notes turn black when played correctly.",
                "reviewText": f"Well done! You completed {bwv}, measures {start_measure+1}–{end_measure}.",
                # Legacy fields for compatibility
                "key": meta.get("key", "C"),
                "keySignature": meta.get("key", "C"),
                "staffDistribution": "chorale"
            }

        # Create the Exercise
        exercise = Exercise(
            description=title,
            data=exercise_data,
            authored_by=author,
            is_public=is_public
        )
        exercise.save()

        self.stdout.write(self.style.SUCCESS(
            f'Successfully created exercise {exercise.id}: {title}'
        ))
        self.stdout.write(f'  Measures: {len(excerpt_measures)}')
        self.stdout.write(f'  Key: {meta.get("key", "?")}')
        self.stdout.write(f'  Time: {meta.get("time", "?")}')
