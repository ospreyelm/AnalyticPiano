import copy
import json
import os
import re
from collections import defaultdict, deque

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from music21 import key

from apps.exercises.models import Course, Exercise, ExercisePlaylistOrdered, Playlist, PlaylistCourseOrdered
from apps.exercises.pitch_voice_utils import strip_to_voice, validate_pitch_voice
from apps.exercises.umto import UMTO, Metadata, Voices, VoiceEvent, Pitch, GradingSlice, AnalysisSlice, AnalysisLayer, InteractionMode
from apps.exercises.umto_factory import save_umto_exercise

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

TARGET_TO_VOICES = {
    "treble": ["soprano", "alto"],
    "bass": ["tenor", "bass"],
}

UNIT1_LANE_DEFS = (
    {
        "target": "treble",
        "lane": "identification",
        "playlist_name": "Unit 1 - Note Names (Treble)",
        "description_token": "(id)",
    },
    {
        "target": "bass",
        "lane": "identification",
        "playlist_name": "Unit 1 - Note Names (Bass)",
        "description_token": "(id)",
    },
    {
        "target": "treble",
        "lane": "analysis",
        "playlist_name": "Unit 1 - Note Names (Treble Name)",
        "description_token": "(analysis)",
    },
    {
        "target": "bass",
        "lane": "analysis",
        "playlist_name": "Unit 1 - Note Names (Bass Name)",
        "description_token": "(analysis)",
    },
    {
        "target": "treble",
        "lane": "exact",
        "playlist_name": "Unit 1 - Note Names (Treble Play)",
        "description_token": "(exact)",
    },
    {
        "target": "bass",
        "lane": "exact",
        "playlist_name": "Unit 1 - Note Names (Bass Play)",
        "description_token": "(exact)",
    },
)


# Signed diatonic index around C4 (C4=0), with room for extended interval work.
DIATONIC_INDEX_LIMIT = 21


STEP_ORDER = ("C", "D", "E", "F", "G", "A", "B")
STEP_TO_INDEX = {step: idx for idx, step in enumerate(STEP_ORDER)}


def _step_octave_to_diatonic_index(step, octave):
    return ((octave - 4) * 7) + STEP_TO_INDEX[step]


