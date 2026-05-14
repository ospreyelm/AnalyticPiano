from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_umto_barline_exercise
from apps.exercises.utils.barline_exercise_builder import build_barline_payload
from apps.exercises.utils.corpus_filter import iter_phrases

PLAYLIST_NAME = "Unit 2 — Add Barlines"
PLAYLIST_SKILL_TAGS = [
    "unit:2",
    "unit:2_rhythm",
    "unit:2_meter_simple",
    "unit:2_meter_compound",
]

SIMPLE_METERS = {"2/4", "3/4", "4/4"}
COMPOUND_METER_BEATS = {
    "6/8": 2,
    "9/8": 3,
    "12/8": 4,
}


def _manual_notes(meter, measures):
    if measures < 1:
        raise CommandError("--measures must be at least 1")
    if meter in SIMPLE_METERS:
        beats = int(meter.split("/")[0]) * measures
        return [{"pitch": "B4", "duration": "q", "dots": 0} for _ in range(beats)]
    if meter in COMPOUND_METER_BEATS:
        beats = COMPOUND_METER_BEATS[meter] * measures
        return [{"pitch": "B4", "duration": "q", "dots": 1} for _ in range(beats)]
    raise CommandError(f"Unsupported meter: {meter}")


def _level_playlist_name(level: int) -> str:
    return f"Unit 2 — Add Barlines, Level {level}"


def _level_skill_tags(level: int) -> list:
    return ["unit:2", "unit:2_rhythm", f"unit:2_L{level}"]


class Command(BaseCommand):
    help = "Create Unit 2 add-barlines exercises"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--public", action="store_true")
        # manual-only args
        parser.add_argument("--count", type=int, default=1)
        parser.add_argument("--meter", default="3/4")
        parser.add_argument("--measures", type=int, default=2)
        parser.add_argument("--pitch-mode", default="rhythm_only")
        parser.add_argument(
            "--source",
            choices=["manual", "corpus", "essen", "kern"],
            default="manual",
        )
        # corpus-only args
        parser.add_argument(
            "--level", type=int, default=None, help="Level 1-8; omit for all levels"
        )
        parser.add_argument(
            "--limit", type=int, default=None, help="Max phrases per level (default: unlimited)"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Print counts without saving"
        )

    def handle(self, *args, **options):
        source = options["source"]

        if source in ("essen", "kern"):
            raise CommandError(
                "Essen/Kern import is not implemented yet; "
                "use --source manual or --source corpus"
            )

        user_model = get_user_model()
        try:
            author = user_model.objects.get(email=options["author"])
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        if source == "corpus":
            self._handle_corpus(author, options)
        else:
            self._handle_manual(author, options)

    def _handle_manual(self, author, options):
        if options["count"] < 1:
            raise CommandError("--count must be at least 1")

        notes = _manual_notes(options["meter"], options["measures"])

        playlist, created = Playlist.objects.get_or_create(
            name=PLAYLIST_NAME,
            authored_by=author,
            defaults=dict(
                is_dynamic=False,
                is_adaptive=False,
                is_public=options["public"],
                skill_tags=list(PLAYLIST_SKILL_TAGS),
            ),
        )
        if not created:
            playlist.is_dynamic = False
            playlist.is_adaptive = False
            if options["public"]:
                playlist.is_public = True
            merged_skill_tags = list(playlist.skill_tags or [])
            for tag in PLAYLIST_SKILL_TAGS:
                if tag not in merged_skill_tags:
                    merged_skill_tags.append(tag)
            playlist.skill_tags = merged_skill_tags
            playlist.save()

        exercise_is_public = playlist.is_public
        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for index in range(options["count"]):
            payload = build_barline_payload(
                time_signature=options["meter"],
                clef="treble",
                notes=list(notes),
                measures=options["measures"],
                show_time_signature=index % 2 == 0,
                pitch_mode=options["pitch_mode"],
                source="Unit 2 add barlines manual seed",
                tags=list(PLAYLIST_SKILL_TAGS),
            )
            exercise = save_umto_barline_exercise(
                description=f"Unit 2 add barlines {options['meter']} #{index + 1}",
                author=author,
                payload=payload,
                is_public=exercise_is_public,
                overwrite=True,
            )
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist,
                exercise=exercise,
                order=index + 1,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {options['count']} barline exercise(s) in '{playlist.name}'"
            )
        )

    def _handle_corpus(self, author, options):
        is_public = options["public"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        target_levels = [options["level"]] if options["level"] else list(range(1, 9))

        by_level: dict = defaultdict(list)
        seen_per_level: dict = defaultdict(set)

        for phrase in iter_phrases(levels=target_levels):
            level = phrase.level
            if limit and len(by_level[level]) >= limit:
                continue
            if phrase.fingerprint in seen_per_level[level]:
                continue
            seen_per_level[level].add(phrase.fingerprint)
            by_level[level].append(phrase)

        for level in by_level:
            by_level[level].sort(key=lambda p: (p.source_path, p.phrase_offset))

        if dry_run:
            for level in sorted(by_level):
                self.stdout.write(f"Level {level}: {len(by_level[level])} phrase(s) (dry run)")
            return

        for level in sorted(by_level):
            phrases = by_level[level]
            skill_tags = _level_skill_tags(level)
            playlist_name = _level_playlist_name(level)

            playlist, _ = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=True,
                    is_public=is_public,
                    skill_tags=skill_tags,
                ),
            )
            playlist.is_dynamic = False
            playlist.is_adaptive = True
            playlist.skill_tags = skill_tags
            if is_public:
                playlist.is_public = True
            playlist.save()

            exercises = []
            for phrase in phrases:
                description = f"Unit 2 barline L{level} {phrase.fingerprint}"
                payload = build_barline_payload(
                    time_signature=phrase.time_signature,
                    clef="treble",
                    notes=phrase.notes,
                    measures=phrase.measures,
                    show_time_signature=True,
                    pitch_mode="rhythm_only",
                    source=phrase.source_path,
                    tags=skill_tags,
                )
                ex = save_umto_barline_exercise(
                    description=description,
                    author=author,
                    payload=payload,
                    is_public=is_public,
                    overwrite=True,
                    complexity=level,
                )
                exercises.append(ex)

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for order, ex in enumerate(exercises, 1):
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=order,
                    is_adaptive_entry=(order == 1),
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level}: {len(exercises)} exercise(s) in '{playlist_name}'"
                )
            )
