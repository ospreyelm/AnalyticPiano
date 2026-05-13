from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator

# Duration ordering: smaller index = shorter = harder
SMALLEST_VALUE_ORDER = ["16", "8", "q", "h", "w"]  # ascending duration

_LEVEL_DEFS = [
    # level, meters, smallest_dur_ceiling, ceiling_dots
    (1, {"3/4", "4/4"},               "q",  0),
    (2, {"2/4", "3/4", "4/4"},        "8",  0),
    (3, {"2/4", "3/4", "4/4"},        "16", 0),
    (4, {"6/8", "9/8", "12/8"},       "q",  1),
    (5, {"6/8", "9/8", "12/8"},       "8",  0),
    (6, {"6/8", "9/8", "12/8"},       "16", 0),
    (7, {"2/2", "3/2", "4/2"},        "8",  0),
    (8, {"6/4", "9/4", "12/4"},       "8",  0),
]

_DUR_FRACTION = {
    "w":  Fraction(1, 1),
    "h":  Fraction(1, 2),
    "q":  Fraction(1, 4),
    "8":  Fraction(1, 8),
    "16": Fraction(1, 16),
}


def _dur_value(duration: str, dots: int = 0) -> Fraction:
    base = _DUR_FRACTION[duration]
    total = base
    add = base
    for _ in range(dots):
        add /= 2
        total += add
    return total


def assign_level(time_signature: str, smallest_dur: str, dots: int = 0) -> int | None:
    """Return the lowest level number this phrase qualifies for, or None."""
    phrase_smallest = _dur_value(smallest_dur, dots)
    for level, meters, ceiling_dur, ceiling_dots in _LEVEL_DEFS:
        if time_signature not in meters:
            continue
        ceiling = _dur_value(ceiling_dur, ceiling_dots)
        if phrase_smallest >= ceiling:
            return level
    return None


from apps.exercises.utils.barline_exercise_builder import meter_info, duration_quarters


def _total_bars_quarters(time_signature: str, measures: int) -> Fraction:
    beats_per_measure, beat_quarters = meter_info(time_signature)
    return Fraction(measures * beats_per_measure) * beat_quarters


def is_valid_phrase(time_signature: str, notes: list[dict], measures: int) -> bool:
    try:
        beats_per_measure, beat_quarters = meter_info(time_signature)
    except ValueError:
        return False

    expected = _total_bars_quarters(time_signature, measures)
    actual = sum(duration_quarters(n["duration"], n.get("dots", 0)) for n in notes)
    if actual != expected:
        return False

    if len(notes) >= 2:
        last = duration_quarters(notes[-1]["duration"], notes[-1].get("dots", 0))
        prev = duration_quarters(notes[-2]["duration"], notes[-2].get("dots", 0))
        if last < prev:
            return False

    return True


_DOUBLE_MAP = {
    "16": "8",
    "8":  "q",
    "q":  "h",
    "h":  "w",
}


def double_durations(notes: list[dict]) -> list[dict]:
    result = []
    for n in notes:
        dur = n["duration"]
        dots = n.get("dots", 0)
        if dur not in _DOUBLE_MAP:
            raise ValueError(f"Cannot double duration '{dur}': would exceed whole note")
        new_dur = _DOUBLE_MAP[dur]
        if new_dur == "w" and dots > 0:
            raise ValueError(f"Cannot double dotted {dur}: would exceed whole note")
        result.append({**n, "duration": new_dur, "dots": dots})
    return result


def phrase_fingerprint(time_signature: str, notes: list[dict]) -> str:
    rhythm = ",".join(f"{n['duration']}.{n.get('dots', 0)}" for n in notes)
    raw = f"{time_signature}|{rhythm}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


_M21_DUR_TYPE = {
    "whole":    "w",
    "half":     "h",
    "quarter":  "q",
    "eighth":   "8",
    "16th":     "16",
}

_DERIVE_METER = {
    "2/4": "2/2", "3/4": "3/2", "4/4": "4/2",
    "6/8": "6/4", "9/8": "9/4", "12/8": "12/4",
}

_DERIVED_LEVELS = {7, 8}
_L7_SOURCES = {2, 3}
_L8_SOURCES = {5, 6}


@dataclass
class PhraseResult:
    level: int
    time_signature: str
    notes: list[dict]
    measures: int
    source_path: str
    phrase_offset: int
    fingerprint: str


def _iter_corpus_streams(collections=("ryansMammoth", "oneills1850", "essenFolksong")):
    from music21 import corpus, converter, stream as m21stream
    for path in corpus.getPaths():
        path_str = str(path)
        if not any(c in path_str for c in collections):
            continue
        try:
            parsed = converter.parse(path_str)
        except Exception:
            continue
        if isinstance(parsed, m21stream.Opus):
            for score in parsed.scores:
                yield path_str, score
        else:
            yield path_str, parsed


