import json
from django.core.management.base import BaseCommand
from apps.exercises.models import Playlist, Exercise

class Command(BaseCommand):
    help = 'Ensures Unit 1 exercises are correctly tagged with skill tags for the student app.'

    def handle(self, *args, **options):
        # We target exercises in Unit 1 playlists
        # Map of skill tags to their primary Unit 1 playlist identifiers (tags)
        unit1_skills = ["Note_Names", "Ledger_Lines", "clefs", "enharmonic"]
        
        count = 0
        for tag in unit1_skills:
            # Find playlists for this skill in Unit 1
            playlists = Playlist.objects.filter(tags__contains=["unit:1"]).filter(tags__contains=[tag])
            
            for pl in playlists:
                self.stdout.write(f"Processing playlist: {pl.name} (Tag: {tag})")
                for ex in pl.exercises.all():
                    modified = False
                    
                    # Ensure unit:1 is in skill_tags
                    if "unit:1" not in ex.skill_tags:
                        ex.skill_tags.append("unit:1")
                        modified = True
                        
                    # Ensure the specific skill is in skill_tags
                    if tag not in ex.skill_tags:
                        ex.skill_tags.append(tag)
                        modified = True
                        
                    if modified:
                        ex.save()
                        count += 1
                        
        self.stdout.write(self.style.SUCCESS(f"Successfully tagged/updated {count} exercises for Unit 1."))
