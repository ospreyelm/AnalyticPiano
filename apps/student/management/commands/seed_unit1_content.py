from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.exercises.models import Playlist, Exercise, Course, PlaylistCourseOrdered

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds Unit 1 content with playlists and a course for testing the student app.'

    def handle(self, *args, **options):
        author = User.objects.filter(is_staff=True).first()
        if not author:
            self.stdout.write(self.style.ERROR("No staff user found to author content."))
            return

        unit1_skills = {
            "Note_Names": "1.1 Note Names",
            "Ledger_Lines": "1.2 Ledger Lines",
            "clefs": "1.3 Clefs (Treble & Bass)",
            "enharmonic": "1.4 Enharmonics",
        }

        # Create Course
        course = Course.objects.filter(title="Unit 1: Pitch & Staff Notation").first()
        if not course:
            course = Course(title="Unit 1: Pitch & Staff Notation", authored_by=author)
            course.save()
            self.stdout.write(f"Created Course: {course.title}")

        exercises = list(Exercise.objects.all())
        if not exercises:
             self.stdout.write(self.style.WARNING("No exercises found in DB to assign to playlists."))

        for i, (tag, name) in enumerate(unit1_skills.items()):
            playlist = Playlist.objects.filter(name=name, authored_by=author).first()
            p_created = False
            if not playlist:
                playlist = Playlist(name=name, authored_by=author, tags=["unit:1", tag])
                playlist.save()
                p_created = True
                
            if p_created:
                # Assign some exercises if available
                chunk_size = 5
                start = i * chunk_size
                playlist_exercises = exercises[start : start + chunk_size]
                for idx, ex in enumerate(playlist_exercises, 1):
                    playlist.exercises.add(ex, through_defaults={"order": idx})
                self.stdout.write(f"Created Playlist: {name} with {len(playlist_exercises)} exercises.")

            # Link to course
            if not PlaylistCourseOrdered.objects.filter(playlist=playlist, course=course).exists():
                PlaylistCourseOrdered.objects.create(
                    playlist=playlist,
                    course=course,
                    order=i + 1
                )


        self.stdout.write(self.style.SUCCESS("Unit 1 content seeded successfully."))
