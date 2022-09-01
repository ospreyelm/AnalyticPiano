from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from apps.exercises.models import Playlist, Exercise
from lab.objects import ExerciseRepository

User = get_user_model()


class CustomExerciseRepo(ExerciseRepository):
    def getGroupList(self):
        return sorted(
            [
                {
                    "name": g.name,
                    "size": g.size(),
                }
                for g in self.groups
                if len(g.name) > 0
            ],
            key=lambda g: g["name"].lower(),
        )


class Command(BaseCommand):
    def handle(self, *args, **options):
        repository = CustomExerciseRepo.create()
        for group in repository.getGroupList():
            if Playlist.objects.filter(name=group["name"]).exists():
                continue
            playlist = Playlist()
            playlist.name = group["name"]
            playlist.authored_by = User.objects.filter(is_superuser=True).first()
            playlist.exercises = ""
            playlist.save()

        self.stdout.write(
            self.style.SUCCESS(
                "%s playlists are successfully created." % Playlist.objects.count()
            )
        )

        for repo_exercise in repository.exercises:
            repo_exercise.load()
            exercise = Exercise()
            exercise.data = repo_exercise.exerciseDefinition.data
            exercise.is_public = True
            exercise.authored_by = User.objects.filter(is_superuser=True).first()
            exercise.save()

            playlist = Playlist.objects.filter(
                name=repo_exercise.getGroupName()
            ).first()
            if playlist.exercises == "":
                playlist.exercises = exercise.id
            else:
                playlist.exercises = playlist.exercises + "," + exercise.id
            playlist.save()

        self.stdout.write(
            self.style.SUCCESS(
                "%s exercises are successfully created and assigned to proper playlists."
                % Exercise.objects.count()
            )
        )
