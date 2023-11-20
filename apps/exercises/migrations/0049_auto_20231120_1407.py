# Generated by Django 2.2.28 on 2023-11-20 19:07

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0048_auto_20230326_1328'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='id',
            field=models.CharField(blank=True, max_length=16, null=True, unique=True, verbose_name='C-ID'),
        ),
        migrations.AlterField(
            model_name='course',
            name='tardy_threshold',
            field=models.IntegerField(default=120, help_text="When performances are submitted after the due date, this threshold determines if they're considered tardy or late. Submissions before this threshold are tardy, submissions after are late.", validators=[django.core.validators.MinValueValidator(1)], verbose_name='Late threshold (hours)'),
        ),
    ]
