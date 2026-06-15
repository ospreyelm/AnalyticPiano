import re
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from music21 import stream
from music21.corpus import chorales

from apps.exercises.management.commands.import_bach_phrases import _parse_riemenschneider_arg
from apps.exercises.models import Exercise
from apps.exercises.utils.m21_cir_converter import m21_to_cir


BACH_PHRASE_RE = re.compile(
    r"\bBach\s+R(?P<riemenschneider>\d+)\s+-\s+Phrase\s+\d+\s+"
    r"\(mm\.(?P<start>\d+)-(?P<end>\d+)\)\s+\[(?P<mode>[^\]]+)\]"
)


_DURATION_QL = {
    "w": 4.0,
    "h": 2.0,
    "q": 1.0,
    "8": 0.5,
    "16": 0.25,
    "32": 0.125,
}


def _duration_ql(item: dict) -> float:
    duration = item.get("duration", {})
    base = _DURATION_QL.get(duration.get("type"), 0.0)
    dots = int(duration.get("dots", 0) or 0)
    return base * (2.0 - 0.5 ** dots) if dots else base


def _measure_duration_ql(measure: dict) -> float:
    max_duration = 0.0
    for staff in measure.get("staves", {}).values():
        for voice in staff.get("voices", []):
            voice_duration = sum(_duration_ql(item) for item in voice.get("items", []))
            max_duration = max(max_duration, voice_duration)
    return round(max_duration, 6)


def _measure_durations(measures: list[dict]) -> list[float]:
    return [_measure_duration_ql(measure) for measure in measures]


def _barline_offsets(measures: list[dict]) -> list[float]:
    offsets = []
    cursor = 0.0
    for measure in measures[:-1]:
        cursor = round(cursor + _measure_duration_ql(measure), 6)
        if cursor > 0:
            offsets.append(cursor)
    return offsets


def _parse_bach_phrase(description: str | None) -> dict | None:
    match = BACH_PHRASE_RE.search(description or "")
    if not match:
        return None
    return {
        "riemenschneider": int(match.group("riemenschneider")),
        "start": int(match.group("start")),
        "end": int(match.group("end")),
        "mode": match.group("mode"),
    }


def _clean_phrase(score, start_measure: int, end_measure: int):
    phrase_score = score.measures(start_measure, end_measure)
    for part in phrase_score.parts:
        for measure in list(part.getElementsByClass(stream.Measure)):
            if measure.number > end_measure:
                part.remove(measure)

        measures_by_number = {}
        for measure in list(part.getElementsByClass(stream.Measure)):
            measures_by_number.setdefault(measure.number, []).append(measure)

        for number, measures in list(measures_by_number.items()):
            if len(measures) <= 1:
                continue
            if number == end_measure:
                extras = measures[1:]
            elif number == start_measure:
                extras = measures[:-1]
            else:
                extras = measures[:-1]
            for extra in extras:
                part.remove(extra)
    return phrase_score


def _score_cache_key(riemenschneider: int):
    return riemenschneider


def _expected_measures_for_slice(
    *,
    riemenschneider: int,
    start_measure: int,
    end_measure: int,
    key_override: str | None,
    score_cache: dict[int, object],
) -> list[dict]:
    cache_key = _score_cache_key(riemenschneider)
    if cache_key not in score_cache:
        score_cache[cache_key] = list(
            chorales.Iterator(
                riemenschneider,
                riemenschneider,
                numberingSystem="riemenschneider",
            )
        )[0]
    cir_data = m21_to_cir(
        _clean_phrase(score_cache[cache_key], start_measure, end_measure),
        key_override=key_override,
    )
    return cir_data.get("measures", [])


def _exercise_key_override(exercise: Exercise) -> str | None:
    data = exercise.data or {}
    return data.get("key") or data.get("score", {}).get("meta", {}).get("key")


