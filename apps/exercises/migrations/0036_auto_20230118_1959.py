# Generated by Django 2.2.28 on 2023-01-19 00:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0035_auto_20230118_1843'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='is_public',
            field=models.BooleanField(default=False, help_text='Sharing your course will make it available to other users. Doing so will make your email visible to people looking to use your course.', verbose_name='Commons'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='is_public',
            field=models.BooleanField(default=False, help_text='Sharing your exercise will allow other users to include it in their playlists. Doing so will make your email visible to people looking to use this exercise.', verbose_name='Commons'),
        ),
        migrations.AlterField(
            model_name='playlist',
            name='is_public',
            field=models.BooleanField(default=False, help_text='Sharing your playlist will allow other users to include it in their courses. Doing so will make your email visible to people looking to use this playlist.', verbose_name='Commons'),
        ),
    ]
