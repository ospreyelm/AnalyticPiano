import re
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.exercises.models import Exercise, ExercisePlaylistOrdered, Playlist

def _extract_stage_from_description(description):
    match = re.search(r"S(\d+)\s*$", description or "")
    if not match:
        return None
    return int(match.group(1))

User = get_user_model()


LANE_PLAYLISTS = (
    {
        "name": "Unit 1 - Note Names (Treble)",
        "exercise_tags": ["unit:1", "Note_Names", "Read_Treble_Clef"],
        "playlist_tags": ["unit:1", "Note_Names", "Read_Treble_Clef"],
        "exercise_type": "identify",
    },
    {
        "name": "Unit 1 - Note Names (Bass)",
        "exercise_tags": ["unit:1", "Note_Names", "Read_Bass_Clef"],
        "playlist_tags": ["unit:1", "Note_Names", "Read_Bass_Clef"],
        "exercise_type": "identify",
    },
    {
        "name": "Unit 1 - Note Names (Treble Play)",
        "exercise_tags": ["unit:1", "Note_Names", "enharmonic", "Read_Treble_Clef"],
        "playlist_tags": [
            "unit:1",
            "Note_Names",
            "enharmonic",
            "Enharmonic_Reading",
            "Read_Treble_Clef",
        ],
        "exercise_type": "matching",
    },
    {
        "name": "Unit 1 - Note Names (Bass Play)",
        "exercise_tags": ["unit:1", "Note_Names", "enharmonic", "Read_Bass_Clef"],
        "playlist_tags": [
            "unit:1",
            "Note_Names",
            "enharmonic",
            "Enharmonic_Reading",
            "Read_Bass_Clef",
        ],
        "exercise_type": "matching",
    },
    {
        "name": "Unit 1 - Clefs",
        "exercise_tags": ["unit:1", "clefs"],
        "playlist_tags": ["unit:1", "clefs"],
    },
    {
        "name": "Unit 1 - Ledger Lines",
        "exercise_tags": ["unit:1", "Ledger_Lines"],
        "playlist_tags": ["unit:1", "Ledger_Lines"],
    },
    {
        "name": "Unit 1 - Enharmonics",
        "exercise_tags": ["unit:1", "enharmonic"],
        "playlist_tags": ["unit:1", "enharmonic"],
    },
)


class Command(BaseCommand):
    help = "Rebuild Unit 1 playlist ordering from existing exercises by lane tags."

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument(
            "--max-per-playlist",
            type=int,
            default=36,
            help="Maximum exercises per playlist (default: 36). Pass 0 for no cap.",
        )

    def handle(self, *args, **options):
        author_email = options["author"]
        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist as exc:
            raise CommandError(f"Author not found: {author_email}") from exc

        max_per_playlist = options["max_per_playlist"]
        rebuilt = 0
        for lane in LANE_PLAYLISTS:
            playlist_qs = Playlist.objects.filter(authored_by=author, name=lane["name"]).order_by("_id")
            if playlist_qs.count() > 1:
                raise CommandError(f"Multiple playlists found for lane name: {lane['name']}")

            playlist = playlist_qs.first()
            if playlist is None:
                self.stdout.write(
                    self.style.WARNING(f"Skipping missing playlist: {lane['name']}")
                )
                continue

            rows = Exercise.objects.filter(authored_by=author)
            for tag in lane["exercise_tags"]:
                rows = rows.filter(skill_tags__contains=[tag])

            # Filter by description token to guarantee lane separation.
            # Identify exercises contain "(id)", matching/playback contain "(exact)".
            lane_type = lane.get("exercise_type")
            if lane_type == "identify":
                rows = rows.filter(description__icontains="(id)")
            elif lane_type == "matching":
                rows = rows.filter(description__icontains="(exact)")

            ordered_exercises = list(rows.order_by("complexity", "description", "_id"))
            if max_per_playlist:
                ordered_exercises = ordered_exercises[:max_per_playlist]

            with transaction.atomic():
                desired_tags = lane["playlist_tags"]
                if playlist.skill_tags != desired_tags:
                    playlist.skill_tags = desired_tags
                    playlist.save(update_fields=["skill_tags", "updated"])

                ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
                bulk_epos = []
                for index, exercise in enumerate(ordered_exercises, start=1):
                    stage_num = _extract_stage_from_description(exercise.description) or 1
                    diff_tier = 1
                    if stage_num == 3:
                        diff_tier = 2
                    elif stage_num >= 4:
                        diff_tier = 3
                    
                    is_source = (stage_num >= 4)
                    
                    bulk_epos.append(
                        ExercisePlaylistOrdered(
                            playlist=playlist,
                            exercise=exercise,
                            order=index,
                            difficulty_tier=diff_tier,
                            is_mastery_challenge_source=is_source
                        )
                    )
                ExercisePlaylistOrdered.objects.bulk_create(bulk_epos)

            rebuilt += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Rebuilt {playlist.name}: {len(ordered_exercises)} exercises"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Rebuilt {rebuilt} Unit 1 playlists."))