def _repair_exercise_data(data: dict, expected_measures: list[dict]) -> dict:
    repaired = deepcopy(data)
    score = repaired.setdefault("score", {})
    score["measures"] = deepcopy(expected_measures)
    metadata = score.setdefault("umto", {}).setdefault("metadata", {})
    metadata["barline_offsets"] = _barline_offsets(expected_measures)
    return repaired


class Command(BaseCommand):
    help = (
        "Dry-run or repair Bach Riemenschneider phrase rows whose stored "
        "legacy measures were rebarred incorrectly after UMTO flattening."
    )

    def add_arguments(self, parser):
        parser.add_argument("--author", required=True)
        parser.add_argument(
            "--riemenschneider",
            help="Optional Riemenschneider number/range/list to audit or repair.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Update mismatched Exercise.data rows. Dry-run only without this flag.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Print each mismatched exercise with expected and stored durations.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            author = User.objects.get(email=options["author"])
        except User.DoesNotExist:
            raise CommandError(f"No user with email '{options['author']}'.")

        riem_filter = None
        if options["riemenschneider"]:
            riem_filter = set(_parse_riemenschneider_arg(options["riemenschneider"]))

        queryset = Exercise.objects.filter(
            authored_by=author,
            description__startswith="Bach R",
        ).order_by("description", "id")
        candidates = list(queryset)

        checked = 0
        skipped = 0
        load_errors = []
        mismatches = []
        score_cache = {}

        for exercise in candidates:
            parsed = _parse_bach_phrase(exercise.description)
            if parsed is None:
                skipped += 1
                continue
            if riem_filter is not None and parsed["riemenschneider"] not in riem_filter:
                skipped += 1
                continue

            checked += 1
            try:
                actual_measures = (exercise.data or {}).get("score", {}).get("measures", [])
                expected_measures = _expected_measures_for_slice(
                    riemenschneider=parsed["riemenschneider"],
                    start_measure=parsed["start"],
                    end_measure=parsed["end"],
                    key_override=_exercise_key_override(exercise),
                    score_cache=score_cache,
                )
            except Exception as exc:
                load_errors.append((exercise, exc))
                continue

            actual_durations = _measure_durations(actual_measures)
            expected_durations = _measure_durations(expected_measures)
            if actual_durations == expected_durations:
                continue

            mismatches.append(
                {
                    "exercise": exercise,
                    "expected_measures": expected_measures,
                    "expected_durations": expected_durations,
                    "actual_durations": actual_durations,
                    "barline_offsets": _barline_offsets(expected_measures),
                }
            )

        self.stdout.write(f"Author: {author.email}")
        if riem_filter is not None:
            self.stdout.write(
                "Riemenschneider filter: "
                + ", ".join(str(n) for n in sorted(riem_filter))
            )
        self.stdout.write(f"Checked exercises: {checked}")
        self.stdout.write(f"Skipped exercises: {skipped}")
        self.stdout.write(f"Mismatched exercises: {len(mismatches)}")
        self.stdout.write(f"Load errors: {len(load_errors)}")

        if options["list"]:
            for mismatch in mismatches:
                exercise = mismatch["exercise"]
                self.stdout.write(
                    f"  {exercise.id}: {exercise.description} "
                    f"stored={mismatch['actual_durations']} "
                    f"source={mismatch['expected_durations']} "
                    f"barlines={mismatch['barline_offsets']}"
                )
            for exercise, exc in load_errors:
                self.stdout.write(
                    self.style.WARNING(
                        f"  ERROR {exercise.id}: {exercise.description}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        if not options["execute"]:
            self.stdout.write("Dry run only. Pass --execute to repair mismatched exercises.")
            return

        with transaction.atomic():
            for mismatch in mismatches:
                exercise = mismatch["exercise"]
                exercise.data = _repair_exercise_data(
                    exercise.data or {},
                    mismatch["expected_measures"],
                )
                exercise.save(update_fields=["data"])

        self.stdout.write(self.style.SUCCESS(f"Repaired {len(mismatches)} exercises."))
