from django.core.management import BaseCommand
from django.db import connections

from apps.exercises.models import PerformanceData, Exercise, Playlist, Course


class Command(BaseCommand):
    def handle(self, *args, **options):
        models = [Exercise, Playlist, Course, PerformanceData]
        with connections['default'].cursor() as cursor:
            for model in models:
                cursor.execute(
                    "UPDATE {} "
                    "SET created = DATE_TRUNC('second', created), updated = DATE_TRUNC('second', updated) ".format(
                        model._meta.db_table
                    )
                )
        self.stdout.write(
            self.style.SUCCESS('Successfully removed microseconds from timestamps.')
        )
