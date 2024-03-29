# Generated by Django 2.2.28 on 2023-01-22 08:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0037_auto_20230119_2236'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exercise',
            name='description',
            field=models.CharField(blank=True, help_text='Brief description for your reference only; not seen by others.', max_length=60, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='is_public',
            field=models.BooleanField(default=False, help_text='Check to share your exercise with other users of this site: allow them to include the exercise in their playlists and see your email address.', verbose_name='Commons'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='rhythm',
            field=models.CharField(blank=True, help_text='Duration of each chord: w h q or 1 2 4 for whole, half, quarter; W H Q for dotted whole, half, quarter respectively.', max_length=255, null=True, verbose_name='Rhythm'),
        ),
        migrations.AlterField(
            model_name='exercise',
            name='time_signature',
            field=models.CharField(blank=True, default='', help_text='Enter a numerical time signature: two numbers separated by a slash', max_length=8, null=True, verbose_name='Meter'),
        ),
        migrations.AlterField(
            model_name='playlist',
            name='is_auto',
            field=models.BooleanField(default=False, verbose_name='Auto-generated'),
        ),
        migrations.AlterField(
            model_name='playlist',
            name='transposition_type',
            field=models.CharField(blank=True, choices=[(None, None), ('Exercise Loop', 'Exercise Loop'), ('Playlist Loop', 'Playlist Loop')], help_text="Determines order of transposed exercises. Exercise Loop means that each exercise will have its transposed versions come after it successively. Playlist Loop means that the entire playlist will come in its original key, followed successively by the playlist's transposed versions.", max_length=32, null=True, verbose_name='Transposition Types'),
        ),
    ]
