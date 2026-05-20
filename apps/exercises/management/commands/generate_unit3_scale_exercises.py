"""Generate Unit 3 scale play exercises.

Major scales are read from a MusicXML file (preserves fingering/register choices).
Minor scales (natural, harmonic, melodic) are generated programmatically via music21.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.exercises.models import ExercisePlaylistOrdered, Playlist
from apps.exercises.umto import InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

User = get_user_model()

# Maps (measure_index, key_id, accidentals, display_name).
# Derived from docs/scales-key-signatures/piano-major-scales-fingerings.mxl
# by reading the KeySignature fifths value per measure.
# fifths: 0=C, 1=G, 2=D, 3=A, 4=E, 5=B, 6=F#, 7=C#,
#        -1=F, -2=Bb, -3=Eb, -4=Ab, -5=Db, -6=Gb, -7=Cb
SCALE_MEASURE_MAP = [
    (0,  "C",  0, "C major"),
    (1,  "F",  1, "F major"),
    (2,  "G",  1, "G major"),
    (3,  "Bb", 2, "Bb major"),
    (4,  "D",  2, "D major"),
    (5,  "Eb", 3, "Eb major"),
    (6,  "A",  3, "A major"),
    (7,  "Ab", 4, "Ab major"),
    (8,  "E",  4, "E major"),
    (9,  "Db", 5, "Db major"),
    (10, "B",  5, "B major"),
    (11, "Gb", 6, "Gb major"),
    (12, "F#", 6, "F# major"),
    (13, "Cb", 7, "Cb major"),
    (14, "C#", 7, "C# major"),
]

# Maps (root_for_music21, key_id, accidentals, root_display_name, rh_start_octave).
# root_for_music21: music21 pitch notation ("B-" for Bb, "F#" for F#).
# key_id: HarmonyLab minor key string ("i" prefix + letter + "_"/"#"/"b").
# rh_start_octave: RH starting octave, matching the parallel major scale register.
# Ordered by circle of fifths (sharps then flats, ascending accidental count).
MINOR_SCALE_MAP = [
    ("A",   "iA_", 0, "A",   3),
    ("E",   "iE_", 1, "E",   4),
    ("D",   "iD_", 1, "D",   4),
    ("B",   "iB_", 2, "B",   3),
    ("G",   "iG_", 2, "G",   3),
    ("F#",  "iF#", 3, "F#",  3),
    ("C",   "iC_", 3, "C",   4),
    ("C#",  "iC#", 4, "C#",  4),
    ("F",   "iF_", 4, "F",   3),
    ("G#",  "iG#", 5, "G#",  3),  # parallel = Ab major, oct 3
    ("B-",  "iBb", 5, "Bb",  3),
    ("D#",  "iD#", 6, "D#",  4),  # parallel = Eb major, oct 4
    ("E-",  "iEb", 6, "Eb",  4),
    ("A#",  "iA#", 7, "A#",  3),  # parallel = Bb major, oct 3
    ("A-",  "iAb", 7, "Ab",  3),
]

LEVEL_MAX_ACC = {1: 3, 2: 5, 3: 7}

# Treble right-hand part shifted down an octave for these major-scale keys so
# the top note stays within a 5-octave keyboard. (Major mode only — minor scales
# start at octave 4 and stay within range for all keys.)
TREBLE_OCTAVE_DOWN_KEYS = {"F", "G", "A", "Bb", "B", "Ab", "F#"}

TYPE_MAP = {
    "whole": "w",
    "half": "h",
    "quarter": "q",
    "eighth": "8",
    "16th": "16",
    "32nd": "32",
}

# Configuration for each minor scale form.
# scale_class: music21 scale class name to instantiate.
# playlist_label: used in playlist name, e.g. "Unit 3 — Minor Scales (Natural)".
# skill_tag: exercise/playlist skill tag.
# display_suffix: appended to root name for exercise description, e.g. "A natural minor".
MINOR_FORM_CONFIG = {
    "natural": {
        "scale_class": "MinorScale",
        "playlist_label": "Natural",
        "skill_tag": "unit:3_minor_scale_natural",
        "display_suffix": "natural minor",
    },
    "harmonic": {
        "scale_class": "HarmonicMinorScale",
        "playlist_label": "Harmonic",
        "skill_tag": "unit:3_minor_scale_harmonic",
        "display_suffix": "harmonic minor",
    },
    "melodic": {
        "scale_class": "MelodicMinorScale",
        "playlist_label": "Melodic",
        "skill_tag": "unit:3_minor_scale_melodic",
        "display_suffix": "melodic minor",
    },
}


def _voice_items_from_measure(m21_measure):
    """Convert a music21 Measure to a list of CIR note/rest items."""
    from music21 import note as m21_note, chord as m21_chord

    items = []
    for el in m21_measure.flatten().notesAndRests:
        dur = {"type": TYPE_MAP.get(el.duration.type, "q"), "dots": el.duration.dots}
        if isinstance(el, m21_note.Rest):
            items.append({"kind": "rest", "duration": dur})
        elif isinstance(el, m21_note.Note):
            items.append({
                "kind": "note",
                "pitch": {
                    "step": el.pitch.step,
                    "alter": int(el.pitch.alter),
                    "octave": el.pitch.octave,
                },
                "duration": dur,
            })
        elif isinstance(el, m21_chord.Chord):
            # Use the highest pitch for a single-voice grand-staff scale
            p = el.pitches[-1]
            items.append({
                "kind": "note",
                "pitch": {
                    "step": p.step,
                    "alter": int(p.alter),
                    "octave": p.octave,
                },
                "duration": dur,
            })
    return items


def _shift_octave(items, delta):
    """Return a copy of voice items with every note's octave shifted by delta."""
    result = []
    for item in items:
        if item.get("kind") == "note" and "pitch" in item:
            item = dict(item, pitch=dict(item["pitch"], octave=item["pitch"]["octave"] + delta))
        result.append(item)
    return result


