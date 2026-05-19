import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from apps.exercises.models import Playlist

class Command(BaseCommand):
    help = 'Create a new Smart (Dynamic) and Adaptive Playlist tied to specific tags.'

    def add_arguments(self, parser):
        parser.add_argument('--name', type=str, required=True, help='Name of the playlist')
        parser.add_argument('--tag', type=str, required=True, help='Tag to filter exercises (e.g. bach)')
        parser.add_argument('--author', type=str, required=True, help='Email of the author (User)')
        parser.add_argument('--non-adaptive', action='store_true', help='Disable adaptive mastery (True by default)')

    def handle(self, *args, **options):
        name = options['name']
        tag = options['tag']
        author_email = options['author']
        is_adaptive = not options['non_adaptive']
        
        User = get_user_model()
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{author_email}" not found')

        # Create the Playlist instance
        # The .save() method in HarmonyLab handles P-ID generation automatically
        playlist = Playlist(
            name=name,
            authored_by=author,
            is_adaptive=is_adaptive,
            is_dynamic=True, # This makes it a "Smart Assignment"
            is_public=True,
            tags=[tag]
        )
        
        try:
            playlist.save()
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created Smart Playlist "{name}"'
            ))
            self.stdout.write(f'  ID: {playlist.id}')
            self.stdout.write(f'  Dynamic: Yes (Tag: {tag})')
            self.stdout.write(f'  Adaptive: {"Yes" if is_adaptive else "No"}')
            self.stdout.write(f'  Author: {author.email}')
        except Exception as e:
            raise CommandError(f'Failed to create playlist: {str(e)}')
