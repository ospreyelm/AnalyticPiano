"""Generate Unit 5 triad and seventh chord quality identification exercises.

Each exercise shows a single root-position chord on a keyboard staff. The student
identifies its quality from a multiple-choice popup. No MIDI input is required.

Difficulty is staged by expanding the choice set:
  Triads:        Stage 1 = major/minor (2 choices) → Stage 3 = all four
  Seventh chords: Stage 1 = dominant/major7 (2 choices) → Stage 4 = all five
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.generation.music21_builder import chord_notes_key_and_spelling
from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto_factory import save_umto_chord_id_exercise

User = get_user_model()

# (HarmonyLab key string, root display name, accidental count)
ALL_ROOTS = [
    ("jC_", "C",  0),
    ("jG_", "G",  1),
    ("jF_", "F",  1),
    ("jD_", "D",  2),
    ("jBb", "Bb", 2),
    ("jA_", "A",  3),
    ("jEb", "Eb", 3),
    ("jE_", "E",  4),
    ("jAb", "Ab", 4),
    ("jB_", "B",  5),
    ("jDb", "Db", 5),
    ("jF#", "F#", 6),
]

# (stage_num, display_choices, quality_pool, max_accidentals)
TRIAD_STAGES = [
    (1, ["major", "minor"],
        ["major", "minor"], 3),
    (2, ["major", "minor", "diminished"],
        ["major", "minor", "diminished"], 5),
    (3, ["major", "minor", "diminished", "augmented"],
        ["major", "minor", "diminished", "augmented"], 99),
]

SEVENTH_STAGES = [
    (1, ["dominant 7", "major 7"],
        ["dominant", "major7"], 3),
    (2, ["dominant 7", "major 7", "minor 7"],
        ["dominant", "major7", "minor7"], 5),
    (3, ["dominant 7", "major 7", "minor 7", "half-dim 7"],
        ["dominant", "major7", "minor7", "half_dim"], 99),
    (4, ["dominant 7", "major 7", "minor 7", "half-dim 7", "diminished 7"],
        ["dominant", "major7", "minor7", "half_dim", "dim7"], 99),
]

# Internal quality name → display answer label
QUALITY_DISPLAY = {
    "major":      "major",
    "minor":      "minor",
    "diminished": "diminished",
    "augmented":  "augmented",
    "dominant":   "dominant 7",
    "major7":     "major 7",
    "minor7":     "minor 7",
    "half_dim":   "half-dim 7",
    "dim7":       "diminished 7",
}

PROBLEMS_PER_PLAYLIST = 48
CHORDS_PER_WORKSHEET = 4


def _generate_problems(quality_pool, eligible_roots, n=PROBLEMS_PER_PLAYLIST):
    """Round-robin (quality, root) pairs to produce n individual chord problems."""
    problems = []
    i = 0
    while len(problems) < n:
        quality = quality_pool[i % len(quality_pool)]
        key_str, root_label, _ = eligible_roots[i % len(eligible_roots)]
        problems.append((key_str, root_label, quality))
        i += 1
    return problems


def _chunk_problems(items, size):
    """Split items into chunks of at most size."""
    return [items[i:i + size] for i in range(0, len(items), size)]


class Command(BaseCommand):
    help = "Create Unit 5 chord quality identification exercises (triads and seventh chords)"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Email of exercise author")
        parser.add_argument("--public", action="store_true", help="Make exercises public")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exercises")
        parser.add_argument(
            "--type",
            choices=["triads", "sevenths", "both"],
            default="both",
            help="Which chord types to generate (default: both)",
        )

    def handle(self, *args, **options):
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        chord_type = options["type"]
        if chord_type in ("triads", "both"):
            self._handle_type(author, options, "triad", TRIAD_STAGES, "Unit 5 — Triad Quality")
        if chord_type in ("sevenths", "both"):
            self._handle_type(author, options, "seventh_chord", SEVENTH_STAGES, "Unit 5 — Seventh Chord Quality")

    def _handle_type(self, author, options, chord_type, stages, playlist_prefix):
        skill_root = "unit:5_triad_quality" if chord_type == "triad" else "unit:5_seventh_chord_quality"

        for stage_num, display_choices, quality_pool, max_acc in stages:
            eligible_roots = [(k, r, a) for k, r, a in ALL_ROOTS if a <= max_acc]
            problems = _generate_problems(quality_pool, eligible_roots)
            worksheets = _chunk_problems(problems, CHORDS_PER_WORKSHEET)

            created_exercises = []
            for worksheet_idx, worksheet in enumerate(worksheets, start=1):
                chords = []
                worksheet_key = None
                for key_str, root_label, quality in worksheet:
                    display_answer = QUALITY_DISPLAY[quality]
                    midi_notes, display_key, _ = chord_notes_key_and_spelling(key_str, quality, chord_type)
                    if worksheet_key is None:
                        worksheet_key = display_key
                    chords.append({
                        "notes": midi_notes,
                        "answer": display_answer,
                        "choices": display_choices,
                        "rhythmValue": "w",
                    })

                desc = f"Unit 5 {chord_type.replace('_', ' ').title()}: Stage {stage_num} — Worksheet {worksheet_idx}"

                skill_tags = ["unit:5", skill_root, f"unit:5_L{stage_num}"]

                ex = save_umto_chord_id_exercise(
                    description=desc,
                    author=author,
                    chord_key=worksheet_key,
                    chords=chords,
                    skill_tags=skill_tags,
                    complexity=5,
                    is_public=options["public"],
                    overwrite=options["overwrite"],
                )
                created_exercises.append(ex)
                self.stdout.write(
                    f"  {desc}: {len(chords)} chords (id={ex.id})"
                )

            self._build_playlist(
                author=author,
                exercises=created_exercises,
                playlist_name=f"{playlist_prefix}: Stage {stage_num}",
                skill_tags=["unit:5", skill_root, f"unit:5_L{stage_num}"],
                is_public=options["public"],
                stage=stage_num,
                choices=display_choices,
            )

    def _build_playlist(self, author, exercises, playlist_name, skill_tags, is_public,
                        stage, choices):
        playlist, created = Playlist.objects.get_or_create(
            name=playlist_name,
            authored_by=author,
            defaults=dict(
                is_dynamic=False,
                is_adaptive=False,
                is_public=True,
                skill_tags=skill_tags,
            ),
        )
        if not created:
            playlist.skill_tags = skill_tags
            if is_public:
                playlist.is_public = True
            playlist.save()

        ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
        for order, ex in enumerate(exercises, start=1):
            ExercisePlaylistOrdered.objects.create(
                playlist=playlist, exercise=ex, order=order
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Stage {stage} ({len(choices)} choices): "
                f"{len(exercises)} exercises → playlist '{playlist_name}'"
            )
        )