def _measure_to_cir(treble_measure, bass_measure, display_name, treble_octave_shift=0):
    """Convert a pair of music21 Measures (treble + bass) to a CIR dict."""
    treble_items = _voice_items_from_measure(treble_measure)
    if treble_octave_shift:
        treble_items = _shift_octave(treble_items, treble_octave_shift)
    return {
        "meta": {"key": display_name, "time": "4/4"},
        "measures": [
            {
                "staves": {
                    "treble": {
                        "clef": "treble",
                        "voices": [
                            {"items": treble_items, "direction": "up"},
                            {"items": [], "direction": "down"},
                        ],
                    },
                    "bass": {
                        "clef": "bass",
                        "voices": [
                            {"items": _voice_items_from_measure(bass_measure), "direction": "up"},
                            {"items": [], "direction": "down"},
                        ],
                    },
                }
            }
        ],
    }


def _pitch_to_cir_item(p):
    """Convert a music21 Pitch to a CIR note item (quarter note)."""
    return {
        "kind": "note",
        "pitch": {
            "step": p.step,
            "alter": int(p.alter),
            "octave": p.octave,
        },
        "duration": {"type": "q", "dots": 0},
    }


def _build_minor_scale_cir(root, display_name, scale_class_name, rh_start_octave=4):
    """Build CIR for a two-octave minor scale (quarter notes, up then down).

    Treble (RH): root{rh_start_octave} → root{rh_start_octave+2} ascending, then descending.
    Bass   (LH): root2 → root4 ascending, then descending.
    For MelodicMinorScale, ascending uses raised 6th+7th; descending uses natural minor.
    """
    from music21 import scale as m21_scale

    lh_start = 2
    rh_end = rh_start_octave + 2

    sc = getattr(m21_scale, scale_class_name)(root)
    treble_up = sc.getPitches(f"{root}{rh_start_octave}", f"{root}{rh_end}")
    bass_up = sc.getPitches(f"{root}{lh_start}", f"{root}{lh_start + 2}")

    if scale_class_name == "MelodicMinorScale":
        # Descending uses natural minor (lowered 6th+7th)
        nat = m21_scale.MinorScale(root)
        treble_down = list(reversed(nat.getPitches(f"{root}{rh_start_octave}", f"{root}{rh_end}")))[1:]
        bass_down = list(reversed(nat.getPitches(f"{root}{lh_start}", f"{root}{lh_start + 2}")))[1:]
    else:
        treble_down = list(reversed(treble_up))[1:]
        bass_down = list(reversed(bass_up))[1:]

    treble_items = [_pitch_to_cir_item(p) for p in treble_up + treble_down]
    bass_items = [_pitch_to_cir_item(p) for p in bass_up + bass_down]

    return {
        "meta": {"key": display_name, "time": "4/4"},
        "measures": [
            {
                "staves": {
                    "treble": {
                        "clef": "treble",
                        "voices": [
                            {"items": treble_items, "direction": "up"},
                            {"items": [], "direction": "down"},
                        ],
                    },
                    "bass": {
                        "clef": "bass",
                        "voices": [
                            {"items": bass_items, "direction": "up"},
                            {"items": [], "direction": "down"},
                        ],
                    },
                }
            }
        ],
    }


