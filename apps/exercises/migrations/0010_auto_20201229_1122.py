# Generated by Django 2.2.13 on 2020-12-29 16:22

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_better_admin_arrayfield.models.fields


def rename_course_playlists(apps, schema_editor):
    Course = apps.get_model("exercises", "Course")
    Playlist = apps.get_model("exercises", "Playlist")
    db_alias = schema_editor.connection.alias
    courses = Course.objects.using(db_alias).all()
    for course in courses:
        course_playlist_names = course.playlists.split(",")
        playlist_ids = list(
            Playlist.objects.using(db_alias)
            .filter(name__in=course_playlist_names)
            .values_list("id", flat=True)
        )
        course.playlists = ",".join(playlist_ids)
        course.save()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("exercises", "0009_auto_20201221_1651"),
    ]

    operations = [
        migrations.AlterField(
            model_name="course",
            name="playlists",
            field=models.CharField(
                help_text="Ordered set of playlist IDs, separated by comma.",
                max_length=1024,
                verbose_name="Playlists",
            ),
        ),
        migrations.AlterField(
            model_name="course",
            name="title",
            field=models.CharField(
                max_length=64,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Enter a valid title consisting of letters, numbers, spaces, underscores or hyphens",
                        regex="^[a-zA-Z0-9-_ +]+$",
                    )
                ],
                verbose_name="Title",
            ),
        ),
        migrations.AlterField(
            model_name="exercise",
            name="name",
            field=models.CharField(
                blank=True, max_length=60, null=True, verbose_name="Description"
            ),
        ),
        migrations.AlterField(
            model_name="playlist",
            name="authored_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="playlists",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Author of Unit",
            ),
        ),
        migrations.AlterField(
            model_name="playlist",
            name="name",
            field=models.CharField(
                max_length=32,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="Enter a valid name consisting of letters, numbers, spaces, underscores or hyphens",
                        regex="^[a-zA-Z0-9-_ ]+$",
                    )
                ],
                verbose_name="Name",
            ),
        ),
        migrations.AlterField(
            model_name="playlist",
            name="transpose_requests",
            field=django_better_admin_arrayfield.models.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("ab", "ab"),
                        ("Cb", "Cb"),
                        ("eb", "eb"),
                        ("Gb", "Gb"),
                        ("bb", "bb"),
                        ("Db", "Db"),
                        ("f", "f"),
                        ("Ab", "Ab"),
                        ("c", "c"),
                        ("Eb", "Eb"),
                        ("g", "g"),
                        ("Bb", "Bb"),
                        ("d", "d"),
                        ("F", "F"),
                        ("a", "a"),
                        ("C", "C"),
                        ("e", "e"),
                        ("G", "G"),
                        ("b", "b"),
                        ("D", "D"),
                        ("f#", "f#"),
                        ("A", "A"),
                        ("c#", "c#"),
                        ("E", "E"),
                        ("g#", "g#"),
                        ("B", "B"),
                        ("d#", "d#"),
                        ("F#", "F#"),
                        ("a#", "a#"),
                        ("C#", "C#"),
                    ],
                    max_length=10,
                ),
                blank=True,
                default=list,
                help_text="Valid choices are ab Cb eb Gb bb Db f Ab c Eb g Bb d F a C e G b D f# A c# E g# B d# F# a# C#",
                null=True,
                size=None,
                verbose_name="Transpose requests",
            ),
        ),
        migrations.RunPython(rename_course_playlists, reverse_code=reverse),
    ]
