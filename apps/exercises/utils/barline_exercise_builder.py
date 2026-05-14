from fractions import Fraction
from math import lcm

SIMPLE_METERS = {
    "2/4": (2, Fraction(1, 1)),
    "3/4": (3, Fraction(1, 1)),
    "4/4": (4, Fraction(1, 1)),
    "2/2": (2, Fraction(2, 1)),
    "3/2": (3, Fraction(2, 1)),
    "4/2": (4, Fraction(2, 1)),
}
COMPOUND_METERS = {
    "6/8": (2, Fraction(3, 2)),
    "9/8": (3, Fraction(3, 2)),
    "12/8": (4, Fraction(3, 2)),
    "6/4": (2, Fraction(3, 1)),
    "9/4": (3, Fraction(3, 1)),
    "12/4": (4, Fraction(3, 1)),
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


BEAMABLE_DURATIONS = {"8", "16", "32"}


def beaming_is_clean(notes, time_signature):
    """Return True if every beamable note (8th, 16th, 32nd) starts on an exact
    eighth-note subdivision within its beat group.  Phrases where a non-beamable
    note (e.g. quarter) ends mid-beat leave the next eighth starting at an
    off-grid position that VexFlow cannot beam correctly (issue #467)."""
    try:
        _, beat_quarters = meter_info(time_signature)
    except ValueError:
        return True  # unknown meter — don't filter
    beat = beat_quarters  # beat size in quarter-note units
    eighth = Fraction(1, 2)
    elapsed = Fraction(0)
    for note in notes:
        dur = duration_quarters(note["duration"], note.get("dots", 0))
        if note["duration"] in BEAMABLE_DURATIONS:
            pos_in_beat = elapsed % beat
            if pos_in_beat % eighth != 0:
                return False
        elapsed += dur
    return True


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
    # Compute note-index based barline positions: index of last note before each barline.
    # A barline after note index N means the cursor is placed at position N.
    bar_quarters = Fraction(beats_per_measure) * beat_quarters
    pickup_q = pickup_beats_fraction * beat_quarters
    note_beat_onsets = []
    correct_barline_positions = [0] if has_pickup else []
    elapsed_quarters = Fraction(0, 1)
    for note_idx, note in enumerate(notes):
        note_beat_onsets.append(_payload_number(elapsed_quarters / beat_quarters))
        elapsed_quarters += duration_quarters(note["duration"], note.get("dots", 0))
        # If elapsed (from note start, not pickup) hits a measure boundary, barline here.
        # Measure boundaries in note-time: pickup_q, pickup_q + bar_q, pickup_q + 2*bar_q ...
        note_elapsed = elapsed_quarters  # total from note 0 (no pickup offset)
        measures_elapsed = (note_elapsed - pickup_q) / bar_quarters
        if (measures_elapsed == int(measures_elapsed)
                and int(measures_elapsed) > 0
                and int(measures_elapsed) < measures):
            correct_barline_positions.append(note_idx)

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