class Command(BaseCommand):
    help = "Create Unit 3 scale play exercises (major from MusicXML, minor via music21)"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True, help="Email of exercise author")
        parser.add_argument(
            "--mxl",
            default="docs/scales-key-signatures/piano-major-scales-fingerings.mxl",
            help="Path to MusicXML file (major mode only)",
        )
        parser.add_argument("--public", action="store_true", help="Make exercises public")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing exercises")
        parser.add_argument(
            "--mode",
            choices=["major", "minor", "both"],
            default="major",
            help="Which scales to generate (default: major)",
        )
        parser.add_argument(
            "--minor-forms",
            nargs="+",
            choices=["natural", "harmonic", "melodic"],
            default=["natural", "harmonic", "melodic"],
            help="Which minor scale forms to generate when --mode includes minor (default: all three)",
        )

    def handle(self, *args, **options):
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist as exc:
            raise CommandError(f"Unknown author: {options['author']}") from exc

        mode = options["mode"]
        if mode in ("major", "both"):
            self._handle_major(author, options)
        if mode in ("minor", "both"):
            for form in options["minor_forms"]:
                self._handle_minor(author, options, form)

    def _handle_major(self, author, options):
        from music21 import converter

        mxl_path = options["mxl"]
        if not os.path.exists(mxl_path):
            raise CommandError(f"MusicXML not found: {mxl_path}")

        self.stdout.write(f"Parsing {mxl_path}...")
        score = converter.parse(mxl_path)

        # music21 splits the grand-staff piano score into two parts:
        # parts[0] = treble staff, parts[1] = bass staff
        treble_measures = list(score.parts[0].getElementsByClass("Measure"))
        bass_measures = list(score.parts[1].getElementsByClass("Measure"))

        self.stdout.write(
            f"Found {len(treble_measures)} treble + {len(bass_measures)} bass measures."
        )

        created_exercises = []  # list of (Exercise, n_acc)
        for m_idx, key_id, n_acc, display_name in SCALE_MEASURE_MAP:
            if m_idx >= len(treble_measures) or m_idx >= len(bass_measures):
                self.stdout.write(
                    self.style.WARNING(f"Missing measure {m_idx}, skipping {display_name}")
                )
                continue

            treble_shift = -1 if key_id in TREBLE_OCTAVE_DOWN_KEYS else 0
            cir = _measure_to_cir(
                treble_measures[m_idx],
                bass_measures[m_idx],
                display_name,
                treble_octave_shift=treble_shift,
            )
            desc = f"Unit 3 Scale — {display_name}"
            skill_tags = ["unit:3", "unit:3_major_scale"]

            ex = save_umto_exercise(
                description=desc,
                score_data=cir,
                author=author,
                skill_tags=skill_tags,
                complexity=3,
                is_public=options["public"],
                overwrite=options["overwrite"],
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"Play the {display_name} scale on the keyboard.",
                    key=key_id,
                    meter="4/4",
                    clef="keyboard",
                    complexity_score=3,
                    mode=InteractionMode.PLAYBACK,
                    unit=3,
                ),
            )
            created_exercises.append((ex, n_acc))
            self.stdout.write(f"  Created: {desc} (id={ex.id})")

        self._build_playlists(
            author=author,
            exercises=created_exercises,
            playlist_prefix="Unit 3 — Major Scales",
            skill_tags=["unit:3", "major_scale", "unit:3_major_scale"],
            is_public=options["public"],
        )

    def _handle_minor(self, author, options, form):
        cfg = MINOR_FORM_CONFIG[form]
        self.stdout.write(f"Generating {form} minor scales...")

        created_exercises = []  # list of (Exercise, n_acc)
        for root, key_id, n_acc, root_display, rh_oct in MINOR_SCALE_MAP:
            display_name = f"{root_display} {cfg['display_suffix']}"
            cir = _build_minor_scale_cir(root, display_name, cfg["scale_class"], rh_oct)
            desc = f"Unit 3 Scale — {display_name}"
            skill_tags = ["unit:3", "unit:3_minor_scale", cfg["skill_tag"]]

            ex = save_umto_exercise(
                description=desc,
                score_data=cir,
                author=author,
                skill_tags=skill_tags,
                complexity=3,
                is_public=options["public"],
                overwrite=options["overwrite"],
                umto_kwargs=dict(
                    exercise_id="TEMP",
                    source=f"Play the {display_name} scale on the keyboard.",
                    key=key_id,
                    meter="4/4",
                    clef="keyboard",
                    complexity_score=3,
                    mode=InteractionMode.PLAYBACK,
                    unit=3,
                ),
            )
            created_exercises.append((ex, n_acc))
            self.stdout.write(f"  Created: {desc} (id={ex.id})")

        self._build_playlists(
            author=author,
            exercises=created_exercises,
            playlist_prefix=f"Unit 3 — Minor Scales ({cfg['playlist_label']})",
            skill_tags=["unit:3", "minor_scale", "unit:3_minor_scale", cfg["skill_tag"]],
            is_public=options["public"],
        )

    def _build_playlists(self, author, exercises, playlist_prefix, skill_tags, is_public):
        """Create the three level playlists from a list of (Exercise, n_acc) pairs."""
        for level, max_acc in LEVEL_MAX_ACC.items():
            playlist_name = f"{playlist_prefix}, Level {level}"
            level_tags = skill_tags + [f"unit:3_L{level}"]

            playlist, created = Playlist.objects.get_or_create(
                name=playlist_name,
                authored_by=author,
                defaults=dict(
                    is_dynamic=False,
                    is_adaptive=False,
                    is_public=True,
                    skill_tags=level_tags,
                ),
            )
            if not created:
                playlist.skill_tags = level_tags
                if is_public:
                    playlist.is_public = True
                playlist.save()

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            level_exercises = [ex for ex, n_acc in exercises if n_acc <= max_acc]
            for order, ex in enumerate(level_exercises, start=1):
                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist, exercise=ex, order=order
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Level {level} (≤{max_acc} accidentals): "
                    f"{len(level_exercises)} scales → playlist '{playlist_name}'"
                )
            )
