# Generated by Django 2.2.28 on 2023-01-18 23:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exercises', '0034_auto_20230115_2159'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exercise',
            name='description',
            field=models.CharField(blank=True, help_text='Brief description showed to authors in the exercise dashboard table.', max_length=60, null=True, verbose_name='Description'),
        ),
    ]
