# Generated by Django 2.2.28 on 2023-03-14 14:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0042_performance_dict_refresh'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='performancedata',
            name='playlist_performances',
        ),
        migrations.RemoveField(
            model_name='performancedata',
            name='supervisor',
        ),
    ]
