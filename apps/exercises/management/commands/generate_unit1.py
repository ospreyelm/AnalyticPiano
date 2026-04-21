import json
import os
from collections import defaultdict, deque

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from music21 import key, pitch

from apps.exercises.models import Course, Exercise, ExercisePlaylistOrdered, Playlist, PlaylistCourseOrdered
from apps.exercises.pitch_voice_utils import strip_to_voice, validate_pitch_voice

User = get_user_model()

# Stage definitions by (Step, Octave)
TREBLE_STAGE_STEP_SET = {
    1: {("C", 4), ("G", 4), ("C", 5), ("G", 5)},
    2: {("B", 3), ("D", 4), ("F", 4), ("A", 4), ("B", 4), ("D", 5), ("F", 5), ("A", 5)},
    3: {("E", 4), ("E", 5), ("B", 5), ("C", 6)},
    4: {("A", 3)},
}


# Stage weights from spec: stage K => 6-K
STAGE_WEIGHTS = {1: 5, 2: 4, 3: 3, 4: 2}


def _midi(step, octave, alter=0):
    step_to_pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return (octave + 1) * 12 + step_to_pc[step] + alter


def _key_complexity(key_name):
    """Return number of accidentals in key signature."""
    try:
        k = key.Key(key_name)
        return abs(k.sharps)
    except:
        return 0


def _treble_cumulative_step_sets():
    out = {}
    running = set()
    for stage in [1, 2, 3, 4]:
        running.update(TREBLE_STAGE_STEP_SET[stage])
        out[stage] = set(running)
    return out


def _mirror_around_c4(midi_num):
    c4 = 60
    return c4 - (midi_num - c4)


def _midi_to_step_octave(m):
    p = pitch.Pitch(midi=m)
    return (p.step, p.octave)


def _bass_cumulative_step_sets():
    treble = _treble_cumulative_step_sets()
    out = {}
    for stage in [1, 2, 3, 4]:
        out[stage] = {_midi_to_step_octave(_mirror_around_c4(_midi(s, o))) for s, o in treble[stage]}
    return out


def _weighted_interleave(stage_to_items):
    queues = {k: deque(v) for k, v in stage_to_items.items()}
    ordered = []
    while any(queues[k] for k in queues):
        # Weight by stage
        for stage_key in sorted(queues.keys()):
            # stage_key is (stage, key_complexity)
            # Higher stage weight for lower stage numbers
            stage_num = stage_key[0]
            weight = STAGE_WEIGHTS.get(stage_num, 1)
            for _ in range(weight):
                if queues[stage_key]:
                    ordered.append(queues[stage_key].popleft())
    return ordered


