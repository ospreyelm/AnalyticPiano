# Generated by Django 2.2.13 on 2021-02-04 01:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exercises", "0017_merge_20210203_2011"),
    ]

    operations = [
        migrations.AlterField(
            model_name="playlist",
            name="is_auto",
            field=models.BooleanField(default=False, verbose_name="Is Auto Playlist"),
        ),
    ]
