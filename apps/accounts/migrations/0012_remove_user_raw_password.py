# Generated by Django 2.2.28 on 2022-07-10 18:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_additional_user_preferences'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='raw_password',
        ),
    ]