class Command(BaseCommand):
    help = "Generate Unit 1 note-name identification exercises from local Bach CIR corpus"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--clef", choices=["treble", "bass", "both"], default="both")
        parser.add_argument("--input-dir", default=os.path.join("data", "corpus", "bach"))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        author_email = options["author"]
        clef = options["clef"]
        corpus_dir = options["input_dir"]
        dry_run = options["dry_run"]

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"Author not found: {author_email}")

        if not os.path.isdir(corpus_dir):
            raise CommandError(f"Corpus directory missing: {corpus_dir}. Did you run import_music21_corpus?")

        cumulative_treble = _treble_cumulative_step_sets()
        cumulative_bass = _bass_cumulative_step_sets()

        created = []
        for filename in sorted(os.listdir(corpus_dir)):
            if not filename.endswith(".json"):
                continue
            with open(os.path.join(corpus_dir, filename), "r") as f:
                blob = json.load(f)

            score = blob.get("score", {})
            measures = score.get("measures", [])
            if len(measures) < 2:
                continue

            for target in (["treble", "bass"] if clef == "both" else [clef]):
                voice_name = "soprano" if target == "treble" else "bass"
                stage_map = cumulative_treble if target == "treble" else cumulative_bass

                for start_idx in range(0, len(measures) - 1):
                    end_idx = start_idx + 2
                    window_score = {
                        "meta": score.get("meta", {}),
                        "measures": measures[start_idx:end_idx],
                    }

                    try:
                        one_voice = strip_to_voice(window_score, voice_name)
                        validate_pitch_voice(one_voice, voice_name)
                    except ValueError:
                        continue

                    notes_data = []
                    any_chromatic = False
                    for m in one_voice.get("measures", []):
                        for staff_name in ["treble", "bass"]:
                            voice_list = m.get("staves", {}).get(staff_name, {}).get("voices", [])
                            if not voice_list:
                                continue
                            for voice_obj in voice_list:
                                for item in voice_obj.get("items", []):
                                    if item.get("kind") == "note":
                                        p = item.get("pitch", {})
                                        notes_data.append(p)
                                        if not p.get("is_diatonic", True):
                                            any_chromatic = True
                                    elif item.get("kind") == "chord":
                                        notes_data = []
                                        break
                                if not notes_data: break
                            if not notes_data: break

                    if any_chromatic:
                        continue
                    
                    if not notes_data or len(notes_data) < 6 or len(notes_data) > 14:
                        continue

                    stage = None
                    note_steps = set((p["step"], p["octave"]) for p in notes_data)
                    for candidate in [1, 2, 3, 4]:
                        if note_steps.issubset(stage_map[candidate]):
                            stage = candidate
                            break
                    
                    if stage is None:
                        continue

                    key_name = score.get("meta", {}).get("key", "C")
                    complexity = (stage * 10) + _key_complexity(key_name)

                    bwv = filename.replace(".json", "")
                    human_start = start_idx + 1
                    human_end = end_idx
                    desc = f"{bwv.upper()} mm.{human_start}-{human_end} - {voice_name.title()} (note_name) Stage {stage}"

                    if Exercise.objects.filter(description=desc).exists():
                        ex = Exercise.objects.get(description=desc)
                        if ex.complexity != complexity:
                            ex.complexity = complexity
                            if not dry_run:
                                ex.save()
                        created.append((target, stage, complexity, ex))
                        continue

                    payload = {
                        "type": "chorale_identification",
                        "analysisType": "note_name",
                        "score": one_voice,
                    }

                    if not dry_run:
                        ex = Exercise(
                            description=desc,
                            data=payload,
                            authored_by=author,
                            is_public=True,
                            skill_tags=["unit:1", "Note_Names"],
                            complexity=complexity,
                        )
                        ex.save()
                        created.append((target, stage, complexity, ex))

        if dry_run:
            self.stdout.write("Dry-run complete")
            return

        self._wire_playlists_and_course(author, created)
        self.stdout.write(f"Generation complete. created={len(created)}")

    def _wire_playlists_and_course(self, author, created):
        by_target = defaultdict(list)
        for target, stage, complexity, ex in created:
            by_target[target].append((stage, complexity, ex))

        for target, rows in by_target.items():
            playlist_name = "Unit 1 - Note Names (Treble)" if target == "treble" else "Unit 1 - Note Names (Bass)"
            try:
                playlist = Playlist.objects.get(name=playlist_name, authored_by=author)
            except Playlist.DoesNotExist:
                playlist = Playlist(
                    name=playlist_name,
                    authored_by=author,
                    is_public=True,
                    skill_tags=["unit:1", "Note_Names"],
                )
                playlist.save()

            stage_buckets = defaultdict(list)
            # Sort by complexity (Stage * 10 + NumAccidentals) then description
            sorted_rows = sorted(rows, key=lambda x: (x[1], x[2].description))
            for stage, complexity, ex in sorted_rows:
                stage_buckets[(stage, complexity % 10)].append(ex)
            
            ordered = _weighted_interleave(stage_buckets)

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for idx, ex in enumerate(ordered, start=1):
                m = ExercisePlaylistOrdered(playlist=playlist, exercise=ex, order=idx)
                m.save()

            try:
                course = Course.objects.get(title="Unit 1: Pitch & Staff Notation", authored_by=author)
            except Course.DoesNotExist:
                course = Course(
                    title="Unit 1: Pitch & Staff Notation",
                    authored_by=author,
                    is_public=True,
                )
                course.save()

            if not PlaylistCourseOrdered.objects.filter(course=course, playlist=playlist).exists():
                m = PlaylistCourseOrdered(course=course, playlist=playlist, order=1)
                m.save()
