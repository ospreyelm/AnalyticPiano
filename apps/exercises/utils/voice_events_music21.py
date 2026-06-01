"""Build a music21 Score from UMTO VoiceEvent lists.

The generated VoiceEvents already carry MIDI in `pitch.midi`, so this converter
does not depend on the (separately fixed) music21_builder._pitch_to_midi helper.
One music21 Part per non-empty SATB voice; rests for `kind == "rest"`.
"""
from __future__ import annotations

from music21 import note, stream


def _append_event(part, event):
    ql = float(event.duration)
    if event.kind == "rest" or event.pitch is None:
        part.append(note.Rest(quarterLength=ql))
        return
    n = note.Note(midi=event.pitch.midi, quarterLength=ql)
    part.append(n)


def score_from_voices(voices) -> "stream.Score":
    score = stream.Score()
    for voice_id in ("S", "A", "T", "B"):
        events = getattr(voices, voice_id, None) or []
        if not events:
            continue
        part = stream.Part(id=voice_id)
        for event in events:
            _append_event(part, event)
        score.insert(0, part)
    return score