def _diatonic_index_to_step_octave(index_num):
    if index_num < -DIATONIC_INDEX_LIMIT or index_num > DIATONIC_INDEX_LIMIT:
        raise ValueError(f"diatonic index out of configured range: {index_num}")

    step_idx = index_num % 7
    octave = 4 + ((index_num - step_idx) // 7)
    return (STEP_ORDER[step_idx], octave)


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


def _mirror_diatonic_index(index_num):
    mirrored = -index_num
    if mirrored < -DIATONIC_INDEX_LIMIT or mirrored > DIATONIC_INDEX_LIMIT:
        raise ValueError(f"mirrored diatonic index out of configured range: {mirrored}")
    return mirrored


def _bass_cumulative_step_sets():
    treble = _treble_cumulative_step_sets()
    out = {}
    for stage in [1, 2, 3, 4]:
        out[stage] = {
            _diatonic_index_to_step_octave(_mirror_diatonic_index(_step_octave_to_diatonic_index(s, o)))
            for s, o in treble[stage]
        }
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


_DUR_QL = {"w": 4.0, "h": 2.0, "q": 1.0, "8": 0.5, "16": 0.25, "32": 0.125}


def _measure_ql(measure, voice_name):
    """Return total quarter-length of the first matching voice in a measure."""
    for staff in measure.get("staves", {}).values():
        for v in staff.get("voices", []):
            total = 0.0
            for item in v.get("items", []):
                d = item.get("duration", {})
                base = _DUR_QL.get(d.get("type", "q"), 1.0)
                total += base * (2.0 - 0.5 ** d["dots"]) if d.get("dots") else base
            return total
    return 0.0


def _full_measure_ql(time_sig):
    """Return expected quarter-length of a full measure from a 'N/D' time signature."""
    try:
        num, den = time_sig.split("/")
        return int(num) * (4.0 / int(den))
    except Exception:
        return 4.0


def _ql_to_rest_items(remaining_ql):
    """Return a list of rest CIR items that fill exactly remaining_ql quarter-lengths."""
    # Priority: largest value first. Plain durations before dotted of same magnitude.
    CANDIDATES = [
        (4.0,   "w",  0),
        (3.0,   "h",  1),
        (2.0,   "h",  0),
        (1.5,   "q",  1),
        (1.0,   "q",  0),
        (0.75,  "8",  1),
        (0.5,   "8",  0),
        (0.375, "16", 1),
        (0.25,  "16", 0),
        (0.125, "32", 0),
    ]
    items = []
    remaining_ql = round(remaining_ql, 5)
    while remaining_ql > 0.001:
        placed = False
        for dur_ql, dur_type, dots in CANDIDATES:
            if remaining_ql >= dur_ql - 0.001:
                items.append({"kind": "rest", "duration": {"type": dur_type, "dots": dots}})
                remaining_ql = round(remaining_ql - dur_ql, 5)
                placed = True
                break
        if not placed:
            break
    return items


def _voice_ql(voice_items):
    total = 0.0
    for item in voice_items:
        d = item.get("duration", {})
        base = _DUR_QL.get(d.get("type", "q"), 1.0)
        total += base * (2.0 - 0.5 ** d["dots"]) if d.get("dots") else base
    return total


def _pad_voice_to_full(voice_items, full_ql, prepend=False):
    """Pad voice_items to full_ql with rests. prepend=True puts rests before existing notes."""
    remaining = round(full_ql - _voice_ql(voice_items), 5)
    if remaining > 0.001:
        rests = _ql_to_rest_items(remaining)
        if prepend:
            voice_items[:0] = rests
        else:
            voice_items.extend(rests)


def _pad_score_measures(score, time_sig, is_upbeat=False):
    """In-place: pad every measure's voices to full_ql using rests.
    For upbeat scores, m[0] gets rests prepended (note lands at bar end)."""
    full_ql = _full_measure_ql(time_sig)
    for m_idx, m in enumerate(score.get("measures", [])):
        prepend = is_upbeat and m_idx == 0
        for staff in m.get("staves", {}).values():
            for v in staff.get("voices", []):
                _pad_voice_to_full(v["items"], full_ql, prepend=prepend)


def _has_long_consecutive_note_run(notes_data, max_allowed=3):
    """True if any identical pitch token repeats more than max_allowed times in a row."""
    run = 0
    previous = None
    for p in notes_data:
        token = (p.get("step"), p.get("octave"), p.get("alter", 0))
        if token == previous:
            run += 1
        else:
            previous = token
            run = 1
        if run > max_allowed:
            return True
    return False


def _extract_stage_from_description(description):
    match = re.search(r"S(\d+)\s*$", description or "")
    if not match:
        return None
    return int(match.group(1))


def _midi(step, octave, alter=0):
    semitones = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    return ((int(octave) + 1) * 12) + semitones[step] + int(alter)


def _lane_playlist_tags(target):
    clef_tag = "Read_Treble_Clef" if target == "treble" else "Read_Bass_Clef"
    return ["unit:1", "Note_Names", "enharmonic", "Enharmonic_Reading", clef_tag]


def _voice_window_to_matching_chords(one_voice_score):
    rows = []
    for measure in one_voice_score.get("measures", []):
        for staff in measure.get("staves", {}).values():
            for voice in staff.get("voices", []):
                for item in voice.get("items", []):
                    if item.get("kind") != "note":
                        continue
                    pitch = item.get("pitch", {})
                    if not all(k in pitch for k in ("step", "octave")):
                        continue
                    rows.append(
                        {
                            "visible": [_midi(pitch["step"], pitch["octave"], pitch.get("alter", 0))],
                            "hidden": [],
                            "rhythmValue": item.get("duration", {}).get("type", "q"),
                        }
                    )
    return rows


def _key_token(key_name):
    if not key_name:
        return "jC_"
    normalized = key_name.strip()
    is_minor = normalized.endswith('m') or (len(normalized) > 0 and normalized[0].islower())
    root = normalized
    if is_minor and normalized.endswith('m'):
        root = normalized[:-1]
    if root:
        root = root[0].upper() + root[1:]
    root = root.replace('-', 'b')
    prefix = 'i' if is_minor else 'j'
    suffix = '_' if len(root) == 1 else ''
    return f"{prefix}{root}{suffix}"




class Command(BaseCommand):
    help = "Generate Unit 1 note-name identification exercises from local Bach CIR corpus"

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument("--clef", choices=["treble", "bass", "both"], default="both")
        parser.add_argument("--input-dir", default=os.path.join("data", "corpus", "bach"))
        parser.add_argument("--max-per-playlist", type=int, default=36)
        parser.add_argument("--max-per-stage", type=int, default=12)
        parser.add_argument(
            "--lanes",
            choices=["exact", "analysis", "identification", "all", "both"],
            default="all",
            help="Which lane(s) to emit. 'all' or 'both' = exact + analysis + identification.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--cleanup-legacy", action="store_true",
                            help="Delete exercises with old (matching) and (note_name) descriptions")
        parser.add_argument("--file", help="Only process this specific filename (e.g. bwv2.6.json)")
        parser.add_argument(
            "--input-mode",
            choices=["dropdown", "text"],
            default="dropdown",
            help="Default input mode for identification exercises (dropdown or text).",
        )
        parser.add_argument(
            "--playlist-only",
            action="store_true",
            help="Skip exercise generation; only rebuild playlists from already-imported exercises.",
        )

    def handle(self, *args, **options):
        author_email = options["author"]
        clef = options["clef"]
        corpus_dir = options["input_dir"]
        max_per_playlist = options["max_per_playlist"]
        max_per_stage = options["max_per_stage"]
        lanes = options["lanes"]
        dry_run = options["dry_run"]
        cleanup_legacy = options["cleanup_legacy"]
        target_file = options["file"]
        playlist_only = options.get("playlist_only", False)
        exercise_created_count = 0
        exercise_updated_count = 0

        self.stdout.write(f"STARTED generate_unit1 author={author_email} clef={clef} lanes={lanes}")

        if playlist_only:
            self.stdout.write("--playlist-only: skipping exercise generation, rebuilding playlists only.")
            try:
                author = User.objects.get(email=author_email)
            except User.DoesNotExist:
                raise CommandError(f"Author not found: {author_email}")
            playlist_stats = self._wire_playlists_and_course(
                author,
                lanes=lanes,
                max_per_playlist=options["max_per_playlist"],
                max_per_stage=options["max_per_stage"],
            )
            self.stdout.write(
                f"COMPLETED (playlist-only) playlists_created={playlist_stats['created']} "
                f"playlists_updated={playlist_stats['updated']}"
            )
            return

        try:
            author = User.objects.get(email=author_email)
        except User.DoesNotExist:
            raise CommandError(f"Author not found: {author_email}")

        if cleanup_legacy:
            legacy_qs = Exercise.objects.filter(
                description__regex=r'\(matching\) Stage \d|\(note_name\) Stage \d'
            )
            count = legacy_qs.count()
            if not dry_run:
                legacy_qs.delete()
                self.stdout.write(f"Deleted {count} legacy exercises.")
            else:
                self.stdout.write(f"[dry-run] Would delete {count} legacy exercises.")

        if not os.path.isdir(corpus_dir):
            raise CommandError(f"Corpus directory missing: {corpus_dir}. Did you run import_music21_corpus?")

        cumulative_treble = _treble_cumulative_step_sets()
        cumulative_bass = _bass_cumulative_step_sets()

        created = []
        for filename in sorted(os.listdir(corpus_dir)):
            if not filename.endswith(".json"):
                continue
            if target_file and filename.lower() != target_file.lower():
                continue
            with open(os.path.join(corpus_dir, filename), "r") as f:
                blob = json.load(f)

            score = blob.get("score", {})
            measures = score.get("measures", [])
            if len(measures) < 2:
                continue

            for target in (["treble", "bass"] if clef == "both" else [clef]):
                stage_map = cumulative_treble if target == "treble" else cumulative_bass

                time_sig = score.get("meta", {}).get("time", "4/4")
                full_ql = _full_measure_ql(time_sig)

                for voice_name in TARGET_TO_VOICES[target]:
                    for start_idx in range(0, len(measures) - 1):
                        end_idx = start_idx + 2

                        # Extend upbeat windows to 3 measures so partial m1 isn't smooshed.
                        m1_ql = _measure_ql(measures[start_idx], voice_name)
                        is_upbeat = m1_ql < full_ql * 0.95
                        if is_upbeat and end_idx < len(measures):
                            end_idx = start_idx + 3

                        # Pad any incomplete measure (upbeat or truncated final bar) with rests.
                        raw_window = {
                            "meta": score.get("meta", {}),
                            "measures": measures[start_idx:end_idx],
                        }
                        window_score = copy.deepcopy(raw_window)
                        _pad_score_measures(window_score, time_sig, is_upbeat=is_upbeat)

                        try:
                            one_voice = strip_to_voice(window_score, voice_name)
                            validate_pitch_voice(one_voice, voice_name)
                        except ValueError:
                            continue

                        # Count rests from original (pre-padding) to avoid filtering upbeat windows.
                        try:
                            orig_voice = strip_to_voice(raw_window, voice_name)
                        except ValueError:
                            continue

                        notes_data = []
                        any_chromatic = False
                        orig_rest_count = 0
                        has_chord = False
                        for m in orig_voice.get("measures", []):
                            for staff_name in ["treble", "bass"]:
                                voice_list = m.get("staves", {}).get(staff_name, {}).get("voices", [])
                                for voice_obj in voice_list:
                                    for item in voice_obj.get("items", []):
                                        kind = item.get("kind")
                                        if kind == "note":
                                            p = item.get("pitch", {})
                                            notes_data.append(p)
                                            if not p.get("is_diatonic", True):
                                                any_chromatic = True
                                        elif kind == "rest":
                                            orig_rest_count += 1
                                        elif kind == "chord":
                                            has_chord = True

                        if has_chord or any_chromatic:
                            continue

                        if orig_rest_count > 2:
                            continue

                        if not notes_data or len(notes_data) < 6 or len(notes_data) > 14:
                            continue

                        if _has_long_consecutive_note_run(notes_data, max_allowed=3):
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

                        clef_tag = "Read_Treble_Clef" if target == "treble" else "Read_Bass_Clef"
                        base_tags = ["unit:1", "Note_Names", "enharmonic", "Enharmonic_Reading", clef_tag]
                        
                        # Filter the score to only include the specific target voice
                        voice_idx = 0 if voice_name in ["soprano", "tenor"] else 1
                        filtered_measures = []
                        for m in window_score["measures"]:
                            m_filtered = {
                                "number": m["number"],
                                "staves": {
                                    target: {
                                        "voices": [copy.deepcopy(m["staves"][target]["voices"][voice_idx])]
                                    }
                                }
                            }
                            # Set the voice direction to "auto" to allow VexFlow to determine stem directions
                            # for a single voice (instead of forcing up/down from the chorale context).
                            m_filtered["staves"][target]["voices"][0]["direction"] = "auto"
                            filtered_measures.append(m_filtered)

                        one_voice = {
                            "meta": copy.deepcopy(score["meta"]),
                            "measures": filtered_measures,
                        }
                        one_voice["meta"]["key"] = _key_token(key_name)


                        intro_text = (
                            f"{bwv.upper()}, measures {human_start}-{human_end}, "
                            f"{voice_name.title()} voice."
                        )

                        if lanes in ("exact", "all", "both"):
                            exact_desc = f"{bwv.upper()} m.{human_start}-{human_end} {voice_name.title()} (exact) S{stage}"
                            exact = (
                                Exercise.objects.filter(description=exact_desc, authored_by=author)
                                .defer("data")
                                .first()
                            )
                            if exact is None:
                                if not dry_run:
                                    exact = save_umto_exercise(
                                        description=exact_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id="TEMP",
                                            source=f"Play the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.PLAYBACK,
                                            target_voice=voice_name,
                                            unit=1,
                                        ),
                                    )
                                    self.stdout.write(f"CREATED exercise {exact.id}: {exact_desc}")
                                    exercise_created_count += 1
                            else:
                                if not dry_run:
                                    # Update via factory to ensure schema consistency
                                    exact = save_umto_exercise(
                                        description=exact_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id=exact.id,
                                            source=f"Play the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.PLAYBACK,
                                            target_voice=voice_name,
                                            unit=1,
                                        ),
                                        overwrite=True
                                    )
                                    self.stdout.write(f"UPDATED exercise {exact.id}: {exact_desc}")
                                    exercise_updated_count += 1
                            if exact is not None:
                                created.append((target, "exact", stage, complexity, exact))

                        if lanes in ("analysis", "all", "both"):
                            analysis_desc = f"{bwv.upper()} m.{human_start}-{human_end} {voice_name.title()} (analysis) S{stage}"
                            analysis_ex = (
                                Exercise.objects.filter(description=analysis_desc, authored_by=author)
                                .defer("data")
                                .first()
                            )
                            if analysis_ex is None:
                                if not dry_run:
                                    analysis_ex = save_umto_exercise(
                                        description=analysis_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id="TEMP",
                                            source=f"Name the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.ANALYSIS_MATCH,
                                            target_voice=voice_name,
                                            unit=1,
                                        ),
                                    )
                                    self.stdout.write(f"CREATED exercise {analysis_ex.id}: {analysis_desc}")
                                    exercise_created_count += 1
                            else:
                                if not dry_run:
                                    analysis_ex = save_umto_exercise(
                                        description=analysis_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id=analysis_ex.id,
                                            source=f"Name the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.ANALYSIS_MATCH,
                                            target_voice=voice_name,
                                            unit=1,
                                        ),
                                        overwrite=True
                                    )
                                    self.stdout.write(f"UPDATED exercise {analysis_ex.id}: {analysis_desc}")
                                    exercise_updated_count += 1
                            if analysis_ex is not None:
                                created.append((target, "analysis", stage, complexity, analysis_ex))

                        if lanes in ("identification", "all", "both"):
                            id_desc = f"{bwv.upper()} m.{human_start}-{human_end} {voice_name.title()} (id) S{stage}"
                            id_ex = (
                                Exercise.objects.filter(description=id_desc, authored_by=author)
                                .defer("data")
                                .first()
                            )
                            if id_ex is None:
                                if not dry_run:
                                    id_ex = save_umto_exercise(
                                        description=id_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id="TEMP",
                                            source=f"Identify the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.IDENTIFICATION,
                                            target_voice=voice_name,
                                            input_mode=options["input_mode"],
                                            unit=1,
                                        ),
                                    )
                                    self.stdout.write(f"CREATED exercise {id_ex.id}: {id_desc}")
                                    exercise_created_count += 1
                            else:
                                if not dry_run:
                                    id_ex = save_umto_exercise(
                                        description=id_desc,
                                        score_data=one_voice,
                                        author=author,
                                        skill_tags=base_tags,
                                        complexity=complexity,
                                        auto_playlist=False,
                                        umto_kwargs=dict(
                                            exercise_id=id_ex.id,
                                            source=f"Identify the notes: {intro_text}",
                                            key=one_voice["meta"].get("key", "C"),
                                            meter=one_voice["meta"].get("time", "4/4"),
                                            clef=target,
                                            complexity_score=1,
                                            mode=InteractionMode.IDENTIFICATION,
                                            target_voice=voice_name,
                                            input_mode=options["input_mode"],
                                            unit=1,
                                        ),
                                        overwrite=True
                                    )
                                    self.stdout.write(f"UPDATED exercise {id_ex.id}: {id_desc}")
                                    exercise_updated_count += 1
                            if id_ex is not None:
                                created.append((target, "identification", stage, complexity, id_ex))

        if dry_run:
            self.stdout.write("Dry-run complete")
            return

        playlist_stats = self._wire_playlists_and_course(
            author,
            lanes=lanes,
            max_per_playlist=max_per_playlist,
            max_per_stage=max_per_stage,
        )
        self.stdout.write(
            "COMPLETED generate_unit1 "
            f"exercises_created={exercise_created_count} "
            f"exercises_updated={exercise_updated_count} "
            f"playlists_created={playlist_stats['created']} "
            f"playlists_updated={playlist_stats['updated']}"
        )
        self.stdout.write(f"Generation complete. created={len(created)}")

    def _lane_rows_from_db(self, author, lane_def):
        target = lane_def["target"]
        clef_tag = "Read_Treble_Clef" if target == "treble" else "Read_Bass_Clef"
        rows = (
            Exercise.objects.filter(authored_by=author, description__icontains=lane_def["description_token"])
            .filter(skill_tags__contains=["unit:1"])
            .filter(skill_tags__contains=["Note_Names"])
            .filter(skill_tags__contains=[clef_tag])
            .order_by("complexity", "description", "_id")
        )

        stage_buckets = defaultdict(list)
        for ex in rows:
            stage_num = _extract_stage_from_description(ex.description) or 1
            stage_buckets[(stage_num, ex.complexity % 10)].append(ex)

        ordered = _weighted_interleave(stage_buckets)
        return ordered

    def _cap_lane_rows(self, ordered, max_per_playlist=36, max_per_stage=12):
        if max_per_stage > 0:
            stage_counts = defaultdict(int)
            capped = []
            for ex in ordered:
                stage_num = _extract_stage_from_description(ex.description)
                if stage_num is None:
                    capped.append(ex)
                    continue
                if stage_counts[stage_num] >= max_per_stage:
                    continue
                stage_counts[stage_num] += 1
                capped.append(ex)
            ordered = capped

        if max_per_playlist > 0:
            ordered = ordered[:max_per_playlist]
        return ordered

    def _wire_playlists_and_course(self, author, lanes="both", max_per_playlist=36, max_per_stage=12):
        # "all" / "both" means every lane type is allowed; otherwise restrict to the named lane.
        all_lane_types = {"identification", "analysis", "exact"}
        if lanes in ("all", "both"):
            allowed_lanes = all_lane_types
        else:
            allowed_lanes = {lanes}
        playlist_created_count = 0
        playlist_updated_count = 0

        try:
            course = Course.objects.get(title="Unit 1: Pitch & Staff Notation", authored_by=author)
        except Course.DoesNotExist:
            course = Course(
                title="Unit 1: Pitch & Staff Notation",
                authored_by=author,
                is_public=True,
            )
            course.save()

        ordered_playlists = []
        for lane_def in UNIT1_LANE_DEFS:
            if lane_def["lane"] not in allowed_lanes:
                continue

            ordered = self._lane_rows_from_db(author, lane_def)
            ordered = self._cap_lane_rows(
                ordered,
                max_per_playlist=max_per_playlist,
                max_per_stage=max_per_stage,
            )

            playlist, was_created = Playlist.objects.get_or_create(
                name=lane_def["playlist_name"],
                authored_by=author,
                defaults=dict(
                    is_public=True,
                    skill_tags=_lane_playlist_tags(lane_def["target"]),
                ),
            )
            if was_created:
                playlist_created_count += 1
            else:
                playlist_updated_count += 1
            playlist.skill_tags = _lane_playlist_tags(lane_def["target"])
            playlist.is_public = True
            playlist.save()

            ExercisePlaylistOrdered.objects.filter(playlist=playlist).delete()
            for idx, ex in enumerate(ordered, start=1):
                stage_num = _extract_stage_from_description(ex.description) or 1
                diff_tier = 1
                if stage_num == 3:
                    diff_tier = 2
                elif stage_num >= 4:
                    diff_tier = 3

                ExercisePlaylistOrdered.objects.create(
                    playlist=playlist,
                    exercise=ex,
                    order=idx,
                    difficulty_tier=diff_tier,
                    is_mastery_challenge_source=(stage_num >= 4),
                )
            ordered_playlists.append(playlist)

        for index, playlist in enumerate(ordered_playlists, start=1):
            PlaylistCourseOrdered.objects.update_or_create(
                course=course,
                playlist=playlist,
                defaults={"order": index},
            )
        return {"created": playlist_created_count, "updated": playlist_updated_count}
