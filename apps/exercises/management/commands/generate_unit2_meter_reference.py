import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from music21 import meter


ALLOWED_SIGNATURES = [
    "2/2",
    "2/4",
    "2/8",
    "2/16",
    "3/2",
    "3/4",
    "3/8",
    "3/16",
    "4/2",
    "4/4",
    "4/8",
    "4/16",
    "6/2",
    "6/4",
    "6/8",
    "6/16",
    "9/2",
    "9/4",
    "9/8",
    "9/16",
    "12/2",
    "12/4",
    "12/8",
    "12/16",
]

QL_TO_LABEL = {
    0.125: "thirty-second",
    0.25: "sixteenth",
    0.5: "eighth",
    0.75: "dotted eighth",
    1.0: "quarter",
    1.5: "dotted quarter",
    2.0: "half",
    3.0: "dotted half",
    4.0: "whole",
    6.0: "dotted whole",
}


def quarter_length_to_label(value):
    rounded = round(float(value), 6)
    try:
        return QL_TO_LABEL[rounded]
    except KeyError as exc:
        raise CommandError(
            f"Unsupported quarterLength for Unit 2 meter labels: {rounded}"
        ) from exc


def _normalize_words(text):
    return text.strip().lower()


def _canonical_meter_parts(numerator, classification):
    parts = classification.split()
    if len(parts) == 2 and parts[0] in ("simple", "compound"):
        return parts[0], parts[1]

    # music21 reports 3/8 and 3/16 as "Other Single"; Phase 1 treats them as
    # simple triple for pedagogical consistency with the spec formulas.
    if numerator in (2, 3, 4):
        division_type = "simple"
    elif numerator in (6, 9, 12):
        division_type = "compound"
    else:
        raise CommandError(f"Unsupported numerator for Unit 2 signatures: {numerator}")

    grouping_map = {2: "duple", 3: "triple", 4: "quadruple", 6: "duple", 9: "triple", 12: "quadruple"}
    try:
        grouping = grouping_map[numerator]
    except KeyError as exc:
        raise CommandError(f"Unsupported grouping numerator: {numerator}") from exc

    return division_type, grouping


def validate_reference_entry(entry):
    numerator = entry["numerator"]
    denominator = entry["denominator"]
    division_type = entry["division_type"]

    if division_type == "simple":
        expected_beat_count = numerator
        expected_division_count = numerator * 2
        expected_division_value = quarter_length_to_label(4 / (denominator * 2))
        expected_beat_value = quarter_length_to_label(4 / denominator)
    elif division_type == "compound":
        if numerator % 3 != 0:
            raise CommandError(
                f"Compound signature must divide evenly by 3: {entry['time_signature']}"
            )
        expected_beat_count = numerator // 3
        expected_division_count = numerator
        expected_division_value = quarter_length_to_label(4 / denominator)
        expected_beat_value = quarter_length_to_label((4 / denominator) * 3)
    else:
        raise CommandError(f"Unexpected division_type: {division_type}")

    if entry["beat_count"] != expected_beat_count:
        raise CommandError(
            f"Bad beat_count for {entry['time_signature']}: {entry['beat_count']}"
        )
    if entry["division_count"] != expected_division_count:
        raise CommandError(
            f"Bad division_count for {entry['time_signature']}: {entry['division_count']}"
        )
    if entry["beat_value"] != expected_beat_value:
        raise CommandError(
            f"Bad beat_value for {entry['time_signature']}: {entry['beat_value']}"
        )
    if entry["division_value"] != expected_division_value:
        raise CommandError(
            f"Bad division_value for {entry['time_signature']}: {entry['division_value']}"
        )
    if denominator not in (2, 4, 8, 16):
        raise CommandError(f"Unsupported denominator in {entry['time_signature']}")


def build_reference_entry(ts_string):
    ts = meter.TimeSignature(ts_string)
    classification = _normalize_words(ts.classification)
    numerator, denominator = [int(x) for x in ts_string.split("/")]
    division_type, grouping = _canonical_meter_parts(numerator, classification)
    full_meter = f"{division_type} {grouping}"

    if division_type == "compound":
        beat_count = numerator // 3
        division_count = numerator
        beat_q_len = (4 / denominator) * 3
        division_q_len = 4 / denominator
    else:
        beat_count = numerator
        division_count = numerator * 2
        beat_q_len = 4 / denominator
        division_q_len = 4 / (denominator * 2)

    # touch music21's decomposition API so generation still runs through the
    # music21 meter object before emitting canonicalized values.
    if not ts.beatDivisionCountName:
        raise CommandError(f"Unable to read beatDivisionCountName for {ts_string}")

    entry = {
        "time_signature": ts_string,
        "numerator": numerator,
        "denominator": denominator,
        "division_type": division_type,
        "grouping": grouping,
        "full_meter": full_meter,
        "beat_count": beat_count,
        "division_count": division_count,
        "beat_value": quarter_length_to_label(beat_q_len),
        "division_value": quarter_length_to_label(division_q_len),
    }
    validate_reference_entry(entry)
    return entry


class Command(BaseCommand):
    help = "Generate apps/exercises/data/unit2_meter_reference.json from music21"

    def handle(self, *args, **options):
        data = [build_reference_entry(ts) for ts in ALLOWED_SIGNATURES]
        path = Path("apps/exercises/data/unit2_meter_reference.json")
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))
