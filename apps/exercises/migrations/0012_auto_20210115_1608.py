# Generated by Django 2.2.13 on 2021-01-15 21:08
from copy import copy

from django.db import migrations


def modify_performance_data(apps, schema_editor):
    PerformanceData = apps.get_model("exercises", "PerformanceData")
    db_alias = schema_editor.connection.alias
    for pd in PerformanceData.objects.using(db_alias).all():
        new_raw_data = []
        exercise_data = copy(pd.data)
        for exercise in exercise_data:
            exercise_error_count = exercise.get("exercise_error_tally")
            if exercise_error_count and exercise_error_count == "n/a":
                exercise["exercise_error_tally"] = -1
            new_raw_data.append(exercise)
        pd.data = new_raw_data
        pd.save()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("exercises", "0011_auto_20210111_0207"),
    ]

    operations = [migrations.RunPython(modify_performance_data, reverse_code=reverse)]
