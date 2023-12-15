# Generated by Django 2.2.28 on 2023-03-22 19:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0046_auto_20230321_1436'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='tardy_threshold',
            field=models.IntegerField(default=120, help_text="When performances are submitted after the due date, this threshold determines if they're considered tardy or late. Submissions before this threshold are tardy, submissions after are late.", verbose_name='Tardiness threshold (hours)'),
        ),
    ]