# Generated by Django 2.2.28 on 2022-11-04 01:10

import pytz
import django.contrib.postgres.fields.jsonb
from django.db import migrations
from django.conf import settings

# If the PerformanceData properties are ever significantly changed, this will have to be changed
from apps.exercises.models import PerformanceData

# This import is used only for the correct string conversion (on line 19), so likely won't need to be changed.
# If this needs to be changed, it may be a good idea to change the performance_dict keys to be the user ids instead of the stringified user objects
from apps.accounts.models import User


def forwards(apps, schema_editor):
    # PerformanceData = apps.get_model("exercises","PerformanceData")

    PlaylistCourseOrdered = apps.get_model("exercises", "PlaylistCourseOrdered")
    Course = apps.get_model("exercises", "Course")
    # User = apps.get_model("accounts", "User")
    db_alias = schema_editor.connection.alias
    for pd in PerformanceData.objects.using(db_alias).all():
        performer = str(User.objects.using(db_alias).get(id=pd.user_id))
        for pco in PlaylistCourseOrdered.objects.using(db_alias).filter(
            playlist_id=pd.playlist_id
        ):
            course = Course.objects.using(db_alias).get(_id=pco.course_id)
            course.performance_dict = {}
            pass_mark = "X"
            if pd.playlist_passed:
                pass_mark = "P"
                if pco.due_date:
                    due_date = pco.due_date.replace(tzinfo=pytz.utc).astimezone(
                        pytz.timezone(settings.TIME_ZONE)
                    )
                    pass_date = pd.get_local_pass_date
                    if due_date < pass_date:
                        diff = pass_date - due_date
                        days, seconds = diff.days, diff.seconds
                        hours = days * 24 + seconds // 3600
                        if hours >= 6:
                            pass_mark = "T"
                        if days >= 7:
                            pass_mark = "L"
            if not (performer in course.performance_dict):
                course.performance_dict[performer] = {"time_elapsed": 0}
            course.performance_dict[performer][pco.order] = pass_mark
            for exercise_data in pd.data:
                course.performance_dict[performer]["time_elapsed"] += int(
                    exercise_data["exercise_duration"]
                )
            course.save()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("exercises", "0030_auto_20221031_2114"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=reverse),
    ]
