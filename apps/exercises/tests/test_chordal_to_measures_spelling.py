import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "harmony.settings.ci")
try:
    django.setup()
except Exception:
    pass

from apps.exercises.umto_factory import _chordal_to_measures


def _all_pitches(measures):
    out = []
    for m in measures:
        for staff in m["staves"].values():
            for voice in staff["voices"]:
                for item in voice["items"]:
                    if item.get("kind") == "note":
                        out.append((item["pitch"]["step"], item["pitch"]["alter"]))
                    elif item.get("kind") == "chord":
                        for n in item["notes"]:
                            out.append((n["pitch"]["step"], n["pitch"]["alter"]))
    return out


def test_honors_stored_spelling():
    chords = [{"offset": 0.0, "duration": 4.0, "visible": [70], "hidden": [],
               "spelling": ["Bb4"]}]
    measures = _chordal_to_measures(chords, "4/4")
    pitches = _all_pitches(measures)
    assert ("B", -1) in pitches
    assert ("A", 1) not in pitches


def test_defaults_without_spelling():
    chords = [{"offset": 0.0, "duration": 4.0, "visible": [70], "hidden": []}]
    measures = _chordal_to_measures(chords, "4/4")
    # No spelling -> existing default (sharp table) -> A#
    assert ("A", 1) in _all_pitches(measures)
