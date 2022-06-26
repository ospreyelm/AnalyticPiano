# Generated by Django 2.2.13 on 2021-01-12 22:06

import apps.accounts.models
import django.contrib.postgres.fields.jsonb
from django.db import migrations


def set_additional_user_preferences(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    db_alias = schema_editor.connection.alias
    for user in User.objects.using(db_alias).all():
        user.preferences['auto_advance'] = user.auto_advance
        user.preferences['auto_advance_delay'] = user.auto_advance_delay
        user.preferences['auto_repeat'] = user.auto_repeat
        user.preferences['auto_repeat_delay'] = user.auto_repeat_delay
        user.save()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0010_auto_20220622_2338'),
    ]

    operations = [
        migrations.RunPython(set_additional_user_preferences)
    ]