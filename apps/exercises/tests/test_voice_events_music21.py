import pytest

from apps.exercises.umto import Pitch, VoiceEvent, Voices

m21 = pytest.importorskip("music21")


def _satb_c_major_triad():
    """One onset: C3/E4/G4/C5 (a C-major sonority across SATB)."""
    return Voices(
        S=[VoiceEvent(kind="note", pitch=Pitch(step="C", alter=0, octave=5, midi=72),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        A=[VoiceEvent(kind="note", pitch=Pitch(step="G", alter=0, octave=4, midi=67),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        T=[VoiceEvent(kind="note", pitch=Pitch(step="E", alter=0, octave=4, midi=64),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
        B=[VoiceEvent(kind="note", pitch=Pitch(step="C", alter=0, octave=3, midi=48),
                      duration=4.0, duration_type="w", dots=0, is_target=True)],
    )


def test_converter_preserves_midi_pitches():
    from apps.exercises.utils.voice_events_music21 import score_from_voices
    score = score_from_voices(_satb_c_major_triad())
    midis = sorted(n.pitch.midi for n in score.recurse().notes)
    assert midis == [48, 64, 67, 72]


def test_converter_chordifies_to_one_vertical():
    from apps.exercises.utils.voice_events_music21 import score_from_voices
    score = score_from_voices(_satb_c_major_triad())
    chords = list(score.chordify().recurse().getElementsByClass("Chord"))
    assert len(chords) == 1
    assert sorted(p.midi for p in chords[0].pitches) == [48, 64, 67, 72]
