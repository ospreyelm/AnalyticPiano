# Generated by Django 2.2.28 on 2022-07-05 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_additional_user_preferences'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='raw_password',
        ),
        migrations.AlterField(
            model_name='user',
            name='password',
            field=models.CharField(default='', max_length=32),
        ),
    ]
