import json
from pathlib import Path


REFERENCE_PATH = Path("apps/exercises/data/unit2_meter_reference.json")
MANIFEST_PATH = Path("apps/exercises/data/unit2_symbolic_drill_manifest.json")


def load_reference_rows():
    return json.loads(REFERENCE_PATH.read_text())


def load_manifest_rows():
    return json.loads(MANIFEST_PATH.read_text())


def _grouping_choices(correct):
    return [x for x in ["duple", "triple", "quadruple"] if x != correct]


def _division_type_choices(correct):
    return [x for x in ["simple", "compound"] if x != correct]


def _full_meter_choices(correct):
    ordered = [
        "simple duple",
        "simple triple",
        "simple quadruple",
        "compound duple",
        "compound triple",
        "compound quadruple",
    ]
    return [x for x in ordered if x != correct]


def _ensure_four(correct, distractors, fallback=None):
    unique = []
    for value in [correct] + list(distractors):
        if value not in unique:
            unique.append(value)
    if fallback:
        for value in fallback:
            if value not in unique:
                unique.append(value)
            if len(unique) == 4:
                break
    return unique[:4]


def _note_value_choices(correct):
    ordered = [
        "sixteenth",
        "eighth",
        "dotted eighth",
        "quarter",
        "dotted quarter",
        "half",
        "dotted half",
        "whole",
        "dotted whole",
    ]
    return [x for x in ordered if x != correct]


def _build_explanation(subtype, source_signature, row):
    full_meter = row["full_meter"]
    if subtype == "meter_to_ts":
        return f"{source_signature} is a {full_meter} signature."
    return f"{source_signature} maps to {full_meter}."


def build_symbolic_problem(subtype, source_signature, reference_map):
    row = reference_map[source_signature]
    full_meter = row["full_meter"]

    if subtype == "ts_to_grouping":
        answer = row["grouping"]
        choices = _ensure_four(answer, _grouping_choices(answer), fallback=["duple", "triple", "quadruple"])
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_division_type":
        answer = row["division_type"]
        choices = _ensure_four(answer, _division_type_choices(answer), fallback=["simple", "compound"])
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_beat_value":
        answer = row["beat_value"]
        choices = _ensure_four(answer, [row["division_value"]], fallback=_note_value_choices(answer))
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_division_value":
        answer = row["division_value"]
        choices = _ensure_four(answer, [row["beat_value"]], fallback=_note_value_choices(answer))
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_beat_count":
        answer = str(row["beat_count"])
        choices = _ensure_four(
            answer,
            [str(row["division_count"]), str(row["numerator"]), "2", "3", "4", "6", "9", "12"],
        )
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_division_count":
        answer = str(row["division_count"])
        choices = _ensure_four(
            answer,
            [str(row["beat_count"]), str(row["numerator"]), "4", "6", "9", "12", "8"],
        )
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "ts_to_full_meter":
        answer = full_meter
        choices = _ensure_four(answer, _full_meter_choices(answer))
        prompt = {"kind": "time_signature", "text": source_signature}
    elif subtype == "meter_to_ts":
        answer = source_signature
        wrong = [
            k
            for k, v in reference_map.items()
            if v["full_meter"] != full_meter and k != source_signature
        ]
        choices = _ensure_four(answer, wrong)
        prompt = {"kind": "meter_label", "text": full_meter}
    else:
        raise ValueError(f"Unsupported subtype: {subtype}")

    return {
        "subtype": subtype,
        "prompt": prompt,
        "choices": choices,
        "answer": answer,
        "correct_index": choices.index(answer),
        "source_signature": source_signature,
        "explanation": _build_explanation(subtype, source_signature, row),
        "tags": ["unit:2", f"unit:2_{subtype}"],
    }


def build_symbolic_problem_set(manifest_rows):
    reference_map = {row["time_signature"]: row for row in load_reference_rows()}
    return [
        build_symbolic_problem(row["subtype"], row["source_signature"], reference_map)
        for row in manifest_rows
    ]
