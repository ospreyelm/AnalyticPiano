# Generated by Django 2.2.28 on 2023-12-14 00:55

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0019_auto_20231213_1649'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='content_permits',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=set, verbose_name='Content Permits'),
        ),
        migrations.AlterField(
            model_name='user',
            name='performance_permits',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, default=set, verbose_name='Performance Permissions'),
        ),
    ]
