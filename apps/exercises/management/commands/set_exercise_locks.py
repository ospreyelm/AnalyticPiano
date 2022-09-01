from django.core.management import BaseCommand

from apps.exercises.models import PerformanceData, Exercise


class Command(BaseCommand):
    def handle(self, *args, **options):
        performed_exercises = {}
        performances = PerformanceData.objects.all()

        for performance in performances:
            for exercise in performance.data:
                performed_exercises.setdefault(exercise["id"], [])
                performed_exercises[exercise["id"]].append(performance.user_id)
        performed_exercises = {k: list(set(v)) for k, v in performed_exercises.items()}

        """
        Sample output structure for performed_exercises:
        {
            'EA00CI': [2, 3], 
            'EA00CJ': [2, 3], 
            'EA00CK': [2, 3], 
            'EA00CL': [2, 3], 
            'EA00CI1': [2]       # transposed
        }
        values are the user ids that have performed the exercise
        """

        locked_exercises = 0
        for exercise in Exercise.objects.all():
            if exercise.locked:
                continue

            for key, value in performed_exercises.items():
                if (
                    exercise.id not in key
                ):  # filtering for regular and transposed exercises
                    continue

                # if more than one users have performed exercise, or if only one user did and it is not the author of exercise
                if len(value) > 1 or (
                    len(value) == 1 and value != exercise.authored_by_id
                ):
                    exercise.locked = True
                    exercise.save()
                    locked_exercises += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{locked_exercises} exercises has been successfully locked."
            )
        )
