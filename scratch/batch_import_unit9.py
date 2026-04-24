import os
import django
from django.core.management import call_command
from django.utils.timezone import now

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'harmony.settings.local')
django.setup()

from apps.exercises.models import Playlist, Exercise, ExercisePlaylistOrdered
from apps.accounts.models import User
from django.db import connection

def reset_sequences():
    print("Resetting database sequences with VERY large buffer for safety...")
    with connection.cursor() as cursor:
        # Using a massive buffer (+1000) to jump over any and all problematic fragments/stray records
        cursor.execute("SELECT setval(pg_get_serial_sequence('\"exercises_exercise\"','_id'), (SELECT COALESCE(MAX(\"_id\"), 3000) + 1000 FROM \"exercises_exercise\"))")
        cursor.execute("SELECT setval(pg_get_serial_sequence('\"exercises_playlist\"','_id'), (SELECT COALESCE(MAX(\"_id\"), 1000) + 1000 FROM \"exercises_playlist\"))")
        cursor.execute("SELECT setval(pg_get_serial_sequence('\"exercises_exerciseplaylistordered\"','_id'), (SELECT COALESCE(MAX(\"_id\"), 5000) + 1000 FROM \"exercises_exerciseplaylistordered\"))")

def batch_import_unit9():
    author_email = 'avner-local2025@localhost'
    playlist_name = 'Unit 9 Bach Phrases (R11-20)'
    
    try:
        author = User.objects.get(email=author_email)
    except User.DoesNotExist:
        print(f"Error: User {author_email} not found.")
        return

    # 1. Cleanup "zombie" playlists from failed attempts
    print(f"Cleaning up existing playlists named '{playlist_name}'...")
    zombies = Playlist.objects.filter(name=playlist_name)
    z_count = zombies.count()
    zombies.delete()
    print(f"Deleted {z_count} zombie playlist(s).")

    # 2. Reset sequences
    reset_sequences()

    # 3. Create Playlist
    # Use standard constructor and .save() to ensure the model's custom save() runs for P-ID generation
    playlist = Playlist(
        name=playlist_name,
        authored_by=author,
        is_dynamic=False,
        is_adaptive=False,
        skill_tags=['unit:9']
    )
    playlist.save()
    
    if not playlist.id:
        print("Warning: Playlist P-ID not generated automatically. Forcing set_id...")
        playlist.set_id(initial="P")
        playlist.save()
        
    print(f"Created Playlist: {playlist.name} (P-ID: {playlist.id}, _id: {playlist._id})")

    # 4. Run Imports
    start_time = now()
    for riem_num in range(11, 21):
        print(f"--- Importing Riemenschneider {riem_num} ---")
        try:
            call_command(
                'import_bach_phrases',
                riemenschneider=riem_num,
                author=author_email,
                mode='roman'
            )
        except Exception as e:
            print(f"Failed to import R{riem_num}: {e}")

    # 3. Collect new exercises and link them
    # We find exercises created by the author after our start_time
    # and that have 'Bach R11' through 'Bach R20' in their description.
    new_exercises = Exercise.objects.filter(
        authored_by=author,
        created__gte=start_time,
        description__icontains='Bach R'
    ).order_by('id') # order by ID/Description
    
    # Actually, order should ideally follow the R-number and Phrase number.
    # We'll sort them in Python for better control.
    def sort_key(ex):
        # Description: "Bach R15 - Phrase 2 (mm.5-12)"
        import re
        match = re.search(r'R(\d+) - Phrase (\d+)', ex.description)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (0, 0)
    
    sorted_exercises = sorted(new_exercises, key=sort_key)
    
    print(f"Linking {len(sorted_exercises)} exercises to playlist...")
    for idx, ex in enumerate(sorted_exercises):
        ExercisePlaylistOrdered.objects.create(
            exercise=ex,
            playlist=playlist,
            order=idx + 1
        )
        print(f"  Added {ex.id}: {ex.description}")

    print(f"\nSuccessfully populated playlist {playlist.id} with {len(sorted_exercises)} exercises.")

if __name__ == "__main__":
    batch_import_unit9()
