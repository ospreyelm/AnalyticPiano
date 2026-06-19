from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("exercises", "0069_playlist_teacher_play_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="playlist",
            name="canonical_mode",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=32,
            ),
        ),
    ]
