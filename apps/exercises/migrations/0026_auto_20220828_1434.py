# Generated by Django 2.2.28 on 2022-08-28 18:34
import re
import operator
import apps.exercises.models
from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    Course = apps.get_model("exercises", "Course")
    Playlist = apps.get_model("exercises", "Playlist")
    PlaylistCourseOrdered = apps.get_model("exercises", "PlaylistCourseOrdered")
    db_alias = schema_editor.connection.alias
    for course in Course.objects.using(db_alias).all():
        playlist_list = Playlist.objects.using(db_alias).filter(
            id__in=re.split(r"[,; \n]+", course.playlists_string)
        )
        due_dates = course.due_dates.split(" ")
        publish_dates = course.publish_dates.split(" ")
        for i in range(0, len(playlist_list)):
            PlaylistCourseOrdered.objects.using(db_alias).create(
                {
                    "course_id": course._id,
                    "playlist_id": playlist_list[i]._id,
                    "due_date": due_dates[i],
                    "publish_date": publish_dates[i],
                    "order": i + 1,
                }
            )


def reverse(apps, schema_editor):
    Course = apps.get_model("exercises", "Course")
    Playlist = apps.get_model("exercises", "Playlist")
    PlaylistCourseOrdered = apps.get_model("exercises", "PlaylistCourseOrdered")
    db_alias = schema_editor.connection.alias
    for course in Course.objects.using(db_alias).all():
        pco_list = sorted(
            PlaylistCourseOrdered.objects.using(db_alias).filter(course_id=course._id),
            key=operator.attrgetter("order"),
        )
        playlist_list = map(
            lambda pco: Playlist.objects.using(db_alias).get(_id=pco.playlist_id),
            pco_list,
        )
        for i in range(0, len(playlist_list)):
            course.playlist_string = course.playlist_string + " " + playlist_list[i].id
            course.due_dates = course.due_dates + " " + pco_list[i].due_date
            course.publish_dates = course.publish_dates + " " + pco_list[i].publish_date
        course.save()


class Migration(migrations.Migration):

    dependencies = [
        ("exercises", "0025_auto_20220807_1435"),
    ]

    operations = [
        migrations.RemoveField(model_name="course", name="slug"),
        migrations.RenameField(
            model_name="course",
            old_name="playlists",
            new_name="playlists_string",
        ),
        migrations.CreateModel(
            name="PlaylistCourseOrdered",
            fields=[
                (
                    "_id",
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                        unique=True,
                        verbose_name="_ID",
                    ),
                ),
                ("order", models.IntegerField(verbose_name="Order")),
                (
                    "due_date",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Format: MM-DD-YYYY",
                        null=True,
                        verbose_name="Due Date",
                    ),
                ),
                (
                    "publish_date",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Format: MM-DD-YYYY",
                        null=True,
                        verbose_name="Publish Date",
                    ),
                ),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="exercises.Course",
                    ),
                ),
                (
                    "playlist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="exercises.Playlist",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=(apps.exercises.models.ClonableModelMixin, models.Model),
        ),
        migrations.AddField(
            model_name="course",
            name="playlists",
            field=models.ManyToManyField(
                blank=True,
                help_text="These are the exercise playlists within the course. You can add playlists after creating the course.",
                related_name="courses",
                through="exercises.PlaylistCourseOrdered",
                to="exercises.Playlist",
            ),
        ),
        migrations.RunPython(forwards, reverse_code=reverse),
        migrations.RemoveField(model_name="course", name="playlists_string"),
        migrations.RemoveField(model_name="course", name="due_dates"),
        migrations.RemoveField(model_name="course", name="publish_dates"),
        migrations.AlterField(
            model_name="exercise",
            name="rhythm",
            field=models.CharField(
                blank=True,
                help_text="Rhythm for this exercise's notes",
                max_length=255,
                null=True,
                verbose_name="Rhythm",
            ),
        ),
        migrations.AlterField(
            model_name="exercise",
            name="time_signature",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Time signature for this exercise. Ex: 3/4",
                max_length=8,
                null=True,
                verbose_name="Meter",
            ),
        ),
        migrations.AlterField(
            model_name="playlist",
            name="exercises",
            field=models.ManyToManyField(
                blank=True,
                help_text="These are the exercises within this playlist. You can add exercises after creating the playlist.",
                related_name="playlists",
                through="exercises.ExercisePlaylistOrdered",
                to="exercises.Exercise",
            ),
        ),
        migrations.AlterField(
            model_name="playlist",
            name="transposition_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Exercise Loop", "Exercise Loop"),
                    ("Playlist Loop", "Playlist Loop"),
                    (None, None),
                ],
                help_text="Determines order of transposed exercises. Exercise Loop means that each exercise will have its transposed versions come after it successively. Playlist Loop means that the entire playlist will come in its original key, followed successively by the playlist's transposed versions.",
                max_length=32,
                null=True,
                verbose_name="Transposition Types",
            ),
        ),
    ]
