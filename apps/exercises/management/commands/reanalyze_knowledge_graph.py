import os
import re
from django.core.management.base import BaseCommand
from apps.exercises.models import Exercise
from apps.exercises.utils.skills_analyzer import analyze_chunk_skills
from music21 import converter

class Command(BaseCommand):
    help = 'Re-analyze all exercises and apply the 5-branch Knowledge Graph taxonomy'

    def handle(self, *args, **options):
        exercises = Exercise.objects.all()
        self.stdout.write(f'Syncing {len(exercises)} exercises with Knowledge Graph...')
        
        count = 0
        for ex in exercises:
            try:
                # Seek the source file
                filename = ex.data.get('source', {}).get('originalPath')
                if not filename or not os.path.exists(filename):
                    basename = ex.data.get('source', {}).get('filename')
                    if basename:
                        # Check local scripts folder as fallback
                        possible_paths = [
                            os.path.join(os.getcwd(), 'scripts', 'bach_chorales', basename),
                        ]
                        for p in possible_paths:
                            if p and os.path.exists(p):
                                filename = p
                                break
                    
                score = None
                if filename and os.path.exists(filename):
                    score = converter.parse(filename)
                else:
                    # FALLBACK: Try music21 corpus if it looks like a Bach chorale
                    src_file = str(ex.data.get('source', {}).get('filename') or '').lower()
                    desc = str(ex.description or '').lower()
                    if 'bwv' in src_file or 'bwv' in desc:
                        # Try to find BWV X.Y
                        match = re.search(r'bwv\s?(\d+)\.(\d+)', src_file + desc)
                        if match:
                            bwv, move = match.groups()
                            try:
                                from music21 import corpus
                                score = corpus.parse(f'bach/bwv{bwv}.{move}')
                                self.stdout.write(f"  [CORPUS] Loaded BWV {bwv}.{move} for {ex.id}")
                            except:
                                pass

                if not score:
                    self.stdout.write(self.style.WARNING(f'  [SKIPPED] {ex.id}: No source score found'))
                    continue
                    
                # Analyze the score
                key_str = ex.data.get('key', 'C')
                detected_tags, complexity = analyze_chunk_skills(score, key_str)
                
                # Update Exercise record (ArrayField assignment)
                ex.complexity = complexity
                ex.skill_tags = list(detected_tags) 
                ex.save()
                
                count += 1
                self.stdout.write(self.style.SUCCESS(f'  [SYNCED] {ex.id} -> Unit {complexity} ({len(detected_tags)} tags)'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  [FAILED] {ex.id}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'\nKnowledge Graph Sync Complete: {count} exercises updated.'))
