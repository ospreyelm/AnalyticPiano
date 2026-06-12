from django.db import migrations


def backfill_is_official(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Exercise = apps.get_model("exercises", "Exercise")
    Playlist = apps.get_model("exercises", "Playlist")
    factory_user = User.objects.filter(email="factory@monteverdi.app").first()
    if factory_user is None:
        return
    Exercise.objects.filter(authored_by=factory_user).update(is_official=True)
    Playlist.objects.filter(authored_by=factory_user).update(is_official=True)


class Migration(migrations.Migration):
    dependencies = [
        ("exercises", "0066_add_is_official_to_exercise_playlist"),
    ]
    operations = [
        migrations.RunPython(backfill_is_official, migrations.RunPython.noop),
    ]
