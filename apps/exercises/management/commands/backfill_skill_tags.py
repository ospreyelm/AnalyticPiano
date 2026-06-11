from django.core.management.base import BaseCommand
from django.core.paginator import Paginator

from apps.exercises.models import Exercise
from apps.exercises.utils.music21_builder import build_score_from_data
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills

class Command(BaseCommand):
    help = 'Backfill Knowledge Graph skill tags for existing exercises.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all exercises, overwriting existing skill tags. If empty, only processes exercises with empty tags.',
        )

    def handle(self, *args, **options):
        process_all = options['all']
        
        if process_all:
            exercises = Exercise.objects.all()
            self.stdout.write("Targeting ALL exercises to rebuild skill tags (overwriting existing).")
        else:
            exercises = Exercise.objects.filter(skill_tags=[])
            self.stdout.write("Targeting only exercises with empty skill tags.")
            
        total = exercises.count()
        self.stdout.write(f"Found {total} exercises to backfill.")
        
        paginator = Paginator(exercises, 1000)
        
        processed_count = 0
        error_count = 0
        failure_counts = {
            "no_source_score": 0,
            "no_measures": 0,
            "invalid_key": 0,
            "music21_error": 0,
        }
        
        for page_num in paginator.page_range:
            self.stdout.write(f"Processing page {page_num} of {paginator.num_pages}...")
            
            for ex in paginator.page(page_num).object_list:
                try:
                    # Get the key
                    ex_key = ex.data.get('key', 'C')
                    
                    # Convert JSON data back into a music21 stream/score to analyze
                    chunk_score = build_score_from_data(ex.data)
                    
                    detected_skills, detected_complexity = analyze_chunk_skills(
                        chunk_score, 
                        ex_key,
                        description=ex.description
                    )
                except Exception as e:
                    error_text = str(e)
                    if "Cannot make a step out of 'J'" in error_text:
                        failure_counts["invalid_key"] += 1
                    elif "No measures found" in error_text:
                        failure_counts["no_measures"] += 1
                    elif not (ex.data or {}).get("score"):
                        failure_counts["no_source_score"] += 1
                    else:
                        failure_counts["music21_error"] += 1
                    self.stdout.write(self.style.WARNING(f"  Warning: Skipping exercise {ex.id}: {e}"))
                    error_count += 1
                    continue
                
                ex.skill_tags = detected_skills
                ex.complexity = detected_complexity
                ex.save(update_fields=['skill_tags', 'complexity'])
                processed_count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Backfill complete. Processed: {processed_count}. Errors: {error_count}.'))
        self.stdout.write(f"Failure categories: {failure_counts}")
