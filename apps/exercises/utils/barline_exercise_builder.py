from fractions import Fraction
from math import lcm

SIMPLE_METERS = {
    "2/4": (2, Fraction(1, 1)),
    "3/4": (3, Fraction(1, 1)),
    "4/4": (4, Fraction(1, 1)),
}
COMPOUND_METERS = {
    "6/8": (2, Fraction(3, 2)),
    "9/8": (3, Fraction(3, 2)),
    "12/8": (4, Fraction(3, 2)),
}
DURATION_TO_QUARTERS = {
    "w": Fraction(4, 1),
    "h": Fraction(2, 1),
    "q": Fraction(1, 1),
    "8": Fraction(1, 2),
    "16": Fraction(1, 4),
}


def duration_quarters(duration, dots=0):
    if duration not in DURATION_TO_QUARTERS:
        raise ValueError(f"Unsupported duration: {duration}")
    base = DURATION_TO_QUARTERS[duration]
    total = base
    add = base
    for _ in range(int(dots or 0)):
        add /= 2
        total += add
    return total


def meter_info(time_signature):
    if time_signature in SIMPLE_METERS:
        beats_per_measure, beat_quarters = SIMPLE_METERS[time_signature]
        return beats_per_measure, beat_quarters
    if time_signature in COMPOUND_METERS:
        beats_per_measure, beat_quarters = COMPOUND_METERS[time_signature]
        return beats_per_measure, beat_quarters
    raise ValueError(f"Unsupported time signature: {time_signature}")


def _integer_tick_scale(values):
    scale = 1
    for value in values:
        scale = lcm(scale, value.denominator)
    return scale


def _as_fraction(value):
    if isinstance(value, Fraction):
        return value
    return Fraction(str(value))


def _payload_number(value):
    if value.denominator == 1:
        return int(value)
    return float(value)


def build_barline_payload(
    *,
    time_signature,
    clef,
    notes,
    measures,
    pickup_beats=0,
    show_time_signature,
    pitch_mode,
    source,
    tags=None,
):
    beats_per_measure, beat_quarters = meter_info(time_signature)
    pickup_beats_fraction = _as_fraction(pickup_beats)
    if pickup_beats_fraction < 0:
        raise ValueError("pickup_beats must be non-negative")
    if pickup_beats_fraction >= beats_per_measure:
        raise ValueError("pickup_beats must be smaller than one measure")
    total_quarters = sum(
        duration_quarters(note["duration"], note.get("dots", 0)) for note in notes
    )
    total_beats = pickup_beats_fraction + (Fraction(measures, 1) * beats_per_measure)
    expected_quarters = total_beats * beat_quarters
    if total_quarters != expected_quarters:
        raise ValueError(
            f"total duration {total_quarters} does not equal expected {expected_quarters}"
        )

    full_measure_beats = measures * beats_per_measure
    has_pickup = pickup_beats_fraction > 0
    beat_count = full_measure_beats + (1 if has_pickup else 0)
    slot_widths = []
    if has_pickup:
        slot_widths.append(pickup_beats_fraction * beat_quarters)
    slot_widths.extend([beat_quarters] * full_measure_beats)
    scale = _integer_tick_scale(slot_widths)
    beat_positions_ticks = [0]
    elapsed_ticks = Fraction(0, 1)
    for slot_width in slot_widths:
        elapsed_ticks += slot_width * scale
        beat_positions_ticks.append(int(elapsed_ticks))
    pickup_slot_count = 1 if has_pickup else 0
    correct_barline_positions = [0] if has_pickup else []
    correct_barline_positions.extend(
        pickup_slot_count + (measure_index * beats_per_measure) - 1
        for measure_index in range(1, measures)
    )
    note_beat_onsets = []
    elapsed_quarters = Fraction(0, 1)
    for note in notes:
        note_beat_onsets.append(_payload_number(elapsed_quarters / beat_quarters))
        elapsed_quarters += duration_quarters(note["duration"], note.get("dots", 0))

    return {
        "type": "umto_barline_placement",
        "isUMTO": True,
        "mode": "identification",
        "time_signature": time_signature,
        "show_time_signature": bool(show_time_signature),
        "clef": clef,
        "measures": measures,
        "pickup_beats": _payload_number(pickup_beats_fraction),
        "pitch_mode": pitch_mode,
        "notes": list(notes),
        "correct_barline_positions": correct_barline_positions,
        "beat_count": beat_count,
        "beat_positions_ticks": beat_positions_ticks,
        "note_beat_onsets": note_beat_onsets,
        "source": source,
        "tags": list(tags or ["unit:2", "unit:2_rhythm"]),
    }