def _extract_notes_from_stream(stream) -> tuple[str | None, list[dict]]:
    try:
        ts_list = list(stream.recurse().getElementsByClass("TimeSignature"))
        if not ts_list:
            return None, []
        ts = ts_list[0]
        time_sig = f"{ts.numerator}/{ts.denominator}"
        notes_and_rests = list(stream.flatten().notesAndRests)
        notes = []
        for elem in notes_and_rests:
            if elem.isRest:
                return None, []
            if not elem.isNote:
                continue
            if elem.tie and elem.tie.type in ("stop", "continue"):
                return None, []
            dur_type = elem.duration.type
            if dur_type not in _M21_DUR_TYPE:
                return None, []
            dots = elem.duration.dots
            pitch_step = elem.pitch.step
            acc = elem.pitch.accidental
            alter = int(acc.alter) if acc else 0
            octave = elem.pitch.octave
            pitch_name = pitch_step + ("#" if alter > 0 else "b" if alter < 0 else "") + str(octave)
            notes.append({"pitch": pitch_name, "duration": _M21_DUR_TYPE[dur_type], "dots": dots})
        return time_sig, notes
    except Exception:
        return None, []


def _slice_phrases(notes: list[dict], time_signature: str, prefer_bars: int, fallback_bars: int) -> list[tuple[list[dict], int]]:
    try:
        beats_per_measure, beat_quarters = meter_info(time_signature)
    except ValueError:
        return []
    bar_quarters = Fraction(beats_per_measure) * beat_quarters
    results = []
    for target_bars in (prefer_bars, fallback_bars):
        target_quarters = bar_quarters * target_bars
        i = 0
        while i < len(notes):
            accumulated = Fraction(0)
            j = i
            phrase = []
            while j < len(notes) and accumulated < target_quarters:
                n = notes[j]
                accumulated += duration_quarters(n["duration"], n.get("dots", 0))
                phrase.append(n)
                j += 1
            if accumulated == target_quarters and len(phrase) > 0:
                results.append((phrase, i))
                i = j
            else:
                i += 1
    return results


def _compute_measures(notes: list[dict], time_signature: str) -> int:
    beats_per_measure, beat_quarters = meter_info(time_signature)
    bar_q = Fraction(beats_per_measure) * beat_quarters
    phrase_q = sum(duration_quarters(n["duration"], n.get("dots", 0)) for n in notes)
    return int(phrase_q / bar_q)


def iter_phrases(levels: list[int] | None = None) -> Iterator[PhraseResult]:
    target_levels = set(levels) if levels is not None else set(range(1, 9))
    source_levels = target_levels - _DERIVED_LEVELS
    need_l7 = 7 in target_levels
    need_l8 = 8 in target_levels

    seen_fingerprints: set[str] = set()

    def _emit(level, time_sig, notes, measures, source_path, offset) -> PhraseResult | None:
        fp = phrase_fingerprint(time_sig, notes)
        if fp in seen_fingerprints:
            return None
        if not is_valid_phrase(time_sig, notes, measures):
            return None
        seen_fingerprints.add(fp)
        return PhraseResult(
            level=level,
            time_signature=time_sig,
            notes=notes,
            measures=measures,
            source_path=source_path,
            phrase_offset=offset,
            fingerprint=fp,
        )

    for source_path, stream in _iter_corpus_streams():
        time_sig, all_notes = _extract_notes_from_stream(stream)
        if not time_sig or not all_notes:
            continue

        smallest_val = min(_dur_value(n["duration"], n.get("dots", 0)) for n in all_notes)
        smallest_dur = min(_DUR_FRACTION, key=lambda d: abs(_DUR_FRACTION[d] - smallest_val))
        smallest_dots = 1 if smallest_val < _DUR_FRACTION[smallest_dur] else 0

        direct_level = assign_level(time_sig, smallest_dur, smallest_dots)

        if direct_level in source_levels:
            prefer = 4 if direct_level in {3, 5, 6} else 2
            for phrase, offset in _slice_phrases(all_notes, time_sig, prefer, 2):
                measures = _compute_measures(phrase, time_sig)
                result = _emit(direct_level, time_sig, phrase, measures, source_path, offset)
                if result:
                    yield result

        derived_ts = _DERIVE_METER.get(time_sig)
        derived_target = None
        if derived_ts and direct_level is not None:
            if need_l7 and direct_level in _L7_SOURCES:
                derived_target = 7
            elif need_l8 and direct_level in _L8_SOURCES:
                derived_target = 8

        if derived_target and derived_ts:
            try:
                doubled = double_durations(all_notes)
            except ValueError:
                continue
            for phrase, offset in _slice_phrases(doubled, derived_ts, 4, 2):
                measures = _compute_measures(phrase, derived_ts)
                result = _emit(derived_target, derived_ts, phrase, measures, source_path, offset)
                if result:
                    yield result
